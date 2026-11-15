package com.factory.wms

import android.app.Application
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.test.core.app.ApplicationProvider
import com.factory.wms.data.api.RetrofitClient
import com.factory.wms.data.model.ScanLine
import com.factory.wms.ui.navigation.Screen
import com.factory.wms.ui.navigation.navigatePrimary
import com.factory.wms.ui.screens.ScanScreenBase
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
class NativeQuantityNavigationTest {
    @get:org.junit.Rule(order = Int.MIN_VALUE) val settings = WmsSettingsDataStoreRule()
    @get:Rule val compose = createEmptyComposeRule()
    private lateinit var activity: ActivityController<ComponentActivity>
    private lateinit var nav: NavHostController
    private lateinit var vm: ScanViewModel

    @Before fun before() {
        RetrofitClient.setSession("http://127.0.0.1:9/", "synthetic-owner", 91)
        vm = ScanViewModel(ApplicationProvider.getApplicationContext<Application>())
        vm.addScanLine(ScanLine("M001", 2.75, location_code = "A", material_name = "轴承", material_spec = "M8"))
        activity = Robolectric.buildActivity(ComponentActivity::class.java).setup().visible()
        activity.get().setContent {
            val controller = rememberNavController(); SideEffect { nav = controller }
            WmsTheme(darkTheme = false) {
                NavHost(controller, startDestination = Screen.Home.route) {
                    composable(Screen.Home.route) { Text("首页") }
                    composable(Screen.Login.route) { Text("登录") }
                    composable(Screen.Inbound.route) {
                        val state by vm.uiState.collectAsState()
                        ScanScreenBase("入库", "合成验证", CardBlue, { controller.popBackStack() },
                            state.scanLines, state.totalQuantity, vm, remember { SnackbarHostState() },
                            false, false, {}, {}, "", "1", {}, {}, {}, { com.factory.wms.ui.screens.ScanBarcodeResult.Rejected }, {}, "提交入库", CardBlue)
                    }
                }
            }
        }
        compose.runOnIdle { nav.navigatePrimary(Screen.Inbound.route) }
    }

    @After fun after() {
        closeWmsTestViewModels(listOf(vm)); RetrofitClient.setToken(null); RetrofitClient.setBaseUrl("")
        val content = activity.get().findViewById<android.view.ViewGroup>(android.R.id.content)
        for (index in 0 until content.childCount) (content.getChildAt(index) as? androidx.compose.ui.platform.ComposeView)?.disposeComposition()
        disposeComposeActivity(activity)
    }

    @Test fun primaryTabRoundTripRestoresPendingInputAndStillBlocksSubmit() {
        compose.onNodeWithContentDescription("修改数量：M001 A").performScrollTo().performTextReplacement("12.5")
        compose.onNodeWithText("提交入库").assertIsNotEnabled()
        compose.runOnIdle { nav.navigatePrimary(Screen.Home.route) }
        compose.runOnIdle { nav.navigatePrimary(Screen.Inbound.route) }
        compose.onNodeWithContentDescription("修改数量：M001 A").performScrollTo().assertTextContains("12.5")
        compose.onNodeWithText("提交入库").assertIsNotEnabled()
        compose.onNodeWithText("确定数量").performScrollTo().performClick()
        compose.runOnIdle { assertEquals(12.5, vm.uiState.value.totalQuantity, 0.0) }
        compose.onNodeWithText("提交入库").assertIsEnabled()
    }

    @Test fun systemBackRequiresExplicitDiscardOrContinue() {
        compose.onNodeWithContentDescription("修改数量：M001 A").performScrollTo().performTextReplacement("12.5")
        compose.runOnIdle { activity.get().onBackPressedDispatcher.onBackPressed() }
        compose.onNodeWithText("数量尚未确认").assertIsDisplayed()
        compose.onNodeWithText("继续修改").performClick()
        compose.onNodeWithContentDescription("修改数量：M001 A").assertTextContains("12.5")
        compose.runOnIdle { assertEquals(2.75, vm.uiState.value.totalQuantity, 0.0) }
    }
    @Test fun forcedLoginMustNotSilentlyLosePendingQuantity() {
        compose.onNodeWithContentDescription("修改数量：M001 A").performScrollTo().performTextReplacement("12.5")
        compose.runOnIdle {
            nav.navigate(Screen.Login.route) { popUpTo(0) { inclusive = true } }
        }
        compose.runOnIdle { nav.navigate(Screen.Inbound.route) }
        compose.onNodeWithContentDescription("修改数量：M001 A").performScrollTo().assertTextContains("12.5")
        compose.onNodeWithText("提交入库").assertIsNotEnabled()
    }

    @Test fun explicitBackDiscardKeepsCommittedQuantityAndReenablesSubmit() {
        compose.onNodeWithContentDescription("修改数量：M001 A").performScrollTo().performTextReplacement("12.5")
        compose.runOnIdle { activity.get().onBackPressedDispatcher.onBackPressed() }
        compose.onNodeWithText("放弃输入并返回").performClick()
        compose.onNodeWithText("首页").assertIsDisplayed()
        compose.runOnIdle { nav.navigatePrimary(Screen.Inbound.route) }
        compose.onNodeWithContentDescription("修改数量：M001 A").performScrollTo().assertTextContains("2.75")
        compose.onNodeWithText("提交入库").assertIsEnabled()
        compose.runOnIdle { assertEquals(2.75, vm.uiState.value.totalQuantity, 0.0) }
    }

    @Test fun clearCancelRetainsPendingInputAndConfirmedClearRemovesIt() {
        compose.onNodeWithContentDescription("修改数量：M001 A").performScrollTo().performTextReplacement("12.5")
        compose.onNodeWithText("清空").performScrollTo().performClick()
        compose.onNodeWithText("清空物料清单？").assertIsDisplayed()
        compose.onNode(hasText("取消") and hasAnyAncestor(isDialog())).performClick()
        compose.onNodeWithContentDescription("修改数量：M001 A").performScrollTo().assertTextContains("12.5")
        compose.onNodeWithText("提交入库").assertIsNotEnabled()
        compose.onNodeWithText("清空").performScrollTo().performClick()
        compose.onNodeWithText("确认清空").performClick()
        compose.runOnIdle { assertTrue(vm.uiState.value.scanLines.isEmpty()); assertTrue(vm.uiState.value.quantityDrafts.isEmpty()) }
    }

    @Test fun removeCanBeCancelledBeforeExplicitlyRemovingOneLine() {
        compose.onNodeWithContentDescription("移除").performScrollTo().performClick()
        compose.onNodeWithText("确认移除物料").assertIsDisplayed()
        compose.onNodeWithText("取消").performClick()
        compose.runOnIdle { assertEquals(2.75, vm.uiState.value.totalQuantity, 0.0) }
        compose.onNodeWithContentDescription("移除").performScrollTo().performClick()
        compose.onNodeWithText("确认移除").performClick()
        compose.runOnIdle { assertTrue(vm.uiState.value.scanLines.isEmpty()) }
    }

}
