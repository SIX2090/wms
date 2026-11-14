package com.factory.wms

import android.app.Application
import android.content.Context
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.test.core.app.ApplicationProvider
import com.factory.wms.ui.theme.WmsTheme
import com.factory.wms.update.*
import kotlinx.coroutines.*
import okhttp3.Protocol
import okhttp3.Response
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [31], application = Application::class)
class AppUpdatePanelTest {
    @get:Rule val compose = createEmptyComposeRule()

    @Test fun checkButtonExecutesRealManagerAndDisplaysResultWithoutNetworkOrDatabase() {
        val context = ApplicationProvider.getApplicationContext<Context>()
        context.getSharedPreferences("app_update", Context.MODE_PRIVATE).edit().clear().commit()
        var checks = 0
        val downloads = UpdateDownloadClient(UpdateDownloadClient.client().newBuilder().addInterceptor { chain ->
            checks++
            Response.Builder().request(chain.request()).protocol(Protocol.HTTP_1_1).code(200)
                .message("synthetic").body("[]".toResponseBody()).build()
        }.build())
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Unconfined)
        val manager = AppUpdateManager(context, downloads = downloads, scope = scope, io = Dispatchers.Unconfined)
        val controller = Robolectric.buildActivity(ComponentActivity::class.java).setup().visible()
        try {
            controller.get().setContent { WmsTheme { AppUpdatePanel(manager) } }
            compose.onNodeWithText("检查更新").assertIsEnabled().performClick()
            compose.onNodeWithText("暂无已验收的更新，当前版本仍可使用").assertIsDisplayed()
            assertEquals(1, checks)
            compose.onNodeWithText("检查更新").performClick()
            assertEquals(2, checks)
            compose.onNodeWithText("安装更新").assertDoesNotExist()
        } finally { scope.cancel(); controller.pause().stop().destroy() }
    }
}
