"""Offline checks: do not import WMS or access any database, backup, or network."""
import ast
import os
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
TARGETS = (
    (ROOT / 'scripts' / 'verify_ai_stage6_prelaunch.py', '预发布验证的应用和备份目录隔离尚未证明'),
    (ROOT / 'scripts' / 'verify_ai_browser_e2e.py', '浏览器验证的应用和备份目录隔离尚未证明'),
)


def first_executable(target):
    body = list(ast.parse(target.read_text(encoding='utf-8-sig')).body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
        body.pop(0)
    while body and isinstance(body[0], ast.ImportFrom) and body[0].module == '__future__':
        body.pop(0)
    return body[0]


class Stage6FailClosed(unittest.TestCase):
    def test_guard_is_first_executable_statement(self):
        for target, message in TARGETS:
            with self.subTest(target=target.name):
                node = first_executable(target)
                self.assertIsInstance(node, ast.Raise)
                self.assertIsInstance(node.exc, ast.Call)
                self.assertIsInstance(node.exc.func, ast.Name)
                self.assertEqual(node.exc.func.id, 'SystemExit')
                self.assertIn(message, node.exc.args[0].value)

    def test_import_and_main_are_blocked_before_effects(self):
        # Check the AST before executing the current version, never execute the old version.
        self.test_guard_is_first_executable_statement()
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
except SystemExit as e:
 if sys.argv[3] not in str(e): raise
else: raise AssertionError('unsafe entry not blocked')
'''
        env = {key: os.environ[key] for key in ('SYSTEMROOT', 'WINDIR') if key in os.environ}
        for target, message in TARGETS:
            for mode in ('__main__', 'isolated_import'):
                with self.subTest(target=target.name, mode=mode):
                    result = subprocess.run(
                        [sys.executable, '-I', '-S', '-B', '-X', 'utf8', '-c', bootstrap, str(target), mode, message],
                        env=env, capture_output=True, timeout=10,
                    )
                    self.assertEqual(result.returncode, 0, 'guarded child failed')


if __name__ == '__main__':
    unittest.main()
