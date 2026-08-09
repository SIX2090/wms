package com.factory.wms.ui.viewmodel.voice

import android.content.Context
import android.util.Log
import java.io.File

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
 * 当前实现状态：骨架已就位，提供完整接口 + 反射 wrapper；AudioRecord 录音 / 实时解码
 * 留给后续 PR（见 TODO 标记）。本 PR 主要目的是让 [VoiceSttEngineRegistry] 接入 sherpa 路径，
 *   并验证 isAvailable / start / stop / destroy 生命周期。
 */
class SherpaVoiceSttEngine(
    private val appContext: Context,
    private val modelDirOverride: File? = null
) : VoiceSttEngine {

    private var listener: VoiceSttListener? = null
    private var runtime: SherpaRuntime? = null
    private var started = false
    private var modelDir: File? = null

    override fun isAvailable(): Boolean {
        // 1) 模型文件存在性
        val dir = modelDirOverride ?: defaultModelDir()
        if (dir == null || !dir.isDirectory) {
            Log.i(TAG, "sherpa-onnx model dir not found: $dir")
            return false
        }
        val required = listOf("tokens.txt", "encoder.onnx", "decoder.onnx", "joiner.onnx")
        val missing = required.filter { !File(dir, it).isFile }
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
            started = true
            // TODO 第二阶段：启动 AudioRecord 录音线程，把 PCM 16k mono 16-bit 推给
            //   runtime.feed(stream, samples)，并轮询 runtime.getPartial(stream)
            //   通过 listener.onPartial 推送。本 PR 仅占位。
            listener?.onPartial("（sherpa-onnx 引擎待接入音频 pipeline）")
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
        runtime?.stop()
    }

    override fun destroy() {
        started = false
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

    private fun defaultModelDir(): File? {
        val base = appContext.filesDir ?: return null
        return File(base, "sherpa-onnx/stream")
    }

    companion object {
        private const val TAG = "SherpaVoiceSttEngine"
        // sherpa-onnx 的核心类全限定名，用于反射探测运行时是否已挂入
        const val RUNTIME_CLASS_FQCN = "com.k2fsa.sherpa.onnx.OnlineRecognizer"
    }
}
