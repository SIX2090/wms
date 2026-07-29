package com.factory.wms.di;

import android.content.Context;
import androidx.room.Room;
import com.factory.wms.data.api.AuthInterceptor;
import com.factory.wms.data.api.BaseUrlInterceptor;
import com.factory.wms.data.api.WmsApiService;
import com.factory.wms.data.local.WmsDatabase;
import com.factory.wms.data.repository.AuthRepository;
import com.factory.wms.data.repository.AuthStore;
import com.factory.wms.data.repository.WmsRepository;
import com.factory.wms.util.Constants;
import java.util.concurrent.TimeUnit;
import kotlin.Metadata;
import kotlin.jvm.internal.Intrinsics;
import okhttp3.OkHttpClient;
import okhttp3.logging.HttpLoggingInterceptor;
import retrofit2.Retrofit;
import retrofit2.converter.gson.GsonConverterFactory;

/* compiled from: AppContainer.kt */
@Metadata(d1 = {"\u0000L\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0006\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0018\u0002\n\u0002\b\u0003\b\u0007\u0018\u00002\u00020\u0001B\u000f\u0012\u0006\u0010\u0002\u001a\u00020\u0003¢\u0006\u0004\b\u0004\u0010\u0005R\u0018\u0010\u0006\u001a\n \u0007*\u0004\u0018\u00010\u00030\u0003X\u0082\u0004¢\u0006\u0004\n\u0002\u0010\bR\u0011\u0010\t\u001a\u00020\n¢\u0006\b\n\u0000\u001a\u0004\b\u000b\u0010\fR\u000e\u0010\r\u001a\u00020\u000eX\u0082\u0004¢\u0006\u0002\n\u0000R\u000e\u0010\u000f\u001a\u00020\u0010X\u0082\u0004¢\u0006\u0002\n\u0000R\u000e\u0010\u0011\u001a\u00020\u0012X\u0082\u0004¢\u0006\u0002\n\u0000R\u0018\u0010\u0013\u001a\n \u0007*\u0004\u0018\u00010\u00140\u0014X\u0082\u0004¢\u0006\u0004\n\u0002\u0010\u0015R\u0018\u0010\u0016\u001a\n \u0007*\u0004\u0018\u00010\u00170\u0017X\u0082\u0004¢\u0006\u0004\n\u0002\u0010\u0018R\u0011\u0010\u0019\u001a\u00020\u001a¢\u0006\b\n\u0000\u001a\u0004\b\u001b\u0010\u001cR\u0011\u0010\u001d\u001a\u00020\u001e¢\u0006\b\n\u0000\u001a\u0004\b\u001f\u0010 ¨\u0006!"}, d2 = {"Lcom/factory/wms/di/AppContainer;", "", "context", "Landroid/content/Context;", "<init>", "(Landroid/content/Context;)V", "appContext", "kotlin.jvm.PlatformType", "Landroid/content/Context;", "authStore", "Lcom/factory/wms/data/repository/AuthStore;", "getAuthStore", "()Lcom/factory/wms/data/repository/AuthStore;", "database", "Lcom/factory/wms/data/local/WmsDatabase;", "logging", "Lokhttp3/logging/HttpLoggingInterceptor;", "okHttpClient", "Lokhttp3/OkHttpClient;", "retrofit", "Lretrofit2/Retrofit;", "Lretrofit2/Retrofit;", "api", "Lcom/factory/wms/data/api/WmsApiService;", "Lcom/factory/wms/data/api/WmsApiService;", "authRepository", "Lcom/factory/wms/data/repository/AuthRepository;", "getAuthRepository", "()Lcom/factory/wms/data/repository/AuthRepository;", "wmsRepository", "Lcom/factory/wms/data/repository/WmsRepository;", "getWmsRepository", "()Lcom/factory/wms/data/repository/WmsRepository;", "app_debug"}, k = 1, mv = {2, 0, 0}, xi = 48)
/* loaded from: classes4.dex */
public final class AppContainer {
    public static final int $stable = 8;
    private final WmsApiService api;
    private final Context appContext;
    private final AuthRepository authRepository;
    private final AuthStore authStore;
    private final WmsDatabase database;
    private final HttpLoggingInterceptor logging;
    private final OkHttpClient okHttpClient;
    private final Retrofit retrofit;
    private final WmsRepository wmsRepository;

    /* JADX WARN: Multi-variable type inference failed */
    public AppContainer(Context context) {
        Intrinsics.checkNotNullParameter(context, "context");
        this.appContext = context.getApplicationContext();
        Context appContext = this.appContext;
        Intrinsics.checkNotNullExpressionValue(appContext, "appContext");
        this.authStore = new AuthStore(appContext);
        Context appContext2 = this.appContext;
        Intrinsics.checkNotNullExpressionValue(appContext2, "appContext");
        this.database = (WmsDatabase) Room.databaseBuilder(appContext2, WmsDatabase.class, "factory_wms.db").build();
        HttpLoggingInterceptor httpLoggingInterceptor = new HttpLoggingInterceptor(null, 1, 0 == true ? 1 : 0);
        httpLoggingInterceptor.level(HttpLoggingInterceptor.Level.BASIC);
        this.logging = httpLoggingInterceptor;
        this.okHttpClient = new OkHttpClient.Builder().addInterceptor(new BaseUrlInterceptor(this.authStore)).addInterceptor(new AuthInterceptor(this.authStore)).addInterceptor(this.logging).connectTimeout(15L, TimeUnit.SECONDS).readTimeout(30L, TimeUnit.SECONDS).writeTimeout(30L, TimeUnit.SECONDS).build();
        this.retrofit = new Retrofit.Builder().baseUrl(Constants.RETROFIT_BASE_URL).client(this.okHttpClient).addConverterFactory(GsonConverterFactory.create()).build();
        this.api = (WmsApiService) this.retrofit.create(WmsApiService.class);
        WmsApiService api = this.api;
        Intrinsics.checkNotNullExpressionValue(api, "api");
        this.authRepository = new AuthRepository(api, this.authStore);
        WmsApiService api2 = this.api;
        Intrinsics.checkNotNullExpressionValue(api2, "api");
        this.wmsRepository = new WmsRepository(api2, this.database.dao());
    }

    public final AuthStore getAuthStore() {
        return this.authStore;
    }

    public final AuthRepository getAuthRepository() {
        return this.authRepository;
    }

    public final WmsRepository getWmsRepository() {
        return this.wmsRepository;
    }
}
