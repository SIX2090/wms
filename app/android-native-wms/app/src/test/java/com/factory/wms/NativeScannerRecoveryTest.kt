package com.factory.wms

import android.app.Application
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.dp
import com.factory.wms.ui.components.ScannerUnavailableContent
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
class NativeScannerRecoveryTest(private val scale: Float) {
    companion object { @JvmStatic @Parameters fun cases() = listOf(arrayOf(1f), arrayOf(2f)) }
    @get:Rule val compose = createEmptyComposeRule()
    private lateinit var activity: ActivityController<ComponentActivity>
    private var manual = 0
    private var retry = 0
    @Before fun before() {
        activity = Robolectric.buildActivity(ComponentActivity::class.java).setup().visible()
        activity.get().setContent {
            CompositionLocalProvider(LocalDensity provides Density(1f, scale)) {
                WmsTheme { Box(Modifier.fillMaxSize().background(Color.Black)) {
                    ScannerUnavailableContent({ manual++ }, { retry++ })
                } }
            }
        }
    }
    @After fun after() = disposeComposeActivity(activity)
    @Test fun recoveryActionsAreVisibleDistinctAndReachable() {
        compose.onNodeWithText("摄像头不可用").assertIsDisplayed()
        compose.onNodeWithText("无法使用摄像头，可改为手动输入编码").assertIsDisplayed()
        val first = compose.onNodeWithText("手动输入")
        val second = compose.onNodeWithText("重试")
        first.assertIsDisplayed(); second.assertIsDisplayed()
        val firstButton = compose.onNode(hasClickAction() and hasText("手动输入"))
        val secondButton = compose.onNode(hasClickAction() and hasText("重试"))
        val a = firstButton.getUnclippedBoundsInRoot(); val b = secondButton.getUnclippedBoundsInRoot()
        assertTrue(a.right - a.left >= 48.dp && a.bottom - a.top >= 48.dp)
        assertTrue(b.right - b.left >= 48.dp && b.bottom - b.top >= 48.dp)
        assertTrue(a.right <= b.left)
        firstButton.performClick(); secondButton.performClick()
        compose.runOnIdle { assertEquals(1, manual); assertEquals(1, retry) }
    }
}
