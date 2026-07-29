package androidx.compose.foundation.text2.input.internal;

import android.view.KeyEvent;
import android.view.inputmethod.EditorInfo;
import android.view.inputmethod.InputConnection;
import androidx.compose.foundation.text2.input.InputTransformation;
import androidx.compose.foundation.text2.input.TextFieldCharSequence;
import androidx.compose.foundation.text2.input.TextFieldState;
import androidx.compose.foundation.text2.input.internal.AndroidTextInputSession_androidKt$platformSpecificTextInputSession$2;
import androidx.compose.foundation.text2.input.internal.undo.TextFieldEditUndoBehavior;
import androidx.compose.ui.platform.PlatformTextInputMethodRequest;
import androidx.compose.ui.platform.PlatformTextInputSession;
import androidx.compose.ui.text.TextRange;
import androidx.compose.ui.text.input.ImeAction;
import androidx.compose.ui.text.input.ImeOptions;
import androidx.compose.ui.text.input.KeyboardType;
import kotlin.KotlinNothingValueException;
import kotlin.Metadata;
import kotlin.ResultKt;
import kotlin.Unit;
import kotlin.coroutines.Continuation;
import kotlin.coroutines.intrinsics.IntrinsicsKt;
import kotlin.coroutines.jvm.internal.DebugMetadata;
import kotlin.coroutines.jvm.internal.SuspendLambda;
import kotlin.jvm.functions.Function0;
import kotlin.jvm.functions.Function1;
import kotlin.jvm.functions.Function2;
import kotlin.jvm.internal.Intrinsics;
import kotlinx.coroutines.BuildersKt__Builders_commonKt;
import kotlinx.coroutines.CoroutineScope;
import kotlinx.coroutines.CoroutineStart;

/* compiled from: AndroidTextInputSession.android.kt */
@Metadata(d1 = {"\u0000\n\n\u0000\n\u0002\u0010\u0001\n\u0002\u0018\u0002\u0010\u0000\u001a\u00020\u0001*\u00020\u0002H\u008a@"}, d2 = {"<anonymous>", "", "Lkotlinx/coroutines/CoroutineScope;"}, k = 3, mv = {1, 8, 0}, xi = 48)
@DebugMetadata(c = "androidx.compose.foundation.text2.input.internal.AndroidTextInputSession_androidKt$platformSpecificTextInputSession$2", f = "AndroidTextInputSession.android.kt", i = {}, l = {73}, m = "invokeSuspend", n = {}, s = {})
/* loaded from: classes.dex */
final class AndroidTextInputSession_androidKt$platformSpecificTextInputSession$2 extends SuspendLambda implements Function2<CoroutineScope, Continuation<?>, Object> {
    final /* synthetic */ ComposeInputMethodManager $composeImm;
    final /* synthetic */ ImeOptions $imeOptions;
    final /* synthetic */ Function1<ImeAction, Unit> $onImeAction;
    final /* synthetic */ TransformedTextFieldState $state;
    final /* synthetic */ PlatformTextInputSession $this_platformSpecificTextInputSession;
    private /* synthetic */ Object L$0;
    int label;

    /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
    /* JADX WARN: Multi-variable type inference failed */
    AndroidTextInputSession_androidKt$platformSpecificTextInputSession$2(PlatformTextInputSession platformTextInputSession, TransformedTextFieldState transformedTextFieldState, ComposeInputMethodManager composeInputMethodManager, ImeOptions imeOptions, Function1<? super ImeAction, Unit> function1, Continuation<? super AndroidTextInputSession_androidKt$platformSpecificTextInputSession$2> continuation) {
        super(2, continuation);
        this.$this_platformSpecificTextInputSession = platformTextInputSession;
        this.$state = transformedTextFieldState;
        this.$composeImm = composeInputMethodManager;
        this.$imeOptions = imeOptions;
        this.$onImeAction = function1;
    }

