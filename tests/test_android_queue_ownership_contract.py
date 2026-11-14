"""Queue source contracts and execution of the real migration SQL, without app import.

Android manager/Room behavior is covered by OfflineQueueOwnershipTest in Android CI.
This file only opens a synthetic in-memory SQLite database and reads source files.
"""
from pathlib import Path
import re
import sqlite3
import unittest

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'app/android-native-wms/app/src/main/java/com/factory/wms/data'


class QueueOwnershipContract(unittest.TestCase):
    def read(self, name):
        return (DATA / name).read_text(encoding='utf-8')

    def test_real_migration_preserves_every_old_column_and_quarantines_all_states(self):
        source = self.read('local/DatabaseMigrations.kt')
        migration = source.split('val MIGRATION_2_3 =', 1)[1].split('val ALL:', 1)[0]
        statements = re.findall(r'db\.execSQL\("([^"\n]+)"\)', migration)
        self.assertEqual(len(statements), 4)
        with sqlite3.connect(':memory:') as db:
            self.assertTrue(all(not row[2] for row in db.execute('PRAGMA database_list')))
            db.execute('CREATE TABLE pending_operations(request_id TEXT PRIMARY KEY, '
                       'payload_json TEXT, status TEXT, attempt_count INTEGER, last_error TEXT)')
            before = [('a', '{"qty":1}', 'pending', 2, 'offline'),
                      ('b', '{"qty":2}', 'syncing', 3, 'response lost'),
                      ('c', '{"qty":3}', 'failed', 5, 'business refusal')]
            db.executemany('INSERT INTO pending_operations VALUES(?,?,?,?,?)', before)
            for sql in statements:
                db.execute(sql.replace('`', ''))
            self.assertEqual(db.execute('SELECT request_id,payload_json,status,attempt_count,last_error '
                                        'FROM pending_operations ORDER BY request_id').fetchall(), before)
            self.assertEqual(db.execute('SELECT owner_server,owner_user_id,needs_review,next_retry_at '
                                        'FROM pending_operations').fetchall(), [(None, None, 1, 0)] * 3)

    def test_rows_have_owner_and_legacy_review_is_separate_from_original_status(self):
        entity = self.read('local/PendingOperationEntity.kt')
        for column in ('owner_server', 'owner_user_id', 'needs_review', 'next_retry_at'):
            self.assertIn('name = "' + column + '"', entity)
        self.assertIn('defaultValue = "1"', entity)
        self.assertIn('STATUS_AUTH_REQUIRED', entity)

    def test_no_runtime_delete_and_rebuild_on_database_open_failure(self):
        source = self.read('local/AppDatabase.kt')
        get_database = source.split('fun getDatabase(', 1)[1].split('internal fun ', 1)[0]
        self.assertNotIn('rebuildPreservingQueue(appContext)', get_database)
        self.assertIn('throw e', get_database)
        self.assertIn('原库已保留', get_database)
        self.assertIn('version = 3', source)
        self.assertNotIn('.fallbackToDestructiveMigration(', source)

    def test_submit_captures_one_api_and_owner_before_network_and_keeps_it_on_fallback(self):
        source = self.read('repository/WmsRepository.kt')
        body = source.split('private suspend fun submitWithOfflineFallback(', 1)[1].split(
            '/** 按作业类型写入本地操作日志', 1)[0]
        self.assertLess(body.index('val session = RetrofitClient.sessionSnapshot()'),
                        body.index('call(submitApi, requestId)'))
        self.assertIn('val submitApi = RetrofitClient.apiServiceFor(session)', body)
        self.assertIn('session = session', body)
        self.assertIn('catch (e: CancellationException)', body)

    def test_replay_never_caches_api_and_checks_owner_before_claim_and_send(self):
        source = self.read('repository/OfflineQueueManager.kt')
        self.assertNotIn('by lazy { apiProvider()', source)
        self.assertIn('belongsTo(op, session)', source)
        self.assertIn('apiProvider(session)', source)
        self.assertIn('catch (e: CancellationException)', source)
        self.assertIn('if (dao.markSyncing(op.requestId) != 1)', source)
        self.assertIn('if (dao.deleteByRequestId(op.requestId) != 1)', source)

    def test_http_classification_retains_error_body_and_throttling_delay(self):
        source = self.read('repository/OfflineQueueManager.kt')
        self.assertIn('code == 429', source)
        self.assertIn('code == 401 || code == 403', source)
        self.assertIn('response.errorBody()?.string()', source)
        self.assertIn('response.headers()["Retry-After"]', source)
        self.assertIn('STATUS_AUTH_REQUIRED', source)

    def test_unknown_rows_cannot_be_claimed_reset_or_silently_replaced(self):
        source = self.read('local/PendingOperationDao.kt')
        self.assertIn('OnConflictStrategy.IGNORE', source)
        self.assertIn('AND needs_review = 0', source)
        self.assertIn('owner_server = :ownerServer AND owner_user_id = :ownerUserId', source)
        self.assertIn('AND next_retry_at <= :now', source)

    def test_identity_is_stable_user_id_not_token_or_entered_username(self):
        source = self.read('repository/WmsRepository.kt')
        self.assertIn('envelope.data.user.id', source)
        self.assertIn('KEY_USER_ID', source)
        self.assertIn('getSavedUserId()', source)
        self.assertIn('ownerUserId = session.userId', self.read('repository/OfflineQueueManager.kt'))

    def test_three_submit_screens_show_reason_and_only_offer_an_eligible_retry(self):
        ui = DATA.parent / 'ui'
        screens = (ui / 'screens/ScanScreens.kt').read_text(encoding='utf-8')
        self.assertEqual(screens.count('offlineSyncMessage = uiState.offlineSyncMessage'), 3)
        self.assertEqual(screens.count('offlineRetryAvailable = uiState.offlineRetryAvailable'), 3)
        viewmodel = (ui / 'viewmodel/scan/ScanViewModel.kt').read_text(encoding='utf-8')
        self.assertIn('queue.lastSyncMessage.collect', viewmodel)
        self.assertIn('queue.canRetry.collect', viewmodel)
        banner = (ui / 'components/WmsComponents.kt').read_text(encoding='utf-8').split('fun PendingSyncBanner(', 1)[1]
        self.assertIn('if (canRetry)', banner)
        self.assertNotIn('已重试多次仍失败，请检查网络', banner)


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(QueueOwnershipContract)
    assert suite.countTestCases() == 9
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
