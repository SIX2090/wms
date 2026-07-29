package com.factory.wms.ui.viewmodel;

import kotlin.Metadata;
import kotlin.coroutines.Continuation;
import kotlin.coroutines.jvm.internal.ContinuationImpl;
import kotlin.coroutines.jvm.internal.DebugMetadata;

/* compiled from: MainViewModel.kt */
@Metadata(k = 3, mv = {2, 0, 0}, xi = 48)
@DebugMetadata(c = "com.factory.wms.ui.viewmodel.MainViewModel", f = "MainViewModel.kt", i = {0}, l = {361}, m = "updatePendingCount", n = {"this"}, s = {"L$0"})
/* loaded from: classes10.dex */
final class MainViewModel$updatePendingCount$1 extends ContinuationImpl {
    Object L$0;
    int label;
    /* synthetic */ Object result;
    final /* synthetic */ MainViewModel this$0;

    /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
    MainViewModel$updatePendingCount$1(MainViewModel mainViewModel, Continuation<? super MainViewModel$updatePendingCount$1> continuation) {
        super(continuation);
        this.this$0 = mainViewModel;
    }

    @Override // kotlin.coroutines.jvm.internal.BaseContinuationImpl
    public final Object invokeSuspend(Object obj) {
        Object updatePendingCount;
        this.result = obj;
        this.label |= Integer.MIN_VALUE;
        updatePendingCount = this.this$0.updatePendingCount(this);
        return updatePendingCount;
    }
}
