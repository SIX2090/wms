package com.factory.wms.data.repository;

import androidx.autofill.HintConstants;
import com.factory.wms.data.api.WmsApiService;
import kotlin.Metadata;
import kotlin.jvm.internal.Intrinsics;

/* compiled from: AuthRepository.kt */
@Metadata(d1 = {"\u00000\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0018\u0002\n\u0002\u0010\u0002\n\u0000\n\u0002\u0010\u000e\n\u0002\b\u0005\n\u0002\u0010\u000b\n\u0000\b\u0007\u0018\u00002\u00020\u0001B\u0017\u0012\u0006\u0010\u0002\u001a\u00020\u0003\u0012\u0006\u0010\u0004\u001a\u00020\u0005¢\u0006\u0004\b\u0006\u0010\u0007J,\u0010\b\u001a\b\u0012\u0004\u0012\u00020\n0\t2\u0006\u0010\u000b\u001a\u00020\f2\u0006\u0010\r\u001a\u00020\f2\u0006\u0010\u000e\u001a\u00020\fH\u0086@¢\u0006\u0002\u0010\u000fJ\u0006\u0010\u0010\u001a\u00020\nJ\u0006\u0010\u0011\u001a\u00020\u0012J\u0006\u0010\u000b\u001a\u00020\fJ\u0006\u0010\u000e\u001a\u00020\fR\u000e\u0010\u0002\u001a\u00020\u0003X\u0082\u0004¢\u0006\u0002\n\u0000R\u000e\u0010\u0004\u001a\u00020\u0005X\u0082\u0004¢\u0006\u0002\n\u0000¨\u0006\u0013"}, d2 = {"Lcom/factory/wms/data/repository/AuthRepository;", "", "api", "Lcom/factory/wms/data/api/WmsApiService;", "authStore", "Lcom/factory/wms/data/repository/AuthStore;", "<init>", "(Lcom/factory/wms/data/api/WmsApiService;Lcom/factory/wms/data/repository/AuthStore;)V", "login", "Lcom/factory/wms/data/repository/NetworkResult;", "", "username", "", HintConstants.AUTOFILL_HINT_PASSWORD, "baseUrl", "(Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;Lkotlin/coroutines/Continuation;)Ljava/lang/Object;", "logout", "isLoggedIn", "", "app_debug"}, k = 1, mv = {2, 0, 0}, xi = 48)
/* loaded from: classes6.dex */
public final class AuthRepository {
    public static final int $stable = 8;
    private final WmsApiService api;
    private final AuthStore authStore;

    public AuthRepository(WmsApiService api, AuthStore authStore) {
        Intrinsics.checkNotNullParameter(api, "api");
        Intrinsics.checkNotNullParameter(authStore, "authStore");
        this.api = api;
        this.authStore = authStore;
    }

