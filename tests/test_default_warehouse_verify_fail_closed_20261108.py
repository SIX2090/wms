"""Offline checks for the direct pytest path; no WMS or external I/O."""
import ast
import os
from pathlib import Path
import subprocess
import sys
import unittest


TARGETS = (
    Path(__file__).resolve().parent / 'test_get_default_warehouse.py',
    Path(__file__).resolve().parent / 'test_feature_2026_10_08_excel_ocr_export_behavior.py',
)
MESSAGE = '安全阻断'


def first_executable(target):
    body = ast.parse(target.read_text(encoding='utf-8-sig')).body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
        body = body[1:]
    while body and isinstance(body[0], ast.ImportFrom) and body[0].module == '__future__':
        body = body[1:]
    return body[0]


class DefaultWarehouseGuard(unittest.TestCase):
    def test_guard_is_first_before_app_import_and_cleanup(self):
        for target in TARGETS:
            with self.subTest(path=target.name):
                node = first_executable(target)
                self.assertIsInstance(node, ast.ImportFrom)
                self.assertEqual(node.module, 'scripts.verify_db_guard')
                self.assertEqual([item.name for item in node.names], ['require_isolated_test_runtime'])
                body = ast.parse(target.read_text(encoding='utf-8-sig')).body
                call = body[next(i for i, item in enumerate(body) if item.lineno == node.lineno)+1]
                self.assertIsInstance(call, ast.Expr)
                self.assertEqual(call.value.func.id, 'require_isolated_test_runtime')
                self.assertEqual(call.value.args, [])

    def test_import_and_direct_execution_stop_before_any_effect(self):
        bootstrap = r'''import builtins, runpy, socket, sqlite3, subprocess, sys
from pathlib import Path
sys.path.insert(0,str(Path(sys.argv[1]).resolve().parents[1]))
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
except SystemExit as exc:
 if sys.argv[3] not in str(exc): raise
else: raise AssertionError('unsafe test was not blocked')
'''
        env = {key: os.environ[key] for key in ('SYSTEMROOT', 'WINDIR') if key in os.environ}
        for target in TARGETS:
            for mode in ('__main__', 'synthetic_import'):
                with self.subTest(path=target.name, mode=mode):
                    # Refuse to execute even in the mocked child unless the AST guard is present.
                    self.test_guard_is_first_before_app_import_and_cleanup()
                    result = subprocess.run([sys.executable, '-I', '-S', '-B', '-X', 'utf8', '-c', bootstrap,
                                             str(target), mode, MESSAGE], env=env, capture_output=True, timeout=10)
                    self.assertEqual(result.returncode, 0, 'guarded child failed')


if __name__ == '__main__':
    unittest.main()
