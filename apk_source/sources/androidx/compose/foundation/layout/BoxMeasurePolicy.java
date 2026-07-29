package androidx.compose.foundation.layout;

import androidx.compose.ui.Alignment;
import androidx.compose.ui.layout.Measurable;
import androidx.compose.ui.layout.MeasurePolicy;
import androidx.compose.ui.layout.MeasureResult;
import androidx.compose.ui.layout.MeasureScope;
import androidx.compose.ui.layout.Placeable;
import androidx.compose.ui.unit.Constraints;
import androidx.compose.ui.unit.ConstraintsKt;
import androidx.compose.ui.unit.LayoutDirection;
import java.util.List;
import kotlin.Metadata;
import kotlin.Unit;
import kotlin.jvm.functions.Function1;
import kotlin.jvm.internal.Intrinsics;
import kotlin.jvm.internal.Ref;

/* compiled from: Box.kt */
@Metadata(d1 = {"\u0000F\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010\u000b\n\u0002\b\u0006\n\u0002\u0010\u0000\n\u0000\n\u0002\u0010\b\n\u0000\n\u0002\u0010\u000e\n\u0000\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010 \n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\b\u0082\b\u0018\u00002\u00020\u0001B\u0015\u0012\u0006\u0010\u0002\u001a\u00020\u0003\u0012\u0006\u0010\u0004\u001a\u00020\u0005¢\u0006\u0002\u0010\u0006J\t\u0010\u0007\u001a\u00020\u0003HÂ\u0003J\t\u0010\b\u001a\u00020\u0005HÂ\u0003J\u001d\u0010\t\u001a\u00020\u00002\b\b\u0002\u0010\u0002\u001a\u00020\u00032\b\b\u0002\u0010\u0004\u001a\u00020\u0005HÆ\u0001J\u0013\u0010\n\u001a\u00020\u00052\b\u0010\u000b\u001a\u0004\u0018\u00010\fHÖ\u0003J\t\u0010\r\u001a\u00020\u000eHÖ\u0001J\t\u0010\u000f\u001a\u00020\u0010HÖ\u0001J,\u0010\u0011\u001a\u00020\u0012*\u00020\u00132\f\u0010\u0014\u001a\b\u0012\u0004\u0012\u00020\u00160\u00152\u0006\u0010\u0017\u001a\u00020\u0018H\u0016ø\u0001\u0000¢\u0006\u0004\b\u0019\u0010\u001aR\u000e\u0010\u0002\u001a\u00020\u0003X\u0082\u0004¢\u0006\u0002\n\u0000R\u000e\u0010\u0004\u001a\u00020\u0005X\u0082\u0004¢\u0006\u0002\n\u0000\u0082\u0002\u0007\n\u0005\b¡\u001e0\u0001¨\u0006\u001b"}, d2 = {"Landroidx/compose/foundation/layout/BoxMeasurePolicy;", "Landroidx/compose/ui/layout/MeasurePolicy;", "alignment", "Landroidx/compose/ui/Alignment;", "propagateMinConstraints", "", "(Landroidx/compose/ui/Alignment;Z)V", "component1", "component2", "copy", "equals", "other", "", "hashCode", "", "toString", "", "measure", "Landroidx/compose/ui/layout/MeasureResult;", "Landroidx/compose/ui/layout/MeasureScope;", "measurables", "", "Landroidx/compose/ui/layout/Measurable;", "constraints", "Landroidx/compose/ui/unit/Constraints;", "measure-3p2s80s", "(Landroidx/compose/ui/layout/MeasureScope;Ljava/util/List;J)Landroidx/compose/ui/layout/MeasureResult;", "foundation-layout_release"}, k = 1, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
final /* data */ class BoxMeasurePolicy implements MeasurePolicy {
    private final Alignment alignment;
    private final boolean propagateMinConstraints;

    /* renamed from: component1, reason: from getter */
    private final Alignment getAlignment() {
        return this.alignment;
    }

    /* renamed from: component2, reason: from getter */
    private final boolean getPropagateMinConstraints() {
        return this.propagateMinConstraints;
    }

    public static /* synthetic */ BoxMeasurePolicy copy$default(BoxMeasurePolicy boxMeasurePolicy, Alignment alignment, boolean z, int i, Object obj) {
        if ((i & 1) != 0) {
            alignment = boxMeasurePolicy.alignment;
        }
        if ((i & 2) != 0) {
            z = boxMeasurePolicy.propagateMinConstraints;
        }
        return boxMeasurePolicy.copy(alignment, z);
    }

    public final BoxMeasurePolicy copy(Alignment alignment, boolean propagateMinConstraints) {
        return new BoxMeasurePolicy(alignment, propagateMinConstraints);
    }

    public boolean equals(Object other) {
        if (this == other) {
            return true;
        }
        if (!(other instanceof BoxMeasurePolicy)) {
            return false;
        }
        BoxMeasurePolicy boxMeasurePolicy = (BoxMeasurePolicy) other;
        return Intrinsics.areEqual(this.alignment, boxMeasurePolicy.alignment) && this.propagateMinConstraints == boxMeasurePolicy.propagateMinConstraints;
    }

    public int hashCode() {
        return (this.alignment.hashCode() * 31) + Boolean.hashCode(this.propagateMinConstraints);
    }

    public String toString() {
        return "BoxMeasurePolicy(alignment=" + this.alignment + ", propagateMinConstraints=" + this.propagateMinConstraints + ')';
    }

    public BoxMeasurePolicy(Alignment alignment, boolean propagateMinConstraints) {
        this.alignment = alignment;
        this.propagateMinConstraints = propagateMinConstraints;
    }

    @Override // androidx.compose.ui.layout.MeasurePolicy
    /* renamed from: measure-3p2s80s */
    public MeasureResult mo38measure3p2s80s(final MeasureScope $this$measure_u2d3p2s80s, final List<? extends Measurable> list, long constraints) {
        long m6040copyZbe2FdA;
        boolean matchesParentSize;
        boolean matchesParentSize2;
        boolean matchesParentSize3;
        int boxWidth;
        int boxHeight;
        Placeable placeable;
        if (list.isEmpty()) {
            return MeasureScope.layout$default($this$measure_u2d3p2s80s, Constraints.m6052getMinWidthimpl(constraints), Constraints.m6051getMinHeightimpl(constraints), null, new Function1<Placeable.PlacementScope, Unit>() { // from class: androidx.compose.foundation.layout.BoxMeasurePolicy$measure$1
                @Override // kotlin.jvm.functions.Function1
                public /* bridge */ /* synthetic */ Unit invoke(Placeable.PlacementScope placementScope) {
                    invoke2(placementScope);
                    return Unit.INSTANCE;
                }

                /* renamed from: invoke, reason: avoid collision after fix types in other method */
                public final void invoke2(Placeable.PlacementScope $this$layout) {
                }
            }, 4, null);
        }
        if (this.propagateMinConstraints) {
            m6040copyZbe2FdA = constraints;
        } else {
            m6040copyZbe2FdA = Constraints.m6040copyZbe2FdA(constraints, (r12 & 1) != 0 ? Constraints.m6052getMinWidthimpl(constraints) : 0, (r12 & 2) != 0 ? Constraints.m6050getMaxWidthimpl(constraints) : 0, (r12 & 4) != 0 ? Constraints.m6051getMinHeightimpl(constraints) : 0, (r12 & 8) != 0 ? Constraints.m6049getMaxHeightimpl(constraints) : 0);
        }
        long contentConstraints = m6040copyZbe2FdA;
        if (list.size() == 1) {
            final Measurable measurable = list.get(0);
            matchesParentSize3 = BoxKt.getMatchesParentSize(measurable);
            if (!matchesParentSize3) {
                Placeable placeable2 = measurable.mo5016measureBRTryo0(contentConstraints);
                boxWidth = Math.max(Constraints.m6052getMinWidthimpl(constraints), placeable2.getWidth());
                boxHeight = Math.max(Constraints.m6051getMinHeightimpl(constraints), placeable2.getHeight());
                placeable = placeable2;
            } else {
                boxWidth = Constraints.m6052getMinWidthimpl(constraints);
                boxHeight = Constraints.m6051getMinHeightimpl(constraints);
                placeable = measurable.mo5016measureBRTryo0(Constraints.INSTANCE.m6058fixedJhjzzOo(Constraints.m6052getMinWidthimpl(constraints), Constraints.m6051getMinHeightimpl(constraints)));
            }
            final Placeable placeable3 = placeable;
            final int i = boxWidth;
            final int i2 = boxHeight;
            return MeasureScope.layout$default($this$measure_u2d3p2s80s, boxWidth, boxHeight, null, new Function1<Placeable.PlacementScope, Unit>() { // from class: androidx.compose.foundation.layout.BoxMeasurePolicy$measure$2
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
                    Alignment alignment;
                    Placeable placeable4 = Placeable.this;
                    Measurable measurable2 = measurable;
                    LayoutDirection layoutDirection = $this$measure_u2d3p2s80s.getLayoutDirection();
                    int i3 = i;
                    int i4 = i2;
                    alignment = this.alignment;
                    BoxKt.placeInBox($this$layout, placeable4, measurable2, layoutDirection, i3, i4, alignment);
                }
            }, 4, null);
        }
        final Placeable[] placeables = new Placeable[list.size()];
        final Ref.IntRef boxWidth2 = new Ref.IntRef();
        boxWidth2.element = Constraints.m6052getMinWidthimpl(constraints);
        final Ref.IntRef boxHeight2 = new Ref.IntRef();
        boxHeight2.element = Constraints.m6051getMinHeightimpl(constraints);
        int size = list.size();
        boolean hasMatchParentSizeChildren = false;
        for (int index$iv = 0; index$iv < size; index$iv++) {
            Object item$iv = list.get(index$iv);
            Measurable measurable2 = (Measurable) item$iv;
            int index = index$iv;
            matchesParentSize2 = BoxKt.getMatchesParentSize(measurable2);
            if (!matchesParentSize2) {
                Placeable placeable4 = measurable2.mo5016measureBRTryo0(contentConstraints);
                placeables[index] = placeable4;
                boxWidth2.element = Math.max(boxWidth2.element, placeable4.getWidth());
                boxHeight2.element = Math.max(boxHeight2.element, placeable4.getHeight());
            } else {
                hasMatchParentSizeChildren = true;
            }
        }
        if (hasMatchParentSizeChildren) {
            long matchParentSizeConstraints = ConstraintsKt.Constraints(boxWidth2.element != Integer.MAX_VALUE ? boxWidth2.element : 0, boxWidth2.element, boxHeight2.element != Integer.MAX_VALUE ? boxHeight2.element : 0, boxHeight2.element);
            int size2 = list.size();
            for (int index$iv2 = 0; index$iv2 < size2; index$iv2++) {
                Object item$iv2 = list.get(index$iv2);
                Measurable measurable3 = (Measurable) item$iv2;
                int index2 = index$iv2;
                matchesParentSize = BoxKt.getMatchesParentSize(measurable3);
                if (matchesParentSize) {
                    placeables[index2] = measurable3.mo5016measureBRTryo0(matchParentSizeConstraints);
                }
            }
        }
        return MeasureScope.layout$default($this$measure_u2d3p2s80s, boxWidth2.element, boxHeight2.element, null, new Function1<Placeable.PlacementScope, Unit>() { // from class: androidx.compose.foundation.layout.BoxMeasurePolicy$measure$5
            /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
            /* JADX WARN: Multi-variable type inference failed */
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
                Alignment alignment;
                Placeable[] placeableArr = placeables;
                List<Measurable> list2 = list;
                MeasureScope measureScope = $this$measure_u2d3p2s80s;
                Ref.IntRef intRef = boxWidth2;
                Ref.IntRef intRef2 = boxHeight2;
                BoxMeasurePolicy boxMeasurePolicy = this;
                int index$iv3 = 0;
                int length = placeableArr.length;
                int i3 = 0;
                while (i3 < length) {
                    Placeable placeable5 = placeableArr[i3];
                    Intrinsics.checkNotNull(placeable5, "null cannot be cast to non-null type androidx.compose.ui.layout.Placeable");
                    Measurable measurable4 = list2.get(index$iv3);
                    LayoutDirection layoutDirection = measureScope.getLayoutDirection();
                    int i4 = intRef.element;
                    int i5 = intRef2.element;
                    alignment = boxMeasurePolicy.alignment;
                    BoxKt.placeInBox($this$layout, placeable5, measurable4, layoutDirection, i4, i5, alignment);
                    i3++;
                    index$iv3++;
                }
            }
        }, 4, null);
    }
}
