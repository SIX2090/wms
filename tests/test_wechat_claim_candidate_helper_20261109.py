"""Copied helper's real poll function with fake HTTP and no real delivery."""
import ast
import logging
from pathlib import Path
import socket
import sqlite3
import subprocess
import types
import unittest
from unittest.mock import patch

CANDIDATE = Path(__file__).resolve().parents[1]


def deny(*_a, **_kw): raise AssertionError('network, DB and child processes forbidden')


class HelperCandidateTests(unittest.TestCase):
    def setUp(self):
        for target, name in ((socket.socket, 'connect'), (socket.socket, 'connect_ex'),
                             (socket, 'getaddrinfo'), (socket, 'create_connection'),
                             (sqlite3, 'connect'), (subprocess, 'Popen')):
            guard = patch.object(target, name, deny)
            guard.start()
            self.addCleanup(guard.stop)
        source = ast.parse((CANDIDATE / 'app/wechat_helper.py').read_text(encoding='utf-8-sig'))
        names = {'poll_once', '_WmsReportUncertain', '_require_wms_response', '_require_wms_report_response'}
        nodes = [n for n in source.body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in names]
        self.assertEqual({n.name for n in nodes}, names)
        self.calls, self.sent = [], []
        self.token = 'a' * 64
        self.task = {'id': 1, 'claim_token': self.token,
                     'image_url': 'https://evil.invalid/image', 'report_url': 'https://evil.invalid/report'}
        self.image_status = 200
        self.lost_report = False
        test = self
        class Response:
            def __init__(self, status=200, body=None):
                self.status_code, self.body, self.content = status, body, b'synthetic-image'
            def json(self): return self.body
            def raise_for_status(self):
                if self.status_code >= 400: raise ValueError('synthetic HTTP error')
        class Session:
            def __enter__(self): return self
            def __exit__(self, *_a): pass
            def get(self, url, **kwargs):
                test.calls.append(('get', url, kwargs))
                if url.endswith('/tasks'):
                    return Response(body={'status': 'success', 'tasks': [test.task]})
                return Response(status=test.image_status)
            def post(self, url, **kwargs):
                test.calls.append(('post', url, kwargs))
                if test.lost_report: raise RuntimeError('synthetic lost reply')
                return Response(body={'status':'success'})
        self.env = {'_WmsSession': Session, 'WMS_BASE_URL': 'https://synthetic.invalid',
                    'helper_headers': lambda: {'X-Wechat-Helper-Token': 'synthetic'},
                    'absolute_wms_url': lambda path: 'https://synthetic.invalid' + path,
                    '_LOOPBACK_NO_PROXY': {}, 'logger': logging.getLogger('synthetic'),
                    'send_image_task': lambda content, task: (self.sent.append((content, task)) or
                                                               ('ready', 'ok', 'synthetic'))}
        exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])),
                     '<copied-helper>', 'exec'), self.env)

    def test_token_is_sent_only_to_canonical_endpoints_without_redirects(self):
        self.assertEqual(self.env['poll_once'](), 1)
        self.assertEqual(len(self.sent), 1)
        self.assertEqual([c[1] for c in self.calls], ['https://synthetic.invalid/api/wechat_helper/tasks',
            'https://synthetic.invalid/api/wechat_helper/task/1/image',
            'https://synthetic.invalid/api/wechat_helper/task/1/report'])
        self.assertEqual(self.calls[0][2]['headers']['X-Wechat-Helper-Protocol'], '2')
        for _, _, kw in self.calls:
            self.assertFalse(kw['allow_redirects'])
        for _, _, kw in self.calls[1:]:
            self.assertEqual(kw['headers']['X-Wechat-Task-Claim'], self.token)

    def test_lost_receipt_never_sends_second_report_or_task(self):
        self.lost_report = True
        with self.assertRaises(self.env['_WmsReportUncertain']): self.env['poll_once']()
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(sum(call[0] == 'post' for call in self.calls), 1)

    def test_image_redirect_is_not_followed_or_delivered(self):
        self.image_status = 307
        self.assertEqual(self.env['poll_once'](), 0)
        self.assertEqual(self.sent, [])
        self.assertEqual(sum(call[0] == 'get' for call in self.calls), 2)
        self.assertEqual(self.calls[-1][2]['json']['status'], 'failed')

    def test_old_response_without_claim_token_fails_closed(self):
        self.task.pop('claim_token')
        with self.assertRaises(self.env['_WmsReportUncertain']): self.env['poll_once']()
        self.assertEqual(self.sent, [])
        self.assertEqual(len(self.calls), 1)


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(HelperCandidateTests)
    if suite.countTestCases() != 4: raise SystemExit('synthetic test list incomplete')
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
