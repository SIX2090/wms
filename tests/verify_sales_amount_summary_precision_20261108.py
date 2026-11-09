"""Synthetic source-level sales amount regression; run with python -I -S -B.

The current code is expected to fail the two-line rounding test. No WMS app,
database, network, or child process is used.
"""
import ast
import builtins
from decimal import Decimal, ROUND_HALF_UP, localcontext
import math
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import types
import unittest


ROOT = Path(__file__).resolve().parents[1]


def main():
    def deny(*_args, **_kwargs):
        raise AssertionError('禁止应用导入、数据库、网络或子进程')

    sqlite3.connect = deny
    sqlite3.dbapi2.connect = deny
    socket.socket.connect = deny
    socket.socket.connect_ex = deny
    socket.getaddrinfo = deny
    subprocess.Popen = deny
    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == 'app' or name.startswith('app.'):
            deny()
        return original_import(name, *args, **kwargs)

    builtins.__import__ = guarded_import

    def extract(path, name):
        tree = ast.parse((ROOT / path).read_text(encoding='utf-8-sig'))
        matches = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == name]
        if len(matches) != 1:
            raise AssertionError('目标函数不存在或不唯一: ' + name)
        function = matches[0]
        function.decorator_list = []
        function.body = [node for node in function.body
                         if not (isinstance(node, ast.ImportFrom) and node.module == 'sqlalchemy')]
        return function

    namespace = {'Decimal': Decimal, 'ROUND_HALF_UP': ROUND_HALF_UP, 'localcontext': localcontext, 'math': math,
                 'inspect': lambda *_args, **_kwargs: None, 'STOCK_COMPARE_EPSILON': 1e-6}
    functions = [extract('app/utils.py', 'round_to_2_decimals'),
                 extract('app/utils.py', 'round_money_product'),
                 extract('app/app.py', 'recalculate_sales_order')]
    exec(compile(ast.fix_missing_locations(ast.Module(body=functions, type_ignores=[])),
                 '<synthetic-source>', 'exec'), namespace)
    report = extract('app/services/sales_report_print.py', 'sales_summary_context')
    assignments = [node.value for node in ast.walk(report) if isinstance(node, ast.Assign)
                   and any(isinstance(target, ast.Name) and target.id == 'shipped_amount'
                           for target in node.targets)]
    if len(assignments) != 1:
        raise AssertionError('销售报表发货金额表达式不唯一，须重新核对')
    expression = compile(ast.fix_missing_locations(ast.Expression(body=assignments[0])),
                         '<synthetic-report-expression>', 'eval')

    class SalesSummaryAmount(unittest.TestCase):
        def values(self, quantities, price):
            items = [types.SimpleNamespace(quantity=qty, shipped_quantity=qty, price=price, tax_rate=0)
                     for qty in quantities]
            order = types.SimpleNamespace(items=items, status='draft')
            namespace['recalculate_sales_order'](order)
            report_amount = eval(expression, {'round_to_2_decimals': namespace['round_to_2_decimals'],
                                              'round_money_product': namespace['round_money_product'],
                                              'orders': [order]})
            return order.shipped_amount, report_amount

        def test_regular_values_match(self):
            self.assertEqual(self.values([1.0, 2.0], 0.5), (1.5, 1.5))

        def test_report_shipped_amount_matches_line_rounded_order(self):
            order_amount, report_amount = self.values([0.01, 0.01], 0.5)
            self.assertEqual(order_amount, 0.02)
            self.assertEqual(report_amount, order_amount,
                             '销售汇总报表的发货金额应与同口径单据金额一致')

        def test_report_matches_several_rounded_orders_and_empty_orders(self):
            orders = []
            for quantities, price in (([0.01, 0.01], 0.5), ([1.0, 2.0], 0.5), ([], 3.5)):
                items = [types.SimpleNamespace(quantity=qty, shipped_quantity=qty, price=price, tax_rate=0)
                         for qty in quantities]
                order = types.SimpleNamespace(items=items, status='draft')
                namespace['recalculate_sales_order'](order)
                orders.append(order)
            actual = eval(expression, {'round_to_2_decimals': namespace['round_to_2_decimals'],
                                       'round_money_product': namespace['round_money_product'],
                                       'orders': orders})
            self.assertEqual(actual, namespace['round_to_2_decimals'](sum(order.shipped_amount for order in orders)))

        def test_report_tolerates_missing_quantity_and_price(self):
            items = [types.SimpleNamespace(quantity=0, shipped_quantity=None, price=None, tax_rate=0)]
            order = types.SimpleNamespace(items=items, status='draft')
            namespace['recalculate_sales_order'](order)
            actual = eval(expression, {'round_to_2_decimals': namespace['round_to_2_decimals'],
                                       'round_money_product': namespace['round_money_product'], 'orders': [order]})
            self.assertEqual(actual, order.shipped_amount)

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(SalesSummaryAmount)
    if suite.countTestCases() != 4:
        raise RuntimeError('测试清单不完整或为空')
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)


def test_sales_amount_precision_in_isolated_process():
    env = {key: os.environ[key] for key in ('SYSTEMROOT', 'WINDIR') if key in os.environ}
    result = subprocess.run([sys.executable, '-I', '-S', '-B', '-X', 'utf8', __file__],
                            env=env, capture_output=True, text=True, encoding='utf-8', timeout=30)
    assert result.returncode == 0, result.stderr


if __name__ == '__main__':
    main()
