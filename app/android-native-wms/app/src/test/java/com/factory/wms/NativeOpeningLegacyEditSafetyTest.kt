package com.factory.wms

import android.app.Application
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.test.core.app.ApplicationProvider
import com.factory.wms.data.api.RetrofitClient
import com.factory.wms.data.model.OpeningStockLine
import com.factory.wms.data.model.QuantityDraft
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
import org.robolectric.RobolectricTestRunner
import org.robolectric.android.controller.ActivityController
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [31], application = Application::class, qualifiers = "w320dp-h800dp-mdpi")
@GraphicsMode(GraphicsMode.Mode.NATIVE)
class NativeOpeningLegacyEditSafetyTest {
    @get:org.junit.Rule(order = Int.MIN_VALUE) val settings = WmsSettingsDataStoreRule()
    @get:Rule val compose = createEmptyComposeRule()
    private lateinit var activity: ActivityController<ComponentActivity>
    private lateinit var vm: OpeningStockViewModel
    private lateinit var line: OpeningStockLine
    @Suppress("UNCHECKED_CAST")
    @Before fun before() {
        RetrofitClient.setSession("http://127.0.0.1:9/", "synthetic-owner", 91)
        vm = OpeningStockViewModel(ApplicationProvider.getApplicationContext<Application>())
        val warehouse = WarehouseDto(1, "WH1", "一号仓")
        line = OpeningStockLine("WL-000238", 100.0, .35, materialName = "不锈钢内六角螺栓", materialSpec = "M8×30", materialUnit = "件")
        val state = OpeningStockViewModel::class.java.getDeclaredField("_uiState").also { it.isAccessible = true }.get(vm) as MutableStateFlow<OpeningStockUiState>
        state.value = OpeningStockUiState(warehouses = listOf(warehouse), selectedWarehouse = warehouse, lines = listOf(line))
        activity = Robolectric.buildActivity(ComponentActivity::class.java).setup().visible()
    }
    @After fun after() { closeWmsTestViewModels(listOf(vm)); RetrofitClient.setToken(null); RetrofitClient.setBaseUrl(""); disposeComposeActivity(activity) }
    private fun show() { activity.get().setContent { WmsTheme { OpeningStockScreen(vm) {} } } }
    private fun openCard() {
        compose.onAllNodes(hasScrollAction()).onFirst().performScrollToNode(hasText("不锈钢内六角螺栓"))
        compose.onNode(hasClickAction() and hasAnyDescendant(hasText("不锈钢内六角螺栓")), useUnmergedTree = true).performScrollTo().performClick()
    }
    @Test fun unfinishedInlineDraftCannotBeOverriddenByOldDialog() {
        vm.setQuantityDraft(line.uiId, QuantityDraft("1.", 100.0, "请先确认数量"))
        show(); openCard()
        compose.onAllNodesWithText("修改数量：WL-000238").assertCountEquals(0)
        compose.runOnIdle { assertEquals("1.", vm.uiState.value.quantityDrafts[line.uiId]?.raw); assertEquals(100.0, vm.uiState.value.lines.single().quantity, 0.0) }
    }
    @Test fun staleDialogCannotOverwriteNewScanQuantity() {
        show(); openCard()
        compose.onNodeWithText("修改数量：WL-000238").assertIsDisplayed()
        compose.runOnIdle { assertTrue(vm.updateLineQuantityExpected(line.uiId, 100.0, 101.0)) }
        compose.onNode(hasSetTextAction() and hasText("数量（确切值）")).performTextReplacement("99")
        compose.onNodeWithText("确定").performClick()
        compose.runOnIdle { assertEquals(101.0, vm.uiState.value.lines.single().quantity, 0.0) }
        compose.onNodeWithText("物料已变化，请取消后重新打开").assertIsDisplayed()
    }
    @Test fun staleDialogCannotRemoveChangedLine() {
        show(); openCard()
        compose.onNodeWithText("修改数量：WL-000238").assertIsDisplayed()
        compose.runOnIdle { assertTrue(vm.updateLineQuantityExpected(line.uiId, 100.0, 101.0)) }
        compose.onNodeWithText("删除该行").performClick()
        compose.runOnIdle { assertEquals(101.0, vm.uiState.value.lines.single().quantity, 0.0) }
        compose.onNodeWithText("物料已变化，请取消后重新打开").assertIsDisplayed()
    }
    @Test fun unchangedLineCanStillBeEditedToZero() {
        show(); openCard()
        compose.onNode(hasSetTextAction() and hasText("数量（确切值）")).performTextReplacement("0")
        compose.onNodeWithText("确定").performClick()
        compose.runOnIdle { assertEquals(0.0, vm.uiState.value.lines.single().quantity, 0.0) }
        compose.onAllNodesWithText("修改数量：WL-000238").assertCountEquals(0)
    }
    @Test fun unchangedLineCanStillBeRemoved() {
        show(); openCard()
        compose.onNodeWithText("删除该行").performClick()
        compose.runOnIdle { assertTrue(vm.uiState.value.lines.isEmpty()) }
    }
    @Test fun cancellingLegacyEditPreservesOriginalQuantity() {
        show(); openCard()
        compose.onNode(hasSetTextAction() and hasText("数量（确切值）")).performTextReplacement("25")
        compose.onNodeWithText("取消").performClick()
        compose.runOnIdle { assertEquals(100.0, vm.uiState.value.lines.single().quantity, 0.0) }
    }

}
