"""Offline guard for an independently executable database probe."""
import ast
import os
from pathlib import Path
import subprocess
import sys
import unittest


TARGET = Path(__file__).resolve().parent / 'material_unused_delete_lock_probe.py'
MESSAGE = '隔离文件库及应用出站尚未证明'


def first_executable():
    body = ast.parse(TARGET.read_text(encoding='utf-8-sig')).body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
        body = body[1:]
    while body and isinstance(body[0], ast.ImportFrom) and body[0].module == '__future__':
        body = body[1:]
    return body[0]


class LockProbeSafety(unittest.TestCase):
    def test_guard_precedes_argument_parsing_and_all_side_effects(self):
        node = first_executable()
        self.assertIsInstance(node, ast.Raise)
        self.assertIsInstance(node.exc, ast.Call)
        self.assertIsInstance(node.exc.func, ast.Name)
        self.assertEqual(node.exc.func.id, 'RuntimeError')
        self.assertIn(MESSAGE, node.exc.args[0].value)

    def test_main_and_import_stop_before_app_database_or_network(self):
        # Never execute an unguarded version: check before each child launch.
        bootstrap = r'''import builtins, runpy, socket, sqlite3, subprocess, sys
def refuse(*args, **kwargs): raise AssertionError('forbidden side effect')
socket.socket.connect = refuse
socket.socket.connect_ex = refuse
socket.getaddrinfo = refuse
sqlite3.connect = refuse
subprocess.Popen = refuse
original = builtins.__import__
def guarded(name, *args, **kwargs):
 if name == 'app' or name.startswith('app.'): raise AssertionError('forbidden app import')
 return original(name, *args, **kwargs)
builtins.__import__ = guarded
try:
 runpy.run_path(sys.argv[1], run_name=sys.argv[2])
except RuntimeError as exc:
 if sys.argv[3] not in str(exc): raise
else: raise AssertionError('unsafe entry not blocked')
'''
        env = {key: os.environ[key] for key in ('SYSTEMROOT', 'WINDIR') if key in os.environ}
        for mode in ('__main__', 'synthetic_import'):
            with self.subTest(mode=mode):
                self.test_guard_precedes_argument_parsing_and_all_side_effects()
                result = subprocess.run([sys.executable, '-I', '-S', '-B', '-X', 'utf8', '-c', bootstrap,
                                         str(TARGET), mode, MESSAGE], env=env, capture_output=True, timeout=10)
                self.assertEqual(result.returncode, 0, 'guarded child failed')


if __name__ == '__main__':
    unittest.main()
