"""Full migration source on fabricated schema and private :memory: SQLite only.

This test never imports the WMS application or opens a database file. The schema
is deliberately synthetic and an authorizer injects index permission failures;
it cannot establish the state or compatibility of any real installation.
"""
import ast
import sys
import importlib.util
import builtins
import datetime
from pathlib import Path
import re
import socket
import sqlite3
import subprocess
import types
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'app' / 'app.py'
spec = importlib.util.spec_from_file_location('sqlite_schema_checkpoint', ROOT / 'app/sqlite_schema_checkpoint.py')
checkpoint_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checkpoint_module)
sys.modules['sqlite_schema_checkpoint'] = checkpoint_module
DENIED_PERFORMANCE_INDEXES = frozenset({
    'idx_location_inventory_wh_material', 'idx_material_supplier',
    'idx_material_unit', 'idx_material_created', 'idx_supplier_created',
    'idx_customer_created',
})
REQUIRED_AI_INDEX = 'idx_ai_tool_call_denied'
# Explicit synthetic objects observed in the isolated fixture. This is not an
# authorization list for production or a complete inventory of old schemas.
SYNTHETIC_REPLAY_OBJECTS = frozenset({
    'contract', 'document_push_line', 'material_image',
    'idx_ai_acceptance_snapshot_created', 'idx_ai_evidence_package_dates',
    'idx_ai_evidence_package_decision', 'idx_ai_material_alias_material',
    'idx_ai_tool_call_denied', 'idx_ai_tool_call_user_source', 'idx_contract_no',
    'idx_contract_status', 'idx_in_order_contract_id', 'idx_in_order_item_contract_id',
    'idx_in_order_item_in_order_id', 'idx_in_order_item_material_id',
    'idx_in_order_item_source_sales_item', 'idx_in_order_source_sales_order_id',
    'idx_location_inventory_loc', 'idx_location_inventory_material_id',
    'idx_location_inventory_warehouse', 'idx_material_image_material',
    'idx_material_status', 'idx_opening_stock_doc', 'idx_out_order_contract_id',
    'idx_out_order_item_contract_id', 'idx_out_order_item_material_id',
    'idx_out_order_item_out_order_id', 'idx_out_order_item_sales_source',
    'idx_out_order_item_source_in_item', 'idx_out_order_source_in_order_id',
    'idx_print_job_workstation_status', 'idx_purchase_order_contract_id',
    'idx_purchase_order_item_contract_id', 'idx_push_request',
    'idx_push_source_item_status', 'idx_push_target_status', 'idx_sales_order_contract_id',
    'idx_sales_order_item_contract_id', 'idx_stock_transaction_material_id',
    'idx_stock_transaction_ref', 'idx_stock_txn_warehouse_id',
    'uix_opening_stock_line_doc', 'uq_print_workstation_auth_token',
})


def refuse(*_args, **_kwargs):
    raise AssertionError('real WMS, database files, network and subprocesses are forbidden')


class SyntheticLogger:
    def __init__(self):
        self.warnings = []
        self.errors = []

    def warning(self, *args, **_kwargs):
        self.warnings.append(args)

    def info(self, *_args, **_kwargs):
        pass

    def error(self, *args, **_kwargs):
        self.errors.append(args)


class MemoryConnectionProxy:
    """Observe close/commit while keeping the synthetic memory DB inspectable."""
    def __init__(self, connection):
        self.connection = connection
        self.commits = 0
        self.closed = False
        self.schema_before_close = None
        self.schema_before_commit = None
        self.replaying = False
        self.replayed_tables = 0

    def __getattr__(self, name):
        return getattr(self.connection, name)

    fail_replay = False

    def execute(self, sql, *args):
        if sql == 'ROLLBACK TO SAVEPOINT wms_additive_schema':
            self.replaying = True
        elif self.replaying and sql.lstrip().upper().startswith('CREATE TABLE'):
            self.replayed_tables += 1
            if self.fail_replay and self.replayed_tables == 2:
                raise sqlite3.OperationalError('synthetic schema replay failure')
        return self.connection.execute(sql, *args)

    def commit(self):
        self.schema_before_commit = self.connection.execute(
            "SELECT type, name, tbl_name, sql FROM sqlite_master "
            "WHERE type IN ('table','index') AND name NOT LIKE 'sqlite_%' ORDER BY type, name"
        ).fetchall()
        self.commits += 1
        return self.connection.commit()

    def close(self):
        self.closed = True
        # sqlite3.close rolls back a pending transaction. Keep the connection
        # open only so the test can inspect the result in this private memory DB.
        if self.connection.in_transaction:
            self.schema_before_close = self.connection.execute(
                "SELECT type, name, tbl_name, sql FROM sqlite_master "
                "WHERE type IN ('table','index') AND name NOT LIKE 'sqlite_%' ORDER BY type, name"
            ).fetchall()
            self.connection.rollback()


def synthetic_schema(db, migration):
    """Make artificial tables broad enough to exercise the full source path."""
    columns = {'status', 'created_at', 'updated_at', 'warehouse_id', 'category_id', 'unit_id'}
    for node in ast.walk(migration):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            columns.update(re.findall(r'[A-Za-z_][A-Za-z0-9_]*', node.value))
    tables = set()
    for path in (ROOT / 'app' / 'models').glob('*.py'):
        tree = ast.parse(path.read_text(encoding='utf-8-sig'))
        for cls in tree.body:
            if not isinstance(cls, ast.ClassDef) or not any('db.Model' in ast.unparse(base) for base in cls.bases):
                continue
            table = next((node.value.value for node in cls.body
                          if isinstance(node, ast.Assign)
                          and any(isinstance(target, ast.Name) and target.id == '__tablename__'
                                  for target in node.targets)
                          and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)), None)
            tables.add(table or re.sub(r'(?<!^)(?=[A-Z])', '_', cls.name).lower())
            for node in cls.body:
                if (isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)
                        and isinstance(node.value.func, ast.Attribute) and node.value.func.attr == 'Column'):
                    columns.update(target.id for target in node.targets if isinstance(target, ast.Name))
    columns = sorted({value.lower() for value in columns if len(value) < 70 and value.lower() != 'id'})
    for table in sorted(tables):
        db.execute('CREATE TABLE "' + table + '" (id INTEGER PRIMARY KEY, '
                   + ', '.join('"' + name + '" TEXT' for name in columns) + ')')
    db.execute('INSERT INTO material (id, status) VALUES (1, NULL)')
    db.commit()


