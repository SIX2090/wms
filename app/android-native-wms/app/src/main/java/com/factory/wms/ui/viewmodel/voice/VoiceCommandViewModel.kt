package com.factory.wms.ui.viewmodel.voice

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.factory.wms.ui.navigation.Screen
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/**
 * 语音指令：将识别文本解析为 WMS 操作指令。
 * 关键词解析并做优先级排序，避免包含关系误命中
 * （如"识物盘点"先于"盘点"、"识别单据"先于"识物"）。
 */
fun parseCommand(heardText: String): VoiceCommand {
    val t = heardText.trim()
    if (t.isEmpty()) return VoiceCommand.Unrecognized
    val lt = t.lowercase()
    return when {
        lt.contains("识物盘点") || (lt.contains("识物") && lt.contains("盘点")) ->
            VoiceCommand.Navigate(Screen.StocktakeRecognize)
        lt.contains("识别单据") || lt.contains("单据识别") || lt.contains("识别送货单") ->
            VoiceCommand.Navigate(Screen.DocumentOcr)
        lt.contains("识物") -> VoiceCommand.Navigate(Screen.ObjectRecognize)
        lt.contains("入库") || lt.contains("采购入库") -> VoiceCommand.Navigate(Screen.Inbound)
        lt.contains("出库") -> VoiceCommand.Navigate(Screen.Outbound)
        // "期初库存"须先于"库存"匹配，避免误判为查库存
        lt.contains("期初") -> VoiceCommand.Navigate(Screen.OpeningStock)
        lt.contains("库存") || lt.contains("查库存") -> VoiceCommand.Navigate(Screen.StockQuery)
        lt.contains("盘点") -> VoiceCommand.Navigate(Screen.Stocktake)
        // "返回首页/回到首页"倾向于回首页，故先判首页再判返回
        lt.contains("首页") || lt.contains("主页") || lt.contains("回到主页面") -> VoiceCommand.GoHome
        lt.contains("返回") || lt.contains("后退") || lt.contains("上一页") -> VoiceCommand.GoBack
        lt.contains("退出") || lt.contains("登出") || lt.contains("注销") || lt.contains("退出登录") ->
            VoiceCommand.Logout
        else -> VoiceCommand.Unrecognized
    }
}

/** 语音识别命中的操作指令。 */
sealed class VoiceCommand(val label: String) {
    data class Navigate(val screen: Screen) : VoiceCommand("打开${screen.title}")
    data object GoBack : VoiceCommand("返回上一页")
    data object GoHome : VoiceCommand("回到首页")
    data object Logout : VoiceCommand("退出登录")
    data object Unrecognized : VoiceCommand("未识别到可执行指令")
}

data class VoiceUiState(
    val isListening: Boolean = false,
    val partialText: String = "",
    val heardText: String = "",
    val message: String = "",
    val error: String? = null
)

class VoiceCommandViewModel : ViewModel() {

    private val _uiState = MutableStateFlow(VoiceUiState())
    val uiState: StateFlow<VoiceUiState> = _uiState.asStateFlow()

    private val _commands = MutableSharedFlow<VoiceCommand>(extraBufferCapacity = 8)
    val commands = _commands.asSharedFlow()

    private var speechRecognizer: SpeechRecognizer? = null

    /**
     * 语音识别超时保护：
     * 国内设备 / 无 Google 服务场景下，SpeechRecognizer 可能既不回调 onBeginningOfSpeech
     * 也不回调 onError，UI 会永远卡在"正在聆听"。在 startListening 时启动 8 秒 Job，
     * stopListening / dispatchResults / onError 三个出口负责取消该 Job。
     */
    private var listenTimeoutJob: Job? = null

