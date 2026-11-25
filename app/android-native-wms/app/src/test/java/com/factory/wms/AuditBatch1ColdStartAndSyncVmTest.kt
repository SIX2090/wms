package com.factory.wms

import android.app.Application
import android.content.Context
import android.content.Intent
import android.content.pm.PackageInstaller
import android.os.Looper
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performTextInput
import androidx.compose.ui.test.performTextReplacement
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.ViewModelStore
import androidx.test.core.app.ApplicationProvider
import com.factory.wms.data.api.RetrofitClient
import com.factory.wms.data.local.AppDatabase
import com.factory.wms.data.local.PendingOperationEntity
import com.factory.wms.data.model.InboundRequest
import com.factory.wms.data.model.PendingNativeWrite
import com.factory.wms.data.model.ScanLine
import com.factory.wms.data.repository.OfflineQueueManager
import com.factory.wms.data.repository.WmsRepository
import com.factory.wms.ui.navigation.AppNavGraph
import com.factory.wms.ui.theme.WmsTheme
import com.factory.wms.ui.viewmodel.auth.AuthViewModel
import com.factory.wms.ui.viewmodel.sync.SyncStatusViewModel
import com.factory.wms.update.AppUpdateManager
import com.factory.wms.update.UpdateBusinessGate
import com.factory.wms.update.UpdateInstaller
import com.factory.wms.update.UpdateRelease
import com.factory.wms.update.businessUpdateGate
import com.google.gson.Gson
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.emptyFlow
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import okhttp3.mockwebserver.Dispatcher
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okhttp3.mockwebserver.RecordedRequest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.Shadows
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import java.io.File

/**
 * 审计报告第一批（P-01 / P-02 / P-03 / A-01）及三项核心回归的运行时验证测试：
 * - P-01: WmsRepository 构造期不触发 Room 同步建库；
 * - P-02: AuthViewModel 启动会话恢复在后台线程读取，失败安全降级；
 * - P-03 + 冷启动顺序: 有残留安装会话且有待补传单据时，启动屏障阻止补传先抢门闩；
 * - A-01 + 登录进入首页实际入口: SyncStatusViewModel 具备 Android 默认工厂单参构造函数，
 *   沿 AppNavGraph 登录进入首页并由 Android 框架创建 GlobalQueueStatus 中的队列组件不崩溃。
 */
@OptIn(ExperimentalCoroutinesApi::class)
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [31], application = Application::class, qualifiers = "w360dp-h800dp-mdpi")
@GraphicsMode(GraphicsMode.Mode.NATIVE)
class AuditBatch1ColdStartAndSyncVmTest {

    @get:Rule(order = Int.MIN_VALUE)
    val settingsRule = WmsSettingsDataStoreRule()

    @get:Rule
    val compose = createEmptyComposeRule()

    private val app: Application get() = ApplicationProvider.getApplicationContext()

    @Before
    fun setUp() {
        businessUpdateGate.endStartupRecovery()
        businessUpdateGate.endInstall()
        clearOfflineQueueSingleton()
        clearAppDatabaseSingleton()
        app.deleteDatabase("wms_database")
        app.getSharedPreferences("app_update", Context.MODE_PRIVATE).edit().clear().commit()
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
        businessUpdateGate.endStartupRecovery()
        businessUpdateGate.endInstall()
        clearOfflineQueueSingleton()
        clearAppDatabaseSingleton()
        File(app.filesDir, "crash/last_crash.txt").delete()
        app.getSharedPreferences("app_update", Context.MODE_PRIVATE).edit().clear().commit()
    }

    @Test
    fun repositoryConstructionDoesNotOpenRoomDatabaseSynchronously() {
        val dbFile = app.getDatabasePath("wms_database")
        assertFalse("Precondition: database file should not exist", dbFile.exists())

        val repo = WmsRepository(app)
        assertFalse("WmsRepository 构造期不应同步打开 Room 数据库", dbFile.exists())
        assertNull("AppDatabase 单例在未访问 DAO 前应保持未初始化", currentDatabaseInstance())
        assertTrue(repo.javaClass.simpleName == "WmsRepository")
    }

    @Test
    fun androidDefaultViewModelFactoryInstantiatesSyncStatusViewModel() {
        // 实证 AndroidViewModelFactory 通过反射调用 public constructor(Application) 不抛异常。
        val store = ViewModelStore()
        try {
            val factory = ViewModelProvider.AndroidViewModelFactory.getInstance(app)
            val vm = ViewModelProvider(store, factory)[SyncStatusViewModel::class.java]
            assertNotNull(vm)
        } finally {
            store.clear()
        }
    }

