package com.factory.wms.ui.screens

import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.*
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material.icons.outlined.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.factory.wms.data.model.DashboardDto
import com.factory.wms.data.model.WarehouseDto
import com.factory.wms.ui.components.StatusBarIconEffect
import com.factory.wms.ui.components.WarehouseSelector
import com.factory.wms.ui.components.WmsShimmerBox
import com.factory.wms.ui.navigation.Screen
import com.factory.wms.ui.util.formatQty
import com.factory.wms.ui.theme.*
import com.factory.wms.ui.viewmodel.auth.AuthViewModel
import com.factory.wms.ui.viewmodel.home.HomeViewModel
import kotlinx.coroutines.delay
import java.text.SimpleDateFormat
import java.util.*

data class FunctionCard(
    val title: String,
    val subtitle: String,
    val icon: ImageVector,
    val gradient: List<Color>,
    val screen: Screen
)

@OptIn(ExperimentalMaterial3Api::class)
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

    // 首页顶部是深蓝 Hero → 浅色状态栏图标（修复深色图标压在深蓝上不可读）
    StatusBarIconEffect(darkIcons = false)

    // BUG-2026-09-10-010：首页概览的仓库切换需要仓库列表，进入首页时加载一次。
    // BUG-2026-09-26-003：底部 Tab 用 saveState/restoreState 恢复首页时，VM 存活、
    // loadWarehouses 早退，dashboard 停留旧值——录完单回首页"今日入库"不更新，
    // 只能杀进程重开。effect 在恢复时重启，此处补 loadDashboard() 让数字跟上
    // （GET 幂等，与 loadWarehouses 内部触发的刷新并发安全）。
    LaunchedEffect(Unit) {
        homeViewModel.loadWarehouses()
        homeViewModel.loadDashboard()
    }

    val cards = remember {
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
            )
        )
    }

    LaunchedEffect(uiState.error) {
        uiState.error?.let {
            snackbarHostState.showSnackbar(it, duration = SnackbarDuration.Short)
            authViewModel.clearError()
        }
    }

    val dateFormat = remember { SimpleDateFormat("MM月dd日 EEEE", Locale.CHINESE) }
    val todayDate = remember { dateFormat.format(Date()) }

    Scaffold(
        snackbarHost = { SnackbarHost(snackbarHostState) },
        containerColor = Background
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .verticalScroll(rememberScrollState())
        ) {
            // ── Hero Section ──
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(
                        brush = Brush.verticalGradient(
                            colors = listOf(
                                Primary,
                                PrimaryDark
                            )
                        )
                    )
                    .padding(top = 16.dp, bottom = 48.dp)
            ) {
                // Decorative circles
                Box(
                    modifier = Modifier
                        .size(180.dp)
                        .offset(x = (-40).dp, y = (-60).dp)
                        .clip(CircleShape)
                        .background(Color.White.copy(alpha = 0.04f))
                )
                Box(
                    modifier = Modifier
                        .size(120.dp)
                        .align(Alignment.TopEnd)
                        .offset(x = 20.dp, y = (-30).dp)
                        .clip(CircleShape)
                        .background(Color.White.copy(alpha = 0.06f))
                )

                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 20.dp)
                ) {
                    // Top bar row
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Column {
                            Text(
                                "WMS 仓库管理",
                                color = Color.White,
                                fontSize = 22.sp,
                                fontWeight = FontWeight.Bold
                            )
                            Spacer(modifier = Modifier.height(2.dp))
                            Text(
                                todayDate,
                                color = Color.White.copy(alpha = 0.7f),
                                fontSize = 13.sp
                            )
                        }
                        IconButton(onClick = { showLogoutDialog = true }) {
                            Box(
                                modifier = Modifier
                                    .size(40.dp)
                                    .clip(CircleShape)
                                    .background(Color.White.copy(alpha = 0.15f)),
                                contentAlignment = Alignment.Center
                            ) {
                                Icon(
                                    Icons.Outlined.Logout,
                                    contentDescription = "退出",
                                    tint = Color.White.copy(alpha = 0.9f),
                                    modifier = Modifier.size(20.dp)
                                )
                            }
                        }
                    }

                    Spacer(modifier = Modifier.height(20.dp))

                    // Greeting + avatar
                    Row(
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        // Avatar
                        Box(
                            modifier = Modifier
                                .size(48.dp)
                                .clip(CircleShape)
                                .background(Color.White.copy(alpha = 0.2f)),
                            contentAlignment = Alignment.Center
                        ) {
                            Text(
                                uiState.username.take(1).uppercase(),
                                color = Color.White,
                                fontWeight = FontWeight.Bold,
                                fontSize = 20.sp
                            )
                        }
                        Spacer(modifier = Modifier.width(12.dp))
                        Column {
                            Text(
                                "你好，${uiState.username}",
                                color = Color.White,
                                fontWeight = FontWeight.SemiBold,
                                fontSize = 18.sp
                            )
                            Text(
                                "角色: ${uiState.role.ifBlank { "操作员" }}",
                                color = Color.White.copy(alpha = 0.7f),
                                fontSize = 13.sp
                            )
                        }
                    }
                }
            }

            // ── 今日概览条 ──
            // BUG-2026-09-10-010：多仓用户此前只能看到默认仓的今日数据，
            // 顶部提供仓库切换（默认仓 / 各仓 / 全部仓库汇总）。
            val dashboardData = homeUiState.dashboard
            if (dashboardData != null) {
                // 标题 + 概览条整体半悬浮，上探压住 Hero 下边缘（Hero 底部已留 48dp）
                Column(modifier = Modifier.offset(y = (-28).dp)) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(bottom = 6.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            "今日概览",
                            fontWeight = FontWeight.SemiBold,
                            fontSize = 15.sp,
                            // 半悬浮后标题压在 Hero 深蓝背景上，需白色
                            color = Color.White,
                            modifier = Modifier.padding(start = 20.dp)
                        )
                        Spacer(modifier = Modifier.weight(1f))
                        WarehouseSelector(
                            currentLabel = dashboardData.warehouse,
                            warehouses = homeUiState.warehouses,
                            selectedId = homeUiState.selectedWarehouseId,
                            onSelect = { homeViewModel.selectWarehouse(it) },
                            showDefaultWarehouse = false,
                            allowAll = false
                        )
                    }
                    TodayOverviewBar(
                        dashboard = dashboardData,
                        onNavigate = onNavigate
                    )
                }
            } else if (homeUiState.isLoading) {
                // AI-APP-UI-002：数据未返回时渲染同形骨架。
                // 与真实布局同形半悬浮（标题占位在 Hero 上用白色 shimmer）。
                Column(modifier = Modifier.offset(y = (-28).dp)) {
                    DashboardOverviewSkeleton()
                }
            } else {
                // BUG-2026-09-26-004：加载失败（dashboard=null 且不在加载中）此前也
                // 落到骨架分支——shimmer 永远转下去，用户分不清"在加载"还是"坏了"，
                // 且没有任何重试入口。渲染同形失败条：点击重试 + 切仓入口常驻
                // （换仓本身会触发 loadDashboard，也是一条重试路径）。
                Column(modifier = Modifier.offset(y = (-28).dp)) {
                    DashboardOverviewError(
                        warehouses = homeUiState.warehouses,
                        selectedId = homeUiState.selectedWarehouseId,
                        onSelectWarehouse = { homeViewModel.selectWarehouse(it) },
                        onRetry = { homeViewModel.loadDashboard() }
                    )
                }
            }

            // ── Card Grid ──
            Spacer(modifier = Modifier.height(20.dp))

            val screenWidth = LocalConfiguration.current.screenWidthDp.dp
            val gridSpacing = 10.dp
            // 3 列：左右各 20dp 外边距 + 2 个间距
            val cardWidth = (screenWidth - 40.dp - gridSpacing * 2) / 3
            val rowCount = (cards.size + 2) / 3

            for (row in 0 until rowCount) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 20.dp),
                    horizontalArrangement = Arrangement.spacedBy(gridSpacing)
                ) {
                    for (col in 0..2) {
                        val index = row * 3 + col
                        if (index < cards.size) {
                            val card = cards[index]
                            FunctionCardItem(
                                card = card,
                                index = index,
                                modifier = Modifier.width(cardWidth),
                                onClick = { onNavigate(card.screen) }
                            )
                        } else {
                            // 13 张卡 3 列末行只 1 张：不补占位会被 spacedBy 拉变形
                            Spacer(modifier = Modifier.width(cardWidth))
                        }
                    }
                }
                Spacer(modifier = Modifier.height(10.dp))
            }

            // ── Bottom Info ──
            Spacer(modifier = Modifier.height(8.dp))

            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 20.dp),
                shape = RoundedCornerShape(16.dp),
                colors = CardDefaults.cardColors(
                    containerColor = CardBackground
                ),
                elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 14.dp, vertical = 12.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Box(
                        modifier = Modifier
                            .size(30.dp)
                            .clip(RoundedCornerShape(9.dp))
                            .background(Primary.copy(alpha = 0.12f)),
                        contentAlignment = Alignment.Center
                    ) {
                        Icon(
                            Icons.Outlined.Dns,
                            contentDescription = null,
                            tint = Primary,
                            modifier = Modifier.size(16.dp)
                        )
                    }
                    Spacer(modifier = Modifier.width(10.dp))
                    Column {
                        Text(
                            "当前服务器",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                        Text(
                            uiState.baseUrl,
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurface,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(24.dp))
        }
    }

    // Logout dialog
    if (showLogoutDialog) {
        AlertDialog(
            onDismissRequest = { showLogoutDialog = false },
            shape = RoundedCornerShape(20.dp),
            title = {
                Text("退出登录", fontWeight = FontWeight.SemiBold)
            },
            text = { Text("确定要退出当前账号吗？") },
            confirmButton = {
                TextButton(onClick = {
                    showLogoutDialog = false
                    authViewModel.logout()
                    onLogout()
                }) {
                    Text("确定退出", color = MaterialTheme.colorScheme.error)
                }
            },
            dismissButton = {
                TextButton(onClick = { showLogoutDialog = false }) {
                    Text("取消")
                }
            }
        )
    }
}

