package com.factory.wms

import android.app.Application
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.compose.ui.unit.dp
import androidx.test.core.app.ApplicationProvider
import com.factory.wms.data.api.RetrofitClient
import com.factory.wms.data.model.OpeningStockLine
import com.factory.wms.data.model.OpeningStockRequest
import com.factory.wms.data.model.WarehouseDto
import com.factory.wms.ui.screens.OpeningStockScreen
import com.factory.wms.ui.theme.WmsTheme
import com.factory.wms.ui.viewmodel.opening.OpeningStockUiState
import com.factory.wms.ui.viewmodel.opening.OpeningStockViewModel
import com.google.gson.Gson
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
@Config(sdk = [31], application = Application::class, qualifiers = "w360dp-h800dp-mdpi")
@GraphicsMode(GraphicsMode.Mode.NATIVE)
class NativeOpeningQuantityTest {
    @get:org.junit.Rule(order = Int.MIN_VALUE) val settings = WmsSettingsDataStoreRule()
    @get:Rule val compose = createEmptyComposeRule()
    private lateinit var activity: ActivityController<ComponentActivity>
    private lateinit var vm: OpeningStockViewModel
    private var returned = false
    @Suppress("UNCHECKED_CAST")
    @Before fun before() {
        RetrofitClient.setSession("http://127.0.0.1:9/", "synthetic-owner", 91)
        vm = OpeningStockViewModel(ApplicationProvider.getApplicationContext<Application>())
        val warehouse = WarehouseDto(1, "WH1", "一号仓")
        val state = OpeningStockViewModel::class.java.getDeclaredField("_uiState").also { it.isAccessible = true }.get(vm) as MutableStateFlow<OpeningStockUiState>
        state.value = OpeningStockUiState(warehouses = listOf(warehouse), selectedWarehouse = warehouse,
            lines = listOf(OpeningStockLine("WL-1", 5.5, .35, materialName = "合成螺栓", materialSpec = "M8×30", materialUnit = "件")))
        activity = Robolectric.buildActivity(ComponentActivity::class.java).setup().visible()
        activity.get().setContent { WmsTheme(darkTheme = false) { OpeningStockScreen(vm, canEdit = true) { returned = true } } }
    }
    @After fun after() { closeWmsTestViewModels(listOf(vm)); RetrofitClient.setToken(null); RetrofitClient.setBaseUrl(""); disposeComposeActivity(activity) }
    private fun control(label: String): SemanticsNodeInteraction {
        compose.onAllNodes(hasScrollAction()).onFirst().performScrollToNode(hasContentDescription(label))
        return compose.onNodeWithContentDescription(label)
    }
    private fun input() = control("修改数量：WL-1 ")
    @Test fun inlineControlsAllowDecimalInputAndZero() {
        for (label in listOf("增加数量：WL-1|", "减少数量：WL-1|", "修改数量：WL-1 ")) {
            val bounds = control(label).performScrollTo().getUnclippedBoundsInRoot()
            assertTrue("$label must be at least 48dp", bounds.right - bounds.left >= 48.dp && bounds.bottom - bounds.top >= 48.dp)
        }
        control("增加数量：WL-1|").performScrollTo().performClick().performClick()
        control("减少数量：WL-1|").performScrollTo().performClick()
        compose.runOnIdle { assertEquals(6.5, vm.uiState.value.lines.single().quantity, 0.0) }
        input().performScrollTo().performTextReplacement("2.25")
        compose.onNodeWithText("确定数量").performScrollTo().performClick()
        compose.runOnIdle { assertEquals(2.25, vm.uiState.value.lines.single().quantity, 0.0) }
        input().performScrollTo().performTextReplacement("0")
        compose.onNodeWithText("确定数量").performScrollTo().performClick()
        compose.runOnIdle { assertEquals(0.0, vm.uiState.value.lines.single().quantity, 0.0) }
    }
    @Test fun incompleteInputBlocksSubmissionAndCanBeCancelled() {
        input().performScrollTo().performTextReplacement("")
        compose.onNodeWithText("提交建账").assertIsNotEnabled()
        compose.runOnIdle { vm.submit(); assertEquals(5.5, vm.uiState.value.lines.single().quantity, 0.0) }
        compose.onNodeWithText("取消").performScrollTo().performClick()
        compose.runOnIdle { assertTrue(vm.uiState.value.quantityDrafts.isEmpty()); assertEquals(5.5, vm.uiState.value.lines.single().quantity, 0.0) }
    }
    @Test fun staleEditDoesNotOverwriteANewScanAndBackRequiresAChoice() {
        input().performScrollTo().performTextReplacement("8")
        compose.runOnIdle { vm.addLine("WL-1", 1.0) }
        compose.onNodeWithText("确定数量").performScrollTo().performClick()
        compose.runOnIdle { assertEquals(6.5, vm.uiState.value.lines.single().quantity, 0.0) }
        compose.onNodeWithText("清单已变化，请取消修改后重新核对").assertExists()
        compose.onNodeWithContentDescription("返回").performClick()
        compose.onNodeWithText("放弃未确认的数量？").assertIsDisplayed()
        compose.onNodeWithText("继续修改").performClick()
        assertFalse(returned)
    }
    @Test fun undoRemovalRestoresTheUnconfirmedInput() {
        input().performScrollTo().performTextReplacement("2.25")
        compose.onNodeWithContentDescription("移除").performScrollTo().performClick()
        compose.runOnIdle { assertTrue(vm.uiState.value.lines.isEmpty()) }
        compose.onNodeWithText("撤销").performClick()
        compose.runOnIdle {
            assertEquals("2.25", vm.uiState.value.quantityDrafts.values.single().raw)
            assertEquals(5.5, vm.uiState.value.lines.single().quantity, 0.0)
        }
        input().performScrollTo().assertTextEquals("2.25")
    }
    @Test fun uiOnlyIdentityAndUnitDoNotChangeTheRequestBody() {
        val line = vm.uiState.value.lines.single()
        val json = Gson().toJson(OpeningStockRequest("2026-11-15", "WH1", listOf(line)))
        assertTrue(json.contains("WL-1")); assertTrue(json.contains("5.5")); assertTrue(json.contains("0.35"))
        assertFalse(json.contains("uiId")); assertFalse(json.contains("materialUnit")); assertFalse(json.contains("合成螺栓"))
        assertEquals(json, Gson().toJson(Gson().fromJson(json, OpeningStockRequest::class.java)))
    }
}
