package com.factory.wms.ui.components

import androidx.compose.foundation.layout.*
import androidx.compose.material3.LocalTextStyle
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.factory.wms.ui.util.quantityDisplayText

/** 物料识别信息完整换行，名称、编码和规格各有明确层级。 */
@Composable
fun WmsMaterialIdentity(code: String, name: String?, brand: String?, spec: String?) {
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(name?.takeIf { it.isNotBlank() } ?: code, modifier = Modifier.fillMaxWidth(),
            style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
        if (!name.isNullOrBlank()) {
            Text("编码 $code", modifier = Modifier.fillMaxWidth(), style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        val details = listOfNotNull(brand?.takeIf { it.isNotBlank() }, spec?.takeIf { it.isNotBlank() }).joinToString(" · ")
        if (details.isNotBlank()) {
            Text(details, modifier = Modifier.fillMaxWidth(), style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant, softWrap = true)
        }
    }
}

@Composable
fun WmsQuantityText(value: String, modifier: Modifier = Modifier, color: Color = MaterialTheme.colorScheme.onSurface,
    fontSize: androidx.compose.ui.unit.TextUnit = 20.sp) {
    Text(quantityDisplayText(value), modifier = modifier, fontSize = fontSize,
        fontWeight = FontWeight.SemiBold, softWrap = true, color = color,
        style = LocalTextStyle.current.copy(fontFeatureSettings = "tnum"))
}

/** 普通数量自然并排；长数量、窄屏或大字体使用完整行，不缩小关键数字。 */
@Composable
fun WmsAdaptiveRecord(
    quantityText: String,
    identity: @Composable () -> Unit,
    quantity: @Composable () -> Unit
) {
    val density = LocalDensity.current
    val measurer = rememberTextMeasurer()
    val quantityStyle = MaterialTheme.typography.titleMedium.copy(fontSize = 20.sp, fontWeight = FontWeight.SemiBold)
    BoxWithConstraints(Modifier.fillMaxWidth()) {
        val naturalWidth = measurer.measure(quantityText, style = quantityStyle, softWrap = false).size.width
        val availableWidth = with(density) { maxWidth.toPx() }
        if (density.fontScale <= 1.3f && naturalWidth < availableWidth * 0.36f) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                Column(Modifier.weight(1f)) { identity() }
                Column(Modifier.width(with(density) { naturalWidth.toDp() } + 4.dp)) { quantity() }
            }
        } else {
            Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                identity()
                quantity()
            }
        }
    }
}
