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
import com.factory.wms.ui.components.WmsDateNavRow
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
class NativeDateNavigationTouchTest(private val scale: Float, private val dark: Boolean) {
    companion object { @JvmStatic @Parameters fun cases() = listOf(1f, 2f).flatMap { s -> listOf(false, true).map { arrayOf<Any>(s, it) } } }
    @get:Rule val compose = createEmptyComposeRule()
    private lateinit var activity: ActivityController<ComponentActivity>
    private var prev = 0; private var next = 0; private var reset = 0
    @Before fun before() {
        activity = Robolectric.buildActivity(ComponentActivity::class.java).setup().visible()
        activity.get().setContent { CompositionLocalProvider(LocalDensity provides Density(1f, scale)) {
            WmsTheme(darkTheme = dark) { WmsDateNavRow("2026-11-15", { prev++ }, { next++ },
                wrapInCard = false, onResetToday = { reset++ }, onDateSelected = {}) }
        } }
    }
    @After fun after() = disposeComposeActivity(activity)
    @Test fun dateControlsHave48DpTargetsAndRemainDistinct() {
        val previous = compose.onNode(hasClickAction() and hasAnyDescendant(hasContentDescription("前一天")), useUnmergedTree = true)
        val following = compose.onNode(hasClickAction() and hasAnyDescendant(hasContentDescription("后一天")), useUnmergedTree = true)
        val date = compose.onNode(hasClickAction() and hasText("2026-11-15"), useUnmergedTree = true)
        val today = compose.onNode(hasClickAction() and hasAnyDescendant(hasText("回到今天")), useUnmergedTree = true)
        for (node in listOf(previous, following, date, today)) {
            val b = node.assertIsDisplayed().getUnclippedBoundsInRoot()
            assertTrue(b.right - b.left >= 48.dp && b.bottom - b.top >= 48.dp)
        }
        previous.performClick(); following.performClick(); today.performClick()
        assertEquals(1, prev); assertEquals(1, next); assertEquals(1, reset)
    }
}
