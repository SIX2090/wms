package com.factory.wms.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowForward
import androidx.compose.material.icons.outlined.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.luminance
import androidx.compose.ui.platform.LocalDensity
import com.factory.wms.ui.components.WmsAdaptiveRecord
import com.factory.wms.ui.components.WmsQuantityText
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.factory.wms.data.model.DashboardDto
import com.factory.wms.data.model.WarehouseDto
import com.factory.wms.ui.components.StatusBarIconEffect
import com.factory.wms.ui.components.WarehouseSelector
import com.factory.wms.ui.components.WmsShimmerBox
import com.factory.wms.ui.navigation.Screen
import com.factory.wms.ui.theme.*
import com.factory.wms.ui.util.formatQty
import com.factory.wms.ui.util.quantityDisplayText
import com.factory.wms.ui.viewmodel.auth.AuthViewModel
import com.factory.wms.ui.viewmodel.home.HomeViewModel
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

data class FunctionCard(
    val title: String,
    val subtitle: String,
    val icon: ImageVector,
    val gradient: List<Color>,
    val screen: Screen
)

internal fun homeFunctionCards(): List<FunctionCard> =
listOf(
            FunctionCard(
                title = "入库",
                subtitle = "手工/扫码 · 多物料入库",
                icon = Icons.Outlined.ArrowDownward,
                gradient = listOf(CardBlue, CardBlueDark),
                screen = Screen.Inbound
            ),
            FunctionCard(
                title = "出库",
                subtitle = "手工/扫码 · 多物料出库",
                icon = Icons.Outlined.ArrowUpward,
                gradient = listOf(CardGreen, CardGreenDark),
                screen = Screen.Outbound
            ),
            FunctionCard(
                title = "查库存",
                subtitle = "扫码查询 · 实时库存",
                icon = Icons.Outlined.Search,
                gradient = listOf(CardOrange, CardOrangeDark),
                screen = Screen.StockQuery
            ),
            FunctionCard(
                // BUG-2026-09-18-007：与 Screen.Stocktake 标题、底部 Tab 统一为「盘点」。
                // 入口页标题带"扫码"而目标页已改为"盘点"会出现两级标题跳变，
                // 且本页副标题已说明"扫码/识物"，信息不丢失。
                title = "盘点",
                subtitle = "扫码/识物 · 快速盘点",
                icon = Icons.Outlined.Inventory2,
                gradient = listOf(CardPurple, CardPurpleDark),
                screen = Screen.Stocktake
            ),
            FunctionCard(
                title = "期初库存",
                subtitle = "选日期仓库 · 扫码建账",
                icon = Icons.Outlined.AccountBalanceWallet,
                gradient = listOf(CardCyan, CardCyanDark),
                screen = Screen.OpeningStock
            ),
            FunctionCard(
                title = "识别单据",
                subtitle = "拍照识别 · 自动录入",
                icon = Icons.Outlined.Description,
                gradient = listOf(CardTeal, CardTealDark),
                screen = Screen.DocumentOcr
            ),
            FunctionCard(
                title = "识物",
                subtitle = "拍照识别 · 智能匹配",
                icon = Icons.Outlined.CameraAlt,
                gradient = listOf(CardPink, CardPinkDark),
                screen = Screen.ObjectRecognize
            ),
            FunctionCard(
                title = "物料档案",
                subtitle = "搜索 · 拍照建档",
                icon = Icons.Outlined.Badge,
                gradient = listOf(CardAmber, CardAmberDark),
                screen = Screen.MaterialArchive
            ),
            FunctionCard(
                title = "每日报表",
                subtitle = "采购入库 · 领料单明细",
                icon = Icons.Outlined.Assessment,
                gradient = listOf(CardPinkLight, CardPinkDark),
                screen = Screen.DailyReport
            ),
            FunctionCard(
                title = "库存日报",
                subtitle = "按仓每日结存",
                icon = Icons.Outlined.Inventory2,
                gradient = listOf(CardCyanLight, CardCyanDark),
                screen = Screen.StockDailyReport
            ),
            FunctionCard(
                title = "出入库明细",
                subtitle = "按仓查流水",
                icon = Icons.Outlined.SwapVert,
                gradient = listOf(CardGreen, CardGreenDark),
                screen = Screen.InOutDetailReport
            ),
            FunctionCard(
                title = "库存台账",
                subtitle = "期初出入结存",
                icon = Icons.Outlined.MenuBook,
                gradient = listOf(CardTealLight, CardTealDark),
                screen = Screen.StockLedgerReport
            ),
            FunctionCard(
                title = "盘点记录",
                subtitle = "回查差异采纳",
                icon = Icons.Outlined.History,
                gradient = listOf(CardPurple, CardPurpleDark),
                screen = Screen.StocktakeRecord
            ),
            // AI-ASSISTANT-MOBILE-001：AI 助手入口（与 PC 同链路 28 意图）
            FunctionCard(
                title = "AI 助手",
                subtitle = "查库存 · 查单号 · 分析问答",
                icon = Icons.Outlined.SmartToy,
                gradient = listOf(CardBlueLight, CardBlueDark),
                screen = Screen.AssistantChat
            )
        )

