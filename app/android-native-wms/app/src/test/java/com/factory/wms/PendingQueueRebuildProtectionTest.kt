package com.factory.wms

import android.content.Context
import android.content.ContextWrapper
import android.database.DatabaseErrorHandler
import android.database.sqlite.SQLiteDatabase
import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import com.factory.wms.data.local.AppDatabase
import com.factory.wms.data.local.PendingOperationEntity
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.shadows.ShadowSQLiteConnection
import java.io.File
import java.nio.file.Files

/**
 * BUG-2026-09-21-005：删库重建不得静默清空离线待同步队列。
 *
 * ## 背景
 *
 * `AppDatabase.getDatabase` 的恢复策略是"建库失败 → 删库重建"，但本库除物料缓存/
 * 操作日志（可重建）外还有 `pending_operations`——工人已提交、尚未联网同步的
 * 离线单据，是**不可重建的业务数据**。此前删库直接把它一并抹掉且无日志、无告警，
 * 工人以为"已暂存、联网会自动传"的单据就此消失，事后无法对账。
 *
 * 修复：删库前用原生 SQLite 只读备份队列表（[AppDatabase.backupPendingOperations]），
 * 重建后经 `openHelper.writableDatabase` 原样回补（[AppDatabase.restorePendingOperations]）。
 * 本测试用真实 SQLite 文件（Robolectric）验证备份、回补与端到端重建保单的完整链路。
 *
 * 运行方式：`./gradlew testReleaseUnitTest`。
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [31], application = android.app.Application::class)
class PendingQueueRebuildProtectionTest {

    private lateinit var context: Context
    private lateinit var databaseDirectory: File

    /** 与 AppDatabase.DB_NAME 一致（private const，测试侧重复声明以保持可读）。 */
    private val dbName = "wms_database"

    @Before
    fun setUp() {
        // BUG-2026-10-08-014-F01: these tests close/reopen real files. Robolectric's
        // OFF/MEMORY defaults are for disposable in-process databases, not disk recovery.
        // Configure the initial open; do not switch journal_mode on an open connection.
        ShadowSQLiteConnection.setDefaultSyncMode("FULL")
        ShadowSQLiteConnection.setDefaultJournalMode("PERSIST")
        val application: Context = ApplicationProvider.getApplicationContext()
        // BUG-2026-10-08-014-F02: failed Room opens can outlive a test's singleton.
        // Never reuse their file paths in another test, even after unlinking files.
        databaseDirectory = Files.createTempDirectory("pending-queue-").toFile()
        context = object : ContextWrapper(application) {
            override fun getApplicationContext(): Context = this
            override fun getDatabasePath(name: String): File = File(databaseDirectory, name)
            override fun deleteDatabase(name: String): Boolean =
                super.deleteDatabase(getDatabasePath(name).absolutePath)

            override fun openOrCreateDatabase(
                name: String, mode: Int, factory: SQLiteDatabase.CursorFactory?
            ): SQLiteDatabase =
                super.openOrCreateDatabase(getDatabasePath(name).absolutePath, mode, factory)

            override fun openOrCreateDatabase(
                name: String, mode: Int, factory: SQLiteDatabase.CursorFactory?,
                errorHandler: DatabaseErrorHandler?
            ): SQLiteDatabase =
                super.openOrCreateDatabase(getDatabasePath(name).absolutePath, mode, factory, errorHandler)
        }
        purgeDatabase()
    }

    @After
    fun tearDown() {
        purgeDatabase()
        databaseDirectory.deleteRecursively()
    }

    // ---------------------------------------------------------------
    // 工具
    // ---------------------------------------------------------------

    /**
     * 彻底清理共享的 wms_database，修复本类在 CI 上的**顺序依赖偶发失败**（BUG-2026-09-22-001）。
     *
     * 本类 8 条用例共用同一磁盘库文件（同一 Robolectric 沙箱）。旧实现有两点缺陷：
     * ① setUp 只 resetSingleton()（把 INSTANCE 置空）却**不关闭仍打开的 Room 连接**；
     * ② 单靠 context.deleteDatabase()——Robolectric 的影子实现不像真机那样清干净
     *    WAL 模式的 -wal/-shm 侧车文件（真机 deleteDatabase 会一并删除）。
     * 任一点都会让后续用例的 backupPendingOperations 读到脏状态，断言随用例顺序漂移
     * （实证：run #691/#692/#695 每次挂的方法都不同；且是 BUG-2026-09-21-005 该类的
     * 第三次偶发复发，属 R6 同根因反复模式）。
     *
     * 修复：**先关连接再置空单例** + 显式删除主文件与 -wal/-shm/-journal 侧车，
     * 保证每条用例从真正干净的磁盘状态开始，与用例执行顺序无关。
     */
    private fun purgeDatabase() {
        closeSingletonInstance()
        resetSingleton()
        context.deleteDatabase(dbName)
        listOf("", "-wal", "-shm", "-journal").forEach { suffix ->
            context.getDatabasePath(dbName + suffix).delete()
        }
    }

    /** AppDatabase.INSTANCE 是 companion 的私有静态字段，测试间必须复位防串扰。 */
    private fun resetSingleton() {
        val field = AppDatabase::class.java.getDeclaredField("INSTANCE")
        field.isAccessible = true
        field.set(null, null)
    }

    private fun closeSingletonInstance() {
        val field = AppDatabase::class.java.getDeclaredField("INSTANCE")
        field.isAccessible = true
        (field.get(null) as? AppDatabase)?.close()
    }

    private fun sampleEntity(requestId: String) = PendingOperationEntity(
        requestId = requestId,
        operationType = PendingOperationEntity.TYPE_OUTBOUND,
        payloadJson = """{"warehouse_code":"WH01","lines":[]}""",
        warehouseCode = "WH01",
        summary = "出库 2 项 · 主仓",
        status = PendingOperationEntity.STATUS_PENDING,
        attemptCount = 1,
        lastError = "网络超时",
        createdAt = 1_700_000_000_000L,
        updatedAt = 1_700_000_100_000L
    )

    /** 用原生 SQLite 在标准路径种一个含 pending_operations 表与若干行的库文件。 */
    private fun plantRawDatabase(rows: List<PendingOperationEntity>, userVersion: Int = 1) {
        // 前序用例（getDatabase catch...）的 Room 实例可能仍持有连接。此处再 purge
        // 一次，确保任何残留连接与侧车文件在种数据前彻底清掉（CI 实测曾因此
        // 只读验证读到空）。
        purgeDatabase()
        val dbFile = context.getDatabasePath(dbName)
        dbFile.parentFile?.mkdirs()
        SQLiteDatabase.openOrCreateDatabase(dbFile, null).use { raw ->
            // BUG-2026-10-08-014 根治（本轮修正）：**不要在这里切 journal_mode 或
            // 做 wal_checkpoint**。
            //
            // purgeDatabase() 已把主文件连同 -wal/-shm/-journal 整个删掉，所以新建的
            // 文件默认就是 rollback journal 模式，根本不是 WAL——两条 PRAGMA 都是
            // 对不存在的问题出手。历史注释把它们当成"根治"，实测两条都是反效果：
            //
            //   * NATIVE 引擎：切换 journal_mode 会走进 walIndexAppend，正是
            //     BUG-2026-09-21-005 那次 SIGBUS（exit 134）的路径；
            //   * LEGACY 引擎：切换会留下未完成事务，紧接着的 openDatabase 在
            //     setLocaleFromConfiguration 提交时抛 SQLITE_BUSY（database is locked），
            //     表现为「rebuild preserving queue keeps pending rows」失败。
            //
            // 换言之这两个症状同源：**只要切 journal_mode，两种引擎各坏一处**。
            // 新建文件本就不是 WAL，删除后不产侧车，INSERT 直接落主文件，
            // 任何打开方式（含 OPEN_READONLY）都能读到——这才是与执行顺序无关的正解。
            raw.execSQL(
                "CREATE TABLE IF NOT EXISTS `pending_operations` (" +
                    "`request_id` TEXT NOT NULL, `operation_type` TEXT NOT NULL, " +
                    "`payload_json` TEXT NOT NULL, `warehouse_code` TEXT, " +
                    "`summary` TEXT NOT NULL, `status` TEXT NOT NULL, " +
                    "`attempt_count` INTEGER NOT NULL, `last_error` TEXT, " +
                    "`created_at` INTEGER NOT NULL, `updated_at` INTEGER NOT NULL, " +
                    "PRIMARY KEY(`request_id`))"
            )
            rows.forEach { row ->
                raw.execSQL(
                    "INSERT INTO pending_operations VALUES (?,?,?,?,?,?,?,?,?,?)",
                    arrayOf(
                        row.requestId, row.operationType, row.payloadJson, row.warehouseCode,
                        row.summary, row.status, row.attemptCount, row.lastError,
                        row.createdAt, row.updatedAt
                    )
                )
            }
            raw.version = userVersion
        }
        // 兜底：删干净侧车文件，保证后续 OPEN_READONLY 打开的是自洽主文件。
        // BUG-2026-10-08-014 第四次复发定位：Robolectric 影子 SQLite 的 WAL recovery
        // 依赖 -shm 索引；checkpoint(TRUNCATE) 清空 -wal 但 -shm 可能残留过期索引，
        // 只读打开时影子实现用旧索引映射主文件 → 读到空。必须连同 -shm 一起删，
        // 让任何打开方式都从主文件重建索引，彻底消除执行顺序漂移。
        listOf("-wal", "-shm", "-journal").forEach { suffix ->
            context.getDatabasePath(dbName + suffix).delete()
        }
    }

    // ---------------------------------------------------------------
    // backupPendingOperations
    // ---------------------------------------------------------------

    @Test
    fun `fixture context routes opens and deletes to its unique directory`() {
        val file = context.getDatabasePath(dbName)
        assertEquals(databaseDirectory, file.parentFile)
        assertTrue(context === context.applicationContext)
        context.openOrCreateDatabase(dbName, Context.MODE_PRIVATE, null).use { raw ->
            assertEquals(file.absolutePath, raw.path)
            raw.execSQL("CREATE TABLE fixture_marker (id INTEGER)")
        }
        assertTrue(file.isFile)
        assertTrue(context.deleteDatabase(dbName))
        assertTrue(!file.exists())
    }

    @Test
    fun `file fixture persists queue with durable sqlite defaults`() {
        plantRawDatabase(listOf(sampleEntity("req-durable")))
        SQLiteDatabase.openDatabase(
            context.getDatabasePath(dbName).absolutePath, null, SQLiteDatabase.OPEN_READWRITE
        ).use { raw ->
            raw.rawQuery("PRAGMA synchronous", null).use { cursor ->
                assertTrue(cursor.moveToFirst())
                assertEquals("File recovery fixtures require FULL synchronization", 2, cursor.getInt(0))
            }
            raw.rawQuery("PRAGMA journal_mode", null).use { cursor ->
                assertTrue(cursor.moveToFirst())
                assertEquals("File recovery fixtures require a persistent journal", "persist", cursor.getString(0))
            }
        }
        val rows = AppDatabase.backupPendingOperations(context)
        assertEquals(1, rows.size)
        assertEquals("req-durable", rows.single().requestId)
    }

    @Test
    fun `backup returns empty when db file does not exist`() {
        val rows = AppDatabase.backupPendingOperations(context)
        assertTrue("库文件不存在时备份必须返回空（全新安装场景）", rows.isEmpty())
    }

    @Test
    fun `backup reads pending rows from readable sqlite file`() {
        plantRawDatabase(listOf(sampleEntity("req-a"), sampleEntity("req-b")))

        val rows = AppDatabase.backupPendingOperations(context)

        assertEquals("可读库文件中的待同步单据必须全部备份出来", 2, rows.size)
        val a = rows.first { it.requestId == "req-a" }
        assertEquals(PendingOperationEntity.TYPE_OUTBOUND, a.operationType)
        assertEquals("WH01", a.warehouseCode)
        assertEquals(1, a.attemptCount)
        assertEquals("网络超时", a.lastError)
        assertEquals(1_700_000_000_000L, a.createdAt)
    }

    @Test
    fun `backup keeps nullable columns null`() {
        plantRawDatabase(listOf(sampleEntity("req-null").copy(warehouseCode = null, lastError = null)))

        val rows = AppDatabase.backupPendingOperations(context)

        assertEquals(1, rows.size)
        assertEquals("可空列必须原样保留为 null，不得变成字符串 \"null\"", null, rows[0].warehouseCode)
        assertEquals(null, rows[0].lastError)
    }

    @Test
    fun `backup returns empty when table is missing (v1 legacy db)`() {
        // v1 老库没有队列表：本就无单可丢，返回空而非报错
        val dbFile = context.getDatabasePath(dbName)
        dbFile.parentFile?.mkdirs()
        SQLiteDatabase.openOrCreateDatabase(dbFile, null).use { raw ->
            raw.execSQL("CREATE TABLE IF NOT EXISTS some_other_table (id INTEGER)")
        }

        val rows = AppDatabase.backupPendingOperations(context)
        assertTrue("无队列表的老库备份必须返回空", rows.isEmpty())
    }

    @Test
    fun `backup returns empty and does not throw on corrupted file`() {
        // 物理损坏：写一段非 SQLite 字节。数据本已不可读，备份失败不阻断恢复流程。
        val dbFile = context.getDatabasePath(dbName)
        dbFile.parentFile?.mkdirs()
        dbFile.writeBytes("this is not a sqlite database at all".toByteArray())

        val rows = AppDatabase.backupPendingOperations(context)
        assertTrue("损坏文件备份必须返回空且不得抛异常阻断启动", rows.isEmpty())
    }

    // ---------------------------------------------------------------
    // restorePendingOperations
    // ---------------------------------------------------------------

    @Test
    fun `restore writes backed up rows into fresh database`() = runBlocking {
        val db = Room.inMemoryDatabaseBuilder(context, AppDatabase::class.java)
            .allowMainThreadQueries()
            .build()
        try {
            val rows = listOf(sampleEntity("req-x"), sampleEntity("req-y"))

            AppDatabase.restorePendingOperations(db, rows)

            val restored = db.pendingOperationDao().listAll()
            assertEquals("回补后新库必须包含全部备份单据", 2, restored.size)
            val x = restored.first { it.requestId == "req-x" }
            assertEquals("WH01", x.warehouseCode)
            assertEquals("出库 2 项 · 主仓", x.summary)
            assertEquals(PendingOperationEntity.STATUS_PENDING, x.status)
        } finally {
            db.close()
        }
    }

    @Test
    fun `restore with empty list is a no-op and does not throw`() {
        val db = Room.inMemoryDatabaseBuilder(context, AppDatabase::class.java)
            .allowMainThreadQueries()
            .build()
        try {
            AppDatabase.restorePendingOperations(db, emptyList())
        } finally {
            db.close()
        }
    }

    // ---------------------------------------------------------------
    // 端到端：备份 → 删库 → 重建 → 回补，单据仍在
    //
    // 直接调用 rebuildPreservingQueue（getDatabase catch 分支的抽出实现），
    // 验证本仓库自己拥有的保单链路；不依赖"Room 对特定坏文件何时抛异常"
    // 的内部行为——该行为随 Android/Room 版本变化，属环境依赖、不可测。
    // ---------------------------------------------------------------

    private fun plantFullOldSchema(rows: List<PendingOperationEntity>, version: Int) {
        val template = Room.inMemoryDatabaseBuilder(context, AppDatabase::class.java)
            .allowMainThreadQueries().build()
        val definitions = try {
            template.openHelper.writableDatabase.query(
                "SELECT sql FROM sqlite_master WHERE type IN ('table','index') AND sql IS NOT NULL " +
                    "AND tbl_name NOT IN ('room_master_table','android_metadata','sqlite_sequence') " +
                    "AND name != 'pending_operations' ORDER BY CASE type WHEN 'table' THEN 0 ELSE 1 END"
            ).use { cursor -> buildList { while (cursor.moveToNext()) add(cursor.getString(0)) } }
        } finally { template.close() }
        plantRawDatabase(rows, version)
        SQLiteDatabase.openDatabase(context.getDatabasePath(dbName).absolutePath, null,
            SQLiteDatabase.OPEN_READWRITE).use { raw ->
            for (sql in definitions) raw.execSQL(sql)
            if (version == 1) raw.execSQL("DROP TABLE pending_operations")
        }
    }

    @Test
    fun `real v2 migration retains all original states and isolates every legacy row`() = runBlocking {
        val original = listOf("pending", "syncing", "failed").mapIndexed { i, status ->
            sampleEntity("legacy-$i").copy(status = status, attemptCount = i, lastError = "old-$i")
        }
        plantFullOldSchema(original, 2)
        val migrated = AppDatabase.getDatabase(context)
        assertEquals(3, migrated.openHelper.writableDatabase.version)
        assertEquals(original, migrated.pendingOperationDao().listAll())
        migrated.pendingOperationDao().resetStuckSyncing()
        assertEquals(original, migrated.pendingOperationDao().listAll())
        assertTrue(migrated.pendingOperationDao().listPending().isEmpty())
        assertEquals(3, migrated.pendingOperationDao().countFailed())
    }

    @Test
    fun `real v1 upgrade creates v3 queue without destructive migration`() = runBlocking {
        plantFullOldSchema(emptyList(), 1)
        val migrated = AppDatabase.getDatabase(context)
        assertEquals(3, migrated.openHelper.writableDatabase.version)
        assertTrue(migrated.pendingOperationDao().listAll().isEmpty())
    }

    @Test
    fun `open failure preserves original queue instead of rebuilding`() = runBlocking {
        val original = sampleEntity("req-survive")
        plantRawDatabase(listOf(original), userVersion = 2)
        // The intentionally incomplete v2 schema must fail Room validation.
        assertTrue(runCatching { AppDatabase.getDatabase(context) }.isFailure)
        val rows = AppDatabase.backupPendingOperations(context)
        assertEquals(listOf(original), rows)
        SQLiteDatabase.openDatabase(context.getDatabasePath(dbName).absolutePath, null,
            SQLiteDatabase.OPEN_READWRITE).use { raw ->
            assertEquals("failed migration must roll back its schema", 2, raw.version)
        }
    }

    @Test
    fun `corruption cannot delete or replace original file`() {
        val dbFile = context.getDatabasePath(dbName)
        dbFile.parentFile?.mkdirs()
        val original = "corrupted-not-a-sqlite-file".toByteArray()
        dbFile.writeBytes(original)
        assertTrue(runCatching { AppDatabase.getDatabase(context) }.isFailure)
        assertTrue(dbFile.isFile)
        org.junit.Assert.assertArrayEquals(original, dbFile.readBytes())
    }

    @Test
    fun `future schema downgrade failure preserves queue and version`() {
        val original = sampleEntity("req-future")
        plantRawDatabase(listOf(original), userVersion = 99)
        assertTrue(runCatching { AppDatabase.getDatabase(context) }.isFailure)
        assertEquals(listOf(original), AppDatabase.backupPendingOperations(context))
        SQLiteDatabase.openDatabase(context.getDatabasePath(dbName).absolutePath, null,
            SQLiteDatabase.OPEN_READWRITE).use { raw -> assertEquals(99, raw.version) }
    }

    @Test
    fun `diagnostic backup and restore retain ownership review and retry metadata`() = runBlocking {
        val original = sampleEntity("req-owned").copy(ownerServer = "https://synthetic.example.invalid",
            ownerUserId = 11, needsReview = false, nextRetryAt = 123456789L)
        val disk = Room.databaseBuilder(context, AppDatabase::class.java, dbName)
            .allowMainThreadQueries().build()
        try { disk.pendingOperationDao().upsert(original) } finally { disk.close() }
        val rows = AppDatabase.backupPendingOperations(context)
        assertEquals(listOf(original), rows)
        val memory = Room.inMemoryDatabaseBuilder(context, AppDatabase::class.java)
            .allowMainThreadQueries().build()
        try {
            AppDatabase.restorePendingOperations(memory, rows)
            assertEquals(listOf(original), memory.pendingOperationDao().listAll())
        } finally { memory.close() }
    }
}
