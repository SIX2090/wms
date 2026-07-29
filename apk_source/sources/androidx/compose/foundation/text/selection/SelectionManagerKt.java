package androidx.compose.foundation.text.selection;

import androidx.compose.foundation.text.Handle;
import androidx.compose.foundation.text.selection.Selection;
import androidx.compose.ui.geometry.Offset;
import androidx.compose.ui.geometry.OffsetKt;
import androidx.compose.ui.geometry.Rect;
import androidx.compose.ui.geometry.RectKt;
import androidx.compose.ui.layout.LayoutCoordinates;
import androidx.compose.ui.layout.LayoutCoordinatesKt;
import androidx.compose.ui.text.TextRange;
import androidx.compose.ui.unit.IntSize;
import java.util.List;
import kotlin.Metadata;
import kotlin.NoWhenBranchMatchedException;
import kotlin.Pair;
import kotlin.collections.CollectionsKt;
import kotlin.jvm.internal.Intrinsics;
import kotlin.ranges.RangesKt;

/* compiled from: SelectionManager.kt */
@Metadata(d1 = {"\u0000F\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0004\n\u0002\u0018\u0002\n\u0002\b\u0004\n\u0002\u0010 \n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0004\n\u0002\u0010\u000b\n\u0002\b\u0007\u001a\"\u0010\u0002\u001a\u00020\u00032\u0006\u0010\u0004\u001a\u00020\u00052\u0006\u0010\u0006\u001a\u00020\u0007H\u0000ø\u0001\u0000¢\u0006\u0004\b\b\u0010\t\u001a*\u0010\n\u001a\u00020\u00032\u0006\u0010\u0004\u001a\u00020\u00052\u0006\u0010\u0006\u001a\u00020\u00072\u0006\u0010\u000b\u001a\u00020\fH\u0002ø\u0001\u0000¢\u0006\u0004\b\r\u0010\u000e\u001a*\u0010\u000f\u001a\u00020\u00012\u0018\u0010\u0010\u001a\u0014\u0012\u0010\u0012\u000e\u0012\u0004\u0012\u00020\u0013\u0012\u0004\u0012\u00020\u00140\u00120\u00112\u0006\u0010\u0015\u001a\u00020\u0016H\u0001\u001a\u001e\u0010\u0017\u001a\u0004\u0018\u00010\u00142\b\u0010\u0018\u001a\u0004\u0018\u00010\u00142\b\u0010\u0019\u001a\u0004\u0018\u00010\u0014H\u0000\u001a\u001e\u0010\u001a\u001a\u00020\u001b*\u00020\u00012\u0006\u0010\u001c\u001a\u00020\u0003H\u0000ø\u0001\u0000¢\u0006\u0004\b\u001d\u0010\u001e\u001a\u001e\u0010\u001f\u001a\b\u0012\u0004\u0012\u0002H 0\u0011\"\u0004\b\u0000\u0010 *\b\u0012\u0004\u0012\u0002H 0\u0011H\u0002\u001a\f\u0010!\u001a\u00020\u0001*\u00020\u0016H\u0000\"\u000e\u0010\u0000\u001a\u00020\u0001X\u0082\u0004¢\u0006\u0002\n\u0000\u0082\u0002\u0007\n\u0005\b¡\u001e0\u0001¨\u0006\""}, d2 = {"invertedInfiniteRect", "Landroidx/compose/ui/geometry/Rect;", "calculateSelectionMagnifierCenterAndroid", "Landroidx/compose/ui/geometry/Offset;", "manager", "Landroidx/compose/foundation/text/selection/SelectionManager;", "magnifierSize", "Landroidx/compose/ui/unit/IntSize;", "calculateSelectionMagnifierCenterAndroid-O0kMr_c", "(Landroidx/compose/foundation/text/selection/SelectionManager;J)J", "getMagnifierCenter", "anchor", "Landroidx/compose/foundation/text/selection/Selection$AnchorInfo;", "getMagnifierCenter-JVtK1S4", "(Landroidx/compose/foundation/text/selection/SelectionManager;JLandroidx/compose/foundation/text/selection/Selection$AnchorInfo;)J", "getSelectedRegionRect", "selectableSubSelectionPairs", "", "Lkotlin/Pair;", "Landroidx/compose/foundation/text/selection/Selectable;", "Landroidx/compose/foundation/text/selection/Selection;", "containerCoordinates", "Landroidx/compose/ui/layout/LayoutCoordinates;", "merge", "lhs", "rhs", "containsInclusive", "", "offset", "containsInclusive-Uv8p0NA", "(Landroidx/compose/ui/geometry/Rect;J)Z", "firstAndLast", "T", "visibleBounds", "foundation_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class SelectionManagerKt {
    private static final Rect invertedInfiniteRect = new Rect(Float.POSITIVE_INFINITY, Float.POSITIVE_INFINITY, Float.NEGATIVE_INFINITY, Float.NEGATIVE_INFINITY);

    /* compiled from: SelectionManager.kt */
    @Metadata(k = 3, mv = {1, 8, 0}, xi = 48)
    public /* synthetic */ class WhenMappings {
        public static final /* synthetic */ int[] $EnumSwitchMapping$0;

        static {
            int[] iArr = new int[Handle.values().length];
            try {
                iArr[Handle.SelectionStart.ordinal()] = 1;
            } catch (NoSuchFieldError e) {
            }
            try {
                iArr[Handle.SelectionEnd.ordinal()] = 2;
            } catch (NoSuchFieldError e2) {
            }
            try {
                iArr[Handle.Cursor.ordinal()] = 3;
            } catch (NoSuchFieldError e3) {
            }
            $EnumSwitchMapping$0 = iArr;
        }
    }

    public static final Selection merge(Selection lhs, Selection rhs) {
        Selection merge;
        return (lhs == null || (merge = lhs.merge(rhs)) == null) ? rhs : merge;
    }

    /* JADX INFO: Access modifiers changed from: private */
    /* JADX WARN: Multi-variable type inference failed */
    public static final <T> List<T> firstAndLast(List<? extends T> list) {
        switch (list.size()) {
            case 0:
            case 1:
                return list;
            default:
                return CollectionsKt.listOf(CollectionsKt.first((List) list), CollectionsKt.last((List) list));
        }
    }

    public static final Rect getSelectedRegionRect(List<? extends Pair<? extends Selectable, Selection>> list, LayoutCoordinates containerCoordinates) {
        List $this$fastForEach$iv;
        int $i$f$fastForEach;
        int i;
        int[] offsets;
        LayoutCoordinates layoutCoordinates = containerCoordinates;
        if (list.isEmpty()) {
            return invertedInfiniteRect;
        }
        Rect rect = invertedInfiniteRect;
        float containerTop = rect.getLeft();
        float containerRight = rect.getTop();
        float containerRight2 = rect.getRight();
        float containerBottom = rect.getBottom();
        List $this$fastForEach$iv2 = list;
        int $i$f$fastForEach2 = 0;
        int index$iv = 0;
        int size = $this$fastForEach$iv2.size();
        while (index$iv < size) {
            Object item$iv = $this$fastForEach$iv2.get(index$iv);
            Pair<? extends Selectable, Selection> pair = (Pair) item$iv;
            Selectable selectable = pair.component1();
            Selection subSelection = pair.component2();
            int startOffset = subSelection.getStart().getOffset();
            int endOffset = subSelection.getEnd().getOffset();
            if (startOffset == endOffset) {
                $this$fastForEach$iv = $this$fastForEach$iv2;
                $i$f$fastForEach = $i$f$fastForEach2;
                i = size;
            } else {
                LayoutCoordinates localCoordinates = selectable.getLayoutCoordinates();
                if (localCoordinates == null) {
                    $this$fastForEach$iv = $this$fastForEach$iv2;
                    $i$f$fastForEach = $i$f$fastForEach2;
                    i = size;
                } else {
                    $this$fastForEach$iv = $this$fastForEach$iv2;
                    int minOffset = Math.min(startOffset, endOffset);
                    int maxOffset = Math.max(startOffset, endOffset);
                    $i$f$fastForEach = $i$f$fastForEach2;
                    int $i$f$fastForEach3 = maxOffset - 1;
                    i = size;
                    if (minOffset == $i$f$fastForEach3) {
                        offsets = new int[]{minOffset};
                    } else {
                        offsets = new int[]{minOffset, maxOffset - 1};
                    }
                    Rect rect2 = invertedInfiniteRect;
                    float left = rect2.getLeft();
                    float top = rect2.getTop();
                    float right = rect2.getRight();
                    float bottom = rect2.getBottom();
                    int minOffset2 = offsets.length;
                    int i2 = 0;
                    float left2 = left;
                    float top2 = top;
                    float right2 = right;
                    while (i2 < minOffset2) {
                        int i3 = minOffset2;
                        int i4 = offsets[i2];
                        Rect rect3 = selectable.getBoundingBox(i4);
                        left2 = Math.min(left2, rect3.getLeft());
                        top2 = Math.min(top2, rect3.getTop());
                        right2 = Math.max(right2, rect3.getRight());
                        bottom = Math.max(bottom, rect3.getBottom());
                        i2++;
                        minOffset2 = i3;
                    }
                    long localTopLeft = OffsetKt.Offset(left2, top2);
                    long localBottomRight = OffsetKt.Offset(right2, bottom);
                    long containerTopLeft = layoutCoordinates.mo5024localPositionOfR5De75A(localCoordinates, localTopLeft);
                    long containerBottomRight = layoutCoordinates.mo5024localPositionOfR5De75A(localCoordinates, localBottomRight);
                    float containerLeft = Math.min(containerTop, Offset.m3505getXimpl(containerTopLeft));
                    float containerLeft2 = Offset.m3506getYimpl(containerTopLeft);
                    float containerTop2 = Math.min(containerRight, containerLeft2);
                    float containerTop3 = Offset.m3505getXimpl(containerBottomRight);
                    float containerRight3 = Math.max(containerRight2, containerTop3);
                    float containerRight4 = Offset.m3506getYimpl(containerBottomRight);
                    containerBottom = Math.max(containerBottom, containerRight4);
                    containerRight2 = containerRight3;
                    containerRight = containerTop2;
                    containerTop = containerLeft;
                }
            }
            index$iv++;
            layoutCoordinates = containerCoordinates;
            $this$fastForEach$iv2 = $this$fastForEach$iv;
            $i$f$fastForEach2 = $i$f$fastForEach;
            size = i;
        }
        return new Rect(containerTop, containerRight, containerRight2, containerBottom);
    }

    /* renamed from: calculateSelectionMagnifierCenterAndroid-O0kMr_c, reason: not valid java name */
    public static final long m1040calculateSelectionMagnifierCenterAndroidO0kMr_c(SelectionManager manager, long magnifierSize) {
        Selection selection = manager.getSelection();
        if (selection == null) {
            return Offset.INSTANCE.m3520getUnspecifiedF1C5BW0();
        }
        Handle draggingHandle = manager.getDraggingHandle();
        switch (draggingHandle == null ? -1 : WhenMappings.$EnumSwitchMapping$0[draggingHandle.ordinal()]) {
            case -1:
                return Offset.INSTANCE.m3520getUnspecifiedF1C5BW0();
            case 0:
            default:
                throw new NoWhenBranchMatchedException();
            case 1:
                return m1042getMagnifierCenterJVtK1S4(manager, magnifierSize, selection.getStart());
            case 2:
                return m1042getMagnifierCenterJVtK1S4(manager, magnifierSize, selection.getEnd());
            case 3:
                throw new IllegalStateException("SelectionContainer does not support cursor".toString());
        }
    }

    /* renamed from: getMagnifierCenter-JVtK1S4, reason: not valid java name */
    private static final long m1042getMagnifierCenterJVtK1S4(SelectionManager manager, long magnifierSize, Selection.AnchorInfo anchor) {
        LayoutCoordinates containerCoordinates;
        LayoutCoordinates selectableCoordinates;
        int offset;
        float lineStartX;
        Selectable selectable = manager.getAnchorSelectable$foundation_release(anchor);
        if (selectable != null && (containerCoordinates = manager.getContainerLayoutCoordinates()) != null && (selectableCoordinates = selectable.getLayoutCoordinates()) != null && (offset = anchor.getOffset()) <= selectable.getLastVisibleOffset()) {
            Offset m1029getCurrentDragPosition_m7T9E = manager.m1029getCurrentDragPosition_m7T9E();
            Intrinsics.checkNotNull(m1029getCurrentDragPosition_m7T9E);
            long localDragPosition = selectableCoordinates.mo5024localPositionOfR5De75A(containerCoordinates, m1029getCurrentDragPosition_m7T9E.getPackedValue());
            float dragX = Offset.m3505getXimpl(localDragPosition);
            long lineRange = selectable.mo990getRangeOfLineContainingjx7JFs(offset);
            if (TextRange.m5565getCollapsedimpl(lineRange)) {
                lineStartX = selectable.getLineLeft(offset);
            } else {
                float lineStartX2 = selectable.getLineLeft(TextRange.m5571getStartimpl(lineRange));
                float lineEndX = selectable.getLineRight(TextRange.m5566getEndimpl(lineRange) - 1);
                float minX = Math.min(lineStartX2, lineEndX);
                float maxX = Math.max(lineStartX2, lineEndX);
                lineStartX = RangesKt.coerceIn(dragX, minX, maxX);
            }
            if (lineStartX == -1.0f) {
                return Offset.INSTANCE.m3520getUnspecifiedF1C5BW0();
            }
            if (Math.abs(dragX - lineStartX) > IntSize.m6264getWidthimpl(magnifierSize) / 2) {
                return Offset.INSTANCE.m3520getUnspecifiedF1C5BW0();
            }
            float lineCenterY = selectable.getCenterYForOffset(offset);
            return lineCenterY == -1.0f ? Offset.INSTANCE.m3520getUnspecifiedF1C5BW0() : containerCoordinates.mo5024localPositionOfR5De75A(selectableCoordinates, OffsetKt.Offset(lineStartX, lineCenterY));
        }
        return Offset.INSTANCE.m3520getUnspecifiedF1C5BW0();
    }

    public static final Rect visibleBounds(LayoutCoordinates $this$visibleBounds) {
        Rect boundsInWindow = LayoutCoordinatesKt.boundsInWindow($this$visibleBounds);
        return RectKt.m3543Rect0a9Yr6o($this$visibleBounds.mo5028windowToLocalMKHz9U(boundsInWindow.m3540getTopLeftF1C5BW0()), $this$visibleBounds.mo5028windowToLocalMKHz9U(boundsInWindow.m3534getBottomRightF1C5BW0()));
    }

    /* renamed from: containsInclusive-Uv8p0NA, reason: not valid java name */
    public static final boolean m1041containsInclusiveUv8p0NA(Rect $this$containsInclusive_u2dUv8p0NA, long offset) {
        float left = $this$containsInclusive_u2dUv8p0NA.getLeft();
        float right = $this$containsInclusive_u2dUv8p0NA.getRight();
        float m3505getXimpl = Offset.m3505getXimpl(offset);
        if (left <= m3505getXimpl && m3505getXimpl <= right) {
            float top = $this$containsInclusive_u2dUv8p0NA.getTop();
            float bottom = $this$containsInclusive_u2dUv8p0NA.getBottom();
            float m3506getYimpl = Offset.m3506getYimpl(offset);
            if (top <= m3506getYimpl && m3506getYimpl <= bottom) {
                return true;
            }
        }
        return false;
    }
}
