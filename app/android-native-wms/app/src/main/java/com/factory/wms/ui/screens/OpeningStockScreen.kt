package com.factory.wms.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
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
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.factory.wms.data.model.OpeningStockLine
import com.factory.wms.data.model.WarehouseDto
import com.factory.wms.ui.components.ScannerDialog
import com.factory.wms.ui.theme.*
import com.factory.wms.ui.viewmodel.opening.OpeningStockViewModel
import com.factory.wms.util.formatQuantity
import java.util.Calendar

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun OpeningStockScreen(
    viewModel: OpeningStockViewModel,
    onBack: () -> Unit
) {
    val uiState by viewModel.uiState.collectAsState()
    var showManualDialog by remember { mutableStateOf(false) }
    var showCameraScanner by remember { mutableStateOf(false) }
    var showDateDialog by remember { mutableStateOf(false) }
    var showWarehouseDialog by remember { mutableStateOf(false) }
    var manualCode by remember { mutableStateOf("") }
    var manualQty by remember { mutableStateOf("1") }
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
            snackbarHostState.showSnackbar(it, duration = SnackbarDuration.Long)
            viewModel.clearSuccess()
        }
    }

    Scaffold(
        snackbarHost = { SnackbarHost(snackbarHostState) },
        containerColor = Background,
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text("期初库存", fontWeight = FontWeight.Bold, fontSize = 20.sp)
                        Text(
                            "选择日期+仓库，扫码录入初始化库存",
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
                .fillMaxSize()
                .padding(padding)
        ) {
            // 日期 + 仓库选择
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 4.dp),
                horizontalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                // 日期
                OutlinedCard(
                    onClick = { showDateDialog = true },
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
                        Icon(
                            Icons.Outlined.CalendarMonth,
                            null,
                            tint = CardTeal,
                            modifier = Modifier.size(20.dp)
                        )
                        Spacer(modifier = Modifier.width(8.dp))
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
                // 仓库
                OutlinedCard(
                    onClick = { showWarehouseDialog = true },
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
                        Icon(
                            Icons.Outlined.Warehouse,
                            null,
                            tint = CardTeal,
                            modifier = Modifier.size(20.dp)
                        )
                        Spacer(modifier = Modifier.width(8.dp))
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
                    colors = CardDefaults.cardColors(containerColor = CardTeal.copy(alpha = 0.06f)),
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
                            onClick = { viewModel.clearLines() },
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
                            onRemove = { viewModel.removeLine(index) }
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
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Box(
                            modifier = Modifier
                                .size(80.dp)
                                .clip(CircleShape)
                                .background(CardTeal.copy(alpha = 0.06f)),
                            contentAlignment = Alignment.Center
                        ) {
                            Icon(
                                Icons.Outlined.QrCodeScanner,
                                null,
                                modifier = Modifier.size(40.dp),
                                tint = CardTeal.copy(alpha = 0.5f)
                            )
                        }
                        Spacer(modifier = Modifier.height(16.dp))
                        Text(
                            "暂无期初物料",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.SemiBold,
                            color = OnSurface
                        )
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(
                            "点击下方按钮扫码或手动添加",
                            style = MaterialTheme.typography.bodySmall,
                            color = OnSurfaceVariant
                        )
                    }
                }
            }

            // 底部操作
            Surface(
                modifier = Modifier.fillMaxWidth(),
                shadowElevation = 8.dp,
                color = MaterialTheme.colorScheme.surface
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Button(
                        onClick = { viewModel.submit() },
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(52.dp),
                        enabled = uiState.lines.isNotEmpty() && uiState.selectedWarehouse != null && !uiState.isLoading,
                        shape = RoundedCornerShape(14.dp),
                        colors = ButtonDefaults.buttonColors(
                            containerColor = CardTeal,
                            disabledContainerColor = CardTeal.copy(alpha = 0.3f)
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
                            onClick = { showCameraScanner = true },
                            modifier = Modifier
                                .weight(1f)
                                .height(48.dp),
                            shape = RoundedCornerShape(12.dp),
                            border = ButtonDefaults.outlinedButtonBorder.copy(
                                brush = androidx.compose.ui.graphics.SolidColor(CardTeal.copy(alpha = 0.3f))
                            )
                        ) {
                            Icon(
                                Icons.Outlined.QrCodeScanner,
                                null,
                                modifier = Modifier.size(20.dp),
                                tint = CardTeal
                            )
                            Spacer(Modifier.width(6.dp))
                            Text("扫码添加", color = CardTeal, fontWeight = FontWeight.Medium)
                        }
                        OutlinedButton(
                            onClick = { showManualDialog = true },
                            modifier = Modifier
                                .weight(1f)
                                .height(48.dp),
                            shape = RoundedCornerShape(12.dp),
                            border = ButtonDefaults.outlinedButtonBorder.copy(
                                brush = androidx.compose.ui.graphics.SolidColor(CardTeal.copy(alpha = 0.3f))
                            )
                        ) {
                            Icon(
                                Icons.Outlined.Edit,
                                null,
                                modifier = Modifier.size(20.dp),
                                tint = CardTeal
                            )
                            Spacer(Modifier.width(6.dp))
                            Text("手动添加", color = CardTeal, fontWeight = FontWeight.Medium)
                        }
                    }
                }
            }
        }
    }

    // 手动添加对话框
    if (showManualDialog) {
        AlertDialog(
            onDismissRequest = { showManualDialog = false },
            shape = RoundedCornerShape(20.dp),
            title = { Text("添加期初物料", fontWeight = FontWeight.SemiBold) },
            text = {
                Column {
                    OutlinedTextField(
                        value = manualCode,
                        onValueChange = { manualCode = it },
                        label = { Text("物料编码") },
                        placeholder = { Text("输入或扫描物料编码") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(12.dp),
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedBorderColor = CardTeal,
                            focusedLabelColor = CardTeal
                        )
                    )
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
                                containerColor = CardTeal.copy(alpha = 0.1f)
                            )
                        ) {
                            Icon(Icons.Outlined.Remove, "减1", tint = CardTeal, modifier = Modifier.size(22.dp))
                        }
                        Spacer(modifier = Modifier.width(8.dp))
                        OutlinedTextField(
                            value = manualQty,
                            onValueChange = { manualQty = it },
                            label = { Text("数量") },
                            singleLine = true,
                            modifier = Modifier.weight(1f),
                            shape = RoundedCornerShape(12.dp),
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedBorderColor = CardTeal,
                                focusedLabelColor = CardTeal
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
                            colors = IconButtonDefaults.filledIconButtonColors(containerColor = CardTeal)
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
                    colors = ButtonDefaults.buttonColors(containerColor = CardTeal)
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
            onBarcodeScanned = { barcode ->
                showCameraScanner = false
                viewModel.addLine(barcode, manualQty.toDoubleOrNull() ?: 1.0)
                manualCode = ""
                manualQty = "1"
            }
        )
    }
}

