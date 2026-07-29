package com.factory.wms.data.repository;

import androidx.core.view.MotionEventCompat;
import kotlin.Metadata;
import kotlin.coroutines.Continuation;
import kotlin.coroutines.jvm.internal.ContinuationImpl;
import kotlin.coroutines.jvm.internal.DebugMetadata;

/* compiled from: WmsRepository.kt */
@Metadata(k = 3, mv = {2, 0, 0}, xi = 48)
@DebugMetadata(c = "com.factory.wms.data.repository.WmsRepository", f = "WmsRepository.kt", i = {0, 0, 1, 1, 1}, l = {MotionEventCompat.AXIS_GENERIC_15, 49, 55}, m = "findMaterial", n = {"this", "keyword", "this", "keyword", "materials"}, s = {"L$0", "L$1", "L$0", "L$1", "L$2"})
/* loaded from: classes6.dex */
final class WmsRepository$findMaterial$1 extends ContinuationImpl {
    Object L$0;
    Object L$1;
    Object L$2;
    int label;
    /* synthetic */ Object result;
    final /* synthetic */ WmsRepository this$0;

    /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
    WmsRepository$findMaterial$1(WmsRepository wmsRepository, Continuation<? super WmsRepository$findMaterial$1> continuation) {
        super(continuation);
        this.this$0 = wmsRepository;
    }

    @Override // kotlin.coroutines.jvm.internal.BaseContinuationImpl
    public final Object invokeSuspend(Object obj) {
        this.result = obj;
        this.label |= Integer.MIN_VALUE;
        return this.this$0.findMaterial(null, this);
    }
}
