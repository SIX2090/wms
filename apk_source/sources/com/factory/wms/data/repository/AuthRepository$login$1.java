package com.factory.wms.data.repository;

import kotlin.Metadata;
import kotlin.coroutines.Continuation;
import kotlin.coroutines.jvm.internal.ContinuationImpl;
import kotlin.coroutines.jvm.internal.DebugMetadata;

/* compiled from: AuthRepository.kt */
@Metadata(k = 3, mv = {2, 0, 0}, xi = 48)
@DebugMetadata(c = "com.factory.wms.data.repository.AuthRepository", f = "AuthRepository.kt", i = {0, 0}, l = {13}, m = "login", n = {"this", "username"}, s = {"L$0", "L$1"})
/* loaded from: classes6.dex */
final class AuthRepository$login$1 extends ContinuationImpl {
    Object L$0;
    Object L$1;
    int label;
    /* synthetic */ Object result;
    final /* synthetic */ AuthRepository this$0;

    /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
    AuthRepository$login$1(AuthRepository authRepository, Continuation<? super AuthRepository$login$1> continuation) {
        super(continuation);
        this.this$0 = authRepository;
    }

    @Override // kotlin.coroutines.jvm.internal.BaseContinuationImpl
    public final Object invokeSuspend(Object obj) {
        this.result = obj;
        this.label |= Integer.MIN_VALUE;
        return this.this$0.login(null, null, null, this);
    }
}
