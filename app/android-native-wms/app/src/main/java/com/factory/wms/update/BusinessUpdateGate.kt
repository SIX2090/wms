package com.factory.wms.update

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/** One process-wide lock: acquiring installation and starting a write are atomic. */
internal class UpdateBusinessGate {
    private var writers = 0
    private var installing = false
    /**
     * 启动期异步恢复更新租约前的内存屏障：
     * 由 WmsApplication.onCreate 在主线程零 IO 置位，后台 appUpdates.recover() 结束后复位。
     * 期间拒绝一切业务写入与离线补传抢占门闩，确保残留安装会话必然先拿到 beginInstall()。
     */
    private var startupRecoveryPending = false

    @Synchronized fun beginStartupRecovery() {
        startupRecoveryPending = true
    }

    @Synchronized fun endStartupRecovery() {
        startupRecoveryPending = false
        (this as Object).notifyAll()
    }

    @Synchronized fun isStartupRecoveryPending(): Boolean = startupRecoveryPending

    /**
     * 业务写入/离线补传入场检查：
     * 若启动期后台 appUpdates.recover() 尚未完成，短暂等待至其结束唤醒，
     * 既确保残留安装会话必然先拿到 beginInstall()，又不误伤无残留会话时的正常业务提交。
     */
    @Synchronized fun enterBusiness(waitForStartupRecoveryMs: Long = 2000L): Boolean {
        if (startupRecoveryPending && waitForStartupRecoveryMs > 0L) {
            val deadline = System.currentTimeMillis() + waitForStartupRecoveryMs
            while (startupRecoveryPending) {
                val remaining = deadline - System.currentTimeMillis()
                if (remaining <= 0L) break
                try {
                    (this as Object).wait(remaining)
                } catch (_: InterruptedException) {
                    Thread.currentThread().interrupt()
                    break
                }
            }
        }
        if (installing || startupRecoveryPending) return false
        writers++
        return true
    }

    /** 挂起入口：启动恢复期间切至 Dispatchers.IO 等待，绝不在主线程阻塞；平时走零开销快速路径。 */
    suspend fun awaitAndEnterBusiness(waitForStartupRecoveryMs: Long = 2000L): Boolean {
        if (!isStartupRecoveryPending()) return enterBusiness(0L)
        return withContext(Dispatchers.IO) { enterBusiness(waitForStartupRecoveryMs) }
    }

    @Synchronized fun leaveBusiness() {
        check(writers > 0)
        writers--
    }

    @Synchronized fun beginInstall(): Boolean {
        if (installing || writers != 0) return false
        installing = true
        return true
    }

    @Synchronized fun endInstall() { installing = false }

}

internal val businessUpdateGate = UpdateBusinessGate()
