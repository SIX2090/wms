package com.factory.wms.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.outlined.Clear
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.factory.wms.ui.theme.CardBackground
import com.factory.wms.ui.theme.OnSurface
import com.factory.wms.ui.theme.OnSurfaceVariant
import com.factory.wms.ui.theme.SurfaceVariant

/**
 * 通用下拉选择卡片（2026-09-12 出库「领料部门/领料人」）。
 * 与 WarehouseSelectorCard 同款视觉；valueText 为 null 时显示 placeholder。
 */
@Composable
fun PartySelectorCard(
    label: String,
    placeholder: String,
    valueText: String?,
    icon: ImageVector,
    accentColor: Color,
    onClick: () -> Unit
) {
    OutlinedCard(
        onClick = onClick,
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 8.dp),
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
                    .background(accentColor.copy(alpha = 0.12f)),
                contentAlignment = Alignment.Center
            ) {
                Icon(icon, null, tint = accentColor, modifier = Modifier.size(19.dp))
            }
            Spacer(modifier = Modifier.width(10.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text(label, style = MaterialTheme.typography.labelSmall, color = OnSurfaceVariant)
                Text(
                    valueText ?: placeholder,
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.SemiBold,
                    color = if (valueText != null) OnSurface else OnSurfaceVariant,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
            }
            Icon(Icons.Filled.KeyboardArrowDown, null, tint = OnSurfaceVariant, modifier = Modifier.size(20.dp))
        }
    }
}

/** 通用选择条目：主标题 + 副标题（如部门编码、员工职位/部门）。 */
data class PartyPickerItem(
    val id: Long,
    val title: String,
    val subtitle: String = ""
)

/**
 * 通用下拉选择对话框（2026-09-12 出库「领料部门/领料人」）。
 * 与 WarehousePickerDialog 同款交互；allowClear 时首行提供「清除选择」。
 */
@Composable
fun PartyPickerDialog(
    title: String,
    items: List<PartyPickerItem>,
    selectedId: Long?,
    loading: Boolean,
    icon: ImageVector,
    accentColor: Color,
    allowClear: Boolean = true,
    onDismiss: () -> Unit,
    onSelect: (PartyPickerItem?) -> Unit,
    onRetry: () -> Unit
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(20.dp),
        title = { Text(title, fontWeight = FontWeight.SemiBold) },
        text = {
            if (loading) {
                Box(modifier = Modifier.fillMaxWidth().padding(24.dp), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator(color = accentColor)
                }
            } else if (items.isEmpty() && !allowClear) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Text("暂无数据", color = OnSurfaceVariant)
                    Spacer(modifier = Modifier.height(8.dp))
                    TextButton(onClick = onRetry) { Text("重新加载") }
                }
            } else {
                LazyColumn(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    if (allowClear) {
                        item {
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .clip(RoundedCornerShape(14.dp))
                                    .clickable { onSelect(null) }
                                    .padding(horizontal = 12.dp, vertical = 10.dp),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Box(
                                    modifier = Modifier
                                        .size(36.dp)
                                        .clip(RoundedCornerShape(10.dp))
                                        .background(SurfaceVariant),
                                    contentAlignment = Alignment.Center
                                ) {
                                    Icon(Icons.Outlined.Clear, null, tint = OnSurfaceVariant, modifier = Modifier.size(19.dp))
                                }
                                Spacer(modifier = Modifier.width(12.dp))
                                Text(
                                    "不选择（留空）",
                                    style = MaterialTheme.typography.titleSmall,
                                    color = OnSurfaceVariant
                                )
                            }
                        }
                    }
                    if (items.isEmpty()) {
                        item {
                            Column(
                                modifier = Modifier.fillMaxWidth().padding(vertical = 12.dp),
                                horizontalAlignment = Alignment.CenterHorizontally
                            ) {
                                Text("暂无数据", color = OnSurfaceVariant)
                                Spacer(modifier = Modifier.height(8.dp))
                                TextButton(onClick = onRetry) { Text("重新加载") }
                            }
                        }
                    } else {
                        itemsIndexed(items) { _, item ->
                            val isSelected = selectedId == item.id
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .clip(RoundedCornerShape(14.dp))
                                    .background(if (isSelected) accentColor.copy(alpha = 0.10f) else Color.Transparent)
                                    .clickable { onSelect(item) }
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
                                        icon,
                                        null,
                                        tint = if (isSelected) accentColor else OnSurfaceVariant,
                                        modifier = Modifier.size(19.dp)
                                    )
                                }
                                Spacer(modifier = Modifier.width(12.dp))
                                Column(modifier = Modifier.weight(1f)) {
                                    Text(
                                        item.title,
                                        style = MaterialTheme.typography.titleSmall,
                                        fontWeight = FontWeight.SemiBold,
                                        maxLines = 1,
                                        overflow = TextOverflow.Ellipsis
                                    )
                                    if (item.subtitle.isNotBlank()) {
                                        Text(
                                            item.subtitle,
                                            style = MaterialTheme.typography.bodySmall,
                                            color = OnSurfaceVariant,
                                            maxLines = 1,
                                            overflow = TextOverflow.Ellipsis
                                        )
                                    }
                                }
                                if (isSelected) {
                                    Icon(Icons.Filled.CheckCircle, null, tint = accentColor, modifier = Modifier.size(20.dp))
                                }
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
