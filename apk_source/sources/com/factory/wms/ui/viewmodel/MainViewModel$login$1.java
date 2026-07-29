package com.factory.wms.ui.viewmodel;

import com.factory.wms.data.repository.AuthRepository;
import com.factory.wms.data.repository.NetworkResult;
import kotlin.Metadata;
import kotlin.NoWhenBranchMatchedException;
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
@DebugMetadata(c = "com.factory.wms.ui.viewmodel.MainViewModel$login$1", f = "MainViewModel.kt", i = {}, l = {87}, m = "invokeSuspend", n = {}, s = {})
/* loaded from: classes10.dex */
final class MainViewModel$login$1 extends SuspendLambda implements Function2<CoroutineScope, Continuation<? super Unit>, Object> {
    final /* synthetic */ String $baseUrl;
    final /* synthetic */ String $password;
    final /* synthetic */ String $username;
    int label;
    final /* synthetic */ MainViewModel this$0;

    /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
    MainViewModel$login$1(MainViewModel mainViewModel, String str, String str2, String str3, Continuation<? super MainViewModel$login$1> continuation) {
        super(2, continuation);
        this.this$0 = mainViewModel;
        this.$username = str;
        this.$password = str2;
        this.$baseUrl = str3;
    }

    @Override // kotlin.coroutines.jvm.internal.BaseContinuationImpl
    public final Continuation<Unit> create(Object obj, Continuation<?> continuation) {
        return new MainViewModel$login$1(this.this$0, this.$username, this.$password, this.$baseUrl, continuation);
    }

    @Override // kotlin.jvm.functions.Function2
    public final Object invoke(CoroutineScope coroutineScope, Continuation<? super Unit> continuation) {
        return ((MainViewModel$login$1) create(coroutineScope, continuation)).invokeSuspend(Unit.INSTANCE);
    }

    @Override // kotlin.coroutines.jvm.internal.BaseContinuationImpl
    public final Object invokeSuspend(Object obj) {
        MutableStateFlow $this$update$iv;
        Object prevValue$iv;
        MainUiState copy;
        AuthRepository authRepository;
        Object $result;
        MutableStateFlow $this$update$iv2;
        Object prevValue$iv2;
        MainUiState copy2;
        MutableStateFlow $this$update$iv3;
        Object prevValue$iv3;
        AuthRepository authRepository2;
        AuthRepository authRepository3;
        MainUiState copy3;
        Object coroutine_suspended = IntrinsicsKt.getCOROUTINE_SUSPENDED();
        switch (this.label) {
            case 0:
                ResultKt.throwOnFailure(obj);
                $this$update$iv = this.this$0._uiState;
                do {
                    prevValue$iv = $this$update$iv.getValue();
                    MainUiState it = (MainUiState) prevValue$iv;
                    copy = it.copy((r32 & 1) != 0 ? it.isLoggedIn : false, (r32 & 2) != 0 ? it.username : null, (r32 & 4) != 0 ? it.selectedTab : null, (r32 & 8) != 0 ? it.loading : true, (r32 & 16) != 0 ? it.message : null, (r32 & 32) != 0 ? it.error : null, (r32 & 64) != 0 ? it.inboundLines : null, (r32 & 128) != 0 ? it.outboundLines : null, (r32 & 256) != 0 ? it.queryMaterial : null, (r32 & 512) != 0 ? it.stocktakeLines : null, (r32 & 1024) != 0 ? it.stocktakeMode : null, (r32 & 2048) != 0 ? it.stocktakeWarehouse : null, (r32 & 4096) != 0 ? it.searchResults : null, (r32 & 8192) != 0 ? it.pendingCount : 0, (r32 & 16384) != 0 ? it.baseUrl : null);
                } while (!$this$update$iv.compareAndSet(prevValue$iv, copy));
                authRepository = this.this$0.authRepository;
                this.label = 1;
                Object login = authRepository.login(StringsKt.trim((CharSequence) this.$username).toString(), this.$password, this.$baseUrl, this);
                if (login != coroutine_suspended) {
                    $result = login;
                    break;
                } else {
                    return coroutine_suspended;
                }
            case 1:
                $result = obj;
                ResultKt.throwOnFailure($result);
                break;
            default:
                throw new IllegalStateException("call to 'resume' before 'invoke' with coroutine");
        }
        NetworkResult result = (NetworkResult) $result;
        if (result instanceof NetworkResult.Success) {
            $this$update$iv3 = this.this$0._uiState;
            MainViewModel mainViewModel = this.this$0;
            do {
                prevValue$iv3 = $this$update$iv3.getValue();
                MainUiState it2 = (MainUiState) prevValue$iv3;
                authRepository2 = mainViewModel.authRepository;
                String username = authRepository2.username();
                authRepository3 = mainViewModel.authRepository;
                copy3 = it2.copy((r32 & 1) != 0 ? it2.isLoggedIn : true, (r32 & 2) != 0 ? it2.username : username, (r32 & 4) != 0 ? it2.selectedTab : null, (r32 & 8) != 0 ? it2.loading : false, (r32 & 16) != 0 ? it2.message : ((NetworkResult.Success) result).getMessage(), (r32 & 32) != 0 ? it2.error : null, (r32 & 64) != 0 ? it2.inboundLines : null, (r32 & 128) != 0 ? it2.outboundLines : null, (r32 & 256) != 0 ? it2.queryMaterial : null, (r32 & 512) != 0 ? it2.stocktakeLines : null, (r32 & 1024) != 0 ? it2.stocktakeMode : null, (r32 & 2048) != 0 ? it2.stocktakeWarehouse : null, (r32 & 4096) != 0 ? it2.searchResults : null, (r32 & 8192) != 0 ? it2.pendingCount : 0, (r32 & 16384) != 0 ? it2.baseUrl : authRepository3.baseUrl());
            } while (!$this$update$iv3.compareAndSet(prevValue$iv3, copy3));
            this.this$0.refreshMaterials();
            this.this$0.retryPending();
        } else {
            if (!(result instanceof NetworkResult.Error)) {
                throw new NoWhenBranchMatchedException();
            }
            $this$update$iv2 = this.this$0._uiState;
            do {
                prevValue$iv2 = $this$update$iv2.getValue();
                MainUiState it3 = (MainUiState) prevValue$iv2;
                copy2 = it3.copy((r32 & 1) != 0 ? it3.isLoggedIn : false, (r32 & 2) != 0 ? it3.username : null, (r32 & 4) != 0 ? it3.selectedTab : null, (r32 & 8) != 0 ? it3.loading : false, (r32 & 16) != 0 ? it3.message : null, (r32 & 32) != 0 ? it3.error : ((NetworkResult.Error) result).getMessage(), (r32 & 64) != 0 ? it3.inboundLines : null, (r32 & 128) != 0 ? it3.outboundLines : null, (r32 & 256) != 0 ? it3.queryMaterial : null, (r32 & 512) != 0 ? it3.stocktakeLines : null, (r32 & 1024) != 0 ? it3.stocktakeMode : null, (r32 & 2048) != 0 ? it3.stocktakeWarehouse : null, (r32 & 4096) != 0 ? it3.searchResults : null, (r32 & 8192) != 0 ? it3.pendingCount : 0, (r32 & 16384) != 0 ? it3.baseUrl : null);
            } while (!$this$update$iv2.compareAndSet(prevValue$iv2, copy2));
        }
        return Unit.INSTANCE;
    }
}
