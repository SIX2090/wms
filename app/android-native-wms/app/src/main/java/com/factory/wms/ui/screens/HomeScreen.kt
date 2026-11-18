package com.factory.wms.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowForward
import androidx.compose.material.icons.filled.ExpandLess
import androidx.compose.material.icons.filled.ExpandMore
import androidx.compose.material.icons.outlined.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.luminance
import androidx.compose.ui.graphics.compositeOver
import androidx.compose.ui.platform.LocalDensity
import com.factory.wms.ui.components.WmsAdaptiveRecord
import com.factory.wms.ui.components.WmsQuantityText
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
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
import java.util.Calendar
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

/**
 * 时段问候语（2026-11-18 沉浸式品牌头）。
 *
 * 固定写「早上好」会让夜班人员 20 点看到「早上好」，因此按设备小时分档。
 * 抽成纯函数是为了让守卫与 Robolectric 断言能锁定四条分支，而不依赖跑测试的钟点。
 */
internal fun greetingForHour(hour: Int): String = when (hour) {
    in 5..10 -> "早上好"
    in 11..12 -> "上午好"
    in 13..17 -> "下午好"
    else -> "晚上好"
}

/** 当前设备时段的问候语。 */
internal fun currentGreeting(): String = greetingForHour(Calendar.getInstance().get(Calendar.HOUR_OF_DAY))

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
    Column(modifier.fillMaxSize().verticalScroll(rememberScrollState())) {
        // 普通单行顶栏：无渐变、无问候语。
        Row(
            Modifier.fillMaxWidth().heightIn(min = 56.dp).background(CardBackground)
                .padding(horizontal = 16.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text("仓库工作台", Modifier.weight(1f), style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.SemiBold, color = OnSurface)
            Row(
                Modifier.clickable(onClickLabel = "退出登录") { onLogout() }
                    .heightIn(min = 48.dp).padding(horizontal = 8.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(4.dp)
            ) {
                Text("退出", style = MaterialTheme.typography.titleMedium, color = OnSurface)
                Icon(Icons.Outlined.Logout, contentDescription = "退出登录", tint = OnSurface,
                    modifier = Modifier.size(20.dp))
            }
        }
        // 当前仓库上下文条（参数契约为测试锁定，逐字保留）。
        Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp)) {
            WarehouseSelector(
                currentLabel = dashboard?.warehouse,
                warehouses = warehouses,
                selectedId = selectedWarehouseId,
                onSelect = onSelectWarehouse,
                showDefaultWarehouse = false,
                allowAll = false
            )
        }
        Column(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 12.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)) {
            // 待办 / 告警两张独立 tile，20sp 等宽数字。
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                HomeMetricTile(
                    "待处理单据",
                    "${(dashboard?.pendingInOrders ?: 0) + (dashboard?.pendingOutOrders ?: 0)}",
                    OnSurface, { onNavigate(Screen.OverviewOrders) }, Modifier.weight(1f)
                )
                HomeMetricTile(
                    "库存告警", "${dashboard?.alertCount ?: 0}", Error,
                    { onNavigate(Screen.OverviewAlerts) }, Modifier.weight(1f)
                )
            }
            // 入库 / 出库 58dp 双色主操作块。
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                HomePrimaryTask(cards[0], Modifier.weight(1f).heightIn(min = 58.dp)) { onNavigate(Screen.Inbound) }
                HomePrimaryTask(cards[1], Modifier.weight(1f).heightIn(min = 58.dp)) { onNavigate(Screen.Outbound) }
            }
            // 三段折叠入口，默认只展开「开始作业」。
            HomeCollapsibleSection("开始作业", true) {
                HomeEntryRow(cards[2]) { onNavigate(Screen.StockQuery) }
                HomeEntryRow(cards[3]) { onNavigate(Screen.Stocktake) }
            }
            HomeCollapsibleSection("查询与报表", false) {
                HomeEntryRow(cards[8]) { onNavigate(Screen.DailyReport) }
                HomeEntryRow(cards[9]) { onNavigate(Screen.StockDailyReport) }
                HomeEntryRow(cards[10]) { onNavigate(Screen.InOutDetailReport) }
                HomeEntryRow(cards[11]) { onNavigate(Screen.StockLedgerReport) }
                HomeEntryRow(cards[12]) { onNavigate(Screen.StocktakeRecord) }
            }
            HomeCollapsibleSection("资料与工具", false) {
                HomeEntryRow(cards[4]) { onNavigate(Screen.OpeningStock) }
                HomeEntryRow(cards[5]) { onNavigate(Screen.DocumentOcr) }
                HomeEntryRow(cards[6]) { onNavigate(Screen.ObjectRecognize) }
                HomeEntryRow(cards[7]) { onNavigate(Screen.MaterialArchive) }
                HomeEntryRow(cards[13]) { onNavigate(Screen.AssistantChat) }
            }
            // 今日出入库：仅在有数据时展示，加载/失败走对应占位。
            when {
                dashboard != null -> {
                    Surface(color = CardBackground, shape = MaterialTheme.shapes.medium) {
                        Column(Modifier.fillMaxWidth()) {
                            TodayMovementCell(
                                "今日入库", formatQty(dashboard.todayInQuantity),
                                "${dashboard.todayInOrders} 单", Modifier.fillMaxWidth()
                            ) { onNavigate(Screen.Inbound) }
                            HorizontalDivider(color = DividerSoft)
                            TodayMovementCell(
                                "今日出库", formatQty(dashboard.todayOutQuantity),
                                "${dashboard.todayOutOrders} 单", Modifier.fillMaxWidth()
                            ) { onNavigate(Screen.Outbound) }
                        }
                    }
                }
                isLoading -> DashboardOverviewSkeleton()
                else -> DashboardOverviewError(onRetry = onRetry)
            }
            Spacer(Modifier.height(8.dp))
        }
    }
}

