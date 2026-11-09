"""Actual extracted report function against a private synthetic SQLite memory DB."""
import ast
import hashlib
from datetime import datetime
from pathlib import Path
import socket
import sqlite3
import subprocess
import types
import unittest
from unittest.mock import patch


SOURCE = Path(__file__).resolve().parents[1] / 'app/app.py'


def refuse(*_args, **_kwargs):
    raise AssertionError('network, other databases and subprocess forbidden')


class ReportCAS(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.addCleanup(self.db.close)
        self.db.execute('CREATE TABLE synthetic_log (id INTEGER PRIMARY KEY, status TEXT, message TEXT, sent_at TEXT)')
        self.original_message='old'+chr(10)+'[claim-sha256:'+hashlib.sha256(('a'*64).encode()).hexdigest()+']'
        self.db.execute("INSERT INTO synthetic_log VALUES (1, 'sending', ?, NULL)",(self.original_message,))
        self.db.commit()
        self.assertTrue(all(not row[2] for row in self.db.execute('PRAGMA database_list')))
        for target, name in ((socket.socket, 'connect'), (socket.socket, 'connect_ex'),
                             (socket, 'getaddrinfo'), (sqlite3, 'connect'),
                             (sqlite3.dbapi2, 'connect'), (subprocess, 'Popen')):
            guard = patch.object(target, name, refuse)
            guard.start()
            self.addCleanup(guard.stop)
        conn = self.db
        self.after_read = None
        owner = self

        class Field:
            def __init__(self,name): self.name=name
            def __eq__(self,value): return (self.name,'=',value)
            def in_(self,values): return (self.name,'in',tuple(values))

        class Query:
            def get_or_404(self, log_id):
                found = conn.execute('SELECT status,message FROM synthetic_log WHERE id=?', (log_id,)).fetchone()
                if not found:
                    raise LookupError('synthetic 404')
                if owner.after_read:
                    owner.after_read()
                return types.SimpleNamespace(status=found[0],message=found[1])

            def filter_by(self, **where):
                self.where = where
                return self

            def filter(self,*conditions):
                self.conditions=conditions
                return self

            def update(self, values, synchronize_session=False):
                assert self.conditions==(('id','=',1),('status','in',('sending','delivery_started')),('message','=',owner.original_message))
                assert synchronize_session is False
                assert set(values) <= {'status', 'message', 'sent_at'}
                names = list(values)
                parameters = [values[name].isoformat() if isinstance(values[name], datetime) else values[name]
                              for name in names]
                sql = 'UPDATE synthetic_log SET ' + ', '.join(name + '=?' for name in names)
                return conn.execute(sql + ' WHERE id=? AND status IN (?,?) AND message=?',
                                    parameters + [1,'sending','delivery_started',owner.original_message]).rowcount

        self.session = types.SimpleNamespace(commit=self.db.commit, rollback=self.db.rollback)
        self.payload = {'status': 'ready', 'msg': 'synthetic ready'}
        self.scope = {'_wechat_helper_authorized': lambda: True,
                      'WechatShareLog': types.SimpleNamespace(query=Query(),id=Field('id'),status=Field('status'),message=Field('message')),
                      'request': types.SimpleNamespace(get_json=lambda **_kw: self.payload,headers={'X-Wechat-Task-Claim':'a'*64}),
                      'db': types.SimpleNamespace(session=self.session),
                      'jsonify': lambda obj: obj, 'datetime': datetime,
                      'app': types.SimpleNamespace(logger=types.SimpleNamespace(error=lambda *_a: None))}
        tree = ast.parse(SOURCE.read_text(encoding='utf-8-sig'))
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                        and n.name == 'wechat_helper_report_task')
        function.decorator_list = []
        exec(compile(ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[])),
                     '<synthetic-report>', 'exec'), self.scope)

    def current(self):
        return self.db.execute('SELECT status, message, sent_at FROM synthetic_log WHERE id=1').fetchone()

    def test_ready_commit_and_late_pending_cannot_requeue(self):
        self.assertEqual(self.scope['wechat_helper_report_task'](1)['status'], 'success')
        self.assertEqual(self.current()[:2], ('uncertain', 'old'+chr(10)+'回报：synthetic ready'))
        self.payload = {'status': 'pending', 'msg': 'late'}
        response, status = self.scope['wechat_helper_report_task'](1)
        self.assertEqual((response['status'], status), ('error', 409))
        self.assertEqual(self.current()[:2], ('uncertain', 'old'+chr(10)+'回报：synthetic ready'))

    def test_state_changes_after_read_before_atomic_update(self):
        def transition():
            self.db.execute("UPDATE synthetic_log SET status='sent', message='other worker' WHERE id=1")
            self.db.commit()
        self.after_read = transition
        response, status = self.scope['wechat_helper_report_task'](1)
        self.assertEqual((response['status'], status), ('error', 409))
        self.assertEqual(self.current()[:2], ('sent', 'other worker'))

    def test_commit_failure_rolls_back_update(self):
        def fail_commit():
            raise sqlite3.OperationalError('synthetic commit failure')
        self.session.commit = fail_commit
        response, status = self.scope['wechat_helper_report_task'](1)
        self.assertEqual((response['status'], status), ('error', 500))
        self.assertEqual(self.current()[:2], ('sending', self.original_message))


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ReportCAS)
    if suite.countTestCases() != 3:
        raise SystemExit('synthetic test list is incomplete')
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
