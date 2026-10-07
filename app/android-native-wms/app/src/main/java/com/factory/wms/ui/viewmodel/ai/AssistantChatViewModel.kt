package com.factory.wms.ui.viewmodel.ai

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.factory.wms.data.model.AssistantChatResult
import com.factory.wms.data.repository.WmsRepository
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/**
 * AI-ASSISTANT-MOBILE-001：聊天消息（UI 展示模型）。
 *
 * [isUser] 区分气泡方向；[cards]/[actions] 为后端透传的结构化卡片与建议动作。
 */
data class AssistantChatMessage(
    val id: Long = System.currentTimeMillis(),
    val text: String,
    val isUser: Boolean,
    val cards: List<com.factory.wms.data.model.AssistantCard> = emptyList(),
    val actions: List<com.factory.wms.data.model.AssistantAction> = emptyList()
)

data class AssistantChatUiState(
    val isLoading: Boolean = false,
    val messages: List<AssistantChatMessage> = emptyList(),
    val error: String? = null,
    /** AUDIT-2026-10-07-P6：发送失败需退回输入框的文本（null=无待退回）。 */
    val failedDraft: String? = null
)

/**
 * AI-ASSISTANT-MOBILE-001：App 端 AI 助手聊天 ViewModel。
 *
 * 与 PC AI 助手共用后端处理链（28 个意图：查库存/查单号/今日概况/
 * 五类建单草稿/分析问答），本地不解析意图——所有理解都在服务端。
 */
class AssistantChatViewModel(application: Application) : AndroidViewModel(application) {

    private val repository = WmsRepository(application)

    private val _uiState = MutableStateFlow(AssistantChatUiState())
    val uiState: StateFlow<AssistantChatUiState> = _uiState.asStateFlow()

    private var chatJob: Job? = null

    fun clearError() {
        _uiState.value = _uiState.value.copy(error = null, failedDraft = null)
    }

    /** P6：UI 取走退回草稿后清标记，避免重组时反复回填。 */
    fun consumeFailedDraft() {
        _uiState.value = _uiState.value.copy(failedDraft = null)
    }

    /** 发送一条消息；进行中时忽略新发送（防连点重复请求）。 */
    fun send(text: String) {
        val trimmed = text.trim()
        if (trimmed.isEmpty() || _uiState.value.isLoading) return

        _uiState.value = _uiState.value.copy(
            messages = _uiState.value.messages + AssistantChatMessage(text = trimmed, isUser = true),
            isLoading = true,
            error = null,
            failedDraft = null
        )
        chatJob?.cancel()
        chatJob = viewModelScope.launch {
            val result = repository.assistantChat(trimmed)
            result.fold(
                onSuccess = { data: AssistantChatResult? ->
                    val reply = data?.reply?.takeIf { it.isNotBlank() }
                        ?: "AI 助手没有返回有效回复，请换个说法试试。"
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        messages = _uiState.value.messages + AssistantChatMessage(
                            text = reply,
                            isUser = false,
                            cards = data?.cards.orEmpty(),
                            actions = data?.actions.orEmpty()
                        )
                    )
                },
                onFailure = { e ->
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = e.message ?: "网络异常，请稍后重试",
                        // AUDIT-2026-10-07-P6：失败消息退回输入框，用户改后重发，
                        // 不用手打一遍
                        failedDraft = trimmed
                    )
                }
            )
        }
    }

    /** 清空当前对话（仅清本地展示；服务端历史由后端保留）。 */
    fun clearConversation() {
        _uiState.value = AssistantChatUiState()
    }
}
