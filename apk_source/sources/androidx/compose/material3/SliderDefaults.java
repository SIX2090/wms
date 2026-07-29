package androidx.compose.material3;

import androidx.compose.foundation.BackgroundKt;
import androidx.compose.foundation.HoverableKt;
import androidx.compose.foundation.IndicationKt;
import androidx.compose.foundation.interaction.MutableInteractionSource;
import androidx.compose.foundation.layout.SizeKt;
import androidx.compose.foundation.layout.SpacerKt;
import androidx.compose.material.ripple.RippleKt;
import androidx.compose.material3.tokens.SliderTokens;
import androidx.compose.runtime.Composer;
import androidx.compose.runtime.ComposerKt;
import androidx.compose.runtime.EffectsKt;
import androidx.compose.runtime.RecomposeScopeImplKt;
import androidx.compose.runtime.ScopeUpdateScope;
import androidx.compose.runtime.SnapshotStateKt;
import androidx.compose.runtime.snapshots.SnapshotStateList;
import androidx.compose.ui.Modifier;
import androidx.compose.ui.draw.ShadowKt;
import androidx.compose.ui.geometry.Offset;
import androidx.compose.ui.geometry.OffsetKt;
import androidx.compose.ui.geometry.Size;
import androidx.compose.ui.graphics.Color;
import androidx.compose.ui.graphics.ColorKt;
import androidx.compose.ui.graphics.GraphicsLayerScopeKt;
import androidx.compose.ui.graphics.RectangleShapeKt;
import androidx.compose.ui.graphics.Shape;
import androidx.compose.ui.graphics.StrokeCap;
import androidx.compose.ui.graphics.drawscope.DrawScope;
import androidx.compose.ui.unit.Dp;
import androidx.compose.ui.unit.LayoutDirection;
import androidx.profileinstaller.ProfileVerifier;
import kotlin.Metadata;
import kotlin.Unit;
import kotlin.coroutines.Continuation;
import kotlin.jvm.functions.Function2;
import kotlinx.coroutines.CoroutineScope;

