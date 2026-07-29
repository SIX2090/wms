package com.factory.wms.data.model;

import com.google.gson.annotations.SerializedName;
import kotlin.Metadata;
import kotlin.jvm.internal.DefaultConstructorMarker;
import kotlin.jvm.internal.Intrinsics;

/* compiled from: ApiModels.kt */
@Metadata(d1 = {"\u0000\"\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0000\n\u0002\u0010\u000e\n\u0002\b\n\n\u0002\u0010\u000b\n\u0002\b\u0002\n\u0002\u0010\b\n\u0002\b\u0002\b\u0087\b\u0018\u00002\u00020\u0001B\u001f\u0012\n\b\u0002\u0010\u0002\u001a\u0004\u0018\u00010\u0003\u0012\n\b\u0002\u0010\u0004\u001a\u0004\u0018\u00010\u0003¢\u0006\u0004\b\u0005\u0010\u0006J\u000b\u0010\n\u001a\u0004\u0018\u00010\u0003HÆ\u0003J\u000b\u0010\u000b\u001a\u0004\u0018\u00010\u0003HÆ\u0003J!\u0010\f\u001a\u00020\u00002\n\b\u0002\u0010\u0002\u001a\u0004\u0018\u00010\u00032\n\b\u0002\u0010\u0004\u001a\u0004\u0018\u00010\u0003HÆ\u0001J\u0013\u0010\r\u001a\u00020\u000e2\b\u0010\u000f\u001a\u0004\u0018\u00010\u0001HÖ\u0003J\t\u0010\u0010\u001a\u00020\u0011HÖ\u0001J\t\u0010\u0012\u001a\u00020\u0003HÖ\u0001R\u0018\u0010\u0002\u001a\u0004\u0018\u00010\u00038\u0006X\u0087\u0004¢\u0006\b\n\u0000\u001a\u0004\b\u0007\u0010\bR\u0018\u0010\u0004\u001a\u0004\u0018\u00010\u00038\u0006X\u0087\u0004¢\u0006\b\n\u0000\u001a\u0004\b\t\u0010\b¨\u0006\u0013"}, d2 = {"Lcom/factory/wms/data/model/SubmitResult;", "", "orderNo", "", "checkNo", "<init>", "(Ljava/lang/String;Ljava/lang/String;)V", "getOrderNo", "()Ljava/lang/String;", "getCheckNo", "component1", "component2", "copy", "equals", "", "other", "hashCode", "", "toString", "app_debug"}, k = 1, mv = {2, 0, 0}, xi = 48)
/* loaded from: classes5.dex */
public final /* data */ class SubmitResult {
    public static final int $stable = 0;

    @SerializedName("check_no")
    private final String checkNo;

    @SerializedName("order_no")
    private final String orderNo;

    /* JADX WARN: Multi-variable type inference failed */
    public SubmitResult() {
        this(null, 0 == true ? 1 : 0, 3, 0 == true ? 1 : 0);
    }

    public static /* synthetic */ SubmitResult copy$default(SubmitResult submitResult, String str, String str2, int i, Object obj) {
        if ((i & 1) != 0) {
            str = submitResult.orderNo;
        }
        if ((i & 2) != 0) {
            str2 = submitResult.checkNo;
        }
        return submitResult.copy(str, str2);
    }

    /* renamed from: component1, reason: from getter */
    public final String getOrderNo() {
        return this.orderNo;
    }

    /* renamed from: component2, reason: from getter */
    public final String getCheckNo() {
        return this.checkNo;
    }

    public final SubmitResult copy(String orderNo, String checkNo) {
        return new SubmitResult(orderNo, checkNo);
    }

    public boolean equals(Object other) {
        if (this == other) {
            return true;
        }
        if (!(other instanceof SubmitResult)) {
            return false;
        }
        SubmitResult submitResult = (SubmitResult) other;
        return Intrinsics.areEqual(this.orderNo, submitResult.orderNo) && Intrinsics.areEqual(this.checkNo, submitResult.checkNo);
    }

    public int hashCode() {
        return ((this.orderNo == null ? 0 : this.orderNo.hashCode()) * 31) + (this.checkNo != null ? this.checkNo.hashCode() : 0);
    }

    public String toString() {
        return "SubmitResult(orderNo=" + this.orderNo + ", checkNo=" + this.checkNo + ")";
    }

    public SubmitResult(String orderNo, String checkNo) {
        this.orderNo = orderNo;
        this.checkNo = checkNo;
    }

    public /* synthetic */ SubmitResult(String str, String str2, int i, DefaultConstructorMarker defaultConstructorMarker) {
        this((i & 1) != 0 ? null : str, (i & 2) != 0 ? null : str2);
    }

    public final String getOrderNo() {
        return this.orderNo;
    }

    public final String getCheckNo() {
        return this.checkNo;
    }
}
