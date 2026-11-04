"""Old schema -> explicit additive upgrade; preserve existing row values."""
import ast
import hashlib
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine
import app as w
from schema_upgrade import plan_schema_upgrade, apply_schema_upgrade

ROOT = Path(__file__).resolve().parents[1]


def old_database(path):
    metadata = MetaData()
    for table in w.db.metadata.tables.values():
        if table.name != 'material_image':
            table.to_metadata(metadata)
    table = metadata.tables['in_order']
    removed = {'source_sales_order_id', 'source_purchase_order_id'}
    for constraint in list(table.constraints):
        if any(c.name in removed for c in constraint.columns):
            table.constraints.remove(constraint)
    for column in list(table.columns):
        if column.name in removed:
            table._columns.remove(column)
    engine = create_engine('sqlite:///' + path.as_posix())
    metadata.create_all(engine); engine.dispose()
    with sqlite3.connect(path) as conn:
        conn.execute("INSERT INTO material(id,code,name,stock) VALUES(1,'KEEP','保留物料',12.5)")


def test_plan_schema_upgrade(tmp_path):
    path = tmp_path / 'old.sqlite'; old_database(path)
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as conn:
        plan = plan_schema_upgrade(conn, w.db.metadata)
    assert not plan['blocked']
    assert len(plan['statements']) >= 3
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_apply_schema_upgrade(tmp_path):
    path = tmp_path / 'old.sqlite'; old_database(path)
    with sqlite3.connect(path) as conn:
        before = conn.execute('SELECT * FROM material').fetchall()
        assert apply_schema_upgrade(conn, w.db.metadata) >= 3
        assert conn.execute('SELECT * FROM material').fetchall() == before
        assert not plan_schema_upgrade(conn, w.db.metadata)['statements']
        assert apply_schema_upgrade(conn, w.db.metadata) == 0
    engine = create_engine('sqlite:///' + path.as_posix())
    from startup_check import schema_diff
    assert schema_diff(w.app, w.db, engine=engine)[0] == []
    engine.dispose()


def test_upgrade_cli_preview_backup_and_no_bootstrap(tmp_path):
    path = tmp_path / 'old.sqlite'; old_database(path)
    backup = tmp_path / 'before.sqlite'
    script = str(ROOT / 'scripts/upgrade_schema.py')
    before = path.read_bytes()
    preview = subprocess.run([sys.executable, script, '--db', str(path)], capture_output=True, text=True, encoding='utf-8')
    assert preview.returncode == 0, preview.stderr
    assert path.read_bytes() == before
    applied = subprocess.run([sys.executable, script, '--db', str(path), '--apply', '--backup', str(backup)], capture_output=True, text=True, encoding='utf-8')
    assert applied.returncode == 0, applied.stderr
    with sqlite3.connect(backup) as conn:
        assert 'source_purchase_order_id' not in {r[1] for r in conn.execute('PRAGMA table_info(in_order)')}
        assert conn.execute('SELECT stock FROM material').fetchone()[0] == 12.5
    with sqlite3.connect(path) as conn:
        assert conn.execute('SELECT count(*) FROM user').fetchone()[0] == 0
        assert conn.execute('SELECT count(*) FROM warehouse').fetchone()[0] == 0


def test_unsafe_nonnullable_change_blocks_whole_upgrade():
    metadata = MetaData()
    Table('existing', metadata, Column('id', Integer, primary_key=True), Column('optional', String), Column('required', String, nullable=False))
    with sqlite3.connect(':memory:') as conn:
        conn.execute('CREATE TABLE existing(id INTEGER PRIMARY KEY)')
        conn.execute('INSERT INTO existing VALUES(1)'); conn.commit()
        with pytest.raises(ValueError, match='非空列'):
            apply_schema_upgrade(conn, metadata)
        assert [r[1] for r in conn.execute('PRAGMA table_info(existing)')] == ['id']


@pytest.mark.parametrize('name', ['WMS_NO_DB_TOUCH', 'WMS_SKIP_STARTUP_DB_UPGRADE'])
def test_server_schema_guard_is_reachable_with_write_controls(name):
    """Execute actual startup statements before serve, retaining conditional guards."""
    source = (ROOT / 'app/run_server.py').read_text(encoding='utf-8')
    tree = ast.parse(source)
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
    steps = []
    for node in main.body:
        if any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'verify_schema_or_raise' for n in ast.walk(node)):
            steps.append(node)
    reached = []
    ns = {'app': object(), 'db': object(), 'startup_db_upgrade_disabled': lambda: True,
          'verify_schema_or_raise': lambda *a: reached.append(name) or 'ok'}
    exec(compile(ast.Module(body=steps, type_ignores=[]), '<startup>', 'exec'), ns)
    assert reached == [name]


def test_no_touch_missing_schema_is_readonly_failure(tmp_path, monkeypatch):
    from startup_check import verify_schema_or_raise
    path = tmp_path / 'old.sqlite'; old_database(path)
    before = path.read_bytes()
    monkeypatch.setenv('WMS_NO_DB_TOUCH', '1')
    monkeypatch.delenv('WMS_SCHEMA_CHECK', raising=False)
    engine = create_engine('sqlite:///' + path.as_posix())
    with pytest.raises(RuntimeError, match='source_purchase_order_id'):
        verify_schema_or_raise(w.app, w.db, engine=engine)
    engine.dispose()
    assert path.read_bytes() == before


def test_known_migration_gaps_have_explicit_upgrade_coverage(tmp_path):
    from tests.test_r6_startup_migration_column_guard import KNOWN_GAP
    metadata = MetaData()
    for table in w.db.metadata.tables.values():
        table.to_metadata(metadata)
    active = {(t, c) for t, c in KNOWN_GAP if t in metadata.tables and c in metadata.tables[t].columns}
    assert len(active) == len(KNOWN_GAP), 'Historical gaps must map to the current schema'
    for name, table in metadata.tables.items():
        missing = {c for t, c in active if t == name}
        for constraint in list(table.constraints):
            if any(c.name in missing for c in constraint.columns):
                table.constraints.remove(constraint)
        for index in list(table.indexes):
            if any(c.name in missing for c in index.columns):
                table.indexes.remove(index)
        for column in list(table.columns):
            if column.name in missing:
                table._columns.remove(column)
    path = tmp_path / 'gaps.sqlite'
    engine = create_engine('sqlite:///' + path.as_posix())
    metadata.create_all(engine); engine.dispose()
    with sqlite3.connect(path) as conn:
        assert not plan_schema_upgrade(conn, w.db.metadata)['blocked']
        assert apply_schema_upgrade(conn, w.db.metadata) >= len(active)
        assert not plan_schema_upgrade(conn, w.db.metadata)['statements']