@Composable
fun FunctionCardItem(
    card: FunctionCard,
    modifier: Modifier = Modifier,
    index: Int = 0,
    onClick: () -> Unit
) {
    var pressed by remember { mutableStateOf(false) }
    val haptics = LocalHapticFeedback.current
    val scale by animateFloatAsState(
        targetValue = if (pressed) 0.96f else 1f,
        animationSpec = spring(dampingRatio = Spring.DampingRatioMediumBouncy),
        label = "card_scale"
    )

    // AI-APP-UI-002：入场交错动画——卡片按序号依次淡入上浮，
    // 首页从"一屏元素同时砸下来"变为有节奏的进入，感知更精致。
    // 延迟封顶 400ms：卡片再多也不会让最后一排等太久。
    val entrance = remember { androidx.compose.animation.core.Animatable(0f) }
    LaunchedEffect(Unit) {
        delay((index * 35L).coerceAtMost(400L))
        entrance.animateTo(1f, tween(320, easing = FastOutSlowInEasing))
    }

    Card(
        modifier = modifier
            .height(104.dp)
            .graphicsLayer {
                alpha = entrance.value
                translationY = (1f - entrance.value) * 36f
            }
            .scale(scale)
            .shadow(
                elevation = if (pressed) 3.dp else 5.dp,
                shape = RoundedCornerShape(16.dp),
                ambientColor = card.gradient.first().copy(alpha = 0.15f),
                spotColor = card.gradient.first().copy(alpha = 0.2f)
            )
            .clip(RoundedCornerShape(16.dp))
            .clickable(
                interactionSource = remember { MutableInteractionSource() },
                indication = null,
                onClick = {
                    haptics.performHapticFeedback(HapticFeedbackType.LongPress)
                    onClick()
                }
            ),
        shape = RoundedCornerShape(16.dp),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
        colors = CardDefaults.cardColors(containerColor = Color.Transparent)
    ) {
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(
                    brush = Brush.linearGradient(
                        colors = card.gradient,
                        start = Offset(0f, 0f),
                        end = Offset(600f, 600f)
                    )
                )
        ) {
            // Decorative background elements（随卡片缩小，避免溢出）
            Box(
                modifier = Modifier
                    .size(70.dp)
                    .offset(x = 60.dp, y = (-28).dp)
                    .clip(CircleShape)
                    .background(Color.White.copy(alpha = 0.08f))
            )
            Box(
                modifier = Modifier
                    .size(40.dp)
                    .offset(x = 55.dp, y = 45.dp)
                    .clip(CircleShape)
                    .background(Color.White.copy(alpha = 0.05f))
            )
            Box(
                modifier = Modifier
                    .size(22.dp)
                    .offset(x = (-8).dp, y = 78.dp)
                    .clip(CircleShape)
                    .background(Color.White.copy(alpha = 0.06f))
            )

            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(10.dp),
                verticalArrangement = Arrangement.SpaceBetween
            ) {
                // Icon container
                Box(
                    modifier = Modifier
                        .size(36.dp)
                        .clip(RoundedCornerShape(12.dp))
                        .background(Color.White.copy(alpha = 0.22f)),
                    contentAlignment = Alignment.Center
                ) {
                    Icon(
                        imageVector = card.icon,
                        contentDescription = null,
                        tint = Color.White,
                        modifier = Modifier.size(20.dp)
                    )
                }

                // Title & subtitle（104dp 高度内单行副标题，Ellipsis 兜底截断）
                Column {
                    Text(
                        text = card.title,
                        color = Color.White,
                        fontWeight = FontWeight.Bold,
                        fontSize = 15.sp,
                        letterSpacing = 0.5.sp,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                    Spacer(modifier = Modifier.height(2.dp))
                    Text(
                        text = card.subtitle,
                        color = Color.White.copy(alpha = 0.8f),
                        fontSize = 11.sp,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                }
            }
        }
    }
}

