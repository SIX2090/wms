package com.factory.wms

import android.app.Application
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.test.core.app.ApplicationProvider
import com.factory.wms.data.api.RetrofitClient
import com.factory.wms.data.model.OpeningStockDto
import com.factory.wms.ui.screens.BuiltItemCard
import com.factory.wms.ui.screens.OpeningStockScreen
import com.factory.wms.ui.theme.WmsTheme
import com.factory.wms.ui.viewmodel.opening.OpeningStockViewModel
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
class NativeOpeningMissingValueTest {
    @get:org.junit.Rule(order = Int.MIN_VALUE) val settings = WmsSettingsDataStoreRule()
    @get:Rule val compose = createEmptyComposeRule()
    private lateinit var activity: ActivityController<ComponentActivity>
    private lateinit var vm: OpeningStockViewModel
    private fun item(quantity: Double?, price: Double?) = OpeningStockDto(
        id = 7, materialCode = "WL-000238-EXTRA-LONG", materialName = "不锈钢内六角螺栓", spec = "M8×30",
        unit = "件", warehouseId = 1, warehouseName = "一号仓", date = "2026-11-15",
        quantity = quantity, price = price, amount = null)
    @Before fun before() {
        RetrofitClient.setSession("http://127.0.0.1:9/", "synthetic-owner", 91)
        vm = OpeningStockViewModel(ApplicationProvider.getApplicationContext<Application>())
        activity = Robolectric.buildActivity(ComponentActivity::class.java).setup().visible()
    }
    @After fun after() { closeWmsTestViewModels(listOf(vm)); RetrofitClient.setToken(null); RetrofitClient.setBaseUrl(""); disposeComposeActivity(activity) }
    @Test fun missingQuantityIsNotRenderedAsZero() {
        activity.get().setContent { WmsTheme { BuiltItemCard(item(null, null)) {} } }
        compose.onNodeWithText("数量未获取").assertIsDisplayed()
        compose.onAllNodesWithText("0", substring = false).assertCountEquals(0)
    }
    @Test fun realZeroRemainsVisible() {
        activity.get().setContent { WmsTheme { BuiltItemCard(item(0.0, 0.0)) {} } }
        compose.onNodeWithText("0 件").assertIsDisplayed()
        compose.onAllNodesWithText("数量未获取").assertCountEquals(0)
    }
    @Test fun readOnlyRoleCanSelectWarehouseWithoutEntryOrEditActions() {
        vm.startEditing(item(2.0, 5.0))
        activity.get().setContent { WmsTheme { OpeningStockScreen(vm, canEdit = false) {} } }
        compose.onNodeWithText("选择仓库").performClick()
        compose.onNode(isDialog()).assertExists()
        compose.onAllNodesWithText("保存").assertCountEquals(0)
        compose.onAllNodesWithText("扫码录入").assertCountEquals(0)
    }
    @Test fun readOnlyRowShowsQuantityWithoutEditAction() {
        activity.get().setContent { WmsTheme { BuiltItemCard(item(2.0, 5.0), onClick = null) } }
        compose.onNodeWithText("2 件").assertIsDisplayed()
        compose.onAllNodesWithContentDescription("编辑").assertCountEquals(0)
    }
    @Test fun missingOriginalCannotBeSubmittedEvenViaViewModel() {
        vm.startEditing(item(null, null))
        vm.submitEdit(1.0, 1.0)
        assertFalse(vm.uiState.value.updating)
        assertTrue(vm.uiState.value.error.orEmpty().contains("未获取"))
        assertNotNull(vm.uiState.value.editingItem)
    }
    @Test fun dialogExplainsUnavailableValuesAndDisablesSave() {
        vm.startEditing(item(null, null))
        activity.get().setContent { WmsTheme { OpeningStockScreen(vm, canEdit = true) {} } }
        compose.onNodeWithText("原数量或单价未获取，请刷新后重试").assertIsDisplayed()
        compose.onNodeWithText("保存").assertIsNotEnabled()
    }
}
