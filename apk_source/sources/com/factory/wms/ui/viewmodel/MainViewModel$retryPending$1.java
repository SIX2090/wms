package com.factory.wms.ui.viewmodel;

import kotlin.Metadata;
import kotlin.Unit;
import kotlin.coroutines.Continuation;
import kotlin.coroutines.jvm.internal.DebugMetadata;
import kotlin.coroutines.jvm.internal.SuspendLambda;
import kotlin.jvm.functions.Function2;
import kotlinx.coroutines.CoroutineScope;

/* compiled from: MainViewModel.kt */
@Metadata(d1 = {"\u0000\n\n\u0000\n\u0002\u0010\u0002\n\u0002\u0018\u0002\u0010\u0000\u001a\u00020\u0001*\u00020\u0002H\n"}, d2 = {"<anonymous>", "", "Lkotlinx/coroutines/CoroutineScope;"}, k = 3, mv = {2, 0, 0}, xi = 48)
@DebugMetadata(c = "com.factory.wms.ui.viewmodel.MainViewModel$retryPending$1", f = "MainViewModel.kt", i = {1}, l = {286, 287}, m = "invokeSuspend", n = {"sent"}, s = {"I$0"})
/* loaded from: classes10.dex */
final class MainViewModel$retryPending$1 extends SuspendLambda implements Function2<CoroutineScope, Continuation<? super Unit>, Object> {
    int I$0;
    int label;
    final /* synthetic */ MainViewModel this$0;

    /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
    MainViewModel$retryPending$1(MainViewModel mainViewModel, Continuation<? super MainViewModel$retryPending$1> continuation) {
        super(2, continuation);
        this.this$0 = mainViewModel;
    }

    @Override // kotlin.coroutines.jvm.internal.BaseContinuationImpl
    public final Continuation<Unit> create(Object obj, Continuation<?> continuation) {
        return new MainViewModel$retryPending$1(this.this$0, continuation);
    }

    @Override // kotlin.jvm.functions.Function2
    public final Object invoke(CoroutineScope coroutineScope, Continuation<? super Unit> continuation) {
        return ((MainViewModel$retryPending$1) create(coroutineScope, continuation)).invokeSuspend(Unit.INSTANCE);
    }

    /* JADX WARN: Removed duplicated region for block: B:18:0x0050 A[RETURN] */
    /* JADX WARN: Removed duplicated region for block: B:19:0x0051  */
    /* JADX WARN: Removed duplicated region for block: B:8:0x0055  */
    @Override // kotlin.coroutines.jvm.internal.BaseContinuationImpl
    /*
        Code decompiled incorrectly, please refer to instructions dump.
        To view partially-correct add '--show-bad-code' argument
    */
    public final java.lang.Object invokeSuspend(java.lang.Object r27) {
        /*
            r26 = this;
            r0 = r26
            java.lang.Object r1 = kotlin.coroutines.intrinsics.IntrinsicsKt.getCOROUTINE_SUSPENDED()
            int r2 = r0.label
            switch(r2) {
                case 0: goto L22;
                case 1: goto L1b;
                case 2: goto L13;
                default: goto Lb;
            }
        Lb:
            java.lang.IllegalStateException r1 = new java.lang.IllegalStateException
            java.lang.String r2 = "call to 'resume' before 'invoke' with coroutine"
            r1.<init>(r2)
            throw r1
        L13:
            r1 = r27
            int r2 = r0.I$0
            kotlin.ResultKt.throwOnFailure(r1)
            goto L53
        L1b:
            r2 = r27
            kotlin.ResultKt.throwOnFailure(r2)
            r3 = r2
            goto L3a
        L22:
            kotlin.ResultKt.throwOnFailure(r27)
            r2 = r27
            com.factory.wms.ui.viewmodel.MainViewModel r3 = r0.this$0
            com.factory.wms.data.repository.WmsRepository r3 = com.factory.wms.ui.viewmodel.MainViewModel.access$getWmsRepository$p(r3)
            r4 = r0
            kotlin.coroutines.Continuation r4 = (kotlin.coroutines.Continuation) r4
            r5 = 1
            r0.label = r5
            java.lang.Object r3 = r3.retryPending(r4)
            if (r3 != r1) goto L3a
            return r1
        L3a:
            java.lang.Number r3 = (java.lang.Number) r3
            int r3 = r3.intValue()
            com.factory.wms.ui.viewmodel.MainViewModel r4 = r0.this$0
            r5 = r0
            kotlin.coroutines.Continuation r5 = (kotlin.coroutines.Continuation) r5
            r0.I$0 = r3
            r6 = 2
            r0.label = r6
            java.lang.Object r4 = com.factory.wms.ui.viewmodel.MainViewModel.access$updatePendingCount(r4, r5)
            if (r4 != r1) goto L51
            return r1
        L51:
            r1 = r2
            r2 = r3
        L53:
            if (r2 <= 0) goto La6
            com.factory.wms.ui.viewmodel.MainViewModel r3 = r0.this$0
            kotlinx.coroutines.flow.MutableStateFlow r3 = com.factory.wms.ui.viewmodel.MainViewModel.access$get_uiState$p(r3)
            r4 = 0
        L5c:
            java.lang.Object r5 = r3.getValue()
            r24 = r5
            com.factory.wms.ui.viewmodel.MainUiState r24 = (com.factory.wms.ui.viewmodel.MainUiState) r24
            r6 = r24
            r25 = 0
            java.lang.StringBuilder r7 = new java.lang.StringBuilder
            r7.<init>()
            java.lang.String r8 = "已自动重传 "
            java.lang.StringBuilder r7 = r7.append(r8)
            java.lang.StringBuilder r7 = r7.append(r2)
            java.lang.String r8 = " 张离线单据"
            java.lang.StringBuilder r7 = r7.append(r8)
            java.lang.String r11 = r7.toString()
            r22 = 32751(0x7fef, float:4.5894E-41)
            r23 = 0
            r7 = 0
            r8 = 0
            r9 = 0
            r10 = 0
            r12 = 0
            r13 = 0
            r14 = 0
            r15 = 0
            r16 = 0
            r17 = 0
            r18 = 0
            r19 = 0
            r20 = 0
            r21 = 0
            com.factory.wms.ui.viewmodel.MainUiState r6 = com.factory.wms.ui.viewmodel.MainUiState.copy$default(r6, r7, r8, r9, r10, r11, r12, r13, r14, r15, r16, r17, r18, r19, r20, r21, r22, r23)
            boolean r7 = r3.compareAndSet(r5, r6)
            if (r7 == 0) goto L5c
        La6:
            kotlin.Unit r2 = kotlin.Unit.INSTANCE
            return r2
        */
        throw new UnsupportedOperationException("Method not decompiled: com.factory.wms.ui.viewmodel.MainViewModel$retryPending$1.invokeSuspend(java.lang.Object):java.lang.Object");
    }
}
