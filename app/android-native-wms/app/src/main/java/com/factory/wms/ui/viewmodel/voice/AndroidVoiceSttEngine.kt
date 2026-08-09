package com.factory.wms.ui.viewmodel.voice

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer

/**
 * 基于 [SpeechRecognizer] 的 [VoiceSttEngine] 实现。
 *
 * 行为对齐原 [VoiceCommandViewModel] 中的识别流程：
 * - 启动时校验 isRecognitionAvailable。
 * - 通过 [Listener] 回调 partial / result / error。
 * - 错误码转 [SttError] 枚举，便于上层做统一 UI 提示。
 *
 * 注意：此实现在国内设备 / 无 Google 服务场景下可能静默挂起；
 * UI 层（[VoiceCommandViewModel]）需自行启动兜底超时。
 */
class AndroidVoiceSttEngine(
    private val appContext: Context
) : VoiceSttEngine {

    private var recognizer: SpeechRecognizer? = null
    private var listener: VoiceSttListener? = null
    private var started = false

    override fun isAvailable(): Boolean =
        SpeechRecognizer.isRecognitionAvailable(appContext)

    override fun start(config: SttConfig) {
        if (!isAvailable()) {
            listener?.onError(SttError.EngineUnavailable)
            return
        }
        // 重启前先释放旧实例，避免多个 recognizer 抢麦克风
        releaseRecognizer()
        val r = SpeechRecognizer.createSpeechRecognizer(appContext)
        r.setRecognitionListener(buildListener())
        recognizer = r
        started = true

        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, config.language)
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, config.partialResults)
            putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, config.maxResults)
        }
        r.startListening(intent)
    }

    override fun stop() {
        val r = recognizer ?: return
        if (started) {
            runCatching { r.stopListening() }
            runCatching { r.cancel() }
        }
        releaseRecognizer()
    }

    override fun destroy() {
        releaseRecognizer()
        listener = null
    }

    override fun setListener(listener: VoiceSttListener?) {
        this.listener = listener
    }

    private fun releaseRecognizer() {
        started = false
        recognizer?.let { runCatching { it.destroy() } }
        recognizer = null
    }

    private fun buildListener(): RecognitionListener = object : RecognitionListener {
        override fun onReadyForSpeech(params: Bundle?) = Unit
        override fun onBeginningOfSpeech() = Unit
        override fun onRmsChanged(rmsdB: Float) = Unit
        override fun onBufferReceived(buffer: ByteArray?) = Unit
        override fun onEndOfSpeech() = Unit
        override fun onEvent(eventType: Int, params: Bundle?) = Unit

        override fun onError(error: Int) {
            started = false
            listener?.onError(mapError(error))
        }

        override fun onResults(results: Bundle?) {
            started = false
            val texts = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                ?: emptyList()
            listener?.onResult(texts)
        }

        override fun onPartialResults(partialResults: Bundle?) {
            val texts = partialResults?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                ?: return
            val first = texts.firstOrNull()?.trim().orEmpty()
            if (first.isNotEmpty()) listener?.onPartial(first)
        }
    }

    private fun mapError(code: Int): SttError = when (code) {
        SpeechRecognizer.ERROR_NO_MATCH -> SttError.NoMatch
        SpeechRecognizer.ERROR_SPEECH_TIMEOUT -> SttError.SpeechTimeout
        SpeechRecognizer.ERROR_RECOGNIZER_BUSY -> SttError.Busy
        SpeechRecognizer.ERROR_AUDIO -> SttError.AudioError
        SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS -> SttError.PermissionDenied
        SpeechRecognizer.ERROR_NETWORK -> SttError.NetworkError
        SpeechRecognizer.ERROR_NETWORK_TIMEOUT -> SttError.NetworkTimeout
        SpeechRecognizer.ERROR_SERVER -> SttError.ServerError
        SpeechRecognizer.ERROR_CLIENT -> SttError.ClientError
        SpeechRecognizer.ERROR_TOO_MANY_REQUESTS -> SttError.TooManyRequests
        else -> SttError.Unknown
    }
}
