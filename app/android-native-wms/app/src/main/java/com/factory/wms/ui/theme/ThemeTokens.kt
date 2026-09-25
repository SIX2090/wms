package com.factory.wms.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.ReadOnlyComposable
import androidx.compose.ui.graphics.Color

/**
 * AI-APP-FIX-301 / FIX-303：颜色令牌 → colorScheme / 语义色扩展的单点映射。
 *
 * 页面继续引用同名令牌（Background、CardBackground、OnSurface、Success……），
 * 无需逐处修改约 250 个调用点；亮/暗取值在此处一次生效：
 *  - 亮色模式下取值与原硬编码完全一致（视觉零变化）；
 *  - 暗色模式下自动落到 DarkColorScheme / DarkSemanticColors。
 *
 * 合理例外（保留原常量，不在此映射）：模块渐变 accent（CardBlue/Green/…）、
 * 彩色底上的 Color.White / OnPrimary、品牌渐变（Primary→PrimaryDark）、
 * 相机取景框/图片预览上的固定色。
 */

/** 页面背景 → colorScheme.background（亮 F3F4F6 / 暗 0F0F11）。 */
val Background: Color
    @Composable
    @ReadOnlyComposable
    get() = MaterialTheme.colorScheme.background

/** 卡片/顶栏容器底 → colorScheme.surface（亮 White / 暗 18181B）。 */
val CardBackground: Color
    @Composable
    @ReadOnlyComposable
    get() = MaterialTheme.colorScheme.surface

/** 主文本 → colorScheme.onSurface（亮 111827 / 暗 F4F4F5）。 */
val OnSurface: Color
    @Composable
    @ReadOnlyComposable
    get() = MaterialTheme.colorScheme.onSurface

/** 次级文本 → colorScheme.onSurfaceVariant（亮 6B7280 / 暗 A1A1AA）。 */
val OnSurfaceVariant: Color
    @Composable
    @ReadOnlyComposable
    get() = MaterialTheme.colorScheme.onSurfaceVariant

/** 三级弱化文本（提示/placeholder）→ 语义色 textSecondary。 */
val OnSurfaceSecondary: Color
    @Composable
    @ReadOnlyComposable
    get() = MaterialTheme.wmsColors.textSecondary

/** 浅底/分隔填充 → colorScheme.outlineVariant（亮 F0F2F5 / 暗 27272A）。 */
val SurfaceVariant: Color
    @Composable
    @ReadOnlyComposable
    get() = MaterialTheme.colorScheme.outlineVariant

/** 柔和分隔线 → 语义色 divider。 */
val DividerSoft: Color
    @Composable
    @ReadOnlyComposable
    get() = MaterialTheme.wmsColors.divider

/** 描边 → 语义色 border。 */
val BorderSoft: Color
    @Composable
    @ReadOnlyComposable
    get() = MaterialTheme.wmsColors.border

/** 品牌主色 → colorScheme.primary（亮 4361EE / 暗 7B8FF7）。 */
val Primary: Color
    @Composable
    @ReadOnlyComposable
    get() = MaterialTheme.colorScheme.primary

/** 主色浅底 → colorScheme.primaryContainer（亮 E8ECFD / 暗 2D3FBF）。 */
val PrimaryContainer: Color
    @Composable
    @ReadOnlyComposable
    get() = MaterialTheme.colorScheme.primaryContainer

// ── 状态语义色（亮/暗双版，来自 SemanticColors.kt）──

val Success: Color
    @Composable
    @ReadOnlyComposable
    get() = MaterialTheme.wmsColors.success

val SuccessContainer: Color
    @Composable
    @ReadOnlyComposable
    get() = MaterialTheme.wmsColors.successContainer

val Warning: Color
    @Composable
    @ReadOnlyComposable
    get() = MaterialTheme.wmsColors.warning

val WarningContainer: Color
    @Composable
    @ReadOnlyComposable
    get() = MaterialTheme.wmsColors.warningContainer

val Error: Color
    @Composable
    @ReadOnlyComposable
    get() = MaterialTheme.wmsColors.error

val ErrorContainer: Color
    @Composable
    @ReadOnlyComposable
    get() = MaterialTheme.wmsColors.errorContainer

val Info: Color
    @Composable
    @ReadOnlyComposable
    get() = MaterialTheme.wmsColors.info

val InfoContainer: Color
    @Composable
    @ReadOnlyComposable
    get() = MaterialTheme.wmsColors.infoContainer
