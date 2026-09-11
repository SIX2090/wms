package com.factory.wms.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.outlined.HelpOutline
import androidx.compose.material.icons.outlined.Inventory2
import androidx.compose.material.icons.outlined.SearchOff
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.factory.wms.data.model.VoiceMaterialMatch
import com.factory.wms.ui.viewmodel.voice.VoiceDraftStage
import com.factory.wms.ui.viewmodel.voice.VoiceOutDraftUiState
import com.factory.wms.ui.theme.*
import com.factory.wms.util.formatQuantity

/**
 * AI-VOICE-OUT-F01：语音建单结果对话框（唯一入口）。
 *
 * 按 [VoiceOutDraftUiState.stage] 切换四种形态，全部走同一个 AlertDialog，
 * 避免多个 dialog 同时存在互相抢占焦点：
 *
 * - [VoiceDraftStage.PARSING]     解析中（转圈 + 显示"我听到的是…"）
 * - [VoiceDraftStage.NEED_CHOICE] 多命中 → 列表点选（R5：不替用户决定）
 * - [VoiceDraftStage.CONFIRMING]  已定物料 → 核对数量/领料人后建单
 * - [VoiceDraftStage.NOT_FOUND]   没找到 → 展示"听成了什么 + 试过什么 + 最接近候选"
 *
 * 设计原则（"聪明的 AI"）：任何失败都必须把 AI 的理解过程摊给用户看，
 * 不允许只说一句"没听懂"就把用户打发了。所以 NOT_FOUND 态也照样渲染
 * 归一化文本、试过的策略和候选列表。
 */
@Composable
fun VoiceOutDraftDialog(
    state: VoiceOutDraftUiState,
    onChooseMaterial: (VoiceMaterialMatch) -> Unit,
    onQuantityChange: (String) -> Unit,
    onPickerChange: (String) -> Unit,
    onConfirm: () -> Unit,
    onBackToChoice: () -> Unit,
    onDismiss: () -> Unit,
    onRetry: () -> Unit
) {
    // CREATED 由 NavGraph 的 LaunchedEffect 负责跳转，这里不做渲染（避免跳到一半还挂着弹窗）
    if (state.stage == VoiceDraftStage.IDLE || state.stage == VoiceDraftStage.CREATED) return

    AlertDialog(
        onDismissRequest = onDismiss,
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(20.dp),
        title = {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    when (state.stage) {
                        VoiceDraftStage.PARSING -> "正在识别"
                        VoiceDraftStage.NEED_CHOICE -> "请选择物料"
                        VoiceDraftStage.CONFIRMING, VoiceDraftStage.CREATING -> "确认领料单"
                        else -> "没找到匹配物料"
                    },
                    fontWeight = FontWeight.SemiBold
                )
                Spacer(Modifier.width(8.dp))
                // 降级提示：告诉用户这不是精确匹配，别盲信
                if (state.degraded && state.stage != VoiceDraftStage.PARSING) {
                    DegradedBadge()
                }
            }
        },
        text = {
            Column {
                HeardCard(state)
                Spacer(Modifier.height(12.dp))
                when (state.stage) {
                    VoiceDraftStage.PARSING -> ParsingBody()
                    VoiceDraftStage.NEED_CHOICE -> ChoiceBody(state, onChooseMaterial)
                    VoiceDraftStage.CONFIRMING, VoiceDraftStage.CREATING ->
                        ConfirmBody(state, onQuantityChange, onPickerChange, onBackToChoice)
                    else -> NotFoundBody(state, onChooseMaterial)
                }
                state.error?.takeIf { it.isNotBlank() }?.let { err ->
                    Spacer(Modifier.height(10.dp))
                    Text(err, color = Error, fontSize = 13.sp)
                }
            }
        },
        confirmButton = {
            when (state.stage) {
                VoiceDraftStage.PARSING -> TextButton(onClick = onDismiss) { Text("取消") }
                VoiceDraftStage.NEED_CHOICE -> TextButton(onClick = onDismiss) { Text("取消") }
                VoiceDraftStage.CONFIRMING, VoiceDraftStage.CREATING -> Button(
                    onClick = onConfirm,
                    enabled = !state.loading,
                    shape = RoundedCornerShape(12.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = CardGreen)
                ) {
                    if (state.loading) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(16.dp),
                            color = Color.White,
                            strokeWidth = 2.dp
                        )
                        Spacer(Modifier.width(8.dp))
                    }
                    Text("生成草稿")
                }
                else -> TextButton(onClick = onRetry) {
                    Text("重新说一次", color = PrimaryDark, fontWeight = FontWeight.SemiBold)
                }
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("关闭") }
        }
    )
}

