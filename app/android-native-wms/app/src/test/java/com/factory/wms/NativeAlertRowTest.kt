package com.factory.wms

import android.app.Application
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Column
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.compose.ui.text.TextLayoutResult
import androidx.compose.ui.unit.Density
import com.factory.wms.data.model.AlertItemDto
import com.factory.wms.data.model.MobileOrderDto
import com.factory.wms.ui.screens.AlertRow
import com.factory.wms.ui.screens.OrderRow
import com.factory.wms.ui.theme.*
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
class NativeAlertRowTest(private val scale: Float, private val dark: Boolean) {
    companion object { @JvmStatic @Parameters fun cases() = listOf(1f, 2f).flatMap { s -> listOf(false, true).map { arrayOf<Any>(s, it) } } }
    @get:Rule val compose = createEmptyComposeRule()
    private lateinit var activity: ActivityController<ComponentActivity>
    private var background = Color.Unspecified
    @Before fun before() { activity = Robolectric.buildActivity(ComponentActivity::class.java).setup().visible() }
    @After fun after() = disposeComposeActivity(activity)
    @Test fun realZeroAndUnknownRemainDistinctAndComplete() {
        val zero = AlertItemDto(1, "WL-000516", "工业擦机布", "白色加厚型", "包", 0.0, 20.0, null, 20.0, "danger", 20.0)
        val missing = AlertItemDto(2, "WL-UNKNOWN", "尚未获取的物料", "规格", "件", null, null, null, null, "danger", null)
        activity.get().setContent { CompositionLocalProvider(LocalDensity provides Density(1f, scale)) {
            WmsTheme(darkTheme = dark) { background = CardBackground; Column { AlertRow(zero, Error); AlertRow(missing, Error) } }
        } }
        for (text in listOf("WL-000516", "工业擦机布", "规格：白色加厚型", "20 包", "现有 0 包  /  安全库存 20 包",
            "WL-UNKNOWN", "尚未获取的物料", "现有 —  /  安全库存 —")) {
            val node = compose.onNodeWithText(text)
            node.assertExists()
            val layouts = mutableListOf<TextLayoutResult>()
            node.performSemanticsAction(SemanticsActions.GetTextLayoutResult) { it(layouts) }
            val layout = layouts.single()
            assertTrue("Contrast below 4.5:1 for $text", contrastRatio(layout.layoutInput.style.color, background) >= 4.5f)
            assertEquals(text.length, layout.getLineEnd(layout.lineCount - 1, visibleEnd = true))
            repeat(layout.lineCount) { assertFalse(layout.isLineEllipsized(it)) }
        }
    }
    @Test fun pendingOrderNumberAndDetailsRemainComplete() {
        val order = MobileOrderDto(1, "RK-20261115-006", "2026-11-15", "purchase_in", "一号仓", null,
            "pending", null, null, null, null, 8)
        activity.get().setContent { CompositionLocalProvider(LocalDensity provides Density(1f, scale)) {
            WmsTheme(darkTheme = dark) { background = CardBackground; OrderRow(order, CardOrange, inbound = true) }
        } }
        for (text in listOf("RK-20261115-006", "待处理", "2026-11-15 · 明细 8 项")) {
            val node = compose.onNodeWithText(text).assertIsDisplayed()
            val layouts = mutableListOf<TextLayoutResult>()
            node.performSemanticsAction(SemanticsActions.GetTextLayoutResult) { it(layouts) }
            val layout = layouts.single()
            assertTrue("Contrast below 4.5:1 for $text", contrastRatio(layout.layoutInput.style.color, background) >= 4.5f)
            assertEquals(text.length, layout.getLineEnd(layout.lineCount - 1, visibleEnd = true))
            repeat(layout.lineCount) { assertFalse(layout.isLineEllipsized(it)) }
        }
    }

    @Test fun missingStockMustNotBeDisplayedAsZero() {
        val item = AlertItemDto(3, "WL-MISSING", "合成物料", "规格", "包", null, null, null, null, "danger", null)
        activity.get().setContent { CompositionLocalProvider(LocalDensity provides Density(1f, scale)) {
            WmsTheme(darkTheme = dark) { AlertRow(item, Error) }
        } }
        compose.onAllNodes(hasText("现有 0", substring = true)).assertCountEquals(0)
        compose.onNodeWithText("现有 —  /  安全库存 —").assertIsDisplayed()
    }

}
