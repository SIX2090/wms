package com.factory.wms.ui.screens;

import com.factory.wms.ui.viewmodel.MainViewModel;
import kotlin.Metadata;
import kotlin.Unit;
import kotlin.jvm.functions.Function1;
import kotlin.jvm.internal.FunctionReferenceImpl;
import kotlin.jvm.internal.Intrinsics;

/* compiled from: StocktakeScreen.kt */
@Metadata(k = 3, mv = {2, 0, 0}, xi = 48)
/* loaded from: classes4.dex */
/* synthetic */ class StocktakeScreenKt$StocktakeScreen$3$2$1 extends FunctionReferenceImpl implements Function1<String, Unit> {
    StocktakeScreenKt$StocktakeScreen$3$2$1(Object obj) {
        super(1, obj, MainViewModel.class, "setStocktakeWarehouse", "setStocktakeWarehouse(Ljava/lang/String;)V", 0);
    }

    @Override // kotlin.jvm.functions.Function1
    public /* bridge */ /* synthetic */ Unit invoke(String str) {
        invoke2(str);
        return Unit.INSTANCE;
    }

    /* renamed from: invoke, reason: avoid collision after fix types in other method */
    public final void invoke2(String p0) {
        Intrinsics.checkNotNullParameter(p0, "p0");
        ((MainViewModel) this.receiver).setStocktakeWarehouse(p0);
    }
}