    @Override // kotlin.coroutines.jvm.internal.BaseContinuationImpl
    public final Continuation<Unit> create(Object obj, Continuation<?> continuation) {
        AndroidTextInputSession_androidKt$platformSpecificTextInputSession$2 androidTextInputSession_androidKt$platformSpecificTextInputSession$2 = new AndroidTextInputSession_androidKt$platformSpecificTextInputSession$2(this.$this_platformSpecificTextInputSession, this.$state, this.$composeImm, this.$imeOptions, this.$onImeAction, continuation);
        androidTextInputSession_androidKt$platformSpecificTextInputSession$2.L$0 = obj;
        return androidTextInputSession_androidKt$platformSpecificTextInputSession$2;
    }

    @Override // kotlin.jvm.functions.Function2
    public final Object invoke(CoroutineScope coroutineScope, Continuation<?> continuation) {
        return ((AndroidTextInputSession_androidKt$platformSpecificTextInputSession$2) create(coroutineScope, continuation)).invokeSuspend(Unit.INSTANCE);
    }

    /* compiled from: AndroidTextInputSession.android.kt */
    @Metadata(d1 = {"\u0000\n\n\u0000\n\u0002\u0010\u0002\n\u0002\u0018\u0002\u0010\u0000\u001a\u00020\u0001*\u00020\u0002H\u008a@"}, d2 = {"<anonymous>", "", "Lkotlinx/coroutines/CoroutineScope;"}, k = 3, mv = {1, 8, 0}, xi = 48)
    @DebugMetadata(c = "androidx.compose.foundation.text2.input.internal.AndroidTextInputSession_androidKt$platformSpecificTextInputSession$2$1", f = "AndroidTextInputSession.android.kt", i = {}, l = {52}, m = "invokeSuspend", n = {}, s = {})
    /* renamed from: androidx.compose.foundation.text2.input.internal.AndroidTextInputSession_androidKt$platformSpecificTextInputSession$2$1, reason: invalid class name */
    static final class AnonymousClass1 extends SuspendLambda implements Function2<CoroutineScope, Continuation<? super Unit>, Object> {
        final /* synthetic */ ComposeInputMethodManager $composeImm;
        final /* synthetic */ ImeOptions $imeOptions;
        final /* synthetic */ TransformedTextFieldState $state;
        int label;

        /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
        AnonymousClass1(TransformedTextFieldState transformedTextFieldState, ComposeInputMethodManager composeInputMethodManager, ImeOptions imeOptions, Continuation<? super AnonymousClass1> continuation) {
            super(2, continuation);
            this.$state = transformedTextFieldState;
            this.$composeImm = composeInputMethodManager;
            this.$imeOptions = imeOptions;
        }

        @Override // kotlin.coroutines.jvm.internal.BaseContinuationImpl
        public final Continuation<Unit> create(Object obj, Continuation<?> continuation) {
            return new AnonymousClass1(this.$state, this.$composeImm, this.$imeOptions, continuation);
        }

        @Override // kotlin.jvm.functions.Function2
        public final Object invoke(CoroutineScope coroutineScope, Continuation<? super Unit> continuation) {
            return ((AnonymousClass1) create(coroutineScope, continuation)).invokeSuspend(Unit.INSTANCE);
        }

