package androidx.compose.foundation.layout;

import androidx.compose.ui.Modifier;
import androidx.compose.ui.layout.IntrinsicMeasurable;
import androidx.compose.ui.layout.IntrinsicMeasureScope;
import androidx.compose.ui.layout.Measurable;
import androidx.compose.ui.layout.MeasureResult;
import androidx.compose.ui.layout.MeasureScope;
import androidx.compose.ui.layout.Placeable;
import androidx.compose.ui.node.LayoutModifierNode;
import androidx.compose.ui.unit.Constraints;
import androidx.compose.ui.unit.ConstraintsKt;
import androidx.compose.ui.unit.Density;
import androidx.compose.ui.unit.Dp;
import kotlin.Metadata;
import kotlin.Unit;
import kotlin.jvm.functions.Function1;
import kotlin.jvm.internal.DefaultConstructorMarker;
import kotlin.ranges.RangesKt;

/* compiled from: Size.kt */
@Metadata(d1 = {"\u0000L\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0004\n\u0002\u0010\u000b\n\u0002\b\u0011\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0010\b\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0004\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\b\u0006\b\u0002\u0018\u00002\u00020\u00012\u00020\u0002B5\u0012\b\b\u0002\u0010\u0003\u001a\u00020\u0004\u0012\b\b\u0002\u0010\u0005\u001a\u00020\u0004\u0012\b\b\u0002\u0010\u0006\u001a\u00020\u0004\u0012\b\b\u0002\u0010\u0007\u001a\u00020\u0004\u0012\u0006\u0010\b\u001a\u00020\t¢\u0006\u0002\u0010\nJ\u001c\u0010\u001f\u001a\u00020 *\u00020!2\u0006\u0010\"\u001a\u00020#2\u0006\u0010$\u001a\u00020 H\u0016J\u001c\u0010%\u001a\u00020 *\u00020!2\u0006\u0010\"\u001a\u00020#2\u0006\u0010&\u001a\u00020 H\u0016J&\u0010'\u001a\u00020(*\u00020)2\u0006\u0010\"\u001a\u00020*2\u0006\u0010+\u001a\u00020\u001bH\u0016ø\u0001\u0000¢\u0006\u0004\b,\u0010-J\u001c\u0010.\u001a\u00020 *\u00020!2\u0006\u0010\"\u001a\u00020#2\u0006\u0010$\u001a\u00020 H\u0016J\u001c\u0010/\u001a\u00020 *\u00020!2\u0006\u0010\"\u001a\u00020#2\u0006\u0010&\u001a\u00020 H\u0016R\u001a\u0010\b\u001a\u00020\tX\u0086\u000e¢\u0006\u000e\n\u0000\u001a\u0004\b\u000b\u0010\f\"\u0004\b\r\u0010\u000eR\"\u0010\u0007\u001a\u00020\u0004X\u0086\u000eø\u0001\u0000ø\u0001\u0001¢\u0006\u0010\n\u0002\u0010\u0013\u001a\u0004\b\u000f\u0010\u0010\"\u0004\b\u0011\u0010\u0012R\"\u0010\u0006\u001a\u00020\u0004X\u0086\u000eø\u0001\u0000ø\u0001\u0001¢\u0006\u0010\n\u0002\u0010\u0013\u001a\u0004\b\u0014\u0010\u0010\"\u0004\b\u0015\u0010\u0012R\"\u0010\u0005\u001a\u00020\u0004X\u0086\u000eø\u0001\u0000ø\u0001\u0001¢\u0006\u0010\n\u0002\u0010\u0013\u001a\u0004\b\u0016\u0010\u0010\"\u0004\b\u0017\u0010\u0012R\"\u0010\u0003\u001a\u00020\u0004X\u0086\u000eø\u0001\u0000ø\u0001\u0001¢\u0006\u0010\n\u0002\u0010\u0013\u001a\u0004\b\u0018\u0010\u0010\"\u0004\b\u0019\u0010\u0012R\u001e\u0010\u001a\u001a\u00020\u001b*\u00020\u001c8BX\u0082\u0004ø\u0001\u0000ø\u0001\u0001¢\u0006\u0006\u001a\u0004\b\u001d\u0010\u001e\u0082\u0002\u000b\n\u0005\b¡\u001e0\u0001\n\u0002\b!¨\u00060"}, d2 = {"Landroidx/compose/foundation/layout/SizeNode;", "Landroidx/compose/ui/node/LayoutModifierNode;", "Landroidx/compose/ui/Modifier$Node;", "minWidth", "Landroidx/compose/ui/unit/Dp;", "minHeight", "maxWidth", "maxHeight", "enforceIncoming", "", "(FFFFZLkotlin/jvm/internal/DefaultConstructorMarker;)V", "getEnforceIncoming", "()Z", "setEnforceIncoming", "(Z)V", "getMaxHeight-D9Ej5fM", "()F", "setMaxHeight-0680j_4", "(F)V", "F", "getMaxWidth-D9Ej5fM", "setMaxWidth-0680j_4", "getMinHeight-D9Ej5fM", "setMinHeight-0680j_4", "getMinWidth-D9Ej5fM", "setMinWidth-0680j_4", "targetConstraints", "Landroidx/compose/ui/unit/Constraints;", "Landroidx/compose/ui/unit/Density;", "getTargetConstraints-OenEA2s", "(Landroidx/compose/ui/unit/Density;)J", "maxIntrinsicHeight", "", "Landroidx/compose/ui/layout/IntrinsicMeasureScope;", "measurable", "Landroidx/compose/ui/layout/IntrinsicMeasurable;", "width", "maxIntrinsicWidth", "height", "measure", "Landroidx/compose/ui/layout/MeasureResult;", "Landroidx/compose/ui/layout/MeasureScope;", "Landroidx/compose/ui/layout/Measurable;", "constraints", "measure-3p2s80s", "(Landroidx/compose/ui/layout/MeasureScope;Landroidx/compose/ui/layout/Measurable;J)Landroidx/compose/ui/layout/MeasureResult;", "minIntrinsicHeight", "minIntrinsicWidth", "foundation-layout_release"}, k = 1, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
final class SizeNode extends Modifier.Node implements LayoutModifierNode {
    private boolean enforceIncoming;
    private float maxHeight;
    private float maxWidth;
    private float minHeight;
    private float minWidth;

    public /* synthetic */ SizeNode(float f, float f2, float f3, float f4, boolean z, DefaultConstructorMarker defaultConstructorMarker) {
        this(f, f2, f3, f4, z);
    }

    public /* synthetic */ SizeNode(float f, float f2, float f3, float f4, boolean z, int i, DefaultConstructorMarker defaultConstructorMarker) {
        this((i & 1) != 0 ? Dp.INSTANCE.m6114getUnspecifiedD9Ej5fM() : f, (i & 2) != 0 ? Dp.INSTANCE.m6114getUnspecifiedD9Ej5fM() : f2, (i & 4) != 0 ? Dp.INSTANCE.m6114getUnspecifiedD9Ej5fM() : f3, (i & 8) != 0 ? Dp.INSTANCE.m6114getUnspecifiedD9Ej5fM() : f4, z, null);
    }

    /* renamed from: getMinWidth-D9Ej5fM, reason: not valid java name and from getter */
    public final float getMinWidth() {
        return this.minWidth;
    }

    /* renamed from: setMinWidth-0680j_4, reason: not valid java name */
    public final void m627setMinWidth0680j_4(float f) {
        this.minWidth = f;
    }

    /* renamed from: getMinHeight-D9Ej5fM, reason: not valid java name and from getter */
    public final float getMinHeight() {
        return this.minHeight;
    }

    /* renamed from: setMinHeight-0680j_4, reason: not valid java name */
    public final void m626setMinHeight0680j_4(float f) {
        this.minHeight = f;
    }

    /* renamed from: getMaxWidth-D9Ej5fM, reason: not valid java name and from getter */
    public final float getMaxWidth() {
        return this.maxWidth;
    }

    /* renamed from: setMaxWidth-0680j_4, reason: not valid java name */
    public final void m625setMaxWidth0680j_4(float f) {
        this.maxWidth = f;
    }

    /* renamed from: getMaxHeight-D9Ej5fM, reason: not valid java name and from getter */
    public final float getMaxHeight() {
        return this.maxHeight;
    }

    /* renamed from: setMaxHeight-0680j_4, reason: not valid java name */
    public final void m624setMaxHeight0680j_4(float f) {
        this.maxHeight = f;
    }

    public final boolean getEnforceIncoming() {
        return this.enforceIncoming;
    }

    public final void setEnforceIncoming(boolean z) {
        this.enforceIncoming = z;
    }

    private SizeNode(float minWidth, float minHeight, float maxWidth, float maxHeight, boolean enforceIncoming) {
        this.minWidth = minWidth;
        this.minHeight = minHeight;
        this.maxWidth = maxWidth;
        this.maxHeight = maxHeight;
        this.enforceIncoming = enforceIncoming;
    }

    /* renamed from: getTargetConstraints-OenEA2s, reason: not valid java name */
    private final long m619getTargetConstraintsOenEA2s(Density $this$targetConstraints) {
        int maxWidth;
        int maxHeight;
        int it;
        int it2;
        int i = 0;
        if (!Dp.m6099equalsimpl0(this.maxWidth, Dp.INSTANCE.m6114getUnspecifiedD9Ej5fM())) {
            maxWidth = RangesKt.coerceAtLeast($this$targetConstraints.mo307roundToPx0680j_4(this.maxWidth), 0);
        } else {
            maxWidth = Integer.MAX_VALUE;
        }
        if (!Dp.m6099equalsimpl0(this.maxHeight, Dp.INSTANCE.m6114getUnspecifiedD9Ej5fM())) {
            maxHeight = RangesKt.coerceAtLeast($this$targetConstraints.mo307roundToPx0680j_4(this.maxHeight), 0);
        } else {
            maxHeight = Integer.MAX_VALUE;
        }
        if (!Dp.m6099equalsimpl0(this.minWidth, Dp.INSTANCE.m6114getUnspecifiedD9Ej5fM())) {
            it = RangesKt.coerceAtLeast(RangesKt.coerceAtMost($this$targetConstraints.mo307roundToPx0680j_4(this.minWidth), maxWidth), 0);
            if (it == Integer.MAX_VALUE) {
                it = 0;
            }
        } else {
            it = 0;
        }
        if (!Dp.m6099equalsimpl0(this.minHeight, Dp.INSTANCE.m6114getUnspecifiedD9Ej5fM()) && (it2 = RangesKt.coerceAtLeast(RangesKt.coerceAtMost($this$targetConstraints.mo307roundToPx0680j_4(this.minHeight), maxHeight), 0)) != Integer.MAX_VALUE) {
            i = it2;
        }
        int minHeight = i;
        return ConstraintsKt.Constraints(it, maxWidth, minHeight, maxHeight);
    }

    @Override // androidx.compose.ui.node.LayoutModifierNode
    /* renamed from: measure-3p2s80s */
    public MeasureResult mo90measure3p2s80s(MeasureScope $this$measure_u2d3p2s80s, Measurable measurable, long constraints) {
        int resolvedMinWidth;
        int resolvedMaxWidth;
        int resolvedMinHeight;
        int resolvedMaxHeight;
        long targetConstraints;
        long targetConstraints2 = m619getTargetConstraintsOenEA2s($this$measure_u2d3p2s80s);
        if (this.enforceIncoming) {
            targetConstraints = ConstraintsKt.m6062constrainN9IONVI(constraints, targetConstraints2);
        } else {
            if (!Dp.m6099equalsimpl0(this.minWidth, Dp.INSTANCE.m6114getUnspecifiedD9Ej5fM())) {
                resolvedMinWidth = Constraints.m6052getMinWidthimpl(targetConstraints2);
            } else {
                resolvedMinWidth = RangesKt.coerceAtMost(Constraints.m6052getMinWidthimpl(constraints), Constraints.m6050getMaxWidthimpl(targetConstraints2));
            }
            if (!Dp.m6099equalsimpl0(this.maxWidth, Dp.INSTANCE.m6114getUnspecifiedD9Ej5fM())) {
                resolvedMaxWidth = Constraints.m6050getMaxWidthimpl(targetConstraints2);
            } else {
                resolvedMaxWidth = RangesKt.coerceAtLeast(Constraints.m6050getMaxWidthimpl(constraints), Constraints.m6052getMinWidthimpl(targetConstraints2));
            }
            if (!Dp.m6099equalsimpl0(this.minHeight, Dp.INSTANCE.m6114getUnspecifiedD9Ej5fM())) {
                resolvedMinHeight = Constraints.m6051getMinHeightimpl(targetConstraints2);
            } else {
                resolvedMinHeight = RangesKt.coerceAtMost(Constraints.m6051getMinHeightimpl(constraints), Constraints.m6049getMaxHeightimpl(targetConstraints2));
            }
            if (!Dp.m6099equalsimpl0(this.maxHeight, Dp.INSTANCE.m6114getUnspecifiedD9Ej5fM())) {
                resolvedMaxHeight = Constraints.m6049getMaxHeightimpl(targetConstraints2);
            } else {
                resolvedMaxHeight = RangesKt.coerceAtLeast(Constraints.m6049getMaxHeightimpl(constraints), Constraints.m6051getMinHeightimpl(targetConstraints2));
            }
            targetConstraints = ConstraintsKt.Constraints(resolvedMinWidth, resolvedMaxWidth, resolvedMinHeight, resolvedMaxHeight);
        }
        final Placeable placeable = measurable.mo5016measureBRTryo0(targetConstraints);
        return MeasureScope.layout$default($this$measure_u2d3p2s80s, placeable.getWidth(), placeable.getHeight(), null, new Function1<Placeable.PlacementScope, Unit>() { // from class: androidx.compose.foundation.layout.SizeNode$measure$1
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
                Placeable.PlacementScope.placeRelative$default($this$layout, Placeable.this, 0, 0, 0.0f, 4, null);
            }
        }, 4, null);
    }

    @Override // androidx.compose.ui.node.LayoutModifierNode
    public int minIntrinsicWidth(IntrinsicMeasureScope $this$minIntrinsicWidth, IntrinsicMeasurable measurable, int height) {
        long constraints = m619getTargetConstraintsOenEA2s($this$minIntrinsicWidth);
        if (Constraints.m6048getHasFixedWidthimpl(constraints)) {
            return Constraints.m6050getMaxWidthimpl(constraints);
        }
        return ConstraintsKt.m6064constrainWidthK40F9xA(constraints, measurable.minIntrinsicWidth(height));
    }

    @Override // androidx.compose.ui.node.LayoutModifierNode
    public int minIntrinsicHeight(IntrinsicMeasureScope $this$minIntrinsicHeight, IntrinsicMeasurable measurable, int width) {
        long constraints = m619getTargetConstraintsOenEA2s($this$minIntrinsicHeight);
        if (Constraints.m6047getHasFixedHeightimpl(constraints)) {
            return Constraints.m6049getMaxHeightimpl(constraints);
        }
        return ConstraintsKt.m6063constrainHeightK40F9xA(constraints, measurable.minIntrinsicHeight(width));
    }

    @Override // androidx.compose.ui.node.LayoutModifierNode
    public int maxIntrinsicWidth(IntrinsicMeasureScope $this$maxIntrinsicWidth, IntrinsicMeasurable measurable, int height) {
        long constraints = m619getTargetConstraintsOenEA2s($this$maxIntrinsicWidth);
        if (Constraints.m6048getHasFixedWidthimpl(constraints)) {
            return Constraints.m6050getMaxWidthimpl(constraints);
        }
        return ConstraintsKt.m6064constrainWidthK40F9xA(constraints, measurable.maxIntrinsicWidth(height));
    }

    @Override // androidx.compose.ui.node.LayoutModifierNode
    public int maxIntrinsicHeight(IntrinsicMeasureScope $this$maxIntrinsicHeight, IntrinsicMeasurable measurable, int width) {
        long constraints = m619getTargetConstraintsOenEA2s($this$maxIntrinsicHeight);
        if (Constraints.m6047getHasFixedHeightimpl(constraints)) {
            return Constraints.m6049getMaxHeightimpl(constraints);
        }
        return ConstraintsKt.m6063constrainHeightK40F9xA(constraints, measurable.maxIntrinsicHeight(width));
    }
}
