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
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.factory.wms.data.api.AuthEventBus
import com.factory.wms.data.model.MaterialArchiveDto
import com.factory.wms.ui.components.VoiceAssistantOverlay
import com.factory.wms.ui.screens.*
import com.factory.wms.ui.theme.Primary
import com.factory.wms.ui.viewmodel.ai.AiViewModel
import com.factory.wms.ui.viewmodel.archive.MaterialArchiveViewModel
import com.factory.wms.ui.viewmodel.auth.AuthViewModel
import com.factory.wms.ui.viewmodel.home.HomeViewModel
import com.factory.wms.ui.viewmodel.opening.OpeningStockViewModel
import com.factory.wms.ui.viewmodel.report.ReportViewModel
import com.factory.wms.ui.viewmodel.scan.ScanViewModel
import com.factory.wms.ui.viewmodel.voice.VoiceCommandViewModel

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
    val authViewModel: AuthViewModel = viewModel()
    val inboundScanViewModel: ScanViewModel = viewModel(key = "inbound_scan")
    val outboundScanViewModel: ScanViewModel = viewModel(key = "outbound_scan")
    val stockQueryViewModel: ScanViewModel = viewModel(key = "stock_query")
    val stocktakeViewModel: ScanViewModel = viewModel(key = "stocktake")
    val aiViewModel: AiViewModel = viewModel()
    val openingStockViewModel: OpeningStockViewModel = viewModel()
    val voiceViewModel: VoiceCommandViewModel = viewModel()
    val homeViewModel: HomeViewModel = viewModel()
    val materialArchiveViewModel: MaterialArchiveViewModel = viewModel()
    val reportViewModel: ReportViewModel = viewModel()

    // 物料档案详情：选中的物料通过共享状态传递（避免 route 参数序列化 DTO）
    var selectedMaterialArchive by remember { mutableStateOf<MaterialArchiveDto?>(null) }

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
                    HomeScreen(
                        authViewModel = authViewModel,
                        homeViewModel = homeViewModel,
                        onNavigate = { screen ->
                            navController.navigate(screen.route)
                        },
                        onLogout = {
                            navController.navigate(Screen.Login.route) {
                                popUpTo(0) { inclusive = true }
                            }
                        }
                    )
                }

                composable(Screen.Inbound.route) {
                    InboundScreen(
                        viewModel = inboundScanViewModel,
                        onBack = { navController.popBackStack() }
                    )
                }

                composable(Screen.Outbound.route) {
                    OutboundScreen(
                        viewModel = outboundScanViewModel,
                        onBack = { navController.popBackStack() }
                    )
                }

                composable(Screen.StockQuery.route) {
                    StockQueryScreen(
                        viewModel = stockQueryViewModel,
                        onBack = { navController.popBackStack() }
                    )
                }

                composable(Screen.Stocktake.route) {
                    StocktakeScreen(
                        viewModel = stocktakeViewModel,
                        onBack = { navController.popBackStack() },
                        onRecognize = { navController.navigate(Screen.StocktakeRecognize.route) }
                    )
                }

                composable(Screen.OpeningStock.route) {
                    OpeningStockScreen(
                        viewModel = openingStockViewModel,
                        onBack = { navController.popBackStack() }
                    )
                }

                composable(Screen.DocumentOcr.route) {
                    DocumentOcrScreen(
                        viewModel = aiViewModel,
                        onBack = { navController.popBackStack() }
                    )
                }

                composable(Screen.ObjectRecognize.route) {
                    ObjectRecognizeScreen(
                        viewModel = aiViewModel,
                        onBack = { navController.popBackStack() }
                    )
                }

                composable(Screen.StocktakeRecognize.route) {
                    StocktakeRecognizeScreen(
                        aiViewModel = aiViewModel,
                        scanViewModel = stocktakeViewModel,
                        onBack = { navController.popBackStack() }
                    )
                }

                composable(Screen.MaterialArchive.route) {
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
                    val material = selectedMaterialArchive
                    if (material != null) {
                        MaterialArchiveDetailScreen(
                            material = material,
                            viewModel = materialArchiveViewModel,
                            onBack = { navController.popBackStack() }
                        )
                    }
                }

                composable(Screen.DailyReport.route) {
                    DailyReportScreen(
                        viewModel = reportViewModel,
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

        // 语音助手悬浮层，仅登录态显示
        if (authState.isLoggedIn) {
            VoiceAssistantOverlay(
                voiceViewModel = voiceViewModel,
                authViewModel = authViewModel,
                navController = navController
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
