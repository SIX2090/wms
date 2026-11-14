package com.factory.wms

import android.app.Application
import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import com.factory.wms.data.api.RetrofitClient
import com.factory.wms.data.api.WmsApiService
import com.factory.wms.data.local.AppDatabase
import com.factory.wms.data.local.PendingOperationEntity
import com.factory.wms.data.model.ApiEnvelope
import com.factory.wms.data.model.SubmitResult
import com.factory.wms.data.repository.OfflineQueueManager
import com.google.gson.Gson
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.emptyFlow
import okhttp3.Protocol
import okhttp3.Request
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import retrofit2.Response
import java.io.IOException
import java.lang.reflect.Proxy
import java.util.concurrent.Executor

/** Real Room + real manager, a synthetic API terminates before DNS, sockets or business services. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [31], application = Application::class)
class OfflineQueueOwnershipTest {
    private val server = "https://queue-a.example.invalid/"
    private lateinit var db: AppDatabase
    private lateinit var manager: OfflineQueueManager
    private lateinit var scope: CoroutineScope
    private val sent = mutableListOf<Pair<String, String>>()
    private var beforeSend: () -> Unit = {}
    private var response: () -> Response<ApiEnvelope<SubmitResult>> = { success() }
    private var online = true
    private val dao get() = db.pendingOperationDao()

    @Before fun before() {
        RetrofitClient.onUnauthorized = null
        RetrofitClient.setSession(server, "synthetic-A", 11)
        db = Room.inMemoryDatabaseBuilder(ApplicationProvider.getApplicationContext(), AppDatabase::class.java)
            .allowMainThreadQueries().setQueryExecutor(Executor { it.run() })
            .setTransactionExecutor(Executor { it.run() }).build()
        scope = CoroutineScope(SupervisorJob() + Dispatchers.Unconfined)
        manager = OfflineQueueManager(dao, { session ->
            // The production API factory must accept this exact snapshot as well.
            RetrofitClient.apiServiceFor(session)
            @Suppress("UNCHECKED_CAST")
            (Proxy.newProxyInstance(WmsApiService::class.java.classLoader,
                arrayOf(WmsApiService::class.java)) { _, method, args ->
                check(method.name in listOf("submitInbound", "submitOutbound", "submitStocktake"))
                beforeSend()
                RetrofitClient.guardRequest(Request.Builder().url(session.server + "api/mobile/submit").build(), session, true)
                sent += (args!![0] as String) to Gson().toJson(args[1])
                response()
            } as WmsApiService)
        }, { online }, emptyFlow(), scope)
    }

    @After fun after() {
        scope.cancel()
        db.close()
        RetrofitClient.setSession("", null)
    }

    private fun success() = Response.success(ApiEnvelope("success", true, null, null,
        SubmitResult(1, "synthetic-order", null)))

    private fun refusal(code: Int, retry: String? = null): Response<ApiEnvelope<SubmitResult>> {
        val raw = okhttp3.Response.Builder().request(Request.Builder().url(server).build())
            .protocol(Protocol.HTTP_1_1).code(code).message("synthetic")
            .apply { if (retry != null) header("Retry-After", retry) }.build()
        return Response.error("""{"status":"error","msg":"合成拒绝原因$code"}""".toResponseBody(), raw)
    }

    private suspend fun enqueue(id: String = "request-1", type: String = "inbound",
        session: RetrofitClient.SessionSnapshot = RetrofitClient.sessionSnapshot(),
        autoSync: Boolean = false): Boolean {
        // Existing ownership tests arrange their response after enqueue; freeze automatic
        // replay only during fixture setup, then exercise the real manager explicitly.
        val wasOnline = online
        if (!autoSync) online = false
        return try { manager.enqueue(id, type, mapOf("warehouse_code" to "WH-A", "lines" to emptyList<String>()),
            "WH-A", "合成作业", session)
        } finally { online = wasOnline }
    }

    private suspend fun awaitReplay(id: String, timeoutMs: Long) {
        withTimeout(timeoutMs) {
            while (dao.getByRequestId(id) != null) delay(10)
            scope.coroutineContext[Job]!!.children.toList().forEach { it.join() }
        }
    }

    @Test fun onlineEnqueueStartsSyncWithoutNewNetworkEvent() = runBlocking {
        for (type in listOf("inbound", "outbound", "stocktake")) {
            val id = "online-$type"
            assertTrue(enqueue(id, type, autoSync = true))
            awaitReplay(id, 5_000)
            assertEquals(1, sent.count { it.first == id })
        }
        assertTrue(dao.listAll().isEmpty())
    }

    @Test fun transientFailureSchedulesAutomaticReplayWhileOnline() = runBlocking {
        for (kind in listOf("io", "http503")) {
            val id = "retry-$kind"
            var attempts = 0
            response = {
                if (++attempts == 1) {
                    if (kind == "io") throw IOException("synthetic transient failure")
                    refusal(503)
                } else success()
            }
            val started = System.currentTimeMillis()
            assertTrue(enqueue(id))
            manager.doSync() // First attempt only. The second must come from the timer.
            val pending = dao.getByRequestId(id)!!
            assertEquals(1, pending.attemptCount)
            assertTrue(pending.nextRetryAt > started)
            manager.doSync() // A premature manual trigger must respect the deadline.
            assertEquals(1, attempts)
            awaitReplay(id, 45_000)
            val deliveries = sent.filter { it.first == id }
            assertEquals(2, attempts)
            assertEquals(2, deliveries.size)
            assertEquals(deliveries[0], deliveries[1])
        }
    }

    @Test fun anotherAccountCannotReplayAndOriginalAccountWithNewTokenCan() = runBlocking {
        assertTrue(enqueue())
        RetrofitClient.setSession(server, "synthetic-B", 22)
        manager.doSync()
        assertTrue(sent.isEmpty())
        assertEquals(1, dao.listAll().size)
        RetrofitClient.setSession(server, "synthetic-A-renewed", 11)
        manager.doSync()
        assertEquals(listOf("request-1"), sent.map { it.first })
        assertTrue(dao.listAll().isEmpty())
    }

    @Test fun anotherServerCannotReplayEvenWithSameUserId() = runBlocking {
        assertTrue(enqueue())
        RetrofitClient.setSession("https://queue-b.example.invalid/", "synthetic-other", 11)
        manager.doSync()
        assertTrue(sent.isEmpty())
        assertEquals(0, dao.listAll().single().attemptCount)
    }

    @Test fun identitySwitchBetweenSelectionAndSendingIsRejectedByRealGuard() = runBlocking {
        assertTrue(enqueue())
        beforeSend = { RetrofitClient.setSession(server, "synthetic-B", 22) }
        manager.doSync()
        assertTrue(sent.isEmpty())
        assertEquals("pending", dao.listAll().single().status)
    }

    @Test fun failureEnqueuesOriginalSnapshotAfterAccountSwitch() = runBlocking {
        val original = RetrofitClient.sessionSnapshot()
        RetrofitClient.setSession(server, "synthetic-B", 22)
        assertTrue(enqueue(session = original))
        assertEquals(11, dao.listAll().single().ownerUserId)
        manager.doSync()
        assertTrue(sent.isEmpty())
    }

    @Test fun unknownIdentityCannotCreateQueueOwnership() = runBlocking {
        RetrofitClient.setSession(server, "synthetic-legacy")
        assertFalse(enqueue())
        assertTrue(dao.listAll().isEmpty())
    }

    @Test fun legacyRowsKeepPayloadStatusAttemptsAndErrorsAndCannotBeRetried() = runBlocking {
        val originals = listOf("pending", "syncing", "failed").mapIndexed { i, status ->
            PendingOperationEntity("legacy-$i", "inbound", "{\"old\":$i}", "WH-A",
                status = status, attemptCount = i, lastError = "old-error-$i")
        }
        originals.forEach { dao.upsert(it) }
        dao.resetStuckSyncing()
        manager.doSync()
        manager.retryFailed()
        assertEquals(originals, dao.listAll())
        assertEquals(3, dao.countFailed())
        assertTrue(sent.isEmpty())
        assertTrue(manager.lastSyncMessage.value.orEmpty().contains("人工核对"))
    }

    @Test fun sameKeyRetriesKeepExistingPayloadOwnerStatusAndError() = runBlocking {
        assertTrue(enqueue())
        assertTrue(enqueue())
        dao.markFailed("request-1", "failed", 3, "original-error")
        val original = dao.listAll().single()
        assertFalse(enqueue())
        assertEquals(original, dao.listAll().single())
        assertFalse(manager.enqueue("request-1", "inbound", mapOf("changed" to true), "WH-A", "changed",
            RetrofitClient.sessionSnapshot()))
        RetrofitClient.setSession(server, "synthetic-B", 22)
        assertFalse(enqueue())
        assertEquals(original, dao.listAll().single())
    }

    @Test fun serverCredentialsOrQueryCannotBecomePersistedOwnership() = runBlocking {
        for (address in listOf("https://user:pass@queue-a.example.invalid/",
                "https://queue-a.example.invalid/?token=synthetic", "https://queue-a.example.invalid/#fragment")) {
            RetrofitClient.setSession(address, "synthetic-token", 11)
            assertFalse(enqueue())
        }
        assertTrue(dao.listAll().isEmpty())
    }

    @Test fun manualRetryCannotResetAnotherAccountsFailedRow() = runBlocking {
        assertTrue(enqueue())
        dao.markFailed("request-1", "failed", 4, "original-error")
        val original = dao.listAll().single()
        RetrofitClient.setSession(server, "synthetic-B", 22)
        manager.retryFailed("request-1")
        assertEquals(original, dao.listAll().single())
        assertTrue(sent.isEmpty())
    }

    @Test fun throttlingIsRetryableWithBoundedAttemptsAndHonorsRetryAfter() = runBlocking {
        assertTrue(enqueue())
        response = { refusal(429, "120") }
        val now = System.currentTimeMillis()
        manager.doSync()
        val row = dao.listAll().single()
        assertEquals("pending", row.status)
        assertEquals(1, row.attemptCount)
        assertTrue(row.nextRetryAt >= now + 120000)
        assertTrue(row.lastError.orEmpty().contains("合成拒绝原因429"))
        manager.doSync()
        assertEquals(1, sent.size)
    }

    @Test fun unauthorizedAndForbiddenRemainVisibleUntilSameOwnerManuallyRetries() = runBlocking {
        for (code in listOf(401, 403)) {
            assertTrue(enqueue("request-$code"))
            response = { refusal(code) }
            manager.doSync()
            val row = dao.getByRequestId("request-$code")!!
            assertEquals("auth_required", row.status)
            assertEquals(0, row.attemptCount)
            assertTrue(row.lastError.orEmpty().contains("合成拒绝原因$code"))
        }
        assertEquals(2, dao.countFailed())
    }

    @Test fun throttlingAlsoAcceptsHttpDateRetryAfter() = runBlocking {
        assertTrue(enqueue())
        val date = java.time.ZonedDateTime.now(java.time.ZoneOffset.UTC).plusMinutes(3)
            .format(java.time.format.DateTimeFormatter.RFC_1123_DATE_TIME)
        response = { refusal(429, date) }
        manager.doSync()
        val expected = java.time.ZonedDateTime.parse(date, java.time.format.DateTimeFormatter.RFC_1123_DATE_TIME)
            .toInstant().toEpochMilli()
        assertEquals(expected, dao.listAll().single().nextRetryAt)
    }

    @Test fun failedClaimPreventsSendingAndKeepsOriginalPendingRow() = runBlocking {
        assertTrue(enqueue())
        val rejecting = object : com.factory.wms.data.local.PendingOperationDao by dao {
            override suspend fun markSyncing(requestId: String, now: Long, syncing: String): Int = 0
        }
        val guarded = OfflineQueueManager(rejecting, { error("API must not be resolved without a claim") },
            { true }, emptyFlow(), scope)
        guarded.doSync()
        assertTrue(sent.isEmpty())
        assertEquals("pending", dao.listAll().single().status)
    }

    @Test fun localInsertFailureCannotClaimSuccessfulEnqueue() = runBlocking {
        val rejecting = object : com.factory.wms.data.local.PendingOperationDao by dao {
            override suspend fun upsert(operation: PendingOperationEntity): Long = throw IOException("synthetic disk full")
        }
        val guarded = OfflineQueueManager(rejecting, { error("no API during enqueue") }, { true }, emptyFlow(), scope)
        assertFalse(guarded.enqueue("no-write", "inbound", emptyMap<String, String>(), "WH-A", "合成作业",
            RetrofitClient.sessionSnapshot()))
        assertTrue(dao.listAll().isEmpty())
    }

    @Test fun repeatedThrottlingEventuallyRequiresManualAction() = runBlocking {
        assertTrue(enqueue())
        dao.markFailed("request-1", "pending", PendingOperationEntity.MAX_ATTEMPTS - 1, "old rate limit")
        response = { refusal(429) }
        manager.doSync()
        val row = dao.listAll().single()
        assertEquals("failed", row.status)
        assertEquals(PendingOperationEntity.MAX_ATTEMPTS, row.attemptCount)
        assertEquals(0L, row.nextRetryAt)
        assertTrue(row.lastError.orEmpty().contains("429"))
    }

    @Test fun concurrentSyncAndLogoutKeepOneOriginalIdentityAndRequest() = runBlocking {
        assertTrue(enqueue())
        val started = CompletableDeferred<Unit>()
        val release = CompletableDeferred<Unit>()
        response = {
            started.complete(Unit)
            runBlocking { release.await() }
            success()
        }
        withTimeout(5000) {
            val first = async(Dispatchers.Default) { manager.doSync() }
            started.await()
            val second = async(Dispatchers.Default) { manager.doSync() }
            RetrofitClient.setSession(server, null)
            release.complete(Unit)
            first.await()
            second.await()
        }
        assertEquals(listOf("request-1"), sent.map { it.first })
        assertTrue(dao.listAll().isEmpty())
    }

    @Test fun businessRefusalsAreTerminalAndKeepSpecificServerMessage() = runBlocking {
        for (code in listOf(400, 409, 422)) {
            assertTrue(enqueue("request-$code"))
            response = { refusal(code) }
            manager.doSync()
            assertEquals("failed", dao.getByRequestId("request-$code")!!.status)
            assertTrue(dao.getByRequestId("request-$code")!!.lastError.orEmpty().contains("合成拒绝原因$code"))
        }
    }

    @Test fun accountSwitchHidesPreviousOwnersFailureReasonAndRetryControl() = runBlocking {
        assertTrue(enqueue())
        response = { refusal(403) }
        manager.doSync()
        assertTrue(manager.lastSyncMessage.value.orEmpty().contains("合成拒绝原因403"))
        assertTrue(manager.canRetry.value)
        RetrofitClient.setSession(server, "synthetic-B", 22)
        manager.doSync()
        assertFalse(manager.lastSyncMessage.value.orEmpty().contains("合成拒绝原因403"))
        assertFalse(manager.canRetry.value)
        assertEquals(1, dao.listAll().size)
    }

    @Test fun lostResponseReusesOriginalRequestIdPayloadAndServerIdempotency() = runBlocking {
        val applied = mutableSetOf<String>()
        var attempts = 0
        response = {
            applied += sent.last().first
            if (++attempts == 1) throw IOException("synthetic response lost")
            success()
        }
        assertTrue(enqueue())
        val payload = dao.listAll().single().payloadJson
        manager.doSync()
        assertEquals(payload, dao.listAll().single().payloadJson)
        manager.doSync()
        assertEquals(1, sent.size)
        awaitReplay("request-1", 45_000)
        assertEquals(1, applied.size)
        assertEquals(listOf("request-1", "request-1"), sent.map { it.first })
        assertEquals(sent[0].second, sent[1].second)
        assertTrue(dao.listAll().isEmpty())
    }

    @Test fun everyOperationUsesTheSameOwnershipAndReplayGuard() = runBlocking {
        for (type in listOf("inbound", "outbound", "stocktake")) assertTrue(enqueue(type, type))
        manager.doSync()
        assertEquals(3, sent.size)
        assertTrue(dao.listAll().isEmpty())
    }

    @Test fun updateInstallationDefersReplayAndRetainsRealRoomRowsAndIdentity() = runBlocking {
        assertTrue(enqueue("update-in", "inbound"))
        assertTrue(enqueue("update-out", "outbound"))
        assertTrue(enqueue("update-count", "stocktake"))
        val before = dao.listAll().associateBy { it.requestId }
        val gate = com.factory.wms.update.businessUpdateGate
        assertTrue(gate.beginInstall())
        try {
            manager.doSync()
            assertTrue(sent.isEmpty())
            assertEquals(before, dao.listAll().associateBy { it.requestId })
        } finally { gate.endInstall() }
        manager.doSync()
        assertEquals(before.keys, sent.map { it.first }.toSet())
        assertTrue(dao.listAll().isEmpty())
    }

    @Test fun cancellationDoesNotConsumeRetryOrCreateAnotherOperation() = runBlocking {
        assertTrue(enqueue())
        response = { throw CancellationException("synthetic cancellation") }
        try { manager.doSync(); fail("cancellation must propagate") } catch (_: CancellationException) { }
        val row = dao.listAll().single()
        assertEquals(0, row.attemptCount)
        assertEquals("syncing", row.status)
        dao.resetStuckSyncing()
        assertEquals("pending", dao.listAll().single().status)
    }
}
