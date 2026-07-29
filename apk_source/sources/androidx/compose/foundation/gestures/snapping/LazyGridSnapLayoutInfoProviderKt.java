package androidx.compose.foundation.gestures.snapping;

import androidx.compose.animation.SplineBasedDecayKt;
import androidx.compose.animation.core.DecayAnimationSpec;
import androidx.compose.animation.core.DecayAnimationSpecKt;
import androidx.compose.foundation.gestures.Orientation;
import androidx.compose.foundation.lazy.grid.LazyGridItemInfo;
import androidx.compose.foundation.lazy.grid.LazyGridLayoutInfo;
import androidx.compose.foundation.lazy.grid.LazyGridState;
import androidx.compose.ui.unit.Density;
import androidx.compose.ui.unit.IntOffset;
import androidx.compose.ui.unit.IntSize;
import java.util.ArrayList;
import java.util.List;
import kotlin.Metadata;
import kotlin.ranges.RangesKt;

/* compiled from: LazyGridSnapLayoutInfoProvider.kt */
@Metadata(d1 = {"\u0000.\n\u0000\n\u0002\u0010\b\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0002\u001a\u001a\u0010\u0005\u001a\u00020\u00062\u0006\u0010\u0007\u001a\u00020\b2\b\b\u0002\u0010\t\u001a\u00020\nH\u0007\u001a\u0014\u0010\u000b\u001a\u00020\u0001*\u00020\f2\u0006\u0010\r\u001a\u00020\u000eH\u0000\u001a\u0014\u0010\u000f\u001a\u00020\u0001*\u00020\f2\u0006\u0010\r\u001a\u00020\u000eH\u0000\"\u0018\u0010\u0000\u001a\u00020\u0001*\u00020\u00028@X\u0080\u0004¢\u0006\u0006\u001a\u0004\b\u0003\u0010\u0004¨\u0006\u0010"}, d2 = {"singleAxisViewportSize", "", "Landroidx/compose/foundation/lazy/grid/LazyGridLayoutInfo;", "getSingleAxisViewportSize", "(Landroidx/compose/foundation/lazy/grid/LazyGridLayoutInfo;)I", "SnapLayoutInfoProvider", "Landroidx/compose/foundation/gestures/snapping/SnapLayoutInfoProvider;", "lazyGridState", "Landroidx/compose/foundation/lazy/grid/LazyGridState;", "positionInLayout", "Landroidx/compose/foundation/gestures/snapping/SnapPositionInLayout;", "offsetOnMainAxis", "Landroidx/compose/foundation/lazy/grid/LazyGridItemInfo;", "orientation", "Landroidx/compose/foundation/gestures/Orientation;", "sizeOnMainAxis", "foundation_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class LazyGridSnapLayoutInfoProviderKt {
    public static /* synthetic */ SnapLayoutInfoProvider SnapLayoutInfoProvider$default(LazyGridState lazyGridState, SnapPositionInLayout snapPositionInLayout, int i, Object obj) {
        if ((i & 2) != 0) {
            snapPositionInLayout = SnapPositionInLayout.INSTANCE.getCenterToCenter();
        }
        return SnapLayoutInfoProvider(lazyGridState, snapPositionInLayout);
    }

    public static final SnapLayoutInfoProvider SnapLayoutInfoProvider(final LazyGridState lazyGridState, final SnapPositionInLayout positionInLayout) {
        return new SnapLayoutInfoProvider() { // from class: androidx.compose.foundation.gestures.snapping.LazyGridSnapLayoutInfoProviderKt$SnapLayoutInfoProvider$1
            private final LazyGridLayoutInfo getLayoutInfo() {
                return LazyGridState.this.getLayoutInfo();
            }

            @Override // androidx.compose.foundation.gestures.snapping.SnapLayoutInfoProvider
            public float calculateApproachOffset(float initialVelocity) {
                DecayAnimationSpec decayAnimationSpec = SplineBasedDecayKt.splineBasedDecay(LazyGridState.this.getDensity());
                float offset = Math.abs(DecayAnimationSpecKt.calculateTargetValue(decayAnimationSpec, 0.0f, initialVelocity));
                float estimatedNumberOfItemsInDecay = (float) Math.floor(Math.abs(offset) / averageItemSize());
                float approachOffset = (averageItemSize() * estimatedNumberOfItemsInDecay) - averageItemSize();
                float finalDecayOffset = RangesKt.coerceAtLeast(approachOffset, 0.0f);
                if (finalDecayOffset == 0.0f) {
                    return finalDecayOffset;
                }
                return Math.signum(initialVelocity) * finalDecayOffset;
            }

            private final List<LazyGridItemInfo> singleAxisItems() {
                List $this$fastFilter$iv = LazyGridState.this.getLayoutInfo().getVisibleItemsInfo();
                LazyGridState lazyGridState2 = LazyGridState.this;
                List target$iv = new ArrayList($this$fastFilter$iv.size());
                int size = $this$fastFilter$iv.size();
                for (int index$iv$iv = 0; index$iv$iv < size; index$iv$iv++) {
                    LazyGridItemInfo lazyGridItemInfo = $this$fastFilter$iv.get(index$iv$iv);
                    LazyGridItemInfo it = lazyGridItemInfo;
                    boolean z = false;
                    if (lazyGridState2.getLayoutInfo().getOrientation() == Orientation.Horizontal) {
                        if (it.getRow() == 0) {
                            z = true;
                        }
                    } else if (it.getColumn() == 0) {
                        z = true;
                    }
                    if (z) {
                        target$iv.add(lazyGridItemInfo);
                    }
                }
                return target$iv;
            }

            @Override // androidx.compose.foundation.gestures.snapping.SnapLayoutInfoProvider
            public float calculateSnappingOffset(float currentVelocity) {
                float distanceFromItemBeforeTarget = Float.NEGATIVE_INFINITY;
                float distanceFromItemAfterTarget = Float.POSITIVE_INFINITY;
                List $this$fastForEach$iv = getLayoutInfo().getVisibleItemsInfo();
                SnapPositionInLayout snapPositionInLayout = positionInLayout;
                int size = $this$fastForEach$iv.size();
                for (int index$iv = 0; index$iv < size; index$iv++) {
                    Object item$iv = $this$fastForEach$iv.get(index$iv);
                    LazyGridItemInfo item = (LazyGridItemInfo) item$iv;
                    float distance = SnapPositionInLayoutKt.calculateDistanceToDesiredSnapPosition(LazyGridSnapLayoutInfoProviderKt.getSingleAxisViewportSize(getLayoutInfo()), getLayoutInfo().getBeforeContentPadding(), getLayoutInfo().getAfterContentPadding(), LazyGridSnapLayoutInfoProviderKt.sizeOnMainAxis(item, getLayoutInfo().getOrientation()), LazyGridSnapLayoutInfoProviderKt.offsetOnMainAxis(item, getLayoutInfo().getOrientation()), item.getIndex(), snapPositionInLayout);
                    if (distance <= 0.0f && distance > distanceFromItemBeforeTarget) {
                        distanceFromItemBeforeTarget = distance;
                    }
                    if (distance >= 0.0f && distance < distanceFromItemAfterTarget) {
                        distanceFromItemAfterTarget = distance;
                    }
                }
                Density $this$calculateSnappingOffset_u24lambda_u242 = LazyGridState.this.getDensity();
                return SnapFlingBehaviorKt.m437calculateFinalOffsetFhqu1e0(LazyListSnapLayoutInfoProviderKt.calculateFinalSnappingItem($this$calculateSnappingOffset_u24lambda_u242, currentVelocity), distanceFromItemBeforeTarget, distanceFromItemAfterTarget);
            }

            public final float averageItemSize() {
                int sum$iv;
                List items = singleAxisItems();
                if (!items.isEmpty()) {
                    if (getLayoutInfo().getOrientation() == Orientation.Vertical) {
                        sum$iv = 0;
                        int size = items.size();
                        for (int index$iv$iv = 0; index$iv$iv < size; index$iv$iv++) {
                            Object item$iv$iv = items.get(index$iv$iv);
                            LazyGridItemInfo it = (LazyGridItemInfo) item$iv$iv;
                            sum$iv += IntSize.m6263getHeightimpl(it.getSize());
                        }
                    } else {
                        sum$iv = 0;
                        int size2 = items.size();
                        for (int index$iv$iv2 = 0; index$iv$iv2 < size2; index$iv$iv2++) {
                            Object item$iv$iv2 = items.get(index$iv$iv2);
                            LazyGridItemInfo it2 = (LazyGridItemInfo) item$iv$iv2;
                            sum$iv += IntSize.m6264getWidthimpl(it2.getSize());
                        }
                    }
                    int size3 = sum$iv;
                    return size3 / items.size();
                }
                return 0.0f;
            }
        };
    }

    public static final int getSingleAxisViewportSize(LazyGridLayoutInfo $this$singleAxisViewportSize) {
        if ($this$singleAxisViewportSize.getOrientation() == Orientation.Vertical) {
            return IntSize.m6263getHeightimpl($this$singleAxisViewportSize.mo699getViewportSizeYbymL2g());
        }
        return IntSize.m6264getWidthimpl($this$singleAxisViewportSize.mo699getViewportSizeYbymL2g());
    }

    public static final int sizeOnMainAxis(LazyGridItemInfo $this$sizeOnMainAxis, Orientation orientation) {
        if (orientation == Orientation.Vertical) {
            return IntSize.m6263getHeightimpl($this$sizeOnMainAxis.getSize());
        }
        return IntSize.m6264getWidthimpl($this$sizeOnMainAxis.getSize());
    }

    public static final int offsetOnMainAxis(LazyGridItemInfo $this$offsetOnMainAxis, Orientation orientation) {
        if (orientation == Orientation.Vertical) {
            return IntOffset.m6223getYimpl($this$offsetOnMainAxis.getOffset());
        }
        return IntOffset.m6222getXimpl($this$offsetOnMainAxis.getOffset());
    }
}
