package com.factory.wms

import android.app.Application
import android.os.Looper
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.test.core.app.ApplicationProvider
import com.factory.wms.data.api.RetrofitClient
import com.factory.wms.data.model.WarehouseDto
import com.factory.wms.ui.viewmodel.scan.ScanViewModel
import com.factory.wms.ui.viewmodel.stocktake.StocktakeRecordViewModel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.Job
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.setMain
import okhttp3.mockwebserver.Dispatcher
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okhttp3.mockwebserver.RecordedRequest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger

/** Regression tests for 2026-11-25 stocktake/adjustment audit fixes (Android 3.9.49). */
@OptIn(ExperimentalCoroutinesApi::class)
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [31], application = Application::class)
class StocktakeAuditFixTest {
    private val main = StandardTestDispatcher()
    private lateinit var application: Application
    private lateinit var stores: NativeAuditLocalStores
    private lateinit var server: MockWebServer
    private val models = mutableListOf<ViewModel>()

    @Before
    fun before() {
        Dispatchers.setMain(main)
        DataStoreTestReset.resetWmsSettingsDataStore()
        application = ApplicationProvider.getApplicationContext()
        stores = NativeAuditLocalStores(application)
        server = MockWebServer().apply { start() }
        RetrofitClient.setSession(server.url("/").toString(), "stocktake-audit-owner", 73)
    }

    @After
    fun after() {
        closeWmsTestViewModels(models) {
            main.scheduler.runCurrent()
            shadowOf(Looper.getMainLooper()).idle()
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
        fail("Condition did not settle: $label")
    }

    private fun idleRequests(model: ViewModel) = pumpUntil("ViewModel requests complete") {
        model.viewModelScope.coroutineContext[Job]!!.children.none { it.isActive }
    }

    private fun ok(data: String) = MockResponse()
        .setHeader("Content-Type", "application/json")
        .setBody("""{"status":"success","data":$data}""")

    @Test
    fun forceLoadLocationOptionsWorksForStocktakeBeforeDraftRestore() {
        val locationCalls = AtomicInteger()
        server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse =
                when (request.requestUrl!!.encodedPath) {
                    "/api/mobile/location/options" -> {
                        locationCalls.incrementAndGet()
                        ok("""{"enabled":true,"items":["A-01","A-02"],"total_pages":1}""")
                    }
                    else -> ok("""{"items":[]}""")
                }
        }
        val model = keep(ScanViewModel(application))
        model.selectWarehouse(WarehouseDto(1, "W1", "一仓"))
        // Default call before restore/stocktake stays gated (preserves NativeMobileAuditRepairTest)
        model.loadLocationOptions()
        idleRequests(model)
        assertEquals(0, locationCalls.get())

        // Stocktake screen invokes force=true so location picker loads immediately
        model.loadLocationOptions(force = true)
        pumpUntil("forced location options loaded") {
            model.uiState.value.locationEnabled == true && model.uiState.value.locationOptions == listOf("A-01", "A-02")
        }
        assertEquals(1, locationCalls.get())
        assertNull(model.uiState.value.locationError)
    }

    @Test
    fun updateStocktakeAreaPreservesSpacesWhileTyping() {
        val model = keep(ScanViewModel(application))
        model.updateStocktakeArea("Rack A 01 ")
        assertEquals("Rack A 01 ", model.uiState.value.stocktakeArea)
    }

    @Test
    fun stocktakeRecordPaginationDeduplicatesOverlappingRecords() {
        server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val path = request.requestUrl!!.encodedPath
                if (path == "/api/mobile/stocktake/list") {
                    val page = request.requestUrl!!.queryParameter("page")?.toIntOrNull() ?: 1
                    return if (page == 1) {
                        ok(
                            """{"items":[
                                {"id":10,"check_no":"CS-010","warehouse":"一仓","date":"2026-11-25","status":"completed","item_count":1,"diff_count":0},
                                {"id":9,"check_no":"CS-009","warehouse":"一仓","date":"2026-11-25","status":"completed","item_count":1,"diff_count":0}
                            ],"page":1,"page_size":20,"total":3,"total_pages":2}"""
                        )
                    } else {
                        // Simulate concurrent insert shifting CS-009 into page 2 alongside CS-008
                        ok(
                            """{"items":[
                                {"id":9,"check_no":"CS-009","warehouse":"一仓","date":"2026-11-25","status":"completed","item_count":1,"diff_count":0},
                                {"id":8,"check_no":"CS-008","warehouse":"一仓","date":"2026-11-25","status":"completed","item_count":1,"diff_count":0}
                            ],"page":2,"page_size":20,"total":3,"total_pages":2}"""
                        )
                    }
                }
                return ok("""{"items":[]}""")
            }
        }
        val model = keep(StocktakeRecordViewModel(application))
        model.load()
        idleRequests(model)
        assertEquals(listOf("CS-010", "CS-009"), model.uiState.value.records.map { it.checkNo })
        assertTrue(model.uiState.value.hasMore)

        model.loadMore()
        idleRequests(model)
        assertEquals(listOf("CS-010", "CS-009", "CS-008"), model.uiState.value.records.map { it.checkNo })
    }
}
