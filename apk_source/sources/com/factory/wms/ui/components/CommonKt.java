package com.factory.wms.ui.components;

import androidx.compose.foundation.layout.ColumnScope;
import androidx.compose.foundation.layout.PaddingKt;
import androidx.compose.foundation.layout.SizeKt;
import androidx.compose.material3.CardColors;
import androidx.compose.material3.CardDefaults;
import androidx.compose.material3.CardKt;
import androidx.compose.material3.MaterialTheme;
import androidx.compose.material3.TextKt;
import androidx.compose.runtime.Composer;
import androidx.compose.runtime.ComposerKt;
import androidx.compose.runtime.RecomposeScopeImplKt;
import androidx.compose.runtime.ScopeUpdateScope;
import androidx.compose.runtime.internal.ComposableLambdaKt;
import androidx.compose.ui.Modifier;
import androidx.compose.ui.text.TextLayoutResult;
import androidx.compose.ui.text.font.FontFamily;
import androidx.compose.ui.text.font.FontStyle;
import androidx.compose.ui.text.font.FontWeight;
import androidx.compose.ui.text.style.TextAlign;
import androidx.compose.ui.text.style.TextDecoration;
import androidx.compose.ui.unit.Dp;
import androidx.profileinstaller.ProfileVerifier;
import com.factory.wms.ui.viewmodel.ScanLine;
import kotlin.Metadata;
import kotlin.Unit;
import kotlin.jvm.functions.Function0;
import kotlin.jvm.functions.Function1;
import kotlin.jvm.functions.Function2;
import kotlin.jvm.functions.Function3;
import kotlin.jvm.internal.Intrinsics;
import kotlin.ranges.RangesKt;
import kotlin.text.StringsKt;

