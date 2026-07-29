package androidx.compose.material3;

import androidx.compose.animation.AnimatedVisibilityKt;
import androidx.compose.animation.AnimatedVisibilityScope;
import androidx.compose.animation.CrossfadeKt;
import androidx.compose.animation.EnterExitTransitionKt;
import androidx.compose.animation.ExitTransition;
import androidx.compose.animation.core.AnimationSpecKt;
import androidx.compose.animation.core.FiniteAnimationSpec;
import androidx.compose.foundation.BorderStroke;
import androidx.compose.foundation.BorderStrokeKt;
import androidx.compose.foundation.layout.SizeKt;
import androidx.compose.foundation.shape.CornerBasedShape;
import androidx.compose.material.icons.Icons;
import androidx.compose.material.icons.filled.CheckKt;
import androidx.compose.material3.tokens.OutlinedSegmentedButtonTokens;
import androidx.compose.runtime.Composer;
import androidx.compose.runtime.ComposerKt;
import androidx.compose.runtime.RecomposeScopeImplKt;
import androidx.compose.runtime.ScopeUpdateScope;
import androidx.compose.runtime.internal.ComposableLambdaKt;
import androidx.compose.ui.Modifier;
import androidx.compose.ui.graphics.Color;
import androidx.compose.ui.graphics.RectangleShapeKt;
import androidx.compose.ui.graphics.Shape;
import androidx.compose.ui.graphics.TransformOriginKt;
import androidx.profileinstaller.ProfileVerifier;
import kotlin.Metadata;
import kotlin.Unit;
import kotlin.jvm.functions.Function2;
import kotlin.jvm.functions.Function3;
import kotlin.jvm.internal.Intrinsics;

