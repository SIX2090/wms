package com.factory.wms.data.model;

import androidx.core.app.NotificationCompat;
import com.google.gson.annotations.SerializedName;
import kotlin.Metadata;
import kotlin.jvm.internal.DefaultConstructorMarker;
import kotlin.jvm.internal.Intrinsics;
import kotlin.text.StringsKt;

/* compiled from: ApiModels.kt */
@Metadata(d1 = {"\u0000\"\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010\u0000\n\u0000\n\u0002\u0010\u000b\n\u0000\n\u0002\u0010\u000e\n\u0002\b\u001d\n\u0002\u0010\b\n\u0002\b\u0002\b\u0087\b\u0018\u0000*\u0004\b\u0000\u0010\u00012\u00020\u0002BC\u0012\n\b\u0002\u0010\u0003\u001a\u0004\u0018\u00010\u0004\u0012\n\b\u0002\u0010\u0005\u001a\u0004\u0018\u00010\u0006\u0012\n\b\u0002\u0010\u0007\u001a\u0004\u0018\u00010\u0006\u0012\n\b\u0002\u0010\b\u001a\u0004\u0018\u00010\u0006\u0012\n\b\u0002\u0010\t\u001a\u0004\u0018\u00018\u0000¢\u0006\u0004\b\n\u0010\u000bJ\u0010\u0010\u001a\u001a\u0004\u0018\u00010\u0004HÆ\u0003¢\u0006\u0002\u0010\rJ\u000b\u0010\u001b\u001a\u0004\u0018\u00010\u0006HÆ\u0003J\u000b\u0010\u001c\u001a\u0004\u0018\u00010\u0006HÆ\u0003J\u000b\u0010\u001d\u001a\u0004\u0018\u00010\u0006HÆ\u0003J\u0010\u0010\u001e\u001a\u0004\u0018\u00018\u0000HÆ\u0003¢\u0006\u0002\u0010\u0014JP\u0010\u001f\u001a\b\u0012\u0004\u0012\u00028\u00000\u00002\n\b\u0002\u0010\u0003\u001a\u0004\u0018\u00010\u00042\n\b\u0002\u0010\u0005\u001a\u0004\u0018\u00010\u00062\n\b\u0002\u0010\u0007\u001a\u0004\u0018\u00010\u00062\n\b\u0002\u0010\b\u001a\u0004\u0018\u00010\u00062\n\b\u0002\u0010\t\u001a\u0004\u0018\u00018\u0000HÆ\u0001¢\u0006\u0002\u0010 J\u0013\u0010!\u001a\u00020\u00042\b\u0010\"\u001a\u0004\u0018\u00010\u0002HÖ\u0003J\t\u0010#\u001a\u00020$HÖ\u0001J\t\u0010%\u001a\u00020\u0006HÖ\u0001R\u001a\u0010\u0003\u001a\u0004\u0018\u00010\u00048\u0006X\u0087\u0004¢\u0006\n\n\u0002\u0010\u000e\u001a\u0004\b\f\u0010\rR\u0018\u0010\u0005\u001a\u0004\u0018\u00010\u00068\u0006X\u0087\u0004¢\u0006\b\n\u0000\u001a\u0004\b\u000f\u0010\u0010R\u0018\u0010\u0007\u001a\u0004\u0018\u00010\u00068\u0006X\u0087\u0004¢\u0006\b\n\u0000\u001a\u0004\b\u0011\u0010\u0010R\u0018\u0010\b\u001a\u0004\u0018\u00010\u00068\u0006X\u0087\u0004¢\u0006\b\n\u0000\u001a\u0004\b\u0012\u0010\u0010R\u001a\u0010\t\u001a\u0004\u0018\u00018\u00008\u0006X\u0087\u0004¢\u0006\n\n\u0002\u0010\u0015\u001a\u0004\b\u0013\u0010\u0014R\u0011\u0010\u0016\u001a\u00020\u00048F¢\u0006\u0006\u001a\u0004\b\u0016\u0010\u0017R\u0011\u0010\u0018\u001a\u00020\u00068F¢\u0006\u0006\u001a\u0004\b\u0019\u0010\u0010¨\u0006&"}, d2 = {"Lcom/factory/wms/data/model/ApiEnvelope;", "T", "", "success", "", NotificationCompat.CATEGORY_STATUS, "", "message", NotificationCompat.CATEGORY_MESSAGE, "data", "<init>", "(Ljava/lang/Boolean;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;Ljava/lang/Object;)V", "getSuccess", "()Ljava/lang/Boolean;", "Ljava/lang/Boolean;", "getStatus", "()Ljava/lang/String;", "getMessage", "getMsg", "getData", "()Ljava/lang/Object;", "Ljava/lang/Object;", "isOk", "()Z", "displayMessage", "getDisplayMessage", "component1", "component2", "component3", "component4", "component5", "copy", "(Ljava/lang/Boolean;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;Ljava/lang/Object;)Lcom/factory/wms/data/model/ApiEnvelope;", "equals", "other", "hashCode", "", "toString", "app_debug"}, k = 1, mv = {2, 0, 0}, xi = 48)
/* loaded from: classes5.dex */
public final /* data */ class ApiEnvelope<T> {
    public static final int $stable = 0;

    @SerializedName("data")
    private final T data;

    @SerializedName("message")
    private final String message;

    @SerializedName(NotificationCompat.CATEGORY_MESSAGE)
    private final String msg;

    @SerializedName(NotificationCompat.CATEGORY_STATUS)
    private final String status;

    @SerializedName("success")
    private final Boolean success;

    public ApiEnvelope() {
        this(null, null, null, null, null, 31, null);
    }

    /* JADX WARN: Multi-variable type inference failed */
    public static /* synthetic */ ApiEnvelope copy$default(ApiEnvelope apiEnvelope, Boolean bool, String str, String str2, String str3, Object obj, int i, Object obj2) {
        if ((i & 1) != 0) {
            bool = apiEnvelope.success;
        }
        if ((i & 2) != 0) {
            str = apiEnvelope.status;
        }
        String str4 = str;
        if ((i & 4) != 0) {
            str2 = apiEnvelope.message;
        }
        String str5 = str2;
        if ((i & 8) != 0) {
            str3 = apiEnvelope.msg;
        }
        String str6 = str3;
        T t = obj;
        if ((i & 16) != 0) {
            t = apiEnvelope.data;
        }
        return apiEnvelope.copy(bool, str4, str5, str6, t);
    }

    /* renamed from: component1, reason: from getter */
    public final Boolean getSuccess() {
        return this.success;
    }

    /* renamed from: component2, reason: from getter */
    public final String getStatus() {
        return this.status;
    }

    /* renamed from: component3, reason: from getter */
    public final String getMessage() {
        return this.message;
    }

    /* renamed from: component4, reason: from getter */
    public final String getMsg() {
        return this.msg;
    }

    public final T component5() {
        return this.data;
    }

    public final ApiEnvelope<T> copy(Boolean success, String status, String message, String msg, T data) {
        return new ApiEnvelope<>(success, status, message, msg, data);
    }

    public boolean equals(Object other) {
        if (this == other) {
            return true;
        }
        if (!(other instanceof ApiEnvelope)) {
            return false;
        }
        ApiEnvelope apiEnvelope = (ApiEnvelope) other;
        return Intrinsics.areEqual(this.success, apiEnvelope.success) && Intrinsics.areEqual(this.status, apiEnvelope.status) && Intrinsics.areEqual(this.message, apiEnvelope.message) && Intrinsics.areEqual(this.msg, apiEnvelope.msg) && Intrinsics.areEqual(this.data, apiEnvelope.data);
    }

    public int hashCode() {
        return ((((((((this.success == null ? 0 : this.success.hashCode()) * 31) + (this.status == null ? 0 : this.status.hashCode())) * 31) + (this.message == null ? 0 : this.message.hashCode())) * 31) + (this.msg == null ? 0 : this.msg.hashCode())) * 31) + (this.data != null ? this.data.hashCode() : 0);
    }

    public String toString() {
        return "ApiEnvelope(success=" + this.success + ", status=" + this.status + ", message=" + this.message + ", msg=" + this.msg + ", data=" + this.data + ")";
    }

    public ApiEnvelope(Boolean success, String status, String message, String msg, T t) {
        this.success = success;
        this.status = status;
        this.message = message;
        this.msg = msg;
        this.data = t;
    }

    public /* synthetic */ ApiEnvelope(Boolean bool, String str, String str2, String str3, Object obj, int i, DefaultConstructorMarker defaultConstructorMarker) {
        this((i & 1) != 0 ? null : bool, (i & 2) != 0 ? null : str, (i & 4) != 0 ? null : str2, (i & 8) != 0 ? null : str3, (i & 16) != 0 ? null : obj);
    }

    public final Boolean getSuccess() {
        return this.success;
    }

    public final String getStatus() {
        return this.status;
    }

    public final String getMessage() {
        return this.message;
    }

    public final String getMsg() {
        return this.msg;
    }

    public final T getData() {
        return this.data;
    }

    public final boolean isOk() {
        return Intrinsics.areEqual((Object) this.success, (Object) true) || StringsKt.equals(this.status, "success", true);
    }

    public final String getDisplayMessage() {
        String str = this.message;
        if (str != null) {
            return str;
        }
        String str2 = this.msg;
        return str2 == null ? isOk() ? "操作成功" : "操作失败" : str2;
    }
}
