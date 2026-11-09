"""Prototype claim/receipt tests on a newly owned named SQLite memory database."""
import ast
import hashlib
import hmac
from pathlib import Path
import secrets
import socket
import sqlite3
import subprocess
import threading
import time
import unittest
import uuid
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def deny(*_args, **_kwargs):
    raise AssertionError('real network, file DB, or child process forbidden')


class ClaimPrototypeTests(unittest.TestCase):
    def setUp(self):
        self.uri = 'file:wms-synthetic-' + uuid.uuid4().hex + '?mode=memory&cache=shared'
        self.connect_real = sqlite3.connect
        uri = self.uri
        def memory_only(database, *args, **kwargs):
            if database != uri or kwargs.get('uri') is not True:
                deny()
            connection = self.connect_real(database, *args, **kwargs)
            if any(row[2] for row in connection.execute('PRAGMA database_list').fetchall()):
                connection.close()
                deny()
            return connection
        for target, name, replacement in ((socket.socket, 'connect', deny),
                                           (socket.socket, 'connect_ex', deny),
                                           (socket, 'getaddrinfo', deny),
                                           (socket, 'create_connection', deny),
                                           (subprocess, 'Popen', deny),
                                           (sqlite3, 'connect', memory_only)):
            guard = patch.object(target, name, replacement)
            guard.start()
            self.addCleanup(guard.stop)
        self.anchor = sqlite3.connect(self.uri, uri=True, isolation_level=None)
        self.addCleanup(self.anchor.close)
        self.anchor.execute('CREATE TABLE task (id INTEGER PRIMARY KEY, status TEXT NOT NULL, message TEXT)')
        self.anchor.execute('CREATE TABLE direct_attempt (id INTEGER PRIMARY KEY, task_id INTEGER NOT NULL, state TEXT NOT NULL)')
        self.anchor.execute('CREATE TABLE synthetic_image (id INTEGER PRIMARY KEY)')
        self.anchor.execute('CREATE TABLE task_images (task_id INTEGER NOT NULL, image_id INTEGER NOT NULL)')
        self.anchor.execute("INSERT INTO task VALUES (1, 'queued_v2', '合成原始诊断')")
        tree = ast.parse((ROOT / 'tests/wechat_claim_candidate_20261109.py').read_text(encoding='utf-8-sig'))
        functions = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
        self.assertEqual({n.name for n in functions}, {'token_hash', 'claim', 'can_read_image', 'report',
                                                       'reserve_manual_force', 'cleanup_task', 'visible_message',
                                                       'remove_synthetic_expired_image', 'fetch_claimed_image'})
        self.env = {'hashlib': hashlib, 'hmac': hmac, 'secrets': secrets}
        exec(compile(ast.fix_missing_locations(ast.Module(body=functions, type_ignores=[])),
                     '<isolated-wechat-claim>', 'exec'), self.env)

    def test_concurrent_helpers_only_one_receives_the_token(self):
        barrier = threading.Barrier(8)
        results, errors = [], []
        def worker():
            try:
                db = sqlite3.connect(self.uri, uri=True, isolation_level=None)
                try:
                    barrier.wait(timeout=3)
                    for _ in range(200):
                        try:
                            results.append(self.env['claim'](db, 1, 'v2'))
                            break
                        except sqlite3.OperationalError as exc:
                            if 'locked' not in str(exc):
                                raise
                            time.sleep(0.005)
                    else:
                        raise AssertionError('claim did not finish')
                finally:
                    db.close()
            except Exception as exc:
                errors.append(exc)
        threads = [threading.Thread(target=worker) for _ in range(8)]
        for thread in threads: thread.start()
        for thread in threads: thread.join(timeout=5)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(errors, [])
        self.assertEqual(len(results), 8)
        winners = [token for token in results if token is not None]
        self.assertEqual(len(winners), 1)
        self.assertTrue(self.env['can_read_image'](self.anchor, 1, winners[0]))
        self.assertEqual(self.anchor.execute('SELECT status FROM task WHERE id=1').fetchone()[0], 'sending')

    def test_response_loss_or_process_exit_never_requeues(self):
        self.assertIsNotNone(self.env['claim'](self.anchor, 1, 'v2'))
        # Simulated process exit and lost token: another connection cannot claim it.
        another = sqlite3.connect(self.uri, uri=True, isolation_level=None)
        try:
            self.assertIsNone(self.env['claim'](another, 1, 'v2'))
        finally:
            another.close()
        self.assertEqual(self.anchor.execute('SELECT status FROM task').fetchone()[0], 'sending')

    def test_old_helper_and_old_pending_are_never_silently_claimed(self):
        with self.assertRaises(ValueError):
            self.env['claim'](self.anchor, 1, 'old')
        self.anchor.execute("UPDATE task SET status='pending' WHERE id=1")
        self.assertIsNone(self.env['claim'](self.anchor, 1, 'v2'))
        self.assertEqual(self.anchor.execute('SELECT status FROM task').fetchone()[0], 'pending')

    def test_image_and_report_need_the_exact_claim_token(self):
        token = self.env['claim'](self.anchor, 1, 'v2')
        stored = self.anchor.execute('SELECT message FROM task WHERE id=1').fetchone()[0]
        self.assertIn('合成原始诊断', stored)
        self.assertNotIn(token, stored)
        for wrong in (None, '', '0' * 64, '界' * 64, ' ' * 64,
                      token[:-1] + ('0' if token[-1] != '0' else '1')):
            with self.subTest(token=wrong):
                self.assertFalse(self.env['can_read_image'](self.anchor, 1, wrong))
                self.assertFalse(self.env['report'](self.anchor, 1, wrong, 'sent'))
        self.assertTrue(self.env['can_read_image'](self.anchor, 1, token))
        self.assertTrue(self.env['report'](self.anchor, 1, token, 'sent', '合成回报'))
        self.assertFalse(self.env['report'](self.anchor, 1, token, 'failed'))
        self.assertFalse(self.env['can_read_image'](self.anchor, 1, token))
        self.assertEqual(self.anchor.execute('SELECT status FROM task').fetchone()[0], 'sent')
        self.assertEqual(self.anchor.execute('SELECT message FROM task').fetchone()[0], '合成原始诊断\n回报：合成回报')

    def test_long_message_is_never_truncated_or_silently_claimed(self):
        original = 'x' * 499
        self.anchor.execute('UPDATE task SET message=? WHERE id=1', (original,))
        with self.assertRaisesRegex(ValueError, '过长'):
            self.env['claim'](self.anchor, 1, 'v2')
        self.assertEqual(self.anchor.execute('SELECT status,message FROM task').fetchone(), ('queued_v2', original))

    def test_long_or_leaking_report_keeps_task_reserved(self):
        token = self.env['claim'](self.anchor, 1, 'v2')
        self.assertFalse(self.env['report'](self.anchor, 1, token, 'sent', token))
        self.assertFalse(self.env['report'](self.anchor, 1, token, 'sent', 'x' * 500))
        self.assertEqual(self.anchor.execute('SELECT status FROM task').fetchone()[0], 'sending')
        self.assertIsNone(self.env['claim'](self.anchor, 1, 'v2'))

    def test_concurrent_message_mutation_blocks_stale_token(self):
        token = self.env['claim'](self.anchor, 1, 'v2')
        self.anchor.execute("UPDATE task SET message='人工备注已变更' WHERE id=1")
        self.assertFalse(self.env['can_read_image'](self.anchor, 1, token))
        self.assertFalse(self.env['report'](self.anchor, 1, token, 'sent'))
        self.assertEqual(self.anchor.execute('SELECT status,message FROM task').fetchone(),
                         ('sending', '人工备注已变更'))

    def test_manual_force_cannot_overlap_active_claim(self):
        self.assertFalse(self.env['reserve_manual_force'](self.anchor, 1, False))
        self.assertFalse(self.env['reserve_manual_force'](self.anchor, 1, True))
        token = self.env['claim'](self.anchor, 1, 'v2')
        self.assertFalse(self.env['reserve_manual_force'](self.anchor, 1, True))
        self.assertTrue(self.env['report'](self.anchor, 1, token, 'ready'))
        self.assertTrue(self.env['reserve_manual_force'](self.anchor, 1, True))
        self.assertFalse(self.env['reserve_manual_force'](self.anchor, 1, True))
        self.assertFalse(self.env['cleanup_task'](self.anchor, 1))
        self.assertEqual(self.anchor.execute('SELECT status FROM task').fetchone()[0], 'uncertain')

    def test_cleanup_keeps_active_or_ambiguous_records(self):
        for state in ('pending', 'queued_v2', 'sending', 'uncertain'):
            with self.subTest(state=state):
                self.anchor.execute('UPDATE task SET status=? WHERE id=1', (state,))
                self.assertFalse(self.env['cleanup_task'](self.anchor, 1))
                self.assertIsNotNone(self.anchor.execute('SELECT 1 FROM task WHERE id=1').fetchone())
        self.anchor.execute("UPDATE task SET status='sent' WHERE id=1")
        self.assertTrue(self.env['cleanup_task'](self.anchor, 1))

    def test_ui_hides_only_the_valid_internal_digest(self):
        self.env['claim'](self.anchor, 1, 'v2')
        stored = self.anchor.execute('SELECT message FROM task WHERE id=1').fetchone()[0]
        self.assertEqual(self.env['visible_message']('sending', stored), '合成原始诊断')
        arbitrary = '合成原始诊断\n[claim-sha256:not-a-digest]'
        self.assertEqual(self.env['visible_message']('sending', arbitrary), arbitrary)
        self.assertEqual(self.env['visible_message']('failed', stored), stored)

    def test_expired_shared_image_is_preserved_while_any_task_is_active(self):
        self.anchor.execute('INSERT INTO synthetic_image VALUES (9)')
        self.anchor.execute('INSERT INTO task_images VALUES (1,9)')
        self.anchor.execute("INSERT INTO task VALUES (2, 'sent', '合成历史')")
        self.anchor.execute('INSERT INTO task_images VALUES (2,9)')
        self.assertFalse(self.env['remove_synthetic_expired_image'](self.anchor, 9))
        token = self.env['claim'](self.anchor, 1, 'v2')
        self.assertFalse(self.env['remove_synthetic_expired_image'](self.anchor, 9))
        self.assertTrue(self.env['report'](self.anchor, 1, token, 'ready'))
        self.assertFalse(self.env['remove_synthetic_expired_image'](self.anchor, 9))
        self.anchor.execute("UPDATE task SET status='sent' WHERE id=1")
        self.assertTrue(self.env['remove_synthetic_expired_image'](self.anchor, 9))

    def test_redirect_is_not_followed_with_the_claim_token(self):
        token = self.env['claim'](self.anchor, 1, 'v2')
        class Session:
            def __init__(self, status): self.status, self.calls = status, []
            def get(self, url, **kwargs):
                self.calls.append((url, kwargs))
                return type('Response', (), {'status_code': self.status, 'content': b'synthetic'})()
        for status in (301, 302, 303, 307, 308):
            with self.subTest(status=status):
                session = Session(status)
                with self.assertRaises(ValueError):
                    self.env['fetch_claimed_image'](session, 'https://synthetic.invalid', 1, token)
                self.assertEqual(len(session.calls), 1)
                self.assertFalse(session.calls[0][1]['allow_redirects'])
                self.assertEqual(self.anchor.execute('SELECT status FROM task').fetchone()[0], 'sending')
        session = Session(200)
        self.assertEqual(self.env['fetch_claimed_image'](session, 'https://synthetic.invalid', 1, token), b'synthetic')
        self.assertFalse(session.calls[0][1]['allow_redirects'])
        for invalid in ('https://synthetic.invalid.evil', 'http://synthetic.invalid',
                        'https://user@synthetic.invalid', 'https://synthetic.invalid:444'):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self.env['fetch_claimed_image'](session, invalid, 1, token)
        self.assertEqual(len(session.calls), 1)

    def test_uncertain_results_cannot_be_replayed(self):
        for reported in ('pending', 'ready', 'error', 'failed', 'unknown'):
            with self.subTest(reported=reported):
                self.anchor.execute("UPDATE task SET status='queued_v2',message='合成原始诊断' WHERE id=1")
                token = self.env['claim'](self.anchor, 1, 'v2')
                self.assertTrue(self.env['report'](self.anchor, 1, token, reported))
                self.assertEqual(self.anchor.execute('SELECT status FROM task').fetchone()[0], 'uncertain')
                self.assertIsNone(self.env['claim'](self.anchor, 1, 'v2'))

    def test_commit_failure_before_send_rolls_back(self):
        with self.assertRaisesRegex(RuntimeError, 'synthetic commit failure'):
            self.env['claim'](self.anchor, 1, 'v2', fail_before_commit=True)
        self.assertEqual(self.anchor.execute('SELECT status,message FROM task').fetchone(), ('queued_v2', '合成原始诊断'))
        self.assertIsNotNone(self.env['claim'](self.anchor, 1, 'v2'))

    def test_commit_succeeded_but_ack_lost_remains_nonretryable(self):
        db = self.anchor
        class LostCommitAck:
            def execute(self, *args): return db.execute(*args)
            def commit(self):
                db.commit()
                raise RuntimeError('synthetic lost commit acknowledgement')
            def rollback(self): db.rollback()
        with self.assertRaisesRegex(RuntimeError, 'lost commit acknowledgement'):
            self.env['claim'](LostCommitAck(), 1, 'v2')
        self.assertEqual(self.anchor.execute('SELECT status FROM task').fetchone()[0], 'sending')
        self.assertIsNone(self.env['claim'](self.anchor, 1, 'v2'))


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ClaimPrototypeTests)
    if suite.countTestCases() != 15:
        raise SystemExit('synthetic test list is incomplete or empty')
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
