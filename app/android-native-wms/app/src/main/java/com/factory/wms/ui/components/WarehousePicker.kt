package com.factory.wms.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.outlined.Warehouse
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.factory.wms.data.model.WarehouseDto
import com.factory.wms.ui.theme.CardTeal
import com.factory.wms.ui.theme.OnSurfaceVariant
import com.factory.wms.ui.theme.SurfaceVariant

/**
 * 通用仓库选择对话框。入库/出库/盘点/期初建账等需要指定仓库的场景共用。
 * accentColor 用于高亮选中态与图标颜色，默认取主题色 CardTeal。
 */
@Composable
fun WarehousePickerDialog(
    warehouses: List<WarehouseDto>,
    selected: WarehouseDto?,
    loading: Boolean,
    onDismiss: () -> Unit,
    onSelect: (WarehouseDto) -> Unit,
    onRetry: () -> Unit,
    accentColor: Color = CardTeal
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(20.dp),
        title = { Text("选择仓库", fontWeight = FontWeight.SemiBold) },
        text = {
            if (loading) {
                Box(modifier = Modifier.fillMaxWidth().padding(24.dp), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator(color = accentColor)
                }
            } else if (warehouses.isEmpty()) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Text("暂无可用仓库", color = OnSurfaceVariant)
                    Spacer(modifier = Modifier.height(8.dp))
                    TextButton(onClick = onRetry) { Text("重新加载") }
                }
            } else {
                LazyColumn(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    itemsIndexed(warehouses) { _, warehouse ->
                        val isSelected = selected?.id == warehouse.id
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clip(RoundedCornerShape(14.dp))
                                .background(if (isSelected) accentColor.copy(alpha = 0.10f) else Color.Transparent)
                                .clickable { onSelect(warehouse) }
                                .padding(horizontal = 12.dp, vertical = 10.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Box(
                                modifier = Modifier
                                    .size(36.dp)
                                    .clip(RoundedCornerShape(10.dp))
                                    .background(
                                        if (isSelected) accentColor.copy(alpha = 0.16f)
                                        else SurfaceVariant
                                    ),
                                contentAlignment = Alignment.Center
                            ) {
                                Icon(
                                    Icons.Outlined.Warehouse,
                                    null,
                                    tint = if (isSelected) accentColor else OnSurfaceVariant,
                                    modifier = Modifier.size(19.dp)
                                )
                            }
                            Spacer(modifier = Modifier.width(12.dp))
                            Column(modifier = Modifier.weight(1f)) {
                                Text(
                                    "${warehouse.code.orEmpty()} ${warehouse.name.orEmpty()}",
                                    style = MaterialTheme.typography.titleSmall,
                                    fontWeight = FontWeight.SemiBold
                                )
                            }
                            if (isSelected) {
                                Icon(Icons.Filled.CheckCircle, null, tint = accentColor, modifier = Modifier.size(20.dp))
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