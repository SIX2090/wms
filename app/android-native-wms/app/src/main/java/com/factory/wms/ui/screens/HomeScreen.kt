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
    LaunchedEffect(Unit) {
        homeViewModel.loadWarehouses()
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
                subtitle = "搜索物料 · 拍照上传档案照片",
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
                subtitle = "按仓展示 · 各物料每日结存",
                icon = Icons.Outlined.Inventory2,
                gradient = listOf(CardCyanLight, CardCyanDark),
                screen = Screen.StockDailyReport
            ),
            FunctionCard(
                title = "出入库明细",
                subtitle = "日期范围 · 按仓查看流水",
                icon = Icons.Outlined.SwapVert,
                gradient = listOf(CardGreen, CardGreenDark),
                screen = Screen.InOutDetailReport
            ),
            FunctionCard(
                title = "库存台账",
                subtitle = "单物料 · 期初出入结存流水",
                icon = Icons.Outlined.MenuBook,
                gradient = listOf(CardTealLight, CardTealDark),
                screen = Screen.StockLedgerReport
            ),
            FunctionCard(
                title = "盘点记录",
                subtitle = "本人盘点 · 回查差异与采纳状态",
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
                    .padding(top = 16.dp, bottom = 32.dp)
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
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        "今日概览",
                        fontWeight = FontWeight.SemiBold,
                        fontSize = 15.sp,
                        color = MaterialTheme.colorScheme.onSurface,
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
            } else {
                // AI-APP-UI-002：数据未返回时渲染同形骨架。
                // 原先此处整块不渲染，数据到达瞬间功能卡网格整体下沉一截，
                // 看起来像"页面闪了一下"；骨架占位让布局高度始终稳定。
                DashboardOverviewSkeleton()
            }

            // ── Card Grid ──
            Spacer(modifier = Modifier.height(20.dp))

            val screenWidth = LocalConfiguration.current.screenWidthDp.dp
            val cardWidth = (screenWidth - 56.dp) / 2
            val rowCount = (cards.size + 1) / 2

            for (row in 0 until rowCount) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 20.dp),
                    horizontalArrangement = Arrangement.spacedBy(16.dp)
                ) {
                    for (col in 0..1) {
                        val index = row * 2 + col
                        if (index < cards.size) {
                            val card = cards[index]
                            FunctionCardItem(
                                card = card,
                                index = index,
                                modifier = Modifier.width(cardWidth),
                                onClick = { onNavigate(card.screen) }
                            )
                        }
                    }
                }
                Spacer(modifier = Modifier.height(16.dp))
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
            .height(168.dp)
            .graphicsLayer {
                alpha = entrance.value
                translationY = (1f - entrance.value) * 36f
            }
            .scale(scale)
            .shadow(
                elevation = if (pressed) 4.dp else 8.dp,
                shape = RoundedCornerShape(22.dp),
                ambientColor = card.gradient.first().copy(alpha = 0.15f),
                spotColor = card.gradient.first().copy(alpha = 0.2f)
            )
            .clip(RoundedCornerShape(22.dp))
            .clickable(
                interactionSource = remember { MutableInteractionSource() },
                indication = null,
                onClick = {
                    haptics.performHapticFeedback(HapticFeedbackType.LongPress)
                    onClick()
                }
            ),
        shape = RoundedCornerShape(22.dp),
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
            // Decorative background elements
            Box(
                modifier = Modifier
                    .size(90.dp)
                    .offset(x = 80.dp, y = (-30).dp)
                    .clip(CircleShape)
                    .background(Color.White.copy(alpha = 0.08f))
            )
            Box(
                modifier = Modifier
                    .size(50.dp)
                    .offset(x = 70.dp, y = 50.dp)
                    .clip(CircleShape)
                    .background(Color.White.copy(alpha = 0.05f))
            )
            Box(
                modifier = Modifier
                    .size(30.dp)
                    .offset(x = (-10).dp, y = 120.dp)
                    .clip(CircleShape)
                    .background(Color.White.copy(alpha = 0.06f))
            )

            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(18.dp),
                verticalArrangement = Arrangement.SpaceBetween
            ) {
                // Icon container
                Box(
                    modifier = Modifier
                        .size(48.dp)
                        .clip(RoundedCornerShape(16.dp))
                        .background(Color.White.copy(alpha = 0.22f)),
                    contentAlignment = Alignment.Center
                ) {
                    Icon(
                        imageVector = card.icon,
                        contentDescription = null,
                        tint = Color.White,
                        modifier = Modifier.size(26.dp)
                    )
                }

                // Title & subtitle
                Column {
                    Text(
                        text = card.title,
                        color = Color.White,
                        fontWeight = FontWeight.Bold,
                        fontSize = 17.sp,
                        letterSpacing = 0.5.sp
                    )
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        text = card.subtitle,
                        color = Color.White.copy(alpha = 0.8f),
                        fontSize = 12.sp,
                        lineHeight = 17.sp,
                        maxLines = 2,
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
            sub = "入${dashboard.pendingInOrders} 出${dashboard.pendingOutOrders}",
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
            sub = "低于安全库存",
            icon = Icons.Outlined.WarningAmber,
            color = Error,
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
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        // AI-APP-UI-002：卡片内不再重复渲染「今日概览」标题——
        // 外层已有同名标题 + 仓库切换器，卡片内再来一遍是纯视觉冗余。
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 10.dp, vertical = 14.dp),
            horizontalArrangement = Arrangement.SpaceEvenly
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
                horizontalArrangement = Arrangement.SpaceEvenly
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
        Modifier.clickable(
            interactionSource = remember { MutableInteractionSource() },
            indication = null,
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
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        Text(
            item.sub,
            fontSize = 10.sp,
            color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.8f)
        )
    }
}

// AI-APP-FIX-403：私有 formatQty 已合并为 ui/util/Format.kt 的共享实现（千分位）