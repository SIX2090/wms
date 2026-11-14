package com.factory.wms

import android.app.Application
import android.content.Context
import androidx.test.core.app.ApplicationProvider
import com.factory.wms.data.api.RetrofitClient
import com.factory.wms.update.*
import com.google.gson.Gson
import okhttp3.Interceptor
import okhttp3.OkHttpClient
import okhttp3.Protocol
import okhttp3.Response
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.io.File
import java.io.IOException
import java.security.MessageDigest
import java.util.concurrent.CountDownLatch
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [31], application = Application::class)
class UpdateProtocolTest {
    private val context = ApplicationProvider.getApplicationContext<Context>()
    private val bytes = "synthetic APK bytes".toByteArray()
    private val hash = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
    private fun release() = UpdateRelease("com.factory.wms", 41, "test-41", 26,
        "https://github.com/SIX2090/wms/releases/download/android-apk-900/wms-mobile-scan.apk",
        bytes.size.toLong(), hash, "b".repeat(64), "a".repeat(40), "test")

    private fun client(terminal: (okhttp3.Request) -> Response): UpdateDownloadClient {
        val calls = UpdateDownloadClient.client().newBuilder().addInterceptor(Interceptor { chain ->
            terminal(chain.request())
        }).build()
        return UpdateDownloadClient(calls)
    }
    private fun reply(request: okhttp3.Request, body: ByteArray, code: Int = 200, next: String? = null) =
        Response.Builder().request(request).protocol(Protocol.HTTP_1_1).code(code).message("synthetic")
            .body(body.toResponseBody()).apply { if (next != null) header("Location", next) }.build()

    @Test fun trustedChannelSelectsHighestVersionIndependentOfTagOrder() {
        val latest = release()
        val old = latest.copy(versionCode = 40)
        val c = client { req ->
            val body = if (req.url.encodedPath.contains("matching-refs")) {
                Gson().toJson(listOf(mapOf("ref" to "refs/tags/${old.tag}"),
                    mapOf("ref" to "refs/tags/${latest.tag}")))
            } else Gson().toJson(mapOf("draft" to false, "prerelease" to false,
                "target_commitish" to latest.commitSha, "body" to Gson().toJson(latest)))
            reply(req, body.toByteArray())
        }
        assertEquals(latest, c.latest())
    }

    @Test fun persistedReleaseUsesExplicitProtocolKeysAndRoundTrips() {
        val r = release()
        assertEquals(r, UpdateRelease.parse(r.toJson()))
        val obj = com.google.gson.JsonParser.parseString(r.toJson()).asJsonObject
        assertEquals("com.factory.wms", obj["packageName"].asString)
        assertEquals(41L, obj["versionCode"].asLong)
    }

    @Test fun noStableRecordIsNotReplacedByLatestCandidate() {
        var requests = 0
        val c = client { req -> requests++; reply(req, "[]".toByteArray()) }
        assertNull(c.latest())
        assertEquals(1, requests)
    }

    @Test fun forgedReleaseBodyCannotChangeTagIdentity() {
        val r = release()
        val c = client { req -> reply(req, (if (req.url.encodedPath.contains("matching-refs"))
            Gson().toJson(listOf(mapOf("ref" to "refs/tags/${r.tag}"))) else
            Gson().toJson(mapOf("draft" to false, "prerelease" to false,
                "target_commitish" to r.commitSha, "body" to Gson().toJson(r.copy(versionCode = 42)))))
            .toByteArray()) }
        assertThrows(IllegalArgumentException::class.java) { c.latest() }
    }

    @Test fun downloadIsAtomicAndDoesNotUseBusinessCredentials() {
        RetrofitClient.setSession("https://warehouse.example.invalid/", "synthetic-business-token")
        try {
            var requests = 0
            val c = client { req ->
                requests++
                assertNull(req.header("Authorization")); assertNull(req.header("Cookie"))
                if (requests == 1) reply(req, byteArrayOf(), 302,
                    "https://release-assets.githubusercontent.com/synthetic.apk?signature=test")
                else reply(req, bytes)
            }
            val output = File(context.cacheDir, "update-protocol.apk")
            output.delete()
            val progress = mutableListOf<Int>()
            c.download(release(), output, progress::add)
            assertArrayEquals(bytes, output.readBytes())
            assertFalse(File(output.parentFile, output.name + ".part").exists())
            assertEquals(100, progress.last())
            assertEquals(2, requests)
        } finally { RetrofitClient.setSession("", null) }
    }

