package com.factory.wms

import android.app.Application
import android.util.Log
import com.factory.wms.data.api.AuthEventBus
import com.factory.wms.data.api.RetrofitClient
import com.factory.wms.data.repository.WmsRepository
import coil.ImageLoader
import coil.ImageLoaderFactory
import coil.util.DebugLogger
import com.factory.wms.util.CrashReporter
import com.factory.wms.util.ScanFeedback
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import java.io.File

class WmsApplication : Application(), ImageLoaderFactory {

    internal val appUpdates by lazy { com.factory.wms.update.AppUpdateManager(this) }

    /**
     * 进程级协程作用域，仅用于启动期的后台预热。
     *
     * 用 [SupervisorJob] 隔离失败：预热任务异常不得影响其他任务，也不得让 App 崩溃。
     * 生命周期等于进程，随进程结束回收——预热本身就是一次性动作，无需手动取消。
     */
    private val appScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    /**
     * 进程级 WmsRepository（BUG-2026-09-12-011）。
     *
     * 懒加载：仅在需要预热离线队列时才真正构造，避免给启动增加无谓开销。
     * 其内部持有的 DB / Retrofit 均为单例，多建一个 Repository 实例不产生重复资源。
     */
    private val repository: WmsRepository by lazy { WmsRepository(this) }

    override fun onCreate() {
        super.onCreate()
        installCrashLogger()
        // 主线程零 IO 置位启动恢复屏障：在任何 Activity/AuthViewModel/离线队列启动前，
        // 阻止业务写入与离线补传抢占 businessUpdateGate，确保后台 appUpdates.recover()
        // 必然先检查并接管残留安装会话。
        com.factory.wms.update.businessUpdateGate.beginStartupRecovery()
        RetrofitClient.onUnauthorized = {
            AuthEventBus.notifyUnauthorized()
        }
        // P-01 / P-03（2026-11-24）：将启动期磁盘 IO 统一移入 Dispatchers.IO 后台预热，
        // 不阻塞主线程冷启动。
        warmUpOfflineQueue()
        appScope.launch { cleanupStaleCameraCache() }
        // 异常信息仅保存在本机，由用户选择复制并反馈；启动时不自动上传。
    }

    /**
     * BUG-2026-09-13-001：「WMS扫码屡次停止运行」——现场只报一句系统弹窗，
     * 拿不到任何堆栈，导致一个确定性崩溃被含糊描述成"修了一百遍还是不行"。
     *
     * 这里装一个进程级未捕获异常处理器，把堆栈落到
     *   `filesDir/crash/last_crash.txt`
     * 供现场取回（开发者选项里的"错误报告"能直接看到，或用 adb 拉取）。
     *
     * 刻意**不**改变崩溃行为（不吞异常、不"假装没崩"）：崩溃该发生就发生，
     * 否则会掩盖真实缺陷、把崩溃变成静默的数据错误——那比崩溃更危险。
     * 本处理器只做一件事：把真相留下来。
     *
     * 只保留最近一次崩溃，避免反复崩溃时无限写盘。
     */
    private fun installCrashLogger() {
        val defaultHandler = Thread.getDefaultUncaughtExceptionHandler()
        Thread.setDefaultUncaughtExceptionHandler { thread, throwable ->
            runCatching {
                val dir = File(filesDir, "crash")
                if (!dir.exists()) dir.mkdirs()
                val sw = java.io.StringWriter()
                throwable.printStackTrace(java.io.PrintWriter(sw))
                val text = buildString {
                    append("time=").append(
                        java.text.SimpleDateFormat("yyyy-MM-dd HH:mm:ss", java.util.Locale.US)
                            .format(java.util.Date())
                    ).append('\n')
                    append("thread=").append(thread.name).append('\n')
                    append("version=").append(BuildConfig.VERSION_NAME)
                        .append(" (").append(BuildConfig.VERSION_CODE).append(")\n")
                    append("sdk=").append(android.os.Build.VERSION.SDK_INT)
                        .append(" device=").append(android.os.Build.MODEL)
                        .append(" rom=").append(android.os.Build.MANUFACTURER).append('\n')
                    append("---- stack ----\n").append(sw.toString())
                }
                File(dir, "last_crash.txt").writeText(text)
                Log.e(TAG, "捕获到未处理异常，堆栈已写入 filesDir/crash/last_crash.txt")
                // AI-MOB-CRASH-01：同一份崩溃再另存一份结构化 JSON（crash/pending_*.json），
                // 保留本机结构化记录；不在启动时自动上传。
                CrashReporter.writePendingReport(this, thread, throwable)
            }.onFailure {
                Log.e(TAG, "写入崩溃日志失败: ${it.message}")
            }
            // 交回系统默认处理，保持标准崩溃行为不变
            defaultHandler?.uncaughtException(thread, throwable)
        }
    }

