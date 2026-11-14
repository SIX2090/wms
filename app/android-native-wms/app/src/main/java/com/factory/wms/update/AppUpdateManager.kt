package com.factory.wms.update

import android.content.Context
import android.content.Intent
import android.content.pm.PackageInstaller
import android.net.Uri
import android.os.Build
import android.provider.Settings
import com.factory.wms.BuildConfig
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import java.io.File
import java.util.UUID

internal data class UpdateUiState(
    val message: String = "自动检查并下载已验收版本", val progress: Int? = null,
    val busy: Boolean = false, val ready: Boolean = false, val installing: Boolean = false
)

internal class AppUpdateManager(
    private val context: Context,
    private val downloads: UpdateDownloadClient = UpdateDownloadClient(),
    private val installer: UpdateInstaller = AndroidUpdateInstaller(context),
    private val verify: (File, UpdateRelease) -> Unit = ApkUpdateVerifier(context)::verify,
    private val gate: UpdateBusinessGate = businessUpdateGate,
    private val scope: CoroutineScope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate),
    private val now: () -> Long = System::currentTimeMillis,
    private val version: Long = BuildConfig.VERSION_CODE.toLong(),
    private val io: CoroutineDispatcher = Dispatchers.IO
) {
    private val prefs = context.getSharedPreferences("app_update", Context.MODE_PRIVATE)
    private val directory = File(context.filesDir, "app_updates")
    private val apk get() = File(directory, "update.apk")
    private val mutex = Mutex()
    private val mutable = MutableStateFlow(UpdateUiState())
    val state = mutable.asStateFlow()
    private var foreground = false
    private var activity: android.app.Activity? = null
    private var confirmation: Intent? = null
    private var target: UpdateRelease? = null
    private var sessionId = -1
    private var nonce = ""
    private var startedAt = 0L
    private var ownsGate = false
    private var autoInstall = true
    private var monitor: Job? = null

    /** Called before queue warmup, so a surviving session cannot race replay. */
    fun recover() {
        File(directory, "update.apk.part").delete()
        target = runCatching { UpdateRelease.parse(prefs.getString("target", "")!!) }.getOrNull()
        val release = target
        if (release != null && version >= release.versionCode) {
            clearSession()
            apk.delete()
            prefs.edit().remove("target").apply()
            target = null
            mutable.value = UpdateUiState("更新完成，当前版本 ${BuildConfig.VERSION_NAME}")
            return
        }
        sessionId = prefs.getInt("session", -1)
        nonce = prefs.getString("nonce", "") ?: ""
        startedAt = prefs.getLong("started", 0)
        if (sessionId >= 0) {
            ownsGate = gate.beginInstall()
            check(ownsGate) { "无法恢复更新安装状态" }
            if (sessionAlive() != false) {
                mutable.value = UpdateUiState("正在恢复安装状态", ready = true, installing = true)
                monitorSession()
                return
            }
        }
        run {
            clearSession()
            if (release != null && apk.exists()) {
                autoInstall = false // After a process death, recheck first, then explicit retry.
                mutable.value = UpdateUiState("更新包已保留，点安装更新继续", ready = true)
            }
        }
    }

    fun foreground(activity: android.app.Activity?) {
        this.activity = activity
        foreground = activity != null
        if (!foreground) return
        confirmation?.let { launchConfirmation(it); return }
        if (sessionId >= 0) return
        check(false)
        if (target != null && apk.exists()) installIfReady()
    }

    fun check(manual: Boolean = true) {
        scope.launch {
            if (!mutex.tryLock()) return@launch
            try {
                if (sessionId >= 0) return@launch
                val last = prefs.getLong("last_check", 0)
                if (!manual && last > 0 && now() >= last && now() - last < 6 * 60 * 60 * 1000L) return@launch
                mutable.value = UpdateUiState("正在检查更新", busy = true)
                prefs.edit().putLong("last_check", now()).apply()
                val release = withContext(io) { downloads.latest() }
                if (release == null || release.versionCode <= version) {
                    mutable.value = UpdateUiState(if (release == null)
                        "暂无已验收的更新，当前版本仍可使用" else "当前没有更高的稳定版本")
                    return@launch
                }
                release.validate(context.packageName, version, Build.VERSION.SDK_INT)
                target = release
                prefs.edit().putString("target", release.toJson()).apply()
                withContext(io) {
                    check(directory.isDirectory || directory.mkdirs()) { "无法创建更新目录" }
                    if (!apk.isFile || apk.length() != release.size || apk.sha256() != release.sha256) {
                        downloads.download(release, apk) { percent ->
                            mutable.value = UpdateUiState("正在下载 ${release.versionName}", percent, busy = true)
                        }
                    }
                    verify(apk, release)
                }
                autoInstall = true
                mutable.value = UpdateUiState("${release.versionName} 已准备好", ready = true)
            } catch (e: CancellationException) { throw e
            } catch (e: Exception) {
                mutable.value = UpdateUiState("更新未完成：${e.message ?: "请稍后重试"}")
            } finally { mutex.unlock() }
            installIfReady()
        }
    }

    fun install() { autoInstall = true; installIfReady(requestPermission = true) }

    private fun installIfReady(requestPermission: Boolean = false) {
        if (!foreground || !autoInstall || sessionId >= 0 || !mutable.value.ready) return
        if (!installer.permitted()) {
            mutable.value = mutable.value.copy(message = "更新已下载，请允许 WMS 安装应用后继续")
            if (requestPermission) runCatching {
                activity?.startActivity(Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                    Uri.parse("package:${context.packageName}")))
            }.onFailure { mutable.value = mutable.value.copy(message = "无法打开安装设置，请在系统设置中允许 WMS 安装应用") }
            return
        }
        scope.launch {
            if (!mutex.tryLock()) return@launch
            var committed = false
            try {
                val release = target ?: return@launch
                // Verify again after cache/process changes, before acquiring the business lease.
                withContext(io) { verify(apk, release) }
                if (!foreground || !autoInstall || !gate.beginInstall()) {
                    mutable.value = mutable.value.copy(message = "更新已就绪，等待当前业务操作结束")
                    return@launch
                }
                ownsGate = true
                sessionId = installer.create(release)
                nonce = UUID.randomUUID().toString()
                startedAt = now()
                check(prefs.edit().putInt("session", sessionId).putString("nonce", nonce)
                    .putLong("started", startedAt).commit()) { "无法保存安装会话" }
                mutable.value = UpdateUiState("正在安装更新，当前内容已保留", ready = true, installing = true)
                withContext(io) { installer.commit(sessionId, apk, nonce) }
                committed = true
                monitorSession()
            } catch (e: CancellationException) { throw e
            } catch (e: Exception) {
                cancelSession("安装未完成：${e.message ?: "请重试"}")
            } finally {
                if (!committed && sessionId < 0 && ownsGate) { gate.endInstall(); ownsGate = false }
                mutex.unlock()
                if (!ownsGate && autoInstall && foreground && mutable.value.ready && !committed) {
                    delay(1000)
                    installIfReady()
                }
            }
        }
    }

    fun receive(intent: Intent) {
        val id = intent.getIntExtra(PackageInstaller.EXTRA_SESSION_ID, -1)
        if (sessionId < 0 || id != sessionId || intent.getStringExtra("wms_nonce") != nonce ||
            intent.action != "${context.packageName}.UPDATE_RESULT.$nonce") return
        when (intent.getIntExtra(PackageInstaller.EXTRA_STATUS, PackageInstaller.STATUS_FAILURE)) {
            PackageInstaller.STATUS_PENDING_USER_ACTION -> {
                @Suppress("DEPRECATION")
                val next = intent.getParcelableExtra<Intent>(Intent.EXTRA_INTENT)
                if (next == null) { cancelSession("系统未提供安装确认，请重试"); return }
                confirmation = next
                mutable.value = mutable.value.copy(message = "请确认安装更新；也可取消后继续使用")
                if (foreground) launchConfirmation(next)
            }
            PackageInstaller.STATUS_SUCCESS -> {
                clearSession()
                autoInstall = false
                mutable.value = UpdateUiState("安装已完成，下次打开将核对新版本")
            }
            else -> cancelSession("安装已取消或失败，当前版本仍可使用，可点安装更新重试")
        }
    }

    private fun launchConfirmation(intent: Intent) {
        runCatching { activity?.startActivity(intent) }.onSuccess { confirmation = null }
            .onFailure { cancelSession("无法打开安装确认，当前版本仍可使用") }
    }

    private fun monitorSession() {
        if (monitor?.isActive == true) return
        val observed = sessionId
        monitor = scope.launch {
            while (sessionId == observed && observed >= 0) {
                delay(1000)
                if (sessionAlive() == false) {
                    clearSession()
                    autoInstall = false
                    mutable.value = UpdateUiState("安装会话已结束，请核对版本或重试", ready = apk.exists())
                } else if (now() - startedAt >= 120_000L || now() < startedAt) {
                    cancelSession("安装等待已超时，已保留更新包，可重新安装")
                }
            }
        }
    }

    private fun cancelSession(message: String) {
        autoInstall = false
        // Do not release writes while a still-live install can complete later.
        if (sessionId >= 0) {
            runCatching { installer.abandon(sessionId) }
            if (sessionAlive() != false) {
                mutable.value = mutable.value.copy(message = "安装状态尚未核对，请先在系统界面完成或取消安装；必要时重启手机")
                if (startedAt == 0L) startedAt = now() - 120_000
                monitorSession()
                return
            }
        }
        clearSession()
        mutable.value = UpdateUiState(message, ready = apk.exists() && target != null)
    }

    private fun clearSession() {
        sessionId = -1
        monitor?.cancel()
        monitor = null
        confirmation = null
        prefs.edit().remove("session").remove("nonce").remove("started").apply()
        if (ownsGate) { gate.endInstall(); ownsGate = false }
    }

    private fun sessionAlive(): Boolean? = runCatching { installer.exists(sessionId) }.getOrNull()
}
