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
    val actions: List<com.factory.wms.data.model.AssistantAction> = emptyList(),
    /** FEATURE-2026-10-07-012：用户发送的图片 base64（null=纯文本），气泡显示缩略图，点击可全屏查看 */
    val image: String? = null
)

data class AssistantChatUiState(
    val isLoading: Boolean = false,
    val messages: List<AssistantChatMessage> = emptyList(),
    val error: String? = null,
    /** AUDIT-2026-10-07-P6：发送失败需退回输入框的文本（null=无待退回）。 */
    val failedDraft: String? = null,
    /** BUG-2026-10-07-009：待发送的图片（base64，null=无） */
    val pendingImage: String? = null,
    /** BUG-2026-10-07-009：待发送的文件（base64 + 文件名，null=无） */
    val pendingFile: Pair<String, String>? = null
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

    /** 发送一条消息；进行中时忽略新发送（防连点重复请求）。
     *  AUDIT-2026-10-07-009-P2：有附件时允许空文本（纯图/纯文件发送），
     *  消息气泡展示「[图片]」/「[文件]」占位。 */
    fun send(text: String) {
        val trimmed = text.trim()
        val image = _uiState.value.pendingImage
        val file = _uiState.value.pendingFile
        val hasAttachment = image != null || file != null
        if ((trimmed.isEmpty() && !hasAttachment) || _uiState.value.isLoading) return

        val displayText = when {
            trimmed.isNotEmpty() -> trimmed
            file != null -> "[文件] ${file.second}"
            else -> "[图片]"
        }

        _uiState.value = _uiState.value.copy(
            // FEATURE-2026-10-07-012：图片进消息模型，气泡渲染缩略图（点击全屏查看）
            messages = _uiState.value.messages + AssistantChatMessage(
                text = displayText,
                isUser = true,
                image = image
            ),
            isLoading = true,
            error = null,
            failedDraft = null,
            pendingImage = null,
            pendingFile = null
        )
        chatJob?.cancel()
        chatJob = viewModelScope.launch {
            // AUDIT-2026-10-07-009-P2：纯附件时后端要求 text 非空，补占位文案
            val requestText = trimmed.ifEmpty { "请识别附件内容" }
            val result = repository.assistantChat(requestText, image, file)
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

    /** BUG-2026-10-07-009：设置待发送的图片 */
    fun setPendingImage(base64: String?) {
        _uiState.value = _uiState.value.copy(pendingImage = base64)
    }

    /** BUG-2026-10-07-009：设置待发送的文件 */
    fun setPendingFile(base64: String, fileName: String) {
        _uiState.value = _uiState.value.copy(pendingFile = base64 to fileName)
    }

    /** BUG-2026-10-07-009：清除待发送的图片/文件 */
    fun clearPendingAttachments() {
        _uiState.value = _uiState.value.copy(pendingImage = null, pendingFile = null)
    }

    /** 清空当前对话（仅清本地展示；服务端历史由后端保留）。 */
    fun clearConversation() {
        _uiState.value = AssistantChatUiState()
    }
}
