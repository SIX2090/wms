"""Synthetic status checks: no network, database, files or WMS imports."""
import ast
import hashlib
from datetime import datetime
from io import BytesIO
from pathlib import Path
import os
import socket
import sqlite3
import subprocess
import types
import unittest
from unittest.mock import patch
from urllib.parse import urlparse


SOURCE = Path(__file__).resolve().parents[1] / 'app/app.py'


def refuse(*_args, **_kwargs):
    raise AssertionError('network, database and subprocess forbidden')


class ReadyConfirmation(unittest.TestCase):
    def setUp(self):
        for target, name in ((socket.socket, 'connect'), (socket.socket, 'connect_ex'),
                             (socket, 'getaddrinfo'), (sqlite3, 'connect'),
                             (subprocess, 'Popen')):
            guard = patch.object(target, name, refuse)
            guard.start()
            self.addCleanup(guard.stop)
        tree = ast.parse(SOURCE.read_text(encoding='utf-8-sig'))
        names = {'_wechat_share_send_image', 'wechat_helper_report_task'}
        functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
        self.assertEqual(len(functions), len(names))
        for function in functions:
            function.decorator_list = []
        self.original_message=chr(10)+'[claim-sha256:'+hashlib.sha256(('a'*64).encode()).hexdigest()+']'
        self.log = types.SimpleNamespace(status='sending', message=self.original_message, sent_at=None)
        self.payload = {'status': 'ready', 'msg': '已粘贴，请人工确认'}
        self.request = types.SimpleNamespace(get_json=lambda **_kwargs: self.payload,headers={'X-Wechat-Task-Claim':'a'*64})
        self.session = types.SimpleNamespace(commit=lambda: None, rollback=lambda: None)
        self.config = types.SimpleNamespace(helper_url='http://synthetic.invalid/send',
            sender_name='', sender_wechat_id='', receiver_name='synthetic', receiver_wechat_id='',
            receiver_search_key='synthetic', receiver_type='person', auto_send=False)
        response = types.SimpleNamespace(status_code=200, ok=True,
            json=lambda: {'status': 'ready', 'code': 'ok', 'msg': '已粘贴，请人工确认'})
        exceptions = types.SimpleNamespace(ConnectionError=type('ConnectionError', (Exception,), {}),
                                           Timeout=type('Timeout', (Exception,), {}))
        requests = types.SimpleNamespace(post=lambda *_args, **_kwargs: response, exceptions=exceptions)
        self.scope = {'app': types.SimpleNamespace(config={'WECHAT_HELPER_TOKEN': 'synthetic'},
                           logger=types.SimpleNamespace(warning=lambda *_a: None, error=lambda *_a: None)),
                      'requests': requests, 'os': os, 'urlparse': urlparse,
                      '_wechat_share_helper_url_allowed': lambda _url: True, '_LOOPBACK_NO_PROXY': {},
                      'request': self.request, 'datetime': datetime,
                      'db': types.SimpleNamespace(session=self.session), 'jsonify': lambda obj: obj,
                      '_wechat_helper_authorized': lambda: True}
        log = self.log
        class Field:
            def __init__(self,name): self.name=name
            def __eq__(self,value): return (self.name,'=',value)
            def in_(self,values): return (self.name,'in',tuple(values))

        class Query:
            def get_or_404(self, _id):
                return log

            def filter_by(self, **conditions):
                self.conditions = conditions
                return self

            def filter(self,*conditions):
                self.conditions=conditions
                return self

            def update(self, values, synchronize_session=False):
                assert synchronize_session is False
                if self.conditions != (('id','=',1),('status','in',('sending','delivery_started')),('message','=',log.message)) or log.status not in ('sending','delivery_started'):
                    return 0
                for key, value in values.items():
                    setattr(log, key, value)
                return 1
        self.scope['WechatShareLog'] = types.SimpleNamespace(query=Query(),id=Field('id'),status=Field('status'),message=Field('message'))
        exec(compile(ast.fix_missing_locations(ast.Module(body=functions, type_ignores=[])),
                     '<synthetic-wechat-status>', 'exec'), self.scope)

    def test_direct_ready_is_not_pending_queue(self):
        with patch('builtins.open', return_value=BytesIO(b'synthetic image')):
            status, code, message = self.scope['_wechat_share_send_image'](self.config, 'synthetic.png')
        self.assertEqual(status, 'uncertain')
        self.assertEqual(code, 'ok')
        self.assertIn('人工确认', message)

    def test_poll_report_ready_is_not_pending_queue(self):
        result = self.scope['wechat_helper_report_task'](1)
        self.assertEqual(result['status'], 'success')
        self.assertEqual(self.log.status, 'uncertain')
        self.assertIn('人工确认', self.log.message)

    def test_pending_report_is_held_for_confirmation(self):
        self.payload = {'status': 'pending', 'msg': '等待执行'}
        self.scope['wechat_helper_report_task'](1)
        self.assertEqual(self.log.status, 'uncertain')
        self.assertIn('核对', self.log.message)

    def test_sent_report_preserves_sent_state(self):
        self.payload = {'status': 'sent', 'msg': '已发送'}
        self.scope['wechat_helper_report_task'](1)
        self.assertEqual(self.log.status, 'sent')
        self.assertIsNotNone(self.log.sent_at)

    def test_late_pending_does_not_requeue_ready_task(self):
        self.log.status = 'uncertain'
        self.payload = {'status': 'pending', 'msg': '迟到回报'}
        response, status = self.scope['wechat_helper_report_task'](1)
        self.assertEqual(status, 409)
        self.assertEqual(response['status'], 'error')
        self.assertEqual(self.log.status, 'uncertain')

    def test_late_failure_does_not_override_sent(self):
        self.log.status = 'sent'
        self.payload = {'status': 'error', 'msg': '迟到回报'}
        response, status = self.scope['wechat_helper_report_task'](1)
        self.assertEqual(status, 409)
        self.assertEqual(response['status'], 'error')
        self.assertEqual(self.log.status, 'sent')

    def test_reported_error_is_not_asserted_safe_to_retry(self):
        self.payload = {'status': 'error', 'msg': 'synthetic failure'}
        self.scope['wechat_helper_report_task'](1)
        self.assertEqual(self.log.status, 'uncertain')
        self.assertIn('核对', self.log.message)
        self.assertIn('synthetic failure', self.log.message)


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ReadyConfirmation)
    if suite.countTestCases() != 7:
        raise SystemExit('synthetic test list is incomplete')
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
