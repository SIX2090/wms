package com.factory.wms

import android.app.Application
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.mutableStateOf
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.compose.ui.unit.Density
import androidx.lifecycle.ViewModel
import androidx.test.core.app.ApplicationProvider
import com.factory.wms.data.model.InOutDetailItem
import com.factory.wms.data.model.InOutDetailSummary
import com.factory.wms.data.model.MaterialDto
import com.factory.wms.data.model.OpeningStockDto
import com.factory.wms.data.model.StockLedgerItem
import com.factory.wms.data.model.StockLedgerSummary
import com.factory.wms.data.model.WarehouseDto
import com.factory.wms.ui.screens.InOutDetailReportScreen
import com.factory.wms.ui.screens.BuiltItemsSection
import com.factory.wms.ui.screens.StockLedgerReportScreen
import com.factory.wms.ui.theme.WmsTheme
import com.factory.wms.ui.viewmodel.opening.OpeningStockUiState
import com.factory.wms.ui.viewmodel.report.InOutDetailReportUiState
import com.factory.wms.ui.viewmodel.report.InOutDetailReportViewModel
import com.factory.wms.ui.viewmodel.report.StockLedgerReportUiState
import com.factory.wms.ui.viewmodel.report.StockLedgerReportViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import org.junit.After
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.Assert.assertEquals
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.android.controller.ActivityController
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [31], application = Application::class, qualifiers = "w320dp-h800dp-mdpi")
@GraphicsMode(GraphicsMode.Mode.NATIVE)
class NativeReportScrollTest {
    @get:Rule(order = Int.MIN_VALUE) val settings = WmsSettingsDataStoreRule()
    @get:Rule val compose = createEmptyComposeRule()
    private lateinit var activity: ActivityController<ComponentActivity>
    private lateinit var viewModel: ViewModel
    private val warehouse = WarehouseDto(1, "WH1", "一号仓")

    @Before fun setUp() {
        activity = Robolectric.buildActivity(ComponentActivity::class.java).setup().visible()
    }

    @After fun tearDown() {
        if (::viewModel.isInitialized) closeWmsTestViewModels(listOf(viewModel))
        disposeComposeActivity(activity)
    }

    @Test fun openingStockLoadsEachPageOnlyAtTheCurrentListEnd() {
        val items = (1..36).map { id ->
            OpeningStockDto(id, "TEST-$id", "物料 $id", null, "件", 1, "一号仓",
                null, 1.0, null, null)
        }
        val state = mutableStateOf(OpeningStockUiState(
            builtFirstLoad = false, builtItems = items.take(12),
            builtPage = 1, builtTotalPages = 3, builtTotal = 36
        ))
        val requestedPages = mutableListOf<Int>()
        content {
            BuiltItemsSection(state.value, "", {}, onLoadMore = {
                val nextPage = state.value.builtPage + 1
                requestedPages.add(nextPage)
                state.value = state.value.copy(builtItems = items.take(nextPage * 12), builtPage = nextPage)
            }, onRetry = {}, onItemClick = {})
        }
        val list = compose.onNode(hasScrollToIndexAction())
        compose.runOnIdle { assertEquals(emptyList<Int>(), requestedPages) }
        list.performScrollToIndex(11)
        compose.runOnIdle { assertEquals(listOf(2), requestedPages) }
        list.performScrollToIndex(23)
        compose.runOnIdle { assertEquals(listOf(2, 3), requestedPages) }
    }

    @Test fun inOutReportFiltersScrollAwayWithTheRecords() {
        val vm = InOutDetailReportViewModel(ApplicationProvider.getApplicationContext())
        viewModel = vm
        val state = state<InOutDetailReportUiState>()
        state.value = state.value.copy(warehouses = listOf(warehouse))
        content { InOutDetailReportScreen(vm) {} }
        compose.runOnIdle {
            state.value = state.value.copy(
                selectedWarehouseId = "1",
                queried = true,
                hasMore = false,
                summary = InOutDetailSummary(12, 12.0, 0.0),
                items = (1..12).map { InOutDetailItem(id = it, materialName = "测试物料 $it", quantity = 1.0) }
            )
        }
        assertFiltersScrollWithRecords("开始日期")
    }

    @Test fun stockLedgerFiltersScrollAwayWithTheRecords() {
        val vm = StockLedgerReportViewModel(ApplicationProvider.getApplicationContext())
        viewModel = vm
        state<StockLedgerReportUiState>().value = StockLedgerReportUiState(
            warehouses = listOf(warehouse),
            selectedWarehouseId = "1",
            selectedMaterial = MaterialDto(id = 1, code = "TEST-01", name = "测试物料", brand = null,
                spec = null, unit = "件", category = null, supplier = null, stock = 12.0,
                price = null, minStock = null, reorderPoint = null),
            queried = true,
            hasMore = false,
            summary = StockLedgerSummary(12, 0.0, 12.0, 0.0, 12.0),
            items = (1..12).map {
                StockLedgerItem(referenceNo = "TEST-$it", inQuantity = 1.0,
                    outQuantity = 0.0, balanceQuantity = it.toDouble())
            }
        )
        content { StockLedgerReportScreen(vm) {} }
        assertFiltersScrollWithRecords("全部流水")
    }

    private fun assertFiltersScrollWithRecords(filterLabel: String) {
        val list = compose.onNode(hasScrollToIndexAction())
        val filter = compose.onNodeWithText(filterLabel)
        filter.assertIsDisplayed().assert(hasAnyAncestor(hasScrollToIndexAction()))
        list.performScrollToIndex(13) // 0 是筛选，1–12 是明细，13 是页尾。
        compose.onNodeWithText("已加载全部 12 条").assertIsDisplayed()
        filter.assertDoesNotExist()
        list.performScrollToIndex(0)
        filter.assertIsDisplayed()
    }

    @Suppress("UNCHECKED_CAST")
    private fun <T> state(): MutableStateFlow<T> =
        viewModel.javaClass.getDeclaredField("_uiState").apply { isAccessible = true }
            .get(viewModel) as MutableStateFlow<T>

    private fun content(body: @Composable () -> Unit) {
        activity.get().setContent {
            CompositionLocalProvider(LocalDensity provides Density(1f, 2f)) {
                WmsTheme(darkTheme = false, content = body)
            }
        }
    }
}
