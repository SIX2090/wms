"""Index-only upgrade gaps: synthetic files, read-only startup, atomic repair."""
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
from types import SimpleNamespace

import pytest
from sqlalchemy import Column, Index, Integer, MetaData, String, Table, create_engine

import app as w
from schema_upgrade import apply_schema_upgrade, plan_schema_upgrade
from startup_check import schema_diff, verify_schema_or_raise


def test_read_sqlite_indexes():
    from schema_indexes import read_sqlite_indexes
    with sqlite3.connect(':memory:') as connection:
        connection.executescript('CREATE TABLE "odd table"(a INTEGER,b INTEGER); '
                                 'CREATE UNIQUE INDEX "odd index" ON "odd table"(b,a) WHERE a > 0;')
        indexes = read_sqlite_indexes(connection, 'odd table')
    assert len(indexes) == 1
    assert indexes[0]['name'] == 'odd index'
    assert indexes[0]['unique'] is True
    assert indexes[0]['column_names'] == ['b', 'a']
    assert str(indexes[0]['dialect_options']['sqlite_where']) == 'a > 0'


def test_compare_model_indexes():
    from schema_indexes import compare_model_indexes, read_sqlite_indexes
    metadata = MetaData()
    table = Table('existing', metadata, Column('a', Integer), Column('b', Integer))
    Index('ix_partial', table.c.b, table.c.a, unique=True, sqlite_where=table.c.a > 0)
    with sqlite3.connect(':memory:') as connection:
        connection.executescript('CREATE TABLE existing(a INTEGER,b INTEGER); '
                                 'CREATE UNIQUE INDEX ix_partial ON existing(b,a) WHERE a > 0;')
        assert compare_model_indexes(table, read_sqlite_indexes(connection, 'existing')) == ([], [])


@pytest.fixture()
def index_gap(tmp_path):
    path = tmp_path / 'index-gap.sqlite'
    engine = create_engine('sqlite:///' + path.as_posix())
    w.db.metadata.create_all(engine)
    with sqlite3.connect(path) as connection:
        connection.execute("INSERT INTO material(id,code,name,stock) VALUES(1,'KEEP','Keep',12.5)")
        connection.execute('DROP INDEX idx_ai_retry_run')
        connection.execute('DROP INDEX idx_ai_retry_original')
    yield path, engine
    engine.dispose()


def test_preview_lists_index_only_gap_without_writing(index_gap):
    path, engine = index_gap
    # The exact failure: ORM create_all ignores indexes on an existing table.
    w.db.metadata.create_all(engine)
    before = path.read_bytes()
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as connection:
        plan = plan_schema_upgrade(connection, w.db.metadata)
    assert not plan['blocked']
    assert len(plan['statements']) == 2
    assert all(statement.startswith('CREATE INDEX idx_ai_retry_') for statement in plan['statements'])
    assert path.read_bytes() == before


def test_apply_restores_only_missing_indexes_and_is_idempotent(index_gap):
    path, _ = index_gap
    with sqlite3.connect(path) as connection:
        rows = connection.execute('SELECT * FROM material').fetchall()
        objects = set(connection.execute('SELECT type,name FROM sqlite_master'))
        assert apply_schema_upgrade(connection, w.db.metadata) == 2
        assert connection.execute('SELECT * FROM material').fetchall() == rows
        added = set(connection.execute('SELECT type,name FROM sqlite_master')) - objects
        assert added == {('index', 'idx_ai_retry_original'), ('index', 'idx_ai_retry_run')}
        assert apply_schema_upgrade(connection, w.db.metadata) == 0
        assert plan_schema_upgrade(connection, w.db.metadata) == {'statements': [], 'blocked': []}


def test_index_only_cli_requires_backup_and_preserves_source_preview(index_gap, tmp_path):
    path, _ = index_gap
    script = Path(__file__).resolve().parents[1] / 'scripts' / 'upgrade_schema.py'
    backup = tmp_path / 'before.sqlite'
    before = path.read_bytes()
    def run(*arguments):
        return subprocess.run([sys.executable, str(script), '--db', str(path), *arguments],
                              capture_output=True, text=True, encoding='utf-8', timeout=30)
    preview = run()
    assert preview.returncode == 0, preview.stderr
    assert len(json.loads(preview.stdout)['statements']) == 2
    assert path.read_bytes() == before
    assert run('--apply').returncode != 0
    assert path.read_bytes() == before
    applied = run('--apply', '--backup', str(backup))
    assert applied.returncode == 0, applied.stderr
    with sqlite3.connect(backup) as connection:
        assert 'idx_ai_retry_run' not in {row[1] for row in connection.execute('PRAGMA index_list(ai_agent_retry_record)')}
        assert connection.execute('SELECT stock FROM material').fetchone() == (12.5,)
    with sqlite3.connect(path) as connection:
        assert 'idx_ai_retry_run' in {row[1] for row in connection.execute('PRAGMA index_list(ai_agent_retry_record)')}
        assert connection.execute('SELECT stock FROM material').fetchone() == (12.5,)
        assert connection.execute('SELECT count(*) FROM user').fetchone() == (0,)
    assert json.loads(run().stdout)['statements'] == []


