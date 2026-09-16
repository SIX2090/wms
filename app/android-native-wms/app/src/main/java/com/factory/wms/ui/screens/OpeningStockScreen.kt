package com.factory.wms.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
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
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.factory.wms.data.model.OpeningStockDto
import com.factory.wms.data.model.OpeningStockLine
import com.factory.wms.data.model.WarehouseDto
import com.factory.wms.ui.components.ScannerDialog
import com.factory.wms.ui.components.WarehousePickerDialog
import com.factory.wms.ui.components.WmsEmptyState
import com.factory.wms.ui.components.WmsGradientHeader
import com.factory.wms.ui.theme.*
import com.factory.wms.ui.viewmodel.opening.OpeningStockViewModel
import com.factory.wms.util.formatQuantity
import com.factory.wms.util.ScanFeedback
import java.util.Calendar
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun OpeningStockScreen(
    viewModel: OpeningStockViewModel,
    onBack: () -> Unit
) {
    val uiState by viewModel.uiState.collectAsState()
    var showManualDialog by remember { mutableStateOf(false) }
    var showCameraScanner by remember { mutableStateOf(false) }
    // AI-MOB-CONTINUOUS-SCAN-01：期初建账同样是"连续扫一批"的场景，启用连续扫描。
    var continuousScanCount by remember { mutableStateOf(0) }
    var lastScannedCode by remember { mutableStateOf<String?>(null) }
    // AI-MOB-SCAN-UX-01：扫码反馈需要的 context 与协程作用域
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var showDateDialog by remember { mutableStateOf(false) }
    var showWarehouseDialog by remember { mutableStateOf(false) }
    var manualCode by remember { mutableStateOf("") }
    var manualQty by remember { mutableStateOf("1") }
    // BUG-2026-09-16-010：点行改数量——已录入行不再只能删了重扫
    var editLineIndex by remember { mutableStateOf<Int?>(null) }
    var editQty by remember { mutableStateOf("") }
    // P1-C：已建账列表 / 编辑弹窗状态
    var tab by remember { mutableStateOf(OpeningStockTab.ENTRY) }
    var builtKeyword by remember { mutableStateOf("") }
    var editBuiltQty by remember { mutableStateOf("") }
    var editBuiltPrice by remember { mutableStateOf("") }
    val snackbarHostState = remember { SnackbarHostState() }

    // AI-MOB-ADD-KEYWORD-01：弹窗关闭后清掉候选，避免下次打开时残留上一次的联想结果
    LaunchedEffect(showManualDialog) {
        if (!showManualDialog) {
            viewModel.clearMaterialSuggestions()
        }
    }

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
            snackbarHostState.showSnackbar(it, duration = SnackbarDuration.Long)
            viewModel.clearSuccess()
        }
    }

    // P1-C：编辑弹窗打开时把当前值灌进输入框（每次换行都重置，避免残留上一行）
    LaunchedEffect(uiState.editingItem?.id) {
        uiState.editingItem?.let { item ->
            editBuiltQty = formatQuantity(item.quantity ?: 0.0)
            editBuiltPrice = formatQuantity(item.price ?: 0.0)
        }
    }

    Scaffold(
        snackbarHost = { SnackbarHost(snackbarHostState) },
        containerColor = Background,
        topBar = {
            WmsGradientHeader(
                title = "期初库存",
                subtitle = when (tab) {
                    OpeningStockTab.ENTRY -> "选择日期+仓库，扫码录入初始化库存"
                    OpeningStockTab.BUILT -> "查看并修改本仓已建账明细"
                },
                accent = CardCyan,
                onBack = onBack
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
        ) {
            // P1-C：建账 / 已建账 两个视角。此前手机端只有"建账"，
            // 建完看不到自己建了什么、建错了改不了，只能回 PC 端翻单据。
            OpeningStockTabs(
                current = tab,
                entryCount = uiState.lines.size,
                builtCount = uiState.builtTotal,
                onSelect = { next ->
                    tab = next
                    if (next == OpeningStockTab.BUILT) {
                        viewModel.loadBuiltItems(reset = true)
                    }
                }
            )

            if (tab == OpeningStockTab.BUILT) {
                BuiltItemsSection(
                    state = uiState,
                    keyword = builtKeyword,
                    onKeywordChange = {
                        builtKeyword = it
                        viewModel.searchBuiltItems(it)
                    },
                    onLoadMore = { viewModel.loadMoreBuiltItems() },
                    onItemClick = { viewModel.startEditing(it) }
                )
            } else {
                EntrySection(
                    uiState = uiState,
                    showDateDialog = { showDateDialog = true },
                    showWarehouseDialog = { showWarehouseDialog = true },
                    onLineClick = { index, line ->
                        editLineIndex = index
                        editQty = formatQuantity(line.quantity)
                    },
                    onRemoveLine = { viewModel.removeLine(it) },
                    onClearLines = { viewModel.clearLines() },
                    onSubmit = { viewModel.submit() },
                    onScan = {
                        continuousScanCount = 0
                        lastScannedCode = null
                        showCameraScanner = true
                    },
                    onManualAdd = { showManualDialog = true }
                )
            }
        }
    }

    // P1-C：已建账明细编辑弹窗——改数量/单价，服务端按差额调账
    uiState.editingItem?.let { item ->
        AlertDialog(
            onDismissRequest = { viewModel.cancelEditing() },
            shape = RoundedCornerShape(20.dp),
            title = {
                Text(
                    "修改期初：${item.materialCode.orEmpty()}",
                    fontWeight = FontWeight.SemiBold,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
            },
            text = {
                Column {
                    if (!item.materialName.isNullOrBlank() || !item.spec.isNullOrBlank()) {
                        Text(
                            listOfNotNull(
                                item.materialName?.takeIf { it.isNotBlank() },
                                item.spec?.takeIf { it.isNotBlank() }
                            ).joinToString("  "),
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            maxLines = 2,
                            overflow = TextOverflow.Ellipsis
                        )
                        Spacer(modifier = Modifier.height(10.dp))
                    }

                    // 数量：带 ± 快捷按钮，与手动添加弹窗一致的操作手感
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        FilledIconButton(
                            onClick = {
                                val current = editBuiltQty.toDoubleOrNull() ?: 1.0
                                editBuiltQty = formatQuantity((current - 1).coerceAtLeast(0.0))
                            },
                            modifier = Modifier.size(44.dp),
                            shape = RoundedCornerShape(12.dp),
                            colors = IconButtonDefaults.filledIconButtonColors(
                                containerColor = CardCyan.copy(alpha = 0.1f)
                            )
                        ) {
                            Icon(Icons.Outlined.Remove, "减1", tint = CardCyan, modifier = Modifier.size(22.dp))
                        }
                        Spacer(modifier = Modifier.width(8.dp))
                        OutlinedTextField(
                            value = editBuiltQty,
                            onValueChange = { editBuiltQty = it },
                            label = { Text("数量（确切值）") },
                            singleLine = true,
                            modifier = Modifier.weight(1f),
                            shape = RoundedCornerShape(12.dp),
                            keyboardOptions = KeyboardOptions(
                                keyboardType = KeyboardType.Decimal,
                                imeAction = ImeAction.Next
                            ),
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedBorderColor = CardCyan,
                                focusedLabelColor = CardCyan
                            )
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        FilledIconButton(
                            onClick = {
                                val current = editBuiltQty.toDoubleOrNull() ?: 0.0
                                editBuiltQty = formatQuantity(current + 1)
                            },
                            modifier = Modifier.size(44.dp),
                            shape = RoundedCornerShape(12.dp),
                            colors = IconButtonDefaults.filledIconButtonColors(containerColor = CardCyan)
                        ) {
                            Icon(Icons.Outlined.Add, "加1", tint = Color.White, modifier = Modifier.size(22.dp))
                        }
                    }

                    Spacer(modifier = Modifier.height(10.dp))

                    OutlinedTextField(
                        value = editBuiltPrice,
                        onValueChange = { editBuiltPrice = it },
                        label = { Text("单价") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(12.dp),
                        keyboardOptions = KeyboardOptions(
                            keyboardType = KeyboardType.Decimal,
                            imeAction = ImeAction.Done
                        ),
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedBorderColor = CardCyan,
                            focusedLabelColor = CardCyan
                        )
                    )

                    // 差额预告：用户改之前就知道总账会怎么动（期初是账的起点，改之前要心里有数）
                    val newQty = editBuiltQty.toDoubleOrNull()
                    val oldQty = item.quantity ?: 0.0
                    if (newQty != null && kotlin.math.abs(newQty - oldQty) > 1e-9) {
                        val delta = newQty - oldQty
                        Spacer(modifier = Modifier.height(10.dp))
                        Text(
                            (if (delta > 0) "本仓该物料库存将增加 " else "本仓该物料库存将减少 ")
                                + formatQuantity(kotlin.math.abs(delta)),
                            style = MaterialTheme.typography.bodySmall,
                            color = if (delta > 0) CardCyan else Error
                        )
                    }
                }
            },
            confirmButton = {
                Button(
                    onClick = {
                        val qty = editBuiltQty.toDoubleOrNull()
                        val price = editBuiltPrice.toDoubleOrNull() ?: 0.0
                        if (qty != null && qty >= 0) {
                            viewModel.submitEdit(qty, price)
                        }
                    },
                    enabled = (editBuiltQty.toDoubleOrNull() ?: -1.0) >= 0.0 && !uiState.updating,
                    shape = RoundedCornerShape(12.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = CardCyan)
                ) {
                    if (uiState.updating) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(18.dp),
                            color = Color.White,
                            strokeWidth = 2.dp
                        )
                    } else {
                        Text("保存")
                    }
                }
            },
            dismissButton = {
                TextButton(onClick = { viewModel.cancelEditing() }) {
                    Text("取消")
                }
            }
        )
    }

    // 手动添加对话框
    if (showManualDialog) {
        AlertDialog(
            onDismissRequest = { showManualDialog = false },
            shape = RoundedCornerShape(20.dp),
            title = { Text("添加期初物料", fontWeight = FontWeight.SemiBold) },
            text = {
                Column {
                    // AI-MOB-ADD-KEYWORD-01：与查库存同口径——支持名称/规格/品牌
                    // 关键词模糊联想，不再只认物料编码。
                    OutlinedTextField(
                        value = manualCode,
                        onValueChange = {
                            manualCode = it
                            viewModel.searchMaterialSuggestions(it)
                        },
                        label = { Text("物料编码 / 名称 / 规格 / 品牌") },
                        placeholder = { Text("输入或扫描物料编码，也可搜名称/规格/品牌") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(12.dp),
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedBorderColor = CardCyan,
                            focusedLabelColor = CardCyan
                        )
                    )

                    // 关键词模糊候选：命中即列出，点选后自动回填物料编码
                    if (manualCode.isNotBlank()) {
                        if (uiState.materialSuggestionsLoading) {
                            LinearProgressIndicator(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(top = 6.dp),
                                color = CardCyan,
                                trackColor = CardCyan.copy(alpha = 0.12f)
                            )
                        } else if (uiState.materialSuggestions.isNotEmpty()) {
                            Spacer(modifier = Modifier.height(6.dp))
                            Card(
                                modifier = Modifier.fillMaxWidth(),
                                shape = RoundedCornerShape(12.dp),
                                elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
                                colors = CardDefaults.cardColors(
                                    containerColor = CardCyan.copy(alpha = 0.06f)
                                )
                            ) {
                                Column(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        // 弹窗内空间有限：限高内部滚动
                                        .heightIn(max = 220.dp)
                                        .verticalScroll(rememberScrollState())
                                ) {
                                    uiState.materialSuggestions.forEachIndexed { index, material ->
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
                                                    manualCode = material.code.orEmpty()
                                                    viewModel.clearMaterialSuggestions()
                                                }
                                                .padding(horizontal = 12.dp, vertical = 10.dp)
                                        ) {
                                            Row(verticalAlignment = Alignment.CenterVertically) {
                                                Text(
                                                    material.code.orEmpty(),
                                                    style = MaterialTheme.typography.titleSmall,
                                                    fontWeight = FontWeight.Bold,
                                                    color = CardCyan
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
                                                    // BUG-2026-09-12-002：同 ScanScreenBase——
                                                    // 规格单行截断会吃掉区分物料的尾部差异，放开到 2 行
                                                    maxLines = 2,
                                                    overflow = TextOverflow.Ellipsis
                                                )
                                            }
                                        }
                                        if (index < uiState.materialSuggestions.size - 1) {
                                            HorizontalDivider(
                                                color = CardCyan.copy(alpha = 0.12f),
                                                thickness = 0.5.dp
                                            )
                                        }
                                    }
                                }
                            }
                        }
                    }

                    Spacer(modifier = Modifier.height(12.dp))
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        FilledIconButton(
                            onClick = {
                                val current = manualQty.toDoubleOrNull() ?: 1.0
                                manualQty = formatQuantity((current - 1).coerceAtLeast(0.0))
                            },
                            modifier = Modifier.size(44.dp),
                            shape = RoundedCornerShape(12.dp),
                            colors = IconButtonDefaults.filledIconButtonColors(
                                containerColor = CardCyan.copy(alpha = 0.1f)
                            )
                        ) {
                            Icon(Icons.Outlined.Remove, "减1", tint = CardCyan, modifier = Modifier.size(22.dp))
                        }
                        Spacer(modifier = Modifier.width(8.dp))
                        OutlinedTextField(
                            value = manualQty,
                            onValueChange = { manualQty = it },
                            label = { Text("数量") },
                            singleLine = true,
                            modifier = Modifier.weight(1f),
                            shape = RoundedCornerShape(12.dp),
                            // AI-MOB-SCAN-UX-01：数量框弹数字键盘。
                            // 这里不绑 onDone 加行：本对话框的"添加"按钮有 enabled = 编码非空
                            // 的前置条件（见下方 confirmButton），回车直接提交会绕过该校验。
                            keyboardOptions = KeyboardOptions(
                                keyboardType = KeyboardType.Decimal,
                                imeAction = ImeAction.Next
                            ),
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedBorderColor = CardCyan,
                                focusedLabelColor = CardCyan
                            )
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        FilledIconButton(
                            onClick = {
                                val current = manualQty.toDoubleOrNull() ?: 0.0
                                manualQty = formatQuantity(current + 1)
                            },
                            modifier = Modifier.size(44.dp),
                            shape = RoundedCornerShape(12.dp),
                            colors = IconButtonDefaults.filledIconButtonColors(containerColor = CardCyan)
                        ) {
                            Icon(Icons.Outlined.Add, "加1", tint = Color.White, modifier = Modifier.size(22.dp))
                        }
                    }
                }
            },
            confirmButton = {
                Button(
                    onClick = {
                        viewModel.addLine(manualCode, manualQty.toDoubleOrNull() ?: 1.0)
                        manualCode = ""
                        manualQty = "1"
                        showManualDialog = false
                    },
                    enabled = manualCode.isNotBlank(),
                    shape = RoundedCornerShape(12.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = CardCyan)
                ) {
                    Text("添加")
                }
            },
            dismissButton = {
                TextButton(onClick = { showManualDialog = false }) {
                    Text("取消")
                }
            }
        )
    }

    // BUG-2026-09-16-010：点行改数量对话框——设为确切值（与扫码累加互补）
    editLineIndex?.let { index ->
        val line = uiState.lines.getOrNull(index)
        if (line != null) {
            AlertDialog(
                onDismissRequest = { editLineIndex = null },
                shape = RoundedCornerShape(20.dp),
                title = {
                    Text(
                        "修改数量：${line.materialCode}",
                        fontWeight = FontWeight.SemiBold,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                },
                text = {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        FilledIconButton(
                            onClick = {
                                val current = editQty.toDoubleOrNull() ?: 1.0
                                editQty = formatQuantity((current - 1).coerceAtLeast(0.0))
                            },
                            modifier = Modifier.size(44.dp),
                            shape = RoundedCornerShape(12.dp),
                            colors = IconButtonDefaults.filledIconButtonColors(
                                containerColor = CardCyan.copy(alpha = 0.1f)
                            )
                        ) {
                            Icon(Icons.Outlined.Remove, "减1", tint = CardCyan, modifier = Modifier.size(22.dp))
                        }
                        Spacer(modifier = Modifier.width(8.dp))
                        OutlinedTextField(
                            value = editQty,
                            onValueChange = { editQty = it },
                            label = { Text("数量（确切值）") },
                            singleLine = true,
                            modifier = Modifier.weight(1f),
                            shape = RoundedCornerShape(12.dp),
                            keyboardOptions = KeyboardOptions(
                                keyboardType = KeyboardType.Decimal,
                                imeAction = ImeAction.Done
                            ),
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedBorderColor = CardCyan,
                                focusedLabelColor = CardCyan
                            )
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        FilledIconButton(
                            onClick = {
                                val current = editQty.toDoubleOrNull() ?: 0.0
                                editQty = formatQuantity(current + 1)
                            },
                            modifier = Modifier.size(44.dp),
                            shape = RoundedCornerShape(12.dp),
                            colors = IconButtonDefaults.filledIconButtonColors(containerColor = CardCyan)
                        ) {
                            Icon(Icons.Outlined.Add, "加1", tint = Color.White, modifier = Modifier.size(22.dp))
                        }
                    }
                },
                confirmButton = {
                    Button(
                        onClick = {
                            val qty = editQty.toDoubleOrNull()
                            if (qty != null && qty >= 0) {
                                viewModel.updateLineQuantity(index, qty)
                                editLineIndex = null
                            }
                        },
                        enabled = (editQty.toDoubleOrNull() ?: -1.0) >= 0.0,
                        shape = RoundedCornerShape(12.dp),
                        colors = ButtonDefaults.buttonColors(containerColor = CardCyan)
                    ) {
                        Text("确定")
                    }
                },
                dismissButton = {
                    Row {
                        TextButton(onClick = {
                            viewModel.removeLine(index)
                            editLineIndex = null
                        }) {
                            Text("删除该行", color = Error)
                        }
                        TextButton(onClick = { editLineIndex = null }) {
                            Text("取消")
                        }
                    }
                }
            )
        } else {
            // 行已被移除（如清空后弹窗还在），直接关掉
            editLineIndex = null
        }
    }

    // 日期选择对话框
    if (showDateDialog) {
        DatePickerDialogComposable(
            initialDate = uiState.date,
            onDismiss = { showDateDialog = false },
            onConfirm = { date ->
                viewModel.setDate(date)
                showDateDialog = false
            }
        )
    }

    // 仓库选择对话框
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
            onRetry = { viewModel.loadWarehouses() }
        )
    }

    // 相机扫码对话框
    if (showCameraScanner) {
        ScannerDialog(
            onDismiss = { showCameraScanner = false },
            continuous = true,
            scannedCount = continuousScanCount,
            lastScannedCode = lastScannedCode,
            onBarcodeScanned = { barcode ->
                // AI-MOB-CONTINUOUS-SCAN-01：扫中不关弹窗，连续累计，点"完成"退出。
                continuousScanCount += 1
                lastScannedCode = barcode
                viewModel.addLine(barcode, manualQty.toDoubleOrNull() ?: 1.0)
                manualCode = ""
                manualQty = "1"
                // AI-MOB-SCAN-UX-01：声音+震动反馈（成功/失败可凭体感分辨）
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

@Composable
private fun OpeningStockLineCard(
    line: OpeningStockLine,
    index: Int,
    onClick: () -> Unit,
    onRemove: () -> Unit
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
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
            Box(
                modifier = Modifier
                    .size(38.dp)
                    .clip(RoundedCornerShape(11.dp))
                    .background(CardCyan.copy(alpha = 0.12f)),
                contentAlignment = Alignment.Center
            ) {
                Text("${index + 1}", color = CardCyan, fontWeight = FontWeight.Bold, fontSize = 14.sp)
            }
            Spacer(modifier = Modifier.width(12.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    line.materialCode,
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.SemiBold,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
                val materialDetails = listOfNotNull(
                    line.materialName?.takeIf { it.isNotBlank() },
                    line.materialBrand?.takeIf { it.isNotBlank() },
                    line.materialSpec?.takeIf { it.isNotBlank() }
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
                line.price?.let {
                    Text(
                        "单价: ¥${"%.2f".format(it)}",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
            // 数量胶囊
            Surface(
                shape = RoundedCornerShape(10.dp),
                color = CardCyan.copy(alpha = 0.10f)
            ) {
                Text(
                    "× ${formatQuantity(line.quantity)}",
                    modifier = Modifier.padding(horizontal = 10.dp, vertical = 5.dp),
                    color = CardCyan,
                    fontSize = 13.sp,
                    fontWeight = FontWeight.Bold
                )
            }
            IconButton(
                onClick = onRemove,
                modifier = Modifier.size(36.dp)
            ) {
                Icon(Icons.Outlined.Close, "移除", tint = OnSurfaceSecondary, modifier = Modifier.size(18.dp))
            }
        }
    }
}

@Composable
private fun DatePickerDialogComposable(
    initialDate: String,
    onDismiss: () -> Unit,
    onConfirm: (String) -> Unit
) {
    val context = LocalContext.current
    val calendar = Calendar.getInstance()
    try {
        val parts = initialDate.split("-")
        if (parts.size == 3) {
            calendar.set(parts[0].toInt(), parts[1].toInt() - 1, parts[2].toInt())
        }
    } catch (_: Exception) { }

    val year = calendar.get(Calendar.YEAR)
    val month = calendar.get(Calendar.MONTH)
    val day = calendar.get(Calendar.DAY_OF_MONTH)

    val datePicker = remember { DatePickerDialogState(year, month, day) }

    AlertDialog(
        onDismissRequest = onDismiss,
        shape = RoundedCornerShape(20.dp),
        title = { Text("选择建账日期", fontWeight = FontWeight.SemiBold) },
        text = {
            Column {
                Text(
                    "${datePicker.year}年${datePicker.month + 1}月${datePicker.day}日",
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.Bold,
                    color = CardCyan
                )
                Spacer(modifier = Modifier.height(16.dp))
                // 年份
                YearRow(datePicker)
                Spacer(modifier = Modifier.height(8.dp))
                // 月份
                MonthRow(datePicker)
                Spacer(modifier = Modifier.height(8.dp))
                // 日期
                DayRow(datePicker)
            }
        },
        confirmButton = {
            Button(
                onClick = {
                    val y = datePicker.year
                    val m = datePicker.month + 1
                    val d = datePicker.day
                    onConfirm("%04d-%02d-%02d".format(y, m, d))
                },
                shape = RoundedCornerShape(12.dp),
                colors = ButtonDefaults.buttonColors(containerColor = CardCyan)
            ) { Text("确定") }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("取消") }
        }
    )
}

@Composable
private fun YearRow(state: DatePickerDialogState) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        FilledIconButton(
            onClick = { state.year-- },
            modifier = Modifier.size(40.dp),
            shape = RoundedCornerShape(10.dp),
            colors = IconButtonDefaults.filledIconButtonColors(containerColor = CardCyan.copy(alpha = 0.1f))
        ) { Icon(Icons.Filled.KeyboardArrowLeft, "上一年", tint = CardCyan) }
        Text(
            "${state.year}年",
            modifier = Modifier.weight(1f),
            textAlign = androidx.compose.ui.text.style.TextAlign.Center,
            fontSize = 18.sp,
            fontWeight = FontWeight.SemiBold
        )
        FilledIconButton(
            onClick = { state.year++ },
            modifier = Modifier.size(40.dp),
            shape = RoundedCornerShape(10.dp),
            colors = IconButtonDefaults.filledIconButtonColors(containerColor = CardCyan.copy(alpha = 0.1f))
        ) { Icon(Icons.Filled.KeyboardArrowRight, "下一年", tint = CardCyan) }
    }
}

@Composable
private fun MonthRow(state: DatePickerDialogState) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        FilledIconButton(
            onClick = { state.month = (state.month + 11) % 12 },
            modifier = Modifier.size(40.dp),
            shape = RoundedCornerShape(10.dp),
            colors = IconButtonDefaults.filledIconButtonColors(containerColor = CardCyan.copy(alpha = 0.1f))
        ) { Icon(Icons.Filled.KeyboardArrowLeft, "上一月", tint = CardCyan) }
        Text(
            "${state.month + 1}月",
            modifier = Modifier.weight(1f),
            textAlign = androidx.compose.ui.text.style.TextAlign.Center,
            fontSize = 18.sp,
            fontWeight = FontWeight.SemiBold
        )
        FilledIconButton(
            onClick = { state.month = (state.month + 1) % 12 },
            modifier = Modifier.size(40.dp),
            shape = RoundedCornerShape(10.dp),
            colors = IconButtonDefaults.filledIconButtonColors(containerColor = CardCyan.copy(alpha = 0.1f))
        ) { Icon(Icons.Filled.KeyboardArrowRight, "下一月", tint = CardCyan) }
    }
}

@Composable
private fun DayRow(state: DatePickerDialogState) {
    val daysInMonth = daysInMonth(state.year, state.month)
    if (state.day > daysInMonth) state.day = daysInMonth
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        FilledIconButton(
            onClick = { if (state.day > 1) state.day-- },
            modifier = Modifier.size(40.dp),
            shape = RoundedCornerShape(10.dp),
            colors = IconButtonDefaults.filledIconButtonColors(containerColor = CardCyan.copy(alpha = 0.1f))
        ) { Icon(Icons.Filled.KeyboardArrowLeft, "前一天", tint = CardCyan) }
        Text(
            "${state.day}日",
            modifier = Modifier.weight(1f),
            textAlign = androidx.compose.ui.text.style.TextAlign.Center,
            fontSize = 18.sp,
            fontWeight = FontWeight.SemiBold
        )
        FilledIconButton(
            onClick = { if (state.day < daysInMonth) state.day++ },
            modifier = Modifier.size(40.dp),
            shape = RoundedCornerShape(10.dp),
            colors = IconButtonDefaults.filledIconButtonColors(containerColor = CardCyan.copy(alpha = 0.1f))
        ) { Icon(Icons.Filled.KeyboardArrowRight, "后一天", tint = CardCyan) }
    }
}