/* compiled from: Common.kt */
@Metadata(d1 = {"\u0000:\n\u0000\n\u0002\u0010\u0002\n\u0000\n\u0002\u0010\u000e\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0010\u0006\n\u0000\u001a+\u0010\u0000\u001a\u00020\u00012\b\u0010\u0002\u001a\u0004\u0018\u00010\u00032\b\u0010\u0004\u001a\u0004\u0018\u00010\u00032\b\b\u0002\u0010\u0005\u001a\u00020\u0006H\u0007¢\u0006\u0002\u0010\u0007\u001a\\\u0010\b\u001a\u00020\u00012\u0006\u0010\t\u001a\u00020\n2\u0006\u0010\u000b\u001a\u00020\u00032\u0006\u0010\f\u001a\u00020\u00032\u0012\u0010\r\u001a\u000e\u0012\u0004\u0012\u00020\u0003\u0012\u0004\u0012\u00020\u00010\u000e2\f\u0010\u000f\u001a\b\u0012\u0004\u0012\u00020\u00010\u00102\u0013\b\u0002\u0010\u0011\u001a\r\u0012\u0004\u0012\u00020\u00010\u0010¢\u0006\u0002\b\u0012H\u0007¢\u0006\u0002\u0010\u0013\u001a\n\u0010\u0014\u001a\u00020\u0015*\u00020\u0003¨\u0006\u0016"}, d2 = {"StatusText", "", "message", "", "error", "modifier", "Landroidx/compose/ui/Modifier;", "(Ljava/lang/String;Ljava/lang/String;Landroidx/compose/ui/Modifier;Landroidx/compose/runtime/Composer;II)V", "LineCard", "line", "Lcom/factory/wms/ui/viewmodel/ScanLine;", "quantityLabel", "quantityValue", "onQuantityChange", "Lkotlin/Function1;", "onDelete", "Lkotlin/Function0;", "extraContent", "Landroidx/compose/runtime/Composable;", "(Lcom/factory/wms/ui/viewmodel/ScanLine;Ljava/lang/String;Ljava/lang/String;Lkotlin/jvm/functions/Function1;Lkotlin/jvm/functions/Function0;Lkotlin/jvm/functions/Function2;Landroidx/compose/runtime/Composer;II)V", "toPositiveDoubleOrZero", "", "app_debug"}, k = 2, mv = {2, 0, 0}, xi = 48)
/* loaded from: classes4.dex */
public final class CommonKt {
    /* JADX INFO: Access modifiers changed from: private */
    public static final Unit LineCard$lambda$2(ScanLine scanLine, String str, String str2, Function1 function1, Function0 function0, Function2 function2, int i, int i2, Composer composer, int i3) {
        LineCard(scanLine, str, str2, function1, function0, function2, composer, RecomposeScopeImplKt.updateChangedFlags(i | 1), i2);
        return Unit.INSTANCE;
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final Unit StatusText$lambda$0(String str, String str2, Modifier modifier, int i, int i2, Composer composer, int i3) {
        StatusText(str, str2, modifier, composer, RecomposeScopeImplKt.updateChangedFlags(i | 1), i2);
        return Unit.INSTANCE;
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final Unit StatusText$lambda$1(String str, String str2, Modifier modifier, int i, int i2, Composer composer, int i3) {
        StatusText(str, str2, modifier, composer, RecomposeScopeImplKt.updateChangedFlags(i | 1), i2);
        return Unit.INSTANCE;
    }

    public static final void StatusText(final String message, final String error, Modifier modifier, Composer $composer, final int $changed, final int i) {
        Modifier modifier2;
        String text;
        long secondary;
        Composer $composer2;
        Modifier modifier3;
        Composer $composer3 = $composer.startRestartGroup(1195874961);
        ComposerKt.sourceInformation($composer3, "C(StatusText)P(1)35@1526L10,32@1446L161:Common.kt#qrwxji");
        int $dirty = $changed;
        if ((i & 1) != 0) {
            $dirty |= 6;
        } else if (($changed & 6) == 0) {
            $dirty |= $composer3.changed(message) ? 4 : 2;
        }
        if ((i & 2) != 0) {
            $dirty |= 48;
        } else if (($changed & 48) == 0) {
            $dirty |= $composer3.changed(error) ? 32 : 16;
        }
        int i2 = i & 4;
        if (i2 != 0) {
            $dirty |= 384;
            modifier2 = modifier;
        } else if (($changed & 384) == 0) {
            modifier2 = modifier;
            $dirty |= $composer3.changed(modifier2) ? 256 : 128;
        } else {
            modifier2 = modifier;
        }
        int $dirty2 = $dirty;
        if (($dirty2 & 147) != 146 || !$composer3.getSkipping()) {
            Modifier modifier4 = i2 != 0 ? Modifier.INSTANCE : modifier2;
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventStart(1195874961, $dirty2, -1, "com.factory.wms.ui.components.StatusText (Common.kt:29)");
            }
            if (error != null) {
                text = error;
            } else {
                if (message == null) {
                    if (ComposerKt.isTraceInProgress()) {
                        ComposerKt.traceEventEnd();
                    }
                    ScopeUpdateScope endRestartGroup = $composer3.endRestartGroup();
                    if (endRestartGroup != null) {
                        final Modifier modifier5 = modifier4;
                        endRestartGroup.updateScope(new Function2() { // from class: com.factory.wms.ui.components.CommonKt$$ExternalSyntheticLambda1
                            @Override // kotlin.jvm.functions.Function2
                            public final Object invoke(Object obj, Object obj2) {
                                Unit StatusText$lambda$0;
                                StatusText$lambda$0 = CommonKt.StatusText$lambda$0(message, error, modifier5, $changed, i, (Composer) obj, ((Integer) obj2).intValue());
                                return StatusText$lambda$0;
                            }
                        });
                        return;
                    }
                    return;
                }
                text = message;
            }
            if (error != null) {
                $composer3.startReplaceableGroup(-423033820);
                ComposerKt.sourceInformation($composer3, "31@1383L11");
                secondary = MaterialTheme.INSTANCE.getColorScheme($composer3, MaterialTheme.$stable).getError();
            } else {
                $composer3.startReplaceableGroup(-423032632);
                ComposerKt.sourceInformation($composer3, "31@1420L11");
                secondary = MaterialTheme.INSTANCE.getColorScheme($composer3, MaterialTheme.$stable).getSecondary();
            }
            $composer3.endReplaceableGroup();
            long color = secondary;
            Modifier modifier6 = modifier4;
            $composer2 = $composer3;
            TextKt.m2464Text4IGK_g(text, PaddingKt.m564paddingVpY3zN4$default(modifier4, 0.0f, Dp.m6094constructorimpl(6), 1, null), color, 0L, (FontStyle) null, (FontWeight) null, (FontFamily) null, 0L, (TextDecoration) null, (TextAlign) null, 0L, 0, false, 0, 0, (Function1<? super TextLayoutResult, Unit>) null, MaterialTheme.INSTANCE.getTypography($composer3, MaterialTheme.$stable).getBodyMedium(), $composer2, 0, 0, 65528);
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventEnd();
            }
            modifier3 = modifier6;
        } else {
            $composer3.skipToGroupEnd();
            modifier3 = modifier2;
            $composer2 = $composer3;
        }
        ScopeUpdateScope endRestartGroup2 = $composer2.endRestartGroup();
        if (endRestartGroup2 != null) {
            final Modifier modifier7 = modifier3;
            endRestartGroup2.updateScope(new Function2() { // from class: com.factory.wms.ui.components.CommonKt$$ExternalSyntheticLambda2
                @Override // kotlin.jvm.functions.Function2
                public final Object invoke(Object obj, Object obj2) {
                    Unit StatusText$lambda$1;
                    StatusText$lambda$1 = CommonKt.StatusText$lambda$1(message, error, modifier7, $changed, i, (Composer) obj, ((Integer) obj2).intValue());
                    return StatusText$lambda$1;
                }
            });
        }
    }

