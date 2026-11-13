package com.factory.wms

import android.app.Application
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import com.factory.wms.ui.components.PendingSyncBanner
import com.factory.wms.ui.theme.WmsTheme
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.android.controller.ActivityController
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

/** Actual Compose rendering and clicks, using an empty synthetic Application. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [31], application = Application::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
class PendingSyncBannerTest {
    @get:Rule val compose = createEmptyComposeRule()
    private lateinit var activity: ActivityController<ComponentActivity>

    @Before fun before() {
        activity = Robolectric.buildActivity(ComponentActivity::class.java).setup().visible()
    }
    @After fun after() { activity.pause().stop().destroy() }

    @Test fun legacyReviewIsVisibleAndHasNoMisleadingRetryButton() {
        val message = "3 条历史记录待人工核对归属，禁止自动补传"
        activity.get().setContent { WmsTheme(darkTheme = false) {
            PendingSyncBanner(0, 3, {}, message = message, canRetry = false)
        } }
        compose.onNodeWithText(message).assertIsDisplayed()
        compose.onNodeWithText("3 条需处理").assertIsDisplayed()
        compose.onNodeWithText("重试").assertDoesNotExist()
    }

    @Test fun eligibleOwnerCanSeeSpecificReasonAndActuallyRequestRetry() {
        var retries = 0
        val message = "请使用原账号重新登录或核对权限后重试：合成拒绝原因403"
        activity.get().setContent { WmsTheme(darkTheme = false) {
            PendingSyncBanner(0, 1, { retries++ }, message = message, canRetry = true)
        } }
        compose.onNodeWithText(message).assertIsDisplayed()
        compose.onNodeWithText("重试").performClick()
        compose.runOnIdle { assertEquals(1, retries) }
    }

    @Test fun noRecordsKeepTheBannerHidden() {
        activity.get().setContent { WmsTheme(darkTheme = false) {
            PendingSyncBanner(0, 0, {}, message = "历史消息", canRetry = false)
        } }
        compose.onNodeWithText("历史消息").assertDoesNotExist()
        compose.onNodeWithText("重试").assertDoesNotExist()
    }
}
