package com.factory.wms.ui.components

import androidx.compose.foundation.layout.Box
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowDropDown
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.Icon
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
import androidx.compose.ui.unit.sp
import com.factory.wms.data.model.WarehouseDto

/**
 * 仓库切换下拉（默认仓库 / 各仓 / 全部仓库汇总）。
 *
 * BUG-2026-09-10-009（日报）与 BUG-2026-09-10-010（首页概览）同根因：多仓用户
 * 此前只能看系统默认仓。两个页面需要一致的切换体验，故提取为共享组件，避免
 * 两处实现逐渐漂移。
 *
 * 布局由调用方通过 [modifier] 控制（默认水平内边距 16dp，与报表页一致）。
 *
 * @param currentLabel 当前口径显示名（由服务端回传，如"成品仓"/"全部仓库"）
 * @param selectedId null=默认仓，"all"=全部仓库汇总，其余=仓库 id
 * @param allowAll 是否提供"全部仓库（汇总）"选项（首页支持；每日报表按需求不提供）
 * @param showDefaultWarehouse 是否提供"默认仓库"选项（首页支持；每日报表按需求不提供，
 *        此时下拉只列真实仓库，进入页默认选中第一个仓库）。
 */
@Composable
fun WarehouseSelector(
    currentLabel: String?,
    warehouses: List<WarehouseDto>,
    selectedId: String?,
    onSelect: (String?) -> Unit,
    allowAll: Boolean = true,
    showDefaultWarehouse: Boolean = true,
    modifier: Modifier = Modifier
) {
    var expanded by remember { mutableStateOf(false) }
    // 当前选中仓库（无回传标签时取名称兜底，避免去掉"默认仓库"后显示成空/错名称）
    val chosen = warehouses.firstOrNull { it.id?.toString() == selectedId }
    val label = when {
        !currentLabel.isNullOrBlank() -> currentLabel
        chosen != null -> chosen.name ?: chosen.code ?: chosen.id?.toString() ?: "选择仓库"
        showDefaultWarehouse -> "默认仓库"
        else -> warehouses.firstOrNull()?.name
            ?: warehouses.firstOrNull()?.code
            ?: "选择仓库"
    }
    Box(modifier = modifier) {
        TextButton(onClick = { expanded = true }) {
            Text(label, fontSize = 14.sp)
            Icon(
                Icons.Filled.ArrowDropDown,
                "切换仓库",
                tint = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
        DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            if (showDefaultWarehouse) {
                DropdownMenuItem(
                    text = { Text("默认仓库") },
                    onClick = { expanded = false; onSelect(null) }
                )
            }
            warehouses.forEach { wh ->
                val id = wh.id?.toString() ?: return@forEach
                DropdownMenuItem(
                    text = { Text(wh.name ?: wh.code ?: id) },
                    onClick = { expanded = false; onSelect(id) }
                )
            }
            if (allowAll) {
                DropdownMenuItem(
                    text = { Text("全部仓库（汇总）") },
                    onClick = { expanded = false; onSelect("all") }
                )
            }
        }
    }
}
