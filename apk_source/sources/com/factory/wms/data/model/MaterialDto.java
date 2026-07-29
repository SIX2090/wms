package com.factory.wms.data.model;

import androidx.autofill.HintConstants;
import com.google.gson.annotations.SerializedName;
import kotlin.Metadata;
import kotlin.jvm.internal.DefaultConstructorMarker;
import kotlin.jvm.internal.Intrinsics;

/* compiled from: ApiModels.kt */
@Metadata(d1 = {"\u0000(\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0000\n\u0002\u0010\b\n\u0000\n\u0002\u0010\u000e\n\u0002\b\u0004\n\u0002\u0010\u0006\n\u0002\b\u001b\n\u0002\u0010\u000b\n\u0002\b\u0004\b\u0087\b\u0018\u00002\u00020\u0001Ba\u0012\n\b\u0002\u0010\u0002\u001a\u0004\u0018\u00010\u0003\u0012\b\b\u0002\u0010\u0004\u001a\u00020\u0005\u0012\b\b\u0002\u0010\u0006\u001a\u00020\u0005\u0012\n\b\u0002\u0010\u0007\u001a\u0004\u0018\u00010\u0005\u0012\n\b\u0002\u0010\b\u001a\u0004\u0018\u00010\u0005\u0012\b\b\u0002\u0010\t\u001a\u00020\n\u0012\n\b\u0002\u0010\u000b\u001a\u0004\u0018\u00010\u0005\u0012\n\b\u0002\u0010\f\u001a\u0004\u0018\u00010\u0005¢\u0006\u0004\b\r\u0010\u000eJ\u0010\u0010\u001b\u001a\u0004\u0018\u00010\u0003HÆ\u0003¢\u0006\u0002\u0010\u0010J\t\u0010\u001c\u001a\u00020\u0005HÆ\u0003J\t\u0010\u001d\u001a\u00020\u0005HÆ\u0003J\u000b\u0010\u001e\u001a\u0004\u0018\u00010\u0005HÆ\u0003J\u000b\u0010\u001f\u001a\u0004\u0018\u00010\u0005HÆ\u0003J\t\u0010 \u001a\u00020\nHÆ\u0003J\u000b\u0010!\u001a\u0004\u0018\u00010\u0005HÆ\u0003J\u000b\u0010\"\u001a\u0004\u0018\u00010\u0005HÆ\u0003Jh\u0010#\u001a\u00020\u00002\n\b\u0002\u0010\u0002\u001a\u0004\u0018\u00010\u00032\b\b\u0002\u0010\u0004\u001a\u00020\u00052\b\b\u0002\u0010\u0006\u001a\u00020\u00052\n\b\u0002\u0010\u0007\u001a\u0004\u0018\u00010\u00052\n\b\u0002\u0010\b\u001a\u0004\u0018\u00010\u00052\b\b\u0002\u0010\t\u001a\u00020\n2\n\b\u0002\u0010\u000b\u001a\u0004\u0018\u00010\u00052\n\b\u0002\u0010\f\u001a\u0004\u0018\u00010\u0005HÆ\u0001¢\u0006\u0002\u0010$J\u0013\u0010%\u001a\u00020&2\b\u0010'\u001a\u0004\u0018\u00010\u0001HÖ\u0003J\t\u0010(\u001a\u00020\u0003HÖ\u0001J\t\u0010)\u001a\u00020\u0005HÖ\u0001R\u0015\u0010\u0002\u001a\u0004\u0018\u00010\u0003¢\u0006\n\n\u0002\u0010\u0011\u001a\u0004\b\u000f\u0010\u0010R\u0011\u0010\u0004\u001a\u00020\u0005¢\u0006\b\n\u0000\u001a\u0004\b\u0012\u0010\u0013R\u0011\u0010\u0006\u001a\u00020\u0005¢\u0006\b\n\u0000\u001a\u0004\b\u0014\u0010\u0013R\u0013\u0010\u0007\u001a\u0004\u0018\u00010\u0005¢\u0006\b\n\u0000\u001a\u0004\b\u0015\u0010\u0013R\u0013\u0010\b\u001a\u0004\u0018\u00010\u0005¢\u0006\b\n\u0000\u001a\u0004\b\u0016\u0010\u0013R\u0011\u0010\t\u001a\u00020\n¢\u0006\b\n\u0000\u001a\u0004\b\u0017\u0010\u0018R\u0018\u0010\u000b\u001a\u0004\u0018\u00010\u00058\u0006X\u0087\u0004¢\u0006\b\n\u0000\u001a\u0004\b\u0019\u0010\u0013R\u0018\u0010\f\u001a\u0004\u0018\u00010\u00058\u0006X\u0087\u0004¢\u0006\b\n\u0000\u001a\u0004\b\u001a\u0010\u0013¨\u0006*"}, d2 = {"Lcom/factory/wms/data/model/MaterialDto;", "", "id", "", "code", "", HintConstants.AUTOFILL_HINT_NAME, "spec", "unit", "stock", "", "warehouseCode", "locationCode", "<init>", "(Ljava/lang/Integer;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;DLjava/lang/String;Ljava/lang/String;)V", "getId", "()Ljava/lang/Integer;", "Ljava/lang/Integer;", "getCode", "()Ljava/lang/String;", "getName", "getSpec", "getUnit", "getStock", "()D", "getWarehouseCode", "getLocationCode", "component1", "component2", "component3", "component4", "component5", "component6", "component7", "component8", "copy", "(Ljava/lang/Integer;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;DLjava/lang/String;Ljava/lang/String;)Lcom/factory/wms/data/model/MaterialDto;", "equals", "", "other", "hashCode", "toString", "app_debug"}, k = 1, mv = {2, 0, 0}, xi = 48)
/* loaded from: classes5.dex */
public final /* data */ class MaterialDto {
    public static final int $stable = 0;
    private final String code;
    private final Integer id;

    @SerializedName("location_code")
    private final String locationCode;
    private final String name;
    private final String spec;
    private final double stock;
    private final String unit;

    @SerializedName("warehouse_code")
    private final String warehouseCode;

    public MaterialDto() {
        this(null, null, null, null, null, 0.0d, null, null, 255, null);
    }

    /* renamed from: component1, reason: from getter */
    public final Integer getId() {
        return this.id;
    }

    /* renamed from: component2, reason: from getter */
    public final String getCode() {
        return this.code;
    }

    /* renamed from: component3, reason: from getter */
    public final String getName() {
        return this.name;
    }

    /* renamed from: component4, reason: from getter */
    public final String getSpec() {
        return this.spec;
    }

    /* renamed from: component5, reason: from getter */
    public final String getUnit() {
        return this.unit;
    }

    /* renamed from: component6, reason: from getter */
    public final double getStock() {
        return this.stock;
    }

    /* renamed from: component7, reason: from getter */
    public final String getWarehouseCode() {
        return this.warehouseCode;
    }

    /* renamed from: component8, reason: from getter */
    public final String getLocationCode() {
        return this.locationCode;
    }

    public final MaterialDto copy(Integer id, String code, String name, String spec, String unit, double stock, String warehouseCode, String locationCode) {
        Intrinsics.checkNotNullParameter(code, "code");
        Intrinsics.checkNotNullParameter(name, "name");
        return new MaterialDto(id, code, name, spec, unit, stock, warehouseCode, locationCode);
    }

    public boolean equals(Object other) {
        if (this == other) {
            return true;
        }
        if (!(other instanceof MaterialDto)) {
            return false;
        }
        MaterialDto materialDto = (MaterialDto) other;
        return Intrinsics.areEqual(this.id, materialDto.id) && Intrinsics.areEqual(this.code, materialDto.code) && Intrinsics.areEqual(this.name, materialDto.name) && Intrinsics.areEqual(this.spec, materialDto.spec) && Intrinsics.areEqual(this.unit, materialDto.unit) && Double.compare(this.stock, materialDto.stock) == 0 && Intrinsics.areEqual(this.warehouseCode, materialDto.warehouseCode) && Intrinsics.areEqual(this.locationCode, materialDto.locationCode);
    }

    public int hashCode() {
        return ((((((((((((((this.id == null ? 0 : this.id.hashCode()) * 31) + this.code.hashCode()) * 31) + this.name.hashCode()) * 31) + (this.spec == null ? 0 : this.spec.hashCode())) * 31) + (this.unit == null ? 0 : this.unit.hashCode())) * 31) + Double.hashCode(this.stock)) * 31) + (this.warehouseCode == null ? 0 : this.warehouseCode.hashCode())) * 31) + (this.locationCode != null ? this.locationCode.hashCode() : 0);
    }

    public String toString() {
        return "MaterialDto(id=" + this.id + ", code=" + this.code + ", name=" + this.name + ", spec=" + this.spec + ", unit=" + this.unit + ", stock=" + this.stock + ", warehouseCode=" + this.warehouseCode + ", locationCode=" + this.locationCode + ")";
    }

    public MaterialDto(Integer id, String code, String name, String spec, String unit, double stock, String warehouseCode, String locationCode) {
        Intrinsics.checkNotNullParameter(code, "code");
        Intrinsics.checkNotNullParameter(name, "name");
        this.id = id;
        this.code = code;
        this.name = name;
        this.spec = spec;
        this.unit = unit;
        this.stock = stock;
        this.warehouseCode = warehouseCode;
        this.locationCode = locationCode;
    }

    public /* synthetic */ MaterialDto(Integer num, String str, String str2, String str3, String str4, double d, String str5, String str6, int i, DefaultConstructorMarker defaultConstructorMarker) {
        this((i & 1) != 0 ? null : num, (i & 2) != 0 ? "" : str, (i & 4) == 0 ? str2 : "", (i & 8) != 0 ? null : str3, (i & 16) != 0 ? null : str4, (i & 32) != 0 ? 0.0d : d, (i & 64) != 0 ? null : str5, (i & 128) == 0 ? str6 : null);
    }

    public final Integer getId() {
        return this.id;
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

    public final String getLocationCode() {
        return this.locationCode;
    }
}
