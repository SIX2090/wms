"""Pure/no-I/O host checks; real purchase diagnosis only in standard Linux isolation."""
import ast
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
TARGET=ROOT/'scripts/diagnose_synthetic_purchase.py'


def load():
    spec=importlib.util.spec_from_file_location('synthetic_purchase_diagnostic',TARGET)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


class PurchaseDiagnosticTests(unittest.TestCase):
    def test_diagnostic_exists_and_module_import_is_inert(self):
        self.assertTrue(TARGET.is_file(),'缺少真实路由串联的安全采购诊断入口')
        before=dict(os.environ);cwd=os.getcwd();search=list(sys.path);modules=set(sys.modules)
        load()
        self.assertEqual(dict(os.environ),before);self.assertEqual(os.getcwd(),cwd);self.assertEqual(sys.path,search)
        self.assertFalse(any(name=='app' or name.startswith('app.') for name in set(sys.modules)-modules))

    def test_reuses_authentic_initializer_before_application_access(self):
        tree=ast.parse(TARGET.read_text(encoding='utf-8'))
        function=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='diagnose')
        initialize=next(node.lineno for node in ast.walk(function) if isinstance(node,ast.Call)
                        and isinstance(node.func,ast.Name) and node.func.id=='initialize_synthetic_app')
        uses=[node.lineno for node in ast.walk(function) if isinstance(node,ast.Attribute)
              and isinstance(node.value,ast.Name) and node.value.id=='w']
        self.assertTrue(uses);self.assertLess(initialize,min(uses))
        runtime=ast.parse((ROOT/'scripts/perf_runtime.py').read_text(encoding='utf-8'))
        factory=next(node for node in runtime.body if isinstance(node,ast.FunctionDef) and node.name=='initialize_synthetic_app')
        app_import=next(node.lineno for node in ast.walk(factory) if isinstance(node,ast.Import)
                        and any(item.name=='app' for item in node.names))
        for name in ('require_runtime','require_synthetic_memory_database'):
            call=next(node.lineno for node in ast.walk(factory) if isinstance(node,ast.Call)
                      and isinstance(node.func,ast.Name) and node.func.id==name)
            self.assertLess(call,app_import)
        self.assertIn('from diagnose_synthetic_push import _check',TARGET.read_text(encoding='utf-8'))

    def test_only_explicit_finite_scenario_is_accepted(self):
        module=load()
        for args in ([],['--scenario','unknown'],['--scenario','purchase-receipt','--url','http://synthetic.invalid'],
                     ['--scenario','purchase-receipt','--quantity','100000'],
                     ['--scenario','purchase-receipt','--database','synthetic.db'],
                     ['--scenario','purchase-receipt','--username','admin']):
            with self.subTest(args=args),contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit) as error:
                module.main(args)
            self.assertEqual(error.exception.code,2)

    def test_request_transport_is_relative_no_redirect_and_no_socket(self):
        source=TARGET.read_text(encoding='utf-8');tree=ast.parse(source)
        self.assertIn('relative_target(path)',source)
        self.assertGreaterEqual(source.count('follow_redirects=False'),2)
        self.assertNotIn('requests.',source);self.assertNotIn('socket.',source)
        self.assertNotIn('drop_all(',source);self.assertNotIn('sqlite3.connect',source)
        returns=[node for node in ast.walk(tree) if isinstance(node,ast.Return) and isinstance(node.value,ast.Call)
                 and isinstance(node.value.func,ast.Name) and node.value.func.id=='dict']
        self.assertTrue(returns)
        forbidden={'username','password','nonce','token','payload'}
        for node in returns:self.assertFalse(forbidden.intersection(item.arg for item in node.value.keywords))

    def test_unowned_runtime_refuses_before_app_database_network_or_children(self):
        probe=r"""
import builtins,runpy,socket,sqlite3,subprocess,sys
path=sys.argv[1]
def deny(*a,**k):raise AssertionError('WMS, database, network, listener or subprocess attempted')
socket.socket.connect=socket.socket.connect_ex=socket.socket.bind=socket.getaddrinfo=deny
sqlite3.connect=sqlite3.dbapi2.connect=deny;subprocess.Popen=deny
original=builtins.__import__
def guarded(name,*a,**k):
 if name=='app' or name.startswith('app.'):deny()
 return original(name,*a,**k)
builtins.__import__=guarded
sys.argv=[path,'--scenario','purchase-receipt']
try:runpy.run_path(path,run_name='__main__')
except SystemExit as error:
 if '安全阻断' not in str(error):raise
else:raise AssertionError('unowned purchase diagnostic did not refuse')
"""
        env={key:os.environ[key] for key in ('SYSTEMROOT','PATH','TEMP','TMP') if key in os.environ}
        for extra in ({},{'DATABASE_URL':'sqlite:///:memory:','WMS_DATABASE_URI':'sqlite:///:memory:',
                          'FLASK_ENV':'testing','WMS_TEST_RUNTIME_PROOF':'/forged-synthetic-proof.json'}):
            with self.subTest(extra=extra):
                result=subprocess.run([sys.executable,'-I','-S','-B','-X','utf8','-c',probe,str(TARGET)],
                                      env=dict(env,**extra),capture_output=True,text=True,encoding='utf-8',timeout=20)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)