private class DatePickerDialogState(
    var year: Int,
    var month: Int,
    var day: Int
)

private fun daysInMonth(year: Int, month: Int): Int {
    val calendar = Calendar.getInstance()
    calendar.set(year, month, 1)
    return calendar.getActualMaximum(Calendar.DAY_OF_MONTH)
}

// ======================================================================
// P1-C 建账 / 已建账 双视角
//
// 手机端此前只有"建账"：录完提交就结束，看不到自己建了什么，建错了也改不了
// （得回 PC 端翻单据列表）。这一段补上第二个视角：已建账明细 + 行内编辑。
// ======================================================================

/** 期初页的两个视角。 */
private enum class OpeningStockTab(val label: String) {
    ENTRY("建账"),
    BUILT("已建账")
}

@Composable
private fun OpeningStockTabs(
    current: OpeningStockTab,
    entryCount: Int,
    builtCount: Int,
    onSelect: (OpeningStockTab) -> Unit
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 4.dp),
        horizontalArrangement = Arrangement.spacedBy(10.dp)
    ) {
        OpeningStockTab.entries.forEach { item ->
            val count = when (item) {
                OpeningStockTab.ENTRY -> entryCount
                OpeningStockTab.BUILT -> builtCount
            }
            FilterChip(
                selected = current == item,
                onClick = { if (current != item) onSelect(item) },
                label = {
                    Text(if (count > 0) "${item.label} ($count)" else item.label)
                },
                shape = RoundedCornerShape(10.dp),
                colors = FilterChipDefaults.filterChipColors(
                    selectedContainerColor = CardCyan.copy(alpha = 0.14f),
                    selectedLabelColor = CardCyan
                )
            )
        }
    }
}

