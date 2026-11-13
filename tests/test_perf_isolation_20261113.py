"""Run directly for source/no-I/O tests; actual perf execution belongs to Linux CI."""
import ast
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    path = ROOT / 'scripts' / (name + '.py')
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PerfIsolationTests(unittest.TestCase):
    def test_all_performance_imports_are_inert(self):
        probe = r"""
import builtins,importlib.util,os,pathlib,socket,sqlite3,subprocess,sys,tempfile
path=sys.argv[1]; environment=dict(os.environ);cwd=os.getcwd();search=list(sys.path)
def deny(*a,**k): raise AssertionError('unexpected app/database/network/process/state side effect')
socket.socket.connect=deny;socket.socket.connect_ex=deny;socket.getaddrinfo=deny
sqlite3.connect=deny;subprocess.Popen=deny;tempfile.mkdtemp=deny;os.chdir=deny
original=builtins.__import__
def guarded(name,*a,**k):
 if name=='app' or name.startswith('app.'):deny()
 return original(name,*a,**k)
builtins.__import__=guarded
spec=importlib.util.spec_from_file_location('performance_import_probe',path)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
assert dict(os.environ)==environment,'import changes environment'
assert os.getcwd()==cwd,'import changes cwd'
assert sys.path==search,'import changes module search path'
"""
        env = {key: os.environ[key] for key in ('SYSTEMROOT', 'PATH', 'TEMP', 'TMP') if key in os.environ}
        for name in ('perf_baseline', 'perf_export_baseline', 'perf_runtime'):
            with self.subTest(name=name):
                result = subprocess.run([sys.executable, '-I', '-S', '-B', '-X', 'utf8', '-c', probe,
                                         str(ROOT / 'scripts' / (name + '.py'))],
                                        env=env, capture_output=True, text=True, encoding='utf-8', timeout=20)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_unowned_cli_and_helpers_refuse_before_all_io(self):
        probe = r"""
import builtins,importlib.util,os,runpy,socket,sqlite3,subprocess,sys,tempfile
path,kind=sys.argv[1:];sys.path.insert(0,os.path.dirname(path))
def deny(*a,**k):raise AssertionError('unexpected app/database/network/listener/process I/O')
socket.socket.connect=deny;socket.socket.connect_ex=deny;socket.socket.bind=deny;socket.getaddrinfo=deny
sqlite3.connect=deny;subprocess.Popen=deny;tempfile.mkdtemp=deny
original=builtins.__import__
def guarded(name,*a,**k):
 if name=='app' or name.startswith('app.'):deny()
 return original(name,*a,**k)
builtins.__import__=guarded
try:
 if kind=='cli':
  sys.argv=[path];runpy.run_path(path,run_name='__main__')
 else:
  spec=importlib.util.spec_from_file_location('perf_probe',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  if kind=='benchmark':module.run_benchmark(0.1,1)
  elif kind=='measure':module._measure_endpoint(None,'http://127.0.0.1:8080','/',0.1,1)
  elif kind=='export-seed':module.seed(None,1)
  elif kind=='export-measure':module.measure(None,None,'GET','/',1)
except SystemExit as exc:
 if '安全阻断' not in str(exc):raise
else:raise AssertionError('unowned performance run did not refuse')
"""
        env = {key: os.environ[key] for key in ('SYSTEMROOT', 'PATH', 'TEMP', 'TMP') if key in os.environ}
        for name, kind in (('perf_baseline', 'cli'), ('perf_baseline', 'benchmark'),
                           ('perf_baseline', 'measure'), ('perf_export_baseline', 'cli'),
                           ('perf_export_baseline', 'export-seed'), ('perf_export_baseline', 'export-measure')):
            with self.subTest(name=name, kind=kind):
                result = subprocess.run([sys.executable, '-I', '-S', '-B', '-X', 'utf8', '-c', probe,
                                         str(ROOT / 'scripts' / (name + '.py')), kind],
                                        env=env, capture_output=True, text=True, encoding='utf-8', timeout=20)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_relative_targets_reject_external_or_alias_inputs(self):
        runtime = load('perf_runtime')
        for value in ('http://synthetic.invalid/', '//synthetic.invalid/', '/', '/check?owned=1',
                      '/\\synthetic.invalid/', '/check#fragment'):
            with self.subTest(value=value):
                if value in ('/', '/check?owned=1'):
                    self.assertEqual(runtime.relative_target(value), value)
                else:
                    with self.assertRaises(ValueError):
                        runtime.relative_target(value)

    def test_workflow_uses_existing_exact_source_container_and_exports_artifact(self):
        source = (ROOT / '.github/workflows/perf.yml').read_text(encoding='utf-8')
        self.assertIn('python scripts/run_ci_isolated.py -- python scripts/perf_baseline.py', source)
        self.assertIn('--output output/perf_current.json', source)
        self.assertIn('path: output/perf_current.json', source)
        self.assertIn('continue-on-error: true', source)

    def test_http_baseline_keeps_waitress_lease_and_rejects_redirects(self):
        runtime = (ROOT / 'scripts/perf_runtime.py').read_text(encoding='utf-8')
        self.assertIn("self.listener.bind(('127.0.0.1', 0))", runtime)
        self.assertIn('OwnedSocketLease(self.listener, identity)', runtime)
        self.assertIn('IsolatedSession', runtime)
        self.assertIn('sockets=[self.listener]', runtime)
        self.assertIn("kwargs.get('allow_redirects') is not False", runtime)
        baseline = (ROOT / 'scripts/perf_baseline.py').read_text(encoding='utf-8')
        self.assertNotIn('test_client(', baseline)
        self.assertNotIn('allow_redirects=True', baseline)
        self.assertNotIn('def _free_port', baseline)

    def test_redirect_rejection_happens_before_transport_model(self):
        tree = ast.parse((ROOT / 'scripts/perf_runtime.py').read_text(encoding='utf-8'))
        policy = next(node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
                      and node.name == 'NoRedirectSession')
        calls = []
        class Base:
            def send(self, request, **kwargs):
                calls.append((request, kwargs))
                return 'owned-nonce-checked-response'
        namespace = {'IsolatedSession': Base, 'IsolationError': ValueError}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[policy], type_ignores=[])),
                     '<transport-model>', 'exec'), namespace)
        session = namespace['NoRedirectSession']()
        for kwargs in ({}, {'allow_redirects': True}, {'allow_redirects': None}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                session.send('synthetic request', **kwargs)
        self.assertEqual(calls, [])
        self.assertEqual(session.send('synthetic request', allow_redirects=False), 'owned-nonce-checked-response')
        self.assertEqual(len(calls), 1)

    def test_mismatched_profiles_are_incomparable_and_matching_profiles_keep_regression(self):
        module = load('perf_baseline')
        old = {'endpoints': {'stock': {'p95_ms': 100, 'label': '库存'}}}
        current = {'measurement_profile': module.MEASUREMENT_PROFILE,
                   'endpoints': {'stock': {'p95_ms': 200, 'label': '库存'}}}
        result = module.compare_measurement_profiles(old, current)
        self.assertEqual(result['status'], 'incomparable')
        self.assertEqual(result['alerts'], [])
        old['measurement_profile'] = module.MEASUREMENT_PROFILE
        result = module.compare_measurement_profiles(old, current)
        self.assertEqual(result['status'], 'regression')
        self.assertEqual(result['alerts'][0]['delta_pct'], 100)
        current['endpoints']['stock']['p95_ms'] = 110
        self.assertEqual(module.compare_measurement_profiles(old, current)['status'], 'no_regression')
        self.assertEqual(module.compare_measurement_profiles(dict(old, endpoints={}), current)['status'], 'incomparable')

    def test_bounds_and_pure_statistics(self):
        module = load('perf_baseline')
        for seconds, concurrency in ((0,1),(-1,1),(31,1),(1,0),(1,5),(float('nan'),1)):
            with self.subTest(seconds=seconds, concurrency=concurrency), self.assertRaises(ValueError):
                module.run_benchmark(seconds, concurrency)
        self.assertEqual(module.percentile([1,2,3], 50), 2)
        self.assertEqual(module.summarize([1,2,3], 1, 0)['count'], 3)
        self.assertEqual(module.regression_alerts({'a':{'p95_ms':100}}, {'a':{'p95_ms':200}})[0]['delta_pct'], 100)


def test_actual_waitress_http_and_export_in_synthetic_linux_container():
    import pytest
    if not sys.platform.startswith('linux'):
        pytest.skip('Authentic network-none Linux runtime required; do not forge LPAC descendant capability')
    from scripts.linux_test_runtime import require_subprocess_boundary
    require_subprocess_boundary()
    commands = [
        ([sys.executable, '-B', str(ROOT/'scripts/perf_baseline.py'), '--seconds', '0.05', '--concurrency', '1'],
         ROOT/'output/perf_current.json'),
        ([sys.executable, '-B', str(ROOT/'scripts/perf_export_baseline.py'), '--materials', '2', '--rounds', '1'],
         ROOT/'output/perf_export_current.json'),
    ]
    for command, output in commands:
        result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', timeout=120)
        assert result.returncode == 0, result.stdout + result.stderr
        report = json.loads(output.read_text(encoding='utf-8'))
        assert report['endpoints']
        if 'config' in report:
            assert len(report['endpoints']) == 10
            assert all(item['count'] > 0 for item in report['endpoints'].values()), report
            assert len(report['git_sha']) == 40
            assert report['measurement_profile'] == 'sqlite-memory-waitress-v2'
            assert report['comparison']['status'] == 'not_requested'
        else:
            assert report['meta']['db'] == 'synthetic sqlite memory'
            assert len(report['endpoints']) == 4
            assert all(item['rounds'] == 1 and item['status'] == 200 for item in report['endpoints'].values()), report
    strict = subprocess.run([sys.executable, '-B', str(ROOT/'scripts/perf_baseline.py'),
                             '--seconds', '0.05', '--concurrency', '1', '--strict',
                             '--compare', str(ROOT/'scripts/perf_baseline.json')],
                            capture_output=True, text=True, encoding='utf-8', timeout=120)
    assert strict.returncode == 2, strict.stdout + strict.stderr
    report = json.loads((ROOT/'output/perf_current.json').read_text(encoding='utf-8'))
    assert report['comparison']['status'] == 'incomparable'
    assert '未作性能通过或回归判定' in strict.stdout


if __name__ == '__main__':
    unittest.main()
