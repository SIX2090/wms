"""Exercise actual opening-line mutation using only synthetic objects."""
import ast
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP, localcontext
import math
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import types
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def deny(*_args, **_kwargs):
    raise AssertionError('database, network and subprocess forbidden')


class HistoricalOpeningAmountTests(unittest.TestCase):
    def setUp(self):
        for guard in (patch.object(socket.socket, 'connect', deny), patch.object(socket.socket, 'connect_ex', deny),
                      patch.object(socket, 'getaddrinfo', deny), patch.object(sqlite3, 'connect', deny),
                      patch.object(subprocess, 'Popen', deny)):
            guard.start()
            self.addCleanup(guard.stop)
        self.flushes = []
        tree = ast.parse((ROOT / 'app/app.py').read_text(encoding='utf-8-sig'))
        functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in ('_apply_opening_stock_balance', '_opening_stock_saved_number', '_opening_stock_preserve_validated_line')]
        self.assertEqual(len(functions), 3)
        utils = ast.parse((ROOT / 'app/utils.py').read_text(encoding='utf-8-sig'))
        funcs = [n for n in utils.body if isinstance(n, ast.FunctionDef)
                 and n.name in ('round_to_2_decimals', 'normalize_stock_quantity', 'round_money_product')]
        self.assertEqual(len(funcs), 3)
        self.env = {'Decimal': Decimal, 'ROUND_HALF_UP': ROUND_HALF_UP, 'localcontext': localcontext, 'math': math,
                    'STOCK_COMPARE_EPSILON': 1e-6, 'date': date, 'datetime': datetime,
                    'current_user': SimpleNamespace(is_authenticated=False),
                    'db': SimpleNamespace(session=SimpleNamespace(flush=lambda: self.flushes.append(True)))}
        exec(compile(ast.fix_missing_locations(ast.Module(body=funcs + functions, type_ignores=[])),
                     '<synthetic-opening>', 'exec'), self.env)

    def apply_edit(self, line, material, quantity, price, amount, remark, **kwargs):
        # Exercise the validated server-owned edit pipeline, not a prototype flag.
        if kwargs.pop('preserve_amount_if_unchanged', False):
            item = self.env['_opening_stock_preserve_validated_line'](line, {
                'line_id': line.id, 'quantity': quantity, 'price': price, 'amount': amount,
                '_raw_quantity': quantity, '_raw_price': price}, guarded=True)
            quantity, price, amount = item['quantity'], item['price'], item['amount']
        return self.env['_apply_opening_stock_balance'](
            line, material, quantity, price, amount, remark, **kwargs)

    def line(self, amount):
        return SimpleNamespace(id=12, quantity=1.0, price=5.0, amount=amount, location='', date=date(2025, 1, 1))

    def test_unchanged_historical_line_retains_nonzero_amount(self):
        line = self.line(7.77)
        result, delta = self.apply_edit(
            line, object(), 1.0, 5.0, 5.0, '改备注', preserve_amount_if_unchanged=True)
        self.assertIs(result, line)
        self.assertEqual(delta, 0)
        self.assertEqual(line.amount, 7.77)
        self.assertEqual(line.remark, '改备注')
        self.assertEqual(len(self.flushes), 1)

    def test_unchanged_explicit_zero_is_not_treated_as_missing(self):
        line = self.line(0.0)
        self.apply_edit(
            line, object(), 1.0, 5.0, 5.0, None, preserve_amount_if_unchanged=True)
        self.assertEqual(line.amount, 0.0)

    def test_changed_price_uses_new_amount(self):
        line = self.line(7.77)
        self.apply_edit(
            line, object(), 1.0, 6.0, 6.0, None, preserve_amount_if_unchanged=True)
        self.assertEqual(line.amount, 6.0)

    def test_missing_old_amount_uses_new_amount(self):
        line = self.line(None)
        self.apply_edit(
            line, object(), 1.0, 5.0, 5.0, None, preserve_amount_if_unchanged=True)
        self.assertEqual(line.amount, 5.0)

    def test_unchanged_high_precision_history_is_not_repriced(self):
        line = self.line(7.77)
        line.quantity, line.price = 1.2345, 1.235
        self.apply_edit(
            line, object(), 1.23, 1.24, 1.52, None, preserve_amount_if_unchanged=True)
        self.assertEqual((line.quantity, line.price, line.amount), (1.2345, 1.235, 7.77))

    def test_unchanged_null_price_history_is_not_repriced(self):
        line = self.line(7.77)
        line.price = None
        self.apply_edit(
            line, object(), 1.0, 0.0, 0.0, None, preserve_amount_if_unchanged=True)
        self.assertEqual(line.amount, 7.77)

    def test_default_retains_existing_explicit_recalculation_behavior(self):
        line = self.line(7.77)
        self.env['_apply_opening_stock_balance'](line, object(), 1.0, 5.0, 5.0, None)
        self.assertEqual(line.amount, 5.0)

    def test_changed_quantity_applies_delta_and_new_amount(self):
        calls = []
        class Update:
            def where(self, *_args): return self
            def values(self, **_kwargs): return self
        self.env.update(sa_update=lambda _model: Update(),
                        Material=SimpleNamespace(id=1, stock=0),
                        location_management_enabled=lambda: False)
        self.env['db'].session.execute = lambda _statement: calls.append('total')
        self.env['db'].session.expire = lambda *_args: calls.append('expire')
        service = types.ModuleType('services.warehouse_stock_service')
        def apply(*_args, **kwargs):
            calls.append(('warehouse', kwargs['warehouse'].id))
            return True, ''
        service.apply_opening_balance = apply
        parent = types.ModuleType('services')
        parent.__path__ = []
        line = self.line(7.77)
        line.id = 12
        warehouse = SimpleNamespace(id=2, name='合成仓 B')
        with patch.dict(sys.modules, {'services': parent, 'services.warehouse_stock_service': service}):
            result, delta = self.apply_edit(
                line, SimpleNamespace(id=9), 2.0, 5.0, 10.0, None,
                warehouse=warehouse, preserve_amount_if_unchanged=True)
        self.assertIs(result, line)
        self.assertEqual((delta, line.quantity, line.amount), (1.0, 2.0, 10.0))
        self.assertEqual(calls, ['total', 'expire', ('warehouse', 2)])

    def test_opt_in_only_on_edit_not_compat_upsert(self):
        line = self.line(7.77)
        before = vars(line).copy()
        for line_id, guarded in ((13, True), (12, False)):
            with self.subTest(line_id=line_id, guarded=guarded), self.assertRaises(ValueError):
                self.env['_opening_stock_preserve_validated_line'](line, {
                    'line_id': line_id, 'quantity': 1, 'price': 5, 'amount': 999,
                    '_raw_quantity': 1, '_raw_price': 5}, guarded=guarded)
            self.assertEqual(vars(line), before)
            self.assertEqual(self.flushes, [])

        # Preserve the original edit-only/compatibility wiring contract using
        # the implemented server-owned helper rather than a prototype keyword.
        root = ast.parse((ROOT / 'app/routes/opening_stock.py').read_text(encoding='utf-8-sig'))
        native = ast.parse((ROOT / 'app/routes/native_api.py').read_text(encoding='utf-8-sig'))
        def guarded_calls(tree, name):
            matches = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name]
            self.assertEqual(len(matches), 1)
            calls = [n for n in ast.walk(matches[0]) if isinstance(n, ast.Call)
                     and isinstance(n.func, ast.Name) and n.func.id == '_opening_stock_preserve_validated_line']
            for call in calls:
                self.assertTrue(any(keyword.arg == 'guarded' for keyword in call.keywords))
            return len(calls)
        self.assertEqual(guarded_calls(root, 'add_opening_stock'), 0)
        self.assertEqual(guarded_calls(root, 'edit_opening_stock'), 1)
        self.assertEqual(guarded_calls(root, 'batch_save_opening_stock'), 1)
        self.assertEqual(guarded_calls(root, 'save_opening_stock_doc'), 1)
        self.assertEqual(guarded_calls(native, 'native_api_opening_stock_update'), 1)
        self.assertEqual(guarded_calls(native, 'native_api_opening_stock_submit'), 0)


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(HistoricalOpeningAmountTests)
    if suite.countTestCases() != 9:
        raise SystemExit('synthetic test list is incomplete or empty')
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
