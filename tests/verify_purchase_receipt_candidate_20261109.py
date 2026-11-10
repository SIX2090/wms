"""Full extracted route + receipt experiment; isolated memory only, not product code.

Run with python -I -S -B -X utf8. The create branch is changed only in an AST
copy. Models and Flask request context are synthetic; no WMS import or network.
"""
import os
import subprocess
import sys


def main():
    import ast
    import builtins
    import datetime
    import hashlib
    import json
    import math
    from decimal import Decimal, ROUND_HALF_UP, localcontext
    from functools import wraps
    from pathlib import Path
    import platform
    import socket
    import sqlite3
    import sysconfig
    import types
    import unittest

    def deny(*_args, **_kwargs):
        raise AssertionError('application import, file DB, network or subprocess forbidden')
    real_import = builtins.__import__
    def guarded_import(name, *args, **kwargs):
        level = args[3] if len(args) > 3 else kwargs.get('level', 0)
        if level == 0 and (name == 'app' or name.startswith('app.')):
            deny()
        return real_import(name, *args, **kwargs)
    builtins.__import__ = guarded_import
    memory_connect = sqlite3.connect
    sqlite3.connect = sqlite3.dbapi2.connect = deny
    socket.socket.connect = socket.socket.connect_ex = deny
    socket.create_connection = socket.getaddrinfo = deny
    class DeniedPopen:
        def __init__(self, *_args, **_kwargs):
            deny()
    subprocess.Popen = DeniedPopen
    platform.machine = lambda: 'synthetic'
    sys.path.append(sysconfig.get_paths()['purelib'])
    from flask import Flask, g, jsonify, request
    from sqlalchemy import Column, Date, Float, ForeignKey, Integer, String, UniqueConstraint, create_engine, event, text
    from sqlalchemy.exc import IntegrityError, OperationalError
    from sqlalchemy.orm import declarative_base, relationship, scoped_session, sessionmaker

    Base = declarative_base()
    class Order(Base):
        __tablename__ = 'synthetic_order'
        id = Column(Integer, primary_key=True)
        order_no = Column(String, unique=True, nullable=False)
        date = Column(Date, nullable=False)
        business_type = Column(String)
        operator_id = Column(Integer)
        status = Column(String, default='pending')
        items = relationship('Item', cascade='all, delete-orphan')
    class Item(Base):
        __tablename__ = 'synthetic_item'
        id = Column(Integer, primary_key=True)
        in_order_id = Column(Integer, ForeignKey('synthetic_order.id'))
        material_id = Column(Integer)
        quantity = Column(Float)
        price = Column(Float)
        amount = Column(Float)
        source_purchase_order_item = None
        def __init__(self, **values):
            for name, value in values.items():
                setattr(self, name, value)
    class Material(Base):
        __tablename__ = 'synthetic_material'
        id = Column(Integer, primary_key=True)
        code = Column(String, unique=True)
    class Receipt(Base):
        __tablename__ = 'synthetic_receipt'
        __table_args__ = (UniqueConstraint('user_id', 'endpoint', 'request_key'),)
        id = Column(Integer, primary_key=True)
        user_id = Column(Integer)
        endpoint = Column(String)
        request_key = Column(String)
        status_code = Column(Integer)
        response_json = Column(String)
    class PurchaseOrder(Base):
        __tablename__ = 'synthetic_purchase_order'
        id = Column(Integer, primary_key=True)
    engine = create_engine('sqlite://', creator=lambda: memory_connect(':memory:'))
    session = scoped_session(sessionmaker(bind=engine))
    Base.query = session.query_property()
    Base.metadata.create_all(engine)
    session.execute(text('CREATE TABLE synthetic_counter (prefix TEXT PRIMARY KEY, value INTEGER NOT NULL)'))
    session.execute(text('CREATE TABLE synthetic_subcontract_receive (receive_no TEXT NOT NULL)'))
    # This memory-only candidate must observe legacy writes when they happen:
    # scanning live documents at the next allocation loses an inserted/deleted
    # number. Track both shared SR sources in the same writer transaction.
    for table, column in (('synthetic_order', 'order_no'),
                          ('synthetic_subcontract_receive', 'receive_no')):
        for action in ('INSERT', 'UPDATE'):
            session.execute(text(f'''
                CREATE TRIGGER {table}_{action.lower()}_number AFTER {action} ON {table}
                WHEN substr(NEW.{column}, 1, 2) IN ('IN', 'PI', 'OI', 'SR')
                  AND length(NEW.{column}) > 6
                  AND substr(NEW.{column}, 3) NOT GLOB '*[^0-9]*'
                BEGIN
                  INSERT INTO synthetic_counter(prefix, value)
                  VALUES (substr(NEW.{column}, 1, 6), CAST(substr(NEW.{column}, 7) AS INTEGER))
                  ON CONFLICT(prefix) DO UPDATE SET value=max(value, excluded.value);
                END
            '''))
    session.add(Material(code='M1'))
    session.commit()
    assert all(not row[2] for row in session.execute(text('PRAGMA database_list')))

    root = Path(__file__).resolve().parents[1]
    route_tree = ast.parse((root / 'app/routes/in_order.py').read_text(encoding='utf-8-sig'))
    service_tree = ast.parse((root / 'app/services/web_document_idempotency.py').read_text(encoding='utf-8-sig'))
    utils_tree = ast.parse((root / 'app/utils.py').read_text(encoding='utf-8-sig'))
    def find(tree, name):
        matches = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == name]
        if len(matches) != 1:
            raise AssertionError('missing or duplicate function ' + name)
        matches[0].decorator_list = []
        return matches[0]
    route = find(route_tree, 'add_in_order')
    class RemoveImports(ast.NodeTransformer):
        def visit_ImportFrom(self, node):
            if node.module in ('app', 'flask_login', 'services.product_receipt_materials'):
                return ast.copy_location(ast.Pass(), node)
            return node
    route = RemoveImports().visit(route)
    candidates = [node for node in ast.walk(route) if isinstance(node, ast.If)
                  and isinstance(node.test, ast.Name) and node.test.id == 'order_id'
                  and any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                          and n.func.attr == 'get' for n in ast.walk(node))]
    if len(candidates) != 1:
        raise AssertionError('create/edit branch changed')
    candidates[0].orelse = ast.parse('''
prefix = {'采购入库': 'IN', '产品入库': 'PI', '其他入库': 'OI', '销售退货入库': 'SR'}[business_type]
order_no = allocate(prefix)
order = InOrder(order_no=order_no, date=date.today(), business_type=business_type, operator_id=current_user.id)
db.session.add(order)
db.session.flush()
''').body

    def allocate(prefix):
        base = prefix + datetime.datetime.now().strftime('%y%m')
        session.execute(text('INSERT OR IGNORE INTO synthetic_counter VALUES (:prefix, 0)'), {'prefix': base})
        # The write statement above acquires SQLite's writer reservation before
        # scanning; this is not portable SQL and is only a test candidate.
        rows = list(session.scalars(text('SELECT order_no FROM synthetic_order WHERE order_no LIKE :pattern'),
                                    {'pattern': base + '%'}))
        if prefix == 'SR':
            rows.extend(session.scalars(text('SELECT receive_no FROM synthetic_subcontract_receive '
                                             'WHERE receive_no LIKE :pattern'), {'pattern': base + '%'}))
        numbers = [int(no[len(base):]) for no in rows if no.startswith(base) and no[len(base):].isdecimal()]
        session.execute(text('UPDATE synthetic_counter SET value=CASE WHEN value < :n THEN :n ELSE value END '
                             'WHERE prefix=:prefix'), {'n': max(numbers, default=0), 'prefix': base})
        session.execute(text('UPDATE synthetic_counter SET value=value+1 WHERE prefix=:prefix'), {'prefix': base})
        seq = session.execute(text('SELECT value FROM synthetic_counter WHERE prefix=:prefix'),
                              {'prefix': base}).scalar_one()
        return f'{base}{seq:04d}'

    synthetic_app = Flask('synthetic_candidate')
    user = types.SimpleNamespace(id=1, is_authenticated=True)
    warehouse = types.SimpleNamespace(name='合成仓')
    env = {'request': request, 'g': g, 'jsonify': jsonify, 'json': json, 'hashlib': hashlib,
           'math': math, 'Decimal': Decimal, 'ROUND_HALF_UP': ROUND_HALF_UP, 'localcontext': localcontext,
           'wraps': wraps, 'IntegrityError': IntegrityError, 'OperationalError': OperationalError,
           'db': types.SimpleNamespace(session=session), 'MobileApiRequest': Receipt, 'current_user': user,
           'app': synthetic_app, 'InOrder': Order, 'InOrderItem': Item, 'Material': Material,
           'PurchaseOrder': PurchaseOrder, 'allocate': allocate,
           'Customer': object, 'PurchaseOrderItem': object, 'SalesOrder': object, 'SalesOrderItem': object,
           'api_error': lambda message, code=400: (jsonify(status='error', msg=message), code),
           'assert_warehouse_active': lambda *_args, **_kwargs: (True, ''),
           'get_default_warehouse': lambda: warehouse, 'validate_inventory_warehouse': lambda *_: (warehouse, ''),
           'location_management_enabled': lambda: False, 'is_future_date': lambda value: value > datetime.date.today(),
           'log_operation': lambda *_args: None, 'purchase_in_order_requires_order': lambda: False,
           'recalculate_order_total': lambda _order: None,
           'update_purchase_order_status': lambda *_: None, 'validate_purchase_receive_quantity': lambda *_: (True, ''),
           'validate_sales_return_quantity': lambda *_: (True, ''), 'sales_return_remaining_check': lambda *_: (True, ''),
           '_product_header_project': lambda _business, _contract, project: project,
           '_parse_item_batch_no': lambda value: (value, ''), '_parse_item_expiry_date': lambda _value: (None, ''),
           'resolve_product_receipt_materials': lambda items: items}
    code = ast.fix_missing_locations(ast.Module(body=[find(utils_tree, 'round_to_2_decimals'),
                                find(utils_tree, 'round_money_product'), find(service_tree, '_document_idempotent'),
                                find(service_tree, 'stage_document_response'), route], type_ignores=[]))
    exec(compile(code, '<copied-wms-route>', 'exec'), env)
    synthetic_app.add_url_rule('/in_order/add', view_func=env['_document_idempotent'](env['add_in_order'], mobile=False),
                               methods=['POST'])
    @synthetic_app.teardown_request
    def cleanup_request(_exc):
        session.rollback()

    class FullRoute(unittest.TestCase):
        def setUp(self):
            session.remove()
            session.execute(text('DELETE FROM synthetic_item'))
            session.execute(text('DELETE FROM synthetic_order'))
            session.execute(text('DELETE FROM synthetic_receipt'))
            session.execute(text('DELETE FROM synthetic_counter'))
            session.execute(text('DELETE FROM synthetic_subcontract_receive'))
            session.commit()
            self.client = synthetic_app.test_client()
            self.body = {'order_no': 'IN-OLD-PREVIEW', 'business_type': '采购入库',
                         'warehouse_id': 1, 'items': [{'code': 'M1', 'quantity': 2, 'price': 3}]}
        def post(self, key, body=None):
            return self.client.post('/in_order/add', json=body or self.body, headers={'X-Idempotency-Key': key})
        def test_lost_response_same_key_and_changed_payload(self):
            first = self.post('k1')
            self.assertEqual(first.status_code, 200, first.get_json())
            replay = self.post('k1')
            self.assertEqual(replay.get_json(), first.get_json())
            changed = self.post('k1', dict(self.body, remark='changed'))
            self.assertEqual(changed.status_code, 409)
            self.assertEqual(session.query(Order).count(), 1)
            self.assertEqual(session.query(Item).count(), 1)
        def test_same_preview_separate_keys_and_edit_by_id(self):
            a, b = self.post('a'), self.post('b')
            self.assertEqual((a.status_code, b.status_code), (200, 200))
            self.assertNotEqual(a.json['order_no'], b.json['order_no'])
            edited = self.post('edit', dict(self.body, order_id=a.json['id'], remark='edited'))
            self.assertEqual(edited.status_code, 200, edited.get_json())
            self.assertEqual(edited.json['order_no'], a.json['order_no'])
            self.assertEqual(session.query(Order).count(), 2)
        def test_deleted_number_not_reused(self):
            first = self.post('a')
            session.delete(session.get(Order, first.json['id']))
            session.commit()
            second = self.post('b')
            self.assertEqual(second.status_code, 200)
            self.assertNotEqual(first.json['order_no'], second.json['order_no'])

        def test_shared_legacy_source_delete_preserves_high_water(self):
            base = 'SR' + datetime.datetime.now().strftime('%y%m')
            session.execute(text('INSERT INTO synthetic_subcontract_receive VALUES (:number)'),
                            {'number': base + '10000'})
            session.commit()
            session.execute(text('DELETE FROM synthetic_subcontract_receive'))
            session.commit()
            self.assertEqual(allocate('SR'), base + '10001')

        def test_legacy_counter_change_rolls_back_with_writer(self):
            base = 'SR' + datetime.datetime.now().strftime('%y%m')
            session.execute(text('INSERT INTO synthetic_subcontract_receive VALUES (:number)'),
                            {'number': base + '10000'})
            session.rollback()
            self.assertEqual(allocate('SR'), base + '0001')
        def test_post_allocation_validation_error_rolls_back(self):
            invalid = self.post('failure', dict(self.body, date='bad-date'))
            self.assertEqual(invalid.status_code, 400)
            self.assertEqual(session.query(Order).count(), 0)
            self.assertEqual(session.query(Receipt).count(), 0)
            self.assertEqual(session.execute(text('SELECT count(*) FROM synthetic_counter')).scalar_one(), 0)
            self.assertEqual(self.post('failure').status_code, 200)
        def test_commit_failure_rolls_back_counter_and_receipt(self):
            def reject(_connection):
                raise RuntimeError('synthetic commit failure')
            event.listen(engine, 'commit', reject)
            try:
                result = self.post('commit-failure')
                self.assertEqual(result.status_code, 400)
            finally:
                event.remove(engine, 'commit', reject)
            self.assertEqual(session.query(Order).count(), 0)
            self.assertEqual(session.query(Receipt).count(), 0)
            self.assertEqual(session.execute(text('SELECT count(*) FROM synthetic_counter')).scalar_one(), 0)
            self.assertEqual(self.post('commit-failure').status_code, 200)
        def test_legacy_preview_preserves_product_type(self):
            body = dict(self.body, order_no='PI-OLD-PREVIEW', business_type='')
            result = self.post('legacy', body)
            self.assertEqual(result.status_code, 200, result.get_json())
            self.assertTrue(result.json['order_no'].startswith('PI'))
            self.assertEqual(session.get(Order, result.json['id']).business_type, '产品入库')

        def test_legacy_form_and_unkeyed_request(self):
            form = {'order_no': 'IN-OLD-PREVIEW', 'business_type': '采购入库',
                    'warehouse_id': '1', 'supplier_id': '1',
                    'items_json': json.dumps(self.body['items'])}
            a = self.client.post('/in_order/add', data=form)
            b = self.client.post('/in_order/add', data=form)
            self.assertEqual((a.status_code, b.status_code), (200, 200))
            self.assertNotEqual(a.json['order_no'], b.json['order_no'])
            self.assertEqual(session.query(Receipt).count(), 0)
            self.assertEqual(session.query(Order).count(), 2)

        def test_unkeyed_validation_error_rolls_back(self):
            result = self.client.post('/in_order/add', json=dict(self.body, date='bad-date'))
            self.assertEqual(result.status_code, 400)
            self.assertEqual(session.query(Order).count(), 0)
            self.assertEqual(session.execute(text('SELECT count(*) FROM synthetic_counter')).scalar_one(), 0)

        def test_replay_after_delete_returns_receipt_and_does_not_recreate(self):
            first = self.post('a')
            session.delete(session.get(Order, first.json['id']))
            session.commit()
            replay = self.post('a')
            self.assertEqual(replay.json, first.json)
            self.assertEqual(session.query(Order).count(), 0)

        def test_legacy_writer_after_counter_seed_must_not_conflict(self):
            first = self.post('a')
            self.assertEqual(first.status_code, 200)
            base = first.json['order_no'][:6]
            old_writer_number = f"{base}{int(first.json['order_no'][6:]) + 1:04d}"
            session.add(Order(order_no=old_writer_number, date=datetime.date.today(),
                              business_type='采购入库', operator_id=1))
            session.commit()
            second = self.post('b')
            self.assertEqual(second.status_code, 200, second.get_json())
            self.assertNotEqual(second.json['order_no'], old_writer_number)

        def test_deleted_number_from_legacy_writer_must_not_be_reused(self):
            first = self.post('a')
            self.assertEqual(first.status_code, 200)
            base = first.json['order_no'][:6]
            old_writer_number = f"{base}{int(first.json['order_no'][6:]) + 1:04d}"
            legacy = Order(order_no=old_writer_number, date=datetime.date.today(),
                           business_type='采购入库', operator_id=1)
            session.add(legacy)
            session.commit()
            session.delete(legacy)
            session.commit()
            second = self.post('b')
            self.assertEqual(second.status_code, 200, second.get_json())
            self.assertNotEqual(second.json['order_no'], old_writer_number,
                                '旧入口写入并删除的编号仍不能被复用')

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(FullRoute)
    if suite.countTestCases() != 13:
        raise RuntimeError('full route synthetic cases missing')
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    session.remove()
    engine.dispose()
    raise SystemExit(not result.wasSuccessful())


if __name__ == '__main__':
    main()
