package com.factory.wms

import android.app.Application
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.width
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.compositeOver
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.compose.ui.text.TextLayoutResult
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.dp
import com.factory.wms.ui.components.WmsPrimaryButton
import com.factory.wms.ui.components.WmsPillBadge
import com.factory.wms.ui.theme.*
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
class NativeReadabilityLayoutTest {
    @get:Rule val compose = createEmptyComposeRule()
    private lateinit var activity: ActivityController<ComponentActivity>

    @Before fun before() {
        activity = Robolectric.buildActivity(ComponentActivity::class.java).setup().visible()
    }
    @After fun after() {
        val content = activity.get().findViewById<android.view.ViewGroup>(android.R.id.content)
        for (index in 0 until content.childCount) {
            (content.getChildAt(index) as? androidx.compose.ui.platform.ComposeView)?.disposeComposition()
        }
        activity.pause().stop().destroy()
    }

    @Test fun primaryActionCanGrowInsteadOfClippingLargeText() {
        activity.get().setContent {
            CompositionLocalProvider(LocalDensity provides Density(1f, 2f)) {
                WmsTheme(darkTheme = false) {
                    WmsPrimaryButton("确认并保存当前单据", {},
                        modifier = Modifier.width(160.dp).testTag("action"), haptic = false)
                }
            }
        }
        val layouts = mutableListOf<TextLayoutResult>()
        compose.onNodeWithText("确认并保存当前单据", useUnmergedTree = true)
            .performSemanticsAction(SemanticsActions.GetTextLayoutResult) { it(layouts) }
        assertFalse(layouts.single().hasVisualOverflow)
        val bounds = compose.onNodeWithTag("action").getUnclippedBoundsInRoot()
        assertTrue(bounds.bottom - bounds.top > 50.dp)
    }

    private fun checkBadgeText(dark: Boolean) {
        activity.get().setContent { WmsTheme(darkTheme = dark) {
            Box(Modifier.width(240.dp)) { WmsPillBadge("合成分类", activeColor = Secondary) }
        } }
        val layouts = mutableListOf<TextLayoutResult>()
        compose.onNodeWithText("合成分类", useUnmergedTree = true)
            .performSemanticsAction(SemanticsActions.GetTextLayoutResult) { it(layouts) }
        val surface = if (dark) DarkSurface else PaletteCardBackground
        val badgeBackground = Secondary.copy(alpha = 0.12f).compositeOver(surface)
        assertTrue(contrastRatio(layouts.single().layoutInput.style.color, badgeBackground) >= 4.5f)
    }

    @Test fun lightBadgeTextUsesReadableColor() = checkBadgeText(false)
    @Test fun darkBadgeTextUsesReadableColor() = checkBadgeText(true)


}