    public static final void LineCard(final ScanLine line, final String quantityLabel, final String quantityValue, final Function1<? super String, Unit> onQuantityChange, final Function0<Unit> onDelete, Function2<? super Composer, ? super Integer, Unit> function2, Composer $composer, final int $changed, final int i) {
        Function2 function22;
        Function2 extraContent;
        int $dirty;
        Intrinsics.checkNotNullParameter(line, "line");
        Intrinsics.checkNotNullParameter(quantityLabel, "quantityLabel");
        Intrinsics.checkNotNullParameter(quantityValue, "quantityValue");
        Intrinsics.checkNotNullParameter(onQuantityChange, "onQuantityChange");
        Intrinsics.checkNotNullParameter(onDelete, "onDelete");
        Composer $composer2 = $composer.startRestartGroup(1632237150);
        ComposerKt.sourceInformation($composer2, "C(LineCard)P(1,4,5,3,2)53@2004L11,53@1962L62,54@2059L38,49@1831L1884:Common.kt#qrwxji");
        int $dirty2 = $changed;
        if ((i & 1) != 0) {
            $dirty2 |= 6;
        } else if (($changed & 6) == 0) {
            $dirty2 |= $composer2.changed(line) ? 4 : 2;
        }
        if ((i & 2) != 0) {
            $dirty2 |= 48;
        } else if (($changed & 48) == 0) {
            $dirty2 |= $composer2.changed(quantityLabel) ? 32 : 16;
        }
        if ((i & 4) != 0) {
            $dirty2 |= 384;
        } else if (($changed & 384) == 0) {
            $dirty2 |= $composer2.changed(quantityValue) ? 256 : 128;
        }
        if ((i & 8) != 0) {
            $dirty2 |= 3072;
        } else if (($changed & 3072) == 0) {
            $dirty2 |= $composer2.changedInstance(onQuantityChange) ? 2048 : 1024;
        }
        if ((i & 16) != 0) {
            $dirty2 |= 24576;
        } else if (($changed & 24576) == 0) {
            $dirty2 |= $composer2.changedInstance(onDelete) ? 16384 : 8192;
        }
        int i2 = i & 32;
        if (i2 != 0) {
            $dirty2 |= ProfileVerifier.CompilationStatus.RESULT_CODE_ERROR_CANT_WRITE_PROFILE_VERIFICATION_RESULT_CACHE_FILE;
            function22 = function2;
        } else if ((196608 & $changed) == 0) {
            function22 = function2;
            $dirty2 |= $composer2.changedInstance(function22) ? 131072 : 65536;
        } else {
            function22 = function2;
        }
        int $dirty3 = $dirty2;
        if ((74899 & $dirty3) != 74898 || !$composer2.getSkipping()) {
            extraContent = i2 != 0 ? ComposableSingletons$CommonKt.INSTANCE.m6405getLambda1$app_debug() : function22;
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventStart(1632237150, $dirty3, -1, "com.factory.wms.ui.components.LineCard (Common.kt:48)");
            }
            Modifier m564paddingVpY3zN4$default = PaddingKt.m564paddingVpY3zN4$default(SizeKt.fillMaxWidth$default(Modifier.INSTANCE, 0.0f, 1, null), 0.0f, Dp.m6094constructorimpl(5), 1, null);
            CardColors m1627cardColorsro_MJ88 = CardDefaults.INSTANCE.m1627cardColorsro_MJ88(MaterialTheme.INSTANCE.getColorScheme($composer2, MaterialTheme.$stable).getSurface(), 0L, 0L, 0L, $composer2, CardDefaults.$stable << 12, 14);
            CardDefaults cardDefaults = CardDefaults.INSTANCE;
            float m6094constructorimpl = Dp.m6094constructorimpl(1);
            int $this$dp$iv = CardDefaults.$stable;
            final Function2 function23 = extraContent;
            $dirty = $dirty3;
            CardKt.Card(m564paddingVpY3zN4$default, null, m1627cardColorsro_MJ88, cardDefaults.m1628cardElevationaqJV_2Y(m6094constructorimpl, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, $composer2, ($this$dp$iv << 18) | 6, 62), null, ComposableLambdaKt.composableLambda($composer2, 1468166096, true, new Function3<ColumnScope, Composer, Integer, Unit>() { // from class: com.factory.wms.ui.components.CommonKt$LineCard$1
                @Override // kotlin.jvm.functions.Function3
                public /* bridge */ /* synthetic */ Unit invoke(ColumnScope columnScope, Composer composer, Integer num) {
                    invoke(columnScope, composer, num.intValue());
                    return Unit.INSTANCE;
                }

                /* JADX WARN: Removed duplicated region for block: B:24:0x01e3  */
                /* JADX WARN: Removed duplicated region for block: B:27:0x01ef  */
                /* JADX WARN: Removed duplicated region for block: B:35:0x0318  */
                /* JADX WARN: Removed duplicated region for block: B:38:0x0324  */
                /* JADX WARN: Removed duplicated region for block: B:41:0x035d  */
                /* JADX WARN: Removed duplicated region for block: B:46:0x0455  */
                /* JADX WARN: Removed duplicated region for block: B:49:0x05b6  */
                /* JADX WARN: Removed duplicated region for block: B:52:0x05c2  */
                /* JADX WARN: Removed duplicated region for block: B:55:0x05fb  */
                /* JADX WARN: Removed duplicated region for block: B:60:0x078d  */
                /* JADX WARN: Removed duplicated region for block: B:62:? A[RETURN, SYNTHETIC] */
                /* JADX WARN: Removed duplicated region for block: B:64:0x0611 A[ADDED_TO_REGION] */
                /* JADX WARN: Removed duplicated region for block: B:65:0x05c8  */
                /* JADX WARN: Removed duplicated region for block: B:67:0x0373 A[ADDED_TO_REGION] */
                /* JADX WARN: Removed duplicated region for block: B:68:0x032a  */
                /* JADX WARN: Removed duplicated region for block: B:71:0x01f3  */
                /*
                    Code decompiled incorrectly, please refer to instructions dump.
                    To view partially-correct add '--show-bad-code' argument
                */
                public final void invoke(androidx.compose.foundation.layout.ColumnScope r135, androidx.compose.runtime.Composer r136, int r137) {
                    /*
                        Method dump skipped, instructions count: 1937
                        To view this dump add '--comments-level debug' option
                    */
                    throw new UnsupportedOperationException("Method not decompiled: com.factory.wms.ui.components.CommonKt$LineCard$1.invoke(androidx.compose.foundation.layout.ColumnScope, androidx.compose.runtime.Composer, int):void");
                }
            }), $composer2, 196614, 18);
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventEnd();
            }
        } else {
            $composer2.skipToGroupEnd();
            extraContent = function22;
            $dirty = $dirty3;
        }
        ScopeUpdateScope endRestartGroup = $composer2.endRestartGroup();
        if (endRestartGroup != null) {
            final Function2 function24 = extraContent;
            endRestartGroup.updateScope(new Function2() { // from class: com.factory.wms.ui.components.CommonKt$$ExternalSyntheticLambda0
                @Override // kotlin.jvm.functions.Function2
                public final Object invoke(Object obj, Object obj2) {
                    Unit LineCard$lambda$2;
                    LineCard$lambda$2 = CommonKt.LineCard$lambda$2(ScanLine.this, quantityLabel, quantityValue, onQuantityChange, onDelete, function24, $changed, i, (Composer) obj, ((Integer) obj2).intValue());
                    return LineCard$lambda$2;
                }
            });
        }
    }

    public static final double toPositiveDoubleOrZero(String $this$toPositiveDoubleOrZero) {
        Intrinsics.checkNotNullParameter($this$toPositiveDoubleOrZero, "<this>");
        Double doubleOrNull = StringsKt.toDoubleOrNull($this$toPositiveDoubleOrZero);
        if (doubleOrNull != null) {
            return RangesKt.coerceAtLeast(doubleOrNull.doubleValue(), 0.0d);
        }
        return 0.0d;
    }
}
