package com.factory.wms

import android.app.Application
import android.content.Context
import androidx.test.core.app.ApplicationProvider
import com.factory.wms.update.*
import com.google.gson.Gson
import okhttp3.Protocol
import okhttp3.Response
import okhttp3.ResponseBody.Companion.toResponseBody
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okhttp3.mockwebserver.SocketPolicy
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.io.File
import java.io.IOException
import java.net.SocketTimeoutException
import java.net.InetAddress
import java.security.MessageDigest
import java.util.concurrent.TimeUnit

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [31], application = Application::class)
class UpdateChannelTest {
    private val context = ApplicationProvider.getApplicationContext<Context>()
    private val bytes = "synthetic fixed-signed APK transport".toByteArray()
    private val release = UpdateRelease("com.factory.wms.mobile", 51, "test51", 26,
        "https://github.com/SIX2090/wms/releases/download/android-apk-900-attempt-1/wms-mobile-scan.apk",
        bytes.size.toLong(), MessageDigest.getInstance("SHA-256").digest(bytes)
            .joinToString("") { "%02x".format(it) }, "b".repeat(64), "a".repeat(40), "synthetic")

    private fun reply(request: okhttp3.Request, body: String, code: Int = 200) =
        Response.Builder().request(request).protocol(Protocol.HTTP_1_1).code(code).message("synthetic")
            .body(body.toResponseBody()).build()

    private fun client(terminal: (okhttp3.Request) -> Response) = UpdateDownloadClient(
        UpdateDownloadClient.client().newBuilder().addInterceptor { terminal(it.request()) }.build())

    @Test fun publicStaticChannelWorksWhenRestApiQuotaIsExhaustedWithoutCallingApi() {
        val requested = mutableListOf<String>()
        val c = client { req ->
            requested += req.url.toString()
            assertNull(req.header("Authorization")); assertNull(req.header("Cookie"))
            assertNotEquals("api.github.com", req.url.host)
            if (req.url.toString() == "https://github.com/SIX2090/wms/releases/download/android-mobile-stable-channel/update.json") reply(req, Gson().toJson(mapOf("tag" to release.tag)))
            else {
                assertEquals("/SIX2090/wms/releases/download/${release.tag}/update.json", req.url.encodedPath)
                reply(req, release.toJson())
            }
        }
        assertEquals(release, c.latest())
        assertEquals(2, requested.size)
    }

    @Test fun candidateOrExternalDiscoveryCannotBecomeStableAndDoesNotFallBack() {
        for (tag in listOf("android-apk-900-attempt-1", "https://evil.invalid/manifest", "../other", "")) {
            var calls = 0
            val c = client { req -> calls++; reply(req, Gson().toJson(mapOf("tag" to tag))) }
            assertThrows(IllegalArgumentException::class.java) { c.latest() }
            assertEquals(1, calls)
        }
    }

    @Test fun staticRecordTagVersionAndCommitMustMatchBeforeDownload() {
        for (bad in listOf(release.copy(versionCode = 52), release.copy(commitSha = "c".repeat(40)))) {
            var apiCalls = 0
            val c = client { req ->
                if (req.url.host == "api.github.com") apiCalls++
                reply(req, if (req.url.toString() == "https://github.com/SIX2090/wms/releases/download/android-mobile-stable-channel/update.json")
                    Gson().toJson(mapOf("tag" to release.tag)) else bad.toJson())
            }
            assertThrows(IllegalArgumentException::class.java) { c.latest() }
            assertEquals(0, apiCalls)
        }
    }

    @Test fun missingPublicChannelRetainsOriginalImmutableApiProtocol() {
        var channelCalls = 0; var apiCalls = 0
        val c = client { req ->
            if (req.url.toString() == "https://github.com/SIX2090/wms/releases/download/android-mobile-stable-channel/update.json") { channelCalls++; reply(req, "", 404) }
            else { apiCalls++; reply(req, "[]") }
        }
        assertNull(c.latest())
        assertEquals(1, channelCalls); assertEquals(1, apiCalls)
    }

    @Test fun metadataTimeoutRetriesOnceAndThenUsesStaticRecord() {
        var attempts = 0
        val c = client { req ->
            if (req.url.toString() == "https://github.com/SIX2090/wms/releases/download/android-mobile-stable-channel/update.json") {
                attempts++
                if (attempts == 1) throw SocketTimeoutException("Read timed out")
                reply(req, Gson().toJson(mapOf("tag" to release.tag)))
            } else reply(req, release.toJson())
        }
        assertEquals(release, c.latest())
        assertEquals(2, attempts)
    }

    @Test fun rateLimitAndPlainForbiddenAreDistinguishedAndNotRetried() {
        for (limited in listOf(false, true)) {
            var apiCalls = 0
            val c = client { req ->
                if (req.url.toString() == "https://github.com/SIX2090/wms/releases/download/android-mobile-stable-channel/update.json") reply(req, "", 404)
                else {
                    apiCalls++
                    reply(req, "", 403).newBuilder().apply {
                        if (limited) header("X-RateLimit-Remaining", "0")
                    }.build()
                }
            }
            val error = assertThrows(IOException::class.java) { c.latest() }
            assertTrue(error.message!!.contains(if (limited) "限流" else "拒绝访问"))
            assertEquals(1, apiCalls)
        }
    }

    @Test fun realStalledDownloadRetriesAndPublishesOnlyCompleteHashVerifiedFile() {
        val server = MockWebServer()
        server.start(InetAddress.getByName("127.0.0.1"), 0)
        val output = File(context.cacheDir, "channel-retry.apk")
        output.delete()
        try {
            server.enqueue(MockResponse().setSocketPolicy(SocketPolicy.NO_RESPONSE))
            server.enqueue(MockResponse().setBody(okio.Buffer().write(bytes)))
            val http = UpdateDownloadClient.client().newBuilder()
                .readTimeout(100, TimeUnit.MILLISECONDS).retryOnConnectionFailure(false).build()
            val c = UpdateDownloadClient(okhttp3.Call.Factory { req ->
                assertNull(req.header("Authorization")); assertNull(req.header("Cookie"))
                http.newCall(req.newBuilder().url(server.url("/synthetic.apk")
                    .newBuilder().host("127.0.0.1").build()).build())
            })
            c.download(release, output) {}
            assertEquals(2, server.requestCount)
            assertArrayEquals(bytes, output.readBytes())
            assertFalse(File(output.parentFile, output.name + ".part").exists())
        } finally { server.shutdown(); output.delete() }
    }

    @Test fun exhaustedTimeoutsPreserveExistingApkAndRemovePartialFile() {
        var attempts = 0
        val output = File(context.cacheDir, "channel-failed-retry.apk")
        output.writeText("existing verified update")
        val c = client { _ -> attempts++; throw SocketTimeoutException("Read timed out") }
        try {
            assertThrows(SocketTimeoutException::class.java) { c.download(release, output) {} }
            assertEquals(2, attempts)
            assertEquals("existing verified update", output.readText())
            assertFalse(File(output.parentFile, output.name + ".part").exists())
        } finally { output.delete() }
    }
}
