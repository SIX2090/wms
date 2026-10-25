"""Guard the explicit disk-fixture configuration; Android runtime is verified in CI."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'app/android-native-wms/app/src/test/java/com/factory/wms/PendingQueueRebuildProtectionTest.kt'


def test_disk_defaults_are_configured_before_opening_or_purging_database():
    source = SOURCE.read_text(encoding='utf-8')
    setup = source.split('fun setUp() {', 1)[1].split('\n    }', 1)[0]
    full = setup.index('ShadowSQLiteConnection.setDefaultSyncMode("FULL")')
    persist = setup.index('ShadowSQLiteConnection.setDefaultJournalMode("PERSIST")')
    context = setup.index('ApplicationProvider.getApplicationContext()')
    purge = setup.index('purgeDatabase()')
    assert full < context < purge
    assert persist < context


def test_android_runtime_checks_durability_and_reopened_queue():
    source = SOURCE.read_text(encoding='utf-8')
    probe = source.split('fun `file fixture persists queue with durable sqlite defaults`() {', 1)[1].split('\n    @Test', 1)[0]
    assert 'raw.rawQuery("PRAGMA synchronous", null)' in probe
    assert '2, cursor.getInt(0)' in probe
    assert 'raw.rawQuery("PRAGMA journal_mode", null)' in probe
    assert '"persist", cursor.getString(0)' in probe
    assert 'AppDatabase.backupPendingOperations(context)' in probe
    assert 'assertEquals("req-durable", rows.single().requestId)' in probe
