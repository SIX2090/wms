package com.factory.wms.ui.viewmodel;

import com.factory.wms.data.model.MaterialDto;
import com.factory.wms.data.repository.WmsRepository;
import kotlin.Metadata;
import kotlin.ResultKt;
import kotlin.Unit;
import kotlin.coroutines.Continuation;
import kotlin.coroutines.intrinsics.IntrinsicsKt;
import kotlin.coroutines.jvm.internal.DebugMetadata;
import kotlin.coroutines.jvm.internal.SuspendLambda;
import kotlin.jvm.functions.Function2;
import kotlin.text.StringsKt;
import kotlinx.coroutines.CoroutineScope;
import kotlinx.coroutines.flow.MutableStateFlow;

/* compiled from: MainViewModel.kt */
@Metadata(d1 = {"\u0000\n\n\u0000\n\u0002\u0010\u0002\n\u0002\u0018\u0002\u0010\u0000\u001a\u00020\u0001*\u00020\u0002H\n"}, d2 = {"<anonymous>", "", "Lkotlinx/coroutines/CoroutineScope;"}, k = 3, mv = {2, 0, 0}, xi = 48)
@DebugMetadata(c = "com.factory.wms.ui.viewmodel.MainViewModel$queryMaterial$1", f = "MainViewModel.kt", i = {}, l = {327}, m = "invokeSuspend", n = {}, s = {})
/* loaded from: classes10.dex */
final class MainViewModel$queryMaterial$1 extends SuspendLambda implements Function2<CoroutineScope, Continuation<? super Unit>, Object> {
    final /* synthetic */ String $code;
    int label;
    final /* synthetic */ MainViewModel this$0;

    /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
    MainViewModel$queryMaterial$1(MainViewModel mainViewModel, String str, Continuation<? super MainViewModel$queryMaterial$1> continuation) {
        super(2, continuation);
        this.this$0 = mainViewModel;
        this.$code = str;
    }

    @Override // kotlin.coroutines.jvm.internal.BaseContinuationImpl
    public final Continuation<Unit> create(Object obj, Continuation<?> continuation) {
        return new MainViewModel$queryMaterial$1(this.this$0, this.$code, continuation);
    }

    @Override // kotlin.jvm.functions.Function2
    public final Object invoke(CoroutineScope coroutineScope, Continuation<? super Unit> continuation) {
        return ((MainViewModel$queryMaterial$1) create(coroutineScope, continuation)).invokeSuspend(Unit.INSTANCE);
    }

    @Override // kotlin.coroutines.jvm.internal.BaseContinuationImpl
    public final Object invokeSuspend(Object obj) {
        WmsRepository wmsRepository;
        Object $result;
        MutableStateFlow $this$update$iv;
        MainUiState copy;
        MutableStateFlow $this$update$iv2;
        Object prevValue$iv;
        MainUiState copy2;
        Object coroutine_suspended = IntrinsicsKt.getCOROUTINE_SUSPENDED();
        switch (this.label) {
            case 0:
                ResultKt.throwOnFailure(obj);
                wmsRepository = this.this$0.wmsRepository;
                this.label = 1;
                Object materialByCode = wmsRepository.materialByCode(this.$code, this);
                if (materialByCode == coroutine_suspended) {
                    return coroutine_suspended;
                }
                $result = materialByCode;
                break;
            case 1:
                $result = obj;
                ResultKt.throwOnFailure($result);
                break;
            default:
                throw new IllegalStateException("call to 'resume' before 'invoke' with coroutine");
        }
        MaterialDto material = (MaterialDto) $result;
        if (material == null) {
            $this$update$iv2 = this.this$0._uiState;
            String str = this.$code;
            do {
                prevValue$iv = $this$update$iv2.getValue();
                MainUiState it = (MainUiState) prevValue$iv;
                copy2 = it.copy((r32 & 1) != 0 ? it.isLoggedIn : false, (r32 & 2) != 0 ? it.username : null, (r32 & 4) != 0 ? it.selectedTab : null, (r32 & 8) != 0 ? it.loading : false, (r32 & 16) != 0 ? it.message : null, (r32 & 32) != 0 ? it.error : "未找到物料：" + StringsKt.trim((CharSequence) str).toString(), (r32 & 64) != 0 ? it.inboundLines : null, (r32 & 128) != 0 ? it.outboundLines : null, (r32 & 256) != 0 ? it.queryMaterial : null, (r32 & 512) != 0 ? it.stocktakeLines : null, (r32 & 1024) != 0 ? it.stocktakeMode : null, (r32 & 2048) != 0 ? it.stocktakeWarehouse : null, (r32 & 4096) != 0 ? it.searchResults : null, (r32 & 8192) != 0 ? it.pendingCount : 0, (r32 & 16384) != 0 ? it.baseUrl : null);
            } while (!$this$update$iv2.compareAndSet(prevValue$iv, copy2));
        } else {
            $this$update$iv = this.this$0._uiState;
            while (true) {
                Object prevValue$iv2 = $this$update$iv.getValue();
                MainUiState it2 = (MainUiState) prevValue$iv2;
                MutableStateFlow $this$update$iv3 = $this$update$iv;
                copy = it2.copy((r32 & 1) != 0 ? it2.isLoggedIn : false, (r32 & 2) != 0 ? it2.username : null, (r32 & 4) != 0 ? it2.selectedTab : null, (r32 & 8) != 0 ? it2.loading : false, (r32 & 16) != 0 ? it2.message : "已带出 " + material.getCode(), (r32 & 32) != 0 ? it2.error : null, (r32 & 64) != 0 ? it2.inboundLines : null, (r32 & 128) != 0 ? it2.outboundLines : null, (r32 & 256) != 0 ? it2.queryMaterial : material, (r32 & 512) != 0 ? it2.stocktakeLines : null, (r32 & 1024) != 0 ? it2.stocktakeMode : null, (r32 & 2048) != 0 ? it2.stocktakeWarehouse : null, (r32 & 4096) != 0 ? it2.searchResults : null, (r32 & 8192) != 0 ? it2.pendingCount : 0, (r32 & 16384) != 0 ? it2.baseUrl : null);
                if (!$this$update$iv3.compareAndSet(prevValue$iv2, copy)) {
                    $this$update$iv = $this$update$iv3;
                }
            }
        }
        return Unit.INSTANCE;
    }
}
