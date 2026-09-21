package com.factory.wms

import android.content.Context
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
@Config(sdk = [31])
class PendingQueueRebuildProtectionTest {

    private lateinit var context: Context

    /** 与 AppDatabase.DB_NAME 一致（private const，测试侧重复声明以保持可读）。 */
    private val dbName = "wms_database"

    @Before
    fun setUp() {
        context = ApplicationProvider.getApplicationContext()
        resetSingleton()
        context.deleteDatabase(dbName)
    }

    @After
    fun tearDown() {
        closeSingletonInstance()
        resetSingleton()
        context.deleteDatabase(dbName)
    }

    // ---------------------------------------------------------------
    // 工具
    // ---------------------------------------------------------------

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
        val dbFile = context.getDatabasePath(dbName)
        dbFile.parentFile?.mkdirs()
        SQLiteDatabase.openOrCreateDatabase(dbFile, null).use { raw ->
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
    }

    // ---------------------------------------------------------------
    // backupPendingOperations
    // ---------------------------------------------------------------

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
    // 端到端：Room 打不开（identity hash 校验失败）→ 删库重建 → 单据仍在
    // ---------------------------------------------------------------

    @Test
    fun `getDatabase rebuild preserves pending queue on identity hash mismatch`() = runBlocking {
        // 种一个"可读但 Room 拒绝打开"的库：user_version 与当前版本一致，
        // 但没有 room_master_table——Room 的 identity hash 校验必然失败，
        // 而原生 SQLite 仍能读出队列表。这是删库重建分支最典型的真实触发场景。
        plantRawDatabase(listOf(sampleEntity("req-survive")), userVersion = 2)

        val db = AppDatabase.getDatabase(context)

        val rows = db.pendingOperationDao().listAll()
        assertEquals(
            "删库重建后离线待同步单据必须仍在（本 BUG 的核心回归）",
            1,
            rows.size
        )
        assertEquals("req-survive", rows[0].requestId)
        assertEquals("WH01", rows[0].warehouseCode)
        assertEquals("出库 2 项 · 主仓", rows[0].summary)
    }
}
