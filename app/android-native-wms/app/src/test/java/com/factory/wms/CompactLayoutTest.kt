package com.factory.wms

import android.app.Application
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.width
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Description
import androidx.compose.material3.OutlinedTextField
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.compose.ui.text.TextLayoutResult
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.dp
import com.factory.wms.ui.components.WmsExpandableSection
import com.factory.wms.ui.components.WmsGradientHeader
import com.factory.wms.ui.navigation.Screen
import com.factory.wms.ui.screens.FunctionCard
import com.factory.wms.ui.screens.FunctionCardItem
import com.factory.wms.ui.theme.WmsTheme
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

/** BUG-2026-10-30-010: actual Compose measurement and interaction, no server/database. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [31], application = Application::class, qualifiers = "w360dp-h800dp-mdpi")
@GraphicsMode(GraphicsMode.Mode.NATIVE)
class CompactLayoutTest {
    @get:Rule val compose = createEmptyComposeRule()
    private lateinit var controller: ActivityController<ComponentActivity>

    @Before fun setUp() {
        // Direct Robolectric Activity avoids adding a test Activity to the release manifest.
        controller = Robolectric.buildActivity(ComponentActivity::class.java).setup().visible()
    }

    @After fun tearDown() { controller.pause().stop().destroy() }

    private fun content(fontScale: Float = 1f, body: @Composable () -> Unit) {
        controller.get().setContent {
            CompositionLocalProvider(LocalDensity provides Density(1f, fontScale)) {
                WmsTheme(darkTheme = false, content = body)
            }
        }
    }

    @Test fun longCardTitleFitsAtLargeFontAndStillNavigates() {
        var clicked = false
        val title = "出入库明细"
        content(fontScale = 1.6f) {
            FunctionCardItem(
                FunctionCard(title, "按仓查流水", Icons.Outlined.Description,
                    listOf(Color.Blue, Color.Blue), Screen.InOutDetailReport),
                modifier = Modifier.width(96.dp).testTag("card"),
                onClick = { clicked = true }
            )
        }
        val layouts = mutableListOf<TextLayoutResult>()
        compose.onNodeWithText(title, useUnmergedTree = true)
            .performSemanticsAction(SemanticsActions.GetTextLayoutResult) { it(layouts) }
        assertTrue(layouts.isNotEmpty())
        assertFalse("Full title must wrap without truncation", layouts.single().hasVisualOverflow)
        compose.onNodeWithText(title, useUnmergedTree = true).assertIsDisplayed()
        compose.onNodeWithTag("card").performClick()
        compose.runOnIdle { assertTrue(clicked) }
    }

    @Test fun headerHeightComesFromTextRatherThanDecorativeCircle() {
        content {
            Box(Modifier.width(360.dp).testTag("header")) {
                WmsGradientHeader("出库", "扫码或手动添加物料", Color(0xFF059669), onBack = {})
            }
        }
        val bounds = compose.onNodeWithTag("header").getUnclippedBoundsInRoot()
        assertTrue("Compact header should leave room for materials: $bounds", bounds.height < 120.dp)
        compose.onNodeWithText("出库").assertIsDisplayed()
    }

    @Test fun optionalInformationStartsClosedAndRetainsEditedValueAfterToggle() {
        content {
            var remark by remember { mutableStateOf("") }
            WmsExpandableSection("更多信息（选填）", "已填 ${if (remark.isBlank()) 0 else 1} 项") {
                OutlinedTextField(remark, { remark = it }, modifier = Modifier.testTag("remark"))
            }
        }
        compose.onNodeWithTag("remark").assertDoesNotExist()
        compose.onNodeWithText("更多信息（选填）").performClick()
        compose.onNodeWithTag("remark").performTextInput("到货验收")
        compose.onNodeWithText("更多信息（选填）").performClick()
        compose.onNodeWithTag("remark").assertDoesNotExist()
        compose.onNodeWithText("已填 1 项").assertIsDisplayed()
        compose.onNodeWithText("更多信息（选填）").performClick()
        compose.onNodeWithTag("remark").assertTextContains("到货验收")
    }
}
