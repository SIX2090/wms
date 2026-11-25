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

    @Volatile private var listener: VoiceSttListener? = null
    @Volatile private var runtime: SherpaRuntime? = null
    @Volatile private var modelDir: File? = null

    private val lifecycleLock = Any()
    private val capturing = AtomicBoolean(false)
    private val preparingModel = AtomicBoolean(false)
    private var audioRecord: AudioRecord? = null
    private var captureThread: Thread? = null
    private var startThread: Thread? = null
    private var startGeneration: Long = 0L
    @Volatile private var started = false

    override fun isAvailable(): Boolean {
        // 1) 模型目录与类路径检测（P-07：绝不在主线程同步拷贝 ~70MB 模型文件）
        val dir = modelDirOverride ?: defaultModelDir()
        if (dir == null) {
            Log.i(TAG, "sherpa-onnx model dir not found: $dir")
            return false
        }
        val required = listOf("tokens.txt", "encoder.onnx", "decoder.onnx", "joiner.onnx")
        val missing = required.filter { !File(dir, it).isFile }
        if (missing.isNotEmpty()) {
            val bundled = runCatching {
                appContext.assets.list("sherpa-onnx/stream")?.toSet().orEmpty()
            }.getOrDefault(emptySet())
            if (!required.all { it in bundled }) {
                Log.w(TAG, "sherpa-onnx model missing files: $missing in $dir")
                return false
            }
            // 仅在后台线程异步预拷贝，不阻塞当前（可能为主线程的）调用方
            if (preparingModel.compareAndSet(false, true)) {
                Thread({
                    try {
                        copyModelFromAssets(dir)
                    } finally {
                        preparingModel.set(false)
                    }
                }, "sherpa-model-copy").start()
            }
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
        val dir = modelDir ?: run {
            listener?.onError(SttError.EngineUnavailable)
            return
        }
        val gen = synchronized(lifecycleLock) {
            if (started) return
            started = true
            ++startGeneration
        }
        // P-07（2026-11-24）：模型复制（单飞原子落盘）与 SherpaRuntime 初始化统一在后台线程执行，
        // 避免 ~70MB 磁盘拷贝与 ONNX 建图阻塞主线程；与 stop/destroy 共享 lifecycleLock 防止资源泄漏。
        val thread = Thread({
            try {
                val required = listOf("tokens.txt", "encoder.onnx", "decoder.onnx", "joiner.onnx")
                if (required.any { !File(dir, it).isFile }) {
                    copyModelFromAssets(dir)
                }
                val stillActiveAfterCopy = synchronized(lifecycleLock) { started && startGeneration == gen }
                if (!stillActiveAfterCopy) return@Thread
                if (required.any { !File(dir, it).isFile }) {
                    synchronized(lifecycleLock) {
                        if (startGeneration == gen) started = false
                    }
                    listener?.onError(SttError.EngineUnavailable)
                    return@Thread
                }
                val created = SherpaRuntime.create(appContext, dir, config)
                if (created == null) {
                    synchronized(lifecycleLock) {
                        if (startGeneration == gen) started = false
                    }
                    listener?.onError(SttError.EngineUnavailable)
                    return@Thread
                }
                val attached = synchronized(lifecycleLock) {
                    if (!started || startGeneration != gen) {
                        false
                    } else {
                        runtime = created
                        startAudioCapture()
                        true
                    }
                }
                if (!attached) {
                    created.destroy()
                }
            } catch (t: Throwable) {
                Log.e(TAG, "sherpa-onnx start failed", t)
                synchronized(lifecycleLock) {
                    if (startGeneration == gen) {
                        started = false
                        runtime?.destroy()
                        runtime = null
                    }
                }
                listener?.onError(SttError.Unknown)
            } finally {
                synchronized(lifecycleLock) {
                    if (startGeneration == gen) startThread = null
                }
            }
        }, "sherpa-stt-start")
        synchronized(lifecycleLock) {
            if (started && startGeneration == gen) {
                startThread = thread
                thread.start()
            }
        }
    }

    override fun stop() {
        val finalText = synchronized(lifecycleLock) {
            if (!started) return
            started = false
            startGeneration++
            startThread?.interrupt()
            startThread = null
            stopAudioCapture()
            // 拿到当前流式已解码的最终文本作为结果；如果什么都没有就推空列表
            try {
                runtime?.pollFinal().orEmpty()
            } catch (t: Throwable) {
                Log.w(TAG, "pollFinal failed", t)
                ""
            }
        }
        listener?.onResult(if (finalText.isEmpty()) emptyList() else listOf(finalText))
    }

    override fun destroy() {
        synchronized(lifecycleLock) {
            started = false
            startGeneration++
            startThread?.interrupt()
            startThread = null
            stopAudioCapture()
            runtime?.destroy()
            runtime = null
            listener = null
        }
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
    private fun copyModelFromAssets(dir: File): Boolean = synchronized(MODEL_COPY_LOCK) {
        if (!BuildConfig.SHERPA_ENABLED) return false
        val required = listOf("tokens.txt", "encoder.onnx", "decoder.onnx", "joiner.onnx")
        if (required.all { File(dir, it).isFile }) return true
        val assetBase = BuildConfig.SHERPA_MODEL_DIR.trim('/')
        return try {
            dir.mkdirs()
            required.all { name ->
                val target = File(dir, name)
                if (target.isFile) return@all true
                val tmp = File(dir, "$name.tmp")
                try {
                    appContext.assets.open("$assetBase/$name").use { input ->
                        tmp.outputStream().use { output -> input.copyTo(output) }
                    }
                    if (!tmp.renameTo(target)) {
                        tmp.copyTo(target, overwrite = true)
                        tmp.delete()
                    }
                    Log.i(TAG, "sherpa-onnx model installed from assets: $name")
                    true
                } catch (t: Throwable) {
                    runCatching { tmp.delete() }
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
        private val MODEL_COPY_LOCK = Any()
        // sherpa-onnx 的核心类全限定名，用于反射探测运行时是否已挂入
        const val RUNTIME_CLASS_FQCN = "com.k2fsa.sherpa.onnx.OnlineRecognizer"

        /** 16 kHz mono，与 sherpa-onnx 流式模型默认期望一致。 */
        private const val SAMPLE_RATE = 16_000

        /** 每次读取 100ms 音频（1600 samples @ 16kHz）。 */
        private const val FRAME_SAMPLES = 1_600
    }
}
