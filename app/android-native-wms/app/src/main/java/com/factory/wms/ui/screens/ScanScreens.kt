package com.factory.wms.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
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
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.factory.wms.data.model.CheckOrderDto
import com.factory.wms.data.model.ScanLine
import com.factory.wms.data.model.WarehouseDto
import com.factory.wms.ui.components.OfflineDataBanner
import com.factory.wms.ui.components.PartyPickerDialog
import com.factory.wms.ui.components.PartyPickerItem
import com.factory.wms.ui.components.PartySelectorCard
import com.factory.wms.ui.components.ScannerDialog
import com.factory.wms.ui.components.VoiceDraftCreatedBanner
import com.factory.wms.ui.components.WarehousePickerDialog
import com.factory.wms.ui.components.WmsEmptyState
import com.factory.wms.ui.components.WmsGradientHeader
import com.factory.wms.ui.components.WmsInfoCell
import com.factory.wms.ui.components.WmsSubmitConfirmDialog
import com.factory.wms.ui.theme.*
import com.factory.wms.ui.viewmodel.scan.ScanViewModel
import com.factory.wms.ui.viewmodel.scan.SubmittedPrintInfo
import com.factory.wms.util.formatQuantity
import com.factory.wms.util.ScanFeedback
import com.factory.wms.ui.util.formatQty
import com.factory.wms.ui.util.toPositiveQtyOrNull
import androidx.compose.ui.platform.LocalContext
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun InboundScreen(
    viewModel: ScanViewModel,
    onBack: () -> Unit
) {
    val uiState by viewModel.uiState.collectAsState()
    var showSubmitDialog by remember { mutableStateOf(false) }
    var showScannerDialog by remember { mutableStateOf(false) }
    var showWarehouseDialog by remember { mutableStateOf(false) }
    // BUG-2026-09-18-008：供应商下拉（选填）弹窗开关
    var showSupplierDialog by remember { mutableStateOf(false) }
    var manualCode by remember { mutableStateOf("") }
    var manualQty by remember { mutableStateOf("1") }
    var acknowledgedPrintTargetId by remember { mutableStateOf<Int?>(null) }
    val snackbarHostState = remember { SnackbarHostState() }
    val scope = rememberCoroutineScope()

    LaunchedEffect(Unit) {
        viewModel.restoreEditDraft("inbound")
        if (uiState.warehouses.isEmpty() && !uiState.warehousesLoading) {
            viewModel.loadWarehouses()
        }
        // BUG-2026-09-18-008：供应商档案只需拉一次，用于「供应商」下拉
        if (uiState.suppliers.isEmpty() && !uiState.suppliersLoading) {
            viewModel.loadSuppliers()
        }
    }

    LaunchedEffect(uiState.error) {
        uiState.error?.let {
            snackbarHostState.showSnackbar(it, duration = SnackbarDuration.Short)
            viewModel.clearError()
        }
    }
    LaunchedEffect(uiState.success) {
        uiState.success?.let {
            snackbarHostState.showSnackbar(it, duration = SnackbarDuration.Short)
            viewModel.clearSuccess()
        }
    }

    ScanScreenBase(
        // BUG-2026-09-18-007：标题不再写死"扫码入库"。
        // 本页支持 扫码添加 / 手动添加 / 语音建单 三种录入口，标题写"扫码"与
        // 底部 Tab「入库」两套口径，用户从"手工添加"进来看到"扫码入库"会怀疑
        // 进错了页面（现场反馈）。统一为业务动作名，与 Tab 一致；
        // "扫码"只作为其中一种录入方式出现在按钮文案里。
        title = "入库",
        subtitle = "扫码或手动添加物料，完成入库",
        gradient = CardBlue,
        onBack = onBack,
        scanLines = uiState.scanLines,
        totalQuantity = uiState.totalQuantity,
        viewModel = viewModel,
        snackbarHostState = snackbarHostState,
        isLoading = uiState.isLoading,
        showScannerDialog = showScannerDialog,
        onShowScanner = { showScannerDialog = true },
        onDismissScanner = {
            showScannerDialog = false
            viewModel.clearMaterialSuggestions()
        },
        manualCode = manualCode,
        manualQty = manualQty,
        onManualCodeChange = {
            manualCode = it
            viewModel.searchMaterialSuggestions(it)
        },
        onManualQtyChange = { manualQty = it },
        materialSuggestions = uiState.materialSuggestions,
        materialSuggestionsLoading = uiState.materialSuggestionsLoading,
        onMaterialSuggestionSelected = { material ->
            manualCode = material.code.orEmpty()
            viewModel.clearMaterialSuggestions()
        },
        // AI-MOB-OFFLINE-01：断网提交已暂存条数 / 失败条数 / 人工重试
        offlinePendingCount = uiState.offlinePendingCount,
        offlineFailedCount = uiState.offlineFailedCount,
        onRetryOffline = { viewModel.retryOfflineSync() },
        onManualAdd = {
            // AI-APP-FIX-105 / BUG-2026-09-26-001：非法/非正数量拦截提示，
            // 禁止 `?: 1.0` 静默兜底（输入 "abc" 按 1 入库、"0"/负数直接放行，现场无感知即错账）。
            val qty = manualQty.toPositiveQtyOrNull()
            if (manualCode.isNotBlank() && qty != null) {
                viewModel.addScanLine(
                    ScanLine(
                        material_code = manualCode.trim(),
                        quantity = qty,
                        location_code = uiState.selectedLocation.ifBlank { null }
                    )
                )
                manualCode = ""
                manualQty = "1"
                viewModel.clearMaterialSuggestions()
                showScannerDialog = false
            } else if (manualCode.isNotBlank()) {
                scope.launch {
                    snackbarHostState.showSnackbar("请输入大于 0 的有效数量", duration = SnackbarDuration.Short)
                }
            }
        },
        onScanBarcode = { barcode ->
            val qty = manualQty.toPositiveQtyOrNull()
            if (qty != null) {
                viewModel.addScanLine(
                    ScanLine(
                        material_code = barcode.trim(),
                        quantity = qty,
                        location_code = uiState.selectedLocation.ifBlank { null }
                    )
                )
                manualCode = ""
                manualQty = "1"
            } else {
                scope.launch {
                    snackbarHostState.showSnackbar("请输入大于 0 的有效数量", duration = SnackbarDuration.Short)
                }
            }
        },
        onSubmitClick = { showSubmitDialog = true },
        submitLabel = "提交入库",
        submitColor = CardBlue,
        // BUG-2026-09-18-009：入库产生单据，需要库位选择 + 拍照取证（原先靠文案隐式开启）
        showLocationSelector = true,
        showEvidenceCapture = true,
        submittedPrint = uiState.submittedPrint,
        printLoading = uiState.printLoading,
        onPrintOrder = { viewModel.printSubmittedOrder() },
        onDismissPrint = { viewModel.clearSubmittedPrint() },
        header = {
            Column {
                // AI-APP-FIX-406：WarehouseSelectorCard 并入 PartySelectorCard（同款视觉，消除重复实现）
                PartySelectorCard(
                    label = "收货仓库",
                    placeholder = "请选择仓库",
                    valueText = uiState.selectedWarehouse?.let { "${it.code} ${it.name.orEmpty()}" },
                    icon = Icons.Outlined.Warehouse,
                    accentColor = CardBlue,
                    onClick = { showWarehouseDialog = true }
                )
                // BUG-2026-09-18-008：供应商/备注（均选填）。
                // 此前入库请求体只有明细行，InOrder.supplier_id 恒为 NULL，
                // 每日报表「采购入库」的供应商列永远空白、采购对账断链。
                PartySelectorCard(
                    label = "供应商（选填）",
                    placeholder = "请选择供应商",
                    valueText = uiState.selectedSupplier?.let {
                        "${it.code.orEmpty()} ${it.name.orEmpty()}".trim()
                    },
                    icon = Icons.Outlined.Storefront,
                    accentColor = CardBlue,
                    onClick = { showSupplierDialog = true }
                )
                InboundRemarkCard(
                    remark = uiState.inboundRemark,
                    onRemarkChange = { viewModel.onInboundRemarkChange(it) },
                    accentColor = CardBlue
                )
            }
        }
    )

    uiState.submittedPrint?.let { printInfo ->
        if (acknowledgedPrintTargetId != printInfo.targetId) {
            PrintConfirmationDialog(
                info = printInfo,
                loading = uiState.printLoading,
                onPrint = {
                    acknowledgedPrintTargetId = printInfo.targetId
                    viewModel.printSubmittedOrder()
                },
                onLater = { acknowledgedPrintTargetId = printInfo.targetId }
            )
        }
    }

    if (showWarehouseDialog) {
        WarehousePickerDialog(
            warehouses = uiState.warehouses,
            selected = uiState.selectedWarehouse,
            loading = uiState.warehousesLoading,
            onDismiss = { showWarehouseDialog = false },
            onSelect = { warehouse ->
                viewModel.selectWarehouse(warehouse)
                showWarehouseDialog = false
            },
            onRetry = { viewModel.loadWarehouses() },
            accentColor = CardBlue
        )
    }

    // BUG-2026-09-18-008：供应商选择对话框（选填，与出库页领料部门同款）
    if (showSupplierDialog) {
        PartyPickerDialog(
            title = "选择供应商",
            items = uiState.suppliers.map {
                PartyPickerItem(
                    id = it.id,
                    title = "${it.code.orEmpty()} ${it.name.orEmpty()}".trim(),
                    subtitle = ""
                )
            },
            selectedId = uiState.selectedSupplier?.id,
            loading = uiState.suppliersLoading,
            icon = Icons.Outlined.Storefront,
            accentColor = CardBlue,
            onDismiss = { showSupplierDialog = false },
            onSelect = { item ->
                viewModel.selectSupplier(item?.let { sel ->
                    uiState.suppliers.firstOrNull { it.id == sel.id }
                })
                showSupplierDialog = false
            },
            onRetry = { viewModel.loadSuppliers() }
        )
    }

    if (showSubmitDialog) {
        // AI-APP-FIX-406：自绘弹窗骨架 → WmsSubmitConfirmDialog（正文信息行保留本页口径）
        WmsSubmitConfirmDialog(
            title = "确认入库",
            confirmLabel = "确认入库",
            onConfirm = {
                showSubmitDialog = false
                viewModel.submitInbound()
            },
            onDismiss = { showSubmitDialog = false },
            accent = CardBlue,
            // BUG-2026-09-12-010：提交中禁用，配合 ViewModel 层守卫双保险。
            // BUG-2026-09-18-010：在"非提交中"之上追加"已选仓库"前置校验，
            // 不能用 isLoading 覆盖前置条件（对照盘点弹窗的同一写法）。
            confirmEnabled = uiState.selectedWarehouse != null && !uiState.isLoading,
            text = {
                // BUG-2026-09-18-010：本弹窗原先是四个页里**信息最少**的一个
                // （出库页显示领料部门/领料人，盘点页显示仓库+盘点单并在未选时警告）。
                // 入库单的仓库是决定库存记到哪个仓的唯一依据，多仓场景下选错仓
                // 提交是一次**真实账目错误**（库存进错仓），而提交后单据已 completed
                // 无补录入口。此处补齐仓库与单头信息，并给出未选仓库的前置提示。
                val wh = uiState.selectedWarehouse
                // AI-APP-FIX-508：逐行渲染——长备注限 2 行省略，其余行限 1 行，
                // 避免一条长备注把确认弹窗撑到看不清「确认提交」按钮。
                val lines = buildList<Pair<String, Int>> {
                    if (wh == null) {
                        add("尚未选择收货仓库，请先选择仓库" to 2)
                    } else {
                        add("收货仓库：${wh.code} ${wh.name.orEmpty()}" to 1)
                    }
                    uiState.selectedSupplier?.let {
                        add("供应商：${it.name.orEmpty()}" to 1)
                    }
                    if (uiState.contractNo.isNotBlank()) {
                        add("合同编号：${uiState.contractNo}" to 1)
                    }
                    if (uiState.inboundRemark.isNotBlank()) {
                        add("备注：${uiState.inboundRemark}" to 2)
                    }
                    add("共 ${uiState.scanLines.size} 种物料，数量 ${formatQuantity(uiState.totalQuantity)}" to 1)
                    if (wh != null) add("确认提交入库？" to 1)
                }
                Column {
                    lines.forEach { (line, maxLines) ->
                        Text(line, maxLines = maxLines, overflow = TextOverflow.Ellipsis)
                    }
                }
            }
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun OutboundScreen(
    viewModel: ScanViewModel,
    onBack: () -> Unit,
    /**
     * AI-VOICE-OUT-F01：语音建单草稿预填。
     *
     * 由 NavGraph 在语音建单成功后设置（元素为 物料编码 to 数量），
     * 本页在 [LaunchedEffect] 中消费一次即回调 [onVoicePrefillConsumed] 清空，
     * 避免用户从底部 Tab 再次进出时被重复添加。
     */
    voicePrefillLines: List<Pair<String, Double>> = emptyList(),
    onVoicePrefillConsumed: () -> Unit = {},
    /** 语音草稿单号：非空时页顶展示"语音草稿已生成"提示条 */
    voiceDraftOrderNo: String? = null,
    onDismissVoiceDraft: () -> Unit = {},
    /** 出库页换仓时回写语音建单流程的仓库（单向同步，见 ScanViewModel.setOnWarehouseChanged） */
    onVoiceWarehouseChanged: ((WarehouseDto) -> Unit)? = null
) {
    val uiState by viewModel.uiState.collectAsState()
    var showSubmitDialog by remember { mutableStateOf(false) }
    var showScannerDialog by remember { mutableStateOf(false) }
    var showWarehouseDialog by remember { mutableStateOf(false) }
    // 2026-09-12 领料部门/领料人下拉对话框
    var showDepartmentDialog by remember { mutableStateOf(false) }
    var showEmployeeDialog by remember { mutableStateOf(false) }
    var manualCode by remember { mutableStateOf("") }
    var manualQty by remember { mutableStateOf("1") }
    var acknowledgedPrintTargetId by remember { mutableStateOf<Int?>(null) }
    val snackbarHostState = remember { SnackbarHostState() }
    val scope = rememberCoroutineScope()

    // 语音建单跳转过来的物料行：只消费一次，随后立刻通知外部清空
    LaunchedEffect(voicePrefillLines) {
        if (voicePrefillLines.isNotEmpty()) {
            viewModel.restoreEditDraft("outbound")
            // AI-APP-FIX-504：预填被丢弃（有待提交单据/加载中）时必须告知用户——
            // 此前静默 return，语音建的物料行"无声消失"，用户以为已加入清单。
            // 同时消费掉预填，避免残留在导航状态里、下次进页又意外生效。
            if (viewModel.uiState.value.pendingSubmissionId != null || viewModel.uiState.value.isLoading) {
                snackbarHostState.showSnackbar(
                    "语音预填的 ${voicePrefillLines.size} 行物料未生效：当前有单据待提交或正在加载，请稍后重试",
                    duration = SnackbarDuration.Long
                )
                onVoicePrefillConsumed()
                return@LaunchedEffect
            }
            voicePrefillLines.forEach { (code, qty) ->
                viewModel.addScanLine(ScanLine(material_code = code, quantity = qty))
            }
            onVoicePrefillConsumed()
        }
    }

    // 出库页换仓回写语音建单的仓库（单向），保证"界面显示 A 仓，草稿就不会落 B 仓"
    DisposableEffect(viewModel) {
        viewModel.setOnWarehouseChanged { warehouse ->
            onVoiceWarehouseChanged?.invoke(warehouse)
        }
        onDispose { viewModel.setOnWarehouseChanged(null) }
    }

    LaunchedEffect(Unit) {
        viewModel.restoreEditDraft("outbound")
        if (uiState.warehouses.isEmpty() && !uiState.warehousesLoading) {
            viewModel.loadWarehouses()
        }
        // 2026-09-12：进入出库页加载领料部门与员工下拉数据
        if (uiState.departments.isEmpty() && !uiState.departmentsLoading) {
            viewModel.loadDepartments()
        }
        if (uiState.employees.isEmpty() && !uiState.employeesLoading) {
            viewModel.loadEmployees()
        }
    }

    LaunchedEffect(uiState.error) {
        uiState.error?.let {
            snackbarHostState.showSnackbar(it, duration = SnackbarDuration.Short)
            viewModel.clearError()
        }
    }
    LaunchedEffect(uiState.success) {
        uiState.success?.let {
            snackbarHostState.showSnackbar(it, duration = SnackbarDuration.Short)
            viewModel.clearSuccess()
        }
    }

    ScanScreenBase(
        // BUG-2026-09-18-007：同入库页，标题与底部 Tab「出库」统一。
        // 该页入口更多：扫码、手动添加、语音建单、首页/概览下钻，
        // 写死"扫码"会与"手工添加"的实际路径矛盾。
        title = "出库",
        subtitle = "扫码或手动添加物料，完成出库",
        gradient = CardGreen,
        onBack = onBack,
        scanLines = uiState.scanLines,
        totalQuantity = uiState.totalQuantity,
        viewModel = viewModel,
        snackbarHostState = snackbarHostState,
        isLoading = uiState.isLoading,
        showScannerDialog = showScannerDialog,
        onShowScanner = { showScannerDialog = true },
        onDismissScanner = {
            showScannerDialog = false
            viewModel.clearMaterialSuggestions()
        },
        manualCode = manualCode,
        manualQty = manualQty,
        onManualCodeChange = {
            manualCode = it
            viewModel.searchMaterialSuggestions(it)
        },
        onManualQtyChange = { manualQty = it },
        materialSuggestions = uiState.materialSuggestions,
        materialSuggestionsLoading = uiState.materialSuggestionsLoading,
        onMaterialSuggestionSelected = { material ->
            manualCode = material.code.orEmpty()
            viewModel.clearMaterialSuggestions()
        },
        // AI-MOB-OFFLINE-01：断网提交已暂存条数 / 失败条数 / 人工重试
        offlinePendingCount = uiState.offlinePendingCount,
        offlineFailedCount = uiState.offlineFailedCount,
        onRetryOffline = { viewModel.retryOfflineSync() },
        onManualAdd = {
            // AI-APP-FIX-105 / BUG-2026-09-26-001：同入库页，非法数量拦截提示，禁止静默兜底。
            val qty = manualQty.toPositiveQtyOrNull()
            if (manualCode.isNotBlank() && qty != null) {
                viewModel.addScanLine(
                    ScanLine(
                        material_code = manualCode.trim(),
                        quantity = qty,
                        location_code = uiState.selectedLocation.ifBlank { null }
                    )
                )
                manualCode = ""
                manualQty = "1"
                showScannerDialog = false
            } else if (manualCode.isNotBlank()) {
                scope.launch {
                    snackbarHostState.showSnackbar("请输入大于 0 的有效数量", duration = SnackbarDuration.Short)
                }
            }
        },
        onScanBarcode = { barcode ->
            val qty = manualQty.toPositiveQtyOrNull()
            if (qty != null) {
                viewModel.addScanLine(
                    ScanLine(
                        material_code = barcode.trim(),
                        quantity = qty,
                        location_code = uiState.selectedLocation.ifBlank { null }
                    )
                )
                manualCode = ""
                manualQty = "1"
            } else {
                scope.launch {
                    snackbarHostState.showSnackbar("请输入大于 0 的有效数量", duration = SnackbarDuration.Short)
                }
            }
        },
        onSubmitClick = { showSubmitDialog = true },
        // BUG-2026-09-18-011：按钮文案由「提交出库」改为「确认出库」。
        // 全流程文案统一到「确认」口径：底部按钮「确认出库」→ 确认弹窗标题
        // 「确认出库」→ 弹窗主按钮「确认出库」，三处一致。
        //
        // 注意本改动**只动文案**：自 BUG-2026-09-18-009 起 submitLabel 已是
        // 纯显示值（库位选择器/拍照取证改由 showLocationSelector /
        // showEvidenceCapture 显式控制），故改文案不会影响任何功能开关。
        submitLabel = "确认出库",
        submitColor = CardGreen,
        // BUG-2026-09-18-009：出库产生单据，需要库位选择 + 拍照取证（原先靠文案隐式开启）
        showLocationSelector = true,
        showEvidenceCapture = true,
        submittedPrint = uiState.submittedPrint,
        printLoading = uiState.printLoading,
        onPrintOrder = { viewModel.printSubmittedOrder() },
        onDismissPrint = { viewModel.clearSubmittedPrint() },
        header = {
            Column {
                // AI-APP-FIX-406：WarehouseSelectorCard 并入 PartySelectorCard（同款视觉，消除重复实现）
                PartySelectorCard(
                    label = "出库仓库",
                    placeholder = "请选择仓库",
                    valueText = uiState.selectedWarehouse?.let { "${it.code} ${it.name.orEmpty()}" },
                    icon = Icons.Outlined.Warehouse,
                    accentColor = CardGreen,
                    onClick = { showWarehouseDialog = true }
                )
                // 2026-09-12：领料部门/领料人下拉（选填，部门→员工联动过滤）
                PartySelectorCard(
                    label = "领料部门（选填）",
                    placeholder = "请选择领料部门",
                    valueText = uiState.selectedDepartment?.let { "${it.code.orEmpty()} ${it.name.orEmpty()}".trim() },
                    icon = Icons.Outlined.AccountBox,
                    accentColor = CardGreen,
                    onClick = { showDepartmentDialog = true }
                )
                PartySelectorCard(
                    label = "领料人（选填）",
                    placeholder = "请选择领料人",
                    valueText = uiState.selectedEmployee?.let {
                        "${it.code.orEmpty()} ${it.name.orEmpty()}".trim()
                    },
                    icon = Icons.Outlined.Person,
                    accentColor = CardGreen,
                    onClick = { showEmployeeDialog = true }
                )
                ContractInputCard(
                    contractNo = uiState.contractNo,
                    suggestions = uiState.contractSuggestions,
                    loading = uiState.contractSuggestionsLoading,
                    onContractNoChange = { viewModel.onContractNoChange(it) },
                    onSelect = { viewModel.selectContract(it) },
                    accentColor = CardGreen
                )
            }
        },
        banner = {
            voiceDraftOrderNo?.let { orderNo ->
                VoiceDraftCreatedBanner(
                    orderNo = orderNo,
                    onDismiss = onDismissVoiceDraft
                )
            }
        }
    )

    uiState.submittedPrint?.let { printInfo ->
        if (acknowledgedPrintTargetId != printInfo.targetId) {
            PrintConfirmationDialog(
                info = printInfo,
                loading = uiState.printLoading,
                onPrint = {
                    acknowledgedPrintTargetId = printInfo.targetId
                    viewModel.printSubmittedOrder()
                },
                onLater = { acknowledgedPrintTargetId = printInfo.targetId }
            )
        }
    }

    if (showWarehouseDialog) {
        WarehousePickerDialog(
            warehouses = uiState.warehouses,
            selected = uiState.selectedWarehouse,
            loading = uiState.warehousesLoading,
            onDismiss = { showWarehouseDialog = false },
            onSelect = { warehouse ->
                viewModel.selectWarehouse(warehouse)
                showWarehouseDialog = false
            },
            onRetry = { viewModel.loadWarehouses() },
            accentColor = CardGreen
        )
    }

    // 2026-09-12：领料部门选择对话框
    if (showDepartmentDialog) {
        PartyPickerDialog(
            title = "选择领料部门",
            items = uiState.departments.map {
                PartyPickerItem(id = it.id, title = "${it.code.orEmpty()} ${it.name.orEmpty()}".trim())
            },
            selectedId = uiState.selectedDepartment?.id,
            loading = uiState.departmentsLoading,
            icon = Icons.Outlined.AccountBox,
            accentColor = CardGreen,
            onDismiss = { showDepartmentDialog = false },
            onSelect = { item ->
                viewModel.selectDepartment(item?.let { sel ->
                    uiState.departments.firstOrNull { it.id == sel.id }
                })
                showDepartmentDialog = false
            },
            onRetry = { viewModel.loadDepartments() }
        )
    }

    // 2026-09-12：领料人选择对话框
    if (showEmployeeDialog) {
        PartyPickerDialog(
            title = "选择领料人",
            items = uiState.employees.map {
                PartyPickerItem(
                    id = it.id,
                    title = "${it.code.orEmpty()} ${it.name.orEmpty()}".trim(),
                    subtitle = listOfNotNull(it.position, it.departmentName).filter { s -> s.isNotBlank() }.joinToString(" · ")
                )
            },
            selectedId = uiState.selectedEmployee?.id,
            loading = uiState.employeesLoading,
            icon = Icons.Outlined.Person,
            accentColor = CardGreen,
            onDismiss = { showEmployeeDialog = false },
            onSelect = { item ->
                viewModel.selectEmployee(item?.let { sel ->
                    uiState.employees.firstOrNull { it.id == sel.id }
                })
                showEmployeeDialog = false
            },
            onRetry = { viewModel.loadEmployees() }
        )
    }

    if (showSubmitDialog) {
        // AI-APP-FIX-406：自绘弹窗骨架 → WmsSubmitConfirmDialog
        WmsSubmitConfirmDialog(
            title = "确认出库",
            confirmLabel = "确认出库",
            onConfirm = {
                showSubmitDialog = false
                viewModel.submitOutbound()
            },
            onDismiss = { showSubmitDialog = false },
            accent = CardGreen,
            // BUG-2026-09-12-010：提交中禁用，配合 ViewModel 层守卫双保险
            // AI-APP-FIX-106：追加"已选仓库"前置校验（对齐入库弹窗同一写法）。
            confirmEnabled = uiState.selectedWarehouse != null && !uiState.isLoading,
            text = {
                Column {
                    // AI-APP-FIX-106 / BUG-2026-09-26-005：出库仓库是库存扣减的唯一来源，
                    // 选错仓同样是真实账目错误。原弹窗只显示部门/领料人、不显示仓库，
                    // 且确认按钮未做仓库前置校验（入库弹窗 BUG-2026-09-18-010 均已覆盖），
                    // 此处补齐信息展示与校验，四个写路径防线对齐。
                    val wh = uiState.selectedWarehouse
                    if (wh == null) {
                        Text(
                            "尚未选择出库仓库，请先选择仓库",
                            style = MaterialTheme.typography.bodySmall,
                            color = Error,
                            fontWeight = FontWeight.SemiBold
                        )
                    } else {
                        Text(
                            "出库仓库：${wh.code} ${wh.name.orEmpty()}",
                            style = MaterialTheme.typography.bodySmall,
                            color = OnSurfaceVariant
                        )
                    }
                    // BUG-2026-09-18-011：随按钮文案一并统一为「确认出库」。
                    // 原句「…确认提交出库？」与弹窗标题/主按钮的「确认出库」不同词，
                    // 同一屏出现"提交出库/确认出库"两套说法。
                    Text("共 ${uiState.scanLines.size} 种物料，数量 ${formatQuantity(uiState.totalQuantity)}，确认出库？")
                    // 2026-09-12：展示所选领料部门/领料人，提交前最后确认
                    uiState.selectedDepartment?.let {
                        Text("领料部门：${it.name.orEmpty()}", style = MaterialTheme.typography.bodySmall, color = OnSurfaceVariant)
                    }
                    uiState.selectedEmployee?.let {
                        Text("领料人：${it.name.orEmpty()}", style = MaterialTheme.typography.bodySmall, color = OnSurfaceVariant)
                    }
                }
            }
        )
    }
}

@Composable
private fun PrintConfirmationDialog(
    info: SubmittedPrintInfo,
    loading: Boolean,
    onPrint: () -> Unit,
    onLater: () -> Unit
) {
    AlertDialog(
        onDismissRequest = onLater,
        shape = RoundedCornerShape(20.dp),
        icon = {
            Icon(
                Icons.Outlined.Print,
                null,
                tint = Primary,
                modifier = Modifier.size(30.dp)
            )
        },
        title = { Text("单据提交成功", fontWeight = FontWeight.SemiBold) },
        text = {
            Text(
                info.orderNo?.let { "单号：$it\n现在加入打印队列？" }
                    ?: "现在加入打印队列？"
            )
        },
        confirmButton = {
            Button(
                onClick = onPrint,
                enabled = !loading,
                shape = RoundedCornerShape(12.dp)
            ) {
                if (loading) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(18.dp),
                        color = Color.White,
                        strokeWidth = 2.dp
                    )
                } else {
                    Icon(Icons.Outlined.Print, null, modifier = Modifier.size(18.dp))
                    Spacer(modifier = Modifier.width(6.dp))
                    Text("打印单据")
                }
            }
        },
        dismissButton = {
            TextButton(onClick = onLater) {
                Text("稍后打印")
            }
        }
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun StockQueryScreen(
    viewModel: ScanViewModel,
    onBack: () -> Unit,
    /**
     * AI-APP-FIX-507：外部跳转入站预填（识物结果"查该物料库存"CTA）。
     * 消费一次即回调 [onPrefillConsumed] 清空（与出库页 voicePrefillLines 同口径）。
     */
    prefillCode: String? = null,
    onPrefillConsumed: () -> Unit = {}
) {
    val uiState by viewModel.uiState.collectAsState()
    var manualCode by remember { mutableStateOf("") }
    var showScannerDialog by remember { mutableStateOf(false) }
    var showWarehouseDialog by remember { mutableStateOf(false) }
    // AI-MOB-STOCK-F01：扫码（单个物料详情）/ 列表（按仓分页浏览）两种模式
    var listMode by remember { mutableStateOf(false) }
    val snackbarHostState = remember { SnackbarHostState() }
    // AI-MOB-SCAN-UX-01：扫码反馈（声音+震动）
    val queryContext = LocalContext.current

    LaunchedEffect(uiState.error) {
        uiState.error?.let {
            snackbarHostState.showSnackbar(it, duration = SnackbarDuration.Short)
            viewModel.clearError()
        }
    }

    // AI-MOB-STOCK-F01：列表模式错误（如未选仓/加载失败）单独提示，不吞成静默空列表
    LaunchedEffect(uiState.stockListError) {
        uiState.stockListError?.let {
            snackbarHostState.showSnackbar(it, duration = SnackbarDuration.Short)
            viewModel.clearStockListError()
        }
    }

    LaunchedEffect(uiState.scannedCode) {
        if (uiState.scannedCode.isNotEmpty()) {
            viewModel.searchMaterialByCode(uiState.scannedCode)
        }
    }

    // AI-APP-FIX-507：识物结果 CTA 跳入——按预填编码直接查询并回显到搜索框
    LaunchedEffect(prefillCode) {
        if (!prefillCode.isNullOrBlank()) {
            listMode = false
            manualCode = prefillCode
            viewModel.clearMaterialSuggestions()
            viewModel.searchMaterialByCode(prefillCode)
            onPrefillConsumed()
        }
    }

    LaunchedEffect(showScannerDialog) {
        if (!showScannerDialog) {
            viewModel.clearScannedCode()
        }
    }

    // 进入页面即加载仓库（默认选中首仓），查库存按所选仓库口径返回仓库级账面库存
    LaunchedEffect(Unit) {
        if (uiState.warehouses.isEmpty() && !uiState.warehousesLoading) {
            viewModel.loadWarehouses()
        }
    }

    Scaffold(
        snackbarHost = { SnackbarHost(snackbarHostState) },
        containerColor = Background,
        topBar = {
            WmsGradientHeader(
                title = "查库存",
                subtitle = "输入关键词或扫描条码查询库存",
                accent = CardOrange,
                onBack = onBack
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp)
        ) {
            // 仓库选择：查库存按所选仓库口径返回该仓账面库存
            // AI-APP-FIX-406：WarehouseSelectorCard 并入 PartySelectorCard（同款视觉，消除重复实现）
                PartySelectorCard(
                    label = "查询仓库",
                    placeholder = "请选择仓库",
                    valueText = uiState.selectedWarehouse?.let { "${it.code} ${it.name.orEmpty()}" },
                    icon = Icons.Outlined.Warehouse,
                    accentColor = CardOrange,
                    onClick = { showWarehouseDialog = true }
                )

            Spacer(modifier = Modifier.height(4.dp))

            // ── AI-MOB-STOCK-F01：扫码（单个物料）/ 列表（按仓分页浏览）模式切换 ──
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                FilterChip(
                    selected = !listMode,
                    onClick = { listMode = false },
                    label = { Text("扫码查物料") },
                    modifier = Modifier.weight(1f).height(WmsDimens.TouchTargetMin)
                )
                FilterChip(
                    selected = listMode,
                    onClick = {
                        listMode = true
                        // 已有结果则不重复请求，保证切换回来时状态不丢
                        if (!uiState.stockListLoaded && !uiState.stockListLoading) {
                            viewModel.loadStockList()
                        }
                    },
                    label = { Text("库存列表") },
                    modifier = Modifier.weight(1f).height(WmsDimens.TouchTargetMin)
                )
            }

            Spacer(modifier = Modifier.height(4.dp))

            if (listMode) {
                // 外层 Column 已有仓库选择与模式切换，列表区占满剩余高度，内部分页滚动
                StockListSection(
                    uiState = uiState,
                    onKeywordChange = { viewModel.onStockListKeywordChange(it) },
                    onSubmit = { viewModel.loadStockList() },
                    onLoadMore = { viewModel.loadMoreStockList() },
                    onSortChange = { viewModel.setStockListSort(it) },
                    onFilterChange = { viewModel.setStockListFilter(it) },
                    modifier = Modifier.weight(1f)
                )
            } else {
            // Search bar
            Card(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(16.dp),
                elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
                colors = CardDefaults.cardColors(containerColor = CardBackground)
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(4.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    OutlinedTextField(
                        value = manualCode,
                        onValueChange = {
                            manualCode = it
                            // 输入即按 名称/规格/品牌 模糊联想候选，并清掉上一次的查询结果卡片
                            if (uiState.scannedMaterial != null) viewModel.clearScannedMaterial()
                            viewModel.searchMaterialSuggestions(it)
                        },
                        placeholder = { Text("输入名称/规格/品牌，或扫描条码") },
                        singleLine = true,
                        modifier = Modifier.weight(1f),
                        shape = RoundedCornerShape(12.dp),
                        // BUG-2026-09-10-002：键盘搜索键与放大镜按钮同口径——
                        // 精确编码未命中时回退模糊列表，不再只弹「物料不存在」
                        keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                        keyboardActions = KeyboardActions(onSearch = {
                            if (manualCode.isNotBlank()) {
                                viewModel.queryMaterialByKeyword(manualCode.trim())
                            }
                        }),
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedBorderColor = Color.Transparent,
                            unfocusedBorderColor = Color.Transparent
                        )
                    )
                    IconButton(
                        onClick = { showScannerDialog = true },
                        modifier = Modifier.size(48.dp),
                        colors = IconButtonDefaults.iconButtonColors(
                            contentColor = CardOrange
                        )
                    ) {
                        Icon(Icons.Outlined.QrCodeScanner, "扫码", modifier = Modifier.size(24.dp))
                    }
                    FilledIconButton(
                        onClick = {
                            if (manualCode.isNotBlank()) {
                                // BUG-2026-09-10-002：精确编码未命中时回退模糊列表
                                // （含名称/规格/品牌全部命中物料），不再只弹「物料不存在」
                                viewModel.queryMaterialByKeyword(manualCode.trim())
                            }
                        },
                        modifier = Modifier.size(48.dp),
                        shape = RoundedCornerShape(12.dp),
                        colors = IconButtonDefaults.filledIconButtonColors(
                            containerColor = CardOrange
                        )
                    ) {
                        Icon(Icons.Outlined.Search, "查询", tint = Color.White, modifier = Modifier.size(22.dp))
                    }
                }
            }

            // 关键词模糊联想加载指示
            if (manualCode.isNotBlank() && uiState.materialSuggestionsLoading) {
                LinearProgressIndicator(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(top = 4.dp),
                    color = CardOrange,
                    trackColor = CardOrange.copy(alpha = 0.12f)
                )
            }

            // 关键词模糊候选：物料名称/规格/品牌 命中即列出，点选某个规格后查该物料库存
            if (manualCode.isNotBlank() && uiState.scannedMaterial == null && uiState.materialSuggestions.isNotEmpty()) {
                Spacer(modifier = Modifier.height(8.dp))
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(16.dp),
                    elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
                    colors = CardDefaults.cardColors(containerColor = CardBackground)
                ) {
                    // BUG-2026-09-10-002：候选列出全部命中物料（不再 take(8) 截断），
                    // 高度受限内部可滚动；名称/规格/品牌逐行完整显示，不做省略号截断。
                    // AI-APP-FIX-502：Column+verticalScroll 改 LazyColumn——候选是
                    // 不定长列表，LazyColumn 只组合可见项，几百条命中时不掉帧。
                    LazyColumn(
                        modifier = Modifier
                            .fillMaxWidth()
                            .heightIn(max = 360.dp)
                    ) {
                        val visibleSuggestions = uiState.materialSuggestions
                        itemsIndexed(
                            visibleSuggestions,
                            key = { _, material -> material.code ?: material.hashCode().toString() }
                        ) { index, material ->
                            val specBrand = listOfNotNull(
                                material.spec?.takeIf { it.isNotBlank() }?.let { "规格: $it" },
                                material.brand?.takeIf { it.isNotBlank() }?.let { "品牌: $it" }
                            ).joinToString("   ")
                            Column(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .clickable {
                                        manualCode = material.code.orEmpty()
                                        if (uiState.selectedWarehouse != null) {
                                            // 已选仓库：按该仓口径实时查询仓库级账面库存
                                            viewModel.clearMaterialSuggestions()
                                            viewModel.searchMaterialByCode(material.code.orEmpty())
                                        } else {
                                            // 未选仓库：候选即为全局口径，直接展示（无需二次请求）
                                            viewModel.selectMaterialSuggestion(material)
                                        }
                                    }
                                    .padding(horizontal = 16.dp, vertical = 12.dp)
                            ) {
                                Text(
                                    material.code.orEmpty(),
                                    style = MaterialTheme.typography.titleSmall,
                                    fontWeight = FontWeight.Bold,
                                    color = Primary
                                )
                                if (!material.name.isNullOrBlank()) {
                                    Spacer(modifier = Modifier.height(2.dp))
                                    Text(
                                        material.name.orEmpty(),
                                        style = MaterialTheme.typography.bodyMedium,
                                        color = MaterialTheme.colorScheme.onSurface
                                    )
                                }
                                if (specBrand.isNotBlank()) {
                                    Spacer(modifier = Modifier.height(2.dp))
                                    Text(
                                        specBrand,
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant
                                    )
                                }
                            }
                            if (index < visibleSuggestions.size - 1) {
                                HorizontalDivider(color = SurfaceVariant, thickness = 0.5.dp)
                            }
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            // Empty state guidance when no results
            if (!uiState.isLoading && uiState.scannedMaterial == null &&
                uiState.materialSuggestions.isEmpty() && !uiState.materialSuggestionsLoading
            ) {
                Box(
                    modifier = Modifier
                        .weight(1f)
                        .fillMaxWidth(),
                    contentAlignment = Alignment.Center
                ) {
                    if (manualCode.isNotBlank()) {
                        WmsEmptyState(
                            icon = Icons.Outlined.Search,
                            title = "未找到包含「$manualCode」的物料",
                            subtitle = "支持名称/规格/品牌模糊匹配，换个关键词试试",
                            accentColor = CardOrange
                        )
                    } else {
                        WmsEmptyState(
                            icon = Icons.Outlined.Search,
                            title = "输入或扫描物料编码",
                            subtitle = "支持名称/规格/品牌关键词模糊联想",
                            accentColor = CardOrange
                        )
                    }
                }
            } else if (!uiState.isLoading) {
                Spacer(modifier = Modifier.height(16.dp))
            }

            // Loading
            if (uiState.isLoading) {
                Box(
                    modifier = Modifier.fillMaxWidth().padding(40.dp),
                    contentAlignment = Alignment.Center
                ) {
                    CircularProgressIndicator(color = CardOrange)
                }
            }

            // Result
            uiState.scannedMaterial?.let { material ->
                // AI-APP-FIX-501：结果卡整体限高可滚动——开启库位管理后"库位分布"
                // 可能几十行，此前卡片无限撑高，库位列表被屏幕底裁掉且无处滚动。
                // weight(1f, fill=false)：内容短时不强制占满，长时占满剩余空间并
                // 内部滚动。嵌套安全：模糊候选列表与结果卡互斥（候选仅在
                // scannedMaterial == null 时展示），不存在同屏双滚动容器。
                Column(
                    modifier = Modifier
                        .weight(1f, fill = false)
                        .verticalScroll(rememberScrollState())
                ) {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(20.dp),
                    elevation = CardDefaults.cardElevation(defaultElevation = 4.dp),
                    colors = CardDefaults.cardColors(containerColor = CardBackground)
                ) {
                    Column(modifier = Modifier.padding(20.dp)) {
                        // AI-MOB-OFFLINE-HINT-01：缓存回退时必须显著提示。
                        // 不给提示的话，用户无法区分「实时库存 5」和「三天前的 5」，
                        // 看到数字就出库 —— 这是业务风险，不是体验问题。
                        if (material.fromCache) {
                            OfflineDataBanner(cachedAtMillis = material.cachedAtMillis)
                            Spacer(modifier = Modifier.height(12.dp))
                        }
                        // BUG-2026-09-18-003：徽标改两级判定（与服务端 _material_alert_status_values 同口径），
                        // 不再只比 minStock —— 低于安全库存(danger)但高于最低库存的物料此前误显示「库存充足」。
                        // 安全库存 = max(reorderPoint, minStock)；未设阈值的物料退回 充足/不足 二态（保持原行为）。
                        val scanStock = material.stock ?: 0.0
                        val scanMinStock = material.minStock ?: 0.0
                        val scanSafetyStock = maxOf(material.reorderPoint ?: 0.0, scanMinStock)
                        val scanHasThreshold = scanMinStock > 0.0 || scanSafetyStock > 0.0
                        val scanBadge = when {
                            !scanHasThreshold -> if (scanStock > 0.0)
                                Triple("库存充足", Success, SuccessContainer)
                            else Triple("库存不足", Error, ErrorContainer)
                            scanStock <= scanMinStock -> Triple("低于最低库存", Error, ErrorContainer)
                            scanStock <= scanSafetyStock -> Triple("低于安全库存", Warning, WarningContainer)
                            else -> Triple("库存充足", Success, SuccessContainer)
                        }
                        // Header
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(
                                material.code ?: "",
                                style = MaterialTheme.typography.headlineSmall,
                                fontWeight = FontWeight.Bold,
                                color = Primary,
                                // AI-APP-FIX-508：长编码单行省略，不再把右侧状态徽标挤出屏外
                                modifier = Modifier.weight(1f),
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis
                            )
                            Surface(
                                shape = RoundedCornerShape(20.dp),
                                color = scanBadge.third
                            ) {
                                Text(
                                    scanBadge.first,
                                    modifier = Modifier.padding(horizontal = 14.dp, vertical = 6.dp),
                                    color = scanBadge.second,
                                    fontSize = 13.sp,
                                    fontWeight = FontWeight.SemiBold
                                )
                            }
                        }

                        Spacer(modifier = Modifier.height(4.dp))

                        Text(
                            material.name ?: "",
                            style = MaterialTheme.typography.titleMedium,
                            color = MaterialTheme.colorScheme.onSurface
                        )

                        if (!material.spec.isNullOrBlank()) {
                            Spacer(modifier = Modifier.height(2.dp))
                            Text(
                                "规格: ${material.spec}",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }

                        if (!material.brand.isNullOrBlank()) {
                            Text(
                                material.brand,
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }

                        Spacer(modifier = Modifier.height(20.dp))

                        // Divider
                        HorizontalDivider(
                            color = SurfaceVariant,
                            thickness = 1.dp
                        )

                        Spacer(modifier = Modifier.height(16.dp))

                        // Info grid
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceEvenly
                        ) {
                            WmsInfoCell("库存数量", formatQuantity(material.stock ?: 0.0))
                            WmsInfoCell("单位", material.unit ?: "-")
                            WmsInfoCell("最低库存", formatQuantity((material.minStock ?: 0).toDouble()))
                        }

                        Spacer(modifier = Modifier.height(16.dp))

                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceEvenly
                        ) {
                            WmsInfoCell("单价", "¥${"%.2f".format(material.price ?: 0.0)}")
                            // AI-CI-GREEN-005-F04：这里读的是 reorderPoint，对外叫「安全库存」，
                            // 与 PC 物料档案表单、Excel 表头保持一致（命名表见服务端
                            // models/master_data.py 的「库存阈值命名约定」）。
                            WmsInfoCell("安全库存", formatQuantity((material.reorderPoint ?: 0).toDouble()))
                            WmsInfoCell("分类", material.category ?: "-")
                        }

                        // BUG-2026-09-10-003：库位分布——现场找货第二高频问题「货在哪个
                        // 库位、各多少」。开启库位管理时后端下发各库位数量，逐行展示。
                        if (!material.locations.isNullOrEmpty()) {
                            Spacer(modifier = Modifier.height(16.dp))
                            HorizontalDivider(
                                color = SurfaceVariant,
                                thickness = 1.dp
                            )
                            Spacer(modifier = Modifier.height(12.dp))
                            Text(
                                "库位分布",
                                style = MaterialTheme.typography.titleSmall,
                                fontWeight = FontWeight.SemiBold,
                                color = MaterialTheme.colorScheme.onSurface
                            )
                            Spacer(modifier = Modifier.height(8.dp))
                            material.locations.orEmpty().forEach { loc ->
                                Row(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .padding(vertical = 4.dp),
                                    horizontalArrangement = Arrangement.SpaceBetween,
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Text(
                                        loc.location.orEmpty(),
                                        style = MaterialTheme.typography.bodyMedium,
                                        color = MaterialTheme.colorScheme.onSurface
                                    )
                                    Text(
                                        formatQuantity(loc.quantity ?: 0.0),
                                        style = MaterialTheme.typography.bodyMedium,
                                        fontWeight = FontWeight.Bold,
                                        color = Primary
                                    )
                                }
                            }
                        }

                        if (!material.supplier.isNullOrBlank()) {
                            Spacer(modifier = Modifier.height(16.dp))
                            HorizontalDivider(
                                color = SurfaceVariant,
                                thickness = 1.dp
                            )
                            Spacer(modifier = Modifier.height(12.dp))
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Icon(
                                    Icons.Outlined.Business,
                                    null,
                                    tint = OnSurfaceVariant,
                                    modifier = Modifier.size(16.dp)
                                )
                                Spacer(modifier = Modifier.width(6.dp))
                                Text(
                                    "供应商: ${material.supplier}",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant
                                )
                            }
                        }
                    }
                }
                }
            }
            }  // end else (扫码模式)
        }
    }

    if (showScannerDialog) {
        ScannerDialog(
            onDismiss = { showScannerDialog = false },
            // 查库存是"扫一个看一个"的场景，扫中即退出，保持旧行为不启用连续扫描。
            continuous = false,
            onBarcodeScanned = { barcode ->
                showScannerDialog = false
                manualCode = barcode
                viewModel.clearMaterialSuggestions()
                // AI-MOB-SCAN-UX-01：查库存同样是"扫到就想知道结果"的场景，
                // 声音+震动让工人不用盯着屏幕等查询返回。
                // AI-APP-FIX-503：反馈音由本次 searchMaterialByCode 的结果驱动，
                // 不再另发一次 materialExists 重复请求（扫一个码打两次后端）。
                viewModel.searchMaterialByCode(barcode) { found ->
                    if (found) {
                        ScanFeedback.success(queryContext)
                    } else {
                        ScanFeedback.failure(queryContext)
                    }
                }
            }
        )
    }

    if (showWarehouseDialog) {
        WarehousePickerDialog(
            warehouses = uiState.warehouses,
            selected = uiState.selectedWarehouse,
            loading = uiState.warehousesLoading,
            onDismiss = { showWarehouseDialog = false },
            onSelect = { warehouse ->
                viewModel.selectWarehouse(warehouse)
                showWarehouseDialog = false
                // 已有查询结果时，按新选仓库口径刷新该物料的仓库级账面库存
                uiState.scannedMaterial?.code?.let { viewModel.searchMaterialByCode(it) }
            },
            onRetry = { viewModel.loadWarehouses() },
            accentColor = CardOrange
        )
    }
}

/**
 * AI-MOB-STOCK-F01：查库存「列表模式」区块。
 *
 * 按关键字在**所选仓库**内分页浏览库存（仓库级账面库存，复用
 * `/api/mobile/stock/query`）。列表滚到底部自动加载下一页（R1：按 total_pages
 * 翻页取全，不把默认 page_size 当业务上限）。
 *
 * 三种空态明确区分，避免"没有数据"与"没查过/没选仓"混淆：
 * - 未查询过 → 提示输入关键字或直接查询该仓全部物料
 * - 已查询且结果为空 → 「未找到包含 X 的物料」
 * - 未选仓库 → 由 ViewModel 拦截并给出「请先选择仓库」，不拉全量
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun StockListSection(
    uiState: com.factory.wms.ui.viewmodel.scan.ScanUiState,
    onKeywordChange: (String) -> Unit,
    onSubmit: () -> Unit,
    onLoadMore: () -> Unit,
    onSortChange: (String) -> Unit,
    onFilterChange: (String) -> Unit,
    modifier: Modifier = Modifier
) {
    // 关键字输入防抖后自动查询，减少无谓请求（与页内其它搜索一致的手感）。
    // P2-2：原 300ms 对中文输入法偏激进——输入法组合期逐字上屏，打"深沟球轴承"
    // 会连发 4~5 个请求，仓库弱网下表现为列表反复闪烁。放宽到 500ms；
    // 请求本身的取消与乱序丢弃由 ViewModel 的 stockListJob + 序号兜底。
    LaunchedEffect(uiState.stockListKeyword) {
        if (uiState.stockListKeyword.isBlank() && !uiState.stockListLoaded) return@LaunchedEffect
        delay(500)
        onSubmit()
    }

    Column(modifier = modifier.fillMaxWidth()) {

    // 搜索栏
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
        colors = CardDefaults.cardColors(containerColor = CardBackground)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(4.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            OutlinedTextField(
                value = uiState.stockListKeyword,
                onValueChange = onKeywordChange,
                placeholder = { Text("输入编码/名称/规格筛选，留空看全部") },
                singleLine = true,
                modifier = Modifier.weight(1f),
                shape = RoundedCornerShape(12.dp),
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                keyboardActions = KeyboardActions(onSearch = { onSubmit() }),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = Color.Transparent,
                    unfocusedBorderColor = Color.Transparent
                )
            )
            FilledIconButton(
                onClick = onSubmit,
                modifier = Modifier.size(48.dp),
                shape = RoundedCornerShape(12.dp),
                colors = IconButtonDefaults.filledIconButtonColors(containerColor = CardOrange)
            ) {
                Icon(Icons.Outlined.Search, "查询", tint = Color.White, modifier = Modifier.size(22.dp))
            }
        }
    }

    // ── AI-MOB-STOCK-F02：排序 + 库存筛选 ──
    // 排序/筛选都在服务端对全集生效（不是只排当前页），故切换后由 ViewModel
    // 回到第 1 页重新拉取，不能只重排本地已加载的 items。
    Spacer(modifier = Modifier.height(8.dp))
    StockListSortFilterBar(
        sort = uiState.stockListSort,
        filter = uiState.stockListFilter,
        onSortChange = onSortChange,
        onFilterChange = onFilterChange
    )

    // 结果总数提示（分页元数据来自服务端，R1）
    if (uiState.stockListLoaded && uiState.stockListTotal > 0) {
        Spacer(modifier = Modifier.height(8.dp))
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                "共 ${uiState.stockListTotal} 条" +
                    if (uiState.selectedWarehouse != null) "（${uiState.selectedWarehouse.name ?: ""}）" else "",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.weight(1f)
            )
            // P2-3：在线查询此前没有任何"数据截止时间"，而查库存是要拿来决策
            // （要不要领、领多少）的，没有时点用户无法判断看到的是实时值还是
            // 几分钟前的。由服务端下发 hh:mm，避免手机时区不准显示错时间。
            val serverTime = uiState.stockListServerTime
            if (!serverTime.isNullOrBlank()) {
                Text(
                    "数据截止 $serverTime",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }

    Spacer(modifier = Modifier.height(8.dp))

    when {
        uiState.stockListLoading -> {
            Box(
                modifier = Modifier.fillMaxWidth().padding(40.dp),
                contentAlignment = Alignment.Center
            ) {
                CircularProgressIndicator(color = CardOrange)
            }
        }

        uiState.stockListLoaded && uiState.stockListItems.isEmpty() -> {
            // P1-3：空态必须分流。这个接口是仓库级语义，"搜不到"其实是两件事：
            //   ① 物料档案里根本没这个编码 → 该去建档；
            //   ② 档案里有，但这个仓没货 / 被"仅有货"等筛选排除 → 该换仓改筛选。
            // 原来两句并一句，作业员看到"未找到"就跑去建档，白跑一趟。
            // keywordMaterialTotal 为 null 表示服务端未下发该字段（老版本），
            // 此时退回原文案，不猜——猜错比不改更糟。
            val hitsInArchive = uiState.stockListKeywordMaterialTotal
            val emptyTitle = when {
                uiState.stockListKeyword.isBlank() -> "该仓库暂无物料库存记录"
                hitsInArchive == null -> "未找到包含「${uiState.stockListKeyword}」的物料"
                hitsInArchive == 0 -> "物料档案中没有「${uiState.stockListKeyword}」"
                else -> "「${uiState.stockListKeyword}」在本仓没有符合条件的库存"
            }
            val emptySubtitle = when {
                uiState.stockListKeyword.isBlank() -> "可切换仓库或换个关键词试试"
                hitsInArchive == null -> "可切换仓库或换个关键词试试"
                hitsInArchive == 0 -> "请先确认编码是否输错，或在电脑端建档"
                else -> "档案里能查到 $hitsInArchive 条，可切换仓库或取消筛选再看"
            }
            Box(
                modifier = Modifier.fillMaxWidth().padding(top = 40.dp),
                contentAlignment = Alignment.Center
            ) {
                WmsEmptyState(
                    icon = Icons.Outlined.Search,
                    title = emptyTitle,
                    subtitle = emptySubtitle,
                    accentColor = CardOrange
                )
            }
        }

        uiState.stockListItems.isNotEmpty() -> {
            LazyColumn(
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(1f),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                // BUG-2026-09-14-031：key 不得用 `id ?: 0`——id 为可空 Int?，多条为 null 时
                // key 全等 0，Compose 抛 IllegalArgumentException 直接崩溃（LazyColumn 要求
                // key 唯一）。三级兜底：id → 物料编码 → hashCode，hashCode 与对象内容绑定，
                // 同页出现两条相同物料时概率可忽略，且远优于让崩溃发生。
                items(uiState.stockListItems, key = { it.id ?: it.code ?: it.hashCode() }) { material ->
                    StockListRow(material)
                }
                if (uiState.stockListLoadingMore) {
                    item {
                        Box(
                            modifier = Modifier.fillMaxWidth().padding(16.dp),
                            contentAlignment = Alignment.Center
                        ) {
                            CircularProgressIndicator(
                                modifier = Modifier.size(24.dp),
                                color = CardOrange
                            )
                        }
                    }
                } else if (uiState.stockListPage < uiState.stockListTotalPages) {
                    // 滚到底部触发下一页（R1）
                    item {
                        LaunchedEffect(uiState.stockListPage) { onLoadMore() }
                        Spacer(modifier = Modifier.height(8.dp))
                    }
                }
            }
        }

        else -> {
            Box(
                modifier = Modifier.fillMaxWidth().padding(top = 40.dp),
                contentAlignment = Alignment.Center
            ) {
                WmsEmptyState(
                    icon = Icons.Outlined.Search,
                    title = "输入关键字或留空查询该仓全部物料",
                    subtitle = "结果按仓库口径显示账面库存，可滚动分页加载",
                    accentColor = CardOrange
                )
            }
        }
    }
    }  // end Column（列表区容器）
}

/**
 * AI-MOB-STOCK-F02：查库存列表的排序与筛选条。
 *
 * 排序按**仓库级库存**（服务端实时聚合值），不是全局 Material.stock；
 * 切换后由服务端对全集重排并回到第 1 页，避免"只排当前页"的假排序。
 */
@Composable
private fun StockListSortFilterBar(
    sort: String,
    filter: String,
    onSortChange: (String) -> Unit,
    onFilterChange: (String) -> Unit
) {
    Column(modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier.horizontalScroll(rememberScrollState()),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            FilterChip(
                selected = sort.isBlank(),
                modifier = Modifier.height(WmsDimens.TouchTargetMin),
                onClick = { onSortChange("") },
                label = { Text("默认排序") }
            )
            FilterChip(
                selected = sort == "stock_desc",
                modifier = Modifier.height(WmsDimens.TouchTargetMin),
                onClick = { onSortChange("stock_desc") },
                label = { Text("库存多→少") }
            )
            FilterChip(
                selected = sort == "stock_asc",
                modifier = Modifier.height(WmsDimens.TouchTargetMin),
                onClick = { onSortChange("stock_asc") },
                label = { Text("库存少→多") }
            )
        }
        Spacer(modifier = Modifier.height(4.dp))
        Row(
            modifier = Modifier.horizontalScroll(rememberScrollState()),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            FilterChip(
                selected = filter.isBlank(),
                modifier = Modifier.height(WmsDimens.TouchTargetMin),
                onClick = { onFilterChange("") },
                label = { Text("全部") }
            )
            FilterChip(
                selected = filter == "nonzero",
                modifier = Modifier.height(WmsDimens.TouchTargetMin),
                onClick = { onFilterChange("nonzero") },
                label = { Text("仅有货") }
            )
            FilterChip(
                selected = filter == "zero",
                modifier = Modifier.height(WmsDimens.TouchTargetMin),
                onClick = { onFilterChange("zero") },
                label = { Text("零库存") }
            )
            FilterChip(
                selected = filter == "low",
                modifier = Modifier.height(WmsDimens.TouchTargetMin),
                onClick = { onFilterChange("low") },
                label = { Text("低于安全线") }
            )
        }
    }
}

