"""Synthetic in-memory design experiment; not product code or a migration.

Demonstrates durable per-notification reservations and a separate shared rate
window.  It does not prove compatibility with any external database or schema.
"""
from contextlib import ExitStack
import socket
import sqlite3
import subprocess
import threading
import time
import unittest
from unittest.mock import patch
from uuid import uuid4


def refuse(*_args, **_kwargs):
    raise AssertionError('external database, network and child processes forbidden')


class SyntheticClaim:
    def __init__(self, connect):
        self.connect = connect

    def reserve(self, notification_id, now, interval):
        conn = self.connect()
        try:
            for attempt in range(100):
                try:
                    conn.execute('BEGIN IMMEDIATE')
                    break
                except sqlite3.OperationalError as exc:
                    if 'locked' not in str(exc).lower() or attempt == 99:
                        raise
                    time.sleep(0.001)
            if conn.execute('SELECT 1 FROM claim WHERE notification_id=?', (notification_id,)).fetchone():
                conn.rollback()
                return 'duplicate'
            if conn.execute('SELECT 1 FROM alert_log WHERE created_at>=? LIMIT 1',
                            (now - interval,)).fetchone():
                conn.rollback()
                return 'rate_limited'
            conn.execute("INSERT INTO claim VALUES(?, 'sending')", (notification_id,))
            conn.execute("INSERT INTO alert_log VALUES(?, ?, 'sending')", (notification_id, now))
            conn.commit()
            return 'claimed'
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def finish(self, notification_id, status, finished_at):
        if status not in ('sent', 'pending', 'uncertain'):
            raise ValueError('unknown status')
        conn = self.connect()
        try:
            conn.execute('BEGIN IMMEDIATE')
            count = conn.execute("UPDATE alert_log SET status=?,created_at=? WHERE notification_id=? AND status='sending'",
                                 (status, finished_at, notification_id)).rowcount
            count2 = conn.execute("UPDATE claim SET status=? WHERE notification_id=? AND status='sending'",
                                  (status, notification_id)).rowcount
            if (count, count2) != (1, 1):
                raise RuntimeError('reservation no longer owned')
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


class SyntheticAlertClaim(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        original_connect = sqlite3.connect
        self.uri = 'file:wms-alert-' + uuid4().hex + '?mode=memory&cache=shared'
        uri = self.uri
        def memory_only(path, *args, **kwargs):
            if path != uri or kwargs.get('uri') is not True:
                return refuse()
            return original_connect(path, *args, **kwargs)
        for target, name, replacement in ((sqlite3, 'connect', memory_only),
                (socket.socket, 'connect', refuse), (socket.socket, 'connect_ex', refuse),
                (socket, 'getaddrinfo', refuse), (subprocess, 'Popen', refuse)):
            self.stack.enter_context(patch.object(target, name, replacement))
        self.connect = lambda: sqlite3.connect(uri, uri=True, timeout=1)
        self.anchor = self.connect()
        self.addCleanup(self.anchor.close)
        self.assertTrue(all(not row[2] for row in self.anchor.execute('PRAGMA database_list')))
        self.anchor.executescript('''CREATE TABLE claim(notification_id INTEGER PRIMARY KEY, status TEXT NOT NULL);
            CREATE TABLE alert_log(notification_id INTEGER PRIMARY KEY, created_at INTEGER NOT NULL, status TEXT NOT NULL);''')
        self.anchor.commit()
        self.probe = SyntheticClaim(self.connect)

    def concurrent_claims(self, ids):
        barrier = threading.Barrier(len(ids), timeout=5)
        results, errors = [], []
        def run(notification_id):
            try:
                barrier.wait()
                results.append(self.probe.reserve(notification_id, 10000, 600))
            except Exception as exc:
                errors.append(repr(exc))
        workers = [threading.Thread(target=run, args=(value,)) for value in ids]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(5)
        self.assertTrue(all(not worker.is_alive() for worker in workers))
        self.assertEqual(errors, [])
        return results

    def test_same_notification_can_be_claimed_by_only_one_connection(self):
        self.assertCountEqual(self.concurrent_claims([1, 1]), ['claimed', 'duplicate'])
        self.assertEqual(self.anchor.execute('SELECT count(*) FROM claim').fetchone(), (1,))

    def test_different_notifications_share_global_interval(self):
        self.assertCountEqual(self.concurrent_claims([1, 2]), ['claimed', 'rate_limited'])
        self.assertEqual(self.anchor.execute('SELECT count(*) FROM alert_log').fetchone(), (1,))

    def test_crash_leaves_sending_and_same_notification_cannot_replay_after_interval(self):
        self.assertEqual(self.probe.reserve(1, 10000, 600), 'claimed')
        self.assertEqual(self.probe.reserve(1, 20000, 600), 'duplicate')
        self.assertEqual(self.anchor.execute('SELECT status FROM claim').fetchone(), ('sending',))
        self.assertEqual(self.probe.reserve(2, 20000, 600), 'claimed')

    def test_rate_window_starts_at_completion_and_boundary_is_inclusive(self):
        self.assertEqual(self.probe.reserve(1, 10000, 600), 'claimed')
        self.probe.finish(1, 'sent', 10040)
        self.assertEqual(self.probe.reserve(2, 10640, 600), 'rate_limited')
        self.assertEqual(self.probe.reserve(2, 10641, 600), 'claimed')

    def test_failure_after_claim_is_not_automatically_replayed(self):
        self.assertEqual(self.probe.reserve(1, 10000, 600), 'claimed')
        self.probe.finish(1, 'uncertain', 10010)
        self.assertEqual(self.probe.reserve(1, 20000, 600), 'duplicate')
        self.assertEqual(self.anchor.execute('SELECT status FROM alert_log').fetchone(), ('uncertain',))

    def test_rollback_after_partial_finalization_retains_durable_sending(self):
        self.assertEqual(self.probe.reserve(1, 10000, 600), 'claimed')
        self.anchor.execute('DELETE FROM claim WHERE notification_id=1')
        self.anchor.commit()
        with self.assertRaises(RuntimeError):
            self.probe.finish(1, 'sent', 10001)
        self.assertEqual(self.anchor.execute('SELECT status FROM alert_log').fetchone(), ('sending',))


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(SyntheticAlertClaim)
    if suite.countTestCases() != 6:
        raise SystemExit('synthetic test list must be explicitly nonempty')
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
