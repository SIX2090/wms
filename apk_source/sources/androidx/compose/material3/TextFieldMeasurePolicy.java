package androidx.compose.material3;

import androidx.compose.foundation.layout.PaddingValues;
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
import java.util.List;
import java.util.NoSuchElementException;
import kotlin.Metadata;
import kotlin.Unit;
import kotlin.jvm.functions.Function1;
import kotlin.jvm.functions.Function2;
import kotlin.jvm.internal.Intrinsics;

/* compiled from: TextField.kt */
@Metadata(d1 = {"\u0000T\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010\u000b\n\u0000\n\u0002\u0010\u0007\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0010\b\n\u0000\n\u0002\u0010 \n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0004\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0005\b\u0002\u0018\u00002\u00020\u0001B\u001d\u0012\u0006\u0010\u0002\u001a\u00020\u0003\u0012\u0006\u0010\u0004\u001a\u00020\u0005\u0012\u0006\u0010\u0006\u001a\u00020\u0007¢\u0006\u0002\u0010\bJ8\u0010\t\u001a\u00020\n2\f\u0010\u000b\u001a\b\u0012\u0004\u0012\u00020\r0\f2\u0006\u0010\u000e\u001a\u00020\n2\u0018\u0010\u000f\u001a\u0014\u0012\u0004\u0012\u00020\r\u0012\u0004\u0012\u00020\n\u0012\u0004\u0012\u00020\n0\u0010H\u0002J<\u0010\u0011\u001a\u00020\n*\u00020\u00122\f\u0010\u000b\u001a\b\u0012\u0004\u0012\u00020\r0\f2\u0006\u0010\u0013\u001a\u00020\n2\u0018\u0010\u000f\u001a\u0014\u0012\u0004\u0012\u00020\r\u0012\u0004\u0012\u00020\n\u0012\u0004\u0012\u00020\n0\u0010H\u0002J\"\u0010\u0014\u001a\u00020\n*\u00020\u00122\f\u0010\u000b\u001a\b\u0012\u0004\u0012\u00020\r0\f2\u0006\u0010\u0013\u001a\u00020\nH\u0016J\"\u0010\u0015\u001a\u00020\n*\u00020\u00122\f\u0010\u000b\u001a\b\u0012\u0004\u0012\u00020\r0\f2\u0006\u0010\u000e\u001a\u00020\nH\u0016J,\u0010\u0016\u001a\u00020\u0017*\u00020\u00182\f\u0010\u000b\u001a\b\u0012\u0004\u0012\u00020\u00190\f2\u0006\u0010\u001a\u001a\u00020\u001bH\u0016ø\u0001\u0000¢\u0006\u0004\b\u001c\u0010\u001dJ\"\u0010\u001e\u001a\u00020\n*\u00020\u00122\f\u0010\u000b\u001a\b\u0012\u0004\u0012\u00020\r0\f2\u0006\u0010\u0013\u001a\u00020\nH\u0016J\"\u0010\u001f\u001a\u00020\n*\u00020\u00122\f\u0010\u000b\u001a\b\u0012\u0004\u0012\u00020\r0\f2\u0006\u0010\u000e\u001a\u00020\nH\u0016R\u000e\u0010\u0004\u001a\u00020\u0005X\u0082\u0004¢\u0006\u0002\n\u0000R\u000e\u0010\u0006\u001a\u00020\u0007X\u0082\u0004¢\u0006\u0002\n\u0000R\u000e\u0010\u0002\u001a\u00020\u0003X\u0082\u0004¢\u0006\u0002\n\u0000\u0082\u0002\u0007\n\u0005\b¡\u001e0\u0001¨\u0006 "}, d2 = {"Landroidx/compose/material3/TextFieldMeasurePolicy;", "Landroidx/compose/ui/layout/MeasurePolicy;", "singleLine", "", "animationProgress", "", "paddingValues", "Landroidx/compose/foundation/layout/PaddingValues;", "(ZFLandroidx/compose/foundation/layout/PaddingValues;)V", "intrinsicWidth", "", "measurables", "", "Landroidx/compose/ui/layout/IntrinsicMeasurable;", "height", "intrinsicMeasurer", "Lkotlin/Function2;", "intrinsicHeight", "Landroidx/compose/ui/layout/IntrinsicMeasureScope;", "width", "maxIntrinsicHeight", "maxIntrinsicWidth", "measure", "Landroidx/compose/ui/layout/MeasureResult;", "Landroidx/compose/ui/layout/MeasureScope;", "Landroidx/compose/ui/layout/Measurable;", "constraints", "Landroidx/compose/ui/unit/Constraints;", "measure-3p2s80s", "(Landroidx/compose/ui/layout/MeasureScope;Ljava/util/List;J)Landroidx/compose/ui/layout/MeasureResult;", "minIntrinsicHeight", "minIntrinsicWidth", "material3_release"}, k = 1, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
final class TextFieldMeasurePolicy implements MeasurePolicy {
    private final float animationProgress;
    private final PaddingValues paddingValues;
    private final boolean singleLine;

    public TextFieldMeasurePolicy(boolean singleLine, float animationProgress, PaddingValues paddingValues) {
        this.singleLine = singleLine;
        this.animationProgress = animationProgress;
        this.paddingValues = paddingValues;
    }

    @Override // androidx.compose.ui.layout.MeasurePolicy
    /* renamed from: measure-3p2s80s */
    public MeasureResult mo38measure3p2s80s(final MeasureScope $this$measure_u2d3p2s80s, List<? extends Measurable> list, long constraints) {
        long looseConstraints;
        Object it$iv;
        Object it$iv2;
        Object it$iv3;
        Object it$iv4;
        Object it$iv5;
        Object it$iv6;
        long m6040copyZbe2FdA;
        long placeholderConstraints;
        Measurable supportingMeasurable;
        Object it$iv7;
        final int width;
        long supportingConstraints;
        long placeholderConstraints2;
        long placeholderConstraints3;
        Measurable supportingMeasurable2;
        Placeable placeable;
        final int totalHeight;
        final int topPaddingValue = $this$measure_u2d3p2s80s.mo307roundToPx0680j_4(this.paddingValues.getTop());
        int bottomPaddingValue = $this$measure_u2d3p2s80s.mo307roundToPx0680j_4(this.paddingValues.getBottom());
        looseConstraints = Constraints.m6040copyZbe2FdA(constraints, (r12 & 1) != 0 ? Constraints.m6052getMinWidthimpl(constraints) : 0, (r12 & 2) != 0 ? Constraints.m6050getMaxWidthimpl(constraints) : 0, (r12 & 4) != 0 ? Constraints.m6051getMinHeightimpl(constraints) : 0, (r12 & 8) != 0 ? Constraints.m6049getMaxHeightimpl(constraints) : 0);
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
        final Placeable leadingPlaceable = measurable != null ? measurable.mo5016measureBRTryo0(looseConstraints) : null;
        int occupiedSpaceHorizontally = 0 + TextFieldImplKt.widthOrZero(leadingPlaceable);
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
        final Placeable trailingPlaceable = measurable2 != null ? measurable2.mo5016measureBRTryo0(ConstraintsKt.m6067offsetNN6EwU$default(looseConstraints, -occupiedSpaceHorizontally, 0, 2, null)) : null;
        int occupiedSpaceHorizontally2 = occupiedSpaceHorizontally + TextFieldImplKt.widthOrZero(trailingPlaceable);
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
        final Placeable prefixPlaceable = measurable3 != null ? measurable3.mo5016measureBRTryo0(ConstraintsKt.m6067offsetNN6EwU$default(looseConstraints, -occupiedSpaceHorizontally2, 0, 2, null)) : null;
        int occupiedSpaceHorizontally3 = occupiedSpaceHorizontally2 + TextFieldImplKt.widthOrZero(prefixPlaceable);
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
        final Placeable suffixPlaceable = measurable4 != null ? measurable4.mo5016measureBRTryo0(ConstraintsKt.m6067offsetNN6EwU$default(looseConstraints, -occupiedSpaceHorizontally3, 0, 2, null)) : null;
        int occupiedSpaceHorizontally4 = occupiedSpaceHorizontally3 + TextFieldImplKt.widthOrZero(suffixPlaceable);
        int occupiedSpaceVertically4 = Math.max(occupiedSpaceVertically3, TextFieldImplKt.heightOrZero(suffixPlaceable));
        int occupiedSpaceVertically5 = -bottomPaddingValue;
        long labelConstraints = ConstraintsKt.m6066offsetNN6EwU(looseConstraints, -occupiedSpaceHorizontally4, occupiedSpaceVertically5);
        List $this$fastForEach$iv$iv = list;
        int size5 = $this$fastForEach$iv$iv.size();
        int $i$f$fastFirstOrNull7 = 0;
        while (true) {
            if ($i$f$fastFirstOrNull7 >= size5) {
                it$iv5 = null;
                break;
            }
            it$iv5 = $this$fastForEach$iv$iv.get($i$f$fastFirstOrNull7);
            Measurable it5 = (Measurable) it$iv5;
            int i = size5;
            List $this$fastForEach$iv$iv2 = $this$fastForEach$iv$iv;
            if (Intrinsics.areEqual(LayoutIdKt.getLayoutId(it5), "Label")) {
                break;
            }
            $i$f$fastFirstOrNull7++;
            size5 = i;
            $this$fastForEach$iv$iv = $this$fastForEach$iv$iv2;
        }
        Measurable measurable5 = (Measurable) it$iv5;
        final Placeable labelPlaceable = measurable5 != null ? measurable5.mo5016measureBRTryo0(labelConstraints) : null;
        List $this$fastForEach$iv$iv3 = list;
        int size6 = $this$fastForEach$iv$iv3.size();
        int $i$f$fastFirstOrNull8 = 0;
        while (true) {
            if ($i$f$fastFirstOrNull8 >= size6) {
                it$iv6 = null;
                break;
            }
            int i2 = size6;
            List $this$fastForEach$iv$iv4 = $this$fastForEach$iv$iv3;
            it$iv6 = $this$fastForEach$iv$iv4.get($i$f$fastFirstOrNull8);
            Measurable it6 = (Measurable) it$iv6;
            long labelConstraints2 = labelConstraints;
            if (Intrinsics.areEqual(LayoutIdKt.getLayoutId(it6), TextFieldImplKt.SupportingId)) {
                break;
            }
            $i$f$fastFirstOrNull8++;
            size6 = i2;
            $this$fastForEach$iv$iv3 = $this$fastForEach$iv$iv4;
            labelConstraints = labelConstraints2;
        }
        Measurable supportingMeasurable3 = (Measurable) it$iv6;
        int supportingIntrinsicHeight = supportingMeasurable3 != null ? supportingMeasurable3.minIntrinsicHeight(Constraints.m6052getMinWidthimpl(constraints)) : 0;
        int effectiveTopOffset = topPaddingValue + TextFieldImplKt.heightOrZero(labelPlaceable);
        m6040copyZbe2FdA = Constraints.m6040copyZbe2FdA(constraints, (r12 & 1) != 0 ? Constraints.m6052getMinWidthimpl(constraints) : 0, (r12 & 2) != 0 ? Constraints.m6050getMaxWidthimpl(constraints) : 0, (r12 & 4) != 0 ? Constraints.m6051getMinHeightimpl(constraints) : 0, (r12 & 8) != 0 ? Constraints.m6049getMaxHeightimpl(constraints) : 0);
        long textFieldConstraints = ConstraintsKt.m6066offsetNN6EwU(m6040copyZbe2FdA, -occupiedSpaceHorizontally4, ((-effectiveTopOffset) - bottomPaddingValue) - supportingIntrinsicHeight);
        List $this$fastForEach$iv$iv5 = list;
        int size7 = $this$fastForEach$iv$iv5.size();
        int $i$f$fastFirst = 0;
        while (true) {
            int occupiedSpaceHorizontally5 = occupiedSpaceHorizontally4;
            if ($i$f$fastFirst >= size7) {
                throw new NoSuchElementException("Collection contains no element matching the predicate.");
            }
            int i3 = size7;
            List $this$fastForEach$iv$iv6 = $this$fastForEach$iv$iv5;
            Object item$iv$iv = $this$fastForEach$iv$iv6.get($i$f$fastFirst);
            Measurable it7 = (Measurable) item$iv$iv;
            int index$iv$iv5 = $i$f$fastFirst;
            if (Intrinsics.areEqual(LayoutIdKt.getLayoutId(it7), "TextField")) {
                final Placeable textFieldPlaceable = ((Measurable) item$iv$iv).mo5016measureBRTryo0(textFieldConstraints);
                placeholderConstraints = Constraints.m6040copyZbe2FdA(textFieldConstraints, (r12 & 1) != 0 ? Constraints.m6052getMinWidthimpl(textFieldConstraints) : 0, (r12 & 2) != 0 ? Constraints.m6050getMaxWidthimpl(textFieldConstraints) : 0, (r12 & 4) != 0 ? Constraints.m6051getMinHeightimpl(textFieldConstraints) : 0, (r12 & 8) != 0 ? Constraints.m6049getMaxHeightimpl(textFieldConstraints) : 0);
                List $this$fastForEach$iv$iv7 = list;
                int size8 = $this$fastForEach$iv$iv7.size();
                int index$iv$iv6 = 0;
                while (true) {
                    if (index$iv$iv6 >= size8) {
                        supportingMeasurable = supportingMeasurable3;
                        it$iv7 = null;
                        break;
                    }
                    int i4 = size8;
                    List $this$fastForEach$iv$iv8 = $this$fastForEach$iv$iv7;
                    it$iv7 = $this$fastForEach$iv$iv8.get(index$iv$iv6);
                    Measurable it8 = (Measurable) it$iv7;
                    supportingMeasurable = supportingMeasurable3;
                    if (Intrinsics.areEqual(LayoutIdKt.getLayoutId(it8), "Hint")) {
                        break;
                    }
                    index$iv$iv6++;
                    size8 = i4;
                    $this$fastForEach$iv$iv7 = $this$fastForEach$iv$iv8;
                    supportingMeasurable3 = supportingMeasurable;
                }
                Measurable measurable6 = (Measurable) it$iv7;
                final Placeable placeholderPlaceable = measurable6 != null ? measurable6.mo5016measureBRTryo0(placeholderConstraints) : null;
                int occupiedSpaceVertically6 = Math.max(occupiedSpaceVertically4, Math.max(TextFieldImplKt.heightOrZero(textFieldPlaceable), TextFieldImplKt.heightOrZero(placeholderPlaceable)) + effectiveTopOffset + bottomPaddingValue);
                width = TextFieldKt.m2461calculateWidthyeHjK3Y(TextFieldImplKt.widthOrZero(leadingPlaceable), TextFieldImplKt.widthOrZero(trailingPlaceable), TextFieldImplKt.widthOrZero(prefixPlaceable), TextFieldImplKt.widthOrZero(suffixPlaceable), textFieldPlaceable.getWidth(), TextFieldImplKt.widthOrZero(labelPlaceable), TextFieldImplKt.widthOrZero(placeholderPlaceable), constraints);
                supportingConstraints = Constraints.m6040copyZbe2FdA(r44, (r12 & 1) != 0 ? Constraints.m6052getMinWidthimpl(r44) : 0, (r12 & 2) != 0 ? Constraints.m6050getMaxWidthimpl(r44) : width, (r12 & 4) != 0 ? Constraints.m6051getMinHeightimpl(r44) : 0, (r12 & 8) != 0 ? Constraints.m6049getMaxHeightimpl(ConstraintsKt.m6067offsetNN6EwU$default(looseConstraints, 0, -occupiedSpaceVertically6, 1, null)) : 0);
                if (supportingMeasurable != null) {
                    placeholderConstraints2 = placeholderConstraints;
                    placeholderConstraints3 = supportingConstraints;
                    supportingMeasurable2 = supportingMeasurable;
                    placeable = supportingMeasurable2.mo5016measureBRTryo0(placeholderConstraints3);
                } else {
                    placeholderConstraints2 = placeholderConstraints;
                    placeholderConstraints3 = supportingConstraints;
                    supportingMeasurable2 = supportingMeasurable;
                    placeable = null;
                }
                final Placeable supportingPlaceable = placeable;
                int supportingHeight = TextFieldImplKt.heightOrZero(supportingPlaceable);
                totalHeight = TextFieldKt.m2460calculateHeightmKXJcVc(textFieldPlaceable.getHeight(), TextFieldImplKt.heightOrZero(labelPlaceable), TextFieldImplKt.heightOrZero(leadingPlaceable), TextFieldImplKt.heightOrZero(trailingPlaceable), TextFieldImplKt.heightOrZero(prefixPlaceable), TextFieldImplKt.heightOrZero(suffixPlaceable), TextFieldImplKt.heightOrZero(placeholderPlaceable), TextFieldImplKt.heightOrZero(supportingPlaceable), this.animationProgress, constraints, $this$measure_u2d3p2s80s.getDensity(), this.paddingValues);
                int height = totalHeight - supportingHeight;
                List $this$fastForEach$iv$iv9 = list;
                int size9 = $this$fastForEach$iv$iv9.size();
                int index$iv$iv7 = 0;
                while (index$iv$iv7 < size9) {
                    List $this$fastForEach$iv$iv10 = $this$fastForEach$iv$iv9;
                    Object item$iv$iv2 = $this$fastForEach$iv$iv10.get(index$iv$iv7);
                    Measurable it9 = (Measurable) item$iv$iv2;
                    int i5 = size9;
                    if (Intrinsics.areEqual(LayoutIdKt.getLayoutId(it9), TextFieldImplKt.ContainerId)) {
                        final Placeable containerPlaceable = ((Measurable) item$iv$iv2).mo5016measureBRTryo0(ConstraintsKt.Constraints(width != Integer.MAX_VALUE ? width : 0, width, height != Integer.MAX_VALUE ? height : 0, height));
                        return MeasureScope.layout$default($this$measure_u2d3p2s80s, width, totalHeight, null, new Function1<Placeable.PlacementScope, Unit>() { // from class: androidx.compose.material3.TextFieldMeasurePolicy$measure$1
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
                                boolean z;
                                PaddingValues paddingValues;
                                boolean z2;
                                float f;
                                if (Placeable.this != null) {
                                    int i6 = width;
                                    int i7 = totalHeight;
                                    Placeable placeable2 = textFieldPlaceable;
                                    Placeable placeable3 = Placeable.this;
                                    Placeable placeable4 = placeholderPlaceable;
                                    Placeable placeable5 = leadingPlaceable;
                                    Placeable placeable6 = trailingPlaceable;
                                    Placeable placeable7 = prefixPlaceable;
                                    Placeable placeable8 = suffixPlaceable;
                                    Placeable placeable9 = containerPlaceable;
                                    Placeable placeable10 = supportingPlaceable;
                                    z2 = this.singleLine;
                                    int i8 = topPaddingValue;
                                    int height2 = topPaddingValue + Placeable.this.getHeight();
                                    f = this.animationProgress;
                                    TextFieldKt.placeWithLabel($this$layout, i6, i7, placeable2, placeable3, placeable4, placeable5, placeable6, placeable7, placeable8, placeable9, placeable10, z2, i8, height2, f, $this$measure_u2d3p2s80s.getDensity());
                                    return;
                                }
                                int i9 = width;
                                int i10 = totalHeight;
                                Placeable placeable11 = textFieldPlaceable;
                                Placeable placeable12 = placeholderPlaceable;
                                Placeable placeable13 = leadingPlaceable;
                                Placeable placeable14 = trailingPlaceable;
                                Placeable placeable15 = prefixPlaceable;
                                Placeable placeable16 = suffixPlaceable;
                                Placeable placeable17 = containerPlaceable;
                                Placeable placeable18 = supportingPlaceable;
                                z = this.singleLine;
                                float density = $this$measure_u2d3p2s80s.getDensity();
                                paddingValues = this.paddingValues;
                                TextFieldKt.placeWithoutLabel($this$layout, i9, i10, placeable11, placeable12, placeable13, placeable14, placeable15, placeable16, placeable17, placeable18, z, density, paddingValues);
                            }
                        }, 4, null);
                    }
                    index$iv$iv7++;
                    size9 = i5;
                    $this$fastForEach$iv$iv9 = $this$fastForEach$iv$iv10;
                }
                throw new NoSuchElementException("Collection contains no element matching the predicate.");
            }
            $i$f$fastFirst = index$iv$iv5 + 1;
            size7 = i3;
            occupiedSpaceHorizontally4 = occupiedSpaceHorizontally5;
            textFieldConstraints = textFieldConstraints;
            $this$fastForEach$iv$iv5 = $this$fastForEach$iv$iv6;
        }
    }

    @Override // androidx.compose.ui.layout.MeasurePolicy
    public int maxIntrinsicHeight(IntrinsicMeasureScope $this$maxIntrinsicHeight, List<? extends IntrinsicMeasurable> list, int width) {
        return intrinsicHeight($this$maxIntrinsicHeight, list, width, new Function2<IntrinsicMeasurable, Integer, Integer>() { // from class: androidx.compose.material3.TextFieldMeasurePolicy$maxIntrinsicHeight$1
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
        return intrinsicHeight($this$minIntrinsicHeight, list, width, new Function2<IntrinsicMeasurable, Integer, Integer>() { // from class: androidx.compose.material3.TextFieldMeasurePolicy$minIntrinsicHeight$1
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
        return intrinsicWidth(list, height, new Function2<IntrinsicMeasurable, Integer, Integer>() { // from class: androidx.compose.material3.TextFieldMeasurePolicy$maxIntrinsicWidth$1
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
        return intrinsicWidth(list, height, new Function2<IntrinsicMeasurable, Integer, Integer>() { // from class: androidx.compose.material3.TextFieldMeasurePolicy$minIntrinsicWidth$1
            @Override // kotlin.jvm.functions.Function2
            public /* bridge */ /* synthetic */ Integer invoke(IntrinsicMeasurable intrinsicMeasurable, Integer num) {
                return invoke(intrinsicMeasurable, num.intValue());
            }

            public final Integer invoke(IntrinsicMeasurable intrinsicMeasurable, int h) {
                return Integer.valueOf(intrinsicMeasurable.minIntrinsicWidth(h));
            }
        });
    }

    private final int intrinsicWidth(List<? extends IntrinsicMeasurable> measurables, int height, Function2<? super IntrinsicMeasurable, ? super Integer, Integer> intrinsicMeasurer) {
        Object it$iv;
        Object it$iv2;
        Object it$iv3;
        Object it$iv4;
        Object it$iv5;
        Object obj;
        int m2461calculateWidthyeHjK3Y;
        int size = measurables.size();
        for (int index$iv$iv = 0; index$iv$iv < size; index$iv$iv++) {
            Object item$iv$iv = measurables.get(index$iv$iv);
            if (Intrinsics.areEqual(TextFieldImplKt.getLayoutId((IntrinsicMeasurable) item$iv$iv), "TextField")) {
                int textFieldWidth = intrinsicMeasurer.invoke(item$iv$iv, Integer.valueOf(height)).intValue();
                int index$iv$iv2 = 0;
                int size2 = measurables.size();
                while (true) {
                    if (index$iv$iv2 >= size2) {
                        it$iv = null;
                        break;
                    }
                    it$iv = measurables.get(index$iv$iv2);
                    if (Intrinsics.areEqual(TextFieldImplKt.getLayoutId((IntrinsicMeasurable) it$iv), "Label")) {
                        break;
                    }
                    index$iv$iv2++;
                }
                IntrinsicMeasurable it = (IntrinsicMeasurable) it$iv;
                int labelWidth = it != null ? intrinsicMeasurer.invoke(it, Integer.valueOf(height)).intValue() : 0;
                int index$iv$iv3 = 0;
                int size3 = measurables.size();
                while (true) {
                    if (index$iv$iv3 >= size3) {
                        it$iv2 = null;
                        break;
                    }
                    it$iv2 = measurables.get(index$iv$iv3);
                    if (Intrinsics.areEqual(TextFieldImplKt.getLayoutId((IntrinsicMeasurable) it$iv2), "Trailing")) {
                        break;
                    }
                    index$iv$iv3++;
                }
                IntrinsicMeasurable it2 = (IntrinsicMeasurable) it$iv2;
                int trailingWidth = it2 != null ? intrinsicMeasurer.invoke(it2, Integer.valueOf(height)).intValue() : 0;
                List $this$fastFirstOrNull$iv = measurables;
                int index$iv$iv4 = 0;
                int size4 = $this$fastFirstOrNull$iv.size();
                while (true) {
                    if (index$iv$iv4 >= size4) {
                        it$iv3 = null;
                        break;
                    }
                    it$iv3 = $this$fastFirstOrNull$iv.get(index$iv$iv4);
                    List $this$fastFirstOrNull$iv2 = $this$fastFirstOrNull$iv;
                    if (Intrinsics.areEqual(TextFieldImplKt.getLayoutId((IntrinsicMeasurable) it$iv3), TextFieldImplKt.PrefixId)) {
                        break;
                    }
                    index$iv$iv4++;
                    $this$fastFirstOrNull$iv = $this$fastFirstOrNull$iv2;
                }
                IntrinsicMeasurable it3 = (IntrinsicMeasurable) it$iv3;
                int prefixWidth = it3 != null ? intrinsicMeasurer.invoke(it3, Integer.valueOf(height)).intValue() : 0;
                List $this$fastFirstOrNull$iv3 = measurables;
                int $i$f$fastFirstOrNull = 0;
                int index$iv$iv5 = 0;
                int size5 = $this$fastFirstOrNull$iv3.size();
                while (true) {
                    if (index$iv$iv5 >= size5) {
                        it$iv4 = null;
                        break;
                    }
                    it$iv4 = $this$fastFirstOrNull$iv3.get(index$iv$iv5);
                    List $this$fastFirstOrNull$iv4 = $this$fastFirstOrNull$iv3;
                    int $i$f$fastFirstOrNull2 = $i$f$fastFirstOrNull;
                    if (Intrinsics.areEqual(TextFieldImplKt.getLayoutId((IntrinsicMeasurable) it$iv4), TextFieldImplKt.SuffixId)) {
                        break;
                    }
                    index$iv$iv5++;
                    $this$fastFirstOrNull$iv3 = $this$fastFirstOrNull$iv4;
                    $i$f$fastFirstOrNull = $i$f$fastFirstOrNull2;
                }
                IntrinsicMeasurable it4 = (IntrinsicMeasurable) it$iv4;
                int suffixWidth = it4 != null ? intrinsicMeasurer.invoke(it4, Integer.valueOf(height)).intValue() : 0;
                List $this$fastFirstOrNull$iv5 = measurables;
                int $i$f$fastFirstOrNull3 = 0;
                int index$iv$iv6 = 0;
                int size6 = $this$fastFirstOrNull$iv5.size();
                while (true) {
                    if (index$iv$iv6 >= size6) {
                        it$iv5 = null;
                        break;
                    }
                    it$iv5 = $this$fastFirstOrNull$iv5.get(index$iv$iv6);
                    List $this$fastFirstOrNull$iv6 = $this$fastFirstOrNull$iv5;
                    int $i$f$fastFirstOrNull4 = $i$f$fastFirstOrNull3;
                    if (Intrinsics.areEqual(TextFieldImplKt.getLayoutId((IntrinsicMeasurable) it$iv5), "Leading")) {
                        break;
                    }
                    index$iv$iv6++;
                    $this$fastFirstOrNull$iv5 = $this$fastFirstOrNull$iv6;
                    $i$f$fastFirstOrNull3 = $i$f$fastFirstOrNull4;
                }
                IntrinsicMeasurable it5 = (IntrinsicMeasurable) it$iv5;
                int leadingWidth = it5 != null ? intrinsicMeasurer.invoke(it5, Integer.valueOf(height)).intValue() : 0;
                List $this$fastFirstOrNull$iv7 = measurables;
                int $i$f$fastFirstOrNull5 = 0;
                int index$iv$iv7 = 0;
                int size7 = $this$fastFirstOrNull$iv7.size();
                while (true) {
                    if (index$iv$iv7 >= size7) {
                        obj = null;
                        break;
                    }
                    Object item$iv$iv2 = $this$fastFirstOrNull$iv7.get(index$iv$iv7);
                    List $this$fastFirstOrNull$iv8 = $this$fastFirstOrNull$iv7;
                    int $i$f$fastFirstOrNull6 = $i$f$fastFirstOrNull5;
                    if (Intrinsics.areEqual(TextFieldImplKt.getLayoutId((IntrinsicMeasurable) item$iv$iv2), "Hint")) {
                        obj = item$iv$iv2;
                        break;
                    }
                    index$iv$iv7++;
                    $this$fastFirstOrNull$iv7 = $this$fastFirstOrNull$iv8;
                    $i$f$fastFirstOrNull5 = $i$f$fastFirstOrNull6;
                }
                IntrinsicMeasurable it6 = (IntrinsicMeasurable) obj;
                int placeholderWidth = it6 != null ? intrinsicMeasurer.invoke(it6, Integer.valueOf(height)).intValue() : 0;
                m2461calculateWidthyeHjK3Y = TextFieldKt.m2461calculateWidthyeHjK3Y(leadingWidth, trailingWidth, prefixWidth, suffixWidth, textFieldWidth, labelWidth, placeholderWidth, TextFieldImplKt.getZeroConstraints());
                return m2461calculateWidthyeHjK3Y;
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
        Object item$iv$iv;
        int m2460calculateHeightmKXJcVc;
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
            remainingWidth = TextFieldKt.substractConstraintSafely(remainingWidth, it.maxIntrinsicWidth(Integer.MAX_VALUE));
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
            remainingWidth = TextFieldKt.substractConstraintSafely(remainingWidth, it2.maxIntrinsicWidth(Integer.MAX_VALUE));
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
        int labelHeight = it3 != null ? function2.invoke(it3, Integer.valueOf(remainingWidth)).intValue() : 0;
        int index$iv$iv4 = 0;
        int size4 = list.size();
        while (true) {
            if (index$iv$iv4 >= size4) {
                it$iv4 = null;
                break;
            }
            it$iv4 = list.get(index$iv$iv4);
            if (Intrinsics.areEqual(TextFieldImplKt.getLayoutId((IntrinsicMeasurable) it$iv4), TextFieldImplKt.PrefixId)) {
                break;
            }
            index$iv$iv4++;
        }
        IntrinsicMeasurable it4 = (IntrinsicMeasurable) it$iv4;
        if (it4 != null) {
            int height = function2.invoke(it4, Integer.valueOf(remainingWidth)).intValue();
            remainingWidth = TextFieldKt.substractConstraintSafely(remainingWidth, it4.maxIntrinsicWidth(Integer.MAX_VALUE));
            prefixHeight = height;
        } else {
            prefixHeight = 0;
        }
        int index$iv$iv5 = 0;
        int size5 = list.size();
        while (true) {
            if (index$iv$iv5 >= size5) {
                it$iv5 = null;
                break;
            }
            it$iv5 = list.get(index$iv$iv5);
            if (Intrinsics.areEqual(TextFieldImplKt.getLayoutId((IntrinsicMeasurable) it$iv5), TextFieldImplKt.SuffixId)) {
                break;
            }
            index$iv$iv5++;
        }
        IntrinsicMeasurable it5 = (IntrinsicMeasurable) it$iv5;
        if (it5 != null) {
            int height2 = function2.invoke(it5, Integer.valueOf(remainingWidth)).intValue();
            remainingWidth = TextFieldKt.substractConstraintSafely(remainingWidth, it5.maxIntrinsicWidth(Integer.MAX_VALUE));
            suffixHeight = height2;
        } else {
            suffixHeight = 0;
        }
        int size6 = list.size();
        for (int index$iv$iv6 = 0; index$iv$iv6 < size6; index$iv$iv6++) {
            Object item$iv$iv2 = list.get(index$iv$iv6);
            if (Intrinsics.areEqual(TextFieldImplKt.getLayoutId((IntrinsicMeasurable) item$iv$iv2), "TextField")) {
                int textFieldHeight = function2.invoke(item$iv$iv2, Integer.valueOf(remainingWidth)).intValue();
                int index$iv$iv7 = 0;
                int size7 = list.size();
                while (true) {
                    if (index$iv$iv7 >= size7) {
                        it$iv6 = null;
                        break;
                    }
                    it$iv6 = list.get(index$iv$iv7);
                    if (Intrinsics.areEqual(TextFieldImplKt.getLayoutId((IntrinsicMeasurable) it$iv6), "Hint")) {
                        break;
                    }
                    index$iv$iv7++;
                }
                IntrinsicMeasurable it6 = (IntrinsicMeasurable) it$iv6;
                int placeholderHeight = it6 != null ? function2.invoke(it6, Integer.valueOf(remainingWidth)).intValue() : 0;
                int index$iv$iv8 = 0;
                int size8 = list.size();
                while (true) {
                    if (index$iv$iv8 >= size8) {
                        item$iv$iv = null;
                        break;
                    }
                    Object item$iv$iv3 = list.get(index$iv$iv8);
                    if (Intrinsics.areEqual(TextFieldImplKt.getLayoutId((IntrinsicMeasurable) item$iv$iv3), TextFieldImplKt.SupportingId)) {
                        item$iv$iv = item$iv$iv3;
                        break;
                    }
                    index$iv$iv8++;
                }
                IntrinsicMeasurable it7 = (IntrinsicMeasurable) item$iv$iv;
                int supportingHeight = it7 != null ? function2.invoke(it7, Integer.valueOf(width)).intValue() : 0;
                m2460calculateHeightmKXJcVc = TextFieldKt.m2460calculateHeightmKXJcVc(textFieldHeight, labelHeight, leadingHeight, trailingHeight, prefixHeight, suffixHeight, placeholderHeight, supportingHeight, this.animationProgress, TextFieldImplKt.getZeroConstraints(), $this$intrinsicHeight.getDensity(), this.paddingValues);
                return m2460calculateHeightmKXJcVc;
            }
        }
        throw new NoSuchElementException("Collection contains no element matching the predicate.");
    }
}
