package com.factory.wms.ui.screens

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.factory.wms.data.model.ScanLine
import com.factory.wms.ui.theme.CardPurple
import com.factory.wms.ui.viewmodel.scan.ScanViewModel
import com.factory.wms.util.formatQuantity

/** 提交选择前以捕获时的数量核对当前行，防止覆盖后来发生的修改。 */
@Composable
internal fun StocktakeDuplicateDialog(
    incoming: ScanLine,
    original: ScanLine,
    viewModel: ScanViewModel,
    onDismiss: () -> Unit
) {
    var error by remember(incoming, original) { mutableStateOf<String?>(null) }
    val unit = original.material_unit?.takeIf { it.isNotBlank() }?.let { " $it" }.orEmpty()
    val sum = original.quantity + incoming.quantity
    fun apply(value: Double) {
        if (viewModel.hasPendingQuantityDraft(original)) {
            error = "请先确定或取消该物料正在修改的数量。"
        } else if (viewModel.updateScanLineQuantity(original, value, allowZero = true)) onDismiss()
        else error = "原明细已变化或当前不可修改，请取消后重新核对。"
    }
    AlertDialog(
        onDismissRequest = onDismiss,
        shape = RoundedCornerShape(20.dp),
        title = { Text("该物料已盘点") },
        text = {
            Column {
                Text(listOfNotNull(original.material_code, original.material_name?.takeIf { it.isNotBlank() }).joinToString("｜"))
                Text("原实盘：${formatQuantity(original.quantity)}$unit；本次：${formatQuantity(incoming.quantity)}$unit")
                Text(if (sum.isFinite()) "累加后 ${formatQuantity(sum)}$unit；替换后 ${formatQuantity(incoming.quantity)}$unit"
                    else "累加数量过大，请重新核对")
                error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            }
        },
        confirmButton = {
            Column(Modifier.fillMaxWidth()) {
                Button(onClick = { apply(sum) }, enabled = sum.isFinite(),
                    colors = ButtonDefaults.buttonColors(containerColor = CardPurple),
                    modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) { Text("累加") }
                TextButton(onClick = { apply(incoming.quantity) }, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) {
                    Text("替换为本次数量")
                }
                TextButton(onClick = onDismiss, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) { Text("取消") }
            }
        }
    )
}
