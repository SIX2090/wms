package com.factory.wms

import android.app.Application
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.compose.ui.text.TextLayoutResult
import androidx.compose.ui.unit.Density
import com.factory.wms.data.model.AssistantAction
import com.factory.wms.data.model.AssistantCard
import com.factory.wms.ui.screens.AssistantMessageBubble
import com.factory.wms.ui.theme.WmsTheme
import com.factory.wms.ui.viewmodel.ai.AssistantChatMessage
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
class NativeAssistantMessageLayoutTest(private val scale: Float, private val dark: Boolean) {
    companion object { @JvmStatic @Parameters fun cases() = listOf(1f, 2f).flatMap { s -> listOf(false, true).map { arrayOf<Any>(s, it) } } }
    @get:Rule val compose = createEmptyComposeRule()
    private lateinit var activity: ActivityController<ComponentActivity>
    private val title = "WL-000238｜不锈钢内六角螺栓"
    private val meta = "现有 18 件 / 安全库存 50 件；缺口 32 件"
    @Before fun before() {
        val msg = AssistantChatMessage(text = "一号仓当前有 3 项物料低于安全库存。", isUser = false,
            cards = listOf(AssistantCard(title, meta)), actions = listOf(AssistantAction("查看库存告警")))
        activity = Robolectric.buildActivity(ComponentActivity::class.java).setup().visible()
        activity.get().setContent { CompositionLocalProvider(LocalDensity provides Density(1f, scale)) {
            WmsTheme(darkTheme = dark) { Column(Modifier.verticalScroll(rememberScrollState())) { AssistantMessageBubble(msg) {} } }
        } }
    }
    @After fun after() = disposeComposeActivity(activity)
    @Test fun structuredMaterialTextIsNotTruncated() {
        for (label in listOf(title, meta, "查看库存告警")) {
            val node = compose.onNodeWithText(label, useUnmergedTree = true).performScrollTo()
            val layouts = mutableListOf<TextLayoutResult>()
            node.performSemanticsAction(SemanticsActions.GetTextLayoutResult) { it(layouts) }
            val result = layouts.single()
            assertEquals(label.length, result.getLineEnd(result.lineCount - 1, visibleEnd = true))
            repeat(result.lineCount) { assertFalse(result.isLineEllipsized(it)) }
        }
    }
}