        @Override // kotlin.coroutines.jvm.internal.BaseContinuationImpl
        public final Object invokeSuspend(Object $result) {
            Object coroutine_suspended = IntrinsicsKt.getCOROUTINE_SUSPENDED();
            switch (this.label) {
                case 0:
                    ResultKt.throwOnFailure($result);
                    TransformedTextFieldState transformedTextFieldState = this.$state;
                    final ComposeInputMethodManager composeInputMethodManager = this.$composeImm;
                    final ImeOptions imeOptions = this.$imeOptions;
                    this.label = 1;
                    if (transformedTextFieldState.collectImeNotifications(new TextFieldState.NotifyImeListener() { // from class: androidx.compose.foundation.text2.input.internal.AndroidTextInputSession_androidKt$platformSpecificTextInputSession$2$1$$ExternalSyntheticLambda0
                        @Override // androidx.compose.foundation.text2.input.TextFieldState.NotifyImeListener
                        public final void onChange(TextFieldCharSequence textFieldCharSequence, TextFieldCharSequence textFieldCharSequence2) {
                            AndroidTextInputSession_androidKt$platformSpecificTextInputSession$2.AnonymousClass1.invokeSuspend$lambda$0(ComposeInputMethodManager.this, imeOptions, textFieldCharSequence, textFieldCharSequence2);
                        }
                    }, this) != coroutine_suspended) {
                        break;
                    } else {
                        return coroutine_suspended;
                    }
                case 1:
                    ResultKt.throwOnFailure($result);
                    break;
                default:
                    throw new IllegalStateException("call to 'resume' before 'invoke' with coroutine");
            }
            throw new KotlinNothingValueException();
        }

        /* JADX INFO: Access modifiers changed from: private */
        public static final void invokeSuspend$lambda$0(ComposeInputMethodManager $composeImm, ImeOptions $imeOptions, TextFieldCharSequence old, TextFieldCharSequence textFieldCharSequence) {
            boolean needUpdateSelection = (TextRange.m5564equalsimpl0(old.getSelectionInChars(), textFieldCharSequence.getSelectionInChars()) && Intrinsics.areEqual(old.getCompositionInChars(), textFieldCharSequence.getCompositionInChars())) ? false : true;
            if (needUpdateSelection) {
                int m5569getMinimpl = TextRange.m5569getMinimpl(textFieldCharSequence.getSelectionInChars());
                int m5568getMaximpl = TextRange.m5568getMaximpl(textFieldCharSequence.getSelectionInChars());
                TextRange compositionInChars = textFieldCharSequence.getCompositionInChars();
                int m5569getMinimpl2 = compositionInChars != null ? TextRange.m5569getMinimpl(compositionInChars.getPackedValue()) : -1;
                TextRange compositionInChars2 = textFieldCharSequence.getCompositionInChars();
                $composeImm.updateSelection(m5569getMinimpl, m5568getMaximpl, m5569getMinimpl2, compositionInChars2 != null ? TextRange.m5568getMaximpl(compositionInChars2.getPackedValue()) : -1);
            }
            if (!old.contentEquals(textFieldCharSequence) && !KeyboardType.m5782equalsimpl0($imeOptions.getKeyboardType(), KeyboardType.INSTANCE.m5800getPasswordPjHm6EE())) {
                $composeImm.restartInput();
            }
        }
    }

