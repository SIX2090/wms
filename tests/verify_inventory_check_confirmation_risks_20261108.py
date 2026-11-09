"""离线盘点回归，运行: python -I -S -B -X utf8 本文件。当前版本预期失败。"""
import ast
import builtins
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import socket
import sqlite3
import subprocess
import sys
import sysconfig
import types
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def main():
    def deny(*_args, **_kwargs):
        raise AssertionError('禁止应用导入、网络、文件数据库和子进程')

    class DeniedPopen:
        def __init__(self, *_args, **_kwargs):
            deny()

    # -S 禁止加载 site/.pth；添加依赖目录不会执行其中的 .pth。
    memory_connect = sqlite3.connect
    sqlite3.connect = deny
    sqlite3.dbapi2.connect = deny
    socket.socket.connect = deny
    socket.socket.connect_ex = deny
    socket.getaddrinfo = deny
    subprocess.Popen = DeniedPopen
    platform.machine = lambda: 'x86_64'  # 避免 Windows 平台探测调用子进程。
    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == 'app' or name.startswith('app.'):
            deny()
        return original_import(name, *args, **kwargs)

    builtins.__import__ = guarded_import
    sys.path.append(sysconfig.get_paths()['purelib'])
    from sqlalchemy import DateTime, Float, Integer, String, cast, create_engine, func, or_, text
    from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
    from itsdangerous import BadSignature, URLSafeTimedSerializer

    class Base(DeclarativeBase):
        pass

    class Txn(Base):
        __tablename__ = 'synthetic_stock_transaction'
        id: Mapped[int] = mapped_column(Integer, primary_key=True)
        material_id: Mapped[int] = mapped_column(Integer)
        transaction_type: Mapped[str | None] = mapped_column(String, nullable=True)
        warehouse_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
        quantity: Mapped[float] = mapped_column(Float)
        created_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
        reference_type: Mapped[str | None] = mapped_column(String)
        reference_id: Mapped[int | None] = mapped_column(Integer)

    class SyntheticWarehouse(Base):
        __tablename__ = 'synthetic_warehouse'
        id: Mapped[int] = mapped_column(Integer, primary_key=True)
        name: Mapped[str] = mapped_column(String, unique=True)
        code: Mapped[str] = mapped_column(String, unique=True)

    class RemoveImports(ast.NodeTransformer):
        def visit_Import(self, node):
            return None

        def visit_ImportFrom(self, node):
            return None

    def source_function(name):
        tree = ast.parse((ROOT / 'app/routes/check.py').read_text(encoding='utf-8-sig'))
        node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)
        node.decorator_list = []
        return RemoveImports().visit(node)

    def load_functions(env, *names):
        if '_check_period_movement_alerts' in names and '_resolve_check_warehouse' not in names:
            names = ('_resolve_check_warehouse', *names)
        module = ast.fix_missing_locations(ast.Module(body=[source_function(n) for n in names], type_ignores=[]))
        exec(compile(module, '<synthetic-check-source>', 'exec'), env)

    class Loader:
        def joinedload(self, *_args):
            return self

    class Lookup:
        def __init__(self, check):
            self.check = check

        def options(self, *_args):
            return self

        def get_or_404(self, _id):
            return self.check

    class WarehouseLookup:
        def __init__(self, wh):
            self.rows = wh if isinstance(wh, list) else ([] if wh is None else [wh])

        def filter_by(self, **kwargs):
            return WarehouseLookup([row for row in self.rows if all(
                not hasattr(row, key) or getattr(row, key) == value for key, value in kwargs.items())])

        def first(self):
            return self.rows[0] if self.rows else None

        def all(self):
            return self.rows

    class SessionStub:
        def __init__(self):
            self.commits = 0

        def commit(self):
            self.commits += 1

        def rollback(self):
            pass

        def get_bind(self):
            return types.SimpleNamespace(dialect=types.SimpleNamespace(name='sqlite'))

    class Input:
        @staticmethod
        def model_validate(body):
            return types.SimpleNamespace(force=body['force'], confirmation_token=body.get('confirmation_token'))

    def make_check(counted):
        item = types.SimpleNamespace(material_id=1, material=types.SimpleNamespace(code='SYNTH', name='合成物料'),
                                     counted_at=datetime.datetime(2020, 1, 1, 10, 2) if counted else None,
                                     counted_by=1 if counted else None)
        return types.SimpleNamespace(id=1, status='pending', items=[item], warehouse='合成仓',
                                     frozen_at=datetime.datetime(2020, 1, 1, 10, 0), check_no='CK-SYNTH')

    def route_env(check, state, session, movement):
        model = types.SimpleNamespace(items=object(), query=Lookup(check))
        session.get = lambda *_args, **_kwargs: check

        def lock(*_args):
            state['movement_after_lock'] = True
            return check, True

        def snapshot(current, _warehouse_id):
            uncounted = sum(not (item.counted_at or item.counted_by) for item in current.items)
            found, count, samples = movement(current)
            risks = {'uncounted': uncounted, 'total': len(current.items),
                     'incomplete_count': 0,
                     'uncounted_samples': [], 'movement_count': count if found else 0,
                     'movement_samples': samples if found else [],
                     'unknown_warehouse_count': 0, 'unknown_time_count': 0,
                     'invalid_quantity_count': 0, 'unknown_freeze': current.frozen_at is None,
                     'has_risk': bool(uncounted or found or current.frozen_at is None)}
            return f'{current.id}:{uncounted}:{count}:{state.get("snapshot_version", 0)}', risks

        env = {
            'InventoryCheck': model, 'InventoryCheckItem': types.SimpleNamespace(material=object()),
            'selectinload': lambda *_args: Loader(), '_acquire_order_write_lock': lock,
            '_create_adjustment_drafts_from_check': lambda _check: ([], None),
            'assert_warehouse_active': lambda *_args, **_kwargs: (state.get('warehouse_exists', True), '仓库不存在'),
            'api_error': lambda message: {'status': 'error', 'msg': message},
            'log_operation': lambda *_args: None, 'CheckCompleteInput': Input,
            'json_object_body': lambda: {'force': state.get('force', False),
                                        'confirmation_token': state.get('confirmation_token')},
            'jsonify': lambda value: value, 'db': types.SimpleNamespace(session=session),
            '_check_period_movement_alerts': movement,
            '_resolve_check_warehouse': lambda _value: types.SimpleNamespace(id=1),
            '_check_complete_snapshot': snapshot,
            'current_app': types.SimpleNamespace(secret_key='synthetic-test-secret'),
            'current_user': types.SimpleNamespace(get_id=lambda: state.get('user_id', '1')),
            'URLSafeTimedSerializer': URLSafeTimedSerializer, 'BadSignature': BadSignature,
            'app': types.SimpleNamespace(logger=types.SimpleNamespace(error=lambda *_args: None)),
        }
        load_functions(env, '_issue_check_confirmation', '_accept_check_confirmation')
        return env

    class InventoryConfirmationRisk(unittest.TestCase):
        def setUp(self):
            self.engine = create_engine('sqlite://', creator=lambda: memory_connect(':memory:'))
            Base.metadata.create_all(self.engine)
            self.session = Session(self.engine)
            dbs = self.session.execute(text('PRAGMA database_list')).all()
            self.assertTrue(dbs)
            self.assertTrue(all(row[1] in ('main', 'temp') and row[2] == '' for row in dbs))

        def tearDown(self):
            self.session.close()
            self.engine.dispose()

        def movement_env(self, warehouse):
            return {'StockTransaction': Txn, 'Warehouse': types.SimpleNamespace(id=SyntheticWarehouse.id, query=WarehouseLookup(warehouse)),
                    'cast': cast, 'String': String,
                    'normalize_stock_quantity': float,
                    'db': types.SimpleNamespace(session=self.session, func=func, or_=or_)}

        def test_uncounted_confirmation_cannot_skip_other_movement(self):
            check = make_check(False)
            state, session = {}, SessionStub()
            calls = []
            def movement(_check):
                calls.append(1)
                return True, 1, [{'code': 'SYNTH', 'name': '合成物料', 'net': 10}]
            env = route_env(check, state, session, movement)
            load_functions(env, '_check_uncounted_alerts', 'complete_check')
            first = env['complete_check'](1)
            self.assertEqual(first['status'], 'confirm')
            state['force'] = True  # 模拟旧客户端确认未盘，无其他风险凭据。
            second = env['complete_check'](1)
            self.assertNotEqual(second['status'], 'success', '单次 force 不能跳过尚未告知的动销')
            self.assertEqual(session.commits, 0)

        def test_movement_appearing_during_lock_requires_new_confirmation(self):
            check = make_check(True)
            state, session = {}, SessionStub()
            def movement(_check):
                if state.get('movement_after_lock'):
                    return True, 1, [{'code': 'SYNTH', 'name': '合成物料', 'net': 10}]
                return False, 0, []
            env = route_env(check, state, session, movement)
            load_functions(env, '_check_uncounted_alerts', 'complete_check')
            response = env['complete_check'](1)
            self.assertEqual(response['status'], 'confirm', '取得写锁后出现新流水应重新提示')
            self.assertEqual(session.commits, 0)

        def test_equal_inbound_outbound_still_requires_movement_warning(self):
            check = make_check(True)
            self.session.add_all([
                Txn(material_id=1, warehouse_id=1, quantity=10, created_at=datetime.datetime(2020, 1, 1, 10, 1)),
                Txn(material_id=1, warehouse_id=1, quantity=-10, created_at=datetime.datetime(2020, 1, 1, 10, 3)),
            ])
            self.session.commit()
            env = self.movement_env(types.SimpleNamespace(id=1))
            load_functions(env, '_check_period_movement_alerts')
            self.assertTrue(env['_check_period_movement_alerts'](check)[0],
                            '冻结后入库、实盘、等量出库仍发生动销，净额为零不能忽略')

        def test_unknown_warehouse_does_not_label_other_warehouse_as_movement(self):
            check = make_check(True)
            self.session.add(Txn(material_id=1, warehouse_id=2, quantity=7,
                                 created_at=datetime.datetime(2020, 1, 1, 10, 3)))
            self.session.commit()
            movement_globals = self.movement_env(None)
            load_functions(movement_globals, '_check_period_movement_alerts')
            state, session = {'warehouse_exists': False}, SessionStub()
            env = route_env(check, state, session, movement_globals['_check_period_movement_alerts'])
            env['_resolve_check_warehouse'] = movement_globals['_resolve_check_warehouse']
            load_functions(env, '_check_uncounted_alerts', 'complete_check')
            response = env['complete_check'](1)
            self.assertEqual(session.commits, 0, '本场景仅验证提示，不声称发生业务写入')
            self.assertNotEqual(response.get('code'), 'period_movement',
                                '未知仓归属不能把其他仓流水标注成当前盘点仓动销')
            self.assertNotEqual(response.get('status'), 'success')

        def test_movement_excludes_other_warehouse_and_own_check(self):
            check = make_check(True)
            self.session.add_all([
                Txn(material_id=1, warehouse_id=2, quantity=9,
                    created_at=datetime.datetime(2020, 1, 1, 10, 3)),
                Txn(material_id=1, warehouse_id=1, quantity=5,
                    created_at=datetime.datetime(2020, 1, 1, 10, 3),
                    reference_type='check', reference_id=check.id),
            ])
            self.session.commit()
            env = self.movement_env(types.SimpleNamespace(id=1))
            load_functions(env, '_check_period_movement_alerts')
            self.assertEqual(env['_check_period_movement_alerts'](check), (False, 0, []))

        def test_nonzero_and_zero_net_movement_are_both_shown(self):
            check = make_check(True)
            self.session.add(Txn(material_id=1, warehouse_id=1, quantity=-7,
                                 created_at=datetime.datetime(2020, 1, 1, 10, 3)))
            self.session.commit()
            env = self.movement_env(types.SimpleNamespace(id=1))
            load_functions(env, '_check_period_movement_alerts')
            found, count, samples = env['_check_period_movement_alerts'](check)
            self.assertTrue(found)
            self.assertEqual(count, 1)
            self.assertEqual(samples[0]['net'], -7)
            self.session.add(Txn(material_id=1, warehouse_id=1, quantity=7,
                                 created_at=datetime.datetime(2020, 1, 1, 10, 4)))
            self.session.commit()
            found, count, samples = env['_check_period_movement_alerts'](check)
            self.assertTrue(found)
            self.assertEqual(count, 1)
            self.assertEqual(samples[0]['net'], 0)

        def test_warehouse_code_resolves_movement(self):
            check = make_check(True)
            check.warehouse = 'SYN-CODE'
            self.session.add(Txn(material_id=1, warehouse_id=1, quantity=5,
                                 created_at=datetime.datetime(2020, 1, 1, 10, 3)))
            self.session.commit()
            env = self.movement_env(types.SimpleNamespace(id=1, name='合成仓', code='SYN-CODE'))
            load_functions(env, '_check_period_movement_alerts')
            self.assertTrue(env['_check_period_movement_alerts'](check)[0], '有效仓库编码不能漏掉动销')

        def test_warehouse_name_code_conflict_cannot_be_forced(self):
            check = make_check(True)
            check.warehouse = 'SYN-IDENTITY'
            warehouses = [types.SimpleNamespace(id=1, name='SYN-IDENTITY', code='A'),
                          types.SimpleNamespace(id=2, name='B', code='SYN-IDENTITY')]
            movement_globals = self.movement_env(warehouses)
            load_functions(movement_globals, '_check_period_movement_alerts')
            state, session = {'force': True}, SessionStub()
            env = route_env(check, state, session, movement_globals['_check_period_movement_alerts'])
            env['_resolve_check_warehouse'] = movement_globals['_resolve_check_warehouse']
            load_functions(env, '_check_uncounted_alerts', 'complete_check')
            response = env['complete_check'](1)
            self.assertNotEqual(response.get('status'), 'success')
            self.assertEqual(session.commits, 0, '名称与编码冲突不能由 force 猜仓')

        def test_warehouse_unknown_cannot_be_forced_without_freeze(self):
            check = make_check(True)
            check.frozen_at = None
            movement_globals = self.movement_env(None)
            load_functions(movement_globals, '_check_period_movement_alerts')
            state, session = {'force': True}, SessionStub()
            env = route_env(check, state, session, movement_globals['_check_period_movement_alerts'])
            env['_resolve_check_warehouse'] = movement_globals['_resolve_check_warehouse']
            load_functions(env, '_check_uncounted_alerts', 'complete_check')
            response = env['complete_check'](1)
            self.assertNotEqual(response.get('status'), 'success')
            self.assertEqual(session.commits, 0, '未知仓及无冻结时间不能直接完成')

        def test_warehouse_ambiguity_after_lock_cannot_be_forced(self):
            check = make_check(True)
            state, session = {'force': True}, SessionStub()
            def movement(_check):
                return (None, 0, []) if state.get('movement_after_lock') else (False, 0, [])
            env = route_env(check, state, session, movement)
            env['_resolve_check_warehouse'] = lambda _value: None if state.get('movement_after_lock') else types.SimpleNamespace(id=1)
            load_functions(env, '_check_uncounted_alerts', 'complete_check')
            response = env['complete_check'](1)
            self.assertNotEqual(response.get('status'), 'success', '加锁后仓库出现歧义时不能直接完成')
            self.assertEqual(session.commits, 0)

        def test_warehouse_change_before_lock_cannot_be_forced(self):
            check = make_check(True)
            state, session = {'force': True}, SessionStub()
            env = route_env(check, state, session, lambda _check: (False, 0, []))
            def lock(*_args):
                check.warehouse = '另一个仓库'
                return check, True
            env['_acquire_order_write_lock'] = lock
            load_functions(env, '_check_uncounted_alerts', 'complete_check')
            response = env['complete_check'](1)
            self.assertNotEqual(response.get('status'), 'success', '仓库在加锁前变化必须重新核对')
            self.assertEqual(session.commits, 0)

        def test_same_warehouse_text_resolving_to_different_id_cannot_be_forced(self):
            check = make_check(True)
            state, session = {'force': True}, SessionStub()
            env = route_env(check, state, session, lambda _check: (False, 0, []))
            env['_resolve_check_warehouse'] = lambda _value: types.SimpleNamespace(
                id=2 if state.get('movement_after_lock') else 1)
            load_functions(env, '_check_uncounted_alerts', 'complete_check')
            response = env['complete_check'](1)
            self.assertNotEqual(response.get('status'), 'success', '相同仓库文本指向不同仓库 ID 必须重新核对')
            self.assertEqual(session.commits, 0)

        def test_same_warehouse_matching_both_name_and_code_is_not_ambiguous(self):
            check = make_check(True)
            check.warehouse = 'SAME'
            wh = types.SimpleNamespace(id=1, name='SAME', code='SAME')
            self.session.add(Txn(material_id=1, warehouse_id=1, quantity=3,
                                 created_at=datetime.datetime(2020, 1, 1, 10, 3)))
            self.session.commit()
            env = self.movement_env(wh)
            load_functions(env, '_check_period_movement_alerts')
            found, count, _samples = env['_check_period_movement_alerts'](check)
            self.assertTrue(found)
            self.assertEqual(count, 1)

        def test_sqlite_warehouse_name_code_and_conflict(self):
            self.session.add_all([
                SyntheticWarehouse(id=1, name='仓库甲', code='A'),
                SyntheticWarehouse(id=2, name='仓库乙', code='仓库甲'),
                Txn(material_id=1, warehouse_id=1, quantity=5,
                    created_at=datetime.datetime(2020, 1, 1, 10, 3)),
            ])
            self.session.commit()
            check = make_check(True)
            env = self.movement_env(None)
            env['Warehouse'] = types.SimpleNamespace(query=self.session.query(SyntheticWarehouse))
            load_functions(env, '_check_period_movement_alerts')
            check.warehouse = 'A'
            self.assertTrue(env['_check_period_movement_alerts'](check)[0])
            check.warehouse = '仓库甲'
            self.assertIsNone(env['_check_period_movement_alerts'](check)[0], '名称与另一仓库编码冲突必须拒绝猜测')
            check.warehouse = '不存在的仓库'
            self.assertIsNone(env['_check_period_movement_alerts'](check)[0])

        def test_snapshot_captures_balanced_movements_and_changes(self):
            check = make_check(True)
            env = self.movement_env(types.SimpleNamespace(id=1))
            env.update(hashlib=hashlib, json=json, math=math, datetime=datetime.datetime,
                       location_management_enabled=lambda: False)
            load_functions(env, '_check_uncounted_alerts', '_check_complete_snapshot')
            before, risks = env['_check_complete_snapshot'](check, 1)
            self.assertFalse(risks['has_risk'])
            self.session.add_all([
                Txn(material_id=1, warehouse_id=1, transaction_type='in', quantity=10,
                    created_at=datetime.datetime(2020, 1, 1, 10, 1)),
                Txn(material_id=1, warehouse_id=1, transaction_type='out', quantity=-10,
                    created_at=datetime.datetime(2020, 1, 1, 10, 3)),
            ])
            self.session.commit()
            after, risks = env['_check_complete_snapshot'](check, 1)
            self.assertTrue(risks['has_risk'])
            self.assertEqual(risks['movement_count'], 1)
            self.assertNotEqual(before, after, '净额为零的流水也必须改变确认快照')

        def test_snapshot_unknown_warehouse_and_missing_time_are_risks(self):
            check = make_check(True)
            self.session.add(Txn(material_id=1, warehouse_id=None, quantity=3,
                                 created_at=datetime.datetime(2020, 1, 1, 10, 3)))
            self.session.commit()
            env = self.movement_env(types.SimpleNamespace(id=1))
            env.update(hashlib=hashlib, json=json, math=math, datetime=datetime.datetime,
                       location_management_enabled=lambda: False)
            load_functions(env, '_check_uncounted_alerts', '_check_complete_snapshot')
            before, risks = env['_check_complete_snapshot'](check, 1)
            self.assertTrue(risks['has_risk'])
            self.assertEqual(risks['unknown_warehouse_count'], 1)
            check.frozen_at = None
            after, risks = env['_check_complete_snapshot'](check, 1)
            self.assertTrue(risks['unknown_freeze'])
            self.assertNotEqual(before, after)

        def test_snapshot_orphan_and_null_warehouse_are_unknown_not_other_warehouse(self):
            check = make_check(True)
            self.session.add_all([SyntheticWarehouse(id=1, name='仓一', code='A'),
                                  SyntheticWarehouse(id=2, name='仓二', code='B')])
            self.session.add_all([
                Txn(material_id=1, warehouse_id=2, quantity=4, created_at=datetime.datetime(2020, 1, 1, 10, 1)),
                Txn(material_id=1, warehouse_id=999, quantity=5, created_at=datetime.datetime(2020, 1, 1, 10, 2)),
                Txn(material_id=1, warehouse_id=None, quantity=6, created_at=datetime.datetime(2020, 1, 1, 10, 3)),
            ])
            self.session.commit()
            env = self.movement_env(types.SimpleNamespace(id=1))
            env.update(hashlib=hashlib, json=json, math=math, datetime=datetime.datetime,
                       location_management_enabled=lambda: False)
            load_functions(env, '_check_uncounted_alerts', '_check_complete_snapshot')
            before, risks = env['_check_complete_snapshot'](check, 1)
            self.assertEqual(risks['unknown_warehouse_count'], 2)
            self.assertEqual(risks['movement_count'], 0)
            self.session.add(SyntheticWarehouse(id=999, name='仓三', code='C'))
            self.session.commit()
            after, risks = env['_check_complete_snapshot'](check, 1)
            self.assertEqual(risks['unknown_warehouse_count'], 1)
            self.assertNotEqual(before, after)

        def test_invalid_old_sorting_timestamp_is_unknown_but_valid_old_is_not(self):
            check = make_check(True)
            self.session.execute(text("INSERT INTO synthetic_stock_transaction (material_id, warehouse_id, quantity, created_at) VALUES (1, 1, 1, '0000-invalid-date'), (1, 1, 2, '2019-01-01 00:00:00')"))
            self.session.commit()
            env = self.movement_env(types.SimpleNamespace(id=1))
            env.update(hashlib=hashlib, json=json, math=math, datetime=datetime.datetime,
                       location_management_enabled=lambda: False)
            load_functions(env, '_check_uncounted_alerts', '_check_complete_snapshot')
            _, risks = env['_check_complete_snapshot'](check, 1)
            self.assertEqual(risks['unknown_time_count'], 1)
            self.assertEqual(risks['movement_count'], 0)
            self.assertTrue(risks['has_risk'])

        def test_signed_confirmation_binds_user_document_and_snapshot(self):
            env = {'URLSafeTimedSerializer': URLSafeTimedSerializer, 'BadSignature': BadSignature,
                   'current_app': types.SimpleNamespace(secret_key='synthetic-test-secret')}
            load_functions(env, '_issue_check_confirmation', '_accept_check_confirmation')
            issue, accept = env['_issue_check_confirmation'], env['_accept_check_confirmation']
            token = issue(12, 'user-a', 'a' * 64)
            self.assertTrue(accept(token, 12, 'user-a', 'a' * 64))
            self.assertFalse(accept(token, 13, 'user-a', 'a' * 64))
            self.assertFalse(accept(token, 12, 'user-b', 'a' * 64))
            self.assertFalse(accept(token, 12, 'user-a', 'b' * 64))
            self.assertFalse(accept(token + 'x', 12, 'user-a', 'a' * 64))
            self.assertFalse(accept(None, 12, 'user-a', 'a' * 64))
            with patch('itsdangerous.timed.time.time', return_value=10000):
                expiring = issue(12, 'user-a', 'a' * 64)
            with patch('itsdangerous.timed.time.time', return_value=10601):
                self.assertFalse(accept(expiring, 12, 'user-a', 'a' * 64))

        def test_combined_risks_require_signed_confirmation(self):
            check = make_check(False)
            state, session = {}, SessionStub()
            env = route_env(check, state, session,
                            lambda _check: (True, 1, [{'code': 'SYNTH', 'name': '合成物料', 'net': 0}]))
            load_functions(env, '_check_uncounted_alerts', 'complete_check')
            first = env['complete_check'](1)
            self.assertEqual(first['status'], 'confirm')
            self.assertIn('未盘', first['msg'])
            self.assertIn('流水', first['msg'])
            self.assertTrue(first.get('confirmation_token'))
            self.assertEqual(session.commits, 0)
            state.update(force=True, confirmation_token=first['confirmation_token'])
            second = env['complete_check'](1)
            self.assertEqual(second['status'], 'success')
            self.assertEqual(session.commits, 1)

        def test_changed_snapshot_requires_another_confirmation(self):
            check = make_check(False)
            state, session = {}, SessionStub()
            env = route_env(check, state, session, lambda _check: (False, 0, []))
            load_functions(env, '_check_uncounted_alerts', 'complete_check')
            first = env['complete_check'](1)
            self.assertTrue(first.get('confirmation_token'))
            state.update(force=True, confirmation_token=first['confirmation_token'], snapshot_version=1)
            second = env['complete_check'](1)
            self.assertEqual(second['status'], 'confirm')
            self.assertNotEqual(second.get('confirmation_token'), first['confirmation_token'])
            self.assertEqual(session.commits, 0)

        def test_confirmation_for_another_user_is_not_accepted(self):
            check = make_check(False)
            state, session = {}, SessionStub()
            env = route_env(check, state, session, lambda _check: (False, 0, []))
            load_functions(env, '_check_uncounted_alerts', 'complete_check')
            first = env['complete_check'](1)
            self.assertTrue(first.get('confirmation_token'))
            state.update(force=True, confirmation_token=first['confirmation_token'], user_id='other')
            second = env['complete_check'](1)
            self.assertEqual(second['status'], 'confirm')
            self.assertEqual(session.commits, 0)

        def test_disappearing_risk_still_requires_new_confirmation(self):
            check = make_check(False)
            state, session = {}, SessionStub()
            env = route_env(check, state, session, lambda _check: (False, 0, []))
            load_functions(env, '_check_uncounted_alerts', 'complete_check')
            first = env['complete_check'](1)
            check.items[0].counted_by = 1
            state.update(force=True, confirmation_token=first['confirmation_token'])
            second = env['complete_check'](1)
            self.assertEqual(second['status'], 'confirm')
            self.assertIn('当前未发现', second['msg'])
            self.assertEqual(session.commits, 0)

        def test_location_switch_changes_snapshot(self):
            check = make_check(False)
            setting = {'enabled': False}
            env = self.movement_env(types.SimpleNamespace(id=1))
            env.update(hashlib=hashlib, json=json, math=math, datetime=datetime.datetime,
                       location_management_enabled=lambda: setting['enabled'])
            load_functions(env, '_check_uncounted_alerts', '_check_complete_snapshot')
            before, _ = env['_check_complete_snapshot'](check, 1)
            setting['enabled'] = True
            after, _ = env['_check_complete_snapshot'](check, 1)
            self.assertNotEqual(before, after)

        def test_partial_count_metadata_is_a_separate_risk(self):
            check = make_check(True)
            env = self.movement_env(types.SimpleNamespace(id=1))
            env.update(hashlib=hashlib, json=json, math=math, datetime=datetime.datetime,
                       location_management_enabled=lambda: False)
            load_functions(env, '_check_uncounted_alerts', '_check_complete_snapshot')
            _, risks = env['_check_complete_snapshot'](check, 1)
            self.assertFalse(risks['has_risk'])
            check.items[0].counted_by = None
            _, risks = env['_check_complete_snapshot'](check, 1)
            self.assertEqual(risks['incomplete_count'], 1)
            self.assertEqual(risks['uncounted'], 0)
            check.items[0].counted_by = 1
            check.items[0].counted_at = None
            _, risks = env['_check_complete_snapshot'](check, 1)
            self.assertEqual(risks['incomplete_count'], 1)
            self.assertEqual(risks['uncounted'], 0)
            check.items[0].counted_by = None
            _, risks = env['_check_complete_snapshot'](check, 1)
            self.assertEqual(risks['incomplete_count'], 0)
            self.assertEqual(risks['uncounted'], 1)

        def test_movement_sum_overflow_never_reported_as_zero(self):
            check = make_check(True)
            self.session.add_all([
                Txn(material_id=1, warehouse_id=1, quantity=1e308,
                    created_at=datetime.datetime(2020, 1, 1, 10, 1)),
                Txn(material_id=1, warehouse_id=1, quantity=1e308,
                    created_at=datetime.datetime(2020, 1, 1, 10, 2)),
            ])
            self.session.commit()
            env = self.movement_env(types.SimpleNamespace(id=1))
            env.update(hashlib=hashlib, json=json, math=math, datetime=datetime.datetime,
                       location_management_enabled=lambda: False)
            load_functions(env, '_check_uncounted_alerts', '_check_complete_snapshot')
            _, risks = env['_check_complete_snapshot'](check, 1)
            self.assertEqual(risks['movement_count'], 1)
            self.assertGreater(risks['invalid_quantity_count'], 0)
            self.assertIsNone(risks['movement_samples'][0]['net'])

        def test_extreme_finite_quantity_uses_real_stock_normalization(self):
            from decimal import Decimal, ROUND_HALF_UP
            check = make_check(True)
            self.session.add(Txn(material_id=1, warehouse_id=1, quantity=1e100,
                                 created_at=datetime.datetime(2020, 1, 1, 10, 1)))
            self.session.commit()
            env = self.movement_env(types.SimpleNamespace(id=1))
            env.update(hashlib=hashlib, json=json, math=math, datetime=datetime.datetime,
                       location_management_enabled=lambda: False, Decimal=Decimal,
                       ROUND_HALF_UP=ROUND_HALF_UP, STOCK_COMPARE_EPSILON=1e-6)
            tree = ast.parse((ROOT / 'app/utils.py').read_text(encoding='utf-8-sig'))
            names = {'round_to_2_decimals', 'normalize_stock_quantity'}
            module = ast.fix_missing_locations(ast.Module(body=[n for n in tree.body
                if isinstance(n, ast.FunctionDef) and n.name in names], type_ignores=[]))
            exec(compile(module, '<synthetic-real-stock-normalization>', 'exec'), env)
            load_functions(env, '_check_uncounted_alerts', '_check_complete_snapshot')
            _, risks = env['_check_complete_snapshot'](check, 1)
            self.assertTrue(risks['has_risk'])
            self.assertEqual(risks['movement_count'], 1)
            self.assertGreater(risks['invalid_quantity_count'], 0)
            self.assertIsNone(risks['movement_samples'][0]['net'])

        def test_non_sqlite_refuses_before_completion(self):
            check = make_check(True)
            state, session = {}, SessionStub()
            session.get_bind = lambda: types.SimpleNamespace(dialect=types.SimpleNamespace(name='postgresql'))
            env = route_env(check, state, session, lambda _check: (False, 0, []))
            load_functions(env, '_check_uncounted_alerts', 'complete_check')
            response = env['complete_check'](1)
            self.assertNotEqual(response.get('status'), 'success')
            self.assertEqual(session.commits, 0)

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(InventoryConfirmationRisk)
    if suite.countTestCases() != 28:
        raise RuntimeError('测试清单不完整或为空')
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)


def test_inventory_confirmation_risks_in_isolated_process():
    env = {key: os.environ[key] for key in ('SYSTEMROOT', 'WINDIR') if key in os.environ}
    result = subprocess.run([sys.executable, '-I', '-S', '-B', '-X', 'utf8', __file__],
                            env=env, capture_output=True, text=True, encoding='utf-8', timeout=30)
    assert result.returncode == 0, result.stderr


if __name__ == '__main__':
    main()
