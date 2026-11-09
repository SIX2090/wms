"""Copied-source WMS routes with synthetic Flask/ORM, strictly private SQLite memory."""
import ast
import builtins
from datetime import datetime
from pathlib import Path
import platform
import socket
import sqlite3
import subprocess
import sys
import sysconfig
import types
import unittest

CANDIDATE = Path(__file__).resolve().parents[1]


def main():
    def deny(*_a, **_kw): raise AssertionError('real network, DB files or subprocess forbidden')
    real_connect = sqlite3.connect
    def memory_only(database, *args, **kwargs):
        if database != ':memory:' or kwargs.get('uri', False): deny()
        return real_connect(database, *args, **kwargs)
    sqlite3.connect = sqlite3.dbapi2.connect = memory_only
    socket.socket.connect = socket.socket.connect_ex = deny
    socket.getaddrinfo = socket.create_connection = deny
    class DeniedPopen:
        def __init__(self, *_a, **_kw): deny()
    subprocess.Popen = DeniedPopen
    platform.machine = lambda: 'synthetic'
    orig_import = builtins.__import__
    def safe_import(name, *args, **kwargs):
        level = args[2] if len(args) > 2 else kwargs.get('level', 0)
        if level == 0 and (name == 'app' or name.startswith('app.')): deny()
        return orig_import(name, *args, **kwargs)
    builtins.__import__ = safe_import
    sys.path.append(sysconfig.get_paths()['purelib'])
    from flask import Flask, Response, abort, jsonify, request, url_for
    from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, create_engine
    from sqlalchemy.orm import Query, declarative_base, joinedload, relationship, scoped_session, sessionmaker

    Base = declarative_base()
    engine = create_engine('sqlite:///:memory:')
    class SyntheticQuery(Query):
        def get_or_404(self, ident):
            result = self.get(ident)
            if result is None:
                abort(404)
            return result
    session = scoped_session(sessionmaker(bind=engine, expire_on_commit=False, query_cls=SyntheticQuery))
    Base.query = session.query_property()
    class Config(Base):
        __tablename__ = 'synthetic_config'
        id = Column(Integer, primary_key=True)
        receiver_search_key = Column(String, default='')
        receiver_type = Column(String, default='person')
        auto_send = Column(Integer, default=0)
    class Log(Base):
        __tablename__ = 'synthetic_log'
        id = Column(Integer, primary_key=True)
        config_id = Column(Integer, ForeignKey('synthetic_config.id'))
        config = relationship(Config)
        module_key = Column(String)
        order_id = Column(Integer)
        order_no = Column(String)
        receiver_name = Column(String)
        receiver_wechat_id = Column(String)
        created_at = Column(DateTime)
        status = Column(String)
        message = Column(String)
        sent_at = Column(DateTime)
        image_path = Column(String)
    Base.metadata.create_all(engine)
    service_path = CANDIDATE / 'app/services/wechat_poll_claim.py'
    service = types.ModuleType('services.wechat_poll_claim')
    exec(compile(service_path.read_text(encoding='utf-8'), str(service_path), 'exec'), service.__dict__)
    package = types.ModuleType('services')
    package.__path__ = []
    sys.modules['services'] = package
    sys.modules['services.wechat_poll_claim'] = service
    source = ast.parse((CANDIDATE / 'app/app.py').read_text(encoding='utf-8-sig'))
    names = {'_wechat_helper_task_payload', 'wechat_helper_tasks', 'wechat_helper_task_image', 'wechat_helper_report_task'}
    funcs = [n for n in source.body if isinstance(n, ast.FunctionDef) and n.name in names]
    if {n.name for n in funcs} != names: raise AssertionError('copied source list incomplete')
    for fn in funcs: fn.decorator_list = []
    fake_os = types.SimpleNamespace(sep='/', path=types.SimpleNamespace(
        abspath=lambda value: value, exists=lambda value: value == '/synthetic/image.png',
        basename=lambda value: value.rsplit('/', 1)[-1]))
    app = Flask('synthetic-wechat-claim')
    env = {'WechatShareLog': Log, 'joinedload': joinedload, 'request': request, 'jsonify': jsonify,
           'url_for': url_for, 'abort': abort, 'datetime': datetime, 'os': fake_os,
           'db': types.SimpleNamespace(session=session, engine=engine),
           '_wechat_helper_authorized': lambda: True,
           '_wechat_share_output_dir': lambda: '/synthetic',
           'send_file': lambda *_a, **_kw: Response(b'synthetic-image'),
           'app': types.SimpleNamespace(logger=types.SimpleNamespace(error=lambda *_a: None))}
    exec(compile(ast.fix_missing_locations(ast.Module(body=funcs, type_ignores=[])), '<copied-wechat-routes>', 'exec'), env)
    app.add_url_rule('/api/wechat_helper/tasks', 'wechat_helper_tasks', env['wechat_helper_tasks'])
    app.add_url_rule('/api/wechat_helper/task/<int:log_id>/image', 'wechat_helper_task_image', env['wechat_helper_task_image'])
    app.add_url_rule('/api/wechat_helper/task/<int:log_id>/report', 'wechat_helper_report_task',
                     env['wechat_helper_report_task'], methods=['POST'])

    class CandidateRoutes(unittest.TestCase):
        def setUp(self):
            session.query(Log).delete()
            session.add_all([Log(id=1, module_key='in_order', order_id=1, order_no='SYNTHETIC',
                                 created_at=datetime(2026, 1, 1), status='queued_v2', message='原诊断',
                                 image_path='/synthetic/image.png'),
                             Log(id=2, module_key='in_order', order_id=2, order_no='OLD',
                                 created_at=datetime(2025, 1, 1), status='pending', message='历史待核对',
                                 image_path='/synthetic/image.png')])
            session.commit()
            self.client = app.test_client()

        def test_old_helper_is_rejected_and_historical_pending_never_claimed(self):
            response = self.client.get('/api/wechat_helper/tasks')
            self.assertEqual(response.status_code, 426)
            self.assertEqual(session.get(Log, 1).status, 'queued_v2')
            self.assertEqual(session.get(Log, 2).status, 'pending')

        def test_claim_token_binds_image_and_receipt_and_no_replay(self):
            response = self.client.get('/api/wechat_helper/tasks', headers={'X-Wechat-Helper-Protocol': '2'})
            self.assertEqual(response.status_code, 200)
            tasks = response.get_json()['tasks']
            self.assertEqual([t['id'] for t in tasks], [1])
            token = tasks[0]['claim_token']
            self.assertEqual(len(token), 64)
            self.assertNotIn(token, session.get(Log, 1).message)
            self.assertEqual(session.get(Log, 1).status, 'sending')
            self.assertEqual(self.client.get('/api/wechat_helper/tasks', headers={'X-Wechat-Helper-Protocol': '2'}).get_json()['tasks'], [])
            image = '/api/wechat_helper/task/1/image'
            self.assertEqual(self.client.get(image).status_code, 404)
            self.assertEqual(self.client.get(image, headers={'X-Wechat-Task-Claim': token}).status_code, 200)
            self.assertEqual(self.client.get(image, headers={'X-Wechat-Task-Claim': token}).status_code, 404)
            report = '/api/wechat_helper/task/1/report'
            self.assertEqual(self.client.post(report, json={'status':'sent'}).status_code, 409)
            self.assertEqual(self.client.post(report, headers={'X-Wechat-Task-Claim': token}, json={'status':'ready','msg':'合成'}).status_code, 200)
            session.expire_all()
            self.assertEqual(session.get(Log, 1).status, 'uncertain')
            self.assertEqual(session.get(Log, 1).message, '原诊断\n回报：合成')
            self.assertEqual(self.client.post(report, headers={'X-Wechat-Task-Claim': token}, json={'status':'sent'}).status_code, 409)

        def test_claim_commit_failure_never_returns_unconfirmed_token(self):
            class FaultSession:
                def __init__(self, after_commit): self.after_commit = after_commit
                def __getattr__(self, name): return getattr(session, name)
                def commit(self):
                    if self.after_commit: session.commit()
                    raise RuntimeError('synthetic commit fault')
            for after in (False, True):
                with self.subTest(after_commit=after):
                    session.query(Log).filter_by(id=1).update({'status':'queued_v2','message':'原诊断'})
                    session.commit()
                    env['db'].session = FaultSession(after)
                    try:
                        response = self.client.get('/api/wechat_helper/tasks', headers={'X-Wechat-Helper-Protocol': '2'})
                    finally:
                        env['db'].session = session
                    self.assertEqual(response.status_code, 503)
                    self.assertNotIn('claim_token', response.get_data(as_text=True))
                    session.expire_all()
                    self.assertEqual(session.get(Log, 1).status, 'sending' if after else 'queued_v2')
                    if after:
                        self.assertEqual(self.client.get('/api/wechat_helper/tasks', headers={'X-Wechat-Helper-Protocol': '2'}).get_json()['tasks'], [])

        def test_receipt_commit_failure_keeps_sending_or_committed_result(self):
            class FaultSession:
                def __init__(self, after_commit): self.after_commit = after_commit
                def __getattr__(self, name): return getattr(session, name)
                def commit(self):
                    if self.after_commit: session.commit()
                    raise RuntimeError('synthetic commit fault')
            for after in (False, True):
                with self.subTest(after_commit=after):
                    session.query(Log).filter_by(id=1).update({'status':'queued_v2','message':'原诊断'})
                    session.commit()
                    token = self.client.get('/api/wechat_helper/tasks', headers={'X-Wechat-Helper-Protocol': '2'}).get_json()['tasks'][0]['claim_token']
                    self.assertEqual(self.client.get('/api/wechat_helper/task/1/image',
                                     headers={'X-Wechat-Task-Claim': token}).status_code, 200)
                    env['db'].session = FaultSession(after)
                    try:
                        response = self.client.post('/api/wechat_helper/task/1/report',
                            headers={'X-Wechat-Task-Claim': token}, json={'status':'ready','msg':'合成'})
                    finally:
                        env['db'].session = session
                    self.assertEqual(response.status_code, 500)
                    session.expire_all()
                    self.assertEqual(session.get(Log, 1).status, 'uncertain' if after else 'delivery_started')
                    self.assertEqual(self.client.get('/api/wechat_helper/tasks', headers={'X-Wechat-Helper-Protocol': '2'}).get_json()['tasks'], [])

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(CandidateRoutes)
    if suite.countTestCases() != 4: raise SystemExit('synthetic test list incomplete')
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    session.remove()
    engine.dispose()
    return not result.wasSuccessful()


if __name__ == '__main__': raise SystemExit(main())


def test_wechat_claim_candidate_routes_20261109_runs_against_actual_source(tmp_path):
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
