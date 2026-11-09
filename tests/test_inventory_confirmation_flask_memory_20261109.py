"""Offline Flask+SQLite confirmation integration; synthetic shared memory only."""
import ast
import builtins
import datetime
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
import math
from functools import wraps
from pathlib import Path
import platform
import socket
import sqlite3
import subprocess
import sys
import sysconfig
import types
import unittest
import uuid


def main():
    def deny(*_args, **_kwargs):
        raise AssertionError('WMS import, file DB, network and subprocess are forbidden')

    class DeniedPopen:
        def __init__(self, *_args, **_kwargs):
            deny()
    subprocess.Popen = DeniedPopen
    socket.socket.connect = socket.socket.connect_ex = socket.getaddrinfo = deny
    socket.create_connection = deny
    platform.machine = lambda: 'synthetic'
    original_import = builtins.__import__
    fake_app = types.ModuleType('app')
    sys.modules['app'] = fake_app
    def guarded_import(name, *args, **kwargs):
        level = args[3] if len(args) > 3 else kwargs.get('level', 0)
        if level == 0 and (name == 'app' or name.startswith('app.')):
            if name == 'app' and sys.modules.get('app') is fake_app:
                return fake_app
            deny()
        return original_import(name, *args, **kwargs)
    builtins.__import__ = guarded_import
    original_connect = sqlite3.connect
    uri = 'file:wms_synthetic_check_' + uuid.uuid4().hex + '?mode=memory&cache=shared'
    def memory_connect(database, *args, **kwargs):
        if database != uri or kwargs.get('uri') is not True:
            deny()
        return original_connect(database, *args, **kwargs)
    sqlite3.connect = sqlite3.dbapi2.connect = memory_connect
    sys.path.append(sysconfig.get_paths()['purelib'])

    from flask import Flask, abort, flash, g, has_request_context, jsonify, make_response, redirect, request, url_for
    from flask_login import LoginManager, UserMixin, current_user, login_required
    from flask_sqlalchemy import SQLAlchemy
    from flask_wtf import CSRFProtect
    from flask_wtf.csrf import generate_csrf
    from itsdangerous import BadSignature, URLSafeSerializer, URLSafeTimedSerializer
    from pydantic import BaseModel, Field, StrictStr, field_validator
    from sqlalchemy import String, cast, event, inspect
    from sqlalchemy.exc import OperationalError
    from sqlalchemy.orm import selectinload
    from sqlalchemy.pool import NullPool

    app = Flask('synthetic_check_confirmation')
    app.config.update(SECRET_KEY='synthetic-secret-only', TESTING=True,
                      SQLALCHEMY_DATABASE_URI='sqlite://',
                      SQLALCHEMY_ENGINE_OPTIONS={'poolclass': NullPool,
                          'creator': lambda: memory_connect(uri, uri=True, timeout=.01)})
    CSRFProtect(app)
    db = SQLAlchemy(app)
    login = LoginManager(app)

    class User(UserMixin):
        def __init__(self, user_id):
            self.id = user_id
            self.role = {'1': 'warehouse', '2': 'warehouse', '3': 'admin',
                         '4': 'finance', '5': 'sales'}[user_id]
    @login.user_loader
    def user_loader(user_id):
        return User(user_id) if user_id in ('1', '2', '3', '4', '5') else None

    class Warehouse(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        name = db.Column(db.String)
        code = db.Column(db.String)
        status = db.Column(db.String)

    class Material(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        code = db.Column(db.String)
        name = db.Column(db.String)
        unit_id = db.Column(db.Integer)

    class InventoryCheck(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        check_no = db.Column(db.String)
        status = db.Column(db.String)
        warehouse = db.Column(db.String)
        date = db.Column(db.Date)
        frozen_at = db.Column(db.DateTime)
        remark = db.Column(db.String)
        operator_id = db.Column(db.Integer)

    class InventoryCheckItem(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        inventory_check_id = db.Column(db.Integer, db.ForeignKey('inventory_check.id'))
        material_id = db.Column(db.Integer, db.ForeignKey('material.id'))
        system_stock = db.Column(db.Float)
        actual_stock = db.Column(db.Float)
        difference = db.Column(db.Float)
        reason = db.Column(db.String)
        area = db.Column(db.String)
        counted_by = db.Column(db.Integer)
        counted_at = db.Column(db.DateTime)
        material = db.relationship(Material)
        inventory_check = db.relationship(InventoryCheck, backref='items')

    class StockTransaction(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        material_id = db.Column(db.Integer)
        warehouse_id = db.Column(db.Integer)
        quantity = db.Column(db.Float)
        created_at = db.Column(db.DateTime)
        transaction_type = db.Column(db.String)
        reference_type = db.Column(db.String)
        reference_id = db.Column(db.Integer)

    class AdjustmentOrder(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        adjustment_no = db.Column(db.String)
        date = db.Column(db.Date)
        adjustment_type = db.Column(db.String)
        source_type = db.Column(db.String)
        source_id = db.Column(db.Integer)
        status = db.Column(db.String)
        operator_id = db.Column(db.Integer)
        warehouse = db.Column(db.String)
        remark = db.Column(db.String)

    class AdjustmentOrderItem(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        adjustment_order_id = db.Column(db.Integer, db.ForeignKey('adjustment_order.id'))
        material_id = db.Column(db.Integer)
        quantity = db.Column(db.Float)
        unit_id = db.Column(db.Integer)
        location = db.Column(db.String)
        reason = db.Column(db.String)

    fake_app.InventoryCheck = InventoryCheck

    anchor = memory_connect(uri, uri=True, timeout=.01)
    assert anchor.execute('PRAGMA database_list').fetchone()[2] == ''
    root = Path(__file__).resolve().parents[1]
    class StripImports(ast.NodeTransformer):
        def visit_Import(self, node):
            return None
        def visit_ImportFrom(self, node):
            return None

    def function(path, name):
        tree = ast.parse((root / path).read_text(encoding='utf-8-sig'))
        matches = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name]
        if len(matches) != 1:
            raise AssertionError('function missing or ambiguous: ' + name)
        node = matches[0]
        node.decorator_list = []
        return StripImports().visit(node)

    input_tree = ast.parse((root / 'app/request_input.py').read_text(encoding='utf-8-sig'))
    input_nodes = [n for n in input_tree.body if isinstance(n, ast.ClassDef) and n.name == 'CheckCompleteInput']
    assert len(input_nodes) == 1
    funcs = [('app/utils.py', 'round_to_2_decimals'), ('app/utils.py', 'normalize_stock_quantity'),
             ('app/app.py', '_acquire_order_write_lock'), ('app/app.py', '_create_adjustment_drafts_from_check'),
             ('app/routes/check.py', '_resolve_check_warehouse'), ('app/routes/check.py', '_check_uncounted_alerts'),
             ('app/routes/check.py', '_check_complete_snapshot'), ('app/routes/check.py', '_issue_check_confirmation'),
             ('app/routes/check.py', '_accept_check_confirmation'), ('app/request_input.py', 'json_object_body'),
             ('app/routes/check.py', 'complete_check')]
    settings = {'location': False, 'inspect_lock': False, 'locked_out': False}
    env = {'app': app, 'db': db, 'g': g, 'has_request_context': has_request_context,
           'request': request, 'current_user': current_user, 'current_app': app, 'jsonify': jsonify,
           'BaseModel': BaseModel, 'Field': Field, 'StrictStr': StrictStr, 'field_validator': field_validator,
           'Warehouse': Warehouse, 'Material': Material, 'InventoryCheck': InventoryCheck,
           'InventoryCheckItem': InventoryCheckItem, 'StockTransaction': StockTransaction,
           'AdjustmentOrder': AdjustmentOrder, 'AdjustmentOrderItem': AdjustmentOrderItem,
           'selectinload': selectinload, 'cast': cast, 'String': String,
           'datetime': datetime.datetime, 'date': datetime.date, 'Decimal': Decimal,
           'ROUND_HALF_UP': ROUND_HALF_UP, 'math': math, 'hashlib': hashlib, 'json': json,
           'URLSafeTimedSerializer': URLSafeTimedSerializer, 'BadSignature': BadSignature,
           'STOCK_COMPARE_EPSILON': 1e-6, 'location_management_enabled': lambda: settings['location'],
           'assert_warehouse_active': lambda *_args, **_kwargs: (True, ''),
           'generate_order_no': lambda *_args: 'ADJ-SYNTHETIC',
           'api_error': lambda msg: jsonify(status='error', msg=msg), 'log_operation': lambda *_args: None}
    nodes = [input_nodes[0], *[function(path, name) for path, name in funcs]]
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), '<synthetic-real-sources>', 'exec'), env)
    guard_tree = ast.parse((root / 'app/services/document_edit_guard.py').read_text(encoding='utf-8-sig'))
    guard_nodes = [node for node in guard_tree.body if isinstance(node, (ast.Assign, ast.FunctionDef))]
    env.update(abort=abort, make_response=make_response, URLSafeSerializer=URLSafeSerializer,
               event=event, inspect=inspect, OperationalError=OperationalError)
    exec(compile(ast.fix_missing_locations(ast.Module(body=guard_nodes, type_ignores=[])),
                 '<synthetic-real-document-guard>', 'exec'), env)
    guard_module = types.ModuleType('services.document_edit_guard')
    guard_module.guarded_document_write = env['guarded_document_write']
    guard_module.EDIT_ENDPOINTS = env['EDIT_ENDPOINTS']
    services_module = types.ModuleType('services')
    services_module.document_edit_guard = guard_module
    sys.modules['services'] = services_module
    sys.modules['services.document_edit_guard'] = guard_module
    input_module = types.ModuleType('request_input')
    input_nodes = [node for node in input_tree.body if isinstance(node, ast.Assign)
                   and any(isinstance(target, ast.Name) and target.id == 'STOCK_DOCUMENT_JSON_ENDPOINTS'
                           for target in node.targets)]
    input_nodes.append(next(node for node in input_tree.body if isinstance(node, ast.FunctionDef)
                            and node.name == 'validate_document_json_input'))
    exec(compile(ast.fix_missing_locations(ast.Module(body=input_nodes, type_ignores=[])),
                 '<synthetic-real-input-guard>', 'exec'), env)
    input_module.validate_document_json_input = env['validate_document_json_input']
    sys.modules['request_input'] = input_module
    utils_tree = ast.parse((root / 'app/utils.py').read_text(encoding='utf-8-sig'))
    role_constants = {'READ_ONLY_ROLES', 'READ_ONLY_ALLOWED_POST_ENDPOINTS', 'READ_ONLY_DENIED_PREFIXES',
                      'READ_ONLY_DENY_MSG', 'READ_ONLY_ALWAYS_ALLOWED_ENDPOINTS'}
    role_nodes = [node for node in utils_tree.body if isinstance(node, ast.Assign)
                  and any(isinstance(target, ast.Name) and target.id in role_constants for target in node.targets)]
    role_nodes += [node for node in utils_tree.body if isinstance(node, ast.FunctionDef)
                   and node.name in {'is_read_only_role', 'read_only_path_denied', 'require_role'}]
    env.update(wraps=wraps, flash=flash, redirect=redirect, url_for=url_for)
    exec(compile(ast.fix_missing_locations(ast.Module(body=role_nodes, type_ignores=[])),
                 '<synthetic-real-role-guard>', 'exec'), env)
    hook_nodes = [function('app/app.py', 'wants_json_error_response'),
                  function('app/app.py', 'enforce_read_only_role')]
    exec(compile(ast.fix_missing_locations(ast.Module(body=hook_nodes, type_ignores=[])),
                 '<synthetic-real-read-only-hook>', 'exec'), env)
    app.before_request(env['enforce_read_only_role'])
    actual_snapshot = env['_check_complete_snapshot']
    def checked_snapshot(*args):
        if settings['inspect_lock']:
            rival = memory_connect(uri, uri=True, timeout=.01)
            try:
                try:
                    rival.execute("INSERT INTO stock_transaction (material_id,warehouse_id,quantity,created_at) VALUES (1,1,4,'2020-01-01 10:02:00')")
                    rival.commit()
                except sqlite3.OperationalError as exc:
                    assert 'locked' in str(exc).lower()
                    settings['locked_out'] = True
                else:
                    raise AssertionError('rival write succeeded while completion held the lock')
            finally:
                rival.close()
        return actual_snapshot(*args)
    env['_check_complete_snapshot'] = checked_snapshot
    app.add_url_rule('/synthetic/check/<int:id>/complete', 'synthetic_complete_check',
                     login_required(env['complete_check']), methods=['POST'])
    app.add_url_rule('/check/<int:id>/complete', 'complete_check',
                     env['require_role']('warehouse')(login_required(env['complete_check'])),
                     methods=['POST'])
    @app.get('/check/<int:id>/revision')
    @login_required
    def synthetic_revision(id):
        return jsonify(token=env['_sign']('check', db.session.get(InventoryCheck, id)))
    @app.get('/synthetic/csrf')
    def synthetic_csrf():
        return jsonify(token=generate_csrf())

    with app.app_context():
        db.create_all()
        db.session.add_all([Warehouse(id=1, name='合成仓', code='SYN', status='active'),
                            Material(id=1, code='SYN-M', name='合成物料', unit_id=1),
                            InventoryCheck(id=1, check_no='CK-SYN', status='pending', warehouse='合成仓',
                                           date=datetime.date(2020, 1, 1), frozen_at=datetime.datetime(2020, 1, 1, 10),
                                           operator_id=1),
                            InventoryCheckItem(id=1, inventory_check_id=1, material_id=1, system_stock=2,
                                               actual_stock=3, difference=1, area='', reason='合成',
                                               counted_by=None, counted_at=None),
                            InventoryCheck(id=2, check_no='CK-SYN-2', status='pending', warehouse='合成仓',
                                           date=datetime.date(2020, 1, 1), frozen_at=datetime.datetime(2020, 1, 1, 10),
                                           operator_id=1),
                            InventoryCheckItem(id=2, inventory_check_id=2, material_id=1, system_stock=2,
                                               actual_stock=3, difference=1, area='', reason='合成',
                                               counted_by=None, counted_at=None)])
        db.session.commit()
        assert db.session.connection().exec_driver_sql('PRAGMA database_list').fetchone()[2] == ''
        db.session.rollback()

    class Integration(unittest.TestCase):
        def test_confirmation_and_real_lock_transaction(self):
            client = app.test_client()
            path = '/synthetic/check/1/complete'
            anonymous_token = client.get('/synthetic/csrf').get_json()['token']
            self.assertEqual(client.post(path, json={}, headers={'X-CSRFToken': anonymous_token}).status_code, 401)
            with client.session_transaction() as session:
                session['_user_id'], session['_fresh'] = '1', True
            self.assertEqual(client.post(path, json={}).status_code, 400)
            token = client.get('/synthetic/csrf').get_json()['token']
            settings['inspect_lock'] = True
            first = client.post(path, json={}, headers={'X-CSRFToken': token})
            self.assertEqual(first.status_code, 200)
            self.assertEqual(first.get_json()['status'], 'confirm')
            self.assertTrue(settings['locked_out'])
            original_token = first.get_json()['confirmation_token']
            settings['inspect_lock'] = False
            legacy = client.post(path, json={'force': True}, headers={'X-CSRFToken': token}).get_json()
            self.assertEqual(legacy['status'], 'confirm')
            other = app.test_client()
            with other.session_transaction() as session:
                session['_user_id'], session['_fresh'] = '2', True
            other_csrf = other.get('/synthetic/csrf').get_json()['token']
            cross_user = other.post(path, json={'force': True, 'confirmation_token': original_token},
                                    headers={'X-CSRFToken': other_csrf}).get_json()
            self.assertEqual(cross_user['status'], 'confirm')
            rival = memory_connect(uri, uri=True, timeout=.1)
            try:
                rival.execute("INSERT INTO stock_transaction (material_id,warehouse_id,quantity,created_at,transaction_type,reference_type,reference_id) VALUES (1,1,4,'2020-01-01 10:02:00','in','in_order',1)")
                rival.commit()
            finally:
                rival.close()
            changed = client.post(path, json={'force': True, 'confirmation_token': original_token},
                                  headers={'X-CSRFToken': token}).get_json()
            self.assertEqual(changed['status'], 'confirm')
            self.assertIn('流水', changed['msg'])
            self.assertNotEqual(changed['confirmation_token'], original_token)
            done = client.post(path, json={'force': True, 'confirmation_token': changed['confirmation_token']},
                               headers={'X-CSRFToken': token}).get_json()
            self.assertEqual(done['status'], 'success')
            repeated = client.post(path, json={'force': True, 'confirmation_token': changed['confirmation_token']},
                                   headers={'X-CSRFToken': token}).get_json()
            self.assertEqual(repeated['status'], 'error')
            with app.app_context():
                self.assertEqual(db.session.get(InventoryCheck, 1).status, 'completed')
                drafts = AdjustmentOrder.query.all()
                self.assertEqual(len(drafts), 1)
                self.assertEqual(drafts[0].status, 'pending')
                self.assertEqual(AdjustmentOrderItem.query.count(), 1)

        def test_document_guard_revision_lock_and_confirmation(self):
            client = app.test_client()
            anon_csrf = client.get('/synthetic/csrf').get_json()['token']
            self.assertEqual(client.post('/check/2/complete', json={}, headers={'X-CSRFToken': anon_csrf, 'X-Requested-With': 'XMLHttpRequest'}).status_code, 401)
            with client.session_transaction() as session:
                session['_user_id'], session['_fresh'] = '1', True
            self.assertEqual(client.post('/check/2/complete', json={}).status_code, 400)
            csrf = client.get('/synthetic/csrf').get_json()['token']
            revision = client.get('/check/2/revision').get_json()['token']
            path = '/check/2/complete'
            headers = {'X-CSRFToken': csrf, 'X-WMS-Document-Revision': revision}
            self.assertEqual(client.post(path, json={}, headers={**headers, 'X-WMS-Document-Revision': revision + 'x'}).status_code, 409)
            for user_id, expected in (('3', 200), ('4', 403), ('5', 403)):
                other_role = app.test_client()
                with other_role.session_transaction() as session:
                    session['_user_id'], session['_fresh'] = user_id, True
                role_csrf = other_role.get('/synthetic/csrf').get_json()['token']
                role_revision = other_role.get('/check/2/revision').get_json()['token']
                response = other_role.post(path, json={}, headers={'X-CSRFToken': role_csrf,
                                           'X-Requested-With': 'XMLHttpRequest',
                                           'X-WMS-Document-Revision': role_revision})
                self.assertEqual(response.status_code, expected, user_id)
                if user_id == '3':
                    self.assertEqual(response.get_json()['status'], 'confirm')
            other = app.test_client()
            with other.session_transaction() as session:
                session['_user_id'], session['_fresh'] = '2', True
            other_csrf = other.get('/synthetic/csrf').get_json()['token']
            self.assertEqual(other.post(path, json={}, headers={'X-CSRFToken': other_csrf,
                             'X-WMS-Document-Revision': revision}).status_code, 409)
            rival = memory_connect(uri, uri=True, timeout=.1)
            rival.execute("UPDATE inventory_check_item SET reason='synthetic change' WHERE id=2")
            rival.commit()
            rival.close()
            stale = client.post(path, json={}, headers=headers)
            self.assertEqual(stale.status_code, 409)
            self.assertEqual(stale.get_json()['code'], 'DOCUMENT_EDIT_CONFLICT')
            headers['X-WMS-Document-Revision'] = client.get('/check/2/revision').get_json()['token']
            settings['inspect_lock'] = True
            settings['locked_out'] = False
            first = client.post(path, json={}, headers=headers)
            self.assertEqual(first.get_json()['status'], 'confirm')
            self.assertTrue(settings['locked_out'])
            settings['inspect_lock'] = False
            old_confirmation = first.get_json()['confirmation_token']
            rival = memory_connect(uri, uri=True, timeout=.1)
            rival.execute("INSERT INTO stock_transaction (material_id,warehouse_id,quantity,created_at,transaction_type,reference_type,reference_id) VALUES (1,1,5,'2020-01-01 10:03:00','in','in_order',2)")
            rival.commit()
            rival.close()
            changed = client.post(path, json={'force': True, 'confirmation_token': old_confirmation}, headers=headers)
            self.assertEqual(changed.get_json()['status'], 'confirm')
            confirmed = client.post(path, json={'force': True, 'confirmation_token': changed.get_json()['confirmation_token']}, headers=headers)
            self.assertEqual(confirmed.get_json()['status'], 'success')
            self.assertTrue(confirmed.headers.get('X-WMS-Document-Revision'))
            self.assertEqual(client.post(path, json={'force': True, 'confirmation_token': changed.get_json()['confirmation_token']}, headers=headers).status_code, 409)
            headers['X-WMS-Document-Revision'] = confirmed.headers['X-WMS-Document-Revision']
            self.assertEqual(client.post(path, json={'force': True, 'confirmation_token': changed.get_json()['confirmation_token']}, headers=headers).get_json()['status'], 'error')
            with app.app_context():
                self.assertEqual(db.session.get(InventoryCheck, 2).status, 'completed')
                self.assertEqual(AdjustmentOrder.query.filter_by(source_id=2).count(), 1)

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Integration)
    if suite.countTestCases() != 2:
        raise RuntimeError('synthetic test list incomplete')
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    with app.app_context():
        db.session.remove()
        db.engine.dispose()
    anchor.close()
    raise SystemExit(not result.wasSuccessful())


def test_inventory_confirmation_synthetic_process():
    import os
    env = {key: os.environ[key] for key in ('SYSTEMROOT', 'WINDIR') if key in os.environ}
    result = subprocess.run([sys.executable, '-I', '-S', '-B', '-X', 'utf8', __file__],
                            env=env, capture_output=True, text=True, encoding='utf-8', timeout=45)
    assert result.returncode == 0, result.stderr


if __name__ == '__main__':
    main()
