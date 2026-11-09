"""Offline money-product regression; no WMS import, DB, network or children."""
import ast
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
import math
from pathlib import Path
import socket
import sqlite3
import subprocess
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def forbid(*_args, **_kwargs):
    raise AssertionError('database, network and child processes are forbidden')


class MoneyProductTests(unittest.TestCase):
    def setUp(self):
        for target in (patch.object(socket.socket, 'connect', forbid),
                       patch.object(socket.socket, 'connect_ex', forbid),
                       patch.object(socket, 'getaddrinfo', forbid),
                       patch.object(sqlite3, 'connect', forbid),
                       patch.object(subprocess, 'Popen', forbid)):
            target.start()
            self.addCleanup(target.stop)
        tree = ast.parse((ROOT / 'app/utils.py').read_text(encoding='utf-8-sig'))
        nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef)
                 and n.name in ('round_to_2_decimals', 'round_money_product')]
        self.assertEqual({n.name for n in nodes}, {'round_to_2_decimals', 'round_money_product'})
        env = {'Decimal': Decimal, 'InvalidOperation': InvalidOperation, 'ROUND_HALF_UP': ROUND_HALF_UP,
               'localcontext': localcontext, 'math': math}
        exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])),
                     '<synthetic-money-product>', 'exec'), env)
        self.product = env['round_money_product']

    def test_round_money_product(self):
        self.assertEqual(self.product(1.15, 3.50), 4.03)
        self.assertEqual(self.product(0.01, 0.50), 0.01)
        self.assertEqual(self.product(-0.01, 0.50), -0.01)

    def test_ordinary_zero_and_negative(self):
        self.assertEqual(self.product(2, 3.5), 7.0)
        self.assertEqual(self.product(0, 100), 0.0)
        self.assertEqual(self.product(2, -1.25), -2.5)

    def test_strings_exponents_and_four_decimal_quantities(self):
        self.assertEqual(self.product('1.15', '3.50'), 4.03)
        self.assertEqual(self.product('1e-2', '5e-1'), .01)
        self.assertEqual(self.product('0.0001', '50'), .01)

    def test_rejects_nonfinite_product(self):
        for value in (float('nan'), float('inf'), -float('inf')):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self.product(value, 1)

    def test_no_silent_coercion_for_missing_operands(self):
        for value in (None, 'not-a-number'):
            with self.subTest(value=value):
                with self.assertRaises((TypeError, ValueError, InvalidOperation)):
                    self.product(value, 1)

    def test_input_is_not_rounded_before_multiplication(self):
        self.assertEqual(self.product('1.005', '1'), 1.01)
        self.assertEqual(self.product('2.999', '0.5'), 1.50)


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(MoneyProductTests)
    if suite.countTestCases() != 6:
        raise SystemExit('synthetic test list must be explicit and nonempty')
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
