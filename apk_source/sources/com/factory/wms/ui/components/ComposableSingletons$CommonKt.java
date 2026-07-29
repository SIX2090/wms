package com.factory.wms.ui.components;

import androidx.compose.material.icons.Icons;
import androidx.compose.material.icons.filled.DeleteKt;
import androidx.compose.material3.IconKt;
import androidx.compose.runtime.Composer;
import androidx.compose.runtime.ComposerKt;
import androidx.compose.runtime.internal.ComposableLambdaKt;
import androidx.compose.ui.Modifier;
import kotlin.Metadata;
import kotlin.Unit;
import kotlin.jvm.functions.Function2;

/* compiled from: Common.kt */
@Metadata(k = 3, mv = {2, 0, 0}, xi = 48)
/* loaded from: classes4.dex */
public final class ComposableSingletons$CommonKt {
    public static final ComposableSingletons$CommonKt INSTANCE = new ComposableSingletons$CommonKt();

    /* renamed from: lambda-1, reason: not valid java name */
    public static Function2<Composer, Integer, Unit> f78lambda1 = ComposableLambdaKt.composableLambdaInstance(-1572313675, false, new Function2<Composer, Integer, Unit>() { // from class: com.factory.wms.ui.components.ComposableSingletons$CommonKt$lambda-1$1
        @Override // kotlin.jvm.functions.Function2
        public /* bridge */ /* synthetic */ Unit invoke(Composer composer, Integer num) {
            invoke(composer, num.intValue());
            return Unit.INSTANCE;
        }

        public final void invoke(Composer $composer, int $changed) {
            ComposerKt.sourceInformation($composer, "C:Common.kt#qrwxji");
            if (($changed & 3) == 2 && $composer.getSkipping()) {
                $composer.skipToGroupEnd();
                return;
            }
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventStart(-1572313675, $changed, -1, "com.factory.wms.ui.components.ComposableSingletons$CommonKt.lambda-1.<anonymous> (Common.kt:47)");
            }
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventEnd();
            }
        }
    });

    /* renamed from: lambda-2, reason: not valid java name */
    public static Function2<Composer, Integer, Unit> f79lambda2 = ComposableLambdaKt.composableLambdaInstance(-392441081, false, new Function2<Composer, Integer, Unit>() { // from class: com.factory.wms.ui.components.ComposableSingletons$CommonKt$lambda-2$1
        @Override // kotlin.jvm.functions.Function2
        public /* bridge */ /* synthetic */ Unit invoke(Composer composer, Integer num) {
            invoke(composer, num.intValue());
            return Unit.INSTANCE;
        }

        public final void invoke(Composer $composer, int $changed) {
            ComposerKt.sourceInformation($composer, "C68@2779L53:Common.kt#qrwxji");
            if (($changed & 3) == 2 && $composer.getSkipping()) {
                $composer.skipToGroupEnd();
                return;
            }
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventStart(-392441081, $changed, -1, "com.factory.wms.ui.components.ComposableSingletons$CommonKt.lambda-2.<anonymous> (Common.kt:68)");
            }
            IconKt.m1937Iconww6aTOc(DeleteKt.getDelete(Icons.INSTANCE.getDefault()), "删除", (Modifier) null, 0L, $composer, 48, 12);
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventEnd();
            }
        }
    });

    /* renamed from: getLambda-1$app_debug, reason: not valid java name */
    public final Function2<Composer, Integer, Unit> m6405getLambda1$app_debug() {
        return f78lambda1;
    }

    /* renamed from: getLambda-2$app_debug, reason: not valid java name */
    public final Function2<Composer, Integer, Unit> m6406getLambda2$app_debug() {
        return f79lambda2;
    }
}
