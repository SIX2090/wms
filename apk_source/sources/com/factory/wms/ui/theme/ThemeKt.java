package com.factory.wms.ui.theme;

import androidx.compose.material3.ColorScheme;
import androidx.compose.material3.ColorSchemeKt;
import androidx.compose.material3.MaterialTheme;
import androidx.compose.material3.MaterialThemeKt;
import androidx.compose.runtime.Composer;
import androidx.compose.runtime.ComposerKt;
import androidx.compose.runtime.RecomposeScopeImplKt;
import androidx.compose.runtime.ScopeUpdateScope;
import androidx.compose.ui.graphics.Color;
import androidx.compose.ui.graphics.ColorKt;
import kotlin.Metadata;
import kotlin.Unit;
import kotlin.jvm.functions.Function2;
import kotlin.jvm.internal.Intrinsics;

/* compiled from: Theme.kt */
@Metadata(d1 = {"\u0000\u001a\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\b\u0002\u001a \u0010\u0002\u001a\u00020\u00032\u0011\u0010\u0004\u001a\r\u0012\u0004\u0012\u00020\u00030\u0005¢\u0006\u0002\b\u0006H\u0007¢\u0006\u0002\u0010\u0007\"\u000e\u0010\u0000\u001a\u00020\u0001X\u0082\u0004¢\u0006\u0002\n\u0000¨\u0006\b"}, d2 = {"LightColors", "Landroidx/compose/material3/ColorScheme;", "FactoryWmsTheme", "", "content", "Lkotlin/Function0;", "Landroidx/compose/runtime/Composable;", "(Lkotlin/jvm/functions/Function2;Landroidx/compose/runtime/Composer;I)V", "app_debug"}, k = 2, mv = {2, 0, 0}, xi = 48)
/* loaded from: classes3.dex */
public final class ThemeKt {
    private static final ColorScheme LightColors = ColorSchemeKt.m1738lightColorSchemeCXl9yA$default(ColorKt.Color(4280172719L), Color.INSTANCE.m3783getWhite0d7_KjU(), 0, 0, 0, ColorKt.Color(4279203438L), 0, 0, 0, ColorKt.Color(4287774734L), 0, 0, 0, ColorKt.Color(4294375419L), 0, Color.INSTANCE.m3783getWhite0d7_KjU(), 0, 0, 0, 0, 0, 0, ColorKt.Color(4290321436L), 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, -4235812, 15, null);

    /* JADX INFO: Access modifiers changed from: private */
    public static final Unit FactoryWmsTheme$lambda$0(Function2 function2, int i, Composer composer, int i2) {
        FactoryWmsTheme(function2, composer, RecomposeScopeImplKt.updateChangedFlags(i | 1));
        return Unit.INSTANCE;
    }

    public static final void FactoryWmsTheme(final Function2<? super Composer, ? super Integer, Unit> content, Composer $composer, final int $changed) {
        Intrinsics.checkNotNullParameter(content, "content");
        Composer $composer2 = $composer.startRestartGroup(874290511);
        ComposerKt.sourceInformation($composer2, "C(FactoryWmsTheme)22@705L10,20@620L128:Theme.kt#hgqbkh");
        int $dirty = $changed;
        if (($changed & 6) == 0) {
            $dirty |= $composer2.changedInstance(content) ? 4 : 2;
        }
        int $dirty2 = $dirty;
        if (($dirty2 & 3) != 2 || !$composer2.getSkipping()) {
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventStart(874290511, $dirty2, -1, "com.factory.wms.ui.theme.FactoryWmsTheme (Theme.kt:19)");
            }
            MaterialThemeKt.MaterialTheme(LightColors, null, MaterialTheme.INSTANCE.getTypography($composer2, MaterialTheme.$stable), content, $composer2, (($dirty2 << 9) & 7168) | 6, 2);
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventEnd();
            }
        } else {
            $composer2.skipToGroupEnd();
        }
        ScopeUpdateScope endRestartGroup = $composer2.endRestartGroup();
        if (endRestartGroup != null) {
            endRestartGroup.updateScope(new Function2() { // from class: com.factory.wms.ui.theme.ThemeKt$$ExternalSyntheticLambda0
                @Override // kotlin.jvm.functions.Function2
                public final Object invoke(Object obj, Object obj2) {
                    Unit FactoryWmsTheme$lambda$0;
                    FactoryWmsTheme$lambda$0 = ThemeKt.FactoryWmsTheme$lambda$0(Function2.this, $changed, (Composer) obj, ((Integer) obj2).intValue());
                    return FactoryWmsTheme$lambda$0;
                }
            });
        }
    }
}
