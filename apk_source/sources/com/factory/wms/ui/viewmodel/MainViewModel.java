package com.factory.wms.ui.viewmodel;

import androidx.autofill.HintConstants;
import androidx.lifecycle.ViewModel;
import androidx.lifecycle.ViewModelKt;
import com.factory.wms.data.model.MaterialDto;
import com.factory.wms.data.repository.AuthRepository;
import com.factory.wms.data.repository.WmsRepository;
import java.util.ArrayList;
import java.util.Collection;
import java.util.List;
import kotlin.Metadata;
import kotlin.NoWhenBranchMatchedException;
import kotlin.collections.CollectionsKt;
import kotlin.jvm.functions.Function1;
import kotlin.jvm.internal.Intrinsics;
import kotlin.ranges.RangesKt;
import kotlinx.coroutines.BuildersKt__Builders_commonKt;
import kotlinx.coroutines.flow.MutableStateFlow;
import kotlinx.coroutines.flow.StateFlow;
import kotlinx.coroutines.flow.StateFlowKt;

/* compiled from: MainViewModel.kt */
@Metadata(d1 = {"\u0000^\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0010\u0002\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0010\u000e\n\u0002\b\f\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0010\u0006\n\u0002\b\u001a\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\b\u0003\b\u0007\u0018\u00002\u00020\u0001B\u0017\u0012\u0006\u0010\u0002\u001a\u00020\u0003\u0012\u0006\u0010\u0004\u001a\u00020\u0005¢\u0006\u0004\b\u0006\u0010\u0007J\u0006\u0010\u000f\u001a\u00020\u0010J\u000e\u0010\u0011\u001a\u00020\u00102\u0006\u0010\u0012\u001a\u00020\u0013J\u001e\u0010\u0014\u001a\u00020\u00102\u0006\u0010\u0015\u001a\u00020\u00162\u0006\u0010\u0017\u001a\u00020\u00162\u0006\u0010\u0018\u001a\u00020\u0016J\u0006\u0010\u0019\u001a\u00020\u0010J\u000e\u0010\u001a\u001a\u00020\u00102\u0006\u0010\u001b\u001a\u00020\u0016J\u000e\u0010\u001c\u001a\u00020\u00102\u0006\u0010\u001d\u001a\u00020\u0016J\u000e\u0010\u001e\u001a\u00020\u00102\u0006\u0010\u001d\u001a\u00020\u0016J\u000e\u0010\u001f\u001a\u00020\u00102\u0006\u0010\u001d\u001a\u00020\u0016J\u000e\u0010 \u001a\u00020\u00102\u0006\u0010\u001d\u001a\u00020\u0016J\u000e\u0010!\u001a\u00020\u00102\u0006\u0010\"\u001a\u00020#J\u0016\u0010$\u001a\u00020\u00102\u0006\u0010\u001d\u001a\u00020\u00162\u0006\u0010%\u001a\u00020&J\u0016\u0010'\u001a\u00020\u00102\u0006\u0010\u001d\u001a\u00020\u00162\u0006\u0010(\u001a\u00020\u0016J\u0016\u0010)\u001a\u00020\u00102\u0006\u0010\u001d\u001a\u00020\u00162\u0006\u0010%\u001a\u00020&J\u0016\u0010*\u001a\u00020\u00102\u0006\u0010\u001d\u001a\u00020\u00162\u0006\u0010+\u001a\u00020\u0016J\u0016\u0010,\u001a\u00020\u00102\u0006\u0010\u001d\u001a\u00020\u00162\u0006\u0010-\u001a\u00020\u0016J\u0016\u0010.\u001a\u00020\u00102\u0006\u0010\u001d\u001a\u00020\u00162\u0006\u0010/\u001a\u00020&J\u000e\u00100\u001a\u00020\u00102\u0006\u00101\u001a\u00020\u0016J\u000e\u00102\u001a\u00020\u00102\u0006\u00103\u001a\u00020\u0016J\u0006\u00104\u001a\u00020\u0010J\u0016\u00105\u001a\u00020\u00102\u0006\u0010\u0012\u001a\u00020\u00132\u0006\u0010\u001d\u001a\u00020\u0016J\u000e\u00106\u001a\u00020\u00102\u0006\u0010\u0012\u001a\u00020\u0013J\u0006\u00107\u001a\u00020\u0010J\u0006\u00108\u001a\u00020\u0010J\u0006\u00109\u001a\u00020\u0010J\u0006\u0010:\u001a\u00020\u0010J\b\u0010;\u001a\u00020\u0010H\u0002J\u0018\u0010<\u001a\u00020\u00102\u0006\u0010\u0012\u001a\u00020\u00132\u0006\u0010\u001d\u001a\u00020\u0016H\u0002J\u0010\u0010=\u001a\u00020\u00102\u0006\u0010\u001d\u001a\u00020\u0016H\u0002J\u0018\u0010>\u001a\u00020\u00102\u0006\u0010\u0012\u001a\u00020\u00132\u0006\u0010\"\u001a\u00020#H\u0002J,\u0010?\u001a\u00020\u00102\u0006\u0010\u0012\u001a\u00020\u00132\u0006\u0010\u001d\u001a\u00020\u00162\u0012\u0010@\u001a\u000e\u0012\u0004\u0012\u00020B\u0012\u0004\u0012\u00020B0AH\u0002J\u000e\u0010C\u001a\u00020\u0010H\u0082@¢\u0006\u0002\u0010DR\u000e\u0010\u0002\u001a\u00020\u0003X\u0082\u0004¢\u0006\u0002\n\u0000R\u000e\u0010\u0004\u001a\u00020\u0005X\u0082\u0004¢\u0006\u0002\n\u0000R\u0014\u0010\b\u001a\b\u0012\u0004\u0012\u00020\n0\tX\u0082\u0004¢\u0006\u0002\n\u0000R\u0017\u0010\u000b\u001a\b\u0012\u0004\u0012\u00020\n0\f¢\u0006\b\n\u0000\u001a\u0004\b\r\u0010\u000e¨\u0006E"}, d2 = {"Lcom/factory/wms/ui/viewmodel/MainViewModel;", "Landroidx/lifecycle/ViewModel;", "authRepository", "Lcom/factory/wms/data/repository/AuthRepository;", "wmsRepository", "Lcom/factory/wms/data/repository/WmsRepository;", "<init>", "(Lcom/factory/wms/data/repository/AuthRepository;Lcom/factory/wms/data/repository/WmsRepository;)V", "_uiState", "Lkotlinx/coroutines/flow/MutableStateFlow;", "Lcom/factory/wms/ui/viewmodel/MainUiState;", "uiState", "Lkotlinx/coroutines/flow/StateFlow;", "getUiState", "()Lkotlinx/coroutines/flow/StateFlow;", "clearMessage", "", "selectTab", "tab", "Lcom/factory/wms/ui/viewmodel/MainTab;", "login", "username", "", HintConstants.AUTOFILL_HINT_PASSWORD, "baseUrl", "logout", "searchMaterial", "keyword", "scanInbound", "code", "scanOutbound", "scanQuery", "scanStocktake", "addMaterialToCurrent", "material", "Lcom/factory/wms/data/model/MaterialDto;", "updateInboundQuantity", "quantity", "", "updateInboundBatch", "batchNo", "updateOutboundQuantity", "updateOutboundReceiver", "receiver", "updateOutboundDepartment", "department", "updateActualStock", "actualStock", "setStocktakeMode", "mode", "setStocktakeWarehouse", "warehouse", "clearQueryMaterial", "deleteLine", "clearLines", "submitInbound", "submitOutbound", "submitStocktake", "retryPending", "refreshMaterials", "addScannedLine", "queryMaterial", "appendLine", "updateLine", "transform", "Lkotlin/Function1;", "Lcom/factory/wms/ui/viewmodel/ScanLine;", "updatePendingCount", "(Lkotlin/coroutines/Continuation;)Ljava/lang/Object;", "app_debug"}, k = 1, mv = {2, 0, 0}, xi = 48)
/* loaded from: classes10.dex */
public final class MainViewModel extends ViewModel {
    public static final int $stable = 8;
    private final MutableStateFlow<MainUiState> _uiState;
    private final AuthRepository authRepository;
    private final StateFlow<MainUiState> uiState;
    private final WmsRepository wmsRepository;