/** 「我听到的是… / 我理解成…」——把 AI 的理解摊开给用户核对，而不是黑盒。 */
@Composable
private fun HeardCard(state: VoiceOutDraftUiState) {
    Surface(
        color = SurfaceVariant,
        shape = RoundedCornerShape(12.dp),
        modifier = Modifier.fillMaxWidth()
    ) {
        Column(modifier = Modifier.padding(horizontal = 12.dp, vertical = 10.dp)) {
            if (state.heardText.isNotBlank()) {
                Text("我听到：${state.heardText}", fontSize = 13.sp, color = OnSurface)
            }
            if (state.normalizedText.isNotBlank() && state.normalizedText != state.heardText) {
                Spacer(Modifier.height(4.dp))
                Text(
                    "我理解成：${state.normalizedText}",
                    fontSize = 12.sp,
                    color = OnSurfaceVariant
                )
            }
            val parsedBits = buildList {
                if (state.keyword.isNotBlank()) add("物料「${state.keyword}」")
                if (state.spec.isNotBlank()) add("规格「${state.spec}」")
                state.quantity?.let { add("数量 ${formatQuantity(it)}${state.unit}") }
            }
            if (parsedBits.isNotEmpty()) {
                Spacer(Modifier.height(4.dp))
                Text(
                    "解析出：${parsedBits.joinToString("，")}",
                    fontSize = 12.sp,
                    color = OnSurfaceVariant,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis
                )
            }
        }
    }
}

@Composable
private fun DegradedBadge() {
    Surface(color = CardAmber.copy(alpha = 0.14f), shape = RoundedCornerShape(6.dp)) {
        Text(
            "模糊匹配",
            fontSize = 11.sp,
            color = CardAmberDark,
            modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp)
        )
    }
}

@Composable
private fun ParsingBody() {
    Row(verticalAlignment = Alignment.CenterVertically) {
        CircularProgressIndicator(modifier = Modifier.size(18.dp), strokeWidth = 2.dp)
        Spacer(Modifier.width(10.dp))
        Text("正在仓库里找这个物料…", fontSize = 13.sp, color = OnSurfaceVariant)
    }
}

/** 多命中：列出候选让用户点选。每行展示「编码 · 名称 · 规格」，右侧是相似度。 */
@Composable
private fun ChoiceBody(
    state: VoiceOutDraftUiState,
    onChooseMaterial: (VoiceMaterialMatch) -> Unit
) {
    Column {
        StrategiesLine(state)
        if (state.matches.isEmpty()) {
            EmptyCandidates()
        } else {
            Text(
                "仓库里有 ${state.matches.size} 个相近物料，请点选正确的：",
                fontSize = 13.sp,
                color = OnSurfaceVariant
            )
            Spacer(Modifier.height(8.dp))
            // 候选最多 10 个，固定高度避免弹窗被撑爆
            LazyColumn(
                modifier = Modifier.heightIn(max = 280.dp),
                verticalArrangement = Arrangement.spacedBy(4.dp)
            ) {
                itemsIndexed(state.matches) { _, match ->
                    MaterialMatchRow(match, onClick = { onChooseMaterial(match) })
                }
            }
        }
    }
}

