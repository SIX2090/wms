package com.factory.wms

import android.app.Application
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.compose.ui.text.TextLayoutResult
import androidx.compose.ui.unit.Density
import com.factory.wms.data.model.StockLedgerItem
import com.factory.wms.data.model.StocktakeRecordDto
import com.factory.wms.data.model.StocktakeRecordDetailItemDto
import com.factory.wms.ui.screens.StockLedgerItemRow
import com.factory.wms.ui.screens.StocktakeRecordCard
import com.factory.wms.ui.screens.StocktakeRecordDetailRow
import com.factory.wms.ui.theme.WmsTheme
import org.junit.*
import org.junit.Assert.*
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
class NativeRecordReadableTest(private val scale: Float, private val dark: Boolean) {
    companion object { @JvmStatic @Parameters fun cases() = listOf(1f, 2f).flatMap { s -> listOf(false, true).map { arrayOf<Any>(s, it) } } }
    @get:Rule val compose = createEmptyComposeRule()
    private lateinit var activity: ActivityController<ComponentActivity>
    @Before fun before() { activity = Robolectric.buildActivity(ComponentActivity::class.java).setup().visible() }
    @After fun after() = disposeComposeActivity(activity)
    private fun fullText(label: String) {
        val node = compose.onNodeWithText(label, useUnmergedTree = true).assertExists()
        val layouts = mutableListOf<TextLayoutResult>()
        node.performSemanticsAction(SemanticsActions.GetTextLayoutResult) { it(layouts) }
        val result = layouts.single()
        assertEquals(label.length, result.getLineEnd(result.lineCount - 1, visibleEnd = true))
        repeat(result.lineCount) { assertFalse(result.isLineEllipsized(it)) }
    }
    @Test fun ledgerNumberAndTraceMetadataAreNotTruncated() {
        val item = StockLedgerItem("2026-11-12 09:20", "采购入库", "RK-20261112-004", 24.0, 0.0, 124.0,
            "王仓管", "A-01-03", "采购到货")
        activity.get().setContent { CompositionLocalProvider(LocalDensity provides Density(1f, scale)) {
            WmsTheme(darkTheme = dark) { StockLedgerItemRow(item) }
        } }
        fullText("采购入库 · RK-20261112-004")
        fullText("2026-11-12 09:20 · 王仓管 · 库位 A-01-03 · 采购到货")
    }
    @Test fun zeroDifferenceAndFullRecordIdentifiersRemainVisible() {
        val record = StocktakeRecordDto(id = 1, checkNo = "PD-20261114-002", date = "2026-11-14", warehouse = "一号仓",
            status = "completed", createdAt = "2026-11-14 17:05", itemCount = 8, diffCount = 0, batchNo = "PC-20261114-A")
        activity.get().setContent { CompositionLocalProvider(LocalDensity provides Density(1f, scale)) {
            WmsTheme(darkTheme = dark) { StocktakeRecordCard(record) {} }
        } }
        for (text in listOf("PD-20261114-002", "盘点 8 项 · 差异 0 项", "批次 PC-20261114-A", "无差异，无需调整", "提交时间 2026-11-14 17:05")) fullText(text)
    }
    @Test fun missingAmountsAndStatusAreNotShownAsZeroOrCompleted() {
        activity.get().setContent { CompositionLocalProvider(LocalDensity provides Density(1f, scale)) {
            WmsTheme(darkTheme = dark) { StocktakeRecordDetailRow(StocktakeRecordDetailItemDto(materialCode = "WL-MISSING", unit = "件")) }
        } }
        compose.onNodeWithText("账面 — → 实盘 —").assertExists()
        compose.onNodeWithText("差异 —").assertExists()
        compose.onAllNodesWithText("差异 0件").assertCountEquals(0)
        activity.get().setContent { CompositionLocalProvider(LocalDensity provides Density(1f, scale)) {
            WmsTheme(darkTheme = dark) { StocktakeRecordCard(StocktakeRecordDto(checkNo = "PD-MISSING")) }
        } }
        compose.onNodeWithText("状态未获取", useUnmergedTree = true).assertExists()
        compose.onNodeWithText("差异状态未获取", useUnmergedTree = true).assertExists()
        compose.onAllNodesWithText("已完成", useUnmergedTree = true).assertCountEquals(0)
    }
}
