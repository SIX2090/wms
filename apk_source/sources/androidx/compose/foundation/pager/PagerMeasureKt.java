package androidx.compose.foundation.pager;

import androidx.compose.foundation.gestures.Orientation;
import androidx.compose.foundation.gestures.snapping.SnapPositionInLayout;
import androidx.compose.foundation.gestures.snapping.SnapPositionInLayoutKt;
import androidx.compose.foundation.layout.Arrangement;
import androidx.compose.foundation.lazy.layout.LazyLayoutMeasureScope;
import androidx.compose.foundation.lazy.layout.ObservableScopeInvalidator;
import androidx.compose.runtime.MutableState;
import androidx.compose.ui.Alignment;
import androidx.compose.ui.layout.MeasureResult;
import androidx.compose.ui.layout.Placeable;
import androidx.compose.ui.unit.Constraints;
import androidx.compose.ui.unit.ConstraintsKt;
import androidx.compose.ui.unit.Density;
import androidx.compose.ui.unit.LayoutDirection;
import java.util.ArrayList;
import java.util.List;
import kotlin.Metadata;
import kotlin.Unit;
import kotlin.collections.ArrayDeque;
import kotlin.collections.ArraysKt;
import kotlin.collections.CollectionsKt;
import kotlin.jvm.functions.Function0;
import kotlin.jvm.functions.Function1;
import kotlin.jvm.functions.Function3;
import kotlin.jvm.internal.Intrinsics;
import kotlin.ranges.IntRange;
import kotlin.ranges.RangesKt;

