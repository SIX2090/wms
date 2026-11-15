package com.factory.wms

import android.app.Application
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.material3.SnackbarHostState
import androidx.compose.runtime.*
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.lifecycle.viewModelScope
import androidx.test.core.app.ApplicationProvider
import com.factory.wms.ui.screens.ScanScreenBase
import com.factory.wms.ui.theme.*
import com.factory.wms.ui.viewmodel.scan.ScanViewModel
import com.factory.wms.ui.util.toPositiveQtyOrNull
import kotlinx.coroutines.cancel
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.android.controller.ActivityController
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [31], application = Application::class, qualifiers = "w320dp-h800dp-mdpi")
@GraphicsMode(GraphicsMode.Mode.NATIVE)
class NativeEntryInteractionTest {
    @get:Rule val compose = createEmptyComposeRule()
    private lateinit var activity: ActivityController<ComponentActivity>
    private lateinit var vm: ScanViewModel

    @Before fun before() {
        activity = Robolectric.buildActivity(ComponentActivity::class.java).setup().visible()
    }
    @After fun after() {
        if (::vm.isInitialized) vm.viewModelScope.cancel()
        val content = activity.get().findViewById<android.view.ViewGroup>(android.R.id.content)
        for (index in 0 until content.childCount) {
            (content.getChildAt(index) as? androidx.compose.ui.platform.ComposeView)?.disposeComposition()
        }
        disposeComposeActivity(activity)
    }

    @Test fun manualQuantityErrorStaysVisibleAndDonePreservesInvalidInput() {
        DataStoreTestReset.resetWmsSettingsDataStore()
        vm = ScanViewModel(ApplicationProvider.getApplicationContext<Application>())
        var quantity by mutableStateOf("-1")
        var adds = 0
        activity.get().setContent { WmsTheme(darkTheme = false) {
            ScanScreenBase("入库", "合成界面验证", CardBlue, {}, emptyList(), 0.0, vm,
                remember { SnackbarHostState() }, false, true, {}, {}, "M-1", quantity,
                {}, { quantity = it }, { if (quantity.toPositiveQtyOrNull() != null) adds++ }, {}, {}, "提交入库", CardBlue)
        } }
        compose.onNodeWithText("请输入大于 0 的有效数量").assertIsDisplayed()
        compose.onNodeWithText("添加").assertIsNotEnabled()
        val field = compose.onNode(hasSetTextAction() and hasText("数量"))
        field.performImeAction()
        compose.runOnIdle { assertEquals("-1", quantity); assertEquals(0, adds) }
        field.performTextReplacement("2.75")
        compose.onNodeWithText("请输入大于 0 的有效数量").assertDoesNotExist()
        compose.onNodeWithText("添加").assertIsEnabled()
        field.performImeAction()
        compose.runOnIdle { assertEquals(1, adds); assertEquals("2.75", quantity) }
    }
}