    @Test fun invalidUrlAndEveryUnsafeRedirectAreRejectedBeforeNextRequest() {
        for (url in listOf("http://github.com/a", "https://github.com:444/a",
                "https://github.com.evil.invalid/a", "https://user:pass@github.com/a",
                "https://evil.invalid/a", "https://github.com/a#fragment")) {
            assertThrows(IllegalArgumentException::class.java) { checkedUpdateUrl(url) }
            var requests = 0
            val c = client { req -> requests++; reply(req, byteArrayOf(), 302, url) }
            assertThrows(IllegalArgumentException::class.java) {
                c.download(release(), File(context.cacheDir, "unsafe.apk")) {}
            }
            assertEquals(1, requests)
        }
    }

    @Test fun badHashTruncatedAndOversizedBodiesLeaveNoInstallableFile() {
        for (body in listOf("changed APK bytes!!".toByteArray(), bytes.dropLast(1).toByteArray(), bytes + 1)) {
            val output = File(context.cacheDir, "rejected.apk")
            output.delete()
            val c = client { req -> reply(req, body) }
            assertThrows(IllegalArgumentException::class.java) { c.download(release(), output) {} }
            assertFalse(output.exists())
            assertFalse(File(output.parentFile, output.name + ".part").exists())
        }
    }

    @Test fun unsupportedWrongPackageSameAndOlderVersionsAreRejected() {
        val r = release()
        for (bad in listOf(r.copy(packageName = "other.app"), r.copy(versionCode = 40),
                r.copy(versionCode = 1), r.copy(minSdk = 32), r.copy(size = MAX_APK_BYTES + 1),
                r.copy(url = "https://github.com/SIX2090/wms/releases/latest/download/wms-mobile-scan.apk"))) {
            assertThrows(IllegalArgumentException::class.java) { bad.validate("com.factory.wms", 40, 31) }
        }
    }

    @Test fun realApkVerifierRejectsArbitraryFileDespiteMatchingManifestHash() {
        val output = File(context.cacheDir, "not-an-apk.apk")
        output.writeBytes(bytes)
        assertThrows(Exception::class.java) { ApkUpdateVerifier(context).verify(output, release()) }
    }

    @Test fun businessAndInstallCannotWinTheSameRaceAndLeaseAlwaysReleases() {
        val workers = Executors.newFixedThreadPool(2)
        try {
            repeat(100) {
                val gate = UpdateBusinessGate()
                val start = CountDownLatch(1)
                val entered = CountDownLatch(2)
                val leave = CountDownLatch(1)
                val writer = workers.submit<Boolean> {
                    start.await(); val ok = gate.enterBusiness(); entered.countDown(); leave.await()
                    if (ok) gate.leaveBusiness()
                    ok
                }
                val install = workers.submit<Boolean> {
                    start.await(); val ok = gate.beginInstall(); entered.countDown(); leave.await()
                    if (ok) gate.endInstall()
                    ok
                }
                start.countDown()
                assertTrue(entered.await(2, TimeUnit.SECONDS)); leave.countDown()
                assertTrue(writer.get() xor install.get())
                assertTrue(gate.enterBusiness()); gate.leaveBusiness()
            }
        } finally { workers.shutdownNow() }
    }

    @Test fun everyNativeWriteIsBlockedBeforeTransportWhileInstallationOwnsLease() {
        val gate = businessUpdateGate
        assertTrue(gate.beginInstall())
        try {
            var sent = 0
            val calls = RetrofitClient.sharedOkHttpClient().newBuilder().addInterceptor { chain ->
                sent++; reply(chain.request(), "{}".toByteArray())
            }.build()
            for (path in listOf("api/inbound", "api/outbound", "api/stocktake", "api/opening_stock",
                    "api/mobile/inbound_draft", "api/mobile/voice_out_draft")) {
                val body = "{}".toResponseBody() // No socket: guard executes first.
                val request = okhttp3.Request.Builder().url("https://warehouse.example.invalid/$path")
                    .post(okhttp3.RequestBody.create(null, body.bytes())).build()
                assertThrows(IOException::class.java) { calls.newCall(request).execute() }
            }
            assertEquals(0, sent)
        } finally { gate.endInstall() }
    }
}
