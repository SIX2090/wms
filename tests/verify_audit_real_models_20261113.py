"""Source-extracted WMS models on new memory databases; this is not app integration.

Explicit execution: python -I -S -B -X utf8 this_file.py. The worker refuses
application imports, SQLite files, networking and subprocess creation before it
loads dependencies. Model class bodies and tested functions come from source;
application hooks, model-module listeners and route decorators are not executed.
"""
import os
import subprocess
import sys


def main():
    import ast
    import builtins
    from datetime import date, datetime, timedelta
    from decimal import Decimal, ROUND_HALF_UP, localcontext
    import hashlib
    import json
    import math
    from pathlib import Path
    import platform
    import socket
    import sqlite3
    import sysconfig
    import types
    import unittest
    from unittest.mock import patch

    def deny(*_args, **_kwargs):
        raise AssertionError('Application imports, file databases, network and children forbidden')

    memory_connect = sqlite3.connect
    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        level = args[3] if len(args) > 3 else kwargs.get('level', 0)
        if level == 0 and (name == 'app' or name.startswith('app.')):
            deny()
        return original_import(name, *args, **kwargs)

    sqlite3.connect = sqlite3.dbapi2.connect = deny
    socket.socket.connect = socket.socket.connect_ex = deny
    socket.create_connection = socket.getaddrinfo = deny
    subprocess.Popen = deny
    builtins.__import__ = guarded_import
    platform.machine = lambda: 'synthetic'
    sys.path.append(sysconfig.get_paths()['purelib'])  # No site or .pth execution.
    from flask import Flask, current_app, jsonify
    from flask_login import UserMixin
    from flask_sqlalchemy import SQLAlchemy
    from itsdangerous import BadSignature, URLSafeTimedSerializer
    from sqlalchemy import String, cast, event, func, text, update

    root = Path(__file__).resolve().parents[1]
    app = Flask('source-model-audit')
    app.config.update(SECRET_KEY='synthetic-source-model-secret', SQLALCHEMY_DATABASE_URI='sqlite://',
                      SQLALCHEMY_ENGINE_OPTIONS={'creator': lambda: memory_connect(':memory:')})
    db = SQLAlchemy(app)
    ns = dict(db=db, datetime=datetime, timedelta=timedelta, date=date, UserMixin=UserMixin,
              Decimal=Decimal, ROUND_HALF_UP=ROUND_HALF_UP, localcontext=localcontext,
              hashlib=hashlib, json=json, math=math, func=func, cast=cast, String=String,
              current_app=current_app, URLSafeTimedSerializer=URLSafeTimedSerializer,
              BadSignature=BadSignature, app=app, jsonify=jsonify, sa_update=update,
              STOCK_COMPARE_EPSILON=1e-6,
              current_user=types.SimpleNamespace(is_authenticated=True, id=1),
              request=types.SimpleNamespace(remote_addr='synthetic', headers={}),
              get_request_ip=lambda: 'synthetic', api_error=lambda message: ({'status': 'error', 'msg': message}, 400))
    for filename in ('core.py', 'master_data.py', 'documents.py', 'inventory.py'):
        tree = ast.parse((root / 'app/models' / filename).read_text(encoding='utf-8-sig'))
        nodes = [node for node in tree.body if isinstance(node, ast.ClassDef)]
        exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])),
                     'source-model:' + filename, 'exec'), ns)

    trees = {}

    def extract(filename, name):
        if filename not in trees:
            trees[filename] = ast.parse((root / filename).read_text(encoding='utf-8-sig'))
        matches = [node for node in ast.walk(trees[filename])
                   if isinstance(node, ast.FunctionDef) and node.name == name]
        if len(matches) != 1:
            raise AssertionError('Source function must exist exactly once: ' + name)
        node = matches[0]
        node.decorator_list = []
        # Bind only existing dependencies above. Never import the application.
        for child in ast.walk(node):
            if hasattr(child, 'body') and isinstance(child.body, list):
                child.body = [part for part in child.body if not isinstance(part, ast.ImportFrom)
                              or part.module not in ('app', 'db', 'models.master_data', 'services.warehouse_stock_service')]
        exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
                     'source-function:' + filename + ':' + name, 'exec'), ns)

    for name in ('round_to_2_decimals', 'round_money_product', 'normalize_stock_quantity', 'recalculate_order_total'):
        extract('app/utils.py', name)
    extract('app/services/warehouse_identity.py', 'warehouse_aliases')
    for name in ('_recorded_quantity_matches', '_reverse_recorded_opening_stock'):
        extract('app/services/warehouse_stock_service.py', name)
    ns['allow_negative_location_stock'] = lambda: False
    for name in ('update_purchase_order_status', 'log_operation', '_ledger_source_warehouse_getters',
                 '_ledger_source_warehouse_map', '_filter_txn_list_by_warehouse_scope',
                 '_warehouse_location_filter_values', 'get_warehouse_stock_quantities',
                 '_opening_stock_negative_hint', '_opening_stock_line_transaction_ids',
                 '_reverse_opening_stock_line', '_apply_scan_to_batch'):
        extract('app/app.py', name)
    for name in ('delete_in_order_item', 'in_order_item_delete_alias'):
        extract('app/routes/in_order.py', name)
    for name in ('_check_uncounted_alerts', '_check_complete_snapshot',
                 '_issue_check_confirmation', '_accept_check_confirmation'):
        extract('app/routes/check.py', name)

    class RealModelBoundaries(unittest.TestCase):
        def setUp(self):
            self.ctx = app.app_context()
            self.ctx.push()
            db.session.remove()
            db.drop_all()
            db.create_all()
            self.assertTrue(all(not row[2] for row in db.session.execute(text('PRAGMA database_list'))))
            ns['location_management_enabled'] = lambda: False
            self.user = ns['User'](id=1, username='synthetic', password_hash='non-login-test-value')
            self.a = ns['Warehouse'](code='SYN-A', name='合成甲仓', status='active')
            self.b = ns['Warehouse'](code='SYN-B', name='合成乙仓', status='active')
            self.material = ns['Material'](code='SYN-M', name='合成物料', stock=0)
            self.customer = ns['Customer'](code='SYN-CUSTOMER', name='合成客户')
            db.session.add_all([self.user, self.a, self.b, self.material, self.customer])
            db.session.commit()

        def tearDown(self):
            db.session.remove()
            self.ctx.pop()

        def txn(self, warehouse_id, qty, reference_type=None, reference_id=None):
            row = ns['StockTransaction'](material_id=self.material.id, warehouse_id=warehouse_id,
                quantity=qty, transaction_type='in' if qty >= 0 else 'out',
                reference_type=reference_type, reference_id=reference_id, location='',
                created_at=datetime.now())
            db.session.add(row)
            db.session.flush()
            return row

        def make_source(self, kind, warehouse):
            cls = ns['_ledger_source_warehouse_getters']()[kind][0]
            names = dict(in_order='order_no', out_order='order_no', after_sale_out_order='order_no',
                requisition='req_no', sales='order_no', adjustment='adjustment_no', check='check_no',
                subcontract='order_no')
            if kind == 'opening_stock':
                row = cls(material_id=self.material.id, warehouse_id=warehouse.id, quantity=0)
            elif kind == 'transfer':
                row = cls(transfer_no='SYN-T', from_warehouse=self.a.name, to_warehouse=self.b.name,
                          from_location=self.a.name, to_location=self.b.name)
            else:
                row = cls(**{names[kind]: 'SYN-' + kind + '-' + warehouse.code, 'warehouse': warehouse.name})
                if kind == 'sales':
                    row.customer_id = self.customer.id
                elif kind == 'adjustment':
                    row.adjustment_type = 'loss'
            db.session.add(row)
            db.session.flush()
            return row

        def test_all_ten_historical_source_models_resolve_without_cross_warehouse_leak(self):
            kinds = ns['_ledger_source_warehouse_getters']()
            self.assertEqual(set(kinds), {'in_order', 'out_order', 'after_sale_out_order', 'requisition',
                'sales', 'adjustment', 'check', 'subcontract', 'opening_stock', 'transfer'})
            for kind in kinds:
                with self.subTest(kind=kind):
                    if kind == 'transfer':
                        src = self.make_source(kind, self.a)
                        outgoing = self.txn(None, -3, kind, src.id)
                        incoming = self.txn(None, 3, kind, src.id)
                        self.assertEqual(ns['_ledger_source_warehouse_map']([outgoing, incoming]),
                                         {outgoing.id: self.a.name, incoming.id: self.b.name})
                    else:
                        a_doc = self.make_source(kind, self.a)
                        b_doc = self.make_source(kind, self.b)
                        a_txn = self.txn(None, -3, kind, a_doc.id)
                        b_txn = self.txn(None, 7, kind, b_doc.id)
                        self.assertEqual(ns['_ledger_source_warehouse_map']([a_txn, b_txn]),
                                         {a_txn.id: self.a.name, b_txn.id: self.b.name})
            db.session.commit()
            a = ns['get_warehouse_stock_quantities'](self.a)
            b = ns['get_warehouse_stock_quantities'](self.b)
            self.assertEqual(a[self.material.id], -30)
            self.assertEqual(b[self.material.id], 66)

        def test_warning_uses_each_warehouse_balance_with_real_source_models(self):
            a_doc = self.make_source('out_order', self.a)
            b_doc = self.make_source('in_order', self.b)
            self.txn(None, -3, 'out_order', a_doc.id)
            self.txn(None, 7, 'in_order', b_doc.id)
            self.material.stock = 4
            line = ns['OpeningStock'](material_id=self.material.id, warehouse_id=self.a.id, quantity=0)
            db.session.add(line)
            db.session.commit()
            hints = ns['_opening_stock_negative_hint']([line])
            self.assertEqual(len(hints), 1)
            self.assertIn('合成甲仓', hints[0])
            self.assertIn('-3', hints[0])
            self.assertNotIn('合成乙仓', hints[0])

        def test_unknown_history_stays_unassigned(self):
            self.txn(None, -3, 'unknown-synthetic-source', 99)
            self.txn(None, 4)
            line = ns['OpeningStock'](material_id=self.material.id, quantity=0)
            db.session.add(line)
            db.session.commit()
            self.assertEqual(ns['get_warehouse_stock_quantities'](self.a), {})
            self.assertEqual(ns['get_warehouse_stock_quantities'](self.b), {})
            hints = ns['_opening_stock_negative_hint']([line])
            self.assertEqual(len(hints), 1)
            self.assertIn('仓库归属未知', hints[0])

        def test_actual_sqlite_query_error_savepoint_keeps_reversal_and_session_usable(self):
            line = ns['OpeningStock'](material_id=self.material.id, warehouse_id=self.a.id, quantity=10)
            self.material.stock = 10
            db.session.add(line)
            db.session.flush()
            self.txn(self.a.id, 10, 'opening_stock', line.id)
            db.session.commit()
            self.assertEqual(ns['_reverse_opening_stock_line'](line), (True, ''))
            def failing_query(_warehouse):
                return db.session.execute(text('SELECT * FROM synthetic_missing_table')).all()
            with patch.dict(ns, get_warehouse_stock_quantities=failing_query):
                hints = ns['_opening_stock_negative_hint']([line])
                self.assertEqual(len(hints), 1)
                self.assertIn('暂时无法核验', hints[0])
            db.session.delete(line)
            db.session.commit()
            self.assertEqual(db.session.get(ns['Material'], self.material.id).stock, 0)
            self.assertEqual(ns['StockTransaction'].query.count(), 0)
            self.assertEqual(ns['OpeningStock'].query.count(), 0)
            self.assertEqual(db.session.execute(text('SELECT 19')).scalar(), 19)

        def seed_inbound(self):
            purchase = ns['PurchaseOrder'](order_no='SYN-P')
            order = ns['InOrder'](order_no='SYN-I', warehouse=self.a.name, status='pending', total_amount=17)
            db.session.add_all([purchase, order])
            db.session.flush()
            source = ns['PurchaseOrderItem'](purchase_order_id=purchase.id, material_id=self.material.id,
                quantity=10, received_quantity=7.25, price=2, amount=20)
            db.session.add(source)
            db.session.flush()
            item = ns['InOrderItem'](in_order_id=order.id, material_id=self.material.id,
                source_purchase_order_item_id=source.id, quantity=3.2, price=3.75, amount=12)
            other = ns['InOrderItem'](in_order_id=order.id, material_id=self.material.id, quantity=1, price=5, amount=5)
            db.session.add_all([item, other])
            db.session.commit()
            return order.id, item.id, source.id

        def test_real_model_business_commit_failure_does_not_leave_success_log(self):
            order_id, item_id, source_id = self.seed_inbound()
            session = db.session()
            observed = []
            def note_deleted_row(_session, _flush_context):
                if any(isinstance(row, ns['InOrderItem']) and row.id == item_id
                       for row in session.deleted):
                    session.info['synthetic_deleted_target'] = True
            def fail_commit(_session):
                if session.info.pop('synthetic_deleted_target', False):
                    observed.append(item_id)
                    raise RuntimeError('synthetic business commit failure after target DELETE')
            event.listen(session, 'after_flush', note_deleted_row)
            event.listen(session, 'before_commit', fail_commit)
            try:
                response = ns['delete_in_order_item'](order_id, item_id)
            finally:
                event.remove(session, 'after_flush', note_deleted_row)
                event.remove(session, 'before_commit', fail_commit)
                session.info.pop('synthetic_deleted_target', None)
            self.assertEqual(observed, [item_id], 'Fault must reach the real target DELETE transaction')
            status = response[1] if isinstance(response, tuple) else response.status_code
            self.assertEqual(status, 500)
            self.assertIsNotNone(db.session.get(ns['InOrderItem'], item_id))
            self.assertEqual(db.session.get(ns['PurchaseOrderItem'], source_id).received_quantity, 7.25)
            self.assertEqual(ns['OperationLog'].query.count(), 0)
            self.assertEqual(db.session.get(ns['InOrder'], order_id).total_amount, 17)

        def test_real_log_insert_failure_does_not_undo_delete_or_decimal_source(self):
            order_id, item_id, source_id = self.seed_inbound()
            def reject_log(_mapper, _connection, _target):
                raise RuntimeError('synthetic log insert failure')
            event.listen(ns['OperationLog'], 'before_insert', reject_log)
            try:
                result = ns['delete_in_order_item'](order_id, item_id)
            finally:
                event.remove(ns['OperationLog'], 'before_insert', reject_log)
            self.assertEqual(result.get_json()['status'], 'success')
            self.assertIsNone(db.session.get(ns['InOrderItem'], item_id))
            self.assertEqual(db.session.get(ns['PurchaseOrderItem'], source_id).received_quantity, 4.05)
            self.assertEqual(db.session.get(ns['InOrder'], order_id).total_amount, 5)
            self.assertEqual(ns['OperationLog'].query.count(), 0)

        def test_alias_logs_only_successful_committed_deletion(self):
            order_id, item_id, _ = self.seed_inbound()
            result = ns['in_order_item_delete_alias'](order_id, item_id)
            self.assertEqual(result.get_json()['status'], 'success')
            log = ns['OperationLog'].query.one()
            self.assertEqual((log.target_type, log.target_id), ('in_order', order_id))
            self.assertIn('删除入库单明细', log.operation_content)

        def test_mobile_model_update_invalidates_reviewed_check_snapshot(self):
            check = ns['InventoryCheck'](check_no='SYN-C', warehouse=self.a.name, status='pending',
                                        frozen_at=datetime.now() - timedelta(hours=1))
            db.session.add(check)
            db.session.flush()
            row = ns['InventoryCheckItem'](inventory_check_id=check.id, material_id=self.material.id,
                system_stock=10, actual_stock=10, difference=0)
            db.session.add(row)
            db.session.commit()
            fingerprint, risks = ns['_check_complete_snapshot'](check, self.a.id)
            token = ns['_issue_check_confirmation'](check.id, '1', fingerprint)
            self.assertEqual(risks['uncounted'], 1)
            scan = ns['InventoryCheckScan'](check_no='SYN-CS', warehouse=self.a.name, check_id=check.id)
            db.session.add(scan)
            db.session.flush()
            db.session.add(ns['InventoryCheckScanItem'](check_scan_id=scan.id, material_id=self.material.id,
                system_stock=10, actual_stock=8, difference=-2))
            db.session.flush()
            self.assertIsNone(ns['_apply_scan_to_batch'](check, scan, {self.material.id: 10}, operator_id=1))
            db.session.commit()
            db.session.expire_all()
            changed, risks = ns['_check_complete_snapshot'](check, self.a.id)
            self.assertNotEqual(changed, fingerprint)
            self.assertFalse(ns['_accept_check_confirmation'](token, check.id, '1', changed))
            self.assertEqual(risks['uncounted'], 0)
            self.assertEqual(db.session.get(ns['InventoryCheckItem'], row.id).difference, -2)
            self.assertEqual(ns['StockTransaction'].query.count(), 0)
            self.assertEqual(ns['AdjustmentOrder'].query.count(), 0)

        def test_net_zero_movements_and_partial_count_risks_remain_combined(self):
            check = ns['InventoryCheck'](check_no='SYN-C', warehouse=self.a.name,
                                        frozen_at=datetime.now() - timedelta(hours=1))
            db.session.add(check)
            db.session.flush()
            db.session.add(ns['InventoryCheckItem'](inventory_check_id=check.id, material_id=self.material.id,
                system_stock=10, actual_stock=10, difference=0, counted_by=1))
            missing = ns['Material'](code='SYN-MISSING', name='合成未盘物料', stock=0)
            db.session.add(missing)
            db.session.flush()
            db.session.add(ns['InventoryCheckItem'](inventory_check_id=check.id, material_id=missing.id,
                system_stock=5, actual_stock=5, difference=0))
            self.txn(self.a.id, 3)
            self.txn(self.a.id, -3)
            self.txn(self.b.id, 9)
            db.session.commit()
            _, risks = ns['_check_complete_snapshot'](check, self.a.id)
            self.assertEqual((risks['uncounted'], risks['incomplete_count'], risks['movement_count']), (1, 1, 1))
            self.assertEqual(risks['movement_samples'][0]['net'], 0)
            self.assertEqual(risks['unknown_warehouse_count'], 0)

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(RealModelBoundaries)
    if suite.countTestCases() != 9:
        raise AssertionError('Explicit synthetic model test list changed or became empty')
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())


def test_source_models_in_explicit_child():
    env = {key: os.environ[key] for key in ('SYSTEMROOT', 'WINDIR') if key in os.environ}
    result = subprocess.run([sys.executable, '-I', '-S', '-B', '-X', 'utf8', __file__],
                            env=env, capture_output=True, text=True, encoding='utf-8', timeout=90)
    assert result.returncode == 0, result.stdout + result.stderr


if __name__ == '__main__':
    main()
