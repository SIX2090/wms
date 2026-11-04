"""Disposable files only: failed snapshots must preserve earlier valid backups."""
from contextlib import closing
from datetime import datetime
import hashlib
import importlib.util
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


def make_database(path, value=42):
    with closing(sqlite3.connect(path)) as conn:
        conn.execute('CREATE TABLE marker(value INTEGER)')
        conn.execute('INSERT INTO marker VALUES (?)', (value,))
        conn.commit()
    return path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def backup_cli(source, target):
    return subprocess.run([sys.executable, str(ROOT / 'scripts/online_backup.py'), str(source), str(target)],
                          capture_output=True, timeout=3)


@pytest.mark.parametrize('existing', [True, False])
def test_failed_cli_preserves_previous_backup(tmp_path, existing):
    source = tmp_path / 'broken.db'; source.write_bytes(b'synthetic invalid sqlite')
    target = tmp_path / 'snapshot.db'
    before = digest(make_database(target)) if existing else None
    result = backup_cli(source, target)
    assert result.returncode == 2
    assert target.exists() == existing
    if existing:
        assert digest(target) == before


@pytest.mark.parametrize('alias', ['same', 'hardlink'])
def test_cli_rejects_source_alias_without_touching_source(tmp_path, alias):
    source = make_database(tmp_path / 'source.db')
    target = source if alias == 'same' else tmp_path / 'alias.db'
    if alias == 'hardlink':
        os.link(source, target)
    before = digest(source)
    result = backup_cli(source, target)
    assert result.returncode == 2
    assert digest(source) == before
    assert digest(target) == before


@pytest.mark.parametrize('name', ['合成 # source.db', '合成 ? source.db'] if os.name != 'nt' else ['合成 # source.db'])
def test_cli_escapes_source_uri(tmp_path, name):
    source = make_database(tmp_path / name)
    target = tmp_path / 'backup.db'
    assert backup_cli(source, target).returncode == 0
    with closing(sqlite3.connect(target)) as conn:
        assert conn.execute('SELECT value FROM marker').fetchall() == [(42,)]


def test_cli_successfully_replaces_complete_backup(tmp_path):
    source = make_database(tmp_path / 'source.db', 12)
    target = make_database(tmp_path / 'backup.db', 99)
    original = digest(source)
    assert backup_cli(source, target).returncode == 0
    assert digest(source) == original
    with closing(sqlite3.connect(target)) as conn:
        assert conn.execute('PRAGMA integrity_check').fetchone() == ('ok',)
        assert conn.execute('SELECT value FROM marker').fetchall() == [(12,)]


def test_cli_reads_committed_wal_while_source_stays_open(tmp_path):
    source = make_database(tmp_path / 'source.db', 1)
    with closing(sqlite3.connect(source)) as conn:
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('UPDATE marker SET value=7'); conn.commit()
        target = tmp_path / 'backup.db'
        assert backup_cli(source, target).returncode == 0
        with closing(sqlite3.connect(target)) as snapshot:
            assert snapshot.execute('SELECT value FROM marker').fetchall() == [(7,)]
        assert conn.execute('SELECT value FROM marker').fetchall() == [(7,)]


def test_failed_startup_preserves_existing_same_name_snapshot(tmp_path, monkeypatch):
    import app as w
    source = tmp_path / 'broken.db'; source.write_bytes(b'synthetic invalid sqlite')
    folder = tmp_path / 'backups'; folder.mkdir()
    previous = make_database(folder / 'auto_startup_20261104_120000.db')
    before = digest(previous)

    class Frozen(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 11, 4, 12)

    monkeypatch.setattr(w, 'datetime', Frozen)
    monkeypatch.setitem(w.app.config, 'TESTING', False)
    monkeypatch.setitem(w.app.config, 'SQLALCHEMY_DATABASE_URI', 'sqlite:///' + source.as_posix())
    monkeypatch.setitem(w.app.config, 'BACKUP_FOLDER', str(folder))
    monkeypatch.delenv('WMS_SKIP_STARTUP_BACKUP', raising=False)
    monkeypatch.setenv('WMS_STARTUP_BACKUP_MIN_INTERVAL_SECONDS', '0')
    w.backup_sqlite_on_startup()
    assert previous.exists() and digest(previous) == before


@pytest.mark.parametrize('phase', ['copy', 'timeout', 'fsync', 'publish'])
def test_snapshot_connection(tmp_path, monkeypatch, phase):
    import sqlite_snapshot as snapshots
    source = make_database(tmp_path / 'source.db', 1)
    target = make_database(tmp_path / 'snapshot.db', 2)
    source_before, target_before = digest(source), digest(target)

    def fail(*args, **kwargs):
        raise OSError('synthetic failure')

    with closing(sqlite3.connect(source)) as conn:
        selected = conn
        if phase == 'copy':
            class BrokenCopy:
                def execute(self, statement):
                    return conn.execute(statement)

                def backup(self, output, **kwargs):
                    output.execute('CREATE TABLE partial(value)')
                    fail()

            selected = BrokenCopy()
        elif phase == 'timeout':
            clock = iter([0, 31])
            monkeypatch.setattr(snapshots.time, 'monotonic', lambda: next(clock))
        elif phase == 'fsync':
            monkeypatch.setattr(snapshots.os, 'fsync', fail)
        else:
            monkeypatch.setattr(snapshots.os, 'replace', fail)
        with pytest.raises(OSError):
            snapshots.snapshot_connection(selected, target)
    assert digest(source) == source_before and digest(target) == target_before
    assert not list(tmp_path.glob('.wms-snapshot-*'))


