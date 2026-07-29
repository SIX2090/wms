package androidx.compose.foundation.text2.input.internal;

import androidx.compose.foundation.text2.input.CodepointTransformation;
import androidx.compose.foundation.text2.input.CodepointTransformationKt;
import androidx.compose.foundation.text2.input.InputTransformation;
import androidx.compose.foundation.text2.input.TextFieldCharSequence;
import androidx.compose.foundation.text2.input.TextFieldCharSequenceKt;
import androidx.compose.foundation.text2.input.TextFieldState;
import androidx.compose.foundation.text2.input.internal.TransformedTextFieldState;
import androidx.compose.foundation.text2.input.internal.undo.TextFieldEditUndoBehavior;
import androidx.compose.runtime.SnapshotStateKt;
import androidx.compose.runtime.State;
import androidx.compose.ui.text.TextRange;
import androidx.compose.ui.text.TextRangeKt;
import kotlin.Metadata;
import kotlin.Unit;
import kotlin.jvm.JvmStatic;
import kotlin.jvm.functions.Function0;
import kotlin.jvm.functions.Function1;
import kotlin.jvm.internal.DefaultConstructorMarker;
import kotlin.jvm.internal.Intrinsics;

/* compiled from: TransformedTextFieldState.kt */
@Metadata(d1 = {"\u0000\u0084\u0001\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0010\u0002\n\u0002\b\u0002\n\u0002\u0010\u0001\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0004\n\u0002\u0010\u000b\n\u0000\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0010\b\n\u0000\n\u0002\u0018\u0002\n\u0002\b\r\n\u0002\u0010\r\n\u0002\b\u0003\n\u0002\u0018\u0002\n\u0002\b\f\n\u0002\u0010\u000e\n\u0002\b\u0004\b\u0001\u0018\u0000 H2\u00020\u0001:\u0002HIB!\u0012\u0006\u0010\u0002\u001a\u00020\u0003\u0012\b\u0010\u0004\u001a\u0004\u0018\u00010\u0005\u0012\b\u0010\u0006\u001a\u0004\u0018\u00010\u0007¢\u0006\u0002\u0010\bJ\u0006\u0010\u0012\u001a\u00020\u0013J\u0006\u0010\u0014\u001a\u00020\u0013J\u0016\u0010\u0015\u001a\u00020\u00162\u0006\u0010\u0017\u001a\u00020\u0018H\u0086@¢\u0006\u0002\u0010\u0019J\u0006\u0010\u001a\u001a\u00020\u0013J,\u0010\u001b\u001a\u00020\u00132\b\b\u0002\u0010\u001c\u001a\u00020\u001d2\u0017\u0010\u001e\u001a\u0013\u0012\u0004\u0012\u00020 \u0012\u0004\u0012\u00020\u00130\u001f¢\u0006\u0002\b!H\u0086\bJ\u0013\u0010\"\u001a\u00020\u001d2\b\u0010#\u001a\u0004\u0018\u00010\u0001H\u0096\u0002J\b\u0010$\u001a\u00020%H\u0016J\u0018\u0010&\u001a\u00020'2\u0006\u0010(\u001a\u00020'ø\u0001\u0000¢\u0006\u0004\b)\u0010*J\u000e\u0010&\u001a\u00020%2\u0006\u0010+\u001a\u00020%J\u0018\u0010,\u001a\u00020'2\u0006\u0010(\u001a\u00020'ø\u0001\u0000¢\u0006\u0004\b-\u0010*J\u001b\u0010,\u001a\u00020'2\u0006\u0010+\u001a\u00020%ø\u0001\u0001ø\u0001\u0000¢\u0006\u0004\b.\u0010/J\u000e\u00100\u001a\u00020\u00132\u0006\u00101\u001a\u00020%J\u0006\u00102\u001a\u00020\u0013J\u000e\u00103\u001a\u00020\u00132\u0006\u00104\u001a\u000205J\"\u00106\u001a\u00020\u00132\u0006\u00104\u001a\u0002052\b\b\u0002\u00107\u001a\u00020\u001d2\b\b\u0002\u00108\u001a\u000209J*\u0010:\u001a\u00020\u00132\u0006\u00104\u001a\u0002052\u0006\u0010(\u001a\u00020'2\b\b\u0002\u00108\u001a\u000209ø\u0001\u0000¢\u0006\u0004\b;\u0010<J\u0006\u0010=\u001a\u00020\u0013J\u0018\u0010>\u001a\u00020\u00132\u0006\u0010?\u001a\u00020'ø\u0001\u0000¢\u0006\u0004\b@\u0010AJ\u0018\u0010B\u001a\u00020\u00132\u0006\u0010C\u001a\u00020'ø\u0001\u0000¢\u0006\u0004\bD\u0010AJ\b\u0010E\u001a\u00020FH\u0016J\u0006\u0010G\u001a\u00020\u0013R\u0010\u0010\u0006\u001a\u0004\u0018\u00010\u0007X\u0082\u0004¢\u0006\u0002\n\u0000R\u0010\u0010\u0004\u001a\u0004\u0018\u00010\u0005X\u0082\u0004¢\u0006\u0002\n\u0000R\u0011\u0010\t\u001a\u00020\n8F¢\u0006\u0006\u001a\u0004\b\u000b\u0010\fR\u000e\u0010\u0002\u001a\u00020\u0003X\u0082\u0004¢\u0006\u0002\n\u0000R\u0018\u0010\r\u001a\f\u0012\u0006\u0012\u0004\u0018\u00010\u000f\u0018\u00010\u000eX\u0082\u0004¢\u0006\u0002\n\u0000R\u0011\u0010\u0010\u001a\u00020\n8F¢\u0006\u0006\u001a\u0004\b\u0011\u0010\f\u0082\u0002\u000b\n\u0005\b¡\u001e0\u0001\n\u0002\b!¨\u0006J"}, d2 = {"Landroidx/compose/foundation/text2/input/internal/TransformedTextFieldState;", "", "textFieldState", "Landroidx/compose/foundation/text2/input/TextFieldState;", "inputTransformation", "Landroidx/compose/foundation/text2/input/InputTransformation;", "codepointTransformation", "Landroidx/compose/foundation/text2/input/CodepointTransformation;", "(Landroidx/compose/foundation/text2/input/TextFieldState;Landroidx/compose/foundation/text2/input/InputTransformation;Landroidx/compose/foundation/text2/input/CodepointTransformation;)V", "text", "Landroidx/compose/foundation/text2/input/TextFieldCharSequence;", "getText", "()Landroidx/compose/foundation/text2/input/TextFieldCharSequence;", "transformedText", "Landroidx/compose/runtime/State;", "Landroidx/compose/foundation/text2/input/internal/TransformedTextFieldState$TransformedText;", "untransformedText", "getUntransformedText", "collapseSelectionToEnd", "", "collapseSelectionToMax", "collectImeNotifications", "", "notifyImeListener", "Landroidx/compose/foundation/text2/input/TextFieldState$NotifyImeListener;", "(Landroidx/compose/foundation/text2/input/TextFieldState$NotifyImeListener;Lkotlin/coroutines/Continuation;)Ljava/lang/Object;", "deleteSelectedText", "editUntransformedTextAsUser", "notifyImeOfChanges", "", "block", "Lkotlin/Function1;", "Landroidx/compose/foundation/text2/input/internal/EditingBuffer;", "Lkotlin/ExtensionFunctionType;", "equals", "other", "hashCode", "", "mapFromTransformed", "Landroidx/compose/ui/text/TextRange;", "range", "mapFromTransformed-GEjPoXI", "(J)J", "offset", "mapToTransformed", "mapToTransformed-GEjPoXI", "mapToTransformed--jx7JFs", "(I)J", "placeCursorBeforeCharAt", "transformedOffset", "redo", "replaceAll", "newText", "", "replaceSelectedText", "clearComposition", "undoBehavior", "Landroidx/compose/foundation/text2/input/internal/undo/TextFieldEditUndoBehavior;", "replaceText", "replaceText-Sb-Bc2M", "(Ljava/lang/CharSequence;JLandroidx/compose/foundation/text2/input/internal/undo/TextFieldEditUndoBehavior;)V", "selectAll", "selectCharsIn", "transformedRange", "selectCharsIn-5zc-tL8", "(J)V", "selectUntransformedCharsIn", "untransformedRange", "selectUntransformedCharsIn-5zc-tL8", "toString", "", "undo", "Companion", "TransformedText", "foundation_release"}, k = 1, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class TransformedTextFieldState {
    public static final int $stable = 0;
    private static final Companion Companion = new Companion(null);
    private final CodepointTransformation codepointTransformation;
    private final InputTransformation inputTransformation;
    private final TextFieldState textFieldState;
    private final State<TransformedText> transformedText;

    @JvmStatic
    private static final TransformedText calculateTransformedText(TextFieldCharSequence textFieldCharSequence, CodepointTransformation codepointTransformation) {
        return Companion.calculateTransformedText(textFieldCharSequence, codepointTransformation);
    }

    @JvmStatic
    /* renamed from: mapFromTransformed-xdX6-G0, reason: not valid java name */
    private static final long m1150mapFromTransformedxdX6G0(long j, OffsetMappingCalculator offsetMappingCalculator) {
        return Companion.m1161mapFromTransformedxdX6G0(j, offsetMappingCalculator);
    }

    @JvmStatic
    /* renamed from: mapToTransformed-xdX6-G0, reason: not valid java name */
    private static final long m1151mapToTransformedxdX6G0(long j, OffsetMappingCalculator offsetMappingCalculator) {
        return Companion.m1162mapToTransformedxdX6G0(j, offsetMappingCalculator);
    }

    public TransformedTextFieldState(TextFieldState textFieldState, InputTransformation inputTransformation, CodepointTransformation codepointTransformation) {
        this.textFieldState = textFieldState;
        this.inputTransformation = inputTransformation;
        this.codepointTransformation = codepointTransformation;
        final CodepointTransformation transformation = this.codepointTransformation;
        this.transformedText = transformation != null ? SnapshotStateKt.derivedStateOf(new Function0<TransformedText>() { // from class: androidx.compose.foundation.text2.input.internal.TransformedTextFieldState$transformedText$1$1
            /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
            {
                super(0);
            }

            /* JADX WARN: Can't rename method to resolve collision */
            @Override // kotlin.jvm.functions.Function0
            public final TransformedTextFieldState.TransformedText invoke() {
                return TransformedTextFieldState.Companion.calculateTransformedText(TransformedTextFieldState.this.textFieldState.getText(), transformation);
            }
        }) : null;
    }

    public final TextFieldCharSequence getText() {
        TransformedText value;
        TextFieldCharSequence text;
        State<TransformedText> state = this.transformedText;
        return (state == null || (value = state.getValue()) == null || (text = value.getText()) == null) ? this.textFieldState.getText() : text;
    }

    public final TextFieldCharSequence getUntransformedText() {
        return this.textFieldState.getText();
    }

    public final void placeCursorBeforeCharAt(int transformedOffset) {
        m1157selectCharsIn5zctL8(TextRangeKt.TextRange(transformedOffset));
    }

    /* renamed from: selectCharsIn-5zc-tL8, reason: not valid java name */
    public final void m1157selectCharsIn5zctL8(long transformedRange) {
        long untransformedRange = m1153mapFromTransformedGEjPoXI(transformedRange);
        m1158selectUntransformedCharsIn5zctL8(untransformedRange);
    }

    /* renamed from: selectUntransformedCharsIn-5zc-tL8, reason: not valid java name */
    public final void m1158selectUntransformedCharsIn5zctL8(long untransformedRange) {
        TextFieldState $this$iv = this.textFieldState;
        InputTransformation inputTransformation$iv = this.inputTransformation;
        TextFieldEditUndoBehavior undoBehavior$iv = TextFieldEditUndoBehavior.MergeIfPossible;
        TextFieldCharSequence previousValue$iv = $this$iv.getText();
        $this$iv.getMainBuffer().getChangeTracker().clearChanges();
        EditingBuffer $this$selectUntransformedCharsIn_5zc_tL8_u24lambda_u241 = $this$iv.getMainBuffer();
        $this$selectUntransformedCharsIn_5zc_tL8_u24lambda_u241.setSelection(TextRange.m5571getStartimpl(untransformedRange), TextRange.m5566getEndimpl(untransformedRange));
        if ($this$iv.getMainBuffer().getChangeTracker().getChangeCount() != 0 || !TextRange.m5564equalsimpl0(previousValue$iv.getSelectionInChars(), $this$iv.getMainBuffer().m1106getSelectiond9O1mEE()) || !Intrinsics.areEqual(previousValue$iv.getCompositionInChars(), $this$iv.getMainBuffer().m1105getCompositionMzsxiRA())) {
            $this$iv.commitEditAsUser(previousValue$iv, inputTransformation$iv, true, undoBehavior$iv);
        }
    }

    public final void replaceAll(CharSequence newText) {
        TextFieldState $this$iv = this.textFieldState;
        InputTransformation inputTransformation$iv = this.inputTransformation;
        TextFieldEditUndoBehavior undoBehavior$iv = TextFieldEditUndoBehavior.MergeIfPossible;
        TextFieldCharSequence previousValue$iv = $this$iv.getText();
        $this$iv.getMainBuffer().getChangeTracker().clearChanges();
        EditingBuffer $this$replaceAll_u24lambda_u242 = $this$iv.getMainBuffer();
        EditCommandKt.deleteAll($this$replaceAll_u24lambda_u242);
        EditCommandKt.commitText($this$replaceAll_u24lambda_u242, newText.toString(), 1);
        if ($this$iv.getMainBuffer().getChangeTracker().getChangeCount() != 0 || !TextRange.m5564equalsimpl0(previousValue$iv.getSelectionInChars(), $this$iv.getMainBuffer().m1106getSelectiond9O1mEE()) || !Intrinsics.areEqual(previousValue$iv.getCompositionInChars(), $this$iv.getMainBuffer().m1105getCompositionMzsxiRA())) {
            $this$iv.commitEditAsUser(previousValue$iv, inputTransformation$iv, true, undoBehavior$iv);
        }
    }

    public final void selectAll() {
        TextFieldState $this$iv = this.textFieldState;
        InputTransformation inputTransformation$iv = this.inputTransformation;
        TextFieldEditUndoBehavior undoBehavior$iv = TextFieldEditUndoBehavior.MergeIfPossible;
        TextFieldCharSequence previousValue$iv = $this$iv.getText();
        $this$iv.getMainBuffer().getChangeTracker().clearChanges();
        EditingBuffer $this$selectAll_u24lambda_u243 = $this$iv.getMainBuffer();
        $this$selectAll_u24lambda_u243.setSelection(0, $this$selectAll_u24lambda_u243.getLength());
        if ($this$iv.getMainBuffer().getChangeTracker().getChangeCount() != 0 || !TextRange.m5564equalsimpl0(previousValue$iv.getSelectionInChars(), $this$iv.getMainBuffer().m1106getSelectiond9O1mEE()) || !Intrinsics.areEqual(previousValue$iv.getCompositionInChars(), $this$iv.getMainBuffer().m1105getCompositionMzsxiRA())) {
            $this$iv.commitEditAsUser(previousValue$iv, inputTransformation$iv, true, undoBehavior$iv);
        }
    }

    public final void deleteSelectedText() {
        TextFieldState $this$iv = this.textFieldState;
        InputTransformation inputTransformation$iv = this.inputTransformation;
        TextFieldEditUndoBehavior undoBehavior$iv = TextFieldEditUndoBehavior.NeverMerge;
        TextFieldCharSequence previousValue$iv = $this$iv.getText();
        $this$iv.getMainBuffer().getChangeTracker().clearChanges();
        EditingBuffer $this$deleteSelectedText_u24lambda_u244 = $this$iv.getMainBuffer();
        $this$deleteSelectedText_u24lambda_u244.delete(TextRange.m5569getMinimpl($this$deleteSelectedText_u24lambda_u244.m1106getSelectiond9O1mEE()), TextRange.m5568getMaximpl($this$deleteSelectedText_u24lambda_u244.m1106getSelectiond9O1mEE()));
        $this$deleteSelectedText_u24lambda_u244.setSelection(TextRange.m5569getMinimpl($this$deleteSelectedText_u24lambda_u244.m1106getSelectiond9O1mEE()), TextRange.m5569getMinimpl($this$deleteSelectedText_u24lambda_u244.m1106getSelectiond9O1mEE()));
        if ($this$iv.getMainBuffer().getChangeTracker().getChangeCount() != 0 || !TextRange.m5564equalsimpl0(previousValue$iv.getSelectionInChars(), $this$iv.getMainBuffer().m1106getSelectiond9O1mEE()) || !Intrinsics.areEqual(previousValue$iv.getCompositionInChars(), $this$iv.getMainBuffer().m1105getCompositionMzsxiRA())) {
            $this$iv.commitEditAsUser(previousValue$iv, inputTransformation$iv, true, undoBehavior$iv);
        }
    }

    /* renamed from: replaceText-Sb-Bc2M$default, reason: not valid java name */
    public static /* synthetic */ void m1152replaceTextSbBc2M$default(TransformedTextFieldState transformedTextFieldState, CharSequence charSequence, long j, TextFieldEditUndoBehavior textFieldEditUndoBehavior, int i, Object obj) {
        if ((i & 4) != 0) {
            textFieldEditUndoBehavior = TextFieldEditUndoBehavior.MergeIfPossible;
        }
        transformedTextFieldState.m1156replaceTextSbBc2M(charSequence, j, textFieldEditUndoBehavior);
    }

    /* renamed from: replaceText-Sb-Bc2M, reason: not valid java name */
    public final void m1156replaceTextSbBc2M(CharSequence newText, long range, TextFieldEditUndoBehavior undoBehavior) {
        TextFieldState $this$iv = this.textFieldState;
        InputTransformation inputTransformation$iv = this.inputTransformation;
        TextFieldCharSequence previousValue$iv = $this$iv.getText();
        $this$iv.getMainBuffer().getChangeTracker().clearChanges();
        EditingBuffer $this$replaceText_Sb_Bc2M_u24lambda_u245 = $this$iv.getMainBuffer();
        long selection = m1153mapFromTransformedGEjPoXI(range);
        $this$replaceText_Sb_Bc2M_u24lambda_u245.replace(TextRange.m5569getMinimpl(selection), TextRange.m5568getMaximpl(selection), newText);
        int cursor = TextRange.m5569getMinimpl(selection) + newText.length();
        $this$replaceText_Sb_Bc2M_u24lambda_u245.setSelection(cursor, cursor);
        if ($this$iv.getMainBuffer().getChangeTracker().getChangeCount() != 0 || !TextRange.m5564equalsimpl0(previousValue$iv.getSelectionInChars(), $this$iv.getMainBuffer().m1106getSelectiond9O1mEE()) || !Intrinsics.areEqual(previousValue$iv.getCompositionInChars(), $this$iv.getMainBuffer().m1105getCompositionMzsxiRA())) {
            $this$iv.commitEditAsUser(previousValue$iv, inputTransformation$iv, true, undoBehavior);
        }
    }

    public static /* synthetic */ void replaceSelectedText$default(TransformedTextFieldState transformedTextFieldState, CharSequence charSequence, boolean z, TextFieldEditUndoBehavior textFieldEditUndoBehavior, int i, Object obj) {
        if ((i & 2) != 0) {
            z = false;
        }
        if ((i & 4) != 0) {
            textFieldEditUndoBehavior = TextFieldEditUndoBehavior.MergeIfPossible;
        }
        transformedTextFieldState.replaceSelectedText(charSequence, z, textFieldEditUndoBehavior);
    }

    public final void replaceSelectedText(CharSequence newText, boolean clearComposition, TextFieldEditUndoBehavior undoBehavior) {
        TextFieldState $this$iv = this.textFieldState;
        InputTransformation inputTransformation$iv = this.inputTransformation;
        TextFieldCharSequence previousValue$iv = $this$iv.getText();
        $this$iv.getMainBuffer().getChangeTracker().clearChanges();
        EditingBuffer $this$replaceSelectedText_u24lambda_u246 = $this$iv.getMainBuffer();
        if (clearComposition) {
            $this$replaceSelectedText_u24lambda_u246.commitComposition();
        }
        long selection = $this$replaceSelectedText_u24lambda_u246.m1106getSelectiond9O1mEE();
        $this$replaceSelectedText_u24lambda_u246.replace(TextRange.m5569getMinimpl(selection), TextRange.m5568getMaximpl(selection), newText);
        int cursor = TextRange.m5569getMinimpl(selection) + newText.length();
        $this$replaceSelectedText_u24lambda_u246.setSelection(cursor, cursor);
        if ($this$iv.getMainBuffer().getChangeTracker().getChangeCount() != 0 || !TextRange.m5564equalsimpl0(previousValue$iv.getSelectionInChars(), $this$iv.getMainBuffer().m1106getSelectiond9O1mEE()) || !Intrinsics.areEqual(previousValue$iv.getCompositionInChars(), $this$iv.getMainBuffer().m1105getCompositionMzsxiRA())) {
            $this$iv.commitEditAsUser(previousValue$iv, inputTransformation$iv, true, undoBehavior);
        }
    }

    public final void collapseSelectionToMax() {
        TextFieldState $this$iv = this.textFieldState;
        InputTransformation inputTransformation$iv = this.inputTransformation;
        TextFieldEditUndoBehavior undoBehavior$iv = TextFieldEditUndoBehavior.MergeIfPossible;
        TextFieldCharSequence previousValue$iv = $this$iv.getText();
        $this$iv.getMainBuffer().getChangeTracker().clearChanges();
        EditingBuffer $this$collapseSelectionToMax_u24lambda_u247 = $this$iv.getMainBuffer();
        $this$collapseSelectionToMax_u24lambda_u247.setSelection(TextRange.m5568getMaximpl($this$collapseSelectionToMax_u24lambda_u247.m1106getSelectiond9O1mEE()), TextRange.m5568getMaximpl($this$collapseSelectionToMax_u24lambda_u247.m1106getSelectiond9O1mEE()));
        if ($this$iv.getMainBuffer().getChangeTracker().getChangeCount() != 0 || !TextRange.m5564equalsimpl0(previousValue$iv.getSelectionInChars(), $this$iv.getMainBuffer().m1106getSelectiond9O1mEE()) || !Intrinsics.areEqual(previousValue$iv.getCompositionInChars(), $this$iv.getMainBuffer().m1105getCompositionMzsxiRA())) {
            $this$iv.commitEditAsUser(previousValue$iv, inputTransformation$iv, true, undoBehavior$iv);
        }
    }

    public final void collapseSelectionToEnd() {
        TextFieldState $this$iv = this.textFieldState;
        InputTransformation inputTransformation$iv = this.inputTransformation;
        TextFieldEditUndoBehavior undoBehavior$iv = TextFieldEditUndoBehavior.MergeIfPossible;
        TextFieldCharSequence previousValue$iv = $this$iv.getText();
        $this$iv.getMainBuffer().getChangeTracker().clearChanges();
        EditingBuffer $this$collapseSelectionToEnd_u24lambda_u248 = $this$iv.getMainBuffer();
        $this$collapseSelectionToEnd_u24lambda_u248.setSelection(TextRange.m5566getEndimpl($this$collapseSelectionToEnd_u24lambda_u248.m1106getSelectiond9O1mEE()), TextRange.m5566getEndimpl($this$collapseSelectionToEnd_u24lambda_u248.m1106getSelectiond9O1mEE()));
        if ($this$iv.getMainBuffer().getChangeTracker().getChangeCount() != 0 || !TextRange.m5564equalsimpl0(previousValue$iv.getSelectionInChars(), $this$iv.getMainBuffer().m1106getSelectiond9O1mEE()) || !Intrinsics.areEqual(previousValue$iv.getCompositionInChars(), $this$iv.getMainBuffer().m1105getCompositionMzsxiRA())) {
            $this$iv.commitEditAsUser(previousValue$iv, inputTransformation$iv, true, undoBehavior$iv);
        }
    }

    public final void undo() {
        this.textFieldState.getUndoState().undo();
    }

    public final void redo() {
        this.textFieldState.getUndoState().redo();
    }

    public static /* synthetic */ void editUntransformedTextAsUser$default(TransformedTextFieldState $this, boolean notifyImeOfChanges, Function1 block, int i, Object obj) {
        if ((i & 1) != 0) {
            notifyImeOfChanges = true;
        }
        TextFieldState $this$iv = $this.textFieldState;
        InputTransformation inputTransformation$iv = $this.inputTransformation;
        TextFieldEditUndoBehavior undoBehavior$iv = TextFieldEditUndoBehavior.MergeIfPossible;
        TextFieldCharSequence previousValue$iv = $this$iv.getText();
        $this$iv.getMainBuffer().getChangeTracker().clearChanges();
        block.invoke($this$iv.getMainBuffer());
        if ($this$iv.getMainBuffer().getChangeTracker().getChangeCount() != 0 || !TextRange.m5564equalsimpl0(previousValue$iv.getSelectionInChars(), $this$iv.getMainBuffer().m1106getSelectiond9O1mEE()) || !Intrinsics.areEqual(previousValue$iv.getCompositionInChars(), $this$iv.getMainBuffer().m1105getCompositionMzsxiRA())) {
            $this$iv.commitEditAsUser(previousValue$iv, inputTransformation$iv, notifyImeOfChanges, undoBehavior$iv);
        }
    }

    public final void editUntransformedTextAsUser(boolean notifyImeOfChanges, Function1<? super EditingBuffer, Unit> block) {
        TextFieldState $this$iv = this.textFieldState;
        InputTransformation inputTransformation$iv = this.inputTransformation;
        TextFieldEditUndoBehavior undoBehavior$iv = TextFieldEditUndoBehavior.MergeIfPossible;
        TextFieldCharSequence previousValue$iv = $this$iv.getText();
        $this$iv.getMainBuffer().getChangeTracker().clearChanges();
        block.invoke($this$iv.getMainBuffer());
        if ($this$iv.getMainBuffer().getChangeTracker().getChangeCount() != 0 || !TextRange.m5564equalsimpl0(previousValue$iv.getSelectionInChars(), $this$iv.getMainBuffer().m1106getSelectiond9O1mEE()) || !Intrinsics.areEqual(previousValue$iv.getCompositionInChars(), $this$iv.getMainBuffer().m1105getCompositionMzsxiRA())) {
            $this$iv.commitEditAsUser(previousValue$iv, inputTransformation$iv, notifyImeOfChanges, undoBehavior$iv);
        }
    }

    /* renamed from: mapToTransformed--jx7JFs, reason: not valid java name */
    public final long m1154mapToTransformedjx7JFs(int offset) {
        TransformedText value;
        OffsetMappingCalculator mapping;
        State<TransformedText> state = this.transformedText;
        if (state == null || (value = state.getValue()) == null || (mapping = value.getOffsetMapping()) == null) {
            return TextRangeKt.TextRange(offset);
        }
        return mapping.m1111mapFromSourcejx7JFs(offset);
    }

    /* renamed from: mapToTransformed-GEjPoXI, reason: not valid java name */
    public final long m1155mapToTransformedGEjPoXI(long range) {
        TransformedText value;
        OffsetMappingCalculator mapping;
        State<TransformedText> state = this.transformedText;
        if (state == null || (value = state.getValue()) == null || (mapping = value.getOffsetMapping()) == null) {
            return range;
        }
        return Companion.m1162mapToTransformedxdX6G0(range, mapping);
    }

    public final int mapFromTransformed(int offset) {
        TransformedText value;
        OffsetMappingCalculator mapping;
        State<TransformedText> state = this.transformedText;
        if (state == null || (value = state.getValue()) == null || (mapping = value.getOffsetMapping()) == null) {
            return offset;
        }
        return TextRange.m5569getMinimpl(mapping.m1110mapFromDestjx7JFs(offset));
    }

    /* renamed from: mapFromTransformed-GEjPoXI, reason: not valid java name */
    public final long m1153mapFromTransformedGEjPoXI(long range) {
        TransformedText value;
        OffsetMappingCalculator mapping;
        State<TransformedText> state = this.transformedText;
        if (state == null || (value = state.getValue()) == null || (mapping = value.getOffsetMapping()) == null) {
            return range;
        }
        return Companion.m1161mapFromTransformedxdX6G0(range, mapping);
    }

    /* JADX WARN: Removed duplicated region for block: B:11:0x002e  */
    /* JADX WARN: Removed duplicated region for block: B:14:0x003b  */
    /* JADX WARN: Removed duplicated region for block: B:8:0x0025  */
    /*
        Code decompiled incorrectly, please refer to instructions dump.
        To view partially-correct add '--show-bad-code' argument
    */
    public final java.lang.Object collectImeNotifications(final androidx.compose.foundation.text2.input.TextFieldState.NotifyImeListener r11, kotlin.coroutines.Continuation<?> r12) {
        /*
            r10 = this;
            boolean r0 = r12 instanceof androidx.compose.foundation.text2.input.internal.TransformedTextFieldState$collectImeNotifications$1
            if (r0 == 0) goto L14
            r0 = r12
            androidx.compose.foundation.text2.input.internal.TransformedTextFieldState$collectImeNotifications$1 r0 = (androidx.compose.foundation.text2.input.internal.TransformedTextFieldState$collectImeNotifications$1) r0
            int r1 = r0.label
            r2 = -2147483648(0xffffffff80000000, float:-0.0)
            r1 = r1 & r2
            if (r1 == 0) goto L14
            int r12 = r0.label
            int r12 = r12 - r2
            r0.label = r12
            goto L19
        L14:
            androidx.compose.foundation.text2.input.internal.TransformedTextFieldState$collectImeNotifications$1 r0 = new androidx.compose.foundation.text2.input.internal.TransformedTextFieldState$collectImeNotifications$1
            r0.<init>(r10, r12)
        L19:
            r12 = r0
            java.lang.Object r0 = r12.result
            java.lang.Object r1 = kotlin.coroutines.intrinsics.IntrinsicsKt.getCOROUTINE_SUSPENDED()
            int r2 = r12.label
            switch(r2) {
                case 0: goto L3b;
                case 1: goto L2e;
                default: goto L25;
            }
        L25:
            java.lang.IllegalStateException r11 = new java.lang.IllegalStateException
            java.lang.String r12 = "call to 'resume' before 'invoke' with coroutine"
            r11.<init>(r12)
            throw r11
        L2e:
            r11 = 0
            java.lang.Object r1 = r12.L$1
            androidx.compose.foundation.text2.input.TextFieldState$NotifyImeListener r1 = (androidx.compose.foundation.text2.input.TextFieldState.NotifyImeListener) r1
            java.lang.Object r1 = r12.L$0
            androidx.compose.foundation.text2.input.internal.TransformedTextFieldState r1 = (androidx.compose.foundation.text2.input.internal.TransformedTextFieldState) r1
            kotlin.ResultKt.throwOnFailure(r0)
            goto L83
        L3b:
            kotlin.ResultKt.throwOnFailure(r0)
            r2 = r10
            r3 = 0
            r12.L$0 = r2
            r12.L$1 = r11
            r4 = 1
            r12.label = r4
            r5 = r12
            kotlin.coroutines.Continuation r5 = (kotlin.coroutines.Continuation) r5
            r6 = 0
            kotlinx.coroutines.CancellableContinuationImpl r7 = new kotlinx.coroutines.CancellableContinuationImpl
            kotlin.coroutines.Continuation r8 = kotlin.coroutines.intrinsics.IntrinsicsKt.intercepted(r5)
            r7.<init>(r8, r4)
            r4 = r7
            r4.initCancellability()
            r7 = r4
            kotlinx.coroutines.CancellableContinuation r7 = (kotlinx.coroutines.CancellableContinuation) r7
            r8 = 0
            androidx.compose.foundation.text2.input.TextFieldState r9 = access$getTextFieldState$p(r2)
            r9.addNotifyImeListener$foundation_release(r11)
            androidx.compose.foundation.text2.input.internal.TransformedTextFieldState$collectImeNotifications$2$1 r9 = new androidx.compose.foundation.text2.input.internal.TransformedTextFieldState$collectImeNotifications$2$1
            r9.<init>()
            kotlin.jvm.functions.Function1 r9 = (kotlin.jvm.functions.Function1) r9
            r7.invokeOnCancellation(r9)
            java.lang.Object r11 = r4.getResult()
            java.lang.Object r2 = kotlin.coroutines.intrinsics.IntrinsicsKt.getCOROUTINE_SUSPENDED()
            if (r11 != r2) goto L7f
            r2 = r12
            kotlin.coroutines.Continuation r2 = (kotlin.coroutines.Continuation) r2
            kotlin.coroutines.jvm.internal.DebugProbesKt.probeCoroutineSuspended(r2)
        L7f:
            if (r11 != r1) goto L82
            return r1
        L82:
            r11 = r3
        L83:
            kotlin.KotlinNothingValueException r11 = new kotlin.KotlinNothingValueException
            r11.<init>()
            throw r11
        */
        throw new UnsupportedOperationException("Method not decompiled: androidx.compose.foundation.text2.input.internal.TransformedTextFieldState.collectImeNotifications(androidx.compose.foundation.text2.input.TextFieldState$NotifyImeListener, kotlin.coroutines.Continuation):java.lang.Object");
    }

    public boolean equals(Object other) {
        if (this == other) {
            return true;
        }
        if ((other instanceof TransformedTextFieldState) && Intrinsics.areEqual(this.textFieldState, ((TransformedTextFieldState) other).textFieldState)) {
            return Intrinsics.areEqual(this.codepointTransformation, ((TransformedTextFieldState) other).codepointTransformation);
        }
        return false;
    }

    public int hashCode() {
        int result = this.textFieldState.hashCode();
        int i = result * 31;
        CodepointTransformation codepointTransformation = this.codepointTransformation;
        int result2 = i + (codepointTransformation != null ? codepointTransformation.hashCode() : 0);
        return result2;
    }

    public String toString() {
        return "TransformedTextFieldState(textFieldState=" + this.textFieldState + ", codepointTransformation=" + this.codepointTransformation + ", transformedText=" + this.transformedText + ", text=\"" + ((Object) getText()) + "\")";
    }

    /* JADX INFO: Access modifiers changed from: private */
    /* compiled from: TransformedTextFieldState.kt */
    @Metadata(d1 = {"\u0000,\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\t\n\u0002\u0010\u000b\n\u0002\b\u0002\n\u0002\u0010\b\n\u0000\n\u0002\u0010\u000e\n\u0000\b\u0082\b\u0018\u00002\u00020\u0001B\u0015\u0012\u0006\u0010\u0002\u001a\u00020\u0003\u0012\u0006\u0010\u0004\u001a\u00020\u0005¢\u0006\u0002\u0010\u0006J\t\u0010\u000b\u001a\u00020\u0003HÆ\u0003J\t\u0010\f\u001a\u00020\u0005HÆ\u0003J\u001d\u0010\r\u001a\u00020\u00002\b\b\u0002\u0010\u0002\u001a\u00020\u00032\b\b\u0002\u0010\u0004\u001a\u00020\u0005HÆ\u0001J\u0013\u0010\u000e\u001a\u00020\u000f2\b\u0010\u0010\u001a\u0004\u0018\u00010\u0001HÖ\u0003J\t\u0010\u0011\u001a\u00020\u0012HÖ\u0001J\t\u0010\u0013\u001a\u00020\u0014HÖ\u0001R\u0011\u0010\u0004\u001a\u00020\u0005¢\u0006\b\n\u0000\u001a\u0004\b\u0007\u0010\bR\u0011\u0010\u0002\u001a\u00020\u0003¢\u0006\b\n\u0000\u001a\u0004\b\t\u0010\n¨\u0006\u0015"}, d2 = {"Landroidx/compose/foundation/text2/input/internal/TransformedTextFieldState$TransformedText;", "", "text", "Landroidx/compose/foundation/text2/input/TextFieldCharSequence;", "offsetMapping", "Landroidx/compose/foundation/text2/input/internal/OffsetMappingCalculator;", "(Landroidx/compose/foundation/text2/input/TextFieldCharSequence;Landroidx/compose/foundation/text2/input/internal/OffsetMappingCalculator;)V", "getOffsetMapping", "()Landroidx/compose/foundation/text2/input/internal/OffsetMappingCalculator;", "getText", "()Landroidx/compose/foundation/text2/input/TextFieldCharSequence;", "component1", "component2", "copy", "equals", "", "other", "hashCode", "", "toString", "", "foundation_release"}, k = 1, mv = {1, 8, 0}, xi = 48)
    static final /* data */ class TransformedText {
        private final OffsetMappingCalculator offsetMapping;
        private final TextFieldCharSequence text;

        public static /* synthetic */ TransformedText copy$default(TransformedText transformedText, TextFieldCharSequence textFieldCharSequence, OffsetMappingCalculator offsetMappingCalculator, int i, Object obj) {
            if ((i & 1) != 0) {
                textFieldCharSequence = transformedText.text;
            }
            if ((i & 2) != 0) {
                offsetMappingCalculator = transformedText.offsetMapping;
            }
            return transformedText.copy(textFieldCharSequence, offsetMappingCalculator);
        }

        /* renamed from: component1, reason: from getter */
        public final TextFieldCharSequence getText() {
            return this.text;
        }

        /* renamed from: component2, reason: from getter */
        public final OffsetMappingCalculator getOffsetMapping() {
            return this.offsetMapping;
        }

        public final TransformedText copy(TextFieldCharSequence text, OffsetMappingCalculator offsetMapping) {
            return new TransformedText(text, offsetMapping);
        }

        public boolean equals(Object other) {
            if (this == other) {
                return true;
            }
            if (!(other instanceof TransformedText)) {
                return false;
            }
            TransformedText transformedText = (TransformedText) other;
            return Intrinsics.areEqual(this.text, transformedText.text) && Intrinsics.areEqual(this.offsetMapping, transformedText.offsetMapping);
        }

        public int hashCode() {
            return (this.text.hashCode() * 31) + this.offsetMapping.hashCode();
        }

        public String toString() {
            return "TransformedText(text=" + ((Object) this.text) + ", offsetMapping=" + this.offsetMapping + ')';
        }

        public TransformedText(TextFieldCharSequence text, OffsetMappingCalculator offsetMapping) {
            this.text = text;
            this.offsetMapping = offsetMapping;
        }

        public final TextFieldCharSequence getText() {
            return this.text;
        }

        public final OffsetMappingCalculator getOffsetMapping() {
            return this.offsetMapping;
        }
    }

    /* JADX INFO: Access modifiers changed from: private */
    /* compiled from: TransformedTextFieldState.kt */
    @Metadata(d1 = {"\u0000.\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\b\u0005\b\u0082\u0003\u0018\u00002\u00020\u0001B\u0007\b\u0002¢\u0006\u0002\u0010\u0002J\u001a\u0010\u0003\u001a\u0004\u0018\u00010\u00042\u0006\u0010\u0005\u001a\u00020\u00062\u0006\u0010\u0007\u001a\u00020\bH\u0003J\"\u0010\t\u001a\u00020\n2\u0006\u0010\u000b\u001a\u00020\n2\u0006\u0010\f\u001a\u00020\rH\u0003ø\u0001\u0000¢\u0006\u0004\b\u000e\u0010\u000fJ\"\u0010\u0010\u001a\u00020\n2\u0006\u0010\u000b\u001a\u00020\n2\u0006\u0010\f\u001a\u00020\rH\u0003ø\u0001\u0000¢\u0006\u0004\b\u0011\u0010\u000f\u0082\u0002\u0007\n\u0005\b¡\u001e0\u0001¨\u0006\u0012"}, d2 = {"Landroidx/compose/foundation/text2/input/internal/TransformedTextFieldState$Companion;", "", "()V", "calculateTransformedText", "Landroidx/compose/foundation/text2/input/internal/TransformedTextFieldState$TransformedText;", "untransformedText", "Landroidx/compose/foundation/text2/input/TextFieldCharSequence;", "codepointTransformation", "Landroidx/compose/foundation/text2/input/CodepointTransformation;", "mapFromTransformed", "Landroidx/compose/ui/text/TextRange;", "range", "mapping", "Landroidx/compose/foundation/text2/input/internal/OffsetMappingCalculator;", "mapFromTransformed-xdX6-G0", "(JLandroidx/compose/foundation/text2/input/internal/OffsetMappingCalculator;)J", "mapToTransformed", "mapToTransformed-xdX6-G0", "foundation_release"}, k = 1, mv = {1, 8, 0}, xi = 48)
    static final class Companion {
        public /* synthetic */ Companion(DefaultConstructorMarker defaultConstructorMarker) {
            this();
        }

        private Companion() {
        }

        /* JADX INFO: Access modifiers changed from: private */
        @JvmStatic
        public final TransformedText calculateTransformedText(TextFieldCharSequence untransformedText, CodepointTransformation codepointTransformation) {
            OffsetMappingCalculator offsetMappingCalculator = new OffsetMappingCalculator();
            CharSequence transformedText = CodepointTransformationKt.toVisualText(untransformedText, codepointTransformation, offsetMappingCalculator);
            TextRange textRange = null;
            if (transformedText == untransformedText) {
                return null;
            }
            long m1162mapToTransformedxdX6G0 = m1162mapToTransformedxdX6G0(untransformedText.getSelectionInChars(), offsetMappingCalculator);
            TextRange compositionInChars = untransformedText.getCompositionInChars();
            if (compositionInChars != null) {
                long it = compositionInChars.getPackedValue();
                textRange = TextRange.m5559boximpl(TransformedTextFieldState.Companion.m1162mapToTransformedxdX6G0(it, offsetMappingCalculator));
            }
            TextFieldCharSequence transformedTextWithSelection = TextFieldCharSequenceKt.m1087TextFieldCharSequence3r_uNRQ(transformedText, m1162mapToTransformedxdX6G0, textRange);
            return new TransformedText(transformedTextWithSelection, offsetMappingCalculator);
        }

        /* JADX INFO: Access modifiers changed from: private */
        @JvmStatic
        /* renamed from: mapToTransformed-xdX6-G0, reason: not valid java name */
        public final long m1162mapToTransformedxdX6G0(long range, OffsetMappingCalculator mapping) {
            long transformedStart = mapping.m1111mapFromSourcejx7JFs(TextRange.m5571getStartimpl(range));
            long transformedEnd = TextRange.m5565getCollapsedimpl(range) ? transformedStart : mapping.m1111mapFromSourcejx7JFs(TextRange.m5566getEndimpl(range));
            int transformedMin = Math.min(TextRange.m5569getMinimpl(transformedStart), TextRange.m5569getMinimpl(transformedEnd));
            int transformedMax = Math.max(TextRange.m5568getMaximpl(transformedStart), TextRange.m5568getMaximpl(transformedEnd));
            if (TextRange.m5570getReversedimpl(range)) {
                return TextRangeKt.TextRange(transformedMax, transformedMin);
            }
            return TextRangeKt.TextRange(transformedMin, transformedMax);
        }

        /* JADX INFO: Access modifiers changed from: private */
        @JvmStatic
        /* renamed from: mapFromTransformed-xdX6-G0, reason: not valid java name */
        public final long m1161mapFromTransformedxdX6G0(long range, OffsetMappingCalculator mapping) {
            long untransformedStart = mapping.m1110mapFromDestjx7JFs(TextRange.m5571getStartimpl(range));
            long untransformedEnd = TextRange.m5565getCollapsedimpl(range) ? untransformedStart : mapping.m1110mapFromDestjx7JFs(TextRange.m5566getEndimpl(range));
            int untransformedMin = Math.min(TextRange.m5569getMinimpl(untransformedStart), TextRange.m5569getMinimpl(untransformedEnd));
            int untransformedMax = Math.max(TextRange.m5568getMaximpl(untransformedStart), TextRange.m5568getMaximpl(untransformedEnd));
            if (TextRange.m5570getReversedimpl(range)) {
                return TextRangeKt.TextRange(untransformedMax, untransformedMin);
            }
            return TextRangeKt.TextRange(untransformedMin, untransformedMax);
        }
    }
}
