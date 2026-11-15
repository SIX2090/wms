package com.factory.wms

import android.app.Application
import android.content.res.Configuration
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.material3.SnackbarHostState
import androidx.compose.runtime.remember
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.compose.ui.text.TextLayoutResult
import androidx.test.core.app.ApplicationProvider
import com.factory.wms.data.model.MaterialDto
import com.factory.wms.ui.screens.ScanBarcodeResult
import com.factory.wms.ui.screens.ScanScreenBase
import com.factory.wms.ui.theme.CardBlue
import com.factory.wms.ui.theme.WmsTheme
import com.factory.wms.ui.viewmodel.scan.ScanViewModel
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
class NativeScanSuggestionTest(private val scale: Float, private val dark: Boolean) {
    companion object { @JvmStatic @Parameters fun cases() = listOf(1f, 2f).flatMap { s -> listOf(false, true).map { arrayOf<Any>(s, it) } } }
    @get:org.junit.Rule(order = Int.MIN_VALUE) val settings = WmsSettingsDataStoreRule()
    @get:Rule val compose = createEmptyComposeRule()
    private lateinit var activity: ActivityController<ComponentActivity>
    private lateinit var vm: ScanViewModel
    private lateinit var original: Configuration
    private var selected: String? = null
    private val code = "WL-000238-LONG-CODE-2026-EXTRA"
    private val name = "不锈钢内六角螺栓"
    @Before fun before() {
        vm = ScanViewModel(ApplicationProvider.getApplicationContext<Application>())
        val material = MaterialDto(1, code, name, "标准件优选", "M8×30", "件", "紧固件", null, 128.0, .35, 20.0, 50.0)
        activity = Robolectric.buildActivity(ComponentActivity::class.java).setup().visible()
        val resources = activity.get().resources; original = Configuration(resources.configuration)
        @Suppress("DEPRECATION") resources.updateConfiguration(Configuration(original).apply { fontScale = scale }, resources.displayMetrics)
        activity.get().setContent { WmsTheme(darkTheme = dark) {
            ScanScreenBase("入库", "合成界面验证", CardBlue, {}, emptyList(), 0.0, vm,
                remember { SnackbarHostState() }, false, true, {}, {}, "螺栓", "1", {}, {}, {},
                { ScanBarcodeResult.Rejected }, {}, "提交入库", CardBlue,
                materialSuggestions = listOf(material), onMaterialSuggestionSelected = { selected = it.code })
        } }
    }
    @After fun after() {
        closeWmsTestViewModels(listOf(vm)); val resources = activity.get().resources
        @Suppress("DEPRECATION") resources.updateConfiguration(original, resources.displayMetrics)
        disposeComposeActivity(activity)
    }
    @Test fun codeAndNameRemainReadableAndSelectionUsesOriginalCode() {
        for (value in listOf(code, name)) {
            val node = compose.onNode(hasText(value) and hasAnyAncestor(isDialog()), useUnmergedTree = true)
            val layouts = mutableListOf<TextLayoutResult>()
            node.performSemanticsAction(SemanticsActions.GetTextLayoutResult) { it(layouts) }
            val layout = layouts.single()
            Assert.assertEquals("Dialog uses requested system font scale", scale, layout.layoutInput.density.fontScale, .001f)
            Assert.assertEquals(value.length, layout.getLineEnd(layout.lineCount - 1, visibleEnd = true))
            repeat(layout.lineCount) { Assert.assertFalse("Text cannot be ellipsized", layout.isLineEllipsized(it)) }
            node.assertIsDisplayed()
        }
        compose.onNode(hasClickAction() and hasAnyDescendant(hasText(name)) and hasAnyAncestor(isDialog()), useUnmergedTree = true).performClick()
        compose.runOnIdle { Assert.assertEquals(code, selected) }
    }
}
