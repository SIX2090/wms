"""Actual edit route/helpers on explicit fake ORM; no app/DB/network/children.

Real revision, SQLAlchemy persistence, rollback and source-reference behavior have
separate private-memory integration tests. This does not replace those tests.
"""
import ast
import builtins
from collections import Counter
from copy import deepcopy
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
import json
import math
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
FINANCE = ('amount', 'tax_included_amount', 'untaxed_amount', 'tax_amount', 'untaxed_price')


def deny(*args, **kwargs):
    raise AssertionError('app import, database, network and children forbidden')


def functions(path, names):
    tree = ast.parse((ROOT / path).read_text(encoding='utf-8-sig'))
    result = []
    for name in names:
        matches = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == name]
        if not matches and name.startswith('_sales_edit_'):
            continue  # Old product has no new helpers; its actual edit route still runs.
        if len(matches) != 1:
            raise AssertionError('actual source function must be unique: ' + name)
        node = matches[0]
        node.decorator_list = []
        node.body = [stmt for stmt in node.body if not (isinstance(stmt, ast.ImportFrom) and stmt.module == 'app')]
        result.append(node)
    return result


class Field:
    def __eq__(self, other):
        return True

    def in_(self, values):
        return True


class SalesEditHistoryContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env = dict(Counter=Counter, Decimal=Decimal, InvalidOperation=InvalidOperation,
                       ROUND_HALF_UP=ROUND_HALF_UP, localcontext=localcontext, json=json, math=math,
                       STOCK_COMPARE_EPSILON=1e-6, jsonify=lambda value: value,
                       log_operation=lambda *args: None, _sales_stock_shortage_warnings=lambda *args, **kwargs: [])
        nodes = functions('app/utils.py', ('parse_float_value', 'round_to_2_decimals', 'round_money_product'))
        nodes += functions('app/app.py', ('recalculate_sales_order',))
        nodes += functions('app/routes/sales.py', ('_sales_edit_line_id', '_sales_edit_number_unchanged',
                           '_sales_edit_financial_values', 'sales_order_edit'))
        exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])),
                     '<actual-sales-edit-source-with-fake-ORM>', 'exec'), cls.env)

    def setUp(self):
        original_import = builtins.__import__

        def guarded_import(name, *args, **kwargs):
            if name == 'app' or name.startswith('app.'):
                deny()
            return original_import(name, *args, **kwargs)

        sqlalchemy = ModuleType('sqlalchemy')
        sqlalchemy.inspect = lambda *args, **kwargs: None
        for guard in (patch.object(builtins, '__import__', side_effect=guarded_import),
                      patch.object(sqlite3, 'connect', deny), patch.object(sqlite3.dbapi2, 'connect', deny),
                      patch.object(socket.socket, 'connect', deny), patch.object(socket.socket, 'connect_ex', deny),
                      patch.object(socket, 'getaddrinfo', deny), patch.object(subprocess, 'Popen', deny),
                      patch.dict(sys.modules, {'sqlalchemy': sqlalchemy})):
            guard.start()
            self.addCleanup(guard.stop)

    def case(self, amount=Decimal('4.02'), quantity=1.2345, price=3.56789, total=Decimal('9.99')):
        row = SimpleNamespace(id=10, sales_order_id=1, material_id=3, quantity=quantity, price=price,
                              tax_rate=.13, shipped_quantity=0, amount=amount, tax_included_amount=amount,
                              untaxed_amount=Decimal('3.50'), tax_amount=Decimal('.52'), untaxed_price=3.0435,
                              batch_no='B', serial_no=None, remark='line note', contract_id=None,
                              contract_no=None, project_name=None)
        self.order = SimpleNamespace(id=1, order_no='SYN-EDIT', status='draft', items=[row],
                                      total_amount=total, untaxed_amount=Decimal('3.50'), tax_amount=Decimal('.52'))
        self.material = SimpleNamespace(id=3, code='B-M', price=3.5, status='active')
        other = SimpleNamespace(id=4, code='NEW', price=3.5, status='active')
        self.materials = {'B-M': self.material, 'NEW': other}
        self.payload = dict(customer_id=1, warehouse_id=4, remark='header remark changed',
                            items=[dict(line_id=10, code='B-M', quantity=str(quantity), price=str(price),
                                        tax_rate='.13', batch_no='B', remark='line note')])
        self.links = None
        self.next_id = 100
        self.before = deepcopy(self.order.__dict__)

        class Query:
            def __init__(query, kind=None):
                query.kind = kind

            def filter_by(query, **kwargs):
                return query

            def filter(query, *args):
                return query

            def first(query):
                return object() if self.links == query.kind else None

            def delete(query):
                self.order.items.clear()

        class NewLine(SimpleNamespace):
            query = Query()

            def __init__(line, **values):
                defaults = dict(id=None, shipped_quantity=0, amount=None, tax_included_amount=None,
                                untaxed_amount=None, tax_amount=None, untaxed_price=None)
                defaults.update(values)
                super().__init__(**defaults)

        def add(line):
            if line.id is None:
                line.id = self.next_id
                self.next_id += 1
            self.order.items.append(line)

        def rollback():
            self.order.__dict__.clear()
            self.order.__dict__.update(deepcopy(self.before))

        self.env.update(SalesOrder=SimpleNamespace(query=SimpleNamespace(get_or_404=lambda ident: self.order)),
                        SalesOrderItem=NewLine, Customer=object(), Employee=object(),
                        Material=SimpleNamespace(query=SimpleNamespace(filter_by=lambda **kwargs:
                            SimpleNamespace(first=lambda: self.materials.get(kwargs['code'])))),
                        OutOrder=SimpleNamespace(query=Query('out_header'), source_sales_order_id=Field(), purpose=Field()),
                        InOrder=SimpleNamespace(query=Query('in_header')),
                        OutOrderItem=SimpleNamespace(query=Query('out_line'), source_sales_order_item_id=Field()),
                        InOrderItem=SimpleNamespace(query=Query('in_line'), source_sales_order_item_id=Field()),
                        g=SimpleNamespace(document_edit_guard=True),
                        request=SimpleNamespace(get_json=lambda **kwargs: self.payload, form={}),
                        db=SimpleNamespace(or_=lambda *args: True, session=SimpleNamespace(
                            get=lambda *args: SimpleNamespace(id=1), flush=lambda: None, add=add,
                            delete=lambda line: self.order.items.remove(line), commit=lambda: None, rollback=rollback)),
                        validate_sales_warehouse=lambda *args: (SimpleNamespace(id=4, name='synthetic warehouse'), None),
                        app=SimpleNamespace(logger=SimpleNamespace(exception=deny)))
        return row

    def post(self):
        result = self.env['sales_order_edit'](1)
        return result if isinstance(result, tuple) else (result, 200)

    def financial_snapshot(self):
        return (self.order.total_amount, self.order.untaxed_amount, self.order.tax_amount,
                tuple((row.id, row.quantity, row.price, row.tax_rate,
                       *(getattr(row, field) for field in FINANCE)) for row in self.order.items))

    def test_header_and_line_remarks_preserve_identity_financials_and_precision(self):
        for amount in (Decimal('0'), Decimal('4.02'), Decimal('7.77')):
            with self.subTest(amount=amount):
                self.case(amount)
                before = self.financial_snapshot()
                self.payload['items'][0]['remark'] = 'only line note changed'
                self.assertEqual(self.post()[1], 200)
                self.assertEqual(self.financial_snapshot(), before)
                self.assertEqual(self.order.items[0].remark, 'only line note changed')

    def test_explicitly_changing_quantity_to_two_decimals_is_honored(self):
        self.case()
        self.payload['items'][0]['quantity'] = '1.23'
        self.assertEqual(self.post()[1], 200)
        row, = self.order.items
        self.assertEqual((row.id, row.quantity, row.price, row.amount), (10, 1.23, 3.56789, 4.39))

    def test_small_historical_quantity_is_preserved_when_not_edited(self):
        self.case(quantity=.0001)
        before = self.financial_snapshot()
        self.assertEqual(self.post()[1], 200)
        self.assertEqual(self.financial_snapshot(), before)

    def test_actual_price_change_keeps_original_quantity_precision(self):
        self.case()
        self.payload['items'][0]['price'] = '0'
        self.assertEqual(self.post()[1], 200)
        row, = self.order.items
        self.assertEqual((row.id, row.quantity, row.price, row.amount, self.order.total_amount), (10, 1.2345, 0, 0, 0))

    def test_actual_quantity_change_keeps_original_price_precision(self):
        self.case()
        self.payload['items'][0]['quantity'] = '2'
        self.assertEqual(self.post()[1], 200)
        row, = self.order.items
        self.assertEqual((row.id, row.quantity, row.price, row.amount, self.order.total_amount), (10, 2, 3.56789, 7.14, 7.14))

    def test_actual_tax_change_recalculates_only_that_line(self):
        self.case()
        self.payload['items'][0]['tax_rate'] = '0'
        self.assertEqual(self.post()[1], 200)
        row, = self.order.items
        self.assertEqual((row.quantity, row.price, row.amount, row.tax_amount, row.untaxed_amount), (1.2345, 3.56789, 4.4, 0, 4.4))

    def test_added_deleted_and_retained_rows_have_unambiguous_identity(self):
        old = self.case(quantity=1.15, price=3.5)
        removed = deepcopy(old)
        removed.id = 11
        self.order.items.append(removed)
        self.payload['items'].append(dict(line_id=None, code='NEW', quantity='2', price='3', tax_rate='0'))
        self.assertEqual(self.post()[1], 200)
        self.assertEqual([(row.id, row.material_id, row.amount) for row in self.order.items], [(10, 3, Decimal('4.02')), (100, 4, 6)])
        self.assertEqual(self.order.total_amount, 10.02)

    def test_foreign_and_duplicate_ids_are_rejected_without_partial_change(self):
        for variant in ('foreign', 'duplicate'):
            with self.subTest(variant=variant):
                self.case()
                before = self.financial_snapshot()
                if variant == 'foreign':
                    self.payload['items'][0]['line_id'] = 999
                else:
                    self.payload['items'].append(dict(self.payload['items'][0]))
                self.assertEqual(self.post()[1], 400)
                self.assertEqual(self.financial_snapshot(), before)

    def test_invalid_line_id_types_never_fall_back_to_material_matching(self):
        for value in (0, -1, True, False, 10.0, 'x', '0', '1.0', 2**63, '9' * 5000):
            with self.subTest(value=value):
                self.case()
                with self.assertRaisesRegex(ValueError, '销售明细标识无效'):
                    self.env['_sales_edit_line_id'](value)
                before = self.financial_snapshot()
                self.payload['items'][0]['line_id'] = value
                self.assertEqual(self.post()[1], 400)
                self.assertEqual(self.financial_snapshot(), before)

    def test_identified_protocol_requires_the_existing_signed_guard(self):
        self.case()
        self.env['g'].document_edit_guard = False
        before = self.financial_snapshot()
        self.assertEqual(self.post()[1], 409)
        self.assertEqual(self.financial_snapshot(), before)

    def test_legacy_without_ids_retains_explicit_replace_semantics(self):
        self.case()
        self.payload['items'][0].pop('line_id')
        self.assertEqual(self.post()[1], 200)
        row, = self.order.items
        self.assertEqual((row.id, row.quantity, row.price, row.amount), (100, 1.23, 3.57, 4.39))

    def test_all_new_rows_with_null_ids_are_new_financial_intent(self):
        self.case()
        self.payload['items'][0]['line_id'] = None
        self.assertEqual(self.post()[1], 200)
        self.assertEqual([(row.id, row.quantity, row.amount) for row in self.order.items], [(100, 1.23, 4.39)])

    def test_all_downstream_reference_kinds_and_shipped_history_are_protected(self):
        for kind in ('out_header', 'in_header', 'out_line', 'in_line', 'shipped'):
            with self.subTest(kind=kind):
                row = self.case()
                if kind == 'shipped':
                    row.shipped_quantity = .5
                else:
                    self.links = kind
                before = self.financial_snapshot()
                self.assertEqual(self.post()[1], 409)
                self.assertEqual(self.financial_snapshot(), before)

    def test_inactive_existing_row_is_retained_but_new_inactive_row_is_rejected(self):
        self.case()
        self.material.status = 'inactive'
        self.assertEqual(self.post()[1], 200)
        self.assertEqual(self.order.items[0].id, 10)
        self.case()
        self.material.status = 'inactive'
        self.payload['items'][0]['line_id'] = None
        self.assertEqual(self.post()[1], 400)

    def test_client_saved_amount_is_ignored(self):
        self.case()
        self.payload['items'][0].update(saved_amount=999, amount=888, tax_amount=777)
        before = self.financial_snapshot()
        self.assertEqual(self.post()[1], 200)
        self.assertEqual(self.financial_snapshot(), before)

    def test_missing_financial_values_only_are_backfilled(self):
        row = self.case(quantity=1.15, price=3.5)
        row.amount = None
        self.assertEqual(self.post()[1], 200)
        row, = self.order.items
        # An existing primary 4.02 fills None; it must not be replaced by 1.15 * 3.5 = 4.03.
        self.assertEqual((row.id, row.amount, row.tax_included_amount, row.tax_amount), (10, 4.02, Decimal('4.02'), Decimal('.52')))
        self.assertEqual((row.quantity, row.price), (1.15, 3.5))
        self.assertEqual(self.order.total_amount, Decimal('9.99'))

    def test_missing_historical_price_is_preserved_until_explicitly_entered(self):
        row = self.case(price=None)
        self.payload['items'][0]['price'] = ''
        before = self.financial_snapshot()
        self.assertEqual(self.post()[1], 200)
        self.assertEqual(self.financial_snapshot(), before)
        self.payload['items'][0]['price'] = '3.5'
        self.assertEqual(self.post()[1], 200)
        row, = self.order.items
        self.assertEqual((row.price, row.amount, self.order.total_amount), (3.5, 4.32, 4.32))

    def test_unknown_price_cannot_turn_quantity_or_tax_edit_into_zero_money(self):
        for field, value in (('quantity', '2'), ('tax_rate', '0')):
            with self.subTest(field=field):
                self.case(amount=Decimal('7.77'), price=None)
                self.payload['items'][0].update(price='', **{field: value})
                before = self.financial_snapshot()
                body, status = self.post()
                self.assertEqual(status, 400, 'observed money state: ' + repr(self.financial_snapshot()))
                self.assertIn('单价', body['msg'])
                self.assertEqual(self.financial_snapshot(), before)
                self.assertIsNone(getattr(self.order, 'remark', None), 'header mutation must roll back too')

    def test_explicit_zero_or_positive_price_allows_quantity_change(self):
        for price, amount in (('0', 0), ('3.5', 7)):
            with self.subTest(price=price):
                self.case(amount=Decimal('7.77'), price=None)
                self.payload['items'][0].update(quantity='2', price=price)
                self.assertEqual(self.post()[1], 200)
                line, = self.order.items
                self.assertEqual((line.id, line.quantity, line.price, line.amount), (10, 2, float(price), amount))
                self.assertEqual(self.order.total_amount, amount)


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(SalesEditHistoryContract)
    if suite.countTestCases() != 19:
        raise SystemExit('explicit source-model list must contain 19 tests')
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
