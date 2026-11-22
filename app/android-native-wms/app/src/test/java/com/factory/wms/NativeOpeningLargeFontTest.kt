package com.factory.wms

import android.app.Application
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.test.*
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.text.TextLayoutResult
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.dp
import androidx.test.core.app.ApplicationProvider
import com.factory.wms.data.api.RetrofitClient
import com.factory.wms.data.model.OpeningStockLine
import com.factory.wms.data.model.WarehouseDto
import com.factory.wms.ui.screens.OpeningStockScreen
import com.factory.wms.ui.theme.WmsTheme
import com.factory.wms.ui.viewmodel.opening.OpeningStockUiState
import com.factory.wms.ui.viewmodel.opening.OpeningStockViewModel
import kotlinx.coroutines.flow.MutableStateFlow
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
class NativeOpeningLargeFontTest(private val dark: Boolean) {
    companion object { @JvmStatic @Parameters fun cases() = listOf(arrayOf(false), arrayOf(true)) }
    @get:org.junit.Rule(order = Int.MIN_VALUE) val settings = WmsSettingsDataStoreRule()
    @get:Rule val compose = createEmptyComposeRule()
    private lateinit var activity: ActivityController<ComponentActivity>
    private lateinit var vm: OpeningStockViewModel
    @Suppress("UNCHECKED_CAST")
    @Before fun before() {
        RetrofitClient.setSession("http://127.0.0.1:9/", "synthetic-owner", 91)
        vm = OpeningStockViewModel(ApplicationProvider.getApplicationContext<Application>())
        val warehouse = WarehouseDto(1, "WH1", "一号仓")
        val state = OpeningStockViewModel::class.java.getDeclaredField("_uiState").also { it.isAccessible = true }.get(vm) as MutableStateFlow<OpeningStockUiState>
        state.value = OpeningStockUiState(warehouses = listOf(warehouse), selectedWarehouse = warehouse,
            lines = listOf(OpeningStockLine("WL-000238", 100.0, .35, materialName = "不锈钢内六角螺栓", materialSpec = "M8×30", materialUnit = "件")))
        activity = Robolectric.buildActivity(ComponentActivity::class.java).setup().visible()
        activity.get().setContent { CompositionLocalProvider(LocalDensity provides Density(1f, 2f)) {
            WmsTheme(darkTheme = dark) { OpeningStockScreen(vm, canEdit = true) {} }
        } }
    }
    @After fun after() { closeWmsTestViewModels(listOf(vm)); RetrofitClient.setToken(null); RetrofitClient.setBaseUrl(""); disposeComposeActivity(activity) }
    @Test fun quantityControlsAndSubmitRemainReachable() {
        compose.onNodeWithText("提交建账").assertIsDisplayed()
        for (value in listOf(vm.uiState.value.date, "WH1 一号仓")) {
            compose.onAllNodes(hasScrollAction()).onFirst().performScrollToNode(hasText(value))
            val text = compose.onNodeWithText(value, useUnmergedTree = true)
            val layouts = mutableListOf<TextLayoutResult>()
            text.performSemanticsAction(SemanticsActions.GetTextLayoutResult) { it(layouts) }
            assertEquals("Context should remain on one line: $value", 1, layouts.single().lineCount)
            assertEquals("Context must not be truncated: $value", value.length,
                layouts.single().getLineEnd(0, visibleEnd = true))
            assertFalse("Context must not be ellipsized: $value", layouts.single().isLineEllipsized(0))
            text.assertIsDisplayed()
        }
        for (label in listOf("增加数量：WL-000238|", "减少数量：WL-000238|", "修改数量：WL-000238 ")) {
            compose.onAllNodes(hasScrollAction()).onFirst().performScrollToNode(hasContentDescription(label))
            val node = compose.onNodeWithContentDescription(label).performScrollTo()
            val bounds = node.getUnclippedBoundsInRoot()
            assertTrue("$label must be at least 48dp", bounds.right - bounds.left >= 48.dp && bounds.bottom - bounds.top >= 48.dp)
            node.assertIsDisplayed()
        }
        compose.onNodeWithContentDescription("增加数量：WL-000238|").performScrollTo().performClick()
        compose.runOnIdle { assertEquals(101.0, vm.uiState.value.lines.single().quantity, 0.0) }
    }
}
