package com.factory.wms.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.ReceiptLong
import androidx.compose.material.icons.outlined.Search
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LocalTextStyle
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarDuration
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.derivedStateOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.factory.wms.data.model.InOutDetailItem
import com.factory.wms.ui.components.WarehouseSelector
import com.factory.wms.ui.components.WmsDateNavRow
import com.factory.wms.ui.components.WmsEmptyState
import com.factory.wms.ui.components.WmsErrorState
import com.factory.wms.ui.components.WmsListSkeleton
import com.factory.wms.ui.components.WmsPullToRefreshBox
import com.factory.wms.ui.components.WmsTopBar
import com.factory.wms.ui.util.formatQty
import com.factory.wms.ui.theme.WmsDimens
import com.factory.wms.ui.theme.Background
import com.factory.wms.ui.theme.Error
import com.factory.wms.ui.theme.Primary
import com.factory.wms.ui.theme.Success
import com.factory.wms.ui.viewmodel.report.InOutDetailDateLogic
import com.factory.wms.ui.viewmodel.report.InOutDetailReportViewModel
import com.factory.wms.ui.viewmodel.report.InOutDirection
import java.util.Locale

/**
 * 出入库明细页（AI-MOB-RPT-F01 收尾：Android 消费页）。
 * 服务端：GET /api/mobile/report/in_out_detail（只读，零写操作）。
 *
 * 按仓库（必填，AGENTS.md §二）查看日期范围内的出入库流水：
 * 开始/结束日期均可前后翻（结束日期上限今天，开始日期不越过结束日期，
 * 服务端 400 前置钳制）；方向过滤 全部/入库/出库；keyword 搜索编码/名称/规格；
 * 汇总卡基于过滤后全集、与分页解耦（R1）；滚动到底自动翻页。
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun InOutDetailReportScreen(
    viewModel: InOutDetailReportViewModel,
    onBack: () -> Unit
) {
    val uiState by viewModel.uiState.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }
    val listState = rememberLazyListState()

    // BUG-2026-08-24-006 模式：进入页面才加载（ViewModel 在 App 启动时即被创建）；
    // loadWarehouses 默认选中第一个真实仓并触发查询（与库存日报同模式）。
    LaunchedEffect(Unit) {
        viewModel.loadWarehouses()
        viewModel.refresh()
    }

    LaunchedEffect(uiState.error) {
        uiState.error?.let {
            // AI-APP-FIX-201：此处只剩"带数据刷新/翻页失败"的瞬态错误（首屏失败
            // 走 loadError 全屏错误态），Snackbar 加长避免现场没看清就消失。
            snackbarHostState.showSnackbar(it, duration = SnackbarDuration.Long)
            viewModel.clearError()
        }
    }

    // 滚动接近底部（倒数第 3 行进入可视区）自动翻页
    val shouldLoadMore by remember {
        derivedStateOf {
            val info = listState.layoutInfo
            val lastVisible = info.visibleItemsInfo.lastOrNull()?.index ?: 0
            info.totalItemsCount > 0 && lastVisible >= info.totalItemsCount - 3
        }
    }
    LaunchedEffect(shouldLoadMore) {
        if (shouldLoadMore) viewModel.loadMore()
    }

    Scaffold(
        snackbarHost = { SnackbarHost(snackbarHostState) },
        containerColor = Background,
        topBar = {
            // AI-APP-FIX-401：自绘 TopAppBar → 统一 WmsTopBar
            WmsTopBar(
                title = "出入库明细",
                subtitle = "日期范围流水 · 按仓展示",
                onBack = onBack
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .padding(padding)
                .fillMaxSize()
        ) {
            // ── 日期范围导航（开始/结束各自前后翻；钳制逻辑在 ViewModel，
            //    开始不越过结束、结束不超过今天——服务端 400 前置钳制）──
            val todayStr = remember { InOutDetailDateLogic.today() }
            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 8.dp),
                shape = RoundedCornerShape(14.dp),
                colors = CardDefaults.cardColors(
                    containerColor = MaterialTheme.colorScheme.surface
                ),
                elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
            ) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 2.dp)
                ) {
                    // AI-APP-FIX-402：开始/结束两行共用 WmsDateNavRow（wrapInCard=false），
                    // 日期可点弹 DatePicker 直接跳日；钳制逻辑在 ViewModel
                    WmsDateNavRow(
                        label = "开始",
                        date = uiState.startDate,
                        onPrev = { viewModel.shiftStartDay(-1) },
                        onNext = { viewModel.shiftStartDay(1) },
                        // 开始日期后翻不能越过结束日期
                        nextEnabled = uiState.startDate < uiState.endDate,
                        wrapInCard = false,
                        onDateSelected = { viewModel.setStartDate(it) }
                    )
                    WmsDateNavRow(
                        label = "结束",
                        date = uiState.endDate,
                        onPrev = { viewModel.shiftEndDay(-1) },
                        onNext = { viewModel.shiftEndDay(1) },
                        // 结束日期后翻不能越过今天
                        nextEnabled = uiState.endDate < todayStr,
                        wrapInCard = false,
                        onResetToday = { viewModel.resetToday() },
                        onDateSelected = { viewModel.setEndDate(it) }
                    )
                }
            }

            // ── 仓库选择（必填，只列真实仓库；与每日报表/库存日报同模式）──
            WarehouseSelector(
                currentLabel = null,
                warehouses = uiState.warehouses,
                selectedId = uiState.selectedWarehouseId,
                onSelect = { viewModel.selectWarehouse(it) },
                showDefaultWarehouse = false,
                allowAll = false,
                modifier = Modifier.padding(horizontal = 16.dp)
            )

            Spacer(modifier = Modifier.height(8.dp))

            // ── 方向过滤（全部/入库/出库，与每日报表类型切换同模式）──
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp),
                horizontalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                InOutDirection.values().forEach { dir ->
                    FilterChip(
                        selected = uiState.direction == dir,
                        onClick = { viewModel.selectDirection(dir) },
                        label = { Text(dir.label) },
                        modifier = Modifier.weight(1f).height(WmsDimens.TouchTargetMin)
                    )
                }
            }

            Spacer(modifier = Modifier.height(8.dp))

            // ── 搜索行（编码/名称/规格模糊；点搜索才发请求）──
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                OutlinedTextField(
                    value = uiState.keyword,
                    onValueChange = { viewModel.updateKeyword(it) },
                    modifier = Modifier.weight(1f),
                    placeholder = { Text("搜索编码 / 名称 / 规格") },
                    singleLine = true,
                    shape = RoundedCornerShape(12.dp)
                )
                IconButton(onClick = { viewModel.refresh() }) {
                    Icon(Icons.Outlined.Search, "搜索", tint = Primary)
                }
            }

            Spacer(modifier = Modifier.height(8.dp))

            // ── 汇总卡（基于过滤后全集，不随分页缩小，R1）──
            uiState.summary?.let { summary ->
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 16.dp),
                    shape = RoundedCornerShape(14.dp),
                    colors = CardDefaults.cardColors(
                        containerColor = Primary.copy(alpha = 0.08f)
                    ),
                    elevation = CardDefaults.cardElevation(defaultElevation = 0.dp)
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 12.dp, vertical = 12.dp),
                        horizontalArrangement = Arrangement.SpaceEvenly
                    ) {
                        InOutSummaryCell("笔数", "${summary.totalCount}")
                        InOutSummaryCell("入库合计", formatQty(summary.totalInQuantity), Success)
                        InOutSummaryCell("出库合计", formatQty(summary.totalOutQuantity), Error)
                    }
                }
                Spacer(modifier = Modifier.height(10.dp))
            }

            // ── 明细列表 / 加载 / 空态 / 错误态 ──
            // AI-APP-FIX-505：下拉刷新统一（各状态分支都可下拉重查；
            // 仅"带数据刷新"亮指示器，首屏仍走骨架屏）
            WmsPullToRefreshBox(
                isRefreshing = uiState.isLoading && uiState.items.isNotEmpty(),
                onRefresh = { viewModel.refresh() },
                modifier = Modifier.fillMaxSize()
            ) {
                when {
                    // AI-APP-FIX-202：首屏（列表为空）转圈 → 骨架列表；
                    // 带数据刷新保留旧列表 + 居中转圈，不闪骨架。
                    uiState.isLoading && uiState.items.isEmpty() -> {
                        WmsListSkeleton(modifier = Modifier.align(Alignment.TopCenter))
                    }
                    // AI-APP-FIX-201：首屏加载失败 → 全屏错误态 + 重试，
                    // 不再落入下方"该范围内无出入库流水"的误导性空态
                    uiState.loadError != null && uiState.items.isEmpty() -> {
                        WmsErrorState(
                            title = "加载失败",
                            subtitle = uiState.loadError ?: "请检查网络后重试",
                            modifier = Modifier.align(Alignment.Center),
                            onRetry = { viewModel.refresh() }
                        )
                    }
                    uiState.isLoading -> {
                        CircularProgressIndicator(
                            modifier = Modifier.align(Alignment.Center)
                        )
                    }
                    uiState.queried && uiState.items.isEmpty() -> {
                        // 区分「该范围内无流水」与「被关键词/方向滤掉」两种空态
                        val filtered = uiState.keyword.isNotBlank() ||
                            uiState.direction != InOutDirection.ALL
                        WmsEmptyState(
                            icon = Icons.Outlined.ReceiptLong,
                            title = if (filtered) "未找到匹配流水" else "该范围内无出入库流水",
                            subtitle = if (filtered) {
                                "换个关键词或方向条件试试"
                            } else {
                                "可换个仓库，或翻日期扩大范围"
                            },
                            modifier = Modifier.align(Alignment.Center)
                        )
                    }
                    !uiState.queried -> {
                        // 尚未查询（仓库列表未就绪）：不显示误导性空态，安静等待
                    }
                    else -> {
                        LazyColumn(
                            state = listState,
                            modifier = Modifier.fillMaxSize(),
                            contentPadding = PaddingValues(horizontal = 16.dp, vertical = 4.dp),
                            verticalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            items(uiState.items, key = { it.id }) { item ->
                                InOutDetailItemRow(item)
                            }
                            if (uiState.isLoadingMore) {
                                item {
                                    Row(
                                        modifier = Modifier
                                            .fillMaxWidth()
                                            .padding(vertical = 8.dp),
                                        horizontalArrangement = Arrangement.Center
                                    ) {
                                        CircularProgressIndicator(
                                            modifier = Modifier.width(24.dp).height(24.dp),
                                            strokeWidth = 2.dp
                                        )
                                    }
                                }
                            } else if (!uiState.hasMore && uiState.items.isNotEmpty()) {
                                item {
                                    Text(
                                        "已加载全部 ${uiState.items.size} 条",
                                        modifier = Modifier
                                            .fillMaxWidth()
                                            .padding(vertical = 8.dp),
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                                        textAlign = TextAlign.Center
                                    )
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun InOutSummaryCell(
    label: String,
    value: String,
    valueColor: androidx.compose.ui.graphics.Color = Primary
) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Text(
            value,
            fontWeight = FontWeight.Bold,
            fontSize = 16.sp,
            color = valueColor
        )
        Text(
            label,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
    }
}

@Composable
private fun InOutDetailItemRow(item: InOutDetailItem) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surface
        ),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 14.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    "${item.materialName.orEmpty()}（${item.materialCode.orEmpty()}）",
                    fontWeight = FontWeight.SemiBold,
                    fontSize = 15.sp,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
                // spec 可空（BUG-2026-08-24-007），必须 isNullOrBlank 判空
                if (!item.spec.isNullOrBlank()) {
                    Text(
                        item.spec,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                }
                // 类型标签 + 时间 + 操作人 + 库位（可空字段逐项判空拼接）
                val meta = listOfNotNull(
                    item.transactionTypeLabel?.takeIf { it.isNotBlank() },
                    item.createdAt?.takeIf { it.isNotBlank() },
                    item.operator?.takeIf { it.isNotBlank() },
                    item.location?.takeIf { it.isNotBlank() }?.let { "库位 $it" }
                ).joinToString(" · ")
                if (meta.isNotBlank()) {
                    Text(
                        meta,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                }
            }
            Spacer(modifier = Modifier.width(8.dp))
            // 带符号数量：入库 +绿 / 出库 -红（direction 与服务端口径一致）
            val isOut = item.direction == "out" || item.quantity < 0
            val qtyText = (if (isOut) "-" else "+") +
                formatQty(kotlin.math.abs(item.quantity)) +
                (item.unit?.takeIf { it.isNotBlank() }?.let { " $it" } ?: "")
            Text(
                qtyText,
                fontWeight = FontWeight.Bold,
                fontSize = 15.sp,
                // AI-APP-FIX-403：数字列单行省略 + 固定右栏宽 + tnum 等宽数字
                style = LocalTextStyle.current.copy(fontFeatureSetting = "tnum"),
                textAlign = TextAlign.End,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
                modifier = Modifier.width(110.dp),
                color = if (isOut) Error else Success
            )
        }
    }
}

// AI-APP-FIX-403：数量格式化统一为 ui/util/Format.kt 的 formatQty（千分位）
