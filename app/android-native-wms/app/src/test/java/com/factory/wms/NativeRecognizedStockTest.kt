package com.factory.wms

import android.app.Application
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.ui.test.*
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.text.TextLayoutResult
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.test.core.app.ApplicationProvider
import com.factory.wms.data.api.RecognizeMaterialResult
import com.factory.wms.data.api.ExtractedMaterial
import com.factory.wms.data.api.RetrofitClient
import com.factory.wms.data.model.MaterialDto
import com.factory.wms.ui.screens.ObjectRecognizeScreen
import com.factory.wms.ui.theme.WmsTheme
import com.factory.wms.ui.viewmodel.ai.AiUiState
import com.factory.wms.ui.viewmodel.ai.AiViewModel
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
class NativeRecognizedStockTest {
    @get:org.junit.Rule(order = Int.MIN_VALUE) val settings = WmsSettingsDataStoreRule()
    @get:Rule val compose = createEmptyComposeRule()
    private lateinit var activity: ActivityController<ComponentActivity>
    private lateinit var ai: AiViewModel

    @Suppress("UNCHECKED_CAST")
    @Before fun before() {
        RetrofitClient.setSession("http://127.0.0.1:9/", "synthetic-owner", 91)
        ai = AiViewModel(ApplicationProvider.getApplicationContext<Application>())
        fun item(code: String, stock: Double?, price: Double?) = MaterialDto(1, code, "合成物料", null, "M8×30", "件", "紧固件", null, stock, price, 20.0, 50.0)
        val field = AiViewModel::class.java.getDeclaredField("_uiState").also { it.isAccessible = true }
        (field.get(ai) as MutableStateFlow<AiUiState>).value = AiUiState(recognizedMaterial = RecognizeMaterialResult(
            null, ExtractedMaterial(null, "内六角螺栓", "M8×30", 24.0, .92, "银色"),
            listOf(item("WL-MISSING", null, null), item("WL-ZERO", 0.0, 0.0), item("WL-000238-LONG-CODE-2026-EXTRA", 128.0, .35)), 3))
        activity = Robolectric.buildActivity(ComponentActivity::class.java).setup().visible()
        activity.get().setContent { WmsTheme(darkTheme = false) { ObjectRecognizeScreen(ai, {}) } }
    }
    @After fun after() {
        closeWmsTestViewModels(listOf(ai)); RetrofitClient.setToken(null); RetrofitClient.setBaseUrl("")
        disposeComposeActivity(activity)
    }
    @Test fun recognizedSystemMatchesDistinguishMissingFromRealZero() {
        compose.onNodeWithText("未识别").performScrollTo().assertIsDisplayed()
        compose.onNodeWithText("约 24").performScrollTo().assertIsDisplayed()
        compose.onNodeWithText("图像识别置信度").performScrollTo().assertIsDisplayed()
        compose.onNodeWithText("92%").performScrollTo().assertIsDisplayed()
        compose.onNodeWithText("WL-MISSING").performScrollTo().assertIsDisplayed()
        compose.onNodeWithText("库存: 未获取").performScrollTo().assertIsDisplayed()
        compose.onNodeWithText("未获取").performScrollTo().assertIsDisplayed()
        compose.onNodeWithText("WL-ZERO").performScrollTo().assertIsDisplayed()
        compose.onNodeWithText("库存: 0").performScrollTo().assertIsDisplayed()
        compose.onNodeWithText("¥0.00").performScrollTo().assertIsDisplayed()
    }
    @Test fun matchedMaterialCodeIsFullyVisible() {
        val code = "WL-000238-LONG-CODE-2026-EXTRA"
        val node = compose.onNodeWithText(code, useUnmergedTree = true).performScrollTo()
        val layouts = mutableListOf<TextLayoutResult>()
        node.performSemanticsAction(SemanticsActions.GetTextLayoutResult) { it(layouts) }
        val layout = layouts.single()
        Assert.assertEquals(code.length, layout.getLineEnd(layout.lineCount - 1, visibleEnd = true))
        repeat(layout.lineCount) { Assert.assertFalse(layout.isLineEllipsized(it)) }
        node.assertIsDisplayed()
    }

}
