package com.factory.wms

import android.app.Application
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.material3.OutlinedTextField
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.factory.wms.ui.navigation.Screen
import com.factory.wms.ui.navigation.navigatePrimary
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

/** Real Navigation Compose back stacks and saveable draft text; no ViewModel or network. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [31], application = Application::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
class PrimaryNavigationTest {
    @get:Rule val compose = createEmptyComposeRule()
    private lateinit var activity: ActivityController<ComponentActivity>
    private lateinit var nav: NavHostController

    @Before fun before() {
        activity = Robolectric.buildActivity(ComponentActivity::class.java).setup().visible()
        activity.get().setContent {
            val controller = rememberNavController()
            SideEffect { nav = controller }
            WmsTheme(darkTheme = false) {
                NavHost(controller, startDestination = Screen.Home.route) {
                    for (screen in listOf(Screen.Home, Screen.Inbound, Screen.Outbound, Screen.StockQuery)) {
                        composable(screen.route) {
                            var draft by rememberSaveable { mutableStateOf("") }
                            OutlinedTextField(draft, { draft = it }, modifier = Modifier.testTag(screen.route))
                        }
                    }
                }
            }
        }
        compose.waitForIdle()
    }
    @After fun after() { disposeComposeActivity(activity) }

    @Test fun repeatedEntryHasOneDestinationAndReturnsHome() {
        for (screen in listOf(Screen.Inbound, Screen.Outbound, Screen.StockQuery)) {
            compose.runOnIdle { nav.navigatePrimary(screen.route); nav.navigatePrimary(screen.route) }
            compose.waitForIdle()
            compose.runOnIdle {
                assertEquals(screen.route, nav.currentDestination?.route)
                assertTrue(nav.popBackStack())
            }
            compose.waitForIdle()
            compose.runOnIdle { assertEquals(Screen.Home.route, nav.currentDestination?.route) }
        }
    }

    @Test fun switchingPrimaryDestinationsRestoresEachDraft() {
        compose.runOnIdle { nav.navigatePrimary(Screen.Inbound.route) }
        compose.onNodeWithTag(Screen.Inbound.route).performTextInput("待录入 12.25")
        compose.runOnIdle { nav.navigatePrimary(Screen.Outbound.route) }
        compose.onNodeWithTag(Screen.Outbound.route).performTextInput("待出库 3")
        compose.runOnIdle { nav.navigatePrimary(Screen.Inbound.route) }
        compose.onNodeWithTag(Screen.Inbound.route).assertTextContains("待录入 12.25")
        compose.runOnIdle { nav.navigatePrimary(Screen.Outbound.route) }
        compose.onNodeWithTag(Screen.Outbound.route).assertTextContains("待出库 3")
    }
}
