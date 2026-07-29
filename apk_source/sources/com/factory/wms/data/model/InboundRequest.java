package com.factory.wms.data.model;

import java.util.List;
import kotlin.Metadata;
import kotlin.jvm.internal.Intrinsics;

/* compiled from: ApiModels.kt */
@Metadata(d1 = {"\u0000*\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0000\n\u0002\u0010 \n\u0002\u0018\u0002\n\u0002\b\u0007\n\u0002\u0010\u000b\n\u0002\b\u0002\n\u0002\u0010\b\n\u0000\n\u0002\u0010\u000e\n\u0000\b\u0087\b\u0018\u00002\u00020\u0001B\u0015\u0012\f\u0010\u0002\u001a\b\u0012\u0004\u0012\u00020\u00040\u0003¢\u0006\u0004\b\u0005\u0010\u0006J\u000f\u0010\t\u001a\b\u0012\u0004\u0012\u00020\u00040\u0003HÆ\u0003J\u0019\u0010\n\u001a\u00020\u00002\u000e\b\u0002\u0010\u0002\u001a\b\u0012\u0004\u0012\u00020\u00040\u0003HÆ\u0001J\u0013\u0010\u000b\u001a\u00020\f2\b\u0010\r\u001a\u0004\u0018\u00010\u0001HÖ\u0003J\t\u0010\u000e\u001a\u00020\u000fHÖ\u0001J\t\u0010\u0010\u001a\u00020\u0011HÖ\u0001R\u0017\u0010\u0002\u001a\b\u0012\u0004\u0012\u00020\u00040\u0003¢\u0006\b\n\u0000\u001a\u0004\b\u0007\u0010\b¨\u0006\u0012"}, d2 = {"Lcom/factory/wms/data/model/InboundRequest;", "", "lines", "", "Lcom/factory/wms/data/model/InboundLineDto;", "<init>", "(Ljava/util/List;)V", "getLines", "()Ljava/util/List;", "component1", "copy", "equals", "", "other", "hashCode", "", "toString", "", "app_debug"}, k = 1, mv = {2, 0, 0}, xi = 48)
/* loaded from: classes5.dex */
public final /* data */ class InboundRequest {
    public static final int $stable = 8;
    private final List<InboundLineDto> lines;

    /* JADX WARN: Multi-variable type inference failed */
    public static /* synthetic */ InboundRequest copy$default(InboundRequest inboundRequest, List list, int i, Object obj) {
        if ((i & 1) != 0) {
            list = inboundRequest.lines;
        }
        return inboundRequest.copy(list);
    }

    public final List<InboundLineDto> component1() {
        return this.lines;
    }

    public final InboundRequest copy(List<InboundLineDto> lines) {
        Intrinsics.checkNotNullParameter(lines, "lines");
        return new InboundRequest(lines);
    }

    public boolean equals(Object other) {
        if (this == other) {
            return true;
        }
        return (other instanceof InboundRequest) && Intrinsics.areEqual(this.lines, ((InboundRequest) other).lines);
    }

    public int hashCode() {
        return this.lines.hashCode();
    }

    public String toString() {
        return "InboundRequest(lines=" + this.lines + ")";
    }

    public InboundRequest(List<InboundLineDto> lines) {
        Intrinsics.checkNotNullParameter(lines, "lines");
        this.lines = lines;
    }

    public final List<InboundLineDto> getLines() {
        return this.lines;
    }
}