@Composable
fun HomeScreen(
    authViewModel: AuthViewModel,
    homeViewModel: HomeViewModel,
    onNavigate: (Screen) -> Unit,
    onLogout: () -> Unit
) {
    val uiState by authViewModel.uiState.collectAsState()
    val homeUiState by homeViewModel.uiState.collectAsState()
    var showLogoutDialog by remember { mutableStateOf(false) }
    val snackbarHostState = remember { SnackbarHostState() }
    StatusBarIconEffect(darkIcons = MaterialTheme.colorScheme.surface.luminance() > 0.5f)
    LaunchedEffect(Unit) { homeViewModel.loadDashboard() }
    LaunchedEffect(uiState.error) {
        uiState.error?.let {
            snackbarHostState.showSnackbar(it, duration = SnackbarDuration.Short)
            authViewModel.clearError()
        }
    }
    Scaffold(snackbarHost = { SnackbarHost(snackbarHostState) }, containerColor = Background) { padding ->
        HomeWorkbench(
            dashboard = homeUiState.dashboard,
            isLoading = homeUiState.isLoading,
            warehouses = homeUiState.warehouses,
            selectedWarehouseId = homeUiState.selectedWarehouseId,
            onSelectWarehouse = homeViewModel::selectWarehouse,
            onRetry = { homeViewModel.loadDashboard() },
            onNavigate = onNavigate,
            onLogout = { showLogoutDialog = true },
            modifier = Modifier.padding(padding)
        )
    }
    if (showLogoutDialog) {
        AlertDialog(
            onDismissRequest = { showLogoutDialog = false },
            title = { Text("退出登录") },
            text = { Text("确定要退出当前账号吗？") },
            confirmButton = { TextButton(onClick = {
                showLogoutDialog = false
                authViewModel.logout()
                onLogout()
            }) { Text("确定退出", color = MaterialTheme.colorScheme.error) } },
            dismissButton = { TextButton(onClick = { showLogoutDialog = false }) { Text("取消") } }
        )
    }
}

