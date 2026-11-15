package com.factory.wms

import android.app.Application
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.test.core.app.ApplicationProvider
import com.factory.wms.data.api.RetrofitClient
import com.factory.wms.ui.screens.AssistantChatScreen
import com.factory.wms.ui.theme.WmsTheme
import com.factory.wms.ui.viewmodel.ai.AssistantChatUiState
import com.factory.wms.ui.viewmodel.ai.AssistantChatViewModel
import com.factory.wms.ui.viewmodel.ai.AssistantVoiceInputViewModel
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
class NativeAssistantInputTest {
    @get:org.junit.Rule(order = Int.MIN_VALUE) val settings = WmsSettingsDataStoreRule()
    @get:Rule val compose = createEmptyComposeRule()
    private lateinit var activity: ActivityController<ComponentActivity>
    private lateinit var vm: AssistantChatViewModel
    private lateinit var voice: AssistantVoiceInputViewModel
    private lateinit var state: MutableStateFlow<AssistantChatUiState>
    @Suppress("UNCHECKED_CAST")
    @Before fun before() {
        RetrofitClient.setSession("http://127.0.0.1:9/", "synthetic-owner", 91)
        val app = ApplicationProvider.getApplicationContext<Application>()
        vm = AssistantChatViewModel(app); voice = AssistantVoiceInputViewModel(app)
        state = AssistantChatViewModel::class.java.getDeclaredField("_uiState").also { it.isAccessible = true }.get(vm) as MutableStateFlow<AssistantChatUiState>
        state.value = AssistantChatUiState(isLoading = true)
        activity = Robolectric.buildActivity(ComponentActivity::class.java).setup().visible()
        activity.get().setContent { WmsTheme(darkTheme = false) { AssistantChatScreen(vm, voice) {} } }
    }
    @After fun after() { closeWmsTestViewModels(listOf(vm, voice)); RetrofitClient.setToken(null); RetrofitClient.setBaseUrl(""); disposeComposeActivity(activity) }
    @Test fun imeDuringLoadingDoesNotClearCurrentInput() {
        val input = compose.onNode(hasSetTextAction())
        input.performTextReplacement("需要保留的仓库问题")
        input.performImeAction()
        input.assertTextContains("需要保留的仓库问题")
        compose.onNodeWithContentDescription("发送").assertIsNotEnabled()
    }
    @Test fun failedDraftWaitsUntilNewInputIsCleared() {
        val input = compose.onNode(hasSetTextAction())
        input.performTextReplacement("新输入")
        compose.runOnIdle { state.value = state.value.copy(isLoading = false, failedDraft = "待保留的原输入") }
        input.assertTextContains("新输入")
        compose.runOnIdle { assertEquals("待保留的原输入", state.value.failedDraft) }
        compose.onNodeWithContentDescription("发送").assertIsNotEnabled()
        input.performImeAction()
        input.assertTextContains("新输入")
        input.performTextReplacement("")
        input.assertTextContains("待保留的原输入")
        compose.runOnIdle { assertNull(state.value.failedDraft) }
    }
    @Test fun clearingErrorCannotDiscardUnrestoredFailedDraft() {
        val input = compose.onNode(hasSetTextAction())
        input.performTextReplacement("新输入")
        compose.runOnIdle {
            state.value = state.value.copy(isLoading = false, error = "合成错误", failedDraft = "待恢复的原输入")
            vm.clearError()
            assertNull(state.value.error)
            assertEquals("待恢复的原输入", state.value.failedDraft)
        }
        input.assertTextContains("新输入")
        input.performTextReplacement("")
        input.assertTextContains("待恢复的原输入")
    }

}
