package com.factory.wms.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.ArrowDownward
import androidx.compose.material.icons.outlined.ArrowUpward
import androidx.compose.material.icons.outlined.Inbox
import androidx.compose.material.icons.outlined.WarningAmber
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.factory.wms.data.model.AlertItemDto
import com.factory.wms.data.model.MobileOrderDto
import com.factory.wms.ui.components.WmsEmptyState
import com.factory.wms.ui.components.WmsErrorState
import com.factory.wms.ui.components.WmsGradientHeader
import com.factory.wms.ui.components.WmsListSkeleton
import com.factory.wms.ui.components.WmsPullToRefreshBox
import com.factory.wms.ui.theme.*
import com.factory.wms.ui.viewmodel.list.ListKind
import com.factory.wms.ui.viewmodel.list.ListUiState
import com.factory.wms.ui.viewmodel.list.OrderListViewModel
import com.factory.wms.util.formatQuantity

/**
 * 首页概览下钻列表（AI-MOB-DRILLDOWN-01）。
 *
 * 首页四个数字原来只有两个能点、且点了也看不到明细：
 * - 「待处理单据」screen = null，点了完全没反应
 * - 「库存告警」跳到查库存的空白搜索框，用户不知道到底哪些物料告警
 *
 * 本页承接这两类下钻（待处理单据可再切「入库单 / 出库单」），
 * 数据来自后端早已存在、手机端此前未接入的三个接口。
 */

/** 下钻目标：库存告警 / 待处理单据。 */
enum class OverviewTarget { ALERT, PENDING_ORDERS }

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun OverviewListScreen(
    target: OverviewTarget,
    viewModel: OrderListViewModel,
    warehouseId: String,
    warehouseName: String,
    onBack: () -> Unit
) {
    val uiState by viewModel.uiState.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }

    // 进入页面按目标初始化（含默认筛选：告警无筛选；单据默认看待处理）
    LaunchedEffect(target, warehouseId) {
        if (warehouseId.isNotBlank()) {
            viewModel.start(
                kind = if (target == OverviewTarget.ALERT) ListKind.ALERT else ListKind.IN_ORDER,
                warehouseId = warehouseId,
                warehouseName = warehouseName
            )
        }
    }

    LaunchedEffect(uiState.error) {
        uiState.error?.let {
            // AI-APP-FIX-201：此处只剩"带数据刷新/翻页失败"的瞬态错误（首屏失败
            // 走 loadError 全屏错误态），Snackbar 加长避免现场没看清就消失。
            snackbarHostState.showSnackbar(it, duration = SnackbarDuration.Long)
            viewModel.clearError()
        }
    }

    val accent = when (target) {
        OverviewTarget.ALERT -> Error
        OverviewTarget.PENDING_ORDERS -> CardOrange
    }

    Scaffold(
        snackbarHost = { SnackbarHost(snackbarHostState) },
        containerColor = Background,
        topBar = {
            WmsGradientHeader(
                title = if (target == OverviewTarget.ALERT) "库存告警" else "待处理单据",
                subtitle = buildString {
                    append(if (target == OverviewTarget.ALERT) "低于安全库存的物料" else "待处理的出入库单")
                    if (warehouseName.isNotBlank()) append(" · $warehouseName")
                },
                accent = accent,
                onBack = onBack
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
        ) {
            // 待处理单据页：入库单 / 出库单切换（两类单据端点不同，用户按需看）
            if (target == OverviewTarget.PENDING_ORDERS) {
                OrderKindTabs(
                    current = uiState.kind,
                    accent = accent,
                    onSelect = { kind ->
                        viewModel.start(kind, warehouseId, warehouseName)
                    }
                )
                StatusFilterRow(
                    current = uiState.statusFilter,
                    accent = accent,
                    onSelect = { viewModel.setStatusFilter(it) }
                )
            }

            when {
                // AI-APP-FIX-202：首屏转圈 → 骨架列表（高度与真实列表接近，不跳变）
                uiState.isFirstLoad -> {
                    WmsListSkeleton()
                }

                // AI-APP-FIX-201：首屏加载失败 → 全屏错误态 + 重试，
                // 不再落入下方"暂无告警/没有单据"的误导性空态
                uiState.loadError != null -> {
                    Box(
                        modifier = Modifier.fillMaxSize(),
                        contentAlignment = Alignment.Center
                    ) {
                        WmsErrorState(
                            title = "加载失败",
                            subtitle = uiState.loadError ?: "请检查网络后重试",
                            onRetry = { viewModel.retry() }
                        )
                    }
                }

                target == OverviewTarget.ALERT -> AlertList(
                    state = uiState,
                    accent = accent,
                    onLoadMore = { viewModel.loadMore() },
                    onRefresh = { viewModel.retry() }
                )

                else -> OrderList(
                    state = uiState,
                    accent = accent,
                    onLoadMore = { viewModel.loadMore() },
                    onRefresh = { viewModel.retry() }
                )
            }
        }
    }
}

