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
    private val stateLock = Any()
    private val mutable = MutableStateFlow(UpdateUiState())
    val state = mutable.asStateFlow()
    private var foreground = false
    private var activity: android.app.Activity? = null
    private var pendingForegroundResume = false
    private val deferredBroadcasts = mutableListOf<Intent>()
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
        val parsedTarget = runCatching { UpdateRelease.parse(prefs.getString("target", "")!!) }.getOrNull()
        if (parsedTarget != null && version >= parsedTarget.versionCode) {
            clearSession()
            apk.delete()
            prefs.edit().remove("target").apply()
            synchronized(stateLock) { target = null }
            mutable.value = UpdateUiState("更新完成，当前版本 ${BuildConfig.VERSION_NAME}")
            return
        }
        val savedSession = prefs.getInt("session", -1)
        val savedNonce = prefs.getString("nonce", "") ?: ""
        val savedStartedAt = prefs.getLong("started", 0)
        synchronized(stateLock) {
            target = parsedTarget
            sessionId = savedSession
            nonce = savedNonce
            startedAt = savedStartedAt
        }
        if (savedSession >= 0) {
            val acquired = gate.beginInstall()
            synchronized(stateLock) { ownsGate = acquired }
            check(acquired) { "无法恢复更新安装状态" }
            if (sessionAlive(savedSession) != false) {
                mutable.value = UpdateUiState("正在恢复安装状态", ready = true, installing = true)
                monitorSession()
                return
            }
        }
        run {
            clearSession()
            if (parsedTarget != null && apk.exists()) {
                synchronized(stateLock) { autoInstall = false } // After a process death, recheck first, then explicit retry.
                mutable.value = UpdateUiState("更新包已保留，点安装更新继续", ready = true)
            }
        }
    }

    fun foreground(activity: android.app.Activity?) {
        val pendingConfirmation: Intent?
        val shouldCheck: Boolean
        val shouldInstall: Boolean
        synchronized(stateLock) {
            this.activity = activity
            foreground = activity != null
            if (!foreground) {
                pendingForegroundResume = false
                return
            }
            if (gate.isStartupRecoveryPending()) {
                pendingForegroundResume = true
                return
            }
            pendingForegroundResume = false
            pendingConfirmation = confirmation
            shouldCheck = pendingConfirmation == null && sessionId < 0
            shouldInstall = shouldCheck && target != null
        }
        if (pendingConfirmation != null) {
            launchConfirmation(pendingConfirmation)
            return
        }
        if (!shouldCheck) return
        check(false)
        if (shouldInstall && apk.exists()) installIfReady()
    }

    /** 后台启动恢复完成后，切回主线程补派发启动期间暂存的安装结果广播，并按需补执行前台检查/安装恢复。 */
    internal fun onStartupRecoveryFinished() {
        android.os.Handler(android.os.Looper.getMainLooper()).post {
            val queued = synchronized(stateLock) {
                if (deferredBroadcasts.isEmpty()) emptyList()
                else deferredBroadcasts.toList().also { deferredBroadcasts.clear() }
            }
            queued.forEach { handleReceive(it) }
            val resumeActivity = synchronized(stateLock) {
                if (pendingForegroundResume && foreground) {
                    pendingForegroundResume = false
                    activity
                } else {
                    null
                }
            }
            if (resumeActivity != null) {
                foreground(resumeActivity)
            }
        }
    }

    fun check(manual: Boolean = true) {
        scope.launch {
            if (gate.isStartupRecoveryPending()) {
                withContext(io) { gate.awaitStartupRecovery() }
                if (gate.isStartupRecoveryPending()) return@launch
            }
            if (!mutex.tryLock()) return@launch
            try {
                if (synchronized(stateLock) { sessionId >= 0 }) return@launch
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
                synchronized(stateLock) { target = release }
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
                synchronized(stateLock) { autoInstall = true }
                mutable.value = UpdateUiState("${release.versionName} 已准备好", ready = true)
            } catch (e: CancellationException) { throw e
            } catch (e: Exception) {
                val reason = when (e) {
                    is java.net.SocketTimeoutException -> "连接更新服务超时，请稍后重试或切换网络"
                    is java.net.UnknownHostException -> "无法连接更新服务，请检查网络后重试"
                    is java.net.SocketException -> "更新连接中断，请稍后重试或切换网络"
                    else -> e.message ?: "请稍后重试"
                }
                mutable.value = UpdateUiState("更新未完成：$reason")
            } finally { mutex.unlock() }
            installIfReady()
        }
    }

    fun install() {
        synchronized(stateLock) { autoInstall = true }
        installIfReady(requestPermission = true)
    }

    private fun installIfReady(requestPermission: Boolean = false) {
        if (gate.isStartupRecoveryPending()) return
        val canStart = synchronized(stateLock) { foreground && autoInstall && sessionId < 0 }
        if (!canStart || !mutable.value.ready) return
        if (!installer.permitted()) {
            mutable.value = mutable.value.copy(message = "更新已下载，请允许 WMS 安装应用后继续")
            if (requestPermission) runCatching {
                val host = synchronized(stateLock) { activity }
                host?.startActivity(Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                    Uri.parse("package:${context.packageName}")))
            }.onFailure { mutable.value = mutable.value.copy(message = "无法打开安装设置，请在系统设置中允许 WMS 安装应用") }
            return
        }
        scope.launch {
            if (gate.isStartupRecoveryPending()) {
                withContext(io) { gate.awaitStartupRecovery() }
                if (gate.isStartupRecoveryPending()) return@launch
            }
            if (!mutex.tryLock()) return@launch
            var committed = false
            try {
                val release = synchronized(stateLock) { target } ?: return@launch
                // Verify again after cache/process changes, before acquiring the business lease.
                withContext(io) { verify(apk, release) }
                val readyForLease = synchronized(stateLock) { foreground && autoInstall && sessionId < 0 }
                if (!readyForLease || !gate.beginInstall()) {
                    mutable.value = mutable.value.copy(message = "更新已就绪，等待当前业务操作结束")
                    return@launch
                }
                synchronized(stateLock) { ownsGate = true }
                val createdSessionId = installer.create(release)
                val createdNonce = UUID.randomUUID().toString()
                val createdStartedAt = now()
                synchronized(stateLock) {
                    sessionId = createdSessionId
                    nonce = createdNonce
                    startedAt = createdStartedAt
                }
                check(prefs.edit().putInt("session", createdSessionId).putString("nonce", createdNonce)
                    .putLong("started", createdStartedAt).commit()) { "无法保存安装会话" }
                mutable.value = UpdateUiState("正在安装更新，当前内容已保留", ready = true, installing = true)
                withContext(io) { installer.commit(createdSessionId, apk, createdNonce) }
                committed = true
                monitorSession()
            } catch (e: CancellationException) { throw e
            } catch (e: Exception) {
                cancelSession("安装未完成：${e.message ?: "请重试"}")
            } finally {
                val releaseLease = synchronized(stateLock) {
                    if (!committed && sessionId < 0 && ownsGate) {
                        ownsGate = false
                        true
                    } else {
                        false
                    }
                }
                if (releaseLease) gate.endInstall()
                mutex.unlock()
                val shouldRetry = synchronized(stateLock) { !ownsGate && autoInstall && foreground } &&
                    mutable.value.ready && !committed
                if (shouldRetry) {
                    delay(1000)
                    installIfReady()
                }
            }
        }
    }

    fun receive(intent: Intent) {
        val deferred = synchronized(stateLock) {
            if (gate.isStartupRecoveryPending()) {
                deferredBroadcasts.add(Intent(intent))
                true
            } else {
                false
            }
        }
        if (deferred) return
        handleReceive(intent)
    }

    private fun handleReceive(intent: Intent) {
        val id = intent.getIntExtra(PackageInstaller.EXTRA_SESSION_ID, -1)
        val matched = synchronized(stateLock) {
            sessionId >= 0 && id == sessionId &&
                intent.getStringExtra("wms_nonce") == nonce &&
                intent.action == "${context.packageName}.UPDATE_RESULT.$nonce"
        }
        if (!matched) return
        when (intent.getIntExtra(PackageInstaller.EXTRA_STATUS, PackageInstaller.STATUS_FAILURE)) {
            PackageInstaller.STATUS_PENDING_USER_ACTION -> {
                @Suppress("DEPRECATION")
                val next = intent.getParcelableExtra<Intent>(Intent.EXTRA_INTENT)
                if (next == null) { cancelSession("系统未提供安装确认，请重试"); return }
                val isFg = synchronized(stateLock) {
                    confirmation = next
                    foreground
                }
                mutable.value = mutable.value.copy(message = "请确认安装更新；也可取消后继续使用")
                if (isFg) launchConfirmation(next)
            }
            PackageInstaller.STATUS_SUCCESS -> {
                clearSession()
                synchronized(stateLock) { autoInstall = false }
                mutable.value = UpdateUiState("安装已完成，下次打开将核对新版本")
            }
            else -> cancelSession("安装已取消或失败，当前版本仍可使用，可点安装更新重试")
        }
    }

    private fun launchConfirmation(intent: Intent) {
        val host = synchronized(stateLock) { activity } ?: return
        runCatching { host.startActivity(intent) }
            .onSuccess { synchronized(stateLock) { confirmation = null } }
            .onFailure { cancelSession("无法打开安装确认，当前版本仍可使用") }
    }

    private fun monitorSession() {
        val observed = synchronized(stateLock) {
            if (monitor?.isActive == true) return
            sessionId
        }
        if (observed < 0) return
        val job = scope.launch {
            while (synchronized(stateLock) { sessionId == observed } && observed >= 0) {
                delay(1000)
                if (sessionAlive(observed) == false) {
                    clearSession()
                    synchronized(stateLock) { autoInstall = false }
                    mutable.value = UpdateUiState("安装会话已结束，请核对版本或重试", ready = apk.exists())
                } else {
                    val started = synchronized(stateLock) { startedAt }
                    if (now() - started >= 120_000L || now() < started) {
                        cancelSession("安装等待已超时，已保留更新包，可重新安装")
                    }
                }
            }
        }
        synchronized(stateLock) {
            if (sessionId == observed) monitor = job else job.cancel()
        }
    }

    private fun cancelSession(message: String) {
        val activeSession = synchronized(stateLock) {
            autoInstall = false
            sessionId
        }
        // Do not release writes while a still-live install can complete later.
        if (activeSession >= 0) {
            runCatching { installer.abandon(activeSession) }
            if (sessionAlive(activeSession) != false) {
                mutable.value = mutable.value.copy(message = "安装状态尚未核对，请先在系统界面完成或取消安装；必要时重启手机")
                synchronized(stateLock) {
                    if (startedAt == 0L) startedAt = now() - 120_000
                }
                monitorSession()
                return
            }
        }
        clearSession()
        val hasTarget = synchronized(stateLock) { target != null }
        mutable.value = UpdateUiState(message, ready = apk.exists() && hasTarget)
    }

    private fun clearSession() {
        val jobToCancel: Job?
        val shouldReleaseGate: Boolean
        synchronized(stateLock) {
            sessionId = -1
            jobToCancel = monitor
            monitor = null
            confirmation = null
            shouldReleaseGate = ownsGate
            ownsGate = false
        }
        jobToCancel?.cancel()
        prefs.edit().remove("session").remove("nonce").remove("started").apply()
        if (shouldReleaseGate) gate.endInstall()
    }

    private fun sessionAlive(id: Int = synchronized(stateLock) { sessionId }): Boolean? =
        runCatching { installer.exists(id) }.getOrNull()
}