/* compiled from: SegmentedButton.kt */
@Metadata(d1 = {"\u0000^\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\b\u0006\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0010\u0002\n\u0002\b\u0003\n\u0002\u0010\u000b\n\u0000\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0014\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010\b\n\u0002\b\u0003\bÇ\u0002\u0018\u00002\u00020\u0001B\u0007\b\u0002¢\u0006\u0002\u0010\u0002J\r\u0010\u0013\u001a\u00020\u0014H\u0007¢\u0006\u0002\u0010\u0015JA\u0010\u0016\u001a\u00020\u00142\u0006\u0010\u0017\u001a\u00020\u00182\u0013\b\u0002\u0010\u0019\u001a\r\u0012\u0004\u0012\u00020\u00140\u001a¢\u0006\u0002\b\u001b2\u0015\b\u0002\u0010\u001c\u001a\u000f\u0012\u0004\u0012\u00020\u0014\u0018\u00010\u001a¢\u0006\u0002\b\u001bH\u0007¢\u0006\u0002\u0010\u001dJ\"\u0010\u001e\u001a\u00020\u001f2\u0006\u0010 \u001a\u00020!2\b\b\u0002\u0010\"\u001a\u00020\u0004ø\u0001\u0000¢\u0006\u0004\b#\u0010$J\r\u0010%\u001a\u00020\u000fH\u0007¢\u0006\u0002\u0010&J\u008a\u0001\u0010%\u001a\u00020\u000f2\b\b\u0002\u0010'\u001a\u00020!2\b\b\u0002\u0010(\u001a\u00020!2\b\b\u0002\u0010)\u001a\u00020!2\b\b\u0002\u0010*\u001a\u00020!2\b\b\u0002\u0010+\u001a\u00020!2\b\b\u0002\u0010,\u001a\u00020!2\b\b\u0002\u0010-\u001a\u00020!2\b\b\u0002\u0010.\u001a\u00020!2\b\b\u0002\u0010/\u001a\u00020!2\b\b\u0002\u00100\u001a\u00020!2\b\b\u0002\u00101\u001a\u00020!2\b\b\u0002\u00102\u001a\u00020!H\u0007ø\u0001\u0000¢\u0006\u0004\b3\u00104J'\u00105\u001a\u0002062\u0006\u00107\u001a\u0002082\u0006\u00109\u001a\u0002082\b\b\u0002\u0010\n\u001a\u00020\u000bH\u0007¢\u0006\u0002\u0010:R\u0019\u0010\u0003\u001a\u00020\u0004ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u0010\u0007\u001a\u0004\b\u0005\u0010\u0006R\u0019\u0010\b\u001a\u00020\u0004ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u0010\u0007\u001a\u0004\b\t\u0010\u0006R\u0011\u0010\n\u001a\u00020\u000b8G¢\u0006\u0006\u001a\u0004\b\f\u0010\rR\u0018\u0010\u000e\u001a\u00020\u000f*\u00020\u00108@X\u0080\u0004¢\u0006\u0006\u001a\u0004\b\u0011\u0010\u0012\u0082\u0002\u000b\n\u0005\b¡\u001e0\u0001\n\u0002\b!¨\u0006;"}, d2 = {"Landroidx/compose/material3/SegmentedButtonDefaults;", "", "()V", "BorderWidth", "Landroidx/compose/ui/unit/Dp;", "getBorderWidth-D9Ej5fM", "()F", "F", "IconSize", "getIconSize-D9Ej5fM", "baseShape", "Landroidx/compose/foundation/shape/CornerBasedShape;", "getBaseShape", "(Landroidx/compose/runtime/Composer;I)Landroidx/compose/foundation/shape/CornerBasedShape;", "defaultSegmentedButtonColors", "Landroidx/compose/material3/SegmentedButtonColors;", "Landroidx/compose/material3/ColorScheme;", "getDefaultSegmentedButtonColors$material3_release", "(Landroidx/compose/material3/ColorScheme;)Landroidx/compose/material3/SegmentedButtonColors;", "ActiveIcon", "", "(Landroidx/compose/runtime/Composer;I)V", "Icon", "active", "", "activeContent", "Lkotlin/Function0;", "Landroidx/compose/runtime/Composable;", "inactiveContent", "(ZLkotlin/jvm/functions/Function2;Lkotlin/jvm/functions/Function2;Landroidx/compose/runtime/Composer;II)V", "borderStroke", "Landroidx/compose/foundation/BorderStroke;", "color", "Landroidx/compose/ui/graphics/Color;", "width", "borderStroke-l07J4OM", "(JF)Landroidx/compose/foundation/BorderStroke;", "colors", "(Landroidx/compose/runtime/Composer;I)Landroidx/compose/material3/SegmentedButtonColors;", "activeContainerColor", "activeContentColor", "activeBorderColor", "inactiveContainerColor", "inactiveContentColor", "inactiveBorderColor", "disabledActiveContainerColor", "disabledActiveContentColor", "disabledActiveBorderColor", "disabledInactiveContainerColor", "disabledInactiveContentColor", "disabledInactiveBorderColor", "colors-XqyqHi0", "(JJJJJJJJJJJJLandroidx/compose/runtime/Composer;III)Landroidx/compose/material3/SegmentedButtonColors;", "itemShape", "Landroidx/compose/ui/graphics/Shape;", "index", "", "count", "(IILandroidx/compose/foundation/shape/CornerBasedShape;Landroidx/compose/runtime/Composer;II)Landroidx/compose/ui/graphics/Shape;", "material3_release"}, k = 1, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class SegmentedButtonDefaults {
    public static final int $stable = 0;
    public static final SegmentedButtonDefaults INSTANCE = new SegmentedButtonDefaults();
    private static final float BorderWidth = OutlinedSegmentedButtonTokens.INSTANCE.m3003getOutlineWidthD9Ej5fM();
    private static final float IconSize = OutlinedSegmentedButtonTokens.INSTANCE.m3002getIconSizeD9Ej5fM();

    private SegmentedButtonDefaults() {
    }

    public final SegmentedButtonColors colors(Composer $composer, int $changed) {
        $composer.startReplaceableGroup(679457321);
        ComposerKt.sourceInformation($composer, "C(colors)438@18578L11:SegmentedButton.kt#uh7d8r");
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventStart(679457321, $changed, -1, "androidx.compose.material3.SegmentedButtonDefaults.colors (SegmentedButton.kt:438)");
        }
        SegmentedButtonColors defaultSegmentedButtonColors$material3_release = getDefaultSegmentedButtonColors$material3_release(MaterialTheme.INSTANCE.getColorScheme($composer, 6));
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventEnd();
        }
        $composer.endReplaceableGroup();
        return defaultSegmentedButtonColors$material3_release;
    }

    /* renamed from: colors-XqyqHi0, reason: not valid java name */
    public final SegmentedButtonColors m2161colorsXqyqHi0(long activeContainerColor, long activeContentColor, long activeBorderColor, long inactiveContainerColor, long inactiveContentColor, long inactiveBorderColor, long disabledActiveContainerColor, long disabledActiveContentColor, long disabledActiveBorderColor, long disabledInactiveContainerColor, long disabledInactiveContentColor, long disabledInactiveBorderColor, Composer $composer, int $changed, int $changed1, int i) {
        $composer.startReplaceableGroup(132526205);
        ComposerKt.sourceInformation($composer, "C(colors)P(1:c#ui.graphics.Color,2:c#ui.graphics.Color,0:c#ui.graphics.Color,10:c#ui.graphics.Color,11:c#ui.graphics.Color,9:c#ui.graphics.Color,4:c#ui.graphics.Color,5:c#ui.graphics.Color,3:c#ui.graphics.Color,7:c#ui.graphics.Color,8:c#ui.graphics.Color,6:c#ui.graphics.Color)474@20740L11:SegmentedButton.kt#uh7d8r");
        long activeContainerColor2 = (i & 1) != 0 ? Color.INSTANCE.m3782getUnspecified0d7_KjU() : activeContainerColor;
        long activeContentColor2 = (i & 2) != 0 ? Color.INSTANCE.m3782getUnspecified0d7_KjU() : activeContentColor;
        long activeBorderColor2 = (i & 4) != 0 ? Color.INSTANCE.m3782getUnspecified0d7_KjU() : activeBorderColor;
        long inactiveContainerColor2 = (i & 8) != 0 ? Color.INSTANCE.m3782getUnspecified0d7_KjU() : inactiveContainerColor;
        long inactiveContentColor2 = (i & 16) != 0 ? Color.INSTANCE.m3782getUnspecified0d7_KjU() : inactiveContentColor;
        long inactiveBorderColor2 = (i & 32) != 0 ? Color.INSTANCE.m3782getUnspecified0d7_KjU() : inactiveBorderColor;
        long disabledActiveContainerColor2 = (i & 64) != 0 ? Color.INSTANCE.m3782getUnspecified0d7_KjU() : disabledActiveContainerColor;
        long disabledActiveContentColor2 = (i & 128) != 0 ? Color.INSTANCE.m3782getUnspecified0d7_KjU() : disabledActiveContentColor;
        long disabledActiveBorderColor2 = (i & 256) != 0 ? Color.INSTANCE.m3782getUnspecified0d7_KjU() : disabledActiveBorderColor;
        long disabledInactiveContainerColor2 = (i & 512) != 0 ? Color.INSTANCE.m3782getUnspecified0d7_KjU() : disabledInactiveContainerColor;
        long disabledInactiveContentColor2 = (i & 1024) != 0 ? Color.INSTANCE.m3782getUnspecified0d7_KjU() : disabledInactiveContentColor;
        long disabledInactiveBorderColor2 = (i & 2048) != 0 ? Color.INSTANCE.m3782getUnspecified0d7_KjU() : disabledInactiveBorderColor;
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventStart(132526205, $changed, $changed1, "androidx.compose.material3.SegmentedButtonDefaults.colors (SegmentedButton.kt:474)");
        }
        SegmentedButtonColors m2146copy2qZNXz8 = getDefaultSegmentedButtonColors$material3_release(MaterialTheme.INSTANCE.getColorScheme($composer, 6)).m2146copy2qZNXz8(activeContainerColor2, activeContentColor2, activeBorderColor2, inactiveContainerColor2, inactiveContentColor2, inactiveBorderColor2, disabledActiveContainerColor2, disabledActiveContentColor2, disabledActiveBorderColor2, disabledInactiveContainerColor2, disabledInactiveContentColor2, disabledInactiveBorderColor2);
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventEnd();
        }
        $composer.endReplaceableGroup();
        return m2146copy2qZNXz8;
    }

    public final SegmentedButtonColors getDefaultSegmentedButtonColors$material3_release(ColorScheme $this$defaultSegmentedButtonColors) {
        long m3744copywmQWz5c;
        long m3744copywmQWz5c2;
        SegmentedButtonColors defaultSegmentedButtonColorsCached = $this$defaultSegmentedButtonColors.getDefaultSegmentedButtonColorsCached();
        if (defaultSegmentedButtonColorsCached == null) {
            long fromToken = ColorSchemeKt.fromToken($this$defaultSegmentedButtonColors, OutlinedSegmentedButtonTokens.INSTANCE.getSelectedContainerColor());
            long fromToken2 = ColorSchemeKt.fromToken($this$defaultSegmentedButtonColors, OutlinedSegmentedButtonTokens.INSTANCE.getSelectedLabelTextColor());
            long fromToken3 = ColorSchemeKt.fromToken($this$defaultSegmentedButtonColors, OutlinedSegmentedButtonTokens.INSTANCE.getOutlineColor());
            long surface = $this$defaultSegmentedButtonColors.getSurface();
            long fromToken4 = ColorSchemeKt.fromToken($this$defaultSegmentedButtonColors, OutlinedSegmentedButtonTokens.INSTANCE.getUnselectedLabelTextColor());
            long fromToken5 = ColorSchemeKt.fromToken($this$defaultSegmentedButtonColors, OutlinedSegmentedButtonTokens.INSTANCE.getOutlineColor());
            long fromToken6 = ColorSchemeKt.fromToken($this$defaultSegmentedButtonColors, OutlinedSegmentedButtonTokens.INSTANCE.getSelectedContainerColor());
            m3744copywmQWz5c = Color.m3744copywmQWz5c(r17, (r12 & 1) != 0 ? Color.m3748getAlphaimpl(r17) : OutlinedSegmentedButtonTokens.INSTANCE.getDisabledLabelTextOpacity(), (r12 & 2) != 0 ? Color.m3752getRedimpl(r17) : 0.0f, (r12 & 4) != 0 ? Color.m3751getGreenimpl(r17) : 0.0f, (r12 & 8) != 0 ? Color.m3749getBlueimpl(ColorSchemeKt.fromToken($this$defaultSegmentedButtonColors, OutlinedSegmentedButtonTokens.INSTANCE.getDisabledLabelTextColor())) : 0.0f);
            m3744copywmQWz5c2 = Color.m3744copywmQWz5c(r19, (r12 & 1) != 0 ? Color.m3748getAlphaimpl(r19) : OutlinedSegmentedButtonTokens.INSTANCE.getDisabledOutlineOpacity(), (r12 & 2) != 0 ? Color.m3752getRedimpl(r19) : 0.0f, (r12 & 4) != 0 ? Color.m3751getGreenimpl(r19) : 0.0f, (r12 & 8) != 0 ? Color.m3749getBlueimpl(ColorSchemeKt.fromToken($this$defaultSegmentedButtonColors, OutlinedSegmentedButtonTokens.INSTANCE.getOutlineColor())) : 0.0f);
            SegmentedButtonColors it = new SegmentedButtonColors(fromToken, fromToken2, fromToken3, surface, fromToken4, fromToken5, fromToken6, m3744copywmQWz5c, m3744copywmQWz5c2, $this$defaultSegmentedButtonColors.getSurface(), ColorSchemeKt.fromToken($this$defaultSegmentedButtonColors, OutlinedSegmentedButtonTokens.INSTANCE.getDisabledLabelTextColor()), ColorSchemeKt.fromToken($this$defaultSegmentedButtonColors, OutlinedSegmentedButtonTokens.INSTANCE.getOutlineColor()), null);
            $this$defaultSegmentedButtonColors.setDefaultSegmentedButtonColorsCached$material3_release(it);
            return it;
        }
        return defaultSegmentedButtonColorsCached;
    }

    public final CornerBasedShape getBaseShape(Composer $composer, int $changed) {
        ComposerKt.sourceInformationMarkerStart($composer, 1264240381, "C518@23091L5:SegmentedButton.kt#uh7d8r");
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventStart(1264240381, $changed, -1, "androidx.compose.material3.SegmentedButtonDefaults.<get-baseShape> (SegmentedButton.kt:518)");
        }
        Shape value = ShapesKt.getValue(OutlinedSegmentedButtonTokens.INSTANCE.getShape(), $composer, 6);
        Intrinsics.checkNotNull(value, "null cannot be cast to non-null type androidx.compose.foundation.shape.CornerBasedShape");
        CornerBasedShape cornerBasedShape = (CornerBasedShape) value;
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventEnd();
        }
        ComposerKt.sourceInformationMarkerEnd($composer);
        return cornerBasedShape;
    }

    /* renamed from: getBorderWidth-D9Ej5fM, reason: not valid java name */
    public final float m2162getBorderWidthD9Ej5fM() {
        return BorderWidth;
    }

    public final Shape itemShape(int index, int count, CornerBasedShape baseShape, Composer $composer, int $changed, int i) {
        CornerBasedShape end;
        ComposerKt.sourceInformationMarkerStart($composer, -942072063, "C(itemShape)P(2,1)534@23755L9:SegmentedButton.kt#uh7d8r");
        if ((i & 4) != 0) {
            baseShape = getBaseShape($composer, ($changed >> 9) & 14);
        }
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventStart(-942072063, $changed, -1, "androidx.compose.material3.SegmentedButtonDefaults.itemShape (SegmentedButton.kt:534)");
        }
        if (count == 1) {
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventEnd();
            }
            ComposerKt.sourceInformationMarkerEnd($composer);
            return baseShape;
        }
        if (index == 0) {
            end = ShapesKt.start(baseShape);
        } else {
            end = index == count + (-1) ? ShapesKt.end(baseShape) : RectangleShapeKt.getRectangleShape();
        }
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventEnd();
        }
        ComposerKt.sourceInformationMarkerEnd($composer);
        return end;
    }

    /* renamed from: getIconSize-D9Ej5fM, reason: not valid java name */
    public final float m2163getIconSizeD9Ej5fM() {
        return IconSize;
    }

    public final void ActiveIcon(Composer $composer, final int $changed) {
        Composer $composer2 = $composer.startRestartGroup(-1273041460);
        ComposerKt.sourceInformation($composer2, "C(ActiveIcon)554@24257L147:SegmentedButton.kt#uh7d8r");
        int $dirty = $changed;
        if (($changed & 6) == 0) {
            $dirty |= $composer2.changed(this) ? 4 : 2;
        }
        int $dirty2 = $dirty;
        if (($dirty2 & 3) != 2 || !$composer2.getSkipping()) {
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventStart(-1273041460, $dirty2, -1, "androidx.compose.material3.SegmentedButtonDefaults.ActiveIcon (SegmentedButton.kt:553)");
            }
            IconKt.m1937Iconww6aTOc(CheckKt.getCheck(Icons.Filled.INSTANCE), (String) null, SizeKt.m611size3ABfNKs(Modifier.INSTANCE, IconSize), 0L, $composer2, 48, 8);
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventEnd();
            }
        } else {
            $composer2.skipToGroupEnd();
        }
        ScopeUpdateScope endRestartGroup = $composer2.endRestartGroup();
        if (endRestartGroup != null) {
            endRestartGroup.updateScope(new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.SegmentedButtonDefaults$ActiveIcon$1
                /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
                {
                    super(2);
                }

                @Override // kotlin.jvm.functions.Function2
                public /* bridge */ /* synthetic */ Unit invoke(Composer composer, Integer num) {
                    invoke(composer, num.intValue());
                    return Unit.INSTANCE;
                }

                public final void invoke(Composer composer, int i) {
                    SegmentedButtonDefaults.this.ActiveIcon(composer, RecomposeScopeImplKt.updateChangedFlags($changed | 1));
                }
            });
        }
    }

    public final void Icon(final boolean active, Function2<? super Composer, ? super Integer, Unit> function2, Function2<? super Composer, ? super Integer, Unit> function22, Composer $composer, final int $changed, final int i) {
        Function2 function23;
        Function2 inactiveContent;
        int $dirty;
        Function2 activeContent;
        Composer $composer2 = $composer.startRestartGroup(683517296);
        ComposerKt.sourceInformation($composer2, "C(Icon):SegmentedButton.kt#uh7d8r");
        int $dirty2 = $changed;
        if ((i & 1) != 0) {
            $dirty2 |= 6;
        } else if (($changed & 6) == 0) {
            $dirty2 |= $composer2.changed(active) ? 4 : 2;
        }
        int i2 = i & 2;
        if (i2 != 0) {
            $dirty2 |= 48;
            function23 = function2;
        } else if (($changed & 48) == 0) {
            function23 = function2;
            $dirty2 |= $composer2.changedInstance(function23) ? 32 : 16;
        } else {
            function23 = function2;
        }
        int i3 = i & 4;
        if (i3 != 0) {
            $dirty2 |= 384;
            inactiveContent = function22;
        } else if (($changed & 384) == 0) {
            inactiveContent = function22;
            $dirty2 |= $composer2.changedInstance(inactiveContent) ? 256 : 128;
        } else {
            inactiveContent = function22;
        }
        if (($dirty2 & 147) == 146 && $composer2.getSkipping()) {
            $composer2.skipToGroupEnd();
            $dirty = $dirty2;
            activeContent = function23;
        } else {
            final Function2 activeContent2 = i2 != 0 ? ComposableSingletons$SegmentedButtonKt.INSTANCE.m1772getLambda1$material3_release() : function23;
            final Function2 inactiveContent2 = i3 != 0 ? null : inactiveContent;
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventStart(683517296, $dirty2, -1, "androidx.compose.material3.SegmentedButtonDefaults.Icon (SegmentedButton.kt:574)");
            }
            if (inactiveContent2 == null) {
                $composer2.startReplaceableGroup(-905565055);
                ComposerKt.sourceInformation($composer2, "576@24995L448");
                $dirty = $dirty2;
                AnimatedVisibilityKt.AnimatedVisibility(active, (Modifier) null, EnterExitTransitionKt.fadeIn$default(AnimationSpecKt.tween$default(350, 0, null, 6, null), 0.0f, 2, null).plus(EnterExitTransitionKt.m72scaleInL8ZKhE(AnimationSpecKt.tween$default(350, 0, null, 6, null), 0.0f, TransformOriginKt.TransformOrigin(0.0f, 1.0f))), ExitTransition.INSTANCE.getNone(), (String) null, ComposableLambdaKt.composableLambda($composer2, -750750819, true, new Function3<AnimatedVisibilityScope, Composer, Integer, Unit>() { // from class: androidx.compose.material3.SegmentedButtonDefaults$Icon$1
                    /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
                    /* JADX WARN: Multi-variable type inference failed */
                    {
                        super(3);
                    }

                    @Override // kotlin.jvm.functions.Function3
                    public /* bridge */ /* synthetic */ Unit invoke(AnimatedVisibilityScope animatedVisibilityScope, Composer composer, Integer num) {
                        invoke(animatedVisibilityScope, composer, num.intValue());
                        return Unit.INSTANCE;
                    }

                    public final void invoke(AnimatedVisibilityScope $this$AnimatedVisibility, Composer $composer3, int $changed2) {
                        ComposerKt.sourceInformation($composer3, "C585@25414L15:SegmentedButton.kt#uh7d8r");
                        if (ComposerKt.isTraceInProgress()) {
                            ComposerKt.traceEventStart(-750750819, $changed2, -1, "androidx.compose.material3.SegmentedButtonDefaults.Icon.<anonymous> (SegmentedButton.kt:585)");
                        }
                        activeContent2.invoke($composer3, 0);
                        if (ComposerKt.isTraceInProgress()) {
                            ComposerKt.traceEventEnd();
                        }
                    }
                }), $composer2, ($dirty & 14) | ProfileVerifier.CompilationStatus.RESULT_CODE_ERROR_CANT_WRITE_PROFILE_VERIFICATION_RESULT_CACHE_FILE, 18);
                $composer2.endReplaceableGroup();
            } else {
                $dirty = $dirty2;
                $composer2.startReplaceableGroup(-905564577);
                ComposerKt.sourceInformation($composer2, "588@25473L110");
                CrossfadeKt.Crossfade(Boolean.valueOf(active), (Modifier) null, (FiniteAnimationSpec<Float>) null, (String) null, ComposableLambdaKt.composableLambda($composer2, -1364873619, true, new Function3<Boolean, Composer, Integer, Unit>() { // from class: androidx.compose.material3.SegmentedButtonDefaults$Icon$2
                    /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
                    /* JADX WARN: Multi-variable type inference failed */
                    {
                        super(3);
                    }

                    @Override // kotlin.jvm.functions.Function3
                    public /* bridge */ /* synthetic */ Unit invoke(Boolean bool, Composer composer, Integer num) {
                        invoke(bool.booleanValue(), composer, num.intValue());
                        return Unit.INSTANCE;
                    }

                    public final void invoke(boolean it, Composer $composer3, int $changed2) {
                        Function2<Composer, Integer, Unit> function24;
                        ComposerKt.sourceInformation($composer3, "C:SegmentedButton.kt#uh7d8r");
                        int $dirty3 = $changed2;
                        if (($changed2 & 6) == 0) {
                            $dirty3 |= $composer3.changed(it) ? 4 : 2;
                        }
                        if (($dirty3 & 19) == 18 && $composer3.getSkipping()) {
                            $composer3.skipToGroupEnd();
                            return;
                        }
                        if (ComposerKt.isTraceInProgress()) {
                            ComposerKt.traceEventStart(-1364873619, $dirty3, -1, "androidx.compose.material3.SegmentedButtonDefaults.Icon.<anonymous> (SegmentedButton.kt:589)");
                        }
                        if (it) {
                            $composer3.startReplaceableGroup(-412602680);
                            ComposerKt.sourceInformation($composer3, "589@25531L15");
                            function24 = activeContent2;
                        } else {
                            $composer3.startReplaceableGroup(-412602659);
                            ComposerKt.sourceInformation($composer3, "589@25552L17");
                            function24 = inactiveContent2;
                        }
                        function24.invoke($composer3, 0);
                        $composer3.endReplaceableGroup();
                        if (ComposerKt.isTraceInProgress()) {
                            ComposerKt.traceEventEnd();
                        }
                    }
                }), $composer2, ($dirty & 14) | 24576, 14);
                $composer2.endReplaceableGroup();
            }
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventEnd();
            }
            activeContent = activeContent2;
            inactiveContent = inactiveContent2;
        }
        ScopeUpdateScope endRestartGroup = $composer2.endRestartGroup();
        if (endRestartGroup != null) {
            final Function2 function24 = activeContent;
            final Function2 function25 = inactiveContent;
            endRestartGroup.updateScope(new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.SegmentedButtonDefaults$Icon$3
                /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
                /* JADX WARN: Multi-variable type inference failed */
                {
                    super(2);
                }

                @Override // kotlin.jvm.functions.Function2
                public /* bridge */ /* synthetic */ Unit invoke(Composer composer, Integer num) {
                    invoke(composer, num.intValue());
                    return Unit.INSTANCE;
                }

                public final void invoke(Composer composer, int i4) {
                    SegmentedButtonDefaults.this.Icon(active, function24, function25, composer, RecomposeScopeImplKt.updateChangedFlags($changed | 1), i);
                }
            });
        }
    }

    /* renamed from: borderStroke-l07J4OM$default, reason: not valid java name */
    public static /* synthetic */ BorderStroke m2159borderStrokel07J4OM$default(SegmentedButtonDefaults segmentedButtonDefaults, long j, float f, int i, Object obj) {
        if ((i & 2) != 0) {
            f = BorderWidth;
        }
        return segmentedButtonDefaults.m2160borderStrokel07J4OM(j, f);
    }

    /* renamed from: borderStroke-l07J4OM, reason: not valid java name */
    public final BorderStroke m2160borderStrokel07J4OM(long color, float width) {
        return BorderStrokeKt.m237BorderStrokecXLIe8U(width, color);
    }
}
