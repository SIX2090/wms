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
 * AI-MOB-CRASH-01：崩溃**上报**（在既有本地崩溃捕获之上补"自动汇聚到服务器"）。
 *
 * ## 与既有机制的关系（增强，不是另起炉灶）
 *
 * 既有 BUG-2026-09-13-001 / BUG-2026-09-14-028 已提供**本地**崩溃闭环：
 * `WmsApplication.installCrashLogger()`（进程级唯一 UncaughtExceptionHandler）
 * 把堆栈写到 `crash/last_crash.txt`，下次启动 `MainActivity` 检测到就渲染
 * `CrashReportScreen` 让用户**手动截图/复制回传**。它的短板是：堆栈躺在设备上，
 * 要靠用户手动回传才能到开发者手里——现场不截图就永远"看不见"。
 *
 * 本类补上**自动上报**这一环：
 * - 捕获仍由既有 `installCrashLogger` 完成（它是唯一 handler，有破坏性测试
 *   `tests/verify_android_startup_crash_safety.py` 守护，不改动其注册与"不吞异常"语义）；
 *   仅在其中追加调用 [writePendingReport]，把同一份崩溃**另存一份结构化 JSON**
 *   到 `crash/pending_<ts>.json`，专供上报。
 * - [uploadPendingAsync] 在下次启动联网时把 `pending_*.json` 逐个 POST 到
 *   `api/mobile/crash_report`，成功才删，失败保留待下次——崩溃堆栈从此自动汇聚到
 *   服务器 `logs/crash_reports.log`，不再依赖用户手动回传。
 *
 * `last_crash.txt`（供 CrashReportScreen 展示 + adb 取回）与 `pending_*.json`
 * （供上报）各司其职，互不干扰。
 *
 * ## 崩溃回调里的铁律
 *
 * [writePendingReport] 在进程将死的崩溃回调里被调用，**只写本地文件**，
 * 绝不发网络 / 起协程 / 读库（不可靠且可能挂起，连"写盘"这最后一步都会丢）。
 * 网络上报全部推迟到下次启动的 [uploadPendingAsync]。
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
     * 在 [android.app.Application.onCreate] 用进程级作用域调用一次即可。
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
