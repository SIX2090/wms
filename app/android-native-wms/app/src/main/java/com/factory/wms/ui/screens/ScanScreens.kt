package com.factory.wms.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
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
import com.factory.wms.data.model.ScanLine
import com.factory.wms.data.model.WarehouseDto
import com.factory.wms.ui.components.ScannerDialog
import com.factory.wms.ui.components.WarehousePickerDialog
import com.factory.wms.ui.components.WmsEmptyState
import com.factory.wms.ui.components.WmsGradientHeader
import com.factory.wms.ui.theme.*
import com.factory.wms.ui.viewmodel.scan.ScanViewModel
import com.factory.wms.ui.viewmodel.scan.SubmittedPrintInfo
import com.factory.wms.util.formatQuantity
import kotlinx.coroutines.delay

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
                ContractInputCard(
                    contractNo = uiState.contractNo,
                    suggestions = uiState.contractSuggestions,
                    loading = uiState.contractSuggestionsLoading,
                    onContractNoChange = { viewModel.onContractNoChange(it) },
                    onSelect = { viewModel.selectContract(it) },
                    accentColor = CardGreen
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

    if (showSubmitDialog) {
        AlertDialog(
            onDismissRequest = { showSubmitDialog = false },
            shape = RoundedCornerShape(20.dp),
            title = { Text("确认出库", fontWeight = FontWeight.SemiBold) },
            text = {
                Text("共 ${uiState.scanLines.size} 种物料，数量 ${formatQuantity(uiState.totalQuantity)}，确认提交出库？")
            },
            confirmButton = {
                Button(
                    onClick = {
                        showSubmitDialog = false
                        viewModel.submitOutbound()
                    },
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
    val snackbarHostState = remember { SnackbarHostState() }

    LaunchedEffect(uiState.error) {
        uiState.error?.let {
            snackbarHostState.showSnackbar(it, duration = SnackbarDuration.Short)
            viewModel.clearError()
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

    Scaffold(
        snackbarHost = { SnackbarHost(snackbarHostState) },
        containerColor = Background,
        topBar = {
            WmsGradientHeader(
                title = "查库存",
                subtitle = "扫描条码查询物料库存",
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
                        onValueChange = { manualCode = it },
                        placeholder = { Text("输入或扫描物料编码") },
                        singleLine = true,
                        modifier = Modifier.weight(1f),
                        shape = RoundedCornerShape(12.dp),
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
                                viewModel.searchMaterialByCode(manualCode.trim())
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

            Spacer(modifier = Modifier.height(16.dp))

            // Empty state guidance when no results
            if (!uiState.isLoading && uiState.scannedMaterial == null) {
                Box(
                    modifier = Modifier
                        .weight(1f)
                        .fillMaxWidth(),
                    contentAlignment = Alignment.Center
                ) {
                    WmsEmptyState(
                        icon = Icons.Outlined.Search,
                        title = "输入或扫描物料编码",
                        subtitle = "查询实时库存信息",
                        accentColor = CardOrange
                    )
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
    }

    if (showScannerDialog) {
        ScannerDialog(
            onDismiss = { showScannerDialog = false },
            onBarcodeScanned = { barcode ->
                showScannerDialog = false
                manualCode = barcode
                viewModel.searchMaterialByCode(barcode)
            }
        )
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
    var manualCode by remember { mutableStateOf("") }
    var manualQty by remember { mutableStateOf("1") }
    val snackbarHostState = remember { SnackbarHostState() }
    // BUG-2026-09-03-003：盘点重复扫码须确认，防止误把已盘物料再次累加使实盘数翻倍
    var confirmLine by remember { mutableStateOf<ScanLine?>(null) }

    fun addOrConfirmStocktakeLine(line: ScanLine) {
        val exists = viewModel.uiState.value.scanLines.any { it.material_code == line.material_code }
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
        viewModel.maybeRestoreStocktakeDraft { count ->
            snackbarHostState.showSnackbar(
                "已恢复上次未提交的盘点清单（$count 项），请核对后继续盘点",
                duration = SnackbarDuration.Long
            )
        }
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
        onDismissScanner = { showScannerDialog = false },
        manualCode = manualCode,
        manualQty = manualQty,
        onManualCodeChange = { manualCode = it },
        onManualQtyChange = { manualQty = it },
        onManualAdd = {
            if (manualCode.isNotBlank()) {
                addOrConfirmStocktakeLine(
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
            addOrConfirmStocktakeLine(
                ScanLine(
                    material_code = barcode.trim(),
                    quantity = manualQty.toDoubleOrNull() ?: 1.0
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
            WarehouseSelectorCard(
                warehouse = uiState.selectedWarehouse,
                accentColor = CardPurple,
                onClick = { showWarehouseDialog = true },
                label = "盘点仓库"
            )
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

    // BUG-2026-09-03-003：盘点重复扫码确认（替换 / 累加 / 取消保持原值）
    confirmLine?.let { line ->
        val existingQty = viewModel.existingLineQuantity(line.material_code)
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
                Text(
                    if (wh != null)
                        "盘点仓库：${wh.code} ${wh.name.orEmpty()}\n共 ${uiState.scanLines.size} 种物料，确认提交盘点？"
                    else
                        "尚未选择盘点仓库，请先选择仓库"
                )
            },
            confirmButton = {
                Button(
                    onClick = {
                        showSubmitDialog = false
                        viewModel.submitStocktake()
                    },
                    enabled = uiState.selectedWarehouse != null,
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
