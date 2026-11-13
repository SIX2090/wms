"""Actual sales functions on synthetic objects, without app/DB/network/children.

These source-model tests do not replace the isolated real-ORM companion tests.
"""
import ast
import builtins
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
import math
from pathlib import Path
import re
import socket
import sqlite3
import subprocess
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
LINE_MONEY = ('amount', 'tax_included_amount', 'untaxed_amount', 'tax_amount', 'untaxed_price')
HEAD_MONEY = ('total_amount', 'untaxed_amount', 'tax_amount')


def deny(*args, **kwargs):
    raise AssertionError('app import, database, network and child processes forbidden')


def function(path, name):
    tree = ast.parse((ROOT / path).read_text(encoding='utf-8-sig'))
    matches = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name]
    if len(matches) != 1:
        raise AssertionError('actual source function must be unique: ' + name)
    return matches[0]


class SalesProgressMoneyContract(unittest.TestCase):
    def setUp(self):
        original_import = builtins.__import__

        def guarded_import(name, *args, **kwargs):
            if name == 'app' or name.startswith('app.'):
                deny()
            return original_import(name, *args, **kwargs)

        sqlalchemy = ModuleType('sqlalchemy')
        sqlalchemy.inspect = lambda *args, **kwargs: None
        for guard in (patch.object(builtins, '__import__', side_effect=guarded_import),
                      patch.object(sqlite3, 'connect', deny),
                      patch.object(sqlite3.dbapi2, 'connect', deny),
                      patch.object(socket.socket, 'connect', deny),
                      patch.object(socket.socket, 'connect_ex', deny),
                      patch.object(socket, 'getaddrinfo', deny),
                      patch.object(subprocess, 'Popen', deny),
                      patch.dict(sys.modules, {'sqlalchemy': sqlalchemy})):
            guard.start()
            self.addCleanup(guard.stop)
        self.inspect_module = sqlalchemy
        self.env = dict(Decimal=Decimal, InvalidOperation=InvalidOperation, ROUND_HALF_UP=ROUND_HALF_UP,
                        localcontext=localcontext, math=math, re=re, STOCK_COMPARE_EPSILON=1e-6)
        nodes = [function('app/utils.py', name) for name in ('round_to_2_decimals', 'round_money_product')]
        nodes += [function('app/app.py', name) for name in
                  ('recalculate_sales_order', 'sync_sales_order_shipment', 'build_sales_outbound_draft')]
        exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])),
                     '<actual-sales-progress-functions>', 'exec'), self.env)

    def order(self, amount=Decimal('4.02'), total=None, status='confirmed', shipped=0):
        line = SimpleNamespace(id=2, sales_order_id=1, material_id=3, quantity=1.15, price=3.5,
                               shipped_quantity=shipped, tax_rate=.13, amount=amount,
                               tax_included_amount=amount, untaxed_amount=Decimal('3.50'),
                               tax_amount=Decimal('.52'), untaxed_price=3.0435)
        order = SimpleNamespace(id=1, order_no='SYN-HISTORY', items=[line], status=status,
                                total_amount=amount if total is None else total,
                                untaxed_amount=Decimal('3.50'), tax_amount=Decimal('.52'))
        line.sales_order = order
        return order, line

    def snapshot(self, order, line):
        return tuple(getattr(order, key) for key in HEAD_MONEY), tuple(getattr(line, key) for key in LINE_MONEY)

    def wire_sync(self, order, line):
        class Field:
            def __eq__(self, other):
                return True

            def __add__(self, other):
                return lambda row: (row.shipped_quantity or 0) + other

        class Statement:
            def where(self, *args):
                return self

            def values(self, **values):
                self.values_to_apply = values
                return self

        def execute(statement):
            for key, value in statement.values_to_apply.items():
                setattr(line, key, value(line))

        model = SimpleNamespace(id=Field(), shipped_quantity=Field())
        self.env.update(SalesOrder=SimpleNamespace(query=SimpleNamespace(get=lambda ident: order)),
                        SalesOrderItem=model, sa_update=lambda model: Statement(),
                        func=SimpleNamespace(max=lambda floor, expression: lambda row: max(floor, expression(row))),
                        db=SimpleNamespace(session=SimpleNamespace(get=lambda model, ident: line,
                                            execute=execute, expire=lambda *args: None)))
        return SimpleNamespace(source_sales_order_id=1, purpose='', items=[
            SimpleNamespace(source_sales_order_item_id=2, material_id=3, quantity=.5)])

    def test_actual_complete_and_revert_calls_preserve_recorded_money(self):
        for amount in (Decimal('0'), Decimal('4.02'), Decimal('7.77')):
            with self.subTest(amount=amount):
                order, line = self.order(amount)
                before = self.snapshot(order, line)
                outbound = self.wire_sync(order, line)
                self.assertIs(self.env['sync_sales_order_shipment'](outbound), order)
                self.assertEqual(self.snapshot(order, line), before)
                self.assertEqual((line.shipped_quantity, order.status, order.shipment_status), (.5, 'confirmed', 'partial'))
                self.assertEqual(order.shipped_amount, 1.75)
                self.assertEqual(order.remaining_amount, round(float(amount) - 1.75, 2))
                self.env['sync_sales_order_shipment'](outbound, quantity_sign=-1)
                self.assertEqual(self.snapshot(order, line), before)
                self.assertEqual((line.shipped_quantity, order.shipment_status, order.shipped_amount), (0, 'pending', 0))

    def test_completed_downpush_branch_keeps_history_and_clamps_progress(self):
        order, line = self.order(Decimal('7.77'), shipped=1.2)
        before = self.snapshot(order, line)

        class Query:
            def filter(self, *args):
                return self

            def order_by(self, *args):
                return self

            def first(self):
                return None

        self.env.update(OutOrder=SimpleNamespace(query=Query(), source_sales_order_id=1, purpose='',
                                                status='', id=SimpleNamespace(desc=lambda: None)),
                        db=SimpleNamespace(or_=lambda *args: None))
        self.assertEqual(self.env['build_sales_outbound_draft'](order), (None, 'completed'))
        self.assertEqual(self.snapshot(order, line), before)
        self.assertEqual((line.shipped_quantity, order.status, order.shipment_status), (1.15, 'closed', 'shipped'))
        self.assertEqual((order.shipped_amount, order.remaining_amount), (4.03, 3.74))

    def test_missing_financial_values_only_are_filled_by_existing_formula(self):
        order, line = self.order(Decimal('7.77'), total=Decimal('9.99'))
        line.amount = line.untaxed_amount = None
        order.tax_amount = None
        self.env['recalculate_sales_order'](order, recalculate_amounts=False)
        # The recorded primary 7.77, rather than a new 4.03 product, owns missing aliases.
        self.assertEqual((line.amount, line.untaxed_amount), (7.77, 6.88))
        self.assertEqual((line.quantity, line.price), (1.15, 3.5))
        self.assertEqual((line.tax_included_amount, line.tax_amount, line.untaxed_price),
                         (Decimal('7.77'), Decimal('.52'), 3.0435))
        self.assertEqual((order.total_amount, order.untaxed_amount, order.tax_amount),
                         (Decimal('9.99'), Decimal('3.50'), .52))
        self.assertEqual(order.remaining_amount, 9.99)

    def test_missing_header_uses_recorded_lines_without_repricing(self):
        order, line = self.order(Decimal('7.77'))
        order.total_amount = order.untaxed_amount = order.tax_amount = None
        self.env['recalculate_sales_order'](order, recalculate_amounts=False)
        self.assertEqual((order.total_amount, order.untaxed_amount, order.tax_amount), (7.77, 3.5, .52))
        self.assertEqual(line.amount, Decimal('7.77'))

    def test_new_or_explicit_financial_edit_keeps_existing_calculation(self):
        for tax_rate, expected_untaxed, expected_tax in ((0, 4.03, 0), (.13, 3.57, .46), (None, 3.57, .46)):
            with self.subTest(tax_rate=tax_rate):
                order, line = self.order(Decimal('7.77'))
                line.tax_rate = tax_rate
                self.env['recalculate_sales_order'](order)
                self.assertEqual((line.amount, line.tax_included_amount, order.total_amount), (4.03, 4.03, 4.03))
                self.assertEqual((line.untaxed_amount, line.tax_amount), (expected_untaxed, expected_tax))

    def test_inconsistent_stored_header_and_lines_are_preserved(self):
        order, line = self.order(Decimal('4.02'), total=Decimal('7.77'), shipped=.5)
        line.tax_included_amount = Decimal('0')
        before = self.snapshot(order, line)
        self.env['recalculate_sales_order'](order, recalculate_amounts=False)
        self.assertEqual(self.snapshot(order, line), before)
        self.assertEqual((order.shipped_amount, order.remaining_amount), (1.75, 6.02))

    def test_cancelled_sync_and_draft_status_guards_remain(self):
        order, line = self.order(status='cancelled')
        outbound = self.wire_sync(order, line)
        before = self.snapshot(order, line)
        self.assertIsNone(self.env['sync_sales_order_shipment'](outbound))
        self.assertEqual(self.snapshot(order, line), before)
        self.assertEqual((line.shipped_quantity, order.status), (0, 'cancelled'))
        for status in ('cancelled', 'draft'):
            order, line = self.order(status=status, shipped=1.15)
            self.env['recalculate_sales_order'](order, recalculate_amounts=False)
            self.assertEqual((order.status, order.shipment_status), (status, 'shipped'))

    def test_persistent_orders_still_flush_and_reload_items(self):
        order, line = self.order()
        calls = []
        session = SimpleNamespace(flush=lambda: calls.append('flush'),
                                  expire=lambda obj, attrs: calls.append((obj is order, attrs)))
        self.inspect_module.inspect = lambda *args, **kwargs: SimpleNamespace(persistent=True, session=session)
        self.env['recalculate_sales_order'](order, recalculate_amounts=False)
        self.assertEqual(calls, ['flush', (True, ['items'])])


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(SalesProgressMoneyContract)
    if suite.countTestCases() != 8:
        raise SystemExit('explicit synthetic test list must contain eight tests')
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
