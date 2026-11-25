package com.factory.wms

import android.app.Application
import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.os.Looper
import androidx.test.core.app.ApplicationProvider
import com.factory.wms.data.api.RetrofitClient
import com.factory.wms.data.model.CrashReportRequest
import com.factory.wms.data.model.DailyReportData
import com.factory.wms.data.repository.WmsRepository
import com.factory.wms.ui.screens.resolveImageUrl
import com.factory.wms.ui.viewmodel.stocktake.StocktakeRecordViewModel
import com.factory.wms.ui.viewmodel.voice.SherpaVoiceSttEngine
import com.factory.wms.ui.viewmodel.voice.SttConfig
import com.factory.wms.ui.viewmodel.voice.SttError
import com.factory.wms.ui.viewmodel.voice.VoiceSttListener
import com.factory.wms.util.CrashReporter
import com.factory.wms.util.NetworkMonitor
import com.google.gson.Gson
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.runBlocking
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertSame
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.Shadows
import org.robolectric.annotation.Config
import org.robolectric.shadows.ShadowNetworkCapabilities
import java.io.File

/**
 * 审计报告第二批（B-02 / B-03 / P-06 / A-10）运行时回归与覆盖测试：
 * - A-10.1: StocktakeRecordViewModel 首屏/翻页/作废切换/错误分级/详情下钻/会话隔离；
 * - A-10.2: CrashReporter 落盘、截断、20条淘汰与 MockWebServer 上传/坏文件清理；
 * - A-10.3: NetworkMonitor 无网/假在线(缺 VALIDATED)/真在线判定与单例复用；
 * - B-02: WmsRepository.getLocationOptions 多页合并去重、默认库位保留与空页中止；
 * - B-03: DailyReportData 反序列化 warehouse_id 与 all_warehouses。
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [31], application = Application::class)
class AuditBatch2FixesAndCoverageTest {

    @get:Rule(order = Int.MIN_VALUE)
    val settingsRule = WmsSettingsDataStoreRule()

    private val app: Application get() = ApplicationProvider.getApplicationContext()
    private lateinit var server: MockWebServer

    @Before
    fun setUp() {
        server = MockWebServer()
        server.start()
        RetrofitClient.setSession(server.url("/").toString(), "test-token", 101)
        File(app.filesDir, "crash").deleteRecursively()
    }

    @After
    fun tearDown() {
        File(app.filesDir, "crash").deleteRecursively()
        server.shutdown()
    }

    private fun awaitCondition(timeoutMs: Long = 3000L, predicate: () -> Boolean) {
        val deadline = System.currentTimeMillis() + timeoutMs
        while (System.currentTimeMillis() < deadline) {
            Shadows.shadowOf(Looper.getMainLooper()).idle()
            if (predicate()) return
            Thread.sleep(20)
        }
        Shadows.shadowOf(Looper.getMainLooper()).idle()
        assertTrue("Condition timed out after ${timeoutMs}ms", predicate())
    }

    // ── A-10.1: StocktakeRecordViewModel ──

    @Test
    fun stocktakeRecordViewModelLoadsPaginatesTogglesVoidedAndDrillsDetail() {
        // 第 1 页（completed）
        server.enqueue(
            MockResponse().setBody(
                """{"status":"success","data":{"items":[{"id":11,"check_no":"SC-011","warehouse":"一号仓","status":"completed","item_count":3,"diff_count":1}],"total":2,"page":1,"page_size":1,"total_pages":2}}"""
            )
        )
        // 第 2 页（completed）
        server.enqueue(
            MockResponse().setBody(
                """{"status":"success","data":{"items":[{"id":12,"check_no":"SC-012","warehouse":"一号仓","status":"completed","item_count":2,"diff_count":0}],"total":2,"page":2,"page_size":1,"total_pages":2}}"""
            )
        )
        // 详情下钻（id=11）
        server.enqueue(
            MockResponse().setBody(
                """{"status":"success","data":{"id":11,"check_no":"SC-011","warehouse":"一号仓","status":"completed","items":[{"material_code":"M-001","material_name":"轴承","spec":"6204","unit":"套"}]}}"""
            )
        )
        // 切换已作废（status=void）
        server.enqueue(
            MockResponse().setBody(
                """{"status":"success","data":{"items":[{"id":99,"check_no":"SC-099","warehouse":"一号仓","status":"void","item_count":1,"diff_count":0}],"total":1,"page":1,"page_size":20,"total_pages":1}}"""
            )
        )

        val vm = StocktakeRecordViewModel(app)
        try {
            vm.load()
            awaitCondition { !vm.uiState.value.isLoading && vm.uiState.value.records.size == 1 }
            assertEquals("SC-011", vm.uiState.value.records[0].checkNo)
            assertTrue(vm.uiState.value.hasMore)

            vm.loadMore()
            awaitCondition { !vm.uiState.value.isLoading && vm.uiState.value.records.size == 2 }
            assertEquals(listOf(11L, 12L), vm.uiState.value.records.map { it.id })
            assertFalse(vm.uiState.value.hasMore)

            vm.loadDetail(11L)
            awaitCondition { !vm.uiState.value.detailLoading && vm.uiState.value.detail != null }
            assertEquals("SC-011", vm.uiState.value.detail?.checkNo)
            assertEquals("M-001", vm.uiState.value.detail?.items?.single()?.materialCode)
            vm.clearDetail()
            assertNull(vm.uiState.value.detail)
            assertNull(vm.uiState.value.detailTargetId)

            vm.toggleVoided()
            awaitCondition { !vm.uiState.value.isLoading && vm.uiState.value.records.singleOrNull()?.id == 99L }
            assertTrue(vm.uiState.value.showVoided)

            // 验证实际请求参数包含 status=completed 与 status=void
            val r1 = server.takeRequest()
            val r2 = server.takeRequest()
            val r3 = server.takeRequest()
            val r4 = server.takeRequest()
            assertTrue(r1.path!!.contains("status=completed") && r1.path!!.contains("page=1"))
            assertTrue(r2.path!!.contains("page=2"))
            assertTrue(r3.path!!.contains("id=11"))
            assertTrue(r4.path!!.contains("status=void"))
        } finally {
            closeWmsTestViewModels(listOf(vm))
        }
    }

    @Test
    fun stocktakeRecordViewModelSeparatesInitialLoadErrorFromPaginationError() {
        // 首屏失败 → loadError 非空
        server.enqueue(MockResponse().setResponseCode(500).setBody("""{"status":"error","msg":"服务异常"}"""))
        // 重试首屏成功（2 页）
        server.enqueue(
            MockResponse().setBody(
                """{"status":"success","data":{"items":[{"id":21,"check_no":"SC-021"}],"total":2,"page":1,"page_size":1,"total_pages":2}}"""
            )
        )
        // 翻页失败 → error 非空，但保留已加载列表且不置 loadError
        server.enqueue(MockResponse().setResponseCode(500).setBody("""{"status":"error","msg":"翻页超时"}"""))

        val vm = StocktakeRecordViewModel(app)
        try {
            vm.load()
            awaitCondition { !vm.uiState.value.isLoading && vm.uiState.value.loadError != null }
            assertTrue(vm.uiState.value.records.isEmpty())

            vm.load()
            awaitCondition { !vm.uiState.value.isLoading && vm.uiState.value.records.size == 1 }
            assertNull(vm.uiState.value.loadError)

            vm.loadMore()
            awaitCondition { !vm.uiState.value.isLoading && vm.uiState.value.error != null }
            assertEquals(1, vm.uiState.value.records.size)
            assertNull(vm.uiState.value.loadError)
            vm.clearError()
            assertNull(vm.uiState.value.error)
        } finally {
            closeWmsTestViewModels(listOf(vm))
        }
    }

    // ── A-10.2: CrashReporter ──

    @Test
    fun crashReporterWritesTruncatedJsonPrunesOldFilesAndUploadsValidReports() {
        val crashDir = File(app.filesDir, "crash")
        val hugeMessage = "X".repeat(25_000)
        CrashReporter.writePendingReport(app, Thread.currentThread(), IllegalStateException(hugeMessage))

        val firstFile = crashDir.listFiles()?.single { it.name.startsWith("pending_") }
        assertNotNull(firstFile)
        val parsed = Gson().fromJson(firstFile!!.readText(), CrashReportRequest::class.java)
        assertTrue("exception 应截断至 <= 300 字符", parsed.exception.length <= 300)
        assertTrue("stacktrace 应截断至 <= 20000 字符", parsed.stacktrace.length <= 20_000)

        // 写入超过 20 个待上报文件并触发一次 writePendingReport，确认总数被裁剪到 <= 20
        crashDir.mkdirs()
        for (i in 1..23) {
            File(crashDir, "pending_old_$i.json").apply {
                writeText("{}")
                setLastModified(1000L + i * 10L)
            }
        }
        CrashReporter.writePendingReport(app, Thread.currentThread(), RuntimeException("latest"))
        val remaining = crashDir.listFiles()?.filter { it.name.startsWith("pending_") }.orEmpty()
        assertTrue("待上报文件上限应为 20，实际 ${remaining.size}", remaining.size <= 20)

        // 清理后测试损坏 JSON 清理 + 正常上报成功删除
        crashDir.deleteRecursively()
        crashDir.mkdirs()
        val broken = File(crashDir, "pending_1_broken.json").apply {
            writeText("{not-json")
            setLastModified(1000L)
        }
        val valid = File(crashDir, "pending_2_valid.json").apply {
            writeText(Gson().toJson(parsed))
            setLastModified(2000L)
        }
        setNetworkState(hasInternet = true, validated = true)
        server.enqueue(MockResponse().setBody("""{"status":"success","msg":"ok"}"""))

        val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
        try {
            CrashReporter.uploadPendingAsync(app, scope)
            awaitCondition { !broken.exists() && !valid.exists() }
            assertEquals(1, server.requestCount)
        } finally {
            scope.cancel()
        }
    }

    // ── A-10.3: NetworkMonitor ──

    @Test
    fun networkMonitorRequiresBothInternetAndValidatedAndSharesSingleton() {
        val m1 = NetworkMonitor.getInstance(app)
        val m2 = NetworkMonitor.getInstance(app)
        assertSame(m1, m2)

        // 仅连上内网 WiFi（有 INTERNET 但无 VALIDATED）必须判离线，防假在线丢单
        setNetworkState(hasInternet = true, validated = false)
        assertFalse("缺少 VALIDATED 时必须判离线", m1.currentlyOnline())

        // INTERNET + VALIDATED 同时满足才算在线
        setNetworkState(hasInternet = true, validated = true)
        assertTrue("同时具备 INTERNET 与 VALIDATED 应判在线", m1.currentlyOnline())

        // 无网络判离线
        setNetworkState(hasInternet = false, validated = false)
        assertFalse("无 INTERNET 能力应判离线", m1.currentlyOnline())
    }

    // ── B-02 & B-03: 库位分页加固 + 每日报表模型字段 ──

    @Test
    fun getLocationOptionsMergesAllPagesDeduplicatesAndPreservesFirstDefaultLocation() = runBlocking {
        server.enqueue(
            MockResponse().setBody(
                """{"status":"success","data":{"enabled":true,"items":["A-01","A-02"],"default_location":"A-01","total":3,"page":1,"page_size":2,"total_pages":2}}"""
            )
        )
        server.enqueue(
            MockResponse().setBody(
                """{"status":"success","data":{"enabled":true,"items":["A-02","A-03"],"default_location":null,"total":3,"page":2,"page_size":2,"total_pages":2}}"""
            )
        )

        val repo = WmsRepository(app)
        val result = repo.getLocationOptions("WH1").getOrThrow()
        assertEquals(true, result.enabled)
        assertEquals(listOf("A-01", "A-02", "A-03"), result.items)
        assertEquals("A-01", result.defaultLocation)
        assertEquals(3, result.total)
        assertEquals(2, server.requestCount)
    }

    @Test
    fun getLocationOptionsFetchesAllPagesBeyondFiftyWithoutSilentTruncation() = runBlocking {
        // 实证：后端合法返回超过 50 页（52 页）时，客户端必须完整拉取全部 52 页，不截断、不漏尾部库位。
        val totalPages = 52
        for (page in 1..totalPages) {
            val defaultLoc = if (page == 1) """"L-001"""" else "null"
            val loc = "L-%03d".format(page)
            server.enqueue(
                MockResponse().setBody(
                    """{"status":"success","data":{"enabled":true,"items":["$loc"],"default_location":$defaultLoc,"total":$totalPages,"page":$page,"page_size":1,"total_pages":$totalPages}}"""
                )
            )
        }

        val repo = WmsRepository(app)
        val result = repo.getLocationOptions("WH1").getOrThrow()
        assertEquals(totalPages, server.requestCount)
        assertEquals(totalPages, result.items!!.size)
        assertEquals("L-001", result.items!!.first())
        assertEquals("L-051", result.items!![50])
        assertEquals("L-052", result.items!!.last())
        assertEquals("L-001", result.defaultLocation)
    }

    @Test
    fun getLocationOptionsFailsExplicitlyWhenPageCountGrowsMidFetch() = runBlocking {
        // 实证：拉取中途总页数增长无法保证快照完整时，必须显式失败而非返回不完整列表。
        server.enqueue(
            MockResponse().setBody(
                """{"status":"success","data":{"enabled":true,"items":["A-01"],"default_location":null,"total":2,"page":1,"page_size":1,"total_pages":2}}"""
            )
        )
        server.enqueue(
            MockResponse().setBody(
                """{"status":"success","data":{"enabled":true,"items":["A-02"],"default_location":null,"total":3,"page":2,"page_size":1,"total_pages":3}}"""
            )
        )

        val repo = WmsRepository(app)
        val result = repo.getLocationOptions("WH1")
        assertTrue("总页数中途增大应显式失败，不得将不完整列表当作成功返回", result.isFailure)
    }

    @Test
    fun dailyReportDataParsesWarehouseIdAndAllWarehousesFields() {
        val json = """
            {
              "date": "2026-11-24",
              "type": "purchase_in",
              "type_label": "采购入库",
              "summary": {"orders": 1, "items": 2, "total_qty": 10.0, "total_amount": 50.0},
              "items": [],
              "total": 0,
              "page": 1,
              "page_size": 20,
              "total_pages": 0,
              "warehouse": "一号仓",
              "warehouse_id": 7,
              "all_warehouses": false
            }
        """.trimIndent()
        val data = Gson().fromJson(json, DailyReportData::class.java)
        assertEquals(7, data.warehouseId)
        assertEquals(false, data.allWarehouses)
    }

    // ── S-06 & P-07: 图片 URL 协议收紧 + Sherpa 缺失模型非阻塞降级 ──

    @Test
    fun resolveImageUrlAllowsHttpsSameOriginAndRelativeButRejectsForeignHttpAndOtherSchemes() {
        val base = "http://192.168.1.10:8080"
        assertEquals("http://192.168.1.10:8080/static/uploads/a.jpg", resolveImageUrl("/static/uploads/a.jpg", base))
        assertEquals("http://192.168.1.10:8080/static/uploads/a.jpg", resolveImageUrl("static/uploads/a.jpg", base))
        assertEquals("https://cdn.example.com/a.jpg", resolveImageUrl("https://cdn.example.com/a.jpg", base))
        assertEquals("http://192.168.1.10:8080/img.png", resolveImageUrl("http://192.168.1.10:8080/img.png", base))
        assertEquals("", resolveImageUrl("http://evil.example.com/steal.png", base))
        assertEquals("", resolveImageUrl("file:///etc/passwd", base))
        assertEquals("", resolveImageUrl("javascript:alert(1)", base))
    }

    @Test
    fun sherpaEngineMissingModelDegradesSafelyWithoutNpeOrBlocking() {
        val emptyDir = File(app.cacheDir, "empty-sherpa-model").apply { mkdirs() }
        val engine = SherpaVoiceSttEngine(app, modelDirOverride = emptyDir)
        var reportedError: SttError? = null
        engine.setListener(object : VoiceSttListener {
            override fun onPartial(text: String) {}
            override fun onResult(texts: List<String>) {}
            override fun onError(error: SttError, detail: String?) { reportedError = error }
        })
        assertFalse(engine.isAvailable())
        engine.start(SttConfig())
        assertEquals(SttError.EngineUnavailable, reportedError)
        engine.destroy()
    }

    private fun setNetworkState(hasInternet: Boolean, validated: Boolean) {
        val cm = app.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        val shadowCm = Shadows.shadowOf(cm)
        val caps = ShadowNetworkCapabilities.newInstance()
        val shadowCaps = Shadows.shadowOf(caps)
        if (hasInternet) shadowCaps.addCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
        if (validated) shadowCaps.addCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED)
        shadowCm.setNetworkCapabilities(cm.activeNetwork, caps)
    }
}