    fun startListening(context: Context) {
        if (!SpeechRecognizer.isRecognitionAvailable(context)) {
            _uiState.value = VoiceUiState(error = "当前设备不支持语音识别")
            return
        }
        speechRecognizer?.destroy()
        val recognizer = SpeechRecognizer.createSpeechRecognizer(context.applicationContext)
        recognizer.setRecognitionListener(createListener())
        speechRecognizer = recognizer

        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, "zh-CN")
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
            putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 5)
        }
        _uiState.value = VoiceUiState(isListening = true, message = "正在聆听，请说出指令…")
        recognizer.startListening(intent)

        // 8 秒兜底超时：未收到任何识别/错误回调时主动停掉 recognizer 并提示
        listenTimeoutJob?.cancel()
        listenTimeoutJob = viewModelScope.launch {
            delay(VOICE_LISTEN_TIMEOUT_MS)
            val recognizerStillAlive = speechRecognizer
            if (recognizerStillAlive != null) {
                runCatching { recognizerStillAlive.stopListening() }
                runCatching { recognizerStillAlive.cancel() }
                runCatching { recognizerStillAlive.destroy() }
                speechRecognizer = null
                _uiState.value = _uiState.value.copy(
                    isListening = false,
                    error = "识别超时，请重试"
                )
            }
        }
    }

    fun stopListening() {
        listenTimeoutJob?.cancel()
        listenTimeoutJob = null
        speechRecognizer?.let { recognizer ->
            runCatching { recognizer.stopListening() }
            runCatching { recognizer.cancel() }
        }
        speechRecognizer = null
        _uiState.value = _uiState.value.copy(isListening = false)
    }

    fun clearResult() {
        _uiState.value = _uiState.value.copy(heardText = "", message = "", error = null)
    }

    private fun dispatchResults(texts: List<String>) {
        listenTimeoutJob?.cancel()
        listenTimeoutJob = null
        val text = texts.firstOrNull()?.trim().orEmpty()
        val command = parseCommand(text)
        speechRecognizer?.destroy()
        speechRecognizer = null
        _uiState.value = VoiceUiState(
            isListening = false,
            heardText = text,
            message = if (text.isEmpty()) "未识别到内容" else "识别结果：$text"
        )
        viewModelScope.launch { _commands.emit(command) }
    }

    private fun createListener() = object : RecognitionListener {
        override fun onReadyForSpeech(params: Bundle?) = Unit

        override fun onBeginningOfSpeech() {
            // 用户开始说话 = 设备麦克风与识别服务都正常，取消超时兜底
            listenTimeoutJob?.cancel()
            listenTimeoutJob = null
            _uiState.value = _uiState.value.copy(message = "开始聆听…")
        }

        override fun onRmsChanged(rmsdB: Float) = Unit

        override fun onBufferReceived(buffer: ByteArray?) = Unit

        override fun onEndOfSpeech() {
            _uiState.value = _uiState.value.copy(message = "识别中…")
        }

        override fun onError(error: Int) {
            listenTimeoutJob?.cancel()
            listenTimeoutJob = null
            speechRecognizer?.destroy()
            speechRecognizer = null
            val reason = when (error) {
                SpeechRecognizer.ERROR_NO_MATCH -> "没有识别到语音，请重试"
                SpeechRecognizer.ERROR_SPEECH_TIMEOUT -> "说话超时，请重试"
                SpeechRecognizer.ERROR_RECOGNIZER_BUSY -> "识别服务繁忙，请稍后重试"
                SpeechRecognizer.ERROR_AUDIO -> "录音失败，请检查麦克风"
                SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS -> "缺少麦克风权限"
                SpeechRecognizer.ERROR_NETWORK -> "网络异常，语音识别需要联网，请检查网络后重试"
                SpeechRecognizer.ERROR_NETWORK_TIMEOUT -> "网络超时，请检查网络后重试"
                SpeechRecognizer.ERROR_SERVER -> "语音服务暂不可用，请稍后重试"
                SpeechRecognizer.ERROR_CLIENT -> "语音识别服务出错，请重启 App 或安装 Google 服务后重试"
                SpeechRecognizer.ERROR_TOO_MANY_REQUESTS -> "请求过于频繁，请稍后再试"
                else -> "语音识别失败（$error）"
            }
            _uiState.value = _uiState.value.copy(isListening = false, error = reason)
        }

        override fun onResults(results: Bundle?) {
            val texts = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                ?: java.util.ArrayList()
            dispatchResults(texts)
        }

        override fun onPartialResults(partialResults: Bundle?) {
            val texts = partialResults?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                ?: java.util.ArrayList()
            val partial = texts.firstOrNull()?.trim().orEmpty()
            _uiState.value = _uiState.value.copy(partialText = partial)
        }

        override fun onEvent(eventType: Int, params: Bundle?) = Unit
    }

    override fun onCleared() {
        super.onCleared()
        listenTimeoutJob?.cancel()
        listenTimeoutJob = null
        speechRecognizer?.destroy()
        speechRecognizer = null
    }

    companion object {
        /** 语音识别兜底超时（毫秒）。覆盖国内设备无 Google 服务、recognizer 静默挂起的场景。 */
        private const val VOICE_LISTEN_TIMEOUT_MS = 8_000L
    }
}