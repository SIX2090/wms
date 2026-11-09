"""Exercise real money expressions with synthetic data; no WMS or DB access."""
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


def refuse(*_args, **_kwargs):
    raise AssertionError('database, network and subprocess access are forbidden')


def function(path, name):
    tree = ast.parse((ROOT / path).read_text(encoding='utf-8-sig'))
    nodes = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == name]
    if len(nodes) != 1:
        raise AssertionError('target function is missing or ambiguous: ' + name)
    return nodes[0]


def assignment_expression(path, function_name, variable):
    target = function(path, function_name)
    values = [node.value for node in ast.walk(target) if isinstance(node, ast.Assign)
              and any(isinstance(item, ast.Name) and item.id == variable for item in node.targets)]
    if len(values) != 1:
        raise AssertionError('amount assignment is missing or ambiguous: ' + function_name)
    return values[0]


def constructor_expression(path, function_name, constructor, field):
    target = function(path, function_name)
    values = [keyword.value for call in ast.walk(target)
              if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == constructor
              for keyword in call.keywords if keyword.arg == field]
    if len(values) != 1:
        raise AssertionError('amount field is missing or ambiguous: ' + constructor + '.' + field)
    return values[0]


def explicit_import_amount_branch(function_name):
    target = function('app/routes/batch_import.py', function_name)
    branches = [node for node in ast.walk(target) if isinstance(node, ast.If)
                and isinstance(node.test, ast.Compare)
                and isinstance(node.test.left, ast.Name) and node.test.left.id == 'amt'
                and len(node.test.ops) == 1 and isinstance(node.test.ops[0], ast.Eq)
                and len(node.test.comparators) == 1
                and isinstance(node.test.comparators[0], ast.Constant)
                and node.test.comparators[0].value == 0]
    if len(branches) != 1:
        raise AssertionError('explicit import amount branch is missing or ambiguous')
    return branches[0]


class CrosscutMoneyRegression(unittest.TestCase):
    def setUp(self):
        for target in (patch.object(socket.socket, 'connect', refuse),
                       patch.object(socket.socket, 'connect_ex', refuse),
                       patch.object(socket, 'getaddrinfo', refuse),
                       patch.object(sqlite3, 'connect', refuse),
                       patch.object(subprocess, 'Popen', refuse)):
            target.start()
            self.addCleanup(target.stop)
        rounding = function('app/utils.py', 'round_to_2_decimals')
        product = function('app/utils.py', 'round_money_product')
        module = ast.fix_missing_locations(ast.Module(body=[rounding, product], type_ignores=[]))
        self.scope = {'Decimal': Decimal, 'ROUND_HALF_UP': ROUND_HALF_UP, 'localcontext': localcontext, 'math': math,
                      'quantity': 1.15, 'price': 3.50}
        exec(compile(module, '<synthetic-rounding>', 'exec'), self.scope)

    def evaluate(self, expr):
        return eval(compile(ast.fix_missing_locations(ast.Expression(body=expr)),
                            '<synthetic-amount-expression>', 'eval'), self.scope)

    def expected_amount(self):
        return float((Decimal('1.15') * Decimal('3.50')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))

    def imported_amount(self, function_name, supplied):
        self.scope.update(qty=1.15, prc=3.50, amt=supplied)
        branch = ast.fix_missing_locations(ast.Module(body=[explicit_import_amount_branch(function_name)], type_ignores=[]))
        exec(compile(branch, '<synthetic-import-amount>', 'exec'), self.scope)
        return self.scope['amt']

    def test_web_inbound_amount(self):
        expr = assignment_expression('app/routes/in_order.py', 'add_in_order', 'amount')
        self.assertEqual(self.evaluate(expr), self.expected_amount())

    def test_web_after_sale_amount(self):
        expr = assignment_expression('app/routes/after_sale_out.py', 'add_after_sale_out_order', 'amount')
        self.assertEqual(self.evaluate(expr), self.expected_amount())

    def test_transfer_detail_amount(self):
        expr = constructor_expression('app/routes/transfer.py', 'add_transfer_item', 'TransferOrderItem', 'amount')
        self.assertEqual(self.evaluate(expr), self.expected_amount())

    def test_native_inbound_amount(self):
        expr = assignment_expression('app/routes/native_api.py', 'native_api_inbound', 'amount')
        self.assertEqual(self.evaluate(expr), self.expected_amount())

    def test_h5_inbound_header_amount(self):
        expr = constructor_expression('app/routes/mobile.py', 'mobile_scan_submit', 'InOrder', 'total_amount')
        self.assertEqual(self.evaluate(expr), self.expected_amount())

    def test_inbound_import_preserves_positive_explicit_amount(self):
        self.assertEqual(self.imported_amount('import_in_order', 123.45), 123.45)

    def test_outbound_import_preserves_positive_explicit_amount(self):
        self.assertEqual(self.imported_amount('import_out_order', 123.45), 123.45)

    def test_inbound_import_computes_fallback_with_decimal_half_up(self):
        self.assertEqual(self.imported_amount('import_in_order', 0), self.expected_amount())

    def test_outbound_import_computes_fallback_with_decimal_half_up(self):
        self.assertEqual(self.imported_amount('import_out_order', 0), self.expected_amount())

    def test_non_tie_control(self):
        expr = assignment_expression('app/routes/in_order.py', 'add_in_order', 'amount')
        self.scope.update(quantity=2.0, price=3.5)
        self.assertEqual(self.evaluate(expr), 7.0)


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(CrosscutMoneyRegression)
    if suite.countTestCases() != 10:
        raise SystemExit('synthetic test list is incomplete or empty')
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
