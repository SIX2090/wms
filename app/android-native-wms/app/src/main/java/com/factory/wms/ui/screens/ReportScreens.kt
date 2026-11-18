package com.factory.wms.ui.screens

import com.factory.wms.ui.components.WmsCard
import com.factory.wms.ui.theme.readableOn
import androidx.compose.ui.graphics.compositeOver
import com.factory.wms.data.model.DailyReportSummary
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.sizeIn
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.ReceiptLong
import androidx.compose.material.icons.outlined.Refresh
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LocalTextStyle
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarDuration
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.factory.wms.data.model.DailyReportData
import com.factory.wms.data.model.DailyReportItem
import com.factory.wms.ui.components.WmsAdaptiveRecord
import com.factory.wms.ui.components.WarehouseSelector
import com.factory.wms.ui.components.WmsDateNavRow
import com.factory.wms.ui.components.WmsEmptyState
import com.factory.wms.ui.components.WmsErrorState
import com.factory.wms.ui.components.WmsListSkeleton
import com.factory.wms.ui.components.WmsTopBar
import com.factory.wms.ui.util.formatQty
import com.factory.wms.ui.util.quantityDisplayText
import com.factory.wms.ui.theme.WmsDimens
import com.factory.wms.ui.theme.Background
import com.factory.wms.ui.theme.Primary
import com.factory.wms.ui.viewmodel.report.ReportType
import com.factory.wms.ui.viewmodel.report.ReportViewModel
import java.util.Locale
/**
 * 每日明细报表页：按日期查看采购入库 / 领料单明细。
 * 服务端：GET /api/mobile/report/daily_detail
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DailyReportScreen(
    viewModel: ReportViewModel,
    onBack: () -> Unit
) {
    val uiState by viewModel.uiState.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }
    // BUG-2026-08-24-006：进入报表页时才加载（ViewModel 在 App 启动时即被创建，
    // 不能依赖 init 加载）；再次进入也会按当前日期/类型刷新，保证数据不过期。
    LaunchedEffect(Unit) {
        // ViewModel 内先确定仓库，再查报表；只列真实仓库。
        viewModel.load()
    }
    LaunchedEffect(uiState.error) {
        uiState.error?.let {
            // AI-APP-FIX-201：此处只剩"带数据刷新失败"的瞬态错误（首屏失败走
            // loadError 全屏错误态），Snackbar 加长避免现场没看清就消失。
            snackbarHostState.showSnackbar(it, duration = SnackbarDuration.Long)
            viewModel.clearError()
        }
    }
    Scaffold(
        snackbarHost = { SnackbarHost(snackbarHostState) },
        containerColor = Background,
        topBar = {
            // AI-APP-FIX-206：统一共享顶栏（状态栏图标适配），补手动刷新入口
            WmsTopBar(
                title = "每日报表",
                subtitle = "采购入库 · 领料单明细",
                onBack = onBack,
                actions = {
                    IconButton(onClick = { viewModel.load() }, enabled = !uiState.isLoading, modifier = Modifier.sizeIn(minWidth = 48.dp, minHeight = 48.dp)) {
                        Icon(
                            Icons.Outlined.Refresh,
                            "刷新",
                            tint = MaterialTheme.colorScheme.onSurface
                        )
                    }
                }
            )
        }
    ) { padding ->
        // 筛选、汇总与明细共用一个滚动面，大字体时仍能到达明细及日期操作。
        LazyColumn(
            modifier = Modifier.padding(padding).fillMaxSize(),
            contentPadding = PaddingValues(bottom = 16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            item(key = "filters") {
                Column {
                    WmsDateNavRow(
                        date = uiState.date,
                        onPrev = { viewModel.shiftDay(-1) }, onNext = { viewModel.shiftDay(1) },
                        nextEnabled = uiState.date < viewModel.today(),
                        onResetToday = { viewModel.resetToday() }, onDateSelected = { viewModel.setDate(it) }
                    )
                    Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        ReportType.values().forEach { type ->
                            FilterChip(selected = uiState.reportType == type,
                                onClick = { viewModel.selectType(type) }, label = { Text(type.label) },
                                colors = FilterChipDefaults.filterChipColors(
                                    selectedContainerColor = MaterialTheme.colorScheme.tertiaryContainer,
                                    selectedLabelColor = MaterialTheme.colorScheme.onTertiaryContainer
                                ),
                                modifier = Modifier.weight(1f).heightIn(min = WmsDimens.TouchTargetMin))
                        }
                    }
                    WarehouseSelector(
                        currentLabel = uiState.report?.warehouse, warehouses = uiState.warehouses,
                        selectedId = uiState.selectedWarehouseId, onSelect = { viewModel.selectWarehouse(it) },
                        showDefaultWarehouse = false, allowAll = false, modifier = Modifier.padding(horizontal = 16.dp)
                    )
                }
            }
            uiState.report?.let { report ->
                item(key = "summary") {
                    Card(Modifier.fillMaxWidth().padding(horizontal = 16.dp), shape = MaterialTheme.shapes.medium,
                        colors = CardDefaults.cardColors(
                            containerColor = Primary.copy(alpha = 0.08f).compositeOver(MaterialTheme.colorScheme.background)
                        )) { DailyReportSummaryContent(report.summary) }
                }
            }
            when {
                uiState.isLoading && uiState.report == null -> item(key = "loading") { WmsListSkeleton() }
                uiState.loadError != null && uiState.report == null -> item(key = "error") {
                    WmsErrorState(title = "加载失败", subtitle = uiState.loadError ?: "请检查网络后重试",
                        onRetry = { viewModel.load() })
                }
                uiState.isLoading -> item(key = "refreshing") {
                    Box(Modifier.fillMaxWidth().padding(24.dp), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
                }
                uiState.report?.items?.isEmpty() != false -> item(key = "empty") {
                    WmsEmptyState(icon = Icons.Outlined.ReceiptLong,
                        title = "当日暂无${uiState.reportType.label}明细",
                        subtitle = emptyStateHint(uiState.report) ?: "可翻日期回看，或确认单据已在电脑端点「完成」")
                }
                else -> itemsIndexed(uiState.report?.items.orEmpty(),
                    key = { index, item -> "${item.materialCode}|${item.contractNo ?: ""}|$index" }) { _, item ->
                    Box(Modifier.padding(horizontal = 16.dp)) {
                        DailyReportItemRow(item, uiState.reportType == ReportType.PURCHASE_IN)
                    }
                }
            }
        }
    }

}
/**
 * 空态副文案：在「当日暂无X明细」标题之外补充可行动线索；无线索时返回 null
 * （调用方给默认副文案）。诊断字段来自服务端 diagnostics，旧版后端无该节点时
 * 为 null，必须判空。
 */
