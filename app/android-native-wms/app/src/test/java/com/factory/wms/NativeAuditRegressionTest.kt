package com.factory.wms

import android.app.Application
import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import kotlinx.coroutines.flow.first
import android.os.Looper
import com.factory.wms.data.local.AppDatabase
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.test.core.app.ApplicationProvider
import com.factory.wms.data.api.RetrofitClient
import com.factory.wms.data.model.*
import com.factory.wms.data.repository.WmsRepository
import com.factory.wms.ui.viewmodel.scan.ScanViewModel
import com.factory.wms.ui.viewmodel.scan.ScanUiState
import com.factory.wms.ui.viewmodel.opening.OpeningStockViewModel
import com.factory.wms.ui.viewmodel.report.*
import com.factory.wms.ui.viewmodel.list.*
import com.factory.wms.ui.viewmodel.ai.AssistantChatViewModel
import com.google.gson.Gson
import com.google.gson.JsonParser
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableStateFlow
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

/** AI-APP-AUDIT-FIX-20261115-001: correct behavior regression locks against real Android components.
 * All HTTP traffic is restricted to MockWebServer on loopback, with Application (no WmsApplication).
 * Reflection sets input state only; all operations under audit execute the actual production methods.
 */
@OptIn(ExperimentalCoroutinesApi::class)
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [31], application = Application::class)
class NativeAuditRegressionTest {
    private val main = StandardTestDispatcher()
    private lateinit var application: Application
    private lateinit var repo: WmsRepository
    private lateinit var auditDatabase: AppDatabase
    private lateinit var server: MockWebServer
    private val models = mutableListOf<ViewModel>()
    private val releases = mutableListOf<CountDownLatch>()
    private var serverClosed = false
    private lateinit var stores: NativeAuditLocalStores
    private val a = WarehouseDto(1, "A", "Warehouse A")
    private val b = WarehouseDto(2, "B", "Warehouse B")
    @Before fun before() {
        Dispatchers.setMain(main)
        DataStoreTestReset.resetWmsSettingsDataStore()
        application = ApplicationProvider.getApplicationContext()
        stores = NativeAuditLocalStores(application)
        auditDatabase = stores.database
        repo = WmsRepository(application)
        check(WmsRepository::class.java.getDeclaredField("db").apply { isAccessible = true }.get(repo) === auditDatabase)
        server = MockWebServer(); server.start()
        RetrofitClient.setSession(server.url("/").toString(), "synthetic-audit-token", 91)
    }
    @After fun after() {
        releases.forEach { it.countDown() }
        closeWmsTestViewModels(models) {
            main.scheduler.runCurrent(); shadowOf(Looper.getMainLooper()).idle()
        }
        stores.close()
        main.scheduler.runCurrent()
        RetrofitClient.setSession("", null)
        if (!serverClosed) server.shutdown()
        Dispatchers.resetMain()
    }
    private fun <T:ViewModel> keep(model:T):T = model.also { models.add(it) }
    private fun pumpUntil(label:String, test:()->Boolean) {
        val deadline = System.nanoTime()+TimeUnit.SECONDS.toNanos(8)
        while(System.nanoTime()<deadline) {
            main.scheduler.runCurrent(); shadowOf(Looper.getMainLooper()).idle()
            if(test()) return
            Thread.sleep(10)
        }
        fail("Audit setup/behavior timeout: $label")
    }
    private fun ok(data:String) = MockResponse().setHeader("Content-Type","application/json")
        .setBody("""{"status":"success","data":$data}""")
    private fun line(code:String="M001") = ScanLine(code, 3.0,
        material_name="Audit material",material_spec="Spec",material_brand="Brand")
    @Suppress("UNCHECKED_CAST")
    private fun seed(vm:ScanViewModel,state:ScanUiState) {
        val field=ScanViewModel::class.java.getDeclaredField("_uiState").apply{isAccessible=true}
        (field.get(vm) as MutableStateFlow<ScanUiState>).value=state
    }
    private fun idleRequests(vm:ViewModel) {
        pumpUntil("request coroutines complete") { vm.viewModelScope.coroutineContext[Job]!!.children.none { it.isActive } }
    }
    private fun settle() { repeat(50) { main.scheduler.runCurrent(); shadowOf(Looper.getMainLooper()).idle(); Thread.sleep(10) } }
    private fun awaitDraftRemoved() {
        val deadline=System.nanoTime()+TimeUnit.SECONDS.toNanos(8)
        while(System.nanoTime()<deadline) {
            main.scheduler.runCurrent();shadowOf(Looper.getMainLooper()).idle()
            if(runBlocking{repo.loadStocktakeDraft()==null}) return
            Thread.sleep(10)
        }
        // The caller asserts the retained draft, so an old implementation fails on business data.
    }
    private fun material(code:String):MaterialDto = Gson().fromJson(
        """{"id":1,"code":"$code","name":"Audit $code","spec":"x","stock":7}""",MaterialDto::class.java)
    private fun seedLogin()=runBlocking { repo.saveLoginInfo("synthetic-audit-token",server.url("/").toString(),"auditor","warehouse",91) }
    private fun raceResponses(data:(String)->String):CountDownLatch {
        val release=CountDownLatch(1); releases.add(release)
        server.dispatcher=object:Dispatcher() {
            override fun dispatch(request:RecordedRequest):MockResponse {
                val warehouse=request.requestUrl!!.queryParameter("warehouse_id") ?: "2"
                if(warehouse=="1") check(release.await(7,TimeUnit.SECONDS))
                return ok(data(if(warehouse=="1")"A" else "B"))
            }
        }
        return release
    }
    @Test fun cacheNeverReturnsAnotherWarehouse()=runBlocking {
        server.enqueue(ok("""{"id":1,"code":"M001","name":"Audit","stock":71}"""))
        assertEquals(71.0,repo.getMaterialInfo("M001","A").getOrThrow().stock!!,0.0)
        server.shutdown(); serverClosed=true
        assertTrue("A warehouse cache must never answer warehouse B", repo.getMaterialInfo("M001","B").isFailure)
    }
    @Test fun cacheNeverReturnsAnotherServerOrAccount()=runBlocking {
        server.enqueue(ok("""{"id":1,"code":"M001","name":"Server A private name","stock":71}"""))
        repo.getMaterialInfo("M001","A").getOrThrow()
        val originalServer=RetrofitClient.sessionSnapshot().server
        server.shutdown();serverClosed=true
        RetrofitClient.setSession(originalServer,"other-synthetic-user",92)
        val anotherAccount=repo.getMaterialInfo("M001","A")
        RetrofitClient.setSession("http://127.0.0.1:9/","original-user-new-server",91)
        val anotherServer=repo.getMaterialInfo("M001","A")
        // Both dimensions execute even when the old implementation leaks the first cache read.
        val failures=mutableListOf<Throwable>()
        try { assertTrue("Same server and warehouse must not expose account 91 cache to account 92",anotherAccount.isFailure) }
        catch(error:AssertionError){failures.add(error)}
        try { assertTrue("Same account and warehouse must not expose previous server cache",anotherServer.isFailure) }
        catch(error:AssertionError){failures.add(error)}
        org.junit.runners.model.MultipleFailureException.assertEmpty(failures)
    }
    @Test fun logoutPreservesOwnedEditDraft()=runBlocking {
        seedLogin()
        val key=repo.editDraftKey("inbound")
        val draft=ScanEditDraft(listOf(DraftScanLine(line(),"Audit","x",null)),a,null,null,"",null,"采购入库",null,false)
        repo.saveEditDraft(key,draft)
        val persisted=repo.loadEditDraft(key);assertNotNull(persisted)
        repo.logout(); assertEquals(persisted,repo.loadEditDraft(key))
    }
    @Test fun ambiguousManualKeywordNeverChangesMaterialIdentity() {
        server.dispatcher=object:Dispatcher() {
            override fun dispatch(request:RecordedRequest)=if(request.path!!.startsWith("/api/material/info"))
                MockResponse().setResponseCode(400).setBody("""{"status":"error","msg":"not found"}""")
            else ok("""[{"id":1,"code":"M001","name":"Bolt A","spec":"A"},{"id":2,"code":"M002","name":"Bolt B","spec":"B"}]""")
        }
        val vm=keep(ScanViewModel(application))
        vm.addScanLine(ScanLine("Bolt",2.0))
        pumpUntil("exact lookup completed") { server.requestCount >= 1 }; settle()
        assertEquals("Bolt",vm.uiState.value.scanLines.single().material_code)
    }
    @Test fun stockDailyIgnoresOldWarehouseResponse() {
        val release=raceResponses { code -> """{"date":"2026-11-15","summary":{"total_materials":1,"in_stock_materials":1,"zero_materials":0,"total_quantity":7},"items":[{"id":1,"code":"$code","name":"$code","stock":7}],"page":1,"total":1,"page_size":20,"total_pages":1}""" }
        val vm=keep(StockDailyReportViewModel(application))
        vm.selectWarehouse("1");pumpUntil("A sent"){server.requestCount==1}
        vm.selectWarehouse("2");pumpUntil("B displayed"){vm.uiState.value.items.firstOrNull()?.code=="B"}
        release.countDown();idleRequests(vm);assertEquals("B",vm.uiState.value.items.firstOrNull()?.code)
        assertEquals("2",vm.uiState.value.selectedWarehouseId)
    }
    @Test fun inOutIgnoresOldWarehouseResponse() {
        val release=raceResponses { code -> """{"summary":{"total_count":1,"total_in_quantity":7,"total_out_quantity":0},"items":[{"id":1,"material_code":"$code","quantity":7}],"page":1,"total":1,"page_size":20,"total_pages":1}""" }
        val vm=keep(InOutDetailReportViewModel(application))
        vm.selectWarehouse("1");pumpUntil("A sent"){server.requestCount==1}
        vm.selectWarehouse("2");pumpUntil("B displayed"){vm.uiState.value.items.firstOrNull()?.materialCode=="B"}
        release.countDown();idleRequests(vm);assertEquals("B",vm.uiState.value.items.firstOrNull()?.materialCode)
        assertEquals("2",vm.uiState.value.selectedWarehouseId)
    }
    @Test fun stockLedgerIgnoresOldWarehouseResponse() {
        val release=raceResponses { code -> """{"material":{"code":"M001"},"summary":{"count":1,"opening_balance":0,"total_in_quantity":7,"total_out_quantity":0,"ending_balance":7},"items":[{"reference_no":"$code","in_quantity":7,"out_quantity":0,"balance_quantity":7}],"page":1,"total":1,"page_size":20,"total_pages":1}""" }
        val vm=keep(StockLedgerReportViewModel(application))
        vm.selectMaterial(material("M001"));vm.selectWarehouse("1");pumpUntil("A sent"){server.requestCount==1}
        vm.selectWarehouse("2");pumpUntil("B displayed"){vm.uiState.value.items.firstOrNull()?.referenceNo=="B"}
        release.countDown();idleRequests(vm);assertEquals("B",vm.uiState.value.items.firstOrNull()?.referenceNo)
        assertEquals("2",vm.uiState.value.selectedWarehouseId)
    }
    @Test fun openingIgnoresOldWarehouseResponse() {
        val release=raceResponses { code -> """{"items":[{"id":1,"material_code":"$code","warehouse_id":${if(code=="A")1 else 2},"quantity":7}],"page":1,"total":1,"page_size":20,"total_pages":1,"built_total":1,"built_quantity":7}""" }
        val vm=keep(OpeningStockViewModel(application))
        vm.selectWarehouse(a);pumpUntil("A sent"){server.requestCount==1}
        vm.selectWarehouse(b);pumpUntil("B displayed"){vm.uiState.value.builtItems.firstOrNull()?.materialCode=="B"}
        release.countDown();idleRequests(vm);assertEquals("B",vm.uiState.value.builtItems.firstOrNull()?.materialCode)
        assertEquals("B",vm.uiState.value.selectedWarehouse?.code)
        assertEquals(2,vm.uiState.value.builtItems.single().warehouseId)
    }
    @Test fun stocktakeRestoresOriginalWarehouse()=runBlocking {
        repo.saveStocktakeDraft(StocktakeDraft("B","Warehouse B",null,listOf(line())))
        val vm=keep(ScanViewModel(application))
        seed(vm,ScanUiState(warehouses=listOf(a,b),selectedWarehouse=a))
        vm.maybeRestoreStocktakeDraft();pumpUntil("draft restored"){vm.uiState.value.scanLines.isNotEmpty()}
        assertEquals("B",vm.uiState.value.selectedWarehouse?.code)
    }
    @Test fun emptyStocktakeDeletesPersistedDraft()=runBlocking {
        val vm=keep(ScanViewModel(application));seed(vm,ScanUiState(selectedWarehouse=b,scanLines=listOf(line())))
        vm.persistStocktakeDraft();pumpUntil("draft saved"){runBlocking{repo.loadStocktakeDraft()!=null}}
        vm.clearScanLines();vm.persistStocktakeDraft()
        awaitDraftRemoved()
        assertTrue(vm.uiState.value.scanLines.isEmpty());assertNull(repo.loadStocktakeDraft())
    }
    @Test fun queuedStocktakeClearsCorrespondingDraft()=runBlocking {
        seedLogin()
        repo.saveStocktakeDraft(StocktakeDraft("A","Warehouse A",1L,listOf(line())))
        server.shutdown();serverClosed=true
        val vm=keep(ScanViewModel(application))
        seed(vm,ScanUiState(selectedWarehouse=a,selectedCheckOrder=CheckOrderDto(1L,"CHECK-A"),scanLines=listOf(line())))
        vm.submitStocktake()
        pumpUntil("queued and page cleared"){vm.uiState.value.scanLines.isEmpty()&&vm.uiState.value.success!=null}
        awaitDraftRemoved()
        assertNull(repo.loadStocktakeDraft())
    }
    @Test fun stocktakeRetryKeepsOriginalRequestKey()=runBlocking {
        val request=StocktakeRequest(listOf(StocktakeLine("M001",3.0)),warehouseCode="A",checkId=1L)
        server.enqueue(MockResponse().setResponseCode(503).setBody("""{"status":"error","msg":"temporary"}"""))
        server.enqueue(ok("""{"check_no":"CHECK-1"}"""))
        assertTrue(repo.submitStocktake(request).isFailure);assertTrue(repo.submitStocktake(request).isSuccess)
        assertEquals(server.takeRequest().getHeader("X-Idempotency-Key"),server.takeRequest().getHeader("X-Idempotency-Key"))
    }
    @Test fun openingEditRetryKeepsOriginalRequestKey()=runBlocking {
        val request=OpeningStockUpdateRequest(8.0,1.0,revision="old-snapshot")
        server.enqueue(MockResponse().setResponseCode(503).setBody("""{"status":"error","msg":"temporary"}"""))
        server.enqueue(ok("""{"id":1,"quantity":8,"price":1,"delta":1}"""))
        assertTrue(repo.updateOpeningStock(1,request).isFailure);assertTrue(repo.updateOpeningStock(1,request).isSuccess)
        assertEquals(server.takeRequest().getHeader("X-Idempotency-Key"),server.takeRequest().getHeader("X-Idempotency-Key"))
    }
    @Test fun nextInboundHasNoPreviousEvidence()=runBlocking {
        seedLogin()
        val vm=keep(ScanViewModel(application));vm.restoreEditDraft("inbound")
        seed(vm,ScanUiState(selectedWarehouse=a,locationEnabled=false,scanLines=listOf(line()),evidence=listOf("previous-photo")))
        server.enqueue(ok("""{"id":1,"order_no":"IN-1"}"""));vm.submitInbound()
        pumpUntil("first saved"){!vm.uiState.value.isLoading&&vm.uiState.value.scanLines.isEmpty()}
        assertTrue(vm.uiState.value.evidence.isEmpty())
        vm.addScanLine(line("M002"));server.enqueue(ok("""{"id":2,"order_no":"IN-2"}"""));vm.submitInbound()
        pumpUntil("second saved"){!vm.uiState.value.isLoading&&vm.uiState.value.scanLines.isEmpty()}
        val first=JsonParser.parseString(server.takeRequest().body.readUtf8()).asJsonObject
        val second=JsonParser.parseString(server.takeRequest().body.readUtf8()).asJsonObject
        assertEquals(1,first.getAsJsonArray("evidence").size());assertEquals(0,second.getAsJsonArray("evidence").size())
    }
    @Test fun warehousesUseConfiguredDefault() {
        server.dispatcher=object:Dispatcher() {
            override fun dispatch(request:RecordedRequest)=when {
                request.path!!.startsWith("/api/warehouses") -> ok("""{"items":[{"id":1,"code":"A","name":"Warehouse A","is_default":false},{"id":2,"code":"B","name":"Configured default B","is_default":true}]}""")
                else -> ok("""{"items":[],"page":1,"total":0,"page_size":20,"total_pages":0,"built_total":0,"built_quantity":0}""")
            }
        }
        val vm=keep(OpeningStockViewModel(application));vm.loadWarehouses()
        pumpUntil("warehouse list displayed"){vm.uiState.value.warehouses.size==2}
        assertEquals("B",vm.uiState.value.selectedWarehouse?.code)
    }
    @Test fun clearConversationRejectsOldResponse() {
        val release=CountDownLatch(1);releases.add(release)
        server.dispatcher=object:Dispatcher() {
            override fun dispatch(request:RecordedRequest):MockResponse {
                check(release.await(7,TimeUnit.SECONDS))
                return ok("""{"reply":"old conversation response","conversation_id":44,"cards":[],"actions":[]}""")
            }
        }
        val vm=keep(AssistantChatViewModel(application));vm.send("original conversation")
        pumpUntil("old chat sent"){server.requestCount==1}
        vm.clearConversation();assertTrue(vm.uiState.value.messages.isEmpty())
        release.countDown()
        idleRequests(vm);assertTrue(vm.uiState.value.messages.isEmpty())
    }
    @Test fun inboundDraftRetryKeepsOriginalRequestKey()=runBlocking {
        val request=InboundDraftRequest(listOf(InboundDraftLine("M001",3.0)),warehouseCode="A")
        server.enqueue(MockResponse().setResponseCode(503).setBody("""{"status":"error","msg":"temporary"}"""))
        server.enqueue(ok("""{"order_no":"DRAFT-1","status":"pending","items":[],"auto_created":[]}"""))
        assertTrue(repo.createInboundDraft(request).isFailure);assertTrue(repo.createInboundDraft(request).isSuccess)
        assertEquals(server.takeRequest().getHeader("X-Idempotency-Key"),server.takeRequest().getHeader("X-Idempotency-Key"))
    }
    @Test fun exactMaterialEnrichmentPreservesConfirmedIdentity() {
        server.enqueue(ok("""{"id":1,"code":"M001","name":"Exact name","spec":"Exact spec"}"""))
        val vm=keep(ScanViewModel(application));vm.addScanLine(ScanLine("M001",2.0))
        pumpUntil("exact metadata applied"){vm.uiState.value.scanLines.single().material_name=="Exact name"}
        assertEquals("M001",vm.uiState.value.scanLines.single().material_code)
        assertEquals(2.0,vm.uiState.value.scanLines.single().quantity,0.0)
        assertEquals(1,server.requestCount)
    }
    @Test fun offlineCacheWorksOnlyForOriginalOwnerAndWarehouse()=runBlocking {
        server.enqueue(ok("""{"id":1,"code":"M001","name":"Private","stock":71}"""))
        repo.getMaterialInfo("M001","A").getOrThrow()
        server.shutdown();serverClosed=true
        val cached=repo.getMaterialInfo("M001","A").getOrThrow()
        assertEquals("M001",cached.code);assertTrue(cached.fromCache)
        assertEquals(71.0,cached.stock!!,0.0)
    }
    @Test fun legacyUnownedMaterialIsNeverCurrentWarehouseStock()=runBlocking {
        auditDatabase.materialDao().insert(com.factory.wms.data.local.MaterialEntity(
            "M001","Old unowned",null,null,999.0,null,null,null,null,null))
        server.shutdown();serverClosed=true
        assertTrue(repo.getMaterialInfo("M001","A").isFailure)
        assertEquals(999.0,auditDatabase.materialDao().getByCode("M001")!!.stock!!,0.0)
    }
    @Test fun noDefaultWarehouseLeavesNewOpeningUnselected() {
        server.dispatcher=object:Dispatcher(){override fun dispatch(request:RecordedRequest)=
            ok("""{"items":[{"id":1,"code":"A","name":"A","is_default":false},{"id":2,"code":"B","name":"B","is_default":false}]}""")}
        val vm=keep(OpeningStockViewModel(application));vm.loadWarehouses()
        pumpUntil("warehouse list"){vm.uiState.value.warehouses.size==2}
        assertNull(vm.uiState.value.selectedWarehouse)
        settle();assertEquals("No inventory query before warehouse selection",1,server.requestCount)
    }
    @Test fun lostOpeningEditResponseRetriesSameBodyAndProducesOneEffect()=runBlocking {
        val receipts=java.util.concurrent.ConcurrentHashMap<String,String>()
        val keys=java.util.Collections.synchronizedList(mutableListOf<String>())
        val bodies=java.util.Collections.synchronizedList(mutableListOf<String>())
        val calls=java.util.concurrent.atomic.AtomicInteger()
        server.dispatcher=object:Dispatcher(){override fun dispatch(request:RecordedRequest):MockResponse {
            val key=request.getHeader("X-Idempotency-Key")!!
            val body=request.body.readUtf8();keys.add(key);bodies.add(body)
            receipts.putIfAbsent(key,body)
            if(calls.incrementAndGet()==1) return MockResponse().setSocketPolicy(SocketPolicy.DISCONNECT_AFTER_REQUEST)
            return ok("""{"id":1,"quantity":5,"unit_price":2,"revision":"next"}""")
        }}
        val request=OpeningStockUpdateRequest(quantity=5.0,price=2.0,revision="rev-1")
        assertTrue("Transport must lose the first committed receipt",repo.updateOpeningStock(1,request).isFailure)
        val reopened=WmsRepository(application)
        assertTrue(reopened.updateOpeningStock(1,request).isSuccess)
        assertEquals(1,keys.toSet().size);assertEquals(1,bodies.toSet().size)
        assertEquals("Exactly one effect for the original request",1,receipts.size)
        assertEquals(Gson().toJson(request),bodies.first())
    }
    @Test fun uncertainOpeningCannotSilentlyReplaceFrozenPayload()=runBlocking {
        val original=OpeningStockUpdateRequest(quantity=5.0,price=2.0,revision="rev-1")
        server.enqueue(MockResponse().setResponseCode(503))
        assertTrue(repo.updateOpeningStock(1,original).isFailure)
        val requests=server.requestCount
        assertTrue(repo.updateOpeningStock(1,original.copy(quantity=9.0)).isFailure)
        assertEquals("Editing must not send a second intent while first is unknown",requests,server.requestCount)
    }
    @Test fun clearChatRejectsOldFailureAndAttachmentRestoration() {
        val release=CountDownLatch(1);releases.add(release)
        server.dispatcher=object:Dispatcher(){override fun dispatch(request:RecordedRequest):MockResponse {
            if(request.body.clone().readUtf8().contains("old text")) {
                check(release.await(7,TimeUnit.SECONDS));return MockResponse().setResponseCode(503)
            }
            return ok("""{"reply":"new reply","conversation_id":55,"cards":[],"actions":[]}""")
        }}
        val vm=keep(AssistantChatViewModel(application));vm.setPendingImage("old-image")
        vm.setPendingFile("old-file","old.txt");vm.send("old text")
        pumpUntil("old request sent"){server.requestCount==1}
        vm.clearConversation();vm.send("new text")
        pumpUntil("new response"){vm.uiState.value.messages.any{it.text=="new reply"}}
        release.countDown();idleRequests(vm)
        assertNull(vm.uiState.value.pendingImage);assertNull(vm.uiState.value.pendingFile)
        assertNull(vm.uiState.value.failedDraft);assertNull(vm.uiState.value.error)
        assertEquals(listOf("new text","new reply"),vm.uiState.value.messages.map{it.text})
    }

