package com.factory.wms

import android.app.Application
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.compose.ui.unit.dp
import androidx.test.core.app.ApplicationProvider
import com.factory.wms.data.model.DashboardDto
import com.factory.wms.data.model.WarehouseDto
import com.factory.wms.ui.navigation.Screen
import com.factory.wms.ui.screens.HomeWorkbench
import com.factory.wms.ui.theme.WmsTheme
import org.junit.*
import org.junit.Assert.*
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.android.controller.ActivityController
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [31], application = Application::class, qualifiers = "w360dp-h800dp-mdpi")
@GraphicsMode(GraphicsMode.Mode.NATIVE)
class NativeHomeBaselineTest {
    @get:org.junit.Rule(order = Int.MIN_VALUE) val settings = WmsSettingsDataStoreRule()
    @get:Rule val compose = createEmptyComposeRule()
    private lateinit var activity: ActivityController<ComponentActivity>
    private val clicked = mutableListOf<Screen>()
    private val warehouse = WarehouseDto(1, "WH1", "一号仓")
    private val data = DashboardDto(todayInOrders = 6, todayInQuantity = 126.0,
        todayOutOrders = 4, todayOutQuantity = 84.0, pendingInOrders = 5, pendingOutOrders = 3,
        alertCount = 3, warehouse = "一号仓", warehouseId = 1)
    @Before fun before() {
        activity = Robolectric.buildActivity(ComponentActivity::class.java).setup().visible()
        activity.get().setContent { WmsTheme(darkTheme = false) {
            HomeWorkbench(data, false, listOf(warehouse), "1", {}, {}, { clicked += it }, {})
        } }
    }
    @After fun after() {
        val content = activity.get().findViewById<android.view.ViewGroup>(android.R.id.content)
        for (index in 0 until content.childCount) (content.getChildAt(index) as? androidx.compose.ui.platform.ComposeView)?.disposeComposition()
        disposeComposeActivity(activity)
    }
    @Test fun baselineKeepsFourOverviewLinksAndThreePrimaryTiles() {
        // 单行 appbar：标题为「仓库工作台」；概览行内等宽数字保持原值。
        compose.onNodeWithText("仓库工作台").assertIsDisplayed()
        compose.onNodeWithText("一号仓").assertIsDisplayed()
        compose.onNodeWithText("126").assertIsDisplayed()
        compose.onNodeWithText("84").assertIsDisplayed()
        val tiles = listOf("入库", "出库", "查库存").map { compose.onNodeWithText(it) }
        tiles.forEach { it.performScrollTo().assertIsDisplayed() }
        val bounds = tiles.map { it.getUnclippedBoundsInRoot() }
        assertTrue(bounds.all { it.right - it.left >= 48.dp && it.bottom - it.top >= 48.dp })
        listOf("今日入库" to Screen.Inbound, "今日出库" to Screen.Outbound,
            "待处理单据" to Screen.OverviewOrders, "库存告警" to Screen.OverviewAlerts).forEach { (label, _) ->
            compose.onNodeWithText(label).performScrollTo().performClick()
        }
        compose.runOnIdle { assertEquals(listOf(Screen.Inbound, Screen.Outbound, Screen.OverviewOrders, Screen.OverviewAlerts), clicked) }
    }
    @Test fun allFourteenOriginalDestinationsRemainReachable() {
        val expected = linkedMapOf("入库" to Screen.Inbound, "出库" to Screen.Outbound,
            "查库存" to Screen.StockQuery, "盘点" to Screen.Stocktake, "期初库存" to Screen.OpeningStock,
            "识别单据" to Screen.DocumentOcr, "识物" to Screen.ObjectRecognize, "物料档案" to Screen.MaterialArchive,
            "每日报表" to Screen.DailyReport, "库存日报" to Screen.StockDailyReport,
            "出入库明细" to Screen.InOutDetailReport, "库存台账" to Screen.StockLedgerReport,
            "盘点记录" to Screen.StocktakeRecord, "AI 助手" to Screen.AssistantChat)
        // 三段折叠：后两段默认收起，先展开再逐项点击，14 个目的地仍全部可达。
        for (section in listOf("查询与报表", "资料与工具")) {
            compose.onNode(hasClickAction() and hasAnyDescendant(hasText(section)), useUnmergedTree = true)
                .performScrollTo().performClick()
        }
        expected.forEach { (label, _) -> compose.onNodeWithText(label).performScrollTo().performClick() }
        compose.runOnIdle { assertEquals(expected.values.toList(), clicked) }
    }
}
