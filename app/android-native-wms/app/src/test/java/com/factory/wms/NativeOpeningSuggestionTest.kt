package com.factory.wms

import android.app.Application
import android.content.res.Configuration
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.compose.ui.text.TextLayoutResult
import androidx.compose.ui.unit.Density
import androidx.test.core.app.ApplicationProvider
import com.factory.wms.data.api.RetrofitClient
import com.factory.wms.data.model.MaterialDto
import com.factory.wms.data.model.WarehouseDto
import com.factory.wms.ui.screens.OpeningStockScreen
import com.factory.wms.ui.theme.WmsTheme
import com.factory.wms.ui.viewmodel.opening.OpeningStockUiState
import com.factory.wms.ui.viewmodel.opening.OpeningStockViewModel
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
class NativeOpeningSuggestionTest(private val dark: Boolean, private val scale: Float) {
    companion object { @JvmStatic @Parameters fun cases() = listOf(arrayOf(false, 1f), arrayOf(false, 2f), arrayOf(true, 1f), arrayOf(true, 2f)) }
    @get:org.junit.Rule(order = Int.MIN_VALUE) val settings = WmsSettingsDataStoreRule()
    @get:Rule val compose = createEmptyComposeRule()
    private lateinit var activity: ActivityController<ComponentActivity>
    private lateinit var vm: OpeningStockViewModel
    private lateinit var state: MutableStateFlow<OpeningStockUiState>
    private lateinit var originalConfiguration: Configuration
    @Suppress("UNCHECKED_CAST")
    @Before fun before() {
        RetrofitClient.setSession("http://127.0.0.1:9/", "synthetic-owner", 91)
        vm = OpeningStockViewModel(ApplicationProvider.getApplicationContext<Application>())
        state = OpeningStockViewModel::class.java.getDeclaredField("_uiState").also { it.isAccessible = true }.get(vm) as MutableStateFlow<OpeningStockUiState>
        val warehouse = WarehouseDto(1, "WH1", "一号仓")
        state.value = OpeningStockUiState(warehouses = listOf(warehouse), selectedWarehouse = warehouse)
        activity = Robolectric.buildActivity(ComponentActivity::class.java).setup().visible()
        val resources = activity.get().resources
        originalConfiguration = Configuration(resources.configuration)
        val scaled = Configuration(originalConfiguration).apply { fontScale = scale }
        @Suppress("DEPRECATION")
        resources.updateConfiguration(scaled, resources.displayMetrics)
        activity.get().setContent { CompositionLocalProvider(LocalDensity provides Density(1f, scale)) {
            WmsTheme(darkTheme = dark) { OpeningStockScreen(vm) {} }
        } }
    }
    @After fun after() {
        closeWmsTestViewModels(listOf(vm)); RetrofitClient.setToken(null); RetrofitClient.setBaseUrl("")
        val resources = activity.get().resources
        @Suppress("DEPRECATION")
        resources.updateConfiguration(originalConfiguration, resources.displayMetrics)
        disposeComposeActivity(activity)
    }
    @Test fun longCodeAndNameAreReadableAndSelectionFillsTheCode() {
        compose.onNodeWithText("手动添加").assertIsDisplayed().performClick()
        compose.onNode(hasSetTextAction() and hasText("物料编码 / 名称 / 规格 / 品牌")).performTextInput("螺栓")
        val code = "WL-000238-EXTRA-LONG"
        val name = "不锈钢内六角螺栓"
        compose.runOnIdle {
            vm.clearMaterialSuggestions()
            state.value = state.value.copy(materialSuggestionsLoading = false,
                materialSuggestions = listOf(MaterialDto(1, code, name, "标准件优选", "M8×30", "件", "紧固件", null, null, null, null, null)))
        }
        val nameNode = compose.onNodeWithText(name, useUnmergedTree = true)
        val layouts = mutableListOf<TextLayoutResult>()
        nameNode.performSemanticsAction(SemanticsActions.GetTextLayoutResult) { it(layouts) }
        Assert.assertEquals("Dialog must use the requested system font scale", scale, layouts.single().layoutInput.density.fontScale, 0.001f)
        Assert.assertEquals(name, layouts.single().layoutInput.text.text)
        Assert.assertFalse("Name must not overflow", layouts.single().hasVisualOverflow)
        Assert.assertTrue("Name uses at most two lines", layouts.single().lineCount <= 2)
        nameNode.assertIsDisplayed()
        val codeNode = compose.onNodeWithText(code, useUnmergedTree = true)
        val codes = mutableListOf<TextLayoutResult>()
        codeNode.performSemanticsAction(SemanticsActions.GetTextLayoutResult) { it(codes) }
        Assert.assertFalse("Code must not overflow", codes.single().hasVisualOverflow)
        compose.onNode(hasClickAction() and hasAnyDescendant(hasText(name)), useUnmergedTree = true).performClick()
        compose.onNode(hasSetTextAction() and hasText(code)).assertExists()
    }
}
