"""SQLite memory-only regression for migration index diagnostics.

Execute: python -I -S -B -X utf8 tests/test_ai_migration_index_diagnostics_20261108.py
Only the selected statements are extracted; the WMS app and migration entry
point are never imported or called.
"""
import ast
import logging
from pathlib import Path
import socket
import sqlite3
import subprocess
import unittest
from unittest.mock import patch


SOURCE = Path(__file__).resolve().parents[1] / 'app' / 'app.py'
FIRST = {'idx_ai_tool_call_denied', 'idx_ai_tool_call_user_source'}
SECOND = {'idx_ai_acceptance_snapshot_created', 'idx_ai_evidence_package_dates',
          'idx_ai_evidence_package_decision'}


def index_names(node):
    names = set()
    for entry in ast.walk(node):
        if isinstance(entry, ast.Constant) and isinstance(entry.value, str):
            for name in FIRST | SECOND:
                if name in entry.value:
                    names.add(name)
    return names


def source_groups():
    module = ast.parse(SOURCE.read_text(encoding='utf-8-sig'))
    migration = next(n for n in module.body if isinstance(n, ast.FunctionDef)
                     and n.name == 'auto_migrate_database')
    matches = {}
    for node in ast.walk(migration):
        if not isinstance(node, (ast.Try, ast.For)):
            continue
        # Ignore outer try/loops wrapping entire migration: only choose the
        # smallest node describing exactly one intended index group.
        found = index_names(node)
        if found not in (FIRST, SECOND):
            continue
        if any(isinstance(child, (ast.Try, ast.For)) and index_names(child) == found
               for child in ast.iter_child_nodes(node)):
            continue
        key = 'first' if found == FIRST else 'second'
        if key in matches:
            raise AssertionError('ambiguous migration index group')
        matches[key] = node
    if set(matches) != {'first', 'second'}:
        raise AssertionError('migration index groups not found')
    return matches


def real_preceding_fragments():
    """提取真实性能索引循环及 material.status 回填，不执行迁移入口。"""
    module = ast.parse(SOURCE.read_text(encoding='utf-8-sig'))
    migration = next(n for n in module.body if isinstance(n, ast.FunctionDef)
                     and n.name == 'auto_migrate_database')
    outer = next(n for n in migration.body if isinstance(n, ast.Try))
    body = outer.body
    assignments = [i for i, node in enumerate(body)
                   if isinstance(node, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == '_PERF_INDEX_DDL' for t in node.targets)]
    if len(assignments) != 1 or not isinstance(body[assignments[0] + 1], ast.For):
        raise AssertionError('性能索引片段不唯一或结构已变化')
    material = [n for n in body if isinstance(n, ast.If)
                and any(isinstance(x, ast.Constant) and isinstance(x.value, str)
                        and "UPDATE material SET status='active'" in x.value for x in ast.walk(n))]
    if len(material) != 1:
        raise AssertionError('物料状态回填片段不唯一或结构已变化')
    return [body[assignments[0]], body[assignments[0] + 1], material[0]]


def deny(*_args, **_kwargs):
    raise AssertionError('network, other database and child process are forbidden')


class FakeLogger:
    def __init__(self):
        self.messages = []

    def warning(self, message, *args, **_kwargs):
        self.messages.append(message % args if args else message)


