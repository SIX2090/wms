package com.factory.wms

import android.app.Activity
import android.app.Application
import android.content.Context
import android.content.Intent
import android.content.pm.PackageInstaller
import androidx.test.core.app.ApplicationProvider
import com.factory.wms.update.*
import com.google.gson.Gson
import kotlinx.coroutines.*
import kotlinx.coroutines.test.*
import okhttp3.Protocol
import okhttp3.Response
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.io.File
import java.security.MessageDigest

@OptIn(ExperimentalCoroutinesApi::class)
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [31], application = Application::class)
class AppUpdateManagerTest {
    private val context = ApplicationProvider.getApplicationContext<Context>()
    private val prefs get() = context.getSharedPreferences("app_update", Context.MODE_PRIVATE)
    private val bytes = "test payload".toByteArray()
    private val release = UpdateRelease("com.factory.wms", 41, "test41", 26,
        "https://github.com/SIX2090/wms/releases/download/android-apk-900/wms-mobile-scan.apk",
        bytes.size.toLong(), MessageDigest.getInstance("SHA-256").digest(bytes)
            .joinToString("") { "%02x".format(it) }, "c".repeat(64), "a".repeat(40), "test")
    private val activity get() = Robolectric.buildActivity(Activity::class.java).setup().get()

    @Before fun reset() {
        prefs.edit().clear().commit()
        // Only this test Application's private update directory, no business storage.
        File(context.filesDir, "app_updates").listFiles()?.forEach { it.delete() }
    }

    private class Installer : UpdateInstaller {
        var permission = false
        var created = 0
        var committed = 0
        var live = false
        var failCommit = false
        var failQuery = false
        override fun permitted() = permission
        override fun create(release: UpdateRelease): Int { created++; live = true; return 7 }
        override fun commit(sessionId: Int, apk: File, nonce: String) {
            committed++
            check(!failCommit) { "synthetic space failure" }
        }
        override fun exists(sessionId: Int): Boolean {
            check(!failQuery) { "synthetic installer unavailable" }
            return live && sessionId == 7
        }
        override fun abandon(sessionId: Int) { live = false }
    }

    private inner class Harness(private val test: TestScope) {
        val installer = Installer()
        val gate = UpdateBusinessGate()
        val dispatcher = StandardTestDispatcher(test.testScheduler)
        var checks = 0
        var downloads = 0
        var verified = 0
        var badSignature = false
        var failChecks = false
        var currentRelease = release
        val client = UpdateDownloadClient(UpdateDownloadClient.client().newBuilder().addInterceptor { chain ->
            val request = chain.request()
            val content = when {
                request.url.encodedPath.contains("matching-refs") -> {
                    checks++
                    Gson().toJson(listOf(mapOf("ref" to "refs/tags/${currentRelease.tag}"))).toByteArray()
                }
                request.url.host == "api.github.com" -> Gson().toJson(mapOf("draft" to false,
                    "prerelease" to false, "target_commitish" to currentRelease.commitSha,
                    "body" to Gson().toJson(currentRelease))).toByteArray()
                else -> { downloads++; bytes }
            }
            Response.Builder().request(request).protocol(Protocol.HTTP_1_1).code(if (failChecks) 503 else 200)
                .message("synthetic").body(content.toResponseBody()).build()
        }.build())
        fun manager(version: Long = 40, ownGate: UpdateBusinessGate = gate) = AppUpdateManager(
            context, client, installer, { file, _ ->
                verified++; assertArrayEquals(bytes, file.readBytes())
                require(!badSignature) { "synthetic invalid signature" }
            }, ownGate, test.backgroundScope, { 1_000_000L + test.testScheduler.currentTime }, version, dispatcher)
    }

    @Test fun foregroundIntervalAndManualCheckWithoutDuplicateDownload() = runTest {
        val h = Harness(this); val manager = h.manager(); manager.recover()
        manager.foreground(activity); runCurrent()
        assertTrue(manager.state.value.ready); assertEquals(1, h.downloads)
        repeat(5) { manager.foreground(null); manager.foreground(activity) }
        runCurrent()
        assertEquals(1, h.checks); assertEquals(1, h.downloads)
        manager.check(); manager.check(); runCurrent()
        assertEquals(2, h.checks); assertEquals(1, h.downloads)
        assertEquals(0, h.installer.created)
        assertTrue(manager.state.value.message.contains("允许"))
    }

