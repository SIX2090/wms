package com.factory.wms.data.repository;

import kotlin.Metadata;
import kotlin.coroutines.Continuation;
import kotlin.coroutines.jvm.internal.ContinuationImpl;
import kotlin.coroutines.jvm.internal.DebugMetadata;

/* compiled from: WmsRepository.kt */
@Metadata(k = 3, mv = {2, 0, 0}, xi = 48)
@DebugMetadata(c = "com.factory.wms.data.repository.WmsRepository", f = "WmsRepository.kt", i = {}, l = {125}, m = "pendingCount", n = {}, s = {})
/* loaded from: classes6.dex */
final class WmsRepository$pendingCount$1 extends ContinuationImpl {
    int label;
    /* synthetic */ Object result;
    final /* synthetic */ WmsRepository this$0;

    /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
    WmsRepository$pendingCount$1(WmsRepository wmsRepository, Continuation<? super WmsRepository$pendingCount$1> continuation) {
        super(continuation);
        this.this$0 = wmsRepository;
    }

    @Override // kotlin.coroutines.jvm.internal.BaseContinuationImpl
    public final Object invokeSuspend(Object obj) {
        this.result = obj;
        this.label |= Integer.MIN_VALUE;
        return this.this$0.pendingCount(this);
    }
}