    /* compiled from: MainViewModel.kt */
    @Metadata(k = 3, mv = {2, 0, 0}, xi = 48)
    public /* synthetic */ class WhenMappings {
        public static final /* synthetic */ int[] $EnumSwitchMapping$0;

        static {
            int[] iArr = new int[MainTab.values().length];
            try {
                iArr[MainTab.Inbound.ordinal()] = 1;
            } catch (NoSuchFieldError e) {
            }
            try {
                iArr[MainTab.Outbound.ordinal()] = 2;
            } catch (NoSuchFieldError e2) {
            }
            try {
                iArr[MainTab.Query.ordinal()] = 3;
            } catch (NoSuchFieldError e3) {
            }
            try {
                iArr[MainTab.Stocktake.ordinal()] = 4;
            } catch (NoSuchFieldError e4) {
            }
            try {
                iArr[MainTab.Mine.ordinal()] = 5;
            } catch (NoSuchFieldError e5) {
            }
            $EnumSwitchMapping$0 = iArr;
        }
    }

    public MainViewModel(AuthRepository authRepository, WmsRepository wmsRepository) {
        Intrinsics.checkNotNullParameter(authRepository, "authRepository");
        Intrinsics.checkNotNullParameter(wmsRepository, "wmsRepository");
        this.authRepository = authRepository;
        this.wmsRepository = wmsRepository;
        this._uiState = StateFlowKt.MutableStateFlow(new MainUiState(this.authRepository.isLoggedIn(), this.authRepository.username(), null, false, null, null, null, null, null, null, null, null, null, 0, this.authRepository.baseUrl(), 16380, null));
        this.uiState = this._uiState;
        if (!this.authRepository.isLoggedIn()) {
            return;
        }
        refreshMaterials();
        retryPending();
    }

    public final StateFlow<MainUiState> getUiState() {
        return this.uiState;
    }

    public final void clearMessage() {
        MainUiState value;
        MainUiState copy;
        MutableStateFlow $this$update$iv = this._uiState;
        do {
            value = $this$update$iv.getValue();
            MainUiState it = value;
            copy = it.copy((r32 & 1) != 0 ? it.isLoggedIn : false, (r32 & 2) != 0 ? it.username : null, (r32 & 4) != 0 ? it.selectedTab : null, (r32 & 8) != 0 ? it.loading : false, (r32 & 16) != 0 ? it.message : null, (r32 & 32) != 0 ? it.error : null, (r32 & 64) != 0 ? it.inboundLines : null, (r32 & 128) != 0 ? it.outboundLines : null, (r32 & 256) != 0 ? it.queryMaterial : null, (r32 & 512) != 0 ? it.stocktakeLines : null, (r32 & 1024) != 0 ? it.stocktakeMode : null, (r32 & 2048) != 0 ? it.stocktakeWarehouse : null, (r32 & 4096) != 0 ? it.searchResults : null, (r32 & 8192) != 0 ? it.pendingCount : 0, (r32 & 16384) != 0 ? it.baseUrl : null);
        } while (!$this$update$iv.compareAndSet(value, copy));
    }

    public final void selectTab(MainTab tab) {
        Object obj;
        MainUiState copy;
        Object tab2 = tab;
        Intrinsics.checkNotNullParameter(tab2, "tab");
        MutableStateFlow $this$update$iv = this._uiState;
        while (true) {
            MainUiState value = $this$update$iv.getValue();
            MainUiState it = value;
            MutableStateFlow $this$update$iv2 = $this$update$iv;
            obj = tab2;
            copy = it.copy((r32 & 1) != 0 ? it.isLoggedIn : false, (r32 & 2) != 0 ? it.username : null, (r32 & 4) != 0 ? it.selectedTab : tab, (r32 & 8) != 0 ? it.loading : false, (r32 & 16) != 0 ? it.message : null, (r32 & 32) != 0 ? it.error : null, (r32 & 64) != 0 ? it.inboundLines : null, (r32 & 128) != 0 ? it.outboundLines : null, (r32 & 256) != 0 ? it.queryMaterial : null, (r32 & 512) != 0 ? it.stocktakeLines : null, (r32 & 1024) != 0 ? it.stocktakeMode : null, (r32 & 2048) != 0 ? it.stocktakeWarehouse : null, (r32 & 4096) != 0 ? it.searchResults : null, (r32 & 8192) != 0 ? it.pendingCount : 0, (r32 & 16384) != 0 ? it.baseUrl : null);
            if ($this$update$iv2.compareAndSet(value, copy)) {
                break;
            }
            tab2 = tab;
            $this$update$iv = $this$update$iv2;
        }
        Object nextValue$iv = MainTab.Stocktake;
        if (obj == nextValue$iv && this._uiState.getValue().getStocktakeLines().isEmpty()) {
            refreshMaterials();
        }
    }

    public final void login(String username, String password, String baseUrl) {
        Intrinsics.checkNotNullParameter(username, "username");
        Intrinsics.checkNotNullParameter(password, "password");
        Intrinsics.checkNotNullParameter(baseUrl, "baseUrl");
        BuildersKt__Builders_commonKt.launch$default(ViewModelKt.getViewModelScope(this), null, null, new MainViewModel$login$1(this, username, password, baseUrl, null), 3, null);
    }