/** 建账视角：日期 + 仓库 + 录入明细 + 底部提交/扫码/手动添加。 */
@Composable
private fun EntrySection(
    uiState: com.factory.wms.ui.viewmodel.opening.OpeningStockUiState,
    showDateDialog: () -> Unit,
    showWarehouseDialog: () -> Unit,
    onLineClick: (Int, OpeningStockLine) -> Unit,
    onRemoveLine: (Int) -> Unit,
    onClearLines: () -> Unit,
    onSubmit: () -> Unit,
    onScan: () -> Unit,
    onManualAdd: () -> Unit
) {
    Column(modifier = Modifier.fillMaxSize()) {
        // 日期 + 仓库选择
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 4.dp),
            horizontalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            OutlinedCard(
                onClick = showDateDialog,
                modifier = Modifier.weight(1f),
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
                            .background(CardCyan.copy(alpha = 0.12f)),
                        contentAlignment = Alignment.Center
                    ) {
                        Icon(
                            Icons.Outlined.CalendarMonth,
                            null,
                            tint = CardCyan,
                            modifier = Modifier.size(19.dp)
                        )
                    }
                    Spacer(modifier = Modifier.width(10.dp))
                    Column {
                        Text("建账日期", style = MaterialTheme.typography.labelSmall, color = OnSurfaceVariant)
                        Text(
                            uiState.date,
                            style = MaterialTheme.typography.titleSmall,
                            fontWeight = FontWeight.SemiBold,
                            color = OnSurface
                        )
                    }
                }
            }
            OutlinedCard(
                onClick = showWarehouseDialog,
                modifier = Modifier.weight(1f),
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
                            .background(CardCyan.copy(alpha = 0.12f)),
                        contentAlignment = Alignment.Center
                    ) {
                        Icon(
                            Icons.Outlined.Warehouse,
                            null,
                            tint = CardCyan,
                            modifier = Modifier.size(19.dp)
                        )
                    }
                    Spacer(modifier = Modifier.width(10.dp))
                    Column {
                        Text("仓库", style = MaterialTheme.typography.labelSmall, color = OnSurfaceVariant)
                        Text(
                            uiState.selectedWarehouse?.let { "${it.code} ${it.name.orEmpty()}" } ?: "请选择",
                            style = MaterialTheme.typography.titleSmall,
                            fontWeight = FontWeight.SemiBold,
                            color = if (uiState.selectedWarehouse != null) OnSurface else OnSurfaceVariant,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis
                        )
                    }
                }
            }
        }

        // 汇总条
        if (uiState.lines.isNotEmpty()) {
            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 8.dp),
                shape = RoundedCornerShape(16.dp),
                colors = CardDefaults.cardColors(containerColor = CardCyan.copy(alpha = 0.06f)),
                elevation = CardDefaults.cardElevation(defaultElevation = 0.dp)
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(16.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column {
                        Text(
                            "${uiState.lines.size} 种物料",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.SemiBold
                        )
                        Text(
                            "总计: ${formatQuantity(uiState.lines.sumOf { it.quantity })}",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                    FilledTonalButton(
                        onClick = onClearLines,
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
        }

        // 明细列表 / 空态
        if (uiState.lines.isNotEmpty()) {
            LazyColumn(
                modifier = Modifier
                    .weight(1f)
                    .padding(horizontal = 16.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                item { Spacer(modifier = Modifier.height(4.dp)) }
                itemsIndexed(uiState.lines) { index, line ->
                    OpeningStockLineCard(
                        line = line,
                        index = index,
                        onClick = { onLineClick(index, line) },
                        onRemove = { onRemoveLine(index) }
                    )
                }
                item { Spacer(modifier = Modifier.height(8.dp)) }
            }
        } else {
            Box(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth(),
                contentAlignment = Alignment.Center
            ) {
                WmsEmptyState(
                    icon = Icons.Outlined.QrCodeScanner,
                    title = "暂无期初物料",
                    subtitle = "点击下方按钮扫码或手动添加",
                    accentColor = CardCyan
                )
            }
        }

        // 底部操作（顶部圆角浮层）
        Surface(
            modifier = Modifier.fillMaxWidth(),
            shadowElevation = 12.dp,
            color = MaterialTheme.colorScheme.surface,
            shape = RoundedCornerShape(topStart = 24.dp, topEnd = 24.dp)
        ) {
            Column(modifier = Modifier.padding(16.dp)) {
                Button(
                    onClick = onSubmit,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(52.dp),
                    enabled = uiState.lines.isNotEmpty() && uiState.selectedWarehouse != null && !uiState.isLoading,
                    shape = RoundedCornerShape(14.dp),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = CardCyan,
                        disabledContainerColor = CardCyan.copy(alpha = 0.3f)
                    )
                ) {
                    if (uiState.isLoading) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(22.dp),
                            color = Color.White,
                            strokeWidth = 2.dp
                        )
                    } else {
                        Icon(Icons.Outlined.CheckCircle, null, modifier = Modifier.size(20.dp))
                        Spacer(Modifier.width(8.dp))
                        Text("提交期初建账", fontWeight = FontWeight.SemiBold, fontSize = 16.sp)
                    }
                }

                Spacer(modifier = Modifier.height(12.dp))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    OutlinedButton(
                        onClick = onScan,
                        modifier = Modifier
                            .weight(1f)
                            .height(48.dp),
                        shape = RoundedCornerShape(12.dp),
                        border = ButtonDefaults.outlinedButtonBorder.copy(
                            brush = androidx.compose.ui.graphics.SolidColor(CardCyan.copy(alpha = 0.3f))
                        )
                    ) {
                        Icon(
                            Icons.Outlined.QrCodeScanner,
                            null,
                            modifier = Modifier.size(20.dp),
                            tint = CardCyan
                        )
                        Spacer(Modifier.width(6.dp))
                        Text("扫码添加", color = CardCyan, fontWeight = FontWeight.Medium)
                    }
                    OutlinedButton(
                        onClick = onManualAdd,
                        modifier = Modifier
                            .weight(1f)
                            .height(48.dp),
                        shape = RoundedCornerShape(12.dp),
                        border = ButtonDefaults.outlinedButtonBorder.copy(
                            brush = androidx.compose.ui.graphics.SolidColor(CardCyan.copy(alpha = 0.3f))
                        )
                    ) {
                        Icon(
                            Icons.Outlined.Edit,
                            null,
                            modifier = Modifier.size(20.dp),
                            tint = CardCyan
                        )
                        Spacer(Modifier.width(6.dp))
                        Text("手动添加", color = CardCyan, fontWeight = FontWeight.Medium)
                    }
                }
            }
        }
    }
}

