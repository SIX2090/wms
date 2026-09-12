package com.factory.wms.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
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
import com.factory.wms.ui.theme.*
import com.factory.wms.ui.viewmodel.scan.ScanViewModel
import com.factory.wms.ui.viewmodel.scan.SubmittedPrintInfo
import com.factory.wms.util.formatQuantity
import com.factory.wms.util.ScanFeedback
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
    var manualCode by remember { mutableStateOf("") }
    var manualQty by remember { mutableStateOf("1") }
    var acknowledgedPrintTargetId by remember { mutableStateOf<Int?>(null) }
    val snackbarHostState = remember { SnackbarHostState() }

    LaunchedEffect(Unit) {
        if (uiState.warehouses.isEmpty() && !uiState.warehousesLoading) {
            viewModel.loadWarehouses()
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
        title = "扫码入库",
        subtitle = "扫描物料条码，快速完成入库",
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
            if (manualCode.isNotBlank()) {
                viewModel.addScanLine(
                    ScanLine(
                        material_code = manualCode.trim(),
                        quantity = manualQty.toDoubleOrNull() ?: 1.0
                    )
                )
                manualCode = ""
                manualQty = "1"
                viewModel.clearMaterialSuggestions()
                showScannerDialog = false
            }
        },
        onScanBarcode = { barcode ->
            viewModel.addScanLine(
                ScanLine(
                    material_code = barcode.trim(),
                    quantity = manualQty.toDoubleOrNull() ?: 1.0
                )
            )
            manualCode = ""
            manualQty = "1"
        },
        onSubmitClick = { showSubmitDialog = true },
        submitLabel = "提交入库",
        submitColor = CardBlue,
        submittedPrint = uiState.submittedPrint,
        printLoading = uiState.printLoading,
        onPrintOrder = { viewModel.printSubmittedOrder() },
        onDismissPrint = { viewModel.clearSubmittedPrint() },
        header = {
            WarehouseSelectorCard(
                warehouse = uiState.selectedWarehouse,
                accentColor = CardBlue,
                onClick = { showWarehouseDialog = true },
                label = "收货仓库"
            )
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

    if (showSubmitDialog) {
        AlertDialog(
            onDismissRequest = { showSubmitDialog = false },
            shape = RoundedCornerShape(20.dp),
            title = { Text("确认入库", fontWeight = FontWeight.SemiBold) },
            text = {
                Text("共 ${uiState.scanLines.size} 种物料，数量 ${formatQuantity(uiState.totalQuantity)}，确认提交入库？")
            },
            confirmButton = {
                Button(
                    onClick = {
                        showSubmitDialog = false
                        viewModel.submitInbound()
                    },
                    // BUG-2026-09-12-010：提交中禁用，配合 ViewModel 层守卫双保险
                    enabled = !uiState.isLoading,
                    shape = RoundedCornerShape(12.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = CardBlue)
                ) {
                    Text("确认入库")
                }
            },
            dismissButton = {
                TextButton(onClick = { showSubmitDialog = false }) {
                    Text("取消")
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

    // 语音建单跳转过来的物料行：只消费一次，随后立刻通知外部清空
    LaunchedEffect(voicePrefillLines) {
        if (voicePrefillLines.isNotEmpty()) {
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
        title = "扫码出库",
        subtitle = "扫描物料条码，快速完成出库",
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
            if (manualCode.isNotBlank()) {
                viewModel.addScanLine(
                    ScanLine(
                        material_code = manualCode.trim(),
                        quantity = manualQty.toDoubleOrNull() ?: 1.0
                    )
                )
                manualCode = ""
                manualQty = "1"
                showScannerDialog = false
            }
        },
        onScanBarcode = { barcode ->
            viewModel.addScanLine(
                ScanLine(
                    material_code = barcode.trim(),
                    quantity = manualQty.toDoubleOrNull() ?: 1.0
                )
            )
            manualCode = ""
            manualQty = "1"
        },
        onSubmitClick = { showSubmitDialog = true },
        submitLabel = "提交出库",
        submitColor = CardGreen,
        submittedPrint = uiState.submittedPrint,
        printLoading = uiState.printLoading,
        onPrintOrder = { viewModel.printSubmittedOrder() },
        onDismissPrint = { viewModel.clearSubmittedPrint() },
        header = {
            Column {
                WarehouseSelectorCard(
                    warehouse = uiState.selectedWarehouse,
                    accentColor = CardGreen,
                    onClick = { showWarehouseDialog = true },
                    label = "出库仓库"
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
        AlertDialog(
            onDismissRequest = { showSubmitDialog = false },
            shape = RoundedCornerShape(20.dp),
            title = { Text("确认出库", fontWeight = FontWeight.SemiBold) },
            text = {
                Column {
                    Text("共 ${uiState.scanLines.size} 种物料，数量 ${formatQuantity(uiState.totalQuantity)}，确认提交出库？")
                    // 2026-09-12：展示所选领料部门/领料人，提交前最后确认
                    uiState.selectedDepartment?.let {
                        Text("领料部门：${it.name.orEmpty()}", style = MaterialTheme.typography.bodySmall, color = OnSurfaceVariant)
                    }
                    uiState.selectedEmployee?.let {
                        Text("领料人：${it.name.orEmpty()}", style = MaterialTheme.typography.bodySmall, color = OnSurfaceVariant)
                    }
                }
            },
            confirmButton = {
                Button(
                    onClick = {
                        showSubmitDialog = false
                        viewModel.submitOutbound()
                    },
                    // BUG-2026-09-12-010：提交中禁用，配合 ViewModel 层守卫双保险
                    enabled = !uiState.isLoading,
                    shape = RoundedCornerShape(12.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = CardGreen)
                ) {
                    Text("确认出库")
                }
            },
            dismissButton = {
                TextButton(onClick = { showSubmitDialog = false }) {
                    Text("取消")
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
    onBack: () -> Unit
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
    val queryScope = rememberCoroutineScope()

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
            WarehouseSelectorCard(
                warehouse = uiState.selectedWarehouse,
                accentColor = CardOrange,
                onClick = { showWarehouseDialog = true },
                label = "查询仓库"
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
                    modifier = Modifier.weight(1f)
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
                    modifier = Modifier.weight(1f)
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
                    // 高度受限内部可滚动；名称/规格/品牌逐行完整显示，不做省略号截断
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .heightIn(max = 360.dp)
                            .verticalScroll(rememberScrollState())
                    ) {
                        val visibleSuggestions = uiState.materialSuggestions
                        visibleSuggestions.forEachIndexed { index, material ->
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
                                color = Primary
                            )
                            Surface(
                                shape = RoundedCornerShape(20.dp),
                                color = if ((material.stock ?: 0.0) > (material.minStock ?: 0.0))
                                    SuccessContainer else ErrorContainer
                            ) {
                                Text(
                                    if ((material.stock ?: 0.0) > (material.minStock ?: 0.0)) "库存充足" else "库存不足",
                                    modifier = Modifier.padding(horizontal = 14.dp, vertical = 6.dp),
                                    color = if ((material.stock ?: 0.0) > (material.minStock ?: 0.0)) Success else Error,
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
                            InfoChip("库存数量", formatQuantity(material.stock ?: 0.0))
                            InfoChip("单位", material.unit ?: "-")
                            InfoChip("最低库存", formatQuantity((material.minStock ?: 0).toDouble()))
                        }

                        Spacer(modifier = Modifier.height(16.dp))

                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceEvenly
                        ) {
                            InfoChip("单价", "¥${"%.2f".format(material.price ?: 0.0)}")
                            InfoChip("再订货点", formatQuantity((material.reorderPoint ?: 0).toDouble()))
                            InfoChip("分类", material.category ?: "-")
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
                viewModel.searchMaterialByCode(barcode)
                // AI-MOB-SCAN-UX-01：查库存同样是"扫到就想知道结果"的场景，
                // 声音+震动让工人不用盯着屏幕等查询返回。
                queryScope.launch {
                    if (viewModel.materialExists(barcode)) {
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
    modifier: Modifier = Modifier
) {
    // 关键字输入防抖 300ms 后自动查询，减少无谓请求（与页内其它搜索一致的手感）
    LaunchedEffect(uiState.stockListKeyword) {
        if (uiState.stockListKeyword.isBlank() && !uiState.stockListLoaded) return@LaunchedEffect
        delay(300)
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

    // 结果总数提示（分页元数据来自服务端，R1）
    if (uiState.stockListLoaded && uiState.stockListTotal > 0) {
        Spacer(modifier = Modifier.height(8.dp))
        Text(
            "共 ${uiState.stockListTotal} 条" +
                if (uiState.selectedWarehouse != null) "（${uiState.selectedWarehouse.name ?: ""}）" else "",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
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
            Box(
                modifier = Modifier.fillMaxWidth().padding(top = 40.dp),
                contentAlignment = Alignment.Center
            ) {
                WmsEmptyState(
                    icon = Icons.Outlined.Search,
                    title = if (uiState.stockListKeyword.isBlank())
                        "该仓库暂无物料库存记录"
                    else
                        "未找到包含「${uiState.stockListKeyword}」的物料",
                    subtitle = "可切换仓库或换个关键词试试",
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
                items(uiState.stockListItems, key = { it.id ?: 0 }) { material ->
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

/** AI-MOB-STOCK-F01：列表模式单行——编码/名称/规格 + 仓库级账面库存数量。 */
@Composable
private fun StockListRow(material: com.factory.wms.data.model.MaterialDto) {
    val stock = material.stock ?: 0.0
    val minStock = material.minStock ?: 0.0
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(14.dp),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
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
                    color = Primary
                )
                if (!material.name.isNullOrBlank()) {
                    Spacer(modifier = Modifier.height(2.dp))
                    Text(
                        material.name.orEmpty(),
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurface,
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
                    color = if (stock > minStock) Success else Error
                )
                if (!material.unit.isNullOrBlank()) {
                    Text(
                        material.unit,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
        }
    }
}

@Composable
private fun InfoChip(label: String, value: String) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Text(
            label,
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        Spacer(modifier = Modifier.height(2.dp))
        Text(
            value,
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.Bold,
            color = MaterialTheme.colorScheme.onSurface
        )
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

    fun formatStockQty(value: Double): String {
        return if (value == value.toLong().toDouble()) value.toLong().toString() else String.format("%.2f", value)
    }

    LaunchedEffect(Unit) {
        if (uiState.warehouses.isEmpty() && !uiState.warehousesLoading) {
            viewModel.loadWarehouses()
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
        title = "扫码盘点",
        subtitle = "扫描物料条码，录入实际库存",
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
            if (manualCode.isNotBlank()) {
                addOrConfirmStocktakeLine(
                    ScanLine(
                        material_code = manualCode.trim(),
                        quantity = manualQty.toDoubleOrNull() ?: 1.0,
                        location_code = stocktakeArea.trim().ifBlank { null }
                    )
                )
                manualCode = ""
                manualQty = "1"
                showScannerDialog = false
            }
        },
        onScanBarcode = { barcode ->
            addOrConfirmStocktakeLine(
                ScanLine(
                    material_code = barcode.trim(),
                    quantity = manualQty.toDoubleOrNull() ?: 1.0,
                    location_code = stocktakeArea.trim().ifBlank { null }
                )
            )
            manualCode = ""
            manualQty = "1"
        },
        onSubmitClick = { showSubmitDialog = true },
        submitLabel = "提交盘点",
        submitColor = CardPurple,
        extraActionLabel = "识物盘点",
        onExtraAction = onRecognize,
        header = {
            Column(modifier = Modifier.fillMaxWidth()) {
                WarehouseSelectorCard(
                    warehouse = uiState.selectedWarehouse,
                    accentColor = CardPurple,
                    onClick = { showWarehouseDialog = true },
                    label = "盘点仓库"
                )
                OutlinedTextField(
                    value = stocktakeArea,
                    onValueChange = { stocktakeArea = it },
                    label = { Text("盘点库位/区域") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                    supportingText = { Text("启用库位管理且有差异时必填") }
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
                    "${line.material_code} 已在清单中（当前：${formatStockQty(existingQty ?: 0.0)}）。\n" +
                        "本次扫码：${formatStockQty(line.quantity)}。\n\n" +
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
        AlertDialog(
            onDismissRequest = { showSubmitDialog = false },
            shape = RoundedCornerShape(20.dp),
            title = { Text("确认盘点", fontWeight = FontWeight.SemiBold) },
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
                Text(base)
            },
            confirmButton = {
                Button(
                    onClick = {
                        showSubmitDialog = false
                        viewModel.submitStocktake()
                    },
                    // BUG-2026-09-12-010：在原有"仓库+盘点单必选"之上追加"非提交中"，
                    // 不能用 isLoading 覆盖前置校验，否则未选盘点单时按钮会变可点。
                    enabled = uiState.selectedWarehouse != null &&
                        uiState.selectedCheckOrder != null &&
                        !uiState.isLoading,
                    shape = RoundedCornerShape(12.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = CardPurple)
                ) {
                    Text("确认盘点")
                }
            },
            dismissButton = {
                TextButton(onClick = { showSubmitDialog = false }) {
                    Text("取消")
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
                                containerColor = if (isSelected) accentColor.copy(alpha = 0.15f)
                                else Color(0xFFF5F5F5)
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

/** 出入库页顶部的仓库选择卡片；未选择时提示"请选择"。 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun WarehouseSelectorCard(
    warehouse: WarehouseDto?,
    accentColor: Color,
    onClick: () -> Unit,
    label: String = "仓库"
) {
    OutlinedCard(
        onClick = onClick,
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 8.dp),
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.outlinedCardColors(containerColor = CardBackground)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(12.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Box(
                modifier = Modifier
                    .size(36.dp)
                    .clip(RoundedCornerShape(10.dp))
                    .background(accentColor.copy(alpha = 0.12f)),
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    Icons.Outlined.Warehouse,
                    null,
                    tint = accentColor,
                    modifier = Modifier.size(19.dp)
                )
            }
            Spacer(modifier = Modifier.width(10.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text(label, style = MaterialTheme.typography.labelSmall, color = OnSurfaceVariant)
                Text(
                    warehouse?.let { "${it.code} ${it.name.orEmpty()}" } ?: "请选择仓库",
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.SemiBold,
                    color = if (warehouse != null) OnSurface else OnSurfaceVariant,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
            }
            Icon(
                Icons.Filled.KeyboardArrowDown,
                null,
                tint = OnSurfaceVariant,
                modifier = Modifier.size(20.dp)
            )
        }
    }
}
