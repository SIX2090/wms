"""Offline checks for disabled browser entry points; never start the WMS."""
import ast
import os
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ('tests/material_browser_server.py', 'tests/product_receipt_browser_fixture.py')
HARNESS = 'tests/test_material_browser_harness.py'
BLOCKED_TESTS = ('test_browser_fixture_owns_temporary_database_and_port',
                 'test_browser_fixture_rejects_live_ports_before_loading_app')
MESSAGE = '隔离能力尚未证明'


def first_executable(body):
    body = list(body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
        body.pop(0)
    while body and isinstance(body[0], ast.ImportFrom) and body[0].module == '__future__':
        body.pop(0)
    return body[0]


def is_guard(node):
    return (isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call)
            and isinstance(node.exc.func, ast.Name) and node.exc.func.id == 'RuntimeError'
            and len(node.exc.args) == 1 and isinstance(node.exc.args[0], ast.Constant)
            and isinstance(node.exc.args[0].value, str) and MESSAGE in node.exc.args[0].value)


class BrowserFailClosed(unittest.TestCase):
    def test_guards_precede_effects(self):
        for name in FIXTURES:
            with self.subTest(path=name):
                tree = ast.parse((ROOT / name).read_text(encoding='utf-8'))
                self.assertTrue(is_guard(first_executable(tree.body)))
        tree = ast.parse((ROOT / HARNESS).read_text(encoding='utf-8'))
        functions = {n.name: n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        for name in BLOCKED_TESTS:
            with self.subTest(test=name):
                self.assertTrue(is_guard(first_executable(functions[name].body)))
        source = (ROOT / 'tests/material_browser_check.cjs').read_text(encoding='utf-8-sig')
        lines = [line.strip() for line in source.splitlines() if line.strip() and not line.strip().startswith(('//', '#!'))]
        if lines[0] in ("'use strict';", '"use strict";'):
            lines.pop(0)
        self.assertEqual(lines[0], "throw new Error('浏览器验证已阻止：隔离能力尚未证明');")

    def test_fixture_import_and_main_refuse_before_effects(self):
        # Never execute a version unless its first executable statement is the guard.
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
except RuntimeError as e:
 if '隔离能力尚未证明' not in str(e): raise
else: raise AssertionError('fixture was not blocked')
'''
        env = {k: os.environ[k] for k in ('SYSTEMROOT', 'WINDIR') if k in os.environ}
        for name in FIXTURES:
            with self.subTest(path=name):
                tree = ast.parse((ROOT / name).read_text(encoding='utf-8'))
                self.assertTrue(is_guard(first_executable(tree.body)))
                for mode in ('__main__', 'fixture_import'):
                    result = subprocess.run([sys.executable, '-I', '-S', '-B', '-X', 'utf8', '-c', bootstrap,
                                             str(ROOT / name), mode], env=env, capture_output=True, timeout=10)
                    self.assertEqual(result.returncode, 0, 'guarded child failed')

    def test_harness_real_test_bodies_fail_before_setup(self):
        tree = ast.parse((ROOT / HARNESS).read_text(encoding='utf-8'))
        functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
        for name in BLOCKED_TESTS:
            with self.subTest(test=name):
                function = functions[name]
                self.assertTrue(is_guard(first_executable(function.body)))
                function.decorator_list = []
                module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
                scope = {}
                exec(compile(module, '<isolated harness function>', 'exec'), scope)
                with self.assertRaisesRegex(RuntimeError, MESSAGE):
                    scope[name](*([None] * len(function.args.args)))


if __name__ == '__main__':
    unittest.main()