/** 与真实首页共用的无副作用视图；数据、仓库和导航仍由原 ViewModel 提供。 */
@Composable
internal fun HomeWorkbench(
    dashboard: DashboardDto?,
    isLoading: Boolean,
    warehouses: List<WarehouseDto>,
    selectedWarehouseId: String?,
    onSelectWarehouse: (String?) -> Unit,
    onRetry: () -> Unit,
    onNavigate: (Screen) -> Unit,
    onLogout: () -> Unit,
    modifier: Modifier = Modifier
) {
    val cards = remember { homeFunctionCards() }
    val today = remember { SimpleDateFormat("MM月dd日 EEEE", Locale.CHINESE).format(Date()) }
    Column(
        modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(WmsDimens.PagePaddingHorizontal),
        verticalArrangement = Arrangement.spacedBy(WmsDimens.SpaceMd)
    ) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text("仓库工作台", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
                Text(today, style = MaterialTheme.typography.bodyMedium, color = OnSurfaceVariant)
            }
            IconButton(onClick = onLogout) {
                Icon(Icons.Outlined.Logout, contentDescription = "退出登录", tint = OnSurfaceVariant)
            }
        }
        Surface(color = CardBackground, shape = MaterialTheme.shapes.medium) {
            val selector: @Composable (Modifier) -> Unit = { selectorModifier ->
                WarehouseSelector(
                    currentLabel = dashboard?.warehouse, warehouses = warehouses,
                    selectedId = selectedWarehouseId, onSelect = onSelectWarehouse,
                    showDefaultWarehouse = false, allowAll = false,
                    contentColor = MaterialTheme.colorScheme.primary, modifier = selectorModifier
                )
            }
            if (LocalDensity.current.fontScale <= 1.3f) {
                Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 4.dp),
                    verticalAlignment = Alignment.CenterVertically) {
                    Text("当前仓库", style = MaterialTheme.typography.bodyMedium, color = OnSurfaceVariant)
                    selector(Modifier.weight(1f))
                }
            } else {
                Column(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 4.dp)) {
                    Text("当前仓库", style = MaterialTheme.typography.bodyMedium, color = OnSurfaceVariant)
                    selector(Modifier.fillMaxWidth())
                }
            }
        }
        when {
            dashboard != null -> TodayOverviewBar(dashboard, onNavigate)
            isLoading -> DashboardOverviewSkeleton()
            else -> DashboardOverviewError(onRetry = onRetry)
        }
        HomeSectionTitle("开始作业")
        Row(Modifier.fillMaxWidth().height(IntrinsicSize.Min), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            HomePrimaryTask(cards[0], Modifier.weight(1f).fillMaxHeight()) { onNavigate(cards[0].screen) }
            HomePrimaryTask(cards[1], Modifier.weight(1f).fillMaxHeight()) { onNavigate(cards[1].screen) }
        }
        HomeEntryRow(cards[2], showSubtitle = false) { onNavigate(cards[2].screen) }
        Row(Modifier.fillMaxWidth().height(IntrinsicSize.Min), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            listOf(cards[3], cards[4]).forEach { card ->
                FunctionCardItem(card, Modifier.weight(1f).fillMaxHeight(), onClick = { onNavigate(card.screen) })
            }
        }
        HomeSectionTitle("查询与报表")
        HomeEntryGrid(cards.filter { it.screen in listOf(Screen.DailyReport, Screen.StockDailyReport,
            Screen.InOutDetailReport, Screen.StockLedgerReport, Screen.StocktakeRecord) }, onNavigate)
        HomeSectionTitle("资料与工具")
        HomeEntryGrid(listOf(cards[7], cards[5], cards[6], cards[13]), onNavigate)
        dashboard?.let {
            HomeSectionTitle("今日出入库")
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                TodayMovementCell("今日入库", formatQty(it.todayInQuantity), "${it.todayInOrders} 单", Modifier.weight(1f)) { onNavigate(Screen.Inbound) }
                TodayMovementCell("今日出库", formatQty(it.todayOutQuantity), "${it.todayOutOrders} 单", Modifier.weight(1f)) { onNavigate(Screen.Outbound) }
            }
        }
        Spacer(Modifier.height(8.dp))
    }
}

@Composable
private fun HomeSectionTitle(title: String) {
    Text(title, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
}

@Composable
private fun HomePrimaryTask(card: FunctionCard, modifier: Modifier, onClick: () -> Unit) {
    val outbound = card.screen == Screen.Outbound
    val fill = if (outbound) MaterialTheme.colorScheme.tertiaryContainer else MaterialTheme.colorScheme.primaryContainer
    val foreground = if (outbound) MaterialTheme.colorScheme.onTertiaryContainer else MaterialTheme.colorScheme.onPrimaryContainer
    Card(onClick = onClick, modifier = modifier, shape = MaterialTheme.shapes.medium,
        colors = CardDefaults.cardColors(containerColor = fill)) {
        Column(Modifier.fillMaxWidth().padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Icon(card.icon, null, tint = foreground, modifier = Modifier.size(22.dp))
                Text(card.title, modifier = Modifier.weight(1f), style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.SemiBold, color = foreground)
            }
            // Keep the two-character method together when the system enlarges text.
            Text(if (card.screen == Screen.Inbound) "扫码 / 手\u2060工" else "核对数量",
                modifier = Modifier.fillMaxWidth(), style = MaterialTheme.typography.bodyMedium, color = foreground)
        }
    }
}

