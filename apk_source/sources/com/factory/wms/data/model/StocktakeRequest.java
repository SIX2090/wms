package com.factory.wms.data.model;

import com.google.gson.annotations.SerializedName;
import java.util.List;
import kotlin.Metadata;
import kotlin.jvm.internal.DefaultConstructorMarker;
import kotlin.jvm.internal.Intrinsics;

/* compiled from: ApiModels.kt */
@Metadata(d1 = {"\u0000.\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0000\n\u0002\u0010\u000e\n\u0002\b\u0002\n\u0002\u0010 \n\u0002\u0018\u0002\n\u0002\b\f\n\u0002\u0010\u000b\n\u0002\b\u0002\n\u0002\u0010\b\n\u0002\b\u0002\b\u0087\b\u0018\u00002\u00020\u0001B)\u0012\u0006\u0010\u0002\u001a\u00020\u0003\u0012\n\b\u0002\u0010\u0004\u001a\u0004\u0018\u00010\u0003\u0012\f\u0010\u0005\u001a\b\u0012\u0004\u0012\u00020\u00070\u0006¢\u0006\u0004\b\b\u0010\tJ\t\u0010\u000f\u001a\u00020\u0003HÆ\u0003J\u000b\u0010\u0010\u001a\u0004\u0018\u00010\u0003HÆ\u0003J\u000f\u0010\u0011\u001a\b\u0012\u0004\u0012\u00020\u00070\u0006HÆ\u0003J/\u0010\u0012\u001a\u00020\u00002\b\b\u0002\u0010\u0002\u001a\u00020\u00032\n\b\u0002\u0010\u0004\u001a\u0004\u0018\u00010\u00032\u000e\b\u0002\u0010\u0005\u001a\b\u0012\u0004\u0012\u00020\u00070\u0006HÆ\u0001J\u0013\u0010\u0013\u001a\u00020\u00142\b\u0010\u0015\u001a\u0004\u0018\u00010\u0001HÖ\u0003J\t\u0010\u0016\u001a\u00020\u0017HÖ\u0001J\t\u0010\u0018\u001a\u00020\u0003HÖ\u0001R\u0011\u0010\u0002\u001a\u00020\u0003¢\u0006\b\n\u0000\u001a\u0004\b\n\u0010\u000bR\u0018\u0010\u0004\u001a\u0004\u0018\u00010\u00038\u0006X\u0087\u0004¢\u0006\b\n\u0000\u001a\u0004\b\f\u0010\u000bR\u0017\u0010\u0005\u001a\b\u0012\u0004\u0012\u00020\u00070\u0006¢\u0006\b\n\u0000\u001a\u0004\b\r\u0010\u000e¨\u0006\u0019"}, d2 = {"Lcom/factory/wms/data/model/StocktakeRequest;", "", "mode", "", "warehouseCode", "lines", "", "Lcom/factory/wms/data/model/StocktakeLineDto;", "<init>", "(Ljava/lang/String;Ljava/lang/String;Ljava/util/List;)V", "getMode", "()Ljava/lang/String;", "getWarehouseCode", "getLines", "()Ljava/util/List;", "component1", "component2", "component3", "copy", "equals", "", "other", "hashCode", "", "toString", "app_debug"}, k = 1, mv = {2, 0, 0}, xi = 48)
/* loaded from: classes5.dex */
public final /* data */ class StocktakeRequest {
    public static final int $stable = 8;
    private final List<StocktakeLineDto> lines;
    private final String mode;

    @SerializedName("warehouse_code")
    private final String warehouseCode;

    /* JADX WARN: Multi-variable type inference failed */
    public static /* synthetic */ StocktakeRequest copy$default(StocktakeRequest stocktakeRequest, String str, String str2, List list, int i, Object obj) {
        if ((i & 1) != 0) {
            str = stocktakeRequest.mode;
        }
        if ((i & 2) != 0) {
            str2 = stocktakeRequest.warehouseCode;
        }
        if ((i & 4) != 0) {
            list = stocktakeRequest.lines;
        }
        return stocktakeRequest.copy(str, str2, list);
    }

    /* renamed from: component1, reason: from getter */
    public final String getMode() {
        return this.mode;
    }

    /* renamed from: component2, reason: from getter */
    public final String getWarehouseCode() {
        return this.warehouseCode;
    }

    public final List<StocktakeLineDto> component3() {
        return this.lines;
    }

    public final StocktakeRequest copy(String mode, String warehouseCode, List<StocktakeLineDto> lines) {
        Intrinsics.checkNotNullParameter(mode, "mode");
        Intrinsics.checkNotNullParameter(lines, "lines");
        return new StocktakeRequest(mode, warehouseCode, lines);
    }

    public boolean equals(Object other) {
        if (this == other) {
            return true;
        }
        if (!(other instanceof StocktakeRequest)) {
            return false;
        }
        StocktakeRequest stocktakeRequest = (StocktakeRequest) other;
        return Intrinsics.areEqual(this.mode, stocktakeRequest.mode) && Intrinsics.areEqual(this.warehouseCode, stocktakeRequest.warehouseCode) && Intrinsics.areEqual(this.lines, stocktakeRequest.lines);
    }

    public int hashCode() {
        return (((this.mode.hashCode() * 31) + (this.warehouseCode == null ? 0 : this.warehouseCode.hashCode())) * 31) + this.lines.hashCode();
    }

    public String toString() {
        return "StocktakeRequest(mode=" + this.mode + ", warehouseCode=" + this.warehouseCode + ", lines=" + this.lines + ")";
    }

    public StocktakeRequest(String mode, String warehouseCode, List<StocktakeLineDto> lines) {
        Intrinsics.checkNotNullParameter(mode, "mode");
        Intrinsics.checkNotNullParameter(lines, "lines");
        this.mode = mode;
        this.warehouseCode = warehouseCode;
        this.lines = lines;
    }

    public /* synthetic */ StocktakeRequest(String str, String str2, List list, int i, DefaultConstructorMarker defaultConstructorMarker) {
        this(str, (i & 2) != 0 ? null : str2, list);
    }

    public final String getMode() {
        return this.mode;
    }

    public final String getWarehouseCode() {
        return this.warehouseCode;
    }

    public final List<StocktakeLineDto> getLines() {
        return this.lines;
    }
}
