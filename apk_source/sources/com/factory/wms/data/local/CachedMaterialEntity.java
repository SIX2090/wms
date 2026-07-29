package com.factory.wms.data.local;

import androidx.autofill.HintConstants;
import kotlin.Metadata;
import kotlin.jvm.internal.Intrinsics;

/* compiled from: Entities.kt */
@Metadata(d1 = {"\u00002\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0000\n\u0002\u0010\u000e\n\u0002\b\u0004\n\u0002\u0010\u0006\n\u0002\b\u0002\n\u0002\u0010\t\n\u0002\b\u0015\n\u0002\u0010\u000b\n\u0002\b\u0002\n\u0002\u0010\b\n\u0002\b\u0002\b\u0087\b\u0018\u00002\u00020\u0001BE\u0012\u0006\u0010\u0002\u001a\u00020\u0003\u0012\u0006\u0010\u0004\u001a\u00020\u0003\u0012\b\u0010\u0005\u001a\u0004\u0018\u00010\u0003\u0012\b\u0010\u0006\u001a\u0004\u0018\u00010\u0003\u0012\u0006\u0010\u0007\u001a\u00020\b\u0012\b\u0010\t\u001a\u0004\u0018\u00010\u0003\u0012\u0006\u0010\n\u001a\u00020\u000b¢\u0006\u0004\b\f\u0010\rJ\t\u0010\u0018\u001a\u00020\u0003HÆ\u0003J\t\u0010\u0019\u001a\u00020\u0003HÆ\u0003J\u000b\u0010\u001a\u001a\u0004\u0018\u00010\u0003HÆ\u0003J\u000b\u0010\u001b\u001a\u0004\u0018\u00010\u0003HÆ\u0003J\t\u0010\u001c\u001a\u00020\bHÆ\u0003J\u000b\u0010\u001d\u001a\u0004\u0018\u00010\u0003HÆ\u0003J\t\u0010\u001e\u001a\u00020\u000bHÆ\u0003JU\u0010\u001f\u001a\u00020\u00002\b\b\u0002\u0010\u0002\u001a\u00020\u00032\b\b\u0002\u0010\u0004\u001a\u00020\u00032\n\b\u0002\u0010\u0005\u001a\u0004\u0018\u00010\u00032\n\b\u0002\u0010\u0006\u001a\u0004\u0018\u00010\u00032\b\b\u0002\u0010\u0007\u001a\u00020\b2\n\b\u0002\u0010\t\u001a\u0004\u0018\u00010\u00032\b\b\u0002\u0010\n\u001a\u00020\u000bHÆ\u0001J\u0013\u0010 \u001a\u00020!2\b\u0010\"\u001a\u0004\u0018\u00010\u0001HÖ\u0003J\t\u0010#\u001a\u00020$HÖ\u0001J\t\u0010%\u001a\u00020\u0003HÖ\u0001R\u0016\u0010\u0002\u001a\u00020\u00038\u0006X\u0087\u0004¢\u0006\b\n\u0000\u001a\u0004\b\u000e\u0010\u000fR\u0011\u0010\u0004\u001a\u00020\u0003¢\u0006\b\n\u0000\u001a\u0004\b\u0010\u0010\u000fR\u0013\u0010\u0005\u001a\u0004\u0018\u00010\u0003¢\u0006\b\n\u0000\u001a\u0004\b\u0011\u0010\u000fR\u0013\u0010\u0006\u001a\u0004\u0018\u00010\u0003¢\u0006\b\n\u0000\u001a\u0004\b\u0012\u0010\u000fR\u0011\u0010\u0007\u001a\u00020\b¢\u0006\b\n\u0000\u001a\u0004\b\u0013\u0010\u0014R\u0013\u0010\t\u001a\u0004\u0018\u00010\u0003¢\u0006\b\n\u0000\u001a\u0004\b\u0015\u0010\u000fR\u0011\u0010\n\u001a\u00020\u000b¢\u0006\b\n\u0000\u001a\u0004\b\u0016\u0010\u0017¨\u0006&"}, d2 = {"Lcom/factory/wms/data/local/CachedMaterialEntity;", "", "code", "", HintConstants.AUTOFILL_HINT_NAME, "spec", "unit", "stock", "", "warehouseCode", "updatedAt", "", "<init>", "(Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;DLjava/lang/String;J)V", "getCode", "()Ljava/lang/String;", "getName", "getSpec", "getUnit", "getStock", "()D", "getWarehouseCode", "getUpdatedAt", "()J", "component1", "component2", "component3", "component4", "component5", "component6", "component7", "copy", "equals", "", "other", "hashCode", "", "toString", "app_debug"}, k = 1, mv = {2, 0, 0}, xi = 48)
/* loaded from: classes8.dex */
public final /* data */ class CachedMaterialEntity {
    public static final int $stable = 0;
    private final String code;
    private final String name;
    private final String spec;
    private final double stock;
    private final String unit;
    private final long updatedAt;
    private final String warehouseCode;

    /* renamed from: component1, reason: from getter */
    public final String getCode() {
        return this.code;
    }

    /* renamed from: component2, reason: from getter */
    public final String getName() {
        return this.name;
    }

    /* renamed from: component3, reason: from getter */
    public final String getSpec() {
        return this.spec;
    }

    /* renamed from: component4, reason: from getter */
    public final String getUnit() {
        return this.unit;
    }

    /* renamed from: component5, reason: from getter */
    public final double getStock() {
        return this.stock;
    }

    /* renamed from: component6, reason: from getter */
    public final String getWarehouseCode() {
        return this.warehouseCode;
    }

    /* renamed from: component7, reason: from getter */
    public final long getUpdatedAt() {
        return this.updatedAt;
    }

    public final CachedMaterialEntity copy(String code, String name, String spec, String unit, double stock, String warehouseCode, long updatedAt) {
        Intrinsics.checkNotNullParameter(code, "code");
        Intrinsics.checkNotNullParameter(name, "name");
        return new CachedMaterialEntity(code, name, spec, unit, stock, warehouseCode, updatedAt);
    }

    public boolean equals(Object other) {
        if (this == other) {
            return true;
        }
        if (!(other instanceof CachedMaterialEntity)) {
            return false;
        }
        CachedMaterialEntity cachedMaterialEntity = (CachedMaterialEntity) other;
        return Intrinsics.areEqual(this.code, cachedMaterialEntity.code) && Intrinsics.areEqual(this.name, cachedMaterialEntity.name) && Intrinsics.areEqual(this.spec, cachedMaterialEntity.spec) && Intrinsics.areEqual(this.unit, cachedMaterialEntity.unit) && Double.compare(this.stock, cachedMaterialEntity.stock) == 0 && Intrinsics.areEqual(this.warehouseCode, cachedMaterialEntity.warehouseCode) && this.updatedAt == cachedMaterialEntity.updatedAt;
    }

    public int hashCode() {
        return (((((((((((this.code.hashCode() * 31) + this.name.hashCode()) * 31) + (this.spec == null ? 0 : this.spec.hashCode())) * 31) + (this.unit == null ? 0 : this.unit.hashCode())) * 31) + Double.hashCode(this.stock)) * 31) + (this.warehouseCode != null ? this.warehouseCode.hashCode() : 0)) * 31) + Long.hashCode(this.updatedAt);
    }

    public String toString() {
        return "CachedMaterialEntity(code=" + this.code + ", name=" + this.name + ", spec=" + this.spec + ", unit=" + this.unit + ", stock=" + this.stock + ", warehouseCode=" + this.warehouseCode + ", updatedAt=" + this.updatedAt + ")";
    }

    public CachedMaterialEntity(String code, String name, String spec, String unit, double stock, String warehouseCode, long updatedAt) {
        Intrinsics.checkNotNullParameter(code, "code");
        Intrinsics.checkNotNullParameter(name, "name");
        this.code = code;
        this.name = name;
        this.spec = spec;
        this.unit = unit;
        this.stock = stock;
        this.warehouseCode = warehouseCode;
        this.updatedAt = updatedAt;
    }

    public final String getCode() {
        return this.code;
    }

    public final String getName() {
        return this.name;
    }

    public final String getSpec() {
        return this.spec;
    }

    public final String getUnit() {
        return this.unit;
    }

    public final double getStock() {
        return this.stock;
    }

    public final String getWarehouseCode() {
        return this.warehouseCode;
    }

    public final long getUpdatedAt() {
        return this.updatedAt;
    }
}
