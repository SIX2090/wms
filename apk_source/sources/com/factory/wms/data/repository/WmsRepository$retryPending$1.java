package com.factory.wms.data.repository;

import kotlin.Metadata;
import kotlin.coroutines.Continuation;
import kotlin.coroutines.jvm.internal.ContinuationImpl;
import kotlin.coroutines.jvm.internal.DebugMetadata;

/* compiled from: WmsRepository.kt */
@Metadata(k = 3, mv = {2, 0, 0}, xi = 48)
@DebugMetadata(c = "com.factory.wms.data.repository.WmsRepository", f = "WmsRepository.kt", i = {0, 0, 1, 1, 1, 2, 2, 2, 3, 3, 3, 4, 4, 4, 5, 5, 5, 6, 6}, l = {103, 107, 108, 109, 113, 116, 119}, m = "retryPending", n = {"this", "sent", "this", "doc", "sent", "this", "doc", "sent", "this", "doc", "sent", "this", "doc", "sent", "this", "doc", "sent", "this", "sent"}, s = {"L$0", "I$0", "L$0", "L$2", "I$0", "L$0", "L$2", "I$0", "L$0", "L$2", "I$0", "L$0", "L$2", "I$0", "L$0", "L$2", "I$0", "L$0", "I$0"})
/* loaded from: classes6.dex */
final class WmsRepository$retryPending$1 extends ContinuationImpl {
    int I$0;
    Object L$0;
    Object L$1;
    Object L$2;
    int label;
    /* synthetic */ Object result;
    final /* synthetic */ WmsRepository this$0;

    /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
    WmsRepository$retryPending$1(WmsRepository wmsRepository, Continuation<? super WmsRepository$retryPending$1> continuation) {
        super(continuation);
        this.this$0 = wmsRepository;
    }

    @Override // kotlin.coroutines.jvm.internal.BaseContinuationImpl
    public final Object invokeSuspend(Object obj) {
        this.result = obj;
        this.label |= Integer.MIN_VALUE;
        return this.this$0.retryPending(this);
    }
}
