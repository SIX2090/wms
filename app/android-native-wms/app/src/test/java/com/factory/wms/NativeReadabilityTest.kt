package com.factory.wms

import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.compositeOver
import com.factory.wms.ui.components.darken
import com.factory.wms.ui.theme.*
import org.junit.Assert.*
import org.junit.Test
import kotlin.math.pow

class NativeReadabilityTest {
    // Independent WCAG sRGB oracle, rather than checking the helper against itself.
    private fun contrast(foreground: Color, background: Color): Double {
        fun luminance(c: Color): Double {
            fun linear(v: Float): Double = if (v <= 0.04045f) v / 12.92 else ((v + 0.055) / 1.055).pow(2.4)
            return linear(c.red) * 0.2126 + linear(c.green) * 0.7152 + linear(c.blue) * 0.0722
        }
        val a = luminance(foreground.compositeOver(background))
        val b = luminance(background)
        return (maxOf(a, b) + 0.05) / (minOf(a, b) + 0.05)
    }

    @Test fun semanticTextRemainsReadableOnLightAndDarkSurfaces() {
        for ((colors, backgrounds) in listOf(
            LightSemanticColors to listOf(PaletteCardBackground, PaletteBackground, PaletteSurfaceVariant),
            DarkSemanticColors to listOf(DarkSurface, DarkBackground, DarkSurfaceVariant)
        )) {
            for (background in backgrounds) {
                for (foreground in listOf(colors.textSecondary, colors.success, colors.warning, colors.error, colors.info)) {
                    assertTrue("Low text contrast: $foreground / $background", contrast(foreground, background) >= 4.5)
                }
            }
            assertTrue(contrast(colors.onWarningContainer, colors.warningContainer) >= 4.5)
            assertTrue(contrast(colors.onErrorContainer, colors.errorContainer) >= 4.5)
        }
    }

    @Test fun moduleBadgesAndWhiteHeaderTextPassInBothThemes() {
        val accents = listOf(Secondary, Tertiary, CardBlue, CardGreen, CardOrange, CardPurple,
            CardTealLight, CardPinkLight, CardCyanLight, CardAmberLight, PrimaryLight)
        for (accent in accents) {
            for (surface in listOf(PaletteCardBackground, DarkSurface)) {
                val background = accent.copy(alpha = 0.12f).compositeOver(surface)
                assertTrue(contrast(accent.readableOn(background), background) >= 4.499)
            }
            val header = accent.readableOn(Color.White)
            assertTrue(contrast(Color.White, header) >= 4.499)
            assertTrue(contrast(Color.White, header.darken(0.74f)) >= 4.499)
        }
    }

    @Test fun adequateAccentAndAlphaContrastArePreserved() {
        assertEquals(PalettePrimary, PalettePrimary.readableOn(Color.White))
        val foreground = Color.Black.copy(alpha = 0.5f)
        assertEquals(contrast(foreground, Color.White), contrastRatio(foreground, Color.White).toDouble(), 0.001)
    }
}
