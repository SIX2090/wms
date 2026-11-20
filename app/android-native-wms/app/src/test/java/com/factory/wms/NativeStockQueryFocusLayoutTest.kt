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
        Assert.assertEquals(32.dp, bounds.right - bounds.left)
        Assert.assertEquals(32.dp, bounds.bottom - bounds.top)
    }

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
