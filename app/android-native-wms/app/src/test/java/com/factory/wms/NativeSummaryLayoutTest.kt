package com.factory.wms

import android.app.Application
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.width
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.semantics.getOrNull
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.compose.ui.text.TextLayoutResult
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.dp
import com.factory.wms.data.model.*
import com.factory.wms.ui.screens.*
import com.factory.wms.ui.theme.WmsTheme
import com.factory.wms.ui.util.formatQty
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Rule
import org.junit.rules.TestName
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.ParameterizedRobolectricTestRunner
import org.robolectric.ParameterizedRobolectricTestRunner.Parameters
import org.robolectric.android.controller.ActivityController
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import java.io.File

/** Measures actual report and stocktake rows with synthetic DTOs, without a repository or server. */
@RunWith(ParameterizedRobolectricTestRunner::class)
@Config(sdk = [31], application = Application::class, qualifiers = "w320dp-h800dp-mdpi")
@GraphicsMode(GraphicsMode.Mode.NATIVE)
class NativeSummaryLayoutTest(private val fontScale: Float, private val quantity: Double) {
    companion object {
        @JvmStatic
        @Parameters(name = "fontScale={0}, quantity={1}")
        fun cases(): List<Array<Any>> = listOf(1f, 1.3f, 1.6f, 2f).flatMap { scale ->
            listOf(0.0, -0.5, 12.25, 1234567890123.5).map { quantity -> arrayOf<Any>(scale, quantity) }
        }
    }
    @get:Rule val compose = createEmptyComposeRule()
    @get:Rule val testName = TestName()
    private lateinit var activity: ActivityController<ComponentActivity>

    @Before fun before() {
        activity = Robolectric.buildActivity(ComponentActivity::class.java).setup().visible()
    }
    @After fun after() { activity.pause().stop().destroy() }

    private fun checkQuantities(
        expected: (Double, String) -> List<String>,
        row: @Composable (Double, String) -> Unit
    ) {
        val unit = if (quantity > 1000) "毫米/每整套（含附件）" else "个"
        activity.get().setContent {
            CompositionLocalProvider(LocalDensity provides Density(1f, fontScale)) {
                WmsTheme(darkTheme = false) {
                    Box(Modifier.width(288.dp)) { row(quantity, unit) }
                }
            }
        }
        for (text in expected(quantity, unit).distinct()) {
            val nodes = compose.onAllNodes(SemanticsMatcher("Complete summary: $text") { node ->
                node.config.getOrNull(SemanticsProperties.Text)?.any { it.text.replace("\u200B", "") == text } == true
            }, useUnmergedTree = true)
            val count = nodes.fetchSemanticsNodes().size
            assertTrue("Missing summary: $text", count > 0)
            for (index in 0 until count) {
                val layouts = mutableListOf<TextLayoutResult>()
                nodes[index].performSemanticsAction(SemanticsActions.GetTextLayoutResult) { it(layouts) }
                assertEquals(text, layouts.single().layoutInput.text.text.replace("\u200B", ""))
                assertFalse("Summary clipped at fontScale=$fontScale: $text (${layouts.single().size})", layouts.single().hasVisualOverflow)
                nodes[index].assertIsDisplayed()
            }
        }
        val screenshotDirectory = System.getenv("WMS_UI_SCREENSHOTS")
        if (!screenshotDirectory.isNullOrBlank() && quantity > 1000 && (fontScale == 1f || fontScale == 2f)) {
            val output = File(screenshotDirectory, "${testName.methodName}.png")
            output.parentFile?.mkdirs()
            val view = activity.get().window.decorView
            val bitmap = android.graphics.Bitmap.createBitmap(view.width, view.height, android.graphics.Bitmap.Config.ARGB_8888)
            // Draw the measured Android view directly; PixelCopy needs a real window compositor.
            compose.runOnIdle { view.draw(android.graphics.Canvas(bitmap)) }
            output.outputStream().use {
                bitmap.compress(android.graphics.Bitmap.CompressFormat.PNG, 100, it)
            }
        }
    }

    @Test fun inOutSummaryStaysComplete() = checkQuantities(
        expected = { q, _ -> listOf(formatQty(q)) }
    ) { q, _ -> InOutSummaryContent(InOutDetailSummary(1, q, q)) }

    @Test fun dailySummaryStaysComplete() = checkQuantities(
        expected = { q, _ -> listOf(formatQty(q)) }
    ) { q, _ -> DailyReportSummaryContent(DailyReportSummary(1, 2, q, 0.0)) }

    @Test fun stockDailySummaryStaysComplete() = checkQuantities(
        expected = { q, _ -> listOf(formatQty(q)) }
    ) { q, _ -> StockDailySummaryContent(StockDailySummary(1, 2, 3, q)) }

    @Test fun ledgerSummaryStaysComplete() = checkQuantities(
        expected = { q, _ -> listOf(formatQty(q)) }
    ) { q, _ -> LedgerSummaryContent(StockLedgerSummary(1, q, q, q, q)) }
}
