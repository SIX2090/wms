"""Synthetic AI sales reconciliation cases; no app, DB, network or children."""
import builtins
import ast
import dataclasses
from decimal import Decimal
from datetime import datetime
from pathlib import Path
import runpy
import socket
import sqlite3
import subprocess
import types
import json
import uuid
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def forbid(*_args, **_kwargs):
    raise AssertionError('WMS import, database, network and subprocess are forbidden')


class SalesReconciliationAmounts(unittest.TestCase):
    def setUp(self):
        original_import = builtins.__import__

        def safe_import(name, *args, **kwargs):
            if name == 'app' or name.startswith('app.'):
                return forbid()
            return original_import(name, *args, **kwargs)

        for guard in (
            patch.object(socket.socket, 'connect', forbid),
            patch.object(socket.socket, 'connect_ex', forbid),
            patch.object(socket, 'getaddrinfo', forbid),
            patch.object(sqlite3, 'connect', forbid),
            patch.object(subprocess, 'Popen', forbid),
            patch.object(builtins, '__import__', side_effect=safe_import),
        ):
            guard.start()
            self.addCleanup(guard.stop)
        self.module = runpy.run_path(str(ROOT / 'app/ai/documents/sales_draft_validation.py'))

    def order(self, lines, shipped_amount):
        return self.module['SalesOrderInfo'](
            1, 'SYN-ORDER', 'confirmed', 'shipped', 'synthetic customer',
            tuple(lines), shipped_amount=shipped_amount)

    def line(self, line_id, quantity, price):
        return self.module['SalesLineInfo'](
            line_id, line_id, 'SYN', 'synthetic material', quantity, quantity, price, 0)

    def outbound(self, lines, status='completed'):
        return self.module['OutboundDraftInfo'](
            1, 'SYN-OUT', status, 1, 'SYN-ORDER', 'synthetic customer', tuple(lines))

    def reconcile(self, order, *outbounds):
        return self.module['reconcile_sales_report'](sales_order=order, outbound_drafts=list(outbounds))

    def test_order_and_outbound_line_split_can_change_recorded_total(self):
        order = self.order([self.line(i, .01, .5) for i in range(1, 5)], .04)
        outbound = self.outbound([{'material_id': 1, 'quantity': .04, 'price': .5, 'amount': .02}])
        result = self.reconcile(order, outbound)
        self.assertTrue(result.quantity_consistent)
        self.assertFalse(result.amount_consistent, '已存订单金额 0.04 与出库金额 0.02 超过一分容差')
        self.assertAlmostEqual(result.amount_diff, .02)

    def test_explicit_stored_outbound_amount_cannot_be_ignored(self):
        order = self.order([self.line(1, 1, 1)], 1.0)
        outbound = self.outbound([{'material_id': 1, 'quantity': 1, 'price': 1, 'amount': 2}])
        result = self.reconcile(order, outbound)
        self.assertFalse(result.amount_consistent, '已存金额与数量乘价不同时不能错误报告通过')
        self.assertAlmostEqual(result.amount_diff, 1.0)

    def test_exactly_one_cent_remains_within_existing_tolerance(self):
        order = self.order([self.line(1, 1, 1.01)], 1.01)
        outbound = self.outbound([{'material_id': 1, 'quantity': 1, 'price': 1, 'amount': 1}])
        result = self.reconcile(order, outbound)
        self.assertTrue(result.amount_consistent, '既有一分容差包含恰好一分')
        self.assertAlmostEqual(result.amount_diff, .01)

    def test_ordinary_values_and_draft_exclusion(self):
        order = self.order([self.line(1, 1, 3)], 3)
        complete = self.outbound([{'material_id': 1, 'quantity': 1, 'price': 3, 'amount': 3}])
        draft = self.outbound([{'material_id': 1, 'quantity': 50, 'price': 3, 'amount': 150}],
                              status='pending')
        result = self.reconcile(order, complete, draft)
        self.assertTrue(result.is_reconciled)
        self.assertEqual(result.amount_diff, 0)

    def test_missing_order_amount_cannot_be_reported_as_reconciled(self):
        order = self.order([self.line(1, 1, 3)], None)
        complete = self.outbound([{'material_id': 1, 'quantity': 1, 'price': 3, 'amount': 3}])
        result = self.reconcile(order, complete)
        self.assertFalse(result.amount_consistent)
        self.assertFalse(result.is_reconciled)
        self.assertIsNone(result.amount_diff)
        self.assertIsNone(result.to_dict()['amount_diff'])
        self.assertTrue(any('人工核对' in value for value in result.details))

    def test_missing_outbound_amount_cannot_be_reported_as_reconciled(self):
        order = self.order([self.line(1, 1, 3)], 3)
        for supplied in ({'material_id': 1, 'quantity': 1, 'price': 3},
                         {'material_id': 1, 'quantity': 1, 'price': 3, 'amount': None}):
            with self.subTest(supplied=supplied):
                result = self.reconcile(order, self.outbound([supplied]))
                self.assertFalse(result.is_reconciled)
                self.assertIsNone(result.amount_diff)
                self.assertTrue(any('人工核对' in value for value in result.details))

    def test_invalid_nonfinite_values_require_manual_review(self):
        for bad in (float('nan'), float('inf'), '-inf', 'bad', True, Decimal('1e10000')):
            with self.subTest(bad=bad):
                order = self.order([self.line(1, 1, 3)], 3)
                result = self.reconcile(order, self.outbound([
                    {'material_id': 1, 'quantity': 1, 'price': 3, 'amount': bad}]))
                self.assertFalse(result.is_reconciled)
                self.assertIsNone(result.amount_diff)
                result = self.reconcile(self.order([self.line(1, 1, 3)], bad), self.outbound([
                    {'material_id': 1, 'quantity': 1, 'price': 3, 'amount': 3}]))
                self.assertFalse(result.is_reconciled)
                self.assertIsNone(result.amount_diff)

    def test_actual_zero_is_not_treated_as_missing(self):
        order = self.order([self.line(1, 1, 0)], 0)
        result = self.reconcile(order, self.outbound([
            {'material_id': 1, 'quantity': 1, 'price': 0, 'amount': 0}]))
        self.assertTrue(result.is_reconciled)
        self.assertEqual(result.amount_diff, 0)

    def test_amount_greater_than_one_cent_is_not_accepted(self):
        order = self.order([self.line(1, 1, 1.011)], 1.011)
        result = self.reconcile(order, self.outbound([
            {'material_id': 1, 'quantity': 1, 'price': 1, 'amount': 1}]))
        self.assertFalse(result.amount_consistent)
        self.assertAlmostEqual(result.amount_diff, .011)

    def test_no_completed_outbounds_requires_no_synthetic_line_amount(self):
        order = self.order([self.line(1, 0, 3)], 0)
        draft = self.outbound([{'material_id': 1, 'quantity': 1, 'price': 3}], status='pending')
        result = self.reconcile(order, draft)
        self.assertTrue(result.is_reconciled)
        self.assertEqual(result.amount_diff, 0)

    def test_large_decimal_amounts_do_not_lose_the_difference(self):
        order = self.order([self.line(1, 1, 1)], Decimal('9999999999999999.99'))
        result = self.reconcile(order, self.outbound([
            {'material_id': 1, 'quantity': 1, 'price': 1,
             'amount': Decimal('9999999999999999.97')}]))
        self.assertFalse(result.amount_consistent)
        self.assertAlmostEqual(result.amount_diff, .02)

    def test_unrepresentable_recorded_amount_requires_manual_review(self):
        huge = Decimal('1' + '0' * 100)
        order = self.order([self.line(1, 1, 1)], huge)
        outbound = self.outbound([{'material_id': 1, 'quantity': 1, 'price': 1,
                                   'amount': Decimal('1' + '0' * 100 + '.02')}])
        result = self.reconcile(order, outbound)
        self.assertFalse(result.is_reconciled)
        self.assertIsNone(result.amount_diff)
        self.assertTrue(any('人工核对' in value for value in result.details))

    def test_orm_adapter_keeps_real_decimal_and_none(self):
        tree = ast.parse((ROOT / 'app/app.py').read_text(encoding='utf-8-sig'))
        nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name == 'api_ai_sales_draft_check']
        self.assertEqual(len(nodes), 1)
        function = nodes[0]
        function.decorator_list = []
        item = types.SimpleNamespace(id=1, material_id=2, material=None, quantity=1,
                                     shipped_quantity=1, price=1, tax_rate=0.13)
        out_line = types.SimpleNamespace(material_id=2, quantity=1, price=1,
                                         amount=Decimal('9999999999999999.97'))
        outbound = types.SimpleNamespace(id=2, order_no='SYN-OUT', status='completed',
                                         source_sales_order_id=1, customer='synthetic',
                                         business_type='销售出库', items=[out_line])
        order = types.SimpleNamespace(id=1, order_no='SYN', status='confirmed',
                                      shipment_status='shipped', customer=None, items=[item],
                                      total_amount=Decimal('9999999999999999.99'),
                                      shipped_amount=Decimal('9999999999999999.99'),
                                      outbound_orders=[outbound])
        class Query:
            def options(self, *_args):
                return self
            def get_or_404(self, _id):
                return order
        class FakeModel:
            items = object()
            query = Query()
        captured = {}
        class Evidence:
            def to_dict(self):
                return {}
        def evidence(**kwargs):
            captured['order'] = kwargs['sales_order']
            captured['outbound'] = kwargs['outbound_draft']
            return Evidence()
        ns = {**self.module, 'SalesOrder': FakeModel, 'selectinload': lambda _: None,
              'build_sales_draft_evidence': evidence, 'validate_ai_only_draft': lambda **_: (True, 'ok'),
              'current_user': types.SimpleNamespace(id=1, role='sales'),
              'datetime': datetime, 'uuid': uuid, 'jsonify': lambda value: value}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[])),
                     '<synthetic-adapter>', 'exec'), ns)
        result = ns['api_ai_sales_draft_check'](1)
        self.assertEqual(captured['order'].shipped_amount, Decimal('9999999999999999.99'))
        self.assertEqual(result['sales_order']['shipped_amount_exact'], '9999999999999999.99')
        self.assertEqual(captured['outbound'].lines[0]['amount'], Decimal('9999999999999999.97'))
        self.assertEqual(result['outbound_drafts'][0]['lines'][0]['amount'], '9999999999999999.97')
        order.shipped_amount = None
        out_line.amount = None
        result = ns['api_ai_sales_draft_check'](1)
        self.assertIsNone(captured['order'].shipped_amount)
        self.assertIsNone(result['outbound_drafts'][0]['lines'][0]['amount'])
        self.assertEqual(result['sales_order']['shipped_amount'], 0.0)
        self.assertIsInstance(result['sales_order']['shipped_amount'], float)
        self.assertFalse(result['sales_order']['shipped_amount_known'])
        self.assertIsNone(result['sales_order']['shipped_amount_exact'])
        item.quantity = None
        item.shipped_quantity = float('inf')
        out_line.quantity = None
        result = ns['api_ai_sales_draft_check'](1)
        self.assertIsNone(captured['order'].lines[0].quantity)
        self.assertIsNone(result['sales_order']['lines'][0]['quantity'])
        self.assertIsNone(result['sales_order']['lines'][0]['shipped_quantity'])
        self.assertFalse(result['sales_order']['quantity_known'])
        self.assertIsNone(result['outbound_drafts'][0]['lines'][0]['quantity'])
        json.dumps(result, allow_nan=False)

    def test_nonfinite_and_huge_amounts_serialize_without_invalid_numbers(self):
        for value in (None, float('nan'), float('inf'), Decimal('NaN'), Decimal('1e30'), Decimal('1e10000'), 'bad', True):
            with self.subTest(value=value):
                order = self.order([self.line(1, 1, 3)], value)
                output = order.to_dict()
                self.assertEqual(output['shipped_amount'], 0.0)
                self.assertFalse(output['shipped_amount_known'])
                self.assertIsNone(output['shipped_amount_exact'])
                json.dumps(output, allow_nan=False)
        zero = self.order([self.line(1, 1, 0)], 0).to_dict()
        self.assertTrue(zero['shipped_amount_known'])
        self.assertEqual(zero['shipped_amount_exact'], '0')
        json.dumps(zero, allow_nan=False)
        result = self.reconcile(self.order([self.line(1, 1, 3)], 3), self.outbound([
            {'material_id': 1, 'quantity': 1, 'price': 3, 'amount': 3}]))
        for value in (None, float('nan'), float('inf'), Decimal('1e10000')):
            output = dataclasses.replace(result, amount_diff=value).to_dict()
            self.assertIsNone(output['amount_diff'])
            json.dumps(output, allow_nan=False)
        for value in (float('nan'), float('inf'), Decimal('NaN'), Decimal('1e10000')):
            output = self.outbound([{'amount': value}]).to_dict()
            json.dumps(output, allow_nan=False)

    def test_missing_or_nonfinite_quantity_requires_manual_review(self):
        for value in (None, float('nan'), float('inf'), float('-inf')):
            with self.subTest(value=value, source='order'):
                order = self.order([self.line(1, value, 0)], 0)
                result = self.reconcile(order, self.outbound([
                    {'material_id': 1, 'quantity': 1, 'price': 0, 'amount': 0}]))
                self.assertFalse(result.is_reconciled)
                self.assertIsNone(result.quantity_diff)
                self.assertTrue(any('人工核对' in item for item in result.details))
                json.dumps(result.to_dict(), allow_nan=False)
            with self.subTest(value=value, source='outbound'):
                order = self.order([self.line(1, 1, 0)], 0)
                result = self.reconcile(order, self.outbound([
                    {'material_id': 1, 'quantity': value, 'price': 0, 'amount': 0}]))
                self.assertFalse(result.is_reconciled)
                self.assertIsNone(result.quantity_diff)
                self.assertTrue(any('人工核对' in item for item in result.details))
                json.dumps(result.to_dict(), allow_nan=False)

    def test_quantity_epsilon_is_unchanged(self):
        order = self.order([self.line(1, 1, 0)], 0)
        for value, expected in ((1.0, True), (1.0 + 0.5e-6, True), (1.0 + 2e-6, False)):
            with self.subTest(value=value):
                result = self.reconcile(order, self.outbound([
                    {'material_id': 1, 'quantity': value, 'price': 0, 'amount': 0}]))
                self.assertEqual(result.quantity_consistent, expected)

    def test_missing_outbound_quantity_with_inventory_is_not_formatted_as_number(self):
        order = self.order([self.line(1, 1, 1)], 1)
        outbound = self.outbound([{'price': 1, 'amount': 1}])
        result = self.module['reconcile_sales_report'](
            sales_order=order, outbound_drafts=[outbound], query_inventory_delta=lambda *_: -1)
        self.assertFalse(result.is_reconciled)
        self.assertIsNone(result.quantity_diff)
        self.assertTrue(any('人工核对' in item for item in result.details))
        json.dumps(result.to_dict(), allow_nan=False)

    def test_failed_or_nonfinite_inventory_callback_requires_manual_review(self):
        order = self.order([self.line(1, 1, 0)], 0)
        outbound = self.outbound([{'material_id': 1, 'quantity': 1, 'price': 0, 'amount': 0}])
        def failed(*_):
            raise RuntimeError('synthetic error')
        for callback in (failed, lambda *_: None, lambda *_: float('nan'), lambda *_: float('inf')):
            with self.subTest(callback=callback):
                result = self.module['reconcile_sales_report'](
                    sales_order=order, outbound_drafts=[outbound], query_inventory_delta=callback)
                self.assertFalse(result.is_reconciled)
                self.assertIsNone(result.inventory_delta)
                self.assertTrue(any('人工核对' in item for item in result.details))
                json.dumps(result.to_dict(), allow_nan=False)

    def test_inventory_callback_is_deduplicated_and_not_claimed_as_verified(self):
        lines = [self.line(1, 1, 1), self.module['SalesLineInfo'](2, 1, 'SYN', 'synthetic material', 1, 1, 1, 0)]
        order = self.order(lines, 2)
        outbound = self.outbound([{'material_id': 1, 'quantity': 2, 'price': 1, 'amount': 2}])
        calls = []
        def callback(material_id, warehouse_id):
            calls.append((material_id, warehouse_id))
            return -1
        result = self.module['reconcile_sales_report'](
            sales_order=order, outbound_drafts=[outbound], query_inventory_delta=callback, warehouse_id=2)
        self.assertEqual(calls, [(1, 2)])
        self.assertEqual(result.inventory_delta, 1)
        self.assertIsNone(result.inventory_confirmed)
        self.assertTrue(any('库存流水查询范围未确认' in detail for detail in result.details))
        self.assertTrue(result.is_reconciled)

    def test_no_inventory_callback_does_not_claim_stock_verified(self):
        order = self.order([self.line(1, 1, 1)], 1)
        outbound = self.outbound([{'material_id': 1, 'quantity': 1, 'price': 1, 'amount': 1}])
        result = self.reconcile(order, outbound)
        self.assertTrue(result.is_reconciled)
        self.assertIsNone(result.inventory_confirmed)
        self.assertIsNone(result.inventory_delta)
        self.assertTrue(any('库存未核验' in detail for detail in result.details))


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(SalesReconciliationAmounts)
    if suite.countTestCases() != 20:
        raise SystemExit('合成测试清单不完整或为空')
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