    /**
     * 后台预热启动期磁盘依赖（不阻塞主线程）：
     * 1. 先恢复更新安装租约，保证早于离线队列的任意业务请求；
     * 2. 预热扫码反馈开关（SharedPreferences）；
     * 3. 预热离线队列单例（触发 Room 后台打开、复位 syncing、注册网络监听）；
     * 4. 清理超过 24 小时的临时相机缓存文件。
     */
    private fun warmUpOfflineQueue() {
        appScope.launch {
            try {
                runCatching { appUpdates.recover() }.onFailure {
                    Log.w(TAG, "更新状态暂不可用，可继续使用当前版本", it)
                }
            } finally {
                com.factory.wms.update.businessUpdateGate.endStartupRecovery()
                runCatching { appUpdates.onStartupRecoveryFinished() }
                    .onFailure { Log.w(TAG, "恢复前台更新状态失败: ${it.message}") }
            }
            runCatching { ScanFeedback.warmUp(this@WmsApplication) }
                .onFailure { Log.w(TAG, "扫码反馈开关预热失败: ${it.message}") }
            // 启动恢复屏障释放后触发一次离线队列预热与补传：
            // 若无残留安装会话，此前因屏障延后的补传将立即执行；
            // 若有残留安装会话，beginInstall() 已持有门闩，syncPending() 会安全等待安装结束。
            runCatching { repository.offlineQueue?.syncPending() }
                .onFailure { Log.w(TAG, "离线队列预热失败（不影响启动）: ${it.message}") }
        }
    }

    // Coil 2.x：网络下载走 ImageLoader.Builder.callFactory，
    // 复用 Retrofit 的 OkHttpClient（含 Bearer Token 拦截器），图片请求与 API 请求认证一致。
    override fun newImageLoader(): ImageLoader = ImageLoader.Builder(this)
        .callFactory { RetrofitClient.sharedOkHttpClient() }
        .apply {
            if (BuildConfig.DEBUG) logger(DebugLogger())
        }
        .build()

    private fun cleanupStaleCameraCache() {
        try {
            val cameraDir = File(cacheDir, "camera")
            if (!cameraDir.exists() || !cameraDir.isDirectory) return
            val cutoff = System.currentTimeMillis() - 24L * 60L * 60L * 1000L
            var cleanedCount = 0
            var cleanedBytes = 0L
            cameraDir.listFiles()?.forEach { f ->
                if (f.isFile && f.lastModified() < cutoff) {
                    val size = f.length()
                    if (f.delete()) {
                        cleanedCount += 1
                        cleanedBytes += size
                    }
                }
            }
            if (cleanedCount > 0) {
                Log.i(
                    TAG,
                    "已清理 cacheDir/camera/ 中 $cleanedCount 个超过 24h 的临时文件，" +
                        "释放约 $cleanedBytes 字节"
                )
            }
        } catch (e: Exception) {
            // 清理失败不应阻塞 App 启动
            Log.w(TAG, "清理 cacheDir/camera 失败: ${e.message}")
        }
    }

    private companion object {
        private const val TAG = "WmsApp"
    }
}
