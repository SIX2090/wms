package com.factory.wms.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ChevronLeft
import androidx.compose.material.icons.filled.ChevronRight
import androidx.compose.material.icons.outlined.MenuBook
import androidx.compose.material.icons.outlined.Search
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
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
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.factory.wms.data.model.MaterialDto
import com.factory.wms.data.model.StockLedgerItem
import com.factory.wms.ui.components.WarehouseSelector
import com.factory.wms.ui.components.WmsEmptyState
import com.factory.wms.ui.components.WmsErrorState
import com.factory.wms.ui.components.WmsListSkeleton
import com.factory.wms.ui.components.WmsPullToRefreshBox
import com.factory.wms.ui.components.WmsTopBar
import com.factory.wms.ui.util.formatQty
import com.factory.wms.ui.theme.Background
import com.factory.wms.ui.theme.Error
import com.factory.wms.ui.theme.Primary
import com.factory.wms.ui.theme.Success
import com.factory.wms.ui.theme.Warning
import com.factory.wms.ui.viewmodel.report.InOutDetailDateLogic
import com.factory.wms.ui.viewmodel.report.StockLedgerRangeLogic
import com.factory.wms.ui.viewmodel.report.StockLedgerReportViewModel
import java.util.Calendar

/**
 * 库存台账页（AI-MOB-LDG-F01）。
 * 服务端：GET /api/mobile/report/stock_ledger（只读，零写操作）。
 *
 * 按仓库（必填，AGENTS.md §二）+ 单一物料（必填，与电脑端库存台账同口径，
 * AI-OS-LD-001）查看库存流水账：期初结存 → 逐笔入/出 → 行级结存 → 期末结存。
 * 默认全部流水（用户决策口径：start_date 缺省 = 从建账起算），可翻日期收窄范围；
 * 汇总卡基于过滤后全集、与分页解耦（R1）；滚动到底自动翻页。
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun StockLedgerReportScreen(
    viewModel: StockLedgerReportViewModel,
    onBack: () -> Unit
) {
    val uiState by viewModel.uiState.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }
    val listState = rememberLazyListState()
    var showMaterialPicker by remember { mutableStateOf(false) }

    // BUG-2026-08-24-006 模式：进入页面才加载（ViewModel 在 App 启动时即被创建）；
    // 只预载仓库列表——物料未选定前不发起台账查询（单一物料口径）。
    LaunchedEffect(Unit) {
        viewModel.loadWarehouses()
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
            // AI-APP-FIX-401：自绘 TopAppBar → 统一 WmsTopBar（含状态栏图标处理）
            WmsTopBar(
                title = "库存台账",
                subtitle = "单物料流水 · 按仓展示",
                onBack = onBack
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .padding(padding)
                .fillMaxSize()
        ) {
            // ── 仓库选择（必填，只列真实仓库；与出入库明细/库存日报同模式）──
            WarehouseSelector(
                currentLabel = null,
                warehouses = uiState.warehouses,
                selectedId = uiState.selectedWarehouseId,
                onSelect = { viewModel.selectWarehouse(it) },
                showDefaultWarehouse = false,
                allowAll = false,
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp)
            )

            // ── 物料选择卡（台账按单一物料查询，AI-OS-LD-001 口径）──
            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 8.dp)
                    .clickable { showMaterialPicker = true },
                shape = RoundedCornerShape(14.dp),
                colors = CardDefaults.cardColors(
                    containerColor = MaterialTheme.colorScheme.surface
                ),
                elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 14.dp, vertical = 12.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Column(modifier = Modifier.weight(1f)) {
                        val m = uiState.selectedMaterial
                        if (m == null) {
                            Text(
                                "点击选择物料",
                                fontWeight = FontWeight.SemiBold,
                                fontSize = 15.sp,
                                color = Primary
                            )
                            Text(
                                "库存台账按单一物料查询",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        } else {
                            Text(
                                "${m.name.orEmpty()}（${m.code.orEmpty()}）",
                                fontWeight = FontWeight.SemiBold,
                                fontSize = 15.sp,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis
                            )
                            val sub = listOfNotNull(
                                m.spec?.takeIf { it.isNotBlank() },
                                uiState.material?.warehouseStock?.let {
                                    "本仓结存 " + formatQty(it)
                                }
                            ).joinToString(" · ")
                            if (sub.isNotBlank()) {
                                Text(
                                    sub,
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                    maxLines = 1,
                                    overflow = TextOverflow.Ellipsis
                                )
                            }
                        }
                    }
                    if (uiState.selectedMaterial != null) {
                        TextButton(onClick = { viewModel.clearMaterial() }) {
                            Text("换物料", fontSize = 12.sp)
                        }
                    } else {
                        Icon(Icons.Outlined.Search, "选择物料", tint = Primary)
                    }
                }
            }

            // ── 日期范围（默认全部流水；开始空白=全部，结束空白=今天）──
            val todayStr = remember { InOutDetailDateLogic.today() }
            val context = LocalContext.current
            // AI-MOB-LDG-F02：除「±1 天翻」外，点日期文本弹系统日期选择器自由选某天。
            // 用系统 android.app.DatePickerDialog（日历视图），不改动 OpeningStock 自绘选择器；
            // 选定后经 ViewModel.setStartDate/setEndDate 钳制生效（防 start>end / end>今天 400）。
            val openLedgerDatePicker: (Boolean) -> Unit = { isStart ->
                val current = if (isStart) uiState.startDate.ifBlank { todayStr } else uiState.endDate.ifBlank { todayStr }
                val cal = Calendar.getInstance()
                try {
                    val p = current.split("-")
                    if (p.size == 3) cal.set(p[0].toInt(), p[1].toInt() - 1, p[2].toInt())
                } catch (_: Exception) { }
                android.app.DatePickerDialog(
                    context,
                    { _, y, m, d ->
                        val picked = "%04d-%02d-%02d".format(y, m + 1, d)
                        if (isStart) viewModel.setStartDate(picked) else viewModel.setEndDate(picked)
                    },
                    cal.get(Calendar.YEAR), cal.get(Calendar.MONTH), cal.get(Calendar.DAY_OF_MONTH)
                ).show()
            }
            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp),
                shape = RoundedCornerShape(14.dp),
                colors = CardDefaults.cardColors(
                    containerColor = MaterialTheme.colorScheme.surface
                ),
                elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
            ) {
                Column(modifier = Modifier.fillMaxWidth().padding(vertical = 2.dp)) {
                    LedgerDateNavRow(
                        label = "开始",
                        date = StockLedgerRangeLogic.displayStart(uiState.startDate),
                        onPrev = { viewModel.shiftStartDay(-1) },
                        onNext = { viewModel.shiftStartDay(1) },
                        nextEnabled = uiState.startDate.isNotBlank() &&
                            uiState.startDate < StockLedgerRangeLogic.displayEnd(uiState.endDate, todayStr),
                        onDateClick = { openLedgerDatePicker(true) },
                        trailing = {
                            TextButton(onClick = { viewModel.resetAllDates() }) {
                                Text("全部流水", fontSize = 12.sp)
                            }
                        }
                    )
                    LedgerDateNavRow(
                        label = "结束",
                        date = StockLedgerRangeLogic.displayEnd(uiState.endDate, todayStr),
                        onPrev = { viewModel.shiftEndDay(-1) },
                        onNext = { viewModel.shiftEndDay(1) },
                        // 结束日期后翻不能越过今天
                        nextEnabled = StockLedgerRangeLogic.displayEnd(uiState.endDate, todayStr) < todayStr,
                        onDateClick = { openLedgerDatePicker(false) }
                    )
                }
            }

            Spacer(modifier = Modifier.height(8.dp))

            // ── 汇总卡（期初/入/出/期末，基于过滤后全集，不随分页缩小，R1）──
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
                            .padding(horizontal = 8.dp, vertical = 12.dp),
                        horizontalArrangement = Arrangement.SpaceEvenly
                    ) {
                        LedgerSummaryCell("期初", formatQty(summary.openingBalance))
                        LedgerSummaryCell("入库", formatQty(summary.totalInQuantity), Success)
                        LedgerSummaryCell("出库", formatQty(summary.totalOutQuantity), Error)
                        LedgerSummaryCell("期末结存", formatQty(summary.endingBalance), Primary)
                    }
                }
                if (uiState.truncated) {
                    Text(
                        "流水过多，结果已被服务端截断，请缩小日期范围",
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 20.dp, vertical = 4.dp),
                        style = MaterialTheme.typography.bodySmall,
                        color = Warning
                    )
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
                    uiState.selectedMaterial == null && !uiState.isLoading -> {
                        // 引导空态：台账按单一物料查询，先选物料
                        WmsEmptyState(
                            icon = Icons.Outlined.MenuBook,
                            title = "请先选择物料",
                            subtitle = "点击上方卡片搜索并选择物料，查看它的库存流水账",
                            modifier = Modifier.align(Alignment.Center)
                        )
                    }
                    // AI-APP-FIX-202：首屏（列表为空）转圈 → 骨架列表
                    uiState.isLoading && uiState.items.isEmpty() -> {
                        WmsListSkeleton(modifier = Modifier.align(Alignment.TopCenter))
                    }
                    // AI-APP-FIX-201：首屏查询失败 → 全屏错误态 + 重试，
                    // 不再静默落入"尚未查询"的空白等待（注意必须排在 !queried 分支前）
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
                        WmsEmptyState(
                            icon = Icons.Outlined.MenuBook,
                            title = "该范围内无库存流水",
                            subtitle = "可换个仓库/物料，或点「全部流水」扩大范围",
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
                            // 流水行无服务端 id（marker 行已剔除），用索引键保证稳定
                            itemsIndexed(
                                uiState.items,
                                key = { index, item -> "${item.date}_${item.referenceNo}_$index" }
                            ) { _, item ->
                                StockLedgerItemRow(item)
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

    // ── 物料搜索对话框（走既有 /api/material/search，点选即查询台账）──
    if (showMaterialPicker) {
        AlertDialog(
            onDismissRequest = { showMaterialPicker = false },
            title = { Text("选择物料") },
            text = {
                Column(modifier = Modifier.fillMaxWidth()) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        OutlinedTextField(
                            value = uiState.materialKeyword,
                            onValueChange = { viewModel.updateMaterialKeyword(it) },
                            modifier = Modifier.weight(1f),
                            placeholder = { Text("编码 / 名称 / 规格 / 品牌") },
                            singleLine = true,
                            shape = RoundedCornerShape(12.dp)
                        )
                        IconButton(onClick = { viewModel.searchMaterials() }) {
                            Icon(Icons.Outlined.Search, "搜索", tint = Primary)
                        }
                    }
                    Spacer(modifier = Modifier.height(8.dp))
                    when {
                        uiState.materialSearching -> {
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(vertical = 16.dp),
                                horizontalArrangement = Arrangement.Center
                            ) {
                                CircularProgressIndicator(
                                    modifier = Modifier.width(24.dp).height(24.dp),
                                    strokeWidth = 2.dp
                                )
                            }
                        }
                        uiState.materialSuggestions.isEmpty() -> {
                            Text(
                                "输入关键词搜索物料",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                modifier = Modifier.padding(vertical = 8.dp)
                            )
                        }
                        else -> {
                            LazyColumn(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .heightIn(max = 360.dp)
                            ) {
                                items(
                                    uiState.materialSuggestions,
                                    key = { it.id ?: it.code.hashCode() }
                                ) { candidate ->
                                    MaterialCandidateRow(candidate) {
                                        showMaterialPicker = false
                                        viewModel.selectMaterial(candidate)
                                    }
                                }
                            }
                        }
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = { showMaterialPicker = false }) {
                    Text("关闭")
                }
            }
        )
    }
}

@Composable
private fun MaterialCandidateRow(material: MaterialDto, onClick: () -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(vertical = 10.dp, horizontal = 4.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(
                "${material.name.orEmpty()}（${material.code.orEmpty()}）",
                fontWeight = FontWeight.SemiBold,
                fontSize = 14.sp,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis
            )
            val sub = listOfNotNull(
                material.spec?.takeIf { it.isNotBlank() },
                material.brand?.takeIf { it.isNotBlank() }
            ).joinToString(" · ")
            if (sub.isNotBlank()) {
                Text(
                    sub,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
            }
        }
    }
}

@Composable
private fun LedgerDateNavRow(
    label: String,
    date: String,
    onPrev: () -> Unit,
    onNext: () -> Unit,
    nextEnabled: Boolean,
    onDateClick: () -> Unit,
    trailing: (@Composable () -> Unit)? = null
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        IconButton(onClick = onPrev) {
            // 注意：必须用 ${label}——"$label前一天" 会被 Kotlin 解析成
            // 标识符 `label前一天`（中文是合法标识符字符）→ 编译期 Unresolved reference。
            Icon(Icons.Filled.ChevronLeft, "${label}前一天")
        }
        // 日期文本可点（onDateClick 弹日期选择器）；点击涟漪提示可选。
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            modifier = Modifier.clickable(onClick = onDateClick)
        ) {
            Text(
                date,
                fontWeight = FontWeight.SemiBold,
                fontSize = 16.sp,
                color = Primary
            )
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    "${label}日期",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                trailing?.invoke()
            }
        }
        IconButton(onClick = onNext, enabled = nextEnabled) {
            Icon(Icons.Filled.ChevronRight, "${label}后一天")
        }
    }
}

@Composable
private fun LedgerSummaryCell(
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
private fun StockLedgerItemRow(item: StockLedgerItem) {
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
                // 单据类型 + 单号（台账溯源主信息）
                Text(
                    listOfNotNull(
                        item.referenceType?.takeIf { it.isNotBlank() },
                        item.referenceNo?.takeIf { it.isNotBlank() }
                    ).joinToString(" · ").ifBlank { "库存流水" },
                    fontWeight = FontWeight.SemiBold,
                    fontSize = 15.sp,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
                // 日期 + 操作人 + 库位 + 备注（可空字段逐项判空拼接）
                val meta = listOfNotNull(
                    item.date?.takeIf { it.isNotBlank() },
                    item.operator?.takeIf { it.isNotBlank() },
                    item.location?.takeIf { it.isNotBlank() }?.let { "库位 $it" },
                    item.remark?.takeIf { it.isNotBlank() }
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
            // 入/出量 + 行后结存（台账核心：running balance）
            // AI-APP-FIX-403：数字列单行省略 + tnum 等宽数字（本列已右对齐）
            Column(horizontalAlignment = Alignment.End) {
                val hasIn = item.inQuantity > 0
                val hasOut = item.outQuantity > 0
                Text(
                    when {
                        hasIn -> "+" + formatQty(item.inQuantity)
                        hasOut -> "-" + formatQty(item.outQuantity)
                        else -> "—"
                    },
                    fontWeight = FontWeight.Bold,
                    fontSize = 15.sp,
                    style = LocalTextStyle.current.copy(fontFeatureSetting = "tnum"),
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    color = if (hasOut && !hasIn) Error else Success
                )
                Text(
                    "结存 " + formatQty(item.balanceQuantity),
                    style = MaterialTheme.typography.bodySmall.copy(fontFeatureSetting = "tnum"),
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
}
