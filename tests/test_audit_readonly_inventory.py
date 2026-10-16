"""Repair task: AUDIT-FULL-20261016-001-F02. No production DB is used."""
import ast
import hashlib
import json
import logging
import os
import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_TREE = ast.parse((ROOT / 'app/app.py').read_text(encoding='utf-8-sig'))
HELPERS = [
    'auto_migrate_database', 'backfill_empty_warehouse_documents',
    'ensure_print_job_columns', 'ensure_excel_print_template_table', 'ensure_department_table',
    'ensure_outbound_department_columns', 'ensure_stock_transaction_warehouse_id_column',
    'ensure_inventory_check_columns', 'ensure_sales_return_source_columns',
    'ensure_material_status_column', 'ensure_material_dedupe_unique_index',
    'ensure_purchase_return_source_columns', 'ensure_in_order_item_batch_columns',
    'ensure_opening_stock_doc_table', 'cleanup_dangling_opening_stock_transactions',
    'ensure_opening_stock_doc_columns', '_ensure_default_print_templates_unconditional',
]


def _helpers(tmp_path, uri):
    app_dir = tmp_path / 'fake-app'
    instance = app_dir / 'instance'
    instance.mkdir(parents=True)
    sentinel = instance / 'inventory.db'
    sentinel.write_bytes(b'file database must not be opened for a non-file configuration')
    app = SimpleNamespace(config={'SQLALCHEMY_DATABASE_URI': uri},
                          instance_path=str(instance), logger=MagicMock())
    namespace = {'os': os, 'Path': Path, 'sqlite3': sqlite3, 'logging': logging,
                 '__file__': str(app_dir / 'app.py'), '__name__': 'isolated_migrations',
                 'app': app, '_env_flag': lambda *args: False,
                 'startup_db_upgrade_disabled': lambda: False}
    wanted = set(HELPERS) | {'_resolve_sqlite_db_path'}
    for node in APP_TREE.body:
        if isinstance(node, ast.FunctionDef) and node.name in wanted:
            exec(compile(ast.Module(body=[node], type_ignores=[]), '<isolated-migrations>', 'exec'), namespace)
    return namespace, sentinel


@pytest.mark.parametrize('name', HELPERS)
@pytest.mark.parametrize('uri', ['sqlite:///:memory:', 'sqlite://', 'postgresql://fixture/database'])
def test_non_file_configuration_never_opens_fallback_file(name, uri, tmp_path, monkeypatch):
    namespace, sentinel = _helpers(tmp_path, uri)
    connect = MagicMock(side_effect=AssertionError('unexpected file connection'))
    monkeypatch.setattr(sqlite3, 'connect', connect)
    result = namespace[name]()
    assert connect.call_count == 0, f'{name} must not open a disk database for {uri}'
    assert sentinel.read_bytes().startswith(b'file database must not')
    assert result == (False, []) if name == 'ensure_material_dedupe_unique_index' else result is None


def test_explicit_file_maintenance_still_creates_required_table(tmp_path):
    namespace, sentinel = _helpers(tmp_path, 'sqlite:///:memory:')
    target = tmp_path / 'explicit.db'
    with closing(sqlite3.connect(target)) as conn:
        conn.execute('CREATE TABLE marker (value TEXT)')
        conn.execute('INSERT INTO marker VALUES (?)', ('keep',))
        conn.commit()
    namespace['ensure_department_table'](db_path=str(target))
    with closing(sqlite3.connect(target)) as conn:
        assert conn.execute("SELECT name FROM sqlite_master WHERE name='department'").fetchone()
        assert conn.execute('SELECT value FROM marker').fetchone() == ('keep',)
    assert sentinel.read_bytes().startswith(b'file database must not')


def test_configured_file_maintenance_does_not_use_default_database(tmp_path):
    target = tmp_path / 'configured.db'
    with closing(sqlite3.connect(target)) as conn:
        conn.execute('CREATE TABLE marker (value TEXT)')
    namespace, sentinel = _helpers(tmp_path, 'sqlite:///' + target.as_posix())
    namespace['ensure_department_table']()
    with closing(sqlite3.connect(target)) as conn:
        assert conn.execute("SELECT name FROM sqlite_master WHERE name='department'").fetchone()
    assert sentinel.read_bytes().startswith(b'file database must not')


