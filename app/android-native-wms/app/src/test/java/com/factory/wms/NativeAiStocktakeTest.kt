package com.factory.wms

import android.app.Application
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.ui.test.*
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.compose.ui.unit.dp
import androidx.test.core.app.ApplicationProvider
import com.factory.wms.data.api.ExtractedMaterial
import com.factory.wms.data.api.RecognizeMaterialResult
import com.factory.wms.data.api.RetrofitClient
import com.factory.wms.data.model.MaterialDto
import com.factory.wms.data.model.ScanLine
import com.factory.wms.data.model.WarehouseDto
import com.factory.wms.data.model.CheckOrderDto
import com.factory.wms.ui.screens.StocktakeRecognizeScreen
import com.factory.wms.ui.theme.WmsTheme
import com.factory.wms.ui.viewmodel.ai.AiUiState
import com.factory.wms.ui.viewmodel.ai.AiViewModel
import com.factory.wms.ui.viewmodel.scan.ScanViewModel
import com.factory.wms.ui.viewmodel.scan.ScanUiState
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
class NativeAiStocktakeTest {
    @get:org.junit.Rule(order = Int.MIN_VALUE) val settings = WmsSettingsDataStoreRule()
    @get:Rule val compose = createEmptyComposeRule()
    private lateinit var activity: ActivityController<ComponentActivity>
    private lateinit var ai: AiViewModel
    private lateinit var scan: ScanViewModel
    private var returned = false

    private fun item(code: String, name: String, spec: String) = MaterialDto(
        1, code, name, null, spec, "件", "紧固件", null, null, null, null, null)

