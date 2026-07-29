package androidx.compose.foundation.text2.input;

import androidx.autofill.HintConstants;
import androidx.compose.foundation.text2.input.TextFieldBuffer;
import androidx.compose.ui.text.TextRange;
import androidx.compose.ui.text.TextRangeKt;
import kotlin.Metadata;
import kotlin.Unit;
import kotlin.jvm.functions.Function2;

/* compiled from: TextFieldBuffer.kt */
@Metadata(d1 = {"\u0000B\n\u0000\n\u0002\u0010\u0002\n\u0000\n\u0002\u0010\r\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\u0010\b\n\u0002\u0018\u0002\n\u0002\b\u0006\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\b\u0006\n\u0002\u0010\u000e\n\u0002\b\u0003\u001a{\u0010\u0000\u001a\u00020\u00012\u0006\u0010\u0002\u001a\u00020\u00032\u0006\u0010\u0004\u001a\u00020\u00032`\u0010\u0005\u001a\\\u0012\u0013\u0012\u00110\u0007¢\u0006\f\b\b\u0012\b\b\t\u0012\u0004\b\b(\n\u0012\u0013\u0012\u00110\u0007¢\u0006\f\b\b\u0012\b\b\t\u0012\u0004\b\b(\u000b\u0012\u0013\u0012\u00110\u0007¢\u0006\f\b\b\u0012\b\b\t\u0012\u0004\b\b(\f\u0012\u0013\u0012\u00110\u0007¢\u0006\f\b\b\u0012\b\b\t\u0012\u0004\b\b(\r\u0012\u0004\u0012\u00020\u00010\u0006H\u0080\b\u001a\u001c\u0010\u000e\u001a\u00020\u0001*\u00020\u000f2\u0006\u0010\u0010\u001a\u00020\u00072\u0006\u0010\u0011\u001a\u00020\u0007H\u0007\u001aE\u0010\u0012\u001a\u00020\u0001*\u00020\u001326\u0010\u0014\u001a2\u0012\u0013\u0012\u00110\u0016¢\u0006\f\b\b\u0012\b\b\t\u0012\u0004\b\b(\u0017\u0012\u0013\u0012\u00110\u0016¢\u0006\f\b\b\u0012\b\b\t\u0012\u0004\b\b(\u0018\u0012\u0004\u0012\u00020\u00010\u0015H\u0087\b\u001aE\u0010\u0019\u001a\u00020\u0001*\u00020\u001326\u0010\u0014\u001a2\u0012\u0013\u0012\u00110\u0016¢\u0006\f\b\b\u0012\b\b\t\u0012\u0004\b\b(\u0017\u0012\u0013\u0012\u00110\u0016¢\u0006\f\b\b\u0012\b\b\t\u0012\u0004\b\b(\u0018\u0012\u0004\u0012\u00020\u00010\u0015H\u0087\b\u001a\u001c\u0010\u001a\u001a\u00020\u0001*\u00020\u000f2\u0006\u0010\u001b\u001a\u00020\u00072\u0006\u0010\u001c\u001a\u00020\u001dH\u0007\u001a\f\u0010\u001e\u001a\u00020\u0001*\u00020\u000fH\u0007\u001a\f\u0010\u001f\u001a\u00020\u0001*\u00020\u000fH\u0007¨\u0006 "}, d2 = {"findCommonPrefixAndSuffix", "", "a", "", "b", "onFound", "Lkotlin/Function4;", "", "Lkotlin/ParameterName;", HintConstants.AUTOFILL_HINT_NAME, "aPrefixStart", "aSuffixStart", "bPrefixStart", "bSuffixStart", "delete", "Landroidx/compose/foundation/text2/input/TextFieldBuffer;", "start", "end", "forEachChange", "Landroidx/compose/foundation/text2/input/TextFieldBuffer$ChangeList;", "block", "Lkotlin/Function2;", "Landroidx/compose/ui/text/TextRange;", "range", "originalRange", "forEachChangeReversed", "insert", "index", "text", "", "placeCursorAtEnd", "selectAll", "foundation_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class TextFieldBufferKt {
    public static final void insert(TextFieldBuffer $this$insert, int index, String text) {
        $this$insert.replace(index, index, text);
    }

    public static final void delete(TextFieldBuffer $this$delete, int start, int end) {
        $this$delete.replace(start, end, "");
    }

    public static final void placeCursorAtEnd(TextFieldBuffer $this$placeCursorAtEnd) {
        $this$placeCursorAtEnd.placeCursorBeforeCharAt($this$placeCursorAtEnd.getLength());
    }

    public static final void selectAll(TextFieldBuffer $this$selectAll) {
        $this$selectAll.m1082selectCharsIn5zctL8(TextRangeKt.TextRange(0, $this$selectAll.getLength()));
    }

    public static final void forEachChange(TextFieldBuffer.ChangeList $this$forEachChange, Function2<? super TextRange, ? super TextRange, Unit> function2) {
        for (int i = 0; i < $this$forEachChange.getChangeCount(); i++) {
            function2.invoke(TextRange.m5559boximpl($this$forEachChange.mo1075getRangejx7JFs(i)), TextRange.m5559boximpl($this$forEachChange.mo1074getOriginalRangejx7JFs(i)));
        }
    }

    public static final void forEachChangeReversed(TextFieldBuffer.ChangeList $this$forEachChangeReversed, Function2<? super TextRange, ? super TextRange, Unit> function2) {
        for (int i = $this$forEachChangeReversed.getChangeCount() - 1; i >= 0; i--) {
            function2.invoke(TextRange.m5559boximpl($this$forEachChangeReversed.mo1075getRangejx7JFs(i)), TextRange.m5559boximpl($this$forEachChangeReversed.mo1074getOriginalRangejx7JFs(i)));
        }
    }

    /* JADX WARN: Code restructure failed: missing block: B:32:0x0055, code lost:
    
        if (r3 < r4) goto L29;
     */
    /* JADX WARN: Code restructure failed: missing block: B:33:0x0057, code lost:
    
        return;
     */
    /*
        Code decompiled incorrectly, please refer to instructions dump.
        To view partially-correct add '--show-bad-code' argument
    */
    public static final void findCommonPrefixAndSuffix(java.lang.CharSequence r9, java.lang.CharSequence r10, kotlin.jvm.functions.Function4<? super java.lang.Integer, ? super java.lang.Integer, ? super java.lang.Integer, ? super java.lang.Integer, kotlin.Unit> r11) {
        /*
            r0 = 0
            r1 = 0
            int r2 = r9.length()
            r3 = 0
            int r4 = r10.length()
            int r5 = r9.length()
            r6 = 0
            r7 = 1
            if (r5 <= 0) goto L15
            r5 = r7
            goto L16
        L15:
            r5 = r6
        L16:
            if (r5 == 0) goto L53
            int r5 = r10.length()
            if (r5 <= 0) goto L1f
            r6 = r7
        L1f:
            if (r6 == 0) goto L53
            r5 = 0
            r6 = 0
        L23:
            if (r5 != 0) goto L35
            char r7 = r9.charAt(r1)
            char r8 = r10.charAt(r3)
            if (r7 != r8) goto L34
            int r1 = r1 + 1
            int r3 = r3 + 1
            goto L35
        L34:
            r5 = 1
        L35:
            if (r6 != 0) goto L4b
            int r7 = r2 + (-1)
            char r7 = r9.charAt(r7)
            int r8 = r4 + (-1)
            char r8 = r10.charAt(r8)
            if (r7 != r8) goto L4a
            int r2 = r2 + (-1)
            int r4 = r4 + (-1)
            goto L4b
        L4a:
            r6 = 1
        L4b:
            if (r1 >= r2) goto L53
            if (r3 >= r4) goto L53
            if (r5 == 0) goto L23
            if (r6 == 0) goto L23
        L53:
            if (r1 < r2) goto L58
            if (r3 < r4) goto L58
            return
        L58:
            java.lang.Integer r5 = java.lang.Integer.valueOf(r1)
            java.lang.Integer r6 = java.lang.Integer.valueOf(r2)
            java.lang.Integer r7 = java.lang.Integer.valueOf(r3)
            java.lang.Integer r8 = java.lang.Integer.valueOf(r4)
            r11.invoke(r5, r6, r7, r8)
            return
        */
        throw new UnsupportedOperationException("Method not decompiled: androidx.compose.foundation.text2.input.TextFieldBufferKt.findCommonPrefixAndSuffix(java.lang.CharSequence, java.lang.CharSequence, kotlin.jvm.functions.Function4):void");
    }
}
