"""Real print-alert function raced with fake UI/delivery and no real I/O."""
import ast
from datetime import date, datetime, timedelta
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import threading
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def deny(*_a, **_kw): raise AssertionError('network, DB, subprocess forbidden')


class PrintAlertConcurrentSend(unittest.TestCase):
    def test_two_workers_cannot_both_send_before_first_log_is_saved(self):
        with patch.object(socket.socket, 'connect', deny), patch.object(socket.socket, 'connect_ex', deny), \
             patch.object(socket, 'getaddrinfo', deny), patch.object(socket, 'create_connection', deny), \
             patch.object(sqlite3, 'connect', deny), patch.object(subprocess, 'Popen', deny):
            candidate = '--candidate' in sys.argv
            source_path = (Path(r'C:\Users\Administrator\AppData\Local\Temp\wms-wechat-claim-src-vky5oct6')
                           / 'app/routes/print_alerts.py') if candidate else ROOT / 'app/routes/print_alerts.py'
            source = ast.parse(source_path.read_text(encoding='utf-8-sig'))
            functions = [n for n in source.body if isinstance(n, ast.FunctionDef) and n.name == 'push_print_alert_wechat']
            self.assertEqual(len(functions), 1)
            barrier = threading.Barrier(2)
            sent, logs, errors = [], [], []
            class Field:
                def __eq__(self, _value): return self
                def __ge__(self, _value): return self
            class Query:
                def filter(self, *_args): return self
                def first(self): barrier.wait(timeout=3); return None
            class Log:
                module_key, created_at, query = Field(), Field(), Query()
                def __init__(self, **kwargs): self.__dict__.update(kwargs)
            fake = types.ModuleType('app')
            fake.WechatShareLog = Log
            fake.get_system_setting_bool = lambda *_a: True
            fake.get_system_setting_int = lambda *_a: 10
            fake._wechat_share_default_config = lambda: types.SimpleNamespace(id=1, receiver_name='', receiver_wechat_id='')
            fake._wechat_share_send_image = lambda *_a: (sent.append('synthetic') or ('sent', 'ok', 'synthetic'))
            parent = types.ModuleType('services'); parent.__path__ = []
            reserve_service = types.ModuleType('services.print_alert_reserve')
            reservation_lock, reserved = threading.Lock(), []
            def reserve(_db, _log, _metadata, _interval):
                barrier.wait(timeout=3)
                with reservation_lock:
                    if reserved: return None
                    reserved.append(1)
                    return 1
            reserve_service.reserve_alert = reserve
            reserve_service.attach_alert_image = lambda *_args: True
            reserve_service.finish_alert = lambda *_args: True
            scope = {'db': types.SimpleNamespace(session=types.SimpleNamespace(add=logs.append, commit=lambda: None)),
                     'datetime': datetime, 'date': date, 'timedelta': timedelta,
                     '_render_alert_image': lambda _n: 'synthetic.png'}
            exec(compile(ast.fix_missing_locations(ast.Module(body=functions, type_ignores=[])),
                         '<synthetic-alert-race>', 'exec'), scope)
            def worker():
                try: scope['push_print_alert_wechat'](types.SimpleNamespace(id=1, title='synthetic'))
                except Exception as exc: errors.append(exc)
            with patch.dict(sys.modules, {'app': fake, 'services': parent,
                                         'services.print_alert_reserve': reserve_service}), \
                 patch('os.path.exists', return_value=False), patch('os.path.isfile', return_value=True), \
                 patch('os.path.getsize', return_value=1):
                threads = [threading.Thread(target=worker) for _ in range(2)]
                for thread in threads: thread.start()
                for thread in threads: thread.join(timeout=5)
            self.assertFalse(any(thread.is_alive() for thread in threads))
            self.assertEqual(errors, [])
            self.assertEqual(sent, ['synthetic'], '并发检查通过后不得同时发送两次')


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(PrintAlertConcurrentSend)
    if suite.countTestCases() != 1: raise SystemExit('synthetic test list incomplete')
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
