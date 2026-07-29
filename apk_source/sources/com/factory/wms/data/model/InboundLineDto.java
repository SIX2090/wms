package com.factory.wms.data.model;

import com.google.gson.annotations.SerializedName;
import kotlin.Metadata;
import kotlin.jvm.internal.Intrinsics;

/* compiled from: ApiModels.kt */
@Metadata(d1 = {"\u0000*\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0000\n\u0002\u0010\u000e\n\u0002\b\u0002\n\u0002\u0010\u0006\n\u0002\b\u000f\n\u0002\u0010\u000b\n\u0002\b\u0002\n\u0002\u0010\b\n\u0002\b\u0002\b\u0087\b\u0018\u00002\u00020\u0001B/\u0012\u0006\u0010\u0002\u001a\u00020\u0003\u0012\n\b\u0002\u0010\u0004\u001a\u0004\u0018\u00010\u0003\u0012\u0006\u0010\u0005\u001a\u00020\u0006\u0012\n\b\u0002\u0010\u0007\u001a\u0004\u0018\u00010\u0003¢\u0006\u0004\b\b\u0010\tJ\t\u0010\u0010\u001a\u00020\u0003HÆ\u0003J\u000b\u0010\u0011\u001a\u0004\u0018\u00010\u0003HÆ\u0003J\t\u0010\u0012\u001a\u00020\u0006HÆ\u0003J\u000b\u0010\u0013\u001a\u0004\u0018\u00010\u0003HÆ\u0003J5\u0010\u0014\u001a\u00020\u00002\b\b\u0002\u0010\u0002\u001a\u00020\u00032\n\b\u0002\u0010\u0004\u001a\u0004\u0018\u00010\u00032\b\b\u0002\u0010\u0005\u001a\u00020\u00062\n\b\u0002\u0010\u0007\u001a\u0004\u0018\u00010\u0003HÆ\u0001J\u0013\u0010\u0015\u001a\u00020\u00162\b\u0010\u0017\u001a\u0004\u0018\u00010\u0001HÖ\u0003J\t\u0010\u0018\u001a\u00020\u0019HÖ\u0001J\t\u0010\u001a\u001a\u00020\u0003HÖ\u0001R\u0016\u0010\u0002\u001a\u00020\u00038\u0006X\u0087\u0004¢\u0006\b\n\u0000\u001a\u0004\b\n\u0010\u000bR\u0018\u0010\u0004\u001a\u0004\u0018\u00010\u00038\u0006X\u0087\u0004¢\u0006\b\n\u0000\u001a\u0004\b\f\u0010\u000bR\u0011\u0010\u0005\u001a\u00020\u0006¢\u0006\b\n\u0000\u001a\u0004\b\r\u0010\u000eR\u0018\u0010\u0007\u001a\u0004\u0018\u00010\u00038\u0006X\u0087\u0004¢\u0006\b\n\u0000\u001a\u0004\b\u000f\u0010\u000b¨\u0006\u001b"}, d2 = {"Lcom/factory/wms/data/model/InboundLineDto;", "", "materialCode", "", "warehouseCode", "quantity", "", "batchNo", "<init>", "(Ljava/lang/String;Ljava/lang/String;DLjava/lang/String;)V", "getMaterialCode", "()Ljava/lang/String;", "getWarehouseCode", "getQuantity", "()D", "getBatchNo", "component1", "component2", "component3", "component4", "copy", "equals", "", "other", "hashCode", "", "toString", "app_debug"}, k = 1, mv = {2, 0, 0}, xi = 48)
/* loaded from: classes5.dex */
public final /* data */ class InboundLineDto {
    public static final int $stable = 0;

    @SerializedName("batch_no")
    private final String batchNo;

    @SerializedName("material_code")
    private final String materialCode;
    private final double quantity;

    @SerializedName("warehouse_code")
    private final String warehouseCode;

    public static /* synthetic */ InboundLineDto copy$default(InboundLineDto inboundLineDto, String str, String str2, double d, String str3, int i, Object obj) {
        if ((i & 1) != 0) {
            str = inboundLineDto.materialCode;
        }
        if ((i & 2) != 0) {
            str2 = inboundLineDto.warehouseCode;
        }
        String str4 = str2;
        if ((i & 4) != 0) {
            d = inboundLineDto.quantity;
        }
        double d2 = d;
        if ((i & 8) != 0) {
            str3 = inboundLineDto.batchNo;
        }
        return inboundLineDto.copy(str, str4, d2, str3);
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

    /* renamed from: component4, reason: from getter */
    public final String getBatchNo() {
        return this.batchNo;
    }

    public final InboundLineDto copy(String materialCode, String warehouseCode, double quantity, String batchNo) {
        Intrinsics.checkNotNullParameter(materialCode, "materialCode");
        return new InboundLineDto(materialCode, warehouseCode, quantity, batchNo);
    }

    public boolean equals(Object other) {
        if (this == other) {
            return true;
        }
        if (!(other instanceof InboundLineDto)) {
            return false;
        }
        InboundLineDto inboundLineDto = (InboundLineDto) other;
        return Intrinsics.areEqual(this.materialCode, inboundLineDto.materialCode) && Intrinsics.areEqual(this.warehouseCode, inboundLineDto.warehouseCode) && Double.compare(this.quantity, inboundLineDto.quantity) == 0 && Intrinsics.areEqual(this.batchNo, inboundLineDto.batchNo);
    }

    public int hashCode() {
        return (((((this.materialCode.hashCode() * 31) + (this.warehouseCode == null ? 0 : this.warehouseCode.hashCode())) * 31) + Double.hashCode(this.quantity)) * 31) + (this.batchNo != null ? this.batchNo.hashCode() : 0);
    }

    public String toString() {
        return "InboundLineDto(materialCode=" + this.materialCode + ", warehouseCode=" + this.warehouseCode + ", quantity=" + this.quantity + ", batchNo=" + this.batchNo + ")";
    }

    public InboundLineDto(String materialCode, String warehouseCode, double quantity, String batchNo) {
        Intrinsics.checkNotNullParameter(materialCode, "materialCode");
        this.materialCode = materialCode;
        this.warehouseCode = warehouseCode;
        this.quantity = quantity;
        this.batchNo = batchNo;
    }

    /* JADX WARN: Illegal instructions before constructor call */
    /*
        Code decompiled incorrectly, please refer to instructions dump.
        To view partially-correct add '--show-bad-code' argument
    */
    public /* synthetic */ InboundLineDto(java.lang.String r8, java.lang.String r9, double r10, java.lang.String r12, int r13, kotlin.jvm.internal.DefaultConstructorMarker r14) {
        /*
            r7 = this;
            r14 = r13 & 2
            r0 = 0
            if (r14 == 0) goto L7
            r3 = r0
            goto L8
        L7:
            r3 = r9
        L8:
            r9 = r13 & 8
            if (r9 == 0) goto Le
            r6 = r0
            goto Lf
        Le:
            r6 = r12
        Lf:
            r1 = r7
            r2 = r8
            r4 = r10
            r1.<init>(r2, r3, r4, r6)
            return
        */
        throw new UnsupportedOperationException("Method not decompiled: com.factory.wms.data.model.InboundLineDto.<init>(java.lang.String, java.lang.String, double, java.lang.String, int, kotlin.jvm.internal.DefaultConstructorMarker):void");
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

    public final String getBatchNo() {
        return this.batchNo;
    }
}