/** 首页"今日概览"条：今日入库/出库（笔数与数量）+ 待处理单据 + 库存告警。 */
@Composable
fun TodayOverviewBar(
    dashboard: DashboardDto,
    onNavigate: (Screen) -> Unit
) {
    val items = listOf(
        OverviewItem(
            label = "今日入库",
            value = formatQty(dashboard.todayInQuantity),
            sub = "${dashboard.todayInOrders} 单",
            icon = Icons.Outlined.ArrowDownward,
            color = CardBlue,
            screen = Screen.Inbound
        ),
        OverviewItem(
            label = "今日出库",
            value = formatQty(dashboard.todayOutQuantity),
            sub = "${dashboard.todayOutOrders} 单",
            icon = Icons.Outlined.ArrowUpward,
            color = CardGreen,
            screen = Screen.Outbound
        ),
        OverviewItem(
            label = "待处理单据",
            value = "${dashboard.pendingInOrders + dashboard.pendingOutOrders}",
            sub = "入${dashboard.pendingInOrders}·出${dashboard.pendingOutOrders}",
            icon = Icons.Outlined.PendingActions,
            color = CardOrange,
            // AI-MOB-DRILLDOWN-01：此前为 null，点了完全没反应。
            // 现在下钻到明细列表（可再切 入库单 / 出库单）。
            // 即使当前为 0 单也允许进入——用户需要能确认"确实是 0"，
            // 而不是怀疑点击没生效。
            screen = Screen.OverviewOrders
        ),
        OverviewItem(
            label = "库存告警",
            value = "${dashboard.alertCount}",
            sub = "低库存",
            icon = Icons.Outlined.WarningAmber,
            // BUG-2026-09-26-003：0 告警时用中性色。红色=有问题的语义不能被
            // 常驻的红色 0 稀释——天天看红 0，真告警时反而麻木。
            color = if (dashboard.alertCount > 0) Error else OnSurfaceSecondary,
            // AI-MOB-DRILLDOWN-01：此前跳查库存的空白搜索框，
            // 用户看到数字却不知道具体是哪些物料。改跳告警明细。
            screen = Screen.OverviewAlerts
        )
    )

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 20.dp),
        shape = RoundedCornerShape(18.dp),
        colors = CardDefaults.cardColors(containerColor = CardBackground),
        // 半悬浮由调用点 Column 统一 offset（标题+卡片一起上移），此处只加深投影
        elevation = CardDefaults.cardElevation(defaultElevation = 4.dp)
    ) {
        // AI-APP-UI-002：卡片内不再重复渲染「今日概览」标题——
        // 外层已有同名标题 + 仓库切换器，卡片内再来一遍是纯视觉冗余。
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 10.dp, vertical = 14.dp),
            horizontalArrangement = Arrangement.SpaceEvenly,
            // 四格 sub 行数不一致时（如"低库存"vs"入0·出0"）图标和数值仍顶对齐
            verticalAlignment = Alignment.Top
        ) {
            items.forEach { item ->
                OverviewItemCell(
                    item = item,
                    modifier = Modifier.weight(1f),
                    onClicked = {
                        item.screen?.let(onNavigate)
                    }
                )
            }
        }
    }
}

