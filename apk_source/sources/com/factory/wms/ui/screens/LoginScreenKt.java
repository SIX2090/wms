package com.factory.wms.ui.screens;

import androidx.autofill.HintConstants;
import androidx.compose.runtime.Composer;
import androidx.compose.runtime.MutableState;
import androidx.compose.runtime.RecomposeScopeImplKt;
import com.factory.wms.ui.viewmodel.MainUiState;
import kotlin.Metadata;
import kotlin.Unit;
import kotlin.jvm.functions.Function3;
import kotlin.jvm.internal.Intrinsics;

/* compiled from: LoginScreen.kt */
@Metadata(d1 = {"\u0000\u001a\n\u0000\n\u0002\u0010\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\u0010\u000e\n\u0002\b\u0005\u001a5\u0010\u0000\u001a\u00020\u00012\u0006\u0010\u0002\u001a\u00020\u00032\u001e\u0010\u0004\u001a\u001a\u0012\u0004\u0012\u00020\u0006\u0012\u0004\u0012\u00020\u0006\u0012\u0004\u0012\u00020\u0006\u0012\u0004\u0012\u00020\u00010\u0005H\u0007¢\u0006\u0002\u0010\u0007¨\u0006\b²\u0006\n\u0010\t\u001a\u00020\u0006X\u008a\u008e\u0002²\u0006\n\u0010\n\u001a\u00020\u0006X\u008a\u008e\u0002²\u0006\n\u0010\u000b\u001a\u00020\u0006X\u008a\u008e\u0002"}, d2 = {"LoginScreen", "", "state", "Lcom/factory/wms/ui/viewmodel/MainUiState;", "onLogin", "Lkotlin/Function3;", "", "(Lcom/factory/wms/ui/viewmodel/MainUiState;Lkotlin/jvm/functions/Function3;Landroidx/compose/runtime/Composer;I)V", "app_debug", "username", HintConstants.AUTOFILL_HINT_PASSWORD, "baseUrl"}, k = 2, mv = {2, 0, 0}, xi = 48)
/* loaded from: classes4.dex */
public final class LoginScreenKt {
    /* JADX INFO: Access modifiers changed from: private */
    public static final Unit LoginScreen$lambda$18(MainUiState mainUiState, Function3 function3, int i, Composer composer, int i2) {
        LoginScreen(mainUiState, function3, composer, RecomposeScopeImplKt.updateChangedFlags(i | 1));
        return Unit.INSTANCE;
    }

    /* JADX WARN: Removed duplicated region for block: B:56:0x02fb  */
    /* JADX WARN: Removed duplicated region for block: B:59:0x0399  */
    /* JADX WARN: Removed duplicated region for block: B:67:0x04bf  */
    /* JADX WARN: Removed duplicated region for block: B:70:0x04d3  */
    /* JADX WARN: Removed duplicated region for block: B:75:0x053c  */
    /* JADX WARN: Removed duplicated region for block: B:77:0x04c2  */
    /* JADX WARN: Removed duplicated region for block: B:80:0x03a7  */
    /* JADX WARN: Removed duplicated region for block: B:81:0x0309  */
    /*
        Code decompiled incorrectly, please refer to instructions dump.
        To view partially-correct add '--show-bad-code' argument
    */
    public static final void LoginScreen(final com.factory.wms.ui.viewmodel.MainUiState r85, final kotlin.jvm.functions.Function3<? super java.lang.String, ? super java.lang.String, ? super java.lang.String, kotlin.Unit> r86, androidx.compose.runtime.Composer r87, final int r88) {
        /*
            Method dump skipped, instructions count: 1358
            To view this dump add '--comments-level debug' option
        */
        throw new UnsupportedOperationException("Method not decompiled: com.factory.wms.ui.screens.LoginScreenKt.LoginScreen(com.factory.wms.ui.viewmodel.MainUiState, kotlin.jvm.functions.Function3, androidx.compose.runtime.Composer, int):void");
    }

    private static final String LoginScreen$lambda$1(MutableState<String> mutableState) {
        MutableState<String> $this$getValue$iv = mutableState;
        return $this$getValue$iv.getValue();
    }

    private static final String LoginScreen$lambda$4(MutableState<String> mutableState) {
        MutableState<String> $this$getValue$iv = mutableState;
        return $this$getValue$iv.getValue();
    }

    private static final String LoginScreen$lambda$7(MutableState<String> mutableState) {
        MutableState<String> $this$getValue$iv = mutableState;
        return $this$getValue$iv.getValue();
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final Unit LoginScreen$lambda$17$lambda$10$lambda$9(MutableState $username$delegate, String it) {
        Intrinsics.checkNotNullParameter(it, "it");
        $username$delegate.setValue(it);
        return Unit.INSTANCE;
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final Unit LoginScreen$lambda$17$lambda$12$lambda$11(MutableState $password$delegate, String it) {
        Intrinsics.checkNotNullParameter(it, "it");
        $password$delegate.setValue(it);
        return Unit.INSTANCE;
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final Unit LoginScreen$lambda$17$lambda$14$lambda$13(MutableState $baseUrl$delegate, String it) {
        Intrinsics.checkNotNullParameter(it, "it");
        $baseUrl$delegate.setValue(it);
        return Unit.INSTANCE;
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final Unit LoginScreen$lambda$17$lambda$16$lambda$15(Function3 $onLogin, MutableState $username$delegate, MutableState $password$delegate, MutableState $baseUrl$delegate) {
        $onLogin.invoke(LoginScreen$lambda$1($username$delegate), LoginScreen$lambda$4($password$delegate), LoginScreen$lambda$7($baseUrl$delegate));
        return Unit.INSTANCE;
    }
}
