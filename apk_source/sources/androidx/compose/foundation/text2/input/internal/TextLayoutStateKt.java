package androidx.compose.foundation.text2.input.internal;

import androidx.compose.ui.geometry.Offset;
import androidx.compose.ui.geometry.OffsetKt;
import androidx.compose.ui.geometry.Rect;
import androidx.compose.ui.layout.LayoutCoordinates;
import kotlin.Metadata;

/* compiled from: TextLayoutState.kt */
@Metadata(d1 = {"\u0000\u0018\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0018\u0002\n\u0002\b\u0006\u001a\u001e\u0010\u0000\u001a\u00020\u0001*\u00020\u00012\u0006\u0010\u0002\u001a\u00020\u0003H\u0000ø\u0001\u0000¢\u0006\u0004\b\u0004\u0010\u0005\u001a\u001e\u0010\u0006\u001a\u00020\u0001*\u00020\u00072\u0006\u0010\b\u001a\u00020\u0001H\u0000ø\u0001\u0000¢\u0006\u0004\b\t\u0010\n\u001a\u001e\u0010\u000b\u001a\u00020\u0001*\u00020\u00072\u0006\u0010\b\u001a\u00020\u0001H\u0000ø\u0001\u0000¢\u0006\u0004\b\f\u0010\n\u0082\u0002\u0007\n\u0005\b¡\u001e0\u0001¨\u0006\r"}, d2 = {"coerceIn", "Landroidx/compose/ui/geometry/Offset;", "rect", "Landroidx/compose/ui/geometry/Rect;", "coerceIn-3MmeM6k", "(JLandroidx/compose/ui/geometry/Rect;)J", "fromDecorationToTextLayout", "Landroidx/compose/foundation/text2/input/internal/TextLayoutState;", "offset", "fromDecorationToTextLayout-Uv8p0NA", "(Landroidx/compose/foundation/text2/input/internal/TextLayoutState;J)J", "fromTextLayoutToCore", "fromTextLayoutToCore-Uv8p0NA", "foundation_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class TextLayoutStateKt {
    /* renamed from: coerceIn-3MmeM6k, reason: not valid java name */
    public static final long m1147coerceIn3MmeM6k(long $this$coerceIn_u2d3MmeM6k, Rect rect) {
        float xOffset;
        float yOffset;
        if (Offset.m3505getXimpl($this$coerceIn_u2d3MmeM6k) < rect.getLeft()) {
            xOffset = rect.getLeft();
        } else {
            xOffset = Offset.m3505getXimpl($this$coerceIn_u2d3MmeM6k) > rect.getRight() ? rect.getRight() : Offset.m3505getXimpl($this$coerceIn_u2d3MmeM6k);
        }
        if (Offset.m3506getYimpl($this$coerceIn_u2d3MmeM6k) < rect.getTop()) {
            yOffset = rect.getTop();
        } else {
            yOffset = Offset.m3506getYimpl($this$coerceIn_u2d3MmeM6k) > rect.getBottom() ? rect.getBottom() : Offset.m3506getYimpl($this$coerceIn_u2d3MmeM6k);
        }
        return OffsetKt.Offset(xOffset, yOffset);
    }

    /* renamed from: fromTextLayoutToCore-Uv8p0NA, reason: not valid java name */
    public static final long m1149fromTextLayoutToCoreUv8p0NA(TextLayoutState $this$fromTextLayoutToCore_u2dUv8p0NA, long offset) {
        LayoutCoordinates textLayoutNodeCoordinates = $this$fromTextLayoutToCore_u2dUv8p0NA.getTextLayoutNodeCoordinates();
        if (textLayoutNodeCoordinates != null) {
            Offset offset2 = null;
            if (!textLayoutNodeCoordinates.isAttached()) {
                textLayoutNodeCoordinates = null;
            }
            if (textLayoutNodeCoordinates != null) {
                LayoutCoordinates it = $this$fromTextLayoutToCore_u2dUv8p0NA.getCoreNodeCoordinates();
                if (it != null) {
                    if (!it.isAttached()) {
                        it = null;
                    }
                    if (it != null) {
                        LayoutCoordinates coreNodeCoordinates = it;
                        offset2 = Offset.m3494boximpl(coreNodeCoordinates.mo5024localPositionOfR5De75A(textLayoutNodeCoordinates, offset));
                    }
                }
                if (offset2 != null) {
                    return offset2.getPackedValue();
                }
            }
        }
        return offset;
    }

    /* renamed from: fromDecorationToTextLayout-Uv8p0NA, reason: not valid java name */
    public static final long m1148fromDecorationToTextLayoutUv8p0NA(TextLayoutState $this$fromDecorationToTextLayout_u2dUv8p0NA, long offset) {
        Offset offset2;
        long j;
        LayoutCoordinates textLayoutNodeCoordinates = $this$fromDecorationToTextLayout_u2dUv8p0NA.getTextLayoutNodeCoordinates();
        if (textLayoutNodeCoordinates != null) {
            LayoutCoordinates decoratorNodeCoordinates = $this$fromDecorationToTextLayout_u2dUv8p0NA.getDecoratorNodeCoordinates();
            if (decoratorNodeCoordinates != null) {
                if (textLayoutNodeCoordinates.isAttached() && decoratorNodeCoordinates.isAttached()) {
                    j = textLayoutNodeCoordinates.mo5024localPositionOfR5De75A(decoratorNodeCoordinates, offset);
                } else {
                    j = offset;
                }
                offset2 = Offset.m3494boximpl(j);
            } else {
                offset2 = null;
            }
            if (offset2 != null) {
                return offset2.getPackedValue();
            }
        }
        return offset;
    }
}