/**
 * 「今日概览」失败条（BUG-2026-09-26-004）：与真实卡片同形——标题行保留
 * 仓库切换器（换仓即重试），卡片正文为"加载失败，点击重试"。
 * 仅当 dashboard=null 且不在加载中时渲染（加载中走骨架，成功走真实条）。
 */
@Composable
private fun DashboardOverviewError(
    warehouses: List<WarehouseDto>,
    selectedId: String?,
    onSelectWarehouse: (String?) -> Unit,
    onRetry: () -> Unit
) {
    Column {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(bottom = 6.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                "今日概览",
                fontWeight = FontWeight.SemiBold,
                fontSize = 15.sp,
                // 半悬浮后标题压在 Hero 深蓝背景上，需白色（与真实条一致）
                color = Color.White,
                modifier = Modifier.padding(start = 20.dp)
            )
            Spacer(modifier = Modifier.weight(1f))
            WarehouseSelector(
                currentLabel = null,
                warehouses = warehouses,
                selectedId = selectedId,
                onSelect = onSelectWarehouse,
                showDefaultWarehouse = false,
                allowAll = false
            )
        }
        Card(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 20.dp)
                .clickable(onClick = onRetry),
            shape = RoundedCornerShape(18.dp),
            colors = CardDefaults.cardColors(containerColor = CardBackground),
            elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(vertical = 20.dp),
                horizontalArrangement = Arrangement.Center,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Icon(
                    Icons.Outlined.Refresh,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.size(18.dp)
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    "概览加载失败，点击重试",
                    fontSize = 14.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
}

/**
 * 「今日概览」骨架占位（AI-APP-UI-002）：与真实卡片同形同高，
 * dashboard 加载期间布局不跳动。
 */
@Composable
private fun DashboardOverviewSkeleton() {
    Column {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 20.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            // 半悬浮后标题占位压在 Hero 深蓝背景上，shimmer 用 OnSurfaceVariant 在暗底上仍可辨
            WmsShimmerBox(modifier = Modifier.size(width = 76.dp, height = 20.dp), corner = 6.dp)
            Spacer(modifier = Modifier.weight(1f))
            WmsShimmerBox(modifier = Modifier.size(width = 96.dp, height = 32.dp), corner = 16.dp)
        }
        Spacer(modifier = Modifier.height(6.dp))
        Card(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 20.dp),
            shape = RoundedCornerShape(18.dp),
            colors = CardDefaults.cardColors(containerColor = CardBackground),
            elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 10.dp, vertical = 14.dp),
                horizontalArrangement = Arrangement.SpaceEvenly,
                verticalAlignment = Alignment.Top
            ) {
                repeat(4) {
                    Column(
                        modifier = Modifier
                            .weight(1f)
                            .padding(horizontal = 6.dp),
                        horizontalAlignment = Alignment.CenterHorizontally
                    ) {
                        WmsShimmerBox(modifier = Modifier.size(38.dp), corner = 11.dp)
                        Spacer(modifier = Modifier.height(7.dp))
                        WmsShimmerBox(modifier = Modifier.size(width = 40.dp, height = 20.dp), corner = 6.dp)
                        Spacer(modifier = Modifier.height(4.dp))
                        WmsShimmerBox(modifier = Modifier.size(width = 48.dp, height = 12.dp), corner = 6.dp)
                    }
                }
            }
        }
    }
}

