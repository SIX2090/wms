"""Offline source-anchored model of Android queue risks; not an Android runtime test."""
from contextlib import ExitStack
from pathlib import Path
import socket
import sqlite3
import subprocess
import threading
import unittest
from unittest.mock import patch


BASE = Path(__file__).resolve().parents[1] / 'app/android-native-wms/app/src/main/java/com/factory/wms/data'


def refuse(*_args, **_kwargs):
    raise AssertionError('real network, database files and subprocess are forbidden')


class AndroidOfflineIdentityModel(unittest.TestCase):
    def setUp(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        original = sqlite3.connect
        def memory_only(path, *args, **kwargs):
            if path != ':memory:':
                return refuse()
            return original(path, *args, **kwargs)
        for target, name, replacement in ((sqlite3, 'connect', memory_only),
                (socket.socket, 'connect', refuse), (socket.socket, 'connect_ex', refuse),
                (socket, 'getaddrinfo', refuse), (subprocess, 'Popen', refuse)):
            stack.enter_context(patch.object(target, name, replacement))
        self.queue = (BASE / 'repository/OfflineQueueManager.kt').read_text(encoding='utf-8')
        self.entity = (BASE / 'local/PendingOperationEntity.kt').read_text(encoding='utf-8')
        self.client = (BASE / 'api/RetrofitClient.kt').read_text(encoding='utf-8')

    def test_record_identity_is_explicit_and_transport_is_session_bound(self):
        fields = self.entity.split('data class PendingOperationEntity(', 1)[1].split(') {', 1)[0]
        for column in ('owner_server', 'owner_user_id', 'needs_review'):
            self.assertTrue(column in fields, column)
        self.assertIn('.tag(SessionSnapshot::class.java, session)', self.client)
        self.assertIn('if (apiRequest && (!trusted || !current))', self.client)
        self.assertIn('throw IOException(', self.client)

    def test_first_sync_checks_owner_and_never_reuses_cached_api(self):
        self.assertTrue('by lazy { apiProvider() }' not in self.queue)
        self.assertTrue('if (!belongsTo(op, session))' in self.queue)
        self.assertTrue('val api = apiProvider(session)' in self.queue)
        self.assertTrue('op.ownerServer == session.ownerServer && op.ownerUserId == session.userId' in self.queue)

    def test_login_never_attaches_previous_session_credential(self):
        self.assertIn('!request.url.encodedPath.endsWith("/api/login")', self.client)
        self.assertIn('if (baseUrl != url) authToken = null', self.client)
        repository = (BASE / 'repository/WmsRepository.kt').read_text(encoding='utf-8')
        self.assertIn('RetrofitClient.setSession(baseUrl, token, userId)', repository)
        self.assertIn('RetrofitClient.restoreSession(savedBaseUrl, savedToken, expected, getSavedUserId())', repository)

    def test_late_401_is_bound_to_origin_and_generation(self):
        self.assertIn('sameOrigin(response.request.url, session.server)', self.client)
        self.assertIn('generation == session.generation && session.token != null', self.client)
        self.assertIn('authToken = null', self.client)
        self.assertIn('onUnauthorized?.invoke()', self.client)

    def test_shared_image_client_checks_origin_and_each_redirect(self):
        application = (BASE.parent / 'WmsApplication.kt').read_text(encoding='utf-8')
        self.assertIn('RetrofitClient.sharedOkHttpClient()', application)
        self.assertIn('url.scheme == origin.scheme && url.host == origin.host && url.port == origin.port', self.client)
        self.assertIn('.removeHeader("Authorization")', self.client)
        self.assertIn('.addNetworkInterceptor', self.client)
        self.assertIn('chain.proceed(guardRequest(request, session, apiRequest))', self.client)

    def test_checked_request_uses_immutable_token_and_stale_api_is_rejected(self):
        self.assertIn('internal val token: String?', self.client)
        self.assertIn('session.token?.let', self.client)
        self.assertIn('val session = bound ?: sessionSnapshot()', self.client)
        # Source contracts only; real behavior runs in Android's JUnit suite.
        tests = BASE.parents[5] / 'test/java/com/factory/wms/RetrofitCredentialScopeTest.kt'
        runtime = tests.read_text(encoding='utf-8')
        self.assertIn('late401CannotClearAnotherAccountOnSameServer', runtime)
        self.assertIn('cachedApiSnapshotIsRejectedAfterSwitchBeforeSending', runtime)

    def test_429_is_retryable_before_the_business_failure_branch(self):
        self.assertLess(self.queue.index('code == 429'), self.queue.index('if (code in 400..499'))
        self.assertTrue('throw RetryLater(' in self.queue)
        self.assertTrue('response.headers()["Retry-After"]' in self.queue)
        self.assertTrue('nextRetryAt = e.nextRetryAt' in self.queue)

    def test_legacy_records_are_not_reset_and_database_open_cannot_rebuild(self):
        database = (BASE / 'local/AppDatabase.kt').read_text(encoding='utf-8')
        dao = (BASE / 'local/PendingOperationDao.kt').read_text(encoding='utf-8')
        self.assertTrue('deleteDatabase(DB_NAME)' not in database)
        self.assertTrue('throw e' in database)
        self.assertTrue('WHERE status = :syncing AND needs_review = 0' in dao)
        self.assertTrue('WHERE request_id = :requestId AND needs_review = 0' in dao)
        factory = (BASE / 'local/PreservingSQLiteOpenHelperFactory.kt').read_text(encoding='utf-8')
        self.assertTrue('override fun onCorruption' in factory)
        self.assertTrue('.allowDataLossOnRecovery(false)' in factory)

    def test_error_response_message_is_read_from_real_error_body(self):
        replay = self.queue.split('private suspend fun replay(', 1)[1].split('private fun belongsTo(', 1)[0]
        self.assertTrue('response.body()?.displayMessage()' in replay)
        self.assertTrue('response.errorBody()?.string()' in replay)
        self.assertTrue('gson.fromJson(it, ApiEnvelope::class.java)?.displayMessage()' in replay)
        self.assertTrue('code == 401 || code == 403' in replay)

    def test_queue_checks_storage_outcomes_and_rejects_overwrite(self):
        self.assertTrue('if (dao.markSyncing(op.requestId) != 1)' in self.queue)
        self.assertTrue('if (dao.deleteByRequestId(op.requestId) != 1)' in self.queue)
        self.assertTrue('if (dao.upsert(operation) == -1L)' in self.queue)
        self.assertTrue('existing.payloadJson != operation.payloadJson' in self.queue)

    def test_cancellation_is_not_converted_to_another_offline_operation(self):
        repository = (BASE / 'repository/WmsRepository.kt').read_text(encoding='utf-8')
        fallback = repository.split('private suspend fun submitWithOfflineFallback(', 1)[1].split(
            '/** 按作业类型写入本地操作日志', 1)[0]
        self.assertTrue('catch (e: CancellationException)' in fallback)
        self.assertLess(fallback.index('catch (e: CancellationException)'), fallback.index('catch (e: IOException)'))
        self.assertTrue('session = session' in fallback)
        self.assertTrue('catch (e: CancellationException)' in self.queue)

    def test_synthetic_migration_preserves_old_payload_and_marks_manual_review(self):
        db = sqlite3.connect(':memory:')
        self.addCleanup(db.close)
        self.assertTrue(all(not row[2] for row in db.execute('PRAGMA database_list')))
        db.execute('CREATE TABLE pending_operations(request_id TEXT PRIMARY KEY, payload_json TEXT, '
                   'status TEXT, attempt_count INTEGER, last_error TEXT)')
        original = [('old-a', '{"line":"synthetic"}', 'pending', 2, 'offline'),
                    ('old-b', '{"line":"synthetic-2"}', 'syncing', 4, 'lost response'),
                    ('old-c', '{"line":"synthetic-3"}', 'failed', 5, 'rejected')]
        db.executemany('INSERT INTO pending_operations VALUES (?,?,?,?,?)', original)
        db.commit()
        db.execute('BEGIN')
        db.execute('ALTER TABLE pending_operations ADD COLUMN owner TEXT')
        db.execute('ALTER TABLE pending_operations ADD COLUMN server TEXT')
        db.execute('ALTER TABLE pending_operations ADD COLUMN needs_review INTEGER NOT NULL DEFAULT 1')
        db.commit()
        self.assertEqual(db.execute('SELECT request_id,payload_json,status,attempt_count,last_error '
                                    'FROM pending_operations ORDER BY request_id').fetchall(), original)
        self.assertEqual(db.execute('SELECT request_id FROM pending_operations WHERE needs_review=1 '
                                    'ORDER BY request_id').fetchall(), [('old-a',), ('old-b',), ('old-c',)])
        self.assertEqual(db.execute("SELECT request_id FROM pending_operations WHERE status='pending' "
                                    'AND needs_review=0').fetchall(), [])
        # This SQL is an isolated design example, not a Room migration or a
        # claim that Android backup/restore or client rollback is implemented.


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(AndroidOfflineIdentityModel)
    if suite.countTestCases() != 12:
        raise SystemExit('synthetic test list must be explicitly nonempty')
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
