package com.factory.wms.data.repository;

import android.content.Context;
import android.content.SharedPreferences;
import com.factory.wms.data.model.UserProfile;
import com.factory.wms.util.Constants;
import kotlin.Metadata;
import kotlin.jvm.internal.Intrinsics;
import kotlin.text.StringsKt;

/* compiled from: AuthStore.kt */
@Metadata(d1 = {"\u0000:\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0010\u000e\n\u0002\b\u0003\n\u0002\u0010\u0002\n\u0002\b\u0004\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0010\u000b\n\u0002\b\u0003\b\u0007\u0018\u00002\u00020\u0001B\u000f\u0012\u0006\u0010\u0002\u001a\u00020\u0003¢\u0006\u0004\b\u0004\u0010\u0005J\u0006\u0010\n\u001a\u00020\u000bJ\u0006\u0010\f\u001a\u00020\u000bJ\u0006\u0010\r\u001a\u00020\u000bJ\u000e\u0010\u000e\u001a\u00020\u000f2\u0006\u0010\u0010\u001a\u00020\u000bJ \u0010\u0011\u001a\u00020\u000f2\u0006\u0010\u0012\u001a\u00020\u000b2\b\u0010\u0013\u001a\u0004\u0018\u00010\u00142\u0006\u0010\u0015\u001a\u00020\u000bJ\u0006\u0010\u0016\u001a\u00020\u000fJ\u0006\u0010\u0017\u001a\u00020\u0018J\u0010\u0010\u0019\u001a\u00020\u000b2\u0006\u0010\u001a\u001a\u00020\u000bH\u0002R\u0018\u0010\u0006\u001a\n \b*\u0004\u0018\u00010\u00070\u0007X\u0082\u0004¢\u0006\u0004\n\u0002\u0010\t¨\u0006\u001b"}, d2 = {"Lcom/factory/wms/data/repository/AuthStore;", "", "context", "Landroid/content/Context;", "<init>", "(Landroid/content/Context;)V", "prefs", "Landroid/content/SharedPreferences;", "kotlin.jvm.PlatformType", "Landroid/content/SharedPreferences;", "getToken", "", "getUsername", "getBaseUrl", "saveBaseUrl", "", "url", "saveSession", Constants.KEY_TOKEN, "user", "Lcom/factory/wms/data/model/UserProfile;", "fallbackUsername", "clear", "isLoggedIn", "", "normalizeBaseUrl", "raw", "app_debug"}, k = 1, mv = {2, 0, 0}, xi = 48)
/* loaded from: classes6.dex */
public final class AuthStore {
    public static final int $stable = 8;
    private final SharedPreferences prefs;

    public AuthStore(Context context) {
        Intrinsics.checkNotNullParameter(context, "context");
        this.prefs = context.getSharedPreferences(Constants.AUTH_PREFS, 0);
    }

    public final String getToken() {
        String string = this.prefs.getString(Constants.KEY_TOKEN, "");
        return string == null ? "" : string;
    }

    public final String getUsername() {
        String string = this.prefs.getString("username", "");
        return string == null ? "" : string;
    }

    public final String getBaseUrl() {
        String saved = this.prefs.getString(Constants.KEY_BASE_URL, null);
        return normalizeBaseUrl(saved == null ? Constants.DEFAULT_BASE_URL : saved);
    }

    public final void saveBaseUrl(String url) {
        Intrinsics.checkNotNullParameter(url, "url");
        this.prefs.edit().putString(Constants.KEY_BASE_URL, normalizeBaseUrl(url)).apply();
    }

    public final void saveSession(String token, UserProfile user, String fallbackUsername) {
        String str;
        String username;
        Intrinsics.checkNotNullParameter(token, "token");
        Intrinsics.checkNotNullParameter(fallbackUsername, "fallbackUsername");
        SharedPreferences.Editor putString = this.prefs.edit().putString(Constants.KEY_TOKEN, token);
        if (user == null || (username = user.getUsername()) == null) {
            str = fallbackUsername;
        } else {
            String str2 = username;
            if (StringsKt.isBlank(str2)) {
                str2 = fallbackUsername;
            }
            str = str2;
        }
        putString.putString("username", str).apply();
    }

    public final void clear() {
        this.prefs.edit().remove(Constants.KEY_TOKEN).remove("username").apply();
    }

    public final boolean isLoggedIn() {
        return !StringsKt.isBlank(getToken());
    }

    private final String normalizeBaseUrl(String raw) {
        String value = StringsKt.trim((CharSequence) raw).toString();
        if (StringsKt.isBlank(value)) {
            value = Constants.DEFAULT_BASE_URL;
        }
        if (!StringsKt.startsWith$default(value, "http://", false, 2, (Object) null) && !StringsKt.startsWith$default(value, "https://", false, 2, (Object) null)) {
            value = "http://" + value;
        }
        if (!StringsKt.endsWith$default(value, "/", false, 2, (Object) null)) {
            return value + "/";
        }
        return value;
    }
}
