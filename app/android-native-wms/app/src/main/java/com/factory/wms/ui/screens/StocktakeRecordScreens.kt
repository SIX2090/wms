package com.factory.wms.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.ChevronRight
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarDuration
import androidx.compose.material3.Surface
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.factory.wms.data.model.StocktakeRecordDetailData
import com.factory.wms.data.model.StocktakeRecordDetailItemDto
import com.factory.wms.data.model.StocktakeRecordDto
import com.factory.wms.ui.components.WmsEmptyState
import com.factory.wms.ui.components.WmsErrorState
import com.factory.wms.ui.components.WmsListSkeleton
import com.factory.wms.ui.components.WmsPillBadge
import com.factory.wms.ui.components.WmsPullToRefreshBox
import com.factory.wms.ui.components.WmsTopBar
import com.factory.wms.ui.util.formatQty
import com.factory.wms.ui.theme.WmsDimens
import com.factory.wms.ui.theme.Background
import com.factory.wms.ui.theme.CardAmber
import com.factory.wms.ui.theme.CardCyan
import com.factory.wms.ui.theme.CardPurple
import com.factory.wms.ui.theme.CardTeal
import com.factory.wms.ui.theme.OnSurface
import com.factory.wms.ui.theme.Primary
import com.factory.wms.ui.viewmodel.stocktake.StocktakeRecordViewModel

