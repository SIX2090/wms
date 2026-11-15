package com.factory.wms

import android.app.Application
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelStore
import androidx.test.core.app.ApplicationProvider
import com.factory.wms.data.model.DailyReportData
import com.factory.wms.data.model.DailyReportSummary
import com.factory.wms.data.model.DashboardDto
import com.factory.wms.data.model.WarehouseDto
import com.factory.wms.ui.viewmodel.home.HomeViewModel
import com.factory.wms.ui.viewmodel.report.ReportType
import com.factory.wms.ui.viewmodel.report.ReportViewModel
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import kotlinx.coroutines.withContext
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.io.IOException

/** 执行真实 ViewModel／协程；数据源为合成函数，不构造 Repository、不访问网络或数据库。 */
@OptIn(ExperimentalCoroutinesApi::class)
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [31], application = Application::class)
class OverviewLoadingTest {
    private val dispatcher = StandardTestDispatcher()
    private lateinit var application: Application
    private val stores = mutableListOf<ViewModelStore>()
    private val warehouses = listOf(
        WarehouseDto(1, "W1", "仓库一"), WarehouseDto(2, "W2", "仓库二")
    )

    @Before fun before() {
        Dispatchers.setMain(dispatcher)
        application = ApplicationProvider.getApplicationContext()
    }

    @After fun after() {
        stores.forEach { it.clear() }
        Dispatchers.resetMain()
    }

    private fun <T : ViewModel> keep(model: T): T {
        stores += ViewModelStore().also { it.put("subject", model) }
        return model
    }

    private fun report(type: String, date: String?, warehouse: String?) = DailyReportData(
        date = date.orEmpty(), type = type, typeLabel = type,
        summary = DailyReportSummary(1, 1, 3.0, 6.0), items = emptyList(),
        total = 0, page = 1, pageSize = 100, totalPages = 0, warehouse = warehouse
    )

    @Test fun homeDoesNotQueryInConstructor() = runTest(dispatcher) {
        var calls = 0
        keep(HomeViewModel(application, { calls++; Result.success(warehouses) }, {
            calls++; Result.success(DashboardDto())
        }))
        runCurrent()
        assertEquals(0, calls)
    }

    @Test fun homeWaitsForWarehouseAndCoalescesRepeatedEntry() = runTest(dispatcher) {
        val gate = CompletableDeferred<Result<List<WarehouseDto>>>()
        val events = mutableListOf<String>()
        val model = keep(HomeViewModel(application, {
            events += "warehouses"; gate.await()
        }, { warehouse ->
            events += "dashboard:$warehouse"
            Result.success(DashboardDto(warehouseId = warehouse?.toInt()))
        }))
        model.loadDashboard()
        model.loadDashboard()
        runCurrent()
        assertEquals(listOf("warehouses"), events)
        assertTrue(model.uiState.value.isLoading)
        gate.complete(Result.success(warehouses))
        runCurrent()
        assertEquals(listOf("warehouses", "dashboard:1"), events)
        assertEquals("1", model.uiState.value.selectedWarehouseId)
        assertEquals(1, model.uiState.value.dashboard?.warehouseId)
        assertFalse(model.uiState.value.isLoading)
    }

    @Test fun homeReturnRefreshesDataWithoutReloadingWarehouseList() = runTest(dispatcher) {
        var warehouseCalls = 0
        var dashboardCalls = 0
        val model = keep(HomeViewModel(application, {
            warehouseCalls++; Result.success(warehouses)
        }, {
            dashboardCalls++; Result.success(DashboardDto(todayInOrders = dashboardCalls))
        }))
        model.loadDashboard(); runCurrent()
        model.loadDashboard(); runCurrent()
        assertEquals(1, warehouseCalls)
        assertEquals(2, dashboardCalls)
        assertEquals(2, model.uiState.value.dashboard?.todayInOrders)
    }

    @Test fun homeLateSuccessCannotOverwriteNewWarehouse() = runTest(dispatcher) {
        val old = CompletableDeferred<Result<DashboardDto>>()
        val model = keep(HomeViewModel(application, { Result.success(warehouses) }, { id ->
            if (id == "1") withContext(NonCancellable) { old.await() }
            else Result.success(DashboardDto(warehouseId = 2, todayInOrders = 20))
        }))
        model.loadDashboard(); runCurrent()
        model.selectWarehouse("2"); runCurrent()
        assertEquals(2, model.uiState.value.dashboard?.warehouseId)
        old.complete(Result.success(DashboardDto(warehouseId = 1, todayInOrders = 99)))
        runCurrent()
        assertEquals("2", model.uiState.value.selectedWarehouseId)
        assertEquals(20, model.uiState.value.dashboard?.todayInOrders)
    }

