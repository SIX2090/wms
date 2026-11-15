package com.factory.wms.ui.components

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import com.factory.wms.data.api.RetrofitClient
import com.factory.wms.data.model.PendingNativeWrite
import com.factory.wms.data.repository.WmsRepository
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.launch

/** User-owned unresolved writes are never submitted by startup, login, or this read-only collector. */
@Composable
internal fun PendingNativeWriteStatus(session: RetrofitClient.SessionSnapshot) {
    val context = LocalContext.current.applicationContext
    val repository = remember(context) { WmsRepository(context) }
    val changes by WmsRepository.nativeWriteChanges.collectAsState()
    var rows by remember(session.generation) { mutableStateOf<List<PendingNativeWrite>>(emptyList()) }
    var readError by remember(session.generation) { mutableStateOf(false) }
    var showing by remember(session.generation) { mutableStateOf(false) }
    var busy by remember(session.generation) { mutableStateOf(false) }
    var message by remember(session.generation) { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()
    LaunchedEffect(session.generation, changes) {
        try {
            val result = repository.pendingNativeWrites()
            if (session.generation == RetrofitClient.sessionSnapshot().generation) {
                rows = result; readError = false
            }
        } catch (cancelled: CancellationException) { throw cancelled
        } catch (_: Exception) { readError = true }
    }
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
                    PendingNativeWriteDetails(row, busy, onVerify = {
                            busy = true
                            scope.launch {
                                try {
                                    val result = repository.verifyPendingNativeWrite(row.requestId)
                                    if (session.generation == RetrofitClient.sessionSnapshot().generation)
                                        message = result.getOrElse { it.message ?: "核实未完成，原记录已保留" }
                                } finally { busy = false }
                            }
                        }, onAcknowledge = {
                            busy = true
                            scope.launch {
                                try {
                                    repository.acknowledgeNativeWrite(row.operation, row.requestId)
                                    if (session.generation == RetrofitClient.sessionSnapshot().generation)
                                        message = "已结束此请求，可以开始新单；请勿再次录入同一笔业务"
                                } catch (cancelled: CancellationException) { throw cancelled
                                } catch (error: Exception) { message = error.message
                                } finally { busy = false }
                            }
                        })
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
