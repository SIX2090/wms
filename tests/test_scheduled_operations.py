"""Batch 2 acceptance design: only synthetic SQLite and owned child processes."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
import shutil
from datetime import datetime, timedelta, timezone

import pytest
import backup_scheduler as backups

REPO = Path(os.environ.get('REMEDIATION_REPO', Path(__file__).resolve().parents[1]))


def make_source(path):
    connection = sqlite3.connect(path)
    connection.execute('PRAGMA journal_mode=WAL')
    connection.execute('CREATE TABLE sample (value TEXT)')
    connection.execute("INSERT INTO sample VALUES ('first synthetic transaction')")
    connection.commit()
    return connection


def test_run_backup_for_source(tmp_path, monkeypatch):
    source = tmp_path / 'synthetic source #1.db'
    connection = make_source(source)
    try:
        connection.execute("INSERT INTO sample VALUES ('latest committed WAL transaction')")
        connection.commit()
        connection.execute("INSERT INTO sample VALUES ('uncommitted transaction')")
        directory = tmp_path / 'daily'
        monkeypatch.setenv('WMS_BACKUP_DIR', str(directory))
        target = backups.run_backup_for_source(source)
        with sqlite3.connect(target) as copy:
            assert copy.execute('PRAGMA integrity_check').fetchone() == ('ok',)
            assert copy.execute('SELECT value FROM sample').fetchall() == [
                ('first synthetic transaction',), ('latest committed WAL transaction',)]
        assert connection.execute('SELECT COUNT(*) FROM sample').fetchone() == (3,)
        connection.rollback()
        assert connection.execute('SELECT COUNT(*) FROM sample').fetchone() == (2,)
        status = backups.get_daily_backup_status()
        assert status['state'] == 'success' and status['last_success']
        assert target.name.startswith(backups.AUTO_BACKUP_PREFIX)
    finally:
        connection.close()


def test_failure_keeps_previous_success_and_backup(tmp_path, monkeypatch):
    source = tmp_path / 'synthetic.db'
    make_source(source).close()
    monkeypatch.setenv('WMS_BACKUP_DIR', str(tmp_path / 'daily'))
    target = backups.run_backup_for_source(source)
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    success = backups.get_daily_backup_status()['last_success']
    with pytest.raises(Exception):
        backups.run_backup_for_source(tmp_path / 'missing.db')
    status = backups.get_daily_backup_status()
    assert status['state'] == 'failure' and status['last_success'] == success
    assert hashlib.sha256(target.read_bytes()).hexdigest() == digest


def test_get_daily_backup_status(tmp_path, monkeypatch):
    directory = tmp_path / 'daily'
    monkeypatch.setenv('WMS_BACKUP_DIR', str(directory))
    assert backups.get_daily_backup_status()['state'] == 'unknown'
    assert not directory.exists()
    directory.mkdir()
    status = directory / '.daily-backup-status.json'
    status.write_text('{broken', encoding='utf-8')
    assert backups.get_daily_backup_status()['state'] == 'unknown'
    assert status.read_text(encoding='utf-8') == '{broken'
    stamp = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    status.write_text(json.dumps({'state': 'success', 'last_attempt': stamp,
                                  'last_success': stamp}), encoding='utf-8')
    assert backups.get_daily_backup_status()['state'] == 'stale'


def test_status_path_cannot_overwrite_the_source_database(tmp_path, monkeypatch):
    directory = tmp_path / 'daily'
    directory.mkdir()
    source = directory / '.daily-backup-status.json'
    make_source(source).close()
    before = source.read_bytes()
    monkeypatch.setenv('WMS_BACKUP_DIR', str(directory))
    with pytest.raises(ValueError, match='冲突'):
        backups.run_backup_for_source(source)
    assert source.read_bytes() == before


def test_cleanup_never_deletes_a_source_named_like_an_old_daily_backup(tmp_path, monkeypatch):
    directory = tmp_path / 'daily'
    directory.mkdir()
    source = directory / 'auto_daily_old_inventory.db'
    make_source(source).close()
    old = time.time() - 60 * 86400
    os.utime(source, (old, old))
    monkeypatch.setenv('WMS_BACKUP_DIR', str(directory))
    before = source.read_bytes()
    target = backups.run_backup_for_source(source)
    assert source.read_bytes() == before and target.exists()


def test_two_daily_runs_create_independent_verified_files(tmp_path, monkeypatch):
    source = tmp_path / 'source.db'
    make_source(source).close()
    monkeypatch.setenv('WMS_BACKUP_DIR', str(tmp_path / 'daily'))
    first, second = backups.run_backup_for_source(source), backups.run_backup_for_source(source)
    assert first != second and first.read_bytes() == second.read_bytes()


def test_backup_command_missing_source_fails_and_records_failure(tmp_path):
    directory = tmp_path / 'daily'
    env = dict(os.environ, AUTO_BACKUP_ENABLED='true')
    result = subprocess.run([sys.executable, str(REPO / 'tools/run_scheduled_backup.py'),
        '--source', str(tmp_path / 'missing.db'), '--directory', str(directory)],
        env=env, capture_output=True, text=True, timeout=20)
    assert result.returncode != 0
    state = json.loads((directory / '.daily-backup-status.json').read_text(encoding='utf-8'))
    assert state['state'] == 'failure' and state['last_success'] is None
    assert not list(directory.glob('*.db'))


def test_independent_backup_command_does_not_import_flask(tmp_path):
    source = tmp_path / 'synthetic.db'
    make_source(source).close()
    directory = tmp_path / 'daily'
    code = """
