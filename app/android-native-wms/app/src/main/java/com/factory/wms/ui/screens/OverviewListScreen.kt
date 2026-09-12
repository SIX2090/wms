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
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.factory.wms.data.model.AlertItemDto
import com.factory.wms.data.model.MobileOrderDto
import com.factory.wms.ui.components.WmsEmptyState
import com.factory.wms.ui.components.WmsGradientHeader
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
            snackbarHostState.showSnackbar(it, duration = SnackbarDuration.Short)
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
                    append(if (target == OverviewTarget.ALERT) "低于最低库存的物料" else "待处理的出入库单")
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
                uiState.isFirstLoad -> {
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(48.dp),
                        contentAlignment = Alignment.Center
                    ) { CircularProgressIndicator(color = accent) }
                }

                target == OverviewTarget.ALERT -> AlertList(
                    state = uiState,
                    accent = accent,
                    onLoadMore = { viewModel.loadMore() }
                )

                else -> OrderList(
                    state = uiState,
                    accent = accent,
                    onLoadMore = { viewModel.loadMore() }
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
                onClick = { if (current != kind) onSelect(kind) },
                label = { Text(label) },
                shape = RoundedCornerShape(10.dp),
                colors = FilterChipDefaults.filterChipColors(
                    selectedContainerColor = accent.copy(alpha = 0.14f),
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
                onClick = { onSelect(value) },
                label = { Text(label) },
                shape = RoundedCornerShape(10.dp),
                colors = FilterChipDefaults.filterChipColors(
                    selectedContainerColor = accent.copy(alpha = 0.14f),
                    selectedLabelColor = accent
                )
            )
        }
    }
}

/** 库存告警清单：编码/名称/规格 + 现有库存 vs 最低库存 + 缺口。 */
@Composable
private fun AlertList(
    state: ListUiState,
    accent: Color,
    onLoadMore: () -> Unit
) {
    if (state.alerts.isEmpty()) {
        Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            WmsEmptyState(
                icon = Icons.Outlined.WarningAmber,
                title = "本仓暂无库存告警",
                subtitle = state.notice ?: "所有物料都在最低库存之上",
                accentColor = accent
            )
        }
        return
    }

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

    Column(modifier = Modifier.fillMaxSize()) {
        Text(
            "共 ${state.total} 项低于最低库存",
            modifier = Modifier.padding(horizontal = 20.dp, vertical = 10.dp),
            fontSize = 13.sp,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        LazyColumn(
            state = listState,
            modifier = Modifier.fillMaxSize(),
            contentPadding = PaddingValues(horizontal = 16.dp, vertical = 4.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            items(state.alerts, key = { it.id ?: 0 }) { item ->
                AlertRow(item, accent)
            }
            item {
                ListFooter(state)
            }
        }
    }
}

@Composable
private fun AlertRow(item: AlertItemDto, accent: Color) {
    val stock = item.stock ?: 0.0
    val minStock = item.minStock ?: 0.0
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.cardColors(containerColor = CardBackground),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
    ) {
        Column(modifier = Modifier.padding(14.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    item.code.orEmpty(),
                    fontWeight = FontWeight.Bold,
                    fontSize = 15.sp,
                    color = Primary
                )
                if (!item.name.isNullOrBlank()) {
                    Spacer(Modifier.width(8.dp))
                    Text(
                        item.name.orEmpty(),
                        fontSize = 14.sp,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                        modifier = Modifier.weight(1f)
                    )
                }
            }
            if (!item.spec.isNullOrBlank()) {
                Spacer(Modifier.height(3.dp))
                Text(
                    "规格: ${item.spec}",
                    fontSize = 12.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
            }
            Spacer(Modifier.height(8.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                // 缺货量放在最显眼位置——用户最关心"还差多少"
                Surface(
                    shape = RoundedCornerShape(8.dp),
                    color = accent.copy(alpha = 0.12f)
                ) {
                    Text(
                        "缺 ${formatQuantity(item.gap ?: 0.0)}${item.unit.orEmpty()}",
                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 3.dp),
                        fontSize = 12.sp,
                        fontWeight = FontWeight.SemiBold,
                        color = accent
                    )
                }
                Spacer(Modifier.width(10.dp))
                Text(
                    "现有 ${formatQuantity(stock)} / 最低 ${formatQuantity(minStock)}",
                    fontSize = 12.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
}

/** 单据清单：单号 + 状态 + 日期 + 明细数 + 部门/金额。 */
@Composable
private fun OrderList(
    state: ListUiState,
    accent: Color,
    onLoadMore: () -> Unit
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
        return
    }

    val listState = rememberLazyListState()
    val shouldLoadMore by remember {
        derivedStateOf {
            val last = listState.layoutInfo.visibleItemsInfo.lastOrNull()?.index ?: 0
            last >= state.orders.size - 2
        }
    }
    LaunchedEffect(shouldLoadMore, state.page, state.totalPages) {
        if (shouldLoadMore && state.page < state.totalPages) onLoadMore()
    }

    Column(modifier = Modifier.fillMaxSize()) {
        Text(
            "共 ${state.total} 单",
            modifier = Modifier.padding(horizontal = 20.dp, vertical = 10.dp),
            fontSize = 13.sp,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        LazyColumn(
            state = listState,
            modifier = Modifier.fillMaxSize(),
            contentPadding = PaddingValues(horizontal = 16.dp, vertical = 4.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            items(state.orders, key = { it.id ?: 0 }) { order ->
                OrderRow(order, accent, inbound = state.kind == ListKind.IN_ORDER)
            }
            item {
                ListFooter(state)
            }
        }
    }
}

@Composable
private fun OrderRow(order: MobileOrderDto, accent: Color, inbound: Boolean) {
    val isPending = order.status == "pending"
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.cardColors(containerColor = CardBackground),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
    ) {
        Column(modifier = Modifier.padding(14.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(
                    if (inbound) Icons.Outlined.ArrowDownward else Icons.Outlined.ArrowUpward,
                    null,
                    tint = accent,
                    modifier = Modifier.size(18.dp)
                )
                Spacer(Modifier.width(6.dp))
                Text(
                    order.orderNo.orEmpty(),
                    fontWeight = FontWeight.Bold,
                    fontSize = 15.sp,
                    color = Primary,
                    modifier = Modifier.weight(1f),
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
                // 状态标签：待处理用强调色，已完成用中性色
                Surface(
                    shape = RoundedCornerShape(8.dp),
                    color = if (isPending) accent.copy(alpha = 0.12f) else SuccessContainer
                ) {
                    Text(
                        if (isPending) "待处理" else "已完成",
                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 3.dp),
                        fontSize = 12.sp,
                        fontWeight = FontWeight.SemiBold,
                        color = if (isPending) accent else Success
                    )
                }
            }
            Spacer(Modifier.height(8.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    order.date.orEmpty(),
                    fontSize = 12.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                Text(
                    " · ${order.itemCount ?: 0} 项",
                    fontSize = 12.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                // 出库单显示领料部门，入库单显示供应商留空则不占位
                if (!inbound && !order.department.isNullOrBlank()) {
                    Text(
                        " · ${order.department}",
                        fontSize = 12.sp,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                }
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
            TextButton(onClick = { /* 由 shouldLoadMore 自动触发 */ }) {
                Text("上滑加载更多", fontSize = 12.sp)
            }
        }

        state.total > 0 -> Box(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            contentAlignment = Alignment.Center
        ) {
            Text(
                "— 已全部加载 —",
                fontSize = 12.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}
