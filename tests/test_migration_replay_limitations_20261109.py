"""Synthetic SQLite counterexamples to blind post-rollback DDL replay.

No WMS runtime, file database, network or external process is used. These
tests demonstrate limits of a rejected prototype, not a production fix.
"""
from pathlib import Path
import socket
import sqlite3
import subprocess
import unittest
from unittest.mock import patch
from uuid import uuid4


def refuse(*_args, **_kwargs):
    raise AssertionError('file databases, network and subprocesses are forbidden')


class ReplayLimitations(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        uri = f'file:wms_synthetic_migration_{uuid4().hex}?mode=memory&cache=shared'
        self.first = sqlite3.connect(uri, uri=True)
        self.second = sqlite3.connect(uri, uri=True)
        for conn in (self.db, self.first, self.second):
            self.addCleanup(conn.close)
            self.assertTrue(all(not row[2] for row in conn.execute('PRAGMA database_list')))
        for guard in (patch.object(sqlite3, 'connect', refuse),
                      patch.object(sqlite3.dbapi2, 'connect', refuse),
                      patch.object(socket.socket, 'connect', refuse),
                      patch.object(socket.socket, 'connect_ex', refuse),
                      patch.object(socket, 'getaddrinfo', refuse),
                      patch.object(subprocess, 'Popen', refuse)):
            guard.start()
            self.addCleanup(guard.stop)

    def test_savepoint_cannot_rollback_dml_and_keep_later_ddl(self):
        db = self.db
        db.executescript('CREATE TABLE material(id INTEGER PRIMARY KEY,status TEXT);'
                         'INSERT INTO material VALUES(1,NULL);')
        db.execute('BEGIN EXCLUSIVE')
        db.execute('SAVEPOINT before_backfill')
        db.execute("UPDATE material SET status='active'")
        db.execute('CREATE INDEX idx_after_backfill ON material(status)')
        db.execute('ROLLBACK TO before_backfill')
        db.execute('RELEASE before_backfill')
        db.commit()
        self.assertIsNone(db.execute('SELECT status FROM material').fetchone()[0])
        self.assertIsNone(db.execute("SELECT 1 FROM sqlite_master WHERE name='idx_after_backfill'").fetchone())

    def test_create_table_as_select_replay_loses_rows(self):
        source = (Path(__file__).resolve().parents[1] / 'app/app.py').read_text(encoding='utf-8-sig')
        self.assertIn('CREATE TABLE opening_stock_backup_mw001 AS SELECT', source)
        db = self.db
        db.executescript('CREATE TABLE material(id INTEGER PRIMARY KEY,status TEXT);'
                         'INSERT INTO material VALUES(1,NULL);')
        db.execute('BEGIN EXCLUSIVE')
        db.execute("UPDATE material SET status='active'")
        db.execute('CREATE TABLE material_copy AS SELECT * FROM material')
        ddl = db.execute("SELECT sql FROM sqlite_master WHERE name='material_copy'").fetchone()[0]
        self.assertEqual(db.execute('SELECT count(*) FROM material_copy').fetchone()[0], 1)
        db.rollback()
        db.execute('BEGIN EXCLUSIVE')
        db.execute(ddl)
        db.commit()
        self.assertIsNone(db.execute('SELECT status FROM material').fetchone()[0])
        self.assertEqual(db.execute('SELECT count(*) FROM material_copy').fetchone()[0], 0)

    def test_trigger_dependent_schema_decision_survives_but_trigger_data_does_not(self):
        db = self.db
        db.executescript('CREATE TABLE material(id INTEGER PRIMARY KEY,status TEXT);'
                         'INSERT INTO material VALUES(1,NULL); CREATE TABLE marker(value TEXT);'
                         'CREATE TRIGGER marker_trigger AFTER UPDATE ON material '
                         'BEGIN INSERT INTO marker VALUES(NEW.status); END;')
        db.execute('BEGIN EXCLUSIVE')
        db.execute("UPDATE material SET status='active'")
        self.assertEqual(db.execute('SELECT count(*) FROM marker').fetchone()[0], 1)
        if db.execute('SELECT count(*) FROM marker').fetchone()[0]:
            db.execute('CREATE INDEX idx_trigger_selected ON material(status)')
        ddl = db.execute("SELECT sql FROM sqlite_master WHERE name='idx_trigger_selected'").fetchone()[0]
        db.rollback()
        db.execute('BEGIN EXCLUSIVE')
        db.execute(ddl)
        db.commit()
        self.assertEqual(db.execute('SELECT count(*) FROM marker').fetchone()[0], 0)
        self.assertIsNotNone(db.execute("SELECT 1 FROM sqlite_master WHERE name='idx_trigger_selected'").fetchone())

    def test_additions_only_cannot_replay_removal_of_old_index(self):
        db = self.db
        db.executescript('CREATE TABLE items(x INTEGER,y INTEGER); CREATE INDEX idx_old ON items(x);')
        db.execute('BEGIN EXCLUSIVE')
        db.execute('DROP INDEX idx_old')
        db.execute('CREATE INDEX idx_new ON items(y)')
        ddl = db.execute("SELECT sql FROM sqlite_master WHERE name='idx_new'").fetchone()[0]
        db.rollback()
        db.execute('BEGIN EXCLUSIVE')
        db.execute(ddl)
        db.commit()
        names = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE name IN ('idx_old','idx_new')")}
        self.assertEqual(names, {'idx_old', 'idx_new'})

    def test_other_connection_can_change_schema_between_rollback_and_relock(self):
        first, second = self.first, self.second
        first.execute('CREATE TABLE items(id INTEGER)')
        first.commit()
        first.execute('BEGIN EXCLUSIVE')
        first.execute('CREATE INDEX idx_items ON items(id)')
        first.rollback()
        second.execute('ALTER TABLE items ADD COLUMN concurrent_value TEXT')
        second.commit()
        first.execute('BEGIN EXCLUSIVE')
        self.assertEqual([r[1] for r in first.execute('PRAGMA table_info(items)')], ['id', 'concurrent_value'])
        first.rollback()


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ReplayLimitations)
    if suite.countTestCases() != 5:
        raise SystemExit('synthetic test list must be explicitly nonempty')
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
