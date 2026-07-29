package com.factory.wms.data.repository;

import kotlin.Metadata;
import kotlin.coroutines.Continuation;
import kotlin.coroutines.jvm.internal.ContinuationImpl;
import kotlin.coroutines.jvm.internal.DebugMetadata;

/* compiled from: WmsRepository.kt */
@Metadata(k = 3, mv = {2, 0, 0}, xi = 48)
@DebugMetadata(c = "com.factory.wms.data.repository.WmsRepository", f = "WmsRepository.kt", i = {0, 0, 0}, l = {133, 140}, m = "submitOrCache", n = {"this", "type", "request"}, s = {"L$0", "L$1", "L$2"})
/* loaded from: classes6.dex */
final class WmsRepository$submitOrCache$1<T> extends ContinuationImpl {
    Object L$0;
    Object L$1;
    Object L$2;
    int label;
    /* synthetic */ Object result;
    final /* synthetic */ WmsRepository this$0;

    /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
    WmsRepository$submitOrCache$1(WmsRepository wmsRepository, Continuation<? super WmsRepository$submitOrCache$1> continuation) {
        super(continuation);
        this.this$0 = wmsRepository;
    }

    @Override // kotlin.coroutines.jvm.internal.BaseContinuationImpl
    public final Object invokeSuspend(Object obj) {
        Object submitOrCache;
        this.result = obj;
        this.label |= Integer.MIN_VALUE;
        submitOrCache = this.this$0.submitOrCache(null, null, null, this);
        return submitOrCache;
    }
}
