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

    def test_record_has_no_identity_and_cached_api_can_mix_new_token_with_old_origin(self):
        entity_fields = self.entity.split('data class PendingOperationEntity(', 1)[1].split(') {', 1)[0]
        self.assertNotIn('username', entity_fields.lower())
        self.assertNotIn('baseurl', entity_fields.lower())
        self.assertNotIn('server', entity_fields.lower())
        self.assertIn('private val api: WmsApiService by lazy { apiProvider() }', self.queue)
        self.assertIn('authToken?.let { token ->', self.client)
        self.assertIn('retrofit = buildRetrofit(url)', self.client)
        # Model only the verified source properties: API captures its origin on
        # creation while the shared interceptor reads the current token on send.
        state = {'base': 'synthetic-A', 'token': 'token-A'}
        cached_origin = state['base']
        state.update(base='synthetic-B', token='token-B')
        observed_origin, observed_token = cached_origin, state['token']
        self.assertEqual((observed_origin, observed_token), ('synthetic-A', 'token-B'))
        self.assertNotEqual(observed_token, 'token-A')

    def test_first_sync_after_switch_uses_new_origin_for_old_unowned_row(self):
        self.assertIn('private val api: WmsApiService by lazy { apiProvider() }', self.queue)
        self.assertIn('api.submitInbound(op.requestId, body)', self.queue)
        row = {'requestId': 'synthetic-old', 'payload': 'synthetic-A'}
        current = {'base': 'synthetic-B', 'account': 'synthetic-user-B'}
        # No ownership fields exist in the entity; first lazy resolution uses
        # the current session rather than the original submitter's identity.
        replay = (current['base'], current['account'], row['requestId'], row['payload'])
        self.assertEqual(replay, ('synthetic-B', 'synthetic-user-B', 'synthetic-old', 'synthetic-A'))

    def test_new_login_can_attach_previous_server_token_in_source_model(self):
        repository = (BASE / 'repository/WmsRepository.kt').read_text(encoding='utf-8')
        login = repository.split('suspend fun login(username:', 1)[1].split('suspend fun ', 1)[0]
        self.assertLess(login.index('RetrofitClient.setBaseUrl(baseUrl)'), login.index('api.login('))
        self.assertNotIn('RetrofitClient.setToken(null)', login[:login.index('api.login(')])
        interceptor = self.client.split('private val authInterceptor = Interceptor', 1)[1]
        self.assertLess(interceptor.index('addHeader("Authorization"'), interceptor.index('val isLoginRequest'))
        state = {'origin': 'synthetic-A', 'token': 'synthetic-A-token'}
        state['origin'] = 'synthetic-B'
        observed = (state['origin'], state['token'])
        self.assertEqual(observed, ('synthetic-B', 'synthetic-A-token'))

    def test_late_401_can_clear_new_session_in_source_model(self):
        interceptor = self.client.split('private val authInterceptor = Interceptor', 1)[1].split(
            '// 日志仅在 debug', 1)[0]
        self.assertIn('authToken = null', interceptor)
        self.assertIn('onUnauthorized?.invoke()', interceptor)
        self.assertNotIn('authToken ==', interceptor)
        state = {'token': 'synthetic-A-token'}
        state['token'] = 'synthetic-B-token'
        # A's earlier request returns 401 after the B session was installed.
        state['token'] = None
        self.assertIsNone(state['token'])

    def test_absolute_image_uses_shared_unconditional_auth_in_source_model(self):
        kotlin_root = BASE.parent
        application = (kotlin_root / 'WmsApplication.kt').read_text(encoding='utf-8')
        material = (kotlin_root / 'ui/screens/MaterialArchiveScreens.kt').read_text(encoding='utf-8')
        self.assertIn('RetrofitClient.sharedOkHttpClient()', application)
        self.assertIn('if (url.startsWith("http://") || url.startsWith("https://")) return url', material)
        self.assertIn('authToken?.let { token ->', self.client)
        self.assertIn('addHeader("Authorization", "Bearer $token")', self.client)
        token = 'synthetic-token'
        image_url = 'https://untrusted.invalid/synthetic.png'
        self.assertEqual((image_url, token), ('https://untrusted.invalid/synthetic.png', 'synthetic-token'))

    def test_switch_after_identity_check_before_header_read_is_unsafe_in_model(self):
        self.assertIn('authToken?.let { token ->', self.client)
        self.assertIn('private val api: WmsApiService by lazy { apiProvider() }', self.queue)
        state = {'server': 'synthetic-A', 'account': 'A', 'token': 'token-A'}
        checked = threading.Event()
        switched = threading.Event()
        outgoing = []
        def replay():
            self.assertEqual((state['server'], state['account']), ('synthetic-A', 'A'))
            checked.set()
            if not switched.wait(3):
                raise AssertionError('synthetic session switch did not complete')
            outgoing.append(('synthetic-A', state['token']))
        def switch():
            if not checked.wait(3):
                raise AssertionError('synthetic identity check did not complete')
            state.update(server='synthetic-B', account='B', token='token-B')
            switched.set()
        threads = [threading.Thread(target=replay), threading.Thread(target=switch)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(4)
        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertEqual(outgoing, [('synthetic-A', 'token-B')])

    def test_429_is_in_current_all_4xx_business_failure_branch(self):
        self.assertIn('if (code in 400..499)', self.queue)
        self.assertIn('throw BusinessException(msg)', self.queue)
        self.assertIn('markFailure(op, e.message ?: "服务端拒绝该请求", forceFail = true)', self.queue)
        self.assertTrue(400 <= 429 <= 499)

    def test_legacy_rebuild_model_discards_review_and_requeues_unknown_owner(self):
        database_source = (BASE / 'local/AppDatabase.kt').read_text(encoding='utf-8')
        dao = (BASE / 'local/PendingOperationDao.kt').read_text(encoding='utf-8')
        self.assertIn('appContext.deleteDatabase(DB_NAME)', database_source)
        self.assertIn('restorePendingOperations(rebuilt, backup)', database_source)
        self.assertIn('WHERE status = :pending ORDER BY created_at ASC', dao)
        db = sqlite3.connect(':memory:')
        self.addCleanup(db.close)
        db.execute('CREATE TABLE pending_operations(request_id TEXT PRIMARY KEY, payload_json TEXT, '
                   'status TEXT, attempt_count INTEGER, last_error TEXT, owner TEXT, server TEXT, '
                   'needs_review INTEGER NOT NULL)')
        db.execute("INSERT INTO pending_operations VALUES('synthetic-old','{\"qty\":1}',"
                   "'pending',2,'lost response',NULL,NULL,1)")
        # Model the old client's fixed-column backup and v2 rebuild, using only
        # an in-memory table; the real Room downgrade cannot be run here.
        legacy = db.execute('SELECT request_id,payload_json,status,attempt_count,last_error '
                            'FROM pending_operations').fetchall()
        db.execute('DROP TABLE pending_operations')
        db.execute('CREATE TABLE pending_operations(request_id TEXT PRIMARY KEY, payload_json TEXT, '
                   'status TEXT, attempt_count INTEGER, last_error TEXT)')
        db.executemany('INSERT INTO pending_operations VALUES(?,?,?,?,?)', legacy)
        self.assertEqual(db.execute("SELECT request_id FROM pending_operations WHERE status='pending'")
                         .fetchall(), [('synthetic-old',)])
        columns = {row[1] for row in db.execute('PRAGMA table_info(pending_operations)')}
        self.assertNotIn('needs_review', columns)
        self.assertEqual(db.execute('SELECT * FROM pending_operations').fetchone(), legacy[0])

    def test_error_response_model_loses_specific_message(self):
        replay = self.queue.split('private suspend fun replay(', 1)[1].split('private suspend fun markFailure(', 1)[0]
        self.assertIn('response.body()?.displayMessage()', replay)
        self.assertNotIn('response.errorBody()', replay)
        fake_body = None  # Retrofit error responses carry content in errorBody, not body.
        fake_error_body = '{"status":"error","msg":"synthetic warehouse permission"}'
        displayed = fake_body or '服务端返回 403'
        self.assertEqual(displayed, '服务端返回 403')
        self.assertIn('synthetic warehouse permission', fake_error_body)

    def test_source_ignores_queue_mark_and_delete_failures(self):
        self.assertIn('runCatching { dao.markSyncing(op.requestId) }', self.queue)
        self.assertIn('runCatching { dao.deleteByRequestId(op.requestId) }', self.queue)
        self.assertLess(self.queue.index('runCatching { dao.markSyncing(op.requestId) }'),
                        self.queue.index('replay(op)'))
        dao = (BASE / 'local/PendingOperationDao.kt').read_text(encoding='utf-8')
        self.assertIn('WHERE status = :syncing', dao)
        self.assertIn('runCatching { dao.resetStuckSyncing() }', self.queue)

    def test_source_has_generic_catch_without_cancellation_exemption(self):
        repository = (BASE / 'repository/WmsRepository.kt').read_text(encoding='utf-8')
        fallback = repository.split('private suspend fun submitWithOfflineFallback(', 1)[1].split(
            '/** 按作业类型写入本地操作日志', 1)[0]
        self.assertIn('catch (e: Exception)', fallback)
        self.assertNotIn('catch (e: CancellationException)', fallback)
        sync = self.queue.split('private suspend fun doSync()', 1)[1].split('private suspend fun replay(', 1)[0]
        self.assertIn('catch (e: Exception)', sync)
        self.assertNotIn('catch (e: CancellationException)', sync)

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
