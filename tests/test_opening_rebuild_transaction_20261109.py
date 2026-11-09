"""Offline regression for rebuilding only synthetic SQLite memory tables."""
import ast
from pathlib import Path
import socket
import sqlite3
import subprocess
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def deny(*_args, **_kwargs):
    raise AssertionError('network and subprocess access forbidden')


class SyntheticOpeningRebuild(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.addCleanup(self.db.close)
        for guard in (patch.object(socket.socket, 'connect', deny),
                      patch.object(socket.socket, 'connect_ex', deny),
                      patch.object(socket, 'getaddrinfo', deny),
                      patch.object(subprocess, 'Popen', deny)):
            guard.start()
            self.addCleanup(guard.stop)
        tree = ast.parse((ROOT / 'app/app.py').read_text(encoding='utf-8-sig'))
        nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name == '_opening_stock_rebuild_table']
        self.assertEqual(len(nodes), 1)
        namespace = {}
        exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])),
                     '<synthetic-opening-rebuild>', 'exec'), namespace)
        self.rebuild = namespace['_opening_stock_rebuild_table']

    def prepare(self):
        self.db.executescript("""
            CREATE TABLE opening_stock (
                id INTEGER PRIMARY KEY AUTOINCREMENT, material_id INTEGER, warehouse_id INTEGER,
                quantity TEXT DEFAULT '000123', UNIQUE(material_id, warehouse_id));
            CREATE INDEX synthetic_index ON opening_stock(quantity);
            CREATE TABLE audit(message TEXT);
            CREATE TRIGGER synthetic_trigger AFTER INSERT ON opening_stock
                BEGIN INSERT INTO audit(message) VALUES(NEW.quantity); END;
            INSERT INTO opening_stock(id,material_id,warehouse_id) VALUES(100,1,1);
            DELETE FROM opening_stock WHERE id=100;
            INSERT INTO opening_stock(id,material_id,warehouse_id) VALUES(1,2,2);
        """)
        self.db.commit()

    def snapshot(self):
        schema = self.db.execute(
            "SELECT type,name,tbl_name,sql FROM sqlite_master WHERE type IN ('table','index','trigger') ORDER BY 1,2"
        ).fetchall()
        return (schema, self.db.execute('SELECT rowid,* FROM opening_stock').fetchall(),
                self.db.execute('SELECT * FROM audit').fetchall(),
                self.db.execute("SELECT seq FROM sqlite_sequence WHERE name='opening_stock'").fetchall())

    def test_index_recreation_failure_rolls_back_all_objects(self):
        self.prepare()
        before = self.snapshot()
        def deny_recreate(action, name, *_args):
            return sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_CREATE_INDEX and name == 'synthetic_index' else sqlite3.SQLITE_OK
        self.db.set_authorizer(deny_recreate)
        try:
            self.db.execute('BEGIN EXCLUSIVE')
            with self.assertRaises(sqlite3.DatabaseError):
                self.rebuild(self.db.cursor())
            self.db.rollback()
        finally:
            self.db.set_authorizer(None)
        self.assertEqual(self.snapshot(), before)

    def test_external_view_and_trigger_are_preserved_or_rebuild_rolls_back(self):
        self.prepare()
        self.db.executescript("""
            CREATE VIEW synthetic_view AS SELECT id,quantity FROM opening_stock;
            CREATE TABLE other(id INTEGER);
            CREATE TRIGGER other_trigger AFTER INSERT ON other
                BEGIN SELECT count(*) FROM opening_stock; END;
        """)
        self.db.commit()
        before = self.snapshot()
        self.db.execute('BEGIN EXCLUSIVE')
        try:
            self.rebuild(self.db.cursor())
            self.db.commit()
        except (sqlite3.DatabaseError, RuntimeError):
            self.db.rollback()
            self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.db.execute('SELECT id,quantity FROM synthetic_view').fetchall(), [(1, '000123')])
        self.db.execute('INSERT INTO other VALUES(1)')


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(SyntheticOpeningRebuild)
    if suite.countTestCases() != 2:
        raise SystemExit('synthetic test list incomplete')
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
