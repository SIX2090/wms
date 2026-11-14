package com.factory.wms.update

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

@Composable
internal fun AppUpdatePanel(manager: AppUpdateManager) {
    val state by manager.state.collectAsState()
    Column(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp)) {
        Text(state.message, style = MaterialTheme.typography.bodySmall)
        state.progress?.let { progress ->
            LinearProgressIndicator(progress = { progress / 100f }, modifier = Modifier.fillMaxWidth())
            Text("$progress%", style = MaterialTheme.typography.labelSmall)
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            TextButton(onClick = { manager.check() }, enabled = !state.busy && !state.installing) {
                Text(if (state.message.startsWith("更新未完成")) "重试更新" else "检查更新")
            }
            if (state.ready) TextButton(onClick = { manager.install() }, enabled = !state.installing) {
                Text("安装更新")
            }
        }
    }
}
