package com.factory.wms

import android.app.Application
import android.graphics.Bitmap
import android.graphics.Canvas
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Warehouse
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.vectorResource
import androidx.compose.material.icons.outlined.Edit
import androidx.compose.material3.SnackbarHostState
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusManager
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.compose.ui.text.TextLayoutResult
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.test.core.app.ApplicationProvider
import com.factory.wms.data.api.RetrofitClient
import com.factory.wms.data.model.*
import com.factory.wms.ui.navigation.Screen
import com.factory.wms.ui.components.PartySelectorCard
import com.factory.wms.ui.components.PartyPickerDialog
import com.factory.wms.ui.components.PartyPickerItem
import com.factory.wms.ui.components.WmsPrimaryButton
import com.factory.wms.ui.components.WmsOutlinedActionButton
import com.factory.wms.ui.screens.*
import com.factory.wms.ui.theme.*
import com.factory.wms.ui.viewmodel.auth.AuthViewModel
import com.factory.wms.ui.viewmodel.home.HomeViewModel
import com.factory.wms.ui.viewmodel.report.ReportViewModel
import com.factory.wms.ui.viewmodel.scan.ScanViewModel
import kotlinx.coroutines.cancel
import org.junit.*
import org.junit.Assert.*
import org.junit.runner.RunWith
import org.robolectric.ParameterizedRobolectricTestRunner
import org.robolectric.ParameterizedRobolectricTestRunner.Parameters
import org.robolectric.Robolectric
import org.robolectric.android.controller.ActivityController
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import java.io.File

/** Production composables, synthetic data and local Robolectric storage only. No business requests. */
@RunWith(ParameterizedRobolectricTestRunner::class)
@Config(sdk = [31], application = Application::class, qualifiers = "w320dp-h800dp-mdpi")
@GraphicsMode(GraphicsMode.Mode.NATIVE)
class NativeWorkbenchTest(private val fontScale: Float, private val dark: Boolean) {
    @get:org.junit.Rule(order = Int.MIN_VALUE) val wmsSettings = WmsSettingsDataStoreRule()

    companion object {
        @JvmStatic @Parameters(name = "font={0},dark={1}")
        fun cases() = listOf(1f, 1.3f, 1.6f, 2f).flatMap { scale ->
            listOf(false, true).map { arrayOf<Any>(scale, it) }
        }
    }
    @get:Rule val compose = createEmptyComposeRule()
    private lateinit var activity: ActivityController<ComponentActivity>
    private val models = mutableListOf<ViewModel>()
    private var focusManager: FocusManager? = null
    private val app get() = ApplicationProvider.getApplicationContext<Application>()
    private val warehouse = WarehouseDto(1, "WH-SYNTH", "合成一号仓", isDefault = true)
    private val item = DailyReportItem(1, "SYNTH-1", "2026-11-15", "M-6204", "深沟球轴承",
        quantity = 120.0, unit = "套", price = 0.0, amount = 0.0, operator = "合成账号", remark = "", spec = "6204-2RS")

