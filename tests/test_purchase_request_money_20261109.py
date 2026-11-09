"""Purchase request save/import math, exercised without importing the WMS app."""
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
    raise AssertionError('network, database and subprocess are forbidden')


class PurchaseRequestAmountTests(unittest.TestCase):
    def setUp(self):
        for guard in (patch.object(socket.socket, 'connect', deny), patch.object(socket.socket, 'connect_ex', deny),
                      patch.object(socket, 'getaddrinfo', deny), patch.object(sqlite3, 'connect', deny),
                      patch.object(subprocess, 'Popen', deny)):
            guard.start()
            self.addCleanup(guard.stop)
        utils = ast.parse((ROOT / 'app/utils.py').read_text(encoding='utf-8-sig'))

        functions = [n for n in utils.body if isinstance(n, ast.FunctionDef)
                     and n.name in ('round_to_2_decimals', 'round_money_product')]
        self.assertEqual(len(functions), 2)
        self.env = {'Decimal': Decimal, 'ROUND_HALF_UP': ROUND_HALF_UP, 'localcontext': localcontext, 'math': math}
        exec(compile(ast.fix_missing_locations(ast.Module(body=functions, type_ignores=[])), '<utils>', 'exec'), self.env)
        self.tree = ast.parse((ROOT / 'app/routes/purchase_request.py').read_text(encoding='utf-8-sig'))

    def expression(self, field):
        candidates = [node.value for node in ast.walk(self.tree) if isinstance(node, ast.Assign)
                      and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                      and node.targets[0].id == field]
        self.assertEqual(len(candidates), 1)
        return compile(ast.fix_missing_locations(ast.Expression(candidates[0])), '<request-amount>', 'eval')

    def test_save_matches_import_line_rounding(self):
        self.env.update(quantity=1.15, estimated_price=3.5)
        self.assertEqual(eval(self.expression('estimated_amount'), self.env), 4.03)

    def test_two_half_cent_lines_are_each_rounded(self):
        self.env.update(quantity=0.01, estimated_price=0.5)
        line = eval(self.expression('estimated_amount'), self.env)
        self.assertEqual((line, round(line + line, 2)), (0.01, 0.02))


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(PurchaseRequestAmountTests)
    if suite.countTestCases() != 2:
        raise SystemExit('synthetic test list is incomplete or empty')
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
