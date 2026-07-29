package androidx.compose.foundation.text2.input.internal;

import androidx.compose.ui.text.TextRange;
import androidx.compose.ui.text.TextRangeKt;
import kotlin.Metadata;

/* compiled from: OffsetMappingCalculator.kt */
@Metadata(d1 = {"\u00002\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0010\b\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0010\u000b\n\u0002\b\u000e\n\u0002\u0010\u0002\n\u0002\b\u0004\b\u0000\u0018\u00002\u00020\u0001B\u0005¢\u0006\u0002\u0010\u0002J%\u0010\b\u001a\u00020\t2\u0006\u0010\n\u001a\u00020\u00072\u0006\u0010\u000b\u001a\u00020\fH\u0002ø\u0001\u0001ø\u0001\u0000¢\u0006\u0004\b\r\u0010\u000eJ\u001b\u0010\u000f\u001a\u00020\t2\u0006\u0010\n\u001a\u00020\u0007ø\u0001\u0001ø\u0001\u0000¢\u0006\u0004\b\u0010\u0010\u0011J\u001b\u0010\u0012\u001a\u00020\t2\u0006\u0010\n\u001a\u00020\u0007ø\u0001\u0001ø\u0001\u0000¢\u0006\u0004\b\u0013\u0010\u0011J=\u0010\u0014\u001a\u00020\t2\u0006\u0010\n\u001a\u00020\u00072\u0006\u0010\u0015\u001a\u00020\u00072\u0006\u0010\u0016\u001a\u00020\u00072\u0006\u0010\u0017\u001a\u00020\u00072\u0006\u0010\u000b\u001a\u00020\fH\u0002ø\u0001\u0001ø\u0001\u0000¢\u0006\u0004\b\u0018\u0010\u0019J\u001e\u0010\u001a\u001a\u00020\u001b2\u0006\u0010\u001c\u001a\u00020\u00072\u0006\u0010\u001d\u001a\u00020\u00072\u0006\u0010\u001e\u001a\u00020\u0007R\u0016\u0010\u0003\u001a\u00020\u0004X\u0082\u000eø\u0001\u0000ø\u0001\u0001¢\u0006\u0004\n\u0002\u0010\u0005R\u000e\u0010\u0006\u001a\u00020\u0007X\u0082\u000e¢\u0006\u0002\n\u0000\u0082\u0002\u000b\n\u0005\b¡\u001e0\u0001\n\u0002\b!¨\u0006\u001f"}, d2 = {"Landroidx/compose/foundation/text2/input/internal/OffsetMappingCalculator;", "", "()V", "ops", "Landroidx/compose/foundation/text2/input/internal/OpArray;", "[I", "opsSize", "", "map", "Landroidx/compose/ui/text/TextRange;", "offset", "fromSource", "", "map-fzxv0v0", "(IZ)J", "mapFromDest", "mapFromDest--jx7JFs", "(I)J", "mapFromSource", "mapFromSource--jx7JFs", "mapStep", "opOffset", "untransformedLen", "transformedLen", "mapStep-C6u-MEY", "(IIIIZ)J", "recordEditOperation", "", "sourceStart", "sourceEnd", "newLength", "foundation_release"}, k = 1, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class OffsetMappingCalculator {
    public static final int $stable = 8;
    private int[] ops = OpArray.m1113constructorimpl(10);
    private int opsSize;

    public final void recordEditOperation(int sourceStart, int sourceEnd, int newLength) {
        if (!(newLength >= 0)) {
            throw new IllegalArgumentException(("Expected newLen to be ≥ 0, was " + newLength).toString());
        }
        int sourceMin = Math.min(sourceStart, sourceEnd);
        int sourceMax = Math.max(sourceMin, sourceEnd);
        int sourceLength = sourceMax - sourceMin;
        if (sourceLength >= 2 || sourceLength != newLength) {
            int newSize = this.opsSize + 1;
            if (newSize > OpArray.m1120getSizeimpl(this.ops)) {
                int newCapacity = Math.max(newSize * 2, OpArray.m1120getSizeimpl(this.ops) * 2);
                this.ops = OpArray.m1115copyOfS4kM8k(this.ops, newCapacity);
            }
            OpArray.m1122setimpl(this.ops, this.opsSize, sourceMin, sourceLength, newLength);
            this.opsSize = newSize;
        }
    }

    /* renamed from: mapFromSource--jx7JFs, reason: not valid java name */
    public final long m1111mapFromSourcejx7JFs(int offset) {
        return m1108mapfzxv0v0(offset, true);
    }

    /* renamed from: mapFromDest--jx7JFs, reason: not valid java name */
    public final long m1110mapFromDestjx7JFs(int offset) {
        return m1108mapfzxv0v0(offset, false);
    }

    /* renamed from: map-fzxv0v0, reason: not valid java name */
    private final long m1108mapfzxv0v0(int offset, boolean fromSource) {
        int start = offset;
        int end = offset;
        int[] arg0$iv = this.ops;
        int max$iv = this.opsSize;
        boolean reversed$iv = !fromSource;
        if (max$iv >= 0) {
            if (reversed$iv) {
                int start2 = start;
                int end2 = end;
                for (int i$iv = max$iv - 1; -1 < i$iv; i$iv--) {
                    int offset$iv = arg0$iv[i$iv * 3];
                    int srcLen$iv = arg0$iv[(i$iv * 3) + 1];
                    int destLen$iv = arg0$iv[(i$iv * 3) + 2];
                    long newStart = m1109mapStepC6uMEY(start2, offset$iv, srcLen$iv, destLen$iv, fromSource);
                    long newEnd = m1109mapStepC6uMEY(end2, offset$iv, srcLen$iv, destLen$iv, fromSource);
                    start2 = Math.min(TextRange.m5571getStartimpl(newStart), TextRange.m5571getStartimpl(newEnd));
                    end2 = Math.max(TextRange.m5566getEndimpl(newStart), TextRange.m5566getEndimpl(newEnd));
                }
                start = start2;
                end = end2;
            } else {
                int start3 = start;
                int end3 = end;
                for (int i$iv2 = 0; i$iv2 < max$iv; i$iv2++) {
                    int offset$iv2 = arg0$iv[i$iv2 * 3];
                    int srcLen$iv2 = arg0$iv[(i$iv2 * 3) + 1];
                    int destLen$iv2 = arg0$iv[(i$iv2 * 3) + 2];
                    long newStart2 = m1109mapStepC6uMEY(start3, offset$iv2, srcLen$iv2, destLen$iv2, fromSource);
                    long newEnd2 = m1109mapStepC6uMEY(end3, offset$iv2, srcLen$iv2, destLen$iv2, fromSource);
                    start3 = Math.min(TextRange.m5571getStartimpl(newStart2), TextRange.m5571getStartimpl(newEnd2));
                    end3 = Math.max(TextRange.m5566getEndimpl(newStart2), TextRange.m5566getEndimpl(newEnd2));
                }
                start = start3;
                end = end3;
            }
        }
        return TextRangeKt.TextRange(start, end);
    }

    /* renamed from: mapStep-C6u-MEY, reason: not valid java name */
    private final long m1109mapStepC6uMEY(int offset, int opOffset, int untransformedLen, int transformedLen, boolean fromSource) {
        int srcLen = fromSource ? untransformedLen : transformedLen;
        int destLen = fromSource ? transformedLen : untransformedLen;
        if (offset < opOffset) {
            return TextRangeKt.TextRange(offset);
        }
        if (offset == opOffset) {
            if (srcLen == 0) {
                return TextRangeKt.TextRange(opOffset, opOffset + destLen);
            }
            return TextRangeKt.TextRange(opOffset);
        }
        if (offset < opOffset + srcLen) {
            if (destLen == 0) {
                return TextRangeKt.TextRange(opOffset);
            }
            return TextRangeKt.TextRange(opOffset, opOffset + destLen);
        }
        return TextRangeKt.TextRange((offset - srcLen) + destLen);
    }
}
