"""Real cleanup-selection function on synthetic rows, no database or I/O."""
import ast
from datetime import date, datetime
from hashlib import sha256
import json
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def deny(*_args, **_kwargs):
    raise AssertionError('network, DB and subprocess forbidden')


class QueueCleanupStatusTests(unittest.TestCase):
    def test_active_v2_log_protects_other_logs_of_same_key(self):
        with patch.object(socket.socket, 'connect', deny), patch.object(socket.socket, 'connect_ex', deny), \
             patch.object(socket, 'getaddrinfo', deny), patch.object(socket, 'create_connection', deny), \
             patch.object(sqlite3, 'connect', deny), patch.object(subprocess, 'Popen', deny):
            source = (Path(r'C:\Users\Administrator\AppData\Local\Temp\wms-wechat-claim-src-vky5oct6')
                      / 'app/services/wechat_share_cleanup.py') if '--candidate' in sys.argv else (
                      ROOT / 'app/services/wechat_share_cleanup.py')
            tree = ast.parse(source.read_text(encoding='utf-8-sig'))
            funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in ('_key', '_selection')]
            self.assertEqual(len(funcs), 2)
            old = types.SimpleNamespace(id=1, status='failed', module_key='in_order', order_id=7,
                                        share_date=date(2026, 11, 9), message='synthetic',
                                        image_path='/virtual/a.png', created_at=datetime(2025, 1, 1))
            queued = types.SimpleNamespace(id=2, status='queued_v2', module_key='in_order', order_id=7,
                                           share_date=date(2026, 11, 9), message='synthetic queued',
                                           image_path='/virtual/b.png', created_at=datetime(2025, 1, 1))
            class Query:
                def __init__(self, rows): self.rows = rows
                def order_by(self, *_args): return self
                def all(self): return self.rows
            Log = type('Log', (), {'id': object()})
            Dispatch = type('Dispatch', (), {})
            class Session:
                def query(self, model): return Query([old, queued] if model is Log else [])
            values = {}
            for name in ('_PROTECTED', '_REMOVABLE'):
                assignment = next(n for n in tree.body if isinstance(n, ast.Assign)
                                  and any(isinstance(t, ast.Name) and t.id == name for t in n.targets))
                values[name] = ast.literal_eval(assignment.value)
            env = {'Log': Log, 'Dispatch': Dispatch, 'sha256': sha256, 'json': json, **values}
            exec(compile(ast.fix_missing_locations(ast.Module(body=funcs, type_ignores=[])),
                         '<synthetic-cleanup-selection>', 'exec'), env)
            _logs, _claims, selected, _fingerprint, _count = env['_selection'](Session(), None)
            self.assertEqual(selected, [], '待领取任务必须保护同业务键的历史记录')


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(QueueCleanupStatusTests)
    if suite.countTestCases() != 1:
        raise SystemExit('synthetic test list is incomplete or empty')
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