    @Test fun homeLateFailureCannotClearNewWarehouse() = runTest(dispatcher) {
        val old = CompletableDeferred<Result<DashboardDto>>()
        val model = keep(HomeViewModel(application, { Result.success(warehouses) }, { id ->
            if (id == "1") withContext(NonCancellable) { old.await() }
            else Result.success(DashboardDto(warehouseId = 2))
        }))
        model.loadDashboard(); runCurrent()
        model.selectWarehouse("2"); runCurrent()
        old.complete(Result.failure(IOException("old warehouse failed"))); runCurrent()
        assertEquals(2, model.uiState.value.dashboard?.warehouseId)
        assertNull(model.uiState.value.error)
        assertFalse(model.uiState.value.isLoading)
    }

    @Test fun homeSwallowedCancellationCannotEndNewLoading() = runTest(dispatcher) {
        val latest = CompletableDeferred<Result<DashboardDto>>()
        val model = keep(HomeViewModel(application, { Result.success(warehouses) }, { id ->
            if (id == "1") {
                try { awaitCancellation() } catch (_: CancellationException) {
                    Result.failure(IOException("cancelled request"))
                }
            } else latest.await()
        }))
        model.loadDashboard(); runCurrent()
        model.selectWarehouse("2"); runCurrent()
        assertTrue(model.uiState.value.isLoading)
        assertNull(model.uiState.value.error)
        assertNull(model.uiState.value.dashboard)
        latest.complete(Result.success(DashboardDto(warehouseId = 2))); runCurrent()
        assertEquals(2, model.uiState.value.dashboard?.warehouseId)
    }

    @Test fun homeWarehouseFailureUsesDefaultOnceAndRetriesListLater() = runTest(dispatcher) {
        var calls = 0
        val selected = mutableListOf<String?>()
        val model = keep(HomeViewModel(application, {
            calls++
            if (calls == 1) Result.failure(IOException("list unavailable"))
            else Result.success(warehouses)
        }, { id ->
            selected += id; Result.success(DashboardDto())
        }))
        model.loadDashboard(); runCurrent()
        assertEquals(listOf<String?>(null), selected)
        assertFalse(model.uiState.value.isLoading)
        model.loadDashboard(); runCurrent()
        assertEquals(listOf(null, "1"), selected)
        assertEquals(2, calls)
    }

    @Test fun homeFailedDashboardCanBeRetried() = runTest(dispatcher) {
        var calls = 0
        val model = keep(HomeViewModel(application, { Result.success(warehouses) }, {
            if (++calls == 1) Result.failure(IOException("offline"))
            else Result.success(DashboardDto(todayInOrders = 7))
        }))
        model.loadDashboard(); runCurrent()
        assertEquals("offline", model.uiState.value.error)
        assertFalse(model.uiState.value.isLoading)
        model.loadDashboard(); runCurrent()
        assertEquals(7, model.uiState.value.dashboard?.todayInOrders)
        assertNull(model.uiState.value.error)
    }

    @Test fun homeLateWarehouseListCannotReplaceManualSelection() = runTest(dispatcher) {
        val old = CompletableDeferred<Result<List<WarehouseDto>>>()
        var calls = 0
        val requested = mutableListOf<String?>()
        val model = keep(HomeViewModel(application, {
            if (++calls == 1) withContext(NonCancellable) { old.await() }
            else Result.success(warehouses)
        }, { id ->
            requested += id; Result.success(DashboardDto(warehouseId = id?.toInt()))
        }))
        model.loadDashboard(); runCurrent()
        model.selectWarehouse("2"); runCurrent()
        old.complete(Result.success(warehouses)); runCurrent()
        assertEquals(listOf("2"), requested)
        assertEquals("2", model.uiState.value.selectedWarehouseId)
    }

    @Test fun dailyWaitsForWarehouseAndMergesIdenticalQueries() = runTest(dispatcher) {
        val gate = CompletableDeferred<Result<List<WarehouseDto>>>()
        val events = mutableListOf<String>()
        val model = keep(ReportViewModel(application, {
            events += "warehouses"; gate.await()
        }, { type, date, id ->
            events += "report:$id"; Result.success(report(type, date, id))
        }))
        runCurrent()
        assertTrue(events.isEmpty())
        model.load(); model.load(); runCurrent()
        assertEquals(listOf("warehouses"), events)
        gate.complete(Result.success(warehouses)); runCurrent()
        assertEquals(listOf("warehouses", "report:1"), events)
        assertEquals("1", model.uiState.value.report?.warehouse)
        assertFalse(model.uiState.value.isLoading)
    }

