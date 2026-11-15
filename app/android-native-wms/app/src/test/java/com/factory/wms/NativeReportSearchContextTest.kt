package com.factory.wms

import android.app.Application
import android.os.Looper
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.test.core.app.ApplicationProvider
import com.factory.wms.data.api.RetrofitClient
import com.factory.wms.data.model.MaterialDto
import com.factory.wms.data.model.WarehouseDto
import com.factory.wms.ui.viewmodel.report.*
import com.google.gson.Gson
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
class NativeReportSearchContextTest {
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
    private fun material(code: String): MaterialDto = Gson().fromJson(
        """{"id":1,"code":"$code","name":"Material $code","spec":"S"}""", MaterialDto::class.java)
    private fun daily(code: String, page: Int = 1) = ok(
        """{"date":"2026-11-15","summary":{"total_materials":1,"in_stock_materials":1,"zero_materials":0,"total_quantity":7},"items":[{"id":1,"code":"$code","name":"$code","stock":7}],"page":$page,"total":3,"page_size":1,"total_pages":3}""")
    private fun movements(code: String) = ok(
        """{"summary":{"total_count":1,"total_in_quantity":7,"total_out_quantity":0},"items":[{"id":1,"material_code":"$code","quantity":7}],"page":1,"total":1,"page_size":20,"total_pages":1}""")

