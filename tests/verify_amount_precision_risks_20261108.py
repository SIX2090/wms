"""合成金额回归；运行 python -I -S -B -X utf8 本文件，旧版预期失败。"""
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

    class DeniedPopen:
        def __init__(self, *_args, **_kwargs):
            deny()

    sqlite3.connect = deny
    sqlite3.dbapi2.connect = deny
    socket.socket.connect = deny
    socket.socket.connect_ex = deny
    socket.getaddrinfo = deny
    subprocess.Popen = DeniedPopen
    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == 'app' or name.startswith('app.'):
            deny()
        return original_import(name, *args, **kwargs)

    builtins.__import__ = guarded_import

    def source(path):
        return ast.parse((ROOT / path).read_text(encoding='utf-8-sig'))

    def find_function(tree, name):
        matches = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name]
        if len(matches) != 1:
            raise AssertionError('目标函数不存在或不唯一：' + name)
        return matches[0]

    round_function = find_function(source('app/utils.py'), 'round_to_2_decimals')
    product_function = find_function(source('app/utils.py'), 'round_money_product')
    namespace = {'Decimal': Decimal, 'ROUND_HALF_UP': ROUND_HALF_UP, 'localcontext': localcontext, 'math': math}
    module = ast.fix_missing_locations(ast.Module(body=[round_function, product_function], type_ignores=[]))
    exec(compile(module, '<synthetic-round-source>', 'exec'), namespace)
    round_money = namespace['round_to_2_decimals']

    route = find_function(source('app/routes/in_order.py'), 'add_in_order')
    amount_assignments = [node.value for node in ast.walk(route) if isinstance(node, ast.Assign)
                          and any(isinstance(target, ast.Name) and target.id == 'amount' for target in node.targets)
                          and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name)
                          and node.value.func.id in ('round_to_2_decimals', 'round_money_product')]
    if len(amount_assignments) != 1:
        raise AssertionError('入库金额表达式不唯一，须重新核查回归目标')

    push = find_function(source('app/routes/in_order.py'), 'create_in_order_push')
    target_totals = [node.value for node in ast.walk(push) if isinstance(node, ast.Assign)
                     and any(isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name)
                             and t.value.id == 'target' and t.attr == 'total_amount' for t in node.targets)]
    amount_expr = {}
    for node in ast.walk(push):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ('OutOrderItem', 'AfterSaleOutOrderItem'):
            matches = [kw.value for kw in node.keywords if kw.arg == 'amount']
            if len(matches) != 1 or node.func.id in amount_expr:
                raise AssertionError('下推明细金额表达式不唯一')
            amount_expr[node.func.id] = matches[0]
    if len(target_totals) != 2 or set(amount_expr) != {'OutOrderItem', 'AfterSaleOutOrderItem'}:
        raise AssertionError('下推两种目标金额表达式缺失')

    def evaluate(expr, values):
        tree = ast.fix_missing_locations(ast.Expression(body=expr))
        return eval(compile(tree, '<synthetic-money-expression>', 'eval'), values)

    class AmountPrecision(unittest.TestCase):
        def test_existing_half_up_control(self):
            self.assertEqual(round_money(1.005), 1.01)

        def test_two_decimal_inputs_use_decimal_product_before_half_up(self):
            values = {'quantity': 1.15, 'price': 3.50, 'round_to_2_decimals': round_money,
                      'round_money_product': namespace['round_money_product']}
            actual = evaluate(amount_assignments[0], values)
            expected = float((Decimal('1.15') * Decimal('3.50')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
            self.assertEqual(actual, expected, '两位数量与两位单价相乘应按既有十进制半入舍至分')

        def check_push_total(self, target, total_expr):
            material = types.SimpleNamespace(price=0.50)
            source_item = types.SimpleNamespace(material=material)
            selected = [(source_item, 0.01), (source_item, 0.01)]
            env = {'selected': selected, 'source_item': source_item, 'quantity': 0.01,
                   'price': round_money(material.price), 'round_to_2_decimals': round_money,
                   'round_money_product': namespace['round_money_product']}
            line = evaluate(amount_expr[target], env)
            header = evaluate(total_expr, env)
            self.assertEqual(Decimal(str(line)) * 2, Decimal(str(header)),
                             '下推草稿的单头金额应等于已舍入明细金额之和')

        def test_other_out_header_matches_rounded_lines(self):
            self.check_push_total('OutOrderItem', target_totals[0])

        def test_after_sale_header_matches_rounded_lines(self):
            self.check_push_total('AfterSaleOutOrderItem', target_totals[1])

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(AmountPrecision)
    if suite.countTestCases() != 4:
        raise RuntimeError('测试清单不完整或为空')
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)


def test_amount_precision_in_isolated_process():
    env = {key: os.environ[key] for key in ('SYSTEMROOT', 'WINDIR') if key in os.environ}
    result = subprocess.run([sys.executable, '-I', '-S', '-B', '-X', 'utf8', __file__],
                            env=env, capture_output=True, text=True, encoding='utf-8', timeout=30)
    assert result.returncode == 0, result.stderr


if __name__ == '__main__':
    main()
