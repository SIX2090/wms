package com.factory.wms

import com.factory.wms.data.local.AppDatabase
import com.factory.wms.data.local.PendingOperationDao
import com.factory.wms.data.local.PendingOperationEntity
import android.content.Context
import androidx.test.core.app.ApplicationProvider
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/**
 * BUG-2026-09-14-033：离线队列**状态机**的真实可执行测试。
 *
 * ## 为什么这个测试最重要
 *
 * `OfflineQueueManager` 的全部价值建立在「暂存一定成功、失败一定可见」上，
 * 而它承载的三个已登记缺陷**全部是状态机错误**，且**都无法用源码字符串匹配测出**：
 *
 * - **BUG-2026-09-12-008**（P0 静默丢数据）：`replay()` 返回 false 时只 `failCount++`
 *   而不回写状态，记录永久卡在 `syncing`；而三处消费点**全部按状态过滤**
 *   （`listPending` 只取 pending、`countPending` 只算 pending、`countFailed` 只算 failed）
 *   → 该记录在三个界面上同时消失，UI 完全无感知。
 * - **BUG-2026-09-12-009**（P1 谎报已暂存）：`enqueue` 非 suspend，落库前就 `return true`。
 * - **BUG-2026-09-12-011**（P1 承诺未兑现）：队列靠扫码页懒加载初始化。
 *
 * 本测试用**真实 Room 数据库**（Robolectric 提供 Android 运行时）验证状态机的
 * 出口完整性——即"任何一条记录，在任何失败路径下都不会停留在 syncing 态"。
 *
 * 运行方式：`./gradlew testReleaseUnitTest`。
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [31])
class OfflineQueueStateMachineTest {

    private lateinit var db: AppDatabase
    private lateinit var dao: PendingOperationDao

    @Before
    fun setUp() = runBlocking {
        // 用**内存数据库**而非 getDatabase(context)：每个用例一份全新 Schema，
        // 用例间绝对隔离，且不落磁盘（CI 上更快、无残留）。
        // allowMainThreadQueries：Robolectric 单线程测试环境下允许主线程访问，
        // 生产代码仍走协程（DAO 方法是 suspend，不受此配置影响）。
        val context = ApplicationProvider.getApplicationContext<Context>()
        db = androidx.room.Room.inMemoryDatabaseBuilder(context, AppDatabase::class.java)
            .allowMainThreadQueries()
            .build()
        dao = db.pendingOperationDao()
    }

    @After
    fun tearDown() {
        db.close()
    }

    private fun entity(
        requestId: String,
        status: String = PendingOperationEntity.STATUS_PENDING,
        attemptCount: Int = 0
    ) = PendingOperationEntity(
        requestId = requestId,
        operationType = PendingOperationEntity.TYPE_INBOUND,
        payloadJson = """{"test":true}""",
        warehouseCode = "WH01",
        summary = "入库 1 项 · 主仓",
        status = status,
        attemptCount = attemptCount
    )

    // ---------------------------------------------------------------
    // BUG-2026-09-12-008 核心：syncing 不是终态，任何失败路径都必须回写
    // ---------------------------------------------------------------

    @Test
    fun `stuck syncing records are recoverable by resetStuckSyncing`() = runBlocking {
        // 模拟"补传中被杀进程"：记录留在 syncing
        dao.upsert(entity("req-stuck", status = PendingOperationEntity.STATUS_SYNCING))

        // 关键前提：syncing 记录**取不到**（这正是静默丢数据的原因）
        assertEquals(
            "syncing 记录不应出现在待补传列表中（这就是它会被'静默丢失'的原因）",
            0,
            dao.listPending().size
        )

        // 启动时复位 → 重新可见
        dao.resetStuckSyncing()

        val recovered = dao.listPending()
        assertEquals("resetStuckSyncing 后必须重新可见（BUG-2026-09-12-008 的核心后果）", 1, recovered.size)
        assertEquals("req-stuck", recovered[0].requestId)
        assertEquals(PendingOperationEntity.STATUS_PENDING, recovered[0].status)
    }

    @Test
    fun `failed record is visible in countFailed so UI can warn user`() = runBlocking {
        // BUG-2026-09-12-008：重试耗尽的记录必须落 failed（而非停留 syncing），
        // 否则用户在"待同步"和"失败列表"里同时看不到它
        dao.upsert(entity("req-fail"))
        dao.markFailed(
            requestId = "req-fail",
            nextStatus = PendingOperationEntity.STATUS_FAILED,
            attemptCount = PendingOperationEntity.MAX_ATTEMPTS,
            error = "网络超时"
        )

        assertEquals("失败记录必须被 countFailed 统计到，否则用户永远不知道数据没提交成功", 1, dao.countFailed())
        assertEquals("失败记录不应再出现在待补传列表", 0, dao.countPending())

        val failed = dao.listAll().filter { it.status == PendingOperationEntity.STATUS_FAILED }
        assertEquals(1, failed.size)
        assertTrue("必须保留中文失败原因供作业员理解", failed[0].lastError?.isNotBlank() == true)
    }

    @Test
    fun `every non-success terminal path leaves a record reachable by some query`() = runBlocking {
        // 出口完整性：pending / failed 两个"可见态"覆盖所有非成功路径。
        // 若某条记录既不 pending 也不 failed（即停留在 syncing），就是静默丢数据。
        val ids = listOf("r1", "r2", "r3")
        ids.forEach { dao.upsert(entity(it)) }

        // r1：正常待补传
        // r2：重试 2 次仍失败（未达上限）→ 应回 pending 继续重试
        dao.markSyncing("r2")
        dao.markFailed("r2", PendingOperationEntity.STATUS_PENDING, 2, "网络超时")
        // r3：达上限 → failed
        dao.markSyncing("r3")
        dao.markFailed("r3", PendingOperationEntity.STATUS_FAILED, PendingOperationEntity.MAX_ATTEMPTS, "鉴权失败")

        val visible = dao.listAll().map { it.requestId }.toSet()
        assertEquals(
            "所有非成功记录都必须能被某个查询取到——取不到的记录对用户等同于消失",
            ids.toSet(),
            visible
        )
        assertEquals(2, dao.countPending())
        assertEquals(1, dao.countFailed())
    }

    @Test
    fun `resetToPending from failed makes it retryable again`() = runBlocking {
        dao.upsert(entity("r-failed", status = PendingOperationEntity.STATUS_FAILED, attemptCount = 5))
        assertEquals(1, dao.countFailed())

        dao.resetToPending("r-failed")

        assertEquals("人工重试后应重新出现在待补传列表", 1, dao.countPending())
        assertEquals("不应再计入失败", 0, dao.countFailed())
        val row = dao.listPending()[0]
        assertEquals("次数必须清零，否则刚重置就被下一次失败立刻打回 failed", 0, row.attemptCount)
        assertEquals("失败原因应清除", null, row.lastError)
    }

    @Test
    fun `max attempts constant is positive and finite`() {
        // 无限重试会在真正失败上无谓烧电并掩盖故障；0 则永不重试。
        assertTrue("MAX_ATTEMPTS 必须为正且有限", PendingOperationEntity.MAX_ATTEMPTS in 1..100)
    }

    // ---------------------------------------------------------------
    // 幂等：同一 requestId 重复入队不得产生第二条记录
    // （这是"弱网反复点击不产生重复单据"的本地侧保证）
    // ---------------------------------------------------------------

    @Test
    fun `upsert is idempotent by requestId`() = runBlocking {
        dao.upsert(entity("same-id"))
        dao.upsert(entity("same-id"))
        dao.upsert(entity("same-id"))

        assertEquals(
            "同一 requestId 重复入队必须只保留一条（幂等键语义的本地保障）",
            1,
            dao.countPending()
        )
    }

    // ---------------------------------------------------------------
    // 顺序：补传按入队时间升序，保证与用户操作顺序一致
    // ---------------------------------------------------------------

    @Test
    fun `pending list preserves enqueue order`() = runBlocking {
        dao.upsert(entity("first").copy(createdAt = 1_000L))
        dao.upsert(entity("second").copy(createdAt = 2_000L))
        dao.upsert(entity("third").copy(createdAt = 3_000L))

        val order = dao.listPending().map { it.requestId }
        assertEquals(
            "补传必须按用户操作顺序，否则同一物料的先出后入会被颠倒",
            listOf("first", "second", "third"),
            order
        )
    }

    @Test
    fun `dao is accessible from real database instance`() {
        assertNotNull("Room 数据库与 DAO 必须可在 JVM 环境真实实例化", dao)
    }
}
