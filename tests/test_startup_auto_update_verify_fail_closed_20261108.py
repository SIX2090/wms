"""Pure AST check for the startup verification's dynamic import guard."""
import ast
from pathlib import Path
import re
import unittest
import sys
from unittest import mock
from contextlib import redirect_stdout
from io import StringIO


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / 'scripts' / 'verify_startup_auto_update.py'
MESSAGE = '应用和子进程隔离尚未证明'


class StartupVerifySafety(unittest.TestCase):
    def test_static_checks_run_but_dynamic_import_is_blocked(self):
        tree = ast.parse(TARGET.read_text(encoding='utf-8-sig'))
        node = next(item for item in tree.body if isinstance(item, ast.FunctionDef)
                    and item.name == 'test_setting_default_off_and_skip_env')
        guarded = [item for item in node.body if isinstance(item, ast.Expr)
                   and isinstance(item.value, ast.Call)
                   and isinstance(item.value.func, ast.Name)
                   and item.value.func.id == 'require_isolated_test_runtime']
        imports = [item for item in ast.walk(node) if isinstance(item, ast.Import)
                   and any(alias.name == 'run_server' for alias in item.names)]
        self.assertEqual(len(guarded), 1)
        self.assertEqual(len(imports), 1)
        self.assertLess(guarded[0].lineno, imports[0].lineno)
        checks = []
        namespace = {'_read': lambda _path: '', 'APP_PY_PATH': None,
                     'RUN_SERVER_PATH': None, 're': re,
                     'sys': sys, 'ROOT': ROOT,
                     'check': lambda condition, label, failures: checks.append(label)}
        module = ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[]))
        exec(compile(module, '<synthetic-startup-verification>', 'exec'), namespace)
        with mock.patch('scripts.verify_db_guard.require_isolated_test_runtime',
                        side_effect=SystemExit(MESSAGE)), redirect_stdout(StringIO()), \
                self.assertRaisesRegex(SystemExit, MESSAGE):
            namespace[node.name]([])
        self.assertEqual(len(checks), 6)


if __name__ == '__main__':
    unittest.main()
