package com.factory.wms.data.local;

import kotlin.Metadata;
import kotlin.jvm.internal.Intrinsics;

/* compiled from: Entities.kt */
@Metadata(d1 = {"\u0000(\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0000\n\u0002\u0010\t\n\u0000\n\u0002\u0010\u000e\n\u0002\b\u0013\n\u0002\u0010\u000b\n\u0002\b\u0002\n\u0002\u0010\b\n\u0002\b\u0002\b\u0087\b\u0018\u00002\u00020\u0001B5\u0012\b\b\u0002\u0010\u0002\u001a\u00020\u0003\u0012\u0006\u0010\u0004\u001a\u00020\u0005\u0012\u0006\u0010\u0006\u001a\u00020\u0005\u0012\u0006\u0010\u0007\u001a\u00020\u0003\u0012\n\b\u0002\u0010\b\u001a\u0004\u0018\u00010\u0005¢\u0006\u0004\b\t\u0010\nJ\t\u0010\u0012\u001a\u00020\u0003HÆ\u0003J\t\u0010\u0013\u001a\u00020\u0005HÆ\u0003J\t\u0010\u0014\u001a\u00020\u0005HÆ\u0003J\t\u0010\u0015\u001a\u00020\u0003HÆ\u0003J\u000b\u0010\u0016\u001a\u0004\u0018\u00010\u0005HÆ\u0003J=\u0010\u0017\u001a\u00020\u00002\b\b\u0002\u0010\u0002\u001a\u00020\u00032\b\b\u0002\u0010\u0004\u001a\u00020\u00052\b\b\u0002\u0010\u0006\u001a\u00020\u00052\b\b\u0002\u0010\u0007\u001a\u00020\u00032\n\b\u0002\u0010\b\u001a\u0004\u0018\u00010\u0005HÆ\u0001J\u0013\u0010\u0018\u001a\u00020\u00192\b\u0010\u001a\u001a\u0004\u0018\u00010\u0001HÖ\u0003J\t\u0010\u001b\u001a\u00020\u001cHÖ\u0001J\t\u0010\u001d\u001a\u00020\u0005HÖ\u0001R\u0016\u0010\u0002\u001a\u00020\u00038\u0006X\u0087\u0004¢\u0006\b\n\u0000\u001a\u0004\b\u000b\u0010\fR\u0011\u0010\u0004\u001a\u00020\u0005¢\u0006\b\n\u0000\u001a\u0004\b\r\u0010\u000eR\u0011\u0010\u0006\u001a\u00020\u0005¢\u0006\b\n\u0000\u001a\u0004\b\u000f\u0010\u000eR\u0011\u0010\u0007\u001a\u00020\u0003¢\u0006\b\n\u0000\u001a\u0004\b\u0010\u0010\fR\u0013\u0010\b\u001a\u0004\u0018\u00010\u0005¢\u0006\b\n\u0000\u001a\u0004\b\u0011\u0010\u000e¨\u0006\u001e"}, d2 = {"Lcom/factory/wms/data/local/PendingDocumentEntity;", "", "id", "", "type", "", "payloadJson", "createdAt", "lastError", "<init>", "(JLjava/lang/String;Ljava/lang/String;JLjava/lang/String;)V", "getId", "()J", "getType", "()Ljava/lang/String;", "getPayloadJson", "getCreatedAt", "getLastError", "component1", "component2", "component3", "component4", "component5", "copy", "equals", "", "other", "hashCode", "", "toString", "app_debug"}, k = 1, mv = {2, 0, 0}, xi = 48)
/* loaded from: classes8.dex */
public final /* data */ class PendingDocumentEntity {
    public static final int $stable = 0;
    private final long createdAt;
    private final long id;
    private final String lastError;
    private final String payloadJson;
    private final String type;

    /* renamed from: component1, reason: from getter */
    public final long getId() {
        return this.id;
    }

    /* renamed from: component2, reason: from getter */
    public final String getType() {
        return this.type;
    }

    /* renamed from: component3, reason: from getter */
    public final String getPayloadJson() {
        return this.payloadJson;
    }

    /* renamed from: component4, reason: from getter */
    public final long getCreatedAt() {
        return this.createdAt;
    }

    /* renamed from: component5, reason: from getter */
    public final String getLastError() {
        return this.lastError;
    }

    public final PendingDocumentEntity copy(long id, String type, String payloadJson, long createdAt, String lastError) {
        Intrinsics.checkNotNullParameter(type, "type");
        Intrinsics.checkNotNullParameter(payloadJson, "payloadJson");
        return new PendingDocumentEntity(id, type, payloadJson, createdAt, lastError);
    }

    public boolean equals(Object other) {
        if (this == other) {
            return true;
        }
        if (!(other instanceof PendingDocumentEntity)) {
            return false;
        }
        PendingDocumentEntity pendingDocumentEntity = (PendingDocumentEntity) other;
        return this.id == pendingDocumentEntity.id && Intrinsics.areEqual(this.type, pendingDocumentEntity.type) && Intrinsics.areEqual(this.payloadJson, pendingDocumentEntity.payloadJson) && this.createdAt == pendingDocumentEntity.createdAt && Intrinsics.areEqual(this.lastError, pendingDocumentEntity.lastError);
    }

    public int hashCode() {
        return (((((((Long.hashCode(this.id) * 31) + this.type.hashCode()) * 31) + this.payloadJson.hashCode()) * 31) + Long.hashCode(this.createdAt)) * 31) + (this.lastError == null ? 0 : this.lastError.hashCode());
    }

    public String toString() {
        return "PendingDocumentEntity(id=" + this.id + ", type=" + this.type + ", payloadJson=" + this.payloadJson + ", createdAt=" + this.createdAt + ", lastError=" + this.lastError + ")";
    }

    public PendingDocumentEntity(long id, String type, String payloadJson, long createdAt, String lastError) {
        Intrinsics.checkNotNullParameter(type, "type");
        Intrinsics.checkNotNullParameter(payloadJson, "payloadJson");
        this.id = id;
        this.type = type;
        this.payloadJson = payloadJson;
        this.createdAt = createdAt;
        this.lastError = lastError;
    }

    /* JADX WARN: Illegal instructions before constructor call */
    /*
        Code decompiled incorrectly, please refer to instructions dump.
        To view partially-correct add '--show-bad-code' argument
    */
    public /* synthetic */ PendingDocumentEntity(long r11, java.lang.String r13, java.lang.String r14, long r15, java.lang.String r17, int r18, kotlin.jvm.internal.DefaultConstructorMarker r19) {
        /*
            r10 = this;
            r0 = r18 & 1
            if (r0 == 0) goto L8
            r0 = 0
            r3 = r0
            goto L9
        L8:
            r3 = r11
        L9:
            r0 = r18 & 16
            if (r0 == 0) goto L10
            r0 = 0
            r9 = r0
            goto L12
        L10:
            r9 = r17
        L12:
            r2 = r10
            r5 = r13
            r6 = r14
            r7 = r15
            r2.<init>(r3, r5, r6, r7, r9)
            return
        */
        throw new UnsupportedOperationException("Method not decompiled: com.factory.wms.data.local.PendingDocumentEntity.<init>(long, java.lang.String, java.lang.String, long, java.lang.String, int, kotlin.jvm.internal.DefaultConstructorMarker):void");
    }

    public final long getId() {
        return this.id;
    }

    public final String getType() {
        return this.type;
    }

    public final String getPayloadJson() {
        return this.payloadJson;
    }

    public final long getCreatedAt() {
        return this.createdAt;
    }

    public final String getLastError() {
        return this.lastError;
    }
}
