"""Run the extracted report with a synthetic ORM and a fresh SQLite memory DB."""
import ast
import builtins
from datetime import date
from decimal import Decimal, ROUND_HALF_UP, localcontext
import math
import os
import platform
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import sysconfig
import types
import unittest


def main():
    def refuse(*_args, **_kwargs):
        raise AssertionError('only the synthetic memory DB is permitted')

    connect = sqlite3.connect
    def memory_only(database, *args, **kwargs):
        if database != ':memory:' or kwargs.get('uri', False):
            refuse()
        return connect(database, *args, **kwargs)
    sqlite3.connect = sqlite3.dbapi2.connect = memory_only
    socket.socket.connect = socket.socket.connect_ex = refuse
    socket.getaddrinfo = socket.create_connection = refuse
    class DeniedPopen:
        def __init__(self, *_args, **_kwargs):
            refuse()
    subprocess.Popen = DeniedPopen
    platform.machine = lambda: 'synthetic'
    original_import = builtins.__import__
    def safe_import(name, *args, **kwargs):
        level = args[3] if len(args) > 3 else kwargs.get('level', 0)
        if level == 0 and (name == 'app' or name.startswith('app.')):
            refuse()
        return original_import(name, *args, **kwargs)
    builtins.__import__ = safe_import
    sys.path.append(sysconfig.get_paths()['purelib'])

    from flask import Flask, request
    from sqlalchemy import Column, Date, Float, ForeignKey, Integer, Numeric, String, and_, create_engine, or_
    from sqlalchemy.orm import declarative_base, joinedload, relationship, scoped_session, selectinload, sessionmaker

    Base = declarative_base()
    engine = create_engine('sqlite:///:memory:')
    session = scoped_session(sessionmaker(bind=engine))
    Base.query = session.query_property()

    class Warehouse(Base):
        __tablename__ = 'synthetic_warehouse'
        id = Column(Integer, primary_key=True)
        name = Column(String)
        code = Column(String)
        status = Column(String, default='active')

    class Customer(Base):
        __tablename__ = 'synthetic_customer'
        id = Column(Integer, primary_key=True)
        code = Column(String)
        name = Column(String)

    class Employee(Base):
        __tablename__ = 'synthetic_employee'
        id = Column(Integer, primary_key=True)
        name = Column(String)

    class Material(Base):
        __tablename__ = 'synthetic_material'
        id = Column(Integer, primary_key=True)
        code = Column(String)
        name = Column(String)

    class SalesOrder(Base):
        __tablename__ = 'synthetic_order'
        id = Column(Integer, primary_key=True)
        order_no = Column(String)
        date = Column(Date)
        warehouse_id = Column(Integer, ForeignKey('synthetic_warehouse.id'))
        warehouse = Column(String)
        customer_id = Column(Integer, ForeignKey('synthetic_customer.id'))
        salesperson_id = Column(Integer, ForeignKey('synthetic_employee.id'))
        customer = relationship(Customer)
        salesperson = relationship(Employee)
        status = Column(String)
        shipment_status = Column(String)
        project_no = Column(String)
        total_amount = Column(Numeric(18, 2))
        untaxed_amount = Column(Numeric(18, 2))
        tax_amount = Column(Numeric(18, 2))
        shipped_amount = Column(Numeric(18, 2))

    class SalesOrderItem(Base):
        __tablename__ = 'synthetic_order_item'
        id = Column(Integer, primary_key=True)
        order_id = Column(Integer, ForeignKey('synthetic_order.id'))
        material_id = Column(Integer, ForeignKey('synthetic_material.id'))
        material = relationship(Material)
        quantity = Column(Float)
        shipped_quantity = Column(Float)
        price = Column(Float)
        amount = Column(Numeric(18, 2))
        tax_rate = Column(Float)
        tax_included_amount = Column(Numeric(18, 2))
        untaxed_amount = Column(Numeric(18, 2))
        tax_amount = Column(Numeric(18, 2))
        order = relationship(SalesOrder, backref='items')

    Base.metadata.create_all(engine)
    a = Warehouse(name='Synthetic A', code='A')
    b = Warehouse(name='Synthetic B', code='B')
    customer = Customer(code='C', name='Synthetic customer')
    employee = Employee(name='Synthetic employee')
    material = Material(code='M', name='Synthetic material')
    session.add_all([a, b, customer, employee, material])
    session.flush()
    for index, wh in enumerate((a, b)):
        order = SalesOrder(order_no=f'SYN-{index}', date=date.today(), warehouse_id=wh.id,
                           warehouse=wh.name, customer=customer, salesperson=employee,
                           status='confirmed', shipment_status='shipped', project_no='P',
                           total_amount=.02, untaxed_amount=.02, tax_amount=0, shipped_amount=.02)
        session.add(order)
        for _ in range(2):
            session.add(SalesOrderItem(order=order, material=material, quantity=.01,
                                       shipped_quantity=.01, price=.5, amount=.01,
                                       tax_rate=0, tax_included_amount=.01,
                                       untaxed_amount=.01, tax_amount=0))
    session.commit()

    root = Path(__file__).resolve().parents[1]
    def function(path, name):
        tree = ast.parse((root / path).read_text(encoding='utf-8-sig'))
        found = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name]
        if len(found) != 1:
            raise AssertionError('missing or ambiguous source function: ' + name)
        node = found[0]
        node.decorator_list = []
        node.body = [n for n in node.body if not (isinstance(n, ast.ImportFrom) and n.module == 'app')]
        return node

    flask_app = Flask('synthetic-sales-summary')
    def require_synthetic_warehouse():
        warehouse_id = request.args.get('warehouse_id', type=int)
        return (session.get(Warehouse, warehouse_id) if warehouse_id is not None else None, None)

    env = {'Decimal': Decimal, 'ROUND_HALF_UP': ROUND_HALF_UP, 'localcontext': localcontext, 'math': math,
           'request': request, 'db': types.SimpleNamespace(session=session, or_=or_, and_=and_),
           'Warehouse': Warehouse, 'Customer': Customer, 'Employee': Employee,
           'Material': Material, 'SalesOrder': SalesOrder, 'SalesOrderItem': SalesOrderItem,
           'sales_status_label': lambda value: value,
           '_require_report_warehouse': require_synthetic_warehouse}
    nodes = [function('app/utils.py', 'round_to_2_decimals'),
             function('app/utils.py', 'round_money_product'),
             function('app/services/sales_report_print.py', 'sales_summary_context')]
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), '<synthetic-report>', 'exec'), env)

    class SummaryMemoryTests(unittest.TestCase):
        def report(self, **query):
            with flask_app.test_request_context('/synthetic', query_string=query):
                return env['sales_summary_context']()

        def test_warehouse_a_line_rounded_total(self):
            result = self.report(warehouse_id=a.id)
            self.assertEqual([x.order_no for x in result['orders']], ['SYN-0'])
            self.assertEqual(result['shipped_amount'], .02)
            self.assertEqual(result['total_amount'], .02)

        def test_warehouse_b_is_separate(self):
            result = self.report(warehouse_id=b.id)
            self.assertEqual([x.order_no for x in result['orders']], ['SYN-1'])
            self.assertEqual(result['shipped_amount'], .02)

        def test_missing_warehouse_returns_no_orders(self):
            result = self.report()
            self.assertEqual(result['orders'], [])
            self.assertEqual(result['shipped_amount'], 0)

        def test_detail_pagination_does_not_shrink_totals(self):
            result = self.report(warehouse_id=a.id, material_code='M', page=2, per_page=1)
            self.assertEqual(len(result['drill_items']), 1)
            self.assertEqual(result['drill_pagination'].total, 2)
            self.assertEqual(result['shipped_amount'], .02)

        def test_stale_saved_header_is_not_rewritten(self):
            order = session.query(SalesOrder).filter_by(order_no='SYN-0').one()
            previous = order.shipped_amount
            order.shipped_amount = Decimal('0.99')
            session.flush()
            try:
                result = self.report(warehouse_id=a.id)
                self.assertEqual(result['shipped_amount'], .02)
                self.assertEqual(order.shipped_amount, Decimal('0.99'))
            finally:
                order.shipped_amount = previous
                session.flush()

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(SummaryMemoryTests)
    if suite.countTestCases() != 5:
        raise RuntimeError('synthetic test list incomplete')
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    session.remove()
    engine.dispose()
    raise SystemExit(not result.wasSuccessful())


def test_sales_summary_in_synthetic_process():
    env = {key: os.environ[key] for key in ('SYSTEMROOT', 'WINDIR') if key in os.environ}
    result = subprocess.run([sys.executable, '-I', '-S', '-B', '-X', 'utf8', __file__],
                            env=env, capture_output=True, text=True, encoding='utf-8', timeout=30)
    assert result.returncode == 0, result.stderr


if __name__ == '__main__':
    main()
