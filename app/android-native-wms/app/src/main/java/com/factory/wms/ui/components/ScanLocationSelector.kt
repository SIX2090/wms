package com.factory.wms.ui.components

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.factory.wms.ui.viewmodel.scan.ScanViewModel

@Composable
fun ScanLocationSelector(viewModel: ScanViewModel) {
    val state by viewModel.uiState.collectAsState()
    var camera by remember { mutableStateOf(false) }
    var choose by remember { mutableStateOf(false) }
    val editable = !state.isLoading && state.pendingSubmissionId == null
    if (state.locationEnabled == false) return
    Column(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp)) {
        if (state.locationEnabled == null) {
            Text("库位配置未确认，请联网加载；不能据此判定无需库位")
            TextButton(onClick = { viewModel.loadLocationOptions() }, enabled = editable) { Text("加载库位配置") }
        } else {
            OutlinedTextField(
                value = state.selectedLocation,
                onValueChange = { viewModel.selectLocation(it) },
                label = { Text("库位（必填，同一单据使用一个库位）") },
                singleLine = true, enabled = editable, modifier = Modifier.fillMaxWidth()
            )
            Row {
                TextButton(onClick = { choose = true }, enabled = editable) { Text("选择已有库位") }
                TextButton(onClick = { camera = true }, enabled = editable) { Text("扫描库位标签") }
            }
            Text("修改库位将应用到本单全部行；不同库位请分单。")
        }
        state.locationError?.let { Text(it, color = MaterialTheme.colorScheme.error) }
    }
    if (choose) {
        AlertDialog(onDismissRequest = { choose = false }, title = { Text("选择本仓库位") },
            text = {
                Column(Modifier.heightIn(max = 320.dp).verticalScroll(rememberScrollState())) {
                    if (state.locationOptions.isEmpty()) Text("本仓暂无已有库位，请输入或扫描实际库位编码。")
                    state.locationOptions.forEach { location ->
                        TextButton(onClick = { viewModel.selectLocation(location); choose = false }) { Text(location) }
                    }
                }
            }, confirmButton = { TextButton(onClick = { choose = false }) { Text("关闭") } })
    }
    if (camera) {
        ScannerDialog(onDismiss = { camera = false }, continuous = false,
            onBarcodeScanned = { viewModel.selectLocation(it); camera = false })
    }
}
