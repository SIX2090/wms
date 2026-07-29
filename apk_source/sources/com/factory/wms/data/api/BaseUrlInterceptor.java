package com.factory.wms.data.api;

import com.factory.wms.data.repository.AuthStore;
import kotlin.Metadata;
import kotlin.jvm.internal.Intrinsics;
import okhttp3.HttpUrl;
import okhttp3.Interceptor;
import okhttp3.Request;
import okhttp3.Response;

/* compiled from: BaseUrlInterceptor.kt */
@Metadata(d1 = {"\u0000\u001e\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\b\u0007\u0018\u00002\u00020\u0001B\u000f\u0012\u0006\u0010\u0002\u001a\u00020\u0003¢\u0006\u0004\b\u0004\u0010\u0005J\u0010\u0010\u0006\u001a\u00020\u00072\u0006\u0010\b\u001a\u00020\tH\u0016R\u000e\u0010\u0002\u001a\u00020\u0003X\u0082\u0004¢\u0006\u0002\n\u0000¨\u0006\n"}, d2 = {"Lcom/factory/wms/data/api/BaseUrlInterceptor;", "Lokhttp3/Interceptor;", "authStore", "Lcom/factory/wms/data/repository/AuthStore;", "<init>", "(Lcom/factory/wms/data/repository/AuthStore;)V", "intercept", "Lokhttp3/Response;", "chain", "Lokhttp3/Interceptor$Chain;", "app_debug"}, k = 1, mv = {2, 0, 0}, xi = 48)
/* loaded from: classes9.dex */
public final class BaseUrlInterceptor implements Interceptor {
    public static final int $stable = 8;
    private final AuthStore authStore;

    public BaseUrlInterceptor(AuthStore authStore) {
        Intrinsics.checkNotNullParameter(authStore, "authStore");
        this.authStore = authStore;
    }

    @Override // okhttp3.Interceptor
    public Response intercept(Interceptor.Chain chain) {
        Intrinsics.checkNotNullParameter(chain, "chain");
        HttpUrl baseUrl = HttpUrl.INSTANCE.parse(this.authStore.getBaseUrl());
        if (baseUrl == null) {
            return chain.proceed(chain.request());
        }
        Request original = chain.request();
        HttpUrl newUrl = original.url().newBuilder().scheme(baseUrl.scheme()).host(baseUrl.host()).port(baseUrl.port()).build();
        return chain.proceed(original.newBuilder().url(newUrl).build());
    }
}