@Composable
private fun OrderKindTabs(current: ListKind, accent: Color, onSelect: (ListKind) -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 8.dp),
        horizontalArrangement = Arrangement.spacedBy(10.dp)
    ) {
        listOf(ListKind.IN_ORDER to "入库单", ListKind.OUT_ORDER to "出库单").forEach { (kind, label) ->
            FilterChip(
                selected = current == kind,
                modifier = Modifier.height(WmsDimens.TouchTargetMin),
                onClick = { if (current != kind) onSelect(kind) },
                label = { Text(label) },
                shape = RoundedCornerShape(10.dp),
                colors = FilterChipDefaults.filterChipColors(
                    // AI-APP-FIX-301：Chip 选中底 alpha 亮 0.14 / 暗 0.24
                    selectedContainerColor = accent.copy(alpha = MaterialTheme.wmsColors.accentWashAlpha),
                    selectedLabelColor = accent
                )
            )
        }
    }
}

@Composable
private fun StatusFilterRow(current: String?, accent: Color, onSelect: (String?) -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp),
        horizontalArrangement = Arrangement.spacedBy(10.dp)
    ) {
        listOf(null to "全部", "pending" to "待处理", "completed" to "已完成").forEach { (value, label) ->
            FilterChip(
                selected = current == value,
                modifier = Modifier.height(WmsDimens.TouchTargetMin),
                onClick = { onSelect(value) },
                label = { Text(label) },
                shape = RoundedCornerShape(10.dp),
                colors = FilterChipDefaults.filterChipColors(
                    // AI-APP-FIX-301：Chip 选中底 alpha 亮 0.14 / 暗 0.24
                    selectedContainerColor = accent.copy(alpha = MaterialTheme.wmsColors.accentWashAlpha),
                    selectedLabelColor = accent
                )
            )
        }
    }
}

