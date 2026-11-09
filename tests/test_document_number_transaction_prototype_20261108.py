"""Synthetic numbering prototype, not WMS implementation or migration.

Run: python -I -S -B -X utf8 tests/test_document_number_transaction_prototype_20261108.py
All SQLite connections use one freshly named shared in-memory database only.
No WMS import, file DB, network, printer, or subprocess is used by the prototype.
"""
import os
import subprocess
import sys


def main():
    import builtins
    import hashlib
    import json
    import secrets
    import socket
    import sqlite3
    import threading
    import time
    import unittest
    from concurrent.futures import ThreadPoolExecutor
    from unittest.mock import patch

    def forbidden(*_args, **_kwargs):
        raise AssertionError('synthetic prototype forbids app, network, and child processes')

    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        level = args[3] if len(args) > 3 else kwargs.get('level', 0)
        if level == 0 and (name == 'app' or name.startswith('app.')):
            forbidden()
        return real_import(name, *args, **kwargs)

    real_connect = sqlite3.connect
    nonce = secrets.token_hex(16)
    synthetic_uri = 'file:wms_number_' + nonce + '?mode=memory&cache=shared'

    def open_memory():
        # The URI is constructed locally, contains only a fresh hex nonce,
        # and has fixed memory/shared-cache flags; no caller controls it.
        if len(nonce) != 32 or not all(ch in '0123456789abcdef' for ch in nonce):
            raise AssertionError('invalid memory database identity')
        conn = real_connect(synthetic_uri, uri=True, timeout=0.2, isolation_level=None)
        rows = conn.execute('PRAGMA database_list').fetchall()
        if not rows or any(name not in ('main', 'temp') or path != '' for _, name, path in rows):
            conn.close()
            raise AssertionError('database is not private memory')
        return conn

    def create(conn, prefix, month, user, endpoint, key, payload, fail=False):
        """Illustrate the required atomic behavior, without WMS dependencies."""
        fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        # Shared-cache SQLite raises SQLITE_LOCKED without honoring busy_timeout;
        # retry this *synthetic* operation with a bounded deadline.
        deadline = time.monotonic() + 10
        while True:
            try:
                conn.execute('BEGIN IMMEDIATE')
                break
            except sqlite3.OperationalError as exc:
                if 'locked' not in str(exc).lower() or time.monotonic() >= deadline:
                    raise
                time.sleep(0.003)
        try:
            existing = conn.execute(
                'SELECT payload_hash, document_id, document_no FROM receipt '
                'WHERE user_id=? AND endpoint=? AND request_key=?', (user, endpoint, key)
            ).fetchone()
            if existing:
                if existing[0] != fingerprint:
                    raise ValueError('same key with changed payload')
                conn.commit()
                return existing[1], existing[2]

            # Real implementation must seed from every historical model sharing
            # this prefix; this prototype uses a pre-populated synthetic table.
            current = conn.execute('SELECT value FROM serial WHERE prefix=? AND month=?',
                                   (prefix, month)).fetchone()
            if current is None:
                base = prefix + month
                historical = conn.execute('SELECT number FROM history WHERE prefix=? AND month=?',
                                          (prefix, month)).fetchall()
                values = [int(no[len(base):]) for (no,) in historical
                          if no.startswith(base) and no[len(base):].isdigit()]
                conn.execute('INSERT INTO serial(prefix, month, value) VALUES(?,?,?)',
                             (prefix, month, max(values, default=0)))
            conn.execute('UPDATE serial SET value=value+1 WHERE prefix=? AND month=?', (prefix, month))
            number = prefix + month + f"{conn.execute('SELECT value FROM serial WHERE prefix=? AND month=?', (prefix, month)).fetchone()[0]:04d}"
            doc_id = conn.execute('INSERT INTO document(number, payload) VALUES (?, ?)',
                                  (number, json.dumps(payload, sort_keys=True))).lastrowid
            if fail == 'after_document':
                raise RuntimeError('synthetic transaction failure')
            conn.execute('INSERT INTO receipt(user_id, endpoint, request_key, payload_hash, document_id, document_no) '
                         'VALUES(?,?,?,?,?,?)', (user, endpoint, key, fingerprint, doc_id, number))
            if fail == 'after_receipt':
                raise RuntimeError('synthetic transaction failure')
            conn.commit()
            return doc_id, number
        except Exception:
            conn.rollback()
            raise

    class NumberingPrototype(unittest.TestCase):
        def setUp(self):
            self.blockers = [patch.object(socket.socket, 'connect', forbidden),
                             patch.object(socket.socket, 'connect_ex', forbidden),
                             patch.object(socket, 'getaddrinfo', forbidden),
                             patch.object(subprocess, 'Popen', forbidden),
                             patch.object(sqlite3, 'connect', forbidden),
                             patch.object(builtins, '__import__', side_effect=guarded_import)]
            for blocker in self.blockers:
                blocker.start()
                self.addCleanup(blocker.stop)
            self.anchor = open_memory()
            self.addCleanup(self.anchor.close)
            self.anchor.executescript('''
                CREATE TABLE serial(prefix TEXT NOT NULL, month TEXT NOT NULL, value INTEGER NOT NULL,
                                    PRIMARY KEY(prefix,month));
                CREATE TABLE history(source TEXT NOT NULL, prefix TEXT NOT NULL, month TEXT NOT NULL, number TEXT NOT NULL);
                CREATE TABLE document(id INTEGER PRIMARY KEY AUTOINCREMENT, number TEXT NOT NULL UNIQUE, payload TEXT NOT NULL);
                CREATE TABLE receipt(user_id INTEGER NOT NULL, endpoint TEXT NOT NULL, request_key TEXT NOT NULL,
                                     payload_hash TEXT NOT NULL, document_id INTEGER NOT NULL, document_no TEXT NOT NULL,
                                     PRIMARY KEY(user_id,endpoint,request_key));
            ''')

        def invoke(self, key, payload=None, prefix='IN', month='2611', fail=False, user=1, endpoint='create'):
            conn = open_memory()
            try:
                return create(conn, prefix, month, user, endpoint, key, payload or {'v': 1}, fail)
            finally:
                conn.close()

        def test_multiple_connections_allocate_unique_numbers(self):
            barrier = threading.Barrier(8)
            def worker(index):
                conn = open_memory()
                try:
                    barrier.wait(timeout=5)
                    return create(conn, 'IN', '2611', 1, 'create', 'request-' + str(index), {'v': 1})
                finally:
                    conn.close()
            with ThreadPoolExecutor(max_workers=8) as pool:
                results = list(pool.map(worker, range(8)))
            self.assertEqual(len({number for _, number in results}), 8)
            self.assertEqual(self.anchor.execute('SELECT count(*) FROM document').fetchone()[0], 8)

        def test_same_key_concurrent_replay_and_changed_payload(self):
            barrier = threading.Barrier(8)
            def worker(_index):
                conn = open_memory()
                try:
                    barrier.wait(timeout=5)
                    return create(conn, 'IN', '2611', 1, 'create', 'same-request', {'v': 1})
                finally:
                    conn.close()
            with ThreadPoolExecutor(max_workers=8) as pool:
                results = list(pool.map(worker, range(8)))
            self.assertEqual(len(set(results)), 1)
            self.assertEqual(self.anchor.execute('SELECT count(*) FROM document').fetchone()[0], 1)
            with self.assertRaises(ValueError):
                self.invoke('same-request', {'v': 2})
            self.assertEqual(self.anchor.execute('SELECT count(*) FROM document').fetchone()[0], 1)

        def test_failure_rolls_back_sequence_document_and_receipt(self):
            for point in ('after_document', 'after_receipt'):
                with self.subTest(point=point):
                    with self.assertRaisesRegex(RuntimeError, 'synthetic transaction failure'):
                        self.invoke('fail', fail=point)
                    for table in ('serial', 'document', 'receipt'):
                        self.assertEqual(self.anchor.execute('SELECT count(*) FROM ' + table).fetchone()[0], 0)
            self.assertEqual(self.invoke('fail')[1], 'IN26110001')

        def test_response_loss_replay_returns_same_document_and_number(self):
            original = self.invoke('lost-response', {'items': [1, 2]})
            replay = self.invoke('lost-response', {'items': [1, 2]})
            self.assertEqual(replay, original)
            self.assertEqual(self.anchor.execute('SELECT count(*) FROM document').fetchone()[0], 1)
            self.assertEqual(self.anchor.execute('SELECT value FROM serial').fetchone()[0], 1)

        def test_same_key_is_scoped_by_user_and_endpoint(self):
            first = self.invoke('shared-key', user=1, endpoint='create')
            second = self.invoke('shared-key', user=2, endpoint='create')
            third = self.invoke('shared-key', user=1, endpoint='other-create')
            self.assertEqual(len({first, second, third}), 3)
            self.assertEqual(len({first[1], second[1], third[1]}), 3)
            self.assertEqual(self.anchor.execute('SELECT count(*) FROM document').fetchone()[0], 3)

        def test_committed_deleted_number_is_not_reused(self):
            first_id, first_no = self.invoke('first')
            self.anchor.execute('DELETE FROM document WHERE id=?', (first_id,))
            second_id, second_no = self.invoke('second')
            self.assertNotEqual(first_no, second_no)
            self.assertNotEqual(first_id, second_id)
            # Replaying a request after its document was deleted is deliberately
            # not specified by this prototype; the production contract needs review.

        def test_month_boundaries_historical_seed_and_five_digit_sequence(self):
            self.anchor.executemany('INSERT INTO history(source,prefix,month,number) VALUES(?,?,?,?)', [
                ('inbound', 'SR', '2611', 'SR26119999'), ('subcontract', 'SR', '2611', 'SR261110000'),
                ('inbound', 'SR', '2611', 'SR2611not-a-sequence'), ('inbound', 'SR', '2610', 'SR26100007'),
            ])
            self.assertEqual(self.invoke('nov', prefix='SR')[1], 'SR261110001')
            self.assertEqual(self.invoke('dec', prefix='SR', month='2612')[1], 'SR26120001')
            self.assertEqual(self.invoke('oct', prefix='SR', month='2610')[1], 'SR26100008')

        def test_sqlite_integer_sequence_exhaustion_rolls_back(self):
            # SQLite promotes integer overflow to REAL. It must never be used as
            # a rounded or repeated document number after a failed increment.
            self.anchor.execute('INSERT INTO serial VALUES (?, ?, ?)', ('IN', '2611', 9223372036854775807))
            with self.assertRaises((ValueError, OverflowError)):
                self.invoke('overflow')
            row = self.anchor.execute('SELECT value, typeof(value) FROM serial '
                                      'WHERE prefix=? AND month=?', ('IN', '2611')).fetchone()
            self.assertEqual(row, (9223372036854775807, 'integer'))
            self.assertEqual(self.anchor.execute('SELECT count(*) FROM document').fetchone()[0], 0)
            self.assertEqual(self.anchor.execute('SELECT count(*) FROM receipt').fetchone()[0], 0)

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(NumberingPrototype)
    if suite.countTestCases() != 8:
        raise SystemExit('prototype test list must contain exactly 8 cases')
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)


def test_synthetic_numbering_prototype_in_isolated_process():
    env = {key: os.environ[key] for key in ('SYSTEMROOT', 'WINDIR') if key in os.environ}
    result = subprocess.run([sys.executable, '-I', '-S', '-B', '-X', 'utf8', __file__],
                            env=env, capture_output=True, text=True, encoding='utf-8', timeout=35)
    assert result.returncode == 0, result.stderr


if __name__ == '__main__':
    main()