/**
 * 盘点记录回查页（AI-MOB-CHECK-F01）。
 *
 * 手机盘点提交后此前"提交即失联"：作业员看不到自己盘过哪些单、差异多少、
 * 是否已被 PC 端采纳。本页按「本人经手」回查，只读。
 * 服务端：GET /api/mobile/stocktake/list
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun StocktakeRecordScreen(
    viewModel: StocktakeRecordViewModel,
    onBack: () -> Unit
) {
    val uiState by viewModel.uiState.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }

    // BUG-2026-08-24-006：进入页面时才加载（ViewModel 在 App 启动导航图组合阶段
    // 即被创建，不能依赖 init 拉数据）
    LaunchedEffect(Unit) {
        viewModel.load()
    }

    LaunchedEffect(uiState.error) {
        uiState.error?.let {
            // AI-APP-FIX-201：此处只剩"翻页失败"的瞬态错误（首屏失败走
            // loadError 全屏错误态），Snackbar 加长避免现场没看清就消失。
            snackbarHostState.showSnackbar(it, duration = SnackbarDuration.Long)
            viewModel.clearError()
        }
    }

    Scaffold(
        snackbarHost = { SnackbarHost(snackbarHostState) },
        containerColor = Background,
        topBar = {
            // AI-APP-FIX-401：自绘 TopAppBar → 统一 WmsTopBar
            WmsTopBar(
                title = "盘点记录",
                subtitle = if (uiState.total > 0) "共 ${uiState.total} 条本人盘点记录" else "本人盘点记录回查",
                onBack = onBack,
                actions = {
                    // AI-APP-FIX-406：Restore → Refresh（Restore 语义是"还原"，易误解）；
                    // 加载中禁用，防连点触发并发请求
                    IconButton(onClick = { viewModel.load() }, enabled = !uiState.isLoading) {
                        Icon(
                            Icons.Filled.Refresh,
                            "刷新",
                            tint = MaterialTheme.colorScheme.onSurface
                        )
                    }
                }
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .padding(padding)
                .fillMaxSize()
        ) {
            // ── 视图切换：正常记录 / 已作废 ──
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 8.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                FilterChip(
                    selected = !uiState.showVoided,
                    modifier = Modifier.height(WmsDimens.TouchTargetMin),
                    onClick = { if (uiState.showVoided) viewModel.toggleVoided() },
                    label = { Text("正常记录") }
                )
                FilterChip(
                    selected = uiState.showVoided,
                    modifier = Modifier.height(WmsDimens.TouchTargetMin),
                    onClick = { if (!uiState.showVoided) viewModel.toggleVoided() },
                    label = { Text("已作废") }
                )
            }

            when {
                // AI-APP-FIX-202：首屏转圈 → 骨架列表
                uiState.isLoading && uiState.records.isEmpty() -> {
                    WmsListSkeleton()
                }

                // AI-APP-FIX-201：首屏加载失败 → 全屏错误态 + 重试，
                // 不再落入下方"还没有盘点记录"的误导性空态
                uiState.loadError != null && uiState.records.isEmpty() -> {
                    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        WmsErrorState(
                            title = "加载失败",
                            subtitle = uiState.loadError ?: "请检查网络后重试",
                            onRetry = { viewModel.load() }
                        )
                    }
                }

                uiState.isEmpty -> {
                    WmsEmptyState(
                        icon = Icons.Filled.History,
                        title = if (uiState.showVoided) "没有已作废的盘点记录" else "还没有盘点记录",
                        subtitle = if (uiState.showVoided) {
                            "被作废的盘点单会在这里留痕，便于对账"
                        } else {
                            "在扫码盘点页选择进行中的盘点单提交后，记录会出现在这里"
                        },
                        modifier = Modifier.fillMaxSize(),
                        accentColor = CardPurple
                    )
                }

                else -> {
                    // AI-APP-FIX-505：下拉刷新统一入口（顶栏刷新图标保留）。
                    // 仅在"已有数据时的刷新"期间亮指示器，首屏交给骨架屏。
                    WmsPullToRefreshBox(
                        isRefreshing = uiState.isLoading && uiState.records.isNotEmpty(),
                        onRefresh = { viewModel.load() },
                        modifier = Modifier.fillMaxSize()
                    ) {
                    LazyColumn(
                        modifier = Modifier.fillMaxSize(),
                        contentPadding = androidx.compose.foundation.layout.PaddingValues(
                            horizontal = 16.dp, vertical = 4.dp
                        ),
                        verticalArrangement = Arrangement.spacedBy(10.dp)
                    ) {
                        // BUG-2026-09-14-031：`key = { it.id }` 看似安全（id 非空 Long），但该字段
                        // 有默认值 0，Gson 反序列化遇缺失/异常响应会落 0——同页多条即 key 冲突崩溃。
                        // 统一为「id 有效则用 id，否则退 checkNo → hashCode」。
                        items(uiState.records, key = { if (it.id != 0L) it.id else it.checkNo ?: it.hashCode() }) { record ->
                            // AI-APP-FIX-505：点卡片下钻差异明细（id=0 的脏数据不可下钻）
                            StocktakeRecordCard(
                                record = record,
                                onClick = if (record.id != 0L) {
                                    { viewModel.loadDetail(record.id) }
                                } else {
                                    null
                                }
                            )
                        }
                        if (uiState.hasMore) {
                            item {
                                Box(
                                    Modifier
                                        .fillMaxWidth()
                                        .padding(vertical = 12.dp),
                                    contentAlignment = Alignment.Center
                                ) {
                                    if (uiState.isLoading) {
                                        CircularProgressIndicator(
                                            modifier = Modifier.size(22.dp),
                                            color = Primary
                                        )
                                    } else {
                                        TextButton(onClick = { viewModel.loadMore() }) {
                                            Text("加载更多（共 ${uiState.totalPages} 页）")
                                        }
                                    }
                                }
                            }
                        }
                    }
                    }
                }
            }
        }
    }

    // AI-APP-FIX-505：差异明细下钻对话框（加载中/失败/成功三态都在框内闭环）
    if (uiState.detailTargetId != null) {
        StocktakeRecordDetailDialog(
            detail = uiState.detail,
            loading = uiState.detailLoading,
            error = uiState.detailError,
            onRetry = { uiState.detailTargetId?.let { viewModel.loadDetail(it) } },
            onDismiss = { viewModel.clearDetail() }
        )
    }
}

@Composable
private fun StocktakeRecordCard(record: StocktakeRecordDto, onClick: (() -> Unit)? = null) {
    val isVoid = record.status == "void"
    val accent = if (isVoid) CardAmber else CardTeal
    val diff = record.diffCount ?: 0
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .then(
                if (onClick != null) Modifier.clickable(onClick = onClick) else Modifier
            ),
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surface
        ),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
    ) {
        Column(Modifier.padding(14.dp)) {
            // 单号 + 状态标签
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    record.checkNo ?: "—",
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.Bold,
                    color = OnSurface,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.weight(1f)
                )
                Spacer(Modifier.width(8.dp))
                // AI-APP-FIX-406：私有 StatusTag → 统一 WmsPillBadge
                WmsPillBadge(
                    text = if (isVoid) "已作废" else "已完成",
                    activeColor = if (isVoid) CardAmber else CardTeal
                )
            }

            Spacer(Modifier.height(8.dp))

            // 日期 / 仓库
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    record.date ?: "",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                if (!record.warehouse.isNullOrBlank()) {
                    Spacer(Modifier.width(10.dp))
                    Icon(
                        Icons.Filled.Info,
                        contentDescription = null,
                        modifier = Modifier.size(13.dp),
                        tint = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Spacer(Modifier.width(3.dp))
                    Text(
                        record.warehouse,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                }
            }

            Spacer(Modifier.height(8.dp))

            // 盘点条数 / 差异条数 / 批次
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    "盘点 ${record.itemCount ?: 0} 条",
                    style = MaterialTheme.typography.bodySmall,
                    color = OnSurface
                )
                Spacer(Modifier.width(12.dp))
                Text(
                    "差异 ${diff} 条",
                    style = MaterialTheme.typography.bodySmall,
                    fontWeight = if (diff > 0) FontWeight.SemiBold else FontWeight.Normal,
                    color = if (diff > 0) CardAmber else MaterialTheme.colorScheme.onSurfaceVariant
                )
                if (!record.batchNo.isNullOrBlank()) {
                    Spacer(Modifier.width(12.dp))
                    Text(
                        "批次 ${record.batchNo}",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                }
                // AI-APP-FIX-505：可下钻卡片给出箭头提示（点击卡片看差异明细）
                if (onClick != null) {
                    Spacer(Modifier.weight(1f))
                    Icon(
                        Icons.Filled.ChevronRight,
                        contentDescription = "查看差异明细",
                        modifier = Modifier.size(16.dp),
                        tint = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }

            // 采纳状态：批次是否完成 + 调整草稿审核结果
            if (!isVoid) {
                Spacer(Modifier.height(8.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        if (record.adjustmentStatus == "completed") {
                            Icons.Filled.CheckCircle
                        } else {
                            Icons.Filled.Info
                        },
                        contentDescription = null,
                        modifier = Modifier.size(14.dp),
                        tint = when (record.adjustmentStatus) {
                            "completed" -> CardTeal
                            "pending" -> CardAmber
                            else -> CardCyan
                        }
                    )
                    Spacer(Modifier.width(4.dp))
                    Text(
                        adoptionText(record),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }

            if (!record.createdAt.isNullOrBlank()) {
                Spacer(Modifier.height(4.dp))
                Text(
                    "提交时间 ${record.createdAt}",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
}

/** 采纳状态文案：把后端三个状态位翻译成作业员能看懂的一句话。 */
private fun adoptionText(record: StocktakeRecordDto): String = when {
    record.adjustmentStatus == "completed" -> "差异已审核，库存已调整"
    record.adjustmentStatus == "pending" -> "差异已生成调整草稿，等待审核"
    record.batchStatus == "pending" -> "已并入盘点批次，等待电脑端完成盘点"
    else -> "无差异，无需调整"
}

