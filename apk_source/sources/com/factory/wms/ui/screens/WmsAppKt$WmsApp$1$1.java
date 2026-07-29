package com.factory.wms.ui.screens;

import androidx.compose.material3.SnackbarHostState;
import androidx.compose.runtime.State;
import com.factory.wms.ui.viewmodel.MainUiState;
import com.factory.wms.ui.viewmodel.MainViewModel;
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

/* compiled from: WmsApp.kt */
@Metadata(d1 = {"\u0000\n\n\u0000\n\u0002\u0010\u0002\n\u0002\u0018\u0002\u0010\u0000\u001a\u00020\u0001*\u00020\u0002H\n"}, d2 = {"<anonymous>", "", "Lkotlinx/coroutines/CoroutineScope;"}, k = 3, mv = {2, 0, 0}, xi = 48)
@DebugMetadata(c = "com.factory.wms.ui.screens.WmsAppKt$WmsApp$1$1", f = "WmsApp.kt", i = {}, l = {34}, m = "invokeSuspend", n = {}, s = {})
/* loaded from: classes4.dex */
final class WmsAppKt$WmsApp$1$1 extends SuspendLambda implements Function2<CoroutineScope, Continuation<? super Unit>, Object> {
    final /* synthetic */ SnackbarHostState $snackbarHostState;
    final /* synthetic */ State<MainUiState> $state$delegate;
    final /* synthetic */ MainViewModel $viewModel;
    int label;

    /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
    WmsAppKt$WmsApp$1$1(SnackbarHostState snackbarHostState, MainViewModel mainViewModel, State<MainUiState> state, Continuation<? super WmsAppKt$WmsApp$1$1> continuation) {
        super(2, continuation);
        this.$snackbarHostState = snackbarHostState;
        this.$viewModel = mainViewModel;
        this.$state$delegate = state;
    }

    @Override // kotlin.coroutines.jvm.internal.BaseContinuationImpl
    public final Continuation<Unit> create(Object obj, Continuation<?> continuation) {
        return new WmsAppKt$WmsApp$1$1(this.$snackbarHostState, this.$viewModel, this.$state$delegate, continuation);
    }

    @Override // kotlin.jvm.functions.Function2
    public final Object invoke(CoroutineScope coroutineScope, Continuation<? super Unit> continuation) {
        return ((WmsAppKt$WmsApp$1$1) create(coroutineScope, continuation)).invokeSuspend(Unit.INSTANCE);
    }

    @Override // kotlin.coroutines.jvm.internal.BaseContinuationImpl
    public final Object invokeSuspend(Object $result) {
        MainUiState WmsApp$lambda$0;
        MainUiState WmsApp$lambda$02;
        Object coroutine_suspended = IntrinsicsKt.getCOROUTINE_SUSPENDED();
        switch (this.label) {
            case 0:
                ResultKt.throwOnFailure($result);
                WmsApp$lambda$0 = WmsAppKt.WmsApp$lambda$0(this.$state$delegate);
                String text = WmsApp$lambda$0.getError();
                if (text == null) {
                    WmsApp$lambda$02 = WmsAppKt.WmsApp$lambda$0(this.$state$delegate);
                    text = WmsApp$lambda$02.getMessage();
                }
                String str = text;
                if (!(str == null || StringsKt.isBlank(str))) {
                    this.label = 1;
                    if (SnackbarHostState.showSnackbar$default(this.$snackbarHostState, text, null, false, null, this, 14, null) == coroutine_suspended) {
                        return coroutine_suspended;
                    }
                    this.$viewModel.clearMessage();
                }
                return Unit.INSTANCE;
            case 1:
                ResultKt.throwOnFailure($result);
                this.$viewModel.clearMessage();
                return Unit.INSTANCE;
            default:
                throw new IllegalStateException("call to 'resume' before 'invoke' with coroutine");
        }
    }
}
