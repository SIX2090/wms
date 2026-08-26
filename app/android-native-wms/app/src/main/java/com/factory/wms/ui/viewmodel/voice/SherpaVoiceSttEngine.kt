package com.factory.wms.ui.viewmodel.voice

import android.content.Context
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.util.Log
import com.factory.wms.BuildConfig
import java.io.File
import java.util.concurrent.atomic.AtomicBoolean

/**
 * 基于 [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx) 的本地离线中文语音识别引擎。
 *
 * 设计要点：
 * - **运行时反射调用** sherpa-onnx API（`com.k2fsa.sherpa.onnx.*`），编译期不强制依赖，
 *   这样 `sherpa-onnx` AAR 未引入时本类仍可编译运行，运行时通过 [isAvailable] 检测并
 *   给出 [SttError.EngineUnavailable] 回调，由 [VoiceSttEngineRegistry] 自动 fallback
 *   到 [AndroidVoiceSttEngine]。
 * - 模型文件放在 `filesDir/sherpa-onnx/stream/{tokens.txt,encoder.onnx,decoder.onnx,joiner.onnx}`
 *   或用户自定义目录（见 [setModelDir]），由 build.gradle 的 `downloadSherpaModel` task 下载。
 * - 国内 Android 设备无 Google 服务时仍可离线识别，无需网络权限（但首次下载模型需联网）。
 *
 * 音频管线（[start] 之后）：
 *   AudioRecord (16kHz mono PCM16) -> capture thread
 *     -> Short -> Float [-1,1]
 *     -> [SherpaRuntime.feed]
 *     -> [SherpaRuntime.pollPartial] -> [VoiceSttListener.onPartial]
 *
 *   [stop] 时：停录音 -> [SherpaRuntime.pollFinal] -> [VoiceSttListener.onResult]
 */
