package com.factory.wms;

import android.app.Application;
import com.factory.wms.di.AppContainer;
import kotlin.Metadata;
import kotlin.jvm.internal.Intrinsics;

/* compiled from: WmsApplication.kt */
@Metadata(d1 = {"\u0000\u001a\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0018\u0002\n\u0002\b\u0004\n\u0002\u0010\u0002\n\u0000\b\u0007\u0018\u00002\u00020\u0001B\u0007¢\u0006\u0004\b\u0002\u0010\u0003J\b\u0010\t\u001a\u00020\nH\u0016R\u001e\u0010\u0006\u001a\u00020\u00052\u0006\u0010\u0004\u001a\u00020\u0005@BX\u0086.¢\u0006\b\n\u0000\u001a\u0004\b\u0007\u0010\b¨\u0006\u000b"}, d2 = {"Lcom/factory/wms/WmsApplication;", "Landroid/app/Application;", "<init>", "()V", "value", "Lcom/factory/wms/di/AppContainer;", "container", "getContainer", "()Lcom/factory/wms/di/AppContainer;", "onCreate", "", "app_debug"}, k = 1, mv = {2, 0, 0}, xi = 48)
/* loaded from: classes7.dex */
public final class WmsApplication extends Application {
    public static final int $stable = 8;
    private AppContainer container;

    public final AppContainer getContainer() {
        AppContainer appContainer = this.container;
        if (appContainer != null) {
            return appContainer;
        }
        Intrinsics.throwUninitializedPropertyAccessException("container");
        return null;
    }

    @Override // android.app.Application
    public void onCreate() {
        super.onCreate();
        this.container = new AppContainer(this);
    }
}