/** 单张概览 tile：标签 + 20sp 等宽大数字，整卡可点。 */
@Composable
private fun HomeMetricTile(
    label: String,
    value: String,
    valueColor: Color,
    onClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    Surface(onClick = onClick, color = CardBackground, shape = MaterialTheme.shapes.medium,
        modifier = modifier.heightIn(min = 48.dp)) {
        Column(Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 10.dp),
            verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(label, style = MaterialTheme.typography.bodyMedium, color = OnSurfaceVariant)
            WmsQuantityText(value, Modifier.fillMaxWidth(), color = valueColor)
        }
    }
}

/** 可折叠分组：rememberSaveable 保存展开态，旋转后保持；标题行 ≥48dp 且箭头可见。 */
@Composable
private fun HomeCollapsibleSection(
    title: String,
    initiallyExpanded: Boolean,
    content: @Composable () -> Unit
) {
    var expanded by rememberSaveable { mutableStateOf(initiallyExpanded) }
    Column(Modifier.fillMaxWidth()) {
        Row(
            Modifier.fillMaxWidth().heightIn(min = 48.dp)
                .clickable(onClickLabel = if (expanded) "收起$title" else "展开$title") { expanded = !expanded }
                .padding(horizontal = 4.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Box(Modifier.width(3.dp).height(16.dp).background(Primary, RoundedCornerShape(2.dp)))
            Text(title, Modifier.weight(1f), style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold, color = OnSurface)
            Icon(if (expanded) Icons.Filled.ExpandLess else Icons.Filled.ExpandMore,
                contentDescription = if (expanded) "收起" else "展开", tint = OnSurfaceVariant,
                modifier = Modifier.size(20.dp))
        }
        if (expanded) {
            Column(Modifier.fillMaxWidth().padding(vertical = 4.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp)) { content() }
        }
    }
}

@Composable
private fun HomeTileGrid(cards: List<FunctionCard>, onNavigate: (Screen) -> Unit, largeFont: Boolean) {
    val columns = 3
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        cards.chunked(columns).forEach { row ->
            Row(Modifier.fillMaxWidth().height(IntrinsicSize.Min), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                row.forEach { card ->
                    val accent = card.gradient.first().readableOn(CardBackground)
                    val chip = accent.copy(alpha = 0.10f).compositeOver(CardBackground)
                    Card(onClick = { onNavigate(card.screen) }, modifier = Modifier.weight(1f).fillMaxHeight().heightIn(min = 96.dp),
                        shape = MaterialTheme.shapes.medium, colors = CardDefaults.cardColors(containerColor = CardBackground)) {
                        Column(Modifier.fillMaxSize().padding(horizontal = 4.dp, vertical = 10.dp), verticalArrangement = Arrangement.Center,
                            horizontalAlignment = Alignment.CenterHorizontally) {
                            Surface(color = chip, shape = RoundedCornerShape(12.dp)) {
                                Box(Modifier.size(42.dp), contentAlignment = Alignment.Center) {
                                    Icon(card.icon, null, tint = accent.readableOn(chip), modifier = Modifier.size(24.dp))
                                }
                            }
                            Spacer(Modifier.height(8.dp))
                            Text(card.title, modifier = Modifier.fillMaxWidth(), textAlign = TextAlign.Center,
                                style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold, softWrap = true)
                        }
                    }
                }
                repeat(columns - row.size) { Spacer(Modifier.weight(1f)) }
            }
        }
    }
}

