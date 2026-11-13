"""Source/negative checks run directly; actual WMS checks require Linux CI isolation."""
import ast
import contextlib
import io
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTIC = ROOT / 'scripts/diagnose_synthetic_push.py'


def load_diagnostic():
    spec = importlib.util.spec_from_file_location('synthetic_push_diagnostic', DIAGNOSTIC)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SyntheticPushDiagnosticSourceTests(unittest.TestCase):
    def test_safe_diagnostic_exists_and_imports_without_application(self):
        self.assertTrue(DIAGNOSTIC.is_file(), '缺少安全合成诊断入口，旧入口仍无条件阻断')
        before = set(sys.modules)
        load_diagnostic()
        self.assertFalse(any(name == 'app' or name.startswith('app.') for name in set(sys.modules) - before))

    def test_os_and_memory_guards_precede_app_import(self):
        tree = ast.parse(DIAGNOSTIC.read_text(encoding='utf-8'))
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'diagnose')
        app_import = next(node.lineno for node in ast.walk(function) if isinstance(node, ast.Import)
                          and any(alias.name == 'app' for alias in node.names))
        guards = {node.func.id: node.lineno for statement in function.body
                  if isinstance(statement, ast.Expr) and isinstance((node := statement.value), ast.Call)
                  and isinstance(node.func, ast.Name) and node.func.id.startswith('require_')}
        self.assertLess(guards['require_isolated_test_runtime'], app_import)
        self.assertLess(guards['require_synthetic_memory_database'], app_import)
        self.assertLess(guards['require_isolated_test_runtime'], guards['require_synthetic_memory_database'])
        source = DIAGNOSTIC.read_text(encoding='utf-8')
        for forbidden in ('requests.', 'sqlite3.connect', 'drop_all', '127.0.0.1:8080'):
            # The explanatory comment may mention drop_all, but executable code must not call it.
            if forbidden != 'drop_all':
                self.assertNotIn(forbidden, source)
        self.assertFalse(any(isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                             and node.func.attr == 'drop_all' for node in ast.walk(tree)))

    def test_detail_content_accepts_current_business_cells_and_html_escaping(self):
        module=load_diagnostic()
        for code_key,name_key in (('colCode','colName'),('material_code','material_name')):
            page=(f'<title>单据详情 - IN-X</title><table id="itemTable"><tbody><tr>'
                  f'<td data-column-key="{code_key}">D&amp;A</td>'
                  f'<td data-column-key="{name_key}">合成&lt;物料&gt;</td></tr></tbody>'
                  f'<tfoot><tr><td data-column-key="{code_key}"></td>'
                  f'<td data-column-key="{name_key}"></td></tr></tfoot></table>')
            self.assertEqual(module._detail_content(page,'IN-X',[('D&A','合成<物料>')]),
                             dict(document_verified=True,verified_material_rows=1))

    def test_detail_content_rejects_login_empty_shell_wrong_identity_and_rows(self):
        module=load_diagnostic()
        row='<tr><td data-column-key="material_code">M-OWN</td><td data-column-key="material_name">合成物料</td></tr>'
        title='<title>单据详情 - IN-X</title>'
        cases=[
            '<title>登录</title><form>login</form>',
            title+'<script>const order="IN-X";const material="M-OWN 合成物料";</script>',
            '<title>单据详情 - IN-X0</title><table id="itemTable"><tbody>'+row+'</tbody></table>',
            title+'<table id="unrelated"><tbody>'+row+'</tbody></table>',
            title+'<table id="itemTable"><tfoot>'+row+'</tfoot></table>',
            title+'<table id="itemTable"><tbody>'+row.replace('M-OWN','M-OTHER')+'</tbody></table>',
            title+'<table id="itemTable"><tbody>'+row.replace('合成物料','其他物料')+'</tbody></table>',
            title+'<table id="itemTable"><tbody>'+row+row+'</tbody></table>',
        ]
        for page in cases:
            with self.subTest(page=page),self.assertRaises(RuntimeError):
                module._detail_content(page,'IN-X',[('M-OWN','合成物料')])
        with self.assertRaises(RuntimeError):
            module._detail_content(title+'<table id="itemTable"><tbody>'+row+'</tbody></table>','IN-X',
                                   [('M-OWN','合成物料'),('M-MISSING','另一物料')])

    def test_invalid_size_rejected_before_guard_or_application(self):
        module = load_diagnostic()
        for rows in (0, -1, 501, 1.5, True, None, '1'):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                module.diagnose(rows)

    def test_unknown_or_missing_scenario_is_rejected(self):
        module = load_diagnostic()
        for args in ([], ['--scenario', 'anything'], ['--scenario', 'inbound-push', '--rows', '0'],
                     ['--scenario', 'inbound-push', '--rows', '501'],
                     ['--scenario', 'inbound-push', '--base-url', 'http://synthetic.invalid']):
            with self.subTest(args=args), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
                module.main(args)
            self.assertEqual(raised.exception.code, 2)

    def test_unowned_direct_run_stops_before_app_database_network_and_children(self):
        probe = r"""
import builtins,runpy,socket,sqlite3,subprocess,sys
script=sys.argv[1]
def deny(*a,**k): raise AssertionError('unexpected app/database/network/subprocess I/O')
socket.socket.connect=deny; socket.socket.connect_ex=deny; socket.getaddrinfo=deny
sqlite3.connect=deny; subprocess.Popen=deny
original=builtins.__import__
def guarded(name,*a,**k):
 if name=='app' or name.startswith('app.'): deny()
 return original(name,*a,**k)
builtins.__import__=guarded
sys.argv=[script,'--scenario','inbound-push']
try: runpy.run_path(script,run_name='__main__')
except SystemExit as exc:
 if '安全阻断' not in str(exc): raise
else: raise AssertionError('unowned diagnostic did not refuse')
"""
        env = {key: os.environ[key] for key in ('SYSTEMROOT', 'PATH', 'TEMP', 'TMP') if key in os.environ}
        for overrides in ({}, {'DATABASE_URL': 'sqlite:///:memory:', 'WMS_DATABASE_URI': 'sqlite:///:memory:',
                               'FLASK_ENV': 'testing', 'WMS_TEST_RUNTIME_HANDLE': '4',
                               'WMS_TEST_RUNTIME_PROOF': '/synthetic-forged-proof.json'}):
            with self.subTest(overrides=overrides):
                result = subprocess.run([sys.executable, '-I', '-S', '-B', '-X', 'utf8', '-c', probe, str(DIAGNOSTIC)],
                                        env=dict(env, **overrides), capture_output=True, text=True,
                                        encoding='utf-8', timeout=20)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