    @Test fun noUpdateIsThrottledButManualCheckAlwaysWorks() = runTest {
        val h = Harness(this); h.currentRelease = release.copy(versionCode = 40)
        val manager = h.manager(); manager.recover()
        manager.foreground(activity); runCurrent()
        repeat(3) { manager.foreground(activity) }; runCurrent()
        assertEquals(1, h.checks); assertEquals(0, h.downloads)
        manager.check(); runCurrent(); assertEquals(2, h.checks)
        assertTrue(manager.state.value.message.contains("没有更高"))
        advanceTimeBy(6 * 60 * 60 * 1000L + 1)
        manager.foreground(activity); runCurrent(); assertEquals(3, h.checks)
    }

    @Test fun failedAutomaticCheckIsThrottledAndManualRetryStillWorks() = runTest {
        val h = Harness(this); h.failChecks = true
        val manager = h.manager(); manager.recover(); manager.foreground(activity); runCurrent()
        assertTrue(manager.state.value.message.startsWith("更新未完成"))
        repeat(3) { manager.foreground(activity) }; runCurrent()
        assertEquals(1, h.checks)
        h.failChecks = false
        manager.check(); runCurrent()
        assertEquals(2, h.checks); assertTrue(manager.state.value.ready)
    }

    @Test fun grantedPermissionOnReturnInstallsOnceAndBlocksNewBusiness() = runTest {
        val h = Harness(this); val manager = h.manager(); manager.recover()
        manager.foreground(activity); runCurrent()
        manager.install(); runCurrent()
        assertEquals(0, h.installer.created) // Still denied, no assumption after opening Settings.
        h.installer.permission = true
        manager.foreground(activity); manager.install(); manager.install(); runCurrent()
        assertEquals(1, h.installer.created); assertEquals(1, h.installer.committed)
        assertFalse(h.gate.enterBusiness())
        assertTrue(manager.state.value.installing)
    }

    @Test fun inFlightBusinessDelaysInstallWithoutClearingPendingData() = runTest {
        val h = Harness(this); h.installer.permission = true
        assertTrue(h.gate.enterBusiness())
        val businessFile = File(context.filesDir, "synthetic-unsynced-draft")
        businessFile.writeText("original request ID and payload")
        val manager = h.manager(); manager.recover(); manager.foreground(activity); runCurrent()
        assertEquals(0, h.installer.created)
        assertTrue(manager.state.value.message.contains("等待"))
        h.gate.leaveBusiness(); advanceTimeBy(1001); runCurrent()
        assertEquals(1, h.installer.committed)
        assertEquals("original request ID and payload", businessFile.readText())
    }

    private fun callback(status: Int, correct: Boolean = true) = Intent().apply {
        val nonce = prefs.getString("nonce", "")!!
        action = "${context.packageName}.UPDATE_RESULT.$nonce"
        putExtra("wms_nonce", if (correct) nonce else "forged")
        putExtra(PackageInstaller.EXTRA_SESSION_ID, 7)
        putExtra(PackageInstaller.EXTRA_STATUS, status)
    }

    @Test fun forgedCallbackCannotReleaseInstallAndCancelRestoresBusiness() = runTest {
        val h = Harness(this); h.installer.permission = true
        val manager = h.manager(); manager.recover(); manager.foreground(activity); runCurrent()
        manager.receive(callback(PackageInstaller.STATUS_SUCCESS, correct = false))
        assertTrue(manager.state.value.installing); assertFalse(h.gate.enterBusiness())
        manager.receive(callback(PackageInstaller.STATUS_FAILURE_ABORTED))
        assertFalse(manager.state.value.installing)
        assertTrue(h.gate.enterBusiness()); h.gate.leaveBusiness()
        assertTrue(manager.state.value.ready)
        manager.foreground(activity); runCurrent()
        assertEquals(1, h.installer.created) // Cancellation does not create a confirmation loop.
    }

