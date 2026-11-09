"""Offline regression for uncertain print-alert deliveries; no WMS app import."""
import ast
from datetime import date, datetime, timedelta
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import types
import unittest
from unittest.mock import patch


SOURCE = Path(__file__).resolve().parents[1] / 'app/routes/print_alerts.py'


def refuse(*_args, **_kwargs):
    raise AssertionError('network, database and subprocess are forbidden')


class Field:
    def __eq__(self, other):
        return ('eq', other)

    def __ge__(self, other):
        return ('ge', other)


class Query:
    def filter(self, *_args):
        return self

    def first(self):
        return None


class Log:
    module_key = Field()
    created_at = Field()
    query = Query()

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class Session:
    def __init__(self):
        self.logs = []
        self.commits = 0

    def add(self, value):
        self.logs.append(value)

    def commit(self):
        self.commits += 1


class PrintAlertUncertainSend(unittest.TestCase):
    def setUp(self):
        self.stack = []
        for target, name in ((socket.socket, 'connect'), (socket.socket, 'connect_ex'),
                             (socket, 'getaddrinfo'), (sqlite3, 'connect'),
                             (subprocess, 'Popen')):
            guard = patch.object(target, name, refuse)
            guard.start()
            self.addCleanup(guard.stop)
        self.session = Session()
        self.config = types.SimpleNamespace(id=1, receiver_name='synthetic', receiver_wechat_id='')
        self.fake_app = types.ModuleType('app')
        self.fake_app.WechatShareLog = Log
        self.fake_app.get_system_setting_bool = lambda *_args: True
        self.fake_app.get_system_setting_int = lambda *_args: 10
        self.fake_app._wechat_share_default_config = lambda: self.config
        self.tree = ast.parse(SOURCE.read_text(encoding='utf-8-sig'))
        func = next(n for n in self.tree.body if isinstance(n, ast.FunctionDef)
                    and n.name == 'push_print_alert_wechat')
        namespace = {'db': types.SimpleNamespace(session=self.session),
                     'datetime': datetime, 'date': date, 'timedelta': timedelta,
                     '_render_alert_image': lambda _notification: 'synthetic-only.png'}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[func], type_ignores=[])),
                     '<synthetic-alert>', 'exec'), namespace)
        self.push = namespace['push_print_alert_wechat']

    def run_case(self, status, code, message):
        self.fake_app._wechat_share_send_image = lambda *_args: (status, code, message)
        notification = types.SimpleNamespace(title='synthetic alert')
        with patch.dict(sys.modules, {'app': self.fake_app}), \
             patch('os.path.exists', return_value=False):
            self.assertTrue(self.push(notification))
        self.assertEqual(self.session.commits, 1)
        self.assertEqual(len(self.session.logs), 1)
        return self.session.logs[0]

    def test_connection_lost_after_possible_delivery_is_not_requeued(self):
        log = self.run_case('failed', 'helper_offline', '发送结果待核对；不自动重试')
        self.assertEqual(log.status, 'uncertain')
        self.assertIn('核对', log.message)
        self.assertIn('helper_offline', log.message)

    def test_confirmed_preflight_error_still_queues(self):
        log = self.run_case('failed', 'invalid_helper_url', 'invalid')
        self.assertEqual(log.status, 'pending')

    def test_missing_helper_already_returns_pending(self):
        log = self.run_case('pending', 'helper_not_configured', '待发送')
        self.assertEqual(log.status, 'pending')

    def test_timeout_needs_manual_confirmation(self):
        log = self.run_case('failed', 'helper_timeout', '请核对')
        self.assertEqual(log.status, 'uncertain')
        self.assertIn('核对', log.message)

    def test_helper_reported_error_needs_manual_confirmation(self):
        log = self.run_case('failed', 'send_key_failed', '按键失败')
        self.assertEqual(log.status, 'uncertain')
        self.assertIn('核对', log.message)
        self.assertIn('send_key_failed', log.message)

    def test_preflight_auth_failure_remains_failed(self):
        log = self.run_case('failed', 'token_not_configured', '未配置')
        self.assertEqual(log.status, 'failed')

    def test_sent_stays_sent(self):
        log = self.run_case('sent', 'ok', '已发送')
        self.assertEqual(log.status, 'sent')
        self.assertIsNotNone(log.sent_at)


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(PrintAlertUncertainSend)
    if suite.countTestCases() != 7:
        raise SystemExit('synthetic test list is incomplete')
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
