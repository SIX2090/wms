"""Real dispatch claim function against synthetic in-memory ORM only."""
import ast
import builtins
import inspect
from datetime import date, datetime, timedelta
from pathlib import Path
import platform
import socket
import sqlite3
import subprocess
import sys
import sysconfig
import types
import unittest
from uuid import uuid4


def main():
    def deny(*_args, **_kwargs):
        raise AssertionError('external network, DB files and child processes forbidden')
    connect = sqlite3.connect
    def memory_only(database, *args, **kwargs):
        if database != ':memory:' or kwargs.get('uri', False):
            deny()
        return connect(database, *args, **kwargs)
    sqlite3.connect = sqlite3.dbapi2.connect = memory_only
    socket.socket.connect = socket.socket.connect_ex = deny
    socket.getaddrinfo = socket.create_connection = deny
    class DeniedPopen:
        def __init__(self, *_args, **_kwargs): deny()
    subprocess.Popen = DeniedPopen
    platform.machine = lambda: 'synthetic'
    original_import = builtins.__import__
    def safe_import(name, *args, **kwargs):
        level = args[2] if len(args) > 2 else kwargs.get('level', 0)
        if level == 0 and (name == 'app' or name.startswith('app.')):
            deny()
        return original_import(name, *args, **kwargs)
    builtins.__import__ = safe_import
    sys.path.append(sysconfig.get_paths()['purelib'])
    from sqlalchemy import Column, Date, DateTime, Integer, String, create_engine, update
    from sqlalchemy.exc import IntegrityError, SQLAlchemyError
    from sqlalchemy.orm import Session, declarative_base

    Base = declarative_base()
    class Dispatch(Base):
        __tablename__ = 'synthetic_dispatch'
        module_key = Column(String, primary_key=True)
        order_id = Column(Integer, primary_key=True)
        share_date = Column(Date, primary_key=True)
        token = Column(String)
        state = Column(String)
        lease_until = Column(DateTime)
        log_id = Column(Integer)
        updated_at = Column(DateTime)
    class Log(Base):
        __tablename__ = 'synthetic_log'
        id = Column(Integer, primary_key=True)
        module_key = Column(String)
        order_id = Column(Integer)
        share_date = Column(Date)
        status = Column(String)
        message = Column(String)
        sent_at = Column(DateTime)
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    source_path = (Path(r'C:\Users\Administrator\AppData\Local\Temp\wms-wechat-claim-src-vky5oct6')
                   / 'app/services/wechat_share_dispatch.py') if '--candidate' in sys.argv else (
                   Path(__file__).resolve().parents[1] / 'app/services/wechat_share_dispatch.py')
    source = ast.parse(source_path.read_text(encoding='utf-8-sig'))
    names = ('_commit', '_view', '_claim', '_record', '_uncertain', 'execute_share')
    funcs = [n for n in source.body if isinstance(n, ast.FunctionDef) and n.name in names]
    if len(funcs) != len(names):
        raise AssertionError('expected real dispatch functions')
    safe_assignment = next(n for n in source.body if isinstance(n, ast.Assign)
                           and any(isinstance(t, ast.Name) and t.id == 'SAFE_FAILURE_CODES' for t in n.targets))
    safe_codes = frozenset(ast.literal_eval(safe_assignment.value.args[0]))
    if '--codes-only' in sys.argv:
        safe_codes = safe_codes - {'focus_lost', 'paste_failed'}
    env = {'datetime': datetime, 'timedelta': timedelta, 'uuid4': uuid4,
           'LEASE_SECONDS': 300, 'UNCERTAIN_MESSAGE': 'synthetic uncertain',
           'db': types.SimpleNamespace(engine=engine, session=types.SimpleNamespace(new=[], dirty=[], deleted=[])), 'Session': Session,
           'Dispatch': Dispatch, 'Log': Log, 'update': update, 'IntegrityError': IntegrityError,
           'SQLAlchemyError': SQLAlchemyError, 'SAFE_FAILURE_CODES': safe_codes,
           'current_app': types.SimpleNamespace(logger=types.SimpleNamespace(error=lambda *_a: None)),
           'DispatchUnavailable': type('DispatchUnavailable', (RuntimeError,), {})}
    exec(compile(ast.fix_missing_locations(ast.Module(body=funcs, type_ignores=[])),
                 '<synthetic-real-dispatch>', 'exec'), env)

    class ForcedResendRace(unittest.TestCase):
        def setUp(self):
            with Session(engine) as session:
                session.query(Log).delete()
                session.query(Dispatch).delete()
                session.commit()

        def test_force_does_not_steal_a_queued_task_already_claimed_by_helper(self):
            key = {'module_key': 'in_order', 'order_id': 1, 'share_date': date(2026, 11, 9)}
            with Session(engine) as session:
                session.add(Dispatch(**key, token='synthetic-old', state='pending',
                                     lease_until=datetime.now() + timedelta(minutes=1), log_id=1))
                session.add(Log(id=1, **key, status='sending', message='synthetic active claim'))
                session.commit()
            token, result = env['_claim'](key, force=True)
            self.assertIsNone(token, '轮询助手在途时不允许强制直推同时领取')
            self.assertIsNotNone(result)

        def test_safe_new_pending_is_queued_v2_for_the_polling_protocol(self):
            key = {'module_key': 'in_order', 'order_id': 2, 'share_date': date(2026, 11, 9)}
            with Session(engine) as session:
                session.add(Dispatch(**key, token='synthetic-old', state='sending',
                                     lease_until=datetime.now() + timedelta(minutes=1), log_id=2))
                session.add(Log(id=2, **key, status='sending', message='synthetic'))
                session.commit()
            fn = env['_record']
            kwargs = {'queue_for_helper': True} if 'queue_for_helper' in inspect.signature(fn).parameters else {}
            fn(key, 'synthetic-old', 'pending', '尚未直推', **kwargs)
            with Session(engine) as session:
                self.assertEqual(session.get(Log, 2).status, 'queued_v2')
                self.assertEqual(session.get(Dispatch, tuple(key.values())).state, 'pending')

        def test_uncertain_send_codes_are_never_automatically_retried(self):
            for number, code in enumerate(('focus_lost', 'paste_failed'), start=11):
                with self.subTest(code=code):
                    key = {'module_key': 'in_order', 'order_id': number, 'share_date': date(2026, 11, 9)}
                    deliveries = []
                    def deliver(_payload):
                        deliveries.append(code)
                        return 'failed', code, '合成故障'
                    first = env['execute_share'](key, {}, lambda: ({}, b'synthetic'), deliver)
                    second = env['execute_share'](key, {}, lambda: ({}, b'synthetic'), deliver)
                    self.assertEqual(first['status'], 'uncertain')
                    self.assertEqual(second['action'], 'skipped')
                    self.assertEqual(deliveries, [code])

        def test_historical_ambiguous_failure_blocks_normal_retry_but_allows_force(self):
            for number, code in enumerate(('focus_lost', 'paste_failed'), start=21):
                with self.subTest(code=code):
                    key = {'module_key': 'in_order', 'order_id': number, 'share_date': date(2026, 11, 9)}
                    with Session(engine) as session:
                        session.add(Dispatch(**key, token='old', state='failed',
                                             lease_until=datetime.now(), log_id=number * 100))
                        session.add(Log(id=number * 100, **key, status='failed', message=f'失败（错误码：{code}）'))
                        session.commit()
                    deliveries = []
                    def deliver(_payload):
                        deliveries.append(code)
                        return 'sent', 'ok', 'synthetic'
                    normal = env['execute_share'](key, {}, lambda: ({}, b'synthetic'), deliver)
                    self.assertEqual(normal['status'], 'uncertain')
                    self.assertEqual(deliveries, [])
                    forced = env['execute_share'](key, {}, lambda: ({}, b'synthetic'), deliver, force=True)
                    self.assertEqual(forced['status'], 'sent')
                    self.assertEqual(deliveries, [code])

    if '--codes-only' in sys.argv or '--retry-safety' in sys.argv:
        suite = unittest.TestSuite(ForcedResendRace(name) for name in (
            'test_uncertain_send_codes_are_never_automatically_retried',
            'test_historical_ambiguous_failure_blocks_normal_retry_but_allows_force'))
        expected = 2
    else:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(ForcedResendRace)
        expected = 4
    if suite.countTestCases() != expected:
        raise SystemExit('synthetic test list is incomplete or empty')
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    engine.dispose()
    return not result.wasSuccessful()


if __name__ == '__main__':
    raise SystemExit(main())
