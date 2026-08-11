package com.factory.wms.ui.viewmodel.voice

import android.content.Context
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.util.Log
import com.factory.wms.data.api.RetrofitClient
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.ByteArrayOutputStream
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicInteger

/**
 * 基于后端中转的云语音识别引擎（腾讯云一句话识别）。
 *
 * 解决 [AndroidVoiceSttEngine] 在国内设备 / 无 Google 服务场景下"卡在正在聆听"、
 * 而 [SherpaVoiceSttEngine] 又因模型未打包而不可用的问题：
 *
 * - 本地用 [AudioRecord] 采集 16kHz mono PCM16 语音，写入临时缓冲区；
 * - 用户停止说话（[stop]）时组装成 WAV，通过 [RetrofitClient] 上传到
 *   后端 `/mobile/api/asr`（走后端中转，App 端不暴露腾讯云密钥）；
 * - 后端调腾讯云一句话识别后返回中文文本，引擎把文本包装成
 *   [VoiceSttListener.onResult] 回调，供 [VoiceCommandViewModel] 做指令解析。
 *
 * 生命周期与另两个引擎一致：[start] -> 录音 -> [stop] -> 上传识别 -> 回调。
 * 云引擎 [isAvailable] 恒为 true（网络/密钥等问题在 [stop] 时异步回调错误），
 * 由 [VoiceSttEngineRegistry] 优先选用，极端情况下再 fallback 本地引擎。
 */