/** 唯一命中/已点选：核对物料 + 数量（语音没说数量时人工填）+ 领料人（手工输入）。 */
@Composable
private fun ConfirmBody(
    state: VoiceOutDraftUiState,
    onQuantityChange: (String) -> Unit,
    onPickerChange: (String) -> Unit,
    onBackToChoice: () -> Unit
) {
    val material = state.selected
    Column {
        if (material != null) {
            Surface(
                color = CardGreen.copy(alpha = 0.08f),
                shape = RoundedCornerShape(12.dp),
                modifier = Modifier.fillMaxWidth()
            ) {
                Row(
                    modifier = Modifier.padding(12.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Icon(
                        Icons.Filled.CheckCircle, null,
                        tint = CardGreen, modifier = Modifier.size(20.dp)
                    )
                    Spacer(Modifier.width(10.dp))
                    Column(modifier = Modifier.weight(1f)) {
                        Text(
                            material.name.orEmpty().ifBlank { material.code.orEmpty() },
                            fontWeight = FontWeight.SemiBold,
                            fontSize = 15.sp,
                            color = OnSurface
                        )
                        Text(
                            listOfNotNull(
                                material.code?.takeIf { it.isNotBlank() },
                                material.spec?.takeIf { it.isNotBlank() }
                            ).joinToString("  ·  "),
                            fontSize = 12.sp,
                            color = OnSurfaceVariant
                        )
                    }
                }
            }
            // 只有多候选时才允许"选错了，回去重选"
            if (state.matches.size > 1) {
                Spacer(Modifier.height(4.dp))
                TextButton(
                    onClick = onBackToChoice,
                    contentPadding = PaddingValues(0.dp)
                ) {
                    Text("不是这个，重新选", fontSize = 12.sp, color = PrimaryDark)
                }
            }
        }

        Spacer(Modifier.height(12.dp))

        OutlinedTextField(
            value = state.editableQuantity,
            onValueChange = onQuantityChange,
            label = { Text("领料数量${if (state.unit.isNotBlank()) "（${state.unit}）" else ""}") },
            singleLine = true,
            isError = state.editableQuantity.isNotBlank() &&
                (state.editableQuantity.toDoubleOrNull() ?: 0.0) <= 0,
            supportingText = if (state.quantity == null) {
                { Text("语音里没说数量，请手工填写", fontSize = 11.sp) }
            } else null,
            keyboardOptions = KeyboardOptions(
                keyboardType = KeyboardType.Decimal,
                imeAction = ImeAction.Next
            ),
            modifier = Modifier.fillMaxWidth()
        )

        Spacer(Modifier.height(8.dp))

        OutlinedTextField(
            value = state.pickerInput,
            onValueChange = onPickerChange,
            label = { Text("领料人") },
            singleLine = true,
            keyboardOptions = KeyboardOptions(imeAction = ImeAction.Done),
            modifier = Modifier.fillMaxWidth()
        )

        Spacer(Modifier.height(10.dp))
        Text(
            "将生成【领料单草稿】（待你确认），不会自动扣库存；" +
                "提交与完成仍需你本人在出库页操作。",
            fontSize = 11.sp,
            color = OnSurfaceVariant
        )
        StrategiesLine(state)
    }
}

/** 零命中：不退化成"没听懂"，而是把 AI 的努力摊开 + 给出最接近的候选供人工兜底。 */
@Composable
private fun NotFoundBody(
    state: VoiceOutDraftUiState,
    onChooseMaterial: (VoiceMaterialMatch) -> Unit
) {
    Column {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(
                Icons.Outlined.SearchOff, null,
                tint = OnSurfaceVariant, modifier = Modifier.size(18.dp)
            )
            Spacer(Modifier.width(8.dp))
            Text(
                "仓库里没有完全对得上的物料",
                fontSize = 13.sp,
                color = OnSurfaceVariant
            )
        }
        StrategiesLine(state)
        if (state.matches.isNotEmpty()) {
            Spacer(Modifier.height(8.dp))
            Text(
                "下面是我找到的最接近的 ${state.matches.size} 个，若其中有你要的，可直接点选：",
                fontSize = 13.sp,
                color = OnSurface)
            Spacer(Modifier.height(8.dp))
            LazyColumn(
                modifier = Modifier.heightIn(max = 260.dp),
                verticalArrangement = Arrangement.spacedBy(4.dp)
            ) {
                itemsIndexed(state.matches) { _, match ->
                    MaterialMatchRow(match, onClick = { onChooseMaterial(match) })
                }
            }
        } else {
            Spacer(Modifier.height(8.dp))
            Text(
                "建议：换一种说法（如只说物料名「螺丝」），或先在电脑端补建该物料档案。",
                fontSize = 12.sp,
                color = OnSurfaceVariant
            )
        }
    }
}