import runpy,sys
sys.argv=['run_scheduled_backup.py','--source',sys.argv[1],'--directory',sys.argv[2]]
try:
    runpy.run_path(%r,run_name='__main__')
except SystemExit as result:
    assert result.code in (0,None), result.code
assert 'flask' not in sys.modules and 'app' not in sys.modules
""" % str(REPO / 'tools/run_scheduled_backup.py')
    env = dict(os.environ, AUTO_BACKUP_ENABLED='true')
    result = subprocess.run([sys.executable, '-c', code, str(source), str(directory)],
                            env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert len(list(directory.glob('auto_daily_*.db'))) == 1


def supervisor(tmp_path, worker, *extra):
    return [sys.executable, str(REPO / 'tools/supervise_process.py'),
            '--state-directory', str(tmp_path / 'monitor'), '--max-restarts', '2',
            '--restart-delay', '0.01', *extra, '--', sys.executable, str(worker)]


def test_supervisor_retries_then_stops_after_success(tmp_path):
    marker = tmp_path / 'attempts.txt'
    worker = tmp_path / 'synthetic-worker.py'
    worker.write_text("from pathlib import Path\nimport sys\np=Path(%r)\n"
                      "n=int(p.read_text())+1 if p.exists() else 1\np.write_text(str(n))\n"
                      "sys.exit(17 if n<3 else 0)\n" % str(marker), encoding='utf-8')
    result = subprocess.run(supervisor(tmp_path, worker), capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
    assert marker.read_text() == '3'
    state = json.loads((tmp_path / 'monitor/supervisor-status.json').read_text())
    assert state['phase'] == 'stopped' and state['last_exit_code'] == 0


def test_supervisor_exhausted_budget_survives_next_task_trigger(tmp_path):
    marker = tmp_path / 'attempts.txt'
    worker = tmp_path / 'synthetic-worker.py'
    worker.write_text("from pathlib import Path\np=Path(%r)\n"
                      "p.write_text(p.read_text()+'x' if p.exists() else 'x')\nraise SystemExit(17)\n"
                      % str(marker), encoding='utf-8')
    command = supervisor(tmp_path, worker)
    result = subprocess.run(command, capture_output=True, text=True, timeout=20)
    assert result.returncode != 0
    assert marker.read_text() == 'xxx'
    result = subprocess.run(command, capture_output=True, text=True, timeout=20)
    assert result.returncode != 0
    assert marker.read_text() == 'xxx'
    state = json.loads((tmp_path / 'monitor/supervisor-status.json').read_text())
    assert state['phase'] == 'exhausted'


def test_supervisor_arguments_are_literal_and_not_shell_commands(tmp_path):
    output = tmp_path / 'arguments.json'
    worker = tmp_path / 'synthetic worker.py'
    worker.write_text('import json,sys\nfrom pathlib import Path\n'
                      'Path(%r).write_text(json.dumps(sys.argv[1:]),encoding="utf-8")\n'
                      % str(output), encoding='utf-8')
    arguments = ['spaces and 中文', '$(must-remain-text)', '& | <> ^ %PATH%', 'a"b']
    result = subprocess.run(supervisor(tmp_path, worker) + arguments,
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert json.loads(output.read_text(encoding='utf-8')) == arguments


def test_supervisor_invalid_state_and_missing_command_fail_closed(tmp_path):
    directory = tmp_path / 'monitor'
    directory.mkdir()
    path = directory / 'supervisor-status.json'
    path.write_text('{broken', encoding='utf-8')
    marker = tmp_path / 'must-not-exist.txt'
    worker = tmp_path / 'worker.py'
    worker.write_text('from pathlib import Path\nPath(%r).touch()\n' % str(marker), encoding='utf-8')
    result = subprocess.run(supervisor(tmp_path, worker), capture_output=True, text=True, timeout=15)
    assert result.returncode != 0 and not marker.exists()
    assert path.read_text(encoding='utf-8') == '{broken'
    result = subprocess.run(supervisor(tmp_path, tmp_path / 'missing-worker.py', '--reset-budget'),
                            capture_output=True, text=True, timeout=15)
    assert result.returncode != 0
    assert json.loads(path.read_text())['phase'] == 'exhausted'


def test_supervisor_duplicate_does_not_start_child_or_overwrite_owner_state(tmp_path):
    marker = tmp_path / 'attempts.txt'
    worker = tmp_path / 'synthetic-worker.py'
    worker.write_text("from pathlib import Path\nimport time\nPath(%r).write_text('owned')\n"
                      "time.sleep(4)\n" % str(marker), encoding='utf-8')
    owner = subprocess.Popen(supervisor(tmp_path, worker), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = time.monotonic() + 15
        while not marker.exists():
            assert owner.poll() is None and time.monotonic() < deadline
            time.sleep(0.05)
        path = tmp_path / 'monitor/supervisor-status.json'
        before = path.read_bytes()
        other = subprocess.run(supervisor(tmp_path, worker), capture_output=True, text=True, timeout=3)
        assert other.returncode != 0
        assert path.read_bytes() == before
        assert owner.wait(timeout=10) == 0
    finally:
        if owner.poll() is None:
            owner.terminate()
            owner.wait(timeout=10)


def test_portable_export_contains_and_runs_independent_operations(tmp_path):
    from tools.prepare_portable_sources import prepare_sources
    fixture = tmp_path / 'package-source'
    fixture.mkdir()
    (fixture / 'app').mkdir()
    (fixture / 'app/app.py').write_text('raise RuntimeError("WMS must never be imported")\n', encoding='utf-8')
    for name in ['app/runtime_guard.py', 'app/sqlite_snapshot.py', 'app/backup_scheduler.py',
                 'tools/run_scheduled_backup.py', 'tools/supervise_process.py',
                 'tools/configure_scheduled_operations.ps1']:
        destination = fixture / name
        destination.parent.mkdir(exist_ok=True)
        shutil.copy2(REPO / name, destination)
    for arguments in [['init', '-b', 'main'], ['add', '.'],
                      ['-c', 'user.name=Synthetic QA', '-c', 'user.email=qa@example.test',
                       'commit', '-m', 'synthetic program-only package']]:
        subprocess.run(['git', '-C', str(fixture), *arguments], check=True, capture_output=True, timeout=20)
    output = fixture / 'dist/candidate'
    prepare_sources(fixture, output)
    assert (output / 'tools/configure_scheduled_operations.ps1').is_file()
    assert (output / 'tools/supervise_process.py').is_file()
    source = tmp_path / 'synthetic.db'
    make_source(source).close()
    result = subprocess.run([sys.executable, str(output / 'tools/run_scheduled_backup.py'),
        '--source', str(source), '--directory', str(tmp_path / 'daily')],
        env=dict(os.environ, AUTO_BACKUP_ENABLED='true'), capture_output=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
    assert len(list((tmp_path / 'daily').glob('auto_daily_*.db'))) == 1