/* compiled from: PagerMeasure.kt */
@Metadata(d1 = {"\u0000¨\u0001\n\u0000\n\u0002\u0010\u000b\n\u0000\n\u0002\u0010\u0007\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010\b\n\u0000\n\u0002\u0010 \n\u0002\b\u0004\n\u0002\u0018\u0002\n\u0002\b\u0006\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0010\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\u0010\u000e\n\u0000\n\u0002\u0010!\n\u0002\u0018\u0002\n\u0002\b\t\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\b\u0004\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0018\u0002\n\u0002\b\u0006\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\b\u0003\u001a@\u0010\u0005\u001a\u0004\u0018\u00010\u00062\u0006\u0010\u0007\u001a\u00020\b2\f\u0010\t\u001a\b\u0012\u0004\u0012\u00020\u00060\n2\u0006\u0010\u000b\u001a\u00020\b2\u0006\u0010\f\u001a\u00020\b2\u0006\u0010\r\u001a\u00020\b2\u0006\u0010\u000e\u001a\u00020\u000fH\u0002\u001aH\u0010\u0010\u001a\b\u0012\u0004\u0012\u00020\u00060\n2\u0006\u0010\u0011\u001a\u00020\b2\u0006\u0010\u0012\u001a\u00020\b2\u0006\u0010\u0013\u001a\u00020\b2\f\u0010\u0014\u001a\b\u0012\u0004\u0012\u00020\b0\n2\u0012\u0010\u0015\u001a\u000e\u0012\u0004\u0012\u00020\b\u0012\u0004\u0012\u00020\u00060\u0016H\u0002\u001a@\u0010\u0017\u001a\b\u0012\u0004\u0012\u00020\u00060\n2\u0006\u0010\u0018\u001a\u00020\b2\u0006\u0010\u0013\u001a\u00020\b2\f\u0010\u0014\u001a\b\u0012\u0004\u0012\u00020\b0\n2\u0012\u0010\u0015\u001a\u000e\u0012\u0004\u0012\u00020\b\u0012\u0004\u0012\u00020\u00060\u0016H\u0002\u001a\u0017\u0010\u0019\u001a\u00020\u001a2\f\u0010\u001b\u001a\b\u0012\u0004\u0012\u00020\u001d0\u001cH\u0082\b\u001a\u008c\u0001\u0010\u001e\u001a\b\u0012\u0004\u0012\u00020\u00060\u001f*\u00020 2\f\u0010!\u001a\b\u0012\u0004\u0012\u00020\u00060\n2\f\u0010\"\u001a\b\u0012\u0004\u0012\u00020\u00060\n2\f\u0010#\u001a\b\u0012\u0004\u0012\u00020\u00060\n2\u0006\u0010$\u001a\u00020\b2\u0006\u0010%\u001a\u00020\b2\u0006\u0010&\u001a\u00020\b2\u0006\u0010'\u001a\u00020\b2\u0006\u0010(\u001a\u00020\b2\u0006\u0010)\u001a\u00020*2\u0006\u0010+\u001a\u00020\u00012\u0006\u0010,\u001a\u00020-2\u0006\u0010.\u001a\u00020\b2\u0006\u0010/\u001a\u00020\bH\u0002\u001aj\u0010\u0015\u001a\u00020\u0006*\u00020 2\u0006\u00100\u001a\u00020\b2\u0006\u00101\u001a\u0002022\u0006\u00103\u001a\u0002042\u0006\u00105\u001a\u0002062\u0006\u0010)\u001a\u00020*2\b\u00107\u001a\u0004\u0018\u0001082\b\u00109\u001a\u0004\u0018\u00010:2\u0006\u0010;\u001a\u00020<2\u0006\u0010+\u001a\u00020\u00012\u0006\u0010/\u001a\u00020\bH\u0002ø\u0001\u0000¢\u0006\u0004\b=\u0010>\u001aé\u0001\u0010?\u001a\u00020@*\u00020 2\u0006\u0010A\u001a\u00020\b2\u0006\u00103\u001a\u0002042\u0006\u0010B\u001a\u00020\b2\u0006\u0010\u000b\u001a\u00020\b2\u0006\u0010\f\u001a\u00020\b2\u0006\u0010.\u001a\u00020\b2\u0006\u0010C\u001a\u00020\b2\u0006\u0010D\u001a\u00020\b2\u0006\u0010E\u001a\u0002022\u0006\u0010)\u001a\u00020*2\b\u00109\u001a\u0004\u0018\u00010:2\b\u00107\u001a\u0004\u0018\u0001082\u0006\u0010+\u001a\u00020\u00012\u0006\u00105\u001a\u0002062\u0006\u0010/\u001a\u00020\b2\u0006\u0010\u0013\u001a\u00020\b2\f\u0010\u0014\u001a\b\u0012\u0004\u0012\u00020\b0\n2\u0006\u0010\u000e\u001a\u00020\u000f2\u0006\u0010F\u001a\u00020G2/\u0010H\u001a+\u0012\u0004\u0012\u00020\b\u0012\u0004\u0012\u00020\b\u0012\u0015\u0012\u0013\u0012\u0004\u0012\u00020J\u0012\u0004\u0012\u00020\u001a0\u0016¢\u0006\u0002\bK\u0012\u0004\u0012\u00020L0IH\u0000ø\u0001\u0000¢\u0006\u0004\bM\u0010N\"\u000e\u0010\u0000\u001a\u00020\u0001X\u0082T¢\u0006\u0002\n\u0000\"\u000e\u0010\u0002\u001a\u00020\u0003X\u0080T¢\u0006\u0002\n\u0000\"\u000e\u0010\u0004\u001a\u00020\u0003X\u0080T¢\u0006\u0002\n\u0000\u0082\u0002\u0007\n\u0005\b¡\u001e0\u0001¨\u0006O"}, d2 = {"DEBUG", "", "MaxPageOffset", "", "MinPageOffset", "calculateNewCurrentPage", "Landroidx/compose/foundation/pager/MeasuredPage;", "viewportSize", "", "visiblePagesInfo", "", "beforeContentPadding", "afterContentPadding", "itemSize", "snapPositionInLayout", "Landroidx/compose/foundation/gestures/snapping/SnapPositionInLayout;", "createPagesAfterList", "currentLastPage", "pagesCount", "beyondBoundsPageCount", "pinnedPages", "getAndMeasure", "Lkotlin/Function1;", "createPagesBeforeList", "currentFirstPage", "debugLog", "", "generateMsg", "Lkotlin/Function0;", "", "calculatePagesOffsets", "", "Landroidx/compose/foundation/lazy/layout/LazyLayoutMeasureScope;", "pages", "extraPagesBefore", "extraPagesAfter", "layoutWidth", "layoutHeight", "finalMainAxisOffset", "maxOffset", "pagesScrollOffset", "orientation", "Landroidx/compose/foundation/gestures/Orientation;", "reverseLayout", "density", "Landroidx/compose/ui/unit/Density;", "spaceBetweenPages", "pageAvailableSize", "index", "childConstraints", "Landroidx/compose/ui/unit/Constraints;", "pagerItemProvider", "Landroidx/compose/foundation/pager/PagerLazyLayoutItemProvider;", "visualPageOffset", "Landroidx/compose/ui/unit/IntOffset;", "horizontalAlignment", "Landroidx/compose/ui/Alignment$Horizontal;", "verticalAlignment", "Landroidx/compose/ui/Alignment$Vertical;", "layoutDirection", "Landroidx/compose/ui/unit/LayoutDirection;", "getAndMeasure-SGf7dI0", "(Landroidx/compose/foundation/lazy/layout/LazyLayoutMeasureScope;IJLandroidx/compose/foundation/pager/PagerLazyLayoutItemProvider;JLandroidx/compose/foundation/gestures/Orientation;Landroidx/compose/ui/Alignment$Horizontal;Landroidx/compose/ui/Alignment$Vertical;Landroidx/compose/ui/unit/LayoutDirection;ZI)Landroidx/compose/foundation/pager/MeasuredPage;", "measurePager", "Landroidx/compose/foundation/pager/PagerMeasureResult;", "pageCount", "mainAxisAvailableSize", "currentPage", "currentPageOffset", "constraints", "placementScopeInvalidator", "Landroidx/compose/foundation/lazy/layout/ObservableScopeInvalidator;", "layout", "Lkotlin/Function3;", "Landroidx/compose/ui/layout/Placeable$PlacementScope;", "Lkotlin/ExtensionFunctionType;", "Landroidx/compose/ui/layout/MeasureResult;", "measurePager-_JDW0YA", "(Landroidx/compose/foundation/lazy/layout/LazyLayoutMeasureScope;ILandroidx/compose/foundation/pager/PagerLazyLayoutItemProvider;IIIIIIJLandroidx/compose/foundation/gestures/Orientation;Landroidx/compose/ui/Alignment$Vertical;Landroidx/compose/ui/Alignment$Horizontal;ZJIILjava/util/List;Landroidx/compose/foundation/gestures/snapping/SnapPositionInLayout;Landroidx/compose/runtime/MutableState;Lkotlin/jvm/functions/Function3;)Landroidx/compose/foundation/pager/PagerMeasureResult;", "foundation_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class PagerMeasureKt {
    private static final boolean DEBUG = false;
    public static final float MaxPageOffset = 0.5f;
    public static final float MinPageOffset = -0.5f;

    /* renamed from: measurePager-_JDW0YA, reason: not valid java name */
    public static final PagerMeasureResult m795measurePager_JDW0YA(final LazyLayoutMeasureScope $this$measurePager_u2d_JDW0YA, int pageCount, final PagerLazyLayoutItemProvider pagerItemProvider, int mainAxisAvailableSize, int beforeContentPadding, int afterContentPadding, int spaceBetweenPages, int currentPage, int currentPageOffset, long constraints, final Orientation orientation, final Alignment.Vertical verticalAlignment, final Alignment.Horizontal horizontalAlignment, final boolean reverseLayout, final long visualPageOffset, final int pageAvailableSize, int beyondBoundsPageCount, List<Integer> list, SnapPositionInLayout snapPositionInLayout, final MutableState<Unit> mutableState, Function3<? super Integer, ? super Integer, ? super Function1<? super Placeable.PlacementScope, Unit>, ? extends MeasureResult> function3) {
        int i;
        int i2;
        int currentFirstPageScrollOffset;
        int maxCrossAxis;
        int maxOffset;
        int index;
        int maxOffset2;
        int index2;
        int currentFirstPageScrollOffset2;
        int currentFirstPage;
        int maxCrossAxis2;
        int currentMainAxisOffset;
        int currentFirstPageScrollOffset3;
        MeasuredPage firstPage;
        int i3;
        int i4;
        int pageSizeWithSpacing;
        int currentFirstPage2;
        ArrayList visiblePagesInfo;
        float newCurrentPageOffsetFraction;
        int currentFirstPageScrollOffset4;
        int i5;
        int i6 = 0;
        if (!(beforeContentPadding >= 0)) {
            throw new IllegalArgumentException("negative beforeContentPadding".toString());
        }
        if (!(afterContentPadding >= 0)) {
            throw new IllegalArgumentException("negative afterContentPadding".toString());
        }
        int pageSizeWithSpacing2 = RangesKt.coerceAtLeast(pageAvailableSize + spaceBetweenPages, 0);
        if (pageCount <= 0) {
            return new PagerMeasureResult(CollectionsKt.emptyList(), pageAvailableSize, spaceBetweenPages, afterContentPadding, orientation, -beforeContentPadding, mainAxisAvailableSize + afterContentPadding, false, beyondBoundsPageCount, null, null, 0.0f, 0, false, function3.invoke(Integer.valueOf(Constraints.m6052getMinWidthimpl(constraints)), Integer.valueOf(Constraints.m6051getMinHeightimpl(constraints)), new Function1<Placeable.PlacementScope, Unit>() { // from class: androidx.compose.foundation.pager.PagerMeasureKt$measurePager$4
                @Override // kotlin.jvm.functions.Function1
                public /* bridge */ /* synthetic */ Unit invoke(Placeable.PlacementScope placementScope) {
                    invoke2(placementScope);
                    return Unit.INSTANCE;
                }

                /* renamed from: invoke, reason: avoid collision after fix types in other method */
                public final void invoke2(Placeable.PlacementScope $this$invoke) {
                }
            }), false);
        }
        if (orientation == Orientation.Vertical) {
            i = Constraints.m6050getMaxWidthimpl(constraints);
        } else {
            i = pageAvailableSize;
        }
        if (orientation != Orientation.Vertical) {
            i2 = Constraints.m6049getMaxHeightimpl(constraints);
        } else {
            i2 = pageAvailableSize;
        }
        final long childConstraints = ConstraintsKt.Constraints$default(0, i, 0, i2, 5, null);
        int firstVisiblePage = currentPage;
        int firstVisiblePageOffset = currentPageOffset;
        while (firstVisiblePage > 0 && firstVisiblePageOffset > 0) {
            firstVisiblePage--;
            firstVisiblePageOffset -= pageSizeWithSpacing2;
        }
        int firstVisiblePageScrollOffset = firstVisiblePageOffset * (-1);
        int currentFirstPage3 = firstVisiblePage;
        int currentFirstPageScrollOffset5 = firstVisiblePageScrollOffset;
        if (currentFirstPage3 >= pageCount) {
            currentFirstPage3 = pageCount - 1;
            currentFirstPageScrollOffset5 = 0;
        }
        ArrayDeque visiblePages = new ArrayDeque();
        int minOffset = (-beforeContentPadding) + (spaceBetweenPages < 0 ? spaceBetweenPages : 0);
        int maxOffset3 = mainAxisAvailableSize;
        int currentFirstPage4 = currentFirstPage3;
        int maxCrossAxis3 = 0;
        int currentFirstPageScrollOffset6 = currentFirstPageScrollOffset5 + minOffset;
        while (currentFirstPageScrollOffset6 < 0 && currentFirstPage4 > 0) {
            int previous = currentFirstPage4 - 1;
            ArrayDeque visiblePages2 = visiblePages;
            int i7 = i6;
            MeasuredPage measuredPage = m794getAndMeasureSGf7dI0($this$measurePager_u2d_JDW0YA, previous, childConstraints, pagerItemProvider, visualPageOffset, orientation, horizontalAlignment, verticalAlignment, $this$measurePager_u2d_JDW0YA.getLayoutDirection(), reverseLayout, pageAvailableSize);
            visiblePages2.add(i7, measuredPage);
            maxCrossAxis3 = Math.max(maxCrossAxis3, measuredPage.getCrossAxisSize());
            currentFirstPageScrollOffset6 += pageSizeWithSpacing2;
            currentFirstPage4 = previous;
            visiblePages = visiblePages2;
            minOffset = minOffset;
            maxOffset3 = maxOffset3;
            i6 = i7;
        }
        int currentFirstPageScrollOffset7 = currentFirstPageScrollOffset6;
        int maxCrossAxis4 = maxCrossAxis3;
        int maxOffset4 = maxOffset3;
        ArrayDeque visiblePages3 = visiblePages;
        int minOffset2 = minOffset;
        int i8 = i6;
        if (currentFirstPageScrollOffset7 >= minOffset2) {
            currentFirstPageScrollOffset = currentFirstPageScrollOffset7;
        } else {
            currentFirstPageScrollOffset = minOffset2;
        }
        int currentFirstPageScrollOffset8 = currentFirstPageScrollOffset - minOffset2;
        int index3 = currentFirstPage4;
        int maxMainAxis = RangesKt.coerceAtLeast(maxOffset4 + afterContentPadding, i8);
        int currentMainAxisOffset2 = -currentFirstPageScrollOffset8;
        boolean remeasureNeeded = false;
        int indexInVisibleItems = 0;
        while (indexInVisibleItems < visiblePages3.size()) {
            if (currentMainAxisOffset2 >= maxMainAxis) {
                visiblePages3.remove(indexInVisibleItems);
                remeasureNeeded = true;
            } else {
                index3++;
                currentMainAxisOffset2 += pageSizeWithSpacing2;
                indexInVisibleItems++;
            }
        }
        int maxCrossAxis5 = maxCrossAxis4;
        boolean remeasureNeeded2 = remeasureNeeded;
        int currentFirstPage5 = currentFirstPage4;
        int maxCrossAxis6 = index3;
        int currentMainAxisOffset3 = currentMainAxisOffset2;
        int currentFirstPageScrollOffset9 = currentFirstPageScrollOffset8;
        while (true) {
            if (maxCrossAxis6 >= pageCount) {
                maxCrossAxis = maxCrossAxis5;
                break;
            }
            if (currentMainAxisOffset3 >= maxMainAxis && currentMainAxisOffset3 > 0 && !visiblePages3.isEmpty()) {
                maxCrossAxis = maxCrossAxis5;
                break;
            }
            int indexInVisibleItems2 = indexInVisibleItems;
            int maxCrossAxis7 = maxCrossAxis5;
            int maxMainAxis2 = maxMainAxis;
            MeasuredPage measuredPage2 = m794getAndMeasureSGf7dI0($this$measurePager_u2d_JDW0YA, maxCrossAxis6, childConstraints, pagerItemProvider, visualPageOffset, orientation, horizontalAlignment, verticalAlignment, $this$measurePager_u2d_JDW0YA.getLayoutDirection(), reverseLayout, pageAvailableSize);
            if (maxCrossAxis6 == pageCount - 1) {
                i5 = pageAvailableSize;
            } else {
                i5 = pageSizeWithSpacing2;
            }
            currentMainAxisOffset3 += i5;
            if (currentMainAxisOffset3 <= minOffset2 && maxCrossAxis6 != pageCount - 1) {
                currentFirstPageScrollOffset9 -= pageSizeWithSpacing2;
                maxCrossAxis5 = maxCrossAxis7;
                currentFirstPage5 = maxCrossAxis6 + 1;
                remeasureNeeded2 = true;
            } else {
                int maxCrossAxis8 = Math.max(maxCrossAxis7, measuredPage2.getCrossAxisSize());
                visiblePages3.add(measuredPage2);
                maxCrossAxis5 = maxCrossAxis8;
            }
            maxCrossAxis6++;
            indexInVisibleItems = indexInVisibleItems2;
            maxMainAxis = maxMainAxis2;
        }
        if (currentMainAxisOffset3 >= maxOffset4) {
            maxOffset = maxOffset4;
            index = maxCrossAxis6;
            maxOffset2 = 0;
            index2 = beforeContentPadding;
            currentFirstPageScrollOffset2 = currentFirstPageScrollOffset9;
            currentFirstPage = currentFirstPage5;
            int i9 = maxCrossAxis;
            maxCrossAxis2 = currentMainAxisOffset3;
            currentMainAxisOffset = i9;
        } else {
            int toScrollBack = maxOffset4 - currentMainAxisOffset3;
            int currentMainAxisOffset4 = currentMainAxisOffset3 + toScrollBack;
            int currentFirstPageScrollOffset10 = currentFirstPageScrollOffset9 - toScrollBack;
            while (true) {
                if (currentFirstPageScrollOffset10 >= beforeContentPadding) {
                    maxOffset = maxOffset4;
                    index = maxCrossAxis6;
                    index2 = beforeContentPadding;
                    maxOffset2 = 0;
                    currentFirstPageScrollOffset4 = currentFirstPageScrollOffset10;
                    break;
                }
                if (currentFirstPage5 <= 0) {
                    maxOffset = maxOffset4;
                    index = maxCrossAxis6;
                    index2 = beforeContentPadding;
                    maxOffset2 = 0;
                    currentFirstPageScrollOffset4 = currentFirstPageScrollOffset10;
                    break;
                }
                int previousIndex = currentFirstPage5 - 1;
                int index4 = maxCrossAxis6;
                MeasuredPage measuredPage3 = m794getAndMeasureSGf7dI0($this$measurePager_u2d_JDW0YA, previousIndex, childConstraints, pagerItemProvider, visualPageOffset, orientation, horizontalAlignment, verticalAlignment, $this$measurePager_u2d_JDW0YA.getLayoutDirection(), reverseLayout, pageAvailableSize);
                visiblePages3.add(0, measuredPage3);
                maxCrossAxis = Math.max(maxCrossAxis, measuredPage3.getCrossAxisSize());
                currentFirstPageScrollOffset10 += pageSizeWithSpacing2;
                currentFirstPage5 = previousIndex;
                maxCrossAxis6 = index4;
                maxOffset4 = maxOffset4;
            }
            if (currentFirstPageScrollOffset4 >= 0) {
                currentFirstPage = currentFirstPage5;
                currentFirstPageScrollOffset2 = currentFirstPageScrollOffset4;
                int i10 = maxCrossAxis;
                maxCrossAxis2 = currentMainAxisOffset4;
                currentMainAxisOffset = i10;
            } else {
                currentFirstPageScrollOffset2 = 0;
                currentFirstPage = currentFirstPage5;
                int i11 = maxCrossAxis;
                maxCrossAxis2 = currentMainAxisOffset4 + currentFirstPageScrollOffset4;
                currentMainAxisOffset = i11;
            }
        }
        if ((currentFirstPageScrollOffset2 >= 0 ? 1 : maxOffset2) == 0) {
            throw new IllegalArgumentException("invalid currentFirstPageScrollOffset".toString());
        }
        int visiblePagesScrollOffset = -currentFirstPageScrollOffset2;
        MeasuredPage firstPage2 = (MeasuredPage) visiblePages3.first();
        if (index2 > 0 || spaceBetweenPages < 0) {
            int size = visiblePages3.size();
            for (int i12 = 0; i12 < size && currentFirstPageScrollOffset2 != 0 && pageSizeWithSpacing2 <= currentFirstPageScrollOffset2 && i12 != CollectionsKt.getLastIndex(visiblePages3); i12++) {
                currentFirstPageScrollOffset2 -= pageSizeWithSpacing2;
                firstPage2 = (MeasuredPage) visiblePages3.get(i12 + 1);
            }
            currentFirstPageScrollOffset3 = currentFirstPageScrollOffset2;
            firstPage = firstPage2;
        } else {
            currentFirstPageScrollOffset3 = currentFirstPageScrollOffset2;
            firstPage = firstPage2;
        }
        MeasuredPage firstPage3 = firstPage;
        int maxCrossAxis9 = currentMainAxisOffset;
        int currentFirstPage6 = currentFirstPage;
        List extraPagesBefore = createPagesBeforeList(currentFirstPage6, beyondBoundsPageCount, list, new Function1<Integer, MeasuredPage>() { // from class: androidx.compose.foundation.pager.PagerMeasureKt$measurePager$extraPagesBefore$1
            /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
            {
                super(1);
            }

            @Override // kotlin.jvm.functions.Function1
            public /* bridge */ /* synthetic */ MeasuredPage invoke(Integer num) {
                return invoke(num.intValue());
            }

            public final MeasuredPage invoke(int it) {
                MeasuredPage m794getAndMeasureSGf7dI0;
                m794getAndMeasureSGf7dI0 = PagerMeasureKt.m794getAndMeasureSGf7dI0(LazyLayoutMeasureScope.this, it, childConstraints, pagerItemProvider, visualPageOffset, orientation, horizontalAlignment, verticalAlignment, LazyLayoutMeasureScope.this.getLayoutDirection(), reverseLayout, pageAvailableSize);
                return m794getAndMeasureSGf7dI0;
            }
        });
        int size2 = extraPagesBefore.size();
        int maxCrossAxis10 = maxCrossAxis9;
        for (int index$iv = 0; index$iv < size2; index$iv++) {
            Object item$iv = extraPagesBefore.get(index$iv);
            maxCrossAxis10 = Math.max(maxCrossAxis10, ((MeasuredPage) item$iv).getCrossAxisSize());
        }
        List extraPagesAfter = createPagesAfterList(((MeasuredPage) visiblePages3.last()).getIndex(), pageCount, beyondBoundsPageCount, list, new Function1<Integer, MeasuredPage>() { // from class: androidx.compose.foundation.pager.PagerMeasureKt$measurePager$extraPagesAfter$1
            /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
            {
                super(1);
            }

            @Override // kotlin.jvm.functions.Function1
            public /* bridge */ /* synthetic */ MeasuredPage invoke(Integer num) {
                return invoke(num.intValue());
            }

            public final MeasuredPage invoke(int it) {
                MeasuredPage m794getAndMeasureSGf7dI0;
                m794getAndMeasureSGf7dI0 = PagerMeasureKt.m794getAndMeasureSGf7dI0(LazyLayoutMeasureScope.this, it, childConstraints, pagerItemProvider, visualPageOffset, orientation, horizontalAlignment, verticalAlignment, LazyLayoutMeasureScope.this.getLayoutDirection(), reverseLayout, pageAvailableSize);
                return m794getAndMeasureSGf7dI0;
            }
        });
        int size3 = extraPagesAfter.size();
        int maxCrossAxis11 = maxCrossAxis10;
        for (int index$iv2 = 0; index$iv2 < size3; index$iv2++) {
            Object item$iv2 = extraPagesAfter.get(index$iv2);
            maxCrossAxis11 = Math.max(maxCrossAxis11, ((MeasuredPage) item$iv2).getCrossAxisSize());
        }
        boolean noExtraPages = Intrinsics.areEqual(firstPage3, visiblePages3.first()) && extraPagesBefore.isEmpty() && extraPagesAfter.isEmpty();
        int maxOffset5 = maxOffset;
        if (orientation == Orientation.Vertical) {
            i3 = maxCrossAxis11;
        } else {
            i3 = maxCrossAxis2;
        }
        int layoutWidth = ConstraintsKt.m6064constrainWidthK40F9xA(constraints, i3);
        if (orientation == Orientation.Vertical) {
            i4 = maxCrossAxis2;
        } else {
            i4 = maxCrossAxis11;
        }
        int layoutHeight = ConstraintsKt.m6063constrainHeightK40F9xA(constraints, i4);
        final List positionedPages = calculatePagesOffsets($this$measurePager_u2d_JDW0YA, visiblePages3, extraPagesBefore, extraPagesAfter, layoutWidth, layoutHeight, maxCrossAxis2, maxOffset5, visiblePagesScrollOffset, orientation, reverseLayout, $this$measurePager_u2d_JDW0YA, spaceBetweenPages, pageAvailableSize);
        if (noExtraPages) {
            pageSizeWithSpacing = pageSizeWithSpacing2;
            currentFirstPage2 = currentFirstPage6;
            visiblePagesInfo = positionedPages;
        } else {
            List $this$fastFilter$iv = positionedPages;
            ArrayList target$iv = new ArrayList($this$fastFilter$iv.size());
            pageSizeWithSpacing = pageSizeWithSpacing2;
            int pageSizeWithSpacing3 = $this$fastFilter$iv.size();
            int index$iv$iv = 0;
            while (index$iv$iv < pageSizeWithSpacing3) {
                MeasuredPage measuredPage4 = $this$fastFilter$iv.get(index$iv$iv);
                int i13 = pageSizeWithSpacing3;
                MeasuredPage it = measuredPage4;
                List $this$fastFilter$iv2 = $this$fastFilter$iv;
                int currentFirstPage7 = currentFirstPage6;
                if (it.getIndex() >= ((MeasuredPage) visiblePages3.first()).getIndex() && it.getIndex() <= ((MeasuredPage) visiblePages3.last()).getIndex()) {
                    target$iv.add(measuredPage4);
                }
                index$iv$iv++;
                pageSizeWithSpacing3 = i13;
                $this$fastFilter$iv = $this$fastFilter$iv2;
                currentFirstPage6 = currentFirstPage7;
            }
            currentFirstPage2 = currentFirstPage6;
            visiblePagesInfo = target$iv;
        }
        int pageSizeWithSpacing4 = pageSizeWithSpacing;
        int index5 = index;
        MeasuredPage newCurrentPage = calculateNewCurrentPage(orientation == Orientation.Vertical ? layoutHeight : layoutWidth, visiblePagesInfo, beforeContentPadding, afterContentPadding, pageSizeWithSpacing4, snapPositionInLayout);
        int currentPagePositionOffset = newCurrentPage != null ? newCurrentPage.getOffset() : 0;
        if (pageSizeWithSpacing4 == 0) {
            newCurrentPageOffsetFraction = 0.0f;
        } else {
            newCurrentPageOffsetFraction = RangesKt.coerceIn((-currentPagePositionOffset) / pageSizeWithSpacing4, -0.5f, 0.5f);
        }
        int maxCrossAxis12 = -beforeContentPadding;
        return new PagerMeasureResult(visiblePagesInfo, pageAvailableSize, spaceBetweenPages, afterContentPadding, orientation, maxCrossAxis12, maxOffset5 + afterContentPadding, reverseLayout, beyondBoundsPageCount, firstPage3, newCurrentPage, newCurrentPageOffsetFraction, currentFirstPageScrollOffset3, index5 < pageCount || maxCrossAxis2 > maxOffset5, function3.invoke(Integer.valueOf(layoutWidth), Integer.valueOf(layoutHeight), new Function1<Placeable.PlacementScope, Unit>() { // from class: androidx.compose.foundation.pager.PagerMeasureKt$measurePager$9
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
            public final void invoke2(Placeable.PlacementScope $this$invoke) {
                List $this$fastForEach$iv = positionedPages;
                int size4 = $this$fastForEach$iv.size();
                for (int index$iv3 = 0; index$iv3 < size4; index$iv3++) {
                    Object item$iv3 = $this$fastForEach$iv.get(index$iv3);
                    MeasuredPage it2 = (MeasuredPage) item$iv3;
                    it2.place($this$invoke);
                }
                ObservableScopeInvalidator.m730attachToScopeimpl(mutableState);
            }
        }), remeasureNeeded2);
    }

    private static final List<MeasuredPage> createPagesAfterList(int currentLastPage, int pagesCount, int beyondBoundsPageCount, List<Integer> list, Function1<? super Integer, MeasuredPage> function1) {
        ArrayList arrayList = null;
        int end = Math.min(currentLastPage + beyondBoundsPageCount, pagesCount - 1);
        int i = currentLastPage + 1;
        if (i <= end) {
            while (true) {
                if (arrayList == null) {
                    Object list2 = new ArrayList();
                    arrayList = (List) list2;
                }
                arrayList.add(function1.invoke(Integer.valueOf(i)));
                if (i == end) {
                    break;
                }
                i++;
            }
        }
        int size = list.size();
        for (int index$iv = 0; index$iv < size; index$iv++) {
            Object item$iv = list.get(index$iv);
            int pageIndex = ((Number) item$iv).intValue();
            boolean z = false;
            if (end + 1 <= pageIndex && pageIndex < pagesCount) {
                z = true;
            }
            if (z) {
                if (arrayList == null) {
                    Object list3 = new ArrayList();
                    arrayList = (List) list3;
                }
                arrayList.add(function1.invoke(Integer.valueOf(pageIndex)));
            }
        }
        return arrayList == null ? CollectionsKt.emptyList() : arrayList;
    }

    private static final List<MeasuredPage> createPagesBeforeList(int currentFirstPage, int beyondBoundsPageCount, List<Integer> list, Function1<? super Integer, MeasuredPage> function1) {
        ArrayList arrayList = null;
        int start = Math.max(0, currentFirstPage - beyondBoundsPageCount);
        int i = currentFirstPage - 1;
        if (start <= i) {
            while (true) {
                if (arrayList == null) {
                    Object list2 = new ArrayList();
                    arrayList = (List) list2;
                }
                arrayList.add(function1.invoke(Integer.valueOf(i)));
                if (i == start) {
                    break;
                }
                i--;
            }
        }
        int size = list.size();
        for (int index$iv = 0; index$iv < size; index$iv++) {
            Object item$iv = list.get(index$iv);
            int pageIndex = ((Number) item$iv).intValue();
            if (pageIndex < start) {
                if (arrayList == null) {
                    Object list3 = new ArrayList();
                    arrayList = (List) list3;
                }
                arrayList.add(function1.invoke(Integer.valueOf(pageIndex)));
            }
        }
        return arrayList == null ? CollectionsKt.emptyList() : arrayList;
    }

    private static final MeasuredPage calculateNewCurrentPage(int viewportSize, List<MeasuredPage> list, int beforeContentPadding, int afterContentPadding, int itemSize, SnapPositionInLayout snapPositionInLayout) {
        Object maxElem$iv;
        if (list.isEmpty()) {
            maxElem$iv = null;
        } else {
            maxElem$iv = list.get(0);
            MeasuredPage it = (MeasuredPage) maxElem$iv;
            float maxValue$iv = -Math.abs(SnapPositionInLayoutKt.calculateDistanceToDesiredSnapPosition(viewportSize, beforeContentPadding, afterContentPadding, itemSize, it.getOffset(), it.getIndex(), snapPositionInLayout));
            int i$iv = 1;
            int lastIndex = CollectionsKt.getLastIndex(list);
            if (1 <= lastIndex) {
                while (true) {
                    Object e$iv = list.get(i$iv);
                    MeasuredPage it2 = (MeasuredPage) e$iv;
                    float v$iv = -Math.abs(SnapPositionInLayoutKt.calculateDistanceToDesiredSnapPosition(viewportSize, beforeContentPadding, afterContentPadding, itemSize, it2.getOffset(), it2.getIndex(), snapPositionInLayout));
                    if (Float.compare(maxValue$iv, v$iv) < 0) {
                        maxElem$iv = e$iv;
                        maxValue$iv = v$iv;
                    }
                    if (i$iv == lastIndex) {
                        break;
                    }
                    i$iv++;
                }
            }
        }
        return (MeasuredPage) maxElem$iv;
    }

    /* JADX INFO: Access modifiers changed from: private */
    /* renamed from: getAndMeasure-SGf7dI0, reason: not valid java name */
    public static final MeasuredPage m794getAndMeasureSGf7dI0(LazyLayoutMeasureScope $this$getAndMeasure_u2dSGf7dI0, int index, long childConstraints, PagerLazyLayoutItemProvider pagerItemProvider, long visualPageOffset, Orientation orientation, Alignment.Horizontal horizontalAlignment, Alignment.Vertical verticalAlignment, LayoutDirection layoutDirection, boolean reverseLayout, int pageAvailableSize) {
        Object key = pagerItemProvider.getKey(index);
        List placeable = $this$getAndMeasure_u2dSGf7dI0.mo726measure0kLqBqw(index, childConstraints);
        return new MeasuredPage(index, pageAvailableSize, placeable, visualPageOffset, key, orientation, horizontalAlignment, verticalAlignment, layoutDirection, reverseLayout, null);
    }

    private static final List<MeasuredPage> calculatePagesOffsets(LazyLayoutMeasureScope $this$calculatePagesOffsets, List<MeasuredPage> list, List<MeasuredPage> list2, List<MeasuredPage> list3, int layoutWidth, int layoutHeight, int finalMainAxisOffset, int maxOffset, int pagesScrollOffset, Orientation orientation, boolean reverseLayout, Density density, int spaceBetweenPages, int pageAvailableSize) {
        ArrayList positionedPages;
        int[] offsets;
        int pagesCount;
        int i;
        int pageSizeWithSpacing = pageAvailableSize + spaceBetweenPages;
        int mainAxisLayoutSize = orientation == Orientation.Vertical ? layoutHeight : layoutWidth;
        boolean hasSpareSpace = finalMainAxisOffset < Math.min(mainAxisLayoutSize, maxOffset);
        if (hasSpareSpace) {
            if (!(pagesScrollOffset == 0)) {
                throw new IllegalStateException(("non-zero pagesScrollOffset=" + pagesScrollOffset).toString());
            }
        }
        ArrayList positionedPages2 = new ArrayList(list.size() + list2.size() + list3.size());
        if (hasSpareSpace) {
            if (!(list2.isEmpty() && list3.isEmpty())) {
                throw new IllegalArgumentException("No extra pages".toString());
            }
            int pagesCount2 = list.size();
            int[] sizes = new int[pagesCount2];
            for (int i2 = 0; i2 < pagesCount2; i2++) {
                sizes[i2] = pageAvailableSize;
            }
            int[] offsets2 = new int[pagesCount2];
            for (int i3 = 0; i3 < pagesCount2; i3++) {
                offsets2[i3] = 0;
            }
            Arrangement.HorizontalOrVertical arrangement = Arrangement.Absolute.INSTANCE.m474spacedBy0680j_4($this$calculatePagesOffsets.mo310toDpu2uoSUM(spaceBetweenPages));
            if (orientation != Orientation.Vertical) {
                offsets = offsets2;
                pagesCount = pagesCount2;
                positionedPages = positionedPages2;
                arrangement.arrange(density, mainAxisLayoutSize, sizes, LayoutDirection.Ltr, offsets);
            } else {
                arrangement.arrange(density, mainAxisLayoutSize, sizes, offsets2);
                offsets = offsets2;
                pagesCount = pagesCount2;
                positionedPages = positionedPages2;
            }
            IntRange reverseAwareOffsetIndices = ArraysKt.getIndices(offsets);
            if (reverseLayout) {
                reverseAwareOffsetIndices = RangesKt.reversed(reverseAwareOffsetIndices);
            }
            int index = reverseAwareOffsetIndices.getFirst();
            int last = reverseAwareOffsetIndices.getLast();
            int step = reverseAwareOffsetIndices.getStep();
            if ((step > 0 && index <= last) || (step < 0 && last <= index)) {
                while (true) {
                    int absoluteOffset = offsets[index];
                    int pagesCount3 = pagesCount;
                    MeasuredPage page = list.get(calculatePagesOffsets$reverseAware(index, reverseLayout, pagesCount));
                    if (reverseLayout) {
                        i = (mainAxisLayoutSize - absoluteOffset) - page.getSize();
                    } else {
                        i = absoluteOffset;
                    }
                    int relativeOffset = i;
                    page.position(relativeOffset, layoutWidth, layoutHeight);
                    positionedPages.add(page);
                    if (index == last) {
                        break;
                    }
                    index += step;
                    pagesCount = pagesCount3;
                }
            }
        } else {
            positionedPages = positionedPages2;
            int currentMainAxis = pagesScrollOffset;
            int size = list2.size();
            for (int index$iv = 0; index$iv < size; index$iv++) {
                Object item$iv = list2.get(index$iv);
                MeasuredPage it = (MeasuredPage) item$iv;
                currentMainAxis -= pageSizeWithSpacing;
                it.position(currentMainAxis, layoutWidth, layoutHeight);
                positionedPages.add(it);
            }
            int currentMainAxis2 = pagesScrollOffset;
            int size2 = list.size();
            for (int index$iv2 = 0; index$iv2 < size2; index$iv2++) {
                Object item$iv2 = list.get(index$iv2);
                MeasuredPage it2 = (MeasuredPage) item$iv2;
                it2.position(currentMainAxis2, layoutWidth, layoutHeight);
                positionedPages.add(it2);
                currentMainAxis2 += pageSizeWithSpacing;
            }
            int size3 = list3.size();
            for (int index$iv3 = 0; index$iv3 < size3; index$iv3++) {
                Object item$iv3 = list3.get(index$iv3);
                MeasuredPage it3 = (MeasuredPage) item$iv3;
                it3.position(currentMainAxis2, layoutWidth, layoutHeight);
                positionedPages.add(it3);
                currentMainAxis2 += pageSizeWithSpacing;
            }
        }
        return positionedPages;
    }

    private static final int calculatePagesOffsets$reverseAware(int $this$calculatePagesOffsets_u24reverseAware, boolean $reverseLayout, int pagesCount) {
        return !$reverseLayout ? $this$calculatePagesOffsets_u24reverseAware : (pagesCount - $this$calculatePagesOffsets_u24reverseAware) - 1;
    }

    private static final void debugLog(Function0<String> function0) {
    }
}
