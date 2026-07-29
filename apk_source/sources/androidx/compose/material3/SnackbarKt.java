package androidx.compose.material3;

import androidx.compose.foundation.layout.PaddingKt;
import androidx.compose.foundation.layout.RowScope;
import androidx.compose.material3.tokens.SnackbarTokens;
import androidx.compose.runtime.Composer;
import androidx.compose.runtime.ComposerKt;
import androidx.compose.runtime.CompositionLocalKt;
import androidx.compose.runtime.ProvidedValue;
import androidx.compose.runtime.RecomposeScopeImplKt;
import androidx.compose.runtime.ScopeUpdateScope;
import androidx.compose.runtime.internal.ComposableLambdaKt;
import androidx.compose.ui.Modifier;
import androidx.compose.ui.graphics.Shape;
import androidx.compose.ui.text.TextLayoutResult;
import androidx.compose.ui.text.TextStyle;
import androidx.compose.ui.text.font.FontFamily;
import androidx.compose.ui.text.font.FontStyle;
import androidx.compose.ui.text.font.FontWeight;
import androidx.compose.ui.text.style.TextAlign;
import androidx.compose.ui.text.style.TextDecoration;
import androidx.compose.ui.unit.Dp;
import androidx.core.view.accessibility.AccessibilityEventCompat;
import androidx.profileinstaller.ProfileVerifier;
import kotlin.Metadata;
import kotlin.Unit;
import kotlin.jvm.functions.Function0;
import kotlin.jvm.functions.Function1;
import kotlin.jvm.functions.Function2;
import kotlin.jvm.functions.Function3;

