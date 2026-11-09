"""Exercise the extracted report endpoint with real SQLAlchemy and a memory DB."""
import ast
import hashlib
from contextlib import ExitStack
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
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def refuse(*_args, **_kwargs):
    raise AssertionError('external databases, networks and child processes are forbidden')


class ReportQuerySQLAlchemy(unittest.TestCase):
    def setUp(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(socket.socket, 'connect', refuse))
        stack.enter_context(patch.object(socket.socket, 'connect_ex', refuse))
        stack.enter_context(patch.object(socket, 'getaddrinfo', refuse))
        stack.enter_context(patch.object(subprocess, 'Popen', refuse))
        stack.enter_context(patch.object(platform, 'win32_ver', lambda *_a, **_k: ('10', '10.0.0', '', '')))
        original_connect = sqlite3.connect
        def memory_only(path, *args, **kwargs):
            if path != ':memory:':
                return refuse()
            return original_connect(path, *args, **kwargs)
        stack.enter_context(patch.object(sqlite3, 'connect', memory_only))
        stack.enter_context(patch.object(sys, 'path', [sysconfig.get_path('purelib'), *sys.path]))
        from sqlalchemy import Column, Integer, String, DateTime, create_engine, update
        from sqlalchemy.orm import declarative_base, Session
        from flask_sqlalchemy.query import Query
        Base = declarative_base()
        class Log(Base):
            __tablename__ = 'synthetic_log'
            id = Column(Integer, primary_key=True)
            status = Column(String)
            message = Column(String)
            sent_at = Column(DateTime)
        owner = self
        class InstrumentedQuery(Query):
            def get_or_404(self, ident, description=None):
                row = super().get_or_404(ident, description=description)
                if owner.after_read:
                    owner.after_read()
                return row
        self.engine = create_engine('sqlite://', creator=lambda: sqlite3.connect(':memory:'))
        self.addCleanup(self.engine.dispose)
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine, query_cls=InstrumentedQuery)
        self.addCleanup(self.session.close)
        self.session.add(Log(id=1, status='sending', message='original'+chr(10)+'[claim-sha256:'+hashlib.sha256(('a'*64).encode()).hexdigest()+']'))
        self.session.commit()
        Log.query = self.session.query(Log)
        self.Log = Log
        self.update = update
        self.after_read = None
        self.payload = {'status': 'ready', 'msg': 'synthetic'}
        scope = {'_wechat_helper_authorized': lambda: True, 'WechatShareLog': Log,
                 'request': types.SimpleNamespace(get_json=lambda **_kw: self.payload, headers={'X-Wechat-Task-Claim':'a'*64}),
                 'db': types.SimpleNamespace(session=self.session), 'jsonify': lambda obj: obj,
                 'datetime': datetime,
                 'app': types.SimpleNamespace(logger=types.SimpleNamespace(error=lambda *_a: None))}
        tree = ast.parse((ROOT / 'app/app.py').read_text(encoding='utf-8'))
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                    and n.name == 'wechat_helper_report_task')
        node.decorator_list = []
        exec(compile(ast.Module(body=[node], type_ignores=[]), '<synthetic-orm>', 'exec'), scope)
        self.report = scope['wechat_helper_report_task']
        with self.engine.connect() as conn:
            self.assertTrue(all(not row[2] for row in conn.exec_driver_sql('PRAGMA database_list')))

    def test_ready_then_late_sent_is_not_overwritten(self):
        self.assertEqual(self.report(1)['status'], 'success')
        self.assertEqual(self.session.get(self.Log, 1).status, 'uncertain')
        self.payload = {'status': 'sent'}
        self.assertEqual(self.report(1)[1], 409)
        self.assertEqual(self.session.get(self.Log, 1).status, 'uncertain')

    def test_changed_state_between_read_and_update_is_not_overwritten(self):
        def transition():
            self.session.execute(self.update(self.Log).where(self.Log.id == 1)
                                 .values(status='sent', message='other worker'))
            self.session.commit()
        self.after_read = transition
        self.assertEqual(self.report(1)[1], 409)
        saved = self.session.get(self.Log, 1)
        self.assertEqual((saved.status, saved.message), ('sent', 'other worker'))

    def test_commit_failure_rolls_back_real_query_update(self):
        with patch.object(self.session, 'commit', side_effect=sqlite3.OperationalError('synthetic failure')):
            self.assertEqual(self.report(1)[1], 500)
        saved = self.session.get(self.Log, 1)
        self.assertEqual((saved.status, saved.message), ('sending', 'original'+chr(10)+'[claim-sha256:'+hashlib.sha256(('a'*64).encode()).hexdigest()+']'))


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ReportQuerySQLAlchemy)
    if suite.countTestCases() != 3:
        raise SystemExit('synthetic test list must be explicitly nonempty')
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