    @Test fun lateDefaultWarehouseListCannotRelocateRestoredStocktake()=runBlocking {
        repo.saveStocktakeDraft(StocktakeDraft("B","Warehouse B",11L,listOf(line())))
        val release=CountDownLatch(1);releases.add(release)
        val lists=java.util.concurrent.atomic.AtomicInteger()
        server.dispatcher=object:Dispatcher(){override fun dispatch(request:RecordedRequest):MockResponse {
            return if(request.path!!.startsWith("/api/warehouses")) {
                if(lists.incrementAndGet()==1) check(release.await(7,TimeUnit.SECONDS))
                ok("""{"items":[{"id":1,"code":"A","name":"Warehouse A","is_default":true},{"id":2,"code":"B","name":"Warehouse B","is_default":false}]}""")
            } else ok("""{"orders":[{"id":11,"check_no":"CHECK-B"}]}""")
        }}
        val vm=keep(ScanViewModel(application));vm.loadWarehouses()
        pumpUntil("first warehouse list sent"){server.requestCount==1}
        vm.maybeRestoreStocktakeDraft()
        pumpUntil("original context restored"){vm.uiState.value.selectedCheckOrder?.id==11L}
        release.countDown();settle()
        assertEquals("B",vm.uiState.value.selectedWarehouse?.code)
        assertEquals(11L,vm.uiState.value.selectedCheckOrder?.id)
        assertEquals("M001",vm.uiState.value.scanLines.single().material_code)
    }
    @Test fun unavailableOriginalWarehousePreservesStocktakeAndBlocksReplacement()=runBlocking {
        repo.saveStocktakeDraft(StocktakeDraft("DISABLED","Original warehouse",11L,listOf(line())))
        server.dispatcher=object:Dispatcher(){override fun dispatch(request:RecordedRequest)=
            ok("""{"items":[{"id":1,"code":"A","name":"Warehouse A","is_default":true}]}""")}
        val vm=keep(ScanViewModel(application));vm.maybeRestoreStocktakeDraft()
        pumpUntil("restore settles"){!vm.uiState.value.isLoading&&vm.uiState.value.scanLines.isNotEmpty()}
        assertNull(vm.uiState.value.selectedWarehouse)
        vm.selectWarehouse(a);vm.submitStocktake();settle()
        assertNull(vm.uiState.value.selectedWarehouse)
        assertEquals("M001",vm.uiState.value.scanLines.single().material_code)
        assertEquals("DISABLED",repo.loadStocktakeDraft()?.warehouseCode)
        assertEquals("Only the warehouse list may be requested",1,server.requestCount)
    }
    @Test fun completedOriginalCheckPreservesStocktakeWithoutSubmittingElsewhere()=runBlocking {
        repo.saveStocktakeDraft(StocktakeDraft("B","Warehouse B",11L,listOf(line())))
        server.dispatcher=object:Dispatcher(){override fun dispatch(request:RecordedRequest)=
            if(request.path!!.startsWith("/api/warehouses")) ok("""{"items":[{"id":2,"code":"B","name":"Warehouse B"}]}""")
            else ok("""{"orders":[]}""")}
        val vm=keep(ScanViewModel(application));vm.maybeRestoreStocktakeDraft()
        pumpUntil("invalid original check"){!vm.uiState.value.isLoading&&vm.uiState.value.scanLines.isNotEmpty()}
        assertEquals("B",vm.uiState.value.selectedWarehouse?.code);assertNull(vm.uiState.value.selectedCheckOrder)
        vm.selectCheckOrder(CheckOrderDto(12,"WRONG-CHECK"));vm.submitStocktake();settle()
        assertNull(vm.uiState.value.selectedCheckOrder)
        assertEquals(11L,repo.loadStocktakeDraft()?.checkId)
        assertEquals(2,server.requestCount)
    }