    @Test fun dailyReturnRefreshesWithoutReloadingWarehouses() = runTest(dispatcher) {
        var warehouseCalls = 0
        var reportCalls = 0
        val model = keep(ReportViewModel(application, {
            warehouseCalls++; Result.success(warehouses)
        }, { type, date, id ->
            reportCalls++; Result.success(report(type, date, id))
        }))
        model.load(); runCurrent()
        model.load(); runCurrent()
        assertEquals(1, warehouseCalls)
        assertEquals(2, reportCalls)
    }

    @Test fun dailyDateAndTypeChangesRejectOldSuccessAndFailure() = runTest(dispatcher) {
        val old = CompletableDeferred<Result<DailyReportData>>()
        val middle = CompletableDeferred<Result<DailyReportData>>()
        var calls = 0
        val model = keep(ReportViewModel(application, { Result.success(warehouses) }, { type, date, id ->
            when (++calls) {
                1 -> withContext(NonCancellable) { old.await() }
                2 -> withContext(NonCancellable) { middle.await() }
                else -> Result.success(report(type, date, id))
            }
        }))
        model.load(); runCurrent()
        model.setDate("2020-01-01"); runCurrent()
        model.selectType(ReportType.REQUISITION); runCurrent()
        assertEquals("requisition", model.uiState.value.report?.type)
        old.complete(Result.success(report("purchase_in", model.today(), "1")))
        middle.complete(Result.failure(IOException("old date failed"))); runCurrent()
        assertEquals("2020-01-01", model.uiState.value.report?.date)
        assertEquals("requisition", model.uiState.value.report?.type)
        assertNull(model.uiState.value.error)
        assertNull(model.uiState.value.loadError)
        assertFalse(model.uiState.value.isLoading)
    }

    @Test fun dailyWarehouseChangeClearsPreviousWarehouseBeforeFailure() = runTest(dispatcher) {
        val gate = CompletableDeferred<Result<DailyReportData>>()
        val model = keep(ReportViewModel(application, { Result.success(warehouses) }, { type, date, id ->
            if (id == "1") Result.success(report(type, date, id)) else gate.await()
        }))
        model.load(); runCurrent()
        assertNotNull(model.uiState.value.report)
        model.selectWarehouse("2")
        assertNull(model.uiState.value.report)
        runCurrent()
        gate.complete(Result.failure(IOException("warehouse two offline"))); runCurrent()
        assertNull(model.uiState.value.report)
        assertEquals("warehouse two offline", model.uiState.value.loadError)
    }

    @Test fun dailySameQueryRefreshFailureRetainsPreviousData() = runTest(dispatcher) {
        var calls = 0
        val model = keep(ReportViewModel(application, { Result.success(warehouses) }, { type, date, id ->
            if (++calls == 1) Result.success(report(type, date, id))
            else Result.failure(IOException("refresh unavailable"))
        }))
        model.load(); runCurrent()
        val previous = model.uiState.value.report
        model.load(); runCurrent()
        assertSame(previous, model.uiState.value.report)
        assertEquals("refresh unavailable", model.uiState.value.error)
        assertNull(model.uiState.value.loadError)
        assertFalse(model.uiState.value.isLoading)
    }

    @Test fun dailyWarehouseFailureKeepsDefaultFallback() = runTest(dispatcher) {
        val selected = mutableListOf<String?>()
        val model = keep(ReportViewModel(application, {
            Result.failure(IOException("warehouse list unavailable"))
        }, { type, date, id ->
            selected += id; Result.success(report(type, date, id))
        }))
        model.load(); runCurrent()
        assertEquals(listOf<String?>(null), selected)
        assertNotNull(model.uiState.value.report)
        assertNull(model.uiState.value.loadError)
    }

    @Test fun dailyInitialFailureCanBeRetried() = runTest(dispatcher) {
        var calls = 0
        val model = keep(ReportViewModel(application, { Result.success(warehouses) }, { type, date, id ->
            if (++calls == 1) Result.failure(IOException("offline"))
            else Result.success(report(type, date, id))
        }))
        model.load(); runCurrent()
        assertEquals("offline", model.uiState.value.loadError)
        model.load(); runCurrent()
        assertNotNull(model.uiState.value.report)
        assertNull(model.uiState.value.loadError)
        assertFalse(model.uiState.value.isLoading)
    }
}
