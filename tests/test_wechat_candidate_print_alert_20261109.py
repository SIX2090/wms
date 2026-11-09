"""Copied print-alert entrypoint on synthetic objects only."""
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

CANDIDATE = Path(__file__).resolve().parents[1]


def deny(*_a, **_kw): raise AssertionError('network, DB and subprocess forbidden')


class CandidatePrintAlert(unittest.TestCase):
    def test_only_confirmed_preflight_enters_new_queue(self):
        with patch.object(socket.socket, 'connect', deny), patch.object(socket.socket, 'connect_ex', deny), \
             patch.object(socket, 'getaddrinfo', deny), patch.object(socket, 'create_connection', deny), \
             patch.object(sqlite3, 'connect', deny), patch.object(subprocess, 'Popen', deny):
            source = ast.parse((CANDIDATE / 'app/routes/print_alerts.py').read_text(encoding='utf-8-sig'))
            nodes = [n for n in source.body if isinstance(n, ast.FunctionDef) and n.name == 'push_print_alert_wechat']
            self.assertEqual(len(nodes), 1)
            class Field:
                def __eq__(self, _other): return self
                def __ge__(self, _other): return self
            class Query:
                def filter(self, *_args): return self
                def first(self): return None
            class Log:
                module_key, created_at, query = Field(), Field(), Query()
                def __init__(self, **kwargs): self.__dict__.update(kwargs)
            captured = []
            fake = types.ModuleType('app')
            fake.WechatShareLog = Log
            fake.get_system_setting_bool = lambda *_a: True
            fake.get_system_setting_int = lambda *_a: 10
            fake._wechat_share_default_config = lambda: types.SimpleNamespace(id=1, receiver_name='', receiver_wechat_id='')
            session = types.SimpleNamespace(add=captured.append, commit=lambda: None)
            parent = types.ModuleType('services'); parent.__path__ = []
            service = types.ModuleType('services.print_alert_reserve')
            def reserve(_db, _log, metadata, _interval):
                captured.append(Log(**metadata, status='sending'))
                return len(captured)
            def finish(_db, _log, ident, status, message):
                captured[ident - 1].status = status
                captured[ident - 1].message = message
                return True
            service.reserve_alert, service.attach_alert_image, service.finish_alert = reserve, (lambda *_a: True), finish
            env = {'db': types.SimpleNamespace(session=session), 'datetime': datetime, 'date': date,
                   'timedelta': timedelta, '_render_alert_image': lambda _n: 'synthetic.png'}
            exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), '<copied-print-alert>', 'exec'), env)
            cases = [('pending', 'helper_not_configured', 'queued_v2'),
                     ('failed', 'invalid_helper_url', 'queued_v2'),
                     ('failed', 'helper_offline', 'uncertain'),
                     ('failed', 'helper_timeout', 'uncertain'),
                     ('failed', 'send_key_failed', 'uncertain'),
                     ('failed', 'token_not_configured', 'failed'), ('sent', 'ok', 'sent')]
            for status, code, expected in cases:
                with self.subTest(code=code):
                    fake._wechat_share_send_image = lambda *_a: (status, code, '合成信息')
                    with patch.dict(sys.modules, {'app': fake, 'services': parent,
                                                 'services.print_alert_reserve': service}), \
                         patch('os.path.isfile', return_value=True), patch('os.path.getsize', return_value=1):
                        self.assertTrue(env['push_print_alert_wechat'](types.SimpleNamespace(id=1, title='合成告警')))
                    self.assertEqual(captured[-1].status, expected)


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(CandidatePrintAlert)
    if suite.countTestCases() != 1: raise SystemExit('synthetic test list incomplete')
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
