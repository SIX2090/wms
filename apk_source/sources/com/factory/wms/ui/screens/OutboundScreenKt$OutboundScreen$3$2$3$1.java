package com.factory.wms.ui.screens;

import com.factory.wms.ui.viewmodel.MainViewModel;
import kotlin.Metadata;
import kotlin.Unit;
import kotlin.jvm.functions.Function0;
import kotlin.jvm.internal.FunctionReferenceImpl;

/* compiled from: OutboundScreen.kt */
@Metadata(k = 3, mv = {2, 0, 0}, xi = 48)
/* loaded from: classes4.dex */
/* synthetic */ class OutboundScreenKt$OutboundScreen$3$2$3$1 extends FunctionReferenceImpl implements Function0<Unit> {
    OutboundScreenKt$OutboundScreen$3$2$3$1(Object obj) {
        super(0, obj, MainViewModel.class, "submitOutbound", "submitOutbound()V", 0);
    }

    @Override // kotlin.jvm.functions.Function0
    public /* bridge */ /* synthetic */ Unit invoke() {
        invoke2();
        return Unit.INSTANCE;
    }

    /* renamed from: invoke, reason: avoid collision after fix types in other method */
    public final void invoke2() {
        ((MainViewModel) this.receiver).submitOutbound();
    }
}
