package com.factory.wms

import android.app.Application
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.compose.ui.unit.Density
import androidx.test.core.app.ApplicationProvider
import com.factory.wms.data.api.RetrofitClient
import com.factory.wms.data.model.StockDailyItem
import com.factory.wms.data.model.StockDailySummary
import com.factory.wms.data.model.WarehouseDto
import com.factory.wms.ui.screens.StockDailyReportScreen
import com.factory.wms.ui.theme.WmsTheme
import com.factory.wms.ui.viewmodel.report.StockDailyPager
import com.factory.wms.ui.viewmodel.report.StockDailyReportUiState
import com.factory.wms.ui.viewmodel.report.StockDailyReportViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import org.junit.*
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.ParameterizedRobolectricTestRunner
import org.robolectric.ParameterizedRobolectricTestRunner.Parameters
import org.robolectric.android.controller.ActivityController
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

@RunWith(ParameterizedRobolectricTestRunner::class)
@Config(sdk = [31], application = Application::class, qualifiers = "w320dp-h800dp-mdpi")
@GraphicsMode(GraphicsMode.Mode.NATIVE)
class NativeStockDailyScreenTest(private val dark: Boolean) {
    companion object { @JvmStatic @Parameters fun cases() = listOf(arrayOf(false), arrayOf(true)) }
    @get:org.junit.Rule(order = Int.MIN_VALUE) val settings = WmsSettingsDataStoreRule()
    @get:Rule val compose = createEmptyComposeRule()
    private lateinit var activity: ActivityController<ComponentActivity>
    private lateinit var vm: StockDailyReportViewModel
    private lateinit var state: MutableStateFlow<StockDailyReportUiState>
    @Suppress("UNCHECKED_CAST")
    @Before fun before() {
        RetrofitClient.setSession("http://127.0.0.1:9/", "synthetic-owner", 91)
        vm = StockDailyReportViewModel(ApplicationProvider.getApplicationContext<Application>())
        state = StockDailyReportViewModel::class.java.getDeclaredField("_uiState").also { it.isAccessible = true }.get(vm) as MutableStateFlow<StockDailyReportUiState>
        val warehouse = WarehouseDto(1, "WH1", "一号仓")
        state.value = state.value.copy(warehouses = listOf(warehouse), selectedWarehouseId = null)
        (StockDailyReportViewModel::class.java.getDeclaredField("pager").also { it.isAccessible = true }.get(vm) as StockDailyPager).onPageLoaded(1, 1)
        activity = Robolectric.buildActivity(ComponentActivity::class.java).setup().visible()
        activity.get().setContent { CompositionLocalProvider(LocalDensity provides Density(1f, 2f)) {
            WmsTheme(darkTheme = dark) { StockDailyReportScreen(vm) {} }
        } }
        compose.runOnIdle {
            state.value = state.value.copy(date = "2026-11-14", dateIsToday = false, generatedAt = "23:59",
                selectedWarehouseId = "1", summary = StockDailySummary(2, 2, 1, 26.0), queried = true, hasMore = false,
                items = listOf(StockDailyItem(1, "WL-000238", "不锈钢内六角螺栓", "标准件优选", "M8×30", "件", "紧固件", 18.0),
                    StockDailyItem(2, "WL-000516", "工业擦机布", "洁工", "白色加厚型", "包", "耗材", 8.0)))
        }
    }
    @After fun after() { closeWmsTestViewModels(listOf(vm)); RetrofitClient.setToken(null); RetrofitClient.setBaseUrl(""); disposeComposeActivity(activity) }
    @Test fun historicalContextAndInventoryRowsAreReachable() {
        compose.onNodeWithText("历史日期 · 收市结存", substring = true).assertIsDisplayed()
        compose.onNodeWithText("物料数仅含正结存", substring = true).assertIsDisplayed()
        compose.onAllNodes(hasScrollAction()).onLast().performScrollToNode(hasText("WL-000238", substring = true))
        compose.onNodeWithText("WL-000238", substring = true).assertIsDisplayed()
    }
}