    public final void logout() {
        this.authRepository.logout();
        this._uiState.setValue(new MainUiState(false, null, null, false, null, null, null, null, null, null, null, null, null, 0, this.authRepository.baseUrl(), 16383, null));
    }

    public final void searchMaterial(String keyword) {
        Intrinsics.checkNotNullParameter(keyword, "keyword");
        BuildersKt__Builders_commonKt.launch$default(ViewModelKt.getViewModelScope(this), null, null, new MainViewModel$searchMaterial$1(this, keyword, null), 3, null);
    }

    public final void scanInbound(String code) {
        Intrinsics.checkNotNullParameter(code, "code");
        addScannedLine(MainTab.Inbound, code);
    }

    public final void scanOutbound(String code) {
        Intrinsics.checkNotNullParameter(code, "code");
        addScannedLine(MainTab.Outbound, code);
    }

    public final void scanQuery(String code) {
        Intrinsics.checkNotNullParameter(code, "code");
        queryMaterial(code);
    }

    public final void scanStocktake(String code) {
        Intrinsics.checkNotNullParameter(code, "code");
        addScannedLine(MainTab.Stocktake, code);
    }

    public final void addMaterialToCurrent(MaterialDto material) {
        Intrinsics.checkNotNullParameter(material, "material");
        MainTab tab = this._uiState.getValue().getSelectedTab();
        appendLine(tab, material);
    }

