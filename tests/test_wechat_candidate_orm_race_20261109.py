"""Copied claim function raced with independent ORM sessions on SQLite memory."""
import ast
import builtins
from datetime import datetime, timedelta
import hashlib
import hmac
import platform
from pathlib import Path
import secrets
import socket
import sqlite3
import subprocess
import sys
import sysconfig
import threading
import time
import types
import unittest
import uuid
from unittest.mock import patch

CANDIDATE = Path(__file__).resolve().parents[1]


def main():
    def deny(*_a, **_kw): raise AssertionError('real network, DB files or subprocess forbidden')
    uri = 'file:wms-orm-' + uuid.uuid4().hex + '?mode=memory&cache=shared'
    real_connect = sqlite3.connect
    def memory_only(database, *args, **kwargs):
        if database != uri or kwargs.get('uri') is not True: deny()
        connection = real_connect(database, *args, **kwargs)
        if any(row[2] for row in connection.execute('PRAGMA database_list').fetchall()):
            connection.close()
            deny()
        return connection
    sqlite3.connect = sqlite3.dbapi2.connect = memory_only
    socket.socket.connect = socket.socket.connect_ex = deny
    socket.getaddrinfo = socket.create_connection = deny
    class DeniedPopen:
        def __init__(self, *_a, **_kw): deny()
    subprocess.Popen = DeniedPopen
    platform.machine = lambda: 'synthetic'
    original_import = builtins.__import__
    def guarded(name, *args, **kwargs):
        level = args[2] if len(args) > 2 else kwargs.get('level', 0)
        if level == 0 and (name == 'app' or name.startswith('app.')):
            if name != 'app' or sys.modules.get('app') is not fake_app:
                deny()
        return original_import(name, *args, **kwargs)
    fake_app = types.ModuleType('app')
    builtins.__import__ = guarded
    sys.path.append(sysconfig.get_paths()['purelib'])
    from sqlalchemy import Column, DateTime, Integer, String, create_engine, text
    from sqlalchemy.exc import OperationalError
    from sqlalchemy.orm import Session, declarative_base
    from sqlalchemy.pool import NullPool, StaticPool, SingletonThreadPool

    anchor = sqlite3.connect(uri, uri=True, isolation_level=None, check_same_thread=False)
    engine = create_engine('sqlite://', creator=lambda: sqlite3.connect(uri, uri=True, check_same_thread=False), poolclass=NullPool)
    Base = declarative_base()
    class Log(Base):
        __tablename__ = 'synthetic_claim_log'
        id = Column(Integer, primary_key=True)
        status = Column(String)
        message = Column(String)
    class AlertLog(Base):
        __tablename__ = 'synthetic_alert_log'
        id = Column(Integer, primary_key=True)
        module_key = Column(String)
        config_id = Column(Integer)
        order_id = Column(Integer)
        order_no = Column(String)
        share_date = Column(String)
        trigger_type = Column(String)
        image_path = Column(String)
        image_size = Column(Integer)
        receiver_name = Column(String)
        receiver_wechat_id = Column(String)
        created_at = Column(DateTime, default=datetime.now)
        status = Column(String)
        message = Column(String)
        sent_at = Column(DateTime)
    class Notification(Base):
        __tablename__ = 'synthetic_notification'
        id = Column(Integer, primary_key=True)
        title = Column(String)
    Base.metadata.create_all(engine)
    tree = ast.parse((CANDIDATE / 'app/services/wechat_poll_claim.py').read_text(encoding='utf-8-sig'))
    funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in ('digest_token','claim_log','claimed_message')]
    if len(funcs) != 3: raise AssertionError('copied source list incomplete')
    env = {'hashlib': hashlib, 'hmac': hmac, 'secrets': secrets}
    exec(compile(ast.fix_missing_locations(ast.Module(body=funcs, type_ignores=[])), '<copied-orm-claim>', 'exec'), env)
    alert_tree = ast.parse((CANDIDATE / 'app/services/print_alert_reserve.py').read_text(encoding='utf-8-sig'))
    alert_funcs = [n for n in alert_tree.body if isinstance(n, ast.FunctionDef)
                   and n.name in ('reserve_alert', 'attach_alert_image', 'finish_alert')]
    if len(alert_funcs) != 3: raise AssertionError('copied alert source list incomplete')
    env.update(datetime=datetime, timedelta=timedelta, Session=Session, text=text,
               StaticPool=StaticPool, SingletonThreadPool=SingletonThreadPool)
    exec(compile(ast.fix_missing_locations(ast.Module(body=alert_funcs, type_ignores=[])), '<copied-alert-claim>', 'exec'), env)
    alert_entry_tree = ast.parse((CANDIDATE / 'app/routes/print_alerts.py').read_text(encoding='utf-8-sig'))
    alert_entry = [n for n in alert_entry_tree.body if isinstance(n, ast.FunctionDef) and n.name == 'push_print_alert_wechat']
    if len(alert_entry) != 1: raise AssertionError('copied alert entrypoint missing')
    fake_app.WechatShareLog = AlertLog
    fake_app.get_system_setting_bool = lambda *_args: True
    fake_app.get_system_setting_int = lambda *_args: 10
    fake_app._wechat_share_default_config = lambda: types.SimpleNamespace(id=1, receiver_name='', receiver_wechat_id='')
    service = types.ModuleType('services.print_alert_reserve')
    service.reserve_alert, service.attach_alert_image, service.finish_alert = (
        env['reserve_alert'], env['attach_alert_image'], env['finish_alert'])
    parent = types.ModuleType('services'); parent.__path__ = []

    class ConcurrentClaimTests(unittest.TestCase):
        def setUp(self):
            with Session(engine) as session:
                session.query(Log).delete()
                session.query(AlertLog).delete()
                session.query(Notification).delete()
                session.add(Log(id=1, status='queued_v2', message='合成原始信息'))
                session.commit()

        def test_claim_log(self):
            barrier, outcomes, errors = threading.Barrier(2), [], []
            def worker():
                try:
                    barrier.wait(timeout=5)
                    for _ in range(200):
                        try:
                            with Session(engine) as session:
                                token = env['claim_log'](session, Log, 1)
                                session.commit()
                                outcomes.append(token)
                            break
                        except OperationalError as exc:
                            if 'locked' not in str(exc).lower(): raise
                            time.sleep(0.005)
                    else: raise AssertionError('worker timed out')
                except Exception as exc: errors.append(exc)
            threads = [threading.Thread(target=worker) for _ in range(2)]
            for thread in threads: thread.start()
            for thread in threads: thread.join(timeout=5)
            self.assertFalse(any(thread.is_alive() for thread in threads))
            self.assertEqual(errors, [])
            winners = [value for value in outcomes if value]
            self.assertEqual(len(outcomes), 2)
            self.assertEqual(len(winners), 1)
            with Session(engine) as session:
                log = session.get(Log, 1)
                self.assertEqual(log.status, 'sending')
                self.assertEqual(env['claimed_message'](log, winners[0]), '合成原始信息')
                self.assertNotIn(winners[0], log.message)

        def test_claim_committed_but_reply_lost_never_requeues(self):
            with Session(engine) as session:
                token = env['claim_log'](session, Log, 1)
                session.commit()
                self.assertIsNotNone(token)
            with Session(engine) as session:
                self.assertIsNone(env['claim_log'](session, Log, 1))
                self.assertEqual(session.get(Log, 1).status, 'sending')

        def test_reserve_alert(self):
            barrier, outcomes, errors = threading.Barrier(2), [], []
            db = types.SimpleNamespace(engine=engine)
            def worker():
                try:
                    barrier.wait(timeout=5)
                    for _ in range(200):
                        try:
                            outcomes.append(env['reserve_alert'](db, AlertLog, {'module_key':'print_alert','order_id':1,'order_no':'合成告警'}, 10))
                            break
                        except OperationalError as exc:
                            if 'locked' not in str(exc).lower(): raise
                            time.sleep(0.005)
                    else: raise AssertionError('worker timed out')
                except Exception as exc: errors.append(exc)
            threads = [threading.Thread(target=worker) for _ in range(2)]
            for thread in threads: thread.start()
            for thread in threads: thread.join(timeout=5)
            self.assertEqual(errors, [])
            self.assertEqual(len(outcomes), 2)
            winners = [item for item in outcomes if item is not None]
            self.assertEqual(len(winners), 1)
            with Session(engine) as session:
                self.assertEqual(session.query(AlertLog).count(), 1)
                self.assertEqual(session.get(AlertLog, winners[0]).status, 'sending')
            self.assertTrue(env['finish_alert'](db, AlertLog, winners[0], 'uncertain', '模拟超时'))
            self.assertFalse(env['finish_alert'](db, AlertLog, winners[0], 'sent', '迟到回报'))
            self.assertIsNone(env['reserve_alert'](db, AlertLog, {'module_key':'print_alert','order_id':1,'order_no':'合成告警'}, 10))

        def test_attach_alert_image(self):
            barrier, delivered, errors = threading.Barrier(2), [], []
            fake_app._wechat_share_send_image = lambda *_args: (delivered.append('synthetic') or ('sent','ok','synthetic'))
            def render(_notification): return '/synthetic/alert.png'
            def synchronized_reserve(*args):
                barrier.wait(timeout=5)
                return env['reserve_alert'](*args)
            service.reserve_alert = synchronized_reserve
            entry_env = {'db': types.SimpleNamespace(engine=engine), 'datetime': datetime,
                         'date': datetime, 'timedelta': timedelta, '_render_alert_image': render}
            # The copied entry uses date.today(); synthesize a proper date provider.
            from datetime import date
            entry_env['date'] = date
            exec(compile(ast.fix_missing_locations(ast.Module(body=alert_entry, type_ignores=[])),
                         '<copied-alert-entry>', 'exec'), entry_env)
            def worker():
                try: entry_env['push_print_alert_wechat'](types.SimpleNamespace(id=1, title='合成告警'))
                except Exception as exc: errors.append(exc)
            with patch.dict(sys.modules, {'app': fake_app, 'services': parent, 'services.print_alert_reserve': service}), \
                 patch('os.path.isfile', return_value=True), patch('os.path.getsize', return_value=1):
                threads = [threading.Thread(target=worker) for _ in range(2)]
                for thread in threads: thread.start()
                for thread in threads: thread.join(timeout=5)
            self.assertFalse(any(thread.is_alive() for thread in threads))
            self.assertEqual(errors, [])
            self.assertEqual(delivered, ['synthetic'])
            service.reserve_alert = env['reserve_alert']
            with Session(engine) as session:
                self.assertEqual(session.query(AlertLog).count(), 1)
                self.assertEqual(session.query(AlertLog).one().status, 'sent')
                self.assertEqual(session.query(AlertLog).one().image_path, '/synthetic/alert.png')
                self.assertEqual(session.query(AlertLog).one().image_size, 1)

        def test_old_sending_and_uncertain_alerts_do_not_become_retryable(self):
            with Session(engine) as session:
                session.add(AlertLog(module_key='print_alert', order_id=1, order_no='合成告警', status='sending',
                                     message='结果未知', created_at=datetime(2020, 1, 1)))
                session.commit()
            db = types.SimpleNamespace(engine=engine)
            metadata = {'module_key':'print_alert','order_id':1,'order_no':'合成告警'}
            self.assertIsNone(env['reserve_alert'](db, AlertLog, metadata, 10))
            with Session(engine) as session:
                alert = session.query(AlertLog).one()
                alert.status = 'uncertain'
                session.commit()
            self.assertIsNone(env['reserve_alert'](db, AlertLog, metadata, 10))

        def test_different_notifications_with_same_title_are_not_confused(self):
            with Session(engine) as session:
                session.add(AlertLog(module_key='print_alert', order_id=1, order_no='相同标题',
                                     status='uncertain', message='结果未知', created_at=datetime(2020, 1, 1)))
                session.commit()
            db = types.SimpleNamespace(engine=engine)
            self.assertIsNone(env['reserve_alert'](db, AlertLog,
                              {'module_key':'print_alert','order_id':1,'order_no':'相同标题'}, 10))
            self.assertIsNotNone(env['reserve_alert'](db, AlertLog,
                                 {'module_key':'print_alert','order_id':2,'order_no':'相同标题'}, 10))

        def test_unresolved_legacy_alert_without_identity_is_not_guessed(self):
            with Session(engine) as session:
                session.add(AlertLog(module_key='print_alert', order_id=0, order_no='旧告警',
                                     status='pending', message='历史未知', created_at=datetime(2020, 1, 1)))
                session.commit()
            db = types.SimpleNamespace(engine=engine)
            self.assertIsNone(env['reserve_alert'](db, AlertLog,
                              {'module_key':'print_alert','order_id':9,'order_no':'新告警'}, 10))

        def test_deleted_notification_id_reuse_must_not_block_a_new_alert(self):
            with Session(engine) as session:
                previous = Notification(title='旧通知')
                session.add(previous)
                session.commit()
                previous_id = previous.id
                session.add(AlertLog(module_key='print_alert', order_id=previous_id, order_no='旧通知',
                                     status='uncertain', message='历史未知', created_at=datetime(2020, 1, 1)))
                session.delete(previous)
                session.commit()
                new = Notification(title='新通知')
                session.add(new)
                session.commit()
                self.assertEqual(new.id, previous_id, '合成 SQLite 应复现删除后 ID 复用')
                new_id = new.id
            db = types.SimpleNamespace(engine=engine)
            self.assertIsNotNone(env['reserve_alert'](db, AlertLog,
                                 {'module_key':'print_alert','order_id':new_id,'order_no':'新通知'}, 10),
                                 '不同通知不应因复用的 ID 被永久误挡')

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ConcurrentClaimTests)
    if suite.countTestCases() != 8: raise SystemExit('synthetic test list incomplete')
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    engine.dispose()
    anchor.close()
    return not result.wasSuccessful()


if __name__ == '__main__': raise SystemExit(main())


def test_wechat_candidate_orm_race_20261109_runs_against_actual_source(tmp_path):
    import os
    import runpy
    guard = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'scripts/verify_db_guard.py'))
    guard['require_owned_test_profile']()
    output = tmp_path / 'actual-source-output.txt'
    errors = tmp_path / 'actual-source-errors.txt'
    empty = tmp_path / 'empty-stdin.txt'
    empty.write_bytes(b'')
    import subprocess as child_process
    with empty.open('rb') as inp, output.open('wb') as out, errors.open('wb') as err:
        child = child_process.run([sys.executable, '-I', '-S', '-B', '-X', 'utf8', str(Path(__file__).resolve())],
            stdin=inp, stdout=out, stderr=err, env=dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8'), timeout=90)
    combined = output.read_text(encoding='utf-8') + errors.read_text(encoding='utf-8')
    assert child.returncode == 0, combined
    assert 'OK' in combined and 'Ran 0 tests' not in combined, combined
