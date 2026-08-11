package com.factory.wms

import android.app.Application
import android.util.Log
import com.factory.wms.data.api.AuthEventBus
import com.factory.wms.data.api.RetrofitClient
import coil.ImageLoader
import coil.ImageLoaderFactory
import coil.util.DebugLogger
import java.io.File

class WmsApplication : Application(), ImageLoaderFactory {
    override fun onCreate() {
        super.onCreate()
        RetrofitClient.onUnauthorized = {
            AuthEventBus.notifyUnauthorized()
        }
        // P2-A: 清理 cacheDir/camera/ 下超过 24 小时的临时拍照文件，
        // 避免 FileProvider 缓存目录无限累积占用空间。
        cleanupStaleCameraCache()
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
                    "WmsApp",
                    "已清理 cacheDir/camera/ 中 $cleanedCount 个超过 24h 的临时文件，" +
                        "释放约 $cleanedBytes 字节"
                )
            }
        } catch (e: Exception) {
            // 清理失败不应阻塞 App 启动
            Log.w("WmsApp", "清理 cacheDir/camera 失败: ${e.message}")
        }
    }
}