    /* JADX WARN: Removed duplicated region for block: B:12:0x002c  */
    /* JADX WARN: Removed duplicated region for block: B:17:0x0064 A[Catch: Exception -> 0x00a8, TryCatch #0 {Exception -> 0x00a8, blocks: (B:13:0x0034, B:15:0x0059, B:17:0x0064, B:20:0x006e, B:22:0x0074, B:24:0x007d, B:26:0x0087, B:27:0x008b, B:29:0x009c, B:33:0x003e), top: B:7:0x0021 }] */
    /* JADX WARN: Removed duplicated region for block: B:19:0x006c  */
    /* JADX WARN: Removed duplicated region for block: B:31:0x0069  */
    /* JADX WARN: Removed duplicated region for block: B:32:0x0039  */
    /* JADX WARN: Removed duplicated region for block: B:9:0x0024  */
    /*
        Code decompiled incorrectly, please refer to instructions dump.
        To view partially-correct add '--show-bad-code' argument
    */
    public final java.lang.Object login(java.lang.String r7, java.lang.String r8, java.lang.String r9, kotlin.coroutines.Continuation<? super com.factory.wms.data.repository.NetworkResult<kotlin.Unit>> r10) {
        /*
            r6 = this;
            boolean r0 = r10 instanceof com.factory.wms.data.repository.AuthRepository$login$1
            if (r0 == 0) goto L14
            r0 = r10
            com.factory.wms.data.repository.AuthRepository$login$1 r0 = (com.factory.wms.data.repository.AuthRepository$login$1) r0
            int r1 = r0.label
            r2 = -2147483648(0xffffffff80000000, float:-0.0)
            r1 = r1 & r2
            if (r1 == 0) goto L14
            int r1 = r0.label
            int r1 = r1 - r2
            r0.label = r1
            goto L19
        L14:
            com.factory.wms.data.repository.AuthRepository$login$1 r0 = new com.factory.wms.data.repository.AuthRepository$login$1
            r0.<init>(r6, r10)
        L19:
            java.lang.Object r1 = r0.result
            java.lang.Object r2 = kotlin.coroutines.intrinsics.IntrinsicsKt.getCOROUTINE_SUSPENDED()
            int r3 = r0.label
            switch(r3) {
                case 0: goto L39;
                case 1: goto L2c;
                default: goto L24;
            }
        L24:
            java.lang.IllegalStateException r7 = new java.lang.IllegalStateException
            java.lang.String r8 = "call to 'resume' before 'invoke' with coroutine"
            r7.<init>(r8)
            throw r7
        L2c:
            java.lang.Object r7 = r0.L$1
            java.lang.String r7 = (java.lang.String) r7
            java.lang.Object r8 = r0.L$0
            com.factory.wms.data.repository.AuthRepository r8 = (com.factory.wms.data.repository.AuthRepository) r8
            kotlin.ResultKt.throwOnFailure(r1)     // Catch: java.lang.Exception -> La8
            r9 = r1
            goto L59
        L39:
            kotlin.ResultKt.throwOnFailure(r1)
            r3 = r6
            com.factory.wms.data.repository.AuthStore r4 = r3.authStore     // Catch: java.lang.Exception -> La8
            r4.saveBaseUrl(r9)     // Catch: java.lang.Exception -> La8
            com.factory.wms.data.api.WmsApiService r9 = r3.api     // Catch: java.lang.Exception -> La8
            com.factory.wms.data.model.LoginRequest r4 = new com.factory.wms.data.model.LoginRequest     // Catch: java.lang.Exception -> La8
            r4.<init>(r7, r8)     // Catch: java.lang.Exception -> La8
            r0.L$0 = r3     // Catch: java.lang.Exception -> La8
            r0.L$1 = r7     // Catch: java.lang.Exception -> La8
            r5 = 1
            r0.label = r5     // Catch: java.lang.Exception -> La8
            java.lang.Object r9 = r9.login(r4, r0)     // Catch: java.lang.Exception -> La8
            if (r9 != r2) goto L58
            return r2
        L58:
            r8 = r3
        L59:
            com.factory.wms.data.model.ApiEnvelope r9 = (com.factory.wms.data.model.ApiEnvelope) r9     // Catch: java.lang.Exception -> La8
            java.lang.Object r2 = r9.getData()     // Catch: java.lang.Exception -> La8
            com.factory.wms.data.model.LoginData r2 = (com.factory.wms.data.model.LoginData) r2     // Catch: java.lang.Exception -> La8
            r3 = 0
            if (r2 == 0) goto L69
            java.lang.String r2 = r2.getToken()     // Catch: java.lang.Exception -> La8
            goto L6a
        L69:
            r2 = r3
        L6a:
            if (r2 != 0) goto L6e
            java.lang.String r2 = ""
        L6e:
            boolean r4 = r9.isOk()     // Catch: java.lang.Exception -> La8
            if (r4 == 0) goto L9c
            r4 = r2
            java.lang.CharSequence r4 = (java.lang.CharSequence) r4     // Catch: java.lang.Exception -> La8
            boolean r4 = kotlin.text.StringsKt.isBlank(r4)     // Catch: java.lang.Exception -> La8
            if (r4 != 0) goto L9c
            com.factory.wms.data.repository.AuthStore r4 = r8.authStore     // Catch: java.lang.Exception -> La8
            java.lang.Object r5 = r9.getData()     // Catch: java.lang.Exception -> La8
            com.factory.wms.data.model.LoginData r5 = (com.factory.wms.data.model.LoginData) r5     // Catch: java.lang.Exception -> La8
            if (r5 == 0) goto L8b
            com.factory.wms.data.model.UserProfile r3 = r5.getUser()     // Catch: java.lang.Exception -> La8
        L8b:
            r4.saveSession(r2, r3, r7)     // Catch: java.lang.Exception -> La8
            com.factory.wms.data.repository.NetworkResult$Success r7 = new com.factory.wms.data.repository.NetworkResult$Success     // Catch: java.lang.Exception -> La8
            kotlin.Unit r8 = kotlin.Unit.INSTANCE     // Catch: java.lang.Exception -> La8
            java.lang.String r2 = r9.getDisplayMessage()     // Catch: java.lang.Exception -> La8
            r7.<init>(r8, r2)     // Catch: java.lang.Exception -> La8
            com.factory.wms.data.repository.NetworkResult r7 = (com.factory.wms.data.repository.NetworkResult) r7     // Catch: java.lang.Exception -> La8
            goto La7
        L9c:
            com.factory.wms.data.repository.NetworkResult$Error r7 = new com.factory.wms.data.repository.NetworkResult$Error     // Catch: java.lang.Exception -> La8
            java.lang.String r8 = r9.getDisplayMessage()     // Catch: java.lang.Exception -> La8
            r7.<init>(r8)     // Catch: java.lang.Exception -> La8
            com.factory.wms.data.repository.NetworkResult r7 = (com.factory.wms.data.repository.NetworkResult) r7     // Catch: java.lang.Exception -> La8
        La7:
            goto Lb9
        La8:
            r7 = move-exception
            com.factory.wms.data.repository.NetworkResult$Error r8 = new com.factory.wms.data.repository.NetworkResult$Error
            java.lang.String r7 = r7.getMessage()
            if (r7 != 0) goto Lb3
            java.lang.String r7 = "登录失败，请检查网络"
        Lb3:
            r8.<init>(r7)
            r7 = r8
            com.factory.wms.data.repository.NetworkResult r7 = (com.factory.wms.data.repository.NetworkResult) r7
        Lb9:
            return r7
        */
        throw new UnsupportedOperationException("Method not decompiled: com.factory.wms.data.repository.AuthRepository.login(java.lang.String, java.lang.String, java.lang.String, kotlin.coroutines.Continuation):java.lang.Object");
    }

    public final void logout() {
        this.authStore.clear();
    }

    public final boolean isLoggedIn() {
        return this.authStore.isLoggedIn();
    }

    public final String username() {
        return this.authStore.getUsername();
    }

    public final String baseUrl() {
        return this.authStore.getBaseUrl();
    }
}