    @Test
    fun loginThroughRealAppNavGraphReachesHomeAndCreatesGlobalQueueStatusByAndroidFramework() {
        // 实证真实「登录 -> 进入首页」入口：不传任何测试 override 参数，
        // 让 AppNavGraph -> GlobalQueueStatus -> 默认 viewModel() 由 Android 框架创建 SyncStatusViewModel。
        val server = MockWebServer()
        server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val path = request.path.orEmpty()
                return when {
                    path.startsWith("/api/login") -> MockResponse().setBody(
                        """{"status":"success","data":{"token":"tok-nav-home","user":{"id":101,"username":"tester","role":"warehouse"}}}"""
                    )
                    path.startsWith("/api/warehouses") -> MockResponse().setBody(
                        """{"status":"success","data":{"items":[{"id":1,"code":"WH1","name":"一号仓","is_default":true}]}}"""
                    )
                    path.startsWith("/api/mobile/dashboard") -> MockResponse().setBody(
                        """{"status":"success","data":{"today_in_orders":2,"today_in_quantity":20.0,"today_out_orders":1,"today_out_quantity":5.0,"pending_in_orders":0,"pending_out_orders":0,"alert_count":0,"warehouse":"一号仓","warehouse_id":1}}"""
                    )
                    else -> MockResponse().setBody("""{"status":"success","data":{}}""")
                }
            }
        }
        server.start()
        val controller = Robolectric.buildActivity(ComponentActivity::class.java).setup().visible()
        try {
            val baseUrl = server.url("/").toString()
            RetrofitClient.setSession(baseUrl, null, null)
            controller.get().setContent {
                WmsTheme(darkTheme = false) {
                    AppNavGraph()
                }
            }
            // 等待 AuthViewModel 在 IO 线程完成初始会话恢复后展示登录页
            val loginDeadline = System.currentTimeMillis() + 5000L
            var loginVisible = false
            while (System.currentTimeMillis() < loginDeadline) {
                Shadows.shadowOf(Looper.getMainLooper()).idle()
                compose.waitForIdle()
                if (compose.onAllNodesWithText("连接设置").fetchSemanticsNodes().isNotEmpty()) {
                    loginVisible = true
                    break
                }
                Thread.sleep(20)
            }
            assertTrue("未登录状态下会话恢复结束后应展示登录页", loginVisible)
            // 展开连接设置并填入本地 MockWebServer 地址
            compose.onNodeWithText("连接设置").performScrollTo().performClick()
            compose.onNodeWithText("服务器地址").performScrollTo().performTextReplacement(baseUrl)
            compose.onNodeWithText("用户名").performScrollTo().performTextInput("tester")
            compose.onNodeWithText("密码").performScrollTo().performTextInput("secret")
            compose.onNodeWithText("登录").performScrollTo().performClick()

            // 等待真实登录请求完成并导航到首页，同时组合真实 GlobalQueueStatus(default viewModel())
            val deadline = System.currentTimeMillis() + 5000L
            var reachedHome = false
            while (System.currentTimeMillis() < deadline) {
                Shadows.shadowOf(Looper.getMainLooper()).idle()
                compose.waitForIdle()
                if (compose.onAllNodesWithText("开始作业").fetchSemanticsNodes().isNotEmpty()) {
                    reachedHome = true
                    break
                }
                Thread.sleep(30)
            }
            assertTrue("登录后应成功导航至首页并由 Android 框架创建 GlobalQueueStatus 队列组件而不崩溃", reachedHome)
            compose.onNodeWithText("开始作业").performScrollTo().assertIsDisplayed()
            compose.onNodeWithText("一号仓").performScrollTo().assertIsDisplayed()
        } finally {
            disposeComposeActivity(controller)
            server.shutdown()
        }
    }

    @Test
    fun coldStartWithSurvivingInstallSessionBlocksOfflineReplayAndLetsRecoverOwnGate() = runBlocking {
        // 实证冷启动竞态修复：有残留安装会话且有待补传单据时，
        // 启动屏障阻止离线补传先抢门闩，appUpdates.recover() 必然成功接管安装会话并继续阻挡补传，
        // 直到安装会话结束后补传才正常发出。
        val server = MockWebServer()
        server.enqueue(MockResponse().setBody("""{"status":"success","data":{"order_no":"IN-REPLAY-001","status":"completed"}}"""))
        server.start()

        val baseUrl = server.url("/").toString()
        RetrofitClient.setSession(baseUrl, "tok-replay", 88)
        val ownerServer = RetrofitClient.sessionSnapshot().ownerServer!!

        // 1. 预置一条待补传入库单到真实 Room 数据库
        val db = AppDatabase.getDatabase(app)
        val dao = db.pendingOperationDao()
        val payload = Gson().toJson(
            InboundRequest(
                warehouse = "一号仓",
                warehouseCode = "WH1",
                lines = listOf(ScanLine(material_code = "M-001", quantity = 5.0))
            )
        )
        dao.upsert(
            PendingOperationEntity(
                requestId = "req-coldstart-001",
                operationType = PendingOperationEntity.TYPE_INBOUND,
                payloadJson = payload,
                warehouseCode = "WH1",
                summary = "入库 1 项",
                status = PendingOperationEntity.STATUS_PENDING,
                ownerServer = ownerServer,
                ownerUserId = 88,
                needsReview = false
            )
        )

        // 2. 预置残留的安装会话（session = 77，仍存活）
        val prefs = app.getSharedPreferences("app_update", Context.MODE_PRIVATE)
        prefs.edit()
            .putInt("session", 77)
            .putString("nonce", "nonce-77")
            .putLong("started", System.currentTimeMillis())
            .commit()

        // 步骤 A：模拟 WmsApplication.onCreate 主线程最先置位启动恢复屏障（早于任何队列或协程）
        businessUpdateGate.beginStartupRecovery()

        var sessionAlive = true
        val fakeInstaller = object : UpdateInstaller {
            override fun permitted() = true
            override fun create(release: UpdateRelease) = 77
            override fun commit(sessionId: Int, apk: File, nonce: String) {}
            override fun exists(sessionId: Int) = sessionAlive && sessionId == 77
            override fun abandon(sessionId: Int) { sessionAlive = false }
        }
        val testScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
        val updateManager = AppUpdateManager(
            context = app,
            installer = fakeInstaller,
            gate = businessUpdateGate,
            scope = testScope,
            io = Dispatchers.IO
        )
        val queue = OfflineQueueManager(
            dao = dao,
            apiProvider = { snap -> RetrofitClient.apiServiceFor(snap) },
            currentlyOnline = { true },
            onlineChanges = emptyFlow(),
            scope = testScope
        )

        try {
            // 步骤 B：真实多线程并发竞态——线程 1 在启动恢复屏障期间先触发离线补传，
            // 线程 2 稍后执行 appUpdates.recover() 抢占 beginInstall() 并释放启动屏障唤醒线程 1。
            val syncStarted = java.util.concurrent.CountDownLatch(1)
            val syncThread = Thread {
                syncStarted.countDown()
                runBlocking { queue.doSync() }
            }
            syncThread.start()
            assertTrue(syncStarted.await(2, java.util.concurrent.TimeUnit.SECONDS))
            Thread.sleep(60)
            assertEquals("recover() 完成前，并发离线补传绝不能抢发请求", 0, server.requestCount)

            // 步骤 C：后台执行 appUpdates.recover()，必然成功拿到 beginInstall() 门闩并唤醒等待中的补传线程
            updateManager.recover()
            businessUpdateGate.endStartupRecovery()
            syncThread.join(3000)
            assertFalse("补传线程应在 recover() 唤醒后迅速退出而不阻塞", syncThread.isAlive)
            assertTrue("recover() 应接管残留安装会话并进入 installing 态", updateManager.state.value.installing)
            assertEquals("recover() 拿到安装门闩后，被唤醒的离线补传仍不得发出请求", 0, server.requestCount)
            assertEquals(1, dao.listPending().size)

            // 步骤 D：启动屏障已释放，但残留安装会话仍持有 installing 门闩，再次触发补传仍被阻挡
            queue.doSync()
            assertEquals("残留安装会话存活期间，离线补传仍不得抢发请求", 0, server.requestCount)
            assertEquals(1, dao.listPending().size)

            // 步骤 E：模拟残留安装会话结束并释放门闩，随后离线补传正常发出并清空队列
            sessionAlive = false
            businessUpdateGate.endInstall()
            queue.doSync()
            assertEquals("安装门闩释放后，离线单据应正常补传一次", 1, server.requestCount)
            assertEquals(0, dao.listPending().size)
        } finally {
            testScope.cancel()
            server.shutdown()
        }
    }

    @Test
    fun authViewModelSessionRestoreDegradesSafelyOffMainThread() {
        RetrofitClient.setSession("http://127.0.0.1:9/", null, null)
        val vm = AuthViewModel(app)
        try {
            Thread.sleep(150)
            Shadows.shadowOf(Looper.getMainLooper()).idle()
            assertFalse(vm.uiState.value.isLoggedIn)
            assertNull(vm.uiState.value.error)
        } finally {
            closeWmsTestViewModels(listOf(vm))
        }
    }

    @Test
    fun syncStatusViewModelReportsReadErrorWhenQueueUnavailable() = runTest {
        val dispatcher = UnconfinedTestDispatcher(testScheduler)
        Dispatchers.setMain(dispatcher)
        val vm = SyncStatusViewModel(
            application = app,
            queueProvider = { null },
            loadPendingWrites = { emptyList() },
            ioDispatcher = dispatcher
        )
        try {
            advanceUntilIdle()
            assertTrue(vm.queueUiState.value.readError)
            assertNull(vm.queueUiState.value.snapshot)
        } finally {
            closeWmsTestViewModels(listOf(vm))
        }
    }

    @Test
    fun syncStatusViewModelIsolatesSessionsAndHandlesVerifyAndAcknowledge() = runTest {
        val dispatcher = UnconfinedTestDispatcher(testScheduler)
        Dispatchers.setMain(dispatcher)
        var currentSession = RetrofitClient.SessionSnapshot("https://a.example/", "tok-a", 1L, 10)
        val sample = PendingNativeWrite(
            operation = "stocktake",
            requestId = "req-001",
            payloadJson = "{}",
            createdAt = 1000L,
            responseJson = """{"status":"success"}"""
        )
        val verified = mutableListOf<String>()
        val acknowledged = mutableListOf<Pair<String, String>>()
        val vm = SyncStatusViewModel(
            application = app,
            queueProvider = { null },
            loadPendingWrites = { listOf(sample) },
            verifyPendingWrite = { id ->
                verified += id
                Result.success("原请求已核实完成")
            },
            acknowledgePendingWrite = { op, id ->
                acknowledged += op to id
            },
            sessionSnapshotProvider = { currentSession },
            ioDispatcher = dispatcher
        )
        try {
            vm.bindSession(currentSession)
            advanceUntilIdle()
            assertEquals(1, vm.pendingWriteUiState.value.rows.size)
            assertFalse(vm.pendingWriteUiState.value.readError)

            vm.verify(currentSession, "req-001")
            advanceUntilIdle()
            assertEquals(listOf("req-001"), verified)
            assertEquals("原请求已核实完成", vm.pendingWriteUiState.value.message)
            assertFalse(vm.pendingWriteUiState.value.busy)

            vm.acknowledge(currentSession, "stocktake", "req-001")
            advanceUntilIdle()
            assertEquals(listOf("stocktake" to "req-001"), acknowledged)
            assertTrue(vm.pendingWriteUiState.value.message!!.contains("已结束此请求"))
            assertFalse(vm.pendingWriteUiState.value.busy)

            val nextSession = RetrofitClient.SessionSnapshot("https://b.example/", "tok-b", 2L, 20)
            currentSession = nextSession
            vm.bindSession(nextSession)
            assertEquals(2L, vm.pendingWriteUiState.value.sessionGeneration)
            assertNull(vm.pendingWriteUiState.value.message)
        } finally {
            closeWmsTestViewModels(listOf(vm))
        }
    }

    @Test
    fun syncStatusViewModelOldSessionVerifyDoesNotClearNewSessionBusyFlag() = runTest {
        val dispatcher = UnconfinedTestDispatcher(testScheduler)
        Dispatchers.setMain(dispatcher)
        val sessionA = RetrofitClient.SessionSnapshot("https://a.example/", "tok-a", 1L, 10)
        val sessionB = RetrofitClient.SessionSnapshot("https://b.example/", "tok-b", 2L, 20)
        var currentSession = sessionA
        val gateA = CompletableDeferred<Result<String>>()
        val gateB = CompletableDeferred<Result<String>>()
        val vm = SyncStatusViewModel(
            application = app,
            queueProvider = { null },
            loadPendingWrites = { emptyList() },
            verifyPendingWrite = { id ->
                if (id == "req-a") gateA.await() else gateB.await()
            },
            sessionSnapshotProvider = { currentSession },
            ioDispatcher = dispatcher
        )
        try {
            vm.bindSession(sessionA)
            vm.verify(sessionA, "req-a")
            assertTrue(vm.pendingWriteUiState.value.busy)

            currentSession = sessionB
            vm.bindSession(sessionB)
            vm.verify(sessionB, "req-b")
            assertTrue(vm.pendingWriteUiState.value.busy)

            // 旧账号核实结束，不得误清当前新账号的 busy 锁
            gateA.complete(Result.success("旧账号结果"))
            advanceUntilIdle()
            assertTrue("旧账号 finally 不得清除新账号 busy 状态", vm.pendingWriteUiState.value.busy)
            assertNull("旧账号结果不得写入新账号 message", vm.pendingWriteUiState.value.message)

            gateB.complete(Result.success("新账号已核实"))
            advanceUntilIdle()
            assertFalse(vm.pendingWriteUiState.value.busy)
            assertEquals("新账号已核实", vm.pendingWriteUiState.value.message)
        } finally {
            closeWmsTestViewModels(listOf(vm))
        }
    }

    @Test
    fun deferredInstallResultBroadcastDuringStartupRecoveryIsDeliveredAfterRecover() {
        val isolatedGate = UpdateBusinessGate()
        val prefs = app.getSharedPreferences("app_update", Context.MODE_PRIVATE)
        prefs.edit()
            .putInt("session", 88)
            .putString("nonce", "nonce-88")
            .putLong("started", System.currentTimeMillis())
            .commit()

        var sessionAlive = true
        val fakeInstaller = object : UpdateInstaller {
            override fun permitted() = true
            override fun create(release: UpdateRelease) = 88
            override fun commit(sessionId: Int, apk: File, nonce: String) {}
            override fun exists(sessionId: Int) = sessionAlive && sessionId == 88
            override fun abandon(sessionId: Int) { sessionAlive = false }
        }
        val testScope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
        val manager = AppUpdateManager(
            context = app,
            installer = fakeInstaller,
            gate = isolatedGate,
            scope = testScope,
            io = Dispatchers.IO
        )
        try {
            isolatedGate.beginStartupRecovery()
            val broadcast = Intent("${app.packageName}.UPDATE_RESULT.nonce-88").apply {
                putExtra("wms_nonce", "nonce-88")
                putExtra(PackageInstaller.EXTRA_SESSION_ID, 88)
                putExtra(PackageInstaller.EXTRA_STATUS, PackageInstaller.STATUS_SUCCESS)
            }
            // 模拟系统广播先于后台 recover() 到达
            manager.receive(broadcast)

            manager.recover()
            isolatedGate.endStartupRecovery()
            manager.onStartupRecoveryFinished()
            Shadows.shadowOf(Looper.getMainLooper()).idle()

            assertFalse("启动窗口暂存的成功广播补派发后应退出 installing 态", manager.state.value.installing)
            assertTrue("应展示安装已完成文案", manager.state.value.message.contains("安装已完成"))
            assertTrue("补派发释放门闩后业务写入应恢复可用", isolatedGate.enterBusiness(0L))
            isolatedGate.leaveBusiness()
        } finally {
            testScope.cancel()
        }
    }

    @Test
    @Suppress("UNCHECKED_CAST")
    fun savedSessionRestoresDirectlyToHomeWithoutFlashingLogin() {
        val server = MockWebServer()
        server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val path = request.path.orEmpty()
                return when {
                    path.startsWith("/api/warehouses") -> MockResponse().setBody(
                        """{"status":"success","data":{"items":[{"id":1,"code":"WH1","name":"一号仓","is_default":true}]}}"""
                    )
                    path.startsWith("/api/mobile/dashboard") -> MockResponse().setBody(
                        """{"status":"success","data":{"today_in_orders":1,"today_in_quantity":10.0,"today_out_orders":0,"today_out_quantity":0.0,"pending_in_orders":0,"pending_out_orders":0,"alert_count":0,"warehouse":"一号仓","warehouse_id":1}}"""
                    )
                    else -> MockResponse().setBody("""{"status":"success","data":{}}""")
                }
            }
        }
        server.start()
        val baseUrl = server.url("/").toString()
        val controller = Robolectric.buildActivity(ComponentActivity::class.java).setup().visible()
        try {
            val auth = ViewModelProvider(controller.get())[AuthViewModel::class.java]
            val waitInitDeadline = System.currentTimeMillis() + 3000L
            while (auth.uiState.value.isRestoringSession && System.currentTimeMillis() < waitInitDeadline) {
                Shadows.shadowOf(Looper.getMainLooper()).idle()
                Thread.sleep(10)
            }
            val uiStateField = AuthViewModel::class.java.getDeclaredField("_uiState").apply { isAccessible = true }
            val stateFlow = uiStateField.get(auth) as kotlinx.coroutines.flow.MutableStateFlow<com.factory.wms.ui.viewmodel.auth.AuthUiState>

            // 1. 会话仍在 IO 恢复中：AppNavGraph 仅展示背景占位，绝不闪现登录页
            stateFlow.value = com.factory.wms.ui.viewmodel.auth.AuthUiState(isRestoringSession = true)
            controller.get().setContent {
                WmsTheme(darkTheme = false) {
                    AppNavGraph()
                }
            }
            Shadows.shadowOf(Looper.getMainLooper()).idle()
            compose.waitForIdle()
            assertTrue(
                "会话恢复完成前不应闪现登录页",
                compose.onAllNodesWithText("登录工作台").fetchSemanticsNodes().isEmpty()
            )
            assertTrue(
                "会话恢复完成前不应提前挂载首页",
                compose.onAllNodesWithText("开始作业").fetchSemanticsNodes().isEmpty()
            )

            // 2. 模拟 IO 恢复完成并写回有效登录态：直接落到首页且全程未出现登录页
            RetrofitClient.setSession(baseUrl, "tok-restored", 77)
            stateFlow.value = com.factory.wms.ui.viewmodel.auth.AuthUiState(
                isLoggedIn = true,
                username = "keeper",
                role = "warehouse",
                baseUrl = baseUrl,
                isRestoringSession = false
            )
            var sawLoginScreen = false
            var reachedHome = false
            val deadline = System.currentTimeMillis() + 5000L
            while (System.currentTimeMillis() < deadline) {
                Shadows.shadowOf(Looper.getMainLooper()).idle()
                compose.waitForIdle()
                if (compose.onAllNodesWithText("登录工作台").fetchSemanticsNodes().isNotEmpty()) {
                    sawLoginScreen = true
                }
                if (compose.onAllNodesWithText("开始作业").fetchSemanticsNodes().isNotEmpty()) {
                    reachedHome = true
                    break
                }
                Thread.sleep(20)
            }
            assertFalse("已保存有效会话时冷启动不应闪现登录页", sawLoginScreen)
            assertTrue("已保存有效会话时应直接进入首页", reachedHome)
        } finally {
            disposeComposeActivity(controller)
            RetrofitClient.setSession("", null, null)
            server.shutdown()
        }
    }

    @Test
    fun mainActivityReadsCrashFileAsynchronouslyWithoutCrashing() {
        val crashDir = File(app.filesDir, "crash").apply { mkdirs() }
        val crashFile = File(crashDir, "last_crash.txt")
        crashFile.writeText("synthetic crash trace for P-03 test")

        val controller = Robolectric.buildActivity(MainActivity::class.java).setup().visible()
        try {
            Thread.sleep(150)
            Shadows.shadowOf(Looper.getMainLooper()).idle()
            assertTrue("崩溃文件在用户点击继续前不应被自动删除", crashFile.exists())
        } finally {
            controller.pause().stop().destroy()
            Shadows.shadowOf(Looper.getMainLooper()).idle()
        }
    }

    private fun clearOfflineQueueSingleton() {
        runCatching {
            val field = OfflineQueueManager::class.java.getDeclaredField("instance")
            field.isAccessible = true
            field.set(null, null)
        }
    }

    private fun clearAppDatabaseSingleton() {
        val field = AppDatabase::class.java.getDeclaredField("INSTANCE")
        field.isAccessible = true
        (field.get(null) as? AppDatabase)?.close()
        field.set(null, null)
    }

    private fun currentDatabaseInstance(): Any? {
        val field = AppDatabase::class.java.getDeclaredField("INSTANCE")
        field.isAccessible = true
        return field.get(null)
    }
}