class CloudAsrVoiceSttEngine(
    private val appContext: Context
) : VoiceSttEngine {

    private var listener: VoiceSttListener? = null
    // 上传协程作用域：独立于引擎生命周期，destroy() 不会取消它。
    // 原因：ViewModel 在 stop() 之后会立即调用 destroy()，而云引擎的识别结果是
    // 异步上传获得的，若在此取消作用域，结果回调会被丢弃，UI 会一直得不到结果。
    private val uploadScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    // 上传并发计数：uploadScope 不在 destroy() 取消（见 destroy 注释），
    // 极端频繁触发时可能累积在途上传协程；用计数器加上限防护。
    private val activeUploads = AtomicInteger(0)

    @Volatile private var started = false

    // 录音状态
    private val capturing = AtomicBoolean(false)
    private var audioRecord: AudioRecord? = null
    private var captureThread: Thread? = null
    private val pcmBuffer = ByteArrayOutputStream()

    override fun isAvailable(): Boolean = true

    override fun start(config: SttConfig) {
        if (started) {
            Log.w(TAG, "start() called while already started, ignoring")
            return
        }
        pcmBuffer.reset()
        startAudioCapture()
        started = true
    }

    override fun stop() {
        if (!started) return
        started = false
        stopAudioCapture()
        val pcm = pcmBuffer.toByteArray()
        if (pcm.isEmpty()) {
            listener?.onError(SttError.NoMatch)
            return
        }
        val wavBytes = buildWav(pcm)
        // 并发上限防护：超过 MAX_CONCURRENT_UPLOADS 个在途上传时拒绝新上传，
        // 避免极端频繁触发导致协程无界累积（每个在途上传最坏 30s readTimeout 才结束）
        if (activeUploads.incrementAndGet() > MAX_CONCURRENT_UPLOADS) {
            activeUploads.decrementAndGet()
            listener?.onError(SttError.TooManyRequests)
            return
        }
        uploadScope.launch {
            try {
                uploadAndRecognize(wavBytes)
            } finally {
                activeUploads.decrementAndGet()
            }
        }
    }

    override fun destroy() {
        started = false
        stopAudioCapture()
        // 注意：不取消 uploadScope，也不清空 listener。
        // 云引擎的 stop() 是异步上传，ViewModel 在 stop() 后立即调用 destroy()，
        // 若在此取消 uploadScope / 置空 listener，已发起的识别结果将无法回调。
        // 上传协程是单次短任务，完成后自然结束，无累积泄漏。
        // （恶意/异常场景 readTimeout 最长 30s 后回调，UI 仍正常。）
    }

    override fun setListener(listener: VoiceSttListener?) {
        this.listener = listener
    }

    // ---------------- 音频采集：16kHz mono PCM16 -> ByteArrayOutputStream ----------------

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
                minBuf.coerceAtLeast(FRAME_BYTES) * 2
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
        val t = Thread({ captureLoop(record) }, "CloudAsrAudioCapture")
        captureThread = t
        t.start()
    }

    private fun captureLoop(record: AudioRecord) {
        val buf = ByteArray(FRAME_BYTES)
        while (capturing.get()) {
            val n = try {
                record.read(buf, 0, buf.size)
            } catch (t: Throwable) {
                Log.w(TAG, "AudioRecord.read failed", t)
                -1
            }
            if (n <= 0) continue
            pcmBuffer.write(buf, 0, n)
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

    // ---------------- 上传 + 识别 ----------------

    private suspend fun uploadAndRecognize(wavBytes: ByteArray) {
        val mediaType = "audio/wav".toMediaTypeOrNull()
        val requestBody = wavBytes.toRequestBody(mediaType)
        val part = MultipartBody.Part.createFormData(
            "audio",
            "voice_${System.currentTimeMillis()}.wav",
            requestBody
        )
        try {
            val response = RetrofitClient.apiService.asrAudio(part)
            val body = response.body()
            if (response.isSuccessful && body != null && body.isOk()) {
                val text = body.text
                if (!text.isNullOrBlank()) {
                    listener?.onResult(listOf(text))
                } else {
                    listener?.onError(SttError.NoMatch)
                }
            } else {
                val msg = body?.msg ?: "语音识别失败，请重试"
                listener?.onError(mapFailure(response.code(), msg))
            }
        } catch (e: Exception) {
            Log.w(TAG, "cloud ASR request failed", e)
            listener?.onError(SttError.NetworkError)
        }
    }

    private fun mapFailure(code: Int, msg: String): SttError = when (code) {
        400 -> SttError.ClientError
        500 -> SttError.ServerError
        502 -> SttError.ServerError
        429 -> SttError.TooManyRequests
        401, 403 -> SttError.EngineUnavailable
        else -> if (msg.contains("网络", ignoreCase = true)) SttError.NetworkError else SttError.ServerError
    }

    // ---------------- WAV 封装 ----------------

    private fun buildWav(pcm: ByteArray): ByteArray {
        if (pcm.isEmpty()) return pcm
        val byteRate = SAMPLE_RATE * CHANNELS * BITS_PER_SAMPLE / 8
        val blockAlign = CHANNELS * BITS_PER_SAMPLE / 8
        val dataSize = pcm.size
        val out = ByteArrayOutputStream(44 + dataSize)
        out.write("RIFF".toByteArray(Charsets.US_ASCII))
        writeLE32(out, 36 + dataSize)
        out.write("WAVE".toByteArray(Charsets.US_ASCII))
        out.write("fmt ".toByteArray(Charsets.US_ASCII))
        writeLE32(out, 16) // fmt chunk size
        writeLE16(out, 1) // PCM
        writeLE16(out, CHANNELS)
        writeLE32(out, SAMPLE_RATE)
        writeLE32(out, byteRate)
        writeLE16(out, blockAlign)
        writeLE16(out, BITS_PER_SAMPLE)
        out.write("data".toByteArray(Charsets.US_ASCII))
        writeLE32(out, dataSize)
        out.write(pcm)
        return out.toByteArray()
    }

    private fun writeLE32(out: ByteArrayOutputStream, v: Int) {
        out.write(v and 0xFF)
        out.write((v shr 8) and 0xFF)
        out.write((v shr 16) and 0xFF)
        out.write((v shr 24) and 0xFF)
    }

    private fun writeLE16(out: ByteArrayOutputStream, v: Int) {
        out.write(v and 0xFF)
        out.write((v shr 8) and 0xFF)
    }

    companion object {
        private const val TAG = "CloudAsrVoiceSttEngine"
        /** 16 kHz mono，与腾讯云一句话识别 16k_zh 服务一致。 */
        private const val SAMPLE_RATE = 16_000
        private const val CHANNELS = 1
        private const val BITS_PER_SAMPLE = 16
        /** 每次读取 100ms 音频（1600 samples x 2 bytes @16kHz）。 */
        private const val FRAME_BYTES = 3_200
        /** 同时在途的识别上传协程上限，超出直接回调 TooManyRequests。 */
        private const val MAX_CONCURRENT_UPLOADS = 3
    }
}