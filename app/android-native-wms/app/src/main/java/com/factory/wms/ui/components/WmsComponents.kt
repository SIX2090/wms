package com.factory.wms.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.outlined.CloudOff
import androidx.compose.material.icons.outlined.CloudSync
import androidx.compose.material.icons.outlined.ErrorOutline
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.factory.wms.ui.theme.Background
import com.factory.wms.ui.theme.CardBackground
import com.factory.wms.ui.theme.DividerSoft
import com.factory.wms.ui.theme.Error
import com.factory.wms.ui.theme.ErrorContainer
import com.factory.wms.ui.theme.OnSurface
import com.factory.wms.ui.theme.OnSurfaceSecondary
import com.factory.wms.ui.theme.OnSurfaceVariant
import com.factory.wms.ui.theme.Primary
import com.factory.wms.ui.theme.PrimaryContainer
import com.factory.wms.ui.theme.SurfaceVariant
import com.factory.wms.ui.theme.Warning
import com.factory.wms.ui.theme.WarningContainer

// ─────────────────────────────────────────────────────────────────────────────
// WMS 移动端共享设计组件（AI-APP-UI-001）
// 统一全 App 的顶栏 / 卡片 / 空态 / 按钮 / 徽标 / 分组标题视觉语言，
// 让各业务界面保持一致的精致感：柔和阴影、18-20dp 圆角、模块色渐变头部。
// ─────────────────────────────────────────────────────────────────────────────

/** 把颜色按比例调暗（保持透明度），用于生成模块色渐变的结束色。 */
fun Color.darken(factor: Float = 0.72f): Color =
    Color(red * factor, green * factor, blue * factor, alpha)

/** 把颜色按比例调亮（向白色靠拢）。 */
fun Color.lighten(factor: Float = 0.25f): Color =
    Color(
        red + (1f - red) * factor,
        green + (1f - green) * factor,
        blue + (1f - blue) * factor,
        alpha
    )

/**
 * 统一白色顶栏：圆形返回按钮 + 粗体标题 + 灰色副标题 + 底部分隔线。
 * 替代各屏重复书写的 TopAppBar 模板代码。
 */
@Composable
fun WmsTopBar(
    title: String,
    subtitle: String? = null,
    onBack: (() -> Unit)? = null,
    actions: @Composable RowScope.() -> Unit = {}
) {
    Surface(
        color = MaterialTheme.colorScheme.surface,
        shadowElevation = 2.dp
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .statusBarsPadding()
                .heightIn(min = 64.dp)
                .padding(horizontal = 8.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            if (onBack != null) {
                IconButton(onClick = onBack) {
                    Icon(
                        Icons.AutoMirrored.Filled.ArrowBack,
                        contentDescription = "返回",
                        tint = MaterialTheme.colorScheme.onSurface
                    )
                }
            } else {
                Spacer(modifier = Modifier.width(12.dp))
            }
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    title,
                    fontWeight = FontWeight.Bold,
                    fontSize = 20.sp,
                    color = MaterialTheme.colorScheme.onSurface,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
                if (!subtitle.isNullOrBlank()) {
                    Text(
                        subtitle,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                }
            }
            actions()
        }
    }
}

/**
 * 模块色渐变头部：accent → accent.darken() 斜向渐变 + 装饰圆 + 白色标题。
 * 用于扫码/AI 等作业屏，让每个模块有自己的色彩识别度。
 */
@Composable
fun WmsGradientHeader(
    title: String,
    subtitle: String?,
    accent: Color,
    onBack: (() -> Unit)? = null,
    trailing: (@Composable () -> Unit)? = null
) {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .background(
                brush = Brush.linearGradient(
                    colors = listOf(accent.lighten(0.08f), accent.darken(0.74f))
                )
            )
    ) {
        // 装饰圆
        Box(
            modifier = Modifier
                .size(140.dp)
                .offset(x = (-50).dp, y = (-60).dp)
                .clip(CircleShape)
                .background(Color.White.copy(alpha = 0.05f))
        )
        Box(
            modifier = Modifier
                .size(90.dp)
                .align(Alignment.TopEnd)
                .offset(x = 30.dp, y = (-24).dp)
                .clip(CircleShape)
                .background(Color.White.copy(alpha = 0.07f))
        )
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .statusBarsPadding()
                .padding(horizontal = 8.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            if (onBack != null) {
                IconButton(onClick = onBack) {
                    Box(
                        modifier = Modifier
                            .size(36.dp)
                            .clip(CircleShape)
                            .background(Color.White.copy(alpha = 0.16f)),
                        contentAlignment = Alignment.Center
                    ) {
                        Icon(
                            Icons.AutoMirrored.Filled.ArrowBack,
                            contentDescription = "返回",
                            tint = Color.White,
                            modifier = Modifier.size(20.dp)
                        )
                    }
                }
            } else {
                Spacer(modifier = Modifier.width(16.dp))
            }
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    title,
                    color = Color.White,
                    fontWeight = FontWeight.Bold,
                    fontSize = 20.sp,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
                if (!subtitle.isNullOrBlank()) {
                    Spacer(modifier = Modifier.height(1.dp))
                    Text(
                        subtitle,
                        color = Color.White.copy(alpha = 0.75f),
                        fontSize = 12.sp,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                }
            }
            trailing?.invoke()
            Spacer(modifier = Modifier.width(8.dp))
        }
    }
}

