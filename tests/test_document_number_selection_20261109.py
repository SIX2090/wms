"""Select the largest synthetic historical sequence; no WMS or file DB is used."""
import ast
import builtins
import datetime
import os
from pathlib import Path
import platform
import socket
import sqlite3
import subprocess
import sys
import sysconfig
import threading
import types
import unittest


def main():
    def refuse(*_args, **_kwargs):
        raise AssertionError('WMS import, file databases, network and subprocesses forbidden')

    class DeniedPopen:
        def __init__(self, *_args, **_kwargs):
            refuse()
    subprocess.Popen = DeniedPopen
    socket.socket.connect = socket.socket.connect_ex = refuse
    socket.getaddrinfo = socket.create_connection = refuse
    real_import = builtins.__import__
    def safe_import(name, *args, **kwargs):
        level = args[3] if len(args) > 3 else kwargs.get('level', 0)
        if level == 0 and (name == 'app' or name.startswith('app.')):
            refuse()
        return real_import(name, *args, **kwargs)
    builtins.__import__ = safe_import
    original_connect = sqlite3.connect
    sqlite3.connect = sqlite3.dbapi2.connect = refuse
    platform.machine = lambda: 'synthetic'
    sys.path.append(sysconfig.get_paths()['purelib'])
    from sqlalchemy import Column, Integer, String, create_engine, func, cast
    from sqlalchemy.orm import declarative_base, scoped_session, sessionmaker

    Base = declarative_base()
    specs = {
        'InOrder': 'order_no', 'OutOrder': 'order_no', 'SalesOrder': 'order_no',
        'InventoryCheck': 'check_no', 'InventoryCheckScan': 'check_no',
        'SubcontractOrder': 'order_no', 'SubcontractIssue': 'issue_no',
        'SubcontractReceive': 'receive_no', 'PurchaseRequest': 'request_no',
        'PurchaseOrder': 'order_no', 'AfterSaleOutOrder': 'order_no',
        'BOM': 'bom_no', 'ProductionRequisition': 'req_no',
        'TransferOrder': 'transfer_no', 'AdjustmentOrder': 'adjustment_no',
        'OpeningStockDoc': 'doc_no',
    }
    models = {
        name: type(name, (Base,), {'__tablename__': 'synth_' + name.lower(),
                    'id': Column(Integer, primary_key=True), field: Column(String)})
        for name, field in specs.items()
    }
    engine = create_engine('sqlite://', creator=lambda: original_connect(':memory:'))
    session = scoped_session(sessionmaker(bind=engine))
    Base.query = session.query_property()
    Base.metadata.create_all(engine)

    root = Path(__file__).resolve().parents[1]
    tree = ast.parse((root / 'app/app.py').read_text(encoding='utf-8-sig'))
    names = ('generate_order_no', '_generate_order_no_locked', 'generate_sales_order_no',
             '_next_opening_stock_doc_no')
    nodes = []
    for name in names:
        found = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name]
        if len(found) != 1:
            raise AssertionError('missing or ambiguous numbering function: ' + name)
        nodes.append(found[0])
    # Production helper functions, if added, are extracted directly rather than mocked.
    nodes += [n for n in tree.body if isinstance(n, ast.FunctionDef)
              and n.name == '_numbering_existing_max']
    class Clock(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 11, 9, tzinfo=tz)
    env = {**models, 'datetime': Clock, 'db': types.SimpleNamespace(cast=cast, Integer=Integer, func=func),
           '_order_no_generation_lock': threading.Lock()}
    import re
    env['re'] = re
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])),
                 '<real-number-functions-synthetic-db>', 'exec'), env)

    cases = {
        'IN': ('InOrder', 'order_no'), 'PI': ('InOrder', 'order_no'),
        'OI': ('InOrder', 'order_no'), 'OU': ('OutOrder', 'order_no'),
        'SO': ('OutOrder', 'order_no'), 'OO': ('OutOrder', 'order_no'),
        'CK': ('InventoryCheck', 'check_no'), 'CS': ('InventoryCheckScan', 'check_no'),
        'SC': ('SubcontractOrder', 'order_no'), 'SUB': ('SubcontractOrder', 'order_no'),
        'SF': ('SubcontractIssue', 'issue_no'), 'SR': ('SubcontractReceive', 'receive_no'),
        'PR': ('PurchaseRequest', 'request_no'), 'PO': ('PurchaseOrder', 'order_no'),
        'ASO': ('AfterSaleOutOrder', 'order_no'), 'BOM': ('BOM', 'bom_no'),
        'REQ': ('ProductionRequisition', 'req_no'), 'TF': ('TransferOrder', 'transfer_no'),
        'ADJ': ('AdjustmentOrder', 'adjustment_no'), 'QS': ('OpeningStockDoc', 'doc_no'),
    }
    class Selection(unittest.TestCase):
        def setUp(self):
            for model in models.values():
                session.query(model).delete()
            session.commit()

        def add(self, model, field, *numbers):
            session.add_all([models[model](**{field: value}) for value in numbers])
            session.commit()

        def test_every_number_family_uses_numeric_max_not_latest_row(self):
            for prefix, (name, field) in cases.items():
                with self.subTest(prefix=prefix):
                    session.query(models[name]).delete()
                    session.commit()
                    base = prefix + '2611'
                    self.add(name, field, base + '0077', base + '0004')
                    self.assertEqual(env['generate_order_no'](prefix), base + '0078')

        def test_sales_sequence_over_four_digits_and_nonmonotonic_ids(self):
            self.add('SalesOrder', 'order_no', 'SO261110000', 'SO26119999')
            self.assertEqual(env['generate_sales_order_no'](), 'SO261110001')

        def test_malformed_suffix_cannot_make_valid_number_reissued(self):
            self.add('OutOrder', 'order_no', 'OU26110001', 'OU26110009x')
            self.assertEqual(env['generate_order_no']('OU'), 'OU26110002')

        def test_numeric_suffix_above_sqlite_integer_range(self):
            self.add('OutOrder', 'order_no', 'OU26119223372036854775809',
                     'OU26119223372036854775808')
            self.assertEqual(env['generate_order_no']('OU'), 'OU26119223372036854775810')

        def test_excessively_long_numeric_suffix_does_not_guess_an_existing_number(self):
            limit = sys.get_int_max_str_digits()
            if not limit:
                self.skipTest('interpreter has no integer digit limit')
            self.add('OutOrder', 'order_no', 'OU26110001', 'OU2611' + '9' * (limit + 1))
            with self.assertRaises(ValueError):
                env['generate_order_no']('OU')

        def test_shared_sr_and_pr_prefixes_use_the_largest_across_tables(self):
            self.add('SubcontractReceive', 'receive_no', 'SR26110001')
            self.add('InOrder', 'order_no', 'SR26110077')
            self.assertEqual(env['generate_order_no']('SR'), 'SR26110078')
            self.add('PurchaseRequest', 'request_no', 'PR26110009')
            self.add('OutOrder', 'order_no', 'PR26110050')
            self.assertEqual(env['generate_order_no']('PR'), 'PR26110051')

        def test_existing_other_month_is_not_used(self):
            self.add('OutOrder', 'order_no', 'OU261010000', 'OU26120099')
            self.assertEqual(env['generate_order_no']('OU'), 'OU26110001')

        def test_opening_stock_migration_sequence_over_four_digits(self):
            conn = original_connect(':memory:')
            try:
                self.assertEqual(conn.execute('PRAGMA database_list').fetchone()[2], '')
                conn.execute('CREATE TABLE opening_stock_doc (doc_no TEXT NOT NULL UNIQUE)')
                conn.executemany('INSERT INTO opening_stock_doc VALUES (?)',
                                 [('QS26119999',), ('QS261110000',)])
                result = env['_next_opening_stock_doc_no'](conn.cursor(), datetime.date(2026, 11, 1))
                self.assertEqual(result, 'QS261110001')
            finally:
                conn.close()

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Selection)
    if suite.countTestCases() != 8:
        raise RuntimeError('explicit synthetic test list incomplete')
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    session.remove()
    engine.dispose()
    raise SystemExit(not result.wasSuccessful())


def test_document_number_selection_in_isolated_process():
    env = {key: os.environ[key] for key in ('SYSTEMROOT', 'WINDIR') if key in os.environ}
    result = subprocess.run([sys.executable, '-I', '-S', '-B', '-X', 'utf8', __file__],
                            env=env, capture_output=True, text=True, encoding='utf-8', timeout=30)
    assert result.returncode == 0, result.stderr


if __name__ == '__main__':
    main()