def test_create_snapshot_refuses_destination_sidecars_without_deleting_them(tmp_path):
    from sqlite_snapshot import create_snapshot
    source = make_database(tmp_path / 'source.db', 1)
    target = make_database(tmp_path / 'snapshot.db', 2)
    before = digest(target)
    sidecar = tmp_path / 'snapshot.db-wal'; sidecar.write_bytes(b'synthetic busy marker')
    with pytest.raises(OSError, match='旁文件'):
        create_snapshot(source, target)
    assert digest(target) == before and sidecar.read_bytes() == b'synthetic busy marker'


@pytest.mark.parametrize('script,function', [('data_repairs', '_connect'), ('merge_duplicate_materials', 'connect')])
@pytest.mark.parametrize('readonly', [True, False])
def test_maintenance_connection_uses_exact_uri_filename(tmp_path, script, function, readonly):
    source = make_database(tmp_path / '合成 # exact.db')
    before = digest(source)
    spec = importlib.util.spec_from_file_location('synthetic_' + script, ROOT / 'scripts' / (script + '.py'))
    tool = importlib.util.module_from_spec(spec); spec.loader.exec_module(tool)
    with closing(getattr(tool, function)(str(source), readonly)) as conn:
        assert conn.execute('SELECT value FROM marker').fetchall()[0][0] == 42
        if readonly:
            with pytest.raises(sqlite3.OperationalError):
                conn.execute('UPDATE marker SET value=99')
    assert digest(source) == before
    assert sorted(p.name for p in tmp_path.iterdir()) == [source.name]


def test_create_sqlite_online_backup_uses_exact_source_and_validates(tmp_path):
    import app as w
    source = make_database(tmp_path / '合成 # app.db')
    target = tmp_path / 'snapshot.db'
    w.create_sqlite_online_backup(source, target)
    with closing(sqlite3.connect(target)) as conn:
        assert conn.execute('SELECT value FROM marker').fetchall() == [(42,)]


def test_backup_database_uses_exact_source_filename(tmp_path, monkeypatch):
    import auto_update
    folder = tmp_path / '合成 # deployment'; (folder / 'app' / 'instance').mkdir(parents=True)
    make_database(folder / 'app' / 'instance' / 'inventory.db')
    monkeypatch.setattr(auto_update, 'APP_DIR', folder / 'app')
    monkeypatch.setattr(auto_update, 'ROOT_DIR', folder)
    monkeypatch.setattr(auto_update, 'log', lambda *args: None)
    assert auto_update.backup_database() is True
    snapshots = list((folder / 'backups').glob('before_auto_update_*.db'))
    assert len(snapshots) == 1
    with closing(sqlite3.connect(snapshots[0])) as conn:
        assert conn.execute('SELECT value FROM marker').fetchall() == [(42,)]


def test_create_snapshot(tmp_path, monkeypatch):
    import sqlite_snapshot as snapshots
    source = make_database(tmp_path / 'source.db', 1)
    target = make_database(tmp_path / 'snapshot.db', 2)
    before = digest(target)
    connect = sqlite3.connect

    class FailedIntegrity(sqlite3.Connection):
        def execute(self, statement, *args):
            if statement == 'PRAGMA integrity_check':
                return super().execute("SELECT 'synthetic integrity failure'")
            return super().execute(statement, *args)

    monkeypatch.setattr(snapshots.sqlite3, 'connect', lambda *args, **kwargs: connect(*args, **kwargs, factory=FailedIntegrity))
    with pytest.raises(sqlite3.DatabaseError, match='完整性'):
        snapshots.create_snapshot(source, target)
    assert digest(target) == before and not list(tmp_path.glob('.wms-snapshot-*'))


def test_create_snapshot_rechecks_destination_before_publication(tmp_path, monkeypatch):
    import sqlite_snapshot as snapshots
    source = make_database(tmp_path / 'source.db', 1)
    target = make_database(tmp_path / 'snapshot.db', 2)
    before = digest(target)
    sidecar = tmp_path / 'snapshot.db-wal'
    fsync = os.fsync

    def open_destination(descriptor):
        fsync(descriptor)
        sidecar.write_bytes(b'synthetic opened-during-backup')

    monkeypatch.setattr(snapshots.os, 'fsync', open_destination)
    with pytest.raises(OSError, match='发布前'):
        snapshots.create_snapshot(source, target)
    assert digest(target) == before and sidecar.read_bytes() == b'synthetic opened-during-backup'
    assert not list(tmp_path.glob('.wms-snapshot-*'))