@Composable
private fun HomeEntryGrid(cards: List<FunctionCard>, onNavigate: (Screen) -> Unit) {
    val columns = if (LocalDensity.current.fontScale > 1.3f) 1 else 2
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        cards.chunked(columns).forEach { row ->
            Row(Modifier.fillMaxWidth().height(IntrinsicSize.Min), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                row.forEach { card -> FunctionCardItem(card, Modifier.weight(1f).fillMaxHeight()) { onNavigate(card.screen) } }
                repeat(columns - row.size) { Spacer(Modifier.weight(1f)) }
            }
        }
    }
}

@Composable
private fun HomeEntryRow(card: FunctionCard, showSubtitle: Boolean = true, onClick: () -> Unit) {
    Surface(onClick = onClick, color = CardBackground, shape = MaterialTheme.shapes.medium) {
        Row(Modifier.fillMaxWidth().heightIn(min = 56.dp).padding(horizontal = 16.dp, vertical = 12.dp),
            verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Icon(card.icon, null, tint = card.gradient.first().readableOn(CardBackground), modifier = Modifier.size(22.dp))
            Column(Modifier.weight(1f)) {
                Text(card.title, modifier = Modifier.fillMaxWidth(), style = MaterialTheme.typography.titleMedium)
                if (showSubtitle) Text(card.subtitle, style = MaterialTheme.typography.bodyMedium, color = OnSurfaceVariant)
            }
            Icon(Icons.AutoMirrored.Filled.ArrowForward, null, tint = OnSurfaceVariant, modifier = Modifier.size(18.dp))
        }
    }
}

@Composable
fun FunctionCardItem(card: FunctionCard, modifier: Modifier = Modifier, index: Int = 0, onClick: () -> Unit) {
    Card(onClick = onClick, modifier = modifier.heightIn(min = 80.dp), shape = MaterialTheme.shapes.medium,
        colors = CardDefaults.cardColors(containerColor = CardBackground)) {
        Column(Modifier.fillMaxWidth().padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Icon(card.icon, null, tint = card.gradient.first().readableOn(CardBackground), modifier = Modifier.size(24.dp))
            Text(card.title, modifier = Modifier.fillMaxWidth(), style = MaterialTheme.typography.titleMedium)
        }
    }
}

@Composable
fun TodayOverviewBar(dashboard: DashboardDto, onNavigate: (Screen) -> Unit) {
    Surface(color = CardBackground, shape = MaterialTheme.shapes.medium) {
        Row(Modifier.fillMaxWidth().padding(4.dp), verticalAlignment = Alignment.Top) {
            TodayMovementCell("待处理", "${dashboard.pendingInOrders + dashboard.pendingOutOrders}",
                "入${dashboard.pendingInOrders} · 出${dashboard.pendingOutOrders}", Modifier.weight(1f)) { onNavigate(Screen.OverviewOrders) }
            TodayMovementCell("库存告警", "${dashboard.alertCount}", "低库存", Modifier.weight(1f)) { onNavigate(Screen.OverviewAlerts) }
        }
    }
}

@Composable
private fun TodayMovementCell(label: String, value: String, sub: String, modifier: Modifier, onClick: () -> Unit) {
    Box(modifier.clickable(onClick = onClick).heightIn(min = WmsDimens.TouchTargetMin).padding(12.dp)) {
        WmsAdaptiveRecord(value,
            identity = {
                Column {
                    Text(label, modifier = Modifier.fillMaxWidth(), style = MaterialTheme.typography.bodyMedium, color = OnSurfaceVariant)
                    Text(sub, modifier = Modifier.fillMaxWidth(), style = MaterialTheme.typography.bodyMedium, color = OnSurfaceVariant)
                }
            },
            quantity = { WmsQuantityText(value, Modifier.fillMaxWidth()) }
        )
    }
}

@Composable
private fun DashboardOverviewError(onRetry: () -> Unit) {
    OutlinedButton(onClick = onRetry, modifier = Modifier.fillMaxWidth().heightIn(min = 56.dp)) {
        Icon(Icons.Outlined.Refresh, null)
        Spacer(Modifier.width(8.dp))
        Text("概览加载失败，点击重试")
    }
}

@Composable
private fun DashboardOverviewSkeleton() {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        repeat(2) { WmsShimmerBox(Modifier.weight(1f).height(80.dp)) }
    }
}