    @Before fun before() {
        RetrofitClient.setSession("http://127.0.0.1:9/", null, null)
        activity = Robolectric.buildActivity(ComponentActivity::class.java).setup().visible()
    }
    @After fun after() {
        // Manual Robolectric Activities own their window recomposer and text cursor jobs.
        // Clear focus and drain lifecycle cancellation before the next parameterized case.
        compose.runOnUiThread {
            focusManager?.clearFocus(force = true)
            models.forEach { it.viewModelScope.cancel() }
            val content = activity.get().findViewById<android.view.ViewGroup>(android.R.id.content)
            for (index in 0 until content.childCount) {
                (content.getChildAt(index) as? androidx.compose.ui.platform.ComposeView)?.disposeComposition()
            }
            disposeComposeActivity(activity)
        }
        org.robolectric.Shadows.shadowOf(android.os.Looper.getMainLooper()).idle()
        closeWmsTestViewModels(models)
    }
    private fun content(body: @Composable () -> Unit) {
        activity.get().setContent {
            CompositionLocalProvider(LocalDensity provides Density(1f, fontScale)) {
                focusManager = LocalFocusManager.current
                WmsTheme(darkTheme = dark) { Box(Modifier.fillMaxSize()) { body() } }
            }
        }
    }
    private fun capture(name: String) {
        val directory = System.getenv("WMS_UI_SCREENSHOTS") ?: return
        compose.waitForIdle()
        val view = activity.get().window.decorView
        val bitmap = Bitmap.createBitmap(view.width, view.height, Bitmap.Config.ARGB_8888)
        compose.runOnIdle { view.draw(Canvas(bitmap)) }
        val file = File(directory, "$name-$fontScale-${if (dark) "dark" else "light"}.png")
        file.parentFile?.mkdirs()
        file.outputStream().use { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) }
    }
    private fun completeText(text: String): TextLayoutResult {
        val layouts = mutableListOf<TextLayoutResult>()
        compose.onNodeWithText(text, useUnmergedTree = true)
            .performSemanticsAction(SemanticsActions.GetTextLayoutResult) { it(layouts) }
        assertEquals(1, layouts.size)
        assertFalse("Text clipped: $text, scale=$fontScale; size=${layouts.single().size}; constraints=${layouts.single().layoutInput.constraints}; widthOverflow=${layouts.single().didOverflowWidth}; heightOverflow=${layouts.single().didOverflowHeight}; paragraph=${layouts.single().multiParagraph.width}x${layouts.single().multiParagraph.height}", layouts.single().hasVisualOverflow)
        return layouts.single()
    }

    private fun completeIdentityText(text: String) {
        val layouts = mutableListOf<TextLayoutResult>()
        compose.onNodeWithText(text, useUnmergedTree = true)
            .performSemanticsAction(SemanticsActions.GetTextLayoutResult) { it(layouts) }
        val result = layouts.single()
        // A naturally sized Text can report didOverflowWidth through paragraph
        // rounding. Identity completeness is the actual visible character range.
        repeat(result.lineCount) {
            assertFalse("Identity ellipsized: $text, scale=$fontScale", result.isLineEllipsized(it))
        }
        assertEquals("Identity truncated: $text", text.length, result.getLineEnd(result.lineCount - 1, visibleEnd = true))
        assertFalse("Identity height clipped: $text", result.didOverflowHeight)
    }

    @Test fun homeGroupsRetainAllFourteenDestinationsAndWarehouse() {
        val auth = AuthViewModel(app).also { models += it }
        val vm = HomeViewModel(app, { Result.success(listOf(warehouse)) }, {
            Result.success(DashboardDto(todayInOrders = 3, todayInQuantity = 1280.0,
                todayOutOrders = 2, todayOutQuantity = 860.0, pendingInOrders = 2,
                pendingOutOrders = 1, alertCount = 4, warehouse = warehouse.name, warehouseId = 1))
        }).also { models += it }
        val destinations = linkedMapOf("入库" to Screen.Inbound, "出库" to Screen.Outbound,
            "查库存" to Screen.StockQuery, "盘点" to Screen.Stocktake, "期初库存" to Screen.OpeningStock,
            "每日报表" to Screen.DailyReport, "库存日报" to Screen.StockDailyReport,
            "出入库明细" to Screen.InOutDetailReport, "库存台账" to Screen.StockLedgerReport,
            "盘点记录" to Screen.StocktakeRecord, "物料档案" to Screen.MaterialArchive,
            "识别单据" to Screen.DocumentOcr, "识物" to Screen.ObjectRecognize, "AI 助手" to Screen.AssistantChat)
        val clicked = mutableListOf<Screen>()
        vm.loadDashboard()
        org.robolectric.Shadows.shadowOf(android.os.Looper.getMainLooper()).idle()
        assertFalse("Synthetic dashboard must be ready before measuring the view", vm.uiState.value.isLoading)
        content { HomeScreen(auth, vm, { clicked += it }, {}) }
        compose.onNodeWithText("仓库工作台").assertIsDisplayed()
        compose.onNodeWithText("合成一号仓").assertIsDisplayed()
        compose.onNodeWithText("开始作业").performScrollTo().assertIsDisplayed()
        capture("home")
        // 验证分组能收起、展开，且每个入口仍能下钻。
        for (section in listOf("查询与报表", "资料与工具")) {
            val sample = if (section == "查询与报表") "每日报表" else "期初库存"
            compose.onNodeWithText(sample).assertExists()
            compose.onNode(hasClickAction() and hasAnyDescendant(hasText(section)), useUnmergedTree = true)
                .performScrollTo().performClick()
            compose.onNodeWithText(sample).assertDoesNotExist()
            compose.onNode(hasClickAction() and hasAnyDescendant(hasText(section)), useUnmergedTree = true)
                .performScrollTo().performClick()
        }
        destinations.forEach { (label, _) ->
            compose.onNodeWithText(label).performScrollTo().performClick()
            completeText(label)
        }
        compose.runOnIdle { assertEquals(destinations.values.toList(), clicked) }
        capture("home-tools")
        compose.onNodeWithText("待处理单据").performScrollTo().performClick()
        compose.onNodeWithText("库存告警").performScrollTo().performClick()
        compose.runOnIdle { assertEquals(listOf(Screen.OverviewOrders, Screen.OverviewAlerts), clicked.takeLast(2)) }
    }

    @Test fun homeKeepsAdaptiveActionGridAndReadableOverview() {
        val data = DashboardDto(todayInOrders = 3, todayInQuantity = 1280.0,
            todayOutOrders = 2, todayOutQuantity = 860.0, pendingInOrders = 2,
            pendingOutOrders = 1, alertCount = 4, warehouse = warehouse.name)
        content { HomeWorkbench(data, false, listOf(warehouse), "1", {}, {}, {}, {}) }
        val tiles = listOf("入库", "出库", "查库存", "盘点").map { label ->
            val tile = compose.onNode(hasText(label) and hasClickAction()).performScrollTo()
            completeIdentityText(label)
            tile.getUnclippedBoundsInRoot().also { bounds ->
                assertTrue(bounds.right - bounds.left >= 48.dp && bounds.bottom - bounds.top >= 48.dp)
            }
        }
        assertEquals(if (fontScale > 1.3f) 2 else 4, tiles.map { it.left }.distinct().size)
        // 概览两张独立 tile + 今日两行：行内等宽数字存在且完整不截断。
        listOf("待处理单据", "库存告警", "今日入库", "今日出库").forEach {
            compose.onNodeWithText(it).performScrollTo()
            completeIdentityText(it)
        }
        // WmsQuantityText 内部经 quantityDisplayText 在千分位逗号后插入 \u200B（便于长数字换行），
        // 故语义树里的真实文本不是 "1,280"，必须走同一个格式化函数取期望值。
        val quantityText = com.factory.wms.ui.util.quantityDisplayText("1,280")
        compose.onNodeWithText(quantityText).performScrollTo()
        val quantity = completeText(quantityText)
        assertEquals("Overview quantity must not split across lines", 1, quantity.lineCount)
        compose.onNodeWithText("仓库工作台").performScrollTo()
        capture("home-polished")
    }

    @Test fun profileFeedbackDescriptionsRemainReadable() {
        val auth = AuthViewModel(app).also { models += it }
        content { ProfileScreen(auth) {} }
        val descriptions = compose.onAllNodesWithText("区分成功与失败", useUnmergedTree = true)
        assertEquals(2, descriptions.fetchSemanticsNodes().size)
        for (i in 0..1) {
            val layouts = mutableListOf<TextLayoutResult>()
            descriptions[i].performScrollTo().performSemanticsAction(SemanticsActions.GetTextLayoutResult) { it(layouts) }
            val layout = layouts.single()
            assertFalse("Feedback description is clipped", layout.didOverflowHeight)
            if (fontScale <= 1.3f) assertEquals("Feedback description wraps too early", 1, layout.lineCount)
        }
    }

    @Test fun reportShortcutRemainsCompleteAndReachableAfterScrolling() {
        val warehouses = listOf(warehouse)
        val data = DashboardDto(todayInOrders = 3, todayInQuantity = 1280.0, todayOutOrders = 2,
            todayOutQuantity = 860.0, pendingInOrders = 2, pendingOutOrders = 1, alertCount = 4, warehouse = warehouse.name)
        content { Box(Modifier.fillMaxWidth().height(704.dp)) {
            HomeWorkbench(data, false, warehouses, "1", {}, {}, {}, {})
        } }
        // 查询与报表默认展开。
        val shortcut = compose.onNodeWithText("库存日报")
        shortcut.performScrollTo().assertIsDisplayed()
        val full = shortcut.getUnclippedBoundsInRoot()
        val visible = shortcut.fetchSemanticsNode().boundsInRoot
        assertTrue("Report shortcut remains clipped after scrolling", visible.bottom - visible.top + 1 >= (full.bottom - full.top).value)
        completeIdentityText("库存日报")
    }

    @Test fun pairedActionsKeepWholeLabelsAtOrdinaryFontSizes() {
        content { Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            WmsPrimaryButton("扫码添加", {}, Modifier.weight(1f), ImageVector.vectorResource(R.drawable.wms_scan))
            WmsOutlinedActionButton("手动添加", {}, Modifier.weight(1f), Icons.Outlined.Edit)
        } }
        for (text in listOf("扫码添加", "手动添加")) {
            completeIdentityText(text)
            val node = compose.onNodeWithText(text)
            node.assertIsDisplayed()
            if (fontScale <= 1.3f) {
                val layouts = mutableListOf<TextLayoutResult>()
                node.performSemanticsAction(SemanticsActions.GetTextLayoutResult) { it(layouts) }
                assertEquals("Action has an orphaned character: $text", 1, layouts.single().lineCount)
            }
        }
    }

    @Test fun selectedWarehouseAndPartyNamesRemainCompleteAndClickable() {
        val value = "WH-A 合成一号仓（生产备料区域）"
        var clicks = 0
        content { PartySelectorCard("收货仓库", "请选择仓库", value, Icons.Outlined.Warehouse, CardBlue) { clicks++ } }
        completeIdentityText("收货仓库")
        completeIdentityText(value)
        compose.onNodeWithText(value).assertIsDisplayed().performClick()
        compose.runOnIdle { assertEquals(1, clicks) }
    }

    @Test fun partyPickerKeepsFullIdentityAndSelectionClearCallbacks() {
        val entry = PartyPickerItem(7, "合成装备生产一部", "员工编号 E-0001 · 合成班组（装配备料组）")
        val entries = listOf(entry)
        val selected = mutableListOf<PartyPickerItem?>()
        content { PartyPickerDialog("选择领料人", entries, 7, false, Icons.Outlined.Warehouse,
            CardBlue, onDismiss = {}, onSelect = { selected += it }, onRetry = {}) }
        compose.onNodeWithText(entry.title).performScrollTo().assertIsDisplayed()
        completeIdentityText(entry.title)
        completeIdentityText(entry.subtitle)
        compose.onNodeWithText(entry.title).performClick()
        compose.onNodeWithText("不选择（留空）").performScrollTo().performClick()
        compose.runOnIdle { assertEquals(listOf(entry, null), selected) }
    }

    @Test fun scanShowsDistinctMaterialIdentityAndReadableEditableQuantity() {
        val vm = ScanViewModel(app).also { models += it }
        val line = ScanLine("M-6204", 120.0, material_name = "深沟球轴承", material_brand = "合成品牌", material_spec = "6204-2RS")
        vm.addScanLine(line)
        content { val state by vm.uiState.collectAsState(); ScanScreenBase("入库", "扫码或手工录入，核对物料与数量", CardBlue, {}, state.scanLines, state.totalQuantity,
            vm, remember { SnackbarHostState() }, false, false, {}, {}, "", "1", {}, {}, {}, { com.factory.wms.ui.screens.ScanBarcodeResult.Rejected }, {}, "提交入库", CardBlue) }
        compose.onNodeWithText("深沟球轴承").assertIsDisplayed()
        capture("inbound")
        completeText("编码 M-6204")
        completeText("合成品牌 · 6204-2RS")
        val quantityLayouts = mutableListOf<TextLayoutResult>()
        compose.onNodeWithContentDescription("修改数量：M-6204 ", useUnmergedTree = true)
            .performSemanticsAction(SemanticsActions.GetTextLayoutResult) { it(quantityLayouts) }
        assertEquals(1, quantityLayouts.size)
        assertFalse("Quantity input must not clip", quantityLayouts.single().hasVisualOverflow)
        assertTrue("Quantity should dominate the edit hint", quantityLayouts.single().layoutInput.style.fontSize.value >= 20f)
        capture("inbound")
        compose.onNodeWithContentDescription("修改数量：M-6204 ").performTextReplacement("121")
        compose.onNodeWithText("确定数量").assertIsDisplayed()
        compose.onNodeWithText("提交入库").assertIsNotEnabled()
        compose.onNodeWithText("取消").performClick()
        compose.onNodeWithContentDescription("修改数量：M-6204 ").assertTextContains("120")
        compose.runOnIdle { assertEquals(120.0, vm.uiState.value.totalQuantity, 0.0) }
    }

    @Test fun reportKeepsCompactDefaultRowsAndLargeFontDetailsReachable() {
        val vm = ReportViewModel(app, { Result.success(listOf(warehouse)) }, { _, _, _ ->
            Result.success(DailyReportData("2026-11-15", "purchase_in", "采购入库", DailyReportSummary(2, 2, 156.0, 0.0),
                listOf(item, item.copy(orderId = 2, materialCode = "M-0008", materialName = "六角螺母", quantity = 36.0,
                    spec = "M8 · 镀锌", unit = "个")), 2, 1, 50, 1, warehouse = warehouse.name))
        }).also { models += it }
        content { DailyReportScreen(vm, {}) }
        val name = compose.onNodeWithText("深沟球轴承（M-6204）", useUnmergedTree = true)
        name.performScrollTo().assertIsDisplayed()
        completeText("120 套")
        if (fontScale == 1f) {
            val nameBounds = name.getUnclippedBoundsInRoot()
            val quantityBounds = compose.onNodeWithText("120 套", useUnmergedTree = true).getUnclippedBoundsInRoot()
            assertTrue("Ordinary quantity should align with material", quantityBounds.top <= nameBounds.top + 4.dp)
        }
        capture("daily-report")
        compose.onNodeWithText("六角螺母（M-0008）").performScrollTo().assertIsDisplayed()
        compose.onNodeWithText("回到今天").performScrollTo().assertIsDisplayed()
    }

    @Test fun longSpecificationAndQuantityRemainCompleteInNarrowReportRow() {
        val spec = "6204-2RS/C3 · 高温密封型 · 内径20毫米/外径47毫米 · 必须核对尾部型号-A17"
        val quantity = 1234567890123.5
        val unit = "毫米/每整套（含附件）"
        content { Box(Modifier.width(288.dp)) {
            DailyReportItemRow(item.copy(spec = spec, quantity = quantity, unit = unit), true)
        } }
        completeText(spec)
        completeText(com.factory.wms.ui.util.quantityDisplayText("${com.factory.wms.ui.util.formatQty(quantity)} $unit"))
    }

    @Test fun loginConnectionCanCollapseWithoutLosingEditedAddress() {
        val auth = AuthViewModel(app).also { models += it }
        content { LoginScreen(auth, {}) }
        compose.onNodeWithText("登录").performScrollTo().assertIsNotEnabled()
        capture("login")
        compose.onNodeWithText("服务器地址").assertDoesNotExist()
        compose.onNodeWithText("连接设置").performScrollTo().performClick()
        val field = compose.onNode(hasSetTextAction() and hasText("服务器地址"))
        field.performScrollTo().performTextReplacement("http://127.0.0.1:9/")
        compose.onNodeWithText("收起连接设置").performScrollTo().performClick()
        compose.onNodeWithText("服务器地址").assertDoesNotExist()
        compose.onNodeWithText("连接设置").performScrollTo().performClick()
        field.performScrollTo().assertTextContains("http://127.0.0.1:9/")
        capture("login-settings")
        field.performImeAction()
        field.assertTextContains("http://127.0.0.1:9/")
    }
}
