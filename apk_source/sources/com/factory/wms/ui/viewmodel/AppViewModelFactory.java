package com.factory.wms.ui.viewmodel;

import androidx.lifecycle.ViewModel;
import androidx.lifecycle.ViewModelProvider;
import com.factory.wms.data.repository.AuthRepository;
import com.factory.wms.data.repository.WmsRepository;
import kotlin.Metadata;
import kotlin.jvm.internal.Intrinsics;

/* compiled from: AppViewModelFactory.kt */
@Metadata(d1 = {"\u0000&\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0004\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0002\b\u0007\u0018\u00002\u00020\u0001B\u0017\u0012\u0006\u0010\u0002\u001a\u00020\u0003\u0012\u0006\u0010\u0004\u001a\u00020\u0005¢\u0006\u0004\b\u0006\u0010\u0007J%\u0010\b\u001a\u0002H\t\"\b\b\u0000\u0010\t*\u00020\n2\f\u0010\u000b\u001a\b\u0012\u0004\u0012\u0002H\t0\fH\u0016¢\u0006\u0002\u0010\rR\u000e\u0010\u0002\u001a\u00020\u0003X\u0082\u0004¢\u0006\u0002\n\u0000R\u000e\u0010\u0004\u001a\u00020\u0005X\u0082\u0004¢\u0006\u0002\n\u0000¨\u0006\u000e"}, d2 = {"Lcom/factory/wms/ui/viewmodel/AppViewModelFactory;", "Landroidx/lifecycle/ViewModelProvider$Factory;", "authRepository", "Lcom/factory/wms/data/repository/AuthRepository;", "wmsRepository", "Lcom/factory/wms/data/repository/WmsRepository;", "<init>", "(Lcom/factory/wms/data/repository/AuthRepository;Lcom/factory/wms/data/repository/WmsRepository;)V", "create", "T", "Landroidx/lifecycle/ViewModel;", "modelClass", "Ljava/lang/Class;", "(Ljava/lang/Class;)Landroidx/lifecycle/ViewModel;", "app_debug"}, k = 1, mv = {2, 0, 0}, xi = 48)
/* loaded from: classes10.dex */
public final class AppViewModelFactory implements ViewModelProvider.Factory {
    public static final int $stable = 8;
    private final AuthRepository authRepository;
    private final WmsRepository wmsRepository;

    public AppViewModelFactory(AuthRepository authRepository, WmsRepository wmsRepository) {
        Intrinsics.checkNotNullParameter(authRepository, "authRepository");
        Intrinsics.checkNotNullParameter(wmsRepository, "wmsRepository");
        this.authRepository = authRepository;
        this.wmsRepository = wmsRepository;
    }

    @Override // androidx.lifecycle.ViewModelProvider.Factory
    public <T extends ViewModel> T create(Class<T> modelClass) {
        Intrinsics.checkNotNullParameter(modelClass, "modelClass");
        if (modelClass.isAssignableFrom(MainViewModel.class)) {
            return new MainViewModel(this.authRepository, this.wmsRepository);
        }
        throw new IllegalStateException(("Unknown ViewModel: " + modelClass.getName()).toString());
    }
}
