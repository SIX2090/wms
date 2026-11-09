"""No-new-table print alert claim experiment; synthetic memory SQLite only."""
from contextlib import ExitStack
import socket, sqlite3, subprocess, threading, time, unittest
from unittest.mock import patch
from uuid import uuid4


def refuse(*_args, **_kwargs):
    raise AssertionError('external database, network and subprocess forbidden')


class NoTableAlertPrototype(unittest.TestCase):
    def setUp(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        original = sqlite3.connect
        self.uri = 'file:wms-alert-existing-' + uuid4().hex + '?mode=memory&cache=shared'
        uri = self.uri
        def memory_only(path, *args, **kwargs):
            if path != uri or kwargs.get('uri') is not True:
                return refuse()
            return original(path, *args, **kwargs)
        for target, name, value in ((sqlite3, 'connect', memory_only),
                (socket.socket, 'connect', refuse), (socket.socket, 'connect_ex', refuse),
                (socket, 'getaddrinfo', refuse), (subprocess, 'Popen', refuse)):
            stack.enter_context(patch.object(target, name, value))
        self.db = sqlite3.connect(uri, uri=True)
        self.addCleanup(self.db.close)
        self.assertTrue(all(not row[2] for row in self.db.execute('PRAGMA database_list')))
        self.db.execute('CREATE TABLE wechat_share_log(id INTEGER PRIMARY KEY, module_key TEXT NOT NULL, '
                        'order_id INTEGER NOT NULL, status TEXT NOT NULL, created_at INTEGER NOT NULL)')
        self.db.commit()

    def claim(self, now, interval=600):
        connection = sqlite3.connect(self.uri, uri=True)
        try:
            for attempt in range(100):
                try:
                    connection.execute('BEGIN IMMEDIATE')
                    break
                except sqlite3.OperationalError as exc:
                    if 'locked' not in str(exc).lower() or attempt == 99:
                        raise
                    time.sleep(.001)
            # sending without a confirmed outcome remains blocking, including
            # after the time window. No remote call occurs inside this transaction.
            previous = connection.execute("SELECT 1 FROM wechat_share_log WHERE module_key='print_alert' "
                "AND (status='sending' OR created_at>=?) LIMIT 1", (now - interval,)).fetchone()
            if previous:
                connection.rollback()
                return None
            row = connection.execute("INSERT INTO wechat_share_log(module_key,order_id,status,created_at) "
                                     "VALUES('print_alert',0,'sending',?)", (now,))
            log_id = row.lastrowid
            connection.commit()
            return log_id
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def finish(self, log_id, status, now):
        assert status in ('sent', 'uncertain', 'queued_v2')
        row = self.db.execute("UPDATE wechat_share_log SET status=?,created_at=? WHERE id=? AND status='sending'",
                              (status, now, log_id))
        if row.rowcount != 1:
            self.db.rollback()
            raise RuntimeError('synthetic claim changed')
        self.db.commit()

    def test_simultaneous_distinct_notifications_reserve_once(self):
        barrier = threading.Barrier(2, timeout=5)
        results, errors = [], []
        def worker():
            try:
                barrier.wait()
                results.append(self.claim(10000))
            except Exception as exc:
                errors.append(type(exc).__name__)
        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads: thread.start()
        for thread in threads: thread.join(5)
        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertEqual(errors, [])
        self.assertEqual(sum(value is not None for value in results), 1)
        self.assertEqual(self.db.execute('SELECT count(*) FROM wechat_share_log').fetchone(), (1,))

    def test_crashed_sending_blocks_unrelated_notifications_beyond_window(self):
        self.assertIsNotNone(self.claim(10000))
        self.assertIsNone(self.claim(20000))
        self.assertEqual(self.db.execute('SELECT status FROM wechat_share_log').fetchone(), ('sending',))

    def test_terminal_uncertain_outside_window_cannot_identify_same_old_event(self):
        first = self.claim(10000)
        self.finish(first, 'uncertain', 10001)
        # The old schema stores the same zero order_id for all alerts; it
        # cannot establish whether the subsequent call is a new alert or a
        # repeated call for the original notification.
        second = self.claim(20000)
        self.assertIsNotNone(second)
        self.assertEqual(self.db.execute('SELECT DISTINCT order_id FROM wechat_share_log').fetchall(), [(0,)])

    def test_completion_time_preserves_global_interval(self):
        first = self.claim(10000)
        self.finish(first, 'sent', 10040)
        self.assertIsNone(self.claim(10640))
        self.assertIsNotNone(self.claim(10641))

    def test_failed_finalize_does_not_discard_sending_reservation(self):
        first = self.claim(10000)
        with self.assertRaises(RuntimeError):
            self.finish(first + 1, 'sent', 10001)
        self.assertEqual(self.db.execute('SELECT status FROM wechat_share_log').fetchone(), ('sending',))
        self.assertIsNone(self.claim(20000))


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(NoTableAlertPrototype)
    if suite.countTestCases() != 5:
        raise SystemExit('synthetic test list must be explicitly nonempty')
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
