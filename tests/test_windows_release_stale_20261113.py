"""Synthetic release eligibility and safe PowerShell control-flow models only."""
import importlib.util
import builtins
import io
import json
import os
from pathlib import Path
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
A, B = 'a' * 40, 'b' * 40


def load():
    spec = importlib.util.spec_from_file_location('stale_release_target', ROOT/'tools/windows_release.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class StaleReleaseTests(unittest.TestCase):
    def setUp(self):
        def deny(*args, **kwargs):
            raise AssertionError('WMS import, database or network I/O forbidden in release models')
        for patch in (mock.patch.object(socket.socket, 'connect', deny),
                      mock.patch.object(socket.socket, 'connect_ex', deny),
                      mock.patch.object(socket.socket, 'bind', deny),
                      mock.patch.object(socket, 'getaddrinfo', deny),
                      mock.patch.object(sqlite3, 'connect', deny),
                      mock.patch.object(sqlite3.dbapi2, 'connect', deny)):
            patch.start();self.addCleanup(patch.stop)
        original = builtins.__import__
        def guarded(name, *args, **kwargs):
            if name == 'app' or name.startswith('app.'):
                deny()
            return original(name, *args, **kwargs)
        patch = mock.patch.object(builtins, '__import__', guarded)
        patch.start();self.addCleanup(patch.stop)

    def eligibility(self, event='workflow_run', remote=B, relation=0, fetch_error=False):
        module = load()
        calls = []
        def run(command, **kwargs):
            calls.append(command)
            if 'fetch' in command and fetch_error:
                raise subprocess.CalledProcessError(1, command)
            return type('Result', (), {'returncode': relation if 'merge-base' in command else 0})()
        with mock.patch.object(module, '_json_api', return_value={'object': {'sha': remote}}), \
             mock.patch.object(module.subprocess, 'run', side_effect=run):
            result = module.target_eligibility(ROOT, 'owner/wms', A, event)
        return result, calls

    def test_automatic_successful_ancestor_is_stale_skip(self):
        result, calls = self.eligibility()
        self.assertEqual(result, dict(state='stale_skipped', source_sha=A, current_main=B))
        self.assertIn('fetch', calls[0])
        self.assertEqual(calls[1][-4:], ['merge-base', '--is-ancestor', A, B])

    def test_current_target_keeps_packaging_path(self):
        for event in ('workflow_run', 'workflow_dispatch', 'push'):
            result, calls = self.eligibility(event=event, remote=A)
            self.assertEqual(result['state'], 'eligible')
            self.assertEqual(calls, [])

    def test_manual_nonancestor_unknown_and_fetch_failures_still_refuse(self):
        for kwargs in ({'event': 'workflow_dispatch'}, {'relation': 1}, {'relation': 128},
                       {'remote': ''}, {'remote': 'main'}, {'fetch_error': True}):
            with self.subTest(kwargs=kwargs), self.assertRaises((ValueError, subprocess.SubprocessError)):
                self.eligibility(**kwargs)
        module = load()
        with mock.patch.object(module, '_json_api', side_effect=ValueError('query failed')):
            with self.assertRaises(ValueError):
                module.target_eligibility(ROOT, 'owner/wms', A, 'workflow_run')

    def test_stale_plan_has_no_work_directory_download_or_fingerprint(self):
        module = load()
        with tempfile.TemporaryDirectory(prefix='wms-stale-plan-') as folder:
            work = Path(folder)/'no-product'
            def denied(*args, **kwargs):
                raise AssertionError('stale plan attempted asset, fingerprint or packaging operation')
            with mock.patch.object(module.subprocess, 'check_output', return_value=A+'\n'), \
                 mock.patch.object(module, 'target_eligibility', return_value=dict(state='stale_skipped', source_sha=A, current_main=B)), \
                 mock.patch.object(module, '_gh', side_effect=denied), \
                 mock.patch.object(module, 'build_inputs', side_effect=denied):
                result = module.plan_release(ROOT, '2026.11.99', work, 'owner/wms', 'workflow_run')
            self.assertEqual(result['state'], 'stale_skipped')
            self.assertFalse(work.exists())

    def test_publish_discards_stale_before_and_after_upload_without_publishing(self):
        module = load()
        for stage in ('before_upload', 'after_upload'):
            calls = []
            plan = dict(state='build', repository='owner/wms', root=str(ROOT), work_dir='synthetic-owned',
                        source_sha=A, input_fingerprint='f'*64, version='2026.11.99',
                        names=module.release_names('2026.11.99'))
            eligible = dict(state='eligible', source_sha=A, current_main=A)
            stale = dict(state='stale_skipped', source_sha=A, current_main=B)
            decisions = [stale] if stage == 'before_upload' else [eligible, stale]
            draft = dict(tag_name=plan['names']['tag'], target_commitish=A)
            with mock.patch.object(module, 'target_eligibility', side_effect=decisions), \
                 mock.patch.object(module, 'build_inputs', return_value='f'*64), \
                 mock.patch.object(module, '_gh', side_effect=lambda *args, **kwargs: calls.append(args)), \
                 mock.patch.object(module, '_json_api', return_value=[draft]), \
                 mock.patch.object(module, 'tag_commit', return_value=None), \
                 mock.patch.object(module, 'verify_downloads') as verified:
                result = module.publish_release(plan, Path('synthetic-notes'), 'workflow_run')
            self.assertEqual(result['state'], 'stale_skipped')
            self.assertFalse(any(args[:2] == ('release', 'edit') for args in calls))
            self.assertEqual(len(calls), int(stage == 'after_upload'))
            if stage == 'after_upload':
                verified.assert_called_once()
                self.assertEqual(result['unpublished_draft'], plan['names']['tag'])
            else:
                verified.assert_not_called()

    def test_main_records_discard_and_summary_without_claiming_built(self):
        module = load()
        with tempfile.TemporaryDirectory(prefix='wms-stale-cli-') as folder:
            folder = Path(folder);planfile = folder/'plan.json';summary = folder/'summary'
            planfile.write_text(json.dumps(dict(state='build',source_sha=A)),encoding='utf-8')
            stale = dict(state='stale_skipped', source_sha=A, current_main=B)
            with mock.patch.dict(os.environ, GITHUB_EVENT_NAME='workflow_run', GITHUB_STEP_SUMMARY=str(summary)), \
                 mock.patch.object(module, 'publish_release', return_value=stale), \
                 mock.patch('sys.stdout', new=io.StringIO()):
                self.assertEqual(module.main(['publish','--plan',str(planfile),'--notes',str(folder/'notes')]),0)
            self.assertEqual(json.loads(planfile.read_text())['state'], 'stale_skipped')
            text = summary.read_text(encoding='utf-8')
            self.assertIn(A,text);self.assertIn(B,text);self.assertNotIn('built_verified',text)

    def test_workflow_keeps_exact_ci_build_and_stale_summary_guards(self):
        text = (ROOT/'.github/workflows/windows-release.yml').read_text(encoding='utf-8')
        self.assertIn('tools/windows_release.py target',text)
        self.assertIn('check_ci_green.py --target-sha $sha --json',text)
        self.assertIn('RELEASE_TRIGGER_SHA',text)
        self.assertIn("if: steps.release.outputs.state != 'stale_skipped'",text)
        self.assertEqual(text.count("if: steps.release.outputs.state == 'build'"),3)
        self.assertIn('tools/windows_release.py seal',text)
        self.assertIn('tools/windows_release.py publish',text)

    def test_actual_powershell_preflight_only_uses_command_stubs(self):
        shell = shutil.which('pwsh') or shutil.which('powershell')
        if not shell:
            self.skipTest('PowerShell not installed; Python/source models still run')
        workflow = (ROOT/'.github/workflows/windows-release.yml').read_text(encoding='utf-8')
        start = workflow.index('          $ErrorActionPreference') if '          $ErrorActionPreference' in workflow else workflow.index('          $sha = git rev-parse HEAD')
        end = workflow.index('      - name: Download pinned',start)
        body = '\n'.join(line[10:] for line in workflow[start:end].rstrip().splitlines())
        body = body.replace('${{ github.run_id }}','1').replace('${{ github.run_attempt }}','1').replace('${{ github.repository }}','owner/wms')
        for state, target_exit, expected_exit, expected_calls in (
            ('stale_skipped',0,0,['git','target']),
            ('eligible',0,0,['git','target','ci','version','plan']),
            ('eligible',1,1,['git','target'])):
            with self.subTest(state=state,target_exit=target_exit), tempfile.TemporaryDirectory(prefix='wms-pwsh-stale-') as folder:
                folder = Path(folder);script=folder/'probe.ps1';calls=folder/'calls.txt'
                wrapper = r"""
$ErrorActionPreference='Stop'
function global:git { 'git' >> $env:MODEL_CALLS; $global:LASTEXITCODE=0; return $env:MODEL_SHA }
function global:gh { 'gh' >> $env:MODEL_CALLS; $global:LASTEXITCODE=0; return $env:MODEL_REMOTE_SHA }
function global:python {
 if ($args[1] -eq 'target') { 'target' >> $env:MODEL_CALLS; $global:LASTEXITCODE=[int]$env:MODEL_TARGET_EXIT; return ('{"state":"'+$env:MODEL_STATE+'"}') }
 if ($args[0] -eq 'scripts/check_ci_green.py') { 'ci' >> $env:MODEL_CALLS; if ($args[2] -ne $env:MODEL_SHA) { throw 'CI target changed' }; $global:LASTEXITCODE=0; return }
 if ($args[0] -eq '-c') { 'version' >> $env:MODEL_CALLS; $global:LASTEXITCODE=0; return '2026.11.99' }
 if ($args[0] -eq 'tools/windows_release.py' -and $args[1] -eq 'plan') { 'plan' >> $env:MODEL_CALLS; $global:LASTEXITCODE=0; return }
 throw 'Unexpected Python or build invocation forbidden in this model.'
}
"""
                script.write_text(wrapper+'\ntry {\n'+body+'\n} catch { Write-Error $_ -ErrorAction Continue; exit 1 }\n',encoding='utf-8')
                env = dict(os.environ, MODEL_CALLS=str(calls), MODEL_SHA=A, RELEASE_TRIGGER_SHA=A,
                           MODEL_STATE=state, MODEL_TARGET_EXIT=str(target_exit), MODEL_REMOTE_SHA=B if state=='stale_skipped' else A,
                           RUNNER_TEMP=str(folder), GITHUB_OUTPUT=str(folder/'outputs'),
                           GITHUB_STEP_SUMMARY=str(folder/'summary'))
                result = subprocess.run([shell,'-NoProfile','-NonInteractive','-File',str(script)],
                                        env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=30)
                self.assertEqual(result.returncode,expected_exit,result.stdout+result.stderr)
                self.assertEqual(calls.read_text(encoding='utf-8-sig').splitlines(),expected_calls)
                self.assertEqual(sorted(p.name for p in folder.iterdir()),['calls.txt','probe.ps1'])


if __name__ == '__main__':
    unittest.main()
