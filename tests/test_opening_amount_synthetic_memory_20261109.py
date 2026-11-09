"""Actual opening mutation in a fresh in-memory SQLite DB with synthetic ORM only."""
import ast
import builtins
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP, localcontext
import math
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
        raise AssertionError('only the new synthetic memory DB is permitted')

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
        if name == 'app' or name.startswith('app.'):
            refuse()
        return original_import(name, *args, **kwargs)
    builtins.__import__ = safe_import
    sys.path.append(sysconfig.get_paths()['purelib'])

    from sqlalchemy import Column, Date, DateTime, Float, Integer, String, create_engine, update
    from sqlalchemy.orm import declarative_base, scoped_session, sessionmaker

    Base = declarative_base()
    engine = create_engine('sqlite:///:memory:')
    session = scoped_session(sessionmaker(bind=engine, expire_on_commit=False))

    class Material(Base):
        __tablename__ = 'synthetic_material'
        id = Column(Integer, primary_key=True)
        stock = Column(Float, nullable=False)

    class Opening(Base):
        __tablename__ = 'synthetic_opening'
        id = Column(Integer, primary_key=True)
        material_id = Column(Integer, nullable=False)
        warehouse_id = Column(Integer, nullable=False)
        quantity = Column(Float, nullable=False)
        price = Column(Float, nullable=False)
        amount = Column(Float)
        remark = Column(String)
        date = Column(Date)
        location = Column(String, default='')
        doc_id = Column(Integer)
        operator_id = Column(Integer)
        updated_at = Column(DateTime)

    class Ledger(Base):
        __tablename__ = 'synthetic_ledger'
        warehouse_id = Column(Integer, primary_key=True)
        stock = Column(Float, nullable=False)

    Base.metadata.create_all(engine)
    failures = {'fail': False}
    service = types.ModuleType('services.warehouse_stock_service')
    def apply(_material, delta, *, warehouse, **_kwargs):
        ledger = session.get(Ledger, warehouse.id)
        ledger.stock += delta
        if failures['fail']:
            return False, 'synthetic failure'
        return True, ''
    service.apply_opening_balance = apply
    parent = types.ModuleType('services')
    parent.__path__ = []
    sys.modules['services'] = parent
    sys.modules['services.warehouse_stock_service'] = service
    root = Path(__file__).resolve().parents[1]
    source = ast.parse((root / 'app/app.py').read_text(encoding='utf-8-sig'))
    funcs = [n for n in source.body if isinstance(n, ast.FunctionDef) and n.name in ('_apply_opening_stock_balance', '_opening_stock_saved_number', '_opening_stock_preserve_validated_line')]
    utils = ast.parse((root / 'app/utils.py').read_text(encoding='utf-8-sig'))
    funcs += [n for n in utils.body if isinstance(n, ast.FunctionDef)
              and n.name in ('round_to_2_decimals', 'normalize_stock_quantity', 'round_money_product')]
    if len(funcs) != 6:
        raise AssertionError('synthetic source list must contain exactly six functions')
    env = {'Decimal': Decimal, 'ROUND_HALF_UP': ROUND_HALF_UP, 'localcontext': localcontext, 'math': math,
           'STOCK_COMPARE_EPSILON': 1e-6, 'date': date, 'datetime': datetime,
           'current_user': types.SimpleNamespace(is_authenticated=False),
           'db': types.SimpleNamespace(session=session), 'Material': Material,
           'OpeningStock': Opening, 'sa_update': update, 'location_management_enabled': lambda: False}
    exec(compile(ast.fix_missing_locations(ast.Module(body=funcs, type_ignores=[])), '<opening>', 'exec'), env)

    class SyntheticMemoryTests(unittest.TestCase):
        def setUp(self):
            failures['fail'] = False
            session.query(Opening).delete()
            session.query(Ledger).delete()
            session.query(Material).delete()
            session.add_all([Material(id=1, stock=3), Ledger(warehouse_id=1, stock=1),
                             Ledger(warehouse_id=2, stock=2),
                             Opening(id=1, material_id=1, warehouse_id=1, quantity=1, price=5,
                                     amount=7.77, date=date(2025, 1, 1), location=''),
                             Opening(id=2, material_id=1, warehouse_id=2, quantity=2, price=5,
                                     amount=0, date=date(2025, 1, 1), location='')])
            session.commit()

        def edit(self, line_id, quantity, price, amount, warehouse_id):
            line = session.get(Opening, line_id)
            item = env['_opening_stock_preserve_validated_line'](line, {
                'line_id': line_id, 'quantity': quantity, 'price': price, 'amount': amount,
                '_raw_quantity': quantity, '_raw_price': price}, guarded=True)
            return env['_apply_opening_stock_balance'](
                line, session.get(Material, 1), item['quantity'], item['price'], item['amount'],
                '模拟备注', warehouse=types.SimpleNamespace(id=warehouse_id, name='模拟仓'))

        def test_repeat_save_preserves_explicit_amounts_and_separate_warehouses(self):
            for _ in range(2):
                self.edit(1, 1, 5, 5, 1)
                self.edit(2, 2, 5, 10, 2)
                session.commit()
            self.assertEqual((session.get(Opening, 1).amount, session.get(Opening, 2).amount), (7.77, 0))
            self.assertEqual((session.get(Material, 1).stock, session.get(Ledger, 1).stock,
                              session.get(Ledger, 2).stock), (3, 1, 2))

        def test_quantity_change_only_moves_its_warehouse(self):
            _, delta = self.edit(1, 3, 5, 15, 1)
            session.commit()
            self.assertEqual((delta, session.get(Opening, 1).amount), (2, 15))
            self.assertEqual((session.get(Material, 1).stock, session.get(Ledger, 1).stock,
                              session.get(Ledger, 2).stock), (5, 3, 2))

        def test_failure_rolls_back_line_and_both_stock_views(self):
            failures['fail'] = True
            with self.assertRaisesRegex(ValueError, 'synthetic failure'):
                self.edit(1, 3, 5, 15, 1)
            session.rollback()
            line = session.get(Opening, 1)
            self.assertEqual((line.quantity, line.amount), (1, 7.77))
            self.assertEqual((session.get(Material, 1).stock, session.get(Ledger, 1).stock,
                              session.get(Ledger, 2).stock), (3, 1, 2))

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(SyntheticMemoryTests)
    if suite.countTestCases() != 3:
        raise SystemExit('synthetic test list is incomplete or empty')
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    session.remove()
    engine.dispose()
    return not result.wasSuccessful()


if __name__ == '__main__':
    raise SystemExit(main())
