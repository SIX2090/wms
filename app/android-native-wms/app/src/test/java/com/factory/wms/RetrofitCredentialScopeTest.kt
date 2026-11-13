package com.factory.wms

import com.factory.wms.data.api.RetrofitClient
import okhttp3.Interceptor
import okhttp3.Protocol
import okhttp3.Request
import okhttp3.Response
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.io.IOException

/** All calls terminate in an application interceptor, before DNS or sockets. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [31], application = android.app.Application::class)
class RetrofitCredentialScopeTest {
    private val server = "https://warehouse.example.invalid/"

    @Before fun before() {
        RetrofitClient.onUnauthorized = null
        RetrofitClient.setSession(server, "synthetic-token-A")
    }

    @After fun after() {
        RetrofitClient.onUnauthorized = null
        RetrofitClient.setSession("", null)
    }

    private fun request(url: String) = Request.Builder().url(url).build()

    private fun execute(url: String, terminal: (Request) -> Int): Response {
        val client = RetrofitClient.sharedOkHttpClient().newBuilder()
            .addInterceptor(Interceptor { chain ->
                val code = terminal(chain.request())
                Response.Builder().request(chain.request()).protocol(Protocol.HTTP_1_1)
                    .code(code).message("synthetic").body("{}".toResponseBody()).build()
            }).build()
        return client.newCall(request(url)).execute()
    }

    @Test fun sameOriginHasExactlyOneCredential() {
        execute(server + "image.png") {
            assertEquals(listOf("Bearer synthetic-token-A"), it.headers.values("Authorization"))
            200
        }.close()
    }

    @Test fun externalImageHasNoCredentialAndIts401CannotLogOut() {
        var events = 0
        RetrofitClient.onUnauthorized = { events++ }
        execute("https://images.example.invalid/image.png") {
            assertNull(it.header("Authorization"))
            401
        }.close()
        assertEquals("synthetic-token-A", RetrofitClient.getToken())
        assertEquals(0, events)
    }

    @Test fun originIncludesSchemeAndPortAndRedirectHeadersAreStripped() {
        val snapshot = RetrofitClient.sessionSnapshot()
        for (url in listOf("http://warehouse.example.invalid/image.png",
                "https://warehouse.example.invalid:444/image.png", "https://images.example.invalid/a")) {
            val redirected = request(url).newBuilder().header("Authorization", "inherited-secret").build()
            assertNull(RetrofitClient.guardRequest(redirected, snapshot, false).header("Authorization"))
            assertThrows(IOException::class.java) {
                RetrofitClient.guardRequest(redirected, snapshot, true)
            }
        }
    }

    @Test fun loginDoesNotCarryPreviousToken() {
        execute(server + "api/login") {
            assertNull(it.header("Authorization"))
            401
        }.close()
        assertEquals("synthetic-token-A", RetrofitClient.getToken())
    }

    @Test fun late401CannotClearAnotherAccountOnSameServer() {
        var events = 0
        RetrofitClient.onUnauthorized = { events++ }
        execute(server + "api/material/search") {
            assertEquals("Bearer synthetic-token-A", it.header("Authorization"))
            RetrofitClient.setSession(server, "synthetic-token-B")
            401
        }.close()
        assertEquals("synthetic-token-B", RetrofitClient.getToken())
        assertEquals(0, events)
    }

    @Test fun current401ClearsOnlyCurrentSessionOnce() {
        var events = 0
        RetrofitClient.onUnauthorized = { events++ }
        execute(server + "api/material/search") { 401 }.close()
        assertNull(RetrofitClient.getToken())
        assertEquals(1, events)
    }

    @Test fun cachedApiSnapshotIsRejectedAfterSwitchBeforeSending() {
        val old = RetrofitClient.sessionSnapshot()
        RetrofitClient.setSession("https://another.example.invalid/", "synthetic-token-B")
        assertThrows(IOException::class.java) {
            RetrofitClient.guardRequest(request(server + "api/outbound"), old, true)
        }
        assertFalse(old.toString().contains("synthetic-token-A"))
        assertEquals("synthetic-token-B", RetrofitClient.getToken())
    }

    @Test fun switchingServerCannotReusePreviousServerToken() {
        RetrofitClient.setBaseUrl("https://another.example.invalid/")
        assertNull(RetrofitClient.getToken())
    }

    @Test fun staleColdRestoreCannotReplaceAnAlreadyPublishedLogin() {
        val expected = RetrofitClient.sessionSnapshot()
        RetrofitClient.setSession(server, "synthetic-token-B")
        assertFalse(RetrofitClient.restoreSession(server, "synthetic-token-A", expected))
        assertEquals("synthetic-token-B", RetrofitClient.getToken())
    }

    @Test fun coldRestorePublishesServerAndTokenTogether() {
        RetrofitClient.setSession("", null)
        assertTrue(RetrofitClient.restoreSession(server, "synthetic-restored", RetrofitClient.sessionSnapshot()))
        execute(server + "api/material/search") {
            assertEquals("Bearer synthetic-restored", it.header("Authorization"))
            200
        }.close()
    }

    @Test fun twoColdRestorersOfTheSameCredentialDoNotUndoEachOther() {
        RetrofitClient.setSession("", null)
        val expected = RetrofitClient.sessionSnapshot()
        assertTrue(RetrofitClient.restoreSession(server, "synthetic-restored", expected))
        assertTrue(RetrofitClient.restoreSession(server, "synthetic-restored", expected))
        assertEquals("synthetic-restored", RetrofitClient.getToken())
    }
}
