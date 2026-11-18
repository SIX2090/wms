package com.factory.wms

import android.app.Application
import android.graphics.Bitmap
import android.graphics.Canvas
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Warehouse
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.compose.ui.text.TextLayoutResult
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewModelScope
import androidx.test.core.app.ApplicationProvider
import com.factory.wms.data.api.RetrofitClient
import com.factory.wms.data.model.*
import com.factory.wms.ui.components.PartySelectorCard
import com.factory.wms.ui.navigation.*
import com.factory.wms.ui.screens.*
import com.factory.wms.ui.theme.*
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

/** Actual page shell and navigation with synthetic data; no business requests or writes. */
@RunWith(ParameterizedRobolectricTestRunner::class)
@Config(sdk = [31], application = Application::class, qualifiers = "w360dp-h800dp-mdpi")
@GraphicsMode(GraphicsMode.Mode.NATIVE)
class NativeShell360AcceptanceTest(private val scale: Float, private val dark: Boolean) {
    @get:org.junit.Rule(order = Int.MIN_VALUE) val wmsSettings = WmsSettingsDataStoreRule()

    companion object {
        @JvmStatic @Parameters(name = "font={0},dark={1}")
        fun cases() = listOf(1f, 1.3f, 1.6f, 2f).flatMap { s -> listOf(false, true).map { arrayOf<Any>(s, it) } }
    }
    @get:Rule val compose = createEmptyComposeRule()
    private lateinit var activity: ActivityController<ComponentActivity>
    private var vm: ScanViewModel? = null
    // 诊断用：记录概览块四列判定所依赖的两个真实输入（见 #130 断言消息）。
    private var diagFontScale = 0f
    private var diagLabelDp = 0f
    @Before fun before() {
        RetrofitClient.setSession("http://127.0.0.1:9/", null, null)
        activity = Robolectric.buildActivity(ComponentActivity::class.java).setup().visible()
    }
    @After fun after() { vm?.let { closeWmsTestViewModels(listOf(it)) }; disposeComposeActivity(activity) }
    private fun content(route: String, body: @Composable () -> Unit) {
        activity.get().setContent {
            CompositionLocalProvider(LocalDensity provides Density(1f, scale)) {
                WmsTheme(darkTheme = dark) {
                    diagFontScale = LocalDensity.current.fontScale
                    diagLabelDp = with(LocalDensity.current) {
                        MaterialTheme.typography.bodyMedium.fontSize.toDp().value
                    }
                    Scaffold(containerColor = Background,
                        bottomBar = { Box(Modifier.testTag("bottom-nav")) { WmsBottomBar(route, bottomTabs(), {}) } }
                    ) { padding ->
                        Box(Modifier.fillMaxSize().padding(bottom = padding.calculateBottomPadding())
                            .consumeWindowInsets(PaddingValues(bottom = padding.calculateBottomPadding()))) { body() }
                    }
                }
            }
        }
    }
    private fun checkTabs() {
        val bar = compose.onNodeWithTag("bottom-nav").getUnclippedBoundsInRoot()
        val labelBounds = mutableListOf<androidx.compose.ui.unit.DpRect>()
        for (label in listOf("首页", "入库", "出库", "查库存", "我的")) {
            val node = compose.onNode(hasText(label) and hasAnyAncestor(hasTestTag("bottom-nav")), useUnmergedTree = true)
            val layouts = mutableListOf<TextLayoutResult>()
            node.performSemanticsAction(SemanticsActions.GetTextLayoutResult) { it(layouts) }
            val layout = layouts.single()
            assertTrue("Tab label should use at most two lines: $label", layout.lineCount <= 2)
            if (label.length == 2) assertEquals("Two-character tab should stay horizontal: $label", 1, layout.lineCount)
            assertTrue(layout.getLineEnd(layout.lineCount - 1, visibleEnd = true) >= label.length)
            repeat(layout.lineCount) { assertFalse(layout.isLineEllipsized(it)) }
            val b = node.getUnclippedBoundsInRoot()
            labelBounds += b
            assertTrue("Tab label clipped above bar: $label", b.top >= bar.top - 1.dp)
            assertTrue("Tab label clipped below bar: $label", b.bottom <= bar.bottom + 1.dp)
            node.assertIsDisplayed()
        }
        val iconCenters = listOf("首页", "入库", "出库", "查库存", "我的").map { label ->
            val bounds = compose.onNodeWithContentDescription(label, useUnmergedTree = true).getUnclippedBoundsInRoot()
            (bounds.top.value + bounds.bottom.value) / 2f
        }
        assertTrue("Navigation icons should share a baseline", iconCenters.max() - iconCenters.min() <= 1f)
        val actions = compose.onAllNodes(hasClickAction() and hasAnyAncestor(hasTestTag("bottom-nav")))
        assertEquals(5, actions.fetchSemanticsNodes().size)
        repeat(5) {
            val b = actions[it].getUnclippedBoundsInRoot()
            assertTrue(b.right - b.left >= 48.dp)
            assertTrue(b.bottom - b.top >= 48.dp)
            assertTrue("Tab text must stay inside its own action", labelBounds[it].left >= b.left - 1.dp && labelBounds[it].right <= b.right + 1.dp)
            if (it > 0) assertTrue("Adjacent tab actions must not overlap", actions[it - 1].getUnclippedBoundsInRoot().right <= b.left + 1.dp)
        }
    }
    private fun capture(name: String) {
        val directory = System.getenv("WMS_UI_SCREENSHOTS") ?: return
        compose.waitForIdle()
        val view = activity.get().window.decorView
        val bitmap = Bitmap.createBitmap(view.width, view.height, Bitmap.Config.ARGB_8888)
        compose.runOnIdle { view.draw(Canvas(bitmap)) }
        val file = File(directory, "shell360-$name-$scale-${if (dark) "dark" else "light"}.png")
        file.parentFile?.mkdirs()
        file.outputStream().use { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) }
    }
    @Test fun homeAndActualFiveTabsRemainReadable() {
        val warehouse = WarehouseDto(1, "WH-A", "一号仓")
        val list = listOf(warehouse)
        val data = DashboardDto(todayInOrders = 6, todayInQuantity = 126.0, todayOutOrders = 4,
            todayOutQuantity = 84.0, pendingInOrders = 5, pendingOutOrders = 3, alertCount = 3, warehouse = warehouse.name)
        content(Screen.Home.route) { HomeWorkbench(data, false, list, "1", {}, {}, {}, {}) }
        checkTabs()
        if (scale <= 1.3f) {
            val labels = listOf("今日入库", "今日出库", "待处理", "库存告警")
            val rects = labels.map { compose.onNodeWithText(it).getUnclippedBoundsInRoot() }
            val top = rects.map { it.top.value }
            assertTrue(
                "360dp overview should show four columns at ordinary font sizes; " +
                    "tops=$top; rects=${rects.joinToString(" ")}; scale=$scale; dark=$dark; " +
                    "fontScale=$diagFontScale; labelDp=$diagLabelDp; labelWidthDp=${diagLabelDp * 4 + 4}; " +
                    "needDp=${(diagLabelDp * 4 + 4) * 4}",
                top.max() - top.min() < 1f)
        }
        capture("home")
    }
    @Test fun inboundQuantityAndActionsRemainReachableWithActualBottomBar() {
        val model = ScanViewModel(ApplicationProvider.getApplicationContext<Application>()).also { vm = it }
        val lines = listOf(
            ScanLine("WL-000238", 24.0, material_name = "不锈钢内六角螺栓", material_spec = "M8×30", material_unit = "件"),
            ScanLine("WL-000516", 8.0, material_name = "工业擦机布", material_spec = "白色加厚型", material_unit = "件"),
            ScanLine("WL-001027", 4.0, material_name = "六角螺母", material_spec = "M8", material_unit = "件"))
        lines.forEach { model.addScanLine(it) }
        val syntheticPhoto = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9ZlSAAAAAASUVORK5CYII="
        repeat(2) { model.addEvidence(syntheticPhoto) }
        content(Screen.Inbound.route) {
            ScanScreenBase("入库", "扫码或手工录入，核对物料与数量", CardBlue, {}, lines, 36.0,
                model, remember { SnackbarHostState() }, false, false, {}, {}, "", "1", {}, {}, {}, { com.factory.wms.ui.screens.ScanBarcodeResult.Rejected }, {}, "提交入库", CardBlue,
                showEvidenceCapture = true,
                header = { PartySelectorCard("收货仓库", "请选择仓库", "一号仓", Icons.Outlined.Warehouse, CardBlue, {}) })
        }
        checkTabs()
        compose.onNodeWithContentDescription("修改数量：WL-000238 ").performScrollTo()
        val q = compose.onNodeWithContentDescription("修改数量：WL-000238 ")
        capture("inbound-initial")
        val outer = compose.onAllNodes(hasScrollAction()).onFirst()
        repeat(4) {
            val unclipped = q.getUnclippedBoundsInRoot()
            val visible = q.fetchSemanticsNode().boundsInRoot
            if (visible.bottom - visible.top + 1 < (unclipped.bottom - unclipped.top).value) {
                // Bring both nested viewports to the target. A blind swipe can
                // overshoot this first row and is not a reachability assertion.
                val viewport = outer.fetchSemanticsNode().boundsInRoot
                val delta = when {
                    unclipped.bottom.value > viewport.bottom -> unclipped.bottom.value - viewport.bottom
                    unclipped.top.value < viewport.top -> unclipped.top.value - viewport.top
                    else -> 0f
                }
                outer.performSemanticsAction(SemanticsActions.ScrollBy) { it(0f, delta) }
                compose.waitForIdle()
            }
        }
        capture("inbound")
        q.assertIsDisplayed()
        val full = q.getUnclippedBoundsInRoot()
        val clipped = q.fetchSemanticsNode().boundsInRoot
        assertTrue("Quantity must be fully visible after scrolling", clipped.bottom - clipped.top + 1 >= (full.bottom - full.top).value)
        compose.onNodeWithText("提交入库").assertIsDisplayed()
        compose.onNodeWithText("3 种物料").assertIsDisplayed()
        compose.onNodeWithText("合计（件）").assertIsDisplayed()
        compose.onNodeWithText("扫码添加").assertIsDisplayed()
        compose.onNodeWithText("手动添加").assertIsDisplayed()
    }
}
