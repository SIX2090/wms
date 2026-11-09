"""Subcontract subtotal consumers, synthetic objects only."""
import ast
from decimal import Decimal, ROUND_HALF_UP, localcontext
import math
from pathlib import Path
import socket
import sqlite3
import subprocess
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def deny(*_args, **_kwargs):
    raise AssertionError('database, network and subprocess forbidden')


class SubcontractAmountTests(unittest.TestCase):
    def test_each_subtotal_sums_rounded_lines(self):
        with patch.object(socket.socket, 'connect', deny), patch.object(socket.socket, 'connect_ex', deny), \
             patch.object(socket, 'getaddrinfo', deny), patch.object(sqlite3, 'connect', deny), \
             patch.object(subprocess, 'Popen', deny):
            utils = ast.parse((ROOT / 'app/utils.py').read_text(encoding='utf-8-sig'))

            functions = [n for n in utils.body if isinstance(n, ast.FunctionDef)
                         and n.name in ('round_money_product', 'round_to_2_decimals')]
            self.assertEqual(len(functions), 2)
            env = {'Decimal': Decimal, 'ROUND_HALF_UP': ROUND_HALF_UP, 'localcontext': localcontext, 'math': math}
            exec(compile(ast.fix_missing_locations(ast.Module(body=functions, type_ignores=[])), '<utils>', 'exec'), env)
            tree = ast.parse((ROOT / 'app/routes/subcontract.py').read_text(encoding='utf-8-sig'))
            expressions = [n.value for n in ast.walk(tree) if isinstance(n, ast.Assign) and len(n.targets) == 1
                           and isinstance(n.targets[0], ast.Attribute) and n.targets[0].attr == 'total_amount'
                           and isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Name)
                           and n.value.func.id == 'round_to_2_decimals']
            self.assertEqual(len(expressions), 3)
            material = types.SimpleNamespace(price=0.5)
            items = [types.SimpleNamespace(id=i, quantity=0.01, material=material) for i in (1, 2)]
            env.update(order=types.SimpleNamespace(items=items), item_id=3)
            for expression in expressions:
                with self.subTest(line=expression.lineno):
                    result = eval(compile(ast.fix_missing_locations(ast.Expression(expression)), '<subtotal>', 'eval'), env)
                    self.assertEqual(result, 0.02)


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(SubcontractAmountTests)
    if suite.countTestCases() != 1:
        raise SystemExit('synthetic test list is incomplete or empty')
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