    @Suppress("UNCHECKED_CAST")
    @Before fun before() {
        RetrofitClient.setSession("http://127.0.0.1:9/", "synthetic-owner", 91)
        val app = ApplicationProvider.getApplicationContext<Application>()
        ai = AiViewModel(app); scan = ScanViewModel(app)
        val scanField = ScanViewModel::class.java.getDeclaredField("_uiState").also { it.isAccessible = true }
        (scanField.get(scan) as MutableStateFlow<ScanUiState>).value = ScanUiState(
            selectedWarehouse = WarehouseDto(1, "WH1", "一号仓"),
            selectedCheckOrder = CheckOrderDto(1, "PD-20261115-003"), selectedLocation = "A 区")
        val state = AiViewModel::class.java.getDeclaredField("_uiState").also { it.isAccessible = true }
        (state.get(ai) as MutableStateFlow<AiUiState>).value = AiUiState(recognizedMaterial = RecognizeMaterialResult(
            null, ExtractedMaterial(null, "内六角螺栓", "M8×30", null, .92, "银色、不锈钢、圆柱头"),
            listOf(item("WL-000238", "不锈钢内六角螺栓", "M8×30"),
                item("WL-000241", "镀锌内六角螺栓", "M8×30"),
                item("WL-000255", "不锈钢内六角螺栓", "M8×25")), 3))
        activity = Robolectric.buildActivity(ComponentActivity::class.java).setup().visible()
        activity.get().setContent { WmsTheme(darkTheme = false) { StocktakeRecognizeScreen(ai, scan) { returned = true } } }
    }
    @After fun after() {
        closeWmsTestViewModels(listOf(ai, scan))
        RetrofitClient.setToken(null); RetrofitClient.setBaseUrl("")
        val content = activity.get().findViewById<android.view.ViewGroup>(android.R.id.content)
        for (index in 0 until content.childCount) (content.getChildAt(index) as? androidx.compose.ui.platform.ComposeView)?.disposeComposition()
        disposeComposeActivity(activity)
    }
    @Test fun candidateRequiresHumanSelectionAndAllowsZero() {
        compose.onNodeWithText("盘点单：PD-20261115-003").assertIsDisplayed()
        compose.onNodeWithText("仓库：一号仓").assertIsDisplayed()
        compose.onNodeWithText("区域：A 区").assertIsDisplayed()
        compose.onNodeWithText("找到 3 个候选物料，请人工选择").performScrollTo().assertIsDisplayed()
        compose.onNodeWithText("加入盘点清单").performScrollTo().assertIsNotEnabled()
        compose.onNodeWithText("WL-000238").performScrollTo().performClick()
        compose.onNodeWithText("已人工选择").assertExists()
        for (id in listOf("减1", "加1")) {
            val node = compose.onNodeWithContentDescription(id).performScrollTo()
            val b = node.getUnclippedBoundsInRoot()
            assertTrue(b.right - b.left >= 48.dp && b.bottom - b.top >= 48.dp)
        }
        compose.onNode(hasSetTextAction()).performScrollTo().performTextReplacement("0")
        compose.onNodeWithText("加入盘点清单").performScrollTo().performClick()
        compose.runOnIdle {
            assertTrue(returned)
            assertEquals("WL-000238", scan.uiState.value.scanLines.single().material_code)
            assertEquals(0.0, scan.uiState.value.scanLines.single().quantity, 0.0)
        }
    }
    @Test fun invalidQuantityIsNotSilentlyConvertedToOne() {
        compose.onNodeWithText("WL-000238").performScrollTo().performClick()
        compose.onNode(hasSetTextAction()).performScrollTo().performTextReplacement("")
        compose.onNodeWithContentDescription("加1").performScrollTo().performClick()
        compose.onNode(hasSetTextAction()).assert(SemanticsMatcher.expectValue(SemanticsProperties.EditableText, AnnotatedString("")))
        compose.onNodeWithText("加入盘点清单").performScrollTo().performClick()
        compose.runOnIdle { assertTrue(scan.uiState.value.scanLines.isEmpty()); assertFalse(returned) }
    }
    @Test fun duplicateShowsBothOutcomesAndAccumulatesOnlyAfterConfirmation() {
        compose.runOnIdle { scan.addScanLine(ScanLine("WL-000238", 126.0, location_code = "A 区",
            material_name = "不锈钢内六角螺栓", material_spec = "M8×30", material_unit = "件")) }
        compose.onNodeWithText("WL-000238").performScrollTo().performClick()
        compose.onNode(hasSetTextAction()).performScrollTo().performTextReplacement("2")
        compose.onNodeWithText("加入盘点清单").performScrollTo().performClick()
        compose.onNodeWithText("该物料已盘点").assertIsDisplayed()
        compose.onNodeWithText("累加后 128 件；替换后 2 件").assertIsDisplayed()
        compose.runOnIdle { assertEquals(126.0, scan.uiState.value.totalQuantity, 0.0); assertFalse(returned) }
        compose.onNodeWithText("累加").performClick()
        compose.runOnIdle { assertEquals(128.0, scan.uiState.value.totalQuantity, 0.0); assertTrue(returned) }
    }

    @Test fun duplicateCancelPreservesAndReplacementUsesOnlyNewQuantity() {
        compose.runOnIdle { scan.addScanLine(ScanLine("WL-000238", 126.0, location_code = "A 区",
            material_name = "不锈钢内六角螺栓", material_spec = "M8×30", material_unit = "件")) }
        compose.onNodeWithText("WL-000238").performScrollTo().performClick()
        compose.onNode(hasSetTextAction()).performScrollTo().performTextReplacement("2")
        compose.onNodeWithText("加入盘点清单").performScrollTo().performClick()
        compose.onNodeWithText("取消").performClick()
        compose.runOnIdle { assertEquals(126.0, scan.uiState.value.totalQuantity, 0.0); assertFalse(returned) }
        compose.onNodeWithText("加入盘点清单").performScrollTo().performClick()
        compose.onNodeWithText("替换为本次数量").performClick()
        compose.runOnIdle { assertEquals(2.0, scan.uiState.value.totalQuantity, 0.0); assertTrue(returned) }
    }

}