    @Test fun departmentEmployeesRejectLatePreviousDepartment() {
        val release=CountDownLatch(1);releases.add(release)
        server.dispatcher=object:Dispatcher(){override fun dispatch(request:RecordedRequest):MockResponse {
            val id=request.requestUrl!!.queryParameter("department_id")
            if(id=="1") check(release.await(7,TimeUnit.SECONDS))
            return ok("""{"items":[{"id":$id,"name":"Employee-$id","department_id":$id}]}""")
        }}
        val vm=keep(ScanViewModel(application));vm.selectDepartment(DepartmentDto(1,name="First"))
        pumpUntil("first department sent"){server.requestCount==1}
        vm.selectDepartment(DepartmentDto(2,name="Second"))
        pumpUntil("second employees"){vm.uiState.value.employees.singleOrNull()?.id==2L}
        release.countDown();settle()
        assertEquals(2L,vm.uiState.value.selectedDepartment?.id)
        assertEquals(listOf(2L),vm.uiState.value.employees.map{it.id})
    }
    @Test fun checkOrderOptionsRejectLatePreviousWarehouse() {
        val release=CountDownLatch(1);releases.add(release)
        server.dispatcher=object:Dispatcher(){override fun dispatch(request:RecordedRequest):MockResponse {
            val warehouse=request.requestUrl!!.queryParameter("warehouse") ?: request.requestUrl!!.queryParameter("warehouse_code")
            if(warehouse=="A") check(release.await(7,TimeUnit.SECONDS))
            val id=if(warehouse=="A") 11 else 22
            return ok("""{"orders":[{"id":$id,"check_no":"CHECK-$id"}]}""")
        }}
        val vm=keep(ScanViewModel(application));vm.selectWarehouse(a)
        pumpUntil("first check options sent"){server.requestCount==1}
        vm.selectWarehouse(b)
        pumpUntil("second check options"){vm.uiState.value.checkOrders.singleOrNull()?.id==22L}
        vm.selectCheckOrder(CheckOrderDto(22,"CHECK-22"));release.countDown();settle()
        assertEquals("B",vm.uiState.value.selectedWarehouse?.code)
        assertEquals(listOf(22L),vm.uiState.value.checkOrders.map{it.id})
        assertEquals(22L,vm.uiState.value.selectedCheckOrder?.id)
    }
    @Test fun orderStatusListRejectsOldFailureAfterNewSuccess() {
        val release=CountDownLatch(1);releases.add(release)
        server.dispatcher=object:Dispatcher(){override fun dispatch(request:RecordedRequest):MockResponse {
            if(request.requestUrl!!.queryParameter("status")=="pending") {
                check(release.await(7,TimeUnit.SECONDS));return MockResponse().setResponseCode(503)
            }
            return ok("""{"items":[{"id":2,"order_no":"COMPLETED-2","status":"completed"}],"page":1,"total_pages":1,"total":1}""")
        }}
        val vm=keep(OrderListViewModel(application));vm.start(ListKind.IN_ORDER,"1")
        pumpUntil("pending list sent"){server.requestCount==1}
        vm.setStatusFilter("completed")
        pumpUntil("completed list displayed"){!vm.uiState.value.isLoading&&vm.uiState.value.orders.size==1}
        release.countDown();idleRequests(vm)
        assertEquals("completed",vm.uiState.value.statusFilter)
        assertEquals(1,vm.uiState.value.orders.size)
        assertNull(vm.uiState.value.error);assertNull(vm.uiState.value.loadError)
    }