    @Override // kotlin.coroutines.jvm.internal.BaseContinuationImpl
    public final Object invokeSuspend(Object $result) {
        Object coroutine_suspended = IntrinsicsKt.getCOROUTINE_SUSPENDED();
        switch (this.label) {
            case 0:
                ResultKt.throwOnFailure($result);
                CoroutineScope $this$coroutineScope = (CoroutineScope) this.L$0;
                BuildersKt__Builders_commonKt.launch$default($this$coroutineScope, null, CoroutineStart.UNDISPATCHED, new AnonymousClass1(this.$state, this.$composeImm, this.$imeOptions, null), 1, null);
                PlatformTextInputSession platformTextInputSession = this.$this_platformSpecificTextInputSession;
                final TransformedTextFieldState transformedTextFieldState = this.$state;
                final ImeOptions imeOptions = this.$imeOptions;
                final ComposeInputMethodManager composeInputMethodManager = this.$composeImm;
                final Function1<ImeAction, Unit> function1 = this.$onImeAction;
                this.label = 1;
                if (platformTextInputSession.startInputMethod(new PlatformTextInputMethodRequest() { // from class: androidx.compose.foundation.text2.input.internal.AndroidTextInputSession_androidKt$platformSpecificTextInputSession$2$$ExternalSyntheticLambda0
                    @Override // androidx.compose.ui.platform.PlatformTextInputMethodRequest
                    public final InputConnection createInputConnection(EditorInfo editorInfo) {
                        InputConnection invokeSuspend$lambda$0;
                        invokeSuspend$lambda$0 = AndroidTextInputSession_androidKt$platformSpecificTextInputSession$2.invokeSuspend$lambda$0(TransformedTextFieldState.this, imeOptions, composeInputMethodManager, function1, editorInfo);
                        return invokeSuspend$lambda$0;
                    }
                }, this) != coroutine_suspended) {
                    break;
                } else {
                    return coroutine_suspended;
                }
            case 1:
                ResultKt.throwOnFailure($result);
                break;
            default:
                throw new IllegalStateException("call to 'resume' before 'invoke' with coroutine");
        }
        throw new KotlinNothingValueException();
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final InputConnection invokeSuspend$lambda$0(final TransformedTextFieldState $state, ImeOptions $imeOptions, final ComposeInputMethodManager $composeImm, final Function1 $onImeAction, EditorInfo outAttrs) {
        AndroidTextInputSession_androidKt.logDebug$default(null, new Function0<String>() { // from class: androidx.compose.foundation.text2.input.internal.AndroidTextInputSession_androidKt$platformSpecificTextInputSession$2$2$1
            {
                super(0);
            }

            @Override // kotlin.jvm.functions.Function0
            public final String invoke() {
                return "createInputConnection(value=\"" + ((Object) TransformedTextFieldState.this.getText()) + "\")";
            }
        }, 1, null);
        TextInputSession textInputSession = new TextInputSession() { // from class: androidx.compose.foundation.text2.input.internal.AndroidTextInputSession_androidKt$platformSpecificTextInputSession$2$2$textInputSession$1
            @Override // androidx.compose.foundation.text2.input.internal.TextInputSession
            public TextFieldCharSequence getText() {
                return TransformedTextFieldState.this.getText();
            }

            @Override // androidx.compose.foundation.text2.input.internal.TextInputSession
            public void requestEdit(Function1<? super EditingBuffer, Unit> block) {
                TransformedTextFieldState this_$iv = TransformedTextFieldState.this;
                TextFieldState $this$iv$iv = this_$iv.textFieldState;
                InputTransformation inputTransformation$iv$iv = this_$iv.inputTransformation;
                TextFieldEditUndoBehavior undoBehavior$iv$iv = TextFieldEditUndoBehavior.MergeIfPossible;
                TextFieldCharSequence previousValue$iv$iv = $this$iv$iv.getText();
                $this$iv$iv.getMainBuffer().getChangeTracker().clearChanges();
                block.invoke($this$iv$iv.getMainBuffer());
                if ($this$iv$iv.getMainBuffer().getChangeTracker().getChangeCount() != 0 || !TextRange.m5564equalsimpl0(previousValue$iv$iv.getSelectionInChars(), $this$iv$iv.getMainBuffer().m1106getSelectiond9O1mEE()) || !Intrinsics.areEqual(previousValue$iv$iv.getCompositionInChars(), $this$iv$iv.getMainBuffer().m1105getCompositionMzsxiRA())) {
                    $this$iv$iv.commitEditAsUser(previousValue$iv$iv, inputTransformation$iv$iv, false, undoBehavior$iv$iv);
                }
            }

            @Override // androidx.compose.foundation.text2.input.internal.TextInputSession
            public void sendKeyEvent(KeyEvent keyEvent) {
                $composeImm.sendKeyEvent(keyEvent);
            }

            @Override // androidx.compose.foundation.text2.input.internal.TextInputSession
            /* renamed from: onImeAction-KlQnJC8, reason: not valid java name */
            public void mo1104onImeActionKlQnJC8(int imeAction) {
                Function1<ImeAction, Unit> function1 = $onImeAction;
                if (function1 != null) {
                    function1.invoke(ImeAction.m5732boximpl(imeAction));
                }
            }
        };
        AndroidTextInputSession_androidKt.update(outAttrs, $state.getText(), $imeOptions);
        return new StatelessInputConnection(textInputSession);
    }
}
