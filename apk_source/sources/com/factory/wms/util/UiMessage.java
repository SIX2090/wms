package com.factory.wms.util;

import kotlin.Metadata;
import kotlin.jvm.internal.DefaultConstructorMarker;
import kotlin.jvm.internal.Intrinsics;

/* compiled from: UiState.kt */
@Metadata(d1 = {"\u0000 \n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0000\n\u0002\u0010\u000e\n\u0000\n\u0002\u0010\u000b\n\u0002\b\u000b\n\u0002\u0010\b\n\u0002\b\u0002\b\u0087\b\u0018\u00002\u00020\u0001B\u001b\u0012\b\b\u0002\u0010\u0002\u001a\u00020\u0003\u0012\b\b\u0002\u0010\u0004\u001a\u00020\u0005¢\u0006\u0004\b\u0006\u0010\u0007J\t\u0010\u000b\u001a\u00020\u0003HÆ\u0003J\t\u0010\f\u001a\u00020\u0005HÆ\u0003J\u001d\u0010\r\u001a\u00020\u00002\b\b\u0002\u0010\u0002\u001a\u00020\u00032\b\b\u0002\u0010\u0004\u001a\u00020\u0005HÆ\u0001J\u0013\u0010\u000e\u001a\u00020\u00052\b\u0010\u000f\u001a\u0004\u0018\u00010\u0001HÖ\u0003J\t\u0010\u0010\u001a\u00020\u0011HÖ\u0001J\t\u0010\u0012\u001a\u00020\u0003HÖ\u0001R\u0011\u0010\u0002\u001a\u00020\u0003¢\u0006\b\n\u0000\u001a\u0004\b\b\u0010\tR\u0011\u0010\u0004\u001a\u00020\u0005¢\u0006\b\n\u0000\u001a\u0004\b\u0004\u0010\n¨\u0006\u0013"}, d2 = {"Lcom/factory/wms/util/UiMessage;", "", "text", "", "isError", "", "<init>", "(Ljava/lang/String;Z)V", "getText", "()Ljava/lang/String;", "()Z", "component1", "component2", "copy", "equals", "other", "hashCode", "", "toString", "app_debug"}, k = 1, mv = {2, 0, 0}, xi = 48)
/* loaded from: classes10.dex */
public final /* data */ class UiMessage {
    public static final int $stable = 0;
    private final boolean isError;
    private final String text;

    /* JADX WARN: Multi-variable type inference failed */
    public UiMessage() {
        this(null, false, 3, 0 == true ? 1 : 0);
    }

    public static /* synthetic */ UiMessage copy$default(UiMessage uiMessage, String str, boolean z, int i, Object obj) {
        if ((i & 1) != 0) {
            str = uiMessage.text;
        }
        if ((i & 2) != 0) {
            z = uiMessage.isError;
        }
        return uiMessage.copy(str, z);
    }

    /* renamed from: component1, reason: from getter */
    public final String getText() {
        return this.text;
    }

    /* renamed from: component2, reason: from getter */
    public final boolean getIsError() {
        return this.isError;
    }

    public final UiMessage copy(String text, boolean isError) {
        Intrinsics.checkNotNullParameter(text, "text");
        return new UiMessage(text, isError);
    }

    public boolean equals(Object other) {
        if (this == other) {
            return true;
        }
        if (!(other instanceof UiMessage)) {
            return false;
        }
        UiMessage uiMessage = (UiMessage) other;
        return Intrinsics.areEqual(this.text, uiMessage.text) && this.isError == uiMessage.isError;
    }

    public int hashCode() {
        return (this.text.hashCode() * 31) + Boolean.hashCode(this.isError);
    }

    public String toString() {
        return "UiMessage(text=" + this.text + ", isError=" + this.isError + ")";
    }

    public UiMessage(String text, boolean isError) {
        Intrinsics.checkNotNullParameter(text, "text");
        this.text = text;
        this.isError = isError;
    }

    public /* synthetic */ UiMessage(String str, boolean z, int i, DefaultConstructorMarker defaultConstructorMarker) {
        this((i & 1) != 0 ? "" : str, (i & 2) != 0 ? false : z);
    }

    public final String getText() {
        return this.text;
    }

    public final boolean isError() {
        return this.isError;
    }
}