/* compiled from: Slider.kt */
@Metadata(d1 = {"\u0000n\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0010\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0010\u000b\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0004\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0018\u0002\n\u0002\b\f\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010\u0014\n\u0000\n\u0002\u0010\u0007\n\u0002\b\u0004\bÇ\u0002\u0018\u00002\u00020\u0001B\u0007\b\u0002¢\u0006\u0002\u0010\u0002JB\u0010\b\u001a\u00020\t2\u0006\u0010\n\u001a\u00020\u000b2\b\b\u0002\u0010\f\u001a\u00020\r2\b\b\u0002\u0010\u000e\u001a\u00020\u00042\b\b\u0002\u0010\u000f\u001a\u00020\u00102\b\b\u0002\u0010\u0011\u001a\u00020\u0012H\u0007ø\u0001\u0000¢\u0006\u0004\b\u0013\u0010\u0014J3\u0010\u0015\u001a\u00020\t2\u0006\u0010\u0016\u001a\u00020\u00172\b\b\u0002\u0010\f\u001a\u00020\r2\b\b\u0002\u0010\u000e\u001a\u00020\u00042\b\b\u0002\u0010\u000f\u001a\u00020\u0010H\u0007¢\u0006\u0002\u0010\u0018J3\u0010\u0015\u001a\u00020\t2\u0006\u0010\u0019\u001a\u00020\u001a2\b\b\u0002\u0010\f\u001a\u00020\r2\b\b\u0002\u0010\u000e\u001a\u00020\u00042\b\b\u0002\u0010\u000f\u001a\u00020\u0010H\u0007¢\u0006\u0002\u0010\u001bJ3\u0010\u0015\u001a\u00020\t2\u0006\u0010\u001c\u001a\u00020\u001d2\b\b\u0002\u0010\f\u001a\u00020\r2\b\b\u0002\u0010\u000e\u001a\u00020\u00042\b\b\u0002\u0010\u000f\u001a\u00020\u0010H\u0007¢\u0006\u0002\u0010\u001eJ\r\u0010\u000e\u001a\u00020\u0004H\u0007¢\u0006\u0002\u0010\u001fJv\u0010\u000e\u001a\u00020\u00042\b\b\u0002\u0010 \u001a\u00020!2\b\b\u0002\u0010\"\u001a\u00020!2\b\b\u0002\u0010#\u001a\u00020!2\b\b\u0002\u0010$\u001a\u00020!2\b\b\u0002\u0010%\u001a\u00020!2\b\b\u0002\u0010&\u001a\u00020!2\b\b\u0002\u0010'\u001a\u00020!2\b\b\u0002\u0010(\u001a\u00020!2\b\b\u0002\u0010)\u001a\u00020!2\b\b\u0002\u0010*\u001a\u00020!H\u0007ø\u0001\u0000¢\u0006\u0004\b+\u0010,JN\u0010-\u001a\u00020\t*\u00020.2\u0006\u0010/\u001a\u0002002\u0006\u00101\u001a\u0002022\u0006\u00103\u001a\u0002022\u0006\u0010$\u001a\u00020!2\u0006\u0010\"\u001a\u00020!2\u0006\u0010%\u001a\u00020!2\u0006\u0010#\u001a\u00020!H\u0002ø\u0001\u0000¢\u0006\u0004\b4\u00105R\u0018\u0010\u0003\u001a\u00020\u0004*\u00020\u00058@X\u0080\u0004¢\u0006\u0006\u001a\u0004\b\u0006\u0010\u0007\u0082\u0002\u0007\n\u0005\b¡\u001e0\u0001¨\u00066"}, d2 = {"Landroidx/compose/material3/SliderDefaults;", "", "()V", "defaultSliderColors", "Landroidx/compose/material3/SliderColors;", "Landroidx/compose/material3/ColorScheme;", "getDefaultSliderColors$material3_release", "(Landroidx/compose/material3/ColorScheme;)Landroidx/compose/material3/SliderColors;", "Thumb", "", "interactionSource", "Landroidx/compose/foundation/interaction/MutableInteractionSource;", "modifier", "Landroidx/compose/ui/Modifier;", "colors", "enabled", "", "thumbSize", "Landroidx/compose/ui/unit/DpSize;", "Thumb-9LiSoMs", "(Landroidx/compose/foundation/interaction/MutableInteractionSource;Landroidx/compose/ui/Modifier;Landroidx/compose/material3/SliderColors;ZJLandroidx/compose/runtime/Composer;II)V", "Track", "rangeSliderState", "Landroidx/compose/material3/RangeSliderState;", "(Landroidx/compose/material3/RangeSliderState;Landroidx/compose/ui/Modifier;Landroidx/compose/material3/SliderColors;ZLandroidx/compose/runtime/Composer;II)V", "sliderPositions", "Landroidx/compose/material3/SliderPositions;", "(Landroidx/compose/material3/SliderPositions;Landroidx/compose/ui/Modifier;Landroidx/compose/material3/SliderColors;ZLandroidx/compose/runtime/Composer;II)V", "sliderState", "Landroidx/compose/material3/SliderState;", "(Landroidx/compose/material3/SliderState;Landroidx/compose/ui/Modifier;Landroidx/compose/material3/SliderColors;ZLandroidx/compose/runtime/Composer;II)V", "(Landroidx/compose/runtime/Composer;I)Landroidx/compose/material3/SliderColors;", "thumbColor", "Landroidx/compose/ui/graphics/Color;", "activeTrackColor", "activeTickColor", "inactiveTrackColor", "inactiveTickColor", "disabledThumbColor", "disabledActiveTrackColor", "disabledActiveTickColor", "disabledInactiveTrackColor", "disabledInactiveTickColor", "colors-q0g_0yA", "(JJJJJJJJJJLandroidx/compose/runtime/Composer;III)Landroidx/compose/material3/SliderColors;", "drawTrack", "Landroidx/compose/ui/graphics/drawscope/DrawScope;", "tickFractions", "", "activeRangeStart", "", "activeRangeEnd", "drawTrack-LUBghH0", "(Landroidx/compose/ui/graphics/drawscope/DrawScope;[FFFJJJJ)V", "material3_release"}, k = 1, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class SliderDefaults {
    public static final int $stable = 0;
    public static final SliderDefaults INSTANCE = new SliderDefaults();

    private SliderDefaults() {
    }

    public final SliderColors colors(Composer $composer, int $changed) {
        $composer.startReplaceableGroup(1376295968);
        ComposerKt.sourceInformation($composer, "C(colors)886@36284L11:Slider.kt#uh7d8r");
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventStart(1376295968, $changed, -1, "androidx.compose.material3.SliderDefaults.colors (Slider.kt:886)");
        }
        SliderColors defaultSliderColors$material3_release = getDefaultSliderColors$material3_release(MaterialTheme.INSTANCE.getColorScheme($composer, 6));
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventEnd();
        }
        $composer.endReplaceableGroup();
        return defaultSliderColors$material3_release;
    }

    /* renamed from: colors-q0g_0yA, reason: not valid java name */
    public final SliderColors m2208colorsq0g_0yA(long thumbColor, long activeTrackColor, long activeTickColor, long inactiveTrackColor, long inactiveTickColor, long disabledThumbColor, long disabledActiveTrackColor, long disabledActiveTickColor, long disabledInactiveTrackColor, long disabledInactiveTickColor, Composer $composer, int $changed, int $changed1, int i) {
        $composer.startReplaceableGroup(885588574);
        ComposerKt.sourceInformation($composer, "C(colors)P(9:c#ui.graphics.Color,1:c#ui.graphics.Color,0:c#ui.graphics.Color,8:c#ui.graphics.Color,7:c#ui.graphics.Color,6:c#ui.graphics.Color,3:c#ui.graphics.Color,2:c#ui.graphics.Color,5:c#ui.graphics.Color,4:c#ui.graphics.Color)927@38583L11:Slider.kt#uh7d8r");
        long thumbColor2 = (i & 1) != 0 ? Color.INSTANCE.m3782getUnspecified0d7_KjU() : thumbColor;
        long activeTrackColor2 = (i & 2) != 0 ? Color.INSTANCE.m3782getUnspecified0d7_KjU() : activeTrackColor;
        long activeTickColor2 = (i & 4) != 0 ? Color.INSTANCE.m3782getUnspecified0d7_KjU() : activeTickColor;
        long inactiveTrackColor2 = (i & 8) != 0 ? Color.INSTANCE.m3782getUnspecified0d7_KjU() : inactiveTrackColor;
        long inactiveTickColor2 = (i & 16) != 0 ? Color.INSTANCE.m3782getUnspecified0d7_KjU() : inactiveTickColor;
        long disabledThumbColor2 = (i & 32) != 0 ? Color.INSTANCE.m3782getUnspecified0d7_KjU() : disabledThumbColor;
        long disabledActiveTrackColor2 = (i & 64) != 0 ? Color.INSTANCE.m3782getUnspecified0d7_KjU() : disabledActiveTrackColor;
        long disabledActiveTickColor2 = (i & 128) != 0 ? Color.INSTANCE.m3782getUnspecified0d7_KjU() : disabledActiveTickColor;
        long disabledInactiveTrackColor2 = (i & 256) != 0 ? Color.INSTANCE.m3782getUnspecified0d7_KjU() : disabledInactiveTrackColor;
        long disabledInactiveTickColor2 = (i & 512) != 0 ? Color.INSTANCE.m3782getUnspecified0d7_KjU() : disabledInactiveTickColor;
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventStart(885588574, $changed, $changed1, "androidx.compose.material3.SliderDefaults.colors (Slider.kt:927)");
        }
        SliderColors m2191copyK518z4 = getDefaultSliderColors$material3_release(MaterialTheme.INSTANCE.getColorScheme($composer, 6)).m2191copyK518z4(thumbColor2, activeTrackColor2, activeTickColor2, inactiveTrackColor2, inactiveTickColor2, disabledThumbColor2, disabledActiveTrackColor2, disabledActiveTickColor2, disabledInactiveTrackColor2, disabledInactiveTickColor2);
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventEnd();
        }
        $composer.endReplaceableGroup();
        return m2191copyK518z4;
    }

    public final SliderColors getDefaultSliderColors$material3_release(ColorScheme $this$defaultSliderColors) {
        long m3744copywmQWz5c;
        long m3744copywmQWz5c2;
        long m3744copywmQWz5c3;
        long m3744copywmQWz5c4;
        long m3744copywmQWz5c5;
        long m3744copywmQWz5c6;
        long m3744copywmQWz5c7;
        SliderColors defaultSliderColorsCached = $this$defaultSliderColors.getDefaultSliderColorsCached();
        if (defaultSliderColorsCached == null) {
            long fromToken = ColorSchemeKt.fromToken($this$defaultSliderColors, SliderTokens.INSTANCE.getHandleColor());
            long fromToken2 = ColorSchemeKt.fromToken($this$defaultSliderColors, SliderTokens.INSTANCE.getActiveTrackColor());
            m3744copywmQWz5c = Color.m3744copywmQWz5c(r8, (r12 & 1) != 0 ? Color.m3748getAlphaimpl(r8) : 0.38f, (r12 & 2) != 0 ? Color.m3752getRedimpl(r8) : 0.0f, (r12 & 4) != 0 ? Color.m3751getGreenimpl(r8) : 0.0f, (r12 & 8) != 0 ? Color.m3749getBlueimpl(ColorSchemeKt.fromToken($this$defaultSliderColors, SliderTokens.INSTANCE.getTickMarksActiveContainerColor())) : 0.0f);
            long fromToken3 = ColorSchemeKt.fromToken($this$defaultSliderColors, SliderTokens.INSTANCE.getInactiveTrackColor());
            m3744copywmQWz5c2 = Color.m3744copywmQWz5c(r12, (r12 & 1) != 0 ? Color.m3748getAlphaimpl(r12) : 0.38f, (r12 & 2) != 0 ? Color.m3752getRedimpl(r12) : 0.0f, (r12 & 4) != 0 ? Color.m3751getGreenimpl(r12) : 0.0f, (r12 & 8) != 0 ? Color.m3749getBlueimpl(ColorSchemeKt.fromToken($this$defaultSliderColors, SliderTokens.INSTANCE.getTickMarksInactiveContainerColor())) : 0.0f);
            m3744copywmQWz5c3 = Color.m3744copywmQWz5c(r14, (r12 & 1) != 0 ? Color.m3748getAlphaimpl(r14) : 0.38f, (r12 & 2) != 0 ? Color.m3752getRedimpl(r14) : 0.0f, (r12 & 4) != 0 ? Color.m3751getGreenimpl(r14) : 0.0f, (r12 & 8) != 0 ? Color.m3749getBlueimpl(ColorSchemeKt.fromToken($this$defaultSliderColors, SliderTokens.INSTANCE.getDisabledHandleColor())) : 0.0f);
            long m3791compositeOverOWjLjI = ColorKt.m3791compositeOverOWjLjI(m3744copywmQWz5c3, $this$defaultSliderColors.getSurface());
            m3744copywmQWz5c4 = Color.m3744copywmQWz5c(r15, (r12 & 1) != 0 ? Color.m3748getAlphaimpl(r15) : 0.38f, (r12 & 2) != 0 ? Color.m3752getRedimpl(r15) : 0.0f, (r12 & 4) != 0 ? Color.m3751getGreenimpl(r15) : 0.0f, (r12 & 8) != 0 ? Color.m3749getBlueimpl(ColorSchemeKt.fromToken($this$defaultSliderColors, SliderTokens.INSTANCE.getDisabledActiveTrackColor())) : 0.0f);
            m3744copywmQWz5c5 = Color.m3744copywmQWz5c(r26, (r12 & 1) != 0 ? Color.m3748getAlphaimpl(r26) : 0.38f, (r12 & 2) != 0 ? Color.m3752getRedimpl(r26) : 0.0f, (r12 & 4) != 0 ? Color.m3751getGreenimpl(r26) : 0.0f, (r12 & 8) != 0 ? Color.m3749getBlueimpl(ColorSchemeKt.fromToken($this$defaultSliderColors, SliderTokens.INSTANCE.getTickMarksDisabledContainerColor())) : 0.0f);
            m3744copywmQWz5c6 = Color.m3744copywmQWz5c(r26, (r12 & 1) != 0 ? Color.m3748getAlphaimpl(r26) : 0.12f, (r12 & 2) != 0 ? Color.m3752getRedimpl(r26) : 0.0f, (r12 & 4) != 0 ? Color.m3751getGreenimpl(r26) : 0.0f, (r12 & 8) != 0 ? Color.m3749getBlueimpl(ColorSchemeKt.fromToken($this$defaultSliderColors, SliderTokens.INSTANCE.getDisabledInactiveTrackColor())) : 0.0f);
            m3744copywmQWz5c7 = Color.m3744copywmQWz5c(r26, (r12 & 1) != 0 ? Color.m3748getAlphaimpl(r26) : 0.38f, (r12 & 2) != 0 ? Color.m3752getRedimpl(r26) : 0.0f, (r12 & 4) != 0 ? Color.m3751getGreenimpl(r26) : 0.0f, (r12 & 8) != 0 ? Color.m3749getBlueimpl(ColorSchemeKt.fromToken($this$defaultSliderColors, SliderTokens.INSTANCE.getTickMarksDisabledContainerColor())) : 0.0f);
            SliderColors it = new SliderColors(fromToken, fromToken2, m3744copywmQWz5c, fromToken3, m3744copywmQWz5c2, m3791compositeOverOWjLjI, m3744copywmQWz5c4, m3744copywmQWz5c5, m3744copywmQWz5c6, m3744copywmQWz5c7, null);
            $this$defaultSliderColors.setDefaultSliderColorsCached$material3_release(it);
            return it;
        }
        return defaultSliderColorsCached;
    }

    /* renamed from: Thumb-9LiSoMs, reason: not valid java name */
    public final void m2207Thumb9LiSoMs(final MutableInteractionSource interactionSource, Modifier modifier, SliderColors colors, boolean enabled, long thumbSize, Composer $composer, final int $changed, final int i) {
        Modifier modifier2;
        SliderColors sliderColors;
        boolean enabled2;
        long j;
        SliderColors colors2;
        Modifier modifier3;
        SliderColors colors3;
        int $dirty;
        boolean enabled3;
        long thumbSize2;
        long j2;
        Object value$iv;
        SliderDefaults$Thumb$1$1 value$iv2;
        long thumbSize3;
        Modifier m3417shadows4CzXII;
        boolean enabled4;
        Modifier modifier4;
        SliderColors colors4;
        int i2;
        Composer $composer2 = $composer.startRestartGroup(-290277409);
        ComposerKt.sourceInformation($composer2, "C(Thumb)P(2,3!,4:c#ui.unit.DpSize)983@41717L8,987@41833L46,988@41922L658,988@41888L692,1006@42779L5,1014@43049L143,1009@42833L595:Slider.kt#uh7d8r");
        int $dirty2 = $changed;
        if ((i & 1) != 0) {
            $dirty2 |= 6;
        } else if (($changed & 6) == 0) {
            $dirty2 |= $composer2.changed(interactionSource) ? 4 : 2;
        }
        int i3 = i & 2;
        if (i3 != 0) {
            $dirty2 |= 48;
            modifier2 = modifier;
        } else if (($changed & 48) == 0) {
            modifier2 = modifier;
            $dirty2 |= $composer2.changed(modifier2) ? 32 : 16;
        } else {
            modifier2 = modifier;
        }
        if (($changed & 384) == 0) {
            if ((i & 4) == 0) {
                sliderColors = colors;
                if ($composer2.changed(sliderColors)) {
                    i2 = 256;
                    $dirty2 |= i2;
                }
            } else {
                sliderColors = colors;
            }
            i2 = 128;
            $dirty2 |= i2;
        } else {
            sliderColors = colors;
        }
        int i4 = i & 8;
        if (i4 != 0) {
            $dirty2 |= 3072;
            enabled2 = enabled;
        } else if (($changed & 3072) == 0) {
            enabled2 = enabled;
            $dirty2 |= $composer2.changed(enabled2) ? 2048 : 1024;
        } else {
            enabled2 = enabled;
        }
        int i5 = i & 16;
        if (i5 != 0) {
            $dirty2 |= 24576;
            j = thumbSize;
        } else if (($changed & 24576) == 0) {
            j = thumbSize;
            $dirty2 |= $composer2.changed(j) ? 16384 : 8192;
        } else {
            j = thumbSize;
        }
        if ((i & 32) != 0) {
            $dirty2 |= ProfileVerifier.CompilationStatus.RESULT_CODE_ERROR_CANT_WRITE_PROFILE_VERIFICATION_RESULT_CACHE_FILE;
        } else if (($changed & ProfileVerifier.CompilationStatus.RESULT_CODE_ERROR_CANT_WRITE_PROFILE_VERIFICATION_RESULT_CACHE_FILE) == 0) {
            $dirty2 |= $composer2.changed(this) ? 131072 : 65536;
        }
        if (($dirty2 & 74899) == 74898 && $composer2.getSkipping()) {
            $composer2.skipToGroupEnd();
            enabled4 = enabled2;
            thumbSize3 = j;
            modifier4 = modifier2;
            colors4 = sliderColors;
        } else {
            $composer2.startDefaults();
            if (($changed & 1) == 0 || $composer2.getDefaultsInvalid()) {
                Modifier.Companion modifier5 = i3 != 0 ? Modifier.INSTANCE : modifier2;
                if ((i & 4) != 0) {
                    colors2 = colors($composer2, ($dirty2 >> 15) & 14);
                    $dirty2 &= -897;
                } else {
                    colors2 = sliderColors;
                }
                if (i4 != 0) {
                    enabled2 = true;
                }
                if (i5 != 0) {
                    j2 = SliderKt.ThumbSize;
                    $dirty = $dirty2;
                    modifier3 = modifier5;
                    colors3 = colors2;
                    enabled3 = enabled2;
                    thumbSize2 = j2;
                } else {
                    modifier3 = modifier5;
                    colors3 = colors2;
                    long j3 = j;
                    $dirty = $dirty2;
                    enabled3 = enabled2;
                    thumbSize2 = j3;
                }
            } else {
                $composer2.skipToGroupEnd();
                if ((i & 4) != 0) {
                    $dirty2 &= -897;
                }
                modifier3 = modifier2;
                colors3 = sliderColors;
                long j4 = j;
                $dirty = $dirty2;
                enabled3 = enabled2;
                thumbSize2 = j4;
            }
            $composer2.endDefaults();
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventStart(-290277409, $dirty, -1, "androidx.compose.material3.SliderDefaults.Thumb (Slider.kt:986)");
            }
            $composer2.startReplaceableGroup(-1142853013);
            ComposerKt.sourceInformation($composer2, "CC(remember):Slider.kt#9igjgp");
            Object it$iv = $composer2.rememberedValue();
            if (it$iv == Composer.INSTANCE.getEmpty()) {
                value$iv = SnapshotStateKt.mutableStateListOf();
                $composer2.updateRememberedValue(value$iv);
            } else {
                value$iv = it$iv;
            }
            SnapshotStateList interactions = (SnapshotStateList) value$iv;
            $composer2.endReplaceableGroup();
            $composer2.startReplaceableGroup(-1142852924);
            ComposerKt.sourceInformation($composer2, "CC(remember):Slider.kt#9igjgp");
            boolean invalid$iv = ($dirty & 14) == 4;
            Object it$iv2 = $composer2.rememberedValue();
            if (invalid$iv || it$iv2 == Composer.INSTANCE.getEmpty()) {
                value$iv2 = new SliderDefaults$Thumb$1$1(interactionSource, interactions, null);
                $composer2.updateRememberedValue(value$iv2);
            } else {
                value$iv2 = it$iv2;
            }
            $composer2.endReplaceableGroup();
            EffectsKt.LaunchedEffect(interactionSource, (Function2<? super CoroutineScope, ? super Continuation<? super Unit>, ? extends Object>) value$iv2, $composer2, $dirty & 14);
            float elevation = !interactions.isEmpty() ? SliderKt.ThumbPressedElevation : SliderKt.ThumbDefaultElevation;
            Shape shape = ShapesKt.getValue(SliderTokens.INSTANCE.getHandleShape(), $composer2, 6);
            float arg0$iv = SliderTokens.INSTANCE.m3133getStateLayerSizeD9Ej5fM();
            float elevation2 = elevation;
            float elevation3 = 2;
            thumbSize3 = thumbSize2;
            m3417shadows4CzXII = ShadowKt.m3417shadows4CzXII(HoverableKt.hoverable$default(IndicationKt.indication(SizeKt.m612size6HolHcs(modifier3, thumbSize2), interactionSource, RippleKt.m1553rememberRipple9IZ8Weo(false, Dp.m6094constructorimpl(arg0$iv / elevation3), 0L, $composer2, 54, 4)), interactionSource, false, 2, null), enabled3 ? elevation2 : Dp.m6094constructorimpl(0), (r15 & 2) != 0 ? RectangleShapeKt.getRectangleShape() : shape, (r15 & 4) != 0 ? Dp.m6093compareTo0680j_4(r8, Dp.m6094constructorimpl((float) 0)) > 0 : false, (r15 & 8) != 0 ? GraphicsLayerScopeKt.getDefaultShadowColor() : 0L, (r15 & 16) != 0 ? GraphicsLayerScopeKt.getDefaultShadowColor() : 0L);
            SpacerKt.Spacer(BackgroundKt.m209backgroundbw27NRU(m3417shadows4CzXII, colors3.m2202thumbColorvNxB06k$material3_release(enabled3), shape), $composer2, 0);
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventEnd();
            }
            enabled4 = enabled3;
            modifier4 = modifier3;
            colors4 = colors3;
        }
        ScopeUpdateScope endRestartGroup = $composer2.endRestartGroup();
        if (endRestartGroup != null) {
            final Modifier modifier6 = modifier4;
            final SliderColors sliderColors2 = colors4;
            final boolean z = enabled4;
            final long j5 = thumbSize3;
            endRestartGroup.updateScope(new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.SliderDefaults$Thumb$2
                /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
                {
                    super(2);
                }

                @Override // kotlin.jvm.functions.Function2
                public /* bridge */ /* synthetic */ Unit invoke(Composer composer, Integer num) {
                    invoke(composer, num.intValue());
                    return Unit.INSTANCE;
                }

                public final void invoke(Composer composer, int i6) {
                    SliderDefaults.this.m2207Thumb9LiSoMs(interactionSource, modifier6, sliderColors2, z, j5, composer, RecomposeScopeImplKt.updateChangedFlags($changed | 1), i);
                }
            });
        }
    }

    /* JADX WARN: Removed duplicated region for block: B:53:0x0199  */
    @kotlin.Deprecated(message = "Use version that supports slider state")
    /*
        Code decompiled incorrectly, please refer to instructions dump.
        To view partially-correct add '--show-bad-code' argument
    */
    public final void Track(final androidx.compose.material3.SliderPositions r31, androidx.compose.ui.Modifier r32, androidx.compose.material3.SliderColors r33, boolean r34, androidx.compose.runtime.Composer r35, final int r36, final int r37) {
        /*
            Method dump skipped, instructions count: 446
            To view this dump add '--comments-level debug' option
        */
        throw new UnsupportedOperationException("Method not decompiled: androidx.compose.material3.SliderDefaults.Track(androidx.compose.material3.SliderPositions, androidx.compose.ui.Modifier, androidx.compose.material3.SliderColors, boolean, androidx.compose.runtime.Composer, int, int):void");
    }

    /* JADX WARN: Removed duplicated region for block: B:53:0x019a  */
    /*
        Code decompiled incorrectly, please refer to instructions dump.
        To view partially-correct add '--show-bad-code' argument
    */
    public final void Track(final androidx.compose.material3.SliderState r30, androidx.compose.ui.Modifier r31, androidx.compose.material3.SliderColors r32, boolean r33, androidx.compose.runtime.Composer r34, final int r35, final int r36) {
        /*
            Method dump skipped, instructions count: 449
            To view this dump add '--comments-level debug' option
        */
        throw new UnsupportedOperationException("Method not decompiled: androidx.compose.material3.SliderDefaults.Track(androidx.compose.material3.SliderState, androidx.compose.ui.Modifier, androidx.compose.material3.SliderColors, boolean, androidx.compose.runtime.Composer, int, int):void");
    }

    /* JADX WARN: Removed duplicated region for block: B:53:0x019a  */
    /*
        Code decompiled incorrectly, please refer to instructions dump.
        To view partially-correct add '--show-bad-code' argument
    */
    public final void Track(final androidx.compose.material3.RangeSliderState r30, androidx.compose.ui.Modifier r31, androidx.compose.material3.SliderColors r32, boolean r33, androidx.compose.runtime.Composer r34, final int r35, final int r36) {
        /*
            Method dump skipped, instructions count: 449
            To view this dump add '--comments-level debug' option
        */
        throw new UnsupportedOperationException("Method not decompiled: androidx.compose.material3.SliderDefaults.Track(androidx.compose.material3.RangeSliderState, androidx.compose.ui.Modifier, androidx.compose.material3.SliderColors, boolean, androidx.compose.runtime.Composer, int, int):void");
    }

    /* JADX INFO: Access modifiers changed from: private */
    /* renamed from: drawTrack-LUBghH0, reason: not valid java name */
    public final void m2206drawTrackLUBghH0(DrawScope $this$drawTrack_u2dLUBghH0, float[] tickFractions, float activeRangeStart, float activeRangeEnd, long inactiveTrackColor, long activeTrackColor, long inactiveTickColor, long activeTickColor) {
        float f;
        boolean isRtl = $this$drawTrack_u2dLUBghH0.getLayoutDirection() == LayoutDirection.Rtl;
        long sliderLeft = OffsetKt.Offset(0.0f, Offset.m3506getYimpl($this$drawTrack_u2dLUBghH0.mo4294getCenterF1C5BW0()));
        long sliderRight = OffsetKt.Offset(Size.m3574getWidthimpl($this$drawTrack_u2dLUBghH0.mo4295getSizeNHjbRc()), Offset.m3506getYimpl($this$drawTrack_u2dLUBghH0.mo4294getCenterF1C5BW0()));
        long sliderStart = isRtl ? sliderRight : sliderLeft;
        long sliderEnd = isRtl ? sliderLeft : sliderRight;
        f = SliderKt.TickSize;
        float tickSize = $this$drawTrack_u2dLUBghH0.mo313toPx0680j_4(f);
        float trackStrokeWidth = $this$drawTrack_u2dLUBghH0.mo313toPx0680j_4(SliderKt.getTrackHeight());
        long sliderStart2 = sliderEnd;
        long sliderStart3 = sliderStart;
        DrawScope.m4282drawLineNGM6Ib0$default($this$drawTrack_u2dLUBghH0, inactiveTrackColor, sliderStart, sliderEnd, trackStrokeWidth, StrokeCap.INSTANCE.m4099getRoundKaPHkGw(), null, 0.0f, null, 0, 480, null);
        long sliderValueEnd = OffsetKt.Offset(Offset.m3505getXimpl(sliderStart3) + ((Offset.m3505getXimpl(sliderStart2) - Offset.m3505getXimpl(sliderStart3)) * activeRangeEnd), Offset.m3506getYimpl($this$drawTrack_u2dLUBghH0.mo4294getCenterF1C5BW0()));
        long sliderValueStart = OffsetKt.Offset(Offset.m3505getXimpl(sliderStart3) + ((Offset.m3505getXimpl(sliderStart2) - Offset.m3505getXimpl(sliderStart3)) * activeRangeStart), Offset.m3506getYimpl($this$drawTrack_u2dLUBghH0.mo4294getCenterF1C5BW0()));
        DrawScope.m4282drawLineNGM6Ib0$default($this$drawTrack_u2dLUBghH0, activeTrackColor, sliderValueStart, sliderValueEnd, trackStrokeWidth, StrokeCap.INSTANCE.m4099getRoundKaPHkGw(), null, 0.0f, null, 0, 480, null);
        int length = tickFractions.length;
        int i = 0;
        while (i < length) {
            float tick = tickFractions[i];
            boolean outsideFraction = tick > activeRangeEnd || tick < activeRangeStart;
            long sliderStart4 = sliderStart3;
            long sliderEnd2 = sliderStart2;
            DrawScope.m4277drawCircleVaOC9Bg$default($this$drawTrack_u2dLUBghH0, outsideFraction ? inactiveTickColor : activeTickColor, tickSize / 2.0f, OffsetKt.Offset(Offset.m3505getXimpl(OffsetKt.m3528lerpWko1d7g(sliderStart4, sliderEnd2, tick)), Offset.m3506getYimpl($this$drawTrack_u2dLUBghH0.mo4294getCenterF1C5BW0())), 0.0f, null, null, 0, 120, null);
            i++;
            sliderStart3 = sliderStart4;
            sliderStart2 = sliderEnd2;
        }
    }
}
