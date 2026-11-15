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
import com.factory.wms.ui.components.WmsGradientHeader
import com.factory.wms.ui.components.WmsTopBar
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
class NativeHeaderContrastTest(private val scale: Float, private val dark: Boolean, private val blue: Boolean) {
    companion object { @JvmStatic @Parameters fun cases() = listOf(1f, 2f).flatMap { s -> listOf(false, true).flatMap { d -> listOf(false, true).map { b -> arrayOf<Any>(s, d, b) } } } }
    @get:Rule val compose = createEmptyComposeRule()
    private lateinit var activity: ActivityController<ComponentActivity>
    private var back = 0
    @Before fun before() {
        activity = Robolectric.buildActivity(ComponentActivity::class.java).setup().visible()
        activity.get().setContent { CompositionLocalProvider(LocalDensity provides Density(1f, scale)) {
            WmsTheme(darkTheme = dark) {
                WmsGradientHeader("入库", "一号仓", CardBlue, onBack = { back++ }, blueBackground = blue)
            }
        } }
    }
    @After fun after() = disposeComposeActivity(activity)
    @Test fun actualHeaderTextIsCompleteAndHasContrast() {
        // Sample the actual rendered surface, not a duplicated theme calculation.
        val view = activity.get().window.decorView
        val bitmap = Bitmap.createBitmap(view.width, view.height, Bitmap.Config.ARGB_8888)
        compose.runOnIdle { view.draw(Canvas(bitmap)) }
        val background = Color(bitmap.getPixel(bitmap.width - 2, minOf(20, bitmap.height - 1)))
        for (text in listOf("入库", "一号仓")) {
            val node = compose.onNodeWithText(text).assertIsDisplayed()
            val results = mutableListOf<TextLayoutResult>()
            node.performSemanticsAction(SemanticsActions.GetTextLayoutResult) { it(results) }
            val layout = results.single()
            assertTrue("contrast for $text", contrastRatio(layout.layoutInput.style.color, background) >= 4.5f)
            assertEquals(text.length, layout.getLineEnd(layout.lineCount - 1, visibleEnd = true))
            repeat(layout.lineCount) { assertFalse(layout.isLineEllipsized(it)) }
        }
        val control = compose.onNodeWithContentDescription("返回").assertIsDisplayed()
        val bounds = control.getUnclippedBoundsInRoot()
        // The icon is nested; measure the actual clickable parent.
        val button = compose.onNode(hasClickAction() and hasAnyDescendant(hasContentDescription("返回")), useUnmergedTree = true)
        val hit = button.getUnclippedBoundsInRoot()
        assertTrue(hit.right - hit.left >= 48.dp && hit.bottom - hit.top >= 48.dp)
        assertTrue(bounds.right <= hit.right && bounds.left >= hit.left)
        button.performClick(); compose.runOnIdle { assertEquals(1, back) }
    }
    @Test fun standardTopBarBackTargetIsAtLeast48Dp() {
        activity.get().setContent { CompositionLocalProvider(LocalDensity provides Density(1f, scale)) {
            WmsTheme(darkTheme = dark) { WmsTopBar("物料档案", "一号仓", onBack = { back++ }) }
        } }
        val button = compose.onNode(hasClickAction() and hasAnyDescendant(hasContentDescription("返回")), useUnmergedTree = true)
        val hit = button.getUnclippedBoundsInRoot()
        assertTrue(hit.right - hit.left >= 48.dp && hit.bottom - hit.top >= 48.dp)
        button.performClick(); compose.runOnIdle { assertEquals(1, back) }
    }
}
