package androidx.compose.material3;

import androidx.compose.foundation.layout.ColumnScope;
import androidx.compose.foundation.layout.PaddingKt;
import androidx.compose.foundation.layout.PaddingValues;
import androidx.compose.foundation.layout.SizeKt;
import androidx.compose.material3.tokens.DatePickerModalTokens;
import androidx.compose.runtime.Composer;
import androidx.compose.runtime.ComposerKt;
import androidx.compose.runtime.RecomposeScopeImplKt;
import androidx.compose.runtime.ScopeUpdateScope;
import androidx.compose.runtime.internal.ComposableLambdaKt;
import androidx.compose.ui.Modifier;
import androidx.compose.ui.graphics.Shape;
import androidx.compose.ui.unit.Dp;
import androidx.compose.ui.window.DialogProperties;
import androidx.core.location.LocationRequestCompat;
import androidx.core.view.accessibility.AccessibilityEventCompat;
import androidx.profileinstaller.ProfileVerifier;
import kotlin.Metadata;
import kotlin.Unit;
import kotlin.jvm.functions.Function0;
import kotlin.jvm.functions.Function2;
import kotlin.jvm.functions.Function3;

/* compiled from: DatePickerDialog.android.kt */
@Metadata(d1 = {"\u0000N\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\b\u0003\u001a\u009a\u0001\u0010\u0006\u001a\u00020\u00072\f\u0010\b\u001a\b\u0012\u0004\u0012\u00020\u00070\t2\u0011\u0010\n\u001a\r\u0012\u0004\u0012\u00020\u00070\t¢\u0006\u0002\b\u000b2\b\b\u0002\u0010\f\u001a\u00020\r2\u0015\b\u0002\u0010\u000e\u001a\u000f\u0012\u0004\u0012\u00020\u0007\u0018\u00010\t¢\u0006\u0002\b\u000b2\b\b\u0002\u0010\u000f\u001a\u00020\u00102\b\b\u0002\u0010\u0011\u001a\u00020\u00012\b\b\u0002\u0010\u0012\u001a\u00020\u00132\b\b\u0002\u0010\u0014\u001a\u00020\u00152\u001c\u0010\u0016\u001a\u0018\u0012\u0004\u0012\u00020\u0018\u0012\u0004\u0012\u00020\u00070\u0017¢\u0006\u0002\b\u000b¢\u0006\u0002\b\u0019H\u0007ø\u0001\u0000¢\u0006\u0004\b\u001a\u0010\u001b\"\u0010\u0010\u0000\u001a\u00020\u0001X\u0082\u0004¢\u0006\u0004\n\u0002\u0010\u0002\"\u0010\u0010\u0003\u001a\u00020\u0001X\u0082\u0004¢\u0006\u0004\n\u0002\u0010\u0002\"\u000e\u0010\u0004\u001a\u00020\u0005X\u0082\u0004¢\u0006\u0002\n\u0000\u0082\u0002\u0007\n\u0005\b¡\u001e0\u0001¨\u0006\u001c"}, d2 = {"DialogButtonsCrossAxisSpacing", "Landroidx/compose/ui/unit/Dp;", "F", "DialogButtonsMainAxisSpacing", "DialogButtonsPadding", "Landroidx/compose/foundation/layout/PaddingValues;", "DatePickerDialog", "", "onDismissRequest", "Lkotlin/Function0;", "confirmButton", "Landroidx/compose/runtime/Composable;", "modifier", "Landroidx/compose/ui/Modifier;", "dismissButton", "shape", "Landroidx/compose/ui/graphics/Shape;", "tonalElevation", "colors", "Landroidx/compose/material3/DatePickerColors;", "properties", "Landroidx/compose/ui/window/DialogProperties;", "content", "Lkotlin/Function1;", "Landroidx/compose/foundation/layout/ColumnScope;", "Lkotlin/ExtensionFunctionType;", "DatePickerDialog-GmEhDVc", "(Lkotlin/jvm/functions/Function0;Lkotlin/jvm/functions/Function2;Landroidx/compose/ui/Modifier;Lkotlin/jvm/functions/Function2;Landroidx/compose/ui/graphics/Shape;FLandroidx/compose/material3/DatePickerColors;Landroidx/compose/ui/window/DialogProperties;Lkotlin/jvm/functions/Function3;Landroidx/compose/runtime/Composer;II)V", "material3_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class DatePickerDialog_androidKt {
    private static final PaddingValues DialogButtonsPadding = PaddingKt.m559PaddingValuesa9UjIt4$default(0.0f, 0.0f, Dp.m6094constructorimpl(6), Dp.m6094constructorimpl(8), 3, null);
    private static final float DialogButtonsMainAxisSpacing = Dp.m6094constructorimpl(8);
    private static final float DialogButtonsCrossAxisSpacing = Dp.m6094constructorimpl(12);

    /* renamed from: DatePickerDialog-GmEhDVc, reason: not valid java name */
    public static final void m1817DatePickerDialogGmEhDVc(final Function0<Unit> function0, final Function2<? super Composer, ? super Integer, Unit> function2, Modifier modifier, Function2<? super Composer, ? super Integer, Unit> function22, Shape shape, float tonalElevation, DatePickerColors colors, DialogProperties properties, final Function3<? super ColumnScope, ? super Composer, ? super Integer, Unit> function3, Composer $composer, final int $changed, final int i) {
        Function2 dismissButton;
        Shape shape2;
        float tonalElevation2;
        DatePickerColors colors2;
        Modifier.Companion modifier2;
        DialogProperties properties2;
        int $dirty;
        Function2 dismissButton2;
        Shape shape3;
        float tonalElevation3;
        DatePickerColors colors3;
        Modifier modifier3;
        DialogProperties properties3;
        DatePickerColors colors4;
        float tonalElevation4;
        Shape shape4;
        Function2 dismissButton3;
        int i2;
        int i3;
        Composer $composer2 = $composer.startRestartGroup(-36517340);
        ComposerKt.sourceInformation($composer2, "C(DatePickerDialog)P(5,1,4,3,7,8:c#ui.unit.Dp!1,6)68@3428L5,70@3545L8,74@3697L1472:DatePickerDialog.android.kt#uh7d8r");
        int $dirty2 = $changed;
        if ((i & 1) != 0) {
            $dirty2 |= 6;
        } else if (($changed & 6) == 0) {
            $dirty2 |= $composer2.changedInstance(function0) ? 4 : 2;
        }
        if ((i & 2) != 0) {
            $dirty2 |= 48;
        } else if (($changed & 48) == 0) {
            $dirty2 |= $composer2.changedInstance(function2) ? 32 : 16;
        }
        int i4 = i & 4;
        if (i4 != 0) {
            $dirty2 |= 384;
        } else if (($changed & 384) == 0) {
            $dirty2 |= $composer2.changed(modifier) ? 256 : 128;
        }
        int i5 = i & 8;
        if (i5 != 0) {
            $dirty2 |= 3072;
            dismissButton = function22;
        } else if (($changed & 3072) == 0) {
            dismissButton = function22;
            $dirty2 |= $composer2.changedInstance(dismissButton) ? 2048 : 1024;
        } else {
            dismissButton = function22;
        }
        if (($changed & 24576) == 0) {
            if ((i & 16) == 0) {
                shape2 = shape;
                if ($composer2.changed(shape2)) {
                    i3 = 16384;
                    $dirty2 |= i3;
                }
            } else {
                shape2 = shape;
            }
            i3 = 8192;
            $dirty2 |= i3;
        } else {
            shape2 = shape;
        }
        int i6 = i & 32;
        if (i6 != 0) {
            $dirty2 |= ProfileVerifier.CompilationStatus.RESULT_CODE_ERROR_CANT_WRITE_PROFILE_VERIFICATION_RESULT_CACHE_FILE;
            tonalElevation2 = tonalElevation;
        } else if ((196608 & $changed) == 0) {
            tonalElevation2 = tonalElevation;
            $dirty2 |= $composer2.changed(tonalElevation2) ? 131072 : 65536;
        } else {
            tonalElevation2 = tonalElevation;
        }
        if ((1572864 & $changed) == 0) {
            if ((i & 64) == 0) {
                colors2 = colors;
                if ($composer2.changed(colors2)) {
                    i2 = 1048576;
                    $dirty2 |= i2;
                }
            } else {
                colors2 = colors;
            }
            i2 = 524288;
            $dirty2 |= i2;
        } else {
            colors2 = colors;
        }
        int i7 = i & 128;
        if (i7 != 0) {
            $dirty2 |= 12582912;
        } else if (($changed & 12582912) == 0) {
            $dirty2 |= $composer2.changed(properties) ? 8388608 : 4194304;
        }
        if ((i & 256) != 0) {
            $dirty2 |= 100663296;
        } else if (($changed & 100663296) == 0) {
            $dirty2 |= $composer2.changedInstance(function3) ? AccessibilityEventCompat.TYPE_VIEW_TARGETED_BY_SCROLL : 33554432;
        }
        if (($dirty2 & 38347923) == 38347922 && $composer2.getSkipping()) {
            $composer2.skipToGroupEnd();
            modifier3 = modifier;
            properties3 = properties;
            dismissButton3 = dismissButton;
            shape4 = shape2;
            tonalElevation4 = tonalElevation2;
            colors4 = colors2;
        } else {
            $composer2.startDefaults();
            if (($changed & 1) == 0 || $composer2.getDefaultsInvalid()) {
                modifier2 = i4 != 0 ? Modifier.INSTANCE : modifier;
                if (i5 != 0) {
                    dismissButton = null;
                }
                if ((i & 16) != 0) {
                    $dirty2 &= -57345;
                    shape2 = DatePickerDefaults.INSTANCE.getShape($composer2, 6);
                }
                if (i6 != 0) {
                    tonalElevation2 = DatePickerDefaults.INSTANCE.m1816getTonalElevationD9Ej5fM();
                }
                if ((i & 64) != 0) {
                    $dirty2 &= -3670017;
                    colors2 = DatePickerDefaults.INSTANCE.colors($composer2, 6);
                }
                if (i7 != 0) {
                    properties2 = new DialogProperties(false, false, null, false, false, 23, null);
                    dismissButton2 = dismissButton;
                    shape3 = shape2;
                    tonalElevation3 = tonalElevation2;
                    colors3 = colors2;
                    $dirty = $dirty2;
                } else {
                    properties2 = properties;
                    $dirty = $dirty2;
                    dismissButton2 = dismissButton;
                    shape3 = shape2;
                    tonalElevation3 = tonalElevation2;
                    colors3 = colors2;
                }
            } else {
                $composer2.skipToGroupEnd();
                if ((i & 16) != 0) {
                    $dirty2 &= -57345;
                }
                if ((i & 64) != 0) {
                    properties2 = properties;
                    $dirty = $dirty2 & (-3670017);
                    dismissButton2 = dismissButton;
                    shape3 = shape2;
                    tonalElevation3 = tonalElevation2;
                    colors3 = colors2;
                    modifier2 = modifier;
                } else {
                    modifier2 = modifier;
                    properties2 = properties;
                    $dirty = $dirty2;
                    dismissButton2 = dismissButton;
                    shape3 = shape2;
                    tonalElevation3 = tonalElevation2;
                    colors3 = colors2;
                }
            }
            $composer2.endDefaults();
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventStart(-36517340, $dirty, -1, "androidx.compose.material3.DatePickerDialog (DatePickerDialog.android.kt:73)");
            }
            final Shape shape5 = shape3;
            final DatePickerColors datePickerColors = colors3;
            final float f = tonalElevation3;
            final Function2 function23 = dismissButton2;
            AndroidAlertDialog_androidKt.BasicAlertDialog(function0, SizeKt.wrapContentHeight$default(modifier2, null, false, 3, null), properties2, ComposableLambdaKt.composableLambda($composer2, -10625622, true, new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.DatePickerDialog_androidKt$DatePickerDialog$1
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
                    ComposerKt.sourceInformation($composer3, "C79@3857L1306:DatePickerDialog.android.kt#uh7d8r");
                    if (($changed2 & 3) != 2 || !$composer3.getSkipping()) {
                        if (ComposerKt.isTraceInProgress()) {
                            ComposerKt.traceEventStart(-10625622, $changed2, -1, "androidx.compose.material3.DatePickerDialog.<anonymous> (DatePickerDialog.android.kt:79)");
                        }
                        Modifier m599heightInVpY3zN4$default = SizeKt.m599heightInVpY3zN4$default(SizeKt.m608requiredWidth3ABfNKs(Modifier.INSTANCE, DatePickerModalTokens.INSTANCE.m2779getContainerWidthD9Ej5fM()), 0.0f, DatePickerModalTokens.INSTANCE.m2778getContainerHeightD9Ej5fM(), 1, null);
                        Shape shape6 = Shape.this;
                        long containerColor = datePickerColors.getContainerColor();
                        float f2 = f;
                        final Function3<ColumnScope, Composer, Integer, Unit> function32 = function3;
                        final Function2<Composer, Integer, Unit> function24 = function23;
                        final Function2<Composer, Integer, Unit> function25 = function2;
                        SurfaceKt.m2316SurfaceT9BRK9s(m599heightInVpY3zN4$default, shape6, containerColor, 0L, f2, 0.0f, null, ComposableLambdaKt.composableLambda($composer3, -1706202235, true, new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.DatePickerDialog_androidKt$DatePickerDialog$1.1
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

                            /* JADX WARN: Removed duplicated region for block: B:24:0x01de  */
                            /* JADX WARN: Removed duplicated region for block: B:27:0x01ea  */
                            /* JADX WARN: Removed duplicated region for block: B:35:0x0304  */
                            /* JADX WARN: Removed duplicated region for block: B:37:? A[RETURN, SYNTHETIC] */
                            /* JADX WARN: Removed duplicated region for block: B:40:0x01f0  */
                            /*
                                Code decompiled incorrectly, please refer to instructions dump.
                                To view partially-correct add '--show-bad-code' argument
                            */
                            public final void invoke(androidx.compose.runtime.Composer r55, int r56) {
                                /*
                                    Method dump skipped, instructions count: 776
                                    To view this dump add '--comments-level debug' option
                                */
                                throw new UnsupportedOperationException("Method not decompiled: androidx.compose.material3.DatePickerDialog_androidKt$DatePickerDialog$1.AnonymousClass1.invoke(androidx.compose.runtime.Composer, int):void");
                            }
                        }), $composer3, 12582918, LocationRequestCompat.QUALITY_LOW_POWER);
                        if (ComposerKt.isTraceInProgress()) {
                            ComposerKt.traceEventEnd();
                            return;
                        }
                        return;
                    }
                    $composer3.skipToGroupEnd();
                }
            }), $composer2, ($dirty & 14) | 3072 | (($dirty >> 15) & 896), 0);
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventEnd();
            }
            modifier3 = modifier2;
            properties3 = properties2;
            colors4 = colors3;
            tonalElevation4 = tonalElevation3;
            shape4 = shape3;
            dismissButton3 = dismissButton2;
        }
        ScopeUpdateScope endRestartGroup = $composer2.endRestartGroup();
        if (endRestartGroup != null) {
            final Modifier modifier4 = modifier3;
            final Function2 function24 = dismissButton3;
            final Shape shape6 = shape4;
            final float f2 = tonalElevation4;
            final DatePickerColors datePickerColors2 = colors4;
            final DialogProperties dialogProperties = properties3;
            endRestartGroup.updateScope(new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.DatePickerDialog_androidKt$DatePickerDialog$2
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

                public final void invoke(Composer composer, int i8) {
                    DatePickerDialog_androidKt.m1817DatePickerDialogGmEhDVc(function0, function2, modifier4, function24, shape6, f2, datePickerColors2, dialogProperties, function3, composer, RecomposeScopeImplKt.updateChangedFlags($changed | 1), i);
                }
            });
        }
    }
}
