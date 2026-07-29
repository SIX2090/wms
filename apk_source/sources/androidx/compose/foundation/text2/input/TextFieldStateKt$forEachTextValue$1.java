package androidx.compose.foundation.text2.input;

import kotlin.Metadata;
import kotlin.coroutines.Continuation;
import kotlin.coroutines.jvm.internal.ContinuationImpl;
import kotlin.coroutines.jvm.internal.DebugMetadata;

/* compiled from: TextFieldState.kt */
@Metadata(k = 3, mv = {1, 8, 0}, xi = 48)
@DebugMetadata(c = "androidx.compose.foundation.text2.input.TextFieldStateKt", f = "TextFieldState.kt", i = {}, l = {566}, m = "forEachTextValue", n = {}, s = {})
/* loaded from: classes.dex */
final class TextFieldStateKt$forEachTextValue$1 extends ContinuationImpl {
    int label;
    /* synthetic */ Object result;

    TextFieldStateKt$forEachTextValue$1(Continuation<? super TextFieldStateKt$forEachTextValue$1> continuation) {
        super(continuation);
    }

    @Override // kotlin.coroutines.jvm.internal.BaseContinuationImpl
    public final Object invokeSuspend(Object obj) {
        this.result = obj;
        this.label |= Integer.MIN_VALUE;
        return TextFieldStateKt.forEachTextValue(null, null, this);
    }
}
