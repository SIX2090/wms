package com.factory.wms

import android.app.Application
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.dp
import com.factory.wms.data.model.WarehouseDto
import com.factory.wms.ui.components.WarehouseSelector
import com.factory.wms.ui.theme.WmsTheme
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
class NativeWarehouseSelectorTouchTest(private val scale: Float, private val dark: Boolean) {
    companion object { @JvmStatic @Parameters fun cases() = listOf(1f, 2f).flatMap { s -> listOf(false, true).map { d -> arrayOf<Any>(s, d) } } }
    @get:Rule val compose = createEmptyComposeRule()
    private lateinit var activity: ActivityController<ComponentActivity>
    private var selected: String? = null
    @Before fun before() {
        val warehouses = listOf(WarehouseDto(1, "WH1", "一号仓"), WarehouseDto(2, "WH2", "二号仓"))
        activity = Robolectric.buildActivity(ComponentActivity::class.java).setup().visible()
        activity.get().setContent { CompositionLocalProvider(LocalDensity provides Density(1f, scale)) {
            WmsTheme(darkTheme = dark) { WarehouseSelector("一号仓", warehouses, "1", { selected = it }, allowAll = false, showDefaultWarehouse = false) }
        } }
    }
    @After fun after() { disposeComposeActivity(activity) }
    @Test fun selectorHas48DpTargetAndRetainsWarehouseSelection() {
        val button = compose.onNode(hasClickAction() and hasAnyDescendant(hasText("一号仓")), useUnmergedTree = true).assertIsDisplayed()
        val bounds = button.getUnclippedBoundsInRoot()
        assertTrue(bounds.right - bounds.left >= 48.dp && bounds.bottom - bounds.top >= 48.dp)
        button.performClick()
        compose.onNodeWithText("二号仓").assertIsDisplayed().performClick()
        assertEquals("2", selected)
    }
}
