package com.factory.wms.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.ui.zIndex
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material.icons.outlined.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.factory.wms.data.model.MaterialDto
import com.factory.wms.data.model.ScanLine
import com.factory.wms.ui.components.PendingSyncBanner
import com.factory.wms.ui.components.ScannerDialog
// AI-APP-FIX-405：拍照 launcher 迁至 ui/components/CameraLauncher.kt，此处需显式导入
import com.factory.wms.ui.components.rememberCameraLauncherWithPermission
import com.factory.wms.ui.components.WmsEmptyState
import com.factory.wms.ui.components.WmsGradientHeader
import com.factory.wms.ui.components.WmsOutlinedActionButton
import com.factory.wms.ui.components.WmsPrimaryButton
import com.factory.wms.ui.theme.*
import com.factory.wms.ui.viewmodel.scan.ScanViewModel
import com.factory.wms.ui.components.ScanLocationSelector
import com.factory.wms.ui.viewmodel.scan.SubmittedPrintInfo
import com.factory.wms.util.formatQuantity
import com.factory.wms.util.ScanFeedback
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import kotlinx.coroutines.launch
import android.graphics.Bitmap
import java.io.ByteArrayOutputStream
import android.util.Base64
import com.factory.wms.ui.screens.rememberCameraLauncherWithPermission

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ScanScreenBase(
    title: String,
    subtitle: String,
    gradient: Color,
    onBack: () -> Unit,
    scanLines: List<ScanLine>,
    totalQuantity: Double,
    viewModel: ScanViewModel,
    snackbarHostState: SnackbarHostState,
    isLoading: Boolean,
    showScannerDialog: Boolean,
    onShowScanner: () -> Unit,
    onDismissScanner: () -> Unit,
    manualCode: String,
    manualQty: String,
    onManualCodeChange: (String) -> Unit,
    onManualQtyChange: (String) -> Unit,
    onManualAdd: () -> Unit,
    onScanBarcode: (String) -> Unit,
    onSubmitClick: () -> Unit,
    submitLabel: String,
    submitColor: Color,
    /**
     * 是否显示「库位选择器」+「拍照取证」两块单据附属信息（BUG-2026-09-18-009）。
     *
     * 这两块只对**产生单据**的流程有意义（入库单/出库单），盘点页不产生单据、
     * 查库存页根本不会提交，因此由调用方显式声明，不靠文案反推。
     */
    showLocationSelector: Boolean = false,
    /** 是否显示「拍照取证」入口。与 [showLocationSelector] 独立，便于将来分别开关。 */
    showEvidenceCapture: Boolean = false,
    // 额外的识别类操作入口（如扫码盘点页的"识物盘点"），仅在提供时显示
    extraActionLabel: String? = null,
    onExtraAction: (() -> Unit)? = null,
    // 可选的顶部区域（如出入库的仓库选择），渲染在汇总条之前
    header: (@Composable () -> Unit)? = null,
    // 可选的自定义横幅（如语音建单成功提示），渲染在 header 之下、汇总条之上
    banner: (@Composable () -> Unit)? = null,
    // 提交成功后的"打印单据"横幅（提交入库/出库后出现）
    submittedPrint: SubmittedPrintInfo? = null,
    printLoading: Boolean = false,
    onPrintOrder: (() -> Unit)? = null,
    onDismissPrint: (() -> Unit)? = null,
    materialSuggestions: List<MaterialDto> = emptyList(),
    materialSuggestionsLoading: Boolean = false,
    onMaterialSuggestionSelected: (MaterialDto) -> Unit = {},
    // ── AI-MOB-OFFLINE-01：离线待同步状态（由各页从 ScanViewModel.uiState 透传）──
    /** 待自动补传条数 */
    offlinePendingCount: Int = 0,
    /** 重试耗尽的失败条数 */
    offlineFailedCount: Int = 0,
    /** 人工重试失败记录 */
    onRetryOffline: () -> Unit = {}
) {
    var showCameraScanner by remember { mutableStateOf(false) }
    var pendingRemoval by remember { mutableStateOf<ScanLine?>(null) }
    val haptics = LocalHapticFeedback.current
    val scanState by viewModel.uiState.collectAsState()
    val scanFeedback = scanState.scanFeedback.takeIf { scanLines.isNotEmpty() }
    val evidenceCamera = rememberCameraLauncherWithPermission(snackbarHostState) { bitmap: Bitmap ->
        val output = ByteArrayOutputStream()
        bitmap.compress(Bitmap.CompressFormat.JPEG, 80, output)
        viewModel.addEvidence(Base64.encodeToString(output.toByteArray(), Base64.NO_WRAP))
    }
    pendingRemoval?.let { line ->
        AlertDialog(
            onDismissRequest = { pendingRemoval = null },
            title = { Text("确认移除物料") },
            text = {
                Text("${line.material_code} ${line.material_name.orEmpty()}\n规格：${line.material_spec.orEmpty()}\n库位/区域：${line.location_code.orEmpty()}\n数量：${formatQuantity(line.quantity)}")
            },
            confirmButton = {
                TextButton(enabled = !isLoading, onClick = {
                    haptics.performHapticFeedback(HapticFeedbackType.LongPress)
                    viewModel.removeScanLine(line)
                    pendingRemoval = null
                }) { Text("确认移除") }
            },
            dismissButton = {
                TextButton(onClick = { pendingRemoval = null }) { Text("取消") }
            }
        )
    }
    // AI-MOB-CONTINUOUS-SCAN-01：连续扫描的已扫条数与最近一次条码。
    // 计数在弹窗内不自行维护（弹窗只负责"扫到"），由本层持有 —— 这样
    // 顶部"已扫 N 件"的 N 与清单行数口径一致（清空清单时应一并复位）。
    var continuousScanCount by remember { mutableStateOf(0) }
    var lastScannedCode by remember { mutableStateOf<String?>(null) }
    // AI-MOB-SCAN-UX-01：扫码后的物料校验是挂起调用（要判成功/失败给不同反馈），
    // 用一个与组合生命周期绑定的 scope，弹窗关闭后自动取消，不会泄漏。
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    Scaffold(
        snackbarHost = { SnackbarHost(snackbarHostState) },
        containerColor = Background,
        topBar = {
            // 模块色渐变头部：入库蓝 / 出库绿 / 盘点紫，一眼识别当前作业类型
            WmsGradientHeader(
                title = title,
                subtitle = subtitle,
                accent = gradient,
                onBack = onBack
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
        ) {
            // BUG-2026-09-18-006：顶部固定区改为**可滚动**（原为裸 Column 不可滚）。
            //
            // 原实现：header（出库页含 仓库卡 + 领料部门 + 领料人 + 合同卡）/ 库位选择器 /
            // 拍照取证 / 草稿错误 / 扫码反馈 / 离线横幅 / 打印横幅 / 汇总卡 全部平铺在
            // 不可滚动的 Column 里，只有扫码清单占 weight(1f)。于是顶部内容一旦变高，
            // 就会把底部的「提交出库」按钮顶出屏幕——而因为整体不可滚，**滚也找不回来**，
            // 现场表现为"看不到提交按钮，这单提交不了"。
            //
            // 触发条件（用户 2026-09-18 现场截图：「手机端-出库-手工添加 看不到提交功能」）：
            // ① 合同编号输入片段后 ContractInputCard 内联展开全部建议（本次一并限高修复）；
            // ② 选择领料部门/领料人后卡片由占位文案变为两行实际值；
            // ③ 小屏机 / 大字体 / 拍照取证与离线横幅同时出现。
            //
            // 修复：顶部区加 weight(1f) + verticalScroll，底部操作区留在 Column 内
            // （非 weight 子项），权重先分配 → 无论顶部内容多高，提交按钮**必然可见**，
            // 由"被顶出屏幕"变为"顶部区自己滚动"。扫码清单原本就靠 weight 吸收剩余空间：
            // 清单为空时顶部区高、清单有内容时被压到最小高度，两种状态都不会挤压按钮，
            // 因此保留 LazyColumn 自身滚动，不做内嵌滚动容器（嵌套滚动还会互相抢手势）。
            Column(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth()
                    .verticalScroll(rememberScrollState())
            ) {
                // 可选的顶部区域（如仓库选择）
                header?.invoke()

                // 可选的自定义横幅（如「语音草稿已生成」）
                banner?.invoke()
                // BUG-2026-09-18-009：原来这里判断的是
                //     if (submitLabel == "提交入库" || submitLabel == "提交出库")
                // 用**按钮文案**驱动"是否渲染库位选择器 + 拍照取证"两块功能。
                // 全仓库 submitLabel 唯一的逻辑用途就是这一处，其余全是直接显示。
                // 也就是说：谁把按钮文案从"提交入库"改成"确认入库"（纯 UI 润色），
                // 就会**静默删掉**库位选择与拍照取证两个功能——无编译错误、无测试报警，
                // 现场只在"启用库位管理后入库必须填库位"时才炸。文案与逻辑必须解耦。
                if (showLocationSelector) {
                    ScanLocationSelector(viewModel)
                }
                if (showEvidenceCapture) {
                    Row(Modifier.padding(horizontal = 16.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        OutlinedButton(onClick = evidenceCamera, enabled = !isLoading && scanState.evidence.size < 3) {
                            Text("拍照取证（${scanState.evidence.size}/3）")
                        }
                    }
                }
                scanState.draftSaveError?.let { message ->
                    Text(message, color = MaterialTheme.colorScheme.error,
                        modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp))
                }
                scanFeedback?.let { message ->
                    Text(
                        text = message,
                        color = gradient,
                        style = MaterialTheme.typography.bodyMedium,
                        modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp)
                    )
                }

                // AI-MOB-OFFLINE-01：离线待同步横幅。
                // 四个扫码页（入库/出库/盘点/查库存）共用本基类，在此渲染一次即全覆盖。
                // 仅在有暂存/失败记录时显示，正常在线提交时完全不占空间。
                PendingSyncBanner(
                    pendingCount = offlinePendingCount,
                    failedCount = offlineFailedCount,
                    onRetry = onRetryOffline,
                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp)
                )

                // 提交成功后的"打印单据"横幅
                submittedPrint?.let { info ->
                    Card(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 16.dp, vertical = 8.dp),
                        shape = RoundedCornerShape(16.dp),
                        colors = CardDefaults.cardColors(
                            containerColor = gradient.copy(alpha = 0.08f)
                        ),
                        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp)
                    ) {
                        Column(modifier = Modifier.padding(14.dp)) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Icon(
                                    Icons.Outlined.Print,
                                    null,
                                    tint = gradient,
                                    modifier = Modifier.size(20.dp)
                                )
                                Spacer(modifier = Modifier.width(8.dp))
                                Column(modifier = Modifier.weight(1f)) {
                                    Text(
                                        "提交成功",
                                        style = MaterialTheme.typography.titleSmall,
                                        fontWeight = FontWeight.SemiBold,
                                        color = OnSurface
                                    )
                                    Text(
                                        info.orderNo?.let { "单号: $it" } ?: "已生成单据",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = OnSurfaceVariant
                                    )
                                }
                                if (onDismissPrint != null) {
                                    IconButton(onClick = onDismissPrint, modifier = Modifier.size(32.dp)) {
                                        Icon(
                                            Icons.Outlined.Close,
                                            "关闭",
                                            tint = OnSurfaceSecondary,
                                            modifier = Modifier.size(16.dp)
                                        )
                                    }
                                }
                            }
                            Spacer(modifier = Modifier.height(8.dp))
                            Button(
                                onClick = { onPrintOrder?.invoke() },
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .height(44.dp),
                                enabled = !printLoading && onPrintOrder != null,
                                shape = RoundedCornerShape(12.dp),
                                colors = ButtonDefaults.buttonColors(containerColor = gradient)
                            ) {
                                if (printLoading) {
                                    CircularProgressIndicator(
                                        modifier = Modifier.size(18.dp),
                                        color = Color.White,
                                        strokeWidth = 2.dp
                                    )
                                } else {
                                    Icon(
                                        Icons.Outlined.Print,
                                        null,
                                        modifier = Modifier.size(18.dp)
                                    )
                                    Spacer(modifier = Modifier.width(6.dp))
                                    Text(
                                        "打印单据",
                                        fontWeight = FontWeight.SemiBold,
                                        fontSize = 14.sp
                                    )
                                }
                            }
                        }
                    }
                }

                // Summary bar
                if (scanLines.isNotEmpty()) {
                    Card(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 16.dp, vertical = 8.dp),
                        shape = RoundedCornerShape(16.dp),
                        colors = CardDefaults.cardColors(
                            containerColor = gradient.copy(alpha = 0.06f)
                        ),
                        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp)
                    ) {
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(16.dp),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Box(
                                    modifier = Modifier
                                        .size(40.dp)
                                        .clip(RoundedCornerShape(12.dp))
                                        .background(gradient.copy(alpha = 0.12f)),
                                    contentAlignment = Alignment.Center
                                ) {
                                    Icon(
                                        Icons.Outlined.Inventory2,
                                        null,
                                        tint = gradient,
                                        modifier = Modifier.size(20.dp)
                                    )
                                }
                                Spacer(modifier = Modifier.width(12.dp))
                                Column {
                                    Text(
                                        "${scanLines.size} 种物料",
                                        style = MaterialTheme.typography.titleMedium,
                                        fontWeight = FontWeight.SemiBold
                                    )
                                    Text(
                                        "总计: ${formatQuantity(totalQuantity)}",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant
                                    )
                                }
                            }
                            FilledTonalButton(
                                onClick = { viewModel.clearScanLines() },
                                colors = ButtonDefaults.filledTonalButtonColors(
                                    containerColor = ErrorContainer,
                                    contentColor = Error
                                ),
                                shape = RoundedCornerShape(10.dp)
                            ) {
                                Icon(Icons.Outlined.Delete, null, modifier = Modifier.size(16.dp))
                                Spacer(Modifier.width(4.dp))
                                Text("清空", fontSize = 13.sp)
                            }
                        }
                    }

                    // Scan list
                    LazyColumn(
                        modifier = Modifier
                            .fillMaxWidth()
                            // 清单区限高：有扫码行时顶部区整体可滚，清单本身不占满高，
                            // 保证同屏仍能看到提交按钮，清单长了滚顶部区即可。
                            .heightIn(max = 320.dp)
                            .padding(horizontal = 16.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        item { Spacer(modifier = Modifier.height(4.dp)) }
                        // AI-APP-UI-002：稳定 key + animateItem。
                        // 无 key 时增删一行会整体重组并丢失条目内部状态；
                        // 有 key 后 Compose 只增删对应条目，且附带平滑的移动/淡入动画。
                        //
                        // key 必须兼顾**极端重复**：addScanLine 按「编码+库位」合并，
                        // 但 enrichScanLineMaterial 可能把两个不同原始条码（别名命中
                        // 同一物料）补全成同一个正式编码 → 清单出现重复 (编码,库位)。
                        // LazyColumn 遇重复 key 会直接崩溃，故 key 追加"第几次出现"
                        // 序号做去重兜底（同 key 行相对顺序稳定即可保证 key 稳定）。
                        itemsIndexed(
                            scanLines,
                            key = { index, line ->
                                val base = "${line.material_code}|${line.location_code.orEmpty()}"
                                val occurrence = scanLines.subList(0, index).count {
                                    it.material_code == line.material_code &&
                                        it.location_code.orEmpty() == line.location_code.orEmpty()
                                }
                                "$base#$occurrence"
                            },
                            contentType = { _, _ -> "scan_line" }
                        ) { index, line ->
                            Card(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .animateItem(),
                                shape = RoundedCornerShape(16.dp),
                                elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
                                colors = CardDefaults.cardColors(containerColor = CardBackground)
                            ) {
                                Row(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .padding(horizontal = 14.dp, vertical = 12.dp),
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    // Index badge（圆角方块，与模块色呼应）
                                    Box(
                                        modifier = Modifier
                                            .size(38.dp)
                                            .clip(RoundedCornerShape(11.dp))
                                            .background(gradient.copy(alpha = 0.12f)),
                                        contentAlignment = Alignment.Center
                                    ) {
                                        Text(
                                            "${index + 1}",
                                            color = gradient,
                                            fontWeight = FontWeight.Bold,
                                            fontSize = 14.sp
                                        )
                                    }
                                    Spacer(modifier = Modifier.width(12.dp))
                                    Column(modifier = Modifier.weight(1f)) {
                                        Text(
                                            line.material_code,
                                            style = MaterialTheme.typography.titleSmall,
                                            fontWeight = FontWeight.SemiBold,
                                            maxLines = 1,
                                            overflow = TextOverflow.Ellipsis
                                        )
                                        val materialDetails = listOfNotNull(
                                            line.material_name?.takeIf { it.isNotBlank() },
                                            line.material_brand?.takeIf { it.isNotBlank() },
                                            line.material_spec?.takeIf { it.isNotBlank() }
                                        ).joinToString()
                                        if (materialDetails.isNotBlank()) {
                                            Text(
                                                materialDetails,
                                                style = MaterialTheme.typography.bodySmall,
                                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                                maxLines = 2,
                                                overflow = TextOverflow.Ellipsis
                                            )
                                        }
                                    }
                                    // 数量胶囊（右对齐高亮，一眼看清每行数量）
                                    Surface(
                                        shape = RoundedCornerShape(10.dp),
                                        color = gradient.copy(alpha = 0.10f)
                                    ) {
                                        Text(
                                            "× ${formatQuantity(line.quantity)}",
                                            modifier = Modifier.padding(horizontal = 10.dp, vertical = 5.dp),
                                            color = gradient,
                                            fontSize = 13.sp,
                                            fontWeight = FontWeight.Bold
                                        )
                                    }
                                    IconButton(
                                        onClick = { pendingRemoval = line },
                                        enabled = !isLoading,
                                        // AI-APP-UI-002：36dp 低于 48dp 最小触控目标，
                                        // 戴手套点不中还会误触到旁边的数量胶囊。
                                        modifier = Modifier.size(48.dp)
                                    ) {
                                        Icon(
                                            Icons.Outlined.Close,
                                            "移除",
                                            tint = OnSurfaceSecondary,
                                            modifier = Modifier.size(18.dp)
                                        )
                                    }
                                }
                            }
                        }
                        item { Spacer(modifier = Modifier.height(8.dp)) }
                    }
                } else {
                    // Empty state（清单为空时不再 weight(1f) 抢高：顶部区自己可滚）
                    // AI-APP-UI-002：原先写死 height(180.dp)，而 WmsEmptyState 内容
                    // （96dp 图标环 + 标题 + 副标题 + 32dp 上下内边距 ≈ 220dp）超出
                    // 被裁剪——副标题常年显示不全。改为内容自适应 + 最小高度约束。
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .heightIn(min = 180.dp),
                        contentAlignment = Alignment.Center
                    ) {
                        WmsEmptyState(
                            icon = Icons.Outlined.QrCodeScanner,
                            title = "暂无扫描记录",
                            subtitle = "点击下方按钮扫码或手动添加",
                            accentColor = gradient
                        )
                    }
                }
            }

            // Bottom actions（顶部圆角浮层，与列表区自然过渡）
            //
            // BUG-2026-09-18-006：留在可滚区**之外**。Column 非权重子项按测量高度
            // 先分配空间，再去分 weight 给上面的可滚区，因此本区高度（提交按钮 +
            // 手工联想候选 + 扫码/手动按钮）始终被满足，不会被顶部内容挤走，
            // 也不会被软键盘顶掉（Manifest 已是 adjustResize，本区随之上移）。
            Surface(
                modifier = Modifier
                    .fillMaxWidth(),
                shadowElevation = 12.dp,
                color = MaterialTheme.colorScheme.surface,
                shape = RoundedCornerShape(topStart = 24.dp, topEnd = 24.dp)
            ) {
                Column(
                    modifier = Modifier
                        .padding(16.dp)
                        // BUG-2026-09-18-006：本区不再可滚（它在可滚区之外，必须整体可见），
                        // 故对"可能无限长"的内容加限高 + 内部滚动，防止把提交按钮推到屏幕外：
                        // 手工添加候选与下方的扫码/手动按钮区共用最大高度约束，
                        // 候选再多也只是本区内部滚动。
                        .heightIn(max = 420.dp)
                ) {
                    // Submit button（AI-APP-FIX-404：自绘主按钮 → WmsPrimaryButton，
                    // 触觉确认由组件内置——提交是关键动作，避免嘈杂现场重复点）
                    WmsPrimaryButton(
                        text = submitLabel,
                        onClick = onSubmitClick,
                        modifier = Modifier.fillMaxWidth(),
                        icon = Icons.Outlined.CheckCircle,
                        color = submitColor,
                        loading = isLoading,
                        enabled = scanLines.isNotEmpty()
                    )

                    if (materialSuggestionsLoading) {
                        LinearProgressIndicator(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(top = 8.dp),
                            color = submitColor,
                            trackColor = submitColor.copy(alpha = 0.12f)
                        )
                    }
                    if (manualCode.isNotBlank()) {
                        // BUG-2026-09-18-006：原来是无约束的 take(5) 平铺。
                        // 5 条候选各 4 行文本（编码/名称/规格/品牌）约 300dp，
                        // 叠加提交按钮与扫码/手动按钮后必然超出屏幕，把提交按钮挤没。
                        // 与弹窗内候选同口径：限高 + 内部滚动，候选多也不撑破本区。
                        Column(
                            modifier = Modifier
                                .fillMaxWidth()
                                .heightIn(max = 200.dp)
                                .verticalScroll(rememberScrollState())
                        ) {
                            materialSuggestions.take(5).forEach { material ->
                                TextButton(
                                    onClick = { onMaterialSuggestionSelected(material) },
                                    modifier = Modifier.fillMaxWidth()
                                ) {
                                    Column(modifier = Modifier.fillMaxWidth()) {
                                        Text(material.code.orEmpty())
                                        Text(material.name.orEmpty(), style = MaterialTheme.typography.bodySmall)
                                        Text(material.spec.orEmpty(), style = MaterialTheme.typography.bodySmall)
                                        Text(material.brand.orEmpty(), style = MaterialTheme.typography.bodySmall)
                                    }
                                }
                            }
                        }
                    }
                    Spacer(modifier = Modifier.height(12.dp))

                    // Extra recognition-type action (e.g. 识物盘点), only when provided
                    // AI-APP-FIX-404：自绘描边按钮 → WmsOutlinedActionButton
                    if (extraActionLabel != null && onExtraAction != null) {
                        WmsOutlinedActionButton(
                            text = extraActionLabel,
                            onClick = onExtraAction,
                            modifier = Modifier.fillMaxWidth(),
                            icon = Icons.Outlined.CameraAlt,
                            color = submitColor
                        )
                        Spacer(modifier = Modifier.height(12.dp))
                    }

                    // Action buttons（AI-APP-FIX-404：扫码/手动 → WmsOutlinedActionButton）
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        WmsOutlinedActionButton(
                            text = "扫码添加",
                            onClick = {
                                // 每次打开相机都从 0 起算本轮的"已扫 N 件"，
                                // 否则上一轮的计数会串到本轮，与清单对不上。
                                continuousScanCount = 0
                                lastScannedCode = null
                                showCameraScanner = true
                            },
                            modifier = Modifier.weight(1f),
                            icon = Icons.Outlined.QrCodeScanner,
                            color = submitColor
                        )
                        WmsOutlinedActionButton(
                            text = "手动添加",
                            onClick = onShowScanner,
                            modifier = Modifier.weight(1f),
                            icon = Icons.Outlined.Edit,
                            color = submitColor
                        )
                    }
                }
            }
        }
    }

    // Manual add dialog
    if (showScannerDialog) {
        AlertDialog(
            onDismissRequest = onDismissScanner,
            shape = RoundedCornerShape(20.dp),
            title = {
                Text("添加物料", fontWeight = FontWeight.SemiBold)
            },
            text = {
                Column {
                    // AI-MOB-ADD-KEYWORD-01：输入框与「查库存」同口径——支持
                    // 名称/规格/品牌关键词模糊联想，不再只认物料编码。
                    // 后端 /api/material/search 本就按 code|name|spec|brand 四字段
                    // LIKE 匹配，缺的只是这里把候选渲染出来。
                    OutlinedTextField(
                        value = manualCode,
                        onValueChange = onManualCodeChange,
                        label = { Text("物料编码 / 名称 / 规格 / 品牌") },
                        placeholder = { Text("输入或扫描物料编码，也可搜名称/规格/品牌") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(12.dp),
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedBorderColor = submitColor,
                            focusedLabelColor = submitColor
                        )
                    )

                    // 关键词模糊候选：命中即列出，点选后自动回填物料编码
                    if (manualCode.isNotBlank()) {
                        if (materialSuggestionsLoading) {
                            LinearProgressIndicator(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(top = 6.dp),
                                color = submitColor,
                                trackColor = submitColor.copy(alpha = 0.12f)
                            )
                        } else if (materialSuggestions.isNotEmpty()) {
                            Spacer(modifier = Modifier.height(6.dp))
                            Card(
                                modifier = Modifier.fillMaxWidth(),
                                shape = RoundedCornerShape(12.dp),
                                elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
                                colors = CardDefaults.cardColors(
                                    containerColor = submitColor.copy(alpha = 0.06f)
                                )
                            ) {
                                Column(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        // 弹窗内空间有限：限高内部滚动，候选多也不撑破弹窗
                                        .heightIn(max = 220.dp)
                                        .verticalScroll(rememberScrollState())
                                ) {
                                    materialSuggestions.forEachIndexed { index, material ->
                                        val specBrand = listOfNotNull(
                                            material.spec?.takeIf { it.isNotBlank() }
                                                ?.let { "规格: $it" },
                                            material.brand?.takeIf { it.isNotBlank() }
                                                ?.let { "品牌: $it" }
                                        ).joinToString("   ")
                                        Column(
                                            modifier = Modifier
                                                .fillMaxWidth()
                                                .clickable {
                                                    onMaterialSuggestionSelected(material)
                                                }
                                                .padding(horizontal = 12.dp, vertical = 10.dp)
                                        ) {
                                            Row(verticalAlignment = Alignment.CenterVertically) {
                                                Text(
                                                    material.code.orEmpty(),
                                                    style = MaterialTheme.typography.titleSmall,
                                                    fontWeight = FontWeight.Bold,
                                                    color = submitColor
                                                )
                                                if (!material.name.isNullOrBlank()) {
                                                    Spacer(modifier = Modifier.width(8.dp))
                                                    Text(
                                                        material.name.orEmpty(),
                                                        style = MaterialTheme.typography.bodyMedium,
                                                        color = MaterialTheme.colorScheme.onSurface,
                                                        maxLines = 1,
                                                        overflow = TextOverflow.Ellipsis
                                                    )
                                                }
                                            }
                                            if (specBrand.isNotBlank()) {
                                                Spacer(modifier = Modifier.height(2.dp))
                                                Text(
                                                    specBrand,
                                                    style = MaterialTheme.typography.bodySmall,
                                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                                    // BUG-2026-09-12-002：规格是区分物料的关键
                                                    // （如 ZB-BVR-450/750V 1*2.5 红/蓝 只差尾部），
                                                    // 单行省略号会把差异吃掉 → 候选看起来全一样。
                                                    // 放开到 2 行；候选区本身限高+内部滚动，不撑破弹窗。
                                                    maxLines = 2,
                                                    overflow = TextOverflow.Ellipsis
                                                )
                                            }
                                        }
                                        if (index < materialSuggestions.size - 1) {
                                            HorizontalDivider(
                                                color = submitColor.copy(alpha = 0.12f),
                                                thickness = 0.5.dp
                                            )
                                        }
                                    }
                                }
                            }
                        }
                    }

                    Spacer(modifier = Modifier.height(12.dp))
                    Row(
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        // - button
                        FilledIconButton(
                            onClick = {
                                val current = manualQty.toDoubleOrNull() ?: 1.0
                                val newVal = (current - 1).coerceAtLeast(0.0)
                                onManualQtyChange(formatQuantity(newVal))
                            },
                            modifier = Modifier.size(44.dp),
                            shape = RoundedCornerShape(12.dp),
                            colors = IconButtonDefaults.filledIconButtonColors(
                                containerColor = submitColor.copy(alpha = 0.1f)
                            )
                        ) {
                            Icon(
                                Icons.Outlined.Remove,
                                "减1",
                                tint = submitColor,
                                modifier = Modifier.size(22.dp)
                            )
                        }
                        Spacer(modifier = Modifier.width(8.dp))
                        OutlinedTextField(
                            value = manualQty,
                            onValueChange = onManualQtyChange,
                            label = { Text("数量") },
                            singleLine = true,
                            modifier = Modifier.weight(1f),
                            shape = RoundedCornerShape(12.dp),
                            // AI-MOB-SCAN-UX-01：数量框必须弹数字键盘。
                            // 原先未声明 keyboardOptions，弹的是全键盘，输数量要先切符号页，
                            // 现场戴手套时误触率高。Decimal 允许小数点（WMS 有 0.5 这类计量单位）。
                            // ImeAction.Done + onDone 直接加行：扫完码输完数量敲回车即完成，
                            // 不用再挪手去点"添加"按钮。
                            keyboardOptions = KeyboardOptions(
                                keyboardType = KeyboardType.Decimal,
                                imeAction = ImeAction.Done
                            ),
                            keyboardActions = KeyboardActions(onDone = { onManualAdd() }),
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedBorderColor = submitColor,
                                focusedLabelColor = submitColor
                            )
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        // + button
                        FilledIconButton(
                            onClick = {
                                val current = manualQty.toDoubleOrNull() ?: 0.0
                                val newVal = current + 1
                                onManualQtyChange(formatQuantity(newVal))
                            },
                            modifier = Modifier.size(44.dp),
                            shape = RoundedCornerShape(12.dp),
                            colors = IconButtonDefaults.filledIconButtonColors(
                                containerColor = submitColor
                            )
                        ) {
                            Icon(
                                Icons.Outlined.Add,
                                "加1",
                                tint = Color.White,
                                modifier = Modifier.size(22.dp)
                            )
                        }
                    }
                }
            },
            confirmButton = {
                Button(
                    onClick = onManualAdd,
                    enabled = manualCode.isNotBlank(),
                    shape = RoundedCornerShape(12.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = submitColor)
                ) {
                    Text("添加")
                }
            },
            dismissButton = {
                TextButton(onClick = onDismissScanner) {
                    Text("取消")
                }
            }
        )
    }

    // Camera scanner dialog
    if (showCameraScanner) {
        ScannerDialog(
            onDismiss = { showCameraScanner = false },
            continuous = true,
            scannedCount = continuousScanCount,
            lastScannedCode = lastScannedCode,
            feedbackMessage = scanFeedback,
            onBarcodeScanned = { barcode ->
                // AI-MOB-CONTINUOUS-SCAN-01：不再关弹窗，扫中即累计，
                // 用户点"完成"才退出（onDismiss 由弹窗内部按钮触发）。
                continuousScanCount += 1
                lastScannedCode = barcode
                onScanBarcode(barcode)
                // AI-MOB-SCAN-UX-01：声音+震动反馈。
                // 现场工人不看屏幕，靠体感分辨"这一件进去了没有"。
                // 未建档的码用双震+低频音区分，避免一路扫下去到提交才发现有行查无此物。
                scope.launch {
                    if (viewModel.materialExists(barcode)) {
                        ScanFeedback.success(context)
                    } else {
                        ScanFeedback.failure(context)
                    }
                }
            }
        )
    }
}
