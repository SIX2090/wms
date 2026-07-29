package com.factory.wms.ui.viewmodel;

import com.factory.wms.data.model.MaterialDto;
import kotlin.Metadata;
import kotlin.jvm.internal.DefaultConstructorMarker;
import kotlin.jvm.internal.Intrinsics;

/* compiled from: MainViewModel.kt */
@Metadata(d1 = {"\u0000.\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010\u0006\n\u0000\n\u0002\u0010\u000e\n\u0002\b\u0004\n\u0002\u0010\b\n\u0002\b\u0016\n\u0002\u0010\u000b\n\u0002\b\u0004\b\u0087\b\u0018\u00002\u00020\u0001BK\u0012\u0006\u0010\u0002\u001a\u00020\u0003\u0012\b\b\u0002\u0010\u0004\u001a\u00020\u0005\u0012\b\b\u0002\u0010\u0006\u001a\u00020\u0007\u0012\b\b\u0002\u0010\b\u001a\u00020\u0007\u0012\b\b\u0002\u0010\t\u001a\u00020\u0007\u0012\b\b\u0002\u0010\n\u001a\u00020\u0005\u0012\b\b\u0002\u0010\u000b\u001a\u00020\f¢\u0006\u0004\b\r\u0010\u000eJ\t\u0010\u001a\u001a\u00020\u0003HÆ\u0003J\t\u0010\u001b\u001a\u00020\u0005HÆ\u0003J\t\u0010\u001c\u001a\u00020\u0007HÆ\u0003J\t\u0010\u001d\u001a\u00020\u0007HÆ\u0003J\t\u0010\u001e\u001a\u00020\u0007HÆ\u0003J\t\u0010\u001f\u001a\u00020\u0005HÆ\u0003J\t\u0010 \u001a\u00020\fHÆ\u0003JO\u0010!\u001a\u00020\u00002\b\b\u0002\u0010\u0002\u001a\u00020\u00032\b\b\u0002\u0010\u0004\u001a\u00020\u00052\b\b\u0002\u0010\u0006\u001a\u00020\u00072\b\b\u0002\u0010\b\u001a\u00020\u00072\b\b\u0002\u0010\t\u001a\u00020\u00072\b\b\u0002\u0010\n\u001a\u00020\u00052\b\b\u0002\u0010\u000b\u001a\u00020\fHÆ\u0001J\u0013\u0010\"\u001a\u00020#2\b\u0010$\u001a\u0004\u0018\u00010\u0001HÖ\u0003J\t\u0010%\u001a\u00020\fHÖ\u0001J\t\u0010&\u001a\u00020\u0007HÖ\u0001R\u0011\u0010\u0002\u001a\u00020\u0003¢\u0006\b\n\u0000\u001a\u0004\b\u000f\u0010\u0010R\u0011\u0010\u0004\u001a\u00020\u0005¢\u0006\b\n\u0000\u001a\u0004\b\u0011\u0010\u0012R\u0011\u0010\u0006\u001a\u00020\u0007¢\u0006\b\n\u0000\u001a\u0004\b\u0013\u0010\u0014R\u0011\u0010\b\u001a\u00020\u0007¢\u0006\b\n\u0000\u001a\u0004\b\u0015\u0010\u0014R\u0011\u0010\t\u001a\u00020\u0007¢\u0006\b\n\u0000\u001a\u0004\b\u0016\u0010\u0014R\u0011\u0010\n\u001a\u00020\u0005¢\u0006\b\n\u0000\u001a\u0004\b\u0017\u0010\u0012R\u0011\u0010\u000b\u001a\u00020\f¢\u0006\b\n\u0000\u001a\u0004\b\u0018\u0010\u0019¨\u0006'"}, d2 = {"Lcom/factory/wms/ui/viewmodel/ScanLine;", "", "material", "Lcom/factory/wms/data/model/MaterialDto;", "quantity", "", "batchNo", "", "receiver", "department", "actualStock", "scannedTimes", "", "<init>", "(Lcom/factory/wms/data/model/MaterialDto;DLjava/lang/String;Ljava/lang/String;Ljava/lang/String;DI)V", "getMaterial", "()Lcom/factory/wms/data/model/MaterialDto;", "getQuantity", "()D", "getBatchNo", "()Ljava/lang/String;", "getReceiver", "getDepartment", "getActualStock", "getScannedTimes", "()I", "component1", "component2", "component3", "component4", "component5", "component6", "component7", "copy", "equals", "", "other", "hashCode", "toString", "app_debug"}, k = 1, mv = {2, 0, 0}, xi = 48)
/* loaded from: classes10.dex */
public final /* data */ class ScanLine {
    public static final int $stable = 0;
    private final double actualStock;
    private final String batchNo;
    private final String department;
    private final MaterialDto material;
    private final double quantity;
    private final String receiver;
    private final int scannedTimes;

    /* renamed from: component1, reason: from getter */
    public final MaterialDto getMaterial() {
        return this.material;
    }

    /* renamed from: component2, reason: from getter */
    public final double getQuantity() {
        return this.quantity;
    }

    /* renamed from: component3, reason: from getter */
    public final String getBatchNo() {
        return this.batchNo;
    }

    /* renamed from: component4, reason: from getter */
    public final String getReceiver() {
        return this.receiver;
    }

    /* renamed from: component5, reason: from getter */
    public final String getDepartment() {
        return this.department;
    }

    /* renamed from: component6, reason: from getter */
    public final double getActualStock() {
        return this.actualStock;
    }

    /* renamed from: component7, reason: from getter */
    public final int getScannedTimes() {
        return this.scannedTimes;
    }

    public final ScanLine copy(MaterialDto material, double quantity, String batchNo, String receiver, String department, double actualStock, int scannedTimes) {
        Intrinsics.checkNotNullParameter(material, "material");
        Intrinsics.checkNotNullParameter(batchNo, "batchNo");
        Intrinsics.checkNotNullParameter(receiver, "receiver");
        Intrinsics.checkNotNullParameter(department, "department");
        return new ScanLine(material, quantity, batchNo, receiver, department, actualStock, scannedTimes);
    }

    public boolean equals(Object other) {
        if (this == other) {
            return true;
        }
        if (!(other instanceof ScanLine)) {
            return false;
        }
        ScanLine scanLine = (ScanLine) other;
        return Intrinsics.areEqual(this.material, scanLine.material) && Double.compare(this.quantity, scanLine.quantity) == 0 && Intrinsics.areEqual(this.batchNo, scanLine.batchNo) && Intrinsics.areEqual(this.receiver, scanLine.receiver) && Intrinsics.areEqual(this.department, scanLine.department) && Double.compare(this.actualStock, scanLine.actualStock) == 0 && this.scannedTimes == scanLine.scannedTimes;
    }

    public int hashCode() {
        return (((((((((((this.material.hashCode() * 31) + Double.hashCode(this.quantity)) * 31) + this.batchNo.hashCode()) * 31) + this.receiver.hashCode()) * 31) + this.department.hashCode()) * 31) + Double.hashCode(this.actualStock)) * 31) + Integer.hashCode(this.scannedTimes);
    }

    public String toString() {
        return "ScanLine(material=" + this.material + ", quantity=" + this.quantity + ", batchNo=" + this.batchNo + ", receiver=" + this.receiver + ", department=" + this.department + ", actualStock=" + this.actualStock + ", scannedTimes=" + this.scannedTimes + ")";
    }

    public ScanLine(MaterialDto material, double quantity, String batchNo, String receiver, String department, double actualStock, int scannedTimes) {
        Intrinsics.checkNotNullParameter(material, "material");
        Intrinsics.checkNotNullParameter(batchNo, "batchNo");
        Intrinsics.checkNotNullParameter(receiver, "receiver");
        Intrinsics.checkNotNullParameter(department, "department");
        this.material = material;
        this.quantity = quantity;
        this.batchNo = batchNo;
        this.receiver = receiver;
        this.department = department;
        this.actualStock = actualStock;
        this.scannedTimes = scannedTimes;
    }

    public /* synthetic */ ScanLine(MaterialDto materialDto, double d, String str, String str2, String str3, double d2, int i, int i2, DefaultConstructorMarker defaultConstructorMarker) {
        this(materialDto, (i2 & 2) != 0 ? 1.0d : d, (i2 & 4) != 0 ? "" : str, (i2 & 8) != 0 ? "" : str2, (i2 & 16) == 0 ? str3 : "", (i2 & 32) != 0 ? materialDto.getStock() : d2, (i2 & 64) != 0 ? 1 : i);
    }

    public final MaterialDto getMaterial() {
        return this.material;
    }

    public final double getQuantity() {
        return this.quantity;
    }

    public final String getBatchNo() {
        return this.batchNo;
    }

    public final String getReceiver() {
        return this.receiver;
    }

    public final String getDepartment() {
        return this.department;
    }

    public final double getActualStock() {
        return this.actualStock;
    }

    public final int getScannedTimes() {
        return this.scannedTimes;
    }
}
