package com.factory.wms

import android.app.Application
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Column
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.test.*
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.text.TextLayoutResult
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.compose.ui.unit.Density
import com.factory.wms.data.model.MaterialDto
import com.factory.wms.ui.screens.StockListRow
import com.factory.wms.ui.theme.WmsTheme
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
class NativeStockMissingValueTest(private val scale: Float, private val dark: Boolean) {
    companion object { @JvmStatic @Parameters fun cases() = listOf(1f, 2f).flatMap { s -> listOf(false, true).map { arrayOf<Any>(s, it) } } }
    @get:Rule val compose = createEmptyComposeRule()
    private lateinit var activity: ActivityController<ComponentActivity>
    @Before fun before() { activity = Robolectric.buildActivity(ComponentActivity::class.java).setup().visible() }
    @After fun after() = disposeComposeActivity(activity)

    @Test fun unknownStockIsNotTreatedAsZeroButRealZeroRemainsVisible() {
        fun material(code: String, stock: Double?) = MaterialDto(1, code, "合成物料", "品牌", "M8×30", "件", "紧固件", null, stock, null, 20.0, 50.0)
        activity.get().setContent { CompositionLocalProvider(LocalDensity provides Density(1f, scale)) {
            WmsTheme(darkTheme = dark) { Column { StockListRow(material("WL-MISSING", null)); StockListRow(material("WL-ZERO", 0.0)) } }
        } }
        compose.onNodeWithText("WL-MISSING").assertExists()
        compose.onNodeWithText("未获取").assertExists()
        compose.onNodeWithText("WL-ZERO").assertExists()
        compose.onNodeWithText("0").assertExists()
        compose.onAllNodesWithText("无库存").assertCountEquals(1)
    }
    @Test fun longMaterialCodeAndQuantityStayFullyReadable() {
        val code = "WL-000238-LONG-CODE-2026-EXTRA"
        val material = MaterialDto(1, code, "不锈钢内六角螺栓", "品牌", "M8×30", "件", "紧固件", null, 128.0, 0.35, 20.0, 50.0)
        activity.get().setContent { CompositionLocalProvider(LocalDensity provides Density(1f, scale)) {
            WmsTheme(darkTheme = dark) { StockListRow(material) }
        } }
        val node = compose.onNodeWithText(code, useUnmergedTree = true)
        val layouts = mutableListOf<TextLayoutResult>()
        node.performSemanticsAction(SemanticsActions.GetTextLayoutResult) { it(layouts) }
        val layout = layouts.single()
        Assert.assertEquals(code.length, layout.getLineEnd(layout.lineCount - 1, visibleEnd = true))
        repeat(layout.lineCount) { Assert.assertFalse("Code cannot be ellipsized", layout.isLineEllipsized(it)) }
        node.assertIsDisplayed()
        compose.onNodeWithText("128").assertIsDisplayed()
    }

}
