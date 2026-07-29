package com.factory.wms.data.model;

import com.google.gson.annotations.SerializedName;
import java.util.List;
import kotlin.Metadata;
import kotlin.jvm.internal.DefaultConstructorMarker;
import kotlin.jvm.internal.Intrinsics;

/* compiled from: ApiModels.kt */
@Metadata(d1 = {"\u0000.\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0000\n\u0002\u0010\u000e\n\u0002\b\u0002\n\u0002\u0010 \n\u0002\u0018\u0002\n\u0002\b\f\n\u0002\u0010\u000b\n\u0002\b\u0002\n\u0002\u0010\b\n\u0002\b\u0002\b\u0087\b\u0018\u00002\u00020\u0001B-\u0012\n\b\u0002\u0010\u0002\u001a\u0004\u0018\u00010\u0003\u0012\n\b\u0002\u0010\u0004\u001a\u0004\u0018\u00010\u0003\u0012\f\u0010\u0005\u001a\b\u0012\u0004\u0012\u00020\u00070\u0006¢\u0006\u0004\b\b\u0010\tJ\u000b\u0010\u000f\u001a\u0004\u0018\u00010\u0003HÆ\u0003J\u000b\u0010\u0010\u001a\u0004\u0018\u00010\u0003HÆ\u0003J\u000f\u0010\u0011\u001a\b\u0012\u0004\u0012\u00020\u00070\u0006HÆ\u0003J1\u0010\u0012\u001a\u00020\u00002\n\b\u0002\u0010\u0002\u001a\u0004\u0018\u00010\u00032\n\b\u0002\u0010\u0004\u001a\u0004\u0018\u00010\u00032\u000e\b\u0002\u0010\u0005\u001a\b\u0012\u0004\u0012\u00020\u00070\u0006HÆ\u0001J\u0013\u0010\u0013\u001a\u00020\u00142\b\u0010\u0015\u001a\u0004\u0018\u00010\u0001HÖ\u0003J\t\u0010\u0016\u001a\u00020\u0017HÖ\u0001J\t\u0010\u0018\u001a\u00020\u0003HÖ\u0001R\u0018\u0010\u0002\u001a\u0004\u0018\u00010\u00038\u0006X\u0087\u0004¢\u0006\b\n\u0000\u001a\u0004\b\n\u0010\u000bR\u0018\u0010\u0004\u001a\u0004\u0018\u00010\u00038\u0006X\u0087\u0004¢\u0006\b\n\u0000\u001a\u0004\b\f\u0010\u000bR\u0017\u0010\u0005\u001a\b\u0012\u0004\u0012\u00020\u00070\u0006¢\u0006\b\n\u0000\u001a\u0004\b\r\u0010\u000e¨\u0006\u0019"}, d2 = {"Lcom/factory/wms/data/model/OutboundRequest;", "", "receiver", "", "department", "lines", "", "Lcom/factory/wms/data/model/OutboundLineDto;", "<init>", "(Ljava/lang/String;Ljava/lang/String;Ljava/util/List;)V", "getReceiver", "()Ljava/lang/String;", "getDepartment", "getLines", "()Ljava/util/List;", "component1", "component2", "component3", "copy", "equals", "", "other", "hashCode", "", "toString", "app_debug"}, k = 1, mv = {2, 0, 0}, xi = 48)
/* loaded from: classes5.dex */
public final /* data */ class OutboundRequest {
    public static final int $stable = 8;

    @SerializedName("department")
    private final String department;
    private final List<OutboundLineDto> lines;

    @SerializedName("receiver")
    private final String receiver;

    /* JADX WARN: Multi-variable type inference failed */
    public static /* synthetic */ OutboundRequest copy$default(OutboundRequest outboundRequest, String str, String str2, List list, int i, Object obj) {
        if ((i & 1) != 0) {
            str = outboundRequest.receiver;
        }
        if ((i & 2) != 0) {
            str2 = outboundRequest.department;
        }
        if ((i & 4) != 0) {
            list = outboundRequest.lines;
        }
        return outboundRequest.copy(str, str2, list);
    }

    /* renamed from: component1, reason: from getter */
    public final String getReceiver() {
        return this.receiver;
    }

    /* renamed from: component2, reason: from getter */
    public final String getDepartment() {
        return this.department;
    }

    public final List<OutboundLineDto> component3() {
        return this.lines;
    }

    public final OutboundRequest copy(String receiver, String department, List<OutboundLineDto> lines) {
        Intrinsics.checkNotNullParameter(lines, "lines");
        return new OutboundRequest(receiver, department, lines);
    }

    public boolean equals(Object other) {
        if (this == other) {
            return true;
        }
        if (!(other instanceof OutboundRequest)) {
            return false;
        }
        OutboundRequest outboundRequest = (OutboundRequest) other;
        return Intrinsics.areEqual(this.receiver, outboundRequest.receiver) && Intrinsics.areEqual(this.department, outboundRequest.department) && Intrinsics.areEqual(this.lines, outboundRequest.lines);
    }

    public int hashCode() {
        return ((((this.receiver == null ? 0 : this.receiver.hashCode()) * 31) + (this.department != null ? this.department.hashCode() : 0)) * 31) + this.lines.hashCode();
    }

    public String toString() {
        return "OutboundRequest(receiver=" + this.receiver + ", department=" + this.department + ", lines=" + this.lines + ")";
    }

    public OutboundRequest(String receiver, String department, List<OutboundLineDto> lines) {
        Intrinsics.checkNotNullParameter(lines, "lines");
        this.receiver = receiver;
        this.department = department;
        this.lines = lines;
    }

    public /* synthetic */ OutboundRequest(String str, String str2, List list, int i, DefaultConstructorMarker defaultConstructorMarker) {
        this((i & 1) != 0 ? null : str, (i & 2) != 0 ? null : str2, list);
    }

    public final String getReceiver() {
        return this.receiver;
    }

    public final String getDepartment() {
        return this.department;
    }

    public final List<OutboundLineDto> getLines() {
        return this.lines;
    }
}
