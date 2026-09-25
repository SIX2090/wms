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
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.factory.wms.data.model.DailyReportData
import com.factory.wms.data.model.DailyReportItem
import com.factory.wms.ui.components.WarehouseSelector
import com.factory.wms.ui.components.WmsDateNavRow
import com.factory.wms.ui.components.WmsEmptyState
import com.factory.wms.ui.components.WmsErrorState
import com.factory.wms.ui.components.WmsListSkeleton
import com.factory.wms.ui.components.WmsTopBar
import com.factory.wms.ui.util.formatQty
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
        // BUG-2026-09-10-009：先拉可选仓库（多仓用户可切换/看全部），再查报表
        viewModel.loadWarehouses()
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
                    IconButton(onClick = { viewModel.load() }, enabled = !uiState.isLoading) {
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
        Column(
            modifier = Modifier
                .padding(padding)
                .fillMaxSize()
        ) {
            // ── 日期导航条（AI-APP-FIX-402：统一 WmsDateNavRow，日期可点弹 DatePicker 跳日）──
            // 「后一天」到达今天后禁用（FIX-206：未来日期服务端 400，前置钳制，
            // ViewModel.shiftDay/setDate 内有二次钳制兜底）
            WmsDateNavRow(
                date = uiState.date,
                onPrev = { viewModel.shiftDay(-1) },
                onNext = { viewModel.shiftDay(1) },
                nextEnabled = uiState.date < viewModel.today(),
                onResetToday = { viewModel.resetToday() },
                onDateSelected = { viewModel.setDate(it) }
            )

            // ── 类型切换 ──
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp),
                horizontalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                ReportType.values().forEach { type ->
                    FilterChip(
                        selected = uiState.reportType == type,
                        onClick = { viewModel.selectType(type) },
                        label = { Text(type.label) },
                        modifier = Modifier.weight(1f).height(WmsDimens.TouchTargetMin)
                    )
                }
            }

            Spacer(modifier = Modifier.height(8.dp))

            // ── 仓库选择（BUG-2026-09-10-009）──
            // 多仓用户此前只能看系统默认仓，录在其他仓的单据"查不到"。
            // 用户需求：日报下拉只列真实仓库，去掉「默认仓库」与「全部仓库（汇总）」，
            // 进入页默认选中第一个仓库（见 ReportViewModel.loadWarehouses）。
            WarehouseSelector(
                currentLabel = uiState.report?.warehouse,
                warehouses = uiState.warehouses,
                selectedId = uiState.selectedWarehouseId,
                onSelect = { viewModel.selectWarehouse(it) },
                showDefaultWarehouse = false,
                allowAll = false,
                modifier = Modifier.padding(horizontal = 16.dp)
            )

            Spacer(modifier = Modifier.height(10.dp))

            // ── 汇总卡 ──
            uiState.report?.let { report ->
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
                        SummaryCell("单据", "${report.summary.orderCount}")
                        SummaryCell("明细", "${report.summary.itemCount}")
                        SummaryCell("总数量", formatQty(report.summary.quantity))
                    }
                }
                Spacer(modifier = Modifier.height(10.dp))
            }

            // ── 明细列表 / 加载 / 空态 / 错误态 ──
            Box(modifier = Modifier.fillMaxSize()) {
                when {
                    // AI-APP-FIX-202：首屏（尚无报表数据）转圈 → 骨架列表；
                    // 带数据刷新保留旧列表 + 顶部按钮禁用，不闪骨架。
                    uiState.isLoading && uiState.report == null -> {
                        WmsListSkeleton(modifier = Modifier.align(Alignment.TopCenter))
                    }
                    // AI-APP-FIX-201：首屏加载失败 → 全屏错误态 + 重试，
                    // 不再落入下方"当日暂无明细"的误导性空态
                    uiState.loadError != null && uiState.report == null -> {
                        WmsErrorState(
                            title = "加载失败",
                            subtitle = uiState.loadError ?: "请检查网络后重试",
                            modifier = Modifier.align(Alignment.Center),
                            onRetry = { viewModel.load() }
                        )
                    }
                    uiState.isLoading -> {
                        CircularProgressIndicator(
                            modifier = Modifier.align(Alignment.Center)
                        )
                    }
                    (uiState.report?.items?.isEmpty() != false) -> {
                        // BUG-2026-09-10-001：空结果必须给出"为什么"，否则现场只能
                        // 反复问"今天的记录去哪了"。最常见原因是 PC 端保存后未点完成
                        // （报表只统计已完成单据），其次是业务类型不在本报表口径内。
                        WmsEmptyState(
                            icon = Icons.Outlined.ReceiptLong,
                            title = "当日暂无${uiState.reportType.label}明细",
                            subtitle = emptyStateHint(uiState.report)
                                ?: "可翻日期回看，或确认单据已在电脑端点「完成」",
                            modifier = Modifier.align(Alignment.Center)
                        )
                    }
                    else -> {
                        LazyColumn(
                            modifier = Modifier.fillMaxSize(),
                            contentPadding = PaddingValues(
                                horizontal = 16.dp, vertical = 4.dp
                            ),
                            verticalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            // AI-APP-FIX-206：补稳定 key（去除 report!! 强制解包）。
                            // 明细无服务端 id，同物料同合同同日可能重复 → key 追加行序号兜底。
                            itemsIndexed(
                                uiState.report?.items.orEmpty(),
                                key = { index, item -> "${item.materialCode}|${item.contractNo ?: ""}|$index" }
                            ) { _, item ->
                                DailyReportItemRow(
                                    item = item,
                                    isPurchase = uiState.reportType == ReportType.PURCHASE_IN
                                )
                            }
                        }
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
private fun SummaryCell(label: String, value: String) {
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
private fun DailyReportItemRow(
    item: DailyReportItem,
    isPurchase: Boolean
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surface
        ),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
    ) {
        Column(modifier = Modifier.padding(horizontal = 14.dp, vertical = 10.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        "${item.materialName}（${item.materialCode}）",
                        fontWeight = FontWeight.SemiBold,
                        fontSize = 15.sp,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                    // BUG-2026-08-24-007：spec/contractNo 可空（Gson 对缺失/显式
                    // null 字段不走构造器默认值），必须用 isNullOrBlank 判空，
                    // 裸 isNotBlank() 会 NPE 导致 App 崩溃。
                    if (!item.spec.isNullOrBlank()) {
                        Text(
                            item.spec,
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis
                        )
                    }
                }
                Spacer(modifier = Modifier.width(8.dp))
                // 手机端报表不显示金额（用户需求：隐藏单价/金额、操作人、单据编号）
                // AI-APP-FIX-403：数字列单行省略 + 固定右栏宽 + tnum 等宽数字
                Text(
                    "${formatQty(item.quantity)} ${item.unit}",
                    fontWeight = FontWeight.Bold,
                    fontSize = 15.sp,
                    style = LocalTextStyle.current.copy(fontFeatureSetting = "tnum"),
                    textAlign = TextAlign.End,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.width(110.dp),
                    color = Primary
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
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
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
