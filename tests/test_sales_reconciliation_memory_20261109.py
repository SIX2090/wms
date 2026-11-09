"""Run both reconciliation entry points with a synthetic in-memory ORM."""
import ast
import builtins
from io import BytesIO
from datetime import date
from decimal import Decimal, DecimalException, ROUND_HALF_UP, localcontext
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
    from jinja2 import Template
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
        contract_no = Column(String)
        project_name = Column(String)
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

    class OutOrder(Base):
        __tablename__ = 'synthetic_out_order'
        id = Column(Integer, primary_key=True)
        sales_order_id = Column(Integer, ForeignKey('synthetic_order.id'))
        status = Column(String)
        warehouse = Column(String)
        order = relationship(SalesOrder, backref='outbound_orders')

    class OutOrderItem(Base):
        __tablename__ = 'synthetic_out_item'
        id = Column(Integer, primary_key=True)
        out_order_id = Column(Integer, ForeignKey('synthetic_out_order.id'))
        source_sales_order_item_id = Column(Integer, ForeignKey('synthetic_order_item.id'))
        material_id = Column(Integer, ForeignKey('synthetic_material.id'))
        quantity = Column(Float)
        amount = Column(Float)
        order = relationship(OutOrder, backref='items')
        source_sales_order_item = relationship(SalesOrderItem)

    class StockTransaction(Base):
        __tablename__ = 'synthetic_transaction'
        id = Column(Integer, primary_key=True)
        reference_type = Column(String)
        reference_id = Column(Integer)
        material_id = Column(Integer)
        transaction_type = Column(String)
        quantity = Column(Float)

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
        outbound = OutOrder(order=order, status='completed', warehouse=wh.name)
        session.add(outbound)
        session.add(OutOrderItem(order=outbound, material_id=material.id, quantity=.02, amount=.02))
    session.commit()

    root = Path(__file__).resolve().parents[1]
    def function(path, name):
        tree = ast.parse((root / path).read_text(encoding='utf-8-sig'))
        found = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name]
        if len(found) != 1:
            raise AssertionError('missing or ambiguous source function: ' + name)
        node = found[0]
        node.decorator_list = []
        node.body = [n for n in node.body if not (isinstance(n, ast.ImportFrom) and n.module in
                    ('app', 'openpyxl', 'services.sales_report_print', 'doc_print_excel'))]
        return node

    flask_app = Flask('synthetic-sales-summary')
    def require_synthetic_warehouse():
        warehouse_id = request.args.get('warehouse_id', type=int)
        return (session.get(Warehouse, warehouse_id) if warehouse_id is not None else None, None)

    env = {'Decimal': Decimal, 'DecimalException': DecimalException, 'ROUND_HALF_UP': ROUND_HALF_UP,
           'localcontext': localcontext, 'math': math,
           'request': request, 'db': types.SimpleNamespace(session=session, or_=or_, and_=and_),
           'Warehouse': Warehouse, 'Customer': Customer, 'Employee': Employee,
           'Material': Material, 'SalesOrder': SalesOrder, 'SalesOrderItem': SalesOrderItem,
           'StockTransaction': StockTransaction, 'STOCK_COMPARE_EPSILON': 1e-6,
           'sales_status_label': lambda value: value,
           '_require_report_warehouse': require_synthetic_warehouse}
    source_tree = ast.parse((root / 'app/services/sales_report_print.py').read_text(encoding='utf-8-sig'))
    note_nodes = [node.value for node in source_tree.body if isinstance(node, ast.Assign)
                  and any(isinstance(target, ast.Name) and target.id == '_RECONCILIATION_UNKNOWN_WAREHOUSE_NOTE'
                          for target in node.targets)]
    if len(note_nodes) != 1:
        raise AssertionError('missing or ambiguous unknown warehouse notice')
    env['_RECONCILIATION_UNKNOWN_WAREHOUSE_NOTE'] = ast.literal_eval(note_nodes[0])
    class Sheet:
        def __init__(self):
            self.rows = []
        def append(self, row):
            self.rows.append(row)
    class Workbook:
        def __init__(self):
            self.active = Sheet()
            self.other_sheets = {}
            env['synthetic_workbook'] = self
        def create_sheet(self, title):
            self.other_sheets[title] = Sheet()
            return self.other_sheets[title]
        def save(self, output):
            output.write(b'synthetic')
    env.update(Workbook=Workbook, send_file=lambda output, **_kwargs: env['synthetic_workbook'].active.rows,
               jsonify=lambda value: value)
    nodes = [function('app/utils.py', 'round_to_2_decimals'),
             function('app/services/sales_report_print.py', '_reconciliation_amounts'),
             function('app/services/sales_report_print.py', '_reconciliation_excel_amount'),
             function('app/services/sales_report_print.py', '_reconciliation_quantities'),
             function('app/services/sales_report_print.py', '_reconciliation_warehouse_filter'),
             function('app/services/sales_report_print.py', '_reconciliation_warehouse_aliases'),
             function('app/services/sales_report_print.py', '_reconciliation_warehouse_issue'),
             function('app/services/sales_report_print.py', 'sales_reconciliation_context'),
             function('app/services/sales_report_print.py', 'collect_sales_report_print'),
             function('app/routes/sales.py', 'export_sales_reconciliation_report')]
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), '<synthetic-report>', 'exec'), env)
    env['SALES_CONTEXT_BUILDERS'] = {'reconciliation': env['sales_reconciliation_context']}
    env['SALES_REPORT_PRINT_SPECS'] = {'reconciliation': ('合成对账', [])}

    class ReconciliationMemoryTests(unittest.TestCase):
        def report(self, **query):
            with flask_app.test_request_context('/synthetic', query_string=query):
                return env['sales_reconciliation_context']()

        def export(self, **query):
            with flask_app.test_request_context('/synthetic', query_string=query):
                return env['export_sales_reconciliation_report']()

        def print_data(self, **query):
            with flask_app.test_request_context('/synthetic', query_string=query):
                return env['collect_sales_report_print']('reconciliation')

        def test_warehouse_a_line_rounded_total(self):
            result = self.report(warehouse_id=a.id)
            self.assertEqual([x['order'].order_no for x in result['rows']], ['SYN-0'])
            self.assertTrue(result['rows'][0]['ok'])
            self.assertEqual(result['rows'][0]['amount_diff'], 0)

        def test_warehouse_b_is_separate(self):
            result = self.report(warehouse_id=b.id)
            self.assertEqual([x['order'].order_no for x in result['rows']], ['SYN-1'])
            self.assertTrue(result['rows'][0]['ok'])

        def test_missing_warehouse_returns_no_orders(self):
            result = self.report()
            self.assertEqual(result['rows'], [])

        def test_exactly_one_cent_is_within_tolerance(self):
            order = session.query(SalesOrder).filter_by(order_no='SYN-0').one()
            order.shipped_amount = Decimal('1.01')
            order.outbound_orders[0].items[0].amount = 1.0
            session.flush()
            try:
                result = self.report(warehouse_id=a.id)
                self.assertEqual(result['rows'][0]['amount_diff'], Decimal('.01'))
                self.assertTrue(result['rows'][0]['ok'])
                self.assertEqual(self.export(warehouse_id=a.id)[1][-1], '通过')
                self.assertEqual(self.print_data(warehouse_id=a.id)['rows'][0]['result'], '通过')
            finally:
                session.rollback()

        def test_more_than_one_cent_is_not_within_tolerance(self):
            order = session.query(SalesOrder).filter_by(order_no='SYN-0').one()
            order.shipped_amount = Decimal('1.02')
            order.outbound_orders[0].items[0].amount = 1.0
            session.flush()
            try:
                self.assertFalse(self.report(warehouse_id=a.id)['rows'][0]['ok'])
                self.assertEqual(self.export(warehouse_id=a.id)[1][-1], '不一致')
            finally:
                session.rollback()

        def test_missing_header_requires_manual_review(self):
            order = session.query(SalesOrder).filter_by(order_no='SYN-0').one()
            order.shipped_amount = None
            session.flush()
            try:
                row = self.report(warehouse_id=a.id)['rows'][0]
                self.assertFalse(row['ok'])
                self.assertIsNone(row['amount_diff'])
                self.assertEqual(self.export(warehouse_id=a.id)[1][-1], '待人工核对')
                printed = self.print_data(warehouse_id=a.id)['rows'][0]
                self.assertEqual(printed['result'], '待人工核对')
                self.assertIsNone(printed['amount_diff'])
            finally:
                session.rollback()

        def test_precision_boundaries_and_invalid_values(self):
            calculate = env['_reconciliation_amounts']
            self.assertEqual(calculate(Decimal('1.01'), [1.0]), (Decimal('.01'), True))
            self.assertEqual(calculate(Decimal('1.02'), [1.0]), (Decimal('.02'), False))
            self.assertEqual(calculate(Decimal('0'), [0]), (0, True))
            self.assertEqual(calculate(Decimal('0.04'), [.02]), (Decimal('.02'), False))
            self.assertEqual(calculate(Decimal('9999999999999999.99'),
                                       [Decimal('9999999999999999.97')]), (Decimal('.02'), False))
            for invalid in (None, float('nan'), float('inf'), Decimal('NaN'), Decimal('1e100'), True):
                with self.subTest(invalid=invalid):
                    self.assertEqual(calculate(invalid, [0]), (None, False))
                    self.assertEqual(calculate(0, [invalid]), (None, False))

        def test_split_outbound_lines_and_print_status(self):
            order = session.query(SalesOrder).filter_by(order_no='SYN-0').one()
            order.shipped_amount = Decimal('.04')
            session.flush()
            try:
                result = self.report(warehouse_id=a.id)
                self.assertFalse(result['rows'][0]['ok'])
                self.assertEqual(result['rows'][0]['amount_diff'], Decimal('.02'))
                self.assertEqual(self.export(warehouse_id=a.id)[1][-1], '不一致')
            finally:
                session.rollback()

        def test_amount_status_template_renders_unknown_and_regular_values(self):
            text = (root / 'app/templates/sales_reconciliation_report.html').read_text(encoding='utf-8')
            start = text.index('<td class="text-end {% if row.amount_diff')
            end = text.index('</td>', text.index('</td>', start) + 5) + 5
            fragment = Template(text[start:end])
            unknown = fragment.render(row={'amount_diff': None, 'quantity_diff': None, 'ok': False})
            self.assertIn('待核对', unknown)
            self.assertIn('待人工核对', unknown)
            valid = fragment.render(row={'amount_diff': Decimal('0.01'), 'quantity_diff': 0, 'ok': True})
            self.assertIn('0.01', valid)
            self.assertIn('通过', valid)
            invalid = fragment.render(row={'amount_diff': Decimal('0.02'), 'quantity_diff': 0, 'ok': False})
            self.assertIn('不一致', invalid)
            large = fragment.render(row={'amount_diff': Decimal('9999999999999999.97'), 'quantity_diff': 0, 'ok': False})
            self.assertIn('9999999999999999.97', large)

        def test_excel_preserves_precision_as_text_only_when_needed(self):
            from openpyxl import Workbook as RealWorkbook, load_workbook
            excel_amount = env['_reconciliation_excel_amount']
            self.assertEqual(excel_amount(Decimal('1.01')), 1.01)
            self.assertIsInstance(excel_amount(Decimal('1.01')), float)
            self.assertEqual(excel_amount(Decimal('9999999999999999.99')), '9999999999999999.99')
            order = session.query(SalesOrder).filter_by(order_no='SYN-0').one()
            order.shipped_amount = Decimal('9999999999999999.99')
            session.flush()
            try:
                exported = self.export(warehouse_id=a.id)[1]
                self.assertEqual(exported[-2], '9999999999999999.99')
                workbook = RealWorkbook()
                workbook.active.append(exported)
                output = BytesIO()
                workbook.save(output)
                output.seek(0)
                cell = load_workbook(output).active.cell(row=1, column=5)
                self.assertEqual(cell.value, '9999999999999999.99')
                self.assertEqual(cell.data_type, 's')
                printed = self.print_data(warehouse_id=a.id)['rows'][0]
                self.assertEqual(printed['amount_diff'], '9999999999999999.97')
            finally:
                session.rollback()

        def test_missing_quantities_are_unknown_in_page_and_exports(self):
            order = session.query(SalesOrder).filter_by(order_no='SYN-0').one()
            for item in order.items:
                item.shipped_quantity = None
            order.outbound_orders[0].items[0].quantity = None
            session.flush()
            try:
                row = self.report(warehouse_id=a.id)['rows'][0]
                self.assertFalse(row['ok'])
                self.assertIsNone(row['quantity_diff'])
                self.assertEqual(self.export(warehouse_id=a.id)[1][-1], '待人工核对')
                self.assertEqual(self.print_data(warehouse_id=a.id)['rows'][0]['result'], '待人工核对')
            finally:
                session.rollback()

        def test_nonfinite_quantity_is_unknown(self):
            quantities = env['_reconciliation_quantities']
            for invalid in (None, float('nan'), float('inf'), float('-inf'), True, 1e100):
                with self.subTest(invalid=invalid):
                    values = quantities([invalid], [0], 1e-6)
                    self.assertIsNone(values[2])
                    self.assertFalse(values[3])
            self.assertTrue(quantities([1], [1 + 0.5e-6], 1e-6)[3])
            self.assertFalse(quantities([1], [1 + 2e-6], 1e-6)[3])

        def test_cross_warehouse_and_unknown_outbound_require_manual_review(self):
            order = session.query(SalesOrder).filter_by(order_no='SYN-0').one()
            outbound = order.outbound_orders[0]
            for warehouse in (b.name, None, '', 'unknown synthetic warehouse'):
                with self.subTest(warehouse=warehouse):
                    outbound.warehouse = warehouse
                    session.flush()
                    try:
                        row = self.report(warehouse_id=a.id)['rows'][0]
                        self.assertFalse(row['ok'])
                        self.assertIsNone(row['quantity_diff'])
                        self.assertIsNone(row['amount_diff'])
                        self.assertIsNotNone(row['warehouse_reason'])
                        self.assertIn('待人工核对', self.export(warehouse_id=a.id)[1][-1])
                        self.assertIn('待人工核对', self.print_data(warehouse_id=a.id)['rows'][0]['result'])
                        self.assertEqual(outbound.warehouse, warehouse)
                    finally:
                        session.rollback()

        def test_legacy_code_and_explicit_same_warehouse_are_accepted(self):
            order = session.query(SalesOrder).filter_by(order_no='SYN-0').one()
            order.warehouse_id = None
            order.warehouse = a.code
            order.outbound_orders[0].warehouse = a.code
            session.flush()
            try:
                row = self.report(warehouse_id=a.id)['rows'][0]
                self.assertTrue(row['ok'])
                self.assertIsNone(row['warehouse_reason'])
                self.assertEqual(self.export(warehouse_id=a.id)[1][-1], '通过')
            finally:
                session.rollback()

        def test_legacy_warehouse_space_padding_remains_visible(self):
            order = session.query(SalesOrder).filter_by(order_no='SYN-0').one()
            order.warehouse_id = None
            order.warehouse = '  ' + a.code + '  '
            order.outbound_orders[0].warehouse = ' ' + a.name + ' '
            session.flush()
            try:
                row = self.report(warehouse_id=a.id)['rows'][0]
                self.assertTrue(row['ok'])
                self.assertEqual(row['order'].order_no, 'SYN-0')
                self.assertEqual(self.export(warehouse_id=a.id)[1][-1], '通过')
                self.assertEqual(self.print_data(warehouse_id=a.id)['rows'][0]['result'], '通过')
            finally:
                session.rollback()

        def test_unknown_warehouse_notice_does_not_disclose_or_attribute_orders(self):
            for index, (warehouse_id, warehouse) in enumerate(((None, None), (None, 'unmatched'), (9999, None))):
                session.add(SalesOrder(order_no=f'PRIVATE-UNKNOWN-{index}', date=date.today(),
                                       warehouse_id=warehouse_id, warehouse=warehouse,
                                       status='confirmed', shipment_status='pending', total_amount=0,
                                       untaxed_amount=0, tax_amount=0, shipped_amount=0))
            session.flush()
            try:
                note = env['_RECONCILIATION_UNKNOWN_WAREHOUSE_NOTE']
                page = self.report(warehouse_id=a.id)
                self.assertEqual(page['unknown_warehouse_note'], note)
                self.assertEqual([row['order'].order_no for row in page['rows']], ['SYN-0'])
                printed = self.print_data(warehouse_id=a.id)
                self.assertIn(note, printed['print_scope'])
                exported = self.export(warehouse_id=a.id)
                self.assertEqual([row[0] for row in exported[1:]], ['SYN-0'])
                self.assertEqual(env['synthetic_workbook'].other_sheets['归属说明'].rows, [[note]])
                self.assertNotIn('PRIVATE-UNKNOWN', str(printed))
                self.assertNotIn('PRIVATE-UNKNOWN', str(exported))
                template_text = (root / 'app/templates/sales_reconciliation_report.html').read_text(encoding='utf-8')
                start = template_text.index('{% if warehouse_id and unknown_warehouse_note %}')
                end = template_text.index('{% endif %}', start) + len('{% endif %}')
                rendered = Template(template_text[start:end]).render(warehouse_id=a.id, unknown_warehouse_note=note)
                self.assertIn(note, rendered)
                from openpyxl import Workbook as RealWorkbook, load_workbook
                original_workbook, original_send_file = env['Workbook'], env['send_file']
                try:
                    env['Workbook'] = RealWorkbook
                    env['send_file'] = lambda output, **_kwargs: output.getvalue()
                    payload = self.export(warehouse_id=a.id)
                    workbook = load_workbook(BytesIO(payload))
                    self.assertEqual(workbook.sheetnames, ['销售对账', '归属说明'])
                    self.assertEqual(workbook['归属说明']['A1'].value, note)
                    self.assertEqual(workbook['销售对账']['A2'].value, 'SYN-0')
                    self.assertNotIn(b'PRIVATE-UNKNOWN', payload)
                finally:
                    env['Workbook'], env['send_file'] = original_workbook, original_send_file
            finally:
                session.rollback()

        def test_ambiguous_name_code_collision_is_not_guessed(self):
            order = session.query(SalesOrder).filter_by(order_no='SYN-0').one()
            collision = Warehouse(name='unrelated synthetic', code=a.name)
            session.add(collision)
            session.flush()
            try:
                row = self.report(warehouse_id=a.id)['rows'][0]
                self.assertFalse(row['ok'])
                self.assertIsNotNone(row['warehouse_reason'])
                self.assertIn('待人工核对', self.export(warehouse_id=a.id)[1][-1])
            finally:
                session.rollback()

        def test_conflicting_order_id_and_text_requires_manual_review(self):
            order = session.query(SalesOrder).filter_by(order_no='SYN-0').one()
            order.warehouse = b.name
            session.flush()
            try:
                row = self.report(warehouse_id=a.id)['rows'][0]
                self.assertFalse(row['ok'])
                self.assertIsNotNone(row['warehouse_reason'])
            finally:
                session.rollback()

        def test_explicit_id_allows_empty_legacy_order_text(self):
            order = session.query(SalesOrder).filter_by(order_no='SYN-0').one()
            order.warehouse = ''
            session.flush()
            try:
                row = self.report(warehouse_id=a.id)['rows'][0]
                self.assertTrue(row['ok'])
                self.assertIsNone(row['warehouse_reason'])
            finally:
                session.rollback()

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ReconciliationMemoryTests)
    if suite.countTestCases() != 19:
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
