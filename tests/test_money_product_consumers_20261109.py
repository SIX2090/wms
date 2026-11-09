"""Run selected real money expressions on synthetic input, without importing WMS."""
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
TARGETS = {
    'app/app.py': 23,
    'app/routes/after_sale_out.py': 3,
    'app/routes/batch_import.py': 3,
    'app/routes/bom.py': 4,
    'app/routes/in_order.py': 12,
    'app/routes/mobile.py': 6,
    'app/routes/native_api.py': 6,
    'app/routes/out_order.py': 4,
    'app/routes/purchase_order.py': 4,
    'app/routes/purchase_request.py': 3,
    'app/routes/sales.py': 5,
    'app/routes/subcontract.py': 5,
    'app/routes/transfer.py': 5,
    'app/services/sales_report_print.py': 2,
}


def deny(*_args, **_kwargs):
    raise AssertionError('database, network and subprocess are forbidden')


class MoneyConsumerTests(unittest.TestCase):
    def setUp(self):
        for guard in (patch.object(socket.socket, 'connect', deny),
                      patch.object(socket.socket, 'connect_ex', deny),
                      patch.object(socket, 'getaddrinfo', deny),
                      patch.object(sqlite3, 'connect', deny),
                      patch.object(subprocess, 'Popen', deny)):
            guard.start()
            self.addCleanup(guard.stop)
        tree = ast.parse((ROOT / 'app/utils.py').read_text(encoding='utf-8-sig'))
        funcs = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name in ('round_to_2_decimals', 'round_money_product', 'normalize_stock_quantity')]
        self.assertEqual(len(funcs), 3)
        self.env = {'Decimal': Decimal, 'ROUND_HALF_UP': ROUND_HALF_UP,
                    'localcontext': localcontext, 'math': math, 'STOCK_COMPARE_EPSILON': 1e-6}
        exec(compile(ast.fix_missing_locations(ast.Module(body=funcs, type_ignores=[])),
                     '<synthetic-real-money-functions>', 'exec'), self.env)
        class MoneyRow(types.SimpleNamespace):
            def __getitem__(self, key):
                return getattr(self, key)
        item = MoneyRow(quantity=1.15, price=3.5, shipped_quantity=1.15, unit_cost=3.5)
        item.material = item
        self.env.update({name: 1.15 for name in ('quantity', 'qty', 'current_stock', 'receive_qty',
                        'suggested_qty', 'remain_qty', 'order_qty', 'received_qty',
                        'remaining_qty', 'remaining_quantity', 'remaining', 'new_qty')})
        self.env.update(price=3.5, prc=3.5, estimated_price=3.5, unit_cost=3.5, new_price=3.5,
                        item=item, order_item=item, in_item=item, line=item,
                        source_item=types.SimpleNamespace(quantity=1.15, material=item),
                        material=types.SimpleNamespace(stock=1.15, price=3.5),
                        row={'suggested_qty': 1.15})

    def test_selected_real_money_consumers_use_exact_decimal_product(self):
        checked = 0
        for path, minimum in TARGETS.items():
            with self.subTest(path=path):
                tree = ast.parse((ROOT / path).read_text(encoding='utf-8-sig'))
                calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                         and isinstance(node.func, ast.Name) and node.func.id == 'round_money_product']
                self.assertGreaterEqual(len(calls), minimum)
                for call in calls:
                    for nested in ast.walk(call):
                        if isinstance(nested, ast.Call):
                            self.assertIsInstance(nested.func, ast.Name)
                            self.assertIn(nested.func.id, ('round_money_product', 'round_to_2_decimals',
                                                          'normalize_stock_quantity'))
                    expression = ast.fix_missing_locations(ast.Expression(body=call))
                    actual = eval(compile(expression, '<synthetic-money-consumer>', 'eval'), self.env)
                    self.assertEqual(actual, 4.03, f'{path}:{call.lineno}')
                    checked += 1
        self.assertGreater(checked, 60)


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(MoneyConsumerTests)
    if suite.countTestCases() != 1:
        raise SystemExit('synthetic test list must be explicit and nonempty')
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
