package com.factory.wms

import android.app.Application
import android.os.Looper
import androidx.lifecycle.viewModelScope
import androidx.test.core.app.ApplicationProvider
import com.factory.wms.data.api.RetrofitClient
import com.factory.wms.data.repository.WmsRepository
import com.factory.wms.ui.viewmodel.ai.AssistantChatViewModel
import com.google.gson.JsonParser
import kotlinx.coroutines.*
import kotlinx.coroutines.test.*
import okhttp3.mockwebserver.*
import org.junit.*
import org.junit.Assert.*
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

/** A09/A12: actual ViewModels, Retrofit and durable DataStore across a recreated chat owner. */
@OptIn(ExperimentalCoroutinesApi::class)
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [31], application = Application::class)
class NativeAssistantRecreationTest {
    private val main = StandardTestDispatcher()
    private lateinit var application: Application
    private lateinit var server: MockWebServer
    private lateinit var stores: NativeAuditLocalStores
    private lateinit var repository: WmsRepository
    private val models = mutableListOf<AssistantChatViewModel>()
    private val releases = mutableListOf<CountDownLatch>()

    @Before fun before() {
        Dispatchers.setMain(main)
        DataStoreTestReset.resetWmsSettingsDataStore()
        application = ApplicationProvider.getApplicationContext()
        stores = NativeAuditLocalStores(application)
        server = MockWebServer(); server.start()
        RetrofitClient.setSession(server.url("/").toString(), "synthetic-chat-owner", 91)
        repository = WmsRepository(application)
    }
    @After fun after() {
        releases.forEach { it.countDown() }
        closeWmsTestViewModels(models) {
            main.scheduler.runCurrent(); shadowOf(Looper.getMainLooper()).idle()
        }
        stores.close()
        RetrofitClient.setSession("", null)
        server.shutdown()
        Dispatchers.resetMain()
    }
    private fun model() = AssistantChatViewModel(application).also { models += it }
    private fun pump(label: String, condition: () -> Boolean) {
        val deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(8)
        while (System.nanoTime() < deadline) {
            main.scheduler.runCurrent(); shadowOf(Looper.getMainLooper()).idle()
            if (condition()) return
            Thread.sleep(10)
        }
        fail("Chat behavior did not settle: $label")
    }
    private fun ok(reply: String) = MockResponse().setHeader("Content-Type", "application/json")
        .setBody("""{"status":"success","data":{"reply":"$reply","conversation_id":55,"cards":[],"actions":[]}}""")

    @Test fun recreatedChatCannotTurnUnresolvedRequestIntoANewBusinessIntent() = runBlocking {
        server.enqueue(MockResponse().setSocketPolicy(SocketPolicy.DISCONNECT_AFTER_REQUEST))
        val first = model()
        first.setPendingImage("original-image"); first.setPendingFile("original-file", "original.txt")
        first.send("create original draft")
        pump("lost first response") { !first.uiState.value.isLoading && first.uiState.value.error != null }
        val original = repository.pendingNativeWrites().single()
        assertEquals(1, server.requestCount)
        first.viewModelScope.cancel()
        val reopened = model()
        reopened.setPendingImage("original-image"); reopened.setPendingFile("original-file", "original.txt")
        server.enqueue(ok("A duplicate must never be sent"))
        reopened.send("create original draft")
        pump("reopened owner finishes durable request check") {
            !reopened.uiState.value.isLoading &&
                reopened.viewModelScope.coroutineContext[Job]!!.children.none { it.isActive }
        }
        assertEquals("Recreation cannot generate another HTTP write", 1, server.requestCount)
        assertTrue(reopened.uiState.value.error.orEmpty().contains("待核实"))
        assertEquals("original-image", reopened.uiState.value.pendingImage)
        assertEquals("original-file" to "original.txt", reopened.uiState.value.pendingFile)
        assertTrue(reopened.uiState.value.messages.isEmpty())
        assertEquals(original, repository.pendingNativeWrites().single())
    }

    @Test fun manualRetryInOriginalOwnerRetainsRequestIdAndFrozenAttachmentBody() = runBlocking {
        server.enqueue(MockResponse().setResponseCode(503))
        val vm = model(); vm.setPendingImage("image"); vm.setPendingFile("file", "scan.txt")
        vm.send("same intent")
        pump("first failure") { !vm.uiState.value.isLoading && vm.uiState.value.error != null }
        val original = repository.pendingNativeWrites().single()
        server.enqueue(ok("original receipt")); vm.send("same intent")
        pump("retry receipt") { vm.uiState.value.messages.any { it.text == "original receipt" } }
        pump("handled receipt acknowledged") { runBlocking { repository.pendingNativeWrites().isEmpty() } }
        val first = server.takeRequest(); val retry = server.takeRequest()
        assertEquals(original.requestId, first.getHeader("X-Idempotency-Key"))
        assertEquals(first.getHeader("X-Idempotency-Key"), retry.getHeader("X-Idempotency-Key"))
        assertEquals(original.payloadJson, first.body.readUtf8())
        assertEquals(original.payloadJson, retry.body.readUtf8())
    }

    @Test fun explicitClearStartsANewIntentAndOldFailureCannotRestoreAttachments() {
        val release = CountDownLatch(1); releases += release
        server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val text = JsonParser.parseString(request.body.clone().readUtf8()).asJsonObject["text"].asString
                if (text == "old intent") {
                    check(release.await(7, TimeUnit.SECONDS))
                    return MockResponse().setResponseCode(503)
                }
                return ok("new receipt")
            }
        }
        val vm = model(); vm.setPendingImage("old-image"); vm.setPendingFile("old-file", "old.txt")
        vm.send("old intent"); pump("old write sent") { server.requestCount == 1 }
        vm.clearConversation(); vm.send("new intent")
        pump("new receipt") { vm.uiState.value.messages.any { it.text == "new receipt" } }
        release.countDown()
        pump("old coroutine cancelled") { vm.viewModelScope.coroutineContext[Job]!!.children.none { it.isActive } }
        assertEquals(listOf("new intent", "new receipt"), vm.uiState.value.messages.map { it.text })
        assertNull(vm.uiState.value.pendingImage); assertNull(vm.uiState.value.pendingFile)
        assertNull(vm.uiState.value.failedDraft); assertNull(vm.uiState.value.error)
        val first = server.takeRequest(); val second = server.takeRequest()
        assertNotEquals(first.getHeader("X-Idempotency-Key"), second.getHeader("X-Idempotency-Key"))
    }

    @Test fun anotherAccountsUnresolvedChatCannotBlockOrJoinCurrentAccountsConversation() = runBlocking {
        server.enqueue(MockResponse().setResponseCode(503))
        val original = model(); original.send("same words")
        pump("original account failure") { !original.uiState.value.isLoading && original.uiState.value.error != null }
        val preserved = repository.pendingNativeWrites().single()
        original.viewModelScope.cancel()
        RetrofitClient.setSession(server.url("/").toString(), "synthetic-other-chat-owner", 92)
        val current = model(); server.enqueue(ok("other account receipt")); current.send("same words")
        pump("current account reply") { current.uiState.value.messages.any { it.text == "other account receipt" } }
        assertEquals(2, server.requestCount)
        val first = server.takeRequest(); val other = server.takeRequest()
        assertNotEquals(first.getHeader("X-Idempotency-Key"), other.getHeader("X-Idempotency-Key"))
        RetrofitClient.setSession(server.url("/").toString(), "synthetic-renewed-chat-owner", 91)
        assertEquals(preserved, repository.pendingNativeWrites().single())
    }
}