private data class OverviewItem(
    val label: String,
    val value: String,
    val sub: String,
    val icon: ImageVector,
    val color: Color,
    val screen: Screen?
)

@Composable
private fun OverviewItemCell(
    item: OverviewItem,
    modifier: Modifier = Modifier,
    onClicked: (() -> Unit)? = null
) {
    val haptics = LocalHapticFeedback.current
    val clickModifier = if (onClicked != null) {
        // BUG-2026-09-26-004：恢复默认 ripple。此前 indication=null 只有震动、
        // 无任何视觉反馈，弱网/请求中用户以为没点上就连点。震动保留，涟漪补上。
        Modifier.clickable(
            onClick = {
                haptics.performHapticFeedback(HapticFeedbackType.LongPress)
                onClicked()
            }
        )
    } else {
        Modifier
    }
    Column(
        modifier = modifier
            .padding(horizontal = 6.dp)
            .then(clickModifier),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Box(
            modifier = Modifier
                .size(38.dp)
                .clip(RoundedCornerShape(11.dp))
                .background(item.color.copy(alpha = 0.12f)),
            contentAlignment = Alignment.Center
        ) {
            Icon(
                item.icon,
                contentDescription = null,
                tint = item.color,
                modifier = Modifier.size(20.dp)
            )
        }
        Spacer(modifier = Modifier.height(7.dp))
        Text(
            item.value,
            fontSize = 20.sp,
            fontWeight = FontWeight.Bold,
            color = MaterialTheme.colorScheme.onSurface
        )
        Spacer(modifier = Modifier.height(2.dp))
        Text(
            item.label,
            fontSize = 11.sp,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis
        )
        Text(
            item.sub,
            fontSize = 10.sp,
            color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.8f),
            textAlign = TextAlign.Center,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis
        )
    }
}

// AI-APP-FIX-403：私有 formatQty 已合并为 ui/util/Format.kt 的共享实现（千分位）