def test_startup_reports_performance_indexes_without_writing(index_gap, monkeypatch, caplog):
    path, engine = index_gap
    monkeypatch.setenv('WMS_NO_DB_TOUCH', '1')
    monkeypatch.delenv('WMS_SCHEMA_CHECK', raising=False)
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    errors, warnings = schema_diff(w.app, w.db, engine=engine)
    assert errors == []
    for name in ('idx_ai_retry_original', 'idx_ai_retry_run'):
        assert any('缺索引' in warning and name in warning for warning in warnings)
    assert 'schema-check: ok' in verify_schema_or_raise(w.app, w.db, engine=engine)
    assert 'idx_ai_retry_run' in caplog.text
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


@pytest.mark.parametrize('definition', [
    'CREATE INDEX ix_expected ON existing(b,a)',
    'CREATE UNIQUE INDEX ix_expected ON existing(a,b)',
    'CREATE INDEX ix_expected ON existing(a,b) WHERE a > 0',
])
def test_same_name_wrong_definition_is_blocked(tmp_path, definition):
    metadata = MetaData()
    table = Table('existing', metadata, Column('a', Integer), Column('b', Integer))
    Index('ix_expected', table.c.a, table.c.b)
    path = tmp_path / 'wrong.sqlite'
    with sqlite3.connect(path) as connection:
        connection.execute('CREATE TABLE existing(a INTEGER,b INTEGER)')
        connection.execute(definition)
        before = connection.execute("SELECT sql FROM sqlite_master WHERE name='ix_expected'").fetchone()
        plan = plan_schema_upgrade(connection, metadata)
        assert any('ix_expected' in reason for reason in plan['blocked'])
        with pytest.raises(ValueError, match='ix_expected'):
            apply_schema_upgrade(connection, metadata)
        assert connection.execute("SELECT sql FROM sqlite_master WHERE name='ix_expected'").fetchone() == before
    engine = create_engine('sqlite:///' + path.as_posix())
    try:
        errors, _ = schema_diff(w.app, SimpleNamespace(metadata=metadata), engine=engine)
        assert any('索引定义不一致' in error for error in errors)
    finally:
        engine.dispose()


def test_missing_unique_index_rejects_startup_and_failed_upgrade_rolls_back(tmp_path, monkeypatch):
    metadata = MetaData()
    table = Table('existing', metadata, Column('id', Integer), Column('code', String), Column('extra', String))
    Index('ix_unique_code', table.c.code, unique=True)
    path = tmp_path / 'unique.sqlite'
    with sqlite3.connect(path) as connection:
        connection.execute('CREATE TABLE existing(id INTEGER,code VARCHAR)')
        connection.executemany('INSERT INTO existing VALUES(?,?)', [(1, 'same'), (2, 'same')])
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            apply_schema_upgrade(connection, metadata)
        assert [row[1] for row in connection.execute('PRAGMA table_info(existing)')] == ['id', 'code']
        assert connection.execute('SELECT * FROM existing').fetchall() == [(1, 'same'), (2, 'same')]
    engine = create_engine('sqlite:///' + path.as_posix())
    monkeypatch.delenv('WMS_SCHEMA_CHECK', raising=False)
    try:
        with pytest.raises(RuntimeError, match='缺唯一索引.*ix_unique_code'):
            verify_schema_or_raise(w.app, SimpleNamespace(metadata=metadata), engine=engine)
    finally:
        engine.dispose()


def test_index_name_collision_on_another_table_is_reviewable():
    metadata = MetaData()
    table = Table('existing', metadata, Column('id', Integer))
    Index('ix_expected', table.c.id)
    with sqlite3.connect(':memory:') as connection:
        connection.executescript('CREATE TABLE existing(id INTEGER); CREATE TABLE other(id INTEGER); CREATE INDEX ix_expected ON other(id);')
        plan = plan_schema_upgrade(connection, metadata)
        assert any('ix_expected' in reason and 'other' in reason for reason in plan['blocked'])
