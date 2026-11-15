package com.factory.wms

import android.app.Application
import androidx.test.core.app.ApplicationProvider
import com.factory.wms.data.api.RetrofitClient
import com.factory.wms.data.model.*
import com.factory.wms.data.repository.WmsRepository
import kotlinx.coroutines.runBlocking
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
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
    @Test fun everyAffectedWriteReusesFrozenRequestUntilHandled()=runBlocking {
        val operations: List<Pair<String,suspend () -> Result<*>>> = listOf(
            "stocktake" to { repo.submitStocktake(StocktakeRequest(listOf(StocktakeLine("M001",3.0)),warehouseCode="A",checkId=1)) },
            "opening_stock" to { repo.submitOpeningStock(OpeningStockRequest("2026-11-15","A",listOf(OpeningStockLine("M001",3.0,2.0)))) },
            "opening_stock_edit:1" to { repo.updateOpeningStock(1,OpeningStockUpdateRequest(quantity=3.0,revision="rev-1")) },
            "inbound_draft" to { repo.createInboundDraft(InboundDraftRequest(listOf(InboundDraftLine("M001",3.0)),warehouseCode="A")) },
            "voice_out_draft:false" to { repo.createVoiceOutDraft(VoiceOutDraftRequest(text="synthetic",warehouseCode="A",dryRun=false,materialCode="M001",quantity=3.0)) },
            "voice_intent" to { repo.understandVoiceIntent("synthetic question") },
            "assistant_chat:test-session" to { repo.assistantChat("synthetic question",intentScope="test-session") }
        )
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
}
