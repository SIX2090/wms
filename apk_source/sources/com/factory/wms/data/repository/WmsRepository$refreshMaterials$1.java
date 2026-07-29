package com.factory.wms.data.repository;

import kotlin.Metadata;
import kotlin.coroutines.Continuation;
import kotlin.coroutines.jvm.internal.ContinuationImpl;
import kotlin.coroutines.jvm.internal.DebugMetadata;

/* compiled from: WmsRepository.kt */
@Metadata(k = 3, mv = {2, 0, 0}, xi = 48)
@DebugMetadata(c = "com.factory.wms.data.repository.WmsRepository", f = "WmsRepository.kt", i = {0, 1, 1, 2}, l = {24, 27, 33}, m = "refreshMaterials", n = {"this", "this", "materials", "e"}, s = {"L$0", "L$0", "L$1", "L$0"})
/* loaded from: classes6.dex */
final class WmsRepository$refreshMaterials$1 extends ContinuationImpl {
    Object L$0;
    Object L$1;
    int label;
    /* synthetic */ Object result;
    final /* synthetic */ WmsRepository this$0;

    /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
    WmsRepository$refreshMaterials$1(WmsRepository wmsRepository, Continuation<? super WmsRepository$refreshMaterials$1> continuation) {
        super(continuation);
        this.this$0 = wmsRepository;
    }

    @Override // kotlin.coroutines.jvm.internal.BaseContinuationImpl
    public final Object invokeSuspend(Object obj) {
        this.result = obj;
        this.label |= Integer.MIN_VALUE;
        return this.this$0.refreshMaterials(this);
    }
}
