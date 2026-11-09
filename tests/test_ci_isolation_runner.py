"""Controller contracts using synthetic metadata only; no Docker/app/DB access."""
from copy import deepcopy
import os
from pathlib import Path
import runpy
import subprocess
import sys
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
runner = runpy.run_path(str(ROOT / 'scripts/run_ci_isolated.py'))


def record():
    return {'Id': 'a' * 64, 'Image': 'sha256:' + 'b' * 64,
            'Config': {'Labels': {'wms.synthetic.run': 'c' * 32}, 'User': '10001:10001'},
            'HostConfig': {'ReadonlyRootfs': True, 'Privileged': False, 'NetworkMode': 'none',
                           'IpcMode': 'private',
                           'CapDrop': ['ALL'], 'SecurityOpt': ['no-new-privileges=true'],
                           'Tmpfs': {name: 'rw' for name in runner['STATE_MOUNTS']}},
            'Mounts': [{'Type': 'bind', 'Destination': '/run/wms-proof',
                        'Source': str(Path('/synthetic/proof')), 'RW': False}]}


def validate(data):
    runner['validate_inspect'](data, container='a' * 64, image='sha256:' + 'b' * 64,
                               nonce='c' * 32, proof_dir=Path('/synthetic/proof'))


def test_exact_container_contract_is_accepted():
    validate(record())


@pytest.mark.parametrize(('field', 'value'), [
    ('NetworkMode', 'host'), ('NetworkMode', 'bridge'), ('ReadonlyRootfs', False),
    ('Privileged', True), ('PidMode', 'host'), ('IpcMode', 'host'),
    ('CapAdd', ['SYS_ADMIN']), ('CapDrop', []), ('SecurityOpt', []),
    ('SecurityOpt', ['no-new-privileges=true', 'seccomp=unconfined']),
    ('Devices', [{'PathOnHost': '/synthetic/device'}]), ('VolumesFrom', ['unowned']),
    ('PortBindings', {'8080/tcp': [{'HostPort': '8080'}]}), ('Tmpfs', {}),
])
def test_unsafe_container_configuration_is_rejected(field, value):
    data = record(); data['HostConfig'][field] = value
    with pytest.raises(ValueError):
        validate(data)


@pytest.mark.parametrize('change', ['id', 'image', 'label', 'user', 'writable', 'foreign', 'extra', 'volume'])
def test_mismatched_ownership_or_host_mount_is_rejected(change):
    data = record()
    if change == 'id': data['Id'] = 'd' * 64
    if change == 'image': data['Image'] = 'sha256:' + 'd' * 64
    if change == 'label': data['Config']['Labels']['wms.synthetic.run'] = 'other'
    if change == 'user': data['Config']['User'] = '0'
    if change == 'writable': data['Mounts'][0]['RW'] = True
    if change == 'foreign': data['Mounts'][0]['Source'] = '/synthetic/foreign'
    if change == 'extra': data['Mounts'].append({'Type': 'bind', 'Source': '/unowned', 'Destination': '/unowned', 'RW': False})
    if change == 'volume': data['Mounts'].append({'Type': 'volume', 'Destination': '/data'})
    with pytest.raises(ValueError):
        validate(data)


@pytest.mark.parametrize('name', ['app/instance/inventory.db', 'backups/copy.bak', 'app/logs/app.log',
                                  '.env', 'app/.env.production', 'outputs/private.xlsx',
                                  '.git/config', 'app/static/uploads/private.png', 'saved.sqlite3-wal'])
def test_non_source_names_are_excluded_before_blob_reads(name):
    assert not runner['source_member'](name)


@pytest.mark.parametrize('name', ['/absolute.py', '../outside.py', 'app/../../outside.py', 'app\\alias.py'])
def test_aliases_are_rejected(name):
    with pytest.raises(ValueError):
        runner['source_member'](name)


def test_source_files_and_test_fixtures_remain_selected():
    for name in ('app/app.py', 'tests/test_orders.py', 'app/static/templates/example.xlsx', 'scripts/ci-test.Dockerfile'):
        assert runner['source_member'](name)


def test_empty_command_fails_before_engine_access():
    with mock.patch.dict(runner['main'].__globals__, {'docker_environment': lambda: pytest.fail('engine accessed')}):
        with pytest.raises(SystemExit) as error:
            runner['main']([])
        assert error.value.code != 0


