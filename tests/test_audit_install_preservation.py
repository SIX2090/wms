"""Repair task: AUDIT-FULL-20261016-001-F05；只执行有严格边界的临时安装片段。"""
from contextlib import closing
import hashlib
import importlib.util
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('install_restore_validator', ROOT / 'scripts/restore_backup.py')
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)
SCRIPTS = ['install.bat', 'install_e_wms.bat']


def database(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    for table, columns in validator.REQUIRED_SCHEMA.items():
        fields = ', '.join('"' + column + '" TEXT' for column in sorted(columns))
        connection.execute(f'CREATE TABLE "{table}" ({fields})')
    connection.execute('CREATE TABLE business (value TEXT)')
    connection.execute("INSERT INTO business VALUES ('keep')")
    connection.commit()
    return connection


def layout(tmp_path):
    # The old failure routine recursively deletes INSTALL_DIR. Never allow a
    # supplied pytest basetemp outside the OS temporary directory to execute it.
    sandbox = tmp_path.resolve()
    system_temp = Path(tempfile.gettempdir()).resolve()
    assert sandbox.is_relative_to(system_temp) and sandbox != system_temp
    target, package, profile = [sandbox / name for name in ['existing WMS', 'package', 'profile']]
    for path in [target, package, profile]:
        assert path.resolve().is_relative_to(sandbox) and path.resolve() != sandbox
    for folder in [target / 'instance', target / 'backups', target / 'static/uploads', target / 'logs',
                   package / 'app', package / 'scripts', profile / 'Desktop']:
        folder.mkdir(parents=True, exist_ok=True)
    files = {
        target / 'app.py': b'old program', target / 'config.py': b'old customized config',
        target / '.env': b'LOCAL_SETTING=synthetic-keep', target / 'instance/secret_key': b'local-test-key',
        target / 'extra.sqlite': b'other local database', target / 'static/uploads/photo.bin': b'operator image',
        target / 'backups/keep.db': b'operator backup', target / 'logs/keep.log': b'operator log',
        target / 'customer-notes.txt': b'unknown local file', profile / 'Desktop/WMS.lnk': b'old shortcut',
        package / 'app/app.py': b'new program', package / 'app/config.py': b'new program config',
        package / 'app/.env': b'packaged environment must not overwrite',
        package / 'app/extra.sqlite': b'packaged database must not overwrite',
        package / 'app/instance/secret_key': b'packaged key must not overwrite',
        package / 'app/static/uploads/photo.bin': b'packaged image must not overwrite',
        package / 'app/backups/keep.db': b'packaged backup must not overwrite',
        package / 'app/logs/keep.log': b'packaged log must not overwrite',
    }
    for path, content in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    for name in ['online_backup.py', 'restore_backup.py']:
        shutil.copyfile(ROOT / 'scripts' / name, package / 'scripts' / name)
    shutil.copyfile(ROOT / 'app/runtime_guard.py', package / 'app/runtime_guard.py')
    with closing(database(target / 'instance/inventory.db')):
        pass
    return target, package, profile


def source(name):
    return (ROOT / name).read_text(encoding='utf-8')


def failure_functions(text):
    start = text.index('\n:log\n') + 1
    return text[start:text.index('\n:main\n', start)]


def stage(text, first, next_step):
    start = text.index(f'call :log "[{first}/8]')
    return text[start:text.index(f'call :log "[{next_step}/8]', start)]


def run_fragment(tmp_path, name, target, package, profile, body, extra=None):
    sandbox = tmp_path.resolve()
    assert sandbox.is_relative_to(Path(tempfile.gettempdir()).resolve())
    for directory in [target, package, profile]:
        assert directory.resolve().is_relative_to(sandbox) and directory.resolve() != sandbox
    values = {'INSTALL_DIR': target, 'RUN_DIR': target, 'APP_SRC': package / 'app', 'PKG_DIR': package,
              'USERPROFILE': profile, 'PYTHON_EXE': sys.executable, 'STAMP': 'fixture',
              'INSTALL_LOG': sandbox / 'install-fixture.log', 'CONSOLE_OK': '0',
              'COPIED_FILES': '1', 'IN_PLACE_INSTALL': ''}
    values.update(extra or {})
    text = '@echo off\nsetlocal EnableExtensions EnableDelayedExpansion\n'
    text += '\n'.join(f'set "{key}={value}"' for key, value in values.items())
    text += '\ngoto :run_test\n' + failure_functions(source(name))
    text += '\n:run_test\n' + body + '\n'
    harness = sandbox / 'failure-harness.bat'
    harness.write_bytes(text.replace('\n', '\r\n').encode('utf-8'))
    env = dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8', PYTHONPATH=str(target),
               DATABASE_URL='sqlite:///:memory:', FLASK_ENV='testing')
    return subprocess.run(['cmd.exe', '/d', '/c', str(harness)], cwd=target, env=env,
                          stdin=subprocess.DEVNULL, capture_output=True, timeout=60,
                          creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))