/** 统一白色圆角卡片：18dp 圆角 + 柔和阴影。 */
@Composable
fun WmsCard(
    modifier: Modifier = Modifier,
    onClick: (() -> Unit)? = null,
    corner: Dp = 18.dp,
    containerColor: Color = CardBackground,
    contentPadding: PaddingValues = PaddingValues(16.dp),
    content: @Composable ColumnScope.() -> Unit
) {
    val shape = RoundedCornerShape(corner)
    val clickModifier = if (onClick != null) {
        // 简单 clickable 重载自带默认波纹 indication，兼容性最好
        Modifier.clickable(onClick = onClick)
    } else {
        Modifier
    }
    Card(
        modifier = modifier
            .shadow(
                elevation = 3.dp,
                shape = shape,
                ambientColor = OnSurface.copy(alpha = 0.06f),
                spotColor = OnSurface.copy(alpha = 0.08f)
            )
            .then(clickModifier),
        shape = shape,
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
        colors = CardDefaults.cardColors(containerColor = containerColor)
    ) {
        Column(modifier = Modifier.padding(contentPadding)) {
            content()
        }
    }
}

/** 统一空态：双层淡色圆环图标 + 标题 + 副标题。 */
@Composable
fun WmsEmptyState(
    icon: ImageVector,
    title: String,
    subtitle: String,
    modifier: Modifier = Modifier,
    accentColor: Color = Primary
) {
    Column(
        modifier = modifier.padding(32.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Box(
            modifier = Modifier
                .size(96.dp)
                .clip(CircleShape)
                .background(accentColor.copy(alpha = 0.05f)),
            contentAlignment = Alignment.Center
        ) {
            Box(
                modifier = Modifier
                    .size(72.dp)
                    .clip(CircleShape)
                    .background(accentColor.copy(alpha = 0.08f)),
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    icon,
                    contentDescription = null,
                    modifier = Modifier.size(34.dp),
                    tint = accentColor.copy(alpha = 0.55f)
                )
            }
        }
        Spacer(modifier = Modifier.height(16.dp))
        Text(
            title,
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.SemiBold,
            color = OnSurface
        )
        Spacer(modifier = Modifier.height(4.dp))
        Text(
            subtitle,
            style = MaterialTheme.typography.bodySmall,
            color = OnSurfaceVariant
        )
    }
}

/** 统一主按钮：50dp 高、14dp 圆角、模块色、支持加载态。 */
@Composable
fun WmsPrimaryButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    icon: ImageVector? = null,
    color: Color = Primary,
    loading: Boolean = false,
    enabled: Boolean = true
) {
    Button(
        onClick = onClick,
        modifier = modifier.height(50.dp),
        enabled = enabled && !loading,
        shape = RoundedCornerShape(14.dp),
        colors = ButtonDefaults.buttonColors(
            containerColor = color,
            disabledContainerColor = color.copy(alpha = 0.35f)
        ),
        elevation = ButtonDefaults.buttonElevation(
            defaultElevation = 3.dp,
            pressedElevation = 6.dp
        )
    ) {
        if (loading) {
            CircularProgressIndicator(
                modifier = Modifier.size(20.dp),
                color = Color.White,
                strokeWidth = 2.dp
            )
            Spacer(modifier = Modifier.width(8.dp))
        } else if (icon != null) {
            Icon(icon, contentDescription = null, modifier = Modifier.size(19.dp))
            Spacer(modifier = Modifier.width(7.dp))
        }
        Text(text, fontSize = 15.sp, fontWeight = FontWeight.SemiBold)
    }
}