private fun emptyStateHint(report: DailyReportData?): String? {
    val diag = report?.diagnostics ?: return null
    val pending = diag.pendingOrders ?: 0
    if (pending > 0) {
        return "今日该仓还有 $pending 张单据未完成\n（电脑端录入后需点「完成」才会计入报表）"
    }
    val others = diag.otherTypeOrders?.filter { (it.orders ?: 0) > 0 }.orEmpty()
    if (others.isNotEmpty()) {
        val desc = others.joinToString("、") { "${it.businessType ?: "未填写"} ${it.orders} 单" }
        return "今日该仓有其他类型单据：$desc\n（不在本报表统计口径内）"
    }
    return null
}

@Composable
private fun SummaryCell(label: String, value: String, modifier: Modifier = Modifier) {
    Column(modifier = modifier, horizontalAlignment = Alignment.CenterHorizontally) {
        Text(
            quantityDisplayText(value),
            modifier = Modifier.fillMaxWidth(),
            softWrap = true,
            textAlign = TextAlign.Center,
            fontWeight = FontWeight.Bold,
            fontSize = 22.sp,
            style = MaterialTheme.typography.titleMedium.copy(fontFeatureSettings = "tnum"),
            color = Primary.readableOn(Primary.copy(alpha = 0.08f).compositeOver(MaterialTheme.colorScheme.background))
        )
        Text(
            label,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
    }
}

@Composable
internal fun DailyReportItemRow(
    item: DailyReportItem,
    isPurchase: Boolean
) {
    WmsCard(modifier = Modifier.fillMaxWidth(), contentPadding = PaddingValues(horizontal = 14.dp, vertical = 10.dp)) {
        Column(modifier = Modifier.fillMaxWidth()) {
            Column(
                modifier = Modifier.fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                WmsAdaptiveRecord(
                    quantityText = "${formatQty(item.quantity)} ${item.unit}",
                    identity = {
                        Column(modifier = Modifier.fillMaxWidth()) {
                            Text(
                                "${item.materialName}（${item.materialCode}）",
                                fontWeight = FontWeight.SemiBold,
                                fontSize = 16.sp
                            )
                            // BUG-2026-08-24-007：spec/contractNo 可空（Gson 对缺失/显式
                            // null 字段不走构造器默认值），必须用 isNullOrBlank 判空，
                            // 裸 isNotBlank() 会 NPE 导致 App 崩溃。
                            if (!item.spec.isNullOrBlank()) {
                                Text(
                                    item.spec,
                                    style = MaterialTheme.typography.bodyMedium,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant
                                )
                            }
                        }
                    },
                    quantity = {
                        // 手机端报表不显示金额（用户需求：隐藏单价/金额、操作人、单据编号）
                        // 数量使用完整行，保留全部数字、单位与正负号，并支持系统大字体。
                        Text(
                            quantityDisplayText("${formatQty(item.quantity)} ${item.unit}"),
                            fontWeight = FontWeight.Bold,
                            fontSize = 20.sp,
                            style = LocalTextStyle.current.copy(fontFeatureSettings = "tnum"),
                            textAlign = TextAlign.End,
                            softWrap = true,
                            modifier = Modifier.fillMaxWidth(),
                            color = Primary
                        )
                    }
                )
            }
            // 底部行：合同编号 + 往来单位（供应商/部门），不显示单据编号与操作人
            val partyLabel = if (isPurchase) "供应商" else "部门"
            val partyValue = (if (isPurchase) item.supplier else item.department) ?: ""
            // AI-APP-FIX-206：删除 showWarehouse 死代码——日报下拉只列真实仓库
            // （allowAll=false），"全部仓库汇总"口径已不可达。
            val bottomText = buildString {
                if (!item.contractNo.isNullOrBlank()) {
                    append("合同 ${item.contractNo}")
                }
                if (partyValue.isNotBlank()) {
                    if (isNotEmpty()) append(" · ")
                    append("$partyLabel $partyValue")
                }
            }
            if (bottomText.isNotBlank()) {
                Spacer(modifier = Modifier.height(6.dp))
                Text(
                    bottomText,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
}

/**
 * 仓库选择下拉已提取为共享组件 ui/components/WarehouseSelector.kt
 * （BUG-2026-09-10-010：报表与首页需要一致的跨仓切换体验）。
 */

// AI-APP-FIX-403：数量格式化统一为 ui/util/Format.kt 的 formatQty（千分位）

@Composable
internal fun DailyReportSummaryContent(summary: DailyReportSummary) {
    val density = LocalDensity.current
    val measurer = rememberTextMeasurer()
    val quantity = formatQty(summary.quantity)
    val valueStyle = MaterialTheme.typography.titleMedium.copy(fontSize = 22.sp, fontWeight = FontWeight.Bold, fontFeatureSettings = "tnum")
    BoxWithConstraints(Modifier.fillMaxWidth()) {
        val measured = measurer.measure(quantity, style = valueStyle, softWrap = false).size.width
        val inline = density.fontScale <= 1.3f && measured < with(density) { ((maxWidth - 48.dp) / 3).toPx() }
        Column(Modifier.fillMaxWidth().padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            if (inline) {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    SummaryCell("单据", "${summary.orderCount}", modifier = Modifier.weight(1f))
                    SummaryCell("明细", "${summary.itemCount}", modifier = Modifier.weight(1f))
                    SummaryCell("总数量", quantity, modifier = Modifier.weight(1f))
                }
            } else {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    SummaryCell("单据", "${summary.orderCount}", modifier = Modifier.weight(1f))
                    SummaryCell("明细", "${summary.itemCount}", modifier = Modifier.weight(1f))
                }
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    SummaryCell("总数量", quantity, modifier = Modifier.weight(1f))
                }
            }
        }
    }
}
