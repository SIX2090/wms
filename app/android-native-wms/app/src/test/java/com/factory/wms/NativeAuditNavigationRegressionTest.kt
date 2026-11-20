package com.factory.wms

import android.app.Application
import android.content.Context
import android.os.Bundle
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import kotlinx.coroutines.flow.first
import android.os.Looper
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.runtime.SideEffect
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.ui.test.*
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.navigation.NavHostController
import androidx.navigation.compose.rememberNavController
import androidx.test.core.app.ApplicationProvider
import com.factory.wms.data.api.*
import com.factory.wms.data.model.*
import com.factory.wms.data.repository.WmsRepository
import com.factory.wms.ui.navigation.*
import com.factory.wms.ui.theme.WmsTheme
import com.factory.wms.ui.viewmodel.ai.*
import com.factory.wms.ui.viewmodel.auth.*
import com.factory.wms.ui.viewmodel.scan.*
import com.google.gson.Gson
import kotlinx.coroutines.*
import kotlinx.coroutines.test.*
import kotlinx.coroutines.flow.MutableStateFlow
import okhttp3.mockwebserver.*
import org.junit.*
import org.junit.Assert.*
import org.junit.runner.RunWith
import org.robolectric.*
import org.robolectric.android.controller.ActivityController
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

/** Actual application graph, actual recognition CTA and parent list across Navigation Compose owners. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk=[31],application=Application::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@OptIn(ExperimentalCoroutinesApi::class)
class NativeAuditNavigationRegressionTest {
    private val main=StandardTestDispatcher()
    private lateinit var stores:NativeAuditLocalStores
    @get:Rule val compose=createEmptyComposeRule()
    private val graphInstance = mutableIntStateOf(0)
    private var savedNavigation: Bundle? = null
    private lateinit var activity:ActivityController<ComponentActivity>
    private lateinit var server:MockWebServer
    private lateinit var nav:NavHostController
    private lateinit var parent:ScanViewModel
    @Before fun before() {
        Dispatchers.setMain(main)
        DataStoreTestReset.resetWmsSettingsDataStore()
        server=MockWebServer()
        server.dispatcher=object:Dispatcher(){override fun dispatch(request:RecordedRequest):MockResponse {
            if (request.requestUrl?.encodedPath == "/mobile/api/material_archive/404/images") {
                return MockResponse().setResponseCode(404).setHeader("Content-Type", "application/json")
                    .setBody("""{"status":"error","msg":"物料不存在"}""")
            }
            val data=when {
                request.path!!.startsWith("/api/warehouses") -> """{"items":[{"id":1,"code":"A","name":"Warehouse A","is_default":true}]}"""
                request.path!!.startsWith("/api/stocktake/check_orders") -> """{"orders":[{"id":11,"check_no":"CHECK-A","warehouse":"Warehouse A"}]}"""
                request.path!!.startsWith("/api/mobile/location/options") -> """{"enabled":false,"items":[],"page":1,"total_pages":1}"""
                request.path!!.startsWith("/api/material/info") -> """{"id":1,"code":"M001","name":"Recognized M001","spec":"S"}"""
                request.requestUrl?.encodedPath == "/mobile/api/material_archive/search" ->
                    """{"items":[{"id":17,"code":"ARCH-17","name":"档案查询记录"}],"total":1}"""
                request.requestUrl?.encodedPath == "/mobile/api/material_archive/17/images" ->
                    """{"material":{"id":17,"code":"ARCH-17","name":"档案详情记录"},"images":[]}"""
                else -> "{}"
            }
            return MockResponse().setHeader("Content-Type","application/json").setBody("""{"status":"success","data":$data}""")
        }}
        server.start()
        val app=ApplicationProvider.getApplicationContext<Application>()
        stores=NativeAuditLocalStores(app)
        runBlocking { WmsRepository(app).saveLoginInfo("synthetic-nav-token",server.url("/").toString(),"nav-auditor","warehouse",91) }
        activity=Robolectric.buildActivity(ComponentActivity::class.java).setup().visible()
        val auth=ViewModelProvider(activity.get())[AuthViewModel::class.java]
        repeat(50){main.scheduler.runCurrent();Shadows.shadowOf(Looper.getMainLooper()).idle();Thread.sleep(10)}
        state<AuthUiState>(auth).value=AuthUiState(isLoggedIn=true,username="nav-auditor",role="warehouse",baseUrl=server.url("/").toString())
        RetrofitClient.setSession(server.url("/").toString(),"synthetic-nav-token",91)
        activity.get().setContent {
            key(graphInstance.intValue) {
                val controller = rememberNavController()
                remember(controller) { controller.restoreState(savedNavigation) }
                SideEffect { nav = controller }
                WmsTheme(darkTheme = false) { AppNavGraph(controller) }
            }
        }
        compose.waitForIdle()
    }
    @After fun after(){
        disposeComposeActivity(activity)
        drainPendingQuantityDraftWrites { main.scheduler.runCurrent(); Shadows.shadowOf(Looper.getMainLooper()).idle() }
        main.scheduler.runCurrent();stores.close()
        RetrofitClient.setSession("",null);server.shutdown();Dispatchers.resetMain()
    }
    @Suppress("UNCHECKED_CAST")
    private fun <T> state(model:Any):MutableStateFlow<T> = model.javaClass.getDeclaredField("_uiState").apply{isAccessible=true}.get(model) as MutableStateFlow<T>

    private fun waitForText(text: String) {
        compose.waitUntil(10000) {
            main.scheduler.runCurrent()
            Shadows.shadowOf(Looper.getMainLooper()).idle()
            compose.onAllNodesWithText(text, useUnmergedTree = true).fetchSemanticsNodes().isNotEmpty()
        }
    }

    @Test fun archiveDetailRestoresSelectedIdAndReportsDeletedMaterial() {
        compose.runOnIdle { nav.navigate(Screen.MaterialArchive.route) }
        waitForText("档案查询记录")
        compose.onNode(hasClickAction() and hasText("档案查询记录")).performClick()
        waitForText("档案详情记录")
        compose.runOnIdle { assertEquals(17, nav.currentBackStackEntry?.arguments?.getInt("materialId")) }

        val auth = ViewModelProvider(activity.get())[AuthViewModel::class.java]
        val signedIn = auth.uiState.value
        compose.runOnIdle {
            savedNavigation = checkNotNull(nav.saveState())
            state<AuthUiState>(auth).value = AuthUiState()
            graphInstance.intValue++
        }
        compose.runOnIdle { state<AuthUiState>(auth).value = signedIn }
        waitForText("档案详情记录")
        compose.runOnIdle { assertEquals(17, nav.currentBackStackEntry?.arguments?.getInt("materialId")) }

        compose.runOnIdle { nav.navigate("${Screen.MaterialArchiveDetail.route}/404") }
        waitForText("物料不存在")
        compose.onNodeWithText("物料档案加载失败").assertIsDisplayed()
        compose.onNodeWithText("重试").assertHasClickAction()
        compose.runOnIdle { assertTrue(nav.popBackStack()) }
        waitForText("档案详情记录")
    }
    @Test fun recognitionReturnsLineToOriginalStocktakeWithWarehouseCheckAndArea() {
        compose.runOnIdle{nav.navigate(Screen.Stocktake.route)}
        compose.waitUntil(10000){
            main.scheduler.runCurrent();Shadows.shadowOf(Looper.getMainLooper()).idle()
            val owner=nav.getBackStackEntry(Screen.Stocktake.route)
            parent=ViewModelProvider(owner,ScanViewModel.Factory)["stocktake",ScanViewModel::class.java]
            parent.uiState.value.warehouses.isNotEmpty()&&!parent.uiState.value.isLoading
        }
        compose.runOnIdle {
            val current=parent.uiState.value
            // Input fixture only: preserve the exact context whose navigation ownership is under test.
            state<ScanUiState>(parent).value=current.copy(selectedWarehouse=WarehouseDto(1,"A","Warehouse A"),
                selectedCheckOrder=CheckOrderDto(11,"CHECK-A"),selectedLocation="AREA-7",locationEnabled=false)
            nav.navigate(Screen.StocktakeRecognize.route)
        }
        compose.waitForIdle()
        main.scheduler.runCurrent()
        compose.runOnIdle {
            val ai=ViewModelProvider(nav.currentBackStackEntry!!,ViewModelProvider.AndroidViewModelFactory.getInstance(activity.get().application))[AiViewModel::class.java]
            state<AiUiState>(ai).value=AiUiState(recognizedMaterial=Gson().fromJson(
                """{"extracted":{"code":"M001","name":"Recognized M001","quantity":3},"matches":[{"id":1,"code":"M001","name":"Recognized M001","spec":"S"}],"match_count":1}""",
                RecognizeMaterialResult::class.java))
        }
        compose.onNodeWithText("加入盘点清单").performScrollTo().performClick()
        compose.waitForIdle()
        compose.runOnIdle {
            assertEquals(Screen.Stocktake.route,nav.currentDestination?.route)
            assertEquals("A",parent.uiState.value.selectedWarehouse?.code)
            assertEquals(11L,parent.uiState.value.selectedCheckOrder?.id)
            assertEquals("AREA-7",parent.uiState.value.selectedLocation)
            assertEquals("M001",parent.uiState.value.scanLines.single().material_code)
            assertEquals("AREA-7",parent.uiState.value.scanLines.single().location_code)
            assertEquals(3.0,parent.uiState.value.scanLines.single().quantity,0.0)
        }
        // The context above the list can occupy the first viewport; verify the actual
        // line remains visible after scrolling instead of assuming it starts onscreen.
        compose.onNode(hasScrollAction() and hasAnyDescendant(hasText("1 行物料")), useUnmergedTree = true)
            .performSemanticsAction(SemanticsActions.ScrollBy) { scroll -> scroll(0f, 1000f) }
        compose.waitForIdle()
        compose.onNodeWithText("编码 M001").performScrollTo().assertIsDisplayed()
    }
    @Test fun unreadableDraftRequiresExplicitConfirmationAndCancelRetainsOriginal() {
        val application=ApplicationProvider.getApplicationContext<Application>()
        val repository=WmsRepository(application)
        runBlocking { repository.saveStocktakeDraft(StocktakeDraft("A","Warehouse A",null,listOf(ScanLine("M001",3.0)))) }
        val getter=Class.forName("com.factory.wms.data.repository.WmsRepositoryKt")
            .getDeclaredMethod("getDataStore",Context::class.java).apply{isAccessible=true}
        @Suppress("UNCHECKED_CAST")
        val preferences=getter.invoke(null,application) as DataStore<Preferences>
        val key=runBlocking { preferences.data.first().asMap().keys.single{it.name.startsWith("stocktake_edit_")} }
        val stringKey=stringPreferencesKey(key.name)
        val original="{broken-json"
        runBlocking { preferences.edit{it[stringKey]=original} }
        compose.runOnIdle { nav.navigate(Screen.Stocktake.route) }
        compose.waitUntil(10000) {
            main.scheduler.runCurrent();Shadows.shadowOf(Looper.getMainLooper()).idle()
            parent=ViewModelProvider(nav.getBackStackEntry(Screen.Stocktake.route),ScanViewModel.Factory)["stocktake",ScanViewModel::class.java]
            !parent.uiState.value.isLoading && parent.uiState.value.error!=null
        }
        // Execute the real screen's delayed autosave before offering explicit deletion.
        main.scheduler.advanceTimeBy(1000);main.scheduler.runCurrent();compose.waitForIdle()
        assertEquals(original,runBlocking{preferences.data.first()[stringKey]})
        compose.onNodeWithText("清空无法读取的盘点草稿").performClick()
        compose.onNodeWithText("清空无法读取的盘点草稿？").assertExists()
        compose.onNodeWithText("取消").performClick()
        assertEquals(original,runBlocking{preferences.data.first()[stringKey]})
        compose.onNodeWithText("清空无法读取的盘点草稿").performClick()
        val existing=parent.viewModelScope.coroutineContext[Job]!!.children.toSet()
        compose.onNodeWithText("确认清空并重新盘点").performClick()
        val clearJobs=parent.viewModelScope.coroutineContext[Job]!!.children.filterNot { it in existing }.toList()
        assertTrue("Explicit confirmation must schedule the draft deletion", clearJobs.isNotEmpty())
        compose.waitUntil(10000) {
            main.scheduler.runCurrent();Shadows.shadowOf(Looper.getMainLooper()).idle()
            clearJobs.none { it.isActive }
        }
        assertNull(parent.uiState.value.draftSaveError)
        assertNull(runBlocking{preferences.data.first()[stringKey]})
        compose.onNodeWithText("清空无法读取的盘点草稿").assertDoesNotExist()
        compose.runOnIdle { parent.addScanLine(ScanLine("M002",2.0,material_name="Next material",material_spec="S")) }
        assertEquals("M002",parent.uiState.value.scanLines.single().material_code)
    }

}
