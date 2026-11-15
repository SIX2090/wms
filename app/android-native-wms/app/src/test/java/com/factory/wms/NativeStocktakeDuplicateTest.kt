package com.factory.wms

import android.app.Application
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.compose.ui.unit.dp
import androidx.test.core.app.ApplicationProvider
import com.factory.wms.data.api.RetrofitClient
import com.factory.wms.data.model.ScanLine
import com.factory.wms.data.model.QuantityDraft
import com.factory.wms.ui.screens.StocktakeDuplicateDialog
import com.factory.wms.ui.theme.WmsTheme
import com.factory.wms.ui.viewmodel.scan.ScanViewModel
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
class NativeStocktakeDuplicateTest {
    @get:org.junit.Rule(order = Int.MIN_VALUE) val settings = WmsSettingsDataStoreRule()
    @get:Rule val compose = createEmptyComposeRule()
    private lateinit var activity: ActivityController<ComponentActivity>
    private lateinit var vm: ScanViewModel
    private val original = ScanLine("WL-000238", 126.0, location_code = "A-01-03", material_name = "不锈钢内六角螺栓", material_spec = "M8×30", material_unit = "件")
    private val incoming = ScanLine("WL-000238", 2.0, location_code = "A-01-03")
    private var dismissed = false
    @Before fun before() {
        RetrofitClient.setSession("http://127.0.0.1:9/", "synthetic-owner", 91)
        vm = ScanViewModel(ApplicationProvider.getApplicationContext<Application>())
        vm.addScanLine(original)
        activity = Robolectric.buildActivity(ComponentActivity::class.java).setup().visible()
        activity.get().setContent { WmsTheme(darkTheme = false) { StocktakeDuplicateDialog(incoming, original, vm) { dismissed = true } } }
    }
    @After fun after() { closeWmsTestViewModels(listOf(vm)); RetrofitClient.setToken(null); RetrofitClient.setBaseUrl(""); disposeComposeActivity(activity) }
    @Test fun accumulateExplainsTheResultAndRequiresConfirmation() {
        compose.onNodeWithText("该物料已盘点").assertIsDisplayed()
        compose.onNodeWithText("原实盘：126 件；本次：2 件").assertIsDisplayed()
        compose.onNodeWithText("累加后 128 件；替换后 2 件").assertIsDisplayed()
        for (label in listOf("累加", "替换为本次数量", "取消")) {
            val bounds = compose.onNodeWithText(label).getUnclippedBoundsInRoot()
            assertTrue(bounds.bottom - bounds.top >= 48.dp)
        }
        compose.onNodeWithText("累加").performClick()
        compose.runOnIdle { assertEquals(128.0, vm.uiState.value.totalQuantity, 0.0); assertTrue(dismissed) }
    }
    @Test fun replacementUsesOnlyNewQuantity() {
        compose.onNodeWithText("替换为本次数量").performClick()
        compose.runOnIdle { assertEquals(2.0, vm.uiState.value.totalQuantity, 0.0); assertTrue(dismissed) }
    }
    @Test fun cancelKeepsOriginalAndAStaleRecordCannotBeOverwritten() {
        compose.runOnIdle { vm.addScanLine(incoming.copy(quantity = 1.0)) }
        compose.onNodeWithText("替换为本次数量").performClick()
        compose.onNodeWithText("原明细已变化或当前不可修改，请取消后重新核对。").assertIsDisplayed()
        compose.runOnIdle { assertEquals(127.0, vm.uiState.value.totalQuantity, 0.0); assertFalse(dismissed) }
        compose.onNodeWithText("取消").performClick()
        assertTrue(dismissed)
    }
    @Test fun pendingDirectInputIsPreservedUntilExplicitlyResolved() {
        compose.runOnIdle { vm.setQuantityDraft("9:WL-0002387:A-01-03", QuantityDraft("130", 126.0, "")) }
        compose.onNodeWithText("累加").performClick()
        compose.onNodeWithText("请先确定或取消该物料正在修改的数量。").assertIsDisplayed()
        compose.runOnIdle {
            assertEquals(126.0, vm.uiState.value.totalQuantity, 0.0)
            assertEquals("130", vm.uiState.value.quantityDrafts.values.single().raw)
            assertFalse(dismissed)
        }
    }
}
