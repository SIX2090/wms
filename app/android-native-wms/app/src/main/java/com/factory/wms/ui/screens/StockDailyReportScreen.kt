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
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.ChevronLeft
import androidx.compose.material.icons.filled.ChevronRight
import androidx.compose.material.icons.outlined.Inventory2
import androidx.compose.material.icons.outlined.Search
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarDuration
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.derivedStateOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.factory.wms.data.model.StockDailyItem
import com.factory.wms.ui.components.WarehouseSelector
import com.factory.wms.ui.components.WmsEmptyState
import com.factory.wms.ui.theme.Background
import com.factory.wms.ui.theme.Primary
import com.factory.wms.ui.theme.Success
import com.factory.wms.ui.viewmodel.report.StockDailyReportViewModel
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * 库存日报页（AI-MOB-RPT-F02）：按仓库查看当天各物料结存明细。
 * 服务端：GET /api/mobile/report/stock_daily（只读，零写操作）。
 *
 * AI-MOB-RPT-F03（需求 2026-09-17）：进入即自动展示所选仓**结存 > 0** 的
 * 全部物料（服务端过滤，无需搜索）；顶部日期可前后翻页回看历史某天收市结存
 * （流水回推），「回到今天」恢复今天模式。
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun StockDailyReportScreen(
    viewModel: StockDailyReportViewModel,
    onBack: () -> Unit
) {
    val uiState by viewModel.uiState.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }
    val listState = rememberLazyListState()

    // BUG-2026-08-24-006 模式：进入页面才加载（ViewModel 在 App 启动时即被创建）；
    // 先拉可选仓库（默认选中第一个真实仓并触发查询，见 loadWarehouses），
    // refresh 兜底覆盖「仓库列表已加载过」的再次进入场景。
    LaunchedEffect(Unit) {
        viewModel.loadWarehouses()
        viewModel.refresh()
    }

    LaunchedEffect(uiState.error) {
        uiState.error?.let {
            snackbarHostState.showSnackbar(it, duration = SnackbarDuration.Short)
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
            TopAppBar(
                title = {
                    Column {
                        Text("库存日报", fontWeight = FontWeight.Bold, fontSize = 20.sp)
                        Text(
                            "各物料每日结存 · 按仓展示",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(
                            Icons.Filled.ArrowBack,
                            "返回",
                            tint = MaterialTheme.colorScheme.onSurface
                        )
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.surface
                )
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .padding(padding)
                .fillMaxSize()
        ) {
            // ── 日期导航（AI-MOB-RPT-F03：可翻日期看历史收市结存）──
            // 「后一天」在到达今天后禁用（服务端对未来日期 400，此处前置钳制）；
            // 历史日期「数据截至」显示 23:59（收市语义），今天显示当前时刻。
            val todayStr = SimpleDateFormat("yyyy-MM-dd", Locale.US).format(Date())
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
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 4.dp, vertical = 2.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    IconButton(onClick = { viewModel.shiftDay(-1) }) {
                        Icon(Icons.Filled.ChevronLeft, "前一天")
                    }
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Text(
                            uiState.date,
                            fontWeight = FontWeight.SemiBold,
                            fontSize = 16.sp
                        )
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(
                                "数据截至 ${uiState.generatedAt ?: "--:--"}",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                            TextButton(onClick = { viewModel.resetToday() }) {
                                Text("回到今天", fontSize = 12.sp)
                            }
                        }
                    }
                    IconButton(
                        onClick = { viewModel.shiftDay(1) },
                        enabled = uiState.date < todayStr
                    ) {
                        Icon(Icons.Filled.ChevronRight, "后一天")
                    }
                }
            }

            // ── 仓库选择（必填，只列真实仓库；结存跨仓无意义，不提供"全部仓库"）──
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

            // ── 搜索行（编码/名称/规格模糊）──
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
                        StockDailySummaryCell("物料", "${summary.totalMaterials}")
                        StockDailySummaryCell("有库存", "${summary.inStockMaterials}")
                        StockDailySummaryCell("零库存", "${summary.zeroMaterials}")
                        StockDailySummaryCell("合计数量", formatStockQty(summary.totalQuantity))
                    }
                }
                Spacer(modifier = Modifier.height(10.dp))
            }

            // ── 明细列表 / 加载 / 空态 ──
            Box(modifier = Modifier.fillMaxSize()) {
                when {
                    uiState.isLoading -> {
                        CircularProgressIndicator(
                            modifier = Modifier.align(Alignment.Center)
                        )
                    }
                    uiState.queried && uiState.items.isEmpty() -> {
                        // F03 起明细只出结存 > 0：空态须区分「该仓当天无结存物料」
                        // 与「被关键词滤掉」，不再笼统说"物料档案为空"
                        WmsEmptyState(
                            icon = Icons.Outlined.Inventory2,
                            title = if (uiState.keyword.isBlank()) "该仓当天无结存物料" else "未找到匹配物料",
                            subtitle = if (uiState.keyword.isBlank()) {
                                "该仓没有库存大于 0 的物料\n（可换个仓库，或翻日期回看历史结存）"
                            } else {
                                "「${uiState.keyword}」在该仓无匹配，换个关键词试试"
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
                                StockDailyItemRow(item)
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
                                        textAlign = androidx.compose.ui.text.style.TextAlign.Center
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
private fun StockDailySummaryCell(label: String, value: String) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Text(
            value,
            fontWeight = FontWeight.Bold,
            fontSize = 16.sp,
            color = Primary
        )
        Text(
            label,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
    }
}

@Composable
private fun StockDailyItemRow(item: StockDailyItem) {
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
                    "${item.name}（${item.code}）",
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
                val meta = listOfNotNull(
                    item.category?.takeIf { it.isNotBlank() },
                    item.brand?.takeIf { it.isNotBlank() }
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
            // 结存：零库存用弱化色，区别于有库存
            Text(
                "${formatStockQty(item.stock)} ${item.unit.orEmpty()}".trim(),
                fontWeight = FontWeight.Bold,
                fontSize = 15.sp,
                color = if (item.stock == 0.0) {
                    MaterialTheme.colorScheme.onSurfaceVariant
                } else {
                    Success
                }
            )
        }
    }
}

/** 数量格式化：整数不带小数点，小数保留两位（与每日报表同规则） */
private fun formatStockQty(value: Double): String {
    return if (value % 1.0 == 0.0) {
        String.format(Locale.US, "%.0f", value)
    } else {
        String.format(Locale.US, "%.2f", value)
    }
}
