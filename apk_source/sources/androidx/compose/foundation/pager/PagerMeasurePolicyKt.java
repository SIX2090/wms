package androidx.compose.foundation.pager;

import androidx.compose.foundation.CheckScrollableContainerConstraintsKt;
import androidx.compose.foundation.gestures.Orientation;
import androidx.compose.foundation.gestures.snapping.SnapPositionInLayout;
import androidx.compose.foundation.layout.PaddingKt;
import androidx.compose.foundation.layout.PaddingValues;
import androidx.compose.foundation.lazy.layout.LazyLayoutBeyondBoundsStateKt;
import androidx.compose.foundation.lazy.layout.LazyLayoutMeasureScope;
import androidx.compose.runtime.Composer;
import androidx.compose.runtime.ComposerKt;
import androidx.compose.runtime.snapshots.Snapshot;
import androidx.compose.ui.Alignment;
import androidx.compose.ui.layout.MeasureResult;
import androidx.compose.ui.layout.Placeable;
import androidx.compose.ui.unit.Constraints;
import androidx.compose.ui.unit.ConstraintsKt;
import androidx.compose.ui.unit.Dp;
import androidx.compose.ui.unit.IntOffsetKt;
import java.util.List;
import kotlin.Metadata;
import kotlin.Unit;
import kotlin.collections.MapsKt;
import kotlin.jvm.functions.Function0;
import kotlin.jvm.functions.Function1;
import kotlin.jvm.functions.Function2;
import kotlin.jvm.functions.Function3;
import kotlin.math.MathKt;

