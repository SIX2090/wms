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
class NativeQuantityLayoutTest(private val fontScale: Float, private val quantity: Double) {
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
    @After fun after() { disposeComposeActivity(activity) }

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
        for (text in expected(quantity, unit)) {
            val layouts = mutableListOf<TextLayoutResult>()
            val quantityNode = compose.onNode(SemanticsMatcher("Complete quantity: $text") { node ->
                node.config.getOrNull(SemanticsProperties.Text)?.any { it.text.replace("\u200B", "") == text } == true
            }, useUnmergedTree = true)
            quantityNode
                .performSemanticsAction(SemanticsActions.GetTextLayoutResult) { it(layouts) }
            assertTrue("Missing layout: $text", layouts.isNotEmpty())
            assertEquals(text, layouts.single().layoutInput.text.text.replace("\u200B", ""))
            assertFalse("Quantity clipped at fontScale=$fontScale: $text (${layouts.single().size})", layouts.single().hasVisualOverflow)
            val layout = layouts.single()
            for (fraction in Regex("\\d\\.\\d+").findAll(layout.layoutInput.text.text)) {
                val line = layout.getLineForOffset(fraction.range.first)
                for (offset in fraction.range) {
                    assertEquals("Decimal fraction split across lines: $text", line, layout.getLineForOffset(offset))
                }
            }
            quantityNode.assertIsDisplayed()
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

    @Test fun inOutQuantityAndUnitStayComplete() = checkQuantities(
        expected = { q, u -> listOf((if (q < 0) "-" else "+") + formatQty(kotlin.math.abs(q)) + " $u") }
    ) { q, u ->
        InOutDetailItemRow(InOutDetailItem(1, quantity = q, unit = u, materialName = "合成物料"))
    }

    @Test fun dailyQuantityAndUnitStayComplete() = checkQuantities(
        expected = { q, u -> listOf("${formatQty(q)} $u") }
    ) { q, u ->
        DailyReportItemRow(DailyReportItem(1, "TEST", "2026-11-14", "M-1", "合成物料",
            unit = u, quantity = q, price = 0.0, amount = 0.0, operator = "合成账号", remark = ""), true)
    }

    @Test fun stockDailyQuantityAndUnitStayComplete() = checkQuantities(
        expected = { q, u -> listOf("${formatQty(q)} $u") }
    ) { q, u -> StockDailyItemRow(StockDailyItem(1, "M-1", "合成物料", unit = u, stock = q)) }

    @Test fun ledgerMovementAndBalanceStayComplete() = checkQuantities(
        expected = { q, _ -> listOf(when { q > 0 -> "+${formatQty(q)}"; q < 0 -> "-${formatQty(-q)}"; else -> "—" }, "结存 ${formatQty(q)}") }
    ) { q, _ ->
        StockLedgerItemRow(StockLedgerItem(inQuantity = q.coerceAtLeast(0.0),
            outQuantity = (-q).coerceAtLeast(0.0), balanceQuantity = q))
    }

    @Test fun stocktakeSystemActualAndDifferenceStayComplete() = checkQuantities(
        expected = { q, u -> listOf("账面 0$u → 实盘 ${formatQty(q)}$u", (if (q > 0) "+" else "") + formatQty(q)) }
    ) { q, u ->
        StocktakeRecordDetailRow(StocktakeRecordDetailItemDto(materialCode = "M-1", unit = u,
            systemStock = 0.0, actualStock = q, difference = q, isDiff = q != 0.0))
    }
}
