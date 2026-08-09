package com.factory.wms.ui.viewmodel.voice

import android.content.Context
import android.util.Log
import java.io.File
import java.lang.reflect.Method

/**
 * sherpa-onnx 运行时反射 wrapper。
 *
 * 编译期只引用 JDK / Android SDK，不 import sherpa-onnx 任何类；
 * 通过 [Class.forName] + [java.lang.reflect.Method.invoke] 调用真实 API。
 * 这样 sherpa-onnx AAR 未引入时仍可编译；引入后无需改本类代码。
 *
 * 主要反射点（[sherpa-onnx 1.x API]）：
 *   - `OnlineRecognizer.fromTransducer(config, config)` 返回 recognizer
 *   - `recognizer.createStream()` 返回 OnlineStream
 *   - `stream.acceptWaveform(samples: FloatArray, sampleRate: Int)`
 *   - `recognizer.isReady(stream)` -> Boolean
 *   - `recognizer.decode(stream)` -> Unit
 *   - `recognizer.getResult(stream).text` -> String
 *   - `recognizer.reset(stream)` / `stream.release()` / `recognizer.release()`
 *
 * 实际音频流式解码由 AudioRecord 线程驱动，本类只暴露 [feed] / [pollPartial] /
 *   [pollFinal] 三个方法。
 */
internal class SherpaRuntime private constructor(
    private val recognizer: Any,
    private val stream: Any
) {
    private val acceptWaveform: Method
    private val isReady: Method
    private val decode: Method
    private val reset: Method
    private val getResult: Method
    private val resultText: Method
    private val releaseRecognizer: Method
    private val releaseStream: Method

    init {
        val recognizerCls = recognizer.javaClass
        val streamCls = stream.javaClass
        // 方法签名：acceptWaveform(float[], int) 在 stream 上；isReady/decode/reset/getResult 在 recognizer 上
        acceptWaveform = streamCls.getMethod(
            "acceptWaveform",
            FloatArray::class.java,
            Int::class.javaPrimitiveType
        )
        isReady = recognizerCls.getMethod("isReady", streamCls)
        decode = recognizerCls.getMethod("decode", streamCls)
        reset = recognizerCls.getMethod("reset", streamCls)
        getResult = recognizerCls.getMethod("getResult", streamCls)
        // recognizer.getResult(stream) 返回 OnlineRecognizerResult，含 getText()
        val resultCls = getResult.returnType
        resultText = resultCls.getMethod("getText")
        releaseRecognizer = recognizerCls.getMethod("release")
        releaseStream = streamCls.getMethod("release")
    }

    /** 投喂一帧 PCM samples（-1.0f..1.0f）和采样率。 */
    fun feed(samples: FloatArray, sampleRate: Int) {
        acceptWaveform.invoke(stream, samples, sampleRate)
    }

    fun ready(): Boolean = isReady.invoke(recognizer, stream) as Boolean

    fun decodeStep() {
        decode.invoke(recognizer, stream)
    }

    fun resetStream() {
        reset.invoke(recognizer, stream)
    }

    /** 返回当前已解码的部分文本（partial）。 */
    fun pollPartial(): String {
        if (!ready()) return ""
        decodeStep()
        val result = getResult.invoke(recognizer, stream)
        return (resultText.invoke(result) as? String).orEmpty()
    }

    /** 取一次最终结果并 reset stream，供一次性 utterance 使用。 */
    fun pollFinal(): String {
        if (!ready()) return ""
        decodeStep()
        val result = getResult.invoke(recognizer, stream)
        val text = (resultText.invoke(result) as? String).orEmpty()
        resetStream()
        return text
    }

    fun stop() {
        runCatching { resetStream() }
    }

    fun destroy() {
        runCatching { releaseStream.invoke(stream) }
        runCatching { releaseRecognizer.invoke(recognizer) }
    }

    companion object {
        private const val TAG = "SherpaRuntime"

        /** 探测 sherpa-onnx 核心类是否在 classpath（用于 isAvailable 提前判断）。 */
        fun probeClassloader(): Boolean = try {
            Class.forName(SherpaVoiceSttEngine.RUNTIME_CLASS_FQCN)
            true
        } catch (cnf: ClassNotFoundException) {
            false
        } catch (t: Throwable) {
            Log.w(TAG, "probeClassloader failed", t)
            false
        }

        /**
         * 创建 recognizer + stream 反射实例。
         * 失败时返回 null，由 [SherpaVoiceSttEngine.isAvailable] 决定回退。
         */
        fun create(
            @Suppress("UNUSED_PARAMETER") context: Context,
            modelDir: File,
            config: SttConfig
        ): SherpaRuntime? = try {
            // OnlineRecognizer.fromTransducer(OnlineModelConfig, OnlineRecognizerConfig)
            val recognizerCls = Class.forName(SherpaVoiceSttEngine.RUNTIME_CLASS_FQCN)
            val modelConfigCls = Class.forName("com.k2fsa.sherpa.onnx.OnlineModelConfig")
            val recognizerConfigCls = Class.forName("com.k2fsa.sherpa.onnx.OnlineRecognizerConfig")
            val featureConfigCls = Class.forName("com.k2fsa.sherpa.onnx.FeatureConfig")

            // tokens / encoder / decoder / joiner 路径
            val tokens = File(modelDir, "tokens.txt").absolutePath
            val encoder = File(modelDir, "encoder.onnx").absolutePath
            val decoder = File(modelDir, "decoder.onnx").absolutePath
            val joiner = File(modelDir, "joiner.onnx").absolutePath

            // OnlineModelConfig.transducer(...) 返回 OnlineModelConfig
            val transducer = modelConfigCls.getMethod(
                "transducer",
                String::class.java, String::class.java, String::class.java, String::class.java
            ).invoke(null, tokens, encoder, decoder, joiner)
            val modelConfig = modelConfigCls.getMethod("getTransducer").invoke(transducer)

            // OnlineRecognizerConfig 构造：直接 new + 设值（用 Builder 模式）
            val recConfigCtor = recognizerConfigCls.getConstructor()
            val recConfig = recConfigCtor.newInstance()
            recognizerConfigCls.getMethod("setModelConfig", modelConfigCls)
                .invoke(recConfig, modelConfig)

            // FeatureConfig
            val featConfigCtor = featureConfigCls.getConstructor()
            val featConfig = featConfigCtor.newInstance()
            featureConfigCls.getMethod("setSampleRate", Int::class.javaPrimitiveType)
                .invoke(featConfig, 16000)
            featureConfigCls.getMethod("setFeatureDim", Int::class.javaPrimitiveType)
                .invoke(featConfig, 80)
            recognizerConfigCls.getMethod("setFeatureConfig", featureConfigCls)
                .invoke(recConfig, featConfig)

            // OnlineRecognizer.fromTransducer(OnlineModelConfig, OnlineRecognizerConfig)
            val fromTransducer = recognizerCls.getMethod(
                "fromTransducer",
                modelConfigCls,
                recognizerConfigCls
            )
            val recognizer = fromTransducer.invoke(null, modelConfig, recConfig)

            // recognizer.createStream() -> OnlineStream
            val stream = recognizerCls.getMethod("createStream").invoke(recognizer)

            SherpaRuntime(recognizer, stream)
        } catch (cnf: ClassNotFoundException) {
            Log.w(TAG, "sherpa-onnx class not found", cnf)
            null
        } catch (t: Throwable) {
            Log.e(TAG, "sherpa-onnx create failed", t)
            null
        }
    }
}
