package com.factory.wms

import android.app.Application
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.compose.ui.text.TextLayoutResult
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.dp
import com.factory.wms.ui.screens.LoginForm
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
class NativeLoginLayoutTest(private val scale: Float, private val dark: Boolean) {
    companion object { @JvmStatic @Parameters fun cases() = listOf(1f, 2f).flatMap { s -> listOf(false, true).map { arrayOf<Any>(s, it) } } }
    @get:Rule val compose = createEmptyComposeRule()
    private lateinit var activity: ActivityController<ComponentActivity>
    private val address = "http://192.168.100.123:8080/synthetic-long-path"
    @Before fun before() {
        activity = Robolectric.buildActivity(ComponentActivity::class.java).setup().visible()
        activity.get().setContent { CompositionLocalProvider(LocalDensity provides Density(1f, scale)) {
            WmsTheme(darkTheme = dark) { LoginForm(address, false) { _, _, _ -> } }
        } }
    }
    @After fun after() = disposeComposeActivity(activity)
    @Test fun passwordToggleAndFullAddressRemainReachable() {
        compose.onNodeWithText("仓库工作台").performScrollTo().assertIsDisplayed()
        val toggle = compose.onNode(hasClickAction() and SemanticsMatcher.expectValue(SemanticsProperties.Role, Role.Button) and hasAnyDescendant(hasContentDescription("显示密码")), useUnmergedTree = true).performScrollTo()
        val bounds = toggle.getUnclippedBoundsInRoot()
        assertTrue(bounds.right - bounds.left >= 48.dp && bounds.bottom - bounds.top >= 48.dp)
        toggle.performClick()
        compose.onNodeWithContentDescription("隐藏密码", useUnmergedTree = true).assertExists()
        compose.onNodeWithText("连接设置").performScrollTo().performClick()
        val full = compose.onNode(hasText(address) and !hasSetTextAction(), useUnmergedTree = true).performScrollTo()
        val layouts = mutableListOf<TextLayoutResult>()
        full.performSemanticsAction(SemanticsActions.GetTextLayoutResult) { it(layouts) }
        assertEquals(address.length, layouts.single().getLineEnd(layouts.single().lineCount - 1, visibleEnd = true))
        val login = compose.onNode(hasClickAction() and hasText("登录")).performScrollTo()
        val hit = login.getUnclippedBoundsInRoot()
        assertTrue(hit.bottom - hit.top >= 52.dp)
    }
}