    @Test fun legacyUnownedStocktakeStaysPreservedWithoutBeingAssignedToCurrentAccount()=runBlocking {
        val getter=Class.forName("com.factory.wms.data.repository.WmsRepositoryKt")
            .getDeclaredMethod("getDataStore",Context::class.java).apply{isAccessible=true}
        @Suppress("UNCHECKED_CAST")
        val store=getter.invoke(null,application) as DataStore<Preferences>
        val key=stringPreferencesKey("stocktake_draft")
        val legacy=Gson().toJson(StocktakeDraft("B","Old unowned warehouse",11L,listOf(line())))
        store.edit{it[key]=legacy}
        val vm=keep(ScanViewModel(application));vm.maybeRestoreStocktakeDraft()
        pumpUntil("legacy read completed"){!vm.uiState.value.isLoading && vm.uiState.value.success != null}
        assertTrue("An unowned draft cannot be assigned to the currently logged-in account",vm.uiState.value.scanLines.isEmpty())
        assertTrue(vm.uiState.value.success.orEmpty().contains("历史"))
        assertEquals(legacy,store.data.first()[key])
        repo.logout();assertEquals(legacy,store.data.first()[key])
    }
    @Test fun consecutiveOutboundRequestsDoNotReusePreviousEvidence()=runBlocking {
        seedLogin()
        server.dispatcher=object:Dispatcher(){override fun dispatch(request:RecordedRequest)=
            if(request.path=="/api/outbound/preflight") ok("""{"warehouse_code":"A"}""")
            else ok("""{"id":7,"order_no":"OUT-7"}""")}
        val vm=keep(ScanViewModel(application));vm.restoreEditDraft("outbound")
        seed(vm,ScanUiState(selectedWarehouse=a,locationEnabled=false,scanLines=listOf(line()),evidence=listOf("outbound-first-photo")))
        vm.submitOutbound();pumpUntil("first outbound saved"){!vm.uiState.value.isLoading&&vm.uiState.value.scanLines.isEmpty()}
        assertTrue(vm.uiState.value.evidence.isEmpty())
        vm.addScanLine(line("M002"));vm.submitOutbound()
        pumpUntil("second outbound saved"){!vm.uiState.value.isLoading&&vm.uiState.value.scanLines.isEmpty()}
        val bodies=(1..4).map{server.takeRequest()}.filter{it.path=="/api/outbound"}
            .map{JsonParser.parseString(it.body.readUtf8()).asJsonObject}
        assertEquals(2,bodies.size)
        assertEquals(1,bodies[0].getAsJsonArray("evidence").size())
        assertEquals(0,bodies[1].getAsJsonArray("evidence").size())
        assertEquals("M002",bodies[1].getAsJsonArray("lines")[0].asJsonObject["material_code"].asString)
    }

