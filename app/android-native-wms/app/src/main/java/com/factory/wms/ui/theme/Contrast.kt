package com.factory.wms.ui.theme

import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.compositeOver
import androidx.compose.ui.graphics.lerp
import androidx.compose.ui.graphics.luminance

/** Contrast of the rendered foreground against an opaque background. */
fun contrastRatio(foreground: Color, background: Color): Float {
    val foregroundLuminance = foreground.compositeOver(background).luminance()
    val backgroundLuminance = background.luminance()
    return (maxOf(foregroundLuminance, backgroundLuminance) + 0.05f) /
        (minOf(foregroundLuminance, backgroundLuminance) + 0.05f)
}

/** Retain a module's hue while bringing its text to 4.5:1 on the actual surface. */
fun Color.readableOn(background: Color): Color {
    if (contrastRatio(this, background) >= 4.5f) return this
    val rendered = compositeOver(background)
    val destination = if (contrastRatio(Color.Black, background) > contrastRatio(Color.White, background)) {
        Color.Black
    } else Color.White
    var low = 0f
    var high = 1f
    repeat(16) {
        val middle = (low + high) / 2
        if (contrastRatio(lerp(rendered, destination, middle), background) >= 4.5f) high = middle
        else low = middle
    }
    return lerp(rendered, destination, high)
}