/** 统一次要（描边）按钮：46dp 高、12dp 圆角、模块色描边。 */
@Composable
fun WmsOutlinedActionButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    icon: ImageVector? = null,
    color: Color = Primary,
    enabled: Boolean = true
) {
    OutlinedButton(
        onClick = onClick,
        modifier = modifier.height(46.dp),
        enabled = enabled,
        shape = RoundedCornerShape(12.dp),
        colors = ButtonDefaults.outlinedButtonColors(contentColor = color),
        border = ButtonDefaults.outlinedButtonBorder.copy(
            brush = androidx.compose.ui.graphics.SolidColor(color.copy(alpha = 0.35f))
        )
    ) {
        if (icon != null) {
            Icon(icon, contentDescription = null, modifier = Modifier.size(18.dp), tint = color)
            Spacer(modifier = Modifier.width(6.dp))
        }
        Text(text, color = color, fontWeight = FontWeight.Medium, fontSize = 14.sp)
    }
}

/** 统一胶囊徽标：图标 + 文本，活跃态模块色 / 非活跃态灰色。 */
@Composable
fun WmsPillBadge(
    text: String,
    icon: ImageVector? = null,
    activeColor: Color = Primary,
    active: Boolean = true
) {
    Surface(
        shape = RoundedCornerShape(20.dp),
        color = if (active) activeColor.copy(alpha = 0.12f) else SurfaceVariant
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 10.dp, vertical = 4.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            if (icon != null) {
                Icon(
                    icon,
                    contentDescription = null,
                    tint = if (active) activeColor else OnSurfaceVariant,
                    modifier = Modifier.size(14.dp)
                )
                Spacer(modifier = Modifier.width(4.dp))
            }
            Text(
                text,
                fontSize = 12.sp,
                fontWeight = FontWeight.SemiBold,
                color = if (active) activeColor else OnSurfaceVariant
            )
        }
    }
}

/** 统一分组标题：小色块图标 + 粗体标题 + 可选尾部操作。 */
@Composable
fun WmsSectionHeader(
    title: String,
    icon: ImageVector? = null,
    iconTint: Color = Primary,
    trailing: (@Composable () -> Unit)? = null
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically
    ) {
        if (icon != null) {
            Box(
                modifier = Modifier
                    .size(28.dp)
                    .clip(RoundedCornerShape(8.dp))
                    .background(iconTint.copy(alpha = 0.12f)),
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    icon,
                    contentDescription = null,
                    tint = iconTint,
                    modifier = Modifier.size(16.dp)
                )
            }
            Spacer(modifier = Modifier.width(8.dp))
        }
        Text(
            title,
            style = MaterialTheme.typography.titleSmall,
            fontWeight = FontWeight.SemiBold,
            color = OnSurface,
            modifier = Modifier.weight(1f)
        )
        trailing?.invoke()
    }
}

/** 统一信息格：上标签下数值，用于库存/档案等信息网格。 */
@Composable
fun WmsInfoCell(
    label: String,
    value: String,
    modifier: Modifier = Modifier,
    valueColor: Color = OnSurface
) {
    Column(
        modifier = modifier,
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Text(
            label,
            style = MaterialTheme.typography.labelSmall,
            color = OnSurfaceVariant
        )
        Spacer(modifier = Modifier.height(3.dp))
        Text(
            value,
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.Bold,
            color = valueColor,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis
        )
    }
}

/** 统一柔和分隔线。 */
@Composable
fun WmsDivider(modifier: Modifier = Modifier) {
    HorizontalDivider(
        modifier = modifier,
        color = DividerSoft,
        thickness = 1.dp
    )
}

/** 统一页面背景 Scaffold 容器色，避免各处散落引用。 */
val WmsPageBackground: Color get() = Background

/** 统一浅色调色板（图标底色），Active 时 PrimaryContainer。 */
val WmsIconWellColor: Color get() = PrimaryContainer

/** 辅助：弱化文本颜色（提示/次要说明）。 */
val WmsHintColor: Color get() = OnSurfaceSecondary

/**
 * 离线（缓存回退）数据提示横幅（AI-MOB-OFFLINE-HINT-01）。
 *
 * 使用场景：`WmsRepository.getMaterialInfo` 在网络失败时回退到 Room 本地缓存，
 * 返回的 `MaterialDto.fromCache == true`。此时界面上的库存数字**不是实时的**。
 *
 * 为什么必须显示：不给任何提示的话，用户无法区分
 * 「实时库存 5」和「三天前缓存的 5」，看到数字就出库 5 ——
 * 这是**业务风险**（超发/账面为负），不是单纯的体验问题。
 *
 * @param cachedAtMillis 缓存写入时间（epoch millis），为 null 时只提示"离线"不显示时长
 */
