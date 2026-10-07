package com.factory.wms.ui.viewmodel.ai

import android.app.Application
import android.content.Context
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.factory.wms.ui.viewmodel.voice.DefaultEngineFactory
import com.factory.wms.ui.viewmodel.voice.SttConfig
import com.factory.wms.ui.viewmodel.voice.SttError
import com.factory.wms.ui.viewmodel.voice.VoiceSttEngine
import com.factory.wms.ui.viewmodel.voice.VoiceSttEngineFactory
import com.factory.wms.ui.viewmodel.voice.VoiceSttListener
import com.factory.wms.ui.viewmodel.voice.correctVoiceAsrText
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/**
 * AI-ASSISTANT-VOICE-001：App AI 助手聊天页语音输入状态。
 *
 * [partialText] 为识别过程中的实时文本（云端引擎无 partial 时为空，
 * 仅靠 [message] 的倒计时提示反馈录音窗口）。
 */
data class AssistantVoiceUiState(
    val isListening: Boolean = false,
    val partialText: String = "",
    val message: String = "",
    val error: String? = null
)

/**
 * AI-ASSISTANT-VOICE-001：App 端 AI 助手语音输入 ViewModel。
 *
 * 与 [VoiceCommandViewModel]（语音指令链）的职责边界：
 * - 指令链：识别文本 → LLM 意图/本地解析 → 导航/建单——用于全局悬浮麦克风；
 * - 本 VM：识别文本 → **纯文本输出**——用于聊天页输入区，识别结果填入
 *   输入框由用户确认/修改后发送，不解析、不导航、不自动发送
 *   （ASR 可能误识别，让用户过目是最低成本的纠错机会）。
 *
 * 引擎复用 [VoiceSttEngine] 抽象与 [VoiceSttEngineRegistry] 三级回退
 * （云 ASR → sherpa 本地 → Android 系统识别），8 秒兜底超时与
 * [VoiceCommandViewModel] 同口径。领域词纠正（「饮料→领料」等）同样适用：
 * 聊天问句里说「领料」被误识别成「饮料」时同样需要纠正。
 */
class AssistantVoiceInputViewModel(
    application: Application,
    private val engineFactory: VoiceSttEngineFactory
) : AndroidViewModel(application) {

    /** viewModel() 无参委托走的构造（引擎工厂取默认三级回退）。 */
    constructor(application: Application) : this(application, DefaultEngineFactory)

    private val _uiState = MutableStateFlow(AssistantVoiceUiState())
    val uiState: StateFlow<AssistantVoiceUiState> = _uiState.asStateFlow()

    /** 识别完成的最终文本（已过领域词纠正），UI 收到后填入输入框。 */
    private val _recognizedText = MutableSharedFlow<String>(extraBufferCapacity = 4)
    val recognizedText: SharedFlow<String> = _recognizedText.asSharedFlow()

    private var engine: VoiceSttEngine? = null

    /** 兜底超时（同 VoiceCommandViewModel：静默挂起防卡死 + 云引擎最长录音窗口）。 */
    private var listenTimeoutJob: Job? = null

    fun startListening(context: Context) {
        // 每次进入重建引擎，避免上次会话底层实例残留抢麦克风
        engine?.destroy()
        val e = engineFactory.create(context.applicationContext)
        e.setListener(engineListener)
        engine = e

        if (!e.isAvailable()) {
            _uiState.value = AssistantVoiceUiState(error = SttError.EngineUnavailable.toUserMessage())
            return
        }

        _uiState.value = AssistantVoiceUiState(
            isListening = true,
            message = "正在聆听，请说出问题…"
        )
        e.start(SttConfig())
        listenTimeoutJob?.cancel()
        listenTimeoutJob = viewModelScope.launch {
            val totalSeconds = VOICE_LISTEN_TIMEOUT_MS / 1000L
            for (remaining in totalSeconds downTo 1) {
                _uiState.value = _uiState.value.copy(
                    message = "正在聆听（剩余 $remaining 秒）"
                )
                delay(1000)
            }
            val alive = engine
            if (alive != null) {
                runCatching { alive.stop() }
                runCatching { alive.destroy() }
                engine = null
                _uiState.value = _uiState.value.copy(
                    isListening = false,
                    error = "识别超时：请点按麦克风后 $VOICE_LISTEN_SECONDS_TEXT 秒内说出问题"
                )
            }
        }
    }

    fun stopListening() {
        listenTimeoutJob?.cancel()
        listenTimeoutJob = null
        engine?.let { runCatching { it.stop() } }
        engine?.destroy()
        engine = null
        _uiState.value = _uiState.value.copy(isListening = false)
    }

    fun clearResult() {
        _uiState.value = _uiState.value.copy(error = null, message = "")
    }

    private val engineListener = object : VoiceSttListener {
        override fun onPartial(text: String) {
            // 收到 partial 表示识别已启动，取消兜底超时
            listenTimeoutJob?.cancel()
            listenTimeoutJob = null
            _uiState.value = _uiState.value.copy(partialText = text)
        }

        override fun onResult(texts: List<String>) {
            listenTimeoutJob?.cancel()
            listenTimeoutJob = null
            // 领域词纠正（同指令链口径）：问句里的「领料/入库」类误识别同样纠正
            val text = correctVoiceAsrText(texts.firstOrNull()?.trim().orEmpty())
            engine?.destroy()
            engine = null
            _uiState.value = AssistantVoiceUiState(
                message = if (text.isEmpty()) "未识别到内容" else "识别完成"
            )
            if (text.isEmpty()) {
                _uiState.value = _uiState.value.copy(error = "没有识别到语音，请重试")
                return
            }
            viewModelScope.launch { _recognizedText.emit(text) }
        }

        override fun onError(error: SttError, detail: String?) {
            listenTimeoutJob?.cancel()
            listenTimeoutJob = null
            engine?.destroy()
            engine = null
            // 优先展示引擎/后端透传的具体原因（如「未配置腾讯云 ASR 密钥」）
            val shown = detail?.trim()?.takeIf { it.isNotEmpty() }?.take(MAX_ERROR_DETAIL_LEN)
                ?: error.toUserMessage()
            _uiState.value = _uiState.value.copy(isListening = false, error = shown)
        }
    }

    override fun onCleared() {
        super.onCleared()
        listenTimeoutJob?.cancel()
        listenTimeoutJob = null
        engine?.destroy()
        engine = null
    }

    companion object {
        /** 兜底超时（毫秒），与 VoiceCommandViewModel 保持同口径。 */
        private const val VOICE_LISTEN_TIMEOUT_MS = 8_000L

        /** 超时文案用的秒数文本（与 VOICE_LISTEN_TIMEOUT_MS 保持同步）。 */
        private const val VOICE_LISTEN_SECONDS_TEXT = "8"

        /** 错误 detail 最大展示长度，防止超长堆栈撑爆 Snackbar。 */
        private const val MAX_ERROR_DETAIL_LEN = 80
    }
}
