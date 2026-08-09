package com.factory.wms.ui.viewmodel.voice

/**
 * 语音识别引擎抽象层。
 *
 * 设计目的：
 * - 默认实现 [AndroidVoiceSttEngine] 基于 Android [android.speech.SpeechRecognizer]，
 *   在国内设备 / 无 Google 服务场景下可能静默挂起。
 * - 后续可注入 [SherpaVoiceSttEngine]（基于 sherpa-onnx，本地离线中文识别），
 *   绕过对 Google Speech Service 的依赖。
 *
 * 生命周期：
 * - [start] 启动一次识别会话。
 * - [stop] 主动结束本次会话（用户取消、UI 关闭等）。
 * - [destroy] 释放底层资源（ViewModel.onCleared 时调用）。
 *
 * 回调通过 [Listener] 推送：
 * - [Listener.onPartial] 收到部分识别结果。
 * - [Listener.onResult] 收到最终识别结果（多条候选）。
 * - [Listener.onError] 识别失败（细分错误码见 [SttError]）。
 */
interface VoiceSttEngine {
    /** 是否支持当前环境（如设备、Google 服务可用、模型文件存在等）。 */
    fun isAvailable(): Boolean

    /** 启动一次识别会话；如已存在会话应先 stop/destroy。 */
    fun start(config: SttConfig = SttConfig())

    /** 主动结束当前会话，不回调任何结果。 */
    fun stop()

    /** 释放底层资源；调用后引擎不可再用。 */
    fun destroy()

    /** 注册识别回调，重复调用会覆盖前一个监听器。 */
    fun setListener(listener: Listener?)
}

interface VoiceSttListener {
    /** 实时部分识别结果（中文场景下多为"未完成"前缀）。 */
    fun onPartial(text: String) {}

    /** 最终识别结果，按置信度从高到低排序。 */
    fun onResult(texts: List<String>) {}

    /** 识别错误；细分原因见 [SttError]。 */
    fun onError(error: SttError) {}
}

/** 兼容旧命名（保持 [VoiceSttEngine.setListener] 调用点一致）。 */
typealias Listener = VoiceSttListener

data class SttConfig(
    /** BCP-47 语言标签，默认中文。 */
    val language: String = "zh-CN",
    /** 是否启用部分结果。 */
    val partialResults: Boolean = true,
    /** 最大返回候选数。 */
    val maxResults: Int = 5
)

/**
 * 识别错误枚举。覆盖两个引擎共有的失败原因：
 * - [NoMatch]：没有识别到语音 / 静默超时。
 * - [SpeechTimeout]：说话方超时。
 * - [Busy]：底层服务繁忙。
 * - [AudioError]：录音 / 麦克风失败。
 * - [PermissionDenied]：缺少 RECORD_AUDIO 权限。
 * - [NetworkError]：需要联网但网络异常（仅系统引擎触发）。
 * - [NetworkTimeout]：网络超时。
 * - [ServerError]：远端服务不可用。
 * - [ClientError]：本地客户端错误（如缺少 Google 服务）。
 * - [TooManyRequests]：请求过频。
 * - [EngineUnavailable]：引擎不可用（系统：未安装 Google；sherpa：模型缺失）。
 * - [Unknown]：其他未分类错误。
 */
enum class SttError {
    NoMatch,
    SpeechTimeout,
    Busy,
    AudioError,
    PermissionDenied,
    NetworkError,
    NetworkTimeout,
    ServerError,
    ClientError,
    TooManyRequests,
    EngineUnavailable,
    Unknown;

    /** 转为可展示的中文提示。 */
    fun toUserMessage(): String = when (this) {
        NoMatch -> "没有识别到语音，请重试"
        SpeechTimeout -> "说话超时，请重试"
        Busy -> "识别服务繁忙，请稍后重试"
        AudioError -> "录音失败，请检查麦克风"
        PermissionDenied -> "缺少麦克风权限"
        NetworkError -> "网络异常，语音识别需要联网，请检查网络后重试"
        NetworkTimeout -> "网络超时，请检查网络后重试"
        ServerError -> "语音服务暂不可用，请稍后重试"
        ClientError -> "语音识别服务出错，请重启 App 后重试"
        TooManyRequests -> "请求过于频繁，请稍后再试"
        EngineUnavailable -> "当前设备不支持语音识别"
        Unknown -> "语音识别失败，请重试"
    };

    companion object {
        /**
         * 引擎错误分类提示，主要给 sherpa 等本地引擎的细分错误使用；
         * Android 系统识别引擎在 [AndroidVoiceSttEngine] 内自行做错误码映射。
         */
        fun ofSystemUnavailable(): SttError = EngineUnavailable
    }
}