/** 「我试过：别名 → 编码 → 模糊 → 词根」——把降级路径摊开，用户才知道 AI 到底做了什么。 */
@Composable
private fun StrategiesLine(state: VoiceOutDraftUiState) {
    if (state.strategiesTried.isEmpty()) return
    Spacer(Modifier.height(8.dp))
    Row(verticalAlignment = Alignment.CenterVertically) {
        Icon(
            Icons.Outlined.HelpOutline, null,
            tint = OnSurfaceSecondary, modifier = Modifier.size(13.dp)
        )
        Spacer(Modifier.width(4.dp))
        Text(
            "已尝试：${state.strategiesTried.joinToString(" → ")}",
            fontSize = 11.sp,
            color = OnSurfaceSecondary,
            maxLines = 2,
            overflow = TextOverflow.Ellipsis
        )
    }
}

@Composable
private fun EmptyCandidates() {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Icon(
            Icons.Outlined.Inventory2, null,
            tint = OnSurfaceVariant, modifier = Modifier.size(18.dp)
        )
        Spacer(Modifier.width(8.dp))
        Text("没有候选物料", fontSize = 13.sp, color = OnSurfaceVariant)
    }
}

/**
 * 候选物料行：左侧编码/名称/规格三行信息，右侧相似度百分比。
 * 相似度只在 <100 时显示（100 表示精确命中，显示出来反而噪音）。
 */
@Composable
private fun MaterialMatchRow(
    match: VoiceMaterialMatch,
    onClick: () -> Unit
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(12.dp))
            .background(SurfaceVariant)
            .clickable(onClick = onClick)
            .padding(horizontal = 12.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Box(
            modifier = Modifier
                .size(34.dp)
                .clip(RoundedCornerShape(10.dp))
                .background(CardGreen.copy(alpha = 0.12f)),
            contentAlignment = Alignment.Center
        ) {
            Icon(
                Icons.Outlined.Inventory2, null,
                tint = CardGreen, modifier = Modifier.size(18.dp)
            )
        }
        Spacer(Modifier.width(10.dp))
        Column(modifier = Modifier.weight(1f)) {
            Text(
                match.name.orEmpty().ifBlank { match.code.orEmpty() },
                fontSize = 14.sp,
                fontWeight = FontWeight.SemiBold,
                color = OnSurface,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis
            )
            Text(
                listOfNotNull(
                    match.code?.takeIf { it.isNotBlank() },
                    match.spec?.takeIf { it.isNotBlank() },
                    match.unit?.takeIf { it.isNotBlank() }
                ).joinToString("  ·  "),
                fontSize = 12.sp,
                color = OnSurfaceVariant,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis
            )
        }
        match.score?.takeIf { it < 100 }?.let { score ->
            Spacer(Modifier.width(8.dp))
            Text("$score%", fontSize = 12.sp, color = OnSurfaceSecondary)
        }
    }
}

/**
 * 建单成功后的"已生成草稿"提示条。
 *
 * 与 [VoiceOutDraftDialog] 分开：跳转到出库页后弹窗必须消失，
 * 这张提示条挂在出库页顶部，让用户知道草稿单号、并确认还需人工提交。
 */
@Composable
fun VoiceDraftCreatedBanner(
    orderNo: String,
    onDismiss: () -> Unit
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 8.dp),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = CardGreen.copy(alpha = 0.08f)),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp)
    ) {
        Row(
            modifier = Modifier.padding(14.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(
                Icons.Filled.CheckCircle, null,
                tint = CardGreen, modifier = Modifier.size(20.dp)
            )
            Spacer(Modifier.width(10.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    "语音草稿已生成",
                    fontWeight = FontWeight.SemiBold,
                    fontSize = 14.sp,
                    color = OnSurface
                )
                if (orderNo.isNotBlank()) {
                    Text("单号：$orderNo", fontSize = 12.sp, color = OnSurfaceVariant)
                }
                Text(
                    "核对无误后请手工提交，草稿不会自动扣库存。",
                    fontSize = 11.sp,
                    color = OnSurfaceVariant
                )
            }
            TextButton(onClick = onDismiss) { Text("知道了", fontSize = 12.sp) }
        }
    }
}