def test_dispatch_positive_path_starts_explicit_synthetic_tests():
    # Unit-test the dispatch continuation separately from the real kernel probe.
    # No test app, network or subprocess is executed by these mock assertions.
    from scripts import linux_test_runtime
    sharded = runpy.run_path(str(ROOT / 'scripts/run_tests_sharded.py'))
    verify = runpy.run_path(str(ROOT / 'scripts/run_verify_parallel.py'))
    with mock.patch.object(linux_test_runtime, 'require_subprocess_boundary'), \
            mock.patch.dict(os.environ, {}, clear=True), mock.patch.object(sys, 'argv', ['synthetic']), \
            mock.patch.dict(sharded['main'].__globals__, {'collect': lambda *_: ['tests/test_synthetic.py']}), \
            mock.patch.object(subprocess, 'call', return_value=7) as execute:
        assert sharded['main']() == 7
        assert 'tests/test_synthetic.py' in execute.call_args.args[0]
        assert execute.call_args.kwargs['env']['DATABASE_URL'] == 'sqlite:///:memory:'
    with mock.patch.object(linux_test_runtime, 'require_subprocess_boundary'), \
            mock.patch.dict(os.environ, {}, clear=True), \
            mock.patch.dict(verify['_run_one'].__globals__, {'_is_pytest_style': lambda _: False}), \
            mock.patch.object(subprocess, 'run', return_value=subprocess.CompletedProcess([], 9, 'assertion failed', '')) as execute:
        result = verify['_run_one']('tests/verify_synthetic.py')
        assert result[1] == 9 and 'assertion failed' in result[3]
        assert execute.call_args.args[0][-1] == 'tests/verify_synthetic.py'


def test_kernel_capability_cannot_be_replaced_by_environment_only():
    from scripts.linux_test_runtime import require_linux_runtime
    with mock.patch.dict(os.environ, {'WMS_TEST_RUNTIME_PROOF': '/synthetic/forged-proof'}, clear=True):
        with pytest.raises(SystemExit, match='安全阻断'):
            require_linux_runtime()


def test_failed_assertions_are_preserved_in_the_exported_report(tmp_path, monkeypatch):
    verify = runpy.run_path(str(ROOT / 'scripts/run_verify_parallel.py'))
    monkeypatch.setitem(verify['_write_step_summary'].__globals__, 'REPO_ROOT', tmp_path)
    monkeypatch.delenv('GITHUB_STEP_SUMMARY', raising=False)
    verify['_write_step_summary']([('tests/verify_synthetic.py', 7, 0.2, 'assert 3 == 4')], 1, 0.2)
    report = (tmp_path / 'output/verify_failures_summary.md').read_text(encoding='utf-8')
    assert 'tests/verify_synthetic.py' in report and 'assert 3 == 4' in report and '7' in report


@pytest.mark.parametrize('exit_code', [0, 7, 124])
def test_container_parent_exports_reports_before_preserving_exit_code(tmp_path, monkeypatch, exit_code):
    import json
    entry = runpy.run_path(str(ROOT / 'scripts/ci_test_entry.py'))
    scope = entry['main'].__globals__
    proof = tmp_path / 'proof/proof.json'; proof.parent.mkdir(); proof.write_text('{}')
    request = tmp_path / 'request.json'
    request.write_text(json.dumps({'command': ['python', 'scripts/run_tests_sharded.py']}))
    complete = tmp_path / 'test-complete'
    def mapped_path(value):
        return {'/opt/wms-ci-request.json': request, '/work/test-complete': complete}.get(str(value), Path(value))
    monkeypatch.setitem(scope, 'PROFILE', tmp_path / 'profile')
    monkeypatch.setitem(scope, 'PROOF', proof)
    monkeypatch.setitem(scope, 'Path', mapped_path)
    monkeypatch.setitem(scope, 'require_linux_runtime', lambda: None)
    calls = []
    def execute(command, **kwargs):
        calls.append(command)
        if len(calls) == 1:
            return subprocess.CompletedProcess(command, 0)
        assert not complete.exists()
        if exit_code == 124:
            raise subprocess.TimeoutExpired(command, 1500)
        return subprocess.CompletedProcess(command, exit_code)
    def exported(_delay):
        assert json.loads(complete.read_text()) == {'exit_code': exit_code}
        (proof.parent / 'reports-exported').write_text('synthetic-export-complete')
    monkeypatch.setattr(subprocess, 'run', execute)
    monkeypatch.setattr(scope['time'], 'sleep', exported)
    assert entry['main']() == exit_code
    assert len(calls) == 2 and (proof.parent / 'reports-exported').exists()
