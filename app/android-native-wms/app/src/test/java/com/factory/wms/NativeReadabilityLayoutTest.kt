package com.factory.wms

import android.app.Application
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.width
import androidx.compose.runtime.*
import androidx.compose.material3.ColorScheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
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
        disposeComposeActivity(activity)
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

    private fun checkMaterialTextRoles(dark: Boolean) {
        var captured: ColorScheme? = null
        activity.get().setContent { WmsTheme(darkTheme = dark) {
            val scheme = MaterialTheme.colorScheme
            SideEffect { captured = scheme }
            Text("主题文字角色")
        } }
        compose.waitForIdle()
        val c = requireNotNull(captured)
        for ((name, foreground, background) in listOf(
            Triple("primary", c.onPrimary, c.primary),
            Triple("primaryContainer", c.onPrimaryContainer, c.primaryContainer),
            Triple("secondary", c.onSecondary, c.secondary),
            Triple("secondaryContainer", c.onSecondaryContainer, c.secondaryContainer),
            Triple("tertiary", c.onTertiary, c.tertiary),
            Triple("tertiaryContainer", c.onTertiaryContainer, c.tertiaryContainer),
            Triple("surface", c.onSurface, c.surface),
            Triple("surfaceVariant", c.onSurfaceVariant, c.surfaceVariant),
            Triple("background", c.onBackground, c.background),
            Triple("error", c.onError, c.error),
            Triple("errorContainer", c.onErrorContainer, c.errorContainer)
        )) {
            assertTrue("$name text contrast in dark=$dark: ${contrastRatio(foreground, background)} ($foreground / $background)",
                contrastRatio(foreground, background) >= 4.5f)
        }
    }

    @Test fun lightMaterialTextRolesStayReadable() = checkMaterialTextRoles(false)
    @Test fun darkMaterialTextRolesStayReadable() = checkMaterialTextRoles(true)

    private fun checkLoadingAction(dark: Boolean) {
        activity.get().setContent { WmsTheme(darkTheme = dark) {
            androidx.compose.material3.Surface(color = MaterialTheme.colorScheme.surface) {
            Box(Modifier.width(240.dp)) {
                WmsPrimaryButton("正在保存", {}, loading = true, color = CardBlue,
                    modifier = Modifier.testTag("busy"), haptic = false)
            }
            }
        } }
        compose.onNodeWithTag("busy").assertIsNotEnabled()
        val layouts = mutableListOf<TextLayoutResult>()
        compose.onNodeWithText("正在保存", useUnmergedTree = true)
            .performSemanticsAction(SemanticsActions.GetTextLayoutResult) { it(layouts) }
        val bounds = compose.onNodeWithTag("busy").getUnclippedBoundsInRoot()
        val view = activity.get().window.decorView
        val bitmap = android.graphics.Bitmap.createBitmap(view.width, view.height, android.graphics.Bitmap.Config.ARGB_8888)
        compose.runOnIdle { view.draw(android.graphics.Canvas(bitmap)) }
        // Sample actual rendered fill away from label, spinner and rounded corners.
        val background = androidx.compose.ui.graphics.Color(bitmap.getPixel(
            ((bounds.left.value + bounds.right.value) / 2).toInt(), bounds.top.value.toInt() + 4))
        assertTrue("Loading text contrast=${contrastRatio(layouts.single().layoutInput.style.color, background)} on actual fill $background",
            contrastRatio(layouts.single().layoutInput.style.color, background) >= 4.5f)
    }

    @Test fun lightLoadingActionRemainsReadable() = checkLoadingAction(false)
    @Test fun darkLoadingActionRemainsReadable() = checkLoadingAction(true)


}