@Composable
private fun OpeningStockLineCard(
    line: OpeningStockLine,
    index: Int,
    onRemove: () -> Unit
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
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
            Box(
                modifier = Modifier
                    .size(36.dp)
                    .clip(CircleShape)
                    .background(CardTeal.copy(alpha = 0.1f)),
                contentAlignment = Alignment.Center
            ) {
                Text("${index + 1}", color = CardTeal, fontWeight = FontWeight.Bold, fontSize = 14.sp)
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
                Text(
                    "数量: ${formatQuantity(line.quantity)}" +
                        (line.price?.let { "  单价: ¥${"%.2f".format(it)}" } ?: ""),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
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
private fun WarehousePickerDialog(
    warehouses: List<WarehouseDto>,
    selected: WarehouseDto?,
    loading: Boolean,
    onDismiss: () -> Unit,
    onSelect: (WarehouseDto) -> Unit,
    onRetry: () -> Unit
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(20.dp),
        title = { Text("选择仓库", fontWeight = FontWeight.SemiBold) },
        text = {
            if (loading) {
                Box(modifier = Modifier.fillMaxWidth().padding(24.dp), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator(color = CardTeal)
                }
            } else if (warehouses.isEmpty()) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Text("暂无可用仓库", color = OnSurfaceVariant)
                    Spacer(modifier = Modifier.height(8.dp))
                    TextButton(onClick = onRetry) { Text("重新加载") }
                }
            } else {
                LazyColumn {
                    itemsIndexed(warehouses) { _, warehouse ->
                        val isSelected = selected?.id == warehouse.id
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clip(RoundedCornerShape(12.dp))
                                .background(if (isSelected) CardTeal.copy(alpha = 0.08f) else Color.Transparent)
                                .clickable { onSelect(warehouse) }
                                .padding(12.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Icon(
                                Icons.Outlined.Warehouse,
                                null,
                                tint = if (isSelected) CardTeal else OnSurfaceVariant,
                                modifier = Modifier.size(20.dp)
                            )
                            Spacer(modifier = Modifier.width(10.dp))
                            Column(modifier = Modifier.weight(1f)) {
                                Text(
                                    "${warehouse.code.orEmpty()} ${warehouse.name.orEmpty()}",
                                    style = MaterialTheme.typography.titleSmall,
                                    fontWeight = FontWeight.SemiBold
                                )
                            }
                            if (isSelected) {
                                Icon(Icons.Filled.CheckCircle, null, tint = CardTeal, modifier = Modifier.size(20.dp))
                            }
                        }
                    }
                }
            }
        },
        confirmButton = {
            TextButton(onClick = onDismiss) { Text("取消") }
        }
    )
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
                    color = CardTeal
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
                colors = ButtonDefaults.buttonColors(containerColor = CardTeal)
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
            colors = IconButtonDefaults.filledIconButtonColors(containerColor = CardTeal.copy(alpha = 0.1f))
        ) { Icon(Icons.Filled.KeyboardArrowLeft, "上一年", tint = CardTeal) }
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
            colors = IconButtonDefaults.filledIconButtonColors(containerColor = CardTeal.copy(alpha = 0.1f))
        ) { Icon(Icons.Filled.KeyboardArrowRight, "下一年", tint = CardTeal) }
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
            colors = IconButtonDefaults.filledIconButtonColors(containerColor = CardTeal.copy(alpha = 0.1f))
        ) { Icon(Icons.Filled.KeyboardArrowLeft, "上一月", tint = CardTeal) }
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
            colors = IconButtonDefaults.filledIconButtonColors(containerColor = CardTeal.copy(alpha = 0.1f))
        ) { Icon(Icons.Filled.KeyboardArrowRight, "下一月", tint = CardTeal) }
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
            colors = IconButtonDefaults.filledIconButtonColors(containerColor = CardTeal.copy(alpha = 0.1f))
        ) { Icon(Icons.Filled.KeyboardArrowLeft, "前一天", tint = CardTeal) }
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
            colors = IconButtonDefaults.filledIconButtonColors(containerColor = CardTeal.copy(alpha = 0.1f))
        ) { Icon(Icons.Filled.KeyboardArrowRight, "后一天", tint = CardTeal) }
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