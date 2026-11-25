package com.factory.wms.ui.components

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.factory.wms.data.api.RetrofitClient
import com.factory.wms.data.model.PendingNativeWrite
import com.factory.wms.ui.viewmodel.sync.SyncStatusViewModel

/** User-owned unresolved writes are never submitted by startup, login, or this read-only collector. */
@Composable
internal fun PendingNativeWriteStatus(
    session: RetrofitClient.SessionSnapshot,
    syncViewModel: SyncStatusViewModel = viewModel()
) {
    val state by syncViewModel.pendingWriteUiState.collectAsState()
    var showing by remember(session.generation) { mutableStateOf(false) }
    LaunchedEffect(session.generation) {
        syncViewModel.bindSession(session)
    }
    val rows = if (state.sessionGeneration == session.generation) state.rows else emptyList()
    val readError = state.sessionGeneration == session.generation && state.readError
    val busy = state.sessionGeneration == session.generation && state.busy
    val message = if (state.sessionGeneration == session.generation) state.message else null
    if (rows.isEmpty() && !readError) return
    TextButton(onClick = { showing = true }, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) {
        Text(if (readError) "待核实提交记录暂不可读，请保留当前内容" else "${rows.size} 条提交待核实，点击查看原请求")
    }
    if (showing) AlertDialog(
        onDismissRequest = { if (!busy) showing = false },
        title = { Text("需要核实原提交请求") },
        text = {
            Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text("原内容和请求号已保留。核实会按原请求查询或完成原提交，请勿重复录入。")
                rows.forEach { row ->
                    PendingNativeWriteDetails(
                        row = row,
                        busy = busy,
                        onVerify = { syncViewModel.verify(session, row.requestId) },
                        onAcknowledge = { syncViewModel.acknowledge(session, row.operation, row.requestId) }
                    )
                }
                message?.let { Text(it) }
            }
        },
        confirmButton = { TextButton(enabled = !busy, modifier = Modifier.heightIn(min = 48.dp), onClick = { showing = false }) { Text("返回核对") } }
    )
}

@Composable
internal fun PendingNativeWriteDetails(row: PendingNativeWrite, busy: Boolean,
    onVerify: () -> Unit, onAcknowledge: () -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text("类型：${nativeWriteLabel(row.operation)}", style = MaterialTheme.typography.bodyLarge)
        Text("请求号：${row.requestId}", fontFamily = FontFamily.Monospace,
            style = MaterialTheme.typography.bodyMedium, softWrap = true)
        Text(if (row.responseJson != null) "回执状态：已取得回执" else "回执状态：未收到服务器回执",
            style = MaterialTheme.typography.bodyMedium)
        TextButton(enabled = !busy, modifier = Modifier.heightIn(min = 48.dp), onClick = onVerify) { Text("核实原请求") }
        if (row.responseJson != null) TextButton(enabled = !busy, modifier = Modifier.heightIn(min = 48.dp),
            onClick = onAcknowledge) { Text("已核对，结束此请求") }
    }
}

internal fun nativeWriteLabel(operation: String): String = when {
    operation == "stocktake" -> "盘点提交"
    operation == "opening_stock" -> "期初建账"
    operation.startsWith("opening_stock_edit:") -> "期初修改"
    operation == "inbound_draft" -> "识别入库草稿"
    operation.startsWith("voice_out_draft:") -> "语音领料草稿"
    operation == "voice_intent" -> "语音指令"
    operation.startsWith("assistant_chat") -> "AI助手请求"
    else -> "原提交"
}