/**
 * 已建账视角：本仓建账概览 + 关键字筛选 + 明细列表（分页滚动加载）。
 *
 * builtTotal / builtQuantity 由后端按**仓库全集**计算（R1），
 * 因此翻到第 3 页时顶部数字不会缩水。
 */
@Composable
private fun BuiltItemsSection(
    state: com.factory.wms.ui.viewmodel.opening.OpeningStockUiState,
    keyword: String,
    onKeywordChange: (String) -> Unit,
    onLoadMore: () -> Unit,
    onItemClick: (OpeningStockDto) -> Unit
) {
    Column(modifier = Modifier.fillMaxSize()) {
        // 概览卡：本仓建了多少条、合计多少
        Card(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 4.dp),
            shape = RoundedCornerShape(16.dp),
            colors = CardDefaults.cardColors(containerColor = CardCyan.copy(alpha = 0.06f)),
            elevation = CardDefaults.cardElevation(defaultElevation = 0.dp)
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column {
                    Text(
                        "已建账 ${state.builtTotal} 项",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold
                    )
                    Text(
                        "期初合计: ${formatQuantity(state.builtQuantity)}",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
                // 提示用户"点一行就能改"——不然用户不知道列表可点
                Text(
                    "点击行可修改",
                    style = MaterialTheme.typography.bodySmall,
                    color = CardCyan
                )
            }
        }

        // 关键字筛选（编码/名称/规格，与服务端同口径）
        OutlinedTextField(
            value = keyword,
            onValueChange = onKeywordChange,
            placeholder = { Text("搜索物料编码 / 名称 / 规格") },
            leadingIcon = { Icon(Icons.Outlined.Search, null, tint = CardCyan) },
            trailingIcon = {
                if (keyword.isNotEmpty()) {
                    IconButton(onClick = { onKeywordChange("") }) {
                        Icon(Icons.Outlined.Close, "清空", tint = OnSurfaceSecondary)
                    }
                }
            },
            singleLine = true,
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 8.dp),
            shape = RoundedCornerShape(12.dp),
            colors = OutlinedTextFieldDefaults.colors(
                focusedBorderColor = CardCyan,
                focusedLabelColor = CardCyan
            )
        )

        when {
            state.builtFirstLoad -> Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(48.dp),
                contentAlignment = Alignment.Center
            ) { CircularProgressIndicator(color = CardCyan) }

            state.builtItems.isEmpty() -> Box(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth(),
                contentAlignment = Alignment.Center
            ) {
                WmsEmptyState(
                    icon = Icons.Outlined.Inventory2,
                    title = if (keyword.isNotBlank()) "没找到匹配的建账记录" else "本仓还没有期初建账",
                    subtitle = if (keyword.isNotBlank()) {
                        "换个编码 / 名称 / 规格关键字试试"
                    } else {
                        "切到「建账」扫码录入，建完会出现在这里"
                    },
                    accentColor = CardCyan
                )
            }

            else -> {
                val listState = rememberLazyListState()
                // 滑到末尾自动加载下一页（与查库存/概览列表同策略）
                val shouldLoadMore by remember {
                    derivedStateOf {
                        val last = listState.layoutInfo.visibleItemsInfo.lastOrNull()?.index ?: 0
                        last >= state.builtItems.size - 2
                    }
                }
                LaunchedEffect(shouldLoadMore, state.builtPage, state.builtTotalPages) {
                    if (shouldLoadMore && state.builtPage < state.builtTotalPages) onLoadMore()
                }

                LazyColumn(
                    state = listState,
                    modifier = Modifier
                        .weight(1f)
                        .fillMaxWidth(),
                    contentPadding = PaddingValues(horizontal = 16.dp, vertical = 4.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    // BUG-2026-09-14-031 同约定：key 三级兜底，避免 id 为 null 时冲突崩溃
                    items(
                        state.builtItems,
                        key = { it.id ?: it.materialCode ?: it.hashCode() }
                    ) { item ->
                        BuiltItemCard(item = item, onClick = { onItemClick(item) })
                    }
                    item { BuiltListFooter(state) }
                }
            }
        }
    }
}

