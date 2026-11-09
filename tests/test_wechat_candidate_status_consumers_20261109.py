"""Copied status consumers with synthetic rows, no application or database import."""
import ast
from datetime import date
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import types
import unittest
from unittest.mock import patch

CANDIDATE = Path(__file__).resolve().parents[1]


def deny(*_a, **_kw): raise AssertionError('network, DB, and subprocess forbidden')


class StatusConsumers(unittest.TestCase):
    def test_today_summary_counts_delivery_started_as_uncertain(self):
        with patch.object(socket.socket, 'connect', deny), patch.object(socket.socket, 'connect_ex', deny), \
             patch.object(socket, 'getaddrinfo', deny), patch.object(socket, 'create_connection', deny), \
             patch.object(sqlite3, 'connect', deny), patch.object(subprocess, 'Popen', deny):
            source = ast.parse((CANDIDATE / 'app/app.py').read_text(encoding='utf-8-sig'))
            nodes = [n for n in source.body if isinstance(n, ast.FunctionDef) and n.name == 'run_wechat_share_for_today']
            self.assertEqual(len(nodes), 1)
            log = types.SimpleNamespace(id=1, status='delivery_started')
            scope = {'_wechat_share_master_enabled': lambda: True,
                     '_wechat_share_today_in_orders': lambda: [object()],
                     '_wechat_share_wecom_webhook': lambda: '',
                     '_wechat_share_order': lambda *_a, **_kw: (log, 'skipped'),
                     'db': types.SimpleNamespace(session=types.SimpleNamespace(commit=lambda: None))}
            exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])),
                         '<copied-wechat-summary>', 'exec'), scope)
            result = scope['run_wechat_share_for_today'](config=types.SimpleNamespace(enabled=True, share_in_order=True))
            self.assertEqual(result['uncertain'], 1)

    def test_sending_filter_includes_delivery_started(self):
        with patch.object(socket.socket, 'connect', deny), patch.object(socket.socket, 'connect_ex', deny), \
             patch.object(socket, 'getaddrinfo', deny), patch.object(socket, 'create_connection', deny), \
             patch.object(sqlite3, 'connect', deny), patch.object(subprocess, 'Popen', deny):
            source = ast.parse((CANDIDATE / 'app/routes/wechat_share.py').read_text(encoding='utf-8-sig'))
            nodes = [n for n in ast.walk(source) if isinstance(n, ast.FunctionDef) and n.name == 'wechat_share_page']
            self.assertEqual(len(nodes), 1)
            nodes[0].decorator_list = []
            filters = []
            class Field:
                def in_(self, value): return ('in', tuple(value))
                def __eq__(self, value): return ('eq', value)
                def desc(self): return self
            class Query:
                def filter(self, *args): filters.append(args); return self
                def filter_by(self, **_kwargs): return self
                def count(self): return 0
                def order_by(self, *_args): return self
                def limit(self, *_args): return self
                def all(self): return []
            log = types.SimpleNamespace(status=Field(), created_at=Field(), share_date=Field(), query=Query())
            fake = types.ModuleType('app')
            fake.WechatShareLog = log
            fake._wechat_share_default_config = lambda: types.SimpleNamespace(helper_url='')
            fake._wechat_share_master_enabled = lambda: False
            fake._wechat_share_today_in_orders = lambda: []
            fake._wechat_share_get_helper_health = lambda *_a: {}
            fake._wechat_share_wecom_webhook = lambda: ''
            for name in ('_wechat_share_log_message_summary', '_wechat_share_log_status_label',
                         '_wechat_share_log_trigger_label', 'format_file_size'):
                setattr(fake, name, lambda x: x)
            fake.date, fake.os = date, types.SimpleNamespace(environ={})
            fake.request = types.SimpleNamespace(args=types.SimpleNamespace(
                get=lambda name, default=None, **_kw: 'sending' if name == 'status' else default))
            fake.render_template = lambda _name, **kwargs: kwargs
            service = types.ModuleType('services.wechat_poll_claim')
            service.visible_message = lambda _status, message: message
            parent = types.ModuleType('services'); parent.__path__ = []
            scope = {}
            exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])),
                         '<copied-wechat-status-page>', 'exec'), scope)
            with patch.dict(sys.modules, {'app': fake, 'services': parent, 'services.wechat_poll_claim': service}):
                result = scope['wechat_share_page']()
            self.assertEqual(result['log_filters']['status'], 'sending')
            self.assertEqual(filters[0], (('in', ('sending', 'delivery_started')),))


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(StatusConsumers)
    if suite.countTestCases() != 2: raise SystemExit('synthetic test list incomplete')
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
