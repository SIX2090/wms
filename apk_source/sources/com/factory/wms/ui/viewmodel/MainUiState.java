package com.factory.wms.ui.viewmodel;

import androidx.compose.ui.layout.LayoutKt;
import com.factory.wms.data.model.MaterialDto;
import java.util.List;
import kotlin.Metadata;
import kotlin.collections.CollectionsKt;
import kotlin.jvm.internal.DefaultConstructorMarker;
import kotlin.jvm.internal.Intrinsics;

/* compiled from: MainViewModel.kt */
@Metadata(d1 = {"\u0000:\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0000\n\u0002\u0010\u000b\n\u0000\n\u0002\u0010\u000e\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0004\n\u0002\u0010 \n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\b\u0005\n\u0002\u0010\b\n\u0002\b,\b\u0087\b\u0018\u00002\u00020\u0001B»\u0001\u0012\b\b\u0002\u0010\u0002\u001a\u00020\u0003\u0012\b\b\u0002\u0010\u0004\u001a\u00020\u0005\u0012\b\b\u0002\u0010\u0006\u001a\u00020\u0007\u0012\b\b\u0002\u0010\b\u001a\u00020\u0003\u0012\n\b\u0002\u0010\t\u001a\u0004\u0018\u00010\u0005\u0012\n\b\u0002\u0010\n\u001a\u0004\u0018\u00010\u0005\u0012\u000e\b\u0002\u0010\u000b\u001a\b\u0012\u0004\u0012\u00020\r0\f\u0012\u000e\b\u0002\u0010\u000e\u001a\b\u0012\u0004\u0012\u00020\r0\f\u0012\n\b\u0002\u0010\u000f\u001a\u0004\u0018\u00010\u0010\u0012\u000e\b\u0002\u0010\u0011\u001a\b\u0012\u0004\u0012\u00020\r0\f\u0012\b\b\u0002\u0010\u0012\u001a\u00020\u0005\u0012\b\b\u0002\u0010\u0013\u001a\u00020\u0005\u0012\u000e\b\u0002\u0010\u0014\u001a\b\u0012\u0004\u0012\u00020\u00100\f\u0012\b\b\u0002\u0010\u0015\u001a\u00020\u0016\u0012\b\b\u0002\u0010\u0017\u001a\u00020\u0005¢\u0006\u0004\b\u0018\u0010\u0019J\t\u0010.\u001a\u00020\u0003HÆ\u0003J\t\u0010/\u001a\u00020\u0005HÆ\u0003J\t\u00100\u001a\u00020\u0007HÆ\u0003J\t\u00101\u001a\u00020\u0003HÆ\u0003J\u000b\u00102\u001a\u0004\u0018\u00010\u0005HÆ\u0003J\u000b\u00103\u001a\u0004\u0018\u00010\u0005HÆ\u0003J\u000f\u00104\u001a\b\u0012\u0004\u0012\u00020\r0\fHÆ\u0003J\u000f\u00105\u001a\b\u0012\u0004\u0012\u00020\r0\fHÆ\u0003J\u000b\u00106\u001a\u0004\u0018\u00010\u0010HÆ\u0003J\u000f\u00107\u001a\b\u0012\u0004\u0012\u00020\r0\fHÆ\u0003J\t\u00108\u001a\u00020\u0005HÆ\u0003J\t\u00109\u001a\u00020\u0005HÆ\u0003J\u000f\u0010:\u001a\b\u0012\u0004\u0012\u00020\u00100\fHÆ\u0003J\t\u0010;\u001a\u00020\u0016HÆ\u0003J\t\u0010<\u001a\u00020\u0005HÆ\u0003J½\u0001\u0010=\u001a\u00020\u00002\b\b\u0002\u0010\u0002\u001a\u00020\u00032\b\b\u0002\u0010\u0004\u001a\u00020\u00052\b\b\u0002\u0010\u0006\u001a\u00020\u00072\b\b\u0002\u0010\b\u001a\u00020\u00032\n\b\u0002\u0010\t\u001a\u0004\u0018\u00010\u00052\n\b\u0002\u0010\n\u001a\u0004\u0018\u00010\u00052\u000e\b\u0002\u0010\u000b\u001a\b\u0012\u0004\u0012\u00020\r0\f2\u000e\b\u0002\u0010\u000e\u001a\b\u0012\u0004\u0012\u00020\r0\f2\n\b\u0002\u0010\u000f\u001a\u0004\u0018\u00010\u00102\u000e\b\u0002\u0010\u0011\u001a\b\u0012\u0004\u0012\u00020\r0\f2\b\b\u0002\u0010\u0012\u001a\u00020\u00052\b\b\u0002\u0010\u0013\u001a\u00020\u00052\u000e\b\u0002\u0010\u0014\u001a\b\u0012\u0004\u0012\u00020\u00100\f2\b\b\u0002\u0010\u0015\u001a\u00020\u00162\b\b\u0002\u0010\u0017\u001a\u00020\u0005HÆ\u0001J\u0013\u0010>\u001a\u00020\u00032\b\u0010?\u001a\u0004\u0018\u00010\u0001HÖ\u0003J\t\u0010@\u001a\u00020\u0016HÖ\u0001J\t\u0010A\u001a\u00020\u0005HÖ\u0001R\u0011\u0010\u0002\u001a\u00020\u0003¢\u0006\b\n\u0000\u001a\u0004\b\u0002\u0010\u001aR\u0011\u0010\u0004\u001a\u00020\u0005¢\u0006\b\n\u0000\u001a\u0004\b\u001b\u0010\u001cR\u0011\u0010\u0006\u001a\u00020\u0007¢\u0006\b\n\u0000\u001a\u0004\b\u001d\u0010\u001eR\u0011\u0010\b\u001a\u00020\u0003¢\u0006\b\n\u0000\u001a\u0004\b\u001f\u0010\u001aR\u0013\u0010\t\u001a\u0004\u0018\u00010\u0005¢\u0006\b\n\u0000\u001a\u0004\b \u0010\u001cR\u0013\u0010\n\u001a\u0004\u0018\u00010\u0005¢\u0006\b\n\u0000\u001a\u0004\b!\u0010\u001cR\u0017\u0010\u000b\u001a\b\u0012\u0004\u0012\u00020\r0\f¢\u0006\b\n\u0000\u001a\u0004\b\"\u0010#R\u0017\u0010\u000e\u001a\b\u0012\u0004\u0012\u00020\r0\f¢\u0006\b\n\u0000\u001a\u0004\b$\u0010#R\u0013\u0010\u000f\u001a\u0004\u0018\u00010\u0010¢\u0006\b\n\u0000\u001a\u0004\b%\u0010&R\u0017\u0010\u0011\u001a\b\u0012\u0004\u0012\u00020\r0\f¢\u0006\b\n\u0000\u001a\u0004\b'\u0010#R\u0011\u0010\u0012\u001a\u00020\u0005¢\u0006\b\n\u0000\u001a\u0004\b(\u0010\u001cR\u0011\u0010\u0013\u001a\u00020\u0005¢\u0006\b\n\u0000\u001a\u0004\b)\u0010\u001cR\u0017\u0010\u0014\u001a\b\u0012\u0004\u0012\u00020\u00100\f¢\u0006\b\n\u0000\u001a\u0004\b*\u0010#R\u0011\u0010\u0015\u001a\u00020\u0016¢\u0006\b\n\u0000\u001a\u0004\b+\u0010,R\u0011\u0010\u0017\u001a\u00020\u0005¢\u0006\b\n\u0000\u001a\u0004\b-\u0010\u001c¨\u0006B"}, d2 = {"Lcom/factory/wms/ui/viewmodel/MainUiState;", "", "isLoggedIn", "", "username", "", "selectedTab", "Lcom/factory/wms/ui/viewmodel/MainTab;", "loading", "message", "error", "inboundLines", "", "Lcom/factory/wms/ui/viewmodel/ScanLine;", "outboundLines", "queryMaterial", "Lcom/factory/wms/data/model/MaterialDto;", "stocktakeLines", "stocktakeMode", "stocktakeWarehouse", "searchResults", "pendingCount", "", "baseUrl", "<init>", "(ZLjava/lang/String;Lcom/factory/wms/ui/viewmodel/MainTab;ZLjava/lang/String;Ljava/lang/String;Ljava/util/List;Ljava/util/List;Lcom/factory/wms/data/model/MaterialDto;Ljava/util/List;Ljava/lang/String;Ljava/lang/String;Ljava/util/List;ILjava/lang/String;)V", "()Z", "getUsername", "()Ljava/lang/String;", "getSelectedTab", "()Lcom/factory/wms/ui/viewmodel/MainTab;", "getLoading", "getMessage", "getError", "getInboundLines", "()Ljava/util/List;", "getOutboundLines", "getQueryMaterial", "()Lcom/factory/wms/data/model/MaterialDto;", "getStocktakeLines", "getStocktakeMode", "getStocktakeWarehouse", "getSearchResults", "getPendingCount", "()I", "getBaseUrl", "component1", "component2", "component3", "component4", "component5", "component6", "component7", "component8", "component9", "component10", "component11", "component12", "component13", "component14", "component15", "copy", "equals", "other", "hashCode", "toString", "app_debug"}, k = 1, mv = {2, 0, 0}, xi = 48)
/* loaded from: classes10.dex */
public final /* data */ class MainUiState {
    public static final int $stable = 8;
    private final String baseUrl;
    private final String error;
    private final List<ScanLine> inboundLines;
    private final boolean isLoggedIn;
    private final boolean loading;
    private final String message;
    private final List<ScanLine> outboundLines;
    private final int pendingCount;
    private final MaterialDto queryMaterial;
    private final List<MaterialDto> searchResults;
    private final MainTab selectedTab;
    private final List<ScanLine> stocktakeLines;
    private final String stocktakeMode;
    private final String stocktakeWarehouse;
    private final String username;

    public MainUiState() {
        this(false, null, null, false, null, null, null, null, null, null, null, null, null, 0, null, LayoutKt.LargeDimension, null);
    }

    /* renamed from: component1, reason: from getter */
    public final boolean getIsLoggedIn() {
        return this.isLoggedIn;
    }

    public final List<ScanLine> component10() {
        return this.stocktakeLines;
    }

    /* renamed from: component11, reason: from getter */
    public final String getStocktakeMode() {
        return this.stocktakeMode;
    }

    /* renamed from: component12, reason: from getter */
    public final String getStocktakeWarehouse() {
        return this.stocktakeWarehouse;
    }

    public final List<MaterialDto> component13() {
        return this.searchResults;
    }

    /* renamed from: component14, reason: from getter */
    public final int getPendingCount() {
        return this.pendingCount;
    }

    /* renamed from: component15, reason: from getter */
    public final String getBaseUrl() {
        return this.baseUrl;
    }

    /* renamed from: component2, reason: from getter */
    public final String getUsername() {
        return this.username;
    }

    /* renamed from: component3, reason: from getter */
    public final MainTab getSelectedTab() {
        return this.selectedTab;
    }

    /* renamed from: component4, reason: from getter */
    public final boolean getLoading() {
        return this.loading;
    }

    /* renamed from: component5, reason: from getter */
    public final String getMessage() {
        return this.message;
    }

    /* renamed from: component6, reason: from getter */
    public final String getError() {
        return this.error;
    }

    public final List<ScanLine> component7() {
        return this.inboundLines;
    }

    public final List<ScanLine> component8() {
        return this.outboundLines;
    }

    /* renamed from: component9, reason: from getter */
    public final MaterialDto getQueryMaterial() {
        return this.queryMaterial;
    }

    public final MainUiState copy(boolean isLoggedIn, String username, MainTab selectedTab, boolean loading, String message, String error, List<ScanLine> inboundLines, List<ScanLine> outboundLines, MaterialDto queryMaterial, List<ScanLine> stocktakeLines, String stocktakeMode, String stocktakeWarehouse, List<MaterialDto> searchResults, int pendingCount, String baseUrl) {
        Intrinsics.checkNotNullParameter(username, "username");
        Intrinsics.checkNotNullParameter(selectedTab, "selectedTab");
        Intrinsics.checkNotNullParameter(inboundLines, "inboundLines");
        Intrinsics.checkNotNullParameter(outboundLines, "outboundLines");
        Intrinsics.checkNotNullParameter(stocktakeLines, "stocktakeLines");
        Intrinsics.checkNotNullParameter(stocktakeMode, "stocktakeMode");
        Intrinsics.checkNotNullParameter(stocktakeWarehouse, "stocktakeWarehouse");
        Intrinsics.checkNotNullParameter(searchResults, "searchResults");
        Intrinsics.checkNotNullParameter(baseUrl, "baseUrl");
        return new MainUiState(isLoggedIn, username, selectedTab, loading, message, error, inboundLines, outboundLines, queryMaterial, stocktakeLines, stocktakeMode, stocktakeWarehouse, searchResults, pendingCount, baseUrl);
    }

    public boolean equals(Object other) {
        if (this == other) {
            return true;
        }
        if (!(other instanceof MainUiState)) {
            return false;
        }
        MainUiState mainUiState = (MainUiState) other;
        return this.isLoggedIn == mainUiState.isLoggedIn && Intrinsics.areEqual(this.username, mainUiState.username) && this.selectedTab == mainUiState.selectedTab && this.loading == mainUiState.loading && Intrinsics.areEqual(this.message, mainUiState.message) && Intrinsics.areEqual(this.error, mainUiState.error) && Intrinsics.areEqual(this.inboundLines, mainUiState.inboundLines) && Intrinsics.areEqual(this.outboundLines, mainUiState.outboundLines) && Intrinsics.areEqual(this.queryMaterial, mainUiState.queryMaterial) && Intrinsics.areEqual(this.stocktakeLines, mainUiState.stocktakeLines) && Intrinsics.areEqual(this.stocktakeMode, mainUiState.stocktakeMode) && Intrinsics.areEqual(this.stocktakeWarehouse, mainUiState.stocktakeWarehouse) && Intrinsics.areEqual(this.searchResults, mainUiState.searchResults) && this.pendingCount == mainUiState.pendingCount && Intrinsics.areEqual(this.baseUrl, mainUiState.baseUrl);
    }

    public int hashCode() {
        return (((((((((((((((((((((((((((Boolean.hashCode(this.isLoggedIn) * 31) + this.username.hashCode()) * 31) + this.selectedTab.hashCode()) * 31) + Boolean.hashCode(this.loading)) * 31) + (this.message == null ? 0 : this.message.hashCode())) * 31) + (this.error == null ? 0 : this.error.hashCode())) * 31) + this.inboundLines.hashCode()) * 31) + this.outboundLines.hashCode()) * 31) + (this.queryMaterial != null ? this.queryMaterial.hashCode() : 0)) * 31) + this.stocktakeLines.hashCode()) * 31) + this.stocktakeMode.hashCode()) * 31) + this.stocktakeWarehouse.hashCode()) * 31) + this.searchResults.hashCode()) * 31) + Integer.hashCode(this.pendingCount)) * 31) + this.baseUrl.hashCode();
    }

    public String toString() {
        return "MainUiState(isLoggedIn=" + this.isLoggedIn + ", username=" + this.username + ", selectedTab=" + this.selectedTab + ", loading=" + this.loading + ", message=" + this.message + ", error=" + this.error + ", inboundLines=" + this.inboundLines + ", outboundLines=" + this.outboundLines + ", queryMaterial=" + this.queryMaterial + ", stocktakeLines=" + this.stocktakeLines + ", stocktakeMode=" + this.stocktakeMode + ", stocktakeWarehouse=" + this.stocktakeWarehouse + ", searchResults=" + this.searchResults + ", pendingCount=" + this.pendingCount + ", baseUrl=" + this.baseUrl + ")";
    }

    public MainUiState(boolean isLoggedIn, String username, MainTab selectedTab, boolean loading, String message, String error, List<ScanLine> inboundLines, List<ScanLine> outboundLines, MaterialDto queryMaterial, List<ScanLine> stocktakeLines, String stocktakeMode, String stocktakeWarehouse, List<MaterialDto> searchResults, int pendingCount, String baseUrl) {
        Intrinsics.checkNotNullParameter(username, "username");
        Intrinsics.checkNotNullParameter(selectedTab, "selectedTab");
        Intrinsics.checkNotNullParameter(inboundLines, "inboundLines");
        Intrinsics.checkNotNullParameter(outboundLines, "outboundLines");
        Intrinsics.checkNotNullParameter(stocktakeLines, "stocktakeLines");
        Intrinsics.checkNotNullParameter(stocktakeMode, "stocktakeMode");
        Intrinsics.checkNotNullParameter(stocktakeWarehouse, "stocktakeWarehouse");
        Intrinsics.checkNotNullParameter(searchResults, "searchResults");
        Intrinsics.checkNotNullParameter(baseUrl, "baseUrl");
        this.isLoggedIn = isLoggedIn;
        this.username = username;
        this.selectedTab = selectedTab;
        this.loading = loading;
        this.message = message;
        this.error = error;
        this.inboundLines = inboundLines;
        this.outboundLines = outboundLines;
        this.queryMaterial = queryMaterial;
        this.stocktakeLines = stocktakeLines;
        this.stocktakeMode = stocktakeMode;
        this.stocktakeWarehouse = stocktakeWarehouse;
        this.searchResults = searchResults;
        this.pendingCount = pendingCount;
        this.baseUrl = baseUrl;
    }

    public /* synthetic */ MainUiState(boolean z, String str, MainTab mainTab, boolean z2, String str2, String str3, List list, List list2, MaterialDto materialDto, List list3, String str4, String str5, List list4, int i, String str6, int i2, DefaultConstructorMarker defaultConstructorMarker) {
        this((i2 & 1) != 0 ? false : z, (i2 & 2) != 0 ? "" : str, (i2 & 4) != 0 ? MainTab.Inbound : mainTab, (i2 & 8) != 0 ? false : z2, (i2 & 16) != 0 ? null : str2, (i2 & 32) != 0 ? null : str3, (i2 & 64) != 0 ? CollectionsKt.emptyList() : list, (i2 & 128) != 0 ? CollectionsKt.emptyList() : list2, (i2 & 256) == 0 ? materialDto : null, (i2 & 512) != 0 ? CollectionsKt.emptyList() : list3, (i2 & 1024) != 0 ? "all" : str4, (i2 & 2048) != 0 ? "" : str5, (i2 & 4096) != 0 ? CollectionsKt.emptyList() : list4, (i2 & 8192) != 0 ? 0 : i, (i2 & 16384) == 0 ? str6 : "");
    }

    public final boolean isLoggedIn() {
        return this.isLoggedIn;
    }

    public final String getUsername() {
        return this.username;
    }

    public final MainTab getSelectedTab() {
        return this.selectedTab;
    }

    public final boolean getLoading() {
        return this.loading;
    }

    public final String getMessage() {
        return this.message;
    }

    public final String getError() {
        return this.error;
    }

    public final List<ScanLine> getInboundLines() {
        return this.inboundLines;
    }

    public final List<ScanLine> getOutboundLines() {
        return this.outboundLines;
    }

    public final MaterialDto getQueryMaterial() {
        return this.queryMaterial;
    }

    public final List<ScanLine> getStocktakeLines() {
        return this.stocktakeLines;
    }

    public final String getStocktakeMode() {
        return this.stocktakeMode;
    }

    public final String getStocktakeWarehouse() {
        return this.stocktakeWarehouse;
    }

    public final List<MaterialDto> getSearchResults() {
        return this.searchResults;
    }

    public final int getPendingCount() {
        return this.pendingCount;
    }

    public final String getBaseUrl() {
        return this.baseUrl;
    }
}