    public final void updateInboundQuantity(String code, final double quantity) {
        Intrinsics.checkNotNullParameter(code, "code");
        updateLine(MainTab.Inbound, code, new Function1() { // from class: com.factory.wms.ui.viewmodel.MainViewModel$$ExternalSyntheticLambda2
            @Override // kotlin.jvm.functions.Function1
            public final Object invoke(Object obj) {
                ScanLine updateInboundQuantity$lambda$2;
                updateInboundQuantity$lambda$2 = MainViewModel.updateInboundQuantity$lambda$2(quantity, (ScanLine) obj);
                return updateInboundQuantity$lambda$2;
            }
        });
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final ScanLine updateInboundQuantity$lambda$2(double $quantity, ScanLine it) {
        ScanLine copy;
        Intrinsics.checkNotNullParameter(it, "it");
        copy = it.copy((r20 & 1) != 0 ? it.material : null, (r20 & 2) != 0 ? it.quantity : RangesKt.coerceAtLeast($quantity, 0.0d), (r20 & 4) != 0 ? it.batchNo : null, (r20 & 8) != 0 ? it.receiver : null, (r20 & 16) != 0 ? it.department : null, (r20 & 32) != 0 ? it.actualStock : 0.0d, (r20 & 64) != 0 ? it.scannedTimes : 0);
        return copy;
    }

    public final void updateInboundBatch(String code, final String batchNo) {
        Intrinsics.checkNotNullParameter(code, "code");
        Intrinsics.checkNotNullParameter(batchNo, "batchNo");
        updateLine(MainTab.Inbound, code, new Function1() { // from class: com.factory.wms.ui.viewmodel.MainViewModel$$ExternalSyntheticLambda4
            @Override // kotlin.jvm.functions.Function1
            public final Object invoke(Object obj) {
                ScanLine updateInboundBatch$lambda$3;
                updateInboundBatch$lambda$3 = MainViewModel.updateInboundBatch$lambda$3(batchNo, (ScanLine) obj);
                return updateInboundBatch$lambda$3;
            }
        });
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final ScanLine updateInboundBatch$lambda$3(String $batchNo, ScanLine it) {
        ScanLine copy;
        Intrinsics.checkNotNullParameter(it, "it");
        copy = it.copy((r20 & 1) != 0 ? it.material : null, (r20 & 2) != 0 ? it.quantity : 0.0d, (r20 & 4) != 0 ? it.batchNo : $batchNo, (r20 & 8) != 0 ? it.receiver : null, (r20 & 16) != 0 ? it.department : null, (r20 & 32) != 0 ? it.actualStock : 0.0d, (r20 & 64) != 0 ? it.scannedTimes : 0);
        return copy;
    }

    public final void updateOutboundQuantity(String code, final double quantity) {
        Intrinsics.checkNotNullParameter(code, "code");
        updateLine(MainTab.Outbound, code, new Function1() { // from class: com.factory.wms.ui.viewmodel.MainViewModel$$ExternalSyntheticLambda1
            @Override // kotlin.jvm.functions.Function1
            public final Object invoke(Object obj) {
                ScanLine updateOutboundQuantity$lambda$4;
                updateOutboundQuantity$lambda$4 = MainViewModel.updateOutboundQuantity$lambda$4(quantity, (ScanLine) obj);
                return updateOutboundQuantity$lambda$4;
            }
        });
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final ScanLine updateOutboundQuantity$lambda$4(double $quantity, ScanLine it) {
        ScanLine copy;
        Intrinsics.checkNotNullParameter(it, "it");
        copy = it.copy((r20 & 1) != 0 ? it.material : null, (r20 & 2) != 0 ? it.quantity : RangesKt.coerceAtLeast($quantity, 0.0d), (r20 & 4) != 0 ? it.batchNo : null, (r20 & 8) != 0 ? it.receiver : null, (r20 & 16) != 0 ? it.department : null, (r20 & 32) != 0 ? it.actualStock : 0.0d, (r20 & 64) != 0 ? it.scannedTimes : 0);
        return copy;
    }

    public final void updateOutboundReceiver(String code, final String receiver) {
        Intrinsics.checkNotNullParameter(code, "code");
        Intrinsics.checkNotNullParameter(receiver, "receiver");
        updateLine(MainTab.Outbound, code, new Function1() { // from class: com.factory.wms.ui.viewmodel.MainViewModel$$ExternalSyntheticLambda0
            @Override // kotlin.jvm.functions.Function1
            public final Object invoke(Object obj) {
                ScanLine updateOutboundReceiver$lambda$5;
                updateOutboundReceiver$lambda$5 = MainViewModel.updateOutboundReceiver$lambda$5(receiver, (ScanLine) obj);
                return updateOutboundReceiver$lambda$5;
            }
        });
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final ScanLine updateOutboundReceiver$lambda$5(String $receiver, ScanLine it) {
        ScanLine copy;
        Intrinsics.checkNotNullParameter(it, "it");
        copy = it.copy((r20 & 1) != 0 ? it.material : null, (r20 & 2) != 0 ? it.quantity : 0.0d, (r20 & 4) != 0 ? it.batchNo : null, (r20 & 8) != 0 ? it.receiver : $receiver, (r20 & 16) != 0 ? it.department : null, (r20 & 32) != 0 ? it.actualStock : 0.0d, (r20 & 64) != 0 ? it.scannedTimes : 0);
        return copy;
    }

    public final void updateOutboundDepartment(String code, final String department) {
        Intrinsics.checkNotNullParameter(code, "code");
        Intrinsics.checkNotNullParameter(department, "department");
        updateLine(MainTab.Outbound, code, new Function1() { // from class: com.factory.wms.ui.viewmodel.MainViewModel$$ExternalSyntheticLambda3
            @Override // kotlin.jvm.functions.Function1
            public final Object invoke(Object obj) {
                ScanLine updateOutboundDepartment$lambda$6;
                updateOutboundDepartment$lambda$6 = MainViewModel.updateOutboundDepartment$lambda$6(department, (ScanLine) obj);
                return updateOutboundDepartment$lambda$6;
            }
        });
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final ScanLine updateOutboundDepartment$lambda$6(String $department, ScanLine it) {
        ScanLine copy;
        Intrinsics.checkNotNullParameter(it, "it");
        copy = it.copy((r20 & 1) != 0 ? it.material : null, (r20 & 2) != 0 ? it.quantity : 0.0d, (r20 & 4) != 0 ? it.batchNo : null, (r20 & 8) != 0 ? it.receiver : null, (r20 & 16) != 0 ? it.department : $department, (r20 & 32) != 0 ? it.actualStock : 0.0d, (r20 & 64) != 0 ? it.scannedTimes : 0);
        return copy;
    }

    public final void updateActualStock(String code, final double actualStock) {
        Intrinsics.checkNotNullParameter(code, "code");
        updateLine(MainTab.Stocktake, code, new Function1() { // from class: com.factory.wms.ui.viewmodel.MainViewModel$$ExternalSyntheticLambda5
            @Override // kotlin.jvm.functions.Function1
            public final Object invoke(Object obj) {
                ScanLine updateActualStock$lambda$7;
                updateActualStock$lambda$7 = MainViewModel.updateActualStock$lambda$7(actualStock, (ScanLine) obj);
                return updateActualStock$lambda$7;
            }
        });
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final ScanLine updateActualStock$lambda$7(double $actualStock, ScanLine it) {
        ScanLine copy;
        Intrinsics.checkNotNullParameter(it, "it");
        copy = it.copy((r20 & 1) != 0 ? it.material : null, (r20 & 2) != 0 ? it.quantity : 0.0d, (r20 & 4) != 0 ? it.batchNo : null, (r20 & 8) != 0 ? it.receiver : null, (r20 & 16) != 0 ? it.department : null, (r20 & 32) != 0 ? it.actualStock : RangesKt.coerceAtLeast($actualStock, 0.0d), (r20 & 64) != 0 ? it.scannedTimes : 0);
        return copy;
    }

    public final void setStocktakeMode(String mode) {
        MainUiState copy;
        Intrinsics.checkNotNullParameter(mode, "mode");
        MutableStateFlow $this$update$iv = this._uiState;
        while (true) {
            MainUiState value = $this$update$iv.getValue();
            MainUiState it = value;
            MutableStateFlow $this$update$iv2 = $this$update$iv;
            copy = it.copy((r32 & 1) != 0 ? it.isLoggedIn : false, (r32 & 2) != 0 ? it.username : null, (r32 & 4) != 0 ? it.selectedTab : null, (r32 & 8) != 0 ? it.loading : false, (r32 & 16) != 0 ? it.message : null, (r32 & 32) != 0 ? it.error : null, (r32 & 64) != 0 ? it.inboundLines : null, (r32 & 128) != 0 ? it.outboundLines : null, (r32 & 256) != 0 ? it.queryMaterial : null, (r32 & 512) != 0 ? it.stocktakeLines : null, (r32 & 1024) != 0 ? it.stocktakeMode : mode, (r32 & 2048) != 0 ? it.stocktakeWarehouse : null, (r32 & 4096) != 0 ? it.searchResults : null, (r32 & 8192) != 0 ? it.pendingCount : 0, (r32 & 16384) != 0 ? it.baseUrl : null);
            if ($this$update$iv2.compareAndSet(value, copy)) {
                return;
            } else {
                $this$update$iv = $this$update$iv2;
            }
        }
    }

    public final void setStocktakeWarehouse(String warehouse) {
        MainUiState copy;
        Intrinsics.checkNotNullParameter(warehouse, "warehouse");
        MutableStateFlow $this$update$iv = this._uiState;
        while (true) {
            MainUiState value = $this$update$iv.getValue();
            MainUiState it = value;
            MutableStateFlow $this$update$iv2 = $this$update$iv;
            copy = it.copy((r32 & 1) != 0 ? it.isLoggedIn : false, (r32 & 2) != 0 ? it.username : null, (r32 & 4) != 0 ? it.selectedTab : null, (r32 & 8) != 0 ? it.loading : false, (r32 & 16) != 0 ? it.message : null, (r32 & 32) != 0 ? it.error : null, (r32 & 64) != 0 ? it.inboundLines : null, (r32 & 128) != 0 ? it.outboundLines : null, (r32 & 256) != 0 ? it.queryMaterial : null, (r32 & 512) != 0 ? it.stocktakeLines : null, (r32 & 1024) != 0 ? it.stocktakeMode : null, (r32 & 2048) != 0 ? it.stocktakeWarehouse : warehouse, (r32 & 4096) != 0 ? it.searchResults : null, (r32 & 8192) != 0 ? it.pendingCount : 0, (r32 & 16384) != 0 ? it.baseUrl : null);
            if ($this$update$iv2.compareAndSet(value, copy)) {
                return;
            } else {
                $this$update$iv = $this$update$iv2;
            }
        }
    }

    public final void clearQueryMaterial() {
        MainUiState value;
        MainUiState copy;
        MutableStateFlow $this$update$iv = this._uiState;
        do {
            value = $this$update$iv.getValue();
            MainUiState it = value;
            copy = it.copy((r32 & 1) != 0 ? it.isLoggedIn : false, (r32 & 2) != 0 ? it.username : null, (r32 & 4) != 0 ? it.selectedTab : null, (r32 & 8) != 0 ? it.loading : false, (r32 & 16) != 0 ? it.message : null, (r32 & 32) != 0 ? it.error : null, (r32 & 64) != 0 ? it.inboundLines : null, (r32 & 128) != 0 ? it.outboundLines : null, (r32 & 256) != 0 ? it.queryMaterial : null, (r32 & 512) != 0 ? it.stocktakeLines : null, (r32 & 1024) != 0 ? it.stocktakeMode : null, (r32 & 2048) != 0 ? it.stocktakeWarehouse : null, (r32 & 4096) != 0 ? it.searchResults : null, (r32 & 8192) != 0 ? it.pendingCount : 0, (r32 & 16384) != 0 ? it.baseUrl : null);
        } while (!$this$update$iv.compareAndSet(value, copy));
    }

    public final void deleteLine(MainTab tab, String code) {
        MainUiState value;
        MainUiState copy;
        Intrinsics.checkNotNullParameter(tab, "tab");
        Intrinsics.checkNotNullParameter(code, "code");
        MutableStateFlow $this$update$iv = this._uiState;
        do {
            value = $this$update$iv.getValue();
            MainUiState it = value;
            switch (WhenMappings.$EnumSwitchMapping$0[tab.ordinal()]) {
                case 1:
                    Iterable $this$filterNot$iv = it.getInboundLines();
                    Collection destination$iv$iv = new ArrayList();
                    for (Object element$iv$iv : $this$filterNot$iv) {
                        ScanLine line = (ScanLine) element$iv$iv;
                        if (!Intrinsics.areEqual(line.getMaterial().getCode(), code)) {
                            destination$iv$iv.add(element$iv$iv);
                        }
                    }
                    copy = it.copy((r32 & 1) != 0 ? it.isLoggedIn : false, (r32 & 2) != 0 ? it.username : null, (r32 & 4) != 0 ? it.selectedTab : null, (r32 & 8) != 0 ? it.loading : false, (r32 & 16) != 0 ? it.message : null, (r32 & 32) != 0 ? it.error : null, (r32 & 64) != 0 ? it.inboundLines : (List) destination$iv$iv, (r32 & 128) != 0 ? it.outboundLines : null, (r32 & 256) != 0 ? it.queryMaterial : null, (r32 & 512) != 0 ? it.stocktakeLines : null, (r32 & 1024) != 0 ? it.stocktakeMode : null, (r32 & 2048) != 0 ? it.stocktakeWarehouse : null, (r32 & 4096) != 0 ? it.searchResults : null, (r32 & 8192) != 0 ? it.pendingCount : 0, (r32 & 16384) != 0 ? it.baseUrl : null);
                    break;
                case 2:
                    Iterable $this$filterNot$iv2 = it.getOutboundLines();
                    Collection destination$iv$iv2 = new ArrayList();
                    for (Object element$iv$iv2 : $this$filterNot$iv2) {
                        ScanLine line2 = (ScanLine) element$iv$iv2;
                        if (!Intrinsics.areEqual(line2.getMaterial().getCode(), code)) {
                            destination$iv$iv2.add(element$iv$iv2);
                        }
                    }
                    copy = it.copy((r32 & 1) != 0 ? it.isLoggedIn : false, (r32 & 2) != 0 ? it.username : null, (r32 & 4) != 0 ? it.selectedTab : null, (r32 & 8) != 0 ? it.loading : false, (r32 & 16) != 0 ? it.message : null, (r32 & 32) != 0 ? it.error : null, (r32 & 64) != 0 ? it.inboundLines : null, (r32 & 128) != 0 ? it.outboundLines : (List) destination$iv$iv2, (r32 & 256) != 0 ? it.queryMaterial : null, (r32 & 512) != 0 ? it.stocktakeLines : null, (r32 & 1024) != 0 ? it.stocktakeMode : null, (r32 & 2048) != 0 ? it.stocktakeWarehouse : null, (r32 & 4096) != 0 ? it.searchResults : null, (r32 & 8192) != 0 ? it.pendingCount : 0, (r32 & 16384) != 0 ? it.baseUrl : null);
                    break;
                case 3:
                    copy = it.copy((r32 & 1) != 0 ? it.isLoggedIn : false, (r32 & 2) != 0 ? it.username : null, (r32 & 4) != 0 ? it.selectedTab : null, (r32 & 8) != 0 ? it.loading : false, (r32 & 16) != 0 ? it.message : null, (r32 & 32) != 0 ? it.error : null, (r32 & 64) != 0 ? it.inboundLines : null, (r32 & 128) != 0 ? it.outboundLines : null, (r32 & 256) != 0 ? it.queryMaterial : null, (r32 & 512) != 0 ? it.stocktakeLines : null, (r32 & 1024) != 0 ? it.stocktakeMode : null, (r32 & 2048) != 0 ? it.stocktakeWarehouse : null, (r32 & 4096) != 0 ? it.searchResults : null, (r32 & 8192) != 0 ? it.pendingCount : 0, (r32 & 16384) != 0 ? it.baseUrl : null);
                    break;
                case 4:
                    Iterable $this$filterNot$iv3 = it.getStocktakeLines();
                    Collection destination$iv$iv3 = new ArrayList();
                    for (Object element$iv$iv3 : $this$filterNot$iv3) {
                        ScanLine line3 = (ScanLine) element$iv$iv3;
                        if (!Intrinsics.areEqual(line3.getMaterial().getCode(), code)) {
                            destination$iv$iv3.add(element$iv$iv3);
                        }
                    }
                    copy = it.copy((r32 & 1) != 0 ? it.isLoggedIn : false, (r32 & 2) != 0 ? it.username : null, (r32 & 4) != 0 ? it.selectedTab : null, (r32 & 8) != 0 ? it.loading : false, (r32 & 16) != 0 ? it.message : null, (r32 & 32) != 0 ? it.error : null, (r32 & 64) != 0 ? it.inboundLines : null, (r32 & 128) != 0 ? it.outboundLines : null, (r32 & 256) != 0 ? it.queryMaterial : null, (r32 & 512) != 0 ? it.stocktakeLines : (List) destination$iv$iv3, (r32 & 1024) != 0 ? it.stocktakeMode : null, (r32 & 2048) != 0 ? it.stocktakeWarehouse : null, (r32 & 4096) != 0 ? it.searchResults : null, (r32 & 8192) != 0 ? it.pendingCount : 0, (r32 & 16384) != 0 ? it.baseUrl : null);
                    break;
                case 5:
                    copy = it;
                    break;
                default:
                    throw new NoWhenBranchMatchedException();
            }
        } while (!$this$update$iv.compareAndSet(value, copy));
    }

    public final void clearLines(MainTab tab) {
        MainUiState value;
        MainUiState copy;
        Intrinsics.checkNotNullParameter(tab, "tab");
        MutableStateFlow $this$update$iv = this._uiState;
        do {
            value = $this$update$iv.getValue();
            MainUiState it = value;
            switch (WhenMappings.$EnumSwitchMapping$0[tab.ordinal()]) {
                case 1:
                    copy = it.copy((r32 & 1) != 0 ? it.isLoggedIn : false, (r32 & 2) != 0 ? it.username : null, (r32 & 4) != 0 ? it.selectedTab : null, (r32 & 8) != 0 ? it.loading : false, (r32 & 16) != 0 ? it.message : null, (r32 & 32) != 0 ? it.error : null, (r32 & 64) != 0 ? it.inboundLines : CollectionsKt.emptyList(), (r32 & 128) != 0 ? it.outboundLines : null, (r32 & 256) != 0 ? it.queryMaterial : null, (r32 & 512) != 0 ? it.stocktakeLines : null, (r32 & 1024) != 0 ? it.stocktakeMode : null, (r32 & 2048) != 0 ? it.stocktakeWarehouse : null, (r32 & 4096) != 0 ? it.searchResults : null, (r32 & 8192) != 0 ? it.pendingCount : 0, (r32 & 16384) != 0 ? it.baseUrl : null);
                    break;
                case 2:
                    copy = it.copy((r32 & 1) != 0 ? it.isLoggedIn : false, (r32 & 2) != 0 ? it.username : null, (r32 & 4) != 0 ? it.selectedTab : null, (r32 & 8) != 0 ? it.loading : false, (r32 & 16) != 0 ? it.message : null, (r32 & 32) != 0 ? it.error : null, (r32 & 64) != 0 ? it.inboundLines : null, (r32 & 128) != 0 ? it.outboundLines : CollectionsKt.emptyList(), (r32 & 256) != 0 ? it.queryMaterial : null, (r32 & 512) != 0 ? it.stocktakeLines : null, (r32 & 1024) != 0 ? it.stocktakeMode : null, (r32 & 2048) != 0 ? it.stocktakeWarehouse : null, (r32 & 4096) != 0 ? it.searchResults : null, (r32 & 8192) != 0 ? it.pendingCount : 0, (r32 & 16384) != 0 ? it.baseUrl : null);
                    break;
                case 3:
                    copy = it.copy((r32 & 1) != 0 ? it.isLoggedIn : false, (r32 & 2) != 0 ? it.username : null, (r32 & 4) != 0 ? it.selectedTab : null, (r32 & 8) != 0 ? it.loading : false, (r32 & 16) != 0 ? it.message : null, (r32 & 32) != 0 ? it.error : null, (r32 & 64) != 0 ? it.inboundLines : null, (r32 & 128) != 0 ? it.outboundLines : null, (r32 & 256) != 0 ? it.queryMaterial : null, (r32 & 512) != 0 ? it.stocktakeLines : null, (r32 & 1024) != 0 ? it.stocktakeMode : null, (r32 & 2048) != 0 ? it.stocktakeWarehouse : null, (r32 & 4096) != 0 ? it.searchResults : null, (r32 & 8192) != 0 ? it.pendingCount : 0, (r32 & 16384) != 0 ? it.baseUrl : null);
                    break;
                case 4:
                    copy = it.copy((r32 & 1) != 0 ? it.isLoggedIn : false, (r32 & 2) != 0 ? it.username : null, (r32 & 4) != 0 ? it.selectedTab : null, (r32 & 8) != 0 ? it.loading : false, (r32 & 16) != 0 ? it.message : null, (r32 & 32) != 0 ? it.error : null, (r32 & 64) != 0 ? it.inboundLines : null, (r32 & 128) != 0 ? it.outboundLines : null, (r32 & 256) != 0 ? it.queryMaterial : null, (r32 & 512) != 0 ? it.stocktakeLines : CollectionsKt.emptyList(), (r32 & 1024) != 0 ? it.stocktakeMode : null, (r32 & 2048) != 0 ? it.stocktakeWarehouse : null, (r32 & 4096) != 0 ? it.searchResults : null, (r32 & 8192) != 0 ? it.pendingCount : 0, (r32 & 16384) != 0 ? it.baseUrl : null);
                    break;
                case 5:
                    copy = it;
                    break;
                default:
                    throw new NoWhenBranchMatchedException();
            }
        } while (!$this$update$iv.compareAndSet(value, copy));
    }

    public final void submitInbound() {
        BuildersKt__Builders_commonKt.launch$default(ViewModelKt.getViewModelScope(this), null, null, new MainViewModel$submitInbound$1(this, null), 3, null);
    }

    public final void submitOutbound() {
        BuildersKt__Builders_commonKt.launch$default(ViewModelKt.getViewModelScope(this), null, null, new MainViewModel$submitOutbound$1(this, null), 3, null);
    }

    public final void submitStocktake() {
        BuildersKt__Builders_commonKt.launch$default(ViewModelKt.getViewModelScope(this), null, null, new MainViewModel$submitStocktake$1(this, null), 3, null);
    }

    public final void retryPending() {
        BuildersKt__Builders_commonKt.launch$default(ViewModelKt.getViewModelScope(this), null, null, new MainViewModel$retryPending$1(this, null), 3, null);
    }

    /* JADX INFO: Access modifiers changed from: private */
    public final void refreshMaterials() {
        BuildersKt__Builders_commonKt.launch$default(ViewModelKt.getViewModelScope(this), null, null, new MainViewModel$refreshMaterials$1(this, null), 3, null);
    }

    private final void addScannedLine(MainTab tab, String code) {
        BuildersKt__Builders_commonKt.launch$default(ViewModelKt.getViewModelScope(this), null, null, new MainViewModel$addScannedLine$1(this, code, tab, null), 3, null);
    }

    private final void queryMaterial(String code) {
        BuildersKt__Builders_commonKt.launch$default(ViewModelKt.getViewModelScope(this), null, null, new MainViewModel$queryMaterial$1(this, code, null), 3, null);
    }

    /* JADX INFO: Access modifiers changed from: private */
    public final void appendLine(MainTab tab, MaterialDto material) {
        MaterialDto materialDto;
        MainUiState mainUiState;
        MutableStateFlow $this$update$iv;
        List bumpOrAdd;
        MainUiState copy;
        List bumpOrAdd2;
        MainUiState copy2;
        List bumpOrAddActual;
        MainUiState copy3;
        MaterialDto materialDto2 = material;
        MutableStateFlow $this$update$iv2 = this._uiState;
        while (true) {
            MainUiState value = $this$update$iv2.getValue();
            MainUiState state = value;
            switch (WhenMappings.$EnumSwitchMapping$0[tab.ordinal()]) {
                case 1:
                    materialDto = materialDto2;
                    mainUiState = value;
                    $this$update$iv = $this$update$iv2;
                    bumpOrAdd = MainViewModelKt.bumpOrAdd(state.getInboundLines(), materialDto);
                    copy = state.copy((r32 & 1) != 0 ? state.isLoggedIn : false, (r32 & 2) != 0 ? state.username : null, (r32 & 4) != 0 ? state.selectedTab : null, (r32 & 8) != 0 ? state.loading : false, (r32 & 16) != 0 ? state.message : null, (r32 & 32) != 0 ? state.error : null, (r32 & 64) != 0 ? state.inboundLines : bumpOrAdd, (r32 & 128) != 0 ? state.outboundLines : null, (r32 & 256) != 0 ? state.queryMaterial : null, (r32 & 512) != 0 ? state.stocktakeLines : null, (r32 & 1024) != 0 ? state.stocktakeMode : null, (r32 & 2048) != 0 ? state.stocktakeWarehouse : null, (r32 & 4096) != 0 ? state.searchResults : null, (r32 & 8192) != 0 ? state.pendingCount : 0, (r32 & 16384) != 0 ? state.baseUrl : null);
                    break;
                case 2:
                    mainUiState = value;
                    $this$update$iv = $this$update$iv2;
                    materialDto = material;
                    bumpOrAdd2 = MainViewModelKt.bumpOrAdd(state.getOutboundLines(), materialDto);
                    copy = state.copy((r32 & 1) != 0 ? state.isLoggedIn : false, (r32 & 2) != 0 ? state.username : null, (r32 & 4) != 0 ? state.selectedTab : null, (r32 & 8) != 0 ? state.loading : false, (r32 & 16) != 0 ? state.message : null, (r32 & 32) != 0 ? state.error : null, (r32 & 64) != 0 ? state.inboundLines : null, (r32 & 128) != 0 ? state.outboundLines : bumpOrAdd2, (r32 & 256) != 0 ? state.queryMaterial : null, (r32 & 512) != 0 ? state.stocktakeLines : null, (r32 & 1024) != 0 ? state.stocktakeMode : null, (r32 & 2048) != 0 ? state.stocktakeWarehouse : null, (r32 & 4096) != 0 ? state.searchResults : null, (r32 & 8192) != 0 ? state.pendingCount : 0, (r32 & 16384) != 0 ? state.baseUrl : null);
                    break;
                case 3:
                    mainUiState = value;
                    $this$update$iv = $this$update$iv2;
                    copy2 = state.copy((r32 & 1) != 0 ? state.isLoggedIn : false, (r32 & 2) != 0 ? state.username : null, (r32 & 4) != 0 ? state.selectedTab : null, (r32 & 8) != 0 ? state.loading : false, (r32 & 16) != 0 ? state.message : null, (r32 & 32) != 0 ? state.error : null, (r32 & 64) != 0 ? state.inboundLines : null, (r32 & 128) != 0 ? state.outboundLines : null, (r32 & 256) != 0 ? state.queryMaterial : material, (r32 & 512) != 0 ? state.stocktakeLines : null, (r32 & 1024) != 0 ? state.stocktakeMode : null, (r32 & 2048) != 0 ? state.stocktakeWarehouse : null, (r32 & 4096) != 0 ? state.searchResults : null, (r32 & 8192) != 0 ? state.pendingCount : 0, (r32 & 16384) != 0 ? state.baseUrl : null);
                    copy = copy2;
                    materialDto = material;
                    break;
                case 4:
                    bumpOrAddActual = MainViewModelKt.bumpOrAddActual(state.getStocktakeLines(), materialDto2);
                    copy3 = state.copy((r32 & 1) != 0 ? state.isLoggedIn : false, (r32 & 2) != 0 ? state.username : null, (r32 & 4) != 0 ? state.selectedTab : null, (r32 & 8) != 0 ? state.loading : false, (r32 & 16) != 0 ? state.message : null, (r32 & 32) != 0 ? state.error : null, (r32 & 64) != 0 ? state.inboundLines : null, (r32 & 128) != 0 ? state.outboundLines : null, (r32 & 256) != 0 ? state.queryMaterial : null, (r32 & 512) != 0 ? state.stocktakeLines : bumpOrAddActual, (r32 & 1024) != 0 ? state.stocktakeMode : null, (r32 & 2048) != 0 ? state.stocktakeWarehouse : null, (r32 & 4096) != 0 ? state.searchResults : null, (r32 & 8192) != 0 ? state.pendingCount : 0, (r32 & 16384) != 0 ? state.baseUrl : null);
                    copy = copy3;
                    materialDto = materialDto2;
                    mainUiState = value;
                    $this$update$iv = $this$update$iv2;
                    break;
                case 5:
                    materialDto = materialDto2;
                    mainUiState = value;
                    $this$update$iv = $this$update$iv2;
                    copy = state;
                    break;
                default:
                    throw new NoWhenBranchMatchedException();
            }
            MutableStateFlow $this$update$iv3 = $this$update$iv;
            if ($this$update$iv3.compareAndSet(mainUiState, copy)) {
                return;
            }
            materialDto2 = materialDto;
            $this$update$iv2 = $this$update$iv3;
        }
    }

    private final void updateLine(MainTab tab, String code, Function1<? super ScanLine, ScanLine> transform) {
        MainUiState value;
        MainUiState mainUiState;
        MutableStateFlow $this$update$iv = this._uiState;
        do {
            value = $this$update$iv.getValue();
            MainUiState state = value;
            switch (WhenMappings.$EnumSwitchMapping$0[tab.ordinal()]) {
                case 1:
                    Iterable $this$map$iv = state.getInboundLines();
                    Collection destination$iv$iv = new ArrayList(CollectionsKt.collectionSizeOrDefault($this$map$iv, 10));
                    for (Object item$iv$iv : $this$map$iv) {
                        ScanLine it = (ScanLine) item$iv$iv;
                        if (Intrinsics.areEqual(it.getMaterial().getCode(), code)) {
                            it = transform.invoke(it);
                        }
                        destination$iv$iv.add(it);
                    }
                    mainUiState = state.copy((r32 & 1) != 0 ? state.isLoggedIn : false, (r32 & 2) != 0 ? state.username : null, (r32 & 4) != 0 ? state.selectedTab : null, (r32 & 8) != 0 ? state.loading : false, (r32 & 16) != 0 ? state.message : null, (r32 & 32) != 0 ? state.error : null, (r32 & 64) != 0 ? state.inboundLines : (List) destination$iv$iv, (r32 & 128) != 0 ? state.outboundLines : null, (r32 & 256) != 0 ? state.queryMaterial : null, (r32 & 512) != 0 ? state.stocktakeLines : null, (r32 & 1024) != 0 ? state.stocktakeMode : null, (r32 & 2048) != 0 ? state.stocktakeWarehouse : null, (r32 & 4096) != 0 ? state.searchResults : null, (r32 & 8192) != 0 ? state.pendingCount : 0, (r32 & 16384) != 0 ? state.baseUrl : null);
                    break;
                case 2:
                    Iterable $this$map$iv2 = state.getOutboundLines();
                    Collection destination$iv$iv2 = new ArrayList(CollectionsKt.collectionSizeOrDefault($this$map$iv2, 10));
                    for (Object item$iv$iv2 : $this$map$iv2) {
                        ScanLine it2 = (ScanLine) item$iv$iv2;
                        if (Intrinsics.areEqual(it2.getMaterial().getCode(), code)) {
                            it2 = transform.invoke(it2);
                        }
                        destination$iv$iv2.add(it2);
                    }
                    mainUiState = state.copy((r32 & 1) != 0 ? state.isLoggedIn : false, (r32 & 2) != 0 ? state.username : null, (r32 & 4) != 0 ? state.selectedTab : null, (r32 & 8) != 0 ? state.loading : false, (r32 & 16) != 0 ? state.message : null, (r32 & 32) != 0 ? state.error : null, (r32 & 64) != 0 ? state.inboundLines : null, (r32 & 128) != 0 ? state.outboundLines : (List) destination$iv$iv2, (r32 & 256) != 0 ? state.queryMaterial : null, (r32 & 512) != 0 ? state.stocktakeLines : null, (r32 & 1024) != 0 ? state.stocktakeMode : null, (r32 & 2048) != 0 ? state.stocktakeWarehouse : null, (r32 & 4096) != 0 ? state.searchResults : null, (r32 & 8192) != 0 ? state.pendingCount : 0, (r32 & 16384) != 0 ? state.baseUrl : null);
                    break;
                case 3:
                case 5:
                    mainUiState = state;
                    break;
                case 4:
                    Iterable $this$map$iv3 = state.getStocktakeLines();
                    Collection destination$iv$iv3 = new ArrayList(CollectionsKt.collectionSizeOrDefault($this$map$iv3, 10));
                    for (Object item$iv$iv3 : $this$map$iv3) {
                        ScanLine it3 = (ScanLine) item$iv$iv3;
                        if (Intrinsics.areEqual(it3.getMaterial().getCode(), code)) {
                            it3 = transform.invoke(it3);
                        }
                        destination$iv$iv3.add(it3);
                    }
                    mainUiState = state.copy((r32 & 1) != 0 ? state.isLoggedIn : false, (r32 & 2) != 0 ? state.username : null, (r32 & 4) != 0 ? state.selectedTab : null, (r32 & 8) != 0 ? state.loading : false, (r32 & 16) != 0 ? state.message : null, (r32 & 32) != 0 ? state.error : null, (r32 & 64) != 0 ? state.inboundLines : null, (r32 & 128) != 0 ? state.outboundLines : null, (r32 & 256) != 0 ? state.queryMaterial : null, (r32 & 512) != 0 ? state.stocktakeLines : (List) destination$iv$iv3, (r32 & 1024) != 0 ? state.stocktakeMode : null, (r32 & 2048) != 0 ? state.stocktakeWarehouse : null, (r32 & 4096) != 0 ? state.searchResults : null, (r32 & 8192) != 0 ? state.pendingCount : 0, (r32 & 16384) != 0 ? state.baseUrl : null);
                    break;
                default:
                    throw new NoWhenBranchMatchedException();
            }
        } while (!$this$update$iv.compareAndSet(value, mainUiState));
    }

    /* JADX INFO: Access modifiers changed from: private */
    /* JADX WARN: Removed duplicated region for block: B:11:0x0032  */
    /* JADX WARN: Removed duplicated region for block: B:19:0x003b  */
    /* JADX WARN: Removed duplicated region for block: B:8:0x002a  */
    /*
        Code decompiled incorrectly, please refer to instructions dump.
        To view partially-correct add '--show-bad-code' argument
    */
    public final java.lang.Object updatePendingCount(kotlin.coroutines.Continuation<? super kotlin.Unit> r29) {
        /*
            r28 = this;
            r0 = r29
            boolean r1 = r0 instanceof com.factory.wms.ui.viewmodel.MainViewModel$updatePendingCount$1
            if (r1 == 0) goto L18
            r1 = r0
            com.factory.wms.ui.viewmodel.MainViewModel$updatePendingCount$1 r1 = (com.factory.wms.ui.viewmodel.MainViewModel$updatePendingCount$1) r1
            int r2 = r1.label
            r3 = -2147483648(0xffffffff80000000, float:-0.0)
            r2 = r2 & r3
            if (r2 == 0) goto L18
            int r2 = r1.label
            int r2 = r2 - r3
            r1.label = r2
            r2 = r28
            goto L1f
        L18:
            com.factory.wms.ui.viewmodel.MainViewModel$updatePendingCount$1 r1 = new com.factory.wms.ui.viewmodel.MainViewModel$updatePendingCount$1
            r2 = r28
            r1.<init>(r2, r0)
        L1f:
            java.lang.Object r3 = r1.result
            java.lang.Object r4 = kotlin.coroutines.intrinsics.IntrinsicsKt.getCOROUTINE_SUSPENDED()
            int r5 = r1.label
            switch(r5) {
                case 0: goto L3b;
                case 1: goto L32;
                default: goto L2a;
            }
        L2a:
            java.lang.IllegalStateException r1 = new java.lang.IllegalStateException
            java.lang.String r3 = "call to 'resume' before 'invoke' with coroutine"
            r1.<init>(r3)
            throw r1
        L32:
            java.lang.Object r4 = r1.L$0
            com.factory.wms.ui.viewmodel.MainViewModel r4 = (com.factory.wms.ui.viewmodel.MainViewModel) r4
            kotlin.ResultKt.throwOnFailure(r3)
            r6 = r3
            goto L4f
        L3b:
            kotlin.ResultKt.throwOnFailure(r3)
            r5 = r28
            com.factory.wms.data.repository.WmsRepository r6 = r5.wmsRepository
            r1.L$0 = r5
            r7 = 1
            r1.label = r7
            java.lang.Object r6 = r6.pendingCount(r1)
            if (r6 != r4) goto L4e
            return r4
        L4e:
            r4 = r5
        L4f:
            java.lang.Number r6 = (java.lang.Number) r6
            int r5 = r6.intValue()
            kotlinx.coroutines.flow.MutableStateFlow<com.factory.wms.ui.viewmodel.MainUiState> r4 = r4._uiState
            r6 = 0
        L58:
            java.lang.Object r15 = r4.getValue()
            r25 = r15
            com.factory.wms.ui.viewmodel.MainUiState r25 = (com.factory.wms.ui.viewmodel.MainUiState) r25
            r7 = r25
            r26 = 0
            r23 = 24575(0x5fff, float:3.4437E-41)
            r24 = 0
            r8 = 0
            r9 = 0
            r10 = 0
            r11 = 0
            r12 = 0
            r13 = 0
            r14 = 0
            r16 = 0
            r27 = r15
            r15 = r16
            r17 = 0
            r18 = 0
            r19 = 0
            r20 = 0
            r22 = 0
            r21 = r5
            com.factory.wms.ui.viewmodel.MainUiState r7 = com.factory.wms.ui.viewmodel.MainUiState.copy$default(r7, r8, r9, r10, r11, r12, r13, r14, r15, r16, r17, r18, r19, r20, r21, r22, r23, r24)
            r8 = r27
            boolean r9 = r4.compareAndSet(r8, r7)
            if (r9 == 0) goto L58
        L90:
            kotlin.Unit r4 = kotlin.Unit.INSTANCE
            return r4
        */
        throw new UnsupportedOperationException("Method not decompiled: com.factory.wms.ui.viewmodel.MainViewModel.updatePendingCount(kotlin.coroutines.Continuation):java.lang.Object");
    }
}