    @Test fun pendingUserActionIsRetainedInBackgroundAndShownOnReturn() = runTest {
        val h = Harness(this); h.installer.permission = true
        val manager = h.manager(); manager.recover(); manager.foreground(activity); runCurrent()
        manager.foreground(null)
        manager.receive(callback(PackageInstaller.STATUS_PENDING_USER_ACTION).putExtra(Intent.EXTRA_INTENT,
            Intent("synthetic.install.confirmation")))
        assertTrue(manager.state.value.message.contains("确认"))
        val host = activity
        manager.foreground(host)
        val launched = org.robolectric.Shadows.shadowOf(host).nextStartedActivity
        assertEquals("synthetic.install.confirmation", launched.action)
        assertEquals(1, h.installer.created)
    }

    @Test fun installTimeoutAbandonsSessionAndReleasesBusiness() = runTest {
        val h = Harness(this); h.installer.permission = true
        val manager = h.manager(); manager.recover(); manager.foreground(activity); runCurrent()
        advanceTimeBy(120_001); runCurrent()
        assertFalse(h.installer.live); assertFalse(manager.state.value.installing)
        assertTrue(manager.state.value.message.contains("超时"))
        assertTrue(h.gate.enterBusiness()); h.gate.leaveBusiness()
    }

    @Test fun failedVerificationOrCommitNeverLeavesBusinessFrozen() = runTest {
        val h = Harness(this); h.installer.permission = true; h.badSignature = true
        val manager = h.manager(); manager.recover(); manager.foreground(activity); runCurrent()
        assertEquals(0, h.installer.created); assertFalse(manager.state.value.ready)
        assertTrue(h.gate.enterBusiness()); h.gate.leaveBusiness()
        h.badSignature = false; h.installer.failCommit = true
        manager.check(); runCurrent()
        assertEquals(1, h.installer.created); assertFalse(manager.state.value.installing)
        assertTrue(h.gate.enterBusiness()); h.gate.leaveBusiness()
    }

    @Test fun processRecreationRestoresSessionAndSuccessfulVersionRetainsDrafts() = runTest {
        val h = Harness(this); h.installer.permission = true
        val manager = h.manager(); manager.recover(); manager.foreground(activity); runCurrent()
        val otherFile = File(context.filesDir, "synthetic-preserved-queue")
        otherFile.writeText("same owner and request ID")
        val newGate = UpdateBusinessGate()
        val recreated = h.manager(ownGate = newGate); recreated.recover()
        assertFalse(newGate.enterBusiness()); assertEquals(1, h.installer.created)
        h.installer.live = false
        recreated.receive(callback(PackageInstaller.STATUS_SUCCESS))
        assertTrue(newGate.enterBusiness()); newGate.leaveBusiness()
        val upgraded = h.manager(version = 41, ownGate = UpdateBusinessGate()); upgraded.recover()
        assertTrue(upgraded.state.value.message.contains("更新完成"))
        assertEquals("same owner and request ID", otherFile.readText())
        assertFalse(File(context.filesDir, "app_updates/update.apk").exists())
    }

    @Test fun unavailableInstallerDuringRecoveryCannotRaceBusinessOrCrashMonitor() = runTest {
        val h = Harness(this); h.installer.permission = true
        val manager = h.manager(); manager.recover(); manager.foreground(activity); runCurrent()
        h.installer.failQuery = true
        val gate = UpdateBusinessGate()
        val restored = h.manager(ownGate = gate); restored.recover()
        assertFalse(gate.enterBusiness()); assertTrue(restored.state.value.installing)
        advanceTimeBy(120_001); runCurrent()
        assertFalse(gate.enterBusiness()) // Unknown is not proof that a late install is impossible.
        h.installer.failQuery = false
        advanceTimeBy(1001); runCurrent()
        assertFalse(restored.state.value.installing)
        assertTrue(gate.enterBusiness()); gate.leaveBusiness()
    }
}
