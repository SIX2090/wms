package com.factory.wms.util

import android.content.Context
import android.media.AudioManager
import android.media.ToneGenerator
import android.os.Build
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import android.util.Log

/**
 * 扫码音频 / 震动反馈（AI-MOB-SCAN-UX-01）。
 *
 * 为什么需要
 * ------------------------------------------------------------------
 * 仓库现场的特征是：环境嘈杂、工人戴手套、货架间光线差。
 * **工人基本不看屏幕**，如果扫中/扫失败没有任何声音和震动反馈，
 * 就必须盯着屏幕逐条确认 —— 这直接把扫码的效率优势抵消掉了。
 *
 * 设计要点
 * ------------------------------------------------------------------
 * 1. **中/失败必须能靠体感区分**：成功是「短震 + 高频嘀」，失败是「双震 + 低频嘟」。
 *    只震动不区分等于没反馈（工人不知道自己这一下扫上了没有）。
 * 2. **ToneGenerator 必须 release**：它是系统音频资源，用完不释放会泄漏，
 *    多次开关相机后可能拿不到 ToneGenerator（实测部分机型超过约 30 个实例就返回 null）。
 * 3. **不能抛异常**：反馈是锦上添花，无震动马达/静音模式/音频占用都不该让扫码崩掉。
 *    所有分支都吞异常，失败只打日志。
 * 4. **开关由用户控制**：`ProfileScreen` 提供开关，默认开（现场场景默认需要）。
 */
object ScanFeedback {

    private const val TAG = "ScanFeedback"

    /** 开关存储键（与 WmsRepository 的 wms_settings DataStore 同名，共用同一个文件）。 */
    private const val PREFS_NAME = "wms_settings"
    private const val KEY_ENABLED = "scan_feedback_enabled"

    /**
     * 开关的内存缓存。
     *
     * 为什么不在每次扫码时读 DataStore：DataStore 读是挂起 IO，
     * 而扫码回调在相机分析线程上、要求"立刻"出反馈；为一次震动去做磁盘 IO
     * 会引入可感知延迟，还可能因主线程等待而卡顿。
     * 这里在 [warmUp] 时读一次进内存，之后同步判断；设置页改动时再刷新。
     * 初值 true —— 现场场景默认需要反馈，宁可没设置过也有反馈。
     */
    @Volatile
    var enabled: Boolean = true
        private set

    /**
     * 预热开关状态。由 `WmsApplication` 在进程启动时调用一次，
     * 也可在设置页改动后调用以刷新缓存。
     */
    fun warmUp(context: Context) {
        try {
            val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            enabled = prefs.getBoolean(KEY_ENABLED, true)
        } catch (e: Exception) {
            Log.w(TAG, "读取扫码反馈开关失败，按默认（开启）处理", e)
            enabled = true
        }
    }

    /** 持久化开关（设置页调用）。 */
    fun setEnabled(context: Context, value: Boolean) {
        enabled = value
        try {
            context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                .edit()
                .putBoolean(KEY_ENABLED, value)
                .apply()
        } catch (e: Exception) {
            Log.w(TAG, "保存扫码反馈开关失败", e)
        }
    }

    /** 成功：高频短嘀（约 2.4kHz，穿透嘈杂环境）。 */
    private const val TONE_SUCCESS = ToneGenerator.TONE_CDMA_ALERT_CALL_GUARD

    /** 失败：低频警告音，与成功音在音高上明显拉开，闭眼也能分辨。 */
    private const val TONE_FAILURE = ToneGenerator.TONE_SUP_ERROR

    private const val SUCCESS_TONE_MS = 90
    private const val FAILURE_TONE_MS = 320

    /** 成功：单次短震（毫秒）。够短，连续扫不糊成一片。 */
    private const val SUCCESS_VIBRATE_MS = 45L

    /** 失败：双震 [等待, 震动, 等待, 震动]，节奏上与单次短震截然不同。 */
    private val FAILURE_VIBRATE_PATTERN = longArrayOf(0L, 80L, 90L, 80L)

    /**
     * 扫中且**成功加入清单**。
     */
    fun success(context: Context) {
        if (!enabled) return
        playTone(TONE_SUCCESS, SUCCESS_TONE_MS)
        vibrate(context, longArrayOf(0L, SUCCESS_VIBRATE_MS), -1)
    }

    /**
     * 扫中但**未匹配到物料**（或加入失败）。
     *
     * 与 [success] 在音高与震动节奏上双重区分 —— 现场靠手感/听感即可分辨，
     * 不用抬头看屏幕。
     */
    fun failure(context: Context) {
        if (!enabled) return
        playTone(TONE_FAILURE, FAILURE_TONE_MS)
        vibrate(context, FAILURE_VIBRATE_PATTERN, -1)
    }

    /**
     * 构建 ToneGenerator，拿不到时返回 null（静音模式、音频资源被占用等）。
     */
    private fun newToneGenerator(): ToneGenerator? = try {
        // streamType 用 MUSIC：STREAM_NOTIFICATION 静音时不出声，
        // 而现场手机常年静音防扰，MUSIC 音量通常仍可用。
        ToneGenerator(AudioManager.STREAM_MUSIC, 85)
    } catch (e: Exception) {
        Log.w(TAG, "ToneGenerator 创建失败（设备可能无音频输出）", e)
        null
    }

    private fun playTone(tone: Int, durationMs: Int) {
        val generator = newToneGenerator() ?: return
        try {
            generator.startTone(tone, durationMs)
        } catch (e: Exception) {
            Log.w(TAG, "播放提示音失败", e)
        } finally {
            // 必须释放：ToneGenerator 是系统音频资源，不释放会泄漏，
            // 多次开关相机后可能再也拿不到实例。
            // 延迟到音播完再 release，否则会把声音掐断。
            android.os.Handler(android.os.Looper.getMainLooper()).postDelayed({
                try {
                    generator.release()
                } catch (e: Exception) {
                    Log.w(TAG, "释放 ToneGenerator 失败", e)
                }
            }, (durationMs + 120).toLong())
        }
    }

    private fun vibrate(context: Context, pattern: LongArray, repeat: Int) {
        try {
            val vibrator = resolveVibrator(context) ?: return
            if (!vibrator.hasVibrator()) return
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                vibrator.vibrate(VibrationEffect.createWaveform(pattern, repeat))
            } else {
                @Suppress("DEPRECATION")
                vibrator.vibrate(pattern, repeat)
            }
        } catch (e: Exception) {
            Log.w(TAG, "震动失败（可能未授予 VIBRATE 权限）", e)
        }
    }

    private fun resolveVibrator(context: Context): Vibrator? {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            val manager = context.getSystemService(Context.VIBRATOR_MANAGER_SERVICE)
                as? VibratorManager
            manager?.defaultVibrator
        } else {
            @Suppress("DEPRECATION")
            context.getSystemService(Context.VIBRATOR_SERVICE) as? Vibrator
        }
    }
}
