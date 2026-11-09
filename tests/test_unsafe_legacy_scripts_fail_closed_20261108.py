"""Unowned legacy scripts must stop before import-time network or database IO.

Old scripts are only parsed as AST; they are never run unless a literal first
statement is already the required fail-closed guard.
"""
import ast
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = (
    'scripts/edge_case_rules_test.py', 'scripts/verify_unit_delete.py',
    'scripts/endpoint_sweep.py', 'scripts/system_functional_test.py',
    'scripts/wms_e2e_visual.py', 'scripts/verify_login.py', 'scripts/verify_login_pw.py',
    'scripts/verify_base_materials.py', 'scripts/verify_category_add.py',
    'scripts/verify_category_toolbar.py', 'scripts/repro_push_timing.py',
    'scripts/archive/_challenge.py', 'scripts/archive/_bench_push.py',
    'scripts/archive/_bench_lock.py', 'scripts/archive/_bench_big.py',
    'scripts/archive/_full_demo.py', 'scripts/archive/_full_demo2.py',
    'scripts/archive/_demo_login.py', 'scripts/archive/_trae_login.py',
    'scripts/e2e_business_flow.py', 'scripts/e2e_purchase_flow_10sets.py',
    'scripts/crawl_all_pages.py', 'scripts/capture_mobile_screenshots.py',
    'scripts/verify_bug_2026_10_05_002_embedded_duplicate_fab_browser.py',
    'scripts/audit/scan_all_menus.py', 'scripts/archive/_wms_browser_e2e_real.py',
)

CHILD_PROBE = r'''
import builtins, runpy, socket, sqlite3, subprocess, sys
def denied(*args, **kwargs):
    raise AssertionError('network, database, app import or subprocess attempted')
socket.socket.connect = denied
socket.socket.connect_ex = denied
socket.getaddrinfo = denied
sqlite3.connect = denied
subprocess.Popen = denied
original_import = builtins.__import__
def guarded_import(name, *args, **kwargs):
    if name == 'app' or name.startswith('app.'):
        denied()
    return original_import(name, *args, **kwargs)
builtins.__import__ = guarded_import
try:
    runpy.run_path(sys.argv[1], run_name=sys.argv[2])
except RuntimeError as exc:
    if '隔离' not in str(exc):
        raise
else:
    raise AssertionError('legacy script did not fail closed')
'''


class UnsafeLegacyScriptTests(unittest.TestCase):
    def assert_guard_first(self, path):
        body = ast.parse(path.read_text(encoding='utf-8')).body
        index = 0
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                and isinstance(body[0].value.value, str):
            index += 1
        while index < len(body) and isinstance(body[index], ast.ImportFrom) and body[index].module == '__future__':
            index += 1
        self.assertLess(index, len(body))
        first = body[index]
        self.assertIsInstance(first, ast.Raise)
        self.assertIsInstance(first.exc, ast.Call)
        self.assertIsInstance(first.exc.func, ast.Name)
        self.assertEqual(first.exc.func.id, 'RuntimeError')
        self.assertIsInstance(first.exc.args[0], ast.Constant)
        self.assertIn('隔离', first.exc.args[0].value)

    def test_guard_precedes_all_other_executable_code(self):
        self.assertEqual(len(SCRIPTS), 26)
        for name in SCRIPTS:
            with self.subTest(name=name):
                self.assert_guard_first(ROOT / name)

    def test_import_and_direct_execution_do_not_access_io(self):
        env = {key: os.environ[key] for key in ('SYSTEMROOT', 'PATH', 'TEMP', 'TMP')
               if key in os.environ}
        for name in SCRIPTS:
            path = ROOT / name
            for mode in ('legacy_import_probe', '__main__'):
                with self.subTest(name=name, mode=mode):
                    self.assert_guard_first(path)
                    result = subprocess.run(
                        [sys.executable, '-I', '-S', '-B', '-X', 'utf8', '-c', CHILD_PROBE, str(path), mode],
                        cwd=str(ROOT), env=env, capture_output=True, text=True, encoding='utf-8',
                        errors='replace', timeout=10,
                    )
                    self.assertEqual(result.returncode, 0, f'{name} {mode} 隔离探针失败')


if __name__ == '__main__':
    unittest.main()
