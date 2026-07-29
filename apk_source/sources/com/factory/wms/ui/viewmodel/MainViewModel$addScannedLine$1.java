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
import kotlinx.coroutines.CoroutineScope;
import kotlinx.coroutines.flow.MutableStateFlow;

/* compiled from: MainViewModel.kt */
@Metadata(d1 = {"\u0000\n\n\u0000\n\u0002\u0010\u0002\n\u0002\u0018\u0002\u0010\u0000\u001a\u00020\u0001*\u00020\u0002H\n"}, d2 = {"<anonymous>", "", "Lkotlinx/coroutines/CoroutineScope;"}, k = 3, mv = {2, 0, 0}, xi = 48)
@DebugMetadata(c = "com.factory.wms.ui.viewmodel.MainViewModel$addScannedLine$1", f = "MainViewModel.kt", i = {}, l = {316}, m = "invokeSuspend", n = {}, s = {})
/* loaded from: classes10.dex */
final class MainViewModel$addScannedLine$1 extends SuspendLambda implements Function2<CoroutineScope, Continuation<? super Unit>, Object> {
    final /* synthetic */ String $code;
    final /* synthetic */ MainTab $tab;
    int label;
    final /* synthetic */ MainViewModel this$0;

    /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
    MainViewModel$addScannedLine$1(MainViewModel mainViewModel, String str, MainTab mainTab, Continuation<? super MainViewModel$addScannedLine$1> continuation) {
        super(2, continuation);
        this.this$0 = mainViewModel;
        this.$code = str;
        this.$tab = mainTab;
    }

    @Override // kotlin.coroutines.jvm.internal.BaseContinuationImpl
    public final Continuation<Unit> create(Object obj, Continuation<?> continuation) {
        return new MainViewModel$addScannedLine$1(this.this$0, this.$code, this.$tab, continuation);
    }

    @Override // kotlin.jvm.functions.Function2
    public final Object invoke(CoroutineScope coroutineScope, Continuation<? super Unit> continuation) {
        return ((MainViewModel$addScannedLine$1) create(coroutineScope, continuation)).invokeSuspend(Unit.INSTANCE);
    }

    @Override // kotlin.coroutines.jvm.internal.BaseContinuationImpl
    public final Object invokeSuspend(Object obj) {
        WmsRepository wmsRepository;
        Object $result;
        MutableStateFlow $this$update$iv;
        Object prevValue$iv;
        MainUiState copy;
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
            $this$update$iv = this.this$0._uiState;
            String str = this.$code;
            do {
                prevValue$iv = $this$update$iv.getValue();
                MainUiState it = (MainUiState) prevValue$iv;
                copy = it.copy((r32 & 1) != 0 ? it.isLoggedIn : false, (r32 & 2) != 0 ? it.username : null, (r32 & 4) != 0 ? it.selectedTab : null, (r32 & 8) != 0 ? it.loading : false, (r32 & 16) != 0 ? it.message : null, (r32 & 32) != 0 ? it.error : "未找到物料：" + str, (r32 & 64) != 0 ? it.inboundLines : null, (r32 & 128) != 0 ? it.outboundLines : null, (r32 & 256) != 0 ? it.queryMaterial : null, (r32 & 512) != 0 ? it.stocktakeLines : null, (r32 & 1024) != 0 ? it.stocktakeMode : null, (r32 & 2048) != 0 ? it.stocktakeWarehouse : null, (r32 & 4096) != 0 ? it.searchResults : null, (r32 & 8192) != 0 ? it.pendingCount : 0, (r32 & 16384) != 0 ? it.baseUrl : null);
            } while (!$this$update$iv.compareAndSet(prevValue$iv, copy));
        } else {
            this.this$0.appendLine(this.$tab, material);
        }
        return Unit.INSTANCE;
    }
}
