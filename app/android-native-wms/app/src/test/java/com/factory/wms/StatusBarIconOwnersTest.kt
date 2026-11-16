package com.factory.wms

import android.app.Application
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.runtime.mutableStateOf
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.core.view.WindowInsetsControllerCompat
import com.factory.wms.ui.components.StatusBarIconEffect
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [31], application = Application::class)
class StatusBarIconOwnersTest {
    @get:Rule val compose = createEmptyComposeRule()

    @Test fun outgoingPageCannotOverwriteIncomingPageAndFinalOwnerRestoresOriginal() {
        val activity = Robolectric.buildActivity(ComponentActivity::class.java).setup().visible()
        val window = activity.get().window
        val controller = WindowInsetsControllerCompat(window, window.decorView)
        val outgoing = mutableStateOf(false)
        val incoming = mutableStateOf(false)
        controller.isAppearanceLightStatusBars = false
        activity.get().setContent {
            if (outgoing.value) StatusBarIconEffect(darkIcons = false)
            if (incoming.value) StatusBarIconEffect(darkIcons = true)
        }
        compose.runOnIdle { outgoing.value = true }
        compose.runOnIdle { assertFalse(controller.isAppearanceLightStatusBars); incoming.value = true }
        compose.runOnIdle { assertTrue(controller.isAppearanceLightStatusBars); outgoing.value = false }
        compose.runOnIdle { assertTrue(controller.isAppearanceLightStatusBars); incoming.value = false }
        compose.runOnIdle { assertFalse(controller.isAppearanceLightStatusBars) }
        disposeComposeActivity(activity)
    }
}
