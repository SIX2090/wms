"""Execute actual financial projection expressions with synthetic values only.

No WMS import, database, network or subprocess. Full endpoints run in isolated CI.
"""
import ast
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
import math
from pathlib import Path
import socket
import sqlite3
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
REPORTS = [('app/routes/sales.py', 'export_sales_outflow_report'),
           ('app/services/sales_report_print.py', 'sales_outflow_context')]


def refuse(*args, **kwargs):
    raise AssertionError('financial projection test forbids databases, sockets and subprocesses')


class SalesZeroFinancialContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.expressions = []
        for path, name in REPORTS:
            tree = ast.parse((ROOT / path).read_text(encoding='utf-8-sig'))
            fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)
            for field in ('line_amount', 'tax_rate'):
                node = next(n for n in ast.walk(fn) if isinstance(n, ast.Assign)
                            and any(isinstance(t, ast.Name) and t.id == field for t in n.targets))
                cls.expressions.append((path, field, compile(ast.Expression(node.value), '<real-report-projection>', 'eval')))
        tree = ast.parse((ROOT / 'app/app.py').read_text(encoding='utf-8-sig'))
        fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'api_ai_sales_draft_check')
        node = next(n for n in ast.walk(fn) if isinstance(n, ast.keyword) and n.arg == 'tax_rate')
        cls.expressions.append(('app/app.py', 'tax_rate', compile(ast.Expression(node.value), '<real-ai-tax-projection>', 'eval')))
        tree = ast.parse((ROOT / 'app/utils.py').read_text(encoding='utf-8-sig'))
        helper = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'round_money_product')
        namespace = dict(Decimal=Decimal, InvalidOperation=InvalidOperation, ROUND_HALF_UP=ROUND_HALF_UP,
                         localcontext=localcontext, math=math)
        exec(compile(ast.Module(body=[helper], type_ignores=[]), '<real-money-helper>', 'exec'), namespace)
        cls.product = staticmethod(namespace['round_money_product'])

    def setUp(self):
        for target, name in ((socket.socket, 'connect'), (socket.socket, 'connect_ex'),
                             (socket, 'getaddrinfo'), (sqlite3, 'connect'), (subprocess, 'Popen')):
            guard = patch.object(target, name, refuse)
            guard.start()
            self.addCleanup(guard.stop)

    def check(self, field, amount, rate, expected, source_present=True):
        item = SimpleNamespace(amount=amount, tax_rate=rate, quantity=1.15, price=3.5)
        namespace = dict(item=item, sales_item=item if source_present else None,
                         round_money_product=self.product)
        for path, name, expression in self.expressions:
            if name == field and (source_present or path != 'app/app.py'):
                with self.subTest(path=path, field=field, amount=amount, rate=rate):
                    self.assertEqual(eval(expression, namespace), expected)

    def test_explicit_zero_amount_is_preserved(self):
        self.check('line_amount', 0, 0, 0)

    def test_historical_nonzero_amount_is_preserved(self):
        self.check('line_amount', 4.02, 0, 4.02)
        self.check('line_amount', 7.77, 0.13, 7.77)

    def test_missing_amount_keeps_existing_decimal_fallback(self):
        self.check('line_amount', None, 0, 4.03)

    def test_explicit_zero_tax_rate_is_preserved(self):
        self.check('tax_rate', 4.03, 0, 0)

    def test_missing_tax_rate_keeps_default(self):
        self.check('tax_rate', 4.03, None, 0.13)

    def test_absent_source_order_keeps_report_default(self):
        self.check('tax_rate', 4.03, 0, 0.13, source_present=False)

    def test_ordinary_tax_rate_is_unchanged(self):
        self.check('tax_rate', 4.03, 0.13, 0.13)


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(SalesZeroFinancialContract)
    assert suite.countTestCases() == 7
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
