package com.factory.wms

import android.app.Application
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.material3.MaterialTheme
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.compose.ui.text.TextLayoutResult
import androidx.compose.ui.unit.sp
import com.factory.wms.ui.navigation.Screen
import com.factory.wms.ui.navigation.WmsBottomBar
import com.factory.wms.ui.navigation.bottomTabs
import com.factory.wms.ui.theme.WmsTheme
import com.factory.wms.ui.theme.contrastRatio
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
class NativeBottomNavigationContrastTest(private val dark: Boolean) {
    companion object { @JvmStatic @Parameters(name = "dark={0}") fun cases() = listOf(arrayOf(false), arrayOf(true)) }
    @get:Rule val compose = createEmptyComposeRule()
    private lateinit var activity: ActivityController<ComponentActivity>
    private var background = Color.Unspecified
    @Before fun before() {
        activity = Robolectric.buildActivity(ComponentActivity::class.java).setup().visible()
        activity.get().setContent { WmsTheme(darkTheme = dark) {
            background = MaterialTheme.colorScheme.primaryContainer
            WmsBottomBar(Screen.Home.route, bottomTabs(), {})
        } }
    }
    @After fun after() = disposeComposeActivity(activity)
    @Test fun allFiveVisibleLabelsMeetContrastAndMinimumFontSize() {
        for (label in listOf("首页", "入库", "出库", "查库存", "我的")) {
            val results = mutableListOf<TextLayoutResult>()
            compose.onNodeWithText(label, useUnmergedTree = true)
                .performSemanticsAction(SemanticsActions.GetTextLayoutResult) { it(results) }
            assertEquals(1, results.size)
            assertTrue("$label font is below 14sp", results.single().layoutInput.style.fontSize >= 14.sp)
            val foreground = results.single().layoutInput.style.color
            assertTrue("$label contrast is ${contrastRatio(foreground, background)}", contrastRatio(foreground, background) >= 4.5f)
        }
    }
}
