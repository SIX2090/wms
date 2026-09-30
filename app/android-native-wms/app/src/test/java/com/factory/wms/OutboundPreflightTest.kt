package com.factory.wms

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import com.factory.wms.data.model.OutboundRequest
import com.factory.wms.data.model.ScanLine
import com.factory.wms.data.repository.WmsRepository
import com.factory.wms.data.api.RetrofitClient
import kotlinx.coroutines.runBlocking
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/**
 * BUG-2026-09-13-019：出库**提交前预检**（preflight）的真实可执行测试。
 *
 * ## 为什么需要它（M2' 替代 2：无真机的 Robolectric 补强）
 *
 * 台账登记的缺陷：Android 出库提交前按**全局**库存逐行预检、未累计同物料多行需求
 * ——三行 M001 各领 4 个（全局有 10 个）逐行都过、合计 12 个超发。
 *
 * 修复契约（源码已接入，真机验收待完成）：
 * 1. submitOutbound（首次提交）先打 `POST /api/outbound/preflight`（服务端按
 *    **仓库级累计需求**校验），预检过了才打 `POST /api/outbound` 真正提交；
 * 2. 预检**业务拒绝**（如「库存不足」）：失败原因原样返回 UI，**绝不入离线队列**
 *    ——业务上确定失败的请求入队 = 谎报"已暂存"，补传永远不可能成功；
 * 3. 幂等回放（replay=true，提交中断后核实原请求）**跳过预检**：核实是只读回放，
 *    此时库存可能已被上次成功的扣减改变，重复预检会误拦已生效的请求
 *    （BUG-2026-09-13-020 的提交中断幂等键配套契约）。
 *
 * 本文件用 MockWebServer 挂在真实 Retrofit 链路上验证请求**顺序、次数、幂等头**
 * 与失败分流——Python 源码字符串匹配测不出"预检拒绝真的没入队"这种运行时行为。
 *
 * 运行方式：`./gradlew testReleaseUnitTest`。
 *
 * 诚实边界（AGENTS.md R8）：本测试证明 JVM 级请求编排正确，**不能替代真机验收**
 * （弱网下的实际超时表现、相机扫码页的提示可见性）。BUG-2026-09-13-019
 * 台账状态保持「待真机验收」。
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [31])
class OutboundPreflightTest {

    private lateinit var server: MockWebServer
    private lateinit var context: Context
    private lateinit var repository: WmsRepository

    @Before
    fun setUp() {
        context = ApplicationProvider.getApplicationContext()
        println("[DBG-P1] OutboundTest: setUp 开始") // 诊断探针（BUG-2026-10-01-001）
        server = MockWebServer()
        server.start()
        println("[DBG-P2] MockWebServer 已启动") // 诊断探针
        repository = WmsRepository(context)
        println("[DBG-P3] WmsRepository 构造完成") // 诊断探针
        // 把真实 Retrofit 链路指向本地 MockWebServer（authInterceptor 原样经过）
        RetrofitClient.setBaseUrl(server.url("/").toString())
        RetrofitClient.setToken("token-for-test")
    }

    @After
    fun tearDown() {
        RetrofitClient.setToken(null)
        RetrofitClient.setBaseUrl("")
        server.shutdown()
    }

    // ---------------------------------------------------------------
    // 工具
    // ---------------------------------------------------------------

    private fun request() = OutboundRequest(
        lines = listOf(
            ScanLine(material_code = "M001", quantity = 4.0),
            ScanLine(material_code = "M001", quantity = 4.0) // 同物料两行，合计 8 > 可用 2
        ),
        warehouseCode = "WH01"
    )

    private fun ok(body: String) = MockResponse()
        .setResponseCode(200)
        .setHeader("Content-Type", "application/json")
        .setBody(body)

    // ---------------------------------------------------------------
    // 契约 1：首次提交 = 预检 → 提交，两连击且顺序固定
    // ---------------------------------------------------------------

    @Test
    fun `first outbound submit calls preflight then submit in order with idempotency key`() = runBlocking {
        println("[DBG-P4] 契约1: submitOutbound 调用前") // 诊断探针（BUG-2026-10-01-001）
        server.enqueue(ok("""{"status":"success","data":{"warehouse_code":"WH01"}}"""))
        server.enqueue(ok("""{"status":"success","data":{"id":7,"order_no":"OUT-7","check_no":null}}"""))

        val result = repository.submitOutbound(request(), requestId = "idem-1")
        println("[DBG-P5] 契约1: submitOutbound 返回") // 诊断探针

        assertTrue(result.isSuccess)
        assertEquals("OUT-7", result.getOrNull()!!.order_no)

        assertEquals(2, server.requestCount)
        val preflight = server.takeRequest()
        val submit = server.takeRequest()
        assertEquals("/api/outbound/preflight", preflight.path)
        assertEquals("/api/outbound", submit.path)
        // 幂等键必须随提交请求透传（后端 mobile_api_idempotent 依据）
        assertEquals("idem-1", submit.getHeader("X-Idempotency-Key"))
    }

    // ---------------------------------------------------------------
    // 契约 2：预检业务拒绝 → 原样返回原因，不入离线队列，不发提交
    // ---------------------------------------------------------------

    @Test
    fun `preflight business rejection returns server reason without enqueuing offline`() = runBlocking {
        server.enqueue(ok(
            """{"status":"error","msg":"库存不足：M001 本仓可用 2，本次累计 8"}"""
        ))

        val pendingBefore = repository.offlineQueue?.pendingCount?.value ?: 0
        val result = repository.submitOutbound(request(), requestId = "idem-2")

        assertTrue(result.isFailure)
        val ex = result.exceptionOrNull()
        assertTrue("预期 BusinessException，实际 ${ex?.javaClass}", ex is WmsRepository.Companion.BusinessException)
        assertEquals("库存不足：M001 本仓可用 2，本次累计 8", ex!!.message)

        // 只发了预检这一个请求，真正的提交从未发出
        assertEquals(1, server.requestCount)
        assertEquals("/api/outbound/preflight", server.takeRequest().path)

        // 离线队列计数不变：业务拒绝绝不能伪装成"已暂存"
        assertEquals(pendingBefore, repository.offlineQueue?.pendingCount?.value ?: 0)
    }

    // ---------------------------------------------------------------
    // 契约 3：幂等回放跳过预检（提交中断核实不重复执行只读预检）
    // ---------------------------------------------------------------

    @Test
    fun `replay submit skips preflight and goes straight to submit endpoint`() = runBlocking {
        server.enqueue(ok("""{"status":"success","data":{"id":8,"order_no":"OUT-8","check_no":null}}"""))

        val result = repository.submitOutbound(request(), requestId = "idem-3", replay = true)

        assertTrue(result.isSuccess)
        assertEquals("OUT-8", result.getOrNull()!!.order_no)

        // 只有提交请求；预检一次都没打
        assertEquals(1, server.requestCount)
        val submit = server.takeRequest()
        assertEquals("/api/outbound", submit.path)
        // 回放必须复用原幂等键
        assertEquals("idem-3", submit.getHeader("X-Idempotency-Key"))
    }
}