@Composable
private fun BuiltItemCard(item: OpeningStockDto, onClick: () -> Unit) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
        shape = RoundedCornerShape(14.dp),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
        colors = CardDefaults.cardColors(containerColor = CardBackground)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(14.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    item.materialCode.orEmpty(),
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.SemiBold,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
                val details = listOfNotNull(
                    item.materialName?.takeIf { it.isNotBlank() },
                    item.spec?.takeIf { it.isNotBlank() }
                ).joinToString("  ")
                if (details.isNotBlank()) {
                    Text(
                        details,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis
                    )
                }
                val meta = listOfNotNull(
                    item.date?.takeIf { it.isNotBlank() }?.let { "建账日 $it" },
                    item.price?.let { "单价 ¥%.2f".format(it) }
                ).joinToString("   ")
                if (meta.isNotBlank()) {
                    Text(
                        meta,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
            // 期初数量胶囊
            Surface(
                shape = RoundedCornerShape(10.dp),
                color = CardCyan.copy(alpha = 0.10f)
            ) {
                Text(
                    formatQuantity(item.quantity ?: 0.0),
                    modifier = Modifier.padding(horizontal = 10.dp, vertical = 5.dp),
                    color = CardCyan,
                    fontSize = 14.sp,
                    fontWeight = FontWeight.Bold
                )
            }
            Spacer(modifier = Modifier.width(6.dp))
            Icon(
                Icons.Outlined.ChevronRight,
                "编辑",
                tint = OnSurfaceSecondary,
                modifier = Modifier.size(20.dp)
            )
        }
    }
}

@Composable
private fun BuiltListFooter(state: com.factory.wms.ui.viewmodel.opening.OpeningStockUiState) {
    when {
        state.builtLoadingMore -> Box(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            contentAlignment = Alignment.Center
        ) { CircularProgressIndicator(modifier = Modifier.size(22.dp), color = CardCyan) }

        state.builtPage < state.builtTotalPages -> Box(
            modifier = Modifier
                .fillMaxWidth()
                .padding(12.dp),
            contentAlignment = Alignment.Center
        ) {
            TextButton(onClick = { /* 由 shouldLoadMore 自动触发 */ }) {
                Text("上滑加载更多", fontSize = 12.sp)
            }
        }

        state.builtTotal > 0 -> Box(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            contentAlignment = Alignment.Center
        ) {
            Text(
                "— 已全部加载 —",
                fontSize = 12.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}
