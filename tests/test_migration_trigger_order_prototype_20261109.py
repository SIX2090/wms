"""Prove that deferring an unmarked migration backfill changes trigger ordering.

Only fabricated source, an in-memory SQLite connection, and synthetic rows are
used.  This deliberately rejects a prototype; it is not a product fix.
"""
from pathlib import Path
import runpy
import socket
import sqlite3
import subprocess
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def refuse(*_args, **_kwargs):
    raise AssertionError('external database, network, and subprocess forbidden')


def deferred_prototype(source):
    start = source.index('def auto_migrate_database(')
    end = source.index('\ndef backfill_empty_warehouse_documents(', start)
    function = source[start:end]
    modifications = (
        ('        modified = False\n',
         "        _synthetic_version = cursor.execute('PRAGMA main.schema_version').fetchone()[0]\n"
         '        modified = False\n'),
        ('''            cursor.execute(
                "UPDATE material SET status='active' WHERE status IS NULL OR TRIM(status)=''")''',
         '            pass  # prototype defers the backfill'),
        ('''        if not _table_exists('out_order'):
            conn.commit()''',
         '''        if not _table_exists('out_order'):
            if _table_exists('material'):
                cursor.execute("UPDATE material SET status='active' WHERE status IS NULL OR TRIM(status)=''")
            conn.commit()'''),
        ('''        if modified or schema_checkpoint.persist_additions():
            conn.commit()
    except Exception as e:''',
         '''        if modified and _table_exists('material'):
            cursor.execute("UPDATE material SET status='active' WHERE status IS NULL OR TRIM(status)=''")
        if modified or schema_checkpoint.persist_additions() or cursor.execute('PRAGMA main.schema_version').fetchone()[0] != _synthetic_version:
            conn.commit()
    except Exception as e:'''),
    )
    for before, after in modifications:
        if function.count(before) != 1:
            raise AssertionError('migration source changed; prototype is no longer applicable')
        function = function.replace(before, after)
    return source[:start] + function + source[end:]


class MigrationTriggerOrdering(unittest.TestCase):
    def setUp(self):
        original_connect = sqlite3.connect
        def memory_only(path, *args, **kwargs):
            if path != ':memory:':
                return refuse()
            return original_connect(path, *args, **kwargs)
        for guard in (patch.object(sqlite3, 'connect', memory_only),
                      patch.object(socket.socket, 'connect', refuse),
                      patch.object(socket.socket, 'connect_ex', refuse),
                      patch.object(socket, 'getaddrinfo', refuse),
                      patch.object(subprocess, 'Popen', refuse)):
            guard.start()
            self.addCleanup(guard.stop)

    def test_deferring_status_backfill_changes_trigger_dependent_results(self):
        source = (ROOT / 'app/app.py').read_text(encoding='utf-8')
        fixture = runpy.run_path(str(ROOT / 'tests/test_ai_migration_full_memory_20261108.py'))
        cls = fixture['FullMigrationMemory']
        results = []
        with tempfile.TemporaryDirectory(prefix='wms_synthetic_source_') as directory:
            for name, content in (('original', source), ('prototype', deferred_prototype(source))):
                path = Path(directory) / (name + '.py')
                path.write_text(content, encoding='utf-8')
                with patch.dict(cls.setUp.__globals__, {'SOURCE': path}):
                    case = cls('test_normal_synthetic_schema_creates_ai_index')
                    case.setUp()
                    try:
                        case.db.execute("INSERT INTO in_order(id,business_type,order_no,purpose) "
                                        "VALUES(1,'sentinel','IN-SYNTHETIC','')")
                        case.db.execute("CREATE TRIGGER synthetic_status_trigger AFTER UPDATE OF status ON material "
                                        "BEGIN UPDATE in_order SET business_type=NULL WHERE id=1; END")
                        case.db.commit()
                        case.exercise(deny_performance_indexes=False)
                        results.append(case.db.execute(
                            'SELECT business_type FROM in_order WHERE id=1').fetchone()[0])
                    finally:
                        case.doCleanups()
        self.assertEqual(results, ['采购入库', None],
                         'deferred backfill prototype changes an existing trigger-dependent result')


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(MigrationTriggerOrdering)
    if suite.countTestCases() != 1:
        raise SystemExit('synthetic test list must be explicitly nonempty')
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
