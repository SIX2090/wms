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
import com.factory.wms.data.model.MaterialArchiveDto
import com.factory.wms.data.model.MaterialArchiveImageDto
import com.factory.wms.ui.screens.MaterialArchiveDetailScreen
import com.factory.wms.ui.theme.WmsTheme
import com.factory.wms.ui.viewmodel.archive.MaterialArchiveUiState
import com.factory.wms.ui.viewmodel.archive.MaterialArchiveViewModel
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
class NativeArchiveImagesTest(private val scale: Float, private val dark: Boolean) {
    companion object { @JvmStatic @Parameters fun cases() = listOf(1f, 2f).flatMap { s -> listOf(false, true).map { arrayOf<Any>(s, it) } } }
    @get:org.junit.Rule(order = Int.MIN_VALUE) val settings = WmsSettingsDataStoreRule()
    @get:Rule val compose = createEmptyComposeRule()
    private lateinit var activity: ActivityController<ComponentActivity>
    private lateinit var vm: MaterialArchiveViewModel
    @Suppress("UNCHECKED_CAST")
    @Before fun before() {
        RetrofitClient.setSession("http://127.0.0.1:9/", "synthetic-owner", 91)
        vm = MaterialArchiveViewModel(ApplicationProvider.getApplicationContext<Application>())
        val state = MaterialArchiveViewModel::class.java.getDeclaredField("_uiState").also { it.isAccessible = true }.get(vm) as MutableStateFlow<MaterialArchiveUiState>
        state.value = MaterialArchiveUiState(images = (1..4).map { MaterialArchiveImageDto(it, null, null, null, null) })
        // null ID suppresses all HTTP loading and printer operations; four entries are synthetic.
        val material = MaterialArchiveDto(null, "WL-000238-LONG-CODE-2026-EXTRA", "不锈钢内六角螺栓", "M8×30", "件", "紧固件", 4)
        activity = Robolectric.buildActivity(ComponentActivity::class.java).setup().visible()
        activity.get().setContent { CompositionLocalProvider(LocalDensity provides Density(1f, scale)) {
            WmsTheme(darkTheme = dark) { MaterialArchiveDetailScreen(material, vm) {} }
        } }
    }
    @After fun after() { closeWmsTestViewModels(listOf(vm)); RetrofitClient.setToken(null); RetrofitClient.setBaseUrl(""); disposeComposeActivity(activity) }
    @Test fun fourImagesAndAddEntryRemainReachable() {
        compose.onNodeWithText("物料图片 4/5").performScrollTo().assertIsDisplayed()
        for (number in 1..4) compose.onNodeWithText(number.toString(), useUnmergedTree = true).assertExists()
        val add = compose.onNode(hasClickAction() and hasText("添加图片")).performScrollTo().assertIsDisplayed()
        val bounds = add.getUnclippedBoundsInRoot()
        assertTrue(bounds.right - bounds.left >= 48.dp && bounds.bottom - bounds.top >= 48.dp)
        val deletes = compose.onAllNodes(hasClickAction() and hasAnyDescendant(hasContentDescription("删除")), useUnmergedTree = true)
        deletes.assertCountEquals(4)
        repeat(4) { index ->
            val hit = deletes[index].getUnclippedBoundsInRoot()
            assertTrue(hit.right - hit.left >= 48.dp && hit.bottom - hit.top >= 48.dp)
        }
        compose.onNodeWithText("拍照上传").performScrollTo().assertIsDisplayed()
        compose.onNodeWithText("相册上传").performScrollTo().assertIsDisplayed()
        compose.onNodeWithText("打印标签").performScrollTo().assertIsDisplayed()
    }
    @Test fun materialCodeRemainsFullyReadableBesideImageCount() {
        val code = "WL-000238-LONG-CODE-2026-EXTRA"
        val node = compose.onNodeWithText(code, useUnmergedTree = true).performScrollTo()
        val layouts = mutableListOf<TextLayoutResult>()
        node.performSemanticsAction(SemanticsActions.GetTextLayoutResult) { it(layouts) }
        val layout = layouts.single()
        assertEquals(code.length, layout.getLineEnd(layout.lineCount - 1, visibleEnd = true))
        repeat(layout.lineCount) { assertFalse(layout.isLineEllipsized(it)) }
        node.assertIsDisplayed()
    }

}
