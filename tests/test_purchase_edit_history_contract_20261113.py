"""Actual purchase save source on explicit fake ORM; no app/DB/network/children."""
import ast
import builtins
from copy import deepcopy
from datetime import date, datetime
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


def deny(*args, **kwargs):
    raise AssertionError('app import, DB, network and child processes forbidden')


def extract(path, names):
    tree = ast.parse((ROOT / path).read_text(encoding='utf-8-sig'))
    nodes = []
    for name in names:
        matches = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == name]
        if not matches and name.startswith('_purchase_edit_'):
            continue
        if len(matches) != 1:
            raise AssertionError('actual function must be unique: ' + name)
        node = matches[0]
        node.decorator_list = []
        node.body = [stmt for stmt in node.body if not (isinstance(stmt, ast.ImportFrom) and stmt.module == 'app')]
        nodes.append(node)
    return nodes


class PurchaseEditHistoryContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env = dict(Decimal=Decimal, InvalidOperation=InvalidOperation, ROUND_HALF_UP=ROUND_HALF_UP,
                       localcontext=localcontext, math=math, json=json,
                       jsonify=lambda data: data, api_error=lambda message, status=400: (
                           {'status': 'error', 'msg': message}, status),
                       log_operation=lambda *args: None, generate_order_no=lambda *args: 'PO-SYNTHETIC-NEW')
        nodes = extract('app/utils.py', ('parse_float_value', 'round_to_2_decimals', 'round_money_product', 'parse_date_value'))
        nodes += extract('app/routes/purchase_order.py', ('_purchase_edit_line_id', 'save_purchase_order'))
        cls.env.update(date=date, datetime=datetime)
        exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])),
                     '<actual-purchase-save-with-explicit-fake-ORM>', 'exec'), cls.env)

    def setUp(self):
        original_import = builtins.__import__

        def guarded_import(name, *args, **kwargs):
            if name == 'app' or name.startswith('app.'):
                deny()
            return original_import(name, *args, **kwargs)

        orm = ModuleType('sqlalchemy.orm')
        orm.joinedload = lambda *args: None
        sqlalchemy = ModuleType('sqlalchemy')
        sqlalchemy.orm = orm
        login = ModuleType('flask_login')
        login.current_user = SimpleNamespace(id=9)
        for guard in (patch.object(builtins, '__import__', side_effect=guarded_import),
                      patch.object(sqlite3, 'connect', deny), patch.object(sqlite3.dbapi2, 'connect', deny),
                      patch.object(socket.socket, 'connect', deny), patch.object(socket.socket, 'connect_ex', deny),
                      patch.object(socket, 'getaddrinfo', deny), patch.object(subprocess, 'Popen', deny),
                      patch.dict(sys.modules, {'sqlalchemy': sqlalchemy, 'sqlalchemy.orm': orm, 'flask_login': login})):
            guard.start()
            self.addCleanup(guard.stop)

    def case(self, amount=4.02, quantity=1.2345, price=3.56789):
        self.references = []
        self.reference_calls = 0
        self.lock_received = False
        self.lock_fail = False
        self.next_id = 100
        self.staged = []

        class Query:
            def filter_by(query, **kwargs):
                return query

            def first(query):
                return None

        class Order(SimpleNamespace):
            items = object()
            query = Query()

            def __init__(order, **values):
                defaults = dict(id=None, items=[], total_amount=0, purchase_request_id=None)
                defaults.update(values)
                super().__init__(**defaults)

        class Item(SimpleNamespace):
            def __init__(line, **values):
                defaults = dict(id=None, received_quantity=0, purchase_request_item_id=None,
                                amount=None, contract_id=None, contract_no=None, project_name=None, remark='')
                defaults.update(values)
                super().__init__(**defaults)

        self.order_model, self.item_model = Order, Item
        line = Item(id=10, purchase_order_id=1, material_id=3, quantity=quantity, price=price,
                    amount=amount, received_quantity=0, purchase_request_item_id=700, remark='old line')
        self.order = Order(id=1, order_no='PO-SYN-HISTORY', status='pending', items=[line],
                            total_amount=9.99, purchase_request_id=77)
        self.materials = {3: SimpleNamespace(id=3, code='B-M', price=3.5),
                          4: SimpleNamespace(id=4, code='NEW', price=5)}
        material_model = SimpleNamespace(query=SimpleNamespace(filter_by=lambda **kwargs:
            SimpleNamespace(first=lambda: next((m for m in self.materials.values() if m.code == kwargs['code']), None))))
        supplier_model = object()
        self.payload = dict(order_id=1, supplier_id=5, remark='header changed only',
                            items=[dict(line_id=10, material_id=3, material_code='B-M',
                                        quantity=str(quantity), price='' if price is None else str(price), remark='old line')])
        self.before = deepcopy(self.order.__dict__)

        def get(model, ident):
            if model is Order:
                return self.order if ident == self.order.id else None
            if model is material_model:
                return self.materials.get(ident)
            if model is supplier_model:
                return SimpleNamespace(id=5) if ident == 5 else None
            return None

        def add(obj):
            if isinstance(obj, Order):
                obj.id = 2
                self.order = obj
            else:
                obj.id = self.next_id
                self.next_id += 1
                self.order.items.append(obj)

        def rollback():
            self.order.__dict__.clear()
            self.order.__dict__.update(deepcopy(self.before))

        def referenced(ident):
            self.reference_calls += 1
            return self.references.pop(0) if self.references else False

        def lock(*args):
            if self.lock_received:
                self.order.items[0].received_quantity = .5
            return self.order, not self.lock_fail

        self.env.update(Material=material_model, Supplier=supplier_model, PurchaseOrder=Order, PurchaseOrderItem=Item,
                        request=SimpleNamespace(get_json=lambda **kwargs: self.payload, form={}),
                        db=SimpleNamespace(session=SimpleNamespace(get=get, add=add, delete=lambda row: self.order.items.remove(row),
                            flush=lambda: None, commit=lambda: None, rollback=rollback)),
                        _acquire_order_write_lock=lock, has_inbound_reference=referenced,
                        _find_or_create_supplier=lambda name: SimpleNamespace(id=5),
                        stage_document_response=self.staged.append, g=SimpleNamespace(document_edit_guard=True),
                        app=SimpleNamespace(logger=SimpleNamespace(error=deny)))
        return line

    def post(self):
        result = self.env['save_purchase_order']()
        return result if isinstance(result, tuple) else (result, 200)

    def snapshot(self):
        return self.order.total_amount, self.order.purchase_request_id, tuple(
            (row.id, row.quantity, row.price, row.amount, row.received_quantity, row.purchase_request_item_id)
            for row in self.order.items)

    def test_only_remarks_keep_recorded_money_precision_and_request_source(self):
        for amount in (0, 4.02, 7.77):
            with self.subTest(amount=amount):
                self.case(amount=amount)
                before = self.snapshot()
                self.payload['items'][0]['remark'] = 'line changed only'
                self.assertEqual(self.post()[1], 200)
                self.assertEqual(self.snapshot(), before)
                self.assertEqual(self.order.items[0].remark, 'line changed only')

    def test_existing_reference_checks_reject_before_and_after_lock(self):
        for sequence in ([True], [False, True]):
            with self.subTest(sequence=sequence):
                self.case()
                before = self.snapshot()
                self.references = list(sequence)
                self.assertEqual(self.post()[1], 400)
                self.assertEqual(self.snapshot(), before)
                self.assertEqual(self.reference_calls, len(sequence))

    def test_legacy_no_identity_retains_explicit_replacement(self):
        self.case()
        self.payload['items'][0].pop('line_id')
        self.assertEqual(self.post()[1], 200)
        row, = self.order.items
        self.assertEqual((row.quantity, row.price, row.amount, row.purchase_request_item_id), (1.23, 3.57, 4.39, None))

    def test_quantity_change_keeps_saved_price_precision_and_upstream_link(self):
        self.case()
        self.payload['items'][0]['quantity'] = '2'
        self.assertEqual(self.post()[1], 200)
        row, = self.order.items
        self.assertEqual((row.id, row.quantity, row.price, row.amount, row.purchase_request_item_id), (10, 2, 3.56789, 7.14, 700))
        self.assertEqual(self.order.total_amount, 7.14)

    def test_price_change_keeps_saved_quantity_precision(self):
        self.case()
        self.payload['items'][0]['price'] = '0'
        self.assertEqual(self.post()[1], 200)
        row, = self.order.items
        self.assertEqual((row.id, row.quantity, row.price, row.amount, row.purchase_request_item_id), (10, 1.2345, 0, 0, 700))

    def test_user_changing_to_two_decimals_is_not_mistaken_for_unchanged(self):
        self.case()
        self.payload['items'][0]['quantity'] = '1.23'
        self.assertEqual(self.post()[1], 200)
        row, = self.order.items
        self.assertEqual((row.quantity, row.price, row.amount), (1.23, 3.56789, 4.39))

    def test_small_saved_quantity_is_kept_but_new_zero_is_rejected(self):
        self.case(quantity=.0001)
        before = self.snapshot()
        self.assertEqual(self.post()[1], 200)
        self.assertEqual(self.snapshot(), before)
        self.case()
        before = self.snapshot()
        self.payload['items'].append(dict(line_id=None, material_id=4, quantity='0', price='3'))
        self.assertEqual(self.post()[1], 400)
        self.assertEqual(self.snapshot(), before)

    def test_none_amount_only_is_filled_from_saved_components(self):
        self.case(amount=None, quantity=1.15, price=3.5)
        self.assertEqual(self.post()[1], 200)
        row, = self.order.items
        self.assertEqual((row.id, row.quantity, row.price, row.amount), (10, 1.15, 3.5, 4.03))
        self.assertEqual(self.order.total_amount, 9.99)

    def test_missing_saved_price_is_kept_until_operator_enters_one(self):
        self.case(price=None)
        before = self.snapshot()
        self.assertEqual(self.post()[1], 200)
        self.assertEqual(self.snapshot(), before)
        self.payload['items'][0]['price'] = '3.5'
        self.assertEqual(self.post()[1], 200)
        self.assertEqual((self.order.items[0].price, self.order.items[0].amount), (3.5, 4.32))

    def test_unknown_duplicate_and_invalid_ids_do_not_match_by_material(self):
        for value in (999, 0, -1, True, 10.0, 'bad', '1.0', 2**63, 'duplicate'):
            with self.subTest(value=value):
                self.case()
                before = self.snapshot()
                if value == 'duplicate':
                    self.payload['items'].append(dict(self.payload['items'][0]))
                else:
                    self.payload['items'][0]['line_id'] = value
                self.assertEqual(self.post()[1], 400)
                self.assertEqual(self.snapshot(), before)

    def test_modern_identity_requires_existing_signed_revision(self):
        self.case()
        before = self.snapshot()
        self.env['g'].document_edit_guard = False
        self.assertEqual(self.post()[1], 409)
        self.assertEqual(self.snapshot(), before)

    def test_received_quantity_is_rechecked_around_existing_lock(self):
        for moment in ('before', 'after'):
            with self.subTest(moment=moment):
                row = self.case()
                if moment == 'before':
                    row.received_quantity = .5
                else:
                    self.lock_received = True
                self.assertEqual(self.post()[1], 400)
                self.assertEqual((self.order.items[0].id, self.order.items[0].amount), (10, 4.02))

    def test_mixed_deletion_and_new_row_preserve_retained_identity(self):
        row = self.case(amount=4.02, quantity=1.15, price=3.5)
        removed = deepcopy(row)
        removed.id = 11
        self.order.items.append(removed)
        self.payload['items'].append(dict(line_id=None, material_id=4, quantity='2', price='3'))
        self.assertEqual(self.post()[1], 200)
        self.assertEqual([(r.id, r.material_id, r.amount, r.purchase_request_item_id) for r in self.order.items],
                         [(10, 3, 4.02, 700), (100, 4, 6, None)])
        self.assertEqual(self.order.total_amount, 10.02)

    def test_new_material_requires_new_row_identity_and_carries_no_old_source(self):
        self.case()
        before = self.snapshot()
        self.payload['items'][0].update(material_id=4, material_code='NEW')
        self.assertEqual(self.post()[1], 400)
        self.assertEqual(self.snapshot(), before)
        self.payload['items'][0]['line_id'] = None
        self.assertEqual(self.post()[1], 200)
        row, = self.order.items
        self.assertEqual((row.material_id, row.purchase_request_item_id), (4, None))

    def test_client_saved_amount_is_not_a_server_financial_snapshot(self):
        self.case()
        before = self.snapshot()
        self.payload['items'][0].update(saved_amount=999, amount=888)
        self.assertEqual(self.post()[1], 200)
        self.assertEqual(self.snapshot(), before)

    def test_new_document_with_a_foreign_old_line_id_is_rolled_back(self):
        self.case()
        before = self.snapshot()
        self.payload['order_id'] = None
        self.assertEqual(self.post()[1], 400)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.staged, [])

    def test_unknown_blank_price_cannot_recalculate_quantity_change_as_zero(self):
        self.case(amount=7.77, price=None)
        self.payload['items'][0].update(quantity='2', price='')
        before = self.snapshot()
        body, status = self.post()
        self.assertEqual(status, 400, 'observed money state: ' + repr(self.snapshot()))
        self.assertIn('单价', body['msg'])
        self.assertEqual(self.snapshot(), before)
        self.assertIsNone(getattr(self.order, 'remark', None))

    def test_explicit_zero_or_positive_price_allows_quantity_change(self):
        for price, amount in (('0', 0), ('3.5', 7)):
            with self.subTest(price=price):
                self.case(amount=7.77, price=None)
                self.payload['items'][0].update(quantity='2', price=price)
                self.assertEqual(self.post()[1], 200)
                row, = self.order.items
                self.assertEqual((row.id, row.quantity, row.price, row.amount, row.purchase_request_item_id),
                                 (10, 2, float(price), amount, 700))
                self.assertEqual(self.order.total_amount, amount)


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(PurchaseEditHistoryContract)
    if suite.countTestCases() != 18:
        raise SystemExit('explicit source-model list must contain 18 tests')
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