class IndexDiagnostics(unittest.TestCase):
    def setUp(self):
        # The only database connection is created explicitly here, as a new
        # private in-memory SQLite database; subsequent connections are denied.
        self.db = sqlite3.connect(':memory:')
        self.addCleanup(self.db.close)
        for guard in (patch.object(sqlite3, 'connect', deny),
                      patch.object(sqlite3.dbapi2, 'connect', deny),
                      patch.object(socket.socket, 'connect', deny),
                      patch.object(socket.socket, 'connect_ex', deny),
                      patch.object(socket, 'getaddrinfo', deny),
                      patch.object(subprocess, 'Popen', deny)):
            guard.start()
            self.addCleanup(guard.stop)
        self.assertTrue(all(not row[2] for row in self.db.execute('PRAGMA database_list')))
        self.logger = FakeLogger()
        self.groups = source_groups()

    def run_group(self, which, cursor=None):
        node = self.groups[which]
        module = ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[]))
        scope = {'cursor': cursor or self.db.cursor(), 'logging': logging,
                 '__name__': 'synthetic_migration', 'sqlite3': sqlite3}
        with patch.object(logging, 'getLogger', return_value=self.logger):
            exec(compile(module, '<synthetic-migration-indexes>', 'exec'), scope)

    def indexes(self):
        return {r[0] for r in self.db.execute("SELECT name FROM sqlite_master WHERE type='index'")}

    def test_missing_one_column_reports_error_and_other_index_is_created(self):
        self.db.execute('CREATE TABLE ai_tool_call (user_id INTEGER, source TEXT, created_at TEXT)')
        self.run_group('first')
        self.assertIn('idx_ai_tool_call_user_source', self.indexes())
        self.assertNotIn('idx_ai_tool_call_denied', self.indexes())
        self.assertTrue(any('ai_tool_call' in msg and 'idx_ai_tool_call_denied' in msg
                            for msg in self.logger.messages))

    def test_expected_absent_table_does_not_hide_other_tables_indexes(self):
        self.db.execute('CREATE TABLE ai_acceptance_evidence_package (start_date TEXT, end_date TEXT, go_no_go_decision TEXT)')
        self.run_group('second')
        self.assertTrue({'idx_ai_evidence_package_dates', 'idx_ai_evidence_package_decision'} <= self.indexes())
        self.assertFalse(self.logger.messages, 'expected missing table must not be reported as unexpected')

    def test_real_operational_error_is_reported_and_remaining_index_attempted(self):
        self.db.execute('CREATE TABLE ai_tool_call (user_id INTEGER, source TEXT, created_at TEXT, permission_allowed INTEGER)')
        actual = self.db.cursor()

        class FaultCursor:
            def execute(self, sql, *args):
                if 'idx_ai_tool_call_denied' in sql:
                    raise sqlite3.OperationalError('synthetic database is locked')
                return actual.execute(sql, *args)

        self.run_group('first', FaultCursor())
        self.assertIn('idx_ai_tool_call_user_source', self.indexes())
        self.assertTrue(any('idx_ai_tool_call_denied' in msg and 'locked' in msg
                            for msg in self.logger.messages))

    def test_later_absent_table_is_expected_after_present_table(self):
        self.db.execute('CREATE TABLE ai_acceptance_daily_snapshot (created_at TEXT)')
        self.run_group('second')
        self.assertIn('idx_ai_acceptance_snapshot_created', self.indexes())
        self.assertEqual(self.logger.messages, [])

    def test_unexpected_missing_column_reports_specific_index(self):
        self.db.execute('CREATE TABLE ai_acceptance_daily_snapshot (created_at TEXT)')
        self.db.execute('CREATE TABLE ai_acceptance_evidence_package (start_date TEXT, end_date TEXT)')
        self.run_group('second')
        self.assertIn('idx_ai_evidence_package_dates', self.indexes())
        self.assertNotIn('idx_ai_evidence_package_decision', self.indexes())
        self.assertTrue(any('ai_acceptance_evidence_package' in msg
                            and 'idx_ai_evidence_package_decision' in msg
                            and 'no such column' in msg for msg in self.logger.messages))

    def test_logging_failure_does_not_abort_remaining_indexes(self):
        self.db.execute('CREATE TABLE ai_tool_call (user_id INTEGER, source TEXT, created_at TEXT)')
        self.logger.warning = deny
        self.run_group('first')
        self.assertIn('idx_ai_tool_call_user_source', self.indexes())

    def test_existing_healthy_schema_is_idempotent(self):
        self.db.execute('CREATE TABLE ai_tool_call (user_id INTEGER, source TEXT, created_at TEXT, permission_allowed INTEGER)')
        self.db.execute('CREATE TABLE ai_acceptance_daily_snapshot (created_at TEXT)')
        self.db.execute('CREATE TABLE ai_acceptance_evidence_package (start_date TEXT, end_date TEXT, go_no_go_decision TEXT)')
        for _ in range(2):
            self.run_group('first')
            self.run_group('second')
        self.assertTrue((FIRST | SECOND) <= self.indexes())
        self.assertEqual(self.logger.messages, [])

    def test_rollback_discards_indexes_and_unrelated_pending_backfill(self):
        self.db.execute('CREATE TABLE ai_tool_call (user_id INTEGER, source TEXT, created_at TEXT, permission_allowed INTEGER)')
        self.db.execute('CREATE TABLE synthetic_backfill (value INTEGER)')
        self.db.execute('INSERT INTO synthetic_backfill(value) VALUES (0)')
        self.db.commit()
        self.db.execute('BEGIN EXCLUSIVE')
        self.db.execute('UPDATE synthetic_backfill SET value = 1')
        self.run_group('first')
        self.assertTrue(FIRST <= self.indexes())
        self.db.rollback()
        self.assertFalse(FIRST & self.indexes())
        self.assertEqual(self.db.execute('SELECT value FROM synthetic_backfill').fetchone()[0], 0)

    def test_commit_persists_indexes_and_unrelated_pending_backfill(self):
        self.db.execute('CREATE TABLE ai_tool_call (user_id INTEGER, source TEXT, created_at TEXT, permission_allowed INTEGER)')
        self.db.execute('CREATE TABLE synthetic_backfill (value INTEGER)')
        self.db.execute('INSERT INTO synthetic_backfill(value) VALUES (0)')
        self.db.commit()
        self.db.execute('BEGIN EXCLUSIVE')
        self.db.execute('UPDATE synthetic_backfill SET value = 1')
        self.run_group('first')
        self.db.commit()
        self.assertTrue(FIRST <= self.indexes())
        self.assertEqual(self.db.execute('SELECT value FROM synthetic_backfill').fetchone()[0], 1)

    def execute_real_preceding_fragments(self):
        self.db.execute('CREATE TABLE material (id INTEGER PRIMARY KEY, status TEXT)')
        self.db.execute('INSERT INTO material (id, status) VALUES (1, NULL)')
        self.db.execute('CREATE TABLE ai_tool_call (user_id INTEGER, source TEXT, created_at TEXT, permission_allowed INTEGER)')
        self.db.commit()
        self.db.execute('BEGIN EXCLUSIVE')
        cursor = self.db.cursor()
        def table_exists(name):
            return bool(self.db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
            ).fetchone())
        namespace = {'cursor': cursor, '_table_exists': table_exists, 'modified': False,
                     'app': type('App', (), {'logger': self.logger})()}
        module = ast.fix_missing_locations(ast.Module(body=real_preceding_fragments(), type_ignores=[]))
        exec(compile(module, '<synthetic-real-preceding-migration>', 'exec'), namespace)
        self.assertFalse(namespace['modified'], '旧表缺失性能索引列时不能假定 modified 为真')
        self.assertEqual(self.db.execute('SELECT status FROM material WHERE id=1').fetchone()[0], 'active')
        self.run_group('first')
        self.assertTrue(FIRST <= self.indexes())

    def test_real_unflagged_material_backfill_rolls_back_with_indexes(self):
        self.execute_real_preceding_fragments()
        self.db.rollback()
        self.assertIsNone(self.db.execute('SELECT status FROM material WHERE id=1').fetchone()[0])
        self.assertFalse(FIRST & self.indexes())

    def test_real_unflagged_material_backfill_is_committed_with_indexes(self):
        self.execute_real_preceding_fragments()
        self.db.commit()
        self.assertEqual(self.db.execute('SELECT status FROM material WHERE id=1').fetchone()[0], 'active')
        self.assertTrue(FIRST <= self.indexes())

    def test_rollback_then_separate_index_transaction_preserves_backfill_rollback(self):
        self.execute_real_preceding_fragments()
        self.db.rollback()
        self.db.execute('BEGIN EXCLUSIVE')
        self.run_group('first')
        self.run_group('second')
        self.db.commit()
        self.assertIsNone(self.db.execute('SELECT status FROM material WHERE id=1').fetchone()[0])
        self.assertTrue(FIRST <= self.indexes())
        self.assertFalse(self.db.in_transaction)


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(IndexDiagnostics)
    if suite.countTestCases() != 12:
        raise SystemExit('测试清单为空或不完整')
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
