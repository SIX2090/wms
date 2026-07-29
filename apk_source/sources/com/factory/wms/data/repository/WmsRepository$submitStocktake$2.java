package com.factory.wms.data.repository;

import com.factory.wms.data.api.WmsApiService;
import com.factory.wms.data.model.ApiEnvelope;
import com.factory.wms.data.model.StocktakeRequest;
import kotlin.Metadata;
import kotlin.ResultKt;
import kotlin.Unit;
import kotlin.coroutines.Continuation;
import kotlin.coroutines.intrinsics.IntrinsicsKt;
import kotlin.coroutines.jvm.internal.DebugMetadata;
import kotlin.coroutines.jvm.internal.SuspendLambda;
import kotlin.jvm.functions.Function1;

/* compiled from: WmsRepository.kt */
@Metadata(d1 = {"\u0000\u0006\n\u0000\n\u0002\u0018\u0002\u0010\u0000\u001a\u0006\u0012\u0002\b\u00030\u0001H\n"}, d2 = {"<anonymous>", "Lcom/factory/wms/data/model/ApiEnvelope;"}, k = 3, mv = {2, 0, 0}, xi = 48)
@DebugMetadata(c = "com.factory.wms.data.repository.WmsRepository$submitStocktake$2", f = "WmsRepository.kt", i = {}, l = {97}, m = "invokeSuspend", n = {}, s = {})
/* loaded from: classes6.dex */
final class WmsRepository$submitStocktake$2 extends SuspendLambda implements Function1<Continuation<? super ApiEnvelope<?>>, Object> {
    final /* synthetic */ StocktakeRequest $request;
    int label;
    final /* synthetic */ WmsRepository this$0;

    /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
    WmsRepository$submitStocktake$2(WmsRepository wmsRepository, StocktakeRequest stocktakeRequest, Continuation<? super WmsRepository$submitStocktake$2> continuation) {
        super(1, continuation);
        this.this$0 = wmsRepository;
        this.$request = stocktakeRequest;
    }

    @Override // kotlin.coroutines.jvm.internal.BaseContinuationImpl
    public final Continuation<Unit> create(Continuation<?> continuation) {
        return new WmsRepository$submitStocktake$2(this.this$0, this.$request, continuation);
    }

    @Override // kotlin.jvm.functions.Function1
    public final Object invoke(Continuation<? super ApiEnvelope<?>> continuation) {
        return ((WmsRepository$submitStocktake$2) create(continuation)).invokeSuspend(Unit.INSTANCE);
    }

    @Override // kotlin.coroutines.jvm.internal.BaseContinuationImpl
    public final Object invokeSuspend(Object $result) {
        WmsApiService wmsApiService;
        Object coroutine_suspended = IntrinsicsKt.getCOROUTINE_SUSPENDED();
        switch (this.label) {
            case 0:
                ResultKt.throwOnFailure($result);
                wmsApiService = this.this$0.api;
                this.label = 1;
                Object submitStocktake = wmsApiService.submitStocktake(this.$request, this);
                if (submitStocktake == coroutine_suspended) {
                    return coroutine_suspended;
                }
                return submitStocktake;
            case 1:
                ResultKt.throwOnFailure($result);
                return $result;
            default:
                throw new IllegalStateException("call to 'resume' before 'invoke' with coroutine");
        }
    }
}
