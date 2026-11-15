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
import com.factory.wms.data.model.PendingNativeWrite
import com.factory.wms.ui.components.PendingNativeWriteDetails
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
class NativePendingWriteDetailsTest(private val scale: Float, private val dark: Boolean) {
    companion object { @JvmStatic @Parameters fun cases() = listOf(1f, 2f).flatMap { s -> listOf(false, true).map { arrayOf<Any>(s, it) } } }
    @get:Rule val compose = createEmptyComposeRule()
    private lateinit var activity: ActivityController<ComponentActivity>
    private var verifies = 0; private var closes = 0
    @Before fun before() { activity = Robolectric.buildActivity(ComponentActivity::class.java).setup().visible() }
    @After fun after() = disposeComposeActivity(activity)
    private fun show(receipt: String?) {
        val row = PendingNativeWrite("inbound_draft", "REQ-20261115-0036", "{}", responseJson = receipt)
        activity.get().setContent { CompositionLocalProvider(LocalDensity provides Density(1f, scale)) {
            WmsTheme(darkTheme = dark) { PendingNativeWriteDetails(row, false, { verifies++ }, { closes++ }) }
        } }
    }
    @Test fun missingReceiptShowsOriginalIdAndCannotAcknowledge() {
        show(null)
        compose.onNodeWithText("类型：识别入库草稿").assertIsDisplayed()
        val id = "请求号：REQ-20261115-0036"
        val layouts = mutableListOf<TextLayoutResult>()
        compose.onNodeWithText(id).performSemanticsAction(SemanticsActions.GetTextLayoutResult) { it(layouts) }
        assertEquals(id.length, layouts.single().getLineEnd(layouts.single().lineCount - 1, visibleEnd = true))
        compose.onNodeWithText("回执状态：未收到服务器回执").assertIsDisplayed()
        compose.onAllNodesWithText("已核对，结束此请求").assertCountEquals(0)
        val action = compose.onNode(hasClickAction() and hasText("核实原请求"))
        val bounds = action.getUnclippedBoundsInRoot()
        assertTrue(bounds.right - bounds.left >= 48.dp && bounds.bottom - bounds.top >= 48.dp)
        action.performClick(); assertEquals(1, verifies); assertEquals(0, closes)
    }
    @Test fun receivedReceiptKeepsExistingExplicitAcknowledgement() {
        show("synthetic-receipt")
        compose.onNodeWithText("回执状态：已取得回执").assertIsDisplayed()
        compose.onNodeWithText("已核对，结束此请求").performClick()
        assertEquals(1, closes); assertEquals(0, verifies)
    }
}