def test_actual_purchase_routes_receipts_revert_and_reports_in_isolated_linux():
    import pytest
    if not sys.platform.startswith('linux'):
        pytest.skip('Standard true Linux isolation required; never fake a Windows descendant capability')
    from scripts.linux_test_runtime import require_subprocess_boundary
    require_subprocess_boundary()
    result=subprocess.run([sys.executable,'-B',str(TARGET),'--scenario','purchase-receipt'],
                          capture_output=True,text=True,encoding='utf-8',timeout=120)
    assert result.returncode==0,result.stdout+result.stderr
    lines=[line for line in result.stdout.splitlines() if line.startswith('WMS_SYNTHETIC_PURCHASE_DIAGNOSTIC=')]
    assert len(lines)==1,result.stdout
    report=json.loads(lines[0].split('=',1)[1])
    assert report['scenario']=='purchase-receipt' and report['database']=='sqlite:///:memory:'
    assert report['transport']=='flask-test-client' and report['location_management'] is False
    assert report['request_count']==1 and report['purchase_order_count']==1 and report['receipt_count']==2
    assert [stage['stage'] for stage in report['stages']]==[
        'save_request','replay_save','approve_request','push_purchase_order','repeat_purchase_push',
        'create_partial_receipt','complete_partial','revert_partial','recomplete_partial',
        'create_remaining_receipt','complete_remaining','render_execution_report']
    assert all(stage['http_status']==200 and stage['elapsed_ms']>=0 for stage in report['stages'])
    received=[0,0,4,0,4,4,10];pushed=[0,4,4,4,4,10,10]
    assert len(report['snapshots'])==7
    assert [snapshot['stage'] for snapshot in report['snapshots']]==[
        'ordered_no_receipt','partial_draft','partial_completed','partial_reverted',
        'partial_recompleted','remaining_draft','all_completed']
    for row,actual,reserved in zip(report['snapshots'],received,pushed):
        assert row['request_received']==row['purchase_completed']==row['global_stock']==row['warehouse_a']==actual
        assert row['warehouse_b']==0
        assert row['request_remaining']==10-actual
        assert row['report_b_rows']==0
        if row['stage']=='ordered_no_receipt':
            assert row['report_has_warehouse_assignment'] is False
            assert row['report_received'] is None and row['report_remaining'] is None
        else:
            assert row['report_has_warehouse_assignment'] is True
            assert row['report_remaining']==10-actual and row['report_received']==actual
        assert row['purchase_pushed']==reserved and row['purchase_pending']==reserved-actual
        assert row['purchase_remaining_to_push']==10-reserved


if __name__=='__main__':
    unittest.main()