/**
 * AI-APP-FIX-505：盘点记录差异明细下钻对话框。
 *
 * 明细行由服务端按「差异行优先」排序；账面/实盘/差异三列右对齐等宽数字。
 * 加载中/加载失败都留在对话框内闭环（失败给重试），不吞成"点了没反应"。
 */
@Composable
private fun StocktakeRecordDetailDialog(
    detail: StocktakeRecordDetailData?,
    loading: Boolean,
    error: String?,
    onRetry: () -> Unit,
    onDismiss: () -> Unit
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        shape = RoundedCornerShape(20.dp),
        title = {
            Text(
                detail?.checkNo?.let { "盘点单 $it" } ?: "盘点明细",
                fontWeight = FontWeight.SemiBold,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis
            )
        },
        text = {
            when {
                loading -> Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(120.dp),
                    contentAlignment = Alignment.Center
                ) {
                    CircularProgressIndicator(color = Primary)
                }

                error != null -> Column(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    Text(
                        error,
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.error
                    )
                    Spacer(Modifier.height(12.dp))
                    TextButton(onClick = onRetry) { Text("重试") }
                }

                detail != null -> Column(modifier = Modifier.fillMaxWidth()) {
                    // 单头信息（备注限 2 行截断，防长备注撑破对话框）
                    val headerLine = listOfNotNull(
                        detail.date?.takeIf { it.isNotBlank() },
                        detail.warehouse?.takeIf { it.isNotBlank() }
                    ).joinToString(" · ")
                    if (headerLine.isNotBlank()) {
                        Text(
                            headerLine,
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis
                        )
                    }
                    if (!detail.remark.isNullOrBlank()) {
                        Spacer(Modifier.height(2.dp))
                        Text(
                            "备注：${detail.remark}",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            maxLines = 2,
                            overflow = TextOverflow.Ellipsis
                        )
                    }
                    Spacer(Modifier.height(10.dp))
                    if (detail.items.isEmpty()) {
                        Text(
                            "该单没有明细行",
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    } else {
                        // 限高内滚：明细可能几十行，对话框不能撑出屏幕
                        LazyColumn(
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(360.dp),
                            verticalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            items(
                                detail.items,
                                key = { "${it.materialCode}|${it.area}|${it.hashCode()}" }
                            ) { item ->
                                StocktakeRecordDetailRow(item)
                            }
                        }
                    }
                }
            }
        },
        confirmButton = {
            TextButton(onClick = onDismiss) { Text("关闭") }
        }
    )
}