    @Suppress("UNCHECKED_CAST")
    private suspend fun seedUnreadableOwnedStocktake(): Triple<DataStore<Preferences>,Preferences.Key<String>,String> {
        repo.saveStocktakeDraft(StocktakeDraft("B","Warehouse B",null,listOf(line())))
        val getter=Class.forName("com.factory.wms.data.repository.WmsRepositoryKt")
            .getDeclaredMethod("getDataStore",Context::class.java).apply{isAccessible=true}
        val store=getter.invoke(null,application) as DataStore<Preferences>
        val key=store.data.first().asMap().keys.single { it.name.startsWith("stocktake_edit_") }
        val value="{broken-json"
        val stringKey=stringPreferencesKey(key.name)
        store.edit{it[stringKey]=value}
        return Triple(store,stringKey,value)
    }
    @Test fun unreadableOwnedDraftCannotBeDeletedByAutomaticEmptySave()=runBlocking {
        val (store,key,original)=seedUnreadableOwnedStocktake()
        val vm=keep(ScanViewModel(application));vm.maybeRestoreStocktakeDraft()
        pumpUntil("bad draft read reported"){!vm.uiState.value.isLoading&&vm.uiState.value.error!=null}
        assertTrue(vm.uiState.value.scanLines.isEmpty())
        val existing=vm.viewModelScope.coroutineContext[Job]!!.children.toSet()
        vm.persistStocktakeDraft()
        val persistence=vm.viewModelScope.coroutineContext[Job]!!.children.filterNot{it in existing}.toList()
        assertTrue("An actual persistence attempt must be scheduled",persistence.isNotEmpty())
        pumpUntil("automatic persistence attempt completed"){persistence.none{it.isActive}}
        assertEquals("Automatic persistence must retain the original unreadable draft",original,store.data.first()[key])
    }
    @Test fun explicitClearReleasesUnreadableOwnedDraftProtection()=runBlocking {
        val (store,key,_)=seedUnreadableOwnedStocktake()
        val vm=keep(ScanViewModel(application));vm.maybeRestoreStocktakeDraft()
        pumpUntil("bad draft read reported"){!vm.uiState.value.isLoading&&vm.uiState.value.error!=null}
        vm.clearScanLines()
        pumpUntil("explicit raw draft deletion completed"){runBlocking{store.data.first()[key]==null}}
        assertNull(store.data.first()[key])
        vm.addScanLine(line("M002"));vm.persistStocktakeDraft()
        pumpUntil("new draft after explicit clear"){runBlocking{repo.loadStocktakeDraft()?.lines?.singleOrNull()?.material_code=="M002"}}
        assertEquals("M002",repo.loadStocktakeDraft()?.lines?.single()?.material_code)
    }

