"""Browser entries reject missing capabilities before application or network I/O."""
import ast
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ('tests/material_browser_server.py', 'tests/product_receipt_browser_fixture.py')

class BrowserFailClosed(unittest.TestCase):
    def test_guards_precede_application_effects(self):
        for name in FIXTURES:
            tree = ast.parse((ROOT / name).read_text(encoding='utf-8'))
            guards = [item.lineno for item in tree.body if isinstance(item, ast.Expr)
                      and isinstance(item.value, ast.Call) and isinstance(item.value.func, ast.Name)
                      and item.value.func.id == 'require_subprocess_boundary']
            main = next(item for item in tree.body if isinstance(item, ast.FunctionDef) and item.name == 'main')
            self.assertEqual(len(guards), 1)
            self.assertLess(guards[0], main.lineno)
        source = (ROOT / 'tests/material_browser_check.cjs').read_text(encoding='utf-8')
        self.assertLess(source.index('if (boundary.status !== 0)'), source.index("require('../tools/browser_checks"))

    def test_fixture_import_and_main_refuse_before_effects(self):
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
 if '安全阻断' not in str(e): raise
else: raise AssertionError('fixture was not blocked')
'''
        env = {k: os.environ[k] for k in ('SYSTEMROOT', 'WINDIR') if k in os.environ}
        for name in FIXTURES:
            for mode in ('__main__', 'fixture_import'):
                with self.subTest(path=name, mode=mode):
                    result = subprocess.run([sys.executable, '-I', '-S', '-B', '-X', 'utf8', '-c',
                                             bootstrap, str(ROOT / name), mode],
                                            env=env, capture_output=True, timeout=10)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

if __name__ == '__main__':
    unittest.main()