def _fixture(path, enabled='1', cross=False, legacy=False):
    warehouse_column = '' if legacy else ', warehouse_id INTEGER'
    with closing(sqlite3.connect(path)) as conn:
        conn.executescript(f'''
            CREATE TABLE material (id INTEGER PRIMARY KEY, code TEXT, stock REAL);
            CREATE TABLE location_inventory (material_id INTEGER, quantity REAL{warehouse_column});
            CREATE TABLE stock_transaction (material_id INTEGER, quantity REAL{warehouse_column});
            CREATE TABLE system_setting (key TEXT PRIMARY KEY, value TEXT);
            INSERT INTO material VALUES (1, 'M1', 15), (2, 'M2', 3);
        ''')
        conn.execute('INSERT INTO system_setting VALUES (?, ?)', ('location_management_enabled', enabled))
        locs = [(1, 7 if cross else 10, 1), (1, 8 if cross else 5, 2), (2, 3, None)]
        txns = [(1, 10, 1), (1, 5, 2), (2, 3, None)]
        for table, rows in [('location_inventory', locs), ('stock_transaction', txns)]:
            if legacy:
                conn.executemany(f'INSERT INTO {table} VALUES (?, ?)', [row[:2] for row in rows])
            else:
                conn.executemany(f'INSERT INTO {table} VALUES (?, ?, ?)', rows)
        conn.commit()
    return path


def _run_checker(tmp_path, database, extra=()):
    hook = tmp_path / 'hook'
    hook.mkdir(exist_ok=True)
    marker = hook / 'app-was-imported'
    # Fresh process: forbid app startup and any SQLite connection that is not read-only.
    (hook / 'sitecustomize.py').write_text('''
import sys, sqlite3, importlib.abc
from pathlib import Path
class NoApp(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'app' or fullname.startswith('app.'):
            Path(__file__).with_name('app-was-imported').touch()
            raise RuntimeError('APP_IMPORT_FORBIDDEN')
sys.meta_path.insert(0, NoApp())
original = sqlite3.connect
def only_readonly(database, *args, **kwargs):
    assert kwargs.get('uri') is True and 'mode=ro' in str(database), 'READONLY_CONNECTION_REQUIRED'
    connection = original(database, *args, **kwargs)
    denied = {sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE,
              sqlite3.SQLITE_CREATE_TABLE, sqlite3.SQLITE_DROP_TABLE, sqlite3.SQLITE_ALTER_TABLE,
              sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH}
    connection.set_authorizer(lambda action, *rest: sqlite3.SQLITE_DENY if action in denied else sqlite3.SQLITE_OK)
    return connection
sqlite3.connect = only_readonly
''', encoding='utf-8')
    env = dict(os.environ, PYTHONPATH=str(hook), PYTHONUTF8='1', PYTHONIOENCODING='utf-8', FLASK_ENV='production')
    for key in ['SECRET_KEY', 'WMS_ALLOW_AUTO_SECRET_KEY', 'WMS_ALLOW_INSECURE_COOKIE']:
        env.pop(key, None)
    before = hashlib.sha256(database.read_bytes()).hexdigest() if database.exists() else None
    result = subprocess.run([sys.executable, str(ROOT / 'scripts/verify_inventory_identity.py'),
                             '--db', 'sqlite:///' + database.as_posix(), '--json', *extra],
                            env=env, capture_output=True, text=True, encoding='utf-8', timeout=30)
    if before is None:
        assert not database.exists(), '只读检查不得创建缺失的数据库'
    else:
        assert hashlib.sha256(database.read_bytes()).hexdigest() == before
    return result, marker


@pytest.mark.parametrize('pushdown', [True, False])
def test_cli_checks_readonly_without_app_bootstrap(tmp_path, pushdown):
    database = _fixture(tmp_path / 'inventory.db')
    result, marker = _run_checker(tmp_path, database, [] if pushdown else ['--no-pushdown'])
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data['materials'] == 2
    assert data['unattributed_materials'] == 1
    assert data['wh_gate_location_management_enabled'] is True
    assert not marker.exists()


def test_cli_retains_multiwarehouse_mismatch_detection(tmp_path):
    database = _fixture(tmp_path / 'inventory.db', cross=True)
    result, marker = _run_checker(tmp_path, database)
    assert result.returncode == 1
    data = json.loads(result.stdout)
    assert data['mismatch_wh_location_vs_txn'] == 2
    assert not marker.exists()


def test_cli_retains_location_disabled_warehouse_gate(tmp_path):
    database = _fixture(tmp_path / 'inventory.db', enabled='0', cross=True)
    result, marker = _run_checker(tmp_path, database)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['wh_gate_location_management_enabled'] is False
    assert not marker.exists()


def test_cli_legacy_rows_remain_unattributed_without_schema_upgrade(tmp_path):
    database = _fixture(tmp_path / 'legacy.db', legacy=True)
    result, marker = _run_checker(tmp_path, database)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['unattributed_materials'] == 2
    assert not marker.exists()


def test_cli_missing_database_is_not_created(tmp_path):
    result, marker = _run_checker(tmp_path, tmp_path / 'missing.db')
    assert result.returncode == 2
    assert not marker.exists()


@pytest.mark.parametrize('uri', ['sqlite:///:memory:', 'postgresql://fixture/database',
                                  'sqlite:///file:fixture?mode=memory&uri=true'])
def test_cli_unsupported_target_does_not_bootstrap_app(tmp_path, uri):
    database = _fixture(tmp_path / 'inventory.db')
    result, marker = _run_checker(tmp_path, database, ['--db', uri])
    assert result.returncode == 2
    assert not marker.exists()
