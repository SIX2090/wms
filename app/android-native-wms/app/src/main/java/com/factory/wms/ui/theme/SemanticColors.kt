package com.factory.wms.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.ReadOnlyComposable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color

/**
 * AI-APP-FIX-301：语义色扩展（亮/暗双版）。
 *
 * Material3 colorScheme 只有 error 一族语义色槽位，Success/Warning/Info 没有——
 * 若继续硬编码亮色值，暗色模式下会出现"深绿字压深绿底""黄字压暗底"等
 * 近不可读组合（FIX-302 的两处盘点记录正文即属此类）。故建 CompositionLocal
 * 扩展，与 colorScheme 一同随 WmsTheme 的 darkTheme 切换。
 *
 * 使用：`MaterialTheme.wmsColors.success`；页面侧也可直接引用
 * ThemeTokens.kt 的同名令牌（Success/Warning/Info/...），取值即来自此处。
 */
@Immutable
data class WmsSemanticColors(
    val success: Color,
    val successContainer: Color,
    val onSuccessContainer: Color,
    val warning: Color,
    val warningContainer: Color,
    val onWarningContainer: Color,
    val error: Color,
    val errorContainer: Color,
    val onErrorContainer: Color,
    val info: Color,
    val infoContainer: Color,
    val onInfoContainer: Color,
    /** 柔和分隔线（亮 E9EBF0 / 暗 2E2E33）。 */
    val divider: Color,
    /** 描边（亮 E2E5EA / 暗 3A3A40）。 */
    val border: Color,
    /** 三级弱化文本（亮 9CA3AF / 暗 71717A）。 */
    val textSecondary: Color,
    /** 模块色 Chip 选中底 alpha：暗色下 0.14 几乎看不见，提升到 0.24。 */
    val accentWashAlpha: Float,
    /** 骨架微光基础 alpha：暗色背景上 0.14 太淡，提升到 0.30。 */
    val shimmerAlpha: Float
)

internal val LightSemanticColors = WmsSemanticColors(
    success = PaletteSuccess,
    successContainer = PaletteSuccessContainer,
    onSuccessContainer = Color(0xFF065F46),
    warning = PaletteWarning,
    warningContainer = PaletteWarningContainer,
    onWarningContainer = Color(0xFF92400E),
    error = PaletteError,
    errorContainer = PaletteErrorContainer,
    onErrorContainer = Color(0xFFB91C1C),
    info = PaletteInfo,
    infoContainer = PaletteInfoContainer,
    onInfoContainer = Color(0xFF1E40AF),
    divider = PaletteDividerSoft,
    border = PaletteBorderSoft,
    textSecondary = PaletteTextSecondary,
    accentWashAlpha = 0.14f,
    shimmerAlpha = 0.14f
)

internal val DarkSemanticColors = WmsSemanticColors(
    success = Color(0xFF34D399),
    successContainer = Color(0xFF064E3B),
    onSuccessContainer = Color(0xFFA7F3D0),
    warning = Color(0xFFFBBF24),
    warningContainer = Color(0xFF451A03),
    onWarningContainer = Color(0xFFFDE68A),
    error = Color(0xFFF87171),
    errorContainer = Color(0xFF7F1D1D),
    onErrorContainer = Color(0xFFFECACA),
    info = Color(0xFF60A5FA),
    infoContainer = Color(0xFF1E3A8A),
    onInfoContainer = Color(0xFFBFDBFE),
    divider = DarkDividerSoft,
    border = DarkBorderSoft,
    textSecondary = DarkOnSurfaceSecondary,
    accentWashAlpha = 0.24f,
    shimmerAlpha = 0.30f
)

val LocalWmsSemanticColors = staticCompositionLocalOf { LightSemanticColors }

/** 语义色入口：`MaterialTheme.wmsColors.success`。 */
val MaterialTheme.wmsColors: WmsSemanticColors
    @Composable
    @ReadOnlyComposable
    get() = LocalWmsSemanticColors.current