def test_actual_synthetic_push_reports_stages_stock_draft_and_replay():
    import pytest
    if not sys.platform.startswith('linux'):
        pytest.skip('Windows descendants require a newly-issued LPAC process capability; never forge it')
    from scripts.linux_test_runtime import require_subprocess_boundary
    require_subprocess_boundary()
    for rows in (1, 25):
        result = subprocess.run([sys.executable, '-B', str(DIAGNOSTIC), '--scenario', 'inbound-push', '--rows', str(rows)],
                                capture_output=True, text=True, encoding='utf-8', timeout=90)
        assert result.returncode == 0, result.stdout + result.stderr
        lines = [line for line in result.stdout.splitlines() if line.startswith('WMS_SYNTHETIC_DIAGNOSTIC=')]
        assert len(lines) == 1, result.stdout
        report = json.loads(lines[0].split('=', 1)[1])
        assert report['rows'] == rows
        assert report['transport'] == 'flask-test-client' and report['database'] == 'sqlite:///:memory:'
        assert [stage['stage'] for stage in report['stages']] == [
            'save_inbound', 'complete_inbound', 'render_inbound_detail', 'render_push',
            'push_draft', 'replay_push', 'render_target_detail']
        assert all(stage['http_status'] == 200 and stage['elapsed_ms'] >= 0 for stage in report['stages'])
        details=[stage for stage in report['stages'] if stage['stage'] in ('render_inbound_detail','render_target_detail')]
        assert len(details)==2
        assert all(stage['document_verified'] is True and stage['verified_material_rows']==rows for stage in details)
        assert report['source_status'] == 'completed' and report['target_status'] == 'pending'
        assert report['target_count'] == 1 and report['target_quantity'] == rows
        assert report['stock_before'] == 0 and report['stock_after_inbound'] == rows * 2
        assert report['stock_after_push'] == report['stock_after_inbound']
        assert report['request_replayed'] is True


if __name__ == '__main__':
    unittest.main()
