package com.factory.wms

import android.app.Application
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Column
import androidx.compose.material3.Text
import androidx.compose.material3.Button
import androidx.compose.runtime.*
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.compose.ui.unit.dp
import androidx.test.core.app.ApplicationProvider
import com.factory.wms.data.api.RetrofitClient
import com.factory.wms.data.model.ScanLine
import com.factory.wms.data.model.QuantityDraft
import com.factory.wms.ui.components.ScanQuantityStepper
import com.factory.wms.ui.theme.CardBlue
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
@Config(sdk = [31], application = Application::class, qualifiers = "w320dp-h800dp-mdpi")
@GraphicsMode(GraphicsMode.Mode.NATIVE)
class NativeQuantityStepperTest {
    @get:org.junit.Rule(order = Int.MIN_VALUE) val settings = WmsSettingsDataStoreRule()
    @get:Rule val compose = createEmptyComposeRule()
    private lateinit var activity: ActivityController<ComponentActivity>
    private lateinit var vm: ScanViewModel
    private var submitted = 0
    private val initial = ScanLine("M001", 2.75, location_code = "A", material_name = "轴承", material_spec = "M8")

    @Before fun before() {
        RetrofitClient.setSession("http://127.0.0.1:9/", "synthetic-owner", 91)
        vm = ScanViewModel(ApplicationProvider.getApplicationContext<Application>())
        vm.addScanLine(initial)
        activity = Robolectric.buildActivity(ComponentActivity::class.java).setup().visible()
    }

    @After fun after() {
        closeWmsTestViewModels(listOf(vm))
        RetrofitClient.setToken(null); RetrofitClient.setBaseUrl("")
        val content = activity.get().findViewById<android.view.ViewGroup>(android.R.id.content)
        for (index in 0 until content.childCount) (content.getChildAt(index) as? androidx.compose.ui.platform.ComposeView)?.disposeComposition()
        disposeComposeActivity(activity)
    }

    private fun render(allowZero: Boolean = false) {
        activity.get().setContent { WmsTheme(darkTheme = false) {
            val state by vm.uiState.collectAsState()
            var draft by remember { mutableStateOf<QuantityDraft?>(null) }
            Column {
                ScanQuantityStepper(state.scanLines.single(), true, allowZero, draft,
                    { draft = it }, { expected, number -> vm.updateScanLineQuantity(expected, number, allowZero) }, CardBlue)
                Button(onClick = { submitted++ }, enabled = draft == null) { Text("提交") }
            }
        } }
    }

    @Test fun stepAndExactDecimalEditRetainMaterialAndTotal() {
        render()
        for (id in listOf("减少数量：M001|A", "修改数量：M001 A", "增加数量：M001|A")) {
            val bounds = compose.onNodeWithContentDescription(id).getUnclippedBoundsInRoot()
            assertTrue("$id width < 48dp", bounds.right - bounds.left >= 48.dp)
            assertTrue("$id height < 48dp", bounds.bottom - bounds.top >= 48.dp)
        }
        compose.onNodeWithContentDescription("增加数量：M001|A").performClick()
        compose.runOnIdle { assertEquals(3.75, vm.uiState.value.scanLines.single().quantity, 0.0) }
        compose.onNodeWithContentDescription("减少数量：M001|A").performClick()
        compose.runOnIdle { assertEquals(2.75, vm.uiState.value.scanLines.single().quantity, 0.0) }
        compose.onNodeWithContentDescription("修改数量：M001 A").performTextReplacement("12.5")
        compose.onNodeWithText("提交").assertIsNotEnabled()
        compose.runOnIdle { assertEquals(2.75, vm.uiState.value.scanLines.single().quantity, 0.0) }
        compose.onNodeWithText("确定数量").performClick()
        compose.runOnIdle {
            assertEquals(initial.copy(quantity = 12.5), vm.uiState.value.scanLines.single())
            assertEquals(12.5, vm.uiState.value.totalQuantity, 0.0)
        }
        compose.onNodeWithText("提交").assertIsEnabled()
    }

    @Test fun rapidRepeatedStepsNeverLoseOrDuplicateAnIncrement() {
        render()
        compose.onNodeWithContentDescription("增加数量：M001|A").performTouchInput { repeat(20) { click(center) } }
        compose.runOnIdle { assertEquals(22.75, vm.uiState.value.scanLines.single().quantity, 0.0) }
        compose.onNodeWithContentDescription("减少数量：M001|A").performTouchInput { repeat(20) { click(center) } }
        compose.runOnIdle { assertEquals(2.75, vm.uiState.value.scanLines.single().quantity, 0.0) }
    }

    @Test fun invalidAndCancelledInputNeverChangesOrSubmitsTheOldNumber() {
        render()
        compose.onNodeWithContentDescription("修改数量：M001 A").performTextReplacement("")
        compose.onNodeWithText("请输入大于 0 的有效数量").assertIsDisplayed()
        compose.onNodeWithText("提交").assertIsNotEnabled()
        compose.runOnIdle { assertEquals(2.75, vm.uiState.value.totalQuantity, 0.0); assertEquals(0, submitted) }
        compose.onNodeWithText("取消").performClick()
        compose.onNodeWithText("提交").assertIsEnabled()
        compose.runOnIdle { assertEquals(2.75, vm.uiState.value.totalQuantity, 0.0) }
    }

    @Test fun stocktakeMayEnterZeroWhileNegativeIsRejected() {
        render(allowZero = true)
        compose.onNodeWithContentDescription("修改数量：M001 A").performTextReplacement("0")
        compose.onNodeWithText("确定数量").performClick()
        compose.runOnIdle { assertEquals(0.0, vm.uiState.value.totalQuantity, 0.0) }
        compose.onNodeWithContentDescription("修改数量：M001 A").performTextReplacement("-1")
        compose.onNodeWithText("提交").assertIsNotEnabled()
        compose.runOnIdle { assertEquals(0.0, vm.uiState.value.totalQuantity, 0.0) }
    }

    @Test fun concurrentScanIsNotOverwrittenByStaleDraft() {
        render()
        compose.onNodeWithContentDescription("修改数量：M001 A").performTextReplacement("10")
        compose.runOnIdle { vm.addScanLine(initial.copy(quantity = 1.0)) }
        compose.onNodeWithText("确定数量").performClick()
        compose.onNodeWithText("清单已变化，请取消修改后重新核对").assertIsDisplayed()
        compose.onNodeWithText("提交").assertIsNotEnabled()
        compose.runOnIdle { assertEquals(3.75, vm.uiState.value.totalQuantity, 0.0) }
        compose.onNodeWithText("取消").performClick()
        compose.runOnIdle { assertEquals(3.75, vm.uiState.value.totalQuantity, 0.0) }
    }
}
