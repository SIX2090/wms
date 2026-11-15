package com.factory.wms

import android.app.Application
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.compose.ui.unit.Density
import com.factory.wms.data.api.OcrItem
import com.factory.wms.ui.screens.DocumentOcrItemCard
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
class NativeDocumentOcrItemTest(private val scale: Float, private val dark: Boolean) {
    companion object { @JvmStatic @Parameters fun cases() = listOf(1f, 2f).flatMap { s -> listOf(false, true).map { arrayOf<Any>(s, it) } } }
    @get:Rule val compose = createEmptyComposeRule()
    private lateinit var activity: ActivityController<ComponentActivity>
    @Before fun before() { activity = Robolectric.buildActivity(ComponentActivity::class.java).setup().visible() }
    @After fun after() = disposeComposeActivity(activity)
    private fun show(item: OcrItem) {
        activity.get().setContent { CompositionLocalProvider(LocalDensity provides Density(1f, scale)) {
            WmsTheme(darkTheme = dark) { DocumentOcrItemCard(item, 0) }
        } }
    }
    @Test fun matchedCodeQuantityAndUnitAreVisible() {
        show(OcrItem("WL-000238", "不锈钢内六角螺栓", "M8×30", 24.0, null, true, "件"))
        compose.onNodeWithText("不锈钢内六角螺栓").assertIsDisplayed()
        compose.onNodeWithText("规格：M8×30").assertIsDisplayed()
        compose.onNodeWithText("已匹配 WL-000238").assertIsDisplayed()
        compose.onNodeWithText("24 件").assertIsDisplayed()
    }
    @Test fun missingQuantityAndUnknownMatchAreNotPresentedAsRecognizedValues() {
        show(OcrItem(null, "合成物料", "L 码", null, null, null, "盒"))
        compose.onNodeWithText("匹配状态未获取").assertIsDisplayed()
        compose.onNodeWithText("数量未识别（草稿默认 1）").assertIsDisplayed()
        compose.onAllNodesWithText("已匹配").assertCountEquals(0)
        show(OcrItem(null, "合成物料", "L 码", 0.0, null, false, "盒"))
        compose.onNodeWithText("未匹配档案").assertIsDisplayed()
        compose.onNodeWithText("0 盒").assertIsDisplayed()
    }
}
