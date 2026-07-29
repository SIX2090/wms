package androidx.compose.material3;

import androidx.compose.foundation.layout.PaddingValues;
import androidx.compose.ui.geometry.Size;
import androidx.compose.ui.geometry.SizeKt;
import androidx.compose.ui.layout.IntrinsicMeasurable;
import androidx.compose.ui.layout.IntrinsicMeasureScope;
import androidx.compose.ui.layout.LayoutIdKt;
import androidx.compose.ui.layout.Measurable;
import androidx.compose.ui.layout.MeasurePolicy;
import androidx.compose.ui.layout.MeasureResult;
import androidx.compose.ui.layout.MeasureScope;
import androidx.compose.ui.layout.Placeable;
import androidx.compose.ui.unit.Constraints;
import androidx.compose.ui.unit.ConstraintsKt;
import androidx.compose.ui.unit.LayoutDirection;
import androidx.compose.ui.util.MathHelpersKt;
import java.util.List;
import java.util.NoSuchElementException;
import kotlin.Metadata;
import kotlin.Unit;
import kotlin.jvm.functions.Function1;
import kotlin.jvm.functions.Function2;
import kotlin.jvm.internal.Intrinsics;

/* compiled from: OutlinedTextField.kt */
@Metadata(d1 = {"\u0000`\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\u0010\u0002\n\u0000\n\u0002\u0010\u000b\n\u0000\n\u0002\u0010\u0007\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0010\b\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010 \n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\b\u0005\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0005\b\u0002\u0018\u00002\u00020\u0001B1\u0012\u0012\u0010\u0002\u001a\u000e\u0012\u0004\u0012\u00020\u0004\u0012\u0004\u0012\u00020\u00050\u0003\u0012\u0006\u0010\u0006\u001a\u00020\u0007\u0012\u0006\u0010\b\u001a\u00020\t\u0012\u0006\u0010\n\u001a\u00020\u000b¢\u0006\u0002\u0010\fJ<\u0010\r\u001a\u00020\u000e*\u00020\u000f2\f\u0010\u0010\u001a\b\u0012\u0004\u0012\u00020\u00120\u00112\u0006\u0010\u0013\u001a\u00020\u000e2\u0018\u0010\u0014\u001a\u0014\u0012\u0004\u0012\u00020\u0012\u0012\u0004\u0012\u00020\u000e\u0012\u0004\u0012\u00020\u000e0\u0015H\u0002J<\u0010\u0016\u001a\u00020\u000e*\u00020\u000f2\f\u0010\u0010\u001a\b\u0012\u0004\u0012\u00020\u00120\u00112\u0006\u0010\u0017\u001a\u00020\u000e2\u0018\u0010\u0014\u001a\u0014\u0012\u0004\u0012\u00020\u0012\u0012\u0004\u0012\u00020\u000e\u0012\u0004\u0012\u00020\u000e0\u0015H\u0002J\"\u0010\u0018\u001a\u00020\u000e*\u00020\u000f2\f\u0010\u0010\u001a\b\u0012\u0004\u0012\u00020\u00120\u00112\u0006\u0010\u0013\u001a\u00020\u000eH\u0016J\"\u0010\u0019\u001a\u00020\u000e*\u00020\u000f2\f\u0010\u0010\u001a\b\u0012\u0004\u0012\u00020\u00120\u00112\u0006\u0010\u0017\u001a\u00020\u000eH\u0016J,\u0010\u001a\u001a\u00020\u001b*\u00020\u001c2\f\u0010\u0010\u001a\b\u0012\u0004\u0012\u00020\u001d0\u00112\u0006\u0010\u001e\u001a\u00020\u001fH\u0016ø\u0001\u0000¢\u0006\u0004\b \u0010!J\"\u0010\"\u001a\u00020\u000e*\u00020\u000f2\f\u0010\u0010\u001a\b\u0012\u0004\u0012\u00020\u00120\u00112\u0006\u0010\u0013\u001a\u00020\u000eH\u0016J\"\u0010#\u001a\u00020\u000e*\u00020\u000f2\f\u0010\u0010\u001a\b\u0012\u0004\u0012\u00020\u00120\u00112\u0006\u0010\u0017\u001a\u00020\u000eH\u0016R\u000e\u0010\b\u001a\u00020\tX\u0082\u0004¢\u0006\u0002\n\u0000R\u001a\u0010\u0002\u001a\u000e\u0012\u0004\u0012\u00020\u0004\u0012\u0004\u0012\u00020\u00050\u0003X\u0082\u0004¢\u0006\u0002\n\u0000R\u000e\u0010\n\u001a\u00020\u000bX\u0082\u0004¢\u0006\u0002\n\u0000R\u000e\u0010\u0006\u001a\u00020\u0007X\u0082\u0004¢\u0006\u0002\n\u0000\u0082\u0002\u0007\n\u0005\b¡\u001e0\u0001¨\u0006$"}, d2 = {"Landroidx/compose/material3/OutlinedTextFieldMeasurePolicy;", "Landroidx/compose/ui/layout/MeasurePolicy;", "onLabelMeasured", "Lkotlin/Function1;", "Landroidx/compose/ui/geometry/Size;", "", "singleLine", "", "animationProgress", "", "paddingValues", "Landroidx/compose/foundation/layout/PaddingValues;", "(Lkotlin/jvm/functions/Function1;ZFLandroidx/compose/foundation/layout/PaddingValues;)V", "intrinsicHeight", "", "Landroidx/compose/ui/layout/IntrinsicMeasureScope;", "measurables", "", "Landroidx/compose/ui/layout/IntrinsicMeasurable;", "width", "intrinsicMeasurer", "Lkotlin/Function2;", "intrinsicWidth", "height", "maxIntrinsicHeight", "maxIntrinsicWidth", "measure", "Landroidx/compose/ui/layout/MeasureResult;", "Landroidx/compose/ui/layout/MeasureScope;", "Landroidx/compose/ui/layout/Measurable;", "constraints", "Landroidx/compose/ui/unit/Constraints;", "measure-3p2s80s", "(Landroidx/compose/ui/layout/MeasureScope;Ljava/util/List;J)Landroidx/compose/ui/layout/MeasureResult;", "minIntrinsicHeight", "minIntrinsicWidth", "material3_release"}, k = 1, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
final class OutlinedTextFieldMeasurePolicy implements MeasurePolicy {
    private final float animationProgress;
    private final Function1<Size, Unit> onLabelMeasured;
    private final PaddingValues paddingValues;
    private final boolean singleLine;

    /* JADX WARN: Multi-variable type inference failed */
    public OutlinedTextFieldMeasurePolicy(Function1<? super Size, Unit> function1, boolean singleLine, float animationProgress, PaddingValues paddingValues) {
        this.onLabelMeasured = function1;
        this.singleLine = singleLine;
        this.animationProgress = animationProgress;
        this.paddingValues = paddingValues;
    }

    @Override // androidx.compose.ui.layout.MeasurePolicy
    /* renamed from: measure-3p2s80s */
    public MeasureResult mo38measure3p2s80s(final MeasureScope $this$measure_u2d3p2s80s, List<? extends Measurable> list, long constraints) {
        long relaxedConstraints;
        Object it$iv;
        Object it$iv2;
        Object it$iv3;
        Object it$iv4;
        Object it$iv5;
        Object it$iv6;
        long m6040copyZbe2FdA;
        long placeholderConstraints;
        Object it$iv7;
        final int width;
        long supportingConstraints;
        int occupiedSpaceHorizontally;
        int bottomPadding;
        long supportingConstraints2;
        final Placeable supportingPlaceable;
        final int totalHeight;
        int bottomPadding2 = $this$measure_u2d3p2s80s.mo307roundToPx0680j_4(this.paddingValues.getBottom());
        relaxedConstraints = Constraints.m6040copyZbe2FdA(constraints, (r12 & 1) != 0 ? Constraints.m6052getMinWidthimpl(constraints) : 0, (r12 & 2) != 0 ? Constraints.m6050getMaxWidthimpl(constraints) : 0, (r12 & 4) != 0 ? Constraints.m6051getMinHeightimpl(constraints) : 0, (r12 & 8) != 0 ? Constraints.m6049getMaxHeightimpl(constraints) : 0);
        List $this$fastFirstOrNull$iv = list;
        int index$iv$iv = 0;
        int size = $this$fastFirstOrNull$iv.size();
        while (true) {
            if (index$iv$iv >= size) {
                it$iv = null;
                break;
            }
            it$iv = $this$fastFirstOrNull$iv.get(index$iv$iv);
            Measurable it = (Measurable) it$iv;
            List $this$fastFirstOrNull$iv2 = $this$fastFirstOrNull$iv;
            if (Intrinsics.areEqual(LayoutIdKt.getLayoutId(it), "Leading")) {
                break;
            }
            index$iv$iv++;
            $this$fastFirstOrNull$iv = $this$fastFirstOrNull$iv2;
        }
        Measurable measurable = (Measurable) it$iv;
        final Placeable leadingPlaceable = measurable != null ? measurable.mo5016measureBRTryo0(relaxedConstraints) : null;
        int occupiedSpaceHorizontally2 = 0 + TextFieldImplKt.widthOrZero(leadingPlaceable);
        int occupiedSpaceVertically = Math.max(0, TextFieldImplKt.heightOrZero(leadingPlaceable));
        List $this$fastFirstOrNull$iv3 = list;
        int $i$f$fastFirstOrNull = 0;
        int index$iv$iv2 = 0;
        int size2 = $this$fastFirstOrNull$iv3.size();
        while (true) {
            if (index$iv$iv2 >= size2) {
                it$iv2 = null;
                break;
            }
            it$iv2 = $this$fastFirstOrNull$iv3.get(index$iv$iv2);
            Measurable it2 = (Measurable) it$iv2;
            List $this$fastFirstOrNull$iv4 = $this$fastFirstOrNull$iv3;
            int $i$f$fastFirstOrNull2 = $i$f$fastFirstOrNull;
            if (Intrinsics.areEqual(LayoutIdKt.getLayoutId(it2), "Trailing")) {
                break;
            }
            index$iv$iv2++;
            $this$fastFirstOrNull$iv3 = $this$fastFirstOrNull$iv4;
            $i$f$fastFirstOrNull = $i$f$fastFirstOrNull2;
        }
        Measurable measurable2 = (Measurable) it$iv2;
        final Placeable trailingPlaceable = measurable2 != null ? measurable2.mo5016measureBRTryo0(ConstraintsKt.m6067offsetNN6EwU$default(relaxedConstraints, -occupiedSpaceHorizontally2, 0, 2, null)) : null;
        int occupiedSpaceHorizontally3 = occupiedSpaceHorizontally2 + TextFieldImplKt.widthOrZero(trailingPlaceable);
        int occupiedSpaceVertically2 = Math.max(occupiedSpaceVertically, TextFieldImplKt.heightOrZero(trailingPlaceable));
        List $this$fastFirstOrNull$iv5 = list;
        int $i$f$fastFirstOrNull3 = 0;
        int index$iv$iv3 = 0;
        int size3 = $this$fastFirstOrNull$iv5.size();
        while (true) {
            if (index$iv$iv3 >= size3) {
                it$iv3 = null;
                break;
            }
            it$iv3 = $this$fastFirstOrNull$iv5.get(index$iv$iv3);
            Measurable it3 = (Measurable) it$iv3;
            List $this$fastFirstOrNull$iv6 = $this$fastFirstOrNull$iv5;
            int $i$f$fastFirstOrNull4 = $i$f$fastFirstOrNull3;
            if (Intrinsics.areEqual(LayoutIdKt.getLayoutId(it3), TextFieldImplKt.PrefixId)) {
                break;
            }
            index$iv$iv3++;
            $this$fastFirstOrNull$iv5 = $this$fastFirstOrNull$iv6;
            $i$f$fastFirstOrNull3 = $i$f$fastFirstOrNull4;
        }
        Measurable measurable3 = (Measurable) it$iv3;
        final Placeable prefixPlaceable = measurable3 != null ? measurable3.mo5016measureBRTryo0(ConstraintsKt.m6067offsetNN6EwU$default(relaxedConstraints, -occupiedSpaceHorizontally3, 0, 2, null)) : null;
        int occupiedSpaceHorizontally4 = occupiedSpaceHorizontally3 + TextFieldImplKt.widthOrZero(prefixPlaceable);
        int occupiedSpaceVertically3 = Math.max(occupiedSpaceVertically2, TextFieldImplKt.heightOrZero(prefixPlaceable));
        List $this$fastFirstOrNull$iv7 = list;
        int $i$f$fastFirstOrNull5 = 0;
        int index$iv$iv4 = 0;
        int size4 = $this$fastFirstOrNull$iv7.size();
        while (true) {
            if (index$iv$iv4 >= size4) {
                it$iv4 = null;
                break;
            }
            it$iv4 = $this$fastFirstOrNull$iv7.get(index$iv$iv4);
            Measurable it4 = (Measurable) it$iv4;
            List $this$fastFirstOrNull$iv8 = $this$fastFirstOrNull$iv7;
            int $i$f$fastFirstOrNull6 = $i$f$fastFirstOrNull5;
            if (Intrinsics.areEqual(LayoutIdKt.getLayoutId(it4), TextFieldImplKt.SuffixId)) {
                break;
            }
            index$iv$iv4++;
            $this$fastFirstOrNull$iv7 = $this$fastFirstOrNull$iv8;
            $i$f$fastFirstOrNull5 = $i$f$fastFirstOrNull6;
        }
        Measurable measurable4 = (Measurable) it$iv4;
        final Placeable suffixPlaceable = measurable4 != null ? measurable4.mo5016measureBRTryo0(ConstraintsKt.m6067offsetNN6EwU$default(relaxedConstraints, -occupiedSpaceHorizontally4, 0, 2, null)) : null;
        int occupiedSpaceHorizontally5 = occupiedSpaceHorizontally4 + TextFieldImplKt.widthOrZero(suffixPlaceable);
        int occupiedSpaceVertically4 = Math.max(occupiedSpaceVertically3, TextFieldImplKt.heightOrZero(suffixPlaceable));
        int labelHorizontalPaddingOffset = $this$measure_u2d3p2s80s.mo307roundToPx0680j_4(this.paddingValues.mo513calculateLeftPaddingu2uoSUM($this$measure_u2d3p2s80s.getLayoutDirection())) + $this$measure_u2d3p2s80s.mo307roundToPx0680j_4(this.paddingValues.mo514calculateRightPaddingu2uoSUM($this$measure_u2d3p2s80s.getLayoutDirection()));
        long labelConstraints = ConstraintsKt.m6066offsetNN6EwU(relaxedConstraints, MathHelpersKt.lerp((-occupiedSpaceHorizontally5) - labelHorizontalPaddingOffset, -labelHorizontalPaddingOffset, this.animationProgress), -bottomPadding2);
        int $i$f$fastFirstOrNull7 = 0;
        List $this$fastForEach$iv$iv = list;
        int size5 = $this$fastForEach$iv$iv.size();
        int labelHorizontalPaddingOffset2 = 0;
        while (true) {
            if (labelHorizontalPaddingOffset2 >= size5) {
                it$iv5 = null;
                break;
            }
            int i = size5;
            List $this$fastForEach$iv$iv2 = $this$fastForEach$iv$iv;
            it$iv5 = $this$fastForEach$iv$iv2.get(labelHorizontalPaddingOffset2);
            Measurable it5 = (Measurable) it$iv5;
            int $i$f$fastFirstOrNull8 = $i$f$fastFirstOrNull7;
            if (Intrinsics.areEqual(LayoutIdKt.getLayoutId(it5), "Label")) {
                break;
            }
            labelHorizontalPaddingOffset2++;
            size5 = i;
            $this$fastForEach$iv$iv = $this$fastForEach$iv$iv2;
            $i$f$fastFirstOrNull7 = $i$f$fastFirstOrNull8;
        }
        Measurable measurable5 = (Measurable) it$iv5;
        final Placeable labelPlaceable = measurable5 != null ? measurable5.mo5016measureBRTryo0(labelConstraints) : null;
        if (labelPlaceable != null) {
            this.onLabelMeasured.invoke(Size.m3562boximpl(SizeKt.Size(labelPlaceable.getWidth(), labelPlaceable.getHeight())));
        }
        int $i$f$fastFirstOrNull9 = 0;
        int index$iv$iv5 = 0;
        int size6 = list.size();
        while (true) {
            if (index$iv$iv5 >= size6) {
                it$iv6 = null;
                break;
            }
            it$iv6 = list.get(index$iv$iv5);
            Measurable it6 = (Measurable) it$iv6;
            int i2 = size6;
            int $i$f$fastFirstOrNull10 = $i$f$fastFirstOrNull9;
            if (Intrinsics.areEqual(LayoutIdKt.getLayoutId(it6), TextFieldImplKt.SupportingId)) {
                break;
            }
            index$iv$iv5++;
            size6 = i2;
            $i$f$fastFirstOrNull9 = $i$f$fastFirstOrNull10;
        }
        Measurable supportingMeasurable = (Measurable) it$iv6;
        int supportingIntrinsicHeight = supportingMeasurable != null ? supportingMeasurable.minIntrinsicHeight(Constraints.m6052getMinWidthimpl(constraints)) : 0;
        int topPadding = Math.max(TextFieldImplKt.heightOrZero(labelPlaceable) / 2, $this$measure_u2d3p2s80s.mo307roundToPx0680j_4(this.paddingValues.getTop()));
        long relaxedConstraints2 = relaxedConstraints;
        m6040copyZbe2FdA = Constraints.m6040copyZbe2FdA(r29, (r12 & 1) != 0 ? Constraints.m6052getMinWidthimpl(r29) : 0, (r12 & 2) != 0 ? Constraints.m6050getMaxWidthimpl(r29) : 0, (r12 & 4) != 0 ? Constraints.m6051getMinHeightimpl(r29) : 0, (r12 & 8) != 0 ? Constraints.m6049getMaxHeightimpl(ConstraintsKt.m6066offsetNN6EwU(constraints, -occupiedSpaceHorizontally5, ((-bottomPadding2) - topPadding) - supportingIntrinsicHeight)) : 0);
        long textConstraints = m6040copyZbe2FdA;
        int $i$f$fastFirst = 0;
        int size7 = list.size();
        int index$iv$iv6 = 0;
        while (index$iv$iv6 < size7) {
            Object item$iv$iv = list.get(index$iv$iv6);
            Measurable it7 = (Measurable) item$iv$iv;
            int i3 = size7;
            int $i$f$fastFirst2 = $i$f$fastFirst;
            if (Intrinsics.areEqual(LayoutIdKt.getLayoutId(it7), "TextField")) {
                long textConstraints2 = textConstraints;
                final Placeable textFieldPlaceable = ((Measurable) item$iv$iv).mo5016measureBRTryo0(textConstraints2);
                placeholderConstraints = Constraints.m6040copyZbe2FdA(textConstraints2, (r12 & 1) != 0 ? Constraints.m6052getMinWidthimpl(textConstraints2) : 0, (r12 & 2) != 0 ? Constraints.m6050getMaxWidthimpl(textConstraints2) : 0, (r12 & 4) != 0 ? Constraints.m6051getMinHeightimpl(textConstraints2) : 0, (r12 & 8) != 0 ? Constraints.m6049getMaxHeightimpl(textConstraints2) : 0);
                List $this$fastForEach$iv$iv3 = list;
                int size8 = $this$fastForEach$iv$iv3.size();
                int index$iv$iv7 = 0;
                while (true) {
                    if (index$iv$iv7 >= size8) {
                        it$iv7 = null;
                        break;
                    }
                    List $this$fastForEach$iv$iv4 = $this$fastForEach$iv$iv3;
                    it$iv7 = $this$fastForEach$iv$iv4.get(index$iv$iv7);
                    Measurable it8 = (Measurable) it$iv7;
                    int i4 = size8;
                    if (Intrinsics.areEqual(LayoutIdKt.getLayoutId(it8), "Hint")) {
                        break;
                    }
                    index$iv$iv7++;
                    size8 = i4;
                    $this$fastForEach$iv$iv3 = $this$fastForEach$iv$iv4;
                }
                Measurable measurable6 = (Measurable) it$iv7;
                final Placeable placeholderPlaceable = measurable6 != null ? measurable6.mo5016measureBRTryo0(placeholderConstraints) : null;
                int occupiedSpaceVertically5 = Math.max(occupiedSpaceVertically4, Math.max(TextFieldImplKt.heightOrZero(textFieldPlaceable), TextFieldImplKt.heightOrZero(placeholderPlaceable)) + topPadding + bottomPadding2);
                width = OutlinedTextFieldKt.m2075calculateWidthDHJA7U0(TextFieldImplKt.widthOrZero(leadingPlaceable), TextFieldImplKt.widthOrZero(trailingPlaceable), TextFieldImplKt.widthOrZero(prefixPlaceable), TextFieldImplKt.widthOrZero(suffixPlaceable), textFieldPlaceable.getWidth(), TextFieldImplKt.widthOrZero(labelPlaceable), TextFieldImplKt.widthOrZero(placeholderPlaceable), this.animationProgress, constraints, $this$measure_u2d3p2s80s.getDensity(), this.paddingValues);
                supportingConstraints = Constraints.m6040copyZbe2FdA(r29, (r12 & 1) != 0 ? Constraints.m6052getMinWidthimpl(r29) : 0, (r12 & 2) != 0 ? Constraints.m6050getMaxWidthimpl(r29) : width, (r12 & 4) != 0 ? Constraints.m6051getMinHeightimpl(r29) : 0, (r12 & 8) != 0 ? Constraints.m6049getMaxHeightimpl(ConstraintsKt.m6067offsetNN6EwU$default(relaxedConstraints2, 0, -occupiedSpaceVertically5, 1, null)) : 0);
                if (supportingMeasurable != null) {
                    occupiedSpaceHorizontally = occupiedSpaceHorizontally5;
                    bottomPadding = bottomPadding2;
                    supportingConstraints2 = supportingConstraints;
                    supportingPlaceable = supportingMeasurable.mo5016measureBRTryo0(supportingConstraints2);
                } else {
                    occupiedSpaceHorizontally = occupiedSpaceHorizontally5;
                    bottomPadding = bottomPadding2;
                    supportingConstraints2 = supportingConstraints;
                    supportingPlaceable = null;
                }
                int supportingHeight = TextFieldImplKt.heightOrZero(supportingPlaceable);
                totalHeight = OutlinedTextFieldKt.m2074calculateHeightmKXJcVc(TextFieldImplKt.heightOrZero(leadingPlaceable), TextFieldImplKt.heightOrZero(trailingPlaceable), TextFieldImplKt.heightOrZero(prefixPlaceable), TextFieldImplKt.heightOrZero(suffixPlaceable), textFieldPlaceable.getHeight(), TextFieldImplKt.heightOrZero(labelPlaceable), TextFieldImplKt.heightOrZero(placeholderPlaceable), TextFieldImplKt.heightOrZero(supportingPlaceable), this.animationProgress, constraints, $this$measure_u2d3p2s80s.getDensity(), this.paddingValues);
                int height = totalHeight - supportingHeight;
                List $this$fastForEach$iv$iv5 = list;
                int size9 = $this$fastForEach$iv$iv5.size();
                int index$iv$iv8 = 0;
                while (index$iv$iv8 < size9) {
                    int i5 = size9;
                    List $this$fastForEach$iv$iv6 = $this$fastForEach$iv$iv5;
                    Object item$iv$iv2 = $this$fastForEach$iv$iv6.get(index$iv$iv8);
                    Measurable it9 = (Measurable) item$iv$iv2;
                    int occupiedSpaceVertically6 = occupiedSpaceVertically5;
                    if (Intrinsics.areEqual(LayoutIdKt.getLayoutId(it9), TextFieldImplKt.ContainerId)) {
                        final Placeable containerPlaceable = ((Measurable) item$iv$iv2).mo5016measureBRTryo0(ConstraintsKt.Constraints(width != Integer.MAX_VALUE ? width : 0, width, height != Integer.MAX_VALUE ? height : 0, height));
                        return MeasureScope.layout$default($this$measure_u2d3p2s80s, width, totalHeight, null, new Function1<Placeable.PlacementScope, Unit>() { // from class: androidx.compose.material3.OutlinedTextFieldMeasurePolicy$measure$2
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
                                float f;
                                boolean z;
                                PaddingValues paddingValues;
                                int i6 = totalHeight;
                                int i7 = width;
                                Placeable placeable = leadingPlaceable;
                                Placeable placeable2 = trailingPlaceable;
                                Placeable placeable3 = prefixPlaceable;
                                Placeable placeable4 = suffixPlaceable;
                                Placeable placeable5 = textFieldPlaceable;
                                Placeable placeable6 = labelPlaceable;
                                Placeable placeable7 = placeholderPlaceable;
                                Placeable placeable8 = containerPlaceable;
                                Placeable placeable9 = supportingPlaceable;
                                f = this.animationProgress;
                                z = this.singleLine;
                                float density = $this$measure_u2d3p2s80s.getDensity();
                                LayoutDirection layoutDirection = $this$measure_u2d3p2s80s.getLayoutDirection();
                                paddingValues = this.paddingValues;
                                OutlinedTextFieldKt.place($this$layout, i6, i7, placeable, placeable2, placeable3, placeable4, placeable5, placeable6, placeable7, placeable8, placeable9, f, z, density, layoutDirection, paddingValues);
                            }
                        }, 4, null);
                    }
                    index$iv$iv8++;
                    size9 = i5;
                    $this$fastForEach$iv$iv5 = $this$fastForEach$iv$iv6;
                    occupiedSpaceVertically5 = occupiedSpaceVertically6;
                }
                throw new NoSuchElementException("Collection contains no element matching the predicate.");
            }
            index$iv$iv6++;
            size7 = i3;
            $i$f$fastFirst = $i$f$fastFirst2;
            relaxedConstraints2 = relaxedConstraints2;
            textConstraints = textConstraints;
        }
        throw new NoSuchElementException("Collection contains no element matching the predicate.");
    }

    @Override // androidx.compose.ui.layout.MeasurePolicy
    public int maxIntrinsicHeight(IntrinsicMeasureScope $this$maxIntrinsicHeight, List<? extends IntrinsicMeasurable> list, int width) {
        return intrinsicHeight($this$maxIntrinsicHeight, list, width, new Function2<IntrinsicMeasurable, Integer, Integer>() { // from class: androidx.compose.material3.OutlinedTextFieldMeasurePolicy$maxIntrinsicHeight$1
            @Override // kotlin.jvm.functions.Function2
            public /* bridge */ /* synthetic */ Integer invoke(IntrinsicMeasurable intrinsicMeasurable, Integer num) {
                return invoke(intrinsicMeasurable, num.intValue());
            }

            public final Integer invoke(IntrinsicMeasurable intrinsicMeasurable, int w) {
                return Integer.valueOf(intrinsicMeasurable.maxIntrinsicHeight(w));
            }
        });
    }

    @Override // androidx.compose.ui.layout.MeasurePolicy
    public int minIntrinsicHeight(IntrinsicMeasureScope $this$minIntrinsicHeight, List<? extends IntrinsicMeasurable> list, int width) {
        return intrinsicHeight($this$minIntrinsicHeight, list, width, new Function2<IntrinsicMeasurable, Integer, Integer>() { // from class: androidx.compose.material3.OutlinedTextFieldMeasurePolicy$minIntrinsicHeight$1
            @Override // kotlin.jvm.functions.Function2
            public /* bridge */ /* synthetic */ Integer invoke(IntrinsicMeasurable intrinsicMeasurable, Integer num) {
                return invoke(intrinsicMeasurable, num.intValue());
            }

            public final Integer invoke(IntrinsicMeasurable intrinsicMeasurable, int w) {
                return Integer.valueOf(intrinsicMeasurable.minIntrinsicHeight(w));
            }
        });
    }

    @Override // androidx.compose.ui.layout.MeasurePolicy
    public int maxIntrinsicWidth(IntrinsicMeasureScope $this$maxIntrinsicWidth, List<? extends IntrinsicMeasurable> list, int height) {
        return intrinsicWidth($this$maxIntrinsicWidth, list, height, new Function2<IntrinsicMeasurable, Integer, Integer>() { // from class: androidx.compose.material3.OutlinedTextFieldMeasurePolicy$maxIntrinsicWidth$1
            @Override // kotlin.jvm.functions.Function2
            public /* bridge */ /* synthetic */ Integer invoke(IntrinsicMeasurable intrinsicMeasurable, Integer num) {
                return invoke(intrinsicMeasurable, num.intValue());
            }

            public final Integer invoke(IntrinsicMeasurable intrinsicMeasurable, int h) {
                return Integer.valueOf(intrinsicMeasurable.maxIntrinsicWidth(h));
            }
        });
    }

    @Override // androidx.compose.ui.layout.MeasurePolicy
    public int minIntrinsicWidth(IntrinsicMeasureScope $this$minIntrinsicWidth, List<? extends IntrinsicMeasurable> list, int height) {
        return intrinsicWidth($this$minIntrinsicWidth, list, height, new Function2<IntrinsicMeasurable, Integer, Integer>() { // from class: androidx.compose.material3.OutlinedTextFieldMeasurePolicy$minIntrinsicWidth$1
            @Override // kotlin.jvm.functions.Function2
            public /* bridge */ /* synthetic */ Integer invoke(IntrinsicMeasurable intrinsicMeasurable, Integer num) {
                return invoke(intrinsicMeasurable, num.intValue());
            }

            public final Integer invoke(IntrinsicMeasurable intrinsicMeasurable, int h) {
                return Integer.valueOf(intrinsicMeasurable.minIntrinsicWidth(h));
            }
        });
    }

    private final int intrinsicWidth(IntrinsicMeasureScope $this$intrinsicWidth, List<? extends IntrinsicMeasurable> list, int height, Function2<? super IntrinsicMeasurable, ? super Integer, Integer> function2) {
        Object it$iv;
        Object it$iv2;
        Object it$iv3;
        Object it$iv4;
        Object it$iv5;
        Object obj;
        int m2075calculateWidthDHJA7U0;
        int size = list.size();
        for (int index$iv$iv = 0; index$iv$iv < size; index$iv$iv++) {
            Object item$iv$iv = list.get(index$iv$iv);
            if (Intrinsics.areEqual(TextFieldImplKt.getLayoutId((IntrinsicMeasurable) item$iv$iv), "TextField")) {
                int textFieldWidth = function2.invoke(item$iv$iv, Integer.valueOf(height)).intValue();
                int index$iv$iv2 = 0;
                int size2 = list.size();
                while (true) {
                    if (index$iv$iv2 >= size2) {
                        it$iv = null;
                        break;
                    }
                    it$iv = list.get(index$iv$iv2);
                    if (Intrinsics.areEqual(TextFieldImplKt.getLayoutId((IntrinsicMeasurable) it$iv), "Label")) {
                        break;
                    }
                    index$iv$iv2++;
                }
                IntrinsicMeasurable it = (IntrinsicMeasurable) it$iv;
                int labelWidth = it != null ? function2.invoke(it, Integer.valueOf(height)).intValue() : 0;
                List $this$fastFirstOrNull$iv = list;
                int index$iv$iv3 = 0;
                int size3 = $this$fastFirstOrNull$iv.size();
                while (true) {
                    if (index$iv$iv3 >= size3) {
                        it$iv2 = null;
                        break;
                    }
                    it$iv2 = $this$fastFirstOrNull$iv.get(index$iv$iv3);
                    List $this$fastFirstOrNull$iv2 = $this$fastFirstOrNull$iv;
                    if (Intrinsics.areEqual(TextFieldImplKt.getLayoutId((IntrinsicMeasurable) it$iv2), "Trailing")) {
                        break;
                    }
                    index$iv$iv3++;
                    $this$fastFirstOrNull$iv = $this$fastFirstOrNull$iv2;
                }
                IntrinsicMeasurable it2 = (IntrinsicMeasurable) it$iv2;
                int trailingWidth = it2 != null ? function2.invoke(it2, Integer.valueOf(height)).intValue() : 0;
                List $this$fastFirstOrNull$iv3 = list;
                int $i$f$fastFirstOrNull = 0;
                int index$iv$iv4 = 0;
                int size4 = $this$fastFirstOrNull$iv3.size();
                while (true) {
                    if (index$iv$iv4 >= size4) {
                        it$iv3 = null;
                        break;
                    }
                    it$iv3 = $this$fastFirstOrNull$iv3.get(index$iv$iv4);
                    List $this$fastFirstOrNull$iv4 = $this$fastFirstOrNull$iv3;
                    int $i$f$fastFirstOrNull2 = $i$f$fastFirstOrNull;
                    if (Intrinsics.areEqual(TextFieldImplKt.getLayoutId((IntrinsicMeasurable) it$iv3), "Leading")) {
                        break;
                    }
                    index$iv$iv4++;
                    $this$fastFirstOrNull$iv3 = $this$fastFirstOrNull$iv4;
                    $i$f$fastFirstOrNull = $i$f$fastFirstOrNull2;
                }
                IntrinsicMeasurable it3 = (IntrinsicMeasurable) it$iv3;
                int leadingWidth = it3 != null ? function2.invoke(it3, Integer.valueOf(height)).intValue() : 0;
                List $this$fastFirstOrNull$iv5 = list;
                int $i$f$fastFirstOrNull3 = 0;
                int index$iv$iv5 = 0;
                int size5 = $this$fastFirstOrNull$iv5.size();
                while (true) {
                    if (index$iv$iv5 >= size5) {
                        it$iv4 = null;
                        break;
                    }
                    it$iv4 = $this$fastFirstOrNull$iv5.get(index$iv$iv5);
                    List $this$fastFirstOrNull$iv6 = $this$fastFirstOrNull$iv5;
                    int $i$f$fastFirstOrNull4 = $i$f$fastFirstOrNull3;
                    if (Intrinsics.areEqual(TextFieldImplKt.getLayoutId((IntrinsicMeasurable) it$iv4), TextFieldImplKt.PrefixId)) {
                        break;
                    }
                    index$iv$iv5++;
                    $this$fastFirstOrNull$iv5 = $this$fastFirstOrNull$iv6;
                    $i$f$fastFirstOrNull3 = $i$f$fastFirstOrNull4;
                }
                IntrinsicMeasurable it4 = (IntrinsicMeasurable) it$iv4;
                int prefixWidth = it4 != null ? function2.invoke(it4, Integer.valueOf(height)).intValue() : 0;
                List $this$fastFirstOrNull$iv7 = list;
                int $i$f$fastFirstOrNull5 = 0;
                int index$iv$iv6 = 0;
                int size6 = $this$fastFirstOrNull$iv7.size();
                while (true) {
                    if (index$iv$iv6 >= size6) {
                        it$iv5 = null;
                        break;
                    }
                    it$iv5 = $this$fastFirstOrNull$iv7.get(index$iv$iv6);
                    List $this$fastFirstOrNull$iv8 = $this$fastFirstOrNull$iv7;
                    int $i$f$fastFirstOrNull6 = $i$f$fastFirstOrNull5;
                    if (Intrinsics.areEqual(TextFieldImplKt.getLayoutId((IntrinsicMeasurable) it$iv5), TextFieldImplKt.SuffixId)) {
                        break;
                    }
                    index$iv$iv6++;
                    $this$fastFirstOrNull$iv7 = $this$fastFirstOrNull$iv8;
                    $i$f$fastFirstOrNull5 = $i$f$fastFirstOrNull6;
                }
                IntrinsicMeasurable it5 = (IntrinsicMeasurable) it$iv5;
                int suffixWidth = it5 != null ? function2.invoke(it5, Integer.valueOf(height)).intValue() : 0;
                List $this$fastFirstOrNull$iv9 = list;
                int $i$f$fastFirstOrNull7 = 0;
                int index$iv$iv7 = 0;
                int size7 = $this$fastFirstOrNull$iv9.size();
                while (true) {
                    if (index$iv$iv7 >= size7) {
                        obj = null;
                        break;
                    }
                    Object item$iv$iv2 = $this$fastFirstOrNull$iv9.get(index$iv$iv7);
                    List $this$fastFirstOrNull$iv10 = $this$fastFirstOrNull$iv9;
                    int $i$f$fastFirstOrNull8 = $i$f$fastFirstOrNull7;
                    if (Intrinsics.areEqual(TextFieldImplKt.getLayoutId((IntrinsicMeasurable) item$iv$iv2), "Hint")) {
                        obj = item$iv$iv2;
                        break;
                    }
                    index$iv$iv7++;
                    $this$fastFirstOrNull$iv9 = $this$fastFirstOrNull$iv10;
                    $i$f$fastFirstOrNull7 = $i$f$fastFirstOrNull8;
                }
                IntrinsicMeasurable it6 = (IntrinsicMeasurable) obj;
                int placeholderWidth = it6 != null ? function2.invoke(it6, Integer.valueOf(height)).intValue() : 0;
                m2075calculateWidthDHJA7U0 = OutlinedTextFieldKt.m2075calculateWidthDHJA7U0(leadingWidth, trailingWidth, prefixWidth, suffixWidth, textFieldWidth, labelWidth, placeholderWidth, this.animationProgress, TextFieldImplKt.getZeroConstraints(), $this$intrinsicWidth.getDensity(), this.paddingValues);
                return m2075calculateWidthDHJA7U0;
            }
        }
        throw new NoSuchElementException("Collection contains no element matching the predicate.");
    }

    private final int intrinsicHeight(IntrinsicMeasureScope $this$intrinsicHeight, List<? extends IntrinsicMeasurable> list, int width, Function2<? super IntrinsicMeasurable, ? super Integer, Integer> function2) {
        Object it$iv;
        int leadingHeight;
        Object it$iv2;
        int trailingHeight;
        Object it$iv3;
        Object it$iv4;
        int prefixHeight;
        Object it$iv5;
        int suffixHeight;
        Object it$iv6;
        Object obj;
        int m2074calculateHeightmKXJcVc;
        int remainingWidth = width;
        int index$iv$iv = 0;
        int size = list.size();
        while (true) {
            if (index$iv$iv >= size) {
                it$iv = null;
                break;
            }
            it$iv = list.get(index$iv$iv);
            if (Intrinsics.areEqual(TextFieldImplKt.getLayoutId((IntrinsicMeasurable) it$iv), "Leading")) {
                break;
            }
            index$iv$iv++;
        }
        IntrinsicMeasurable it = (IntrinsicMeasurable) it$iv;
        if (it != null) {
            remainingWidth = OutlinedTextFieldKt.substractConstraintSafely(remainingWidth, it.maxIntrinsicWidth(Integer.MAX_VALUE));
            leadingHeight = function2.invoke(it, Integer.valueOf(width)).intValue();
        } else {
            leadingHeight = 0;
        }
        int index$iv$iv2 = 0;
        int size2 = list.size();
        while (true) {
            if (index$iv$iv2 >= size2) {
                it$iv2 = null;
                break;
            }
            it$iv2 = list.get(index$iv$iv2);
            if (Intrinsics.areEqual(TextFieldImplKt.getLayoutId((IntrinsicMeasurable) it$iv2), "Trailing")) {
                break;
            }
            index$iv$iv2++;
        }
        IntrinsicMeasurable it2 = (IntrinsicMeasurable) it$iv2;
        if (it2 != null) {
            remainingWidth = OutlinedTextFieldKt.substractConstraintSafely(remainingWidth, it2.maxIntrinsicWidth(Integer.MAX_VALUE));
            trailingHeight = function2.invoke(it2, Integer.valueOf(width)).intValue();
        } else {
            trailingHeight = 0;
        }
        int index$iv$iv3 = 0;
        int size3 = list.size();
        while (true) {
            if (index$iv$iv3 >= size3) {
                it$iv3 = null;
                break;
            }
            it$iv3 = list.get(index$iv$iv3);
            if (Intrinsics.areEqual(TextFieldImplKt.getLayoutId((IntrinsicMeasurable) it$iv3), "Label")) {
                break;
            }
            index$iv$iv3++;
        }
        IntrinsicMeasurable it3 = (IntrinsicMeasurable) it$iv3;
        int labelHeight = it3 != null ? function2.invoke(it3, Integer.valueOf(MathHelpersKt.lerp(remainingWidth, width, this.animationProgress))).intValue() : 0;
        List $this$fastFirstOrNull$iv = list;
        int index$iv$iv4 = 0;
        int size4 = $this$fastFirstOrNull$iv.size();
        while (true) {
            if (index$iv$iv4 >= size4) {
                it$iv4 = null;
                break;
            }
            it$iv4 = $this$fastFirstOrNull$iv.get(index$iv$iv4);
            List $this$fastFirstOrNull$iv2 = $this$fastFirstOrNull$iv;
            if (Intrinsics.areEqual(TextFieldImplKt.getLayoutId((IntrinsicMeasurable) it$iv4), TextFieldImplKt.PrefixId)) {
                break;
            }
            index$iv$iv4++;
            $this$fastFirstOrNull$iv = $this$fastFirstOrNull$iv2;
        }
        IntrinsicMeasurable it4 = (IntrinsicMeasurable) it$iv4;
        if (it4 != null) {
            int height = function2.invoke(it4, Integer.valueOf(remainingWidth)).intValue();
            remainingWidth = OutlinedTextFieldKt.substractConstraintSafely(remainingWidth, it4.maxIntrinsicWidth(Integer.MAX_VALUE));
            prefixHeight = height;
        } else {
            prefixHeight = 0;
        }
        List $this$fastFirstOrNull$iv3 = list;
        int index$iv$iv5 = 0;
        int size5 = $this$fastFirstOrNull$iv3.size();
        while (true) {
            if (index$iv$iv5 >= size5) {
                it$iv5 = null;
                break;
            }
            it$iv5 = $this$fastFirstOrNull$iv3.get(index$iv$iv5);
            List $this$fastFirstOrNull$iv4 = $this$fastFirstOrNull$iv3;
            if (Intrinsics.areEqual(TextFieldImplKt.getLayoutId((IntrinsicMeasurable) it$iv5), TextFieldImplKt.SuffixId)) {
                break;
            }
            index$iv$iv5++;
            $this$fastFirstOrNull$iv3 = $this$fastFirstOrNull$iv4;
        }
        IntrinsicMeasurable it5 = (IntrinsicMeasurable) it$iv5;
        if (it5 != null) {
            int height2 = function2.invoke(it5, Integer.valueOf(remainingWidth)).intValue();
            remainingWidth = OutlinedTextFieldKt.substractConstraintSafely(remainingWidth, it5.maxIntrinsicWidth(Integer.MAX_VALUE));
            suffixHeight = height2;
        } else {
            suffixHeight = 0;
        }
        List $this$fastFirst$iv = list;
        int index$iv$iv6 = 0;
        int size6 = $this$fastFirst$iv.size();
        while (index$iv$iv6 < size6) {
            Object item$iv$iv = $this$fastFirst$iv.get(index$iv$iv6);
            List $this$fastFirst$iv2 = $this$fastFirst$iv;
            if (Intrinsics.areEqual(TextFieldImplKt.getLayoutId((IntrinsicMeasurable) item$iv$iv), "TextField")) {
                int textFieldHeight = function2.invoke(item$iv$iv, Integer.valueOf(remainingWidth)).intValue();
                List $this$fastFirstOrNull$iv5 = list;
                int index$iv$iv7 = 0;
                int size7 = $this$fastFirstOrNull$iv5.size();
                while (true) {
                    if (index$iv$iv7 >= size7) {
                        it$iv6 = null;
                        break;
                    }
                    it$iv6 = $this$fastFirstOrNull$iv5.get(index$iv$iv7);
                    List $this$fastFirstOrNull$iv6 = $this$fastFirstOrNull$iv5;
                    if (Intrinsics.areEqual(TextFieldImplKt.getLayoutId((IntrinsicMeasurable) it$iv6), "Hint")) {
                        break;
                    }
                    index$iv$iv7++;
                    $this$fastFirstOrNull$iv5 = $this$fastFirstOrNull$iv6;
                }
                IntrinsicMeasurable it6 = (IntrinsicMeasurable) it$iv6;
                int placeholderHeight = it6 != null ? function2.invoke(it6, Integer.valueOf(remainingWidth)).intValue() : 0;
                int index$iv$iv8 = 0;
                int size8 = list.size();
                while (true) {
                    if (index$iv$iv8 >= size8) {
                        obj = null;
                        break;
                    }
                    Object item$iv$iv2 = list.get(index$iv$iv8);
                    int remainingWidth2 = remainingWidth;
                    if (Intrinsics.areEqual(TextFieldImplKt.getLayoutId((IntrinsicMeasurable) item$iv$iv2), TextFieldImplKt.SupportingId)) {
                        obj = item$iv$iv2;
                        break;
                    }
                    index$iv$iv8++;
                    remainingWidth = remainingWidth2;
                }
                IntrinsicMeasurable it7 = (IntrinsicMeasurable) obj;
                int supportingHeight = it7 != null ? function2.invoke(it7, Integer.valueOf(width)).intValue() : 0;
                m2074calculateHeightmKXJcVc = OutlinedTextFieldKt.m2074calculateHeightmKXJcVc(leadingHeight, trailingHeight, prefixHeight, suffixHeight, textFieldHeight, labelHeight, placeholderHeight, supportingHeight, this.animationProgress, TextFieldImplKt.getZeroConstraints(), $this$intrinsicHeight.getDensity(), this.paddingValues);
                return m2074calculateHeightmKXJcVc;
            }
            index$iv$iv6++;
            $this$fastFirst$iv = $this$fastFirst$iv2;
        }
        throw new NoSuchElementException("Collection contains no element matching the predicate.");
    }
}
