package com.factory.wms

import android.app.Application
import androidx.test.core.app.ApplicationProvider
import com.factory.wms.data.api.RetrofitClient
import com.factory.wms.data.model.*
import com.factory.wms.data.repository.WmsRepository
import kotlinx.coroutines.runBlocking
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okhttp3.mockwebserver.Dispatcher
import okhttp3.mockwebserver.RecordedRequest
import okhttp3.mockwebserver.SocketPolicy
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicInteger
import org.junit.*
import org.junit.Assert.*
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/** Durable DataStore intents and actual Retrofit requests, with no production endpoint. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk=[31],application=Application::class)
class NativePendingWriteRecoveryTest {
    private lateinit var server:MockWebServer
    private lateinit var repo:WmsRepository
    private lateinit var application:Application
    private lateinit var stores:NativeAuditLocalStores
    @Before fun before(){
        DataStoreTestReset.resetWmsSettingsDataStore()
        application=ApplicationProvider.getApplicationContext()
        stores=NativeAuditLocalStores(application)
        server=MockWebServer();server.start()
        repo=WmsRepository(application)
        RetrofitClient.setSession(server.url("/").toString(),"synthetic-owner-a",91)
    }
    @After fun after(){stores.close();RetrofitClient.setSession("",null);server.shutdown()}
    private fun success()=MockResponse().setHeader("Content-Type","application/json").setBody(
        """{"status":"success","data":{"id":1,"order_id":1,"order_no":"SYNTHETIC-1","check_no":"CHECK-1","status":"pending","items":[],"auto_created":[],"reply":"ok","conversation_id":1,"cards":[],"actions":[],"action":"reply"}}""")
    private fun writes(): List<Pair<String, suspend () -> Result<*>>> = listOf(
            "stocktake" to { repo.submitStocktake(StocktakeRequest(listOf(StocktakeLine("M001",3.0)),warehouseCode="A",checkId=1)) },
            "opening_stock" to { repo.submitOpeningStock(OpeningStockRequest("2026-11-15","A",listOf(OpeningStockLine("M001",3.0,2.0)))) },
            "opening_stock_edit:1" to { repo.updateOpeningStock(1,OpeningStockUpdateRequest(quantity=3.0,revision="rev-1")) },
            "inbound_draft" to { repo.createInboundDraft(InboundDraftRequest(listOf(InboundDraftLine("M001",3.0)),warehouseCode="A")) },
            "voice_out_draft:false" to { repo.createVoiceOutDraft(VoiceOutDraftRequest(text="synthetic",warehouseCode="A",dryRun=false,materialCode="M001",quantity=3.0)) },
            "voice_intent" to { repo.understandVoiceIntent("synthetic question") },
            "assistant_chat:test-session" to { repo.assistantChat("synthetic question",intentScope="test-session") }
        )

    @Test fun everyAffectedWriteReusesFrozenRequestUntilHandled()=runBlocking {
        val operations = writes()
        for((operation,call) in operations){
            server.enqueue(MockResponse().setResponseCode(503));assertTrue(operation,call().isFailure)
            val stored=repo.pendingNativeWrites().single{it.operation==operation}
            assertNull(stored.responseJson)
            server.enqueue(success());assertTrue(operation,call().isSuccess)
            val first=server.takeRequest();val retry=server.takeRequest()
            assertEquals(operation,stored.requestId,first.getHeader("X-Idempotency-Key"))
            assertEquals(operation,first.getHeader("X-Idempotency-Key"),retry.getHeader("X-Idempotency-Key"))
            assertEquals(operation,stored.payloadJson,first.body.readUtf8())
            assertEquals(operation,stored.payloadJson,retry.body.readUtf8())
            assertNotNull(repo.pendingNativeWrites().single{it.operation==operation}.responseJson)
            repo.acknowledgeNativeWrite(operation,stored.requestId)
            assertFalse(repo.pendingNativeWrites().any{it.operation==operation})
        }
    }
    @Test fun logoutAndOtherAccountCannotReplayOriginalOwnerIntent()=runBlocking {
        val request=InboundDraftRequest(listOf(InboundDraftLine("M001",3.0)),warehouseCode="A")
        server.enqueue(MockResponse().setResponseCode(503));assertTrue(repo.createInboundDraft(request).isFailure)
        val original=repo.pendingNativeWrites().single()
        repo.logout()
        RetrofitClient.setSession(server.url("/").toString(),"synthetic-owner-b",92)
        val other=WmsRepository(application);assertTrue(other.pendingNativeWrites().isEmpty())
        val count=server.requestCount
        assertTrue(other.verifyPendingNativeWrite(original.requestId).isFailure)
        assertEquals(count,server.requestCount)
        RetrofitClient.setSession(server.url("/").toString(),"synthetic-renewed-owner-a",91)
        val reopened=WmsRepository(application)
        assertEquals(original,reopened.pendingNativeWrites().single())
        assertEquals("Listing pending records never sends requests",count,server.requestCount)
        server.enqueue(success());assertTrue(reopened.verifyPendingNativeWrite(original.requestId).isSuccess)
        val first=server.takeRequest();val verified=server.takeRequest()
        assertEquals(first.getHeader("X-Idempotency-Key"),verified.getHeader("X-Idempotency-Key"))
        assertEquals(first.body.readUtf8(),verified.body.readUtf8())
        assertNotNull(reopened.pendingNativeWrites().single().responseJson)
    }
    @Test fun everyAffectedWriteLostReceiptReplaysExactlyOneOriginalEffect()=runBlocking {
        for((operation,call) in writes()) {
            val receipts=ConcurrentHashMap<String,String>()
            val effects=AtomicInteger()
            val releaseReceipt=AtomicBoolean(false)
            server.dispatcher=object:Dispatcher() {
                override fun dispatch(request:RecordedRequest):MockResponse {
                    val id=checkNotNull(request.getHeader("X-Idempotency-Key"))
                    val body=request.body.clone().readUtf8()
                    val previous=receipts.putIfAbsent(id,body)
                    if(previous==null) {
                        // The synthetic server commits its business effect and receipt before the connection disappears.
                        effects.incrementAndGet()
                    }
                    check(previous==null || previous==body) { "Original request payload changed for $operation" }
                    // OkHttp may retry a reused connection. Lose every receipt until the caller has observed uncertainty.
                    return if(releaseReceipt.get()) success()
                        else MockResponse().setSocketPolicy(SocketPolicy.DISCONNECT_AFTER_REQUEST)
                }
            }
            val lost=call()
            assertTrue("$operation must lose the first successful server receipt",lost.isFailure)
            val first=checkNotNull(server.takeRequest(3,TimeUnit.SECONDS))
            val id=checkNotNull(first.getHeader("X-Idempotency-Key"))
            val body=first.body.clone().readUtf8()
            while(true) {
                val transportRetry=server.takeRequest(100,TimeUnit.MILLISECONDS) ?: break
                assertEquals("$operation automatic transport retry must retain its key",id,transportRetry.getHeader("X-Idempotency-Key"))
                assertEquals("$operation automatic transport retry must retain its payload",body,transportRetry.body.readUtf8())
            }
            assertEquals(operation,1,effects.get())
            releaseReceipt.set(true)
            if(operation=="stocktake") {
                // A reliable offline handoff is already complete. Recover the original queued intent, not a new submit.
                assertTrue(lost.exceptionOrNull() is WmsRepository.Companion.OfflineQueuedException)
                val queued=stores.database.pendingOperationDao().listAll().single()
                assertEquals(id,queued.requestId);assertEquals(body,queued.payloadJson)
                stores.online=true
                try { stores.queue.doSync() } finally { stores.online=false }
                assertNull(stores.database.pendingOperationDao().getByRequestId(id))
            } else {
                val pending=repo.pendingNativeWrites().single{it.operation==operation}
                assertEquals(id,pending.requestId);assertEquals(body,pending.payloadJson)
                assertTrue("$operation manual recovery must return the original receipt",call().isSuccess)
                repo.acknowledgeNativeWrite(operation,id)
            }
            val replay=checkNotNull(server.takeRequest(3,TimeUnit.SECONDS))
            assertEquals(operation,id,replay.getHeader("X-Idempotency-Key"))
            assertEquals(operation,body,replay.body.readUtf8())
            assertEquals("$operation must have exactly one committed business effect",1,effects.get())
            assertEquals(operation,1,receipts.size)
            assertNull("$operation must not send an extra request",server.takeRequest(100,TimeUnit.MILLISECONDS))
        }
    }

}
