package com.factory.wms

import android.app.Application
import android.util.Log
import com.factory.wms.data.api.AuthEventBus
import com.factory.wms.data.api.RetrofitClient
import com.factory.wms.data.repository.WmsRepository
import coil.ImageLoader
import coil.ImageLoaderFactory
import coil.util.DebugLogger
import com.factory.wms.util.ScanFeedback
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import java.io.File

class WmsApplication : Application(), ImageLoaderFactory {

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
        RetrofitClient.onUnauthorized = {
            AuthEventBus.notifyUnauthorized()
        }
        // P2-A: 清理 cacheDir/camera/ 下超过 24 小时的临时拍照文件，
        // 避免 FileProvider 缓存目录无限累积占用空间。
        cleanupStaleCameraCache()
        // AI-MOB-SCAN-UX-01：预热扫码反馈开关（默认开）。
        // 扫码回调在相机分析线程上要求"立刻"出反馈，不能在那时做磁盘 IO，
        // 故在进程启动时读一次进内存，之后同步判断。
        ScanFeedback.warmUp(this)
        // BUG-2026-09-12-011：预热离线待提交队列。
        //
        // OfflineQueueManager 挂载在 WmsRepository.offlineQueue（by lazy），其 init 块
        // 负责两件必须发生的事：① 复位进程被杀残留的 syncing 记录；② 注册网络恢复监听。
        // 若只在扫码页（ScanViewModel 首次访问）才触发，则用户"断网提交后没再打开扫码页"
        // 时这两件事都不会发生 —— 数据躺在库里既不补传也无人复位，
        // 离线队列对用户承诺的"联网后自动提交"就是空的。
        // 进程启动即预热，使该承诺与用户后续操作路径无关。
        warmUpOfflineQueue()
    }

    /**
     * 后台预热离线队列单例（不阻塞主线程）。
     *
     * 只做"拿到实例"这一件事：实例化本身极轻（仅建对象），真正的磁盘复位与网络注册
     * 在 [WmsRepository.offlineQueue] 的 init 里以协程方式异步执行。
     * 单例由 `synchronized` 保证幂等，重复调用无副作用。
     */
    private fun warmUpOfflineQueue() {
        appScope.launch {
            runCatching { repository.offlineQueue }
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
