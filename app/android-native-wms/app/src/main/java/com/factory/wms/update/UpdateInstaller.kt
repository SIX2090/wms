package com.factory.wms.update

import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageInstaller
import android.os.Build
import java.io.File

internal interface UpdateInstaller {
    fun permitted(): Boolean
    fun create(release: UpdateRelease): Int
    fun commit(sessionId: Int, apk: File, nonce: String)
    fun exists(sessionId: Int): Boolean
    fun abandon(sessionId: Int)
}

internal class AndroidUpdateInstaller(private val context: Context) : UpdateInstaller {
    private val installer get() = context.packageManager.packageInstaller
    override fun permitted(): Boolean = context.packageManager.canRequestPackageInstalls()
    override fun create(release: UpdateRelease): Int {
        val params = PackageInstaller.SessionParams(PackageInstaller.SessionParams.MODE_FULL_INSTALL)
        params.setAppPackageName(context.packageName)
        params.setSize(release.size)
        if (Build.VERSION.SDK_INT >= 31) params.setRequireUserAction(
            PackageInstaller.SessionParams.USER_ACTION_NOT_REQUIRED)
        return installer.createSession(params)
    }

    override fun commit(sessionId: Int, apk: File, nonce: String) {
        val result = Intent(context, UpdateInstallReceiver::class.java)
            .setAction("${context.packageName}.UPDATE_RESULT.$nonce")
            .putExtra("wms_nonce", nonce)
        // The system adds result extras; mutable is required. The component is explicit
        // and non-exported, and a per-session nonce prevents stale/foreign callbacks.
        val flags = PendingIntent.FLAG_UPDATE_CURRENT or
            (if (Build.VERSION.SDK_INT >= 31) PendingIntent.FLAG_MUTABLE else 0)
        val pending = PendingIntent.getBroadcast(context, sessionId, result, flags)
        installer.openSession(sessionId).use { session ->
            session.openWrite("base.apk", 0, apk.length()).use { output ->
                apk.inputStream().use { it.copyTo(output) }
                session.fsync(output)
            }
            session.commit(pending.intentSender)
        }
    }

    override fun exists(sessionId: Int): Boolean = installer.mySessions.any { it.sessionId == sessionId }
    override fun abandon(sessionId: Int) { installer.abandonSession(sessionId) }
}