    @Suppress("UNCHECKED_CAST")
    private suspend fun seedUnreadableEditDraft(operation:String):Triple<DataStore<Preferences>,Preferences.Key<String>,String> {
        seedLogin()
        val key=stringPreferencesKey(repo.editDraftKey(operation))
        val getter=Class.forName("com.factory.wms.data.repository.WmsRepositoryKt")
            .getDeclaredMethod("getDataStore",Context::class.java).apply{isAccessible=true}
        val store=getter.invoke(null,application) as DataStore<Preferences>
        val original="{broken-$operation-json"
        store.edit{it[key]=original}
        return Triple(store,key,original)
    }
    private suspend fun unreadableEditDraftIsPreserved(operation:String) {
        val(store,key,original)=seedUnreadableEditDraft(operation)
        val vm=keep(ScanViewModel(application));vm.restoreEditDraft(operation)
        val attempt=vm.viewModelScope.launch{vm.persistEditDraft()}
        pumpUntil("$operation automatic/explicit persistence attempt completed"){!attempt.isActive}
        assertEquals("$operation unreadable edit draft must not become an automatic empty save",original,store.data.first()[key])
    }
    private suspend fun explicitEditDraftClearAllowsRecapture(operation:String) {
        val(store,key,_)=seedUnreadableEditDraft(operation)
        val vm=keep(ScanViewModel(application));vm.restoreEditDraft(operation)
        vm.clearScanLines()
        pumpUntil("$operation explicit clear completes"){runBlocking{store.data.first()[key]==null}&&!vm.uiState.value.isLoading}
        vm.addScanLine(line("M002"))
        var saved=false
        val attempt=vm.viewModelScope.launch{saved=vm.persistEditDraft()}
        pumpUntil("$operation recaptured draft persistence completed"){!attempt.isActive}
        assertTrue(saved)
        assertEquals("M002",repo.loadEditDraft(key.name)?.lines?.single()?.line?.material_code)
    }
    @Test fun unreadableInboundDraftCannotBeAutomaticallyOverwritten()=runBlocking { unreadableEditDraftIsPreserved("inbound") }
    @Test fun unreadableOutboundDraftCannotBeAutomaticallyOverwritten()=runBlocking { unreadableEditDraftIsPreserved("outbound") }
    @Test fun explicitInboundDraftClearAllowsRecapture()=runBlocking { explicitEditDraftClearAllowsRecapture("inbound") }
    @Test fun explicitOutboundDraftClearAllowsRecapture()=runBlocking { explicitEditDraftClearAllowsRecapture("outbound") }

    @Test fun unreadableEditDraftCannotBeClearedAfterAccountChanges()=runBlocking {
        val(store,key,original)=seedUnreadableEditDraft("inbound")
        val vm=keep(ScanViewModel(application));vm.restoreEditDraft("inbound")
        repo.saveLoginInfo("synthetic-other-token",server.url("/").toString(),"other-auditor","warehouse",92)
        val existing=vm.viewModelScope.coroutineContext[Job]!!.children.toSet()
        vm.clearScanLines()
        val attempts=vm.viewModelScope.coroutineContext[Job]!!.children.filterNot{it in existing}.toList()
        pumpUntil("changed-owner clear attempt completes"){attempts.none{it.isActive}}
        assertEquals("An explicit clear still requires the original owner",original,store.data.first()[key])
        assertTrue(vm.uiState.value.error.orEmpty().contains("账号"))
    }

}