/** 明细行：编码+名称（+规格/区域）｜账面 → 实盘 → 差异（差异行琥珀色高亮）。 */
@Composable
private fun StocktakeRecordDetailRow(item: StocktakeRecordDetailItemDto) {
    val isDiff = item.isDiff == true
    Surface(
        shape = RoundedCornerShape(10.dp),
        color = if (isDiff) CardAmber.copy(alpha = 0.08f)
        else MaterialTheme.colorScheme.surface
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 10.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    item.materialCode.orEmpty(),
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.SemiBold,
                    color = if (isDiff) CardAmber else Primary,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
                val subLine = listOfNotNull(
                    item.materialName?.takeIf { it.isNotBlank() },
                    item.spec?.takeIf { it.isNotBlank() }?.let { "规格 $it" },
                    item.area?.takeIf { it.isNotBlank() }?.let { "区域 $it" }
                ).joinToString(" · ")
                if (subLine.isNotBlank()) {
                    Text(
                        subLine,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                }
            }
            Spacer(Modifier.width(10.dp))
            val unit = item.unit.orEmpty()
            Column(horizontalAlignment = Alignment.End) {
                Text(
                    "账面 ${formatQty(item.systemStock ?: 0.0)}$unit → 实盘 ${formatQty(item.actualStock ?: 0.0)}$unit",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 1
                )
                val diff = item.difference ?: 0.0
                Text(
                    (if (diff > 0) "+" else "") + formatQty(diff),
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.Bold,
                    color = if (isDiff) CardAmber else MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 1
                )
            }
        }
    }
}

