package androidx.compose.foundation.lazy.staggeredgrid;

import androidx.autofill.HintConstants;
import androidx.compose.foundation.lazy.layout.LazyLayoutMeasureScope;
import androidx.compose.foundation.lazy.layout.ObservableScopeInvalidator;
import androidx.compose.runtime.snapshots.Snapshot;
import androidx.compose.ui.layout.MeasureScope;
import androidx.compose.ui.layout.Placeable;
import androidx.compose.ui.unit.Constraints;
import androidx.compose.ui.unit.ConstraintsKt;
import androidx.compose.ui.unit.IntSizeKt;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import kotlin.Metadata;
import kotlin.Unit;
import kotlin.collections.ArrayDeque;
import kotlin.collections.ArraysKt;
import kotlin.collections.CollectionsKt;
import kotlin.jvm.functions.Function0;
import kotlin.jvm.functions.Function1;
import kotlin.jvm.internal.Intrinsics;
import kotlin.jvm.internal.Ref;
import kotlin.math.MathKt;
import kotlin.ranges.RangesKt;
import kotlinx.coroutines.CoroutineScope;

/* compiled from: LazyStaggeredGridMeasure.kt */
@Metadata(d1 = {"\u0000\u0098\u0001\n\u0000\n\u0002\u0010\u000b\n\u0000\n\u0002\u0010\b\n\u0000\n\u0002\u0010\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\u0010\u000e\n\u0002\b\u0003\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0010 \n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\b\u0005\n\u0002\u0010\u0011\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010\u0015\n\u0002\b\u000e\n\u0002\u0018\u0002\n\u0002\b\f\n\u0002\u0018\u0002\n\u0002\b\u0006\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0018\u0002\n\u0002\b\u0005\n\u0002\u0018\u0002\n\u0002\b\u0006\u001a\u0017\u0010\u0004\u001a\u00020\u00052\f\u0010\u0006\u001a\b\u0012\u0004\u0012\u00020\b0\u0007H\u0082\b\u001a5\u0010\t\u001a\u0002H\n\"\u0004\b\u0000\u0010\n2\u0006\u0010\u000b\u001a\u00020\f2\u0017\u0010\r\u001a\u0013\u0012\u0004\u0012\u00020\f\u0012\u0004\u0012\u0002H\n0\u000e¢\u0006\u0002\b\u000fH\u0083\b¢\u0006\u0002\u0010\u0010\u001aR\u0010\u0011\u001a\b\u0012\u0004\u0012\u00020\u00130\u0012*\u00020\u00142\u0012\u0010\u0015\u001a\u000e\u0012\u0004\u0012\u00020\u0013\u0012\u0004\u0012\u00020\u00050\u000e2!\u0010\u0016\u001a\u001d\u0012\u0013\u0012\u00110\u0003¢\u0006\f\b\u0017\u0012\b\b\u0018\u0012\u0004\b\b(\u0019\u0012\u0004\u0012\u00020\u00010\u000e2\u0006\u0010\u001a\u001a\u00020\u0001H\u0083\b\u001a;\u0010\u001b\u001a\b\u0012\u0004\u0012\u00020\u00130\u0012*\u00020\u00142\u0012\u0010\u001c\u001a\u000e\u0012\n\u0012\b\u0012\u0004\u0012\u00020\u00130\u001e0\u001d2\u0006\u0010\u001f\u001a\u00020 2\u0006\u0010!\u001a\u00020\u0003H\u0002¢\u0006\u0002\u0010\"\u001a\u001d\u0010#\u001a\u00020\b*\u000e\u0012\n\u0012\b\u0012\u0004\u0012\u00020\u00130\u001e0\u001dH\u0002¢\u0006\u0002\u0010$\u001a\u001c\u0010%\u001a\u00020\u0005*\u00020\u00142\u0006\u0010&\u001a\u00020 2\u0006\u0010'\u001a\u00020\u0003H\u0002\u001a7\u0010(\u001a\u00020\u0005\"\u0004\b\u0000\u0010\n*\b\u0012\u0004\u0012\u0002H\n0\u00122\b\b\u0002\u0010)\u001a\u00020\u00012\u0012\u0010*\u001a\u000e\u0012\u0004\u0012\u0002H\n\u0012\u0004\u0012\u00020\u00050\u000eH\u0082\b\u001a\u001c\u0010+\u001a\u00020\u0003*\u00020\u00142\u0006\u0010,\u001a\u00020\u00032\u0006\u0010-\u001a\u00020\u0003H\u0002\u001a+\u0010.\u001a\u00020\u0005*\u00020/2\u0012\u0010\r\u001a\u000e\u0012\u0004\u0012\u00020\u0003\u0012\u0004\u0012\u00020\u00050\u000eH\u0082\bø\u0001\u0000¢\u0006\u0004\b0\u00101\u001a\f\u00102\u001a\u00020\u0003*\u00020 H\u0002\u001a2\u00103\u001a\u00020\u0003\"\u0004\b\u0000\u0010\n*\b\u0012\u0004\u0012\u0002H\n0\u001d2\u0012\u0010\r\u001a\u000e\u0012\u0004\u0012\u0002H\n\u0012\u0004\u0012\u00020\u00030\u000eH\u0082\b¢\u0006\u0002\u00104\u001a\u0016\u00105\u001a\u00020\u0003*\u00020 2\b\b\u0002\u00106\u001a\u00020\u0003H\u0000\u001a\u001e\u00107\u001a\u00020\u0003*\u00020 2\u0006\u00108\u001a\u00020/H\u0002ø\u0001\u0000¢\u0006\u0004\b9\u0010:\u001a,\u0010;\u001a\u00020<*\u00020\u00142\u0006\u0010=\u001a\u00020\u00032\u0006\u0010>\u001a\u00020 2\u0006\u0010?\u001a\u00020 2\u0006\u0010@\u001a\u00020\u0001H\u0003\u001a\u0084\u0001\u0010A\u001a\u00020<*\u00020\f2\u0006\u0010B\u001a\u00020C2\f\u0010D\u001a\b\u0012\u0004\u0012\u00020\u00030\u00122\u0006\u0010E\u001a\u00020F2\u0006\u0010G\u001a\u00020H2\u0006\u0010I\u001a\u00020J2\u0006\u0010K\u001a\u00020\u00012\u0006\u0010L\u001a\u00020\u00012\u0006\u0010M\u001a\u00020N2\u0006\u0010O\u001a\u00020\u00032\u0006\u0010P\u001a\u00020\u00032\u0006\u0010Q\u001a\u00020\u00032\u0006\u0010R\u001a\u00020\u00032\u0006\u0010S\u001a\u00020TH\u0001ø\u0001\u0000¢\u0006\u0004\bU\u0010V\u001a\u0014\u0010W\u001a\u00020\u0005*\u00020 2\u0006\u0010X\u001a\u00020\u0003H\u0002\u001a!\u0010Y\u001a\u00020 *\u00020 2\u0012\u0010\r\u001a\u000e\u0012\u0004\u0012\u00020\u0003\u0012\u0004\u0012\u00020\u00030\u000eH\u0082\b\"\u000e\u0010\u0000\u001a\u00020\u0001X\u0082T¢\u0006\u0002\n\u0000\"\u000e\u0010\u0002\u001a\u00020\u0003X\u0082T¢\u0006\u0002\n\u0000\u0082\u0002\u0007\n\u0005\b¡\u001e0\u0001¨\u0006Z"}, d2 = {"DebugLoggingEnabled", "", "Unset", "", "debugLog", "", "message", "Lkotlin/Function0;", "", "withDebugLogging", "T", "scope", "Landroidx/compose/foundation/lazy/layout/LazyLayoutMeasureScope;", "block", "Lkotlin/Function1;", "Lkotlin/ExtensionFunctionType;", "(Landroidx/compose/foundation/lazy/layout/LazyLayoutMeasureScope;Lkotlin/jvm/functions/Function1;)Ljava/lang/Object;", "calculateExtraItems", "", "Landroidx/compose/foundation/lazy/staggeredgrid/LazyStaggeredGridMeasuredItem;", "Landroidx/compose/foundation/lazy/staggeredgrid/LazyStaggeredGridMeasureContext;", "position", "filter", "Lkotlin/ParameterName;", HintConstants.AUTOFILL_HINT_NAME, "itemIndex", "beforeVisibleBounds", "calculateVisibleItems", "measuredItems", "", "Lkotlin/collections/ArrayDeque;", "itemScrollOffsets", "", "mainAxisLayoutSize", "(Landroidx/compose/foundation/lazy/staggeredgrid/LazyStaggeredGridMeasureContext;[Lkotlin/collections/ArrayDeque;[II)Ljava/util/List;", "debugRender", "([Lkotlin/collections/ArrayDeque;)Ljava/lang/String;", "ensureIndicesInRange", "indices", "itemCount", "fastForEach", "reverse", "action", "findPreviousItemIndex", "item", "lane", "forEach", "Landroidx/compose/foundation/lazy/staggeredgrid/SpanRange;", "forEach-nIS5qE8", "(JLkotlin/jvm/functions/Function1;)V", "indexOfMaxValue", "indexOfMinBy", "([Ljava/lang/Object;Lkotlin/jvm/functions/Function1;)I", "indexOfMinValue", "minBound", "maxInRange", "indexRange", "maxInRange-jy6DScQ", "([IJ)I", "measure", "Landroidx/compose/foundation/lazy/staggeredgrid/LazyStaggeredGridMeasureResult;", "initialScrollDelta", "initialItemIndices", "initialItemOffsets", "canRestartMeasure", "measureStaggeredGrid", "state", "Landroidx/compose/foundation/lazy/staggeredgrid/LazyStaggeredGridState;", "pinnedItems", "itemProvider", "Landroidx/compose/foundation/lazy/staggeredgrid/LazyStaggeredGridItemProvider;", "resolvedSlots", "Landroidx/compose/foundation/lazy/staggeredgrid/LazyStaggeredGridSlots;", "constraints", "Landroidx/compose/ui/unit/Constraints;", "isVertical", "reverseLayout", "contentOffset", "Landroidx/compose/ui/unit/IntOffset;", "mainAxisAvailableSize", "mainAxisSpacing", "beforeContentPadding", "afterContentPadding", "coroutineScope", "Lkotlinx/coroutines/CoroutineScope;", "measureStaggeredGrid-sdzDtKU", "(Landroidx/compose/foundation/lazy/layout/LazyLayoutMeasureScope;Landroidx/compose/foundation/lazy/staggeredgrid/LazyStaggeredGridState;Ljava/util/List;Landroidx/compose/foundation/lazy/staggeredgrid/LazyStaggeredGridItemProvider;Landroidx/compose/foundation/lazy/staggeredgrid/LazyStaggeredGridSlots;JZZJIIIILkotlinx/coroutines/CoroutineScope;)Landroidx/compose/foundation/lazy/staggeredgrid/LazyStaggeredGridMeasureResult;", "offsetBy", "delta", "transform", "foundation_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class LazyStaggeredGridMeasureKt {
    private static final boolean DebugLoggingEnabled = false;
    private static final int Unset = Integer.MIN_VALUE;

    private static final <T> T withDebugLogging(LazyLayoutMeasureScope scope, Function1<? super LazyLayoutMeasureScope, ? extends T> function1) {
        return function1.invoke(scope);
    }

    private static final String debugRender(ArrayDeque<LazyStaggeredGridMeasuredItem>[] arrayDequeArr) {
        return "";
    }

    private static final void debugLog(Function0<String> function0) {
    }

    /* JADX WARN: Multi-variable type inference failed */
    /* JADX WARN: Type inference failed for: r0v17, types: [int[]] */
    /* JADX WARN: Type inference failed for: r0v18, types: [T] */
    /* JADX WARN: Type inference failed for: r0v23 */
    /* JADX WARN: Type inference failed for: r11v4, types: [int[]] */
    /* JADX WARN: Type inference failed for: r13v13 */
    /* JADX WARN: Type inference failed for: r13v14 */
    /* JADX WARN: Type inference failed for: r13v9, types: [T] */
    /* JADX WARN: Type inference failed for: r15v4 */
    /* JADX WARN: Type inference failed for: r15v5 */
    /* JADX WARN: Type inference failed for: r15v6 */
    /* JADX WARN: Type inference failed for: r15v7 */
    /* renamed from: measureStaggeredGrid-sdzDtKU, reason: not valid java name */
    public static final LazyStaggeredGridMeasureResult m763measureStaggeredGridsdzDtKU(LazyLayoutMeasureScope lazyLayoutMeasureScope, LazyStaggeredGridState lazyStaggeredGridState, List<Integer> list, LazyStaggeredGridItemProvider lazyStaggeredGridItemProvider, LazyStaggeredGridSlots lazyStaggeredGridSlots, long j, boolean z, boolean z2, long j2, int i, int i2, int i3, int i4, CoroutineScope coroutineScope) {
        Snapshot.Companion companion;
        int i5;
        int i6;
        int[] iArr;
        ?? r13;
        ?? r0;
        ?? r15;
        LazyStaggeredGridMeasureContext lazyStaggeredGridMeasureContext = new LazyStaggeredGridMeasureContext(lazyStaggeredGridState, list, lazyStaggeredGridItemProvider, lazyStaggeredGridSlots, j, z, lazyLayoutMeasureScope, i, j2, i3, i4, z2, i2, coroutineScope, null);
        Ref.ObjectRef objectRef = new Ref.ObjectRef();
        Ref.ObjectRef objectRef2 = new Ref.ObjectRef();
        Snapshot.Companion companion2 = Snapshot.INSTANCE;
        int i7 = 0;
        Snapshot createNonObservableSnapshot = companion2.createNonObservableSnapshot();
        try {
            Snapshot makeCurrent = createNonObservableSnapshot.makeCurrent();
            try {
                try {
                    int[] updateScrollPositionIfTheFirstItemWasMoved$foundation_release = lazyStaggeredGridState.updateScrollPositionIfTheFirstItemWasMoved$foundation_release(lazyStaggeredGridItemProvider, lazyStaggeredGridState.getScrollPosition().getIndices());
                    ?? scrollOffsets = lazyStaggeredGridState.getScrollPosition().getScrollOffsets();
                    if (updateScrollPositionIfTheFirstItemWasMoved$foundation_release.length == lazyStaggeredGridMeasureContext.getLaneCount()) {
                        r13 = updateScrollPositionIfTheFirstItemWasMoved$foundation_release;
                        companion = null;
                    } else {
                        lazyStaggeredGridMeasureContext.getLaneInfo().reset();
                        int[] iArr2 = new int[lazyStaggeredGridMeasureContext.getLaneCount()];
                        int length = iArr2.length;
                        int i8 = 0;
                        int[] iArr3 = iArr2;
                        while (i8 < length) {
                            Snapshot.Companion companion3 = companion2;
                            try {
                                if (i8 < updateScrollPositionIfTheFirstItemWasMoved$foundation_release.length) {
                                    i5 = i7;
                                    if (updateScrollPositionIfTheFirstItemWasMoved$foundation_release[i8] != -1) {
                                        try {
                                            i6 = updateScrollPositionIfTheFirstItemWasMoved$foundation_release[i8];
                                            iArr = iArr3;
                                            iArr2[i8] = i6;
                                            lazyStaggeredGridMeasureContext.getLaneInfo().setLane(iArr2[i8], i8);
                                            i8++;
                                            iArr3 = iArr;
                                            companion2 = companion3;
                                            i7 = i5;
                                        } catch (Throwable th) {
                                            th = th;
                                            createNonObservableSnapshot.restoreCurrent(makeCurrent);
                                            throw th;
                                        }
                                    }
                                } else {
                                    i5 = i7;
                                }
                                if (i8 == 0) {
                                    iArr = iArr3;
                                    i6 = 0;
                                } else {
                                    iArr = iArr3;
                                    i6 = m762maxInRangejy6DScQ(iArr2, SpanRange.m772constructorimpl(0, i8)) + 1;
                                }
                                iArr2[i8] = i6;
                                lazyStaggeredGridMeasureContext.getLaneInfo().setLane(iArr2[i8], i8);
                                i8++;
                                iArr3 = iArr;
                                companion2 = companion3;
                                i7 = i5;
                            } catch (Throwable th2) {
                                th = th2;
                                createNonObservableSnapshot.restoreCurrent(makeCurrent);
                                throw th;
                            }
                        }
                        companion = null;
                        r13 = iArr3;
                    }
                    objectRef.element = r13;
                    if (scrollOffsets.length == lazyStaggeredGridMeasureContext.getLaneCount()) {
                        r0 = scrollOffsets;
                    } else {
                        r0 = new int[lazyStaggeredGridMeasureContext.getLaneCount()];
                        int i9 = 0;
                        int length2 = r0.length;
                        while (i9 < length2) {
                            if (i9 < scrollOffsets.length) {
                                r15 = scrollOffsets[i9];
                            } else {
                                r15 = i9 == 0 ? companion : r0[i9 - 1];
                            }
                            r0[i9] = r15;
                            i9++;
                        }
                    }
                    objectRef2.element = r0;
                    Unit unit = Unit.INSTANCE;
                    createNonObservableSnapshot.restoreCurrent(makeCurrent);
                    createNonObservableSnapshot.dispose();
                    return measure(lazyStaggeredGridMeasureContext, MathKt.roundToInt(lazyStaggeredGridState.getScrollToBeConsumed()), (int[]) objectRef.element, (int[]) objectRef2.element, true);
                } catch (Throwable th3) {
                    th = th3;
                    createNonObservableSnapshot.dispose();
                    throw th;
                }
            } catch (Throwable th4) {
                th = th4;
            }
        } catch (Throwable th5) {
            th = th5;
        }
    }

    private static final LazyStaggeredGridMeasureResult measure(final LazyStaggeredGridMeasureContext $this$measure, int initialScrollDelta, int[] initialItemIndices, int[] initialItemOffsets, boolean canRestartMeasure) {
        int itemCount;
        boolean remeasureNeeded;
        ArrayDeque[] measuredItems;
        boolean z;
        String str;
        int i;
        int[] gaps;
        boolean z2;
        boolean z3;
        LazyStaggeredGridMeasureContext lazyStaggeredGridMeasureContext;
        int itemCount2;
        int[] currentItemIndices;
        int[] currentItemOffsets;
        int[] firstItemOffsets;
        int[] firstItemIndices;
        int maxOffset;
        int offsetValue;
        int[] firstItemOffsets2;
        int[] currentItemOffsets2;
        int maxOffset2;
        boolean z4;
        boolean canScrollForward;
        boolean z5;
        ArrayDeque[] measuredItems2;
        int[] firstItemIndices2;
        int itemCount3;
        boolean z6;
        int layoutHeight;
        boolean z7;
        List list;
        int scrollDelta;
        int maxOffsetLane;
        boolean gapDetected;
        int maxOffsetLane2;
        int toScrollBack;
        int[] currentItemOffsets3;
        int initialItemsMeasured;
        boolean gapDetected2;
        boolean gapDetected3;
        boolean gapDetected4;
        boolean z8;
        boolean remeasureNeeded2;
        ArrayDeque[] measuredItems3;
        int i2;
        LazyStaggeredGridMeasureContext lazyStaggeredGridMeasureContext2 = $this$measure;
        LazyLayoutMeasureScope scope$iv = $this$measure.getMeasureScope();
        int itemCount4 = $this$measure.getItemProvider().getItemCount();
        if (itemCount4 <= 0) {
            itemCount = itemCount4;
        } else {
            if ($this$measure.getLaneCount() != 0) {
                int scrollDelta2 = initialScrollDelta;
                int[] firstItemIndices3 = Arrays.copyOf(initialItemIndices, initialItemIndices.length);
                String str2 = "copyOf(this, size)";
                Intrinsics.checkNotNullExpressionValue(firstItemIndices3, "copyOf(this, size)");
                int[] firstItemOffsets3 = Arrays.copyOf(initialItemOffsets, initialItemOffsets.length);
                Intrinsics.checkNotNullExpressionValue(firstItemOffsets3, "copyOf(this, size)");
                boolean remeasureNeeded3 = false;
                ensureIndicesInRange(lazyStaggeredGridMeasureContext2, firstItemIndices3, itemCount4);
                offsetBy(firstItemOffsets3, -scrollDelta2);
                int laneCount = $this$measure.getLaneCount();
                ArrayDeque[] arrayDequeArr = new ArrayDeque[laneCount];
                for (int i3 = 0; i3 < laneCount; i3++) {
                    arrayDequeArr[i3] = new ArrayDeque(16);
                }
                ArrayDeque[] measuredItems4 = arrayDequeArr;
                offsetBy(firstItemOffsets3, -$this$measure.getBeforeContentPadding());
                int laneToCheckForGaps = -1;
                while (true) {
                    if (!measure$lambda$38$hasSpaceBeforeFirst(firstItemIndices3, firstItemOffsets3, lazyStaggeredGridMeasureContext2)) {
                        remeasureNeeded = remeasureNeeded3;
                        measuredItems = measuredItems4;
                        break;
                    }
                    int laneIndex = indexOfMaxValue(firstItemIndices3);
                    int itemIndex = firstItemIndices3[laneIndex];
                    int length = firstItemOffsets3.length;
                    for (int i4 = 0; i4 < length; i4++) {
                        if (firstItemIndices3[i4] != firstItemIndices3[laneIndex] && firstItemOffsets3[i4] < firstItemOffsets3[laneIndex]) {
                            firstItemOffsets3[i4] = firstItemOffsets3[laneIndex];
                        }
                    }
                    int previousItemIndex = findPreviousItemIndex(lazyStaggeredGridMeasureContext2, itemIndex, laneIndex);
                    if (previousItemIndex < 0) {
                        laneToCheckForGaps = laneIndex;
                        remeasureNeeded = remeasureNeeded3;
                        measuredItems = measuredItems4;
                        break;
                    }
                    int laneToCheckForGaps2 = laneToCheckForGaps;
                    long spanRange = lazyStaggeredGridMeasureContext2.m759getSpanRangelOCCd4c($this$measure.getItemProvider(), previousItemIndex, laneIndex);
                    LazyStaggeredGridLaneInfo laneInfo = $this$measure.getLaneInfo();
                    if (((int) (spanRange & 4294967295L)) - ((int) (spanRange >> 32)) != 1) {
                        remeasureNeeded2 = remeasureNeeded3;
                        measuredItems3 = measuredItems4;
                        i2 = -2;
                    } else {
                        remeasureNeeded2 = remeasureNeeded3;
                        measuredItems3 = measuredItems4;
                        i2 = (int) (spanRange >> 32);
                    }
                    laneInfo.setLane(previousItemIndex, i2);
                    LazyStaggeredGridMeasuredItem measuredItem = $this$measure.getMeasuredItemProvider().m767getAndMeasurejy6DScQ(previousItemIndex, spanRange);
                    int offset = m762maxInRangejy6DScQ(firstItemOffsets3, spanRange);
                    long $this$isFullSpan$iv = spanRange >> 32;
                    int[] gaps2 = ((int) (spanRange & 4294967295L)) - ((int) $this$isFullSpan$iv) != 1 ? $this$measure.getLaneInfo().getGaps(previousItemIndex) : null;
                    int i$iv = (int) (spanRange >> 32);
                    int i5 = (int) (spanRange & 4294967295L);
                    for (int i$iv2 = i$iv; i$iv2 < i5; i$iv2++) {
                        int lane = i$iv2;
                        firstItemIndices3[lane] = previousItemIndex;
                        int gap = gaps2 == null ? 0 : gaps2[lane];
                        int newOffset = offset + measuredItem.getSizeWithSpacings() + gap;
                        firstItemOffsets3[lane] = newOffset;
                        if ($this$measure.getMainAxisAvailableSize() + newOffset <= 0) {
                            remeasureNeeded2 = true;
                        }
                    }
                    remeasureNeeded3 = remeasureNeeded2;
                    laneToCheckForGaps = laneToCheckForGaps2;
                    measuredItems4 = measuredItems3;
                }
                int $i$f$debugLog = $this$measure.getBeforeContentPadding();
                int minOffset = -$i$f$debugLog;
                if (firstItemOffsets3[0] < minOffset) {
                    scrollDelta2 += firstItemOffsets3[0];
                    offsetBy(firstItemOffsets3, minOffset - firstItemOffsets3[0]);
                }
                int $i$f$debugLog2 = $this$measure.getBeforeContentPadding();
                offsetBy(firstItemOffsets3, $i$f$debugLog2);
                int laneToCheckForGaps3 = laneToCheckForGaps == -1 ? ArraysKt.indexOf(firstItemIndices3, 0) : laneToCheckForGaps;
                if (laneToCheckForGaps3 != -1 && measure$lambda$38$misalignedStart(firstItemIndices3, lazyStaggeredGridMeasureContext2, firstItemOffsets3, laneToCheckForGaps3) && canRestartMeasure) {
                    $this$measure.getLaneInfo().reset();
                    int length2 = firstItemIndices3.length;
                    int[] iArr = new int[length2];
                    for (int i6 = 0; i6 < length2; i6++) {
                        iArr[i6] = -1;
                    }
                    int length3 = firstItemOffsets3.length;
                    int[] iArr2 = new int[length3];
                    for (int i7 = 0; i7 < length3; i7++) {
                        iArr2[i7] = firstItemOffsets3[laneToCheckForGaps3];
                    }
                    return measure(lazyStaggeredGridMeasureContext2, scrollDelta2, iArr, iArr2, false);
                }
                int[] currentItemIndices2 = Arrays.copyOf(firstItemIndices3, firstItemIndices3.length);
                Intrinsics.checkNotNullExpressionValue(currentItemIndices2, "copyOf(this, size)");
                int length4 = firstItemOffsets3.length;
                int[] iArr3 = new int[length4];
                for (int i8 = 0; i8 < length4; i8++) {
                    iArr3[i8] = -firstItemOffsets3[i8];
                }
                int[] currentItemOffsets4 = iArr3;
                int minVisibleOffset = $this$measure.getMainAxisSpacing() + minOffset;
                int maxOffset3 = RangesKt.coerceAtLeast($this$measure.getMainAxisAvailableSize() + $this$measure.getAfterContentPadding(), 0);
                int initialItemsMeasured2 = 0;
                int initialLaneToMeasure = indexOfMinValue$default(currentItemIndices2, 0, 1, null);
                boolean remeasureNeeded4 = remeasureNeeded;
                while (initialLaneToMeasure != -1 && initialItemsMeasured2 < $this$measure.getLaneCount()) {
                    int itemIndex2 = currentItemIndices2[initialLaneToMeasure];
                    int laneIndex2 = initialLaneToMeasure;
                    initialLaneToMeasure = indexOfMinValue(currentItemIndices2, itemIndex2);
                    initialItemsMeasured2++;
                    if (itemIndex2 >= 0) {
                        int laneToCheckForGaps4 = laneToCheckForGaps3;
                        boolean remeasureNeeded5 = remeasureNeeded4;
                        long spanRange2 = lazyStaggeredGridMeasureContext2.m759getSpanRangelOCCd4c($this$measure.getItemProvider(), itemIndex2, laneIndex2);
                        LazyStaggeredGridMeasuredItem measuredItem2 = $this$measure.getMeasuredItemProvider().m767getAndMeasurejy6DScQ(itemIndex2, spanRange2);
                        int scrollDelta3 = scrollDelta2;
                        int minOffset2 = minOffset;
                        int[] firstItemIndices4 = firstItemIndices3;
                        $this$measure.getLaneInfo().setLane(itemIndex2, ((int) (spanRange2 & 4294967295L)) - ((int) (spanRange2 >> 32)) != 1 ? -2 : (int) (spanRange2 >> 32));
                        int offset2 = m762maxInRangejy6DScQ(currentItemOffsets4, spanRange2);
                        String str3 = str2;
                        int[] firstItemOffsets4 = firstItemOffsets3;
                        long $this$forEach_u2dnIS5qE8$iv = spanRange2 & 4294967295L;
                        int i9 = (int) $this$forEach_u2dnIS5qE8$iv;
                        for (int i$iv3 = (int) (spanRange2 >> 32); i$iv3 < i9; i$iv3++) {
                            int lane2 = i$iv3;
                            currentItemOffsets4[lane2] = measuredItem2.getSizeWithSpacings() + offset2;
                            currentItemIndices2[lane2] = itemIndex2;
                            measuredItems[lane2].addLast(measuredItem2);
                        }
                        if (offset2 < minVisibleOffset && currentItemOffsets4[(int) (spanRange2 >> 32)] <= minVisibleOffset) {
                            measuredItem2.setVisible(false);
                            remeasureNeeded5 = true;
                        }
                        long $this$isFullSpan$iv2 = spanRange2 >> 32;
                        if (((int) (spanRange2 & 4294967295L)) - ((int) $this$isFullSpan$iv2) != 1) {
                            initialItemsMeasured2 = $this$measure.getLaneCount();
                            lazyStaggeredGridMeasureContext2 = $this$measure;
                            initialLaneToMeasure = initialLaneToMeasure;
                            str2 = str3;
                            laneToCheckForGaps3 = laneToCheckForGaps4;
                            remeasureNeeded4 = remeasureNeeded5;
                            firstItemOffsets3 = firstItemOffsets4;
                            firstItemIndices3 = firstItemIndices4;
                            scrollDelta2 = scrollDelta3;
                            minOffset = minOffset2;
                        } else {
                            lazyStaggeredGridMeasureContext2 = $this$measure;
                            initialLaneToMeasure = initialLaneToMeasure;
                            initialItemsMeasured2 = initialItemsMeasured2;
                            str2 = str3;
                            laneToCheckForGaps3 = laneToCheckForGaps4;
                            remeasureNeeded4 = remeasureNeeded5;
                            firstItemOffsets3 = firstItemOffsets4;
                            firstItemIndices3 = firstItemIndices4;
                            scrollDelta2 = scrollDelta3;
                            minOffset = minOffset2;
                        }
                    } else {
                        lazyStaggeredGridMeasureContext2 = $this$measure;
                    }
                }
                int scrollDelta4 = scrollDelta2;
                int minOffset3 = minOffset;
                int[] firstItemIndices5 = firstItemIndices3;
                String str4 = str2;
                int[] firstItemOffsets5 = firstItemOffsets3;
                boolean remeasureNeeded6 = remeasureNeeded4;
                while (true) {
                    int[] $this$any$iv = currentItemOffsets4;
                    int length5 = $this$any$iv.length;
                    int i10 = 0;
                    while (true) {
                        if (i10 >= length5) {
                            z = false;
                            break;
                        }
                        int element$iv = $this$any$iv[i10];
                        if (element$iv < maxOffset3 || element$iv <= 0) {
                            z = true;
                            break;
                        }
                        i10++;
                    }
                    if (!z) {
                        ArrayDeque[] arrayDequeArr2 = measuredItems;
                        int length6 = arrayDequeArr2.length;
                        int i11 = 0;
                        while (true) {
                            if (i11 >= length6) {
                                z8 = true;
                                break;
                            }
                            if (!arrayDequeArr2[i11].isEmpty()) {
                                z8 = false;
                                break;
                            }
                            i11++;
                        }
                        if (!z8) {
                            break;
                        }
                    }
                    int currentLaneIndex = indexOfMinValue$default(currentItemOffsets4, 0, 1, null);
                    int itemIndex3 = ArraysKt.maxOrThrow(currentItemIndices2) + 1;
                    if (itemIndex3 >= itemCount4) {
                        break;
                    }
                    int itemCount5 = itemCount4;
                    int[] currentItemIndices3 = currentItemIndices2;
                    int[] currentItemOffsets5 = currentItemOffsets4;
                    int minVisibleOffset2 = minVisibleOffset;
                    String str5 = str4;
                    ArrayDeque[] measuredItems5 = measuredItems;
                    int[] firstItemOffsets6 = firstItemOffsets5;
                    int[] firstItemIndices6 = firstItemIndices5;
                    int initialLaneToMeasure2 = initialLaneToMeasure;
                    int initialItemsMeasured3 = initialItemsMeasured2;
                    int initialItemsMeasured4 = scrollDelta4;
                    int scrollDelta5 = maxOffset3;
                    long spanRange3 = $this$measure.m759getSpanRangelOCCd4c($this$measure.getItemProvider(), itemIndex3, currentLaneIndex);
                    LazyStaggeredGridLaneInfo laneInfo2 = $this$measure.getLaneInfo();
                    if (((int) (spanRange3 & 4294967295L)) - ((int) (spanRange3 >> 32)) != 1) {
                        str = str5;
                        i = -2;
                    } else {
                        str = str5;
                        i = (int) (spanRange3 >> 32);
                    }
                    laneInfo2.setLane(itemIndex3, i);
                    LazyStaggeredGridMeasuredItem measuredItem3 = $this$measure.getMeasuredItemProvider().m767getAndMeasurejy6DScQ(itemIndex3, spanRange3);
                    int offset3 = m762maxInRangejy6DScQ(currentItemOffsets5, spanRange3);
                    long $this$isFullSpan$iv3 = spanRange3 >> 32;
                    if (((int) (spanRange3 & 4294967295L)) - ((int) $this$isFullSpan$iv3) != 1) {
                        gaps = $this$measure.getLaneInfo().getGaps(itemIndex3);
                        if (gaps == null) {
                            gaps = new int[$this$measure.getLaneCount()];
                        }
                    } else {
                        gaps = null;
                    }
                    int $i$f$unpackInt1 = (int) (spanRange3 >> 32);
                    long $this$forEach_u2dnIS5qE8$iv2 = spanRange3 & 4294967295L;
                    int i12 = (int) $this$forEach_u2dnIS5qE8$iv2;
                    for (int i$iv4 = $i$f$unpackInt1; i$iv4 < i12; i$iv4++) {
                        int lane3 = i$iv4;
                        if (gaps != null) {
                            gaps[lane3] = offset3 - currentItemOffsets5[lane3];
                        }
                        currentItemIndices3[lane3] = itemIndex3;
                        currentItemOffsets5[lane3] = measuredItem3.getSizeWithSpacings() + offset3;
                        measuredItems5[lane3].addLast(measuredItem3);
                    }
                    $this$measure.getLaneInfo().setGaps(itemIndex3, gaps);
                    if (offset3 >= minVisibleOffset2 || currentItemOffsets5[(int) (spanRange3 >> 32)] > minVisibleOffset2) {
                        currentItemOffsets4 = currentItemOffsets5;
                        minVisibleOffset = minVisibleOffset2;
                        str4 = str;
                        initialLaneToMeasure = initialLaneToMeasure2;
                        initialItemsMeasured2 = initialItemsMeasured3;
                        measuredItems = measuredItems5;
                        maxOffset3 = scrollDelta5;
                        firstItemOffsets5 = firstItemOffsets6;
                        currentItemIndices2 = currentItemIndices3;
                        firstItemIndices5 = firstItemIndices6;
                        itemCount4 = itemCount5;
                        scrollDelta4 = initialItemsMeasured4;
                    } else {
                        measuredItem3.setVisible(false);
                        currentItemOffsets4 = currentItemOffsets5;
                        minVisibleOffset = minVisibleOffset2;
                        str4 = str;
                        initialLaneToMeasure = initialLaneToMeasure2;
                        initialItemsMeasured2 = initialItemsMeasured3;
                        measuredItems = measuredItems5;
                        maxOffset3 = scrollDelta5;
                        firstItemOffsets5 = firstItemOffsets6;
                        currentItemIndices2 = currentItemIndices3;
                        firstItemIndices5 = firstItemIndices6;
                        itemCount4 = itemCount5;
                        scrollDelta4 = initialItemsMeasured4;
                    }
                }
                ArrayDeque[] measuredItems6 = measuredItems;
                int length7 = measuredItems6.length;
                for (int laneIndex3 = 0; laneIndex3 < length7; laneIndex3++) {
                    ArrayDeque laneItems = measuredItems6[laneIndex3];
                    while (laneItems.size() > 1 && !((LazyStaggeredGridMeasuredItem) laneItems.first()).getIsVisible()) {
                        LazyStaggeredGridMeasuredItem item = (LazyStaggeredGridMeasuredItem) laneItems.removeFirst();
                        int[] gaps3 = item.getSpan() != 1 ? $this$measure.getLaneInfo().getGaps(item.getIndex()) : null;
                        firstItemOffsets5[laneIndex3] = firstItemOffsets5[laneIndex3] - (item.getSizeWithSpacings() + (gaps3 == null ? 0 : gaps3[laneIndex3]));
                    }
                    LazyStaggeredGridMeasuredItem lazyStaggeredGridMeasuredItem = (LazyStaggeredGridMeasuredItem) laneItems.firstOrNull();
                    firstItemIndices5[laneIndex3] = lazyStaggeredGridMeasuredItem != null ? lazyStaggeredGridMeasuredItem.getIndex() : -1;
                }
                int[] $this$any$iv2 = currentItemIndices2;
                int length8 = $this$any$iv2.length;
                int i13 = 0;
                while (true) {
                    if (i13 >= length8) {
                        z2 = false;
                        break;
                    }
                    int element$iv2 = $this$any$iv2[i13];
                    int it = element$iv2 == itemCount4 + (-1) ? 1 : 0;
                    if (it != 0) {
                        z2 = true;
                        break;
                    }
                    i13++;
                }
                if (z2) {
                    offsetBy(currentItemOffsets4, -$this$measure.getMainAxisSpacing());
                }
                int[] $this$all$iv = currentItemOffsets4;
                int length9 = $this$all$iv.length;
                int i14 = 0;
                while (true) {
                    if (i14 >= length9) {
                        z3 = true;
                        break;
                    }
                    int element$iv3 = $this$all$iv[i14];
                    int it2 = element$iv3 < $this$measure.getMainAxisAvailableSize() ? 1 : 0;
                    if (it2 == 0) {
                        z3 = false;
                        break;
                    }
                    i14++;
                }
                if (z3) {
                    int maxOffsetLane3 = indexOfMaxValue(currentItemOffsets4);
                    int toScrollBack2 = $this$measure.getMainAxisAvailableSize() - currentItemOffsets4[maxOffsetLane3];
                    firstItemOffsets = firstItemOffsets5;
                    offsetBy(firstItemOffsets, -toScrollBack2);
                    offsetBy(currentItemOffsets4, toScrollBack2);
                    boolean gapDetected5 = false;
                    while (true) {
                        int length10 = firstItemOffsets.length;
                        int i15 = 0;
                        while (true) {
                            if (i15 >= length10) {
                                maxOffsetLane = maxOffsetLane3;
                                gapDetected = gapDetected5;
                                maxOffsetLane2 = 0;
                                break;
                            }
                            int element$iv4 = firstItemOffsets[i15];
                            maxOffsetLane = maxOffsetLane3;
                            gapDetected = gapDetected5;
                            if (element$iv4 < $this$measure.getBeforeContentPadding()) {
                                maxOffsetLane2 = 1;
                                break;
                            }
                            i15++;
                            maxOffsetLane3 = maxOffsetLane;
                            gapDetected5 = gapDetected;
                        }
                        if (maxOffsetLane2 == 0) {
                            lazyStaggeredGridMeasureContext = $this$measure;
                            toScrollBack = toScrollBack2;
                            itemCount2 = itemCount4;
                            currentItemIndices = currentItemIndices2;
                            currentItemOffsets3 = currentItemOffsets4;
                            firstItemIndices = firstItemIndices5;
                            initialItemsMeasured = scrollDelta4;
                            maxOffset = maxOffset3;
                            gapDetected2 = gapDetected;
                            break;
                        }
                        int laneIndex4 = indexOfMinValue$default(firstItemOffsets, 0, 1, null);
                        int nextLaneIndex = indexOfMaxValue(firstItemIndices5);
                        if (laneIndex4 == nextLaneIndex) {
                            gapDetected3 = gapDetected;
                        } else if (firstItemOffsets[laneIndex4] == firstItemOffsets[nextLaneIndex]) {
                            laneIndex4 = nextLaneIndex;
                            gapDetected3 = gapDetected;
                        } else {
                            gapDetected3 = true;
                        }
                        int currentIndex = firstItemIndices5[laneIndex4] == -1 ? itemCount4 : firstItemIndices5[laneIndex4];
                        lazyStaggeredGridMeasureContext = $this$measure;
                        int previousIndex = findPreviousItemIndex(lazyStaggeredGridMeasureContext, currentIndex, laneIndex4);
                        if (previousIndex < 0) {
                            if (gapDetected3) {
                                firstItemIndices = firstItemIndices5;
                            } else {
                                firstItemIndices = firstItemIndices5;
                                if (!measure$lambda$38$misalignedStart(firstItemIndices, lazyStaggeredGridMeasureContext, firstItemOffsets, laneIndex4)) {
                                    gapDetected4 = gapDetected3;
                                    initialItemsMeasured = scrollDelta4;
                                    toScrollBack = toScrollBack2;
                                    itemCount2 = itemCount4;
                                    currentItemIndices = currentItemIndices2;
                                    currentItemOffsets3 = currentItemOffsets4;
                                    maxOffset = maxOffset3;
                                    gapDetected2 = gapDetected4;
                                }
                            }
                            if (canRestartMeasure) {
                                $this$measure.getLaneInfo().reset();
                                int length11 = firstItemIndices.length;
                                int[] iArr4 = new int[length11];
                                for (int initialLaneToMeasure3 = 0; initialLaneToMeasure3 < length11; initialLaneToMeasure3++) {
                                    iArr4[initialLaneToMeasure3] = -1;
                                }
                                int length12 = firstItemOffsets.length;
                                int[] iArr5 = new int[length12];
                                for (int initialItemsMeasured5 = 0; initialItemsMeasured5 < length12; initialItemsMeasured5++) {
                                    iArr5[initialItemsMeasured5] = firstItemOffsets[laneIndex4];
                                }
                                return measure(lazyStaggeredGridMeasureContext, scrollDelta4, iArr4, iArr5, false);
                            }
                            gapDetected4 = gapDetected3;
                            initialItemsMeasured = scrollDelta4;
                            toScrollBack = toScrollBack2;
                            itemCount2 = itemCount4;
                            currentItemIndices = currentItemIndices2;
                            currentItemOffsets3 = currentItemOffsets4;
                            maxOffset = maxOffset3;
                            gapDetected2 = gapDetected4;
                        } else {
                            boolean gapDetected6 = gapDetected3;
                            int initialLaneToMeasure4 = initialLaneToMeasure;
                            int initialItemsMeasured6 = initialItemsMeasured2;
                            int[] firstItemIndices7 = firstItemIndices5;
                            int initialItemsMeasured7 = scrollDelta4;
                            int minVisibleOffset3 = minVisibleOffset;
                            int maxOffset4 = maxOffset3;
                            long spanRange4 = lazyStaggeredGridMeasureContext.m759getSpanRangelOCCd4c($this$measure.getItemProvider(), previousIndex, laneIndex4);
                            int[] currentItemIndices4 = currentItemIndices2;
                            int[] currentItemOffsets6 = currentItemOffsets4;
                            $this$measure.getLaneInfo().setLane(previousIndex, ((int) (spanRange4 & 4294967295L)) - ((int) (spanRange4 >> 32)) != 1 ? -2 : (int) (spanRange4 >> 32));
                            LazyStaggeredGridMeasuredItem measuredItem4 = $this$measure.getMeasuredItemProvider().m767getAndMeasurejy6DScQ(previousIndex, spanRange4);
                            int offset4 = m762maxInRangejy6DScQ(firstItemOffsets, spanRange4);
                            int toScrollBack3 = toScrollBack2;
                            int itemCount6 = itemCount4;
                            long $this$isFullSpan$iv4 = spanRange4 >> 32;
                            int[] gaps4 = ((int) (spanRange4 & 4294967295L)) - ((int) $this$isFullSpan$iv4) != 1 ? $this$measure.getLaneInfo().getGaps(previousIndex) : null;
                            long $this$forEach_u2dnIS5qE8$iv3 = spanRange4 & 4294967295L;
                            int i16 = (int) $this$forEach_u2dnIS5qE8$iv3;
                            for (int i$iv5 = (int) (spanRange4 >> 32); i$iv5 < i16; i$iv5++) {
                                int lane4 = i$iv5;
                                if (firstItemOffsets[lane4] != offset4) {
                                    gapDetected6 = true;
                                }
                                measuredItems6[lane4].addFirst(measuredItem4);
                                firstItemIndices7[lane4] = previousIndex;
                                int gap2 = gaps4 == null ? 0 : gaps4[lane4];
                                firstItemOffsets[lane4] = offset4 + measuredItem4.getSizeWithSpacings() + gap2;
                            }
                            firstItemIndices5 = firstItemIndices7;
                            maxOffset3 = maxOffset4;
                            scrollDelta4 = initialItemsMeasured7;
                            gapDetected5 = gapDetected6;
                            maxOffsetLane3 = maxOffsetLane;
                            toScrollBack2 = toScrollBack3;
                            initialLaneToMeasure = initialLaneToMeasure4;
                            initialItemsMeasured2 = initialItemsMeasured6;
                            itemCount4 = itemCount6;
                            currentItemIndices2 = currentItemIndices4;
                            minVisibleOffset = minVisibleOffset3;
                            currentItemOffsets4 = currentItemOffsets6;
                        }
                    }
                    if (gapDetected2 && canRestartMeasure) {
                        $this$measure.getLaneInfo().reset();
                        return measure(lazyStaggeredGridMeasureContext, initialItemsMeasured, firstItemIndices, firstItemOffsets, false);
                    }
                    int scrollDelta6 = initialItemsMeasured + toScrollBack;
                    int minOffsetLane = indexOfMinValue$default(firstItemOffsets, 0, 1, null);
                    if (firstItemOffsets[minOffsetLane] < 0) {
                        int offsetValue2 = firstItemOffsets[minOffsetLane];
                        currentItemOffsets = currentItemOffsets3;
                        offsetBy(currentItemOffsets, offsetValue2);
                        offsetBy(firstItemOffsets, -offsetValue2);
                        offsetValue = scrollDelta6 + offsetValue2;
                    } else {
                        currentItemOffsets = currentItemOffsets3;
                        offsetValue = scrollDelta6;
                    }
                } else {
                    lazyStaggeredGridMeasureContext = $this$measure;
                    itemCount2 = itemCount4;
                    currentItemIndices = currentItemIndices2;
                    currentItemOffsets = currentItemOffsets4;
                    firstItemOffsets = firstItemOffsets5;
                    firstItemIndices = firstItemIndices5;
                    maxOffset = maxOffset3;
                    int initialItemsMeasured8 = scrollDelta4;
                    offsetValue = initialItemsMeasured8;
                }
                float consumedScroll = (MathKt.getSign(MathKt.roundToInt($this$measure.getState().getScrollToBeConsumed())) != MathKt.getSign(offsetValue) || Math.abs(MathKt.roundToInt($this$measure.getState().getScrollToBeConsumed())) < Math.abs(offsetValue)) ? $this$measure.getState().getScrollToBeConsumed() : offsetValue;
                int[] $this$transform$iv = Arrays.copyOf(firstItemOffsets, firstItemOffsets.length);
                Intrinsics.checkNotNullExpressionValue($this$transform$iv, str4);
                int length13 = $this$transform$iv.length;
                for (int i$iv6 = 0; i$iv6 < length13; i$iv6++) {
                    int it3 = $this$transform$iv[i$iv6];
                    $this$transform$iv[i$iv6] = -it3;
                }
                int $i$f$debugLog3 = $this$measure.getBeforeContentPadding();
                if ($i$f$debugLog3 > $this$measure.getMainAxisSpacing()) {
                    int laneIndex5 = 0;
                    int length14 = measuredItems6.length;
                    while (laneIndex5 < length14) {
                        ArrayDeque laneItems2 = measuredItems6[laneIndex5];
                        int i17 = 0;
                        int size = laneItems2.size();
                        while (true) {
                            if (i17 >= size) {
                                scrollDelta = offsetValue;
                                break;
                            }
                            LazyStaggeredGridMeasuredItem item2 = (LazyStaggeredGridMeasuredItem) laneItems2.get(i17);
                            scrollDelta = offsetValue;
                            int[] gaps5 = $this$measure.getLaneInfo().getGaps(item2.getIndex());
                            int size2 = item2.getSizeWithSpacings() + (gaps5 == null ? 0 : gaps5[laneIndex5]);
                            if (i17 != CollectionsKt.getLastIndex(laneItems2) && firstItemOffsets[laneIndex5] != 0 && firstItemOffsets[laneIndex5] >= size2) {
                                firstItemOffsets[laneIndex5] = firstItemOffsets[laneIndex5] - size2;
                                firstItemIndices[laneIndex5] = ((LazyStaggeredGridMeasuredItem) laneItems2.get(i17 + 1)).getIndex();
                                i17++;
                                offsetValue = scrollDelta;
                            }
                        }
                        laneIndex5++;
                        offsetValue = scrollDelta;
                    }
                }
                int $i$f$debugLog4 = $this$measure.getBeforeContentPadding();
                int contentPadding = $i$f$debugLog4 + $this$measure.getAfterContentPadding();
                int layoutWidth = $this$measure.getIsVertical() ? Constraints.m6050getMaxWidthimpl($this$measure.getConstraints()) : ConstraintsKt.m6064constrainWidthK40F9xA($this$measure.getConstraints(), ArraysKt.maxOrThrow(currentItemOffsets) + contentPadding);
                int layoutHeight2 = $this$measure.getIsVertical() ? ConstraintsKt.m6063constrainHeightK40F9xA($this$measure.getConstraints(), ArraysKt.maxOrThrow(currentItemOffsets) + contentPadding) : Constraints.m6049getMaxHeightimpl($this$measure.getConstraints());
                int it4 = Math.min($this$measure.getIsVertical() ? layoutHeight2 : layoutWidth, $this$measure.getMainAxisAvailableSize());
                int mainAxisLayoutSize = (it4 - $this$measure.getBeforeContentPadding()) + $this$measure.getAfterContentPadding();
                int extraItemOffset = $this$transform$iv[0];
                boolean beforeVisibleBounds$iv = true;
                int $i$f$calculateExtraItems = 0;
                List list2 = null;
                List $this$fastForEachReversed$iv$iv$iv = $this$measure.getPinnedItems();
                int size3 = $this$fastForEachReversed$iv$iv$iv.size() - 1;
                if (size3 >= 0) {
                    while (true) {
                        int index$iv$iv$iv = size3;
                        size3--;
                        int contentPadding2 = contentPadding;
                        List $this$fastForEachReversed$iv$iv$iv2 = $this$fastForEachReversed$iv$iv$iv;
                        int $i$f$calculateExtraItems2 = $i$f$calculateExtraItems;
                        Object item$iv$iv$iv = $this$fastForEachReversed$iv$iv$iv2.get(index$iv$iv$iv);
                        int index$iv = ((Number) item$iv$iv$iv).intValue();
                        boolean beforeVisibleBounds$iv2 = beforeVisibleBounds$iv;
                        int lane5 = $this$measure.getLaneInfo().getLane(index$iv);
                        switch (lane5) {
                            case -2:
                            case -1:
                                int[] $this$all$iv2 = firstItemIndices;
                                firstItemOffsets2 = firstItemOffsets;
                                maxOffset2 = maxOffset;
                                int length15 = $this$all$iv2.length;
                                currentItemOffsets2 = currentItemOffsets;
                                int i18 = 0;
                                while (true) {
                                    if (i18 >= length15) {
                                        z7 = true;
                                        break;
                                    } else {
                                        int element$iv5 = $this$all$iv2[i18];
                                        int i19 = length15;
                                        int it5 = element$iv5 > index$iv ? 1 : 0;
                                        if (it5 == 0) {
                                            z7 = false;
                                            break;
                                        } else {
                                            i18++;
                                            length15 = i19;
                                        }
                                    }
                                }
                            default:
                                firstItemOffsets2 = firstItemOffsets;
                                currentItemOffsets2 = currentItemOffsets;
                                maxOffset2 = maxOffset;
                                if (firstItemIndices[lane5] > index$iv) {
                                    z7 = true;
                                    break;
                                } else {
                                    z7 = false;
                                    break;
                                }
                        }
                        if (z7) {
                            long spanRange$iv = $this$measure.m759getSpanRangelOCCd4c($this$measure.getItemProvider(), index$iv, 0);
                            if (list2 == null) {
                                Object result$iv = new ArrayList();
                                list = (List) result$iv;
                            } else {
                                list = list2;
                            }
                            LazyStaggeredGridMeasuredItem measuredItem$iv = $this$measure.getMeasuredItemProvider().m767getAndMeasurejy6DScQ(index$iv, spanRange$iv);
                            extraItemOffset -= measuredItem$iv.getSizeWithSpacings();
                            measuredItem$iv.position(extraItemOffset, 0, mainAxisLayoutSize);
                            list.add(measuredItem$iv);
                            list2 = list;
                        }
                        if (size3 >= 0) {
                            $i$f$calculateExtraItems = $i$f$calculateExtraItems2;
                            $this$fastForEachReversed$iv$iv$iv = $this$fastForEachReversed$iv$iv$iv2;
                            beforeVisibleBounds$iv = beforeVisibleBounds$iv2;
                            contentPadding = contentPadding2;
                            maxOffset = maxOffset2;
                            firstItemOffsets = firstItemOffsets2;
                            currentItemOffsets = currentItemOffsets2;
                        }
                    }
                } else {
                    firstItemOffsets2 = firstItemOffsets;
                    currentItemOffsets2 = currentItemOffsets;
                    maxOffset2 = maxOffset;
                }
                if (list2 == null) {
                    list2 = CollectionsKt.emptyList();
                }
                List extraItemsBefore = list2;
                List visibleItems = calculateVisibleItems(lazyStaggeredGridMeasureContext, measuredItems6, $this$transform$iv, mainAxisLayoutSize);
                int extraItemOffset2 = $this$transform$iv[0];
                int layoutHeight3 = 0;
                List list3 = null;
                List $this$fastForEach$iv$iv = $this$measure.getPinnedItems();
                List $this$fastForEach$iv$iv$iv = $this$fastForEach$iv$iv;
                int size4 = $this$fastForEach$iv$iv$iv.size();
                int index$iv$iv$iv2 = 0;
                while (index$iv$iv$iv2 < size4) {
                    int i20 = size4;
                    List $this$fastForEach$iv$iv$iv2 = $this$fastForEach$iv$iv$iv;
                    Object item$iv$iv$iv2 = $this$fastForEach$iv$iv$iv2.get(index$iv$iv$iv2);
                    int index$iv2 = ((Number) item$iv$iv$iv2).intValue();
                    List $this$fastForEach$iv$iv2 = $this$fastForEach$iv$iv;
                    int itemCount7 = itemCount2;
                    int itemIndex4 = layoutHeight3;
                    if (index$iv2 < itemCount7) {
                        measuredItems2 = measuredItems6;
                        int lane6 = $this$measure.getLaneInfo().getLane(index$iv2);
                        switch (lane6) {
                            case -2:
                            case -1:
                                firstItemIndices2 = firstItemIndices;
                                int[] $this$all$iv3 = currentItemIndices;
                                int length16 = $this$all$iv3.length;
                                itemCount3 = itemCount7;
                                int itemCount8 = 0;
                                while (true) {
                                    if (itemCount8 >= length16) {
                                        z6 = true;
                                        break;
                                    } else {
                                        int element$iv6 = $this$all$iv3[itemCount8];
                                        int[] $this$all$iv4 = $this$all$iv3;
                                        int it6 = element$iv6 < index$iv2 ? 1 : 0;
                                        if (it6 == 0) {
                                            z6 = false;
                                            break;
                                        } else {
                                            itemCount8++;
                                            $this$all$iv3 = $this$all$iv4;
                                        }
                                    }
                                }
                            default:
                                firstItemIndices2 = firstItemIndices;
                                itemCount3 = itemCount7;
                                if (currentItemIndices[lane6] < index$iv2) {
                                    z6 = true;
                                    break;
                                } else {
                                    z6 = false;
                                    break;
                                }
                        }
                    } else {
                        firstItemIndices2 = firstItemIndices;
                        measuredItems2 = measuredItems6;
                        itemCount3 = itemCount7;
                        z6 = false;
                    }
                    if (z6) {
                        layoutHeight = layoutHeight2;
                        long spanRange$iv2 = $this$measure.m759getSpanRangelOCCd4c($this$measure.getItemProvider(), index$iv2, 0);
                        if (list3 == null) {
                            Object result$iv2 = new ArrayList();
                            list3 = (List) result$iv2;
                        }
                        LazyStaggeredGridMeasuredItem measuredItem$iv2 = $this$measure.getMeasuredItemProvider().m767getAndMeasurejy6DScQ(index$iv2, spanRange$iv2);
                        measuredItem$iv2.position(extraItemOffset2, 0, mainAxisLayoutSize);
                        extraItemOffset2 += measuredItem$iv2.getSizeWithSpacings();
                        list3.add(measuredItem$iv2);
                    } else {
                        layoutHeight = layoutHeight2;
                    }
                    index$iv$iv$iv2++;
                    layoutHeight2 = layoutHeight;
                    size4 = i20;
                    $this$fastForEach$iv$iv$iv = $this$fastForEach$iv$iv$iv2;
                    layoutHeight3 = itemIndex4;
                    $this$fastForEach$iv$iv = $this$fastForEach$iv$iv2;
                    measuredItems6 = measuredItems2;
                    firstItemIndices = firstItemIndices2;
                    itemCount2 = itemCount3;
                }
                int[] firstItemIndices8 = firstItemIndices;
                int itemCount9 = itemCount2;
                int $i$f$calculateExtraItems3 = layoutHeight2;
                if (list3 == null) {
                    list3 = CollectionsKt.emptyList();
                }
                List extraItemsAfter = list3;
                final List positionedItems = new ArrayList();
                positionedItems.addAll(extraItemsBefore);
                positionedItems.addAll(visibleItems);
                positionedItems.addAll(extraItemsAfter);
                $this$measure.getState().getPlacementAnimator().onMeasured((int) consumedScroll, layoutWidth, $i$f$calculateExtraItems3, positionedItems, $this$measure.getMeasuredItemProvider(), $this$measure.getIsVertical(), $this$measure.getLaneCount(), $this$measure.getCoroutineScope());
                int[] $this$any$iv3 = currentItemOffsets2;
                int length17 = $this$any$iv3.length;
                int i21 = 0;
                while (true) {
                    if (i21 < length17) {
                        int element$iv7 = $this$any$iv3[i21];
                        List extraItemsAfter2 = extraItemsAfter;
                        if (element$iv7 > $this$measure.getMainAxisAvailableSize()) {
                            z4 = true;
                        } else {
                            i21++;
                            extraItemsAfter = extraItemsAfter2;
                        }
                    } else {
                        z4 = false;
                    }
                }
                if (!z4) {
                    int[] $this$all$iv5 = currentItemIndices;
                    int length18 = $this$all$iv5.length;
                    int i22 = 0;
                    while (true) {
                        if (i22 < length18) {
                            int element$iv8 = $this$all$iv5[i22];
                            int it7 = element$iv8 < itemCount9 + (-1) ? 1 : 0;
                            if (it7 == 0) {
                                z5 = false;
                            } else {
                                i22++;
                            }
                        } else {
                            z5 = true;
                        }
                    }
                    if (!z5) {
                        canScrollForward = false;
                        return new LazyStaggeredGridMeasureResult(firstItemIndices8, firstItemOffsets2, consumedScroll, MeasureScope.layout$default(scope$iv, layoutWidth, $i$f$calculateExtraItems3, null, new Function1<Placeable.PlacementScope, Unit>() { // from class: androidx.compose.foundation.lazy.staggeredgrid.LazyStaggeredGridMeasureKt$measure$1$29
                            /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
                            {
                                super(1);
                            }

                            @Override // kotlin.jvm.functions.Function1
                            public /* bridge */ /* synthetic */ Unit invoke(Placeable.PlacementScope placementScope) {
                                invoke2(placementScope);
                                return Unit.INSTANCE;
                            }

                            /* renamed from: invoke, reason: avoid collision after fix types in other method */
                            public final void invoke2(Placeable.PlacementScope $this$layout) {
                                List $this$fastForEach$iv = positionedItems;
                                LazyStaggeredGridMeasureContext lazyStaggeredGridMeasureContext3 = $this$measure;
                                int size5 = $this$fastForEach$iv.size();
                                for (int index$iv3 = 0; index$iv3 < size5; index$iv3++) {
                                    Object item$iv = $this$fastForEach$iv.get(index$iv3);
                                    LazyStaggeredGridMeasuredItem item3 = (LazyStaggeredGridMeasuredItem) item$iv;
                                    item3.place($this$layout, lazyStaggeredGridMeasureContext3);
                                }
                                ObservableScopeInvalidator.m730attachToScopeimpl($this$measure.getState().m770getPlacementScopeInvalidatorzYiylxw$foundation_release());
                            }
                        }, 4, null), canScrollForward, $this$measure.getIsVertical(), remeasureNeeded6, itemCount9, visibleItems, IntSizeKt.IntSize(layoutWidth, $i$f$calculateExtraItems3), minOffset3, maxOffset2, $this$measure.getBeforeContentPadding(), $this$measure.getAfterContentPadding(), $this$measure.getMainAxisSpacing(), null);
                    }
                }
                canScrollForward = true;
                return new LazyStaggeredGridMeasureResult(firstItemIndices8, firstItemOffsets2, consumedScroll, MeasureScope.layout$default(scope$iv, layoutWidth, $i$f$calculateExtraItems3, null, new Function1<Placeable.PlacementScope, Unit>() { // from class: androidx.compose.foundation.lazy.staggeredgrid.LazyStaggeredGridMeasureKt$measure$1$29
                    /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
                    {
                        super(1);
                    }

                    @Override // kotlin.jvm.functions.Function1
                    public /* bridge */ /* synthetic */ Unit invoke(Placeable.PlacementScope placementScope) {
                        invoke2(placementScope);
                        return Unit.INSTANCE;
                    }

                    /* renamed from: invoke, reason: avoid collision after fix types in other method */
                    public final void invoke2(Placeable.PlacementScope $this$layout) {
                        List $this$fastForEach$iv = positionedItems;
                        LazyStaggeredGridMeasureContext lazyStaggeredGridMeasureContext3 = $this$measure;
                        int size5 = $this$fastForEach$iv.size();
                        for (int index$iv3 = 0; index$iv3 < size5; index$iv3++) {
                            Object item$iv = $this$fastForEach$iv.get(index$iv3);
                            LazyStaggeredGridMeasuredItem item3 = (LazyStaggeredGridMeasuredItem) item$iv;
                            item3.place($this$layout, lazyStaggeredGridMeasureContext3);
                        }
                        ObservableScopeInvalidator.m730attachToScopeimpl($this$measure.getState().m770getPlacementScopeInvalidatorzYiylxw$foundation_release());
                    }
                }, 4, null), canScrollForward, $this$measure.getIsVertical(), remeasureNeeded6, itemCount9, visibleItems, IntSizeKt.IntSize(layoutWidth, $i$f$calculateExtraItems3), minOffset3, maxOffset2, $this$measure.getBeforeContentPadding(), $this$measure.getAfterContentPadding(), $this$measure.getMainAxisSpacing(), null);
            }
            itemCount = itemCount4;
        }
        return new LazyStaggeredGridMeasureResult(initialItemIndices, initialItemOffsets, 0.0f, MeasureScope.layout$default(scope$iv, Constraints.m6052getMinWidthimpl($this$measure.getConstraints()), Constraints.m6051getMinHeightimpl($this$measure.getConstraints()), null, new Function1<Placeable.PlacementScope, Unit>() { // from class: androidx.compose.foundation.lazy.staggeredgrid.LazyStaggeredGridMeasureKt$measure$1$1
            @Override // kotlin.jvm.functions.Function1
            public /* bridge */ /* synthetic */ Unit invoke(Placeable.PlacementScope placementScope) {
                invoke2(placementScope);
                return Unit.INSTANCE;
            }

            /* renamed from: invoke, reason: avoid collision after fix types in other method */
            public final void invoke2(Placeable.PlacementScope $this$layout) {
            }
        }, 4, null), false, $this$measure.getIsVertical(), false, itemCount, CollectionsKt.emptyList(), IntSizeKt.IntSize(Constraints.m6052getMinWidthimpl($this$measure.getConstraints()), Constraints.m6051getMinHeightimpl($this$measure.getConstraints())), -$this$measure.getBeforeContentPadding(), $this$measure.getMainAxisAvailableSize() + $this$measure.getAfterContentPadding(), $this$measure.getBeforeContentPadding(), $this$measure.getAfterContentPadding(), $this$measure.getMainAxisSpacing(), null);
    }

    private static final boolean measure$lambda$38$hasSpaceBeforeFirst(int[] firstItemIndices, int[] firstItemOffsets, LazyStaggeredGridMeasureContext $this_measure) {
        int length = firstItemIndices.length;
        for (int lane = 0; lane < length; lane++) {
            int itemIndex = firstItemIndices[lane];
            int itemOffset = firstItemOffsets[lane];
            if (itemOffset < Math.max(-$this_measure.getMainAxisSpacing(), 0) && itemIndex > 0) {
                return true;
            }
        }
        return false;
    }

    private static final boolean measure$lambda$38$misalignedStart(int[] firstItemIndices, LazyStaggeredGridMeasureContext $this_measure, int[] firstItemOffsets, int referenceLane) {
        int lane = 0;
        int length = firstItemIndices.length;
        while (true) {
            boolean z = false;
            if (lane < length) {
                if (findPreviousItemIndex($this_measure, firstItemIndices[lane], lane) == -1 && firstItemOffsets[lane] != firstItemOffsets[referenceLane]) {
                    z = true;
                }
                boolean misalignedOffsets = z;
                if (misalignedOffsets) {
                    return true;
                }
                lane++;
            } else {
                int length2 = firstItemIndices.length;
                for (int lane2 = 0; lane2 < length2; lane2++) {
                    boolean moreItemsInOtherLanes = findPreviousItemIndex($this_measure, firstItemIndices[lane2], lane2) != -1 && firstItemOffsets[lane2] >= firstItemOffsets[referenceLane];
                    if (moreItemsInOtherLanes) {
                        return true;
                    }
                }
                int firstItemLane = $this_measure.getLaneInfo().getLane(0);
                return (firstItemLane == 0 || firstItemLane == -1 || firstItemLane == -2) ? false : true;
            }
        }
    }

    private static final List<LazyStaggeredGridMeasuredItem> calculateVisibleItems(LazyStaggeredGridMeasureContext $this$calculateVisibleItems, ArrayDeque<LazyStaggeredGridMeasuredItem>[] arrayDequeArr, int[] itemScrollOffsets, int mainAxisLayoutSize) {
        boolean z;
        int i = 0;
        for (ArrayDeque<LazyStaggeredGridMeasuredItem> arrayDeque : arrayDequeArr) {
            i += arrayDeque.size();
        }
        ArrayList positionedItems = new ArrayList(i);
        while (true) {
            int length = arrayDequeArr.length;
            int i2 = 0;
            while (true) {
                if (i2 >= length) {
                    z = false;
                    break;
                }
                if (!arrayDequeArr[i2].isEmpty()) {
                    z = true;
                    break;
                }
                i2++;
            }
            if (!z) {
                return positionedItems;
            }
            int result$iv = -1;
            int min$iv = Integer.MAX_VALUE;
            int length2 = arrayDequeArr.length;
            for (int i$iv = 0; i$iv < length2; i$iv++) {
                LazyStaggeredGridMeasuredItem firstOrNull = arrayDequeArr[i$iv].firstOrNull();
                int value$iv = firstOrNull != null ? firstOrNull.getIndex() : Integer.MAX_VALUE;
                if (min$iv > value$iv) {
                    min$iv = value$iv;
                    result$iv = i$iv;
                }
            }
            int laneIndex = result$iv;
            LazyStaggeredGridMeasuredItem item = arrayDequeArr[laneIndex].removeFirst();
            if (item.getLane() == laneIndex) {
                long spanRange = SpanRange.m772constructorimpl(item.getLane(), item.getSpan());
                int mainAxisOffset = m762maxInRangejy6DScQ(itemScrollOffsets, spanRange);
                int crossAxisOffset = $this$calculateVisibleItems.getResolvedSlots().getPositions()[laneIndex];
                if (item.getPlaceablesCount() != 0) {
                    item.position(mainAxisOffset, crossAxisOffset, mainAxisLayoutSize);
                    positionedItems.add(item);
                    int i$iv2 = (int) (spanRange >> 32);
                    int i3 = (int) (spanRange & 4294967295L);
                    for (int i$iv3 = i$iv2; i$iv3 < i3; i$iv3++) {
                        int lane = i$iv3;
                        itemScrollOffsets[lane] = mainAxisOffset + item.getSizeWithSpacings();
                    }
                }
            }
        }
    }

    private static final List<LazyStaggeredGridMeasuredItem> calculateExtraItems(LazyStaggeredGridMeasureContext $this$calculateExtraItems, Function1<? super LazyStaggeredGridMeasuredItem, Unit> function1, Function1<? super Integer, Boolean> function12, boolean beforeVisibleBounds) {
        int $i$f$calculateExtraItems;
        List $this$fastForEachReversed$iv$iv;
        int $i$f$fastForEachReversed;
        Function1<? super Integer, Boolean> function13 = function12;
        int $i$f$calculateExtraItems2 = 0;
        ArrayList arrayList = null;
        List $this$fastForEach$iv = $this$calculateExtraItems.getPinnedItems();
        List $this$fastForEachReversed$iv$iv2 = $this$fastForEach$iv;
        if (beforeVisibleBounds) {
            int $i$f$fastForEachReversed2 = 0;
            int size = $this$fastForEachReversed$iv$iv2.size() - 1;
            if (size >= 0) {
                while (true) {
                    int index$iv$iv = size;
                    size--;
                    Object item$iv$iv = $this$fastForEachReversed$iv$iv2.get(index$iv$iv);
                    int index = ((Number) item$iv$iv).intValue();
                    if (function13.invoke(Integer.valueOf(index)).booleanValue()) {
                        $this$fastForEachReversed$iv$iv = $this$fastForEachReversed$iv$iv2;
                        $i$f$fastForEachReversed = $i$f$fastForEachReversed2;
                        long spanRange = $this$calculateExtraItems.m759getSpanRangelOCCd4c($this$calculateExtraItems.getItemProvider(), index, 0);
                        if (arrayList == null) {
                            Object result = new ArrayList();
                            arrayList = (List) result;
                        }
                        LazyStaggeredGridMeasuredItem measuredItem = $this$calculateExtraItems.getMeasuredItemProvider().m767getAndMeasurejy6DScQ(index, spanRange);
                        function1.invoke(measuredItem);
                        arrayList.add(measuredItem);
                    } else {
                        $this$fastForEachReversed$iv$iv = $this$fastForEachReversed$iv$iv2;
                        $i$f$fastForEachReversed = $i$f$fastForEachReversed2;
                    }
                    if (size < 0) {
                        break;
                    }
                    $this$fastForEachReversed$iv$iv2 = $this$fastForEachReversed$iv$iv;
                    $i$f$fastForEachReversed2 = $i$f$fastForEachReversed;
                }
            }
        } else {
            int index$iv$iv2 = 0;
            int size2 = $this$fastForEachReversed$iv$iv2.size();
            while (index$iv$iv2 < size2) {
                Object item$iv$iv2 = $this$fastForEachReversed$iv$iv2.get(index$iv$iv2);
                int index2 = ((Number) item$iv$iv2).intValue();
                if (function13.invoke(Integer.valueOf(index2)).booleanValue()) {
                    $i$f$calculateExtraItems = $i$f$calculateExtraItems2;
                    long spanRange2 = $this$calculateExtraItems.m759getSpanRangelOCCd4c($this$calculateExtraItems.getItemProvider(), index2, 0);
                    if (arrayList == null) {
                        Object result2 = new ArrayList();
                        arrayList = (List) result2;
                    }
                    LazyStaggeredGridMeasuredItem measuredItem2 = $this$calculateExtraItems.getMeasuredItemProvider().m767getAndMeasurejy6DScQ(index2, spanRange2);
                    function1.invoke(measuredItem2);
                    arrayList.add(measuredItem2);
                } else {
                    $i$f$calculateExtraItems = $i$f$calculateExtraItems2;
                }
                index$iv$iv2++;
                function13 = function12;
                $i$f$calculateExtraItems2 = $i$f$calculateExtraItems;
            }
        }
        return arrayList == null ? CollectionsKt.emptyList() : arrayList;
    }

    static /* synthetic */ void fastForEach$default(List $this$fastForEach_u24default, boolean reverse, Function1 action, int i, Object obj) {
        if ((i & 1) != 0) {
            reverse = false;
        }
        if (reverse) {
            int size = $this$fastForEach_u24default.size() - 1;
            if (size < 0) {
                return;
            }
            do {
                int index$iv = size;
                size--;
                Object item$iv = $this$fastForEach_u24default.get(index$iv);
                action.invoke(item$iv);
            } while (size >= 0);
            return;
        }
        int size2 = $this$fastForEach_u24default.size();
        for (int index$iv2 = 0; index$iv2 < size2; index$iv2++) {
            Object item$iv2 = $this$fastForEach_u24default.get(index$iv2);
            action.invoke(item$iv2);
        }
    }

    private static final <T> void fastForEach(List<? extends T> list, boolean reverse, Function1<? super T, Unit> function1) {
        if (reverse) {
            int size = list.size() - 1;
            if (size < 0) {
                return;
            }
            do {
                int index$iv = size;
                size--;
                Object item$iv = list.get(index$iv);
                function1.invoke(item$iv);
            } while (size >= 0);
            return;
        }
        int size2 = list.size();
        for (int index$iv2 = 0; index$iv2 < size2; index$iv2++) {
            Object item$iv2 = list.get(index$iv2);
            function1.invoke(item$iv2);
        }
    }

    /* renamed from: forEach-nIS5qE8, reason: not valid java name */
    private static final void m761forEachnIS5qE8(long $this$forEach_u2dnIS5qE8, Function1<? super Integer, Unit> function1) {
        int i = (int) (4294967295L & $this$forEach_u2dnIS5qE8);
        for (int i2 = (int) ($this$forEach_u2dnIS5qE8 >> 32); i2 < i; i2++) {
            function1.invoke(Integer.valueOf(i2));
        }
    }

    private static final void offsetBy(int[] $this$offsetBy, int delta) {
        int length = $this$offsetBy.length;
        for (int i = 0; i < length; i++) {
            $this$offsetBy[i] = $this$offsetBy[i] + delta;
        }
    }

    /* renamed from: maxInRange-jy6DScQ, reason: not valid java name */
    private static final int m762maxInRangejy6DScQ(int[] $this$maxInRange_u2djy6DScQ, long indexRange) {
        int max = Integer.MIN_VALUE;
        int i = (int) (4294967295L & indexRange);
        for (int i$iv = (int) (indexRange >> 32); i$iv < i; i$iv++) {
            int it = i$iv;
            max = Math.max(max, $this$maxInRange_u2djy6DScQ[it]);
        }
        return max;
    }

    public static /* synthetic */ int indexOfMinValue$default(int[] iArr, int i, int i2, Object obj) {
        if ((i2 & 1) != 0) {
            i = Integer.MIN_VALUE;
        }
        return indexOfMinValue(iArr, i);
    }

    public static final int indexOfMinValue(int[] $this$indexOfMinValue, int minBound) {
        int result = -1;
        int min = Integer.MAX_VALUE;
        int length = $this$indexOfMinValue.length;
        for (int i = 0; i < length; i++) {
            int i2 = minBound + 1;
            int i3 = $this$indexOfMinValue[i];
            boolean z = false;
            if (i2 <= i3 && i3 < min) {
                z = true;
            }
            if (z) {
                min = $this$indexOfMinValue[i];
                result = i;
            }
        }
        return result;
    }

    private static final <T> int indexOfMinBy(T[] tArr, Function1<? super T, Integer> function1) {
        int result = -1;
        int min = Integer.MAX_VALUE;
        int length = tArr.length;
        for (int i = 0; i < length; i++) {
            int value = function1.invoke(tArr[i]).intValue();
            if (min > value) {
                min = value;
                result = i;
            }
        }
        return result;
    }

    private static final int indexOfMaxValue(int[] $this$indexOfMaxValue) {
        int result = -1;
        int max = Integer.MIN_VALUE;
        int length = $this$indexOfMaxValue.length;
        for (int i = 0; i < length; i++) {
            if (max < $this$indexOfMaxValue[i]) {
                max = $this$indexOfMaxValue[i];
                result = i;
            }
        }
        return result;
    }

    private static final int[] transform(int[] $this$transform, Function1<? super Integer, Integer> function1) {
        int length = $this$transform.length;
        for (int i = 0; i < length; i++) {
            $this$transform[i] = function1.invoke(Integer.valueOf($this$transform[i])).intValue();
        }
        return $this$transform;
    }

    private static final void ensureIndicesInRange(LazyStaggeredGridMeasureContext $this$ensureIndicesInRange, int[] indices, int itemCount) {
        int length = indices.length - 1;
        if (length >= 0) {
            do {
                int i = length;
                length--;
                while (true) {
                    if (indices[i] < itemCount && $this$ensureIndicesInRange.getLaneInfo().assignedToLane(indices[i], i)) {
                        break;
                    } else {
                        indices[i] = findPreviousItemIndex($this$ensureIndicesInRange, indices[i], i);
                    }
                }
                if (indices[i] >= 0 && !$this$ensureIndicesInRange.isFullSpan($this$ensureIndicesInRange.getItemProvider(), indices[i])) {
                    $this$ensureIndicesInRange.getLaneInfo().setLane(indices[i], i);
                }
            } while (length >= 0);
        }
    }

    private static final int findPreviousItemIndex(LazyStaggeredGridMeasureContext $this$findPreviousItemIndex, int item, int lane) {
        return $this$findPreviousItemIndex.getLaneInfo().findPreviousItemIndex(item, lane);
    }
}