/* compiled from: Snackbar.kt */
@Metadata(d1 = {"\u0000D\n\u0000\n\u0002\u0018\u0002\n\u0002\b\t\n\u0002\u0010\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\t\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010\u000b\n\u0000\n\u0002\u0018\u0002\n\u0002\b\t\u001ae\u0010\n\u001a\u00020\u000b2\u0011\u0010\f\u001a\r\u0012\u0004\u0012\u00020\u000b0\r¢\u0006\u0002\b\u000e2\u0011\u0010\u000f\u001a\r\u0012\u0004\u0012\u00020\u000b0\r¢\u0006\u0002\b\u000e2\u0013\u0010\u0010\u001a\u000f\u0012\u0004\u0012\u00020\u000b\u0018\u00010\r¢\u0006\u0002\b\u000e2\u0006\u0010\u0011\u001a\u00020\u00122\u0006\u0010\u0013\u001a\u00020\u00142\u0006\u0010\u0015\u001a\u00020\u0014H\u0003ø\u0001\u0000¢\u0006\u0004\b\u0016\u0010\u0017\u001ag\u0010\u0018\u001a\u00020\u000b2\u0011\u0010\f\u001a\r\u0012\u0004\u0012\u00020\u000b0\r¢\u0006\u0002\b\u000e2\u0013\u0010\u000f\u001a\u000f\u0012\u0004\u0012\u00020\u000b\u0018\u00010\r¢\u0006\u0002\b\u000e2\u0013\u0010\u0010\u001a\u000f\u0012\u0004\u0012\u00020\u000b\u0018\u00010\r¢\u0006\u0002\b\u000e2\u0006\u0010\u0011\u001a\u00020\u00122\u0006\u0010\u0019\u001a\u00020\u00142\u0006\u0010\u001a\u001a\u00020\u0014H\u0003ø\u0001\u0000¢\u0006\u0004\b\u001b\u0010\u0017\u001aj\u0010\u001c\u001a\u00020\u000b2\u0006\u0010\u001d\u001a\u00020\u001e2\b\b\u0002\u0010\u001f\u001a\u00020 2\b\b\u0002\u0010!\u001a\u00020\"2\b\b\u0002\u0010#\u001a\u00020$2\b\b\u0002\u0010%\u001a\u00020\u00142\b\b\u0002\u0010&\u001a\u00020\u00142\b\b\u0002\u0010'\u001a\u00020\u00142\b\b\u0002\u0010\u0013\u001a\u00020\u00142\b\b\u0002\u0010\u0015\u001a\u00020\u0014H\u0007ø\u0001\u0000¢\u0006\u0004\b(\u0010)\u001a\u0099\u0001\u0010\u001c\u001a\u00020\u000b2\b\b\u0002\u0010\u001f\u001a\u00020 2\u0015\b\u0002\u0010\u000f\u001a\u000f\u0012\u0004\u0012\u00020\u000b\u0018\u00010\r¢\u0006\u0002\b\u000e2\u0015\b\u0002\u0010\u0010\u001a\u000f\u0012\u0004\u0012\u00020\u000b\u0018\u00010\r¢\u0006\u0002\b\u000e2\b\b\u0002\u0010!\u001a\u00020\"2\b\b\u0002\u0010#\u001a\u00020$2\b\b\u0002\u0010%\u001a\u00020\u00142\b\b\u0002\u0010&\u001a\u00020\u00142\b\b\u0002\u0010\u0013\u001a\u00020\u00142\b\b\u0002\u0010\u0015\u001a\u00020\u00142\u0011\u0010*\u001a\r\u0012\u0004\u0012\u00020\u000b0\r¢\u0006\u0002\b\u000eH\u0007ø\u0001\u0000¢\u0006\u0004\b+\u0010,\"\u0010\u0010\u0000\u001a\u00020\u0001X\u0082\u0004¢\u0006\u0004\n\u0002\u0010\u0002\"\u0010\u0010\u0003\u001a\u00020\u0001X\u0082\u0004¢\u0006\u0004\n\u0002\u0010\u0002\"\u0010\u0010\u0004\u001a\u00020\u0001X\u0082\u0004¢\u0006\u0004\n\u0002\u0010\u0002\"\u0010\u0010\u0005\u001a\u00020\u0001X\u0082\u0004¢\u0006\u0004\n\u0002\u0010\u0002\"\u0010\u0010\u0006\u001a\u00020\u0001X\u0082\u0004¢\u0006\u0004\n\u0002\u0010\u0002\"\u0010\u0010\u0007\u001a\u00020\u0001X\u0082\u0004¢\u0006\u0004\n\u0002\u0010\u0002\"\u0010\u0010\b\u001a\u00020\u0001X\u0082\u0004¢\u0006\u0004\n\u0002\u0010\u0002\"\u0010\u0010\t\u001a\u00020\u0001X\u0082\u0004¢\u0006\u0004\n\u0002\u0010\u0002\u0082\u0002\u0007\n\u0005\b¡\u001e0\u0001¨\u0006-"}, d2 = {"ContainerMaxWidth", "Landroidx/compose/ui/unit/Dp;", "F", "HeightToFirstLine", "HorizontalSpacing", "HorizontalSpacingButtonSide", "LongButtonVerticalOffset", "SeparateButtonExtraY", "SnackbarVerticalPadding", "TextEndExtraSpacing", "NewLineButtonSnackbar", "", "text", "Lkotlin/Function0;", "Landroidx/compose/runtime/Composable;", "action", "dismissAction", "actionTextStyle", "Landroidx/compose/ui/text/TextStyle;", "actionContentColor", "Landroidx/compose/ui/graphics/Color;", "dismissActionContentColor", "NewLineButtonSnackbar-kKq0p4A", "(Lkotlin/jvm/functions/Function2;Lkotlin/jvm/functions/Function2;Lkotlin/jvm/functions/Function2;Landroidx/compose/ui/text/TextStyle;JJLandroidx/compose/runtime/Composer;I)V", "OneRowSnackbar", "actionTextColor", "dismissActionColor", "OneRowSnackbar-kKq0p4A", "Snackbar", "snackbarData", "Landroidx/compose/material3/SnackbarData;", "modifier", "Landroidx/compose/ui/Modifier;", "actionOnNewLine", "", "shape", "Landroidx/compose/ui/graphics/Shape;", "containerColor", "contentColor", "actionColor", "Snackbar-sDKtq54", "(Landroidx/compose/material3/SnackbarData;Landroidx/compose/ui/Modifier;ZLandroidx/compose/ui/graphics/Shape;JJJJJLandroidx/compose/runtime/Composer;II)V", "content", "Snackbar-eQBnUkQ", "(Landroidx/compose/ui/Modifier;Lkotlin/jvm/functions/Function2;Lkotlin/jvm/functions/Function2;ZLandroidx/compose/ui/graphics/Shape;JJJJLkotlin/jvm/functions/Function2;Landroidx/compose/runtime/Composer;II)V", "material3_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class SnackbarKt {
    private static final float ContainerMaxWidth = Dp.m6094constructorimpl(600);
    private static final float HeightToFirstLine = Dp.m6094constructorimpl(30);
    private static final float HorizontalSpacing = Dp.m6094constructorimpl(16);
    private static final float HorizontalSpacingButtonSide = Dp.m6094constructorimpl(8);
    private static final float SeparateButtonExtraY = Dp.m6094constructorimpl(2);
    private static final float SnackbarVerticalPadding = Dp.m6094constructorimpl(6);
    private static final float TextEndExtraSpacing = Dp.m6094constructorimpl(8);
    private static final float LongButtonVerticalOffset = Dp.m6094constructorimpl(12);

    /* renamed from: Snackbar-eQBnUkQ, reason: not valid java name */
    public static final void m2232SnackbareQBnUkQ(Modifier modifier, Function2<? super Composer, ? super Integer, Unit> function2, Function2<? super Composer, ? super Integer, Unit> function22, boolean actionOnNewLine, Shape shape, long containerColor, long contentColor, long actionContentColor, long dismissActionContentColor, final Function2<? super Composer, ? super Integer, Unit> function23, Composer $composer, final int $changed, final int i) {
        Modifier modifier2;
        Function2 function24;
        Function2 function25;
        boolean z;
        Shape shape2;
        int $dirty;
        Modifier.Companion modifier3;
        Function2 action;
        Function2 dismissAction;
        boolean actionOnNewLine2;
        Shape shape3;
        long containerColor2;
        long contentColor2;
        long actionContentColor2;
        long dismissActionContentColor2;
        Modifier modifier4;
        long containerColor3;
        long contentColor3;
        long actionContentColor3;
        long dismissActionContentColor3;
        Function2 action2;
        Function2 dismissAction2;
        boolean actionOnNewLine3;
        Shape shape4;
        int i2;
        int i3;
        int i4;
        int $dirty2;
        int i5;
        int i6;
        Composer $composer2 = $composer.startRestartGroup(-1235788955);
        ComposerKt.sourceInformation($composer2, "C(Snackbar)P(8!1,6,2,9,3:c#ui.graphics.Color,5:c#ui.graphics.Color,1:c#ui.graphics.Color,7:c#ui.graphics.Color)101@4932L5,102@4984L5,103@5034L12,104@5097L18,105@5173L25,108@5244L1420:Snackbar.kt#uh7d8r");
        int $dirty3 = $changed;
        int i7 = i & 1;
        if (i7 != 0) {
            $dirty3 |= 6;
            modifier2 = modifier;
        } else if (($changed & 6) == 0) {
            modifier2 = modifier;
            $dirty3 |= $composer2.changed(modifier2) ? 4 : 2;
        } else {
            modifier2 = modifier;
        }
        int i8 = i & 2;
        if (i8 != 0) {
            $dirty3 |= 48;
            function24 = function2;
        } else if (($changed & 48) == 0) {
            function24 = function2;
            $dirty3 |= $composer2.changedInstance(function24) ? 32 : 16;
        } else {
            function24 = function2;
        }
        int i9 = i & 4;
        if (i9 != 0) {
            $dirty3 |= 384;
            function25 = function22;
        } else if (($changed & 384) == 0) {
            function25 = function22;
            $dirty3 |= $composer2.changedInstance(function25) ? 256 : 128;
        } else {
            function25 = function22;
        }
        int i10 = i & 8;
        if (i10 != 0) {
            $dirty3 |= 3072;
            z = actionOnNewLine;
        } else if (($changed & 3072) == 0) {
            z = actionOnNewLine;
            $dirty3 |= $composer2.changed(z) ? 2048 : 1024;
        } else {
            z = actionOnNewLine;
        }
        if (($changed & 24576) == 0) {
            if ((i & 16) == 0) {
                shape2 = shape;
                if ($composer2.changed(shape2)) {
                    i6 = 16384;
                    $dirty3 |= i6;
                }
            } else {
                shape2 = shape;
            }
            i6 = 8192;
            $dirty3 |= i6;
        } else {
            shape2 = shape;
        }
        if ((196608 & $changed) == 0) {
            if ((i & 32) == 0) {
                $dirty2 = $dirty3;
                if ($composer2.changed(containerColor)) {
                    i5 = 131072;
                    $dirty = $dirty2 | i5;
                }
            } else {
                $dirty2 = $dirty3;
            }
            i5 = 65536;
            $dirty = $dirty2 | i5;
        } else {
            $dirty = $dirty3;
        }
        if (($changed & 1572864) == 0) {
            if ((i & 64) == 0 && $composer2.changed(contentColor)) {
                i4 = 1048576;
                $dirty |= i4;
            }
            i4 = 524288;
            $dirty |= i4;
        }
        if (($changed & 12582912) == 0) {
            if ((i & 128) == 0 && $composer2.changed(actionContentColor)) {
                i3 = 8388608;
                $dirty |= i3;
            }
            i3 = 4194304;
            $dirty |= i3;
        }
        if ((100663296 & $changed) == 0) {
            if ((i & 256) == 0 && $composer2.changed(dismissActionContentColor)) {
                i2 = AccessibilityEventCompat.TYPE_VIEW_TARGETED_BY_SCROLL;
                $dirty |= i2;
            }
            i2 = 33554432;
            $dirty |= i2;
        }
        if ((i & 512) != 0) {
            $dirty |= 805306368;
        } else if (($changed & 805306368) == 0) {
            $dirty |= $composer2.changedInstance(function23) ? 536870912 : 268435456;
        }
        if (($dirty & 306783379) == 306783378 && $composer2.getSkipping()) {
            $composer2.skipToGroupEnd();
            containerColor3 = containerColor;
            contentColor3 = contentColor;
            actionContentColor3 = actionContentColor;
            dismissActionContentColor3 = dismissActionContentColor;
            modifier4 = modifier2;
            action2 = function24;
            dismissAction2 = function25;
            actionOnNewLine3 = z;
            shape4 = shape2;
        } else {
            $composer2.startDefaults();
            if (($changed & 1) == 0 || $composer2.getDefaultsInvalid()) {
                modifier3 = i7 != 0 ? Modifier.INSTANCE : modifier2;
                action = i8 != 0 ? null : function24;
                dismissAction = i9 != 0 ? null : function25;
                actionOnNewLine2 = i10 != 0 ? false : z;
                if ((i & 16) != 0) {
                    shape3 = SnackbarDefaults.INSTANCE.getShape($composer2, 6);
                    $dirty &= -57345;
                } else {
                    shape3 = shape2;
                }
                if ((i & 32) != 0) {
                    containerColor2 = SnackbarDefaults.INSTANCE.getColor($composer2, 6);
                    $dirty &= -458753;
                } else {
                    containerColor2 = containerColor;
                }
                if ((i & 64) != 0) {
                    contentColor2 = SnackbarDefaults.INSTANCE.getContentColor($composer2, 6);
                    $dirty &= -3670017;
                } else {
                    contentColor2 = contentColor;
                }
                if ((i & 128) != 0) {
                    actionContentColor2 = SnackbarDefaults.INSTANCE.getActionContentColor($composer2, 6);
                    $dirty &= -29360129;
                } else {
                    actionContentColor2 = actionContentColor;
                }
                if ((i & 256) != 0) {
                    dismissActionContentColor2 = SnackbarDefaults.INSTANCE.getDismissActionContentColor($composer2, 6);
                    $dirty = (-234881025) & $dirty;
                } else {
                    dismissActionContentColor2 = dismissActionContentColor;
                }
            } else {
                $composer2.skipToGroupEnd();
                if ((i & 16) != 0) {
                    $dirty &= -57345;
                }
                if ((i & 32) != 0) {
                    $dirty &= -458753;
                }
                if ((i & 64) != 0) {
                    $dirty &= -3670017;
                }
                if ((i & 128) != 0) {
                    $dirty &= -29360129;
                }
                if ((i & 256) != 0) {
                    actionContentColor2 = actionContentColor;
                    dismissActionContentColor2 = dismissActionContentColor;
                    $dirty &= -234881025;
                    modifier3 = modifier2;
                    action = function24;
                    dismissAction = function25;
                    actionOnNewLine2 = z;
                    shape3 = shape2;
                    containerColor2 = containerColor;
                    contentColor2 = contentColor;
                } else {
                    actionContentColor2 = actionContentColor;
                    dismissActionContentColor2 = dismissActionContentColor;
                    modifier3 = modifier2;
                    action = function24;
                    dismissAction = function25;
                    actionOnNewLine2 = z;
                    shape3 = shape2;
                    containerColor2 = containerColor;
                    contentColor2 = contentColor;
                }
            }
            $composer2.endDefaults();
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventStart(-1235788955, $dirty, -1, "androidx.compose.material3.Snackbar (Snackbar.kt:107)");
            }
            final Function2 function26 = action;
            final Function2 function27 = dismissAction;
            final long j = actionContentColor2;
            final long j2 = dismissActionContentColor2;
            final boolean z2 = actionOnNewLine2;
            Function2 action3 = action;
            SurfaceKt.m2316SurfaceT9BRK9s(modifier3, shape3, containerColor2, contentColor2, 0.0f, SnackbarTokens.INSTANCE.m3136getContainerElevationD9Ej5fM(), null, ComposableLambdaKt.composableLambda($composer2, -1829663446, true, new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.SnackbarKt$Snackbar$1
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

                public final void invoke(Composer $composer3, int $changed2) {
                    ComposerKt.sourceInformation($composer3, "C115@5480L10,116@5580L10,117@5645L1013:Snackbar.kt#uh7d8r");
                    if (($changed2 & 3) != 2 || !$composer3.getSkipping()) {
                        if (ComposerKt.isTraceInProgress()) {
                            ComposerKt.traceEventStart(-1829663446, $changed2, -1, "androidx.compose.material3.Snackbar.<anonymous> (Snackbar.kt:115)");
                        }
                        TextStyle textStyle = TypographyKt.fromToken(MaterialTheme.INSTANCE.getTypography($composer3, 6), SnackbarTokens.INSTANCE.getSupportingTextFont());
                        final TextStyle actionTextStyle = TypographyKt.fromToken(MaterialTheme.INSTANCE.getTypography($composer3, 6), SnackbarTokens.INSTANCE.getActionLabelTextFont());
                        ProvidedValue<TextStyle> provides = TextKt.getLocalTextStyle().provides(textStyle);
                        final Function2<Composer, Integer, Unit> function28 = function26;
                        final Function2<Composer, Integer, Unit> function29 = function23;
                        final Function2<Composer, Integer, Unit> function210 = function27;
                        final long j3 = j;
                        final long j4 = j2;
                        final boolean z3 = z2;
                        CompositionLocalKt.CompositionLocalProvider(provides, ComposableLambdaKt.composableLambda($composer3, 835891690, true, new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.SnackbarKt$Snackbar$1.1
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

                            public final void invoke(Composer $composer4, int $changed3) {
                                ComposerKt.sourceInformation($composer4, "C:Snackbar.kt#uh7d8r");
                                if (($changed3 & 3) != 2 || !$composer4.getSkipping()) {
                                    if (ComposerKt.isTraceInProgress()) {
                                        ComposerKt.traceEventStart(835891690, $changed3, -1, "androidx.compose.material3.Snackbar.<anonymous>.<anonymous> (Snackbar.kt:118)");
                                    }
                                    if (function28 == null) {
                                        $composer4.startReplaceableGroup(-2104362406);
                                        ComposerKt.sourceInformation($composer4, "119@5760L278");
                                        SnackbarKt.m2231OneRowSnackbarkKq0p4A(function29, null, function210, actionTextStyle, j3, j4, $composer4, 48);
                                        $composer4.endReplaceableGroup();
                                    } else if (z3) {
                                        $composer4.startReplaceableGroup(-2104362092);
                                        ComposerKt.sourceInformation($composer4, "127@6074L255");
                                        SnackbarKt.m2230NewLineButtonSnackbarkKq0p4A(function29, function28, function210, actionTextStyle, j3, j4, $composer4, 0);
                                        $composer4.endReplaceableGroup();
                                    } else {
                                        $composer4.startReplaceableGroup(-2104361812);
                                        ComposerKt.sourceInformation($composer4, "135@6354L280");
                                        SnackbarKt.m2231OneRowSnackbarkKq0p4A(function29, function28, function210, actionTextStyle, j3, j4, $composer4, 0);
                                        $composer4.endReplaceableGroup();
                                    }
                                    if (ComposerKt.isTraceInProgress()) {
                                        ComposerKt.traceEventEnd();
                                        return;
                                    }
                                    return;
                                }
                                $composer4.skipToGroupEnd();
                            }
                        }), $composer3, ProvidedValue.$stable | 0 | 48);
                        if (ComposerKt.isTraceInProgress()) {
                            ComposerKt.traceEventEnd();
                            return;
                        }
                        return;
                    }
                    $composer3.skipToGroupEnd();
                }
            }), $composer2, ($dirty & 14) | 12779520 | (($dirty >> 9) & 112) | (($dirty >> 9) & 896) | (($dirty >> 9) & 7168), 80);
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventEnd();
            }
            modifier4 = modifier3;
            containerColor3 = containerColor2;
            contentColor3 = contentColor2;
            actionContentColor3 = actionContentColor2;
            dismissActionContentColor3 = dismissActionContentColor2;
            action2 = action3;
            dismissAction2 = dismissAction;
            actionOnNewLine3 = actionOnNewLine2;
            shape4 = shape3;
        }
        ScopeUpdateScope endRestartGroup = $composer2.endRestartGroup();
        if (endRestartGroup != null) {
            final Modifier modifier5 = modifier4;
            final Function2 function28 = action2;
            final Function2 function29 = dismissAction2;
            final boolean z3 = actionOnNewLine3;
            final Shape shape5 = shape4;
            final long j3 = containerColor3;
            final long j4 = contentColor3;
            final long j5 = actionContentColor3;
            final long j6 = dismissActionContentColor3;
            endRestartGroup.updateScope(new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.SnackbarKt$Snackbar$2
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

                public final void invoke(Composer composer, int i11) {
                    SnackbarKt.m2232SnackbareQBnUkQ(Modifier.this, function28, function29, z3, shape5, j3, j4, j5, j6, function23, composer, RecomposeScopeImplKt.updateChangedFlags($changed | 1), i);
                }
            });
        }
    }

    /* renamed from: Snackbar-sDKtq54, reason: not valid java name */
    public static final void m2233SnackbarsDKtq54(final SnackbarData snackbarData, Modifier modifier, boolean actionOnNewLine, Shape shape, long containerColor, long contentColor, long actionColor, long actionContentColor, long dismissActionContentColor, Composer $composer, final int $changed, final int i) {
        Modifier modifier2;
        boolean z;
        Shape shape2;
        long j;
        long j2;
        int $dirty;
        Modifier.Companion modifier3;
        boolean actionOnNewLine2;
        Shape shape3;
        long containerColor2;
        long contentColor2;
        final long actionColor2;
        long actionContentColor2;
        long dismissActionContentColor2;
        long actionContentColor3;
        Modifier modifier4;
        boolean actionOnNewLine3;
        Shape shape4;
        long containerColor3;
        long contentColor3;
        long actionColor3;
        int i2;
        int i3;
        int $dirty2;
        int i4;
        int i5;
        int i6;
        int i7;
        Composer $composer2 = $composer.startRestartGroup(274621471);
        ComposerKt.sourceInformation($composer2, "C(Snackbar)P(8,6,2,7,3:c#ui.graphics.Color,4:c#ui.graphics.Color,0:c#ui.graphics.Color,1:c#ui.graphics.Color,5:c#ui.graphics.Color)203@9555L5,204@9607L5,205@9657L12,206@9713L11,207@9775L18,208@9851L25,238@10864L456:Snackbar.kt#uh7d8r");
        int $dirty3 = $changed;
        if ((i & 1) != 0) {
            $dirty3 |= 6;
        } else if (($changed & 6) == 0) {
            $dirty3 |= $composer2.changed(snackbarData) ? 4 : 2;
        }
        int i8 = i & 2;
        if (i8 != 0) {
            $dirty3 |= 48;
            modifier2 = modifier;
        } else if (($changed & 48) == 0) {
            modifier2 = modifier;
            $dirty3 |= $composer2.changed(modifier2) ? 32 : 16;
        } else {
            modifier2 = modifier;
        }
        int i9 = i & 4;
        if (i9 != 0) {
            $dirty3 |= 384;
            z = actionOnNewLine;
        } else if (($changed & 384) == 0) {
            z = actionOnNewLine;
            $dirty3 |= $composer2.changed(z) ? 256 : 128;
        } else {
            z = actionOnNewLine;
        }
        if (($changed & 3072) == 0) {
            if ((i & 8) == 0) {
                shape2 = shape;
                if ($composer2.changed(shape2)) {
                    i7 = 2048;
                    $dirty3 |= i7;
                }
            } else {
                shape2 = shape;
            }
            i7 = 1024;
            $dirty3 |= i7;
        } else {
            shape2 = shape;
        }
        if (($changed & 24576) == 0) {
            if ((i & 16) == 0) {
                j = containerColor;
                if ($composer2.changed(j)) {
                    i6 = 16384;
                    $dirty3 |= i6;
                }
            } else {
                j = containerColor;
            }
            i6 = 8192;
            $dirty3 |= i6;
        } else {
            j = containerColor;
        }
        if ((196608 & $changed) == 0) {
            if ((i & 32) == 0) {
                j2 = contentColor;
                if ($composer2.changed(j2)) {
                    i5 = 131072;
                    $dirty3 |= i5;
                }
            } else {
                j2 = contentColor;
            }
            i5 = 65536;
            $dirty3 |= i5;
        } else {
            j2 = contentColor;
        }
        if ((1572864 & $changed) == 0) {
            if ((i & 64) == 0) {
                $dirty2 = $dirty3;
                if ($composer2.changed(actionColor)) {
                    i4 = 1048576;
                    $dirty = $dirty2 | i4;
                }
            } else {
                $dirty2 = $dirty3;
            }
            i4 = 524288;
            $dirty = $dirty2 | i4;
        } else {
            $dirty = $dirty3;
        }
        if (($changed & 12582912) == 0) {
            if ((i & 128) == 0 && $composer2.changed(actionContentColor)) {
                i3 = 8388608;
                $dirty |= i3;
            }
            i3 = 4194304;
            $dirty |= i3;
        }
        if ((100663296 & $changed) == 0) {
            if ((i & 256) == 0 && $composer2.changed(dismissActionContentColor)) {
                i2 = AccessibilityEventCompat.TYPE_VIEW_TARGETED_BY_SCROLL;
                $dirty |= i2;
            }
            i2 = 33554432;
            $dirty |= i2;
        }
        int $dirty4 = $dirty;
        if (($dirty4 & 38347923) == 38347922 && $composer2.getSkipping()) {
            $composer2.skipToGroupEnd();
            actionColor3 = actionColor;
            actionContentColor3 = actionContentColor;
            dismissActionContentColor2 = dismissActionContentColor;
            modifier4 = modifier2;
            actionOnNewLine3 = z;
            shape4 = shape2;
            containerColor3 = j;
            contentColor3 = j2;
        } else {
            $composer2.startDefaults();
            if (($changed & 1) == 0 || $composer2.getDefaultsInvalid()) {
                modifier3 = i8 != 0 ? Modifier.INSTANCE : modifier2;
                actionOnNewLine2 = i9 != 0 ? false : z;
                if ((i & 8) != 0) {
                    shape3 = SnackbarDefaults.INSTANCE.getShape($composer2, 6);
                    $dirty4 &= -7169;
                } else {
                    shape3 = shape2;
                }
                if ((i & 16) != 0) {
                    containerColor2 = SnackbarDefaults.INSTANCE.getColor($composer2, 6);
                    $dirty4 &= -57345;
                } else {
                    containerColor2 = j;
                }
                if ((i & 32) != 0) {
                    contentColor2 = SnackbarDefaults.INSTANCE.getContentColor($composer2, 6);
                    $dirty4 &= -458753;
                } else {
                    contentColor2 = j2;
                }
                if ((i & 64) != 0) {
                    actionColor2 = SnackbarDefaults.INSTANCE.getActionColor($composer2, 6);
                    $dirty4 &= -3670017;
                } else {
                    actionColor2 = actionColor;
                }
                if ((i & 128) != 0) {
                    actionContentColor2 = SnackbarDefaults.INSTANCE.getActionContentColor($composer2, 6);
                    $dirty4 &= -29360129;
                } else {
                    actionContentColor2 = actionContentColor;
                }
                if ((i & 256) != 0) {
                    $dirty4 = (-234881025) & $dirty4;
                    actionContentColor3 = actionContentColor2;
                    dismissActionContentColor2 = SnackbarDefaults.INSTANCE.getDismissActionContentColor($composer2, 6);
                } else {
                    dismissActionContentColor2 = dismissActionContentColor;
                    actionContentColor3 = actionContentColor2;
                }
            } else {
                $composer2.skipToGroupEnd();
                if ((i & 8) != 0) {
                    $dirty4 &= -7169;
                }
                if ((i & 16) != 0) {
                    $dirty4 &= -57345;
                }
                if ((i & 32) != 0) {
                    $dirty4 &= -458753;
                }
                if ((i & 64) != 0) {
                    $dirty4 &= -3670017;
                }
                if ((i & 128) != 0) {
                    $dirty4 &= -29360129;
                }
                if ((i & 256) != 0) {
                    actionContentColor3 = actionContentColor;
                    dismissActionContentColor2 = dismissActionContentColor;
                    $dirty4 &= -234881025;
                    modifier3 = modifier2;
                    actionOnNewLine2 = z;
                    shape3 = shape2;
                    containerColor2 = j;
                    contentColor2 = j2;
                    actionColor2 = actionColor;
                } else {
                    actionContentColor3 = actionContentColor;
                    dismissActionContentColor2 = dismissActionContentColor;
                    modifier3 = modifier2;
                    actionOnNewLine2 = z;
                    shape3 = shape2;
                    containerColor2 = j;
                    contentColor2 = j2;
                    actionColor2 = actionColor;
                }
            }
            $composer2.endDefaults();
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventStart(274621471, $dirty4, -1, "androidx.compose.material3.Snackbar (Snackbar.kt:209)");
            }
            final String actionLabel = snackbarData.getVisuals().getActionLabel();
            Function2 actionComposable = actionLabel != null ? ComposableLambdaKt.composableLambda($composer2, -1378313599, true, new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.SnackbarKt$Snackbar$actionComposable$1
                /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
                {
                    super(2);
                }

                @Override // kotlin.jvm.functions.Function2
                public /* bridge */ /* synthetic */ Unit invoke(Composer composer, Integer num) {
                    invoke(composer, num.intValue());
                    return Unit.INSTANCE;
                }

                public final void invoke(Composer $composer3, int $changed2) {
                    Object value$iv;
                    ComposerKt.sourceInformation($composer3, "C214@10104L44,215@10176L32,213@10052L219:Snackbar.kt#uh7d8r");
                    if (($changed2 & 3) != 2 || !$composer3.getSkipping()) {
                        if (ComposerKt.isTraceInProgress()) {
                            ComposerKt.traceEventStart(-1378313599, $changed2, -1, "androidx.compose.material3.Snackbar.<anonymous> (Snackbar.kt:213)");
                        }
                        ButtonColors m1617textButtonColorsro_MJ88 = ButtonDefaults.INSTANCE.m1617textButtonColorsro_MJ88(0L, actionColor2, 0L, 0L, $composer3, 24576, 13);
                        $composer3.startReplaceableGroup(-2057496839);
                        ComposerKt.sourceInformation($composer3, "CC(remember):Snackbar.kt#9igjgp");
                        boolean invalid$iv = $composer3.changed(snackbarData);
                        final SnackbarData snackbarData2 = snackbarData;
                        Object it$iv = $composer3.rememberedValue();
                        if (invalid$iv || it$iv == Composer.INSTANCE.getEmpty()) {
                            value$iv = new Function0<Unit>() { // from class: androidx.compose.material3.SnackbarKt$Snackbar$actionComposable$1$1$1
                                {
                                    super(0);
                                }

                                @Override // kotlin.jvm.functions.Function0
                                public /* bridge */ /* synthetic */ Unit invoke() {
                                    invoke2();
                                    return Unit.INSTANCE;
                                }

                                /* renamed from: invoke, reason: avoid collision after fix types in other method */
                                public final void invoke2() {
                                    SnackbarData.this.performAction();
                                }
                            };
                            $composer3.updateRememberedValue(value$iv);
                        } else {
                            value$iv = it$iv;
                        }
                        $composer3.endReplaceableGroup();
                        final String str = actionLabel;
                        ButtonKt.TextButton((Function0) value$iv, null, false, null, m1617textButtonColorsro_MJ88, null, null, null, null, ComposableLambdaKt.composableLambda($composer3, 521110564, true, new Function3<RowScope, Composer, Integer, Unit>() { // from class: androidx.compose.material3.SnackbarKt$Snackbar$actionComposable$1.2
                            /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
                            {
                                super(3);
                            }

                            @Override // kotlin.jvm.functions.Function3
                            public /* bridge */ /* synthetic */ Unit invoke(RowScope rowScope, Composer composer, Integer num) {
                                invoke(rowScope, composer, num.intValue());
                                return Unit.INSTANCE;
                            }

                            public final void invoke(RowScope $this$TextButton, Composer $composer4, int $changed3) {
                                ComposerKt.sourceInformation($composer4, "C216@10238L17:Snackbar.kt#uh7d8r");
                                if (($changed3 & 17) == 16 && $composer4.getSkipping()) {
                                    $composer4.skipToGroupEnd();
                                    return;
                                }
                                if (ComposerKt.isTraceInProgress()) {
                                    ComposerKt.traceEventStart(521110564, $changed3, -1, "androidx.compose.material3.Snackbar.<anonymous>.<anonymous> (Snackbar.kt:216)");
                                }
                                TextKt.m2464Text4IGK_g(str, (Modifier) null, 0L, 0L, (FontStyle) null, (FontWeight) null, (FontFamily) null, 0L, (TextDecoration) null, (TextAlign) null, 0L, 0, false, 0, 0, (Function1<? super TextLayoutResult, Unit>) null, (TextStyle) null, $composer4, 0, 0, 131070);
                                if (ComposerKt.isTraceInProgress()) {
                                    ComposerKt.traceEventEnd();
                                }
                            }
                        }), $composer3, 805306368, 494);
                        if (ComposerKt.isTraceInProgress()) {
                            ComposerKt.traceEventEnd();
                            return;
                        }
                        return;
                    }
                    $composer3.skipToGroupEnd();
                }
            }) : null;
            Function2 dismissActionComposable = snackbarData.getVisuals().getWithDismissAction() ? ComposableLambdaKt.composableLambda($composer2, -1812633777, true, new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.SnackbarKt$Snackbar$dismissActionComposable$1
                {
                    super(2);
                }

                @Override // kotlin.jvm.functions.Function2
                public /* bridge */ /* synthetic */ Unit invoke(Composer composer, Integer num) {
                    invoke(composer, num.intValue());
                    return Unit.INSTANCE;
                }

                public final void invoke(Composer $composer3, int $changed2) {
                    Object value$iv;
                    ComposerKt.sourceInformation($composer3, "C226@10513L26,225@10471L330:Snackbar.kt#uh7d8r");
                    if (($changed2 & 3) != 2 || !$composer3.getSkipping()) {
                        if (ComposerKt.isTraceInProgress()) {
                            ComposerKt.traceEventStart(-1812633777, $changed2, -1, "androidx.compose.material3.Snackbar.<anonymous> (Snackbar.kt:225)");
                        }
                        $composer3.startReplaceableGroup(-2057496502);
                        ComposerKt.sourceInformation($composer3, "CC(remember):Snackbar.kt#9igjgp");
                        boolean invalid$iv = $composer3.changed(SnackbarData.this);
                        final SnackbarData snackbarData2 = SnackbarData.this;
                        Object it$iv = $composer3.rememberedValue();
                        if (invalid$iv || it$iv == Composer.INSTANCE.getEmpty()) {
                            value$iv = new Function0<Unit>() { // from class: androidx.compose.material3.SnackbarKt$Snackbar$dismissActionComposable$1$1$1
                                {
                                    super(0);
                                }

                                @Override // kotlin.jvm.functions.Function0
                                public /* bridge */ /* synthetic */ Unit invoke() {
                                    invoke2();
                                    return Unit.INSTANCE;
                                }

                                /* renamed from: invoke, reason: avoid collision after fix types in other method */
                                public final void invoke2() {
                                    SnackbarData.this.dismiss();
                                }
                            };
                            $composer3.updateRememberedValue(value$iv);
                        } else {
                            value$iv = it$iv;
                        }
                        $composer3.endReplaceableGroup();
                        IconButtonKt.IconButton((Function0) value$iv, null, false, null, null, ComposableSingletons$SnackbarKt.INSTANCE.m1774getLambda1$material3_release(), $composer3, ProfileVerifier.CompilationStatus.RESULT_CODE_ERROR_CANT_WRITE_PROFILE_VERIFICATION_RESULT_CACHE_FILE, 30);
                        if (ComposerKt.isTraceInProgress()) {
                            ComposerKt.traceEventEnd();
                            return;
                        }
                        return;
                    }
                    $composer3.skipToGroupEnd();
                }
            }) : null;
            m2232SnackbareQBnUkQ(PaddingKt.m562padding3ABfNKs(modifier3, Dp.m6094constructorimpl(12)), actionComposable, dismissActionComposable, actionOnNewLine2, shape3, containerColor2, contentColor2, actionContentColor3, dismissActionContentColor2, ComposableLambdaKt.composableLambda($composer2, -1266389126, true, new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.SnackbarKt$Snackbar$3
                {
                    super(2);
                }

                @Override // kotlin.jvm.functions.Function2
                public /* bridge */ /* synthetic */ Unit invoke(Composer composer, Integer num) {
                    invoke(composer, num.intValue());
                    return Unit.INSTANCE;
                }

                public final void invoke(Composer $composer3, int $changed2) {
                    ComposerKt.sourceInformation($composer3, "C248@11278L34:Snackbar.kt#uh7d8r");
                    if (($changed2 & 3) == 2 && $composer3.getSkipping()) {
                        $composer3.skipToGroupEnd();
                        return;
                    }
                    if (ComposerKt.isTraceInProgress()) {
                        ComposerKt.traceEventStart(-1266389126, $changed2, -1, "androidx.compose.material3.Snackbar.<anonymous> (Snackbar.kt:248)");
                    }
                    TextKt.m2464Text4IGK_g(SnackbarData.this.getVisuals().getMessage(), (Modifier) null, 0L, 0L, (FontStyle) null, (FontWeight) null, (FontFamily) null, 0L, (TextDecoration) null, (TextAlign) null, 0L, 0, false, 0, 0, (Function1<? super TextLayoutResult, Unit>) null, (TextStyle) null, $composer3, 0, 0, 131070);
                    if (ComposerKt.isTraceInProgress()) {
                        ComposerKt.traceEventEnd();
                    }
                }
            }), $composer2, (($dirty4 << 3) & 7168) | 805306368 | (($dirty4 << 3) & 57344) | (($dirty4 << 3) & 458752) | (3670016 & ($dirty4 << 3)) | (29360128 & $dirty4) | (234881024 & $dirty4), 0);
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventEnd();
            }
            modifier4 = modifier3;
            actionOnNewLine3 = actionOnNewLine2;
            shape4 = shape3;
            containerColor3 = containerColor2;
            contentColor3 = contentColor2;
            actionColor3 = actionColor2;
        }
        ScopeUpdateScope endRestartGroup = $composer2.endRestartGroup();
        if (endRestartGroup != null) {
            final Modifier modifier5 = modifier4;
            final boolean z2 = actionOnNewLine3;
            final Shape shape5 = shape4;
            final long j3 = containerColor3;
            final long j4 = contentColor3;
            final long j5 = actionColor3;
            final long j6 = actionContentColor3;
            final long j7 = dismissActionContentColor2;
            endRestartGroup.updateScope(new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.SnackbarKt$Snackbar$4
                /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
                {
                    super(2);
                }

                @Override // kotlin.jvm.functions.Function2
                public /* bridge */ /* synthetic */ Unit invoke(Composer composer, Integer num) {
                    invoke(composer, num.intValue());
                    return Unit.INSTANCE;
                }

                public final void invoke(Composer composer, int i10) {
                    SnackbarKt.m2233SnackbarsDKtq54(SnackbarData.this, modifier5, z2, shape5, j3, j4, j5, j6, j7, composer, RecomposeScopeImplKt.updateChangedFlags($changed | 1), i);
                }
            });
        }
    }

    /* JADX INFO: Access modifiers changed from: private */
    /* JADX WARN: Removed duplicated region for block: B:100:0x0550  */
    /* JADX WARN: Removed duplicated region for block: B:105:0x05fe  */
    /* JADX WARN: Removed duplicated region for block: B:108:0x0664  */
    /* JADX WARN: Removed duplicated region for block: B:110:0x0566 A[ADDED_TO_REGION] */
    /* JADX WARN: Removed duplicated region for block: B:111:0x051d  */
    /* JADX WARN: Removed duplicated region for block: B:113:0x0439 A[ADDED_TO_REGION] */
    /* JADX WARN: Removed duplicated region for block: B:114:0x03f2  */
    /* JADX WARN: Removed duplicated region for block: B:115:0x0369  */
    /* JADX WARN: Removed duplicated region for block: B:118:0x0288  */
    /* JADX WARN: Removed duplicated region for block: B:69:0x0276  */
    /* JADX WARN: Removed duplicated region for block: B:72:0x0282  */
    /* JADX WARN: Removed duplicated region for block: B:80:0x0364  */
    /* JADX WARN: Removed duplicated region for block: B:83:0x03e0  */
    /* JADX WARN: Removed duplicated region for block: B:86:0x03ec  */
    /* JADX WARN: Removed duplicated region for block: B:89:0x0425  */
    /* JADX WARN: Removed duplicated region for block: B:94:0x050b  */
    /* JADX WARN: Removed duplicated region for block: B:97:0x0517  */
    /* renamed from: NewLineButtonSnackbar-kKq0p4A, reason: not valid java name */
    /*
        Code decompiled incorrectly, please refer to instructions dump.
        To view partially-correct add '--show-bad-code' argument
    */
    public static final void m2230NewLineButtonSnackbarkKq0p4A(final kotlin.jvm.functions.Function2<? super androidx.compose.runtime.Composer, ? super java.lang.Integer, kotlin.Unit> r72, final kotlin.jvm.functions.Function2<? super androidx.compose.runtime.Composer, ? super java.lang.Integer, kotlin.Unit> r73, final kotlin.jvm.functions.Function2<? super androidx.compose.runtime.Composer, ? super java.lang.Integer, kotlin.Unit> r74, final androidx.compose.ui.text.TextStyle r75, final long r76, final long r78, androidx.compose.runtime.Composer r80, final int r81) {
        /*
            Method dump skipped, instructions count: 1674
            To view this dump add '--comments-level debug' option
        */
        throw new UnsupportedOperationException("Method not decompiled: androidx.compose.material3.SnackbarKt.m2230NewLineButtonSnackbarkKq0p4A(kotlin.jvm.functions.Function2, kotlin.jvm.functions.Function2, kotlin.jvm.functions.Function2, androidx.compose.ui.text.TextStyle, long, long, androidx.compose.runtime.Composer, int):void");
    }

    /* JADX INFO: Access modifiers changed from: private */
    /* JADX WARN: Removed duplicated region for block: B:100:0x04bc  */
    /* JADX WARN: Removed duplicated region for block: B:114:0x0627  */
    /* JADX WARN: Removed duplicated region for block: B:118:0x060c  */
    /* JADX WARN: Removed duplicated region for block: B:122:0x04aa  */
    /* JADX WARN: Removed duplicated region for block: B:125:0x0277  */
    /* JADX WARN: Removed duplicated region for block: B:75:0x0265  */
    /* JADX WARN: Removed duplicated region for block: B:78:0x0271  */
    /* JADX WARN: Removed duplicated region for block: B:86:0x034e  */
    /* renamed from: OneRowSnackbar-kKq0p4A, reason: not valid java name */
    /*
        Code decompiled incorrectly, please refer to instructions dump.
        To view partially-correct add '--show-bad-code' argument
    */
    public static final void m2231OneRowSnackbarkKq0p4A(final kotlin.jvm.functions.Function2<? super androidx.compose.runtime.Composer, ? super java.lang.Integer, kotlin.Unit> r54, final kotlin.jvm.functions.Function2<? super androidx.compose.runtime.Composer, ? super java.lang.Integer, kotlin.Unit> r55, final kotlin.jvm.functions.Function2<? super androidx.compose.runtime.Composer, ? super java.lang.Integer, kotlin.Unit> r56, final androidx.compose.ui.text.TextStyle r57, final long r58, final long r60, androidx.compose.runtime.Composer r62, final int r63) {
        /*
            Method dump skipped, instructions count: 1613
            To view this dump add '--comments-level debug' option
        */
        throw new UnsupportedOperationException("Method not decompiled: androidx.compose.material3.SnackbarKt.m2231OneRowSnackbarkKq0p4A(kotlin.jvm.functions.Function2, kotlin.jvm.functions.Function2, kotlin.jvm.functions.Function2, androidx.compose.ui.text.TextStyle, long, long, androidx.compose.runtime.Composer, int):void");
    }
}
