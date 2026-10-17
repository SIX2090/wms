"""Repair task: AUDIT-FULL-20261016-001-F06; no production build/download."""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('portable_sources', ROOT / 'tools/prepare_portable_sources.py')
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


def git(root, *args):
    return subprocess.run(['git', '-C', str(root), *args], check=True, capture_output=True)


@pytest.fixture
def repository(tmp_path):
    root = tmp_path / 'source repository'
    root.mkdir()
    git(root, 'init', '-b', 'main')
    git(root, 'config', 'user.name', 'Package Test')
    git(root, 'config', 'user.email', 'package@example.invalid')
    files = {'app/app.py': b'# committed application', 'app/config.py': b'# committed defaults',
             'app/requirements.txt': b'', 'app/static/js/grid.js': b'const safe = true;',
             'tools/helper.py': b'# committed helper'}
    for name, data in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    shutil.copyfile(ROOT / 'tools/prepare_portable_sources.py', root / 'tools/prepare_portable_sources.py')
    git(root, 'add', '.')
    git(root, 'commit', '-m', 'test fixture')
    (root / 'wheelhouse').mkdir()
    return root


def test_prepare_sources_exports_committed_files_ignores_local_files(repository):
    local = repository / 'app/operator-private.txt'
    local.write_bytes(b'synthetic private local content')
    output = repository / 'dist/package one'
    assert builder.prepare_sources(repository, output) == 6
    assert (output / 'app/app.py').read_bytes() == b'# committed application'
    assert not (output / 'app/operator-private.txt').exists()
    assert local.read_bytes() == b'synthetic private local content'


@pytest.mark.parametrize('name', ['app/instance/inventory.db', 'app/static/uploads/image.bin',
    'app/backups/snapshot.bin', 'tools/logs/private.log', 'app/.env', 'tools/.env.local',
    'app/extra.sqlite', 'app/extra.sqlite3-wal', 'app/extra.db-shm', 'tools/client.key',
    'tools/cert.pem', 'app/client.pfx', 'app/signing.keystore', 'app/app.py.bak_old', 'app/running.flag'])
def test_prepare_sources_excludes_even_tracked_private_files(repository, name):
    path = repository / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'synthetic private content')
    git(repository, 'add', '.')
    git(repository, 'commit', '-m', 'synthetic private fixture')
    output = repository / 'dist/new'
    builder.prepare_sources(repository, output)
    assert not (output / name).exists()
    assert path.read_bytes() == b'synthetic private content'


@pytest.mark.parametrize('target', ['root', 'app', 'sibling', 'dist', 'nested', 'existing'])
def test_prepare_sources_refuses_protected_or_existing_directories(repository, target):
    choices = {'root':repository, 'app':repository / 'app', 'sibling':repository.parent / 'other',
               'dist':repository / 'dist', 'nested':repository / 'dist/a/b',
               'existing':repository / 'dist/old'}
    destination = choices[target]
    destination.mkdir(parents=True, exist_ok=True)
    marker = destination / 'operator.txt'
    marker.write_bytes(b'keep')
    with pytest.raises(ValueError):
        builder.prepare_sources(repository, destination)
    assert marker.read_bytes() == b'keep'
    assert (repository / 'app/app.py').is_file()


def test_prepare_sources_dirty_tracked_program_refuses_before_output(repository):
    (repository / 'app/config.py').write_bytes(b'# local customized config')
    with pytest.raises(subprocess.CalledProcessError):
        builder.prepare_sources(repository, repository / 'dist/new')
    assert not (repository / 'dist').exists()


def test_prepare_sources_refuses_linked_output(repository):
    elsewhere = repository.parent / 'elsewhere'
    elsewhere.mkdir()
    try:
        (repository / 'dist').symlink_to(elsewhere, target_is_directory=True)
    except OSError:
        if os.name != 'nt':
            raise
        subprocess.run(['cmd', '/c', 'mklink', '/J', str(repository / 'dist'), str(elsewhere)],
                       check=True, capture_output=True)
    with pytest.raises(ValueError):
        builder.prepare_sources(repository, repository / 'dist/new')
    assert list(elsewhere.iterdir()) == []


def test_prepare_sources_cli_invalid_output_returns_failure_without_writes(repository):
    result = subprocess.run([sys.executable, str(ROOT / 'tools/prepare_portable_sources.py'),
        '--root', str(repository), '--dist', str(repository)], capture_output=True)
    assert result.returncode == 1
    assert (repository / 'app/app.py').exists()


@pytest.mark.skipif(os.name != 'nt', reason='Windows native PowerShell build entry')
@pytest.mark.parametrize('target', ['root', 'app', 'existing', 'outside', 'fresh'])
def test_native_builder_preserves_directories_and_exports_only_program(repository, target):
    sandbox = repository.parent.resolve()
    assert sandbox.is_relative_to(Path(tempfile.gettempdir()).resolve())
    choices = {'root':repository, 'app':repository / 'app', 'existing':repository / 'dist/old',
               'outside':sandbox / 'outside', 'fresh':repository / 'dist/new'}
    destination = choices[target]
    assert destination.resolve().is_relative_to(sandbox) and destination.resolve() != sandbox
    marker = None
    if target != 'fresh':
        destination.mkdir(parents=True, exist_ok=True)
        marker = destination / 'operator.txt'
        marker.write_bytes(b'keep')
    local = repository / 'app/private-operator-note.txt'
    local.write_bytes(b'synthetic private local content')
    source = (ROOT / 'tools/build_portable_dist.ps1').read_text(encoding='utf-8')
    # Execute the real preparation/copy prefix only. No network, pip, launchers or runtime.
    script = sandbox / 'bounded-build.ps1'
    script.write_text(source[:source.index('Get-ChildItem -LiteralPath $dist')], encoding='utf-8-sig')
    result = subprocess.run(['powershell', '-NoProfile', '-File', str(script),
        '-RootDir', str(repository), '-DistDir', str(destination)], capture_output=True, timeout=40)
    if target == 'fresh':
        assert result.returncode == 0, result.stderr.decode(errors='replace')
        assert (destination / 'app/app.py').read_bytes() == b'# committed application'
        assert not (destination / 'app/private-operator-note.txt').exists()
    else:
        assert result.returncode != 0
        assert marker.read_bytes() == b'keep'
    assert local.read_bytes() == b'synthetic private local content'
