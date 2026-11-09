"""Static and isolated no-I/O checks for retired diagnostic entry points.

Run directly: python -I -S -B tests/test_diag_fail_closed_20261108.py.
The old scripts are never executed unless their first executable statement is
already a literal fail-closed guard.
"""
import ast
import os
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTICS = (
    'diag_full_flow.py', 'diag_http.py', 'diag_live_get.py', 'diag_live_push.py',
    'diag_lock_contention.py', 'diag_push_live.py', 'diag_seed_big.py', 'diag_seed_live.py',
)

CHILD_PROBE = r'''
import builtins, runpy, socket, sqlite3, subprocess, sys
def denied(*args, **kwargs):
    raise AssertionError('network, database, application import or subprocess attempted')
socket.socket.connect = denied
socket.socket.connect_ex = denied
socket.getaddrinfo = denied
sqlite3.connect = denied
subprocess.Popen = denied
original_import = builtins.__import__
def safe_import(name, *args, **kwargs):
    if name == 'app' or name.startswith('app.'):
        denied()
    return original_import(name, *args, **kwargs)
builtins.__import__ = safe_import
try:
    runpy.run_path(sys.argv[1], run_name=sys.argv[2])
except RuntimeError as exc:
    if '隔离' not in str(exc):
        raise
else:
    raise AssertionError('diagnostic did not fail closed')
'''


class DiagnosticFailClosedTests(unittest.TestCase):
    def assert_first_executable_is_guard(self, path):
        body = ast.parse(path.read_text(encoding='utf-8')).body
        index = 0
        if (body and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)):
            index += 1
        while index < len(body) and isinstance(body[index], ast.ImportFrom) and body[index].module == '__future__':
            index += 1
        self.assertLess(index, len(body))
        guard = body[index]
        self.assertIsInstance(guard, ast.Raise, '任何 import、连接或请求之前必须拒绝')
        self.assertIsInstance(guard.exc, ast.Call)
        self.assertIsInstance(guard.exc.func, ast.Name)
        self.assertEqual(guard.exc.func.id, 'RuntimeError')
        self.assertTrue(guard.exc.args and isinstance(guard.exc.args[0], ast.Constant))
        self.assertIn('隔离', guard.exc.args[0].value)

    def test_guard_is_first_executable_statement(self):
        self.assertTrue(DIAGNOSTICS)
        for name in DIAGNOSTICS:
            with self.subTest(name=name):
                self.assert_first_executable_is_guard(ROOT / 'tests' / name)

    def test_import_and_direct_execution_stop_before_any_io(self):
        env = {key: os.environ[key] for key in ('SYSTEMROOT', 'PATH', 'TEMP', 'TMP')
               if key in os.environ}
        for name in DIAGNOSTICS:
            path = ROOT / 'tests' / name
            for mode in ('diagnostic_import_probe', '__main__'):
                with self.subTest(name=name, mode=mode):
                    # Never run an older diagnostic whose top-level guard is absent.
                    self.assert_first_executable_is_guard(path)
                    result = subprocess.run(
                        [sys.executable, '-I', '-S', '-B', '-X', 'utf8', '-c', CHILD_PROBE, str(path), mode],
                        cwd=str(ROOT), env=env, capture_output=True, text=True, encoding='utf-8',
                        errors='replace', timeout=10,
                    )
                    self.assertEqual(result.returncode, 0, f'{name} {mode} 隔离探针失败')


if __name__ == '__main__':
    unittest.main()
