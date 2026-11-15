package com.factory.wms

import android.app.Application
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.ui.test.*
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.text.TextLayoutResult
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.test.core.app.ApplicationProvider
import com.factory.wms.data.api.RetrofitClient
import com.factory.wms.data.model.MaterialDto
import com.factory.wms.data.model.MaterialLocationDto
import com.factory.wms.data.model.WarehouseDto
import com.factory.wms.ui.screens.StockQueryScreen
import com.factory.wms.ui.theme.WmsTheme
import com.factory.wms.ui.viewmodel.scan.ScanUiState
import com.factory.wms.ui.viewmodel.scan.ScanViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import org.junit.*
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.android.controller.ActivityController
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [31], application = Application::class, qualifiers = "w360dp-h800dp-mdpi")
@GraphicsMode(GraphicsMode.Mode.NATIVE)
class NativeStockQueryMissingTest {
    @get:org.junit.Rule(order = Int.MIN_VALUE) val settings = WmsSettingsDataStoreRule()
    @get:Rule val compose = createEmptyComposeRule()
    private lateinit var activity: ActivityController<ComponentActivity>
    private lateinit var scan: ScanViewModel
    private lateinit var state: MutableStateFlow<ScanUiState>

    @Suppress("UNCHECKED_CAST")
    @Before fun before() {
        RetrofitClient.setSession("http://127.0.0.1:9/", "synthetic-owner", 91)
        scan = ScanViewModel(ApplicationProvider.getApplicationContext<Application>())
        val warehouse = WarehouseDto(1, "WH1", "一号仓")
        val material = MaterialDto(1, "WL-MISSING", "合成物料", null, "M8×30", "件", "紧固件", null,
            null, null, null, null, listOf(MaterialLocationDto("A-01-03", null)))
        state = ScanViewModel::class.java.getDeclaredField("_uiState").also { it.isAccessible = true }.get(scan) as MutableStateFlow<ScanUiState>
        state.value = ScanUiState(selectedWarehouse = warehouse, warehouses = listOf(warehouse), scannedMaterial = material)
        activity = Robolectric.buildActivity(ComponentActivity::class.java).setup().visible()
        activity.get().setContent { WmsTheme(darkTheme = false) { StockQueryScreen(scan, {}) } }
    }
    @After fun after() {
        closeWmsTestViewModels(listOf(scan)); RetrofitClient.setToken(null); RetrofitClient.setBaseUrl("")
        disposeComposeActivity(activity)
    }
    @Test fun missingValuesDoNotBecomeShortageOrZero() {
        compose.onNodeWithText("库存未获取").assertIsDisplayed()
        compose.onAllNodesWithText("库存不足").assertCountEquals(0)
        compose.onAllNodesWithText("未获取").assertCountEquals(5)
        compose.onAllNodesWithText("0").assertCountEquals(0)
        compose.runOnIdle { state.value = state.value.copy(scannedMaterial = state.value.scannedMaterial!!.copy(stock = 0.0)) }
        compose.onNodeWithText("库存不足").assertIsDisplayed()
        compose.onNodeWithText("0").assertExists()
    }
    @Test fun longCodeIsNotTruncatedNextToStockStatus() {
        val code = "WL-000238-LONG-CODE-2026-EXTRA"
        compose.runOnIdle { state.value = state.value.copy(scannedMaterial = state.value.scannedMaterial!!.copy(code = code, stock = 128.0, minStock = 20.0, reorderPoint = 50.0)) }
        val node = compose.onNodeWithText(code, useUnmergedTree = true).performScrollTo()
        val layouts = mutableListOf<TextLayoutResult>()
        node.performSemanticsAction(SemanticsActions.GetTextLayoutResult) { it(layouts) }
        val layout = layouts.single()
        Assert.assertEquals(code.length, layout.getLineEnd(layout.lineCount - 1, visibleEnd = true))
        repeat(layout.lineCount) { Assert.assertFalse(layout.isLineEllipsized(it)) }
        node.assertIsDisplayed()
        compose.onNodeWithText("库存充足").assertIsDisplayed()
    }


    @Test fun stockQuantityIsProminentAndStatusHasIcon() {
        compose.runOnIdle { state.value = state.value.copy(scannedMaterial = state.value.scannedMaterial!!.copy(stock = 128.0, minStock = 20.0, reorderPoint = 50.0)) }
        val layouts = mutableListOf<TextLayoutResult>()
        compose.onNodeWithText("128", useUnmergedTree = true).performScrollTo()
            .performSemanticsAction(SemanticsActions.GetTextLayoutResult) { it(layouts) }
        Assert.assertTrue("Current stock should be a prominent large number", layouts.single().layoutInput.style.fontSize.value >= 24f)
        val layout = layouts.single()
        Assert.assertEquals("All stock digits must remain visible", 3, layout.getLineEnd(layout.lineCount - 1, visibleEnd = true))
        repeat(layout.lineCount) { line ->
            Assert.assertFalse("Stock must not be ellipsized", layout.isLineEllipsized(line))
            Assert.assertTrue("Stock glyphs must fit horizontally", layout.getLineRight(line) <= layout.size.width + 1f)
            Assert.assertTrue("Stock glyphs must fit vertically", layout.getLineBottom(line) <= layout.size.height + 1f)
        }
        compose.onNodeWithTag("stock-status-icon", useUnmergedTree = true).assertExists()
        compose.onNodeWithText("库存充足").assertExists()
    }
}
