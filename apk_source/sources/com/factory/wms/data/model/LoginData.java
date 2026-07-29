package com.factory.wms.data.model;

import com.factory.wms.util.Constants;
import com.google.gson.annotations.SerializedName;
import kotlin.Metadata;
import kotlin.jvm.internal.DefaultConstructorMarker;
import kotlin.jvm.internal.Intrinsics;

/* compiled from: ApiModels.kt */
@Metadata(d1 = {"\u0000.\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0000\n\u0002\u0010\u000e\n\u0000\n\u0002\u0010\t\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u000f\n\u0002\u0010\u000b\n\u0002\b\u0002\n\u0002\u0010\b\n\u0002\b\u0002\b\u0087\b\u0018\u00002\u00020\u0001B)\u0012\b\b\u0002\u0010\u0002\u001a\u00020\u0003\u0012\n\b\u0002\u0010\u0004\u001a\u0004\u0018\u00010\u0005\u0012\n\b\u0002\u0010\u0006\u001a\u0004\u0018\u00010\u0007¢\u0006\u0004\b\b\u0010\tJ\t\u0010\u0011\u001a\u00020\u0003HÆ\u0003J\u0010\u0010\u0012\u001a\u0004\u0018\u00010\u0005HÆ\u0003¢\u0006\u0002\u0010\rJ\u000b\u0010\u0013\u001a\u0004\u0018\u00010\u0007HÆ\u0003J0\u0010\u0014\u001a\u00020\u00002\b\b\u0002\u0010\u0002\u001a\u00020\u00032\n\b\u0002\u0010\u0004\u001a\u0004\u0018\u00010\u00052\n\b\u0002\u0010\u0006\u001a\u0004\u0018\u00010\u0007HÆ\u0001¢\u0006\u0002\u0010\u0015J\u0013\u0010\u0016\u001a\u00020\u00172\b\u0010\u0018\u001a\u0004\u0018\u00010\u0001HÖ\u0003J\t\u0010\u0019\u001a\u00020\u001aHÖ\u0001J\t\u0010\u001b\u001a\u00020\u0003HÖ\u0001R\u0011\u0010\u0002\u001a\u00020\u0003¢\u0006\b\n\u0000\u001a\u0004\b\n\u0010\u000bR\u001a\u0010\u0004\u001a\u0004\u0018\u00010\u00058\u0006X\u0087\u0004¢\u0006\n\n\u0002\u0010\u000e\u001a\u0004\b\f\u0010\rR\u0013\u0010\u0006\u001a\u0004\u0018\u00010\u0007¢\u0006\b\n\u0000\u001a\u0004\b\u000f\u0010\u0010¨\u0006\u001c"}, d2 = {"Lcom/factory/wms/data/model/LoginData;", "", Constants.KEY_TOKEN, "", "expiresIn", "", "user", "Lcom/factory/wms/data/model/UserProfile;", "<init>", "(Ljava/lang/String;Ljava/lang/Long;Lcom/factory/wms/data/model/UserProfile;)V", "getToken", "()Ljava/lang/String;", "getExpiresIn", "()Ljava/lang/Long;", "Ljava/lang/Long;", "getUser", "()Lcom/factory/wms/data/model/UserProfile;", "component1", "component2", "component3", "copy", "(Ljava/lang/String;Ljava/lang/Long;Lcom/factory/wms/data/model/UserProfile;)Lcom/factory/wms/data/model/LoginData;", "equals", "", "other", "hashCode", "", "toString", "app_debug"}, k = 1, mv = {2, 0, 0}, xi = 48)
/* loaded from: classes5.dex */
public final /* data */ class LoginData {
    public static final int $stable = 0;

    @SerializedName("expires_in")
    private final Long expiresIn;
    private final String token;
    private final UserProfile user;

    public LoginData() {
        this(null, null, null, 7, null);
    }

    public static /* synthetic */ LoginData copy$default(LoginData loginData, String str, Long l, UserProfile userProfile, int i, Object obj) {
        if ((i & 1) != 0) {
            str = loginData.token;
        }
        if ((i & 2) != 0) {
            l = loginData.expiresIn;
        }
        if ((i & 4) != 0) {
            userProfile = loginData.user;
        }
        return loginData.copy(str, l, userProfile);
    }

    /* renamed from: component1, reason: from getter */
    public final String getToken() {
        return this.token;
    }

    /* renamed from: component2, reason: from getter */
    public final Long getExpiresIn() {
        return this.expiresIn;
    }

    /* renamed from: component3, reason: from getter */
    public final UserProfile getUser() {
        return this.user;
    }

    public final LoginData copy(String token, Long expiresIn, UserProfile user) {
        Intrinsics.checkNotNullParameter(token, "token");
        return new LoginData(token, expiresIn, user);
    }

    public boolean equals(Object other) {
        if (this == other) {
            return true;
        }
        if (!(other instanceof LoginData)) {
            return false;
        }
        LoginData loginData = (LoginData) other;
        return Intrinsics.areEqual(this.token, loginData.token) && Intrinsics.areEqual(this.expiresIn, loginData.expiresIn) && Intrinsics.areEqual(this.user, loginData.user);
    }

    public int hashCode() {
        return (((this.token.hashCode() * 31) + (this.expiresIn == null ? 0 : this.expiresIn.hashCode())) * 31) + (this.user != null ? this.user.hashCode() : 0);
    }

    public String toString() {
        return "LoginData(token=" + this.token + ", expiresIn=" + this.expiresIn + ", user=" + this.user + ")";
    }

    public LoginData(String token, Long expiresIn, UserProfile user) {
        Intrinsics.checkNotNullParameter(token, "token");
        this.token = token;
        this.expiresIn = expiresIn;
        this.user = user;
    }

    public /* synthetic */ LoginData(String str, Long l, UserProfile userProfile, int i, DefaultConstructorMarker defaultConstructorMarker) {
        this((i & 1) != 0 ? "" : str, (i & 2) != 0 ? null : l, (i & 4) != 0 ? null : userProfile);
    }

    public final String getToken() {
        return this.token;
    }

    public final Long getExpiresIn() {
        return this.expiresIn;
    }

    public final UserProfile getUser() {
        return this.user;
    }
}