/** AI-MOB-STOCK-F01：列表模式单行——编码/名称/规格 + 仓库级账面库存数量。 */
@Composable
private fun StockListRow(material: com.factory.wms.data.model.MaterialDto) {
    val stock = material.stock ?: 0.0
    val minStock = material.minStock ?: 0.0
    // BUG-2026-09-18-003：安全库存 = max(reorderPoint, minStock)，与服务端 safety_stock 同口径。
    val safetyStock = maxOf(material.reorderPoint ?: 0.0, minStock)
    // P2-4：零库存行原本与有货行视觉完全一致（同样的蓝编码、同样的红/绿数字），
    // 一屏十条扫下来分不出哪些是真能领的。这里做弱化：主色编码与数量都降到
    // 次要灰、卡片压平，并补一个"无库存"标记。不隐藏——有时就是要确认"确实为 0"。
    // 用配色而非 alpha 实现：本文件没有 androidx.compose.ui.draw.alpha 的既有
    // 用法，不为一个无法本地编译验证的新 import 冒险。
    val noStock = stock <= 0.0
    val mutedColor = MaterialTheme.colorScheme.onSurfaceVariant
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(14.dp),
        elevation = CardDefaults.cardElevation(defaultElevation = if (noStock) 0.dp else 1.dp),
        colors = CardDefaults.cardColors(containerColor = CardBackground)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 12.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    material.code.orEmpty(),
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.Bold,
                    color = if (noStock) mutedColor else Primary,
                    // AI-APP-FIX-508：长编码单行省略（同行右侧还有数量列）
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
                if (!material.name.isNullOrBlank()) {
                    Spacer(modifier = Modifier.height(2.dp))
                    Text(
                        material.name.orEmpty(),
                        style = MaterialTheme.typography.bodyMedium,
                        color = if (noStock) mutedColor else MaterialTheme.colorScheme.onSurface,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis
                    )
                }
                val specLine = listOfNotNull(
                    material.spec?.takeIf { it.isNotBlank() }?.let { "规格: $it" },
                    material.brand?.takeIf { it.isNotBlank() }?.let { "品牌: $it" }
                ).joinToString("   ")
                if (specLine.isNotBlank()) {
                    Spacer(modifier = Modifier.height(2.dp))
                    Text(
                        specLine,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis
                    )
                }
            }
            Spacer(modifier = Modifier.width(10.dp))
            Column(horizontalAlignment = Alignment.End) {
                Text(
                    formatQuantity(stock),
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    // BUG-2026-09-18-003：两级判定——破最低库存红线=红、破安全库存预警线=黄、
                    // 其余=绿；不再只比 minStock，否则 danger 档(低于安全库存)会误显绿色。
                    color = if (noStock) mutedColor
                    else if (stock <= minStock) Error
                    else if (stock <= safetyStock) Warning
                    else Success
                )
                if (!material.unit.isNullOrBlank()) {
                    Text(
                        material.unit,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
                if (noStock) {
                    Text(
                        "无库存",
                        style = MaterialTheme.typography.labelSmall,
                        color = mutedColor
                    )
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun StocktakeScreen(
    viewModel: ScanViewModel,
    onBack: () -> Unit,
    onRecognize: () -> Unit = {}
) {
    val uiState by viewModel.uiState.collectAsState()
    var showSubmitDialog by remember { mutableStateOf(false) }
    var showScannerDialog by remember { mutableStateOf(false) }
    var showWarehouseDialog by remember { mutableStateOf(false) }
    // INV-BATCH-001-E：盘点必须先选电脑端建好的进行中盘点单
    var showCheckOrderDialog by remember { mutableStateOf(false) }
    var manualCode by remember { mutableStateOf("") }
    var manualQty by remember { mutableStateOf("1") }
    var stocktakeArea by remember { mutableStateOf("") }
    val snackbarHostState = remember { SnackbarHostState() }
    val scope = rememberCoroutineScope()
    // BUG-2026-09-03-003：盘点重复扫码须确认，防止误把已盘物料再次累加使实盘数翻倍
    var confirmLine by remember { mutableStateOf<ScanLine?>(null) }

    fun addOrConfirmStocktakeLine(line: ScanLine) {
        val exists = viewModel.uiState.value.scanLines.any { it.material_code == line.material_code && it.location_code.orEmpty() == line.location_code.orEmpty() }
        if (exists) {
            confirmLine = line
        } else {
            viewModel.addScanLine(line)
        }
    }

    // AI-APP-FIX-403：局部 formatStockQty 已合并为 ui/util/Format.kt 的 formatQty

    LaunchedEffect(Unit) {
        if (uiState.warehouses.isEmpty() && !uiState.warehousesLoading) {
            viewModel.loadWarehouses()
        }
    }

    // AI-APP-FIX-207：盘点页此前从不拉库位配置，locationEnabled 恒为 null，
    // 「盘点库位/区域」的提示文案只能靠猜。选仓后拉取配置，提示与提交校验
    // 才能对齐服务端"启用库位管理且有差异时必填"的口径。
    LaunchedEffect(uiState.selectedWarehouse) {
        if (uiState.selectedWarehouse != null) {
            viewModel.loadLocationOptions()
        }
    }

    // BUG-2026-09-03-003 断点续盘：进入盘点页先尝试恢复上次未提交清单
    LaunchedEffect(Unit) {
        viewModel.maybeRestoreStocktakeDraft()
    }

    // BUG-2026-09-03-003 断点续盘：清单变化防抖写入本地草稿（进程被杀/误关可恢复）
    LaunchedEffect(uiState.scanLines, uiState.selectedWarehouse) {
        if (uiState.scanLines.isNotEmpty()) {
            delay(600)
            viewModel.persistStocktakeDraft()
        }
    }
    LaunchedEffect(uiState.error) {
        uiState.error?.let {
            snackbarHostState.showSnackbar(it, duration = SnackbarDuration.Short)
            viewModel.clearError()
        }
    }
    LaunchedEffect(uiState.success) {
        uiState.success?.let {
            snackbarHostState.showSnackbar(it, duration = SnackbarDuration.Long)
            viewModel.clearSuccess()
        }
    }

    ScanScreenBase(
        // BUG-2026-09-18-007：同入库/出库页，标题与业务动作一致。
        // 该页同样支持扫码、手工输入与"识物盘点"，且入口来自盘点单/首页，
        // 标题写"扫码"与 HomeScreen 的"盘点"入口语感不一致。
        title = "盘点",
        subtitle = "扫码或手动录入实际库存，生成盘点差异",
        gradient = CardPurple,
        onBack = onBack,
        scanLines = uiState.scanLines,
        totalQuantity = uiState.totalQuantity,
        viewModel = viewModel,
        snackbarHostState = snackbarHostState,
        isLoading = uiState.isLoading,
        showScannerDialog = showScannerDialog,
        onShowScanner = { showScannerDialog = true },
        onDismissScanner = {
            showScannerDialog = false
            viewModel.clearMaterialSuggestions()
        },
        manualCode = manualCode,
        manualQty = manualQty,
        // AI-MOB-ADD-KEYWORD-01：与查库存同口径的关键词模糊联想
        onManualCodeChange = {
            manualCode = it
            viewModel.searchMaterialSuggestions(it)
        },
        onManualQtyChange = { manualQty = it },
        materialSuggestions = uiState.materialSuggestions,
        materialSuggestionsLoading = uiState.materialSuggestionsLoading,
        onMaterialSuggestionSelected = { material ->
            manualCode = material.code.orEmpty()
            viewModel.clearMaterialSuggestions()
        },
        // AI-MOB-OFFLINE-01：断网提交已暂存条数 / 失败条数 / 人工重试
        offlinePendingCount = uiState.offlinePendingCount,
        offlineFailedCount = uiState.offlineFailedCount,
        onRetryOffline = { viewModel.retryOfflineSync() },
        onManualAdd = {
            // AI-APP-FIX-105 / BUG-2026-09-26-001：同入库/出库页，非法数量拦截提示。
            val qty = manualQty.toPositiveQtyOrNull()
            if (manualCode.isNotBlank() && qty != null) {
                addOrConfirmStocktakeLine(
                    ScanLine(
                        material_code = manualCode.trim(),
                        quantity = qty,
                        location_code = stocktakeArea.trim().ifBlank { null }
                    )
                )
                manualCode = ""
                manualQty = "1"
                showScannerDialog = false
            } else if (manualCode.isNotBlank()) {
                scope.launch {
                    snackbarHostState.showSnackbar("请输入大于 0 的有效数量", duration = SnackbarDuration.Short)
                }
            }
        },
        onScanBarcode = { barcode ->
            val qty = manualQty.toPositiveQtyOrNull()
            if (qty != null) {
                addOrConfirmStocktakeLine(
                    ScanLine(
                        material_code = barcode.trim(),
                        quantity = qty,
                        location_code = stocktakeArea.trim().ifBlank { null }
                    )
                )
                manualCode = ""
                manualQty = "1"
            } else {
                scope.launch {
                    snackbarHostState.showSnackbar("请输入大于 0 的有效数量", duration = SnackbarDuration.Short)
                }
            }
        },
        onSubmitClick = { showSubmitDialog = true },
        submitLabel = "提交盘点",
        submitColor = CardPurple,
        // BUG-2026-09-18-009：盘点**不产生出入库单据**，故不需要库位选择器与拍照取证。
        // 这里显式声明为 false —— 原先靠"文案不等于提交入库/出库"隐式决定，
        // 等于把盘点页的行为挂在别人的按钮文案上。
        showLocationSelector = false,
        showEvidenceCapture = false,
        extraActionLabel = "识物盘点",
        onExtraAction = onRecognize,
        header = {
            Column(modifier = Modifier.fillMaxWidth()) {
                // AI-APP-FIX-406：WarehouseSelectorCard 并入 PartySelectorCard（同款视觉，消除重复实现）
                PartySelectorCard(
                    label = "盘点仓库",
                    placeholder = "请选择仓库",
                    valueText = uiState.selectedWarehouse?.let { "${it.code} ${it.name.orEmpty()}" },
                    icon = Icons.Outlined.Warehouse,
                    accentColor = CardPurple,
                    onClick = { showWarehouseDialog = true }
                )
                OutlinedTextField(
                    value = stocktakeArea,
                    onValueChange = { stocktakeArea = it },
                    label = { Text("盘点库位/区域") },
                    singleLine = true,
                    // AI-APP-FIX-406：补 ImeAction（现场戴手套，回车即收键盘）
                    keyboardOptions = KeyboardOptions(imeAction = ImeAction.Done),
                    modifier = Modifier.fillMaxWidth(),
                    // AI-APP-FIX-207：提示对齐库位配置真实状态——启用且未填时
                    // 标红警示（有差异的盘点缺库位会被服务端拒绝）；未启用明示"选填"。
                    supportingText = {
                        when (uiState.locationEnabled) {
                            true -> if (stocktakeArea.isBlank()) {
                                Text(
                                    "已启用库位管理：若盘点有差异，库位必填（建议填写）",
                                    color = MaterialTheme.colorScheme.error
                                )
                            } else {
                                Text("已启用库位管理：有差异时按库位生成调整")
                            }
                            false -> Text("选填（本仓未启用库位管理）")
                            null -> Text("启用库位管理且有差异时必填")
                        }
                    }
                )
                Spacer(modifier = Modifier.height(10.dp))
                // INV-BATCH-001-E：盘点必须选电脑端建好的进行中盘点单
                Spacer(modifier = Modifier.height(10.dp))
                CheckOrderSelectorCard(
                    order = uiState.selectedCheckOrder,
                    ordersEmpty = uiState.checkOrders.isEmpty() &&
                        !uiState.checkOrdersLoading,
                    loading = uiState.checkOrdersLoading,
                    enabled = uiState.selectedWarehouse != null,
                    accentColor = CardPurple,
                    onClick = { showCheckOrderDialog = true }
                )
            }
        }
    )

    if (showWarehouseDialog) {
        WarehousePickerDialog(
            warehouses = uiState.warehouses,
            selected = uiState.selectedWarehouse,
            loading = uiState.warehousesLoading,
            onDismiss = { showWarehouseDialog = false },
            onSelect = { warehouse ->
                viewModel.selectWarehouse(warehouse)
                showWarehouseDialog = false
            },
            onRetry = { viewModel.loadWarehouses() },
            accentColor = CardPurple
        )
    }

    // INV-BATCH-001-E：盘点单选单弹窗（列出所选仓库的进行中盘点单）
    if (showCheckOrderDialog) {
        CheckOrderPickerDialog(
            orders = uiState.checkOrders,
            selected = uiState.selectedCheckOrder,
            loading = uiState.checkOrdersLoading,
            error = uiState.checkOrdersError,
            onDismiss = { showCheckOrderDialog = false },
            onSelect = { order ->
                viewModel.selectCheckOrder(order)
                showCheckOrderDialog = false
            },
            onRefresh = { viewModel.loadPendingCheckOrders() },
            accentColor = CardPurple
        )
    }

    // BUG-2026-09-03-003：盘点重复扫码确认（替换 / 累加 / 取消保持原值）
    confirmLine?.let { line ->
        val existingQty = viewModel.existingLineQuantity(line.material_code, line.location_code)
        AlertDialog(
            onDismissRequest = { confirmLine = null },
            shape = RoundedCornerShape(20.dp),
            title = { Text("物料已在盘点清单", fontWeight = FontWeight.SemiBold) },
            text = {
                Text(
                    "${line.material_code} 已在清单中（当前：${formatQty(existingQty ?: 0.0)}）。\n" +
                        "本次扫码：${formatQty(line.quantity)}。\n\n" +
                        "选择「替换」以本次实盘数量为准；「累加」会把数量相加；" +
                        "点空白处或返回保持原值。"
                )
            },
            confirmButton = {
                Button(
                    onClick = {
                        viewModel.replaceScanLineQuantity(line)
                        confirmLine = null
                    },
                    shape = RoundedCornerShape(12.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = CardPurple)
                ) {
                    Text("替换为本次数量")
                }
            },
            dismissButton = {
                TextButton(
                    onClick = {
                        viewModel.addScanLine(line)
                        confirmLine = null
                    }
                ) {
                    Text("累加")
                }
            }
        )
    }

    if (showSubmitDialog) {
        // AI-APP-FIX-406：自绘弹窗骨架 → WmsSubmitConfirmDialog
        WmsSubmitConfirmDialog(
            title = "确认盘点",
            confirmLabel = "确认盘点",
            onConfirm = {
                showSubmitDialog = false
                viewModel.submitStocktake()
            },
            onDismiss = { showSubmitDialog = false },
            accent = CardPurple,
            // BUG-2026-09-12-010：在原有"仓库+盘点单必选"之上追加"非提交中"，
            // 不能用 isLoading 覆盖前置校验，否则未选盘点单时按钮会变可点。
            confirmEnabled = uiState.selectedWarehouse != null &&
                uiState.selectedCheckOrder != null &&
                !uiState.isLoading,
            text = {
                val wh = uiState.selectedWarehouse
                val co = uiState.selectedCheckOrder
                val base = when {
                    wh == null -> "尚未选择盘点仓库，请先选择仓库"
                    co == null -> "尚未选择盘点单，请先选择进行中的盘点单（电脑端创建后此处选择）"
                    else -> "盘点仓库：${wh.code} ${wh.name.orEmpty()}\n" +
                        "盘点单：${co.checkNo}\n" +
                        "共 ${uiState.scanLines.size} 种物料，确认提交盘点？"
                }
                Column {
                    Text(base)
                    // AI-APP-FIX-207：启用库位管理但未填库位时提交前最后警示。
                    // 注意不硬禁提交：是否有差异由服务端对比账面数后才知道，客户端
                    // 无法预知——硬禁会误伤"无差异"的合法盘点。
                    if (wh != null && co != null &&
                        uiState.locationEnabled == true && stocktakeArea.isBlank()
                    ) {
                        Spacer(Modifier.height(8.dp))
                        Text(
                            "⚠️ 未填写盘点库位：若盘点结果存在差异，服务端将要求补填库位",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.error
                        )
                    }
                }
            }
        )
    }
}

/** INV-BATCH-001-E 盘点单选择卡（盘点提交前必须选电脑端建好的进行中盘点单）。 */
@Composable
private fun CheckOrderSelectorCard(
    order: CheckOrderDto?,
    ordersEmpty: Boolean,
    loading: Boolean,
    enabled: Boolean,
    accentColor: Color,
    onClick: () -> Unit
) {
    val subtitle = when {
        !enabled -> "先选择盘点仓库"
        loading -> "正在加载进行中的盘点单..."
        order != null -> listOfNotNull(
            order.warehouse,
            order.itemCount?.let { "已录 $it 行" }
        ).joinToString(" · ")
        ordersEmpty -> "该仓库暂无进行中的盘点单，请先在电脑端创建"
        else -> "盘点结果将统一记录到该盘点单"
    }
    Card(
        onClick = onClick,
        enabled = enabled,
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(
            containerColor = accentColor.copy(alpha = 0.08f)
        )
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 14.dp, vertical = 12.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(
                Icons.Filled.Description,
                contentDescription = null,
                tint = accentColor
            )
            Spacer(Modifier.width(10.dp))
            Column(Modifier.weight(1f)) {
                Text(
                    if (order != null) "盘点单：${order.checkNo}" else "盘点单（必选）",
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.SemiBold
                )
                Text(
                    subtitle,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis
                )
            }
            if (loading) {
                CircularProgressIndicator(
                    modifier = Modifier.size(16.dp),
                    strokeWidth = 2.dp
                )
            } else {
                Icon(
                    Icons.Filled.ChevronRight,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
}

/** INV-BATCH-001-E 盘点单选单弹窗：列出所选仓库的进行中盘点单。 */
@Composable
private fun CheckOrderPickerDialog(
    orders: List<CheckOrderDto>,
    selected: CheckOrderDto?,
    loading: Boolean,
    error: String?,
    onDismiss: () -> Unit,
    onSelect: (CheckOrderDto) -> Unit,
    onRefresh: () -> Unit,
    accentColor: Color
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        shape = RoundedCornerShape(20.dp),
        title = {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    "选择进行中盘点单",
                    fontWeight = FontWeight.SemiBold,
                    modifier = Modifier.weight(1f)
                )
                TextButton(onClick = onRefresh) { Text("刷新") }
            }
        },
        text = {
            when {
                loading && orders.isEmpty() -> Text("正在加载...")
                // AI-APP-FIX-201：加载失败必须在弹窗内可见（Snackbar 被弹窗遮挡），
                // 否则用户会把"加载失败"误当成"该仓没有进行中盘点单"
                error != null && orders.isEmpty() -> Column {
                    Text(
                        "盘点单加载失败：$error",
                        color = MaterialTheme.colorScheme.error
                    )
                    Spacer(Modifier.height(8.dp))
                    TextButton(onClick = onRefresh) { Text("重试") }
                }
                orders.isEmpty() -> Column(
                    Modifier.verticalScroll(rememberScrollState())
                ) {
                    Text("该仓库暂无进行中的盘点单。")
                    Text("请先在电脑端「盘点管理」创建盘点单后再盘，所有盘点结果将统一记录到该单。")
                }
                else -> Column(
                    Modifier.verticalScroll(rememberScrollState())
                ) {
                    orders.forEach { order ->
                        val isSelected = selected?.id == order.id
                        Card(
                            onClick = { onSelect(order) },
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(vertical = 4.dp),
                            shape = RoundedCornerShape(12.dp),
                            colors = CardDefaults.cardColors(
                                // AI-APP-FIX-301：消灭裸写 Color(0xFFF5F5F5)（暗色下是一块刺眼的亮灰）；
                                // 选中底 alpha 亮 0.14 / 暗 0.24，未选中走 outlineVariant 浅底
                                containerColor = if (isSelected)
                                    accentColor.copy(alpha = MaterialTheme.wmsColors.accentWashAlpha)
                                else MaterialTheme.colorScheme.surfaceVariant
                            )
                        ) {
                            Row(
                                modifier = Modifier.padding(horizontal = 12.dp, vertical = 10.dp),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Icon(
                                    if (isSelected) Icons.Filled.RadioButtonChecked
                                    else Icons.Filled.RadioButtonUnchecked,
                                    contentDescription = null,
                                    tint = if (isSelected) accentColor
                                    else MaterialTheme.colorScheme.onSurfaceVariant
                                )
                                Spacer(Modifier.width(8.dp))
                                Column(Modifier.weight(1f)) {
                                    Text(order.checkNo, fontWeight = FontWeight.SemiBold)
                                    Text(
                                        listOfNotNull(
                                            order.warehouse,
                                            order.itemCount?.let { "已录 $it 行" }
                                        ).joinToString(" · "),
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                                        maxLines = 1,
                                        overflow = TextOverflow.Ellipsis
                                    )
                                }
                            }
                        }
                    }
                }
            }
        },
        confirmButton = {},
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("取消") }
        }
    )
}

/** 出库页合同编号输入卡片（选填）：输入片段实时模糊匹配合同档案，
 * 如输入 0709 可匹配 HD260709；点击建议项回填完整合同编号。 */
@Composable
private fun ContractInputCard(
    contractNo: String,
    suggestions: List<com.factory.wms.data.model.ContractDto>,
    loading: Boolean,
    onContractNoChange: (String) -> Unit,
    onSelect: (com.factory.wms.data.model.ContractDto) -> Unit,
    accentColor: Color
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 4.dp),
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.cardColors(containerColor = CardBackground),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
    ) {
        Column(modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp)) {
            OutlinedTextField(
                value = contractNo,
                onValueChange = onContractNoChange,
                label = { Text("合同编号（选填）") },
                placeholder = { Text("输入片段快速匹配，如 0709") },
                singleLine = true,
                // AI-APP-FIX-406：补 ImeAction
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Done),
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(12.dp),
                leadingIcon = {
                    Icon(
                        Icons.Outlined.Description,
                        null,
                        tint = accentColor,
                        modifier = Modifier.size(20.dp)
                    )
                },
                trailingIcon = {
                    if (loading) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(18.dp),
                            color = accentColor,
                            strokeWidth = 2.dp
                        )
                    }
                }
            )
            if (suggestions.isNotEmpty()) {
                Spacer(modifier = Modifier.height(4.dp))
                // BUG-2026-09-18-006：合同建议原来是无约束的 forEach 平铺。
                // 出库页本卡位于顶部固定区，输入 1 个字符（如 "2"）常能命中十几条合同，
                // 全量展开可高达七八百 dp，把「提交出库」按钮整个顶出屏幕且滚不回来
                // （现场现象：手机端-出库-手工添加 看不到提交按钮）。
                // 与物料候选同口径：限高 + 内部滚动，候选再多也不撑破页面。
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .heightIn(max = 200.dp)
                        .verticalScroll(rememberScrollState())
                ) {
                    suggestions.forEach { contract ->
                        TextButton(
                            onClick = { onSelect(contract) },
                            modifier = Modifier.fillMaxWidth(),
                            contentPadding = PaddingValues(horizontal = 12.dp, vertical = 4.dp)
                        ) {
                            Column(modifier = Modifier.fillMaxWidth()) {
                                Text(
                                    contract.contractNo.orEmpty(),
                                    fontWeight = FontWeight.SemiBold,
                                    fontSize = 14.sp,
                                    color = OnSurface
                                )
                                if (!contract.projectName.isNullOrBlank()) {
                                    Text(
                                        contract.projectName,
                                        style = MaterialTheme.typography.bodySmall,
                                        color = OnSurfaceVariant,
                                        maxLines = 1,
                                        overflow = TextOverflow.Ellipsis
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

/**
 * 入库备注输入卡片（选填，BUG-2026-09-18-008）。
 *
 * 现场常用来记送货单号 / 采购单号 / 随货同行单号——这些信息此前在手机端
 * 完全没有落库入口，只能事后翻纸质单据。留空时后端写默认值
 * 「Android原生端提交」，与旧行为一致。
 *
 * 单行输入、无联想，因此不需要限高（对照 -006：只有"无约束候选列表"才需要限高）。
 */
@Composable
private fun InboundRemarkCard(
    remark: String,
    onRemarkChange: (String) -> Unit,
    accentColor: Color
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 4.dp),
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.cardColors(containerColor = CardBackground),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
    ) {
        Column(modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp)) {
            OutlinedTextField(
                value = remark,
                onValueChange = onRemarkChange,
                label = { Text("备注（选填）") },
                placeholder = { Text("如送货单号、采购单号") },
                singleLine = true,
                // AI-APP-FIX-406：补 ImeAction
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Done),
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(12.dp),
                leadingIcon = {
                    Icon(
                        Icons.Outlined.EditNote,
                        null,
                        tint = accentColor,
                        modifier = Modifier.size(20.dp)
                    )
                }
            )
        }
    }
}