    @Test fun stockDailyKeywordEditStopsOldLoadingWithoutAutomaticQuery() {
        val old = release()
        server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                if (request.requestUrl!!.queryParameter("keyword") == null) {
                    check(old.await(7, TimeUnit.SECONDS))
                    return daily("OLD")
                }
                return daily("NEW")
            }
        }
        val model = keep(StockDailyReportViewModel(application))
        model.selectWarehouse("1")
        pumpUntil("original daily request sent") { server.requestCount == 1 }
        model.updateKeyword("new keyword")
        assertFalse(model.uiState.value.isLoading)
        assertFalse(model.uiState.value.isLoadingMore)
        assertTrue(model.uiState.value.items.isEmpty())
        assertFalse(model.uiState.value.queried)
        assertEquals("Typing must not send a request", 1, server.requestCount)
        old.countDown(); idleRequests(model)
        assertTrue(model.uiState.value.items.isEmpty())
        model.refresh()
        pumpUntil("explicit daily search") { model.uiState.value.items.singleOrNull()?.code == "NEW" }
        server.takeRequest()
        assertEquals("new keyword", server.takeRequest().requestUrl!!.queryParameter("keyword"))
    }

    @Test fun inOutKeywordEditStopsOldLoadingAndRejectsLateFailure() {
        val old = release()
        server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                if (request.requestUrl!!.queryParameter("keyword") == null) {
                    check(old.await(7, TimeUnit.SECONDS))
                    return MockResponse().setResponseCode(503)
                }
                return movements("NEW")
            }
        }
        val model = keep(InOutDetailReportViewModel(application))
        model.selectWarehouse("1")
        pumpUntil("original movements request sent") { server.requestCount == 1 }
        model.updateKeyword("new keyword")
        assertFalse(model.uiState.value.isLoading)
        assertTrue(model.uiState.value.items.isEmpty())
        assertEquals(1, server.requestCount)
        old.countDown(); idleRequests(model)
        assertNull(model.uiState.value.error)
        assertNull(model.uiState.value.loadError)
        model.refresh()
        pumpUntil("explicit movements search") { model.uiState.value.items.singleOrNull()?.materialCode == "NEW" }
        server.takeRequest()
        assertEquals("new keyword", server.takeRequest().requestUrl!!.queryParameter("keyword"))
    }

    @Test fun keywordEditInvalidatesLoadedPagesUntilExplicitFirstPageSearch() {
        server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse = daily(
                request.requestUrl!!.queryParameter("keyword") ?: "OLD",
                request.requestUrl!!.queryParameter("page")!!.toInt())
        }
        val model = keep(StockDailyReportViewModel(application))
        model.selectWarehouse("1")
        pumpUntil("first daily page") { model.uiState.value.queried }
        assertEquals("OLD", model.uiState.value.items.single().code)
        model.updateKeyword("NEW")
        assertTrue(model.uiState.value.items.isEmpty())
        assertNull(model.uiState.value.summary)
        model.loadMore(); main.scheduler.runCurrent()
        assertEquals("New keywords cannot append old query pages", 1, server.requestCount)
        model.refresh()
        pumpUntil("new first page") { model.uiState.value.items.singleOrNull()?.code == "NEW" }
        server.takeRequest()
        val request = server.takeRequest()
        assertEquals("1", request.requestUrl!!.queryParameter("page"))
        assertEquals("NEW", request.requestUrl!!.queryParameter("keyword"))
    }

    @Test fun ledgerMaterialSearchKeepsNewCandidatesAfterOldSuccess() {
        val old = release()
        server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                if (request.requestUrl!!.queryParameter("keyword") == "A") check(old.await(7, TimeUnit.SECONDS))
                return candidates(request.requestUrl!!.queryParameter("keyword")!!)
            }
        }
        val model = keep(StockLedgerReportViewModel(application))
        model.updateMaterialKeyword("A"); model.searchMaterials()
        pumpUntil("A material search sent") { server.requestCount == 1 }
        model.updateMaterialKeyword("B"); model.searchMaterials()
        pumpUntil("B material candidates") { model.uiState.value.materialSuggestions.singleOrNull()?.code == "B" }
        old.countDown(); idleRequests(model)
        assertEquals(listOf("B"), model.uiState.value.materialSuggestions.map { it.code })
        assertEquals("B", model.uiState.value.materialKeyword)
        assertFalse(model.uiState.value.materialSearching)
    }

    @Test fun ledgerEmptyKeywordCancelsOldCandidatesWithoutSendingAnotherRequest() {
        val old = release()
        server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                check(old.await(7, TimeUnit.SECONDS)); return candidates("OLD")
            }
        }
        val model = keep(StockLedgerReportViewModel(application))
        model.updateMaterialKeyword("OLD"); model.searchMaterials()
        pumpUntil("material request sent") { server.requestCount == 1 }
        model.updateMaterialKeyword(""); model.searchMaterials()
        assertFalse(model.uiState.value.materialSearching)
        old.countDown(); idleRequests(model)
        assertTrue(model.uiState.value.materialSuggestions.isEmpty())
        assertEquals(1, server.requestCount)
    }

    @Test fun ledgerSelectionCancelsOldCandidateResults() {
        val old = release()
        server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                check(old.await(7, TimeUnit.SECONDS)); return candidates("OLD")
            }
        }
        val model = keep(StockLedgerReportViewModel(application))
        model.updateMaterialKeyword("OLD"); model.searchMaterials()
        pumpUntil("material request sent") { server.requestCount == 1 }
        model.selectMaterial(material("CONFIRMED"))
        assertFalse(model.uiState.value.materialSearching)
        old.countDown(); idleRequests(model)
        assertEquals("CONFIRMED", model.uiState.value.selectedMaterial?.code)
        assertTrue(model.uiState.value.materialSuggestions.isEmpty())
        assertEquals("", model.uiState.value.materialKeyword)
        assertEquals(1, server.requestCount)
    }

    @Test fun ledgerClearMaterialRejectsOldSearchFailure() {
        val old = release()
        server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                check(old.await(7, TimeUnit.SECONDS)); return MockResponse().setResponseCode(503)
            }
        }
        val model = keep(StockLedgerReportViewModel(application))
        model.updateMaterialKeyword("OLD"); model.searchMaterials()
        pumpUntil("material request sent") { server.requestCount == 1 }
        model.clearMaterial()
        assertFalse(model.uiState.value.materialSearching)
        old.countDown(); idleRequests(model)
        assertNull(model.uiState.value.selectedMaterial)
        assertTrue(model.uiState.value.materialSuggestions.isEmpty())
        assertNull(model.uiState.value.error)
        assertFalse(model.uiState.value.isLoading)
    }

    @Test fun ledgerSearchBindsWarehouseAndRejectsPreviousWarehouseCandidates() {
        val old = release()
        server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val warehouse = request.requestUrl!!.queryParameter("warehouse")
                if (warehouse == "A") check(old.await(7, TimeUnit.SECONDS))
                return candidates(warehouse ?: "UNSCOPED")
            }
        }
        val model = keep(StockLedgerReportViewModel(application))
        @Suppress("UNCHECKED_CAST")
        val state = StockLedgerReportViewModel::class.java.getDeclaredField("_uiState")
            .apply { isAccessible = true }.get(model) as MutableStateFlow<StockLedgerReportUiState>
        state.value = StockLedgerReportUiState(selectedWarehouseId = "1", warehouses = listOf(
            WarehouseDto(1, "A", "Warehouse A"), WarehouseDto(2, "B", "Warehouse B")))
        model.updateMaterialKeyword("bolt"); model.searchMaterials()
        pumpUntil("warehouse A material request") { server.requestCount == 1 }
        model.selectWarehouse("2")
        assertFalse(model.uiState.value.materialSearching)
        model.searchMaterials()
        pumpUntil("warehouse B candidates") { !model.uiState.value.materialSearching }
        old.countDown(); idleRequests(model)
        assertEquals(listOf("B"), model.uiState.value.materialSuggestions.map { it.code })
        assertEquals("A", server.takeRequest().requestUrl!!.queryParameter("warehouse"))
        assertEquals("B", server.takeRequest().requestUrl!!.queryParameter("warehouse"))
    }

    @Test fun ledgerSearchRejectsOldSessionResponse() {
        val old = release()
        server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                check(old.await(7, TimeUnit.SECONDS)); return candidates("PRIVATE-OLD-OWNER")
            }
        }
        val model = keep(StockLedgerReportViewModel(application))
        model.updateMaterialKeyword("OLD"); model.searchMaterials()
        pumpUntil("old owner request sent") { server.requestCount == 1 }
        RetrofitClient.setSession(server.url("/").toString(), "synthetic-new-owner", 92)
        old.countDown(); idleRequests(model)
        assertTrue(model.uiState.value.materialSuggestions.isEmpty())
        assertNull(model.uiState.value.error)
    }
}
