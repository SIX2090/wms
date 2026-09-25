package com.factory.wms.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.graphics.Color

private val LightColorScheme = lightColorScheme(
    primary = PalettePrimary,
    onPrimary = OnPrimary,
    primaryContainer = PalettePrimaryContainer,
    onPrimaryContainer = OnPrimaryContainer,
    secondary = Secondary,
    onSecondary = OnSecondary,
    secondaryContainer = SecondaryContainer,
    onSecondaryContainer = OnSecondaryContainer,
    tertiary = Tertiary,
    onTertiary = OnTertiary,
    tertiaryContainer = TertiaryContainer,
    onTertiaryContainer = OnTertiaryContainer,
    background = PaletteBackground,
    onBackground = PaletteOnSurface,
    // AI-APP-FIX-301：卡片令牌 CardBackground 映射到 surface——
    // 亮色下必须是白色（与原 CardBackground 一致，视觉零变化）
    surface = PaletteCardBackground,
    onSurface = PaletteOnSurface,
    surfaceVariant = PaletteSurfaceVariant,
    onSurfaceVariant = PaletteOnSurfaceVariant,
    error = PaletteError,
    onError = OnPrimary,
    errorContainer = PaletteErrorContainer,
    onErrorContainer = LightSemanticColors.onErrorContainer,
    outline = PaletteOnSurfaceVariant,
    outlineVariant = PaletteSurfaceVariant
)

private val DarkColorScheme = darkColorScheme(
    primary = PrimaryLight,
    onPrimary = OnPrimaryContainer,
    primaryContainer = PrimaryDark,
    onPrimaryContainer = PrimaryLight,
    secondary = SecondaryLight,
    onSecondary = OnSecondaryContainer,
    secondaryContainer = SecondaryDark,
    onSecondaryContainer = SecondaryLight,
    tertiary = TertiaryLight,
    onTertiary = OnTertiaryContainer,
    tertiaryContainer = TertiaryDark,
    onTertiaryContainer = TertiaryLight,
    background = DarkBackground,
    onBackground = DarkOnSurface,
    surface = DarkSurface,
    onSurface = DarkOnSurface,
    surfaceVariant = DarkSurfaceVariant,
    onSurfaceVariant = DarkOnSurfaceVariant,
    // AI-APP-FIX-301：暗色 error 族与语义色扩展对齐（亮红 + 深红底）
    error = DarkSemanticColors.error,
    onError = Color(0xFF450A0A),
    errorContainer = DarkSemanticColors.errorContainer,
    onErrorContainer = DarkSemanticColors.onErrorContainer,
    outline = DarkOnSurfaceVariant,
    outlineVariant = DarkSurfaceVariant
)

@Composable
fun WmsTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit
) {
    // AI-APP-FIX-301：语义色扩展（Success/Warning/Info 族、分隔线、三级文本、
    // Chip 选中底 alpha、骨架微光 alpha）随亮暗一并切换
    CompositionLocalProvider(
        LocalWmsSemanticColors provides if (darkTheme) DarkSemanticColors else LightSemanticColors
    ) {
        MaterialTheme(
            colorScheme = if (darkTheme) DarkColorScheme else LightColorScheme,
            typography = Typography,
            shapes = WmsShapes,
            content = content
        )
    }
}