/** 库存告警清单：编码/名称/规格 + 现有库存 vs 安全库存 + 缺口。 */
@Composable
private fun AlertList(
    state: ListUiState,
    accent: Color,
    onLoadMore: () -> Unit,
    onRefresh: () -> Unit
) {
    val listState = rememberLazyListState()
    // 滑到末尾自动加载下一页（与查库存列表同策略）
    val shouldLoadMore by remember {
        derivedStateOf {
            val last = listState.layoutInfo.visibleItemsInfo.lastOrNull()?.index ?: 0
            last >= state.alerts.size - 2
        }
    }
    LaunchedEffect(shouldLoadMore, state.page, state.totalPages) {
        if (shouldLoadMore && state.page < state.totalPages) onLoadMore()
    }

    // AI-APP-FIX-505：下拉刷新统一（空态也可下拉重试）；首屏加载走骨架屏，
    // 只有"已有内容时的刷新"才亮刷新指示器。
    WmsPullToRefreshBox(
        isRefreshing = state.isLoading && !state.isFirstLoad,
        onRefresh = onRefresh,
        modifier = Modifier.fillMaxSize()
    ) {
    if (state.alerts.isEmpty()) {
        Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            WmsEmptyState(
                icon = Icons.Outlined.WarningAmber,
                title = "本仓暂无库存告警",
                // AI-CI-GREEN-005-F04：告警口径是两级（low/danger），两档都落在
                // 「库存 <= 安全库存」内，所以列表为空 ⟺ 所有物料都在安全库存之上。
                subtitle = state.notice ?: "所有物料都在安全库存之上",
                accentColor = accent
            )
        }
        return@WmsPullToRefreshBox
    }

    Column(modifier = Modifier.fillMaxSize()) {
        Text(
            "共 ${state.total} 项低于安全库存",
            modifier = Modifier.padding(horizontal = 20.dp, vertical = 10.dp),
            fontSize = 14.sp,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        LazyColumn(
            state = listState,
            modifier = Modifier.fillMaxSize(),
            contentPadding = PaddingValues(horizontal = 16.dp, vertical = 4.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            // BUG-2026-09-14-031：key 不得用 `id ?: 0`（id 可空、多条 null 时 key 冲突崩溃）。
            // 三级兜底：id → 物料编码 → hashCode。与 MaterialArchiveScreens 既有写法一致。
            items(state.alerts, key = { it.id ?: it.code ?: it.hashCode() }) { item ->
                AlertRow(item, accent)
            }
            item {
                ListFooter(state)
            }
        }
    }
    }
}

@Composable
internal fun AlertRow(item: AlertItemDto, accent: Color) {
    val safetyStock = item.safetyStock ?: item.minStock
    val unit = item.unit.orEmpty().takeIf { it.isNotBlank() }?.let { " $it" }.orEmpty()
    fun value(number: Double?): String = number?.let { formatQuantity(it) + unit } ?: "—"
    Card(modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = CardBackground),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)) {
        Column(Modifier.fillMaxWidth().padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(item.code.orEmpty(), fontFamily = FontFamily.Monospace, fontWeight = FontWeight.SemiBold,
                fontSize = 14.sp, color = Primary.readableOn(CardBackground), softWrap = true)
            if (!item.name.isNullOrBlank()) Text(item.name.orEmpty(), fontSize = 16.sp,
                fontWeight = FontWeight.SemiBold, softWrap = true)
            if (!item.spec.isNullOrBlank()) Text("规格：${item.spec}", fontSize = 14.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant, softWrap = true)
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                Icon(Icons.Outlined.WarningAmber, contentDescription = null,
                    tint = accent.readableOn(CardBackground), modifier = Modifier.size(20.dp))
                Text("库存告警 · 缺口", fontSize = 14.sp, color = accent.readableOn(CardBackground))
            }
            Text(value(item.gap), modifier = Modifier.fillMaxWidth(), fontSize = 20.sp, fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold, color = accent.readableOn(CardBackground), softWrap = true)
            Text("现有 ${value(item.stock)}  /  安全库存 ${value(safetyStock)}", fontSize = 14.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant, softWrap = true)
        }
    }
}

