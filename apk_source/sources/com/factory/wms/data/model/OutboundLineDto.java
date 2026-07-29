package com.factory.wms.data.model;

import com.google.gson.annotations.SerializedName;
import kotlin.Metadata;
import kotlin.jvm.internal.DefaultConstructorMarker;
import kotlin.jvm.internal.Intrinsics;

/* compiled from: ApiModels.kt */
@Metadata(d1 = {"\u0000*\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0000\n\u0002\u0010\u000e\n\u0002\b\u0002\n\u0002\u0010\u0006\n\u0002\b\f\n\u0002\u0010\u000b\n\u0002\b\u0002\n\u0002\u0010\b\n\u0002\b\u0002\b\u0087\b\u0018\u00002\u00020\u0001B#\u0012\u0006\u0010\u0002\u001a\u00020\u0003\u0012\n\b\u0002\u0010\u0004\u001a\u0004\u0018\u00010\u0003\u0012\u0006\u0010\u0005\u001a\u00020\u0006¢\u0006\u0004\b\u0007\u0010\bJ\t\u0010\u000e\u001a\u00020\u0003HÆ\u0003J\u000b\u0010\u000f\u001a\u0004\u0018\u00010\u0003HÆ\u0003J\t\u0010\u0010\u001a\u00020\u0006HÆ\u0003J)\u0010\u0011\u001a\u00020\u00002\b\b\u0002\u0010\u0002\u001a\u00020\u00032\n\b\u0002\u0010\u0004\u001a\u0004\u0018\u00010\u00032\b\b\u0002\u0010\u0005\u001a\u00020\u0006HÆ\u0001J\u0013\u0010\u0012\u001a\u00020\u00132\b\u0010\u0014\u001a\u0004\u0018\u00010\u0001HÖ\u0003J\t\u0010\u0015\u001a\u00020\u0016HÖ\u0001J\t\u0010\u0017\u001a\u00020\u0003HÖ\u0001R\u0016\u0010\u0002\u001a\u00020\u00038\u0006X\u0087\u0004¢\u0006\b\n\u0000\u001a\u0004\b\t\u0010\nR\u0018\u0010\u0004\u001a\u0004\u0018\u00010\u00038\u0006X\u0087\u0004¢\u0006\b\n\u0000\u001a\u0004\b\u000b\u0010\nR\u0011\u0010\u0005\u001a\u00020\u0006¢\u0006\b\n\u0000\u001a\u0004\b\f\u0010\r¨\u0006\u0018"}, d2 = {"Lcom/factory/wms/data/model/OutboundLineDto;", "", "materialCode", "", "warehouseCode", "quantity", "", "<init>", "(Ljava/lang/String;Ljava/lang/String;D)V", "getMaterialCode", "()Ljava/lang/String;", "getWarehouseCode", "getQuantity", "()D", "component1", "component2", "component3", "copy", "equals", "", "other", "hashCode", "", "toString", "app_debug"}, k = 1, mv = {2, 0, 0}, xi = 48)
/* loaded from: classes5.dex */
public final /* data */ class OutboundLineDto {
    public static final int $stable = 0;

    @SerializedName("material_code")
    private final String materialCode;
    private final double quantity;

    @SerializedName("warehouse_code")
    private final String warehouseCode;

    public static /* synthetic */ OutboundLineDto copy$default(OutboundLineDto outboundLineDto, String str, String str2, double d, int i, Object obj) {
        if ((i & 1) != 0) {
            str = outboundLineDto.materialCode;
        }
        if ((i & 2) != 0) {
            str2 = outboundLineDto.warehouseCode;
        }
        if ((i & 4) != 0) {
            d = outboundLineDto.quantity;
        }
        return outboundLineDto.copy(str, str2, d);
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
    public final double getQuantity() {
        return this.quantity;
    }

    public final OutboundLineDto copy(String materialCode, String warehouseCode, double quantity) {
        Intrinsics.checkNotNullParameter(materialCode, "materialCode");
        return new OutboundLineDto(materialCode, warehouseCode, quantity);
    }

    public boolean equals(Object other) {
        if (this == other) {
            return true;
        }
        if (!(other instanceof OutboundLineDto)) {
            return false;
        }
        OutboundLineDto outboundLineDto = (OutboundLineDto) other;
        return Intrinsics.areEqual(this.materialCode, outboundLineDto.materialCode) && Intrinsics.areEqual(this.warehouseCode, outboundLineDto.warehouseCode) && Double.compare(this.quantity, outboundLineDto.quantity) == 0;
    }

    public int hashCode() {
        return (((this.materialCode.hashCode() * 31) + (this.warehouseCode == null ? 0 : this.warehouseCode.hashCode())) * 31) + Double.hashCode(this.quantity);
    }

    public String toString() {
        return "OutboundLineDto(materialCode=" + this.materialCode + ", warehouseCode=" + this.warehouseCode + ", quantity=" + this.quantity + ")";
    }

    public OutboundLineDto(String materialCode, String warehouseCode, double quantity) {
        Intrinsics.checkNotNullParameter(materialCode, "materialCode");
        this.materialCode = materialCode;
        this.warehouseCode = warehouseCode;
        this.quantity = quantity;
    }

    public /* synthetic */ OutboundLineDto(String str, String str2, double d, int i, DefaultConstructorMarker defaultConstructorMarker) {
        this(str, (i & 2) != 0 ? null : str2, d);
    }

    public final String getMaterialCode() {
        return this.materialCode;
    }

    public final String getWarehouseCode() {
        return this.warehouseCode;
    }

    public final double getQuantity() {
        return this.quantity;
    }
}
