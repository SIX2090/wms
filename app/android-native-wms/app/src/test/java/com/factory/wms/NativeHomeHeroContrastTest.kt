package com.factory.wms

import android.app.Application
import android.graphics.Bitmap
import android.graphics.Canvas
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.compose.ui.text.TextLayoutResult
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.dp
import com.factory.wms.data.model.DashboardDto
import com.factory.wms.data.model.WarehouseDto
import com.factory.wms.ui.screens.HomeWorkbench
import com.factory.wms.ui.theme.WmsTheme
import com.factory.wms.ui.theme.contrastRatio
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
class NativeHomeHeroContrastTest(private val scale: Float, private val dark: Boolean) {
    companion object { @JvmStatic @Parameters fun cases() = listOf(1f, 2f).flatMap { s -> listOf(false, true).map { d -> arrayOf<Any>(s, d) } } }
    @get:Rule val compose = createEmptyComposeRule()
    private lateinit var activity: ActivityController<ComponentActivity>
    @Before fun before() {
        val wh = WarehouseDto(1, "WH1", "一号仓")
        val data = DashboardDto(warehouse = "一号仓", warehouseId = 1)
        activity = Robolectric.buildActivity(ComponentActivity::class.java).setup().visible()
        activity.get().setContent { CompositionLocalProvider(LocalDensity provides Density(1f, scale)) {
            WmsTheme(darkTheme = dark) { HomeWorkbench(data, false, listOf(wh), "1", {}, {}, {}, {}) }
        } }
    }
    @After fun after() { disposeComposeActivity(activity) }
    @Test fun titleAndWarehouseAreReadableAndSelectorIsReachable() {
        val view = activity.get().window.decorView
        val bitmap = Bitmap.createBitmap(view.width, view.height, Bitmap.Config.ARGB_8888)
        compose.runOnIdle { view.draw(Canvas(bitmap)) }
        val background = Color(bitmap.getPixel(2, 2))
        for (label in listOf("今日概览", "当前仓库")) {
            val layouts = mutableListOf<TextLayoutResult>()
            val text = compose.onNodeWithText(label).assertIsDisplayed()
            text.performSemanticsAction(SemanticsActions.GetTextLayoutResult) { it(layouts) }
            val layout = layouts.single()
            assertEquals(label.length, layout.getLineEnd(layout.lineCount - 1, visibleEnd = true))
            repeat(layout.lineCount) { assertFalse(layout.isLineEllipsized(it)) }
            assertTrue("$label must contrast with its blue background", contrastRatio(layout.layoutInput.style.color, background) >= 4.5f)
        }
        val selector = compose.onNode(hasClickAction() and hasAnyDescendant(hasText("一号仓")), useUnmergedTree = true).assertIsDisplayed()
        val bounds = selector.getUnclippedBoundsInRoot()
        assertTrue(bounds.right - bounds.left >= 48.dp && bounds.bottom - bounds.top >= 48.dp)
        selector.performClick()
    }
}
