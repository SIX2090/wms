package com.factory.wms.ui.theme

import androidx.compose.ui.graphics.Color

// ── Primary ── 深海蓝工作台
// 只在常量值上做迁移，令牌名与引用关系全部保持不变，避免波及 21 个页面。
// AI-APP-FIX-301：会被亮/暗切换的令牌（Background/OnSurface/Success 族等）
// 一律改为 internal Palette*，由 ThemeTokens.kt 的同名委托 getter 对外提供
// （页面引用的令牌名不变，但取值跟随 colorScheme / 语义色扩展）。
internal val PalettePrimary = Color(0xFF195173)
val PrimaryLight = Color(0xFF90CFE2)
val PrimaryDark = Color(0xFF102F49)
internal val PalettePrimaryContainer = Color(0xFFE6F1F3)
val OnPrimary = Color.White
// Darken translucent controls on white-text gradients; a white wash lowers contrast.
internal val GradientControlScrim = Color.Black.copy(alpha = 0.12f)
val OnPrimaryContainer = Color(0xFF143C51)

// ── Secondary ── Warm Amber（模块/徽标点缀色，亮暗通用，不参与令牌映射）
val Secondary = Color(0xFFF59E0B)
val SecondaryLight = Color(0xFFFBBF24)
val SecondaryDark = Color(0xFFB45309)
val SecondaryContainer = Color(0xFFFFF3DF)
val OnSecondary = Color(0xFF1A1A1A)
val OnSecondaryContainer = Color(0xFF5C2D00)

// ── Tertiary ── Teal（同上，点缀色保留）
val Tertiary = Color(0xFF087E77)
val TertiaryLight = Color(0xFF86D6C9)
val TertiaryDark = Color(0xFF0F766E)
val TertiaryContainer = Color(0xFFD5F5F0)
val OnTertiary = Color.White
val OnTertiaryContainer = Color(0xFF00332F)

// ── Surface ──（内部调色板，经 ThemeTokens.kt 映射到 colorScheme）
internal val PaletteSurfaceVariant = Color(0xFFF0F2F5)
internal val PaletteBackground = Color(0xFFF1F6F7)
internal val PaletteCardBackground = Color.White

// ── On Surface ──
internal val PaletteOnSurface = Color(0xFF152C39)
internal val PaletteOnSurfaceVariant = Color(0xFF485E6B)
internal val PaletteTextSecondary = Color(0xFF536470)

// ── Divider / Border ── 柔和分隔线与描边（AI-APP-UI-001）
internal val PaletteDividerSoft = Color(0xFFE4ECEE)
internal val PaletteBorderSoft = Color(0xFFDAE5E8)

// ── Status ──（亮色版；暗色版见 SemanticColors.kt DarkSemanticColors）
internal val PaletteSuccess = Color(0xFF047857)
internal val PaletteSuccessContainer = Color(0xFFD1FAE5)
internal val PaletteWarning = Color(0xFF92400E)
internal val PaletteWarningContainer = Color(0xFFFFF3CD)
internal val PaletteError = Color(0xFFB91C1C)
internal val PaletteErrorContainer = Color(0xFFFEE2E2)
internal val PaletteInfo = Color(0xFF1D4ED8)
internal val PaletteInfoContainer = Color(0xFFDBEAFE)

// ── Card Gradients ── 模块渐变 accent（FIX-301：亮暗均保留，不映射）
// 扫码入库 - Indigo
val CardBlue = Color(0xFF195173)
val CardBlueLight = Color(0xFF78B7CD)
val CardBlueDark = Color(0xFF102F49)

// 扫码出库 - Green
val CardGreen = Color(0xFF059669)
val CardGreenLight = Color(0xFF34D399)
val CardGreenDark = Color(0xFF065F46)

// 扫码查库存 - Orange
val CardOrange = Color(0xFFEA580C)
val CardOrangeLight = Color(0xFFFB923C)
val CardOrangeDark = Color(0xFF9A3412)

// 扫码盘点 - Purple
val CardPurple = Color(0xFF7C3AED)
val CardPurpleLight = Color(0xFFA78BFA)
val CardPurpleDark = Color(0xFF5B21B6)

// 扫码识别单据 - Teal
val CardTeal = Color(0xFF087E77)
val CardTealLight = Color(0xFF86D6C9)
val CardTealDark = Color(0xFF0F766E)

// 识物功能 - Rose
val CardPink = Color(0xFFE11D48)
val CardPinkLight = Color(0xFFFB7185)
val CardPinkDark = Color(0xFF9F1239)

// 期初库存 - Cyan
val CardCyan = Color(0xFF0891B2)
val CardCyanLight = Color(0xFF22D3EE)
val CardCyanDark = Color(0xFF155E75)

// 物料档案 - Amber（与期初库存 Cyan 区分，AI-APP-UI-001）
val CardAmber = Color(0xFFD97706)
val CardAmberLight = Color(0xFFFBBF24)
val CardAmberDark = Color(0xFF92400E)

// ── Dark Theme ──（内部调色板，Theme.kt / SemanticColors.kt 使用）
internal val DarkSurface = Color(0xFF192A35)
internal val DarkSurfaceVariant = Color(0xFF29323F)
internal val DarkBackground = Color(0xFF101D26)
internal val DarkPrimaryContainer = Color(0xFF243C4A)
internal val DarkSecondaryContainer = Color(0xFF46331F)
internal val DarkTertiaryContainer = Color(0xFF163E39)
internal val DarkOnPrimary = Color(0xFF0E2C3D)
internal val DarkOnSurface = Color(0xFFE2EBEF)
internal val DarkOnSurfaceVariant = Color(0xFFAFC2CB)
internal val DarkOnSurfaceSecondary = Color(0xFFAFC2CB)
internal val DarkDividerSoft = Color(0xFF2A3C47)
internal val DarkBorderSoft = Color(0xFF354954)
