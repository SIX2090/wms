"""Synthetic in-memory SQLite checks for location rebuild; no WMS app import."""
import ast
from contextlib import ExitStack
from pathlib import Path
import socket
import sqlite3
import subprocess
import unittest
from unittest.mock import patch


def refuse(*_args, **_kwargs):
    raise AssertionError('network and subprocess forbidden')


source = (Path(__file__).resolve().parents[1] / 'app' / 'app.py').read_text(encoding='utf-8')
node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef)
            and n.name == '_location_inventory_rebuild_table')
namespace = {}
exec(compile(ast.Module(body=[node], type_ignores=[]), '<location-only>', 'exec'), namespace)
rebuild = namespace['_location_inventory_rebuild_table']


class LocationRebuild(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        stack = ExitStack()
        cls.addClassCleanup(stack.close)
        original_connect = sqlite3.connect
        def memory_only(path, *args, **kwargs):
            if path != ':memory:':
                return refuse()
            return original_connect(path, *args, **kwargs)
        stack.enter_context(patch.object(sqlite3, 'connect', memory_only))
        stack.enter_context(patch.object(socket.socket, 'connect', refuse))
        stack.enter_context(patch.object(socket.socket, 'connect_ex', refuse))
        stack.enter_context(patch.object(socket, 'getaddrinfo', refuse))
        stack.enter_context(patch.object(subprocess, 'Popen', refuse))

    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.addCleanup(self.db.close)
        self.assertTrue(all(not row[2] for row in self.db.execute('PRAGMA database_list')))

    def run_rebuild(self):
        self.db.commit()
        self.db.execute('BEGIN EXCLUSIVE')
        try:
            rebuild(self.db.cursor())
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def test_old_constraint_extra_objects_sequence_and_null_warehouse(self):
        self.db.executescript('''
            CREATE TABLE log(message TEXT);
            CREATE TABLE location_inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT, material_id INTEGER NOT NULL,
                warehouse_id INTEGER, location TEXT NOT NULL, quantity REAL,
                synthetic_extra TEXT, UNIQUE(material_id, location));
            CREATE INDEX custom_index ON location_inventory(lower(location)) WHERE quantity > 0;
            CREATE TRIGGER custom_trigger AFTER INSERT ON location_inventory
                BEGIN INSERT INTO log VALUES(NEW.synthetic_extra); END;
            INSERT INTO location_inventory(id,material_id,warehouse_id,location,quantity,synthetic_extra)
                VALUES(100,1,1,'removed',1,'removed');
            DELETE FROM location_inventory WHERE id=100;
            INSERT INTO location_inventory(id,material_id,warehouse_id,location,quantity,synthetic_extra)
                VALUES(1,1,NULL,'A',1,'kept');
        ''')
        index = self.db.execute("SELECT sql FROM sqlite_master WHERE name='custom_index'").fetchone()
        trigger = self.db.execute("SELECT sql FROM sqlite_master WHERE name='custom_trigger'").fetchone()
        log = self.db.execute('SELECT * FROM log').fetchall()
        self.run_rebuild()
        self.assertEqual(self.db.execute("SELECT sql FROM sqlite_master WHERE name='custom_index'").fetchone(), index)
        self.assertEqual(self.db.execute("SELECT sql FROM sqlite_master WHERE name='custom_trigger'").fetchone(), trigger)
        self.assertEqual(self.db.execute('SELECT * FROM log').fetchall(), log)
        self.assertEqual(self.db.execute('SELECT synthetic_extra FROM location_inventory').fetchone(), ('kept',))
        self.db.execute("INSERT INTO location_inventory(material_id,warehouse_id,location) VALUES(1,2,'A')")
        self.db.execute("INSERT INTO location_inventory(material_id,warehouse_id,location) VALUES(1,NULL,'A')")
        self.assertEqual(self.db.execute('SELECT max(id) FROM location_inventory').fetchone()[0], 102)
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("INSERT INTO location_inventory(material_id,warehouse_id,location) VALUES(1,2,'A')")

    def test_explicit_old_and_new_unique_both_present(self):
        self.db.executescript('''
            CREATE TABLE location_inventory(id INTEGER PRIMARY KEY,material_id INTEGER,
              warehouse_id INTEGER,location TEXT);
            CREATE UNIQUE INDEX old_u ON location_inventory(material_id,location);
            CREATE UNIQUE INDEX new_u ON location_inventory(material_id,warehouse_id,location);
            INSERT INTO location_inventory VALUES(1,1,1,'A');
        ''')
        self.run_rebuild()
        self.assertIsNone(self.db.execute("SELECT sql FROM sqlite_master WHERE name='old_u'").fetchone())
        self.assertIsNotNone(self.db.execute("SELECT sql FROM sqlite_master WHERE name='new_u'").fetchone())
        self.db.execute("INSERT INTO location_inventory VALUES(2,1,2,'A')")
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("INSERT INTO location_inventory VALUES(3,1,2,'A')")

    def test_hidden_rowid_is_preserved(self):
        self.db.executescript('''
            CREATE TABLE location_inventory(id TEXT PRIMARY KEY,material_id INTEGER,
              warehouse_id INTEGER,location TEXT,UNIQUE(material_id,location));
            INSERT INTO location_inventory VALUES('first',1,1,'A');
            INSERT INTO location_inventory VALUES('second',2,1,'A');
            DELETE FROM location_inventory WHERE id='first';
        ''')
        before = self.db.execute('SELECT rowid,id FROM location_inventory').fetchall()
        self.run_rebuild()
        self.assertEqual(self.db.execute('SELECT rowid,id FROM location_inventory').fetchall(), before)

    def test_external_view_failure_rolls_back(self):
        self.db.executescript('''
            CREATE TABLE location_inventory(id INTEGER PRIMARY KEY,material_id INTEGER,
              warehouse_id INTEGER,location TEXT,UNIQUE(material_id,location));
            INSERT INTO location_inventory VALUES(1,1,1,'A');
            CREATE VIEW external_view AS SELECT * FROM location_inventory;
        ''')
        before = self.db.execute('SELECT type,name,sql FROM sqlite_master ORDER BY name').fetchall()
        with self.assertRaises(sqlite3.DatabaseError):
            self.run_rebuild()
        self.assertEqual(self.db.execute('SELECT type,name,sql FROM sqlite_master ORDER BY name').fetchall(), before)
        self.assertEqual(self.db.execute('SELECT * FROM external_view').fetchall(), [(1,1,1,'A')])

    def test_real_model_foreign_keys_preserve_definitions_and_enforcement(self):
        self.db.executescript("""
            CREATE TABLE material(id INTEGER PRIMARY KEY);
            CREATE TABLE warehouse(id INTEGER PRIMARY KEY);
            INSERT INTO material VALUES(1);
            INSERT INTO warehouse VALUES(1),(2);
            CREATE TABLE location_inventory (
                id INTEGER NOT NULL, material_id INTEGER NOT NULL, warehouse_id INTEGER,
                location VARCHAR(100) NOT NULL, quantity FLOAT, created_at DATETIME,
                updated_at DATETIME, PRIMARY KEY (id),
                CONSTRAINT uix_material_location UNIQUE(material_id,location),
                FOREIGN KEY(material_id) REFERENCES material(id),
                FOREIGN KEY(warehouse_id) REFERENCES warehouse(id));
            INSERT INTO location_inventory VALUES(1,1,1,'A',5,NULL,NULL);
        """)
        before = self.db.execute('PRAGMA foreign_key_list(location_inventory)').fetchall()
        self.assertEqual(len(before), 2)
        self.run_rebuild()
        self.assertEqual(self.db.execute('PRAGMA foreign_key_list(location_inventory)').fetchall(), before)
        self.assertEqual(self.db.execute('PRAGMA foreign_key_check').fetchall(), [])
        self.db.execute('PRAGMA foreign_keys=ON')
        self.assertEqual(self.db.execute('PRAGMA foreign_keys').fetchone(), (1,))
        self.db.execute("INSERT INTO location_inventory(id,material_id,warehouse_id,location) VALUES(2,1,2,'A')")
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("INSERT INTO location_inventory(id,material_id,warehouse_id,location) VALUES(3,999,2,'B')")
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("INSERT INTO location_inventory(id,material_id,warehouse_id,location) VALUES(4,1,999,'B')")

    def test_unexpected_foreign_key_fails_without_changes(self):
        self.db.executescript("""
            CREATE TABLE material(id INTEGER PRIMARY KEY);
            CREATE TABLE location_inventory(id INTEGER PRIMARY KEY,material_id INTEGER,
                warehouse_id INTEGER REFERENCES material(id), location TEXT,
                UNIQUE(material_id,location));
            INSERT INTO location_inventory VALUES(1,1,1,'A');
        """)
        before = self.db.execute('SELECT type,name,sql FROM sqlite_master ORDER BY name').fetchall()
        with self.assertRaises(RuntimeError):
            self.run_rebuild()
        self.assertEqual(self.db.execute('SELECT type,name,sql FROM sqlite_master ORDER BY name').fetchall(), before)
        self.assertEqual(self.db.execute('SELECT * FROM location_inventory').fetchall(), [(1,1,1,'A')])

    def test_external_trigger_failure_rolls_back(self):
        self.db.executescript("""
            CREATE TABLE location_inventory(id INTEGER PRIMARY KEY,material_id INTEGER,
                warehouse_id INTEGER,location TEXT,UNIQUE(material_id,location));
            CREATE TABLE another(id INTEGER);
            CREATE TRIGGER outside_trigger AFTER INSERT ON another BEGIN
                INSERT INTO location_inventory(material_id,warehouse_id,location)
                VALUES(NEW.id,1,'synthetic'); END;
            INSERT INTO location_inventory VALUES(1,1,1,'A');
        """)
        before = self.db.execute('SELECT type,name,sql FROM sqlite_master ORDER BY name').fetchall()
        with self.assertRaises(sqlite3.DatabaseError):
            self.run_rebuild()
        self.assertEqual(self.db.execute('SELECT type,name,sql FROM sqlite_master ORDER BY name').fetchall(), before)
        self.db.execute('INSERT INTO another VALUES(2)')
        self.assertEqual(self.db.execute('SELECT count(*) FROM location_inventory').fetchone(), (2,))

    def test_unexpected_cascading_foreign_key_is_refused(self):
        self.db.executescript("""
            CREATE TABLE material(id INTEGER PRIMARY KEY);
            CREATE TABLE location_inventory(id INTEGER PRIMARY KEY,
                material_id INTEGER REFERENCES material(id) ON DELETE CASCADE,
                warehouse_id INTEGER,location TEXT,UNIQUE(material_id,location));
            INSERT INTO location_inventory VALUES(1,1,1,'A');
        """)
        before = self.db.execute('SELECT type,name,sql FROM sqlite_master ORDER BY name').fetchall()
        with self.assertRaises(RuntimeError):
            self.run_rebuild()
        self.assertEqual(self.db.execute('SELECT type,name,sql FROM sqlite_master ORDER BY name').fetchall(), before)
        self.assertEqual(self.db.execute('SELECT * FROM location_inventory').fetchall(), [(1,1,1,'A')])

    def test_complex_constraint_is_refused_and_original_preserved(self):
        self.db.executescript('''
            CREATE TABLE location_inventory(id INTEGER PRIMARY KEY,material_id INTEGER,
              warehouse_id INTEGER,location TEXT,quantity REAL CHECK(quantity>=0),
              UNIQUE(material_id,location));
            INSERT INTO location_inventory VALUES(1,1,1,'A',2);
        ''')
        before = self.db.execute("SELECT sql FROM sqlite_master WHERE name='location_inventory'").fetchone()
        with self.assertRaises(RuntimeError):
            self.run_rebuild()
        self.assertEqual(self.db.execute("SELECT sql FROM sqlite_master WHERE name='location_inventory'").fetchone(), before)
        self.assertEqual(self.db.execute('SELECT quantity FROM location_inventory').fetchone(), (2,))


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(LocationRebuild)
    if suite.countTestCases() != 9:
        raise SystemExit('synthetic test list is incomplete')
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
