package com.factory.wms

import android.app.Application
import android.os.Looper
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.test.core.app.ApplicationProvider
import com.factory.wms.data.api.RetrofitClient
import com.factory.wms.data.model.WarehouseDto
import com.factory.wms.data.repository.WmsRepository
import com.factory.wms.ui.viewmodel.archive.MaterialArchiveViewModel
import com.factory.wms.ui.viewmodel.list.ListKind
import com.factory.wms.ui.viewmodel.list.OrderListViewModel
import com.factory.wms.ui.viewmodel.report.InOutDetailReportViewModel
import com.factory.wms.ui.viewmodel.report.StockDailyReportViewModel
import com.factory.wms.ui.viewmodel.report.StockLedgerReportViewModel
import com.factory.wms.ui.viewmodel.scan.ScanViewModel
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.test.*
import okhttp3.mockwebserver.*
import org.junit.*
import org.junit.Assert.*
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

/** A02: real ViewModels, Retrofit and private Android stores; all HTTP is loopback. */
@OptIn(ExperimentalCoroutinesApi::class)
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [31], application = Application::class)
class NativeMobileAuditRepairTest {
    private val main = StandardTestDispatcher()
    private lateinit var application: Application
    private lateinit var stores: NativeAuditLocalStores
    private lateinit var server: MockWebServer
    private val models = mutableListOf<ViewModel>()
    private val releases = mutableListOf<CountDownLatch>()

    @Before fun before() {
        Dispatchers.setMain(main)
        DataStoreTestReset.resetWmsSettingsDataStore()
        application = ApplicationProvider.getApplicationContext()
        stores = NativeAuditLocalStores(application)
        server = MockWebServer().apply { start() }
        RetrofitClient.setSession(server.url("/").toString(), "synthetic-report-owner", 91)
    }

    @After fun after() {
        releases.forEach { it.countDown() }
        closeWmsTestViewModels(models) {
            main.scheduler.runCurrent(); shadowOf(Looper.getMainLooper()).idle()
        }
        stores.close()
        RetrofitClient.setSession("", null)
        server.shutdown()
        Dispatchers.resetMain()
    }

    private fun <T : ViewModel> keep(model: T): T = model.also { models.add(it) }
    private fun pumpUntil(label: String, condition: () -> Boolean) {
        val deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(8)
        while (System.nanoTime() < deadline) {
            main.scheduler.runCurrent()
            shadowOf(Looper.getMainLooper()).idle()
            if (condition()) return
            Thread.sleep(10)
        }
        fail("Fixture/request did not settle: $label")
    }
    private fun idleRequests(model: ViewModel) = pumpUntil("ViewModel requests complete") {
        model.viewModelScope.coroutineContext[Job]!!.children.none { it.isActive }
    }
    private fun release(): CountDownLatch = CountDownLatch(1).also { releases.add(it) }
    private fun ok(data: String) = MockResponse().setHeader("Content-Type", "application/json")
        .setBody("""{"status":"success","data":$data}""")
    private fun candidates(code: String) = ok("""[{"id":1,"code":"$code","name":"Material $code","spec":"S"}]""")
    @Test fun unselectedWarehouseDoesNotIssueStockRequests() {
        val model = keep(ScanViewModel(application))
        model.searchMaterialByCode("TEST")
        model.onStockQueryKeywordChange("轴承")
        model.queryMaterialByKeyword("轴承")
        main.scheduler.advanceUntilIdle()
        assertEquals(0, server.requestCount)
        assertNull(model.uiState.value.scannedMaterial)
        assertFalse(model.uiState.value.isLoading)
        assertEquals("请先选择仓库后再查询库存", model.uiState.value.error)
    }

