"""Synthetic transactions only; file-lock tests require the owned Windows LPAC."""
import importlib.util
from pathlib import Path
import sqlite3
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('schema_checkpoint_under_test', ROOT / 'app/sqlite_schema_checkpoint.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
SchemaOnlyCheckpoint = module.SchemaOnlyCheckpoint


class CheckpointMemory(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.addCleanup(self.db.close)
        self.db.execute('CREATE TABLE original(id INTEGER PRIMARY KEY, status TEXT)')
        self.db.execute("INSERT INTO original VALUES(1, 'before')")
        self.db.commit()

    def checkpoint(self):
        self.db.execute('BEGIN EXCLUSIVE')
        return SchemaOnlyCheckpoint(self.db)

    def test_requires_outer_transaction(self):
        with self.assertRaisesRegex(RuntimeError, '外层事务'):
            SchemaOnlyCheckpoint(self.db)

    def test_persist_additions(self):
        self.db.execute('CREATE TABLE audit(message TEXT)')
        self.db.execute("CREATE TRIGGER record_change AFTER UPDATE ON original BEGIN "
                        "INSERT INTO audit VALUES(new.status); END")
        self.db.commit()
        checkpoint = self.checkpoint()
        self.db.execute("UPDATE original SET status='unmarked'")
        self.db.execute('CREATE TABLE "quoted""table" (id INTEGER PRIMARY KEY AUTOINCREMENT, '
                        'parent INTEGER REFERENCES original(id), value TEXT DEFAULT \'synthetic\' CHECK(length(value)>0))')
        self.db.execute('CREATE UNIQUE INDEX "quoted index" ON "quoted""table"(parent)')
        self.assertTrue(checkpoint.persist_additions())
        self.assertTrue(self.db.in_transaction, '外层写锁必须继续持有')
        self.db.commit()
        self.assertEqual(self.db.execute('SELECT status FROM original').fetchone(), ('before',))
        self.assertEqual(self.db.execute('SELECT * FROM audit').fetchall(), [])
        self.db.execute('INSERT INTO "quoted""table"(parent) VALUES(1)')
        self.assertEqual(self.db.execute('SELECT id,value FROM "quoted""table"').fetchone(), (1, 'synthetic'))
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute('INSERT INTO "quoted""table"(parent) VALUES(1)')

    def test_without_additions_does_not_commit_unmarked_data(self):
        checkpoint = self.checkpoint()
        self.db.execute("UPDATE original SET status='unmarked'")
        self.assertFalse(checkpoint.persist_additions())
        self.db.rollback()
        self.assertEqual(self.db.execute('SELECT status FROM original').fetchone(), ('before',))

    def test_cancel(self):
        checkpoint = self.checkpoint()
        self.db.execute('CREATE INDEX new_index ON original(status)')
        checkpoint.cancel()
        self.assertFalse(checkpoint.persist_additions())
        self.db.rollback()
        self.assertIsNone(self.db.execute("SELECT name FROM sqlite_master WHERE name='new_index'").fetchone())

    def test_changed_existing_schema_is_refused(self):
        checkpoint = self.checkpoint()
        self.db.execute('ALTER TABLE original ADD COLUMN extra TEXT')
        with self.assertRaisesRegex(RuntimeError, '已有结构'):
            checkpoint.persist_additions()
        self.db.rollback()
        self.assertEqual([r[1] for r in self.db.execute('PRAGMA table_info(original)')], ['id', 'status'])

    def test_new_business_rows_are_not_silently_discarded(self):
        checkpoint = self.checkpoint()
        self.db.execute('CREATE TABLE copied AS SELECT * FROM original')
        with self.assertRaisesRegex(RuntimeError, '业务数据'):
            checkpoint.persist_additions()
        self.db.rollback()
        self.assertIsNone(self.db.execute("SELECT name FROM sqlite_master WHERE name='copied'").fetchone())

    def test_new_views_and_triggers_are_refused(self):
        for ddl in ('CREATE VIEW new_view AS SELECT * FROM original',
                    'CREATE TRIGGER new_trigger AFTER UPDATE ON original BEGIN SELECT 1; END'):
            with self.subTest(ddl=ddl):
                checkpoint = self.checkpoint()
                self.db.execute(ddl)
                with self.assertRaisesRegex(RuntimeError, '安全单独持久化'):
                    checkpoint.persist_additions()
                self.db.rollback()

    def test_replay_failure_rolls_back_all_changes(self):
        checkpoint = self.checkpoint()
        self.db.execute('CREATE TABLE new_table(id INTEGER)')
        self.db.execute('CREATE INDEX new_index ON original(status)')
        self.db.execute("UPDATE original SET status='unmarked'")
        def authorizer(action, first, *_):
            if action == sqlite3.SQLITE_CREATE_INDEX and first == 'new_index':
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK
        self.db.set_authorizer(authorizer)
        with self.assertRaises(sqlite3.DatabaseError):
            checkpoint.persist_additions()
        self.db.set_authorizer(None)
        self.db.rollback()
        self.assertEqual(self.db.execute('SELECT status FROM original').fetchone(), ('before',))
        self.assertIsNone(self.db.execute("SELECT name FROM sqlite_master WHERE name='new_table'").fetchone())


class CheckpointFileLock(unittest.TestCase):
    def test_outer_writer_lock_survives_savepoint_rollback_delete_and_wal(self):
        guard_spec = importlib.util.spec_from_file_location('owned_guard', ROOT / 'scripts/verify_db_guard.py')
        guard = importlib.util.module_from_spec(guard_spec)
        guard_spec.loader.exec_module(guard)
        try:
            profile = guard.require_owned_test_profile()
        except SystemExit:
            self.skipTest('真实文件锁验证只允许在操作系统隔离的自有测试 profile 中运行')
        with tempfile.TemporaryDirectory(prefix='schema-lock-', dir=profile) as directory:
            for mode in ('DELETE', 'WAL'):
                with self.subTest(mode=mode):
                    path = Path(directory) / (mode + '.sqlite')
                    with path.open('xb'):
                        pass
                    writer = sqlite3.connect(path, timeout=0)
                    other = sqlite3.connect(path, timeout=0)
                    try:
                        self.assertEqual(writer.execute('PRAGMA journal_mode=' + mode).fetchone()[0].upper(), mode)
                        writer.execute('CREATE TABLE original(id INTEGER PRIMARY KEY, status TEXT)')
                        writer.execute("INSERT INTO original VALUES(1,'before')")
                        writer.commit()
                        writer.execute('BEGIN EXCLUSIVE')
                        checkpoint = SchemaOnlyCheckpoint(writer)
                        writer.execute('CREATE INDEX new_index ON original(status)')
                        writer.execute("UPDATE original SET status='unmarked'")
                        observed = []
                        def authorizer(action, first, *_):
                            if action == sqlite3.SQLITE_CREATE_INDEX and first == 'new_index':
                                try:
                                    other.execute("UPDATE original SET status='concurrent'")
                                except sqlite3.OperationalError as exc:
                                    observed.append(exc.sqlite_errorcode)
                                else:
                                    observed.append('writer lock lost')
                            return sqlite3.SQLITE_OK
                        writer.set_authorizer(authorizer)
                        self.assertTrue(checkpoint.persist_additions())
                        writer.set_authorizer(None)
                        self.assertEqual(observed, [sqlite3.SQLITE_BUSY])
                        writer.commit()
                        self.assertEqual(other.execute('SELECT status FROM original').fetchone(), ('before',))
                        self.assertIsNotNone(other.execute("SELECT name FROM sqlite_master WHERE name='new_index'").fetchone())
                    finally:
                        writer.close()
                        other.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
