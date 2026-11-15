package com.factory.wms.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.CheckCircle
import androidx.compose.material.icons.outlined.HelpOutline
import androidx.compose.material.icons.outlined.Info
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.factory.wms.data.api.OcrItem
import com.factory.wms.ui.theme.Primary
import com.factory.wms.ui.theme.PrimaryContainer
import com.factory.wms.ui.theme.Warning
import com.factory.wms.ui.theme.WarningContainer
import com.factory.wms.ui.theme.readableOn
import com.factory.wms.util.formatQuantity

/** 展示识别数据与档案匹配状态，不把未知识别结果伪装为系统数据。 */
@Composable
internal fun DocumentOcrItemCard(item: OcrItem, index: Int) {
    val background = when (item.matched) {
        true -> PrimaryContainer
        false -> WarningContainer
        null -> MaterialTheme.colorScheme.surfaceVariant
    }
    val foreground = when (item.matched) {
        true -> Primary.readableOn(background)
        false -> Warning.readableOn(background)
        null -> MaterialTheme.colorScheme.onSurfaceVariant
    }
    val status = when (item.matched) {
        true -> item.code?.takeIf { it.isNotBlank() }?.let { "已匹配 $it" } ?: "已匹配"
        false -> "未匹配档案"
        null -> "匹配状态未获取"
    }
    val quantity = item.quantity?.let { value ->
        formatQuantity(value) + item.unit?.takeIf { it.isNotBlank() }?.let { " $it" }.orEmpty()
    } ?: "数量未识别（草稿默认 1）"
    Card(modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)) {
        Column(Modifier.fillMaxWidth().padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(item.name?.takeIf { it.isNotBlank() } ?: item.code?.takeIf { it.isNotBlank() } ?: "物料 ${index + 1}",
                style = MaterialTheme.typography.bodyLarge, fontWeight = FontWeight.SemiBold,
                maxLines = 2, overflow = TextOverflow.Ellipsis, color = MaterialTheme.colorScheme.onSurface)
            item.spec?.takeIf { it.isNotBlank() }?.let {
                Text("规格：$it", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant,
                    softWrap = true)
            }
            Surface(shape = RoundedCornerShape(6.dp), color = background) {
                Row(Modifier.padding(horizontal = 8.dp, vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                    Icon(when (item.matched) { true -> Icons.Outlined.CheckCircle; false -> Icons.Outlined.Info; null -> Icons.Outlined.HelpOutline },
                        null, tint = foreground, modifier = Modifier.size(18.dp))
                    Spacer(Modifier.width(6.dp))
                    Text(status, color = foreground, style = MaterialTheme.typography.bodyMedium, softWrap = true)
                }
            }
            Text(quantity, style = MaterialTheme.typography.bodyLarge.copy(fontFamily = FontFamily.Monospace, fontSize = 18.sp),
                fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.onSurface, softWrap = true)
        }
    }
}
