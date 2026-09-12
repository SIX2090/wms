package com.factory.wms.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.Restore
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarDuration
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.factory.wms.data.model.StocktakeRecordDto
import com.factory.wms.ui.components.WmsEmptyState
import com.factory.wms.ui.theme.Background
import com.factory.wms.ui.theme.CardAmber
import com.factory.wms.ui.theme.CardCyan
import com.factory.wms.ui.theme.CardPurple
import com.factory.wms.ui.theme.CardTeal
import com.factory.wms.ui.theme.OnSurface
import com.factory.wms.ui.theme.Primary
import com.factory.wms.ui.viewmodel.stocktake.StocktakeRecordViewModel

/**
 * 盘点记录回查页（AI-MOB-CHECK-F01）。
 *
 * 手机盘点提交后此前"提交即失联"：作业员看不到自己盘过哪些单、差异多少、
 * 是否已被 PC 端采纳。本页按「本人经手」回查，只读。
 * 服务端：GET /api/mobile/stocktake/list
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun StocktakeRecordScreen(
    viewModel: StocktakeRecordViewModel,
    onBack: () -> Unit
) {
    val uiState by viewModel.uiState.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }

    // BUG-2026-08-24-006：进入页面时才加载（ViewModel 在 App 启动导航图组合阶段
    // 即被创建，不能依赖 init 拉数据）
    LaunchedEffect(Unit) {
        viewModel.load()
    }

    LaunchedEffect(uiState.error) {
        uiState.error?.let {
            snackbarHostState.showSnackbar(it, duration = SnackbarDuration.Short)
            viewModel.clearError()
        }
    }

    Scaffold(
        snackbarHost = { SnackbarHost(snackbarHostState) },
        containerColor = Background,
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text("盘点记录", fontWeight = FontWeight.Bold, fontSize = 20.sp)
                        Text(
                            if (uiState.total > 0) "共 ${uiState.total} 条本人盘点记录" else "本人盘点记录回查",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(
                            Icons.Filled.ArrowBack,
                            "返回",
                            tint = MaterialTheme.colorScheme.onSurface
                        )
                    }
                },
                actions = {
                    IconButton(onClick = { viewModel.load() }) {
                        Icon(
                            Icons.Filled.Restore,
                            "刷新",
                            tint = MaterialTheme.colorScheme.onSurface
                        )
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.surface
                )
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .padding(padding)
                .fillMaxSize()
        ) {
            // ── 视图切换：正常记录 / 已作废 ──
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 8.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                FilterChip(
                    selected = !uiState.showVoided,
                    onClick = { if (uiState.showVoided) viewModel.toggleVoided() },
                    label = { Text("正常记录") }
                )
                FilterChip(
                    selected = uiState.showVoided,
                    onClick = { if (!uiState.showVoided) viewModel.toggleVoided() },
                    label = { Text("已作废") }
                )
            }

            when {
                uiState.isLoading && uiState.records.isEmpty() -> {
                    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        CircularProgressIndicator(color = Primary)
                    }
                }

                uiState.isEmpty -> {
                    WmsEmptyState(
                        icon = Icons.Filled.History,
                        title = if (uiState.showVoided) "没有已作废的盘点记录" else "还没有盘点记录",
                        subtitle = if (uiState.showVoided) {
                            "被作废的盘点单会在这里留痕，便于对账"
                        } else {
                            "在扫码盘点页选择进行中的盘点单提交后，记录会出现在这里"
                        },
                        modifier = Modifier.fillMaxSize(),
                        accentColor = CardPurple
                    )
                }

                else -> {
                    LazyColumn(
                        modifier = Modifier.fillMaxSize(),
                        contentPadding = androidx.compose.foundation.layout.PaddingValues(
                            horizontal = 16.dp, vertical = 4.dp
                        ),
                        verticalArrangement = Arrangement.spacedBy(10.dp)
                    ) {
                        items(uiState.records, key = { it.id }) { record ->
                            StocktakeRecordCard(record)
                        }
                        if (uiState.hasMore) {
                            item {
                                Box(
                                    Modifier
                                        .fillMaxWidth()
                                        .padding(vertical = 12.dp),
                                    contentAlignment = Alignment.Center
                                ) {
                                    if (uiState.isLoading) {
                                        CircularProgressIndicator(
                                            modifier = Modifier.size(22.dp),
                                            color = Primary
                                        )
                                    } else {
                                        TextButton(onClick = { viewModel.loadMore() }) {
                                            Text("加载更多（共 ${uiState.totalPages} 页）")
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun StocktakeRecordCard(record: StocktakeRecordDto) {
    val isVoid = record.status == "void"
    val accent = if (isVoid) CardAmber else CardTeal
    val diff = record.diffCount ?: 0
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surface
        ),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
    ) {
        Column(Modifier.padding(14.dp)) {
            // 单号 + 状态标签
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    record.checkNo ?: "—",
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.Bold,
                    color = OnSurface,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.weight(1f)
                )
                Spacer(Modifier.width(8.dp))
                StatusTag(
                    text = if (isVoid) "已作废" else "已完成",
                    color = if (isVoid) CardAmber else CardTeal
                )
            }

            Spacer(Modifier.height(8.dp))

            // 日期 / 仓库
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    record.date ?: "",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                if (!record.warehouse.isNullOrBlank()) {
                    Spacer(Modifier.width(10.dp))
                    Icon(
                        Icons.Filled.Info,
                        contentDescription = null,
                        modifier = Modifier.size(13.dp),
                        tint = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Spacer(Modifier.width(3.dp))
                    Text(
                        record.warehouse,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                }
            }

            Spacer(Modifier.height(8.dp))

            // 盘点条数 / 差异条数 / 批次
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    "盘点 ${record.itemCount ?: 0} 条",
                    style = MaterialTheme.typography.bodySmall,
                    color = OnSurface
                )
                Spacer(Modifier.width(12.dp))
                Text(
                    "差异 ${diff} 条",
                    style = MaterialTheme.typography.bodySmall,
                    fontWeight = if (diff > 0) FontWeight.SemiBold else FontWeight.Normal,
                    color = if (diff > 0) CardAmber else MaterialTheme.colorScheme.onSurfaceVariant
                )
                if (!record.batchNo.isNullOrBlank()) {
                    Spacer(Modifier.width(12.dp))
                    Text(
                        "批次 ${record.batchNo}",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                }
            }

            // 采纳状态：批次是否完成 + 调整草稿审核结果
            if (!isVoid) {
                Spacer(Modifier.height(8.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        if (record.adjustmentStatus == "completed") {
                            Icons.Filled.CheckCircle
                        } else {
                            Icons.Filled.Info
                        },
                        contentDescription = null,
                        modifier = Modifier.size(14.dp),
                        tint = when (record.adjustmentStatus) {
                            "completed" -> CardTeal
                            "pending" -> CardAmber
                            else -> CardCyan
                        }
                    )
                    Spacer(Modifier.width(4.dp))
                    Text(
                        adoptionText(record),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }

            if (!record.createdAt.isNullOrBlank()) {
                Spacer(Modifier.height(4.dp))
                Text(
                    "提交时间 ${record.createdAt}",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
}

/** 采纳状态文案：把后端三个状态位翻译成作业员能看懂的一句话。 */
private fun adoptionText(record: StocktakeRecordDto): String = when {
    record.adjustmentStatus == "completed" -> "差异已审核，库存已调整"
    record.adjustmentStatus == "pending" -> "差异已生成调整草稿，等待审核"
    record.batchStatus == "pending" -> "已并入盘点批次，等待电脑端完成盘点"
    else -> "无差异，无需调整"
}

@Composable
private fun StatusTag(text: String, color: Color) {
    Box(
        modifier = Modifier
            .clip(RoundedCornerShape(6.dp))
            .background(color.copy(alpha = 0.12f))
            .padding(horizontal = 8.dp, vertical = 2.dp)
    ) {
        Text(
            text,
            style = MaterialTheme.typography.labelSmall,
            fontWeight = FontWeight.SemiBold,
            color = color
        )
    }
}