/** 单据清单：单号 + 状态 + 日期 + 明细数 + 部门/金额。 */
@Composable
private fun OrderList(
    state: ListUiState,
    accent: Color,
    onLoadMore: () -> Unit,
    onRefresh: () -> Unit
) {
    val listState = rememberLazyListState()
    // AI-APP-FIX-506：切换入库/出库单（或状态筛选）后滚动位置重置——
    // 此前列表停在原位，从出库第 5 屏切到入库会落在列表中段，用户以为数据丢了。
    LaunchedEffect(state.kind, state.statusFilter) {
        listState.scrollToItem(0)
    }
    val shouldLoadMore by remember {
        derivedStateOf {
            val last = listState.layoutInfo.visibleItemsInfo.lastOrNull()?.index ?: 0
            last >= state.orders.size - 2
        }
    }
    LaunchedEffect(shouldLoadMore, state.page, state.totalPages) {
        if (shouldLoadMore && state.page < state.totalPages) onLoadMore()
    }

    // AI-APP-FIX-505：下拉刷新统一（空态也可下拉重试）
    WmsPullToRefreshBox(
        isRefreshing = state.isLoading && !state.isFirstLoad,
        onRefresh = onRefresh,
        modifier = Modifier.fillMaxSize()
    ) {
    if (state.orders.isEmpty()) {
        Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            WmsEmptyState(
                icon = Icons.Outlined.Inbox,
                title = "当前筛选下没有单据",
                subtitle = "换个状态筛选试试",
                accentColor = accent
            )
        }
        return@WmsPullToRefreshBox
    }

    Column(modifier = Modifier.fillMaxSize()) {
        Text(
            "共 ${state.total} 单",
            modifier = Modifier.padding(horizontal = 20.dp, vertical = 10.dp),
            fontSize = 14.sp,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        LazyColumn(
            state = listState,
            modifier = Modifier.fillMaxSize(),
            contentPadding = PaddingValues(horizontal = 16.dp, vertical = 4.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            // BUG-2026-09-14-031：同上，单据用 orderNo 兜底（单号为业务唯一键）。
            items(state.orders, key = { it.id ?: it.orderNo ?: it.hashCode() }) { order ->
                OrderRow(order, accent, inbound = state.kind == ListKind.IN_ORDER)
            }
            item {
                ListFooter(state)
            }
        }
    }
    }
}

@Composable
internal fun OrderRow(order: MobileOrderDto, accent: Color, inbound: Boolean) {
    val statusText = when (order.status) {
        "pending" -> "待处理"
        "completed" -> "已完成"
        else -> order.status?.takeIf { it.isNotBlank() } ?: "状态未知"
    }
    val statusColor = if (order.status == "pending") accent.readableOn(CardBackground) else MaterialTheme.colorScheme.onSurfaceVariant
    Card(modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = CardBackground),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)) {
        Column(Modifier.fillMaxWidth().padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Row(verticalAlignment = Alignment.Top, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                Icon(if (inbound) Icons.Outlined.ArrowDownward else Icons.Outlined.ArrowUpward,
                    contentDescription = null, tint = accent.readableOn(CardBackground), modifier = Modifier.size(20.dp))
                Text(order.orderNo?.takeIf { it.isNotBlank() } ?: "单号未知", modifier = Modifier.weight(1f),
                    fontFamily = FontFamily.Monospace, fontWeight = FontWeight.SemiBold,
                    fontSize = 16.sp, color = Primary.readableOn(CardBackground), softWrap = true)
            }
            Text(statusText, fontSize = 14.sp, color = statusColor, fontWeight = FontWeight.SemiBold)
            val date = order.date?.takeIf { it.isNotBlank() } ?: "日期未知"
            val count = order.itemCount?.toString() ?: "—"
            Text("$date · 明细 $count 项", fontSize = 14.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant, softWrap = true)
            if (!inbound && !order.department.isNullOrBlank()) {
                Text("领料部门：${order.department}", fontSize = 14.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant, softWrap = true)
            }
        }
    }
}

@Composable
private fun ListFooter(state: ListUiState) {
    when {
        state.isLoadingMore -> Box(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            contentAlignment = Alignment.Center
        ) { CircularProgressIndicator(modifier = Modifier.size(22.dp)) }

        state.page < state.totalPages -> Box(
            modifier = Modifier
                .fillMaxWidth()
                .padding(12.dp),
            contentAlignment = Alignment.Center
        ) {
            // AI-APP-FIX-203：纯提示文案，不做成按钮——onClick 为空的"假按钮"
            // 会让用户以为点了能加载（实际靠上滑自动触发），点了没反应像坏掉。
            Text(
                "上滑加载更多",
                fontSize = 14.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }

        state.total > 0 -> Box(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            contentAlignment = Alignment.Center
        ) {
            Text(
                "— 已全部加载 —",
                fontSize = 14.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}