/* compiled from: PagerMeasurePolicy.kt */
@Metadata(d1 = {"\u0000n\n\u0000\n\u0002\u0010\u000b\n\u0000\n\u0002\u0010\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\u0010\u000e\n\u0000\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010\b\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0006\u001a\u0017\u0010\u0002\u001a\u00020\u00032\f\u0010\u0004\u001a\b\u0012\u0004\u0012\u00020\u00060\u0005H\u0082\b\u001a\u0099\u0001\u0010\u0007\u001a\u0019\u0012\u0004\u0012\u00020\t\u0012\u0004\u0012\u00020\n\u0012\u0004\u0012\u00020\u000b0\b¢\u0006\u0002\b\f2\f\u0010\r\u001a\b\u0012\u0004\u0012\u00020\u000e0\u00052\u0006\u0010\u000f\u001a\u00020\u00102\u0006\u0010\u0011\u001a\u00020\u00122\u0006\u0010\u0013\u001a\u00020\u00012\u0006\u0010\u0014\u001a\u00020\u00152\u0006\u0010\u0016\u001a\u00020\u00172\u0006\u0010\u0018\u001a\u00020\u00192\u0006\u0010\u001a\u001a\u00020\u001b2\b\u0010\u001c\u001a\u0004\u0018\u00010\u001d2\b\u0010\u001e\u001a\u0004\u0018\u00010\u001f2\u0006\u0010 \u001a\u00020!2\f\u0010\"\u001a\b\u0012\u0004\u0012\u00020\u00170\u0005H\u0001ø\u0001\u0000¢\u0006\u0004\b#\u0010$\u001a\u0014\u0010%\u001a\u00020\u0017*\u00020\u00102\u0006\u0010&\u001a\u00020\u0017H\u0000\"\u000e\u0010\u0000\u001a\u00020\u0001X\u0082T¢\u0006\u0002\n\u0000\u0082\u0002\u0007\n\u0005\b¡\u001e0\u0001¨\u0006'"}, d2 = {"DEBUG", "", "debugLog", "", "generateMsg", "Lkotlin/Function0;", "", "rememberPagerMeasurePolicy", "Lkotlin/Function2;", "Landroidx/compose/foundation/lazy/layout/LazyLayoutMeasureScope;", "Landroidx/compose/ui/unit/Constraints;", "Landroidx/compose/ui/layout/MeasureResult;", "Lkotlin/ExtensionFunctionType;", "itemProviderLambda", "Landroidx/compose/foundation/pager/PagerLazyLayoutItemProvider;", "state", "Landroidx/compose/foundation/pager/PagerState;", "contentPadding", "Landroidx/compose/foundation/layout/PaddingValues;", "reverseLayout", "orientation", "Landroidx/compose/foundation/gestures/Orientation;", "beyondBoundsPageCount", "", "pageSpacing", "Landroidx/compose/ui/unit/Dp;", "pageSize", "Landroidx/compose/foundation/pager/PageSize;", "horizontalAlignment", "Landroidx/compose/ui/Alignment$Horizontal;", "verticalAlignment", "Landroidx/compose/ui/Alignment$Vertical;", "snapPositionInLayout", "Landroidx/compose/foundation/gestures/snapping/SnapPositionInLayout;", "pageCount", "rememberPagerMeasurePolicy-121YqSk", "(Lkotlin/jvm/functions/Function0;Landroidx/compose/foundation/pager/PagerState;Landroidx/compose/foundation/layout/PaddingValues;ZLandroidx/compose/foundation/gestures/Orientation;IFLandroidx/compose/foundation/pager/PageSize;Landroidx/compose/ui/Alignment$Horizontal;Landroidx/compose/ui/Alignment$Vertical;Landroidx/compose/foundation/gestures/snapping/SnapPositionInLayout;Lkotlin/jvm/functions/Function0;Landroidx/compose/runtime/Composer;II)Lkotlin/jvm/functions/Function2;", "calculateCurrentPageLayoutOffset", "pageSizeWithSpacing", "foundation_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class PagerMeasurePolicyKt {
    private static final boolean DEBUG = false;

    /* renamed from: rememberPagerMeasurePolicy-121YqSk, reason: not valid java name */
    public static final Function2<LazyLayoutMeasureScope, Constraints, MeasureResult> m796rememberPagerMeasurePolicy121YqSk(final Function0<PagerLazyLayoutItemProvider> function0, final PagerState state, final PaddingValues contentPadding, final boolean reverseLayout, final Orientation orientation, final int beyondBoundsPageCount, final float pageSpacing, final PageSize pageSize, final Alignment.Horizontal horizontalAlignment, final Alignment.Vertical verticalAlignment, final SnapPositionInLayout snapPositionInLayout, final Function0<Integer> function02, Composer $composer, int $changed, int $changed1) {
        Object value$iv$iv;
        $composer.startReplaceableGroup(-1615726010);
        ComposerKt.sourceInformation($composer, "C(rememberPagerMeasurePolicy)P(3,10,1,8,4!1,7:c#ui.unit.Dp,6!1,11,9)56@2324L5682:PagerMeasurePolicy.kt#g6yjnt");
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventStart(-1615726010, $changed, $changed1, "androidx.compose.foundation.pager.rememberPagerMeasurePolicy (PagerMeasurePolicy.kt:56)");
        }
        Object[] keys$iv = {state, contentPadding, Boolean.valueOf(reverseLayout), orientation, horizontalAlignment, verticalAlignment, Dp.m6092boximpl(pageSpacing), pageSize, snapPositionInLayout, function02};
        $composer.startReplaceableGroup(-568225417);
        ComposerKt.sourceInformation($composer, "CC(remember)P(1):Composables.kt#9igjgp");
        boolean invalid$iv = false;
        for (Object key$iv : keys$iv) {
            invalid$iv |= $composer.changed(key$iv);
        }
        Object it$iv$iv = $composer.rememberedValue();
        if (invalid$iv || it$iv$iv == Composer.INSTANCE.getEmpty()) {
            value$iv$iv = new Function2<LazyLayoutMeasureScope, Constraints, PagerMeasureResult>() { // from class: androidx.compose.foundation.pager.PagerMeasurePolicyKt$rememberPagerMeasurePolicy$1$1
                /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
                {
                    super(2);
                }

                @Override // kotlin.jvm.functions.Function2
                public /* bridge */ /* synthetic */ PagerMeasureResult invoke(LazyLayoutMeasureScope lazyLayoutMeasureScope, Constraints constraints) {
                    return m797invoke0kLqBqw(lazyLayoutMeasureScope, constraints.getValue());
                }

                /* renamed from: invoke-0kLqBqw, reason: not valid java name */
                public final PagerMeasureResult m797invoke0kLqBqw(final LazyLayoutMeasureScope $this$null, final long containerConstraints) {
                    int i;
                    int i2;
                    int i3;
                    int m6050getMaxWidthimpl;
                    long visualItemOffset;
                    int i4;
                    int i5;
                    Snapshot this_$iv$iv;
                    Snapshot previous$iv$iv;
                    int currentPage;
                    int currentPageOffset;
                    boolean isVertical = Orientation.this == Orientation.Vertical;
                    CheckScrollableContainerConstraintsKt.m238checkScrollableContainerConstraintsK40F9xA(containerConstraints, isVertical ? Orientation.Vertical : Orientation.Horizontal);
                    if (isVertical) {
                        i = $this$null.mo307roundToPx0680j_4(contentPadding.mo513calculateLeftPaddingu2uoSUM($this$null.getLayoutDirection()));
                    } else {
                        i = $this$null.mo307roundToPx0680j_4(PaddingKt.calculateStartPadding(contentPadding, $this$null.getLayoutDirection()));
                    }
                    int startPadding = i;
                    if (isVertical) {
                        i2 = $this$null.mo307roundToPx0680j_4(contentPadding.mo514calculateRightPaddingu2uoSUM($this$null.getLayoutDirection()));
                    } else {
                        i2 = $this$null.mo307roundToPx0680j_4(PaddingKt.calculateEndPadding(contentPadding, $this$null.getLayoutDirection()));
                    }
                    int endPadding = i2;
                    int topPadding = $this$null.mo307roundToPx0680j_4(contentPadding.getTop());
                    int bottomPadding = $this$null.mo307roundToPx0680j_4(contentPadding.getBottom());
                    final int totalVerticalPadding = topPadding + bottomPadding;
                    final int totalHorizontalPadding = startPadding + endPadding;
                    int totalMainAxisPadding = isVertical ? totalVerticalPadding : totalHorizontalPadding;
                    if (isVertical && !reverseLayout) {
                        i3 = topPadding;
                    } else if (isVertical && reverseLayout) {
                        i3 = bottomPadding;
                    } else {
                        i3 = (isVertical || reverseLayout) ? endPadding : startPadding;
                    }
                    int beforeContentPadding = i3;
                    int afterContentPadding = totalMainAxisPadding - beforeContentPadding;
                    long contentConstraints = ConstraintsKt.m6066offsetNN6EwU(containerConstraints, -totalHorizontalPadding, -totalVerticalPadding);
                    state.setDensity$foundation_release($this$null);
                    int spaceBetweenPages = $this$null.mo307roundToPx0680j_4(pageSpacing);
                    if (isVertical) {
                        m6050getMaxWidthimpl = Constraints.m6049getMaxHeightimpl(containerConstraints) - totalVerticalPadding;
                    } else {
                        m6050getMaxWidthimpl = Constraints.m6050getMaxWidthimpl(containerConstraints) - totalHorizontalPadding;
                    }
                    int mainAxisAvailableSize = m6050getMaxWidthimpl;
                    if (!reverseLayout || mainAxisAvailableSize > 0) {
                        visualItemOffset = IntOffsetKt.IntOffset(startPadding, topPadding);
                    } else {
                        visualItemOffset = IntOffsetKt.IntOffset(isVertical ? startPadding : startPadding + mainAxisAvailableSize, isVertical ? topPadding + mainAxisAvailableSize : topPadding);
                    }
                    PageSize $this$invoke_0kLqBqw_u24lambda_u240 = pageSize;
                    int calculateMainAxisPageSize = $this$invoke_0kLqBqw_u24lambda_u240.calculateMainAxisPageSize($this$null, mainAxisAvailableSize, spaceBetweenPages);
                    PagerState pagerState = state;
                    if (Orientation.this == Orientation.Vertical) {
                        i4 = Constraints.m6050getMaxWidthimpl(contentConstraints);
                    } else {
                        i4 = calculateMainAxisPageSize;
                    }
                    if (Orientation.this != Orientation.Vertical) {
                        i5 = Constraints.m6049getMaxHeightimpl(contentConstraints);
                    } else {
                        i5 = calculateMainAxisPageSize;
                    }
                    pagerState.m801setPremeasureConstraintsBRTryo0$foundation_release(ConstraintsKt.Constraints$default(0, i4, 0, i5, 5, null));
                    PagerLazyLayoutItemProvider itemProvider = function0.invoke();
                    int pageSizeWithSpacing = calculateMainAxisPageSize + spaceBetweenPages;
                    Snapshot.Companion this_$iv = Snapshot.INSTANCE;
                    PagerState pagerState2 = state;
                    Snapshot snapshot$iv = this_$iv.createNonObservableSnapshot();
                    try {
                        Snapshot previous$iv$iv2 = snapshot$iv.makeCurrent();
                        try {
                            currentPage = pagerState2.matchScrollPositionWithKey$foundation_release(itemProvider, pagerState2.getCurrentPage());
                            try {
                                currentPageOffset = PagerMeasurePolicyKt.calculateCurrentPageLayoutOffset(pagerState2, pageSizeWithSpacing);
                            } catch (Throwable th) {
                                th = th;
                                this_$iv$iv = snapshot$iv;
                                previous$iv$iv = previous$iv$iv2;
                            }
                        } catch (Throwable th2) {
                            th = th2;
                            this_$iv$iv = snapshot$iv;
                            previous$iv$iv = previous$iv$iv2;
                        }
                        try {
                            Unit unit = Unit.INSTANCE;
                            try {
                                snapshot$iv.restoreCurrent(previous$iv$iv2);
                                snapshot$iv.dispose();
                                List pinnedPages = LazyLayoutBeyondBoundsStateKt.calculateLazyLayoutPinnedIndices(itemProvider, state.getPinnedPages(), state.getBeyondBoundsInfo());
                                PagerMeasureResult it = PagerMeasureKt.m795measurePager_JDW0YA($this$null, function02.invoke().intValue(), itemProvider, mainAxisAvailableSize, beforeContentPadding, afterContentPadding, spaceBetweenPages, currentPage, currentPageOffset, contentConstraints, Orientation.this, verticalAlignment, horizontalAlignment, reverseLayout, visualItemOffset, calculateMainAxisPageSize, beyondBoundsPageCount, pinnedPages, snapPositionInLayout, state.m798getPlacementScopeInvalidatorzYiylxw$foundation_release(), new Function3<Integer, Integer, Function1<? super Placeable.PlacementScope, ? extends Unit>, MeasureResult>() { // from class: androidx.compose.foundation.pager.PagerMeasurePolicyKt$rememberPagerMeasurePolicy$1$1.2
                                    /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
                                    {
                                        super(3);
                                    }

                                    @Override // kotlin.jvm.functions.Function3
                                    public /* bridge */ /* synthetic */ MeasureResult invoke(Integer num, Integer num2, Function1<? super Placeable.PlacementScope, ? extends Unit> function1) {
                                        return invoke(num.intValue(), num2.intValue(), (Function1<? super Placeable.PlacementScope, Unit>) function1);
                                    }

                                    public final MeasureResult invoke(int width, int height, Function1<? super Placeable.PlacementScope, Unit> function1) {
                                        return LazyLayoutMeasureScope.this.layout(ConstraintsKt.m6064constrainWidthK40F9xA(containerConstraints, totalHorizontalPadding + width), ConstraintsKt.m6063constrainHeightK40F9xA(containerConstraints, totalVerticalPadding + height), MapsKt.emptyMap(), function1);
                                    }
                                });
                                PagerState.applyMeasureResult$foundation_release$default(state, it, false, 2, null);
                                return it;
                            } catch (Throwable th3) {
                                th = th3;
                                snapshot$iv.dispose();
                                throw th;
                            }
                        } catch (Throwable th4) {
                            th = th4;
                            this_$iv$iv = snapshot$iv;
                            previous$iv$iv = previous$iv$iv2;
                            try {
                                this_$iv$iv.restoreCurrent(previous$iv$iv);
                                throw th;
                            } catch (Throwable th5) {
                                th = th5;
                                snapshot$iv.dispose();
                                throw th;
                            }
                        }
                    } catch (Throwable th6) {
                        th = th6;
                    }
                }
            };
            $composer.updateRememberedValue(value$iv$iv);
        } else {
            value$iv$iv = it$iv$iv;
        }
        $composer.endReplaceableGroup();
        Function2<LazyLayoutMeasureScope, Constraints, MeasureResult> function2 = (Function2) value$iv$iv;
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventEnd();
        }
        $composer.endReplaceableGroup();
        return function2;
    }

    private static final void debugLog(Function0<String> function0) {
    }

    public static final int calculateCurrentPageLayoutOffset(PagerState $this$calculateCurrentPageLayoutOffset, int pageSizeWithSpacing) {
        Object it$iv;
        List $this$fastFirstOrNull$iv = $this$calculateCurrentPageLayoutOffset.getLayoutInfo().getVisiblePagesInfo();
        int index$iv$iv = 0;
        int size = $this$fastFirstOrNull$iv.size();
        while (true) {
            if (index$iv$iv >= size) {
                it$iv = null;
                break;
            }
            Object item$iv$iv = $this$fastFirstOrNull$iv.get(index$iv$iv);
            it$iv = item$iv$iv;
            PageInfo it = (PageInfo) it$iv;
            if (it.getIndex() == $this$calculateCurrentPageLayoutOffset.getCurrentPage()) {
                break;
            }
            index$iv$iv++;
        }
        PageInfo pageInfo = (PageInfo) it$iv;
        int previousPassOffset = pageInfo != null ? pageInfo.getOffset() : 0;
        float previousPassFraction = pageSizeWithSpacing == 0 ? $this$calculateCurrentPageLayoutOffset.getCurrentPageOffsetFraction() : (-previousPassOffset) / pageSizeWithSpacing;
        float fractionDiff = $this$calculateCurrentPageLayoutOffset.getCurrentPageOffsetFraction() - previousPassFraction;
        return -MathKt.roundToInt((pageSizeWithSpacing * fractionDiff) - previousPassOffset);
    }
}
