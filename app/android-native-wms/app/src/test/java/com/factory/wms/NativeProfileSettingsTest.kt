package com.factory.wms

import android.app.Application
import android.content.ClipboardManager
import android.content.Context
import android.content.ClipData
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.ui.test.*
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.test.core.app.ApplicationProvider
import com.factory.wms.data.api.RetrofitClient
import com.factory.wms.ui.screens.ProfileScreen
import com.factory.wms.ui.theme.WmsTheme
import com.factory.wms.ui.viewmodel.auth.AuthUiState
import com.factory.wms.ui.viewmodel.auth.AuthViewModel
import com.factory.wms.util.ScanFeedback
import kotlinx.coroutines.flow.MutableStateFlow
import org.junit.*
import org.junit.Assert.*
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.android.controller.ActivityController
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [31], application = Application::class, qualifiers = "w360dp-h800dp-mdpi")
@GraphicsMode(GraphicsMode.Mode.NATIVE)
class NativeProfileSettingsTest {
    @get:org.junit.Rule(order = Int.MIN_VALUE) val settings = WmsSettingsDataStoreRule()
    @get:Rule val compose = createEmptyComposeRule()
    private lateinit var activity: ActivityController<ComponentActivity>
    private lateinit var auth: AuthViewModel
    private lateinit var uiContext: Context
    private val app get() = ApplicationProvider.getApplicationContext<Application>()
    private val address = "http://192.0.2.20:8080/synthetic/long-server-name"

    @Suppress("UNCHECKED_CAST")
    @Before fun before() {
        app.getSharedPreferences("wms_settings", Context.MODE_PRIVATE).edit().clear().commit()
        ScanFeedback.warmUp(app)
        RetrofitClient.setSession("http://127.0.0.1:9/", "synthetic-owner", 91)
        auth = AuthViewModel(app)
        val field = AuthViewModel::class.java.getDeclaredField("_uiState").also { it.isAccessible = true }
        (field.get(auth) as MutableStateFlow<AuthUiState>).value = AuthUiState(true, false, "仓库管理员", "仓管员", address)
        activity = Robolectric.buildActivity(ComponentActivity::class.java).setup().visible()
        activity.get().setContent { uiContext = LocalContext.current; WmsTheme(darkTheme = false) { ProfileScreen(auth) {} } }
    }
    @After fun after() {
        closeWmsTestViewModels(listOf(auth))
        val content = activity.get().findViewById<android.view.ViewGroup>(android.R.id.content)
        for (index in 0 until content.childCount) (content.getChildAt(index) as? androidx.compose.ui.platform.ComposeView)?.disposeComposition()
        disposeComposeActivity(activity)
        app.getSharedPreferences("wms_settings", Context.MODE_PRIVATE).edit().clear().commit()
        ScanFeedback.warmUp(app); RetrofitClient.setSession("", null)
    }
    @Test fun fullRowsToggleIndependentlyAndPersist() {
        compose.onNodeWithText("扫码提示音").performScrollTo().assertIsOn().performClick()
        compose.runOnIdle { assertFalse(ScanFeedback.soundEnabled); assertTrue(ScanFeedback.vibrationEnabled) }
        compose.onNodeWithText("扫码震动").performScrollTo().assertIsOn().performClick()
        compose.runOnIdle { assertFalse(ScanFeedback.soundEnabled); assertFalse(ScanFeedback.vibrationEnabled) }
        ScanFeedback.warmUp(app)
        assertFalse(ScanFeedback.soundEnabled); assertFalse(ScanFeedback.vibrationEnabled)
    }
    @Test fun fullServerAddressIsVisibleAndCopyUsesTheExactValue() {
        compose.onNodeWithText(address).performScrollTo().assertExists()
        val clipboard = uiContext.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
        clipboard.setPrimaryClip(ClipData.newPlainText("test", "synthetic-sentinel"))
        assertEquals("synthetic-sentinel", clipboard.primaryClip?.getItemAt(0)?.text?.toString())
        val button = compose.onNode(hasClickAction() and hasText("复制"))
        button.performScrollTo().assertIsDisplayed().assertIsEnabled()
        val bounds = button.getUnclippedBoundsInRoot()
        assertTrue(bounds.right - bounds.left >= 48.dp && bounds.bottom - bounds.top >= 48.dp)
        button.performClick()
        compose.runOnIdle { assertEquals(address, clipboard.primaryClip?.getItemAt(0)?.text?.toString()) }
    }
}
