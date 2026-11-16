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
import androidx.compose.ui.unit.dp
import com.factory.wms.data.model.MaterialArchiveDto
import com.factory.wms.ui.screens.MaterialArchiveRow
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
class NativeArchiveRowTest(private val scale: Float, private val dark: Boolean) {
    companion object { @JvmStatic @Parameters fun cases() = listOf(1f, 2f).flatMap { s -> listOf(false, true).map { arrayOf<Any>(s, it) } } }
    @get:Rule val compose = createEmptyComposeRule()
    private lateinit var activity: ActivityController<ComponentActivity>
    private var opened = 0
    @Before fun before() { activity = Robolectric.buildActivity(ComponentActivity::class.java).setup().visible() }
    @After fun after() = disposeComposeActivity(activity)
    private fun show(count: Int?) {
        val material = MaterialArchiveDto(1, "WL-000238", "不锈钢内六角螺栓", "M8×30", "件", "紧固件", count)
        activity.get().setContent { CompositionLocalProvider(LocalDensity provides Density(1f, scale)) {
            WmsTheme(darkTheme = dark) { MaterialArchiveRow(material) { opened++ } }
        } }
    }
    @Test fun zeroImagesAndMaterialIdentityRemainReadableAndClickable() {
        show(0)
        for (label in listOf("WL-000238", "不锈钢内六角螺栓", "规格：M8×30", "单位：件 · 分类：紧固件", "图片 0/5")) {
            val node = compose.onNodeWithText(label, useUnmergedTree = true).assertExists()
            val layouts = mutableListOf<TextLayoutResult>()
            node.performSemanticsAction(SemanticsActions.GetTextLayoutResult) { it(layouts) }
            val layout = layouts.single()
            assertEquals(label.length, layout.getLineEnd(layout.lineCount - 1, visibleEnd = true))
            repeat(layout.lineCount) { assertFalse(layout.isLineEllipsized(it)) }
        }
        val action = compose.onNode(hasClickAction())
        val bounds = action.getUnclippedBoundsInRoot()
        assertTrue(bounds.bottom - bounds.top >= 48.dp && bounds.right - bounds.left >= 48.dp)
        action.performClick(); assertEquals(1, opened)
    }
    @Test fun missingImageCountIsNotInventedAsZero() {
        show(null)
        compose.onNodeWithText("图片数量未获取", useUnmergedTree = true).assertExists()
        compose.onAllNodesWithText("图片 0/5", useUnmergedTree = true).assertCountEquals(0)
    }
    @Test fun longSpecificationWrapsWithoutEllipsisOrMissingText() {
        val spec = "ZB-BVR-450/750V-1*25-ULTRA-LONG-SPECIFICATION"
        val material = MaterialArchiveDto(1, "WL-000238", "不锈钢内六角螺栓", spec, "件", "紧固件", 0)
        activity.get().setContent { CompositionLocalProvider(LocalDensity provides Density(1f, scale)) {
            WmsTheme(darkTheme = dark) { MaterialArchiveRow(material) {} }
        } }
        val text = "规格：$spec"
        val layouts = mutableListOf<TextLayoutResult>()
        compose.onNodeWithText(text, useUnmergedTree = true)
            .performSemanticsAction(SemanticsActions.GetTextLayoutResult) { it(layouts) }
        val layout = layouts.single()
        assertTrue("Long specification must wrap", layout.lineCount >= 2)
        assertEquals(text.length, layout.getLineEnd(layout.lineCount - 1, visibleEnd = true))
        repeat(layout.lineCount) { assertFalse(layout.isLineEllipsized(it)) }
    }
}
