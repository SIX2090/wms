package com.factory.wms.ui.viewmodel.voice

import android.content.Context
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.factory.wms.ui.navigation.Screen
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

/**
 * 语音指令 ViewModel。
 *
 * 依赖 [VoiceSttEngine] 抽象，不再直接操作 Android 系统识别 API；
 * 构造时传入引擎（如 [AndroidVoiceSttEngine] 或 [SherpaVoiceSttEngine]），
 * ViewModel 只负责 UI 状态、8 秒兜底超时与命令解析。
 */
class VoiceCommandViewModel(
    private val engineFactory: VoiceSttEngineFactory = DefaultEngineFactory
) : ViewModel() {

    private val _uiState = MutableStateFlow(VoiceUiState())
    val uiState: StateFlow<VoiceUiState> = _uiState.asStateFlow()

    private val _commands = MutableSharedFlow<VoiceCommand>(extraBufferCapacity = 8)
    val commands: SharedFlow<VoiceCommand> = _commands.asSharedFlow()

    private var engine: VoiceSttEngine? = null

    /**
     * 语音识别超时保护：
     * 国内设备 / 无 Google 服务场景下，系统识别 API 可能既不回调 onPartial
     * 也不回调 onError，UI 会永远卡在"正在聆听"。在 startListening 时启动 8 秒 Job，
     * stopListening / 引擎 onResult / onError / onCleared 四个出口负责取消该 Job。
     */
    private var listenTimeoutJob: Job? = null

    fun startListening(context: Context) {
        // 每次进入都重建引擎，避免上次会话的底层实例残留抢麦克风
        engine?.destroy()
        val e = engineFactory.create(context.applicationContext)
        e.setListener(engineListener)
        engine = e

        if (!e.isAvailable()) {
            _uiState.value = VoiceUiState(error = SttError.EngineUnavailable.toUserMessage())
            return
        }

        _uiState.value = VoiceUiState(isListening = true, message = "正在聆听，请说出指令…")
        e.start(SttConfig())

        // 8 秒兜底超时：未收到任何识别/错误回调时主动停掉引擎并提示
        listenTimeoutJob?.cancel()
        listenTimeoutJob = viewModelScope.launch {
            delay(VOICE_LISTEN_TIMEOUT_MS)
            val alive = engine
            if (alive != null) {
                runCatching { alive.stop() }
                runCatching { alive.destroy() }
                engine = null
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
        engine?.let { runCatching { it.stop() } }
        engine?.destroy()
        engine = null
        _uiState.value = _uiState.value.copy(isListening = false)
    }

    fun clearResult() {
        _uiState.value = _uiState.value.copy(heardText = "", message = "", error = null)
    }

    private val engineListener = object : VoiceSttListener {
        override fun onPartial(text: String) {
            // 收到 partial 表示识别已经起来，取消兜底超时
            listenTimeoutJob?.cancel()
            listenTimeoutJob = null
            _uiState.value = _uiState.value.copy(partialText = text)
        }

        override fun onResult(texts: List<String>) {
            listenTimeoutJob?.cancel()
            listenTimeoutJob = null
            val text = texts.firstOrNull()?.trim().orEmpty()
            val command = parseCommand(text)
            engine?.destroy()
            engine = null
            _uiState.value = VoiceUiState(
                isListening = false,
                heardText = text,
                message = if (text.isEmpty()) "未识别到内容" else "识别结果：$text"
            )
            viewModelScope.launch { _commands.emit(command) }
        }

        override fun onError(error: SttError, detail: String?) {
            listenTimeoutJob?.cancel()
            listenTimeoutJob = null
            engine?.destroy()
            engine = null
            // 优先展示引擎/后端给出的具体原因（如"未配置腾讯云 ASR 密钥"），
            // 其次才用 SttError 的笼统默认文案；detail 截断防止超长堆栈撑爆 Snackbar
            val shown = detail?.trim()?.takeIf { it.isNotEmpty() }?.take(MAX_ERROR_DETAIL_LEN)
                ?: error.toUserMessage()
            _uiState.value = _uiState.value.copy(
                isListening = false,
                error = shown
            )
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
        /** 语音识别兜底超时（毫秒）。覆盖国内设备无 Google 服务、recognizer 静默挂起的场景。 */
        private const val VOICE_LISTEN_TIMEOUT_MS = 15_000L

        /** 引擎/后端透传的错误 detail 最大展示长度，防止异常长文本撑爆 Snackbar。 */
        private const val MAX_ERROR_DETAIL_LEN = 80
    }
}

/** 引擎工厂；调用方可在测试或特殊机型注入自定义实现。 */
fun interface VoiceSttEngineFactory {
    fun create(context: Context): VoiceSttEngine
}

/** 默认工厂：先尝试 sherpa-onnx（如已配置），否则回落到 Android 系统识别。 */
object DefaultEngineFactory : VoiceSttEngineFactory {
    override fun create(context: Context): VoiceSttEngine =
        VoiceSttEngineRegistry.create(context)
}

/**
 * 引擎选择中心。根据设备/模型/配置挑选当前使用的 [VoiceSttEngine]。
 *
 * 选择策略：
 * 1. 若调用方通过 [setSelector] 注入了自定义选择器（如设置页切换 / 单测 mock），
 *    优先使用注入的选择器。
 * 2. 否则走 [defaultSelector]：先尝试 [SherpaVoiceSttEngine]（模型齐全 + 运行时
 *    类加载成功才用），否则回落到 [AndroidVoiceSttEngine]。
 *
 * 这样做的好处：
 * - 国内无 Google 服务的设备：sherpa 不可用时自动 fallback，UI 不退化；
 * - 海外或装了 Google 服务的设备：默认走系统识别（低资源占用 / 延迟低）；
 * - 用户可在设置中强制开启"本地识别"（注入 selector）。
 */
object VoiceSttEngineRegistry {
    @Volatile
    private var selector: (Context) -> VoiceSttEngine = ::defaultSelector

    /** 切换全局引擎选择器（单测 / 用户偏好切换时使用）。 */
    fun setSelector(selector: (Context) -> VoiceSttEngine) {
        this.selector = selector
    }

    fun create(context: Context): VoiceSttEngine = selector(context)

    /**
     * 默认选择器：云引擎（走后端中转腾讯云）优先，sherpa 本地离线兜底，Android 系统识别最后。
     * - 云引擎解决国内设备无 Google 服务时系统识别"卡在正在聆听"的痛点；
     * - [SherpaVoiceSttEngine.isAvailable] 内部会做模型存在性 + 反射探测，
     *   不会因为缺模型就崩，最多返回 false → 这里 fallback；
     * - [CloudAsrVoiceSttEngine.isAvailable] 恒为 true，故默认始终走云引擎，
     *   网络 / 密钥异常在 stop 时异步回调错误，UI 不卡死。
     */
    private fun defaultSelector(context: Context): VoiceSttEngine {
        val cloud = CloudAsrVoiceSttEngine(context)
        if (cloud.isAvailable()) return cloud
        val sherpa = SherpaVoiceSttEngine(context)
        return if (sherpa.isAvailable()) sherpa else AndroidVoiceSttEngine(context)
    }
}
