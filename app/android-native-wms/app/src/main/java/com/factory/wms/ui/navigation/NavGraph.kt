package com.factory.wms.ui.navigation

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowDownward
import androidx.compose.material.icons.filled.ArrowUpward
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.outlined.ArrowDownward
import androidx.compose.material.icons.outlined.ArrowUpward
import androidx.compose.material.icons.outlined.Home
import androidx.compose.material.icons.outlined.Person
import androidx.compose.material.icons.outlined.Search
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.factory.wms.data.api.AuthEventBus
import com.factory.wms.data.model.MaterialArchiveDto
import com.factory.wms.ui.components.VoiceAssistantOverlay
import com.factory.wms.ui.screens.*
import com.factory.wms.ui.theme.Primary
import com.factory.wms.ui.viewmodel.ai.AiViewModel
import com.factory.wms.ui.viewmodel.archive.MaterialArchiveViewModel
import com.factory.wms.ui.viewmodel.auth.AuthViewModel
import com.factory.wms.ui.viewmodel.home.HomeViewModel
import com.factory.wms.ui.viewmodel.list.OrderListViewModel
import com.factory.wms.ui.viewmodel.opening.OpeningStockViewModel
import com.factory.wms.ui.viewmodel.report.ReportViewModel
import com.factory.wms.ui.viewmodel.report.StockDailyReportViewModel
import com.factory.wms.ui.viewmodel.scan.ScanViewModel
import com.factory.wms.ui.viewmodel.stocktake.StocktakeRecordViewModel
import com.factory.wms.ui.viewmodel.voice.VoiceCommandViewModel
import com.factory.wms.ui.viewmodel.voice.VoiceOutDraftViewModel

/** 底部 Tab 命中的一级路由：这些页面显示底部导航栏。 */
private val bottomTabRoutes = setOf(
    Screen.Home.route,
    Screen.Inbound.route,
    Screen.Outbound.route,
    Screen.StockQuery.route,
    Screen.Profile.route
)

/** 底部 Tab 定义。 */
private data class BottomTab(
    val screen: Screen,
    val label: String,
    val selectedIcon: ImageVector,
    val unselectedIcon: ImageVector
)

/** 下钻路由的两个可选参数：wid = 仓库 id，wname = 仓库名（标题展示用）。 */
private fun overviewDrilldownArgs() = listOf(
    navArgument("wid") { type = NavType.StringType; defaultValue = "" },
    navArgument("wname") { type = NavType.StringType; defaultValue = "" }
)

/**
 * 把仓库名等明文拼进路由前做转义。
 *
 * 仓库名可能含 `/`、`?`、空格、中文——直接拼进 route 会被 Navigation 当成
 * 路径分隔或参数起始符，导致下钻页拿到错误参数甚至匹配不到目的地。
 * `Uri.encode` 保留 `/`，所以这里显式把它换成 `%2F`（同出库页合同号的
 * 拼参处理口径一致）。
 */
private fun encodeQueryValue(raw: String?): String =
    android.net.Uri.encode(raw.orEmpty()).replace("/", "%2F")

@Composable
private fun bottomTabs(): List<BottomTab> = listOf(
    BottomTab(Screen.Home, "首页", Icons.Filled.Home, Icons.Outlined.Home),
    BottomTab(Screen.Inbound, "入库", Icons.Filled.ArrowDownward, Icons.Outlined.ArrowDownward),
    BottomTab(Screen.Outbound, "出库", Icons.Filled.ArrowUpward, Icons.Outlined.ArrowUpward),
    BottomTab(Screen.StockQuery, "查库存", Icons.Filled.Search, Icons.Outlined.Search),
    BottomTab(Screen.Profile, "我的", Icons.Filled.Person, Icons.Outlined.Person)
)

