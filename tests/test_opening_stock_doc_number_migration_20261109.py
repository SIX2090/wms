"""Exercise the real migration number function against a new memory-only database."""
import ast
import datetime
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import unittest


def main():
    original_connect = sqlite3.connect
    def deny(*_args, **_kwargs):
        raise AssertionError('file databases, network and child processes are forbidden')
    sqlite3.connect = sqlite3.dbapi2.connect = deny
    socket.socket.connect = socket.socket.connect_ex = deny
    socket.create_connection = socket.getaddrinfo = deny
    subprocess.Popen = deny
    source = (Path(__file__).resolve().parents[1] / 'app/app.py').read_text(encoding='utf-8-sig')
    functions = [node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef)
                 and node.name in ('_next_opening_stock_doc_no', '_backfill_opening_stock_docs')]
    if len(functions) != 2 or {node.name for node in functions} != {
            '_next_opening_stock_doc_no', '_backfill_opening_stock_docs'}:
        raise AssertionError('migration functions missing or ambiguous')
    env = {'datetime': datetime.datetime}
    exec(compile(ast.fix_missing_locations(ast.Module(body=functions, type_ignores=[])),
                 '<real-migration-function>', 'exec'), env)

    class MigrationNumber(unittest.TestCase):
        def setUp(self):
            self.conn = original_connect(':memory:')
            self.assertEqual(self.conn.execute('PRAGMA database_list').fetchone()[2], '')
            self.conn.execute('CREATE TABLE opening_stock_doc (id INTEGER PRIMARY KEY, '
                              'doc_no TEXT NOT NULL UNIQUE, date TEXT, warehouse_id INTEGER, '
                              'status TEXT, remark TEXT, operator_id INTEGER, '
                              'created_at TEXT, updated_at TEXT)')
            self.conn.execute('CREATE TABLE opening_stock (id INTEGER PRIMARY KEY, date TEXT, '
                              'warehouse_id INTEGER, doc_id INTEGER)')

        def tearDown(self):
            self.conn.close()

        def next_number(self):
            return env['_next_opening_stock_doc_no'](self.conn.cursor(), datetime.date(2026, 11, 1))

        def insert(self, *numbers):
            self.conn.executemany('INSERT INTO opening_stock_doc (doc_no) VALUES (?)', [(n,) for n in numbers])

        def test_four_to_five_digit_transition_and_nonmonotonic_rows(self):
            self.insert('QS26119999', 'QS261110000', 'QS26110002')
            number = self.next_number()
            self.assertEqual(number, 'QS261110001')
            self.insert(number)
            self.assertEqual(self.next_number(), 'QS261110002')

        def test_malformed_suffix_and_other_month(self):
            self.insert('QS26110009x', 'QS26110001', 'QS261210000')
            self.assertEqual(self.next_number(), 'QS26110002')

        def test_large_numeric_suffix_does_not_silently_reissue(self):
            self.insert('QS26119223372036854775809', 'QS26119223372036854775808')
            self.assertEqual(self.next_number(), 'QS26119223372036854775810')

        def test_unparseable_numeric_suffix_aborts(self):
            limit = sys.get_int_max_str_digits()
            if not limit:
                self.skipTest('interpreter has no digit limit')
            self.insert('QS26110001', 'QS2611' + '9' * (limit + 1))
            with self.assertRaises(ValueError):
                self.next_number()

        def test_rollback_restores_migration_transaction(self):
            self.insert('QS26119999')
            self.conn.commit()
            self.insert(self.next_number())
            self.conn.rollback()
            self.assertEqual(self.next_number(), 'QS261110000')
            self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM opening_stock_doc').fetchone()[0], 1)

        def test_actual_backfill_groups_and_assigns_five_digit_numbers(self):
            self.insert('QS26119999', 'QS261110000')
            self.conn.executemany('INSERT INTO opening_stock (date, warehouse_id) VALUES (?, ?)',
                                  [('2026-11-01', 1), ('2026-11-01', 1), ('2026-11-01', 2)])
            self.assertEqual(env['_backfill_opening_stock_docs'](self.conn.cursor()), 2)
            self.assertEqual(env['_backfill_opening_stock_docs'](self.conn.cursor()), 0)
            rows = self.conn.execute('SELECT s.warehouse_id, d.doc_no FROM opening_stock s '
                                     'JOIN opening_stock_doc d ON d.id=s.doc_id ORDER BY s.id').fetchall()
            self.assertEqual(rows, [(1, 'QS261110001'), (1, 'QS261110001'), (2, 'QS261110002')])

        def test_actual_backfill_rolls_back_with_caller_transaction(self):
            self.insert('QS26119999', 'QS261110000')
            self.conn.execute('INSERT INTO opening_stock (date, warehouse_id) VALUES (?, ?)',
                              ('2026-11-01', 1))
            self.conn.commit()
            self.assertEqual(env['_backfill_opening_stock_docs'](self.conn.cursor()), 1)
            self.conn.rollback()
            self.assertEqual(self.conn.execute('SELECT doc_id FROM opening_stock').fetchone(), (None,))
            self.assertEqual(self.conn.execute('SELECT count(*) FROM opening_stock_doc').fetchone(), (2,))

        def test_startup_fallback_sqlite_row_factory(self):
            self.conn.row_factory = sqlite3.Row
            self.insert('QS26119999', 'QS261110000')
            self.conn.execute('INSERT INTO opening_stock (date, warehouse_id) VALUES (?, ?)',
                              ('2026-11-01', 1))
            self.assertEqual(env['_backfill_opening_stock_docs'](self.conn.cursor()), 1)
            result = self.conn.execute('SELECT d.doc_no FROM opening_stock s '
                                       'JOIN opening_stock_doc d ON d.id=s.doc_id').fetchone()
            self.assertEqual(result['doc_no'], 'QS261110001')

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(MigrationNumber)
    if suite.countTestCases() != 8:
        raise RuntimeError('synthetic migration test list incomplete')
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not result.wasSuccessful())


def test_opening_stock_migration_number_isolated():
    env = {key: os.environ[key] for key in ('SYSTEMROOT', 'WINDIR') if key in os.environ}
    result = subprocess.run([sys.executable, '-I', '-S', '-B', '-X', 'utf8', __file__],
                            env=env, capture_output=True, text=True, encoding='utf-8', timeout=30)
    assert result.returncode == 0, result.stderr


if __name__ == '__main__':
    main()
