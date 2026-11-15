package com.factory.wms.util

import android.content.Context
import android.os.Build
import android.util.Log
import com.factory.wms.BuildConfig
import com.factory.wms.data.api.RetrofitClient
import com.factory.wms.data.model.CrashReportRequest
import com.google.gson.Gson
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import java.io.File

/**
 * 崩溃记录辅助工具。
 *
 * 崩溃回调将信息写入本机；应用启动不自动上传。用户可以在崩溃报告页
 * 复制 `last_crash.txt` 的内容，并自行反馈给维护人员。
 * 结构化记录与现有上报方法保留，避免清理历史信息或改变服务端接口。
 */
object CrashReporter {

    private const val TAG = "CrashReporter"
    private const val CRASH_DIR = "crash"
    private const val PENDING_PREFIX = "pending_"

    /** 与后端 stacktrace 字段上限一致（超出后端 400，故本地先截断）。 */
    private const val MAX_STACK_CHARS = 20000

    /** 待上报文件保留上限，超出删最旧，防反复崩溃 + 长期离线把文件越积越多。 */
    private const val MAX_PENDING_FILES = 20

    private val gson = Gson()

    /**
     * 把一次崩溃另存为结构化 JSON 待上报文件（`crash/pending_<ts>.json`）。
     *
     * 由 `WmsApplication.installCrashLogger()` 的崩溃回调调用。本方法自身
     * 不抛异常（调用方已 runCatching 兜底，此处再保一层，绝不影响崩溃主流程）。
     */
    fun writePendingReport(context: Context, thread: Thread, throwable: Throwable) {
        runCatching {
            val report = CrashReportRequest(
                appVersion = BuildConfig.VERSION_NAME,
                versionCode = BuildConfig.VERSION_CODE,
                androidSdk = Build.VERSION.SDK_INT,
                device = "${Build.MANUFACTURER} ${Build.MODEL} (${Build.DEVICE})".take(200),
                thread = thread.name.take(120),
                exception = (throwable.javaClass.name + ": " + (throwable.message ?: "")).take(300),
                stacktrace = Log.getStackTraceString(throwable).take(MAX_STACK_CHARS),
                occurredAt = System.currentTimeMillis()
            )
            val dir = File(context.filesDir, CRASH_DIR).apply { mkdirs() }
            File(dir, "$PENDING_PREFIX${report.occurredAt}.json").writeText(gson.toJson(report))
            pruneOldPending(dir)
        }.onFailure { Log.w(TAG, "写入待上报崩溃失败: ${it.message}") }
    }

    private fun pruneOldPending(dir: File) {
        val files = pendingFiles(dir)
        val excess = files.size - MAX_PENDING_FILES
        if (excess > 0) {
            files.take(excess).forEach { runCatching { it.delete() } }
        }
    }

    private fun pendingFiles(dir: File): List<File> =
        dir.listFiles()?.filter { it.isFile && it.name.startsWith(PENDING_PREFIX) }
            ?.sortedBy { it.lastModified() } ?: emptyList()

    /**
     * 联网时异步上传待上报崩溃。尽力而为：整体失败只记警告、不抛异常。
     * 仅供显式授权的调用方使用；应用启动不会调用此方法。
     */
    fun uploadPendingAsync(context: Context, scope: CoroutineScope) {
        val appContext = context.applicationContext
        scope.launch(Dispatchers.IO) {
            runCatching { uploadPending(appContext) }
                .onFailure { Log.w(TAG, "崩溃上报失败（保留待下次启动重试）: ${it.message}") }
        }
    }

    private suspend fun uploadPending(context: Context) {
        // 全新安装、从未配置服务器地址时 apiService 会抛错，直接跳过（文件保留）。
        if (RetrofitClient.getBaseUrl().isBlank()) return
        val networkMonitor = NetworkMonitor.getInstance(context)
        // 离线就不空发，留到下次启动。
        if (!networkMonitor.currentlyOnline()) return

        val dir = File(context.filesDir, CRASH_DIR)
        for (file in pendingFiles(dir)) {
            // 每发一条前重新确认在线：中途断网即停，剩余保留。
            if (!networkMonitor.currentlyOnline()) break
            val report = runCatching {
                gson.fromJson(file.readText(), CrashReportRequest::class.java)
            }.getOrNull()
            if (report == null) {
                // 解析不了的坏文件直接删，避免永远卡在这一条反复失败。
                runCatching { file.delete() }
                continue
            }
            val ok = runCatching {
                val resp = RetrofitClient.apiService.reportCrash(report)
                resp.isSuccessful && resp.body()?.isOk() == true
            }.getOrDefault(false)
            if (ok) {
                runCatching { file.delete() }
                Log.i(TAG, "崩溃报告已上报并清除: ${file.name}")
            } else {
                // 上报失败就停（弱网下逐条空发无意义），剩余保留待下次。
                break
            }
        }
    }
}