@Composable
fun AppNavGraph() {
    val navController = rememberNavController()

    // BUG-2026-09-14-032（本次修复的根因）：此处**不得**再饿汉创建全部 ViewModel。
    //
    // 历史：本函数原先在这里一次性创建 14 个 ViewModel，导致「App 启动组合期」就构造了
    // 所有页面的 ViewModel（含语音/AI/期初/报表等用户可能从不打开的页面，以及 4 个
    // ScanViewModel 副本）。三个具体危害：
    //   1) **崩溃放大**：任一 VM 构造期抛异常 = 整个进程闪退（BUG-2026-09-14-029 的
    //      ScanViewModel 崩溃就是被这里放大成"打开应用即闪退"的）；
    //   2) **启动开销与内存常驻**：14 个 VM 及其依赖的 Repository/DAO/协程作用域全部常驻；
    //   3) **竞态温床**：VM 在"会话尚未还原"时就被构造，init 里发起网络请求必然读到空
    //      baseUrl。BUG-2026-08-24-006 已记录过这个竞态（ReportViewModel 报表报错），
    //      当时只给 ReportViewModel 打了"不在 init 加载"的局部补丁，**根因（饿汉创建）
    //      从未消除**——本次一并根治。
    //
    // 现方案：只有 authViewModel 保留在顶层（startDestination 需读其 isLoggedIn 状态，
    // 且它必须在导航建立前就存在）；其余全部下沉到各自 composable 路由内按需创建。
    // 路由内 `viewModel()` 的宿主是 Activity 级 ViewModelStore，同一 key 在跨路由时
    // **复用同一实例**，故：
    //   - 4 个 ScanViewModel 用不同 key，切换页面各自独立（与修复前语义一致）；
    //   - 语音悬浮层、AI 双页面共用等跨路由共享场景，key 相同 → 实例相同，语义不变。
    val authViewModel: AuthViewModel = viewModel()

    // 物料档案详情：选中的物料通过共享状态传递（避免 route 参数序列化 DTO）
    var selectedMaterialArchive by remember { mutableStateOf<MaterialArchiveDto?>(null) }

    // AI-VOICE-OUT-F01：语音建单草稿预填出库页。
    // 用共享状态而非 route 参数，与 selectedMaterialArchive 同一套跨屏传值惯例
    // （出库页消费后立即清空，避免重复累加）。
    var voicePrefillLines by remember { mutableStateOf<List<Pair<String, Double>>>(emptyList()) }
    var voiceDraftOrderNo by remember { mutableStateOf<String?>(null) }

    val authState by authViewModel.uiState.collectAsState()

    val startDestination = if (authState.isLoggedIn) Screen.Home.route else Screen.Login.route

    // 当前目标路由，用于决定是否显示底部 Tab
    val navBackStackEntry by navController.currentBackStackEntryAsState()
    val currentRoute = navBackStackEntry?.destination?.route
    val showBottomBar = currentRoute in bottomTabRoutes

    // Listen for 401 unauthorized events and navigate to login
    LaunchedEffect(Unit) {
        AuthEventBus.unauthorizedEvents.collect {
            navController.navigate(Screen.Login.route) {
                popUpTo(0) { inclusive = true }
            }
        }
    }

    Box(modifier = Modifier.fillMaxSize()) {
        Scaffold(
            containerColor = com.factory.wms.ui.theme.Background,
            bottomBar = {
                if (showBottomBar) {
                    WmsBottomBar(
                        currentRoute = currentRoute,
                        tabs = bottomTabs(),
                        onTabSelected = { screen ->
                            navController.navigate(screen.route) {
                                // 单实例 back stack：切 Tab 收敛到首页后复用已保存状态
                                popUpTo(Screen.Home.route) { saveState = true }
                                launchSingleTop = true
                                restoreState = true
                            }
                        }
                    )
                }
            }
        ) { innerPadding ->
            NavHost(
                navController = navController,
                startDestination = startDestination,
                modifier = Modifier.padding(bottom = innerPadding.calculateBottomPadding())
            ) {
                composable(Screen.Login.route) {
                    LoginScreen(
                        viewModel = authViewModel,
                        onLoginSuccess = {
                            navController.navigate(Screen.Home.route) {
                                popUpTo(Screen.Login.route) { inclusive = true }
                            }
                        }
                    )
                }

                composable(Screen.Home.route) {
                    // 首页 Overview 需读 VM 的 selectedWarehouseId/warehouse 拼下钻参数，
                    // 故在路由内先取实例再传给 Screen（同一 key，跨重组复用）。
                    val homeViewModel: HomeViewModel = viewModel()
                    HomeScreen(
                        authViewModel = authViewModel,
                        homeViewModel = homeViewModel,
                        onNavigate = { screen ->
                            // 下钻路由需要从首页带上当前仓库（后端按仓隔离，
                            // 缺仓库会回退服务端默认仓，与首页口径不一致）
                            navController.navigate(
                                when (screen) {
                                    Screen.OverviewOrders, Screen.OverviewAlerts -> {
                                        val wid = homeViewModel.uiState.value.selectedWarehouseId.orEmpty()
                                        val wname = homeViewModel.uiState.value.dashboard?.warehouse.orEmpty()
                                        screen.route
                                            .replace("{wid}", encodeQueryValue(wid))
                                            .replace("{wname}", encodeQueryValue(wname))
                                    }
                                    else -> screen.route
                                }
                            )
                        },
                        onLogout = {
                            navController.navigate(Screen.Login.route) {
                                popUpTo(0) { inclusive = true }
                            }
                        }
                    )
                }

                composable(Screen.Inbound.route) {
                    val inboundScanViewModel: ScanViewModel = viewModel(key = "inbound_scan")
                    InboundScreen(
                        viewModel = inboundScanViewModel,
                        onBack = { navController.popBackStack() }
                    )
                }

                composable(Screen.Outbound.route) {
                    val outboundScanViewModel: ScanViewModel = viewModel(key = "outbound_scan")
                    val voiceDraftViewModel: VoiceOutDraftViewModel = viewModel()
                    OutboundScreen(
                        viewModel = outboundScanViewModel,
                        onBack = { navController.popBackStack() },
                        voicePrefillLines = voicePrefillLines,
                        onVoicePrefillConsumed = { voicePrefillLines = emptyList() },
                        voiceDraftOrderNo = voiceDraftOrderNo,
                        onDismissVoiceDraft = { voiceDraftOrderNo = null },
                        // 出库页换仓 → 单向回写语音建单流程，保证草稿仓库与界面一致
                        onVoiceWarehouseChanged = { voiceDraftViewModel.selectWarehouse(it) }
                    )
                }

                composable(Screen.StockQuery.route) {
                    val stockQueryViewModel: ScanViewModel = viewModel(key = "stock_query")
                    StockQueryScreen(
                        viewModel = stockQueryViewModel,
                        onBack = { navController.popBackStack() }
                    )
                }

                composable(Screen.Stocktake.route) {
                    val stocktakeViewModel: ScanViewModel = viewModel(key = "stocktake")
                    StocktakeScreen(
                        viewModel = stocktakeViewModel,
                        onBack = { navController.popBackStack() },
                        onRecognize = { navController.navigate(Screen.StocktakeRecognize.route) }
                    )
                }

                composable(Screen.OpeningStock.route) {
                    val openingStockViewModel: OpeningStockViewModel = viewModel()
                    OpeningStockScreen(
                        viewModel = openingStockViewModel,
                        onBack = { navController.popBackStack() }
                    )
                }

                composable(Screen.DocumentOcr.route) {
                    val aiViewModel: AiViewModel = viewModel()
                    DocumentOcrScreen(
                        viewModel = aiViewModel,
                        onBack = { navController.popBackStack() }
                    )
                }

                composable(Screen.ObjectRecognize.route) {
                    val aiViewModel: AiViewModel = viewModel()
                    ObjectRecognizeScreen(
                        viewModel = aiViewModel,
                        onBack = { navController.popBackStack() }
                    )
                }

                composable(Screen.StocktakeRecognize.route) {
                    val aiViewModel: AiViewModel = viewModel()
                    val stocktakeViewModel: ScanViewModel = viewModel(key = "stocktake")
                    StocktakeRecognizeScreen(
                        aiViewModel = aiViewModel,
                        scanViewModel = stocktakeViewModel,
                        onBack = { navController.popBackStack() }
                    )
                }

                composable(Screen.MaterialArchive.route) {
                    val materialArchiveViewModel: MaterialArchiveViewModel = viewModel()
                    MaterialArchiveSearchScreen(
                        viewModel = materialArchiveViewModel,
                        onBack = { navController.popBackStack() },
                        onOpenDetail = { material ->
                            selectedMaterialArchive = material
                            navController.navigate(Screen.MaterialArchiveDetail.route)
                        }
                    )
                }

                composable(Screen.MaterialArchiveDetail.route) {
                    val materialArchiveViewModel: MaterialArchiveViewModel = viewModel()
                    val material = selectedMaterialArchive
                    if (material != null) {
                        MaterialArchiveDetailScreen(
                            material = material,
                            viewModel = materialArchiveViewModel,
                            onBack = { navController.popBackStack() }
                        )
                    }
                }

                composable(
                    route = Screen.OverviewAlerts.route,
                    arguments = overviewDrilldownArgs()
                ) { entry ->
                    val overviewListViewModel: OrderListViewModel = viewModel(key = "overview_list")
                    OverviewListScreen(
                        target = OverviewTarget.ALERT,
                        viewModel = overviewListViewModel,
                        warehouseId = entry.arguments?.getString("wid").orEmpty(),
                        warehouseName = entry.arguments?.getString("wname").orEmpty(),
                        onBack = { navController.popBackStack() }
                    )
                }

                composable(
                    route = Screen.OverviewOrders.route,
                    arguments = overviewDrilldownArgs()
                ) { entry ->
                    val overviewListViewModel: OrderListViewModel = viewModel(key = "overview_list")
                    OverviewListScreen(
                        target = OverviewTarget.PENDING_ORDERS,
                        viewModel = overviewListViewModel,
                        warehouseId = entry.arguments?.getString("wid").orEmpty(),
                        warehouseName = entry.arguments?.getString("wname").orEmpty(),
                        onBack = { navController.popBackStack() }
                    )
                }

                composable(Screen.DailyReport.route) {
                    val reportViewModel: ReportViewModel = viewModel()
                    DailyReportScreen(
                        viewModel = reportViewModel,
                        onBack = { navController.popBackStack() }
                    )
                }

                composable(Screen.StockDailyReport.route) {
                    val stockDailyReportViewModel: StockDailyReportViewModel = viewModel()
                    StockDailyReportScreen(
                        viewModel = stockDailyReportViewModel,
                        onBack = { navController.popBackStack() }
                    )
                }

                composable(Screen.StocktakeRecord.route) {
                    val stocktakeRecordViewModel: StocktakeRecordViewModel = viewModel()
                    StocktakeRecordScreen(
                        viewModel = stocktakeRecordViewModel,
                        onBack = { navController.popBackStack() }
                    )
                }

                composable(Screen.Profile.route) {
                    ProfileScreen(
                        authViewModel = authViewModel,
                        onLogout = {
                            navController.navigate(Screen.Login.route) {
                                popUpTo(0) { inclusive = true }
                            }
                        }
                    )
                }
            }
        }

        // 语音助手悬浮层，仅登录态显示。
        // BUG-2026-09-14-032：语音 VM 惰性创建——未登录时完全不构造（原实现无条件饿汉
        // 创建，未登录也用不上、白占内存与构造开销）。
        // 这里不用 `remember { viewModel() }`：若取出「首次 recall 的实例」在后续重组被
        // 丢弃，会与 ViewModelStore 中的实例脱节。直接在各调用点用 `viewModel<T>()` ——
        // 它就是 ViewModelStore 的按 key 查表，本身是 O(1) 且幂等，无需额外的 remember。
        // 与 Outbound 路由内的 voiceDraftViewModel 类型相同 → 同一 ViewModelStore key
        // → **共享同一实例**，语音建单草稿与出库页读写的是同一份状态（语义未变）。
        if (authState.isLoggedIn) {
            VoiceAssistantOverlay(
                voiceViewModel = viewModel(),
                voiceDraftViewModel = viewModel(),
                authViewModel = authViewModel,
                navController = navController,
                onDraftCreated = { orderNo, lines ->
                    // 语音建单成功 → 预填出库页并跳过去核对（提交/完成仍由人工在出库页执行）
                    voicePrefillLines = lines
                    voiceDraftOrderNo = orderNo.takeIf { it.isNotBlank() }
                    navController.navigate(Screen.Outbound.route) {
                        launchSingleTop = true
                    }
                }
            )
        }
    }
}

/** 底部 Tab 导航栏。 */
@Composable
private fun WmsBottomBar(
    currentRoute: String?,
    tabs: List<BottomTab>,
    onTabSelected: (Screen) -> Unit
) {
    NavigationBar(
        containerColor = com.factory.wms.ui.theme.CardBackground,
        tonalElevation = androidx.compose.ui.unit.Dp(8f)
    ) {
        tabs.forEach { tab ->
            val selected = currentRoute == tab.screen.route
            NavigationBarItem(
                selected = selected,
                onClick = { onTabSelected(tab.screen) },
                icon = {
                    Icon(
                        imageVector = if (selected) tab.selectedIcon else tab.unselectedIcon,
                        contentDescription = tab.label
                    )
                },
                label = { Text(tab.label, fontWeight = if (selected) FontWeight.SemiBold else FontWeight.Normal) },
                colors = NavigationBarItemDefaults.colors(
                    selectedIconColor = Primary,
                    selectedTextColor = Primary,
                    indicatorColor = com.factory.wms.ui.theme.PrimaryContainer
                )
            )
        }
    }
}
