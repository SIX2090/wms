"""Execute actual old-image cleanup with entirely synthetic file and log objects."""
import ast
from datetime import datetime, timedelta
from pathlib import Path
import re
import socket
import sqlite3
import subprocess
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def deny(*_args, **_kwargs):
    raise AssertionError('network, real database and child processes forbidden')


class ActiveImageCleanupTests(unittest.TestCase):
    def test_expired_image_of_sending_task_is_not_deleted(self):
        with patch.object(socket.socket, 'connect', deny), patch.object(socket.socket, 'connect_ex', deny), \
             patch.object(socket, 'getaddrinfo', deny), patch.object(socket, 'create_connection', deny), \
             patch.object(sqlite3, 'connect', deny), patch.object(subprocess, 'Popen', deny):
            source = (Path(r'C:\Users\Administrator\AppData\Local\Temp\wms-wechat-claim-src-vky5oct6')
                      / 'app/app.py') if '--candidate' in sys.argv else ROOT / 'app/app.py'
            tree = ast.parse(source.read_text(encoding='utf-8-sig'))
            funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef)
                     and n.name == '_wechat_share_cleanup_old_images']
            self.assertEqual(len(funcs), 1)
            removed = []
            log = types.SimpleNamespace(status='sending', image_path='/virtual/synthetic.png', image_size=7)
            class Field:
                def in_(self, _paths): return self
            class Query:
                def filter(self, *_args): return self
                def all(self): return [log]
            fake_os = types.SimpleNamespace(listdir=lambda _folder: ['synthetic.png'],
                remove=removed.append, path=types.SimpleNamespace(join=lambda folder, name: folder + '/' + name,
                isfile=lambda _path: True,
                normcase=lambda path: path, realpath=lambda path: path,
                getmtime=lambda _path: (datetime.now() - timedelta(days=100)).timestamp()))
            env = {'datetime': datetime, '_WECHAT_SHARE_IMAGE_RETENTION_DAYS': 30,
                   '_WECHAT_SHARE_IMAGE_NAME_RE': re.compile('synthetic[.]png'),
                   '_wechat_share_output_dir': lambda: '/virtual', 'os': fake_os,
                   'WechatShareLog': types.SimpleNamespace(image_path=Field(), status=Field(), query=Query()),
                   'db': types.SimpleNamespace(engine=types.SimpleNamespace(dialect=types.SimpleNamespace(name='sqlite'),pool=object()),
                          session=types.SimpleNamespace(commit=lambda: None, rollback=lambda: None,
                                                        execute=lambda _query: None)),
                   'app': types.SimpleNamespace(logger=types.SimpleNamespace(info=lambda *_a: None))}
            exec(compile(ast.fix_missing_locations(ast.Module(body=funcs, type_ignores=[])),
                         '<synthetic-image-cleanup>', 'exec'), env)
            fake_sql = types.ModuleType('sqlalchemy')
            fake_sql.text = lambda query: query
            fake_orm = types.ModuleType('sqlalchemy.orm')
            class SyntheticSession:
                def __init__(self, _engine): pass
                def __enter__(self): return self
                def __exit__(self, *_a): pass
                def execute(self, _query): pass
                def query(self, _model): return Query()
                def commit(self): pass
            fake_orm.Session = SyntheticSession
            fake_pool = types.ModuleType('sqlalchemy.pool')
            fake_pool.StaticPool = type('StaticPool', (), {})
            fake_pool.SingletonThreadPool = type('SingletonThreadPool', (), {})
            class ScopedSession:
                def __call__(self): return types.SimpleNamespace(in_transaction=lambda: False, new=[], dirty=[], deleted=[])
                def commit(self): pass
                def rollback(self): pass
            env['db'].session = ScopedSession()
            with patch.dict(sys.modules, {'sqlalchemy': fake_sql, 'sqlalchemy.orm': fake_orm, 'sqlalchemy.pool': fake_pool}):
                self.assertEqual(env['_wechat_share_cleanup_old_images'](), 0)
            self.assertEqual(removed, [])
            self.assertEqual(log.image_path, '/virtual/synthetic.png')


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ActiveImageCleanupTests)
    if suite.countTestCases() != 1:
        raise SystemExit('synthetic test list is incomplete or empty')
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
