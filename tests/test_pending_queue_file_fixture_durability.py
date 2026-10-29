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


def test_disk_fixture_uses_a_unique_directory_for_all_context_database_operations():
    source = SOURCE.read_text(encoding='utf-8')
    assert 'Files.createTempDirectory("pending-queue-")' in source
    assert 'override fun getApplicationContext(): Context = this' in source
    assert 'override fun getDatabasePath(name: String): File = File(databaseDirectory, name)' in source
    assert 'super.deleteDatabase(getDatabasePath(name).absolutePath)' in source
    assert source.count('super.openOrCreateDatabase(getDatabasePath(name).absolutePath, mode, factory') == 2


def test_android_runtime_verifies_context_and_raw_database_share_the_fixture_path():
    source = SOURCE.read_text(encoding='utf-8')
    assert 'fun `fixture context routes opens and deletes to its unique directory`()' in source
    assert 'assertEquals(file.absolutePath, raw.path)' in source
    assert 'assertTrue(context === context.applicationContext)' in source
    assert 'assertTrue(context.deleteDatabase(dbName))' in source