    @Test fun canRetryStockLookupAfterDefaultWarehouseArrives() {
        val pending = release()
        server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse = when (request.requestUrl!!.encodedPath) {
                "/api/warehouses" -> {
                    check(pending.await(7, TimeUnit.SECONDS))
                    ok("""{"items":[{"id":1,"code":"W1","name":"Test","is_default":true}]}""")
                }
                "/api/material/info" -> {
                    assertEquals("W1", request.requestUrl!!.queryParameter("warehouse"))
                    ok("""{"id":1,"code":"TEST","stock":7}""")
                }
                else -> ok("""{"items":[]}""")
            }
        }
        val model = keep(ScanViewModel(application))
        model.loadWarehouses()
        pumpUntil("warehouse read started") { server.requestCount == 1 }
        model.searchMaterialByCode("TEST")
        assertFalse(model.uiState.value.isLoading)
        assertNull(model.uiState.value.scannedMaterial)
        pending.countDown()
        pumpUntil("default warehouse arrived") { model.uiState.value.selectedWarehouse?.code == "W1" }
        model.searchMaterialByCode("TEST")
        pumpUntil("scoped stock arrived") { model.uiState.value.scannedMaterial?.stock == 7.0 }
        assertFalse(model.uiState.value.isLoading)
        assertNull(model.uiState.value.error)
    }

    @Test fun warehouseErrorsAreVisibleAndRefreshLoadsWarehousesAgain() {
        repeat(3) { server.enqueue(MockResponse().setResponseCode(503)) }
        val movement = keep(InOutDetailReportViewModel(application))
        val ledger = keep(StockLedgerReportViewModel(application))
        val daily = keep(StockDailyReportViewModel(application))
        movement.loadWarehouses(); ledger.loadWarehouses(); daily.loadWarehouses()
        idleRequests(movement); idleRequests(ledger); idleRequests(daily)
        assertEquals(3, server.requestCount)
        listOf(movement.uiState.value.warehouseError, ledger.uiState.value.warehouseError,
            daily.uiState.value.warehouseError).forEach { assertTrue(it.orEmpty().contains("503")) }

        repeat(3) { server.enqueue(ok("""{"items":[{"id":1,"code":"W1","name":"Test"}]}""")) }
        movement.refreshWithWarehouses(); ledger.refreshWithWarehouses(); daily.refreshWithWarehouses()
        idleRequests(movement); idleRequests(ledger); idleRequests(daily)
        assertEquals(6, server.requestCount)
        listOf(movement.uiState.value.warehouses, ledger.uiState.value.warehouses,
            daily.uiState.value.warehouses).forEach { assertEquals("W1", it.single().code) }
        listOf(movement.uiState.value.warehouseError, ledger.uiState.value.warehouseError,
            daily.uiState.value.warehouseError).forEach { assertNull(it) }
    }

    @Test fun orderListShowsSecondPageFailureWhileKeepingFirstPage() {
        server.enqueue(ok("""{"items":[{"id":1,"order_no":"SYNTHETIC"}],"page":1,"total":2,"total_pages":2}"""))
        server.enqueue(MockResponse().setResponseCode(503))
        val model = keep(OrderListViewModel(application))
        model.start(ListKind.OUT_ORDER, "1")
        idleRequests(model)
        model.loadMore()
        idleRequests(model)
        assertEquals(2, server.requestCount)
        assertEquals(1, model.uiState.value.orders.size)
        assertEquals(1, model.uiState.value.page)
        assertTrue(model.uiState.value.error.orEmpty().contains("503"))
        assertNull(model.uiState.value.loadError)
    }

    @Test fun alertDisabledPreservesServerNotice() {
        server.enqueue(MockResponse().setHeader("Content-Type","application/json").setBody(
            """{"status":"success","message":"库存预警未启用","data":{"items":[],"total":0,"page":1,"total_pages":0}}"""))
        val model = keep(OrderListViewModel(application))
        model.start(ListKind.ALERT, "1")
        idleRequests(model)
        assertEquals("库存预警未启用", model.uiState.value.notice)
    }

    @Test fun successfulLocationRetryIgnoresOldFailure() {
        val old = release()
        val counter = java.util.concurrent.atomic.AtomicInteger()
        server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                if (request.requestUrl!!.encodedPath != "/api/mobile/location/options") return ok("""{"items":[]}""")
                if (counter.incrementAndGet() == 1) {
                    check(old.await(7, TimeUnit.SECONDS))
                    return MockResponse().setResponseCode(503)
                }
                return ok("""{"enabled":true,"items":["A1"],"total_pages":1}""")
            }
        }
        val model = keep(ScanViewModel(application))
        runBlocking {
            WmsRepository(application).saveLoginInfo(
                "synthetic-report-owner", server.url("/").toString(), "audit", "warehouse", 91)
            model.restoreEditDraft("outbound")
        }
        assertFalse(model.uiState.value.isLoading)
        model.selectWarehouse(WarehouseDto(1, "W1","Test"))
        pumpUntil("first location read") { counter.get() == 1 }
        val previousJobs = model.viewModelScope.coroutineContext[Job]!!.children.toSet()
        model.loadLocationOptions()
        pumpUntil("new read succeeded") { model.uiState.value.locationEnabled == true }
        old.countDown()
        pumpUntil("superseded request cancelled") { previousJobs.any { it.isCancelled } }
        assertNull(model.uiState.value.locationError)
        assertEquals(listOf("A1"), model.uiState.value.locationOptions)
    }
    @Test fun cappedFuzzyMatchesAndArchivePreserveServerTotals() {
        fun truncated(limit: Int) = okhttp3.mockwebserver.MockResponse().setHeader("Content-Type","application/json")
            .setBody("""{"status":"success","total":${limit + 1},"truncated":true,"data":[${(1..limit).joinToString(",") { """{"id":$it,"code":"MAT-$it","name":"Synthetic"}""" }}]}""")
        val scan = keep(ScanViewModel(application))
        server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse = when (request.requestUrl!!.encodedPath) {
                "/api/material/info" -> MockResponse().setResponseCode(404)
                "/api/material/search" -> truncated(100)
                "/api/stocktake/check_orders" -> ok("""{"items":[]}""")
                else -> truncated(5000)
            }
        }
        scan.selectWarehouse(WarehouseDto(1, "W1", "Test"))
        scan.queryMaterialByKeyword("synthetic")
        pumpUntil("100 suggestions") { scan.uiState.value.materialSuggestions.size == 100 }
        assertEquals(101, scan.uiState.value.truncatedMaterialTotal)
        val archive = keep(MaterialArchiveViewModel(application))
        archive.search("Synthetic")
        idleRequests(archive)
        assertEquals(5000, archive.uiState.value.materials.size)
        assertEquals(5001, archive.uiState.value.truncatedTotal)
        assertNull(archive.uiState.value.error)
    }
    @Test fun changingKeywordDiscardsOldExactResult() {
        val block = release()
        server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                if (request.requestUrl!!.encodedPath == "/api/stocktake/check_orders") return ok("""{"items":[]}""")
                if (request.requestUrl!!.encodedPath == "/api/material/search") return candidates("B")
                check(block.await(7, TimeUnit.SECONDS))
                return ok("""{"id":1,"code":"A","name":"Old result","stock":31}""")
            }
        }
        val model = keep(ScanViewModel(application))
        model.selectWarehouse(WarehouseDto(1, "W1","Test"))
        val existing = model.viewModelScope.coroutineContext[Job]!!.children.toSet()
        model.queryMaterialByKeyword("A")
        val lookup = (model.viewModelScope.coroutineContext[Job]!!.children.toSet() - existing).single()
        pumpUntil("A queried") { server.requestCount >= 2 }
        model.onStockQueryKeywordChange("B")
        main.scheduler.advanceTimeBy(190)
        pumpUntil("B suggestion") { model.uiState.value.materialSuggestions.singleOrNull()?.code == "B" }
        block.countDown()
        pumpUntil("A query finished") { lookup.isCompleted }
        assertTrue(lookup.isCancelled)
        assertNull(model.uiState.value.scannedMaterial)
        assertEquals("B", model.uiState.value.materialSuggestions.single().code)
        assertFalse(model.uiState.value.isLoading)
    }
}