class FullMigrationMemory(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.addCleanup(self.db.close)
        self.assertTrue(all(not row[2] for row in self.db.execute('PRAGMA database_list')))
        tree = ast.parse(SOURCE.read_text(encoding='utf-8-sig'))
        self.migration = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                              and n.name == 'auto_migrate_database')
        helper_names = {'_create_opening_stock_doc_table', '_backfill_opening_stock_docs',
                        '_opening_stock_legacy_unique_index', '_opening_stock_rebuild_table',
                        '_location_inventory_rebuild_table'}
        self.functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                          and (node.name in helper_names or node is self.migration)]
        self.assertEqual(len(self.functions), len(helper_names) + 1)
        synthetic_schema(self.db, self.migration)

    def exercise(self, *, deny_performance_indexes):
        if deny_performance_indexes:
            def authorizer(action, first, _second, _database, _source):
                if action == sqlite3.SQLITE_CREATE_INDEX and first in DENIED_PERFORMANCE_INDEXES:
                    return sqlite3.SQLITE_DENY
                return sqlite3.SQLITE_OK
            self.db.set_authorizer(authorizer)
        self.addCleanup(self.db.set_authorizer, None)
        proxy = MemoryConnectionProxy(self.db)
        logger = SyntheticLogger()

        def synthetic_connect(path, *_args, **_kwargs):
            if path != '__private_memory_only__':
                return refuse()
            return proxy

        original_import = builtins.__import__
        def guarded_import(name, *args, **kwargs):
            if name == 'app' or name.startswith('app.'):
                return refuse()
            return original_import(name, *args, **kwargs)

        namespace = {
            '_resolve_sqlite_db_path': lambda: '__private_memory_only__',
            'os': types.SimpleNamespace(path=types.SimpleNamespace(
                exists=lambda value: value == '__private_memory_only__')),
            'sqlite3': sqlite3, 'logging': types.SimpleNamespace(getLogger=lambda _name: logger),
            'app': types.SimpleNamespace(logger=logger), 're': re,
            '__name__': 'synthetic_migration', 'datetime': datetime.datetime, 'date': datetime.date,
        }
        code = compile(ast.fix_missing_locations(ast.Module(body=self.functions, type_ignores=[])),
                       '<synthetic-complete-migration>', 'exec')
        with mock.patch.object(sqlite3, 'connect', synthetic_connect), \
                mock.patch.object(socket.socket, 'connect', refuse), \
                mock.patch.object(socket.socket, 'connect_ex', refuse), \
                mock.patch.object(socket, 'getaddrinfo', refuse), \
                mock.patch.object(subprocess, 'Popen', refuse), \
                mock.patch.object(builtins, '__import__', side_effect=guarded_import):
            exec(code, namespace)
            namespace['auto_migrate_database']()
        self.assertTrue(proxy.closed)
        self.assertEqual(logger.errors, [])
        self.assertTrue(all(not row[2] for row in self.db.execute('PRAGMA database_list')))
        return proxy, logger

    def test_normal_synthetic_schema_creates_ai_index(self):
        proxy, _logger = self.exercise(deny_performance_indexes=False)
        self.assertGreater(proxy.commits, 0)
        self.assertIsNotNone(self.db.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name=?", (REQUIRED_AI_INDEX,)
        ).fetchone())

    def test_ai_index_persists_without_committing_unrelated_backfill(self):
        _proxy, logger = self.exercise(deny_performance_indexes=True)
        self.assertGreaterEqual(len(logger.warnings), len(DENIED_PERFORMANCE_INDEXES))
        self.assertIsNone(self.db.execute('SELECT status FROM material WHERE id=1').fetchone()[0],
                          '原本未标记修改的业务回填不得被额外提交')
        self.assertIsNotNone(self.db.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name=?", (REQUIRED_AI_INDEX,)
        ).fetchone(), '前置索引失败不应让独立 AI 索引静默回滚')

    def test_created_tables_persist_without_committing_unrelated_backfill(self):
        tables = ('contract', 'material_image', 'document_push_line')
        for name in tables:
            self.db.execute('DROP TABLE "' + name + '"')
        self.db.commit()
        _proxy, _logger = self.exercise(deny_performance_indexes=True)
        self.assertIsNone(self.db.execute('SELECT status FROM material WHERE id=1').fetchone()[0],
                          '原本未标记修改的业务回填不得被额外提交')
        present = {row[0] for row in self.db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name IN (?, ?, ?)", tables
        )}
        self.assertEqual(present, set(tables), '迁移成功创建的合成表不应静默回滚')

    def test_synthetic_schema_only_replay_after_rollback(self):
        for name in ('contract', 'material_image', 'document_push_line'):
            self.db.execute('DROP TABLE "' + name + '"')
        self.db.commit()
        baseline = self.db.execute(
            "SELECT type, name, tbl_name, sql FROM sqlite_master "
            "WHERE type IN ('table','index') AND name NOT LIKE 'sqlite_%' ORDER BY type, name"
        ).fetchall()
        proxy, _logger = self.exercise(deny_performance_indexes=True)
        self.assertGreater(proxy.commits, 0)
        self.assertIsNotNone(proxy.schema_before_commit)
        old = {(kind, name): (table, sql) for kind, name, table, sql in baseline}
        observed = {(kind, name): (table, sql) for kind, name, table, sql in proxy.schema_before_commit}
        self.assertTrue(all(observed.get(key) == value for key, value in old.items()))
        new = [(kind, name, table, sql) for kind, name, table, sql in proxy.schema_before_commit
               if (kind, name) not in old]
        self.assertEqual({name for _, name, _, _ in new}, SYNTHETIC_REPLAY_OBJECTS)
        self.assertEqual(len(new), 43)
        self.assertIsNone(self.db.execute('SELECT status FROM material WHERE id=1').fetchone()[0])
        final = {(row[0], row[1]) for row in self.db.execute(
            "SELECT type, name FROM sqlite_master WHERE type IN ('table','index')"
        )}
        self.assertTrue({(kind, name) for kind, name, _, _ in new} <= final)
        for name in ('contract', 'material_image', 'document_push_line'):
            query = 'SELECT COUNT(*) FROM "' + name + '"'
            self.assertEqual(self.db.execute(query).fetchone()[0], 0)

    def test_synthetic_schema_replay_failure_rolls_back_all_new_objects(self):
        for name in ('contract', 'material_image', 'document_push_line'):
            self.db.execute('DROP TABLE "' + name + '"')
        self.db.commit()
        baseline = {(row[0], row[1]) for row in self.db.execute(
            "SELECT type, name FROM sqlite_master WHERE type IN ('table','index')"
        )}
        with mock.patch.object(MemoryConnectionProxy, 'fail_replay', True):
            with self.assertRaisesRegex(sqlite3.OperationalError, 'synthetic schema replay failure'):
                self.exercise(deny_performance_indexes=True)
        after = {(row[0], row[1]) for row in self.db.execute(
            "SELECT type, name FROM sqlite_master WHERE type IN ('table','index')"
        )}
        self.assertEqual(after, baseline)
        self.assertIsNone(self.db.execute('SELECT status FROM material WHERE id=1').fetchone()[0])

    def prepare_legacy_location_inventory(self):
        self.db.execute('DROP TABLE location_inventory')
        self.db.execute('''CREATE TABLE location_inventory (
            id INTEGER PRIMARY KEY, material_id INTEGER NOT NULL,
            warehouse_id INTEGER, location TEXT NOT NULL, quantity REAL,
            created_at TEXT, updated_at TEXT, UNIQUE(material_id, location)
        )''')
        self.db.execute('INSERT INTO location_inventory '
                        '(id, material_id, warehouse_id, location, quantity) '
                        "VALUES (1, 42, 7, 'synthetic-location', 5.0)")
        self.db.commit()

    def test_failed_inventory_rebuild_preserves_original_table_and_rows(self):
        self.prepare_legacy_location_inventory()
        def fail_rename(action, first, second, _database, _source):
            if action == sqlite3.SQLITE_ALTER_TABLE and second == 'location_inventory_rebuild_tmp':
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK
        self.db.set_authorizer(fail_rename)
        _proxy, logger = self.exercise(deny_performance_indexes=False)
        self.assertTrue(any('location_inventory' in str(args[0]) for args in logger.warnings))
        self.assertEqual(self.db.execute(
            'SELECT id, material_id, warehouse_id, location, quantity FROM location_inventory'
        ).fetchall(), [(1, 42, 7, 'synthetic-location', 5.0)])
        self.assertIsNone(self.db.execute(
            "SELECT name FROM sqlite_master WHERE name='location_inventory_rebuild_tmp'"
        ).fetchone())

    def test_inventory_rebuild_failure_at_each_step_preserves_original(self):
        original_db = self.db
        for phase in ('create_temp', 'copy', 'drop_original', 'rename', 'index', 'release'):
            with self.subTest(phase=phase):
                self.db = sqlite3.connect(':memory:')
                self.addCleanup(self.db.close)
                try:
                    synthetic_schema(self.db, self.migration)
                    self.prepare_legacy_location_inventory()
                    state = {'rename': False, 'denied': False}
                    def deny_step(action, first, second, _database, _source):
                        if action == sqlite3.SQLITE_ALTER_TABLE and second == 'location_inventory_rebuild_tmp':
                            state['rename'] = True
                        fail = (
                            (phase == 'create_temp' and action == sqlite3.SQLITE_CREATE_TABLE and first == 'location_inventory_rebuild_tmp') or
                            (phase == 'copy' and action == sqlite3.SQLITE_INSERT and first == 'location_inventory_rebuild_tmp') or
                            (phase == 'drop_original' and action == sqlite3.SQLITE_DROP_TABLE and first == 'location_inventory') or
                            (phase == 'rename' and action == sqlite3.SQLITE_ALTER_TABLE and second == 'location_inventory_rebuild_tmp') or
                            (phase == 'index' and state['rename'] and action == sqlite3.SQLITE_CREATE_INDEX and first == 'idx_location_inventory_material_id') or
                            (phase == 'release' and action == sqlite3.SQLITE_SAVEPOINT and first == 'RELEASE')
                        )
                        if fail and not state['denied']:
                            state['denied'] = True
                            return sqlite3.SQLITE_DENY
                        return sqlite3.SQLITE_OK
                    self.db.set_authorizer(deny_step)
                    _proxy, _logger = self.exercise(deny_performance_indexes=False)
                    self.assertTrue(state['denied'], '故障注入没有命中')
                    self.assertEqual(self.db.execute(
                        'SELECT id, material_id, warehouse_id, location, quantity FROM location_inventory'
                    ).fetchall(), [(1, 42, 7, 'synthetic-location', 5.0)])
                    self.assertIsNone(self.db.execute(
                        "SELECT name FROM sqlite_master WHERE name='location_inventory_rebuild_tmp'"
                    ).fetchone())
                finally:
                    self.db.set_authorizer(None)
                    self.db = original_db

    def test_inventory_rebuild_success_is_idempotent_and_keeps_rows(self):
        self.prepare_legacy_location_inventory()
        self.exercise(deny_performance_indexes=False)
        self.exercise(deny_performance_indexes=False)
        self.assertEqual(self.db.execute(
            'SELECT id, material_id, warehouse_id, location, quantity FROM location_inventory'
        ).fetchall(), [(1, 42, 7, 'synthetic-location', 5.0)])
        definition = self.db.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='location_inventory'"
        ).fetchone()[0]
        self.assertRegex(definition, r'(?is)UNIQUE\s*\(\s*material_id\s*,\s*warehouse_id\s*,\s*location\s*\)')

    def test_rebuild_savepoint_rollback_failure_aborts_outer_transaction(self):
        self.prepare_legacy_location_inventory()
        def deny_savepoint(action, first, _second, _database, _source):
            if action == sqlite3.SQLITE_SAVEPOINT and first in ('RELEASE', 'ROLLBACK'):
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK
        self.db.set_authorizer(deny_savepoint)
        with self.assertRaises(sqlite3.DatabaseError):
            self.exercise(deny_performance_indexes=False)
        self.db.set_authorizer(None)
        self.assertEqual(self.db.execute(
            'SELECT id, material_id, warehouse_id, location, quantity FROM location_inventory'
        ).fetchall(), [(1, 42, 7, 'synthetic-location', 5.0)])
        self.assertIsNone(self.db.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name=?", (REQUIRED_AI_INDEX,)
        ).fetchone(), '外层事务失败时其他 DDL 也应回滚')
        self.assertIsNone(self.db.execute('SELECT status FROM material WHERE id=1').fetchone()[0])

    def test_failed_rebuild_without_marked_changes_still_rolls_back_outer_transaction(self):
        self.prepare_legacy_location_inventory()
        def deny_performance_and_rename(action, first, second, _database, _source):
            if action == sqlite3.SQLITE_CREATE_INDEX and first in DENIED_PERFORMANCE_INDEXES:
                return sqlite3.SQLITE_DENY
            if action == sqlite3.SQLITE_ALTER_TABLE and second == 'location_inventory_rebuild_tmp':
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK
        self.db.set_authorizer(deny_performance_and_rename)
        proxy, _logger = self.exercise(deny_performance_indexes=False)
        self.assertEqual(proxy.commits, 0)
        self.assertIsNotNone(proxy.schema_before_close)
        self.assertEqual(self.db.execute(
            'SELECT id, material_id, warehouse_id, location, quantity FROM location_inventory'
        ).fetchall(), [(1, 42, 7, 'synthetic-location', 5.0)])
        self.assertIsNone(self.db.execute('SELECT status FROM material WHERE id=1').fetchone()[0])
        self.assertIsNone(self.db.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name=?", (REQUIRED_AI_INDEX,)
        ).fetchone())

    def test_location_rebuild_does_not_remove_existing_scratch_object(self):
        original_db = self.db
        name = 'LOCATION_INVENTORY_REBUILD_TMP'
        for kind in ('main_table', 'temp_table', 'main_view', 'temp_view', 'main_index'):
            with self.subTest(kind=kind):
                self.db = sqlite3.connect(':memory:')
                self.addCleanup(self.db.close)
                try:
                    synthetic_schema(self.db, self.migration)
                    self.prepare_legacy_location_inventory()
                    schema = 'sqlite_temp_master' if kind.startswith('temp_') else 'sqlite_master'
                    if kind.endswith('table'):
                        prefix = 'TEMP ' if kind.startswith('temp_') else ''
                        self.db.execute(f'CREATE {prefix}TABLE {name} (marker TEXT)')
                        self.db.execute(f"INSERT INTO {name} VALUES ('synthetic-prior')")
                    elif kind.endswith('view'):
                        prefix = 'TEMP ' if kind.startswith('temp_') else ''
                        self.db.execute(f"CREATE {prefix}VIEW {name} AS SELECT 'synthetic-prior' AS marker")
                    else:
                        self.db.execute(f'CREATE INDEX {name} ON material(status)')
                    self.db.commit()
                    before = self.db.execute(f'SELECT type, name, sql FROM {schema} WHERE name=?', (name,)).fetchone()
                    _proxy, logger = self.exercise(deny_performance_indexes=False)
                    self.assertTrue(any('location_inventory' in str(args[0]) for args in logger.warnings))
                    self.assertEqual(self.db.execute(f'SELECT type, name, sql FROM {schema} WHERE name=?', (name,)).fetchone(), before)
                    self.assertEqual(self.db.execute(
                        'SELECT id, material_id, warehouse_id, location, quantity FROM location_inventory'
                    ).fetchall(), [(1, 42, 7, 'synthetic-location', 5.0)])
                    if not kind.endswith('index'):
                        self.assertEqual(self.db.execute(f'SELECT marker FROM {name}').fetchone()[0], 'synthetic-prior')
                finally:
                    self.db = original_db

    def test_successful_location_rebuild_preserves_unknown_schema(self):
        self.prepare_legacy_location_inventory()
        self.db.execute('ALTER TABLE location_inventory ADD COLUMN synthetic_extra TEXT')
        self.db.execute("UPDATE location_inventory SET synthetic_extra='original'")
        self.db.execute('CREATE INDEX synthetic_location_index ON location_inventory(synthetic_extra)')
        self.db.execute('CREATE TRIGGER synthetic_location_trigger AFTER UPDATE ON location_inventory BEGIN SELECT 1; END')
        self.db.commit()
        try:
            self.exercise(deny_performance_indexes=False)
        except (sqlite3.DatabaseError, RuntimeError):
            self.db.rollback()
        tables_and_objects = {row[0] for row in self.db.execute(
            "SELECT name FROM sqlite_master WHERE name IN "
            "('synthetic_location_index','synthetic_location_trigger')"
        )}
        columns = {row[1] for row in self.db.execute('PRAGMA table_info(location_inventory)')}
        self.assertEqual(tables_and_objects, {
            'synthetic_location_index', 'synthetic_location_trigger'})
        self.assertIn('synthetic_extra', columns)
        self.assertEqual(self.db.execute('SELECT synthetic_extra FROM location_inventory').fetchone()[0], 'original')

    def test_location_rebuild_must_preserve_column_constraints(self):
        original_db = self.db
        schemas = (
            "id INTEGER PRIMARY KEY, material_id INTEGER NOT NULL, warehouse_id INTEGER, location TEXT NOT NULL, quantity REAL DEFAULT 99, created_at TEXT, updated_at TEXT, UNIQUE(material_id, location)",
            "id INTEGER PRIMARY KEY, material_id INTEGER NOT NULL, warehouse_id INTEGER, location TEXT NOT NULL, quantity REAL CHECK(quantity >= 0), created_at TEXT, updated_at TEXT, UNIQUE(material_id, location)",
            "id INTEGER PRIMARY KEY, material_id INTEGER NOT NULL, warehouse_id INTEGER, location TEXT COLLATE NOCASE NOT NULL, quantity REAL, created_at TEXT, updated_at TEXT, UNIQUE(material_id, location)",
            "id INTEGER PRIMARY KEY, material_id INTEGER NOT NULL, warehouse_id INTEGER, location TEXT NOT NULL, quantity REAL, created_at TEXT, updated_at TEXT, UNIQUE(material_id, location), FOREIGN KEY(warehouse_id) REFERENCES material(id)",
        )
        for schema in schemas:
            with self.subTest(schema=schema):
                self.db = sqlite3.connect(':memory:')
                self.addCleanup(self.db.close)
                try:
                    synthetic_schema(self.db, self.migration)
                    self.db.execute('DROP TABLE location_inventory')
                    self.db.execute('CREATE TABLE location_inventory (' + schema + ')')
                    self.db.execute("INSERT INTO location_inventory (id,material_id,warehouse_id,location,quantity) VALUES(1,42,7,'synthetic',5)")
                    self.db.commit()
                    before = self.db.execute("SELECT sql FROM sqlite_master WHERE name='location_inventory'").fetchone()[0]
                    self.exercise(deny_performance_indexes=False)
                    after = self.db.execute("SELECT sql FROM sqlite_master WHERE name='location_inventory'").fetchone()[0]
                    self.assertEqual(after, before, '未知默认值、检查、排序规则或外键不可被静默更改')
                    self.assertEqual(self.db.execute('SELECT quantity FROM location_inventory WHERE id=1').fetchone()[0], 5)
                finally:
                    self.db = original_db

    def test_location_rebuild_preserves_storage_type_and_text_value(self):
        self.db.execute('DROP TABLE location_inventory')
        self.db.execute('''CREATE TABLE location_inventory (
            id INTEGER PRIMARY KEY, material_id INTEGER NOT NULL,
            warehouse_id INTEGER, location TEXT NOT NULL, quantity TEXT,
            created_at TEXT, updated_at TEXT, UNIQUE(material_id, location))''')
        self.db.execute("INSERT INTO location_inventory(id,material_id,warehouse_id,location,quantity) VALUES(1,42,7,'synthetic','000123')")
        self.db.commit()
        before = self.db.execute('SELECT quantity, typeof(quantity) FROM location_inventory WHERE id=1').fetchone()
        self.assertEqual(before, ('000123', 'text'))
        try:
            self.exercise(deny_performance_indexes=False)
        except (sqlite3.DatabaseError, RuntimeError):
            self.db.rollback()
        after = self.db.execute('SELECT quantity, typeof(quantity) FROM location_inventory WHERE id=1').fetchone()
        self.assertEqual(after, before, '重建不得静默改变历史值及 SQLite 存储类型')

    def test_location_new_constraint_name_alone_does_not_prove_new_unique(self):
        self.prepare_legacy_location_inventory()
        self.db.execute('CREATE INDEX uix_material_warehouse_location ON location_inventory(location)')
        self.db.commit()
        self.exercise(deny_performance_indexes=False)
        indexes = self.db.execute('PRAGMA index_list(location_inventory)').fetchall()
        actual = []
        for row in indexes:
            if row[2]:
                actual.append([r[0] for r in self.db.execute('SELECT name FROM pragma_index_info(?) ORDER BY seqno', (row[1],))])
        self.assertIn(['material_id', 'warehouse_id', 'location'], actual,
                      '同名非唯一索引不能代替三列唯一约束')
        self.assertNotIn(['material_id', 'location'], actual,
                         '旧双列唯一约束不应继续阻止跨仓同名库位')

    def test_opening_stock_rebuild_preserves_unknown_schema(self):
        self.db.execute('DROP TABLE opening_stock')
        self.db.execute('''CREATE TABLE opening_stock (
            id INTEGER PRIMARY KEY, doc_id INTEGER, material_id INTEGER NOT NULL,
            warehouse_id INTEGER, date DATE, location TEXT, quantity FLOAT,
            price FLOAT, amount FLOAT, remark TEXT, operator_id INTEGER,
            created_at DATETIME, updated_at DATETIME, synthetic_extra TEXT,
            UNIQUE(material_id, warehouse_id))''')
        self.db.execute("INSERT INTO opening_stock (id,material_id,warehouse_id,location,quantity,price,amount,synthetic_extra) VALUES (1,2,3,'synthetic',4,5,20,'original')")
        self.db.execute('CREATE INDEX synthetic_opening_index ON opening_stock(synthetic_extra)')
        self.db.execute('CREATE TRIGGER synthetic_opening_trigger AFTER UPDATE ON opening_stock BEGIN SELECT 1; END')
        self.db.commit()
        helpers = [n for n in self.functions if n.name == '_opening_stock_rebuild_table']
        namespace = {'re': re}
        exec(compile(ast.fix_missing_locations(ast.Module(body=helpers, type_ignores=[])),
                     '<synthetic-opening-rebuild>', 'exec'), namespace)
        self.db.execute('BEGIN EXCLUSIVE')
        try:
            namespace['_opening_stock_rebuild_table'](self.db.cursor())
            self.db.commit()
        except (sqlite3.DatabaseError, RuntimeError):
            self.db.rollback()
        objects = {row[0] for row in self.db.execute(
            "SELECT name FROM sqlite_master WHERE name IN ('synthetic_opening_index','synthetic_opening_trigger')")}
        columns = {row[1] for row in self.db.execute('PRAGMA table_info(opening_stock)')}
        self.assertEqual(objects, {'synthetic_opening_index', 'synthetic_opening_trigger'})
        self.assertIn('synthetic_extra', columns)
        self.assertEqual(self.db.execute('SELECT synthetic_extra FROM opening_stock').fetchone()[0], 'original')

    def test_location_rebuild_preserves_explicit_nonunique_index(self):
        self.prepare_legacy_location_inventory()
        self.db.execute('CREATE INDEX synthetic_location_warehouse_idx ON location_inventory(lower(location), quantity) WHERE quantity > 0')
        self.db.commit()
        expected = self.db.execute("SELECT sql FROM sqlite_master WHERE name='synthetic_location_warehouse_idx'").fetchone()[0]
        self.exercise(deny_performance_indexes=False)
        actual = self.db.execute("SELECT sql FROM sqlite_master WHERE name='synthetic_location_warehouse_idx'").fetchone()
        self.assertIsNotNone(actual)
        self.assertEqual(actual[0], expected)

    def test_opening_rebuild_preserves_explicit_nonunique_index(self):
        db = sqlite3.connect(':memory:')
        try:
            db.execute('''CREATE TABLE opening_stock (
                id INTEGER PRIMARY KEY, doc_id INTEGER, material_id INTEGER NOT NULL,
                warehouse_id INTEGER, date DATE, location VARCHAR(100) NOT NULL DEFAULT '', quantity FLOAT NOT NULL DEFAULT 0,
                price FLOAT NOT NULL DEFAULT 0, amount FLOAT NOT NULL DEFAULT 0, remark VARCHAR(500), operator_id INTEGER,
                created_at DATETIME, updated_at DATETIME, UNIQUE(material_id, warehouse_id))''')
            db.execute('CREATE INDEX synthetic_opening_warehouse_idx ON opening_stock(lower(location), quantity) WHERE quantity > 0')
            db.commit()
            expected = db.execute("SELECT sql FROM sqlite_master WHERE name='synthetic_opening_warehouse_idx'").fetchone()[0]
            helper = next(n for n in self.functions if n.name == '_opening_stock_rebuild_table')
            namespace = {}
            exec(compile(ast.fix_missing_locations(ast.Module(body=[helper], type_ignores=[])),
                         '<synthetic-opening-rebuild>', 'exec'), namespace)
            db.execute('BEGIN EXCLUSIVE')
            namespace['_opening_stock_rebuild_table'](db.cursor())
            db.commit()
            actual = db.execute("SELECT sql FROM sqlite_master WHERE name='synthetic_opening_warehouse_idx'").fetchone()
            self.assertIsNotNone(actual)
            self.assertEqual(actual[0], expected)
        finally:
            db.close()

    def test_opening_rebuild_refuses_nonstandard_unique_indexes(self):
        helper = next(n for n in self.functions if n.name == '_opening_stock_rebuild_table')
        namespace = {}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[helper], type_ignores=[])),
                     '<synthetic-opening-rebuild>', 'exec'), namespace)
        for suffix in ('WHERE warehouse_id IS NOT NULL', ''):
            with self.subTest(suffix=suffix):
                db = sqlite3.connect(':memory:')
                try:
                    db.execute('''CREATE TABLE opening_stock (
                        id INTEGER PRIMARY KEY, doc_id INTEGER, material_id INTEGER NOT NULL,
                        warehouse_id INTEGER, date DATE, location VARCHAR(100) NOT NULL DEFAULT '', quantity FLOAT NOT NULL DEFAULT 0,
                        price FLOAT NOT NULL DEFAULT 0, amount FLOAT NOT NULL DEFAULT 0, remark VARCHAR(500), operator_id INTEGER,
                        created_at DATETIME, updated_at DATETIME, UNIQUE(material_id, warehouse_id))''')
                    columns = 'material_id, warehouse_id' if suffix else 'material_id DESC, warehouse_id'
                    db.execute(f'CREATE UNIQUE INDEX synthetic_opening_unique ON opening_stock({columns}) {suffix}')
                    db.commit()
                    before = db.execute("SELECT sql FROM sqlite_master WHERE name='synthetic_opening_unique'").fetchone()
                    db.execute('BEGIN EXCLUSIVE')
                    with self.assertRaises(RuntimeError):
                        namespace['_opening_stock_rebuild_table'](db.cursor())
                    db.rollback()
                    self.assertEqual(db.execute("SELECT sql FROM sqlite_master WHERE name='synthetic_opening_unique'").fetchone(), before)
                finally:
                    db.close()

    def test_location_rebuild_refuses_nonstandard_unique_indexes(self):
        original_db = self.db
        for suffix in ('WHERE location IS NOT NULL', ''):
            with self.subTest(suffix=suffix):
                self.db = sqlite3.connect(':memory:')
                self.addCleanup(self.db.close)
                try:
                    synthetic_schema(self.db, self.migration)
                    self.prepare_legacy_location_inventory()
                    columns = 'material_id, location' if suffix else 'material_id, location COLLATE NOCASE'
                    self.db.execute(f'CREATE UNIQUE INDEX synthetic_location_unique ON location_inventory({columns}) {suffix}')
                    self.db.commit()
                    before = self.db.execute("SELECT sql FROM sqlite_master WHERE name='synthetic_location_unique'").fetchone()
                    _proxy, logger = self.exercise(deny_performance_indexes=False)
                    self.assertTrue(any('location_inventory' in str(args[0]) for args in logger.warnings))
                    self.assertEqual(self.db.execute("SELECT sql FROM sqlite_master WHERE name='synthetic_location_unique'").fetchone(), before)
                    ddl = self.db.execute("SELECT sql FROM sqlite_master WHERE name='location_inventory'").fetchone()[0]
                    self.assertRegex(ddl, r'(?is)UNIQUE\s*\(\s*material_id\s*,\s*location\s*\)')
                finally:
                    self.db = original_db

    def test_opening_rebuild_preserves_temp_trigger(self):
        db = sqlite3.connect(':memory:')
        try:
            db.execute('''CREATE TABLE opening_stock (
                id INTEGER PRIMARY KEY, doc_id INTEGER, material_id INTEGER NOT NULL,
                warehouse_id INTEGER, date DATE, location VARCHAR(100) NOT NULL DEFAULT '', quantity FLOAT NOT NULL DEFAULT 0,
                price FLOAT NOT NULL DEFAULT 0, amount FLOAT NOT NULL DEFAULT 0, remark VARCHAR(500), operator_id INTEGER,
                created_at DATETIME, updated_at DATETIME, UNIQUE(material_id, warehouse_id))''')
            db.execute('CREATE TEMP TRIGGER synthetic_opening_temp AFTER UPDATE ON main.opening_stock BEGIN SELECT 1; END')
            db.commit()
            helper = next(n for n in self.functions if n.name == '_opening_stock_rebuild_table')
            namespace = {}
            exec(compile(ast.fix_missing_locations(ast.Module(body=[helper], type_ignores=[])),
                         '<synthetic-opening-rebuild>', 'exec'), namespace)
            db.execute('BEGIN EXCLUSIVE')
            try:
                namespace['_opening_stock_rebuild_table'](db.cursor())
                db.commit()
            except (sqlite3.DatabaseError, RuntimeError):
                db.rollback()
            self.assertIsNotNone(db.execute("SELECT sql FROM sqlite_temp_master WHERE name='synthetic_opening_temp'").fetchone())
        finally:
            db.close()

    def test_opening_rebuild_must_preserve_unknown_default(self):
        db = sqlite3.connect(':memory:')
        try:
            db.execute('''CREATE TABLE opening_stock (
                id INTEGER PRIMARY KEY, doc_id INTEGER, material_id INTEGER NOT NULL,
                warehouse_id INTEGER, date DATE, location VARCHAR(100) NOT NULL DEFAULT '', quantity FLOAT NOT NULL DEFAULT 0,
                price FLOAT NOT NULL DEFAULT 99, amount FLOAT NOT NULL DEFAULT 0, remark VARCHAR(500), operator_id INTEGER,
                created_at DATETIME, updated_at DATETIME, UNIQUE(material_id, warehouse_id))''')
            db.commit()
            before = {row[1]: row[4] for row in db.execute('PRAGMA table_info(opening_stock)')}
            helper = next(n for n in self.functions if n.name == '_opening_stock_rebuild_table')
            namespace = {}
            exec(compile(ast.fix_missing_locations(ast.Module(body=[helper], type_ignores=[])),
                         '<synthetic-opening-rebuild>', 'exec'), namespace)
            db.execute('BEGIN EXCLUSIVE')
            try:
                namespace['_opening_stock_rebuild_table'](db.cursor())
                db.commit()
            except (sqlite3.DatabaseError, RuntimeError):
                db.rollback()
            after = {row[1]: row[4] for row in db.execute('PRAGMA table_info(opening_stock)')}
            self.assertEqual(after['price'], before['price'], '未知默认值不得静默变更')
        finally:
            db.close()

    def test_opening_legacy_fixture_keeps_indexes_and_removes_legacy_unique(self):
        tree = ast.parse((ROOT / 'tests/test_opening_stock_migration.py').read_text(encoding='utf-8-sig'))
        schema = next(n.value.value for n in tree.body if isinstance(n, ast.Assign)
                      and any(isinstance(t, ast.Name) and t.id == '_LEGACY_SCHEMA' for t in n.targets))
        db = sqlite3.connect(':memory:')
        try:
            db.executescript(schema)
            db.execute('ALTER TABLE opening_stock ADD COLUMN doc_id INTEGER')
            db.execute("INSERT INTO opening_stock(id,material_id,warehouse_id,date,quantity,price,amount) VALUES(1,1,2,'2026-01-01',3,4,12)")
            db.commit()
            helper = next(n for n in self.functions if n.name == '_opening_stock_rebuild_table')
            namespace = {}
            exec(compile(ast.fix_missing_locations(ast.Module(body=[helper], type_ignores=[])),
                         '<synthetic-opening-rebuild>', 'exec'), namespace)
            db.execute('BEGIN EXCLUSIVE')
            namespace['_opening_stock_rebuild_table'](db.cursor())
            db.commit()
            indexes = {row[1] for row in db.execute('PRAGMA index_list(opening_stock)')}
            self.assertTrue({'idx_opening_stock_material', 'idx_opening_stock_warehouse',
                             'idx_opening_stock_created'} <= indexes)
            self.assertEqual(db.execute('SELECT quantity,price,amount FROM opening_stock WHERE id=1').fetchone(), (3,4,12))
            db.execute("INSERT INTO opening_stock(id,material_id,warehouse_id,date,quantity,price,amount) VALUES(2,1,2,'2026-01-02',1,1,1)")
            self.assertEqual(db.execute('SELECT COUNT(*) FROM opening_stock').fetchone()[0], 2)
        finally:
            db.close()

    def test_opening_historical_orm_foreign_keys_and_defaults_preserved(self):
        # SQLite 等价结构来自 592c1a6e^ 的 OpeningStock 模型；Python default 不生成 server DEFAULT。
        db = sqlite3.connect(':memory:')
        try:
            db.executescript('''
                CREATE TABLE material (id INTEGER PRIMARY KEY);
                CREATE TABLE warehouse (id INTEGER PRIMARY KEY);
                CREATE TABLE user (id INTEGER PRIMARY KEY);
                CREATE TABLE opening_stock (
                    id INTEGER PRIMARY KEY, doc_id INTEGER, material_id INTEGER NOT NULL,
                    warehouse_id INTEGER, date DATE, location VARCHAR(100) NOT NULL,
                    quantity FLOAT NOT NULL, price FLOAT NOT NULL, amount FLOAT NOT NULL,
                    remark VARCHAR(500), operator_id INTEGER, created_at DATETIME, updated_at DATETIME,
                    CONSTRAINT uix_opening_stock_material_warehouse UNIQUE(material_id, warehouse_id),
                    FOREIGN KEY(material_id) REFERENCES material(id),
                    FOREIGN KEY(warehouse_id) REFERENCES warehouse(id),
                    FOREIGN KEY(operator_id) REFERENCES user(id)
                );
            ''')
            db.commit()
            old_fks = {(r[2], r[3], r[4]) for r in db.execute('PRAGMA foreign_key_list(opening_stock)')}
            old_defaults = {r[1]: r[4] for r in db.execute('PRAGMA table_info(opening_stock)')}
            self.assertEqual(len(old_fks), 3)
            self.assertIsNone(old_defaults['price'])
            helper = next(n for n in self.functions if n.name == '_opening_stock_rebuild_table')
            namespace = {}
            exec(compile(ast.fix_missing_locations(ast.Module(body=[helper], type_ignores=[])),
                         '<synthetic-opening-rebuild>', 'exec'), namespace)
            db.execute('BEGIN EXCLUSIVE')
            try:
                namespace['_opening_stock_rebuild_table'](db.cursor())
                db.commit()
            except (sqlite3.DatabaseError, RuntimeError):
                db.rollback()
            new_fks = {(r[2], r[3], r[4]) for r in db.execute('PRAGMA foreign_key_list(opening_stock)')}
            new_defaults = {r[1]: r[4] for r in db.execute('PRAGMA table_info(opening_stock)')}
            self.assertEqual(new_fks, old_fks, '历史外键不得静默丢失')
            self.assertEqual(new_defaults['price'], old_defaults['price'], '历史默认值不得静默改变')
        finally:
            db.close()

    def test_opening_rebuild_refuses_shadowed_objects_and_enabled_foreign_keys(self):
        helper = next(n for n in self.functions if n.name == '_opening_stock_rebuild_table')
        namespace = {}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[helper], type_ignores=[])),
                     '<synthetic-opening-rebuild>', 'exec'), namespace)
        for kind in ('main_table', 'temp_table', 'main_view', 'temp_view', 'main_index',
                     'shadow_source', 'enabled_fk'):
            with self.subTest(kind=kind):
                db = sqlite3.connect(':memory:')
                try:
                    db.execute('''CREATE TABLE opening_stock (
                        id INTEGER PRIMARY KEY, doc_id INTEGER, material_id INTEGER NOT NULL,
                        warehouse_id INTEGER, date DATE, location TEXT, quantity FLOAT,
                        price FLOAT, amount FLOAT, remark TEXT, operator_id INTEGER,
                        created_at DATETIME, updated_at DATETIME, UNIQUE(material_id, warehouse_id))''')
                    db.execute("INSERT INTO opening_stock(id, material_id, warehouse_id, location, quantity, price, amount) VALUES(1,2,3,'synthetic',4,5,20)")
                    name = 'OPENING_STOCK_NEW'
                    if kind.endswith('table'):
                        prefix = 'TEMP ' if kind.startswith('temp_') else ''
                        db.execute(f'CREATE {prefix}TABLE {name} (marker TEXT)')
                        db.execute(f"INSERT INTO {name} VALUES ('synthetic-prior')")
                    elif kind.endswith('view'):
                        prefix = 'TEMP ' if kind.startswith('temp_') else ''
                        db.execute(f"CREATE {prefix}VIEW {name} AS SELECT 'synthetic-prior' AS marker")
                    elif kind == 'main_index':
                        db.execute(f'CREATE INDEX {name} ON opening_stock(location)')
                    elif kind == 'shadow_source':
                        db.execute('CREATE TEMP TABLE OPENING_STOCK (marker TEXT)')
                        db.execute("INSERT INTO temp.OPENING_STOCK VALUES ('synthetic-prior')")
                    elif kind == 'enabled_fk':
                        db.execute('CREATE TABLE synthetic_child (id INTEGER, parent_id INTEGER REFERENCES opening_stock(id) ON DELETE CASCADE)')
                        db.execute('INSERT INTO synthetic_child VALUES (1,1)')
                    db.commit()
                    if kind == 'enabled_fk':
                        db.execute('PRAGMA foreign_keys=ON')
                        self.assertEqual(db.execute('PRAGMA foreign_keys').fetchone()[0], 1)
                    db.execute('BEGIN EXCLUSIVE')
                    with self.assertRaises(RuntimeError):
                        namespace['_opening_stock_rebuild_table'](db.cursor())
                    db.rollback()
                    self.assertEqual(db.execute('SELECT quantity FROM main.opening_stock WHERE id=1').fetchone()[0], 4.0)
                    if kind == 'enabled_fk':
                        self.assertEqual(db.execute('SELECT COUNT(*) FROM synthetic_child').fetchone()[0], 1)
                    if kind in ('main_table', 'temp_table', 'main_view', 'temp_view'):
                        self.assertEqual(db.execute(f'SELECT marker FROM {name}').fetchone()[0], 'synthetic-prior')
                    if kind == 'shadow_source':
                        self.assertEqual(db.execute('SELECT marker FROM temp.OPENING_STOCK').fetchone()[0], 'synthetic-prior')
                finally:
                    db.close()

    def test_opening_rebuild_requires_outer_transaction_and_main_source(self):
        helper = next(n for n in self.functions if n.name == '_opening_stock_rebuild_table')
        namespace = {}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[helper], type_ignores=[])),
                     '<synthetic-opening-rebuild>', 'exec'), namespace)
        db = sqlite3.connect(':memory:')
        try:
            db.execute('CREATE TABLE opening_stock (id INTEGER)')
            db.commit()
            self.assertFalse(db.in_transaction)
            with self.assertRaises(RuntimeError):
                namespace['_opening_stock_rebuild_table'](db.cursor())
            self.assertIsNone(db.execute("SELECT name FROM sqlite_master WHERE name='opening_stock_new'").fetchone())
            db.execute('DROP TABLE opening_stock')
            db.execute("ATTACH DATABASE ':memory:' AS synthetic_aux")
            db.execute('CREATE TABLE synthetic_aux.opening_stock (id INTEGER)')
            db.execute('INSERT INTO synthetic_aux.opening_stock VALUES(1)')
            db.commit()
            db.execute('BEGIN EXCLUSIVE')
            with self.assertRaises(RuntimeError):
                namespace['_opening_stock_rebuild_table'](db.cursor())
            db.rollback()
            self.assertEqual(db.execute('SELECT id FROM synthetic_aux.opening_stock').fetchall(), [(1,)])
            self.assertIsNone(db.execute("SELECT name FROM main.sqlite_master WHERE name='opening_stock_new'").fetchone())
        finally:
            db.close()

    def test_location_rebuild_refuses_enabled_foreign_keys_without_cascade(self):
        self.prepare_legacy_location_inventory()
        self.db.execute('CREATE TABLE synthetic_child (parent_id INTEGER REFERENCES location_inventory(id) ON DELETE CASCADE)')
        self.db.execute('INSERT INTO synthetic_child VALUES (1)')
        self.db.commit()
        self.db.execute('PRAGMA foreign_keys=ON')
        self.assertEqual(self.db.execute('PRAGMA foreign_keys').fetchone()[0], 1)
        _proxy, logger = self.exercise(deny_performance_indexes=False)
        self.assertTrue(any('location_inventory' in str(args[0]) for args in logger.warnings))
        self.assertEqual(self.db.execute('SELECT quantity FROM main.location_inventory WHERE id=1').fetchone()[0], 5.0)
        self.assertEqual(self.db.execute('SELECT parent_id FROM synthetic_child').fetchall(), [(1,)])

    def test_migration_refuses_temp_inventory_shadow_before_changes(self):
        self.prepare_legacy_location_inventory()
        self.db.execute('CREATE TEMP TABLE LOCATION_INVENTORY (marker TEXT)')
        self.db.execute("INSERT INTO temp.LOCATION_INVENTORY VALUES ('synthetic-prior')")
        self.db.commit()
        with self.assertRaises(RuntimeError):
            self.exercise(deny_performance_indexes=False)
        self.assertEqual(self.db.execute('SELECT quantity FROM main.location_inventory WHERE id=1').fetchone()[0], 5.0)
        self.assertEqual(self.db.execute('SELECT marker FROM temp.LOCATION_INVENTORY').fetchone()[0], 'synthetic-prior')
        self.assertIsNone(self.db.execute('SELECT status FROM material WHERE id=1').fetchone()[0])

    def test_opening_autoincrement_highwater_survives_rebuild(self):
        helper = next(n for n in self.functions if n.name == '_opening_stock_rebuild_table')
        namespace = {}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[helper], type_ignores=[])),
                     '<synthetic-opening-rebuild>', 'exec'), namespace)
        for keep_row in (False, True):
            with self.subTest(keep_row=keep_row):
                db = sqlite3.connect(':memory:')
                try:
                    db.executescript('''CREATE TABLE opening_stock (
                        id INTEGER PRIMARY KEY AUTOINCREMENT, material_id INTEGER NOT NULL,
                        warehouse_id INTEGER, UNIQUE(material_id, warehouse_id));
                        INSERT INTO opening_stock(id,material_id,warehouse_id) VALUES(100,1,1);
                        DELETE FROM opening_stock WHERE id=100;''')
                    if keep_row:
                        db.execute('INSERT INTO opening_stock(id,material_id,warehouse_id) VALUES(1,2,2)')
                    db.commit()
                    db.execute('BEGIN EXCLUSIVE')
                    namespace['_opening_stock_rebuild_table'](db.cursor())
                    db.commit()
                    db.execute('INSERT INTO opening_stock(material_id,warehouse_id) VALUES(3,3)')
                    self.assertEqual(db.execute('SELECT max(id) FROM opening_stock').fetchone()[0], 101)
                finally:
                    db.close()

    def test_opening_implicit_rowid_survives_rebuild(self):
        helper = next(n for n in self.functions if n.name == '_opening_stock_rebuild_table')
        namespace = {}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[helper], type_ignores=[])),
                     '<synthetic-opening-rebuild>', 'exec'), namespace)
        db = sqlite3.connect(':memory:')
        try:
            db.executescript('''CREATE TABLE opening_stock (
                id TEXT PRIMARY KEY, material_id INTEGER, warehouse_id INTEGER,
                UNIQUE(material_id, warehouse_id));
                INSERT INTO opening_stock VALUES('A',1,1);
                INSERT INTO opening_stock VALUES('B',2,2);
                DELETE FROM opening_stock WHERE id='A';''')
            db.commit()
            before = db.execute('SELECT rowid,id FROM opening_stock').fetchall()
            self.assertEqual(before, [(2, 'B')])
            db.execute('BEGIN EXCLUSIVE')
            namespace['_opening_stock_rebuild_table'](db.cursor())
            db.commit()
            self.assertEqual(db.execute('SELECT rowid,id FROM opening_stock').fetchall(), before)
        finally:
            db.close()

    def test_opening_rowid_aliases_shadowed_refuses_without_change(self):
        helper = next(n for n in self.functions if n.name == '_opening_stock_rebuild_table')
        namespace = {}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[helper], type_ignores=[])),
                     '<synthetic-opening-rebuild>', 'exec'), namespace)
        db = sqlite3.connect(':memory:')
        try:
            db.execute('''CREATE TABLE opening_stock (
                id TEXT PRIMARY KEY, material_id INTEGER, warehouse_id INTEGER,
                rowid TEXT, _rowid_ TEXT, oid TEXT, UNIQUE(material_id, warehouse_id))''')
            db.commit()
            before = db.execute("SELECT sql FROM sqlite_master WHERE name='opening_stock'").fetchone()
            db.execute('BEGIN EXCLUSIVE')
            with self.assertRaises(RuntimeError):
                namespace['_opening_stock_rebuild_table'](db.cursor())
            db.rollback()
            self.assertEqual(db.execute("SELECT sql FROM sqlite_master WHERE name='opening_stock'").fetchone(), before)
        finally:
            db.close()

    def test_opening_legacy_unique_index_with_quotes_is_detected(self):
        helper = next(n for n in self.functions if n.name == '_opening_stock_legacy_unique_index')
        namespace = {}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[helper], type_ignores=[])),
                     '<synthetic-opening-index>', 'exec'), namespace)
        db = sqlite3.connect(':memory:')
        try:
            db.execute('CREATE TABLE opening_stock(material_id INTEGER, warehouse_id INTEGER)')
            db.execute('''CREATE UNIQUE INDEX "synthetic index 'quoted" ON opening_stock(material_id,warehouse_id)''')
            self.assertEqual(namespace['_opening_stock_legacy_unique_index'](db.cursor()),
                             "synthetic index 'quoted")
        finally:
            db.close()

    def test_opening_composite_primary_key_is_not_silently_retained(self):
        helper = next(n for n in self.functions if n.name == '_opening_stock_rebuild_table')
        namespace = {}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[helper], type_ignores=[])),
                     '<synthetic-opening-rebuild>', 'exec'), namespace)
        db = sqlite3.connect(':memory:')
        try:
            db.execute('''CREATE TABLE opening_stock (
                material_id INTEGER, warehouse_id INTEGER,
                PRIMARY KEY(material_id,warehouse_id),
                UNIQUE(material_id,warehouse_id))''')
            db.commit()
            before = db.execute("SELECT sql FROM sqlite_master WHERE name='opening_stock'").fetchone()
            db.execute('BEGIN EXCLUSIVE')
            with self.assertRaises(RuntimeError):
                namespace['_opening_stock_rebuild_table'](db.cursor())
            db.rollback()
            self.assertEqual(db.execute("SELECT sql FROM sqlite_master WHERE name='opening_stock'").fetchone(), before)
        finally:
            db.close()

    def test_opening_complex_schema_survives_and_trigger_does_not_fire_during_copy(self):
        helper = next(n for n in self.functions if n.name == '_opening_stock_rebuild_table')
        namespace = {}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[helper], type_ignores=[])),
                     '<synthetic-opening-rebuild>', 'exec'), namespace)
        db = sqlite3.connect(':memory:')
        try:
            db.executescript("""
                CREATE TABLE warehouse(id INTEGER PRIMARY KEY);
                CREATE TABLE audit(message TEXT);
                CREATE TABLE opening_stock(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    material_id INTEGER,
                    warehouse_id INTEGER REFERENCES warehouse(id),
                    note TEXT DEFAULT 'a,b(c)',
                    doubled INTEGER GENERATED ALWAYS AS (material_id * 2) STORED,
                    CONSTRAINT old_pair UNIQUE(material_id,warehouse_id) ON CONFLICT FAIL,
                    UNIQUE(note,id)
                );
                CREATE INDEX "complex index" ON opening_stock(lower(note)) WHERE material_id > 0;
                CREATE TRIGGER "complex trigger" AFTER INSERT ON opening_stock
                    BEGIN INSERT INTO audit(message) VALUES(NEW.note); END;
                INSERT INTO opening_stock(id,material_id,warehouse_id) VALUES(100,1,1);
                DELETE FROM opening_stock WHERE id=100;
                INSERT INTO opening_stock(id,material_id,warehouse_id) VALUES(1,2,2);
            """)
            db.commit()
            audit_before = db.execute('SELECT message FROM audit ORDER BY rowid').fetchall()
            index_before = db.execute("SELECT sql FROM sqlite_master WHERE name='complex index'").fetchone()
            trigger_before = db.execute("SELECT sql FROM sqlite_master WHERE name='complex trigger'").fetchone()
            fks_before = db.execute('PRAGMA foreign_key_list(opening_stock)').fetchall()
            db.execute('BEGIN EXCLUSIVE')
            namespace['_opening_stock_rebuild_table'](db.cursor())
            db.commit()
            self.assertEqual(db.execute('SELECT message FROM audit ORDER BY rowid').fetchall(), audit_before)
            self.assertEqual(db.execute("SELECT sql FROM sqlite_master WHERE name='complex index'").fetchone(), index_before)
            self.assertEqual(db.execute("SELECT sql FROM sqlite_master WHERE name='complex trigger'").fetchone(), trigger_before)
            self.assertEqual(db.execute('PRAGMA foreign_key_list(opening_stock)').fetchall(), fks_before)
            self.assertEqual(db.execute('SELECT doubled FROM opening_stock WHERE id=1').fetchone()[0], 4)
            db.execute('INSERT INTO opening_stock(material_id,warehouse_id) VALUES(2,2)')
            self.assertEqual(db.execute('SELECT max(id) FROM opening_stock').fetchone()[0], 101)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM audit').fetchone()[0], len(audit_before) + 1)
        finally:
            db.close()


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(FullMigrationMemory)
    if suite.countTestCases() != 34:
        raise SystemExit('合成迁移测试清单不完整或为空')
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
