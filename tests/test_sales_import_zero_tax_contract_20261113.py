"""Actual import tax block and helpers; no app import, DB, network or children."""
import ast
import builtins
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
import math
from pathlib import Path
import socket
import sqlite3
import subprocess
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def deny(*args, **kwargs):
    raise AssertionError('app import, database, network and child processes forbidden')


def extract(path, name):
    tree = ast.parse((ROOT / path).read_text(encoding='utf-8-sig'))
    matches = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == name]
    if len(matches) != 1:
        raise AssertionError('source function must be unique: ' + name)
    return matches[0]


class SalesImportZeroTaxContract(unittest.TestCase):
    def setUp(self):
        original_import = builtins.__import__

        def guarded_import(name, *args, **kwargs):
            if name == 'app' or name.startswith('app.'):
                deny()
            return original_import(name, *args, **kwargs)

        for guard in (patch.object(builtins, '__import__', side_effect=guarded_import),
                      patch.object(sqlite3, 'connect', deny),
                      patch.object(sqlite3.dbapi2, 'connect', deny),
                      patch.object(socket.socket, 'connect', deny),
                      patch.object(socket.socket, 'connect_ex', deny),
                      patch.object(socket, 'getaddrinfo', deny),
                      patch.object(subprocess, 'Popen', deny)):
            guard.start()
            self.addCleanup(guard.stop)
        self.env = dict(Decimal=Decimal, InvalidOperation=InvalidOperation, ROUND_HALF_UP=ROUND_HALF_UP,
                        localcontext=localcontext, math=math)
        helpers = [extract('app/utils.py', name) for name in
                   ('round_to_2_decimals', 'round_money_product', 'parse_float_value')]
        helpers.append(extract('app/app.py', '_get_excel_number'))
        route = extract('app/routes/sales.py', 'import_sales_orders')
        blocks = [node.body for node in ast.walk(route) if isinstance(node, ast.For)
                  and any(isinstance(stmt, ast.Assign) and any(isinstance(target, ast.Name)
                      and target.id == 'tax_rate' for target in stmt.targets) for stmt in node.body)]
        self.assertEqual(len(blocks), 1, 'import row loop containing tax computation must be unique')
        body = blocks[0]
        start = next(i for i, stmt in enumerate(body) if isinstance(stmt, ast.Assign)
                     and any(isinstance(target, ast.Name) and target.id == 'tax_rate' for target in stmt.targets))
        end = next(i for i, stmt in enumerate(body) if isinstance(stmt, ast.Assign)
                   and any(isinstance(target, ast.Name) and target.id == 'untaxed_price' for target in stmt.targets))
        calculate = ast.parse('def calculate(row, col_map, quantity, price): pass').body[0]
        calculate.body = body[start:end + 1] + [ast.Return(value=ast.Tuple(elts=[
            ast.Name(id=name, ctx=ast.Load()) for name in
            ('tax_rate', 'included_amount', 'untaxed_amount', 'tax_amount', 'untaxed_price')], ctx=ast.Load()))]
        exec(compile(ast.fix_missing_locations(ast.Module(body=helpers + [calculate], type_ignores=[])),
                     '<actual-sales-import-tax-and-helpers>', 'exec'), self.env)

    def values(self, value, col_map=None, quantity=1.15, price=3.5):
        return self.env['calculate']([value], {'tax_rate': 0} if col_map is None else col_map, quantity, price)

    def test_explicit_zero_tax_is_kept_in_actual_import_calculation(self):
        for value in (0, -0.0, '0', '0.00'):
            with self.subTest(value=value):
                self.assertEqual(self.values(value), (0, 4.03, 4.03, 0, 3.5))

    def test_ordinary_positive_tax_keeps_existing_formula(self):
        for value in (.13, '0.13'):
            with self.subTest(value=value):
                self.assertEqual(self.values(value), (.13, 4.03, 3.57, .46, 3.0973))
        self.assertEqual(self.values(.06), (.06, 4.03, 3.8, .23, 3.3019))

    def test_missing_column_cell_and_blank_keep_thirteen_percent_default(self):
        for value in (None, '', ' ', '\t'):
            with self.subTest(value=value):
                self.assertEqual(self.values(value)[0], .13)
        self.assertEqual(self.values(0, col_map={})[0], .13)
        self.assertEqual(self.env['calculate']([], {'tax_rate': 0}, 1.15, 3.5)[0], .13)

    def test_invalid_and_nonfinite_keep_existing_default(self):
        for value in ('bad', '13%', 'NaN', 'Infinity', float('nan'), float('inf')):
            with self.subTest(value=value):
                self.assertEqual(self.values(value)[0], .13)

    def test_negative_tax_keeps_existing_default_policy(self):
        for value in (-.01, -.13, '-0.13'):
            with self.subTest(value=value):
                self.assertEqual(self.values(value)[0], .13)

    def test_shared_numeric_helper_default_remains_unchanged(self):
        helper = self.env['_get_excel_number']
        for value in (None, '', 'bad', -.13):
            with self.subTest(value=value):
                self.assertEqual(helper([value], {'price': 0}, 'price'), 0)
        self.assertEqual(helper([0], {'price': 0}, 'price', default=.13), 0)

    def test_zero_and_regular_price_and_quantity_keep_existing_money_policy(self):
        self.assertEqual(self.values(0, price=0), (0, 0, 0, 0, 0))
        self.assertEqual(self.values(0, quantity=2, price=3.5), (0, 7, 7, 0, 3.5))
        self.assertEqual(self.values(.13, quantity=2, price=3.5), (.13, 7, 6.19, .81, 3.0973))


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(SalesImportZeroTaxContract)
    if suite.countTestCases() != 7:
        raise SystemExit('explicit source-model test list must contain seven tests')
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
