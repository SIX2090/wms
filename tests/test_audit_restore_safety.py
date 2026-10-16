"""AUDIT-FULL-20261016-001-F01: only disposable SQLite files are restored."""
import importlib.util
import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = {
    'material': 'id INTEGER PRIMARY KEY, code TEXT, stock REAL',
    'warehouse': 'id INTEGER PRIMARY KEY, name TEXT',
    'stock_transaction': 'id INTEGER PRIMARY KEY, material_id INTEGER, quantity REAL, warehouse_id INTEGER, created_at TEXT',
    'in_order': 'id INTEGER PRIMARY KEY, order_no TEXT, status TEXT',
    'out_order': 'id INTEGER PRIMARY KEY, order_no TEXT, status TEXT',
    'user': 'id INTEGER PRIMARY KEY, username TEXT, password_hash TEXT, role TEXT',
    'system_setting': 'id INTEGER PRIMARY KEY, key TEXT, value TEXT',
}


@pytest.fixture
def restore():
    spec = importlib.util.spec_from_file_location('audit_restore', ROOT / 'scripts/restore_backup.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _db(path, stock=2):
    with closing(sqlite3.connect(path)) as conn:
        for table, columns in SCHEMA.items():
            conn.execute(f'CREATE TABLE "{table}" ({columns})')
        conn.execute('INSERT INTO material VALUES (1, ?, ?)', ('TEST', stock))
        conn.commit()
    return path


def _stock(path):
    with closing(sqlite3.connect(path)) as conn:
        return conn.execute('SELECT stock FROM material').fetchone()[0]


def test_restore_rejects_unrelated_sqlite_without_changing_target(restore, tmp_path):
    source = tmp_path / 'other.db'
    with closing(sqlite3.connect(source)) as conn:
        conn.execute('CREATE TABLE unrelated_data (id INTEGER)')
        conn.commit()
    target = _db(tmp_path / 'target.db')
    before = target.read_bytes()
    assert restore.main([str(source), '--db', str(target), '--yes']) == 2
    assert target.read_bytes() == before
    assert not list(tmp_path.glob('*.before_restore_*'))


def test_restore_rejects_missing_required_column(restore, tmp_path):
    source = _db(tmp_path / 'backup.db')
    with closing(sqlite3.connect(source)) as conn:
        conn.execute('ALTER TABLE material DROP COLUMN stock')
        conn.commit()
    target = _db(tmp_path / 'target.db')
    assert restore.main([str(source), '--db', str(target), '--yes']) == 2
    assert _stock(target) == 2


def test_restore_refuses_idle_open_wal_connection(restore, tmp_path):
    source = _db(tmp_path / 'backup.db', 7)
    target = _db(tmp_path / 'target.db')
    with closing(sqlite3.connect(target)) as held:
        held.execute('PRAGMA journal_mode=WAL')
        assert restore.main([str(source), '--db', str(target), '--yes']) == 3
        assert held.execute('SELECT stock FROM material').fetchone()[0] == 2
    assert _stock(target) == 2


def test_restore_refuses_another_process_idle_connection(restore, tmp_path):
    source = _db(tmp_path / 'backup.db', 7)
    target = _db(tmp_path / 'target.db')
    code = "import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); c.execute('PRAGMA journal_mode=WAL'); print('READY',flush=True); sys.stdin.readline(); c.close()"
    child = subprocess.Popen([sys.executable, '-c', code, str(target)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        assert child.stdout.readline().strip() == 'READY'
        assert restore.main([str(source), '--db', str(target), '--yes']) == 3
    finally:
        child.communicate('\n', timeout=10)
    assert _stock(target) == 2


def test_restore_same_file_is_rejected_without_snapshot(restore, tmp_path):
    target = _db(tmp_path / 'target.db')
    assert restore.main([str(target), '--db', str(target), '--yes']) == 2
    assert _stock(target) == 2
    assert not list(tmp_path.glob('*.before_restore_*'))


def test_restore_valid_wms_preserves_old_snapshot(restore, tmp_path):
    source = _db(tmp_path / 'backup.db', 7)
    target = _db(tmp_path / 'target.db')
    assert restore.main([str(source), '--db', str(target), '--yes']) == 0
    assert _stock(target) == 7
    snapshots = list(tmp_path.glob('target.db.before_restore_*'))
    assert len(snapshots) == 1
    assert _stock(snapshots[0]) == 2


def test_restore_reads_committed_source_wal(restore, tmp_path):
    source = _db(tmp_path / 'backup.db', 7)
    target = _db(tmp_path / 'target.db')
    with closing(sqlite3.connect(source)) as held:
        held.execute('PRAGMA journal_mode=WAL')
        held.execute('UPDATE material SET stock=11')
        held.commit()
        assert restore.main([str(source), '--db', str(target), '--yes']) == 0
    assert _stock(target) == 11


def test_restore_snapshot_failure_keeps_target(restore, tmp_path, monkeypatch):
    source = _db(tmp_path / 'backup.db', 7)
    target = _db(tmp_path / 'target.db')
    def fail(*args, **kwargs):
        raise OSError('simulated disk full')
    monkeypatch.setattr(restore, '_snapshot', fail, raising=False)
    assert restore.main([str(source), '--db', str(target), '--yes']) == 2
    assert _stock(target) == 2


def test_restore_rechecks_target_after_confirmation(restore, tmp_path, monkeypatch):
    source = _db(tmp_path / 'backup.db', 7)
    target = _db(tmp_path / 'target.db')
    checks = iter([False, True])
    monkeypatch.setattr(restore, '_db_locked', lambda path: next(checks))
    assert restore.main([str(source), '--db', str(target), '--yes']) == 3
    assert _stock(target) == 2
    assert not list(tmp_path.glob('*.before_restore_*'))


def test_restore_refuses_server_lease_without_sqlite_connection(restore, tmp_path):
    from runtime_guard import acquire_database_lease
    source = _db(tmp_path / 'backup.db', 7)
    target = _db(tmp_path / 'target.db')
    with acquire_database_lease(target):
        assert restore.main([str(source), '--db', str(target), '--yes']) == 3
    assert _stock(target) == 2


def test_restore_holds_lease_through_every_snapshot(restore, tmp_path, monkeypatch):
    from runtime_guard import acquire_database_lease
    source = _db(tmp_path / 'backup.db', 7)
    target = _db(tmp_path / 'target.db')
    original = restore._snapshot
    calls = []
    def checked(source_path, destination):
        with pytest.raises(RuntimeError, match='独占运行锁'):
            acquire_database_lease(target)
        calls.append(destination)
        return original(source_path, destination)
    monkeypatch.setattr(restore, '_snapshot', checked)
    assert restore.main([str(source), '--db', str(target), '--yes']) == 0
    assert len(calls) == 3
