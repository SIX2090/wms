"""Compare real opening-stock amount expressions with normalized synthetic values."""
import ast
from decimal import Decimal, ROUND_HALF_UP, localcontext
import math
from pathlib import Path
import socket
import sqlite3
import subprocess
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def deny(*_args, **_kwargs):
    raise AssertionError('database, network and subprocess forbidden')


class OpeningAmountTests(unittest.TestCase):
    def test_all_save_paths_match_normalized_import_values(self):
        with patch.object(socket.socket, 'connect', deny), patch.object(socket.socket, 'connect_ex', deny), \
             patch.object(socket, 'getaddrinfo', deny), patch.object(sqlite3, 'connect', deny), \
             patch.object(subprocess, 'Popen', deny):
            utils = ast.parse((ROOT / 'app/utils.py').read_text(encoding='utf-8-sig'))
            functions = [n for n in utils.body if isinstance(n, ast.FunctionDef)
                         and n.name in ('round_money_product', 'round_to_2_decimals', 'normalize_stock_quantity')]
            self.assertEqual(len(functions), 3)
            env = {'Decimal': Decimal, 'ROUND_HALF_UP': ROUND_HALF_UP, 'localcontext': localcontext, 'math': math,
                   'STOCK_COMPARE_EPSILON': 1e-6}
            exec(compile(ast.fix_missing_locations(ast.Module(body=functions, type_ignores=[])), '<utils>', 'exec'), env)
            tree = ast.parse((ROOT / 'app/app.py').read_text(encoding='utf-8-sig'))
            for name in ('_opening_stock_payload_from_request', '_opening_stock_normalize_items'):
                fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
                amounts = [value for node in ast.walk(fn) if isinstance(node, ast.Dict)
                           for key, value in zip(node.keys, node.values)
                           if isinstance(key, ast.Constant) and key.value == 'amount']
                self.assertEqual(len(amounts), 1)
                for qty, price, expected in ((1.2345, 1.235, 1.53), (1.15, 3.5, 4.03), (0, 2.5, 0)):
                    with self.subTest(path=name, quantity=qty, price=price):
                        env.update(quantity=qty, price=price)
                        actual = eval(compile(ast.fix_missing_locations(ast.Expression(amounts[0])), '<opening>', 'eval'), env)
                        self.assertEqual(actual, expected)
                        self.assertEqual(actual, env['round_money_product'](
                            env['normalize_stock_quantity'](qty), env['round_to_2_decimals'](price)))
            import_tree = ast.parse((ROOT / 'app/routes/batch_import.py').read_text(encoding='utf-8-sig'))
            self.assertTrue(any(isinstance(n, ast.Assign) and isinstance(n.value, ast.Call)
                                and isinstance(n.value.func, ast.Name) and n.value.func.id == 'round_money_product'
                                and any(isinstance(t, ast.Name) and t.id == 'amount' for t in n.targets)
                                for n in ast.walk(import_tree)))


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(OpeningAmountTests)
    if suite.countTestCases() != 1:
        raise SystemExit('synthetic test list is incomplete or empty')
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
