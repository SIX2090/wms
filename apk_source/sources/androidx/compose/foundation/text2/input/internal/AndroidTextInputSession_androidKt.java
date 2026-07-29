package androidx.compose.foundation.text2.input.internal;

import android.view.inputmethod.EditorInfo;
import androidx.compose.foundation.text2.input.TextFieldCharSequence;
import androidx.compose.ui.text.TextRange;
import androidx.compose.ui.text.input.ImeAction;
import androidx.compose.ui.text.input.ImeOptions;
import androidx.compose.ui.text.input.KeyboardCapitalization;
import androidx.compose.ui.text.input.KeyboardType;
import androidx.core.view.InputDeviceCompat;
import androidx.core.view.inputmethod.EditorInfoCompat;
import kotlin.Metadata;
import kotlin.jvm.functions.Function0;

/* compiled from: AndroidTextInputSession.android.kt */
@Metadata(d1 = {"\u0000T\n\u0000\n\u0002\u0010\u000e\n\u0000\n\u0002\u0010\u000b\n\u0002\b\u0004\n\u0002\u0010\b\n\u0002\b\u0002\n\u0002\u0010\u0002\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010\u0001\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\u001a\u0018\u0010\u0006\u001a\u00020\u00032\u0006\u0010\u0007\u001a\u00020\b2\u0006\u0010\t\u001a\u00020\bH\u0002\u001a \u0010\n\u001a\u00020\u000b2\b\b\u0002\u0010\f\u001a\u00020\u00012\f\u0010\r\u001a\b\u0012\u0004\u0012\u00020\u00010\u000eH\u0002\u001a8\u0010\u000f\u001a\u00020\u0010*\u00020\u00112\u0006\u0010\u0012\u001a\u00020\u00132\u0006\u0010\u0014\u001a\u00020\u00152\u0014\u0010\u0016\u001a\u0010\u0012\u0004\u0012\u00020\u0018\u0012\u0004\u0012\u00020\u000b\u0018\u00010\u0017H\u0080@¢\u0006\u0002\u0010\u0019\u001a\u001c\u0010\u001a\u001a\u00020\u000b*\u00020\u001b2\u0006\u0010\u001c\u001a\u00020\u001d2\u0006\u0010\u0014\u001a\u00020\u0015H\u0000\"\u000e\u0010\u0000\u001a\u00020\u0001X\u0082T¢\u0006\u0002\n\u0000\"\u0016\u0010\u0002\u001a\u00020\u00038\u0000X\u0081T¢\u0006\b\n\u0000\u0012\u0004\b\u0004\u0010\u0005¨\u0006\u001e"}, d2 = {"TAG", "", "TIA_DEBUG", "", "getTIA_DEBUG$annotations", "()V", "hasFlag", "bits", "", "flag", "logDebug", "", "tag", "content", "Lkotlin/Function0;", "platformSpecificTextInputSession", "", "Landroidx/compose/ui/platform/PlatformTextInputSession;", "state", "Landroidx/compose/foundation/text2/input/internal/TransformedTextFieldState;", "imeOptions", "Landroidx/compose/ui/text/input/ImeOptions;", "onImeAction", "Lkotlin/Function1;", "Landroidx/compose/ui/text/input/ImeAction;", "(Landroidx/compose/ui/platform/PlatformTextInputSession;Landroidx/compose/foundation/text2/input/internal/TransformedTextFieldState;Landroidx/compose/ui/text/input/ImeOptions;Lkotlin/jvm/functions/Function1;Lkotlin/coroutines/Continuation;)Ljava/lang/Object;", "update", "Landroid/view/inputmethod/EditorInfo;", "textFieldValue", "Landroidx/compose/foundation/text2/input/TextFieldCharSequence;", "foundation_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class AndroidTextInputSession_androidKt {
    private static final String TAG = "AndroidTextInputSession";
    public static final boolean TIA_DEBUG = false;

    public static /* synthetic */ void getTIA_DEBUG$annotations() {
    }

    /* JADX WARN: Removed duplicated region for block: B:11:0x002e  */
    /* JADX WARN: Removed duplicated region for block: B:14:0x0032  */
    /* JADX WARN: Removed duplicated region for block: B:8:0x0025  */
    /*
        Code decompiled incorrectly, please refer to instructions dump.
        To view partially-correct add '--show-bad-code' argument
    */
    public static final java.lang.Object platformSpecificTextInputSession(androidx.compose.ui.platform.PlatformTextInputSession r9, androidx.compose.foundation.text2.input.internal.TransformedTextFieldState r10, androidx.compose.ui.text.input.ImeOptions r11, kotlin.jvm.functions.Function1<? super androidx.compose.ui.text.input.ImeAction, kotlin.Unit> r12, kotlin.coroutines.Continuation<?> r13) {
        /*
            boolean r0 = r13 instanceof androidx.compose.foundation.text2.input.internal.AndroidTextInputSession_androidKt$platformSpecificTextInputSession$1
            if (r0 == 0) goto L14
            r0 = r13
            androidx.compose.foundation.text2.input.internal.AndroidTextInputSession_androidKt$platformSpecificTextInputSession$1 r0 = (androidx.compose.foundation.text2.input.internal.AndroidTextInputSession_androidKt$platformSpecificTextInputSession$1) r0
            int r1 = r0.label
            r2 = -2147483648(0xffffffff80000000, float:-0.0)
            r1 = r1 & r2
            if (r1 == 0) goto L14
            int r13 = r0.label
            int r13 = r13 - r2
            r0.label = r13
            goto L19
        L14:
            androidx.compose.foundation.text2.input.internal.AndroidTextInputSession_androidKt$platformSpecificTextInputSession$1 r0 = new androidx.compose.foundation.text2.input.internal.AndroidTextInputSession_androidKt$platformSpecificTextInputSession$1
            r0.<init>(r13)
        L19:
            r13 = r0
            java.lang.Object r0 = r13.result
            java.lang.Object r1 = kotlin.coroutines.intrinsics.IntrinsicsKt.getCOROUTINE_SUSPENDED()
            int r2 = r13.label
            switch(r2) {
                case 0: goto L32;
                case 1: goto L2e;
                default: goto L25;
            }
        L25:
            java.lang.IllegalStateException r9 = new java.lang.IllegalStateException
            java.lang.String r10 = "call to 'resume' before 'invoke' with coroutine"
            r9.<init>(r10)
            throw r9
        L2e:
            kotlin.ResultKt.throwOnFailure(r0)
            goto L55
        L32:
            kotlin.ResultKt.throwOnFailure(r0)
            r3 = r9
            r6 = r11
            r4 = r10
            r7 = r12
            android.view.View r9 = r3.getView()
            androidx.compose.foundation.text2.input.internal.ComposeInputMethodManager r9 = androidx.compose.foundation.text2.input.internal.ComposeInputMethodManager_androidKt.ComposeInputMethodManager(r9)
            androidx.compose.foundation.text2.input.internal.AndroidTextInputSession_androidKt$platformSpecificTextInputSession$2 r10 = new androidx.compose.foundation.text2.input.internal.AndroidTextInputSession_androidKt$platformSpecificTextInputSession$2
            r8 = 0
            r2 = r10
            r5 = r9
            r2.<init>(r3, r4, r5, r6, r7, r8)
            kotlin.jvm.functions.Function2 r10 = (kotlin.jvm.functions.Function2) r10
            r11 = 1
            r13.label = r11
            java.lang.Object r9 = kotlinx.coroutines.CoroutineScopeKt.coroutineScope(r10, r13)
            if (r9 != r1) goto L55
            return r1
        L55:
            kotlin.KotlinNothingValueException r9 = new kotlin.KotlinNothingValueException
            r9.<init>()
            throw r9
        */
        throw new UnsupportedOperationException("Method not decompiled: androidx.compose.foundation.text2.input.internal.AndroidTextInputSession_androidKt.platformSpecificTextInputSession(androidx.compose.ui.platform.PlatformTextInputSession, androidx.compose.foundation.text2.input.internal.TransformedTextFieldState, androidx.compose.ui.text.input.ImeOptions, kotlin.jvm.functions.Function1, kotlin.coroutines.Continuation):java.lang.Object");
    }

    public static final void update(EditorInfo $this$update, TextFieldCharSequence textFieldValue, ImeOptions imeOptions) {
        int imeAction = imeOptions.getImeAction();
        int i = 3;
        int i2 = 6;
        if (ImeAction.m5735equalsimpl0(imeAction, ImeAction.INSTANCE.m5747getDefaulteUduSuo())) {
            if (!imeOptions.getSingleLine()) {
                i2 = 0;
            }
        } else if (ImeAction.m5735equalsimpl0(imeAction, ImeAction.INSTANCE.m5751getNoneeUduSuo())) {
            i2 = 1;
        } else if (ImeAction.m5735equalsimpl0(imeAction, ImeAction.INSTANCE.m5749getGoeUduSuo())) {
            i2 = 2;
        } else if (ImeAction.m5735equalsimpl0(imeAction, ImeAction.INSTANCE.m5750getNexteUduSuo())) {
            i2 = 5;
        } else if (ImeAction.m5735equalsimpl0(imeAction, ImeAction.INSTANCE.m5752getPreviouseUduSuo())) {
            i2 = 7;
        } else if (ImeAction.m5735equalsimpl0(imeAction, ImeAction.INSTANCE.m5753getSearcheUduSuo())) {
            i2 = 3;
        } else if (ImeAction.m5735equalsimpl0(imeAction, ImeAction.INSTANCE.m5754getSendeUduSuo())) {
            i2 = 4;
        } else if (!ImeAction.m5735equalsimpl0(imeAction, ImeAction.INSTANCE.m5748getDoneeUduSuo())) {
            throw new IllegalStateException("invalid ImeAction".toString());
        }
        $this$update.imeOptions = i2;
        int keyboardType = imeOptions.getKeyboardType();
        if (KeyboardType.m5782equalsimpl0(keyboardType, KeyboardType.INSTANCE.m5802getTextPjHm6EE())) {
            i = 1;
        } else if (KeyboardType.m5782equalsimpl0(keyboardType, KeyboardType.INSTANCE.m5795getAsciiPjHm6EE())) {
            $this$update.imeOptions |= Integer.MIN_VALUE;
            i = 1;
        } else if (KeyboardType.m5782equalsimpl0(keyboardType, KeyboardType.INSTANCE.m5798getNumberPjHm6EE())) {
            i = 2;
        } else if (!KeyboardType.m5782equalsimpl0(keyboardType, KeyboardType.INSTANCE.m5801getPhonePjHm6EE())) {
            if (KeyboardType.m5782equalsimpl0(keyboardType, KeyboardType.INSTANCE.m5803getUriPjHm6EE())) {
                i = 17;
            } else if (KeyboardType.m5782equalsimpl0(keyboardType, KeyboardType.INSTANCE.m5797getEmailPjHm6EE())) {
                i = 33;
            } else if (KeyboardType.m5782equalsimpl0(keyboardType, KeyboardType.INSTANCE.m5800getPasswordPjHm6EE())) {
                i = 129;
            } else if (KeyboardType.m5782equalsimpl0(keyboardType, KeyboardType.INSTANCE.m5799getNumberPasswordPjHm6EE())) {
                i = 18;
            } else if (KeyboardType.m5782equalsimpl0(keyboardType, KeyboardType.INSTANCE.m5796getDecimalPjHm6EE())) {
                i = InputDeviceCompat.SOURCE_MOUSE;
            } else {
                throw new IllegalStateException("Invalid Keyboard Type".toString());
            }
        }
        $this$update.inputType = i;
        if (!imeOptions.getSingleLine() && hasFlag($this$update.inputType, 1)) {
            $this$update.inputType |= 131072;
            if (ImeAction.m5735equalsimpl0(imeOptions.getImeAction(), ImeAction.INSTANCE.m5747getDefaulteUduSuo())) {
                $this$update.imeOptions |= 1073741824;
            }
        }
        if (hasFlag($this$update.inputType, 1)) {
            int capitalization = imeOptions.getCapitalization();
            if (KeyboardCapitalization.m5767equalsimpl0(capitalization, KeyboardCapitalization.INSTANCE.m5775getCharactersIUNYP9k())) {
                $this$update.inputType |= 4096;
            } else if (KeyboardCapitalization.m5767equalsimpl0(capitalization, KeyboardCapitalization.INSTANCE.m5778getWordsIUNYP9k())) {
                $this$update.inputType |= 8192;
            } else if (KeyboardCapitalization.m5767equalsimpl0(capitalization, KeyboardCapitalization.INSTANCE.m5777getSentencesIUNYP9k())) {
                $this$update.inputType |= 16384;
            }
            if (imeOptions.getAutoCorrect()) {
                $this$update.inputType |= 32768;
            }
        }
        $this$update.initialSelStart = TextRange.m5571getStartimpl(textFieldValue.getSelectionInChars());
        $this$update.initialSelEnd = TextRange.m5566getEndimpl(textFieldValue.getSelectionInChars());
        EditorInfoCompat.setInitialSurroundingText($this$update, textFieldValue);
        $this$update.imeOptions |= 33554432;
    }

    private static final boolean hasFlag(int bits, int flag) {
        return (bits & flag) == flag;
    }

    static /* synthetic */ void logDebug$default(String str, Function0 function0, int i, Object obj) {
        if ((i & 1) != 0) {
            str = TAG;
        }
        logDebug(str, function0);
    }

    private static final void logDebug(String tag, Function0<String> function0) {
    }
}
