package com.factory.wms

import android.app.Application
import android.graphics.Bitmap
import android.graphics.Canvas
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
import androidx.test.core.app.ApplicationProvider
import com.factory.wms.data.api.RetrofitClient
import com.factory.wms.data.model.MaterialDto
import com.factory.wms.data.model.WarehouseDto
import com.factory.wms.ui.screens.StockQueryScreen
import com.factory.wms.ui.theme.WmsTheme
import com.factory.wms.ui.viewmodel.scan.ScanUiState
import com.factory.wms.ui.viewmodel.scan.ScanViewModel
import kotlinx.coroutines.flow.MutableStateFlow
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
class NativeStockQueryFocusLayoutTest(private val scale: Float, private val dark: Boolean) {
    companion object {
        @JvmStatic @Parameters(name = "font={0},dark={1}")
        fun cases() = listOf(1f, 2f).flatMap { s -> listOf(false, true).map { arrayOf<Any>(s, it) } }
    }
    @get:org.junit.Rule(order = Int.MIN_VALUE) val settings = WmsSettingsDataStoreRule()
    @get:Rule val compose = createEmptyComposeRule()
    private lateinit var activity: ActivityController<ComponentActivity>
    private lateinit var scan: ScanViewModel
    @Suppress("UNCHECKED_CAST")
    @Before fun before() {
        RetrofitClient.setSession("http://127.0.0.1:9/", "synthetic-owner", 91)
        scan = ScanViewModel(ApplicationProvider.getApplicationContext<Application>())
        val warehouse = WarehouseDto(1, "WH1", "一号仓")
        val material = MaterialDto(1, "WL-000238", "不锈钢内六角螺栓", "标准件优选", "M8×30", "件", "紧固件", null,
            123456.0, .35, 20.0, 50.0)
        val field = ScanViewModel::class.java.getDeclaredField("_uiState").apply { isAccessible = true }
        (field.get(scan) as MutableStateFlow<ScanUiState>).value = ScanUiState(selectedWarehouse = warehouse, warehouses = listOf(warehouse), scannedMaterial = material)
        activity = Robolectric.buildActivity(ComponentActivity::class.java).setup().visible()
        activity.get().setContent { CompositionLocalProvider(LocalDensity provides Density(1f, scale)) {
            WmsTheme(darkTheme = dark) { StockQueryScreen(scan, {}) }
        } }
    }
    @After fun after() { closeWmsTestViewModels(listOf(scan)); disposeComposeActivity(activity); RetrofitClient.setSession("", null) }

    @Test fun scanIconIsEasyToSee() {
        val icon = compose.onNodeWithContentDescription("扫码", useUnmergedTree = true)
        icon.assertIsDisplayed()
        val bounds = icon.getUnclippedBoundsInRoot()
        Assert.assertEquals(36.dp, bounds.right - bounds.left)
        Assert.assertEquals(36.dp, bounds.bottom - bounds.top)
    }

    @Test fun scanAndSearchHaveMatchingVisibleButtonsAndLeaveRoomToType() {
        val scanButton = actionButton("扫码")
        val searchButton = actionButton("查询")
        val scanBounds = scanButton.assertIsDisplayed().getUnclippedBoundsInRoot()
        val searchBounds = searchButton.assertIsDisplayed().getUnclippedBoundsInRoot()
        for (bounds in listOf(scanBounds, searchBounds)) {
            Assert.assertEquals(48.dp, bounds.right - bounds.left)
            Assert.assertEquals(48.dp, bounds.bottom - bounds.top)
        }
        Assert.assertEquals(searchBounds.top, scanBounds.top)
        val view = activity.get().window.decorView
        val bitmap = Bitmap.createBitmap(view.width, view.height, Bitmap.Config.ARGB_8888)
        compose.runOnIdle { view.draw(Canvas(bitmap)) }
        // 圆角范围内的上沿中心只绘制按钮底色。
        val y = scanBounds.top.value.toInt() + 4
        val scanFill = bitmap.getPixel(scanBounds.left.value.toInt() + 24, y)
        val searchFill = bitmap.getPixel(searchBounds.left.value.toInt() + 24, y)
        Assert.assertEquals("The visible button fills should match", searchFill, scanFill)
        Assert.assertNotEquals(searchFill, bitmap.getPixel(searchBounds.left.value.toInt() - 1, y))
        Assert.assertTrue(searchBounds.left - scanBounds.right >= 6.dp)
        val input = compose.onNode(hasSetTextAction()).assertIsDisplayed().getUnclippedBoundsInRoot()
        Assert.assertTrue(input.right - input.left >= 160.dp)
    }

    private fun actionButton(label: String) = compose.onNode(
        hasClickAction() and hasAnyDescendant(hasContentDescription(label)),
        useUnmergedTree = true
    )

    @Test fun currentStockAndStatusRemainReadable() {
        val layouts = mutableListOf<TextLayoutResult>()
        compose.onNodeWithText("123456", useUnmergedTree = true).performScrollTo()
            .performSemanticsAction(SemanticsActions.GetTextLayoutResult) { it(layouts) }
        val layout = layouts.single()
        Assert.assertTrue(layout.layoutInput.style.fontSize.value >= 24f)
        Assert.assertFalse("Long stock must not clip", layout.hasVisualOverflow)
        Assert.assertEquals(6, layout.getLineEnd(layout.lineCount - 1, visibleEnd = true))
        repeat(layout.lineCount) { Assert.assertFalse(layout.isLineEllipsized(it)) }
        compose.onNodeWithTag("stock-status-icon", useUnmergedTree = true).assertExists()
        compose.onNodeWithText("库存充足").assertExists()
    }
}