def protected_files(target, profile):
    paths = [target / name for name in ['.env', 'instance/inventory.db', 'instance/secret_key', 'extra.sqlite',
                                      'static/uploads/photo.bin', 'backups/keep.db', 'logs/keep.log',
                                      'customer-notes.txt']]
    paths.append(profile / 'Desktop/WMS.lnk')
    return {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def unchanged(expected):
    for path, digest in expected.items():
        assert path.is_file(), f'已有文件被删除：{path}'
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest, f'已有文件被覆盖：{path}'


@pytest.mark.skipif(os.name != 'nt', reason='Windows bounded cmd failure handler')
@pytest.mark.parametrize('name', SCRIPTS)
@pytest.mark.parametrize('mode', ['before-copy', 'after-copy', 'in-place'])
def test_failure_keeps_entire_existing_directory_and_shortcut(tmp_path, name, mode):
    target, package, profile = layout(tmp_path)
    expected = protected_files(target, profile)
    extra = {'COPIED_FILES': ''} if mode == 'before-copy' else {'IN_PLACE_INSTALL': '1'} if mode == 'in-place' else {}
    result = run_fragment(tmp_path, name, target, package, profile,
                          'call :do_rollback\nexit /b !ERRORLEVEL!', extra)
    assert result.returncode != 0
    unchanged(expected)
    assert b'rolled back' not in result.stdout + result.stderr


@pytest.mark.skipif(os.name != 'nt', reason='Windows bounded robocopy failure injection')
@pytest.mark.parametrize('name', SCRIPTS)
@pytest.mark.parametrize('failure', ['copy', 'later-dependency'])
def test_copy_or_dependency_failure_does_not_remove_business_files(tmp_path, name, failure):
    target, package, profile = layout(tmp_path)
    expected = protected_files(target, profile)
    extra = {'APP_SRC': package / 'nonexistent-source'} if failure == 'copy' else None
    body = stage(source(name), 3, 4) + '\ncall :do_rollback\nexit /b 1'
    result = run_fragment(tmp_path, name, target, package, profile, body, extra)
    assert result.returncode != 0
    unchanged(expected)


@pytest.mark.skipif(os.name != 'nt', reason='Windows consistent backup and copy stage')
@pytest.mark.parametrize('name', SCRIPTS)
def test_copy_protects_local_data_and_backup_contains_committed_wal(tmp_path, name):
    target, package, profile = layout(tmp_path)
    connection = sqlite3.connect(target / 'instance/inventory.db')
    try:
        connection.execute('PRAGMA journal_mode=WAL')
        connection.execute('PRAGMA wal_autocheckpoint=0')
        connection.execute("INSERT INTO business VALUES ('latest WAL row')")
        connection.commit()
        assert Path(str(target / 'instance/inventory.db') + '-wal').stat().st_size > 0
        expected = protected_files(target, profile)
        config = (target / 'config.py').read_bytes()
        result = run_fragment(tmp_path, name, target, package, profile, stage(source(name), 3, 4) + '\nexit /b 0')
        assert result.returncode == 0, result.stderr.decode('utf-8', errors='replace')
        unchanged(expected)
        assert (target / 'backups/before_offline_install_fixture_config.py').read_bytes() == config
        with closing(sqlite3.connect(target / 'backups/before_offline_install_fixture_inventory.db')) as backup:
            assert backup.execute('SELECT value FROM business ORDER BY rowid').fetchall() == [('keep',), ('latest WAL row',)]
    finally:
        connection.close()


def fake_app(target):
    (target / 'app.py').write_text('''
from pathlib import Path
import os
class Context:
    def push(self): pass
    def pop(self): pass
class Application:
    def app_context(self): return Context()
app=Application()
def initialize_database():
    Path(__file__).with_name('init.marker').write_text('called')
    if os.environ.get('FIXTURE_INIT_FAIL') == '1':
        Path(__file__).with_name('instance').joinpath('inventory.db').write_bytes(b'partial fresh initialization')
        raise RuntimeError('synthetic initialization failure')
''', encoding='utf-8')


@pytest.mark.skipif(os.name != 'nt', reason='Windows initializer stage with fake app only')
@pytest.mark.parametrize('name', SCRIPTS)
@pytest.mark.parametrize('valid', [True, False])
def test_existing_database_is_never_initialized_again(tmp_path, name, valid):
    target, package, profile = layout(tmp_path)
    fake_app(target)
    if not valid:
        (target / 'instance/inventory.db').write_bytes(b'partial/corrupt existing file')
    expected = protected_files(target, profile)
    result = run_fragment(tmp_path, name, target, package, profile, stage(source(name), 6, 7) + '\nexit /b 0')
    assert (result.returncode == 0) == valid
    assert not (target / 'init.marker').exists()
    unchanged(expected)


@pytest.mark.skipif(os.name != 'nt', reason='Windows fresh initialization with fake app')
@pytest.mark.parametrize('name', SCRIPTS)
@pytest.mark.parametrize('fails', [True, False])
def test_fresh_initialization_runs_once_and_failure_retains_files(tmp_path, name, fails):
    target, package, profile = layout(tmp_path)
    fake_app(target)
    (target / 'instance/inventory.db').unlink()  # synthetic file in the verified sandbox only
    result = run_fragment(tmp_path, name, target, package, profile, stage(source(name), 6, 7) + '\nexit /b 0',
                          {'FIXTURE_INIT_FAIL': '1' if fails else ''})
    assert (result.returncode != 0) == fails
    assert (target / 'init.marker').read_text() == 'called'
    assert (target / 'instance/secret_key').read_bytes() == b'local-test-key'
    assert (profile / 'Desktop/WMS.lnk').read_bytes() == b'old shortcut'


@pytest.mark.skipif(os.name != 'nt', reason='Windows installation completion marker failure')
@pytest.mark.parametrize('name', SCRIPTS)
def test_marker_write_failure_cannot_report_success(tmp_path, name):
    target, package, profile = layout(tmp_path)
    expected = protected_files(target, profile)
    text = source(name)
    body = text[text.index('REM === write installation marker flag'):]
    result = run_fragment(tmp_path, name, target, package, profile, body,
                          {'RUN_DIR': tmp_path / 'missing-parent' / 'missing-install'})
    assert result.returncode != 0
    unchanged(expected)
    log = (tmp_path / 'install-fixture.log').read_bytes()
    assert b'Installation flag written' not in log
    assert b'WMS installation completed successfully' not in log


@pytest.mark.skipif(os.name != 'nt', reason='Windows locale-independent backup identifiers')
@pytest.mark.parametrize('name', SCRIPTS)
def test_backup_identifier_is_unique_and_safe_for_windows_filenames(tmp_path, name):
    target, package, profile = layout(tmp_path)
    text = source(name)
    block = text[text.index('set "STAMP="'):text.index('set "INSTALL_LOG=')]
    body = block + '\n> "%PKG_DIR%\\stamp.marker" echo !STAMP!\nexit /b 0'
    observed = []
    for _ in range(2):
        assert run_fragment(tmp_path, name, target, package, profile, body).returncode == 0
        value = (package / 'stamp.marker').read_text().strip()
        assert re.fullmatch(r'\d{8}_\d{6}_\d{7}_[0-9a-f]{8}', value)
        observed.append(value)
    assert len(set(observed)) == 2


@pytest.mark.parametrize('name', SCRIPTS)
def test_failure_handler_has_no_recursive_cleanup_or_shortcut_deletion(name):
    handler = failure_functions(source(name))
    assert 'rd /s /q' not in handler.lower()
    assert 'del /q' not in handler.lower()
    assert 'rolled back' not in handler.lower()


def test_validate_only_is_readonly_and_never_acquires_restore_lease(tmp_path, monkeypatch):
    path = tmp_path / 'existing.db'
    with closing(database(path)):
        pass
    before = path.read_bytes()
    lease = MagicMock(side_effect=AssertionError('validation cannot enter restore'))
    monkeypatch.setattr(validator, 'acquire_database_lease', lease)
    target = tmp_path / 'not-created' / 'inventory.db'
    assert validator.main([str(path), '--validate-only', '--db', str(target)]) == 0
    assert path.read_bytes() == before
    assert not target.parent.exists()
    lease.assert_not_called()


@pytest.mark.parametrize('kind', ['missing', 'corrupt', 'unrelated'])
def test_validate_only_rejects_non_wms_without_creating_or_restoring(tmp_path, kind):
    path = tmp_path / 'candidate.db'
    if kind == 'corrupt':
        path.write_bytes(b'not sqlite')
    elif kind == 'unrelated':
        with closing(sqlite3.connect(path)) as connection:
            connection.execute('CREATE TABLE unrelated (id INTEGER)')
            connection.commit()
    before = path.read_bytes() if path.exists() else None
    try:
        result = validator.main([str(path), '--validate-only', '--db', str(tmp_path / 'unused.db')])
    except SystemExit as exc:
        result = exc.code
    assert result != 0
    assert (path.read_bytes() if path.exists() else None) == before
    assert not (tmp_path / 'unused.db').exists()