@Composable
fun OfflineDataBanner(
    cachedAtMillis: Long?,
    modifier: Modifier = Modifier,
    text: String = "离线数据"
) {
    val detail = remember(cachedAtMillis) { formatCacheAge(cachedAtMillis) }
    Row(
        modifier = modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(10.dp))
            .background(WarningContainer)
            .padding(horizontal = 12.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Icon(
            Icons.Outlined.CloudOff,
            null,
            tint = Warning,
            modifier = Modifier.size(16.dp)
        )
        Spacer(modifier = Modifier.width(8.dp))
        Column(modifier = Modifier.weight(1f)) {
            Text(
                if (detail.isNullOrEmpty()) text else "$text · $detail",
                color = Warning,
                fontSize = 12.sp,
                fontWeight = FontWeight.SemiBold
            )
            Text(
                "当前无网络，显示的是本地缓存，可能不是最新库存",
                color = Warning.copy(alpha = 0.85f),
                fontSize = 11.sp
            )
        }
    }
}

/**
 * 把缓存时间戳转成"多久之前"的中文描述。
 *
 * 精度只给到分钟/小时/天 —— 现场用户关心的是"这个数还新不新"，
 * 不需要精确到秒（反而增加阅读负担）。
 */
internal fun formatCacheAge(cachedAtMillis: Long?): String? {
    if (cachedAtMillis == null || cachedAtMillis <= 0L) return null
    val deltaMs = System.currentTimeMillis() - cachedAtMillis
    // 时钟回拨或未来时间戳：不显示负数时长，退化成"刚刚"
    if (deltaMs < 0) return "刚刚"
    val minutes = deltaMs / 60_000L
    return when {
        minutes < 1L -> "刚刚"
        minutes < 60L -> "$minutes 分钟前"
        minutes < 60L * 24L -> "${minutes / 60L} 小时前"
        else -> "${minutes / (60L * 24L)} 天前"
    }
}

/**
 * AI-MOB-OFFLINE-01：待同步作业横幅。
 *
 * 使用场景：断网提交时数据已暂存本地队列（[com.factory.wms.data.repository.OfflineQueueManager]），
 * 联网后自动补传。此横幅让作业员**明确知道数据没有丢**，可以放心离开继续下一单。
 *
 * ## 为什么必须区分「待同步」与「失败」（关键）
 *
 * 两者混用一个提示是危险的：
 * - 「待同步」= 数据安全，只是还没传上去 → 用户可以走开，不用重做
 * - 「失败」  = 重试已耗尽，需要人工介入 → 用户必须重做或找管理员
 *
 * 若把"待同步"显示成"提交失败"，用户会**重扫一遍**，反而制造重复单据。
 * 故 [failedCount] > 0 时文案与配色都升级为警示态，并提供人工重试入口。
 *
 * @param pendingCount 待自动补传条数
 * @param failedCount 重试耗尽、需人工处理的条数
 * @param onRetry 人工触发重试（重试全部失败记录并立即尝试补传）
 */
@Composable
fun PendingSyncBanner(
    pendingCount: Int,
    failedCount: Int,
    onRetry: () -> Unit,
    modifier: Modifier = Modifier
) {
    if (pendingCount <= 0 && failedCount <= 0) return

    val isFailed = failedCount > 0
    val container = if (isFailed) ErrorContainer else WarningContainer
    val accent = if (isFailed) Error else Warning

    Row(
        modifier = modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(10.dp))
            .background(container)
            .padding(horizontal = 12.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Icon(
            if (isFailed) Icons.Outlined.ErrorOutline else Icons.Outlined.CloudSync,
            null,
            tint = accent,
            modifier = Modifier.size(16.dp)
        )
        Spacer(modifier = Modifier.width(8.dp))
        Column(modifier = Modifier.weight(1f)) {
            Text(
                if (isFailed) "$failedCount 条同步失败" else "$pendingCount 条待同步",
                color = accent,
                fontSize = 12.sp,
                fontWeight = FontWeight.SemiBold
            )
            Text(
                if (isFailed) {
                    "已重试多次仍失败，请检查网络后点「重试」，或联系管理员"
                } else {
                    "数据已保存，联网后自动提交，无需重做"
                },
                color = accent.copy(alpha = 0.85f),
                fontSize = 11.sp
            )
        }
        if (isFailed) {
            Spacer(modifier = Modifier.width(8.dp))
            Text(
                "重试",
                color = accent,
                fontSize = 12.sp,
                fontWeight = FontWeight.Bold,
                modifier = Modifier
                    .clip(RoundedCornerShape(8.dp))
                    .clickable { onRetry() }
                    .padding(horizontal = 10.dp, vertical = 4.dp)
            )
        }
    }
}

