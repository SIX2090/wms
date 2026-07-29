package com.factory.wms.data.model;

import com.google.gson.annotations.SerializedName;
import kotlin.Metadata;
import kotlin.jvm.internal.Intrinsics;

/* compiled from: ApiModels.kt */
@Metadata(d1 = {"\u0000*\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0000\n\u0002\u0010\u000e\n\u0002\b\u0002\n\u0002\u0010\u0006\n\u0002\b\u000f\n\u0002\u0010\u000b\n\u0002\b\u0002\n\u0002\u0010\b\n\u0002\b\u0002\b\u0087\b\u0018\u00002\u00020\u0001B+\u0012\u0006\u0010\u0002\u001a\u00020\u0003\u0012\n\b\u0002\u0010\u0004\u001a\u0004\u0018\u00010\u0003\u0012\u0006\u0010\u0005\u001a\u00020\u0006\u0012\u0006\u0010\u0007\u001a\u00020\u0006¢\u0006\u0004\b\b\u0010\tJ\t\u0010\u0010\u001a\u00020\u0003HÆ\u0003J\u000b\u0010\u0011\u001a\u0004\u0018\u00010\u0003HÆ\u0003J\t\u0010\u0012\u001a\u00020\u0006HÆ\u0003J\t\u0010\u0013\u001a\u00020\u0006HÆ\u0003J3\u0010\u0014\u001a\u00020\u00002\b\b\u0002\u0010\u0002\u001a\u00020\u00032\n\b\u0002\u0010\u0004\u001a\u0004\u0018\u00010\u00032\b\b\u0002\u0010\u0005\u001a\u00020\u00062\b\b\u0002\u0010\u0007\u001a\u00020\u0006HÆ\u0001J\u0013\u0010\u0015\u001a\u00020\u00162\b\u0010\u0017\u001a\u0004\u0018\u00010\u0001HÖ\u0003J\t\u0010\u0018\u001a\u00020\u0019HÖ\u0001J\t\u0010\u001a\u001a\u00020\u0003HÖ\u0001R\u0016\u0010\u0002\u001a\u00020\u00038\u0006X\u0087\u0004¢\u0006\b\n\u0000\u001a\u0004\b\n\u0010\u000bR\u0018\u0010\u0004\u001a\u0004\u0018\u00010\u00038\u0006X\u0087\u0004¢\u0006\b\n\u0000\u001a\u0004\b\f\u0010\u000bR\u0016\u0010\u0005\u001a\u00020\u00068\u0006X\u0087\u0004¢\u0006\b\n\u0000\u001a\u0004\b\r\u0010\u000eR\u0016\u0010\u0007\u001a\u00020\u00068\u0006X\u0087\u0004¢\u0006\b\n\u0000\u001a\u0004\b\u000f\u0010\u000e¨\u0006\u001b"}, d2 = {"Lcom/factory/wms/data/model/StocktakeLineDto;", "", "materialCode", "", "warehouseCode", "systemStock", "", "actualStock", "<init>", "(Ljava/lang/String;Ljava/lang/String;DD)V", "getMaterialCode", "()Ljava/lang/String;", "getWarehouseCode", "getSystemStock", "()D", "getActualStock", "component1", "component2", "component3", "component4", "copy", "equals", "", "other", "hashCode", "", "toString", "app_debug"}, k = 1, mv = {2, 0, 0}, xi = 48)
/* loaded from: classes5.dex */
public final /* data */ class StocktakeLineDto {
    public static final int $stable = 0;

    @SerializedName("actual_stock")
    private final double actualStock;

    @SerializedName("material_code")
    private final String materialCode;

    @SerializedName("system_stock")
    private final double systemStock;

    @SerializedName("warehouse_code")
    private final String warehouseCode;

    public static /* synthetic */ StocktakeLineDto copy$default(StocktakeLineDto stocktakeLineDto, String str, String str2, double d, double d2, int i, Object obj) {
        if ((i & 1) != 0) {
            str = stocktakeLineDto.materialCode;
        }
        if ((i & 2) != 0) {
            str2 = stocktakeLineDto.warehouseCode;
        }
        String str3 = str2;
        if ((i & 4) != 0) {
            d = stocktakeLineDto.systemStock;
        }
        double d3 = d;
        if ((i & 8) != 0) {
            d2 = stocktakeLineDto.actualStock;
        }
        return stocktakeLineDto.copy(str, str3, d3, d2);
    }

    /* renamed from: component1, reason: from getter */
    public final String getMaterialCode() {
        return this.materialCode;
    }

    /* renamed from: component2, reason: from getter */
    public final String getWarehouseCode() {
        return this.warehouseCode;
    }

    /* renamed from: component3, reason: from getter */
    public final double getSystemStock() {
        return this.systemStock;
    }

    /* renamed from: component4, reason: from getter */
    public final double getActualStock() {
        return this.actualStock;
    }

    public final StocktakeLineDto copy(String materialCode, String warehouseCode, double systemStock, double actualStock) {
        Intrinsics.checkNotNullParameter(materialCode, "materialCode");
        return new StocktakeLineDto(materialCode, warehouseCode, systemStock, actualStock);
    }

    public boolean equals(Object other) {
        if (this == other) {
            return true;
        }
        if (!(other instanceof StocktakeLineDto)) {
            return false;
        }
        StocktakeLineDto stocktakeLineDto = (StocktakeLineDto) other;
        return Intrinsics.areEqual(this.materialCode, stocktakeLineDto.materialCode) && Intrinsics.areEqual(this.warehouseCode, stocktakeLineDto.warehouseCode) && Double.compare(this.systemStock, stocktakeLineDto.systemStock) == 0 && Double.compare(this.actualStock, stocktakeLineDto.actualStock) == 0;
    }

    public int hashCode() {
        return (((((this.materialCode.hashCode() * 31) + (this.warehouseCode == null ? 0 : this.warehouseCode.hashCode())) * 31) + Double.hashCode(this.systemStock)) * 31) + Double.hashCode(this.actualStock);
    }

    public String toString() {
        return "StocktakeLineDto(materialCode=" + this.materialCode + ", warehouseCode=" + this.warehouseCode + ", systemStock=" + this.systemStock + ", actualStock=" + this.actualStock + ")";
    }

    public StocktakeLineDto(String materialCode, String warehouseCode, double systemStock, double actualStock) {
        Intrinsics.checkNotNullParameter(materialCode, "materialCode");
        this.materialCode = materialCode;
        this.warehouseCode = warehouseCode;
        this.systemStock = systemStock;
        this.actualStock = actualStock;
    }

    /* JADX WARN: Illegal instructions before constructor call */
    /*
        Code decompiled incorrectly, please refer to instructions dump.
        To view partially-correct add '--show-bad-code' argument
    */
    public /* synthetic */ StocktakeLineDto(java.lang.String r8, java.lang.String r9, double r10, double r12, int r14, kotlin.jvm.internal.DefaultConstructorMarker r15) {
        /*
            r7 = this;
            r14 = r14 & 2
            if (r14 == 0) goto L7
            r9 = 0
            r2 = r9
            goto L8
        L7:
            r2 = r9
        L8:
            r0 = r7
            r1 = r8
            r3 = r10
            r5 = r12
            r0.<init>(r1, r2, r3, r5)
            return
        */
        throw new UnsupportedOperationException("Method not decompiled: com.factory.wms.data.model.StocktakeLineDto.<init>(java.lang.String, java.lang.String, double, double, int, kotlin.jvm.internal.DefaultConstructorMarker):void");
    }

    public final String getMaterialCode() {
        return this.materialCode;
    }

    public final String getWarehouseCode() {
        return this.warehouseCode;
    }

    public final double getSystemStock() {
        return this.systemStock;
    }

    public final double getActualStock() {
        return this.actualStock;
    }
}
