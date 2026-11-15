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
import com.factory.wms.ui.theme.WmsTheme
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
class NativeCrashReportLayoutTest(private val dark: Boolean, private val scale: Float) {
    companion object { @JvmStatic @Parameters fun cases() = listOf(arrayOf(false, 1f), arrayOf(false, 2f), arrayOf(true, 1f), arrayOf(true, 2f)) }
    @get:Rule val compose = createEmptyComposeRule()
    private lateinit var activity: ActivityController<ComponentActivity>
    private var dismissed = false
    @Before fun before() {
        activity = Robolectric.buildActivity(ComponentActivity::class.java).setup().visible()
        activity.get().setContent { CompositionLocalProvider(LocalDensity provides Density(1f, scale)) {
            WmsTheme(darkTheme = dark) { CrashReportScreen("SYNTHETIC TRACE\njava.lang.IllegalStateException: test", onDismiss = { dismissed = true }) }
        } }
    }
    @After fun after() { disposeComposeActivity(activity) }
    @Test fun crashMessageAndActionsRemainVisibleAndAccessible() {
        compose.onNodeWithText("检测到上次异常退出").assertIsDisplayed()
        compose.onNodeWithText("SYNTHETIC TRACE", substring = true).assertIsDisplayed()
        compose.onNodeWithText("复制崩溃信息").assertIsDisplayed().assertHasClickAction().assertHeightIsAtLeast(48f.dp)
        compose.onNodeWithText("我已记录，继续使用").assertIsDisplayed().assertHasClickAction().assertHeightIsAtLeast(48f.dp).performClick()
        Assert.assertTrue(dismissed)
    }
}