@Composable
private fun HomeSectionTitle(title: String) {
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Box(Modifier.width(3.dp).height(14.dp).background(Primary, RoundedCornerShape(2.dp)))
        Text(title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
    }
}

@Composable
private fun HomePrimaryTask(card: FunctionCard, modifier: Modifier, onClick: () -> Unit) {
    val outbound = card.screen == Screen.Outbound
    val fill = if (outbound) MaterialTheme.colorScheme.tertiary else MaterialTheme.colorScheme.primary
    val foreground = if (outbound) MaterialTheme.colorScheme.onTertiary else MaterialTheme.colorScheme.onPrimary
    Card(onClick = onClick, modifier = modifier, shape = MaterialTheme.shapes.large,
        colors = CardDefaults.cardColors(containerColor = fill)) {
        Column(Modifier.fillMaxWidth().padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Icon(card.icon, null, tint = foreground, modifier = Modifier.size(24.dp))
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
    Surface(color = CardBackground, shape = MaterialTheme.shapes.large) {
      Column {
        cards.chunked(columns).forEach { row ->
            Row(Modifier.fillMaxWidth().height(IntrinsicSize.Min), horizontalArrangement = Arrangement.spacedBy(0.dp)) {
                row.forEach { card -> FunctionCardItem(card, Modifier.weight(1f).fillMaxHeight()) { onNavigate(card.screen) } }
            }
        }
      }
    }
}

@Composable
private fun HomeEntryRow(card: FunctionCard, showSubtitle: Boolean = true, onClick: () -> Unit) {
    Surface(onClick = onClick, color = CardBackground, shape = MaterialTheme.shapes.large) {
        Row(Modifier.fillMaxWidth().heightIn(min = 56.dp).padding(horizontal = 16.dp, vertical = 12.dp),
            verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            HomeModuleIcon(card)
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
    Card(onClick = onClick, modifier = modifier.heightIn(min = 64.dp), shape = MaterialTheme.shapes.medium,
        colors = CardDefaults.cardColors(containerColor = CardBackground)) {
        Row(Modifier.fillMaxWidth().padding(10.dp), verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            HomeModuleIcon(card)
            Text(card.title, modifier = Modifier.weight(1f), style = MaterialTheme.typography.titleMedium)
        }
    }
}

@Composable
private fun HomeModuleIcon(card: FunctionCard) {
    // 去 8 色渐变：统一用主色 8% alpha 叠卡片底，图标取色走可读性兜底。
    val background = CardBackground
    val accent = Primary
    val iconBackground = accent.copy(alpha = 0.08f).compositeOver(background)
    Surface(color = iconBackground, shape = MaterialTheme.shapes.small) {
        Box(Modifier.size(28.dp), contentAlignment = Alignment.Center) {
            Icon(card.icon, null, tint = accent.readableOn(iconBackground), modifier = Modifier.size(20.dp))
        }
    }
}

@Composable
fun TodayOverviewBar(dashboard: DashboardDto, onNavigate: (Screen) -> Unit) {
    // DividerSoft 是 @Composable @ReadOnlyComposable getter，必须在组合作用域内取值；
    // drawBehind 的 lambda 是 DrawScope 而非 @Composable，不能直接调用它。
    val dividerColor = DividerSoft
    val entries = listOf(
        Triple("今日入库", formatQty(dashboard.todayInQuantity), "${dashboard.todayInOrders} 单") to Screen.Inbound,
        Triple("今日出库", formatQty(dashboard.todayOutQuantity), "${dashboard.todayOutOrders} 单") to Screen.Outbound,
        Triple("待处理", "${dashboard.pendingInOrders + dashboard.pendingOutOrders}", "入${dashboard.pendingInOrders} 出${dashboard.pendingOutOrders}") to Screen.OverviewOrders,
        Triple("库存告警", "${dashboard.alertCount}", "低库存") to Screen.OverviewAlerts
    )
    BoxWithConstraints(Modifier.fillMaxWidth()) {
    // 2026-11-18 修正：每格宽度估算的间距增量由 8dp 收敛为 4dp。
    // API 31 起字体缩放是非线性的：14sp 在 1.3 倍下实测 18.8dp（线性只有 18.2dp）。
    // 原「4 字 + 8dp」把四列门槛抬到 83.2*4 = 332.8dp，超过 360dp 屏的 328dp 可用宽，
    // 于是 1.3 倍字体被误降成两列（NativeShell360AcceptanceTest 要求此时仍四列）。
    // 收敛后门槛 79.2*4 = 316.8dp；四列每格 82dp，减内边距后 80dp，仍宽于标签 75.2dp，不会换行。
    val labelWidth = with(LocalDensity.current) { MaterialTheme.typography.bodyMedium.fontSize.toDp() * 4 + 4.dp }
    val columns = if (LocalDensity.current.fontScale > 1.3f || maxWidth < labelWidth * 4) 2 else 4
    Surface(color = CardBackground, shape = MaterialTheme.shapes.medium, shadowElevation = 1.dp) {
        Column(Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
            entries.chunked(columns).forEach { row ->
                Row(Modifier.fillMaxWidth().height(IntrinsicSize.Min)) {
                    row.forEachIndexed { index, entry ->
                        val (data, screen) = entry
                        // 2026-11-18 修正：分隔线改为绘制而非占位。
                        // 原先用 fillMaxHeight 的 1dp Box 参与布局，与 Row(height(IntrinsicSize.Min))
                        // 组合会扰乱行高的 intrinsic 测量，四格顶部不再对齐（曾使
                        // NativeShell360AcceptanceTest「四列同行」断言失败）。绘制不占宽度、不参与测量。
                        Column(Modifier.weight(1f).fillMaxHeight()
                            .drawBehind {
                                if (index < row.lastIndex) {
                                    val x = size.width - 0.5.dp.toPx()
                                    drawLine(dividerColor, Offset(x, 12.dp.toPx()),
                                        Offset(x, size.height - 12.dp.toPx()), 1.dp.toPx())
                                }
                            }
                            .clickable { onNavigate(screen) }
                            .heightIn(min = 48.dp).padding(horizontal = 1.dp, vertical = 10.dp),
                            horizontalAlignment = Alignment.CenterHorizontally,
                            verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            Text(data.second, modifier = Modifier.fillMaxWidth(), textAlign = TextAlign.Center,
                                style = MaterialTheme.typography.titleLarge.copy(fontFeatureSettings = "tnum"),
                                fontWeight = FontWeight.Bold, softWrap = true)
                            Text(data.first, modifier = Modifier.fillMaxWidth(), textAlign = TextAlign.Center,
                                style = MaterialTheme.typography.bodyMedium, color = OnSurfaceVariant, softWrap = true)
                            Text(data.third, modifier = Modifier.fillMaxWidth(), textAlign = TextAlign.Center,
                                style = MaterialTheme.typography.bodyMedium, color = OnSurfaceVariant, softWrap = true)
                        }
                    }
                }
            }
        }
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
