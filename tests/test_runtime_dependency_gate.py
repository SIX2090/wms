"""IA-01: release checks must reject stale or shadowed runtime dependencies."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / 'tools/check_runtime_dependencies.py'


def run_check(requirements, extra_env=None):
    env = dict(os.environ, PYTHONIOENCODING='utf-8', **(extra_env or {}))
    return subprocess.run([sys.executable, str(CHECKER), '--requirements', str(requirements), '--json'],
                          cwd=requirements.parent, env=env, capture_output=True, text=True,
                          encoding='utf-8', timeout=30)


def test_certifi_is_explicitly_pinned_to_patched_release():
    lines = (ROOT / 'app/requirements.txt').read_text(encoding='utf-8').splitlines()
    assert 'certifi==2026.10.18' in lines


def test_actual_release_dependencies_and_imports_match():
    result = run_check(ROOT / 'app/requirements.txt')
    assert result.returncode == 0, result.stderr + result.stdout
    report = json.loads(result.stdout)
    assert report['success'] is True and not report['failures']
    for name in ('pypdf', 'certifi'):
        item = next(row for row in report['packages'] if row['name'] == name)
        assert item['loaded_version'] == item['installed'] == item['required']
        assert Path(item['module_file']).is_file()


def test_stale_environment_refused_without_app_or_database_access(tmp_path):
    requirements = tmp_path / 'requirements.txt'
    requirements.write_text('pypdf==0.0.1\n', encoding='utf-8')
    database = tmp_path / 'must-not-open.db'
    database.write_bytes(b'synthetic sentinel, not a database')
    result = run_check(requirements, {'DATABASE_URL': 'sqlite:///' + database.as_posix()})
    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert report['success'] is False
    assert any('pypdf' in item and '0.0.1' in item for item in report['failures'])
    assert database.read_bytes() == b'synthetic sentinel, not a database'


def test_shadowed_import_rejected_even_if_distribution_metadata_matches(tmp_path):
    from importlib.metadata import version
    requirements = tmp_path / 'requirements.txt'
    requirements.write_text('pypdf==' + version('pypdf') + '\n', encoding='utf-8')
    (tmp_path / 'pypdf.py').write_text('__version__ = "0.0.1"\n', encoding='utf-8')
    result = run_check(requirements, {'PYTHONPATH': str(tmp_path)})
    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert report['packages'][0]['installed'] == version('pypdf')
    assert report['packages'][0]['loaded_version'] == '0.0.1'
    assert report['failures']


@pytest.mark.parametrize('content', ['', 'requests>=2\n', '-r other.txt\n',
                                   'flask==1\nFlask==2\n', 'invalid @ https://example.invalid/x\n'])
def test_invalid_or_unlocked_manifest_is_not_accepted(tmp_path, content):
    requirements = tmp_path / 'requirements.txt'
    requirements.write_text(content, encoding='utf-8')
    result = run_check(requirements)
    assert result.returncode == 1
    assert json.loads(result.stdout)['failures']


def test_portable_check_runs_dependency_gate_before_initialization(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location('portable_runtime_gate', ROOT / 'tools/check_portable_runtime.py')
    runtime = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runtime)
    package = tmp_path / 'package'
    (package / 'python').mkdir(parents=True)
    (package / 'python/python.exe').write_bytes(b'synthetic executable placeholder')
    calls = []
    def refuse(command, **kwargs):
        calls.append(command)
        assert kwargs['env']['WMS_LOCAL_PRINT_AGENT'] == '0'
        assert kwargs['env']['WMS_SKIP_STARTUP_BACKUP'] == '1'
        assert kwargs['env']['AUTO_BACKUP_ENABLED'] == 'false'
        assert str(package) not in kwargs['env']['WMS_BACKUP_DIR']
        if any('check_runtime_dependencies.py' in str(part) for part in command):
            raise subprocess.CalledProcessError(1, command)
        raise AssertionError('Dependency gate must precede initialization and other imports')
    monkeypatch.setattr(runtime.subprocess, 'run', refuse)
    with pytest.raises(subprocess.CalledProcessError):
        runtime.verify_package(package)
    assert len(calls) == 1
    assert not (package / 'app').exists()
