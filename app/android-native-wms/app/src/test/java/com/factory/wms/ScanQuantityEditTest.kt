package com.factory.wms

import android.app.Application
import androidx.test.core.app.ApplicationProvider
import com.factory.wms.data.api.RetrofitClient
import com.factory.wms.data.model.*
import com.factory.wms.data.repository.WmsRepository
import com.factory.wms.ui.viewmodel.scan.ScanUiState
import com.factory.wms.ui.viewmodel.scan.ScanViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.withTimeout
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.Shadows.shadowOf
import android.os.Looper
import org.robolectric.annotation.Config
import com.google.gson.JsonParser
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import java.util.concurrent.TimeUnit

/** BUG-2026-10-30-009：真实 ViewModel / DataStore 行为；不连接生产服务。 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [31])
class ScanQuantityEditTest {
    private lateinit var vm: ScanViewModel
    private lateinit var repository: WmsRepository

    @Before
    fun setUp() {
        DataStoreTestReset.resetWmsSettingsDataStore()
        val app = ApplicationProvider.getApplicationContext<Application>()
        repository = WmsRepository(app)
        vm = ScanViewModel(app)
    }

    @After
    fun tearDown() {
        RetrofitClient.setToken(null)
        RetrofitClient.setBaseUrl("")
    }

    private fun line(qty: Double = 1.0, location: String? = "A") = ScanLine(
        material_code = "M001", quantity = qty, location_code = location,
        material_name = "轴承", material_spec = "608", material_brand = "SKF"
    )

    // 仅种加载中/重复行等公开输入不应生成的防御场景，不替换业务函数。
    @Suppress("UNCHECKED_CAST")
    private fun seedState(state: ScanUiState) {
        val field = ScanViewModel::class.java.getDeclaredField("_uiState")
        field.isAccessible = true
        (field.get(vm) as MutableStateFlow<ScanUiState>).value = state
    }

    @Test
    fun `edit replaces exact quantity and preserves other locations and metadata`() {
        vm.addScanLine(line())
        vm.addScanLine(line(4.0, "B"))
        vm.addScanLine(line(2.0).copy(material_code = "M002"))
        val expected = vm.uiState.value.scanLines[0]
        assertTrue(vm.updateScanLineQuantity(expected, 2.75))
        val state = vm.uiState.value
        assertEquals(expected.copy(quantity = 2.75), state.scanLines[0])
        assertEquals(4.0, state.scanLines[1].quantity, 0.0)
        assertEquals(2.0, state.scanLines[2].quantity, 0.0)
        assertEquals(8.75, state.totalQuantity, 0.0)
        assertEquals("M001 数量已修改为 2.75", state.scanFeedback)
        // 修改后继续扫码仍按本次数量累加。
        vm.addScanLine(line())
        assertEquals(3.75, vm.uiState.value.scanLines[0].quantity, 0.0)
        assertEquals(9.75, vm.uiState.value.totalQuantity, 0.0)
    }

    @Test
    fun `invalid quantities never change lines or total`() {
        vm.addScanLine(line())
        for (bad in listOf(-1.0, 0.0, Double.NaN, Double.POSITIVE_INFINITY, Double.NEGATIVE_INFINITY)) {
            assertFalse(vm.updateScanLineQuantity(line(), bad))
            assertEquals(listOf(line()), vm.uiState.value.scanLines)
            assertEquals(1.0, vm.uiState.value.totalQuantity, 0.0)
        }
    }

    @Test
    fun `zero is permitted only for stocktake and negatives remain rejected`() {
        vm.addScanLine(line())
        assertTrue(vm.updateScanLineQuantity(line(), 0.0, allowZero = true))
        assertEquals(0.0, vm.uiState.value.totalQuantity, 0.0)
        assertEquals(1, vm.uiState.value.scanLines.size)
        assertFalse(vm.updateScanLineQuantity(line(0.0), -0.5, allowZero = true))
    }

    @Test
    fun `changed or removed lines are never overwritten or resurrected`() {
        vm.addScanLine(line())
        vm.addScanLine(line())
        assertFalse(vm.updateScanLineQuantity(line(), 5.0))
        assertEquals(2.0, vm.uiState.value.totalQuantity, 0.0)
        vm.clearScanLines()
        assertFalse(vm.updateScanLineQuantity(line(), 5.0))
        assertTrue(vm.uiState.value.scanLines.isEmpty())
    }

    @Test
    fun `ambiguous duplicate keys are rejected rather than editing arbitrary row`() {
        seedState(ScanUiState(scanLines = listOf(line(), line(2.0)), totalQuantity = 3.0))
        assertFalse(vm.updateScanLineQuantity(line(), 8.0))
        assertEquals(3.0, vm.uiState.value.totalQuantity, 0.0)
    }

    @Test
    fun `loading and pending submissions block editing`() {
        for (state in listOf(
            ScanUiState(scanLines = listOf(line()), totalQuantity = 1.0, isLoading = true),
            ScanUiState(scanLines = listOf(line()), totalQuantity = 1.0, pendingSubmissionId = "req-1")
        )) {
            seedState(state)
            assertFalse(vm.updateScanLineQuantity(line(), 8.0))
            assertEquals(1.0, vm.uiState.value.totalQuantity, 0.0)
        }
    }

    @Test
    fun `null and empty locations represent the same legacy line`() {
        vm.addScanLine(line(location = null))
        assertTrue(vm.updateScanLineQuantity(line(location = ""), 8.0))
        assertNull(vm.uiState.value.scanLines.single().location_code)
        assertEquals(8.0, vm.uiState.value.totalQuantity, 0.0)
    }

    @Test
    fun `overflowing total is rejected without changing either row`() {
        val lines = listOf(line(Double.MAX_VALUE), line(1.0, "B"))
        seedState(ScanUiState(scanLines = lines, totalQuantity = Double.MAX_VALUE))
        assertFalse(vm.updateScanLineQuantity(lines[1], Double.MAX_VALUE))
        assertEquals(lines, vm.uiState.value.scanLines)
        assertTrue(vm.uiState.value.totalQuantity.isFinite())
    }

    private suspend fun restoreDraft(operation: String, url: String = "https://quantity.example.com") {
        repository.saveLoginInfo("token", url, "qty-user", "admin")
        val key = repository.editDraftKey(operation)
        repository.saveEditDraft(key, ScanEditDraft(
            lines = listOf(DraftScanLine(line(), "轴承", "608", "SKF")),
            warehouse = WarehouseDto(id = 1, code = "WH01", name = "主仓"),
            department = null, employee = null, contractNo = "HD-1",
            selectedLocation = "A", locationEnabled = true
        ))
        vm.restoreEditDraft(operation)
    }

    @Test
    fun `inbound and outbound edits persist and restore with warehouse unchanged`() = runBlocking {
        for (operation in listOf("inbound", "outbound")) {
            vm = ScanViewModel(ApplicationProvider.getApplicationContext<Application>())
            restoreDraft(operation)
            assertTrue(vm.updateScanLineQuantity(vm.uiState.value.scanLines.single(), 12.5))
            // Robolectric 的主线程需被显式推进；直接 runBlocking 等 mutex 会挡住
            // 已持锁的自动保存协程回到主线程，造成测试死锁。业务提交本身会挂起让出主线程。
            coroutineScope {
                val saved = async { vm.persistEditDraft() }
                withTimeout(5_000) {
                    while (!saved.isCompleted) {
                        shadowOf(Looper.getMainLooper()).idle()
                        delay(10)
                    }
                }
                assertTrue(saved.await())
            }
            val restored = ScanViewModel(ApplicationProvider.getApplicationContext<Application>())
            restored.restoreEditDraft(operation)
            assertEquals(12.5, restored.uiState.value.scanLines.single().quantity, 0.0)
            assertEquals(12.5, restored.uiState.value.totalQuantity, 0.0)
            assertEquals("WH01", restored.uiState.value.selectedWarehouse?.code)
            assertEquals("HD-1", restored.uiState.value.contractNo)
        }
    }

    @Test
    fun `stocktake zero persists in draft without losing the material row`() = runBlocking {
        repository.clearStocktakeDraft()
        vm.addScanLine(line())
        assertTrue(vm.updateScanLineQuantity(line(), 0.0, allowZero = true))
        vm.persistStocktakeDraft()
        shadowOf(Looper.getMainLooper()).idle()
        // 同一主线程协程会在 DataStore I/O 挂起后恢复，显式等待有限时间。
        val deadline = System.nanoTime() + 5_000_000_000L
        while (repository.loadStocktakeDraft() == null && System.nanoTime() < deadline) {
            shadowOf(Looper.getMainLooper()).idle()
            Thread.sleep(10)
        }
        val draft = repository.loadStocktakeDraft()
        assertNotNull(draft)
        assertEquals(0.0, draft!!.lines.single().quantity, 0.0)
    }

    private fun waitForSubmission() {
        val deadline = System.nanoTime() + 5_000_000_000L
        while (vm.uiState.value.success == null && vm.uiState.value.error == null &&
            System.nanoTime() < deadline) {
            shadowOf(Looper.getMainLooper()).idle()
            Thread.sleep(10)
        }
        assertNull(vm.uiState.value.error)
        assertNotNull("提交应在本地 mock 服务完成", vm.uiState.value.success)
    }

    private fun response() = MockResponse().setHeader("Content-Type", "application/json")
        .setBody("""{"status":"success","data":{"id":7,"order_no":"TEST-7","check_no":"CS-7"}}""")

    private fun assertOutboundOrInboundPayload(operation: String) = runBlocking {
        val server = MockWebServer()
        server.start()
        try {
            restoreDraft(operation, server.url("/").toString())
            assertTrue(vm.updateScanLineQuantity(vm.uiState.value.scanLines.single(), 12.5))
            if (operation == "outbound") server.enqueue(response()) // 预检
            server.enqueue(response())
            vm.clearSuccess() // 恢复草稿的提示不计入提交成功。
            if (operation == "inbound") vm.submitInbound() else vm.submitOutbound()
            waitForSubmission()
            val count = if (operation == "outbound") 2 else 1
            repeat(count) { index ->
                val request = server.takeRequest(1, TimeUnit.SECONDS)
                assertNotNull(request)
                val expectedPath = if (operation == "outbound" && index == 0)
                    "/api/outbound/preflight" else "/api/$operation"
                assertEquals(expectedPath, request!!.path)
                val body = JsonParser.parseString(request.body.readUtf8()).asJsonObject
                assertEquals(12.5, body["lines"].asJsonArray[0].asJsonObject["quantity"].asDouble, 0.0)
                assertEquals("WH01", body["warehouse_code"].asString)
            }
        } finally {
            server.shutdown()
        }
    }

    @Test
    fun `inbound submits edited quantity`() = assertOutboundOrInboundPayload("inbound")

    @Test
    fun `outbound preflight and submit both use edited quantity`() = assertOutboundOrInboundPayload("outbound")

    @Test
    fun `stocktake submits explicit zero actual stock and retains check selection`() {
        val server = MockWebServer()
        server.start()
        try {
            RetrofitClient.setBaseUrl(server.url("/").toString())
            RetrofitClient.setToken("test-token")
            seedState(ScanUiState(
                scanLines = listOf(line()), totalQuantity = 1.0,
                selectedWarehouse = WarehouseDto(id = 1, code = "WH02", name = "第二仓"),
                selectedCheckOrder = CheckOrderDto(id = 9, checkNo = "CHECK-9")
            ))
            assertTrue(vm.updateScanLineQuantity(line(), 0.0, allowZero = true))
            server.enqueue(response())
            vm.submitStocktake()
            waitForSubmission()
            val request = server.takeRequest(1, TimeUnit.SECONDS)
            assertNotNull(request)
            assertEquals("/api/stocktake", request!!.path)
            val body = JsonParser.parseString(request.body.readUtf8()).asJsonObject
            assertEquals(0.0, body["lines"].asJsonArray[0].asJsonObject["actual_stock"].asDouble, 0.0)
            assertEquals("WH02", body["warehouse_code"].asString)
            assertEquals(9, body["check_id"].asInt)
        } finally {
            server.shutdown()
        }
    }
}