class SherpaVoiceSttEngine(
    private val appContext: Context,
    private val modelDirOverride: File? = null
) : VoiceSttEngine {

    private var listener: VoiceSttListener? = null
    private var runtime: SherpaRuntime? = null
    private var modelDir: File? = null

    private val capturing = AtomicBoolean(false)
    private var audioRecord: AudioRecord? = null
    private var captureThread: Thread? = null
    @Volatile private var started = false

    override fun isAvailable(): Boolean {
        // 1) 模型文件存在性（filesDir 缺失时先尝试从 APK assets 复制——
        //    CI 构建已把模型打进 assets/sherpa-onnx/stream/，首次启动落盘到 filesDir）
        val dir = modelDirOverride ?: defaultModelDir()
        if (dir == null) {
            Log.i(TAG, "sherpa-onnx model dir not found: $dir")
            return false
        }
        val required = listOf("tokens.txt", "encoder.onnx", "decoder.onnx", "joiner.onnx")
        var missing = required.filter { !File(dir, it).isFile }
        if (missing.isNotEmpty()) {
            Log.i(TAG, "sherpa-onnx model missing in filesDir ($missing)，尝试从 assets 复制")
            if (copyModelFromAssets(dir)) {
                missing = required.filter { !File(dir, it).isFile }
            }
        }
        if (missing.isNotEmpty()) {
            Log.w(TAG, "sherpa-onnx model missing files: $missing in $dir")
            return false
        }
        // 2) 运行时类可加载（反射）
        if (!SherpaRuntime.probeClassloader()) {
            Log.w(TAG, "sherpa-onnx runtime not on classpath, fallback to AndroidVoiceSttEngine")
            return false
        }
        modelDir = dir
        return true
    }

    override fun start(config: SttConfig) {
        if (started) {
            Log.w(TAG, "start() called while already started, ignoring")
            return
        }
        if (!isAvailable()) {
            listener?.onError(SttError.EngineUnavailable)
            return
        }
        try {
            runtime = SherpaRuntime.create(appContext, modelDir!!, config)
            if (runtime == null) {
                // 反射初始化失败：典型场景是 AAR 与本地 SDK 不匹配（如缺少 JNI .so）
                listener?.onError(SttError.EngineUnavailable)
                return
            }
            started = true
            startAudioCapture()
        } catch (t: Throwable) {
            Log.e(TAG, "sherpa-onnx start failed", t)
            started = false
            runtime?.destroy()
            runtime = null
            listener?.onError(SttError.Unknown)
        }
    }

    override fun stop() {
        if (!started) return
        started = false
        stopAudioCapture()
        // 拿到当前流式已解码的最终文本作为结果；如果什么都没有就推空列表
        val finalText = try {
            runtime?.pollFinal().orEmpty()
        } catch (t: Throwable) {
            Log.w(TAG, "pollFinal failed", t)
            ""
        }
        listener?.onResult(if (finalText.isEmpty()) emptyList() else listOf(finalText))
    }

    override fun destroy() {
        started = false
        stopAudioCapture()
        runtime?.destroy()
        runtime = null
        listener = null
    }

    override fun setListener(listener: VoiceSttListener?) {
        this.listener = listener
    }

    /** 由调用方（Registry / 设置页）可自定义模型目录。 */
    fun setModelDir(dir: File) {
        modelDir = dir
    }

    // ---------------- 音频采集 ----------------

    private fun startAudioCapture() {
        val channelConfig = AudioFormat.CHANNEL_IN_MONO
        val audioFormat = AudioFormat.ENCODING_PCM_16BIT
        val minBuf = AudioRecord.getMinBufferSize(SAMPLE_RATE, channelConfig, audioFormat)
        if (minBuf == AudioRecord.ERROR || minBuf == AudioRecord.ERROR_BAD_VALUE) {
            Log.e(TAG, "AudioRecord.getMinBufferSize failed: $minBuf")
            listener?.onError(SttError.AudioError)
            return
        }
        val record = try {
            AudioRecord(
                MediaRecorder.AudioSource.VOICE_RECOGNITION,
                SAMPLE_RATE,
                channelConfig,
                audioFormat,
                minBuf.coerceAtLeast(FRAME_SAMPLES * 2) * 2
            )
        } catch (se: SecurityException) {
            Log.w(TAG, "AudioRecord permission denied", se)
            listener?.onError(SttError.PermissionDenied)
            return
        } catch (t: Throwable) {
            Log.e(TAG, "AudioRecord init failed", t)
            listener?.onError(SttError.AudioError)
            return
        }
        if (record.state != AudioRecord.STATE_INITIALIZED) {
            Log.e(TAG, "AudioRecord state not initialized: ${record.state}")
            runCatching { record.release() }
            listener?.onError(SttError.AudioError)
            return
        }
        record.startRecording()
        audioRecord = record
        capturing.set(true)
        val t = Thread({ captureLoop(record) }, "SherpaAudioCapture")
        captureThread = t
        t.start()
    }

    private fun captureLoop(record: AudioRecord) {
        val buf = ShortArray(FRAME_SAMPLES)
        while (capturing.get()) {
            val n = try {
                record.read(buf, 0, buf.size)
            } catch (t: Throwable) {
                Log.w(TAG, "AudioRecord.read failed", t)
                -1
            }
            if (n <= 0) continue
            val rt = runtime ?: continue
            // PCM16 -> Float[-1, 1]
            val samples = FloatArray(n) { buf[it] / 32768f }
            try {
                rt.feed(samples, SAMPLE_RATE)
                val partial = rt.pollPartial()
                if (partial.isNotEmpty()) listener?.onPartial(partial)
            } catch (t: Throwable) {
                Log.w(TAG, "sherpa feed/poll failed", t)
            }
        }
    }

    private fun stopAudioCapture() {
        capturing.set(false)
        captureThread?.let {
            try { it.join(300) } catch (_: InterruptedException) {}
        }
        captureThread = null
        audioRecord?.let { r ->
            try { r.stop() } catch (_: Throwable) {}
            try { r.release() } catch (_: Throwable) {}
        }
        audioRecord = null
    }

    private fun defaultModelDir(): File? {
        val base = appContext.filesDir ?: return null
        return File(base, "sherpa-onnx/stream")
    }

    /**
     * 首次启动把 APK assets 中的模型复制到 filesDir（sherpa-onnx 需要文件路径，
     * 不能直接读 assets 流）。assets 目录由 BuildConfig.SHERPA_MODEL_DIR 指定，
     * 模型由 build.gradle 的 downloadSherpaModel task 在构建期平铺为标准四件套。
     * 非 sherpa 构建（SHERPA_ENABLED=false）或 APK 未打包模型时返回 false，
     * 由调用方走 fallback，不抛异常。
     */
    private fun copyModelFromAssets(dir: File): Boolean {
        if (!BuildConfig.SHERPA_ENABLED) return false
        val required = listOf("tokens.txt", "encoder.onnx", "decoder.onnx", "joiner.onnx")
        val assetBase = BuildConfig.SHERPA_MODEL_DIR.trim('/')
        return try {
            dir.mkdirs()
            required.all { name ->
                try {
                    appContext.assets.open("$assetBase/$name").use { input ->
                        File(dir, name).outputStream().use { output -> input.copyTo(output) }
                    }
                    Log.i(TAG, "sherpa-onnx model installed from assets: $name")
                    true
                } catch (t: Throwable) {
                    Log.w(TAG, "sherpa-onnx asset model file missing/copied failed: $name (${t.message})")
                    false
                }
            }
        } catch (t: Throwable) {
            Log.w(TAG, "copyModelFromAssets failed: ${t.message}")
            false
        }
    }

    companion object {
        private const val TAG = "SherpaVoiceSttEngine"
        // sherpa-onnx 的核心类全限定名，用于反射探测运行时是否已挂入
        const val RUNTIME_CLASS_FQCN = "com.k2fsa.sherpa.onnx.OnlineRecognizer"

        /** 16 kHz mono，与 sherpa-onnx 流式模型默认期望一致。 */
        private const val SAMPLE_RATE = 16_000

        /** 每次读取 100ms 音频（1600 samples @ 16kHz）。 */
        private const val FRAME_SAMPLES = 1_600
    }
}
