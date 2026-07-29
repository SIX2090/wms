package androidx.compose.material3;

import androidx.compose.animation.core.Animatable;
import androidx.compose.animation.core.AnimationVector1D;
import androidx.compose.animation.core.VectorConvertersKt;
import androidx.compose.ui.layout.Measurable;
import androidx.compose.ui.layout.MeasureResult;
import androidx.compose.ui.layout.MeasureScope;
import androidx.compose.ui.layout.MultiContentMeasurePolicy;
import androidx.compose.ui.layout.Placeable;
import java.util.ArrayList;
import java.util.List;
import kotlin.Metadata;
import kotlin.Unit;
import kotlin.collections.CollectionsKt;
import kotlin.jvm.functions.Function1;
import kotlin.jvm.internal.IntCompanionObject;
import kotlin.jvm.internal.Intrinsics;
import kotlinx.coroutines.BuildersKt__Builders_commonKt;
import kotlinx.coroutines.CoroutineScope;

/* compiled from: SegmentedButton.kt */
@Metadata(d1 = {"\u0000>\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\u0010\b\n\u0002\u0018\u0002\n\u0002\b\t\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010 \n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\b\u0000\u0018\u00002\u00020\u0001B\r\u0012\u0006\u0010\u0002\u001a\u00020\u0003¢\u0006\u0002\u0010\u0004J2\u0010\u0011\u001a\u00020\u0012*\u00020\u00132\u0012\u0010\u0014\u001a\u000e\u0012\n\u0012\b\u0012\u0004\u0012\u00020\u00160\u00150\u00152\u0006\u0010\u0017\u001a\u00020\u0018H\u0016ø\u0001\u0000¢\u0006\u0004\b\u0019\u0010\u001aR(\u0010\u0005\u001a\u0010\u0012\u0004\u0012\u00020\u0007\u0012\u0004\u0012\u00020\b\u0018\u00010\u0006X\u0086\u000e¢\u0006\u000e\n\u0000\u001a\u0004\b\t\u0010\n\"\u0004\b\u000b\u0010\fR\u0012\u0010\r\u001a\u0004\u0018\u00010\u0007X\u0082\u000e¢\u0006\u0004\n\u0002\u0010\u000eR\u0011\u0010\u0002\u001a\u00020\u0003¢\u0006\b\n\u0000\u001a\u0004\b\u000f\u0010\u0010\u0082\u0002\u0007\n\u0005\b¡\u001e0\u0001¨\u0006\u001b"}, d2 = {"Landroidx/compose/material3/SegmentedButtonContentMeasurePolicy;", "Landroidx/compose/ui/layout/MultiContentMeasurePolicy;", "scope", "Lkotlinx/coroutines/CoroutineScope;", "(Lkotlinx/coroutines/CoroutineScope;)V", "animatable", "Landroidx/compose/animation/core/Animatable;", "", "Landroidx/compose/animation/core/AnimationVector1D;", "getAnimatable", "()Landroidx/compose/animation/core/Animatable;", "setAnimatable", "(Landroidx/compose/animation/core/Animatable;)V", "initialOffset", "Ljava/lang/Integer;", "getScope", "()Lkotlinx/coroutines/CoroutineScope;", "measure", "Landroidx/compose/ui/layout/MeasureResult;", "Landroidx/compose/ui/layout/MeasureScope;", "measurables", "", "Landroidx/compose/ui/layout/Measurable;", "constraints", "Landroidx/compose/ui/unit/Constraints;", "measure-3p2s80s", "(Landroidx/compose/ui/layout/MeasureScope;Ljava/util/List;J)Landroidx/compose/ui/layout/MeasureResult;", "material3_release"}, k = 1, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class SegmentedButtonContentMeasurePolicy implements MultiContentMeasurePolicy {
    public static final int $stable = 0;
    private Animatable<Integer, AnimationVector1D> animatable;
    private Integer initialOffset;
    private final CoroutineScope scope;

    public SegmentedButtonContentMeasurePolicy(CoroutineScope scope) {
        this.scope = scope;
    }

    public final CoroutineScope getScope() {
        return this.scope;
    }

    public final Animatable<Integer, AnimationVector1D> getAnimatable() {
        return this.animatable;
    }

    public final void setAnimatable(Animatable<Integer, AnimationVector1D> animatable) {
        this.animatable = animatable;
    }

    @Override // androidx.compose.ui.layout.MultiContentMeasurePolicy
    /* renamed from: measure-3p2s80s */
    public MeasureResult mo1985measure3p2s80s(final MeasureScope $this$measure_u2d3p2s80s, List<? extends List<? extends Measurable>> list, long constraints) {
        Object maxElem$iv;
        Object maxElem$iv2;
        Object maxElem$iv3;
        float f;
        int i;
        float f2;
        List iconMeasurables = list.get(0);
        List contentMeasurables = list.get(1);
        List $this$fastMap$iv = iconMeasurables;
        List target$iv = new ArrayList($this$fastMap$iv.size());
        int index$iv$iv = 0;
        int size = $this$fastMap$iv.size();
        while (index$iv$iv < size) {
            Object item$iv$iv = $this$fastMap$iv.get(index$iv$iv);
            List $this$fastMap$iv2 = $this$fastMap$iv;
            Measurable it = (Measurable) item$iv$iv;
            target$iv.add(it.mo5016measureBRTryo0(constraints));
            index$iv$iv++;
            $this$fastMap$iv = $this$fastMap$iv2;
        }
        final List iconPlaceables = target$iv;
        if (iconPlaceables.isEmpty()) {
            maxElem$iv = null;
        } else {
            maxElem$iv = iconPlaceables.get(0);
            Placeable it2 = (Placeable) maxElem$iv;
            int maxValue$iv = it2.getWidth();
            int i$iv = 1;
            int lastIndex = CollectionsKt.getLastIndex(iconPlaceables);
            if (1 <= lastIndex) {
                while (true) {
                    Object e$iv = iconPlaceables.get(i$iv);
                    Placeable it3 = (Placeable) e$iv;
                    int v$iv = it3.getWidth();
                    if (maxValue$iv < v$iv) {
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
        Placeable placeable = (Placeable) maxElem$iv;
        int iconWidth = placeable != null ? placeable.getWidth() : 0;
        List $this$fastMap$iv3 = contentMeasurables;
        List target$iv2 = new ArrayList($this$fastMap$iv3.size());
        int index$iv$iv2 = 0;
        int size2 = $this$fastMap$iv3.size();
        while (index$iv$iv2 < size2) {
            Object item$iv$iv2 = $this$fastMap$iv3.get(index$iv$iv2);
            List $this$fastMap$iv4 = $this$fastMap$iv3;
            Measurable it4 = (Measurable) item$iv$iv2;
            target$iv2.add(it4.mo5016measureBRTryo0(constraints));
            index$iv$iv2++;
            $this$fastMap$iv3 = $this$fastMap$iv4;
        }
        final List contentPlaceables = target$iv2;
        if (contentPlaceables.isEmpty()) {
            maxElem$iv2 = null;
        } else {
            maxElem$iv2 = contentPlaceables.get(0);
            Placeable it5 = (Placeable) maxElem$iv2;
            int maxValue$iv2 = it5.getWidth();
            int i$iv2 = 1;
            int lastIndex2 = CollectionsKt.getLastIndex(contentPlaceables);
            if (1 <= lastIndex2) {
                while (true) {
                    Object e$iv2 = contentPlaceables.get(i$iv2);
                    Placeable it6 = (Placeable) e$iv2;
                    int v$iv2 = it6.getWidth();
                    if (maxValue$iv2 < v$iv2) {
                        maxElem$iv2 = e$iv2;
                        maxValue$iv2 = v$iv2;
                    }
                    if (i$iv2 == lastIndex2) {
                        break;
                    }
                    i$iv2++;
                }
            }
        }
        Placeable placeable2 = (Placeable) maxElem$iv2;
        Integer contentWidth = placeable2 != null ? Integer.valueOf(placeable2.getWidth()) : null;
        if (contentPlaceables.isEmpty()) {
            maxElem$iv3 = null;
        } else {
            maxElem$iv3 = contentPlaceables.get(0);
            Placeable it7 = (Placeable) maxElem$iv3;
            int maxValue$iv3 = it7.getHeight();
            int i$iv3 = 1;
            int lastIndex3 = CollectionsKt.getLastIndex(contentPlaceables);
            if (1 <= lastIndex3) {
                while (true) {
                    Object e$iv3 = contentPlaceables.get(i$iv3);
                    Placeable it8 = (Placeable) e$iv3;
                    int height = it8.getHeight();
                    if (maxValue$iv3 < height) {
                        maxElem$iv3 = e$iv3;
                        maxValue$iv3 = height;
                    }
                    if (i$iv3 == lastIndex3) {
                        break;
                    }
                    i$iv3++;
                }
            }
        }
        Placeable placeable3 = (Placeable) maxElem$iv3;
        final int height2 = placeable3 != null ? placeable3.getHeight() : 0;
        int max = Math.max($this$measure_u2d3p2s80s.mo307roundToPx0680j_4(SegmentedButtonDefaults.INSTANCE.m2163getIconSizeD9Ej5fM()), iconWidth);
        f = SegmentedButtonKt.IconSpacing;
        int width = max + $this$measure_u2d3p2s80s.mo307roundToPx0680j_4(f) + (contentWidth != null ? contentWidth.intValue() : 0);
        if (iconWidth == 0) {
            int i2 = $this$measure_u2d3p2s80s.mo307roundToPx0680j_4(SegmentedButtonDefaults.INSTANCE.m2163getIconSizeD9Ej5fM());
            f2 = SegmentedButtonKt.IconSpacing;
            i = (-(i2 + $this$measure_u2d3p2s80s.mo307roundToPx0680j_4(f2))) / 2;
        } else {
            i = 0;
        }
        final int offsetX = i;
        if (this.initialOffset == null) {
            this.initialOffset = Integer.valueOf(offsetX);
        } else {
            Animatable it9 = this.animatable;
            if (it9 == null) {
                Integer num = this.initialOffset;
                Intrinsics.checkNotNull(num);
                it9 = new Animatable(num, VectorConvertersKt.getVectorConverter(IntCompanionObject.INSTANCE), null, null, 12, null);
                this.animatable = it9;
            }
            if (it9.getTargetValue().intValue() != offsetX) {
                BuildersKt__Builders_commonKt.launch$default(this.scope, null, null, new SegmentedButtonContentMeasurePolicy$measure$1(it9, offsetX, null), 3, null);
            }
        }
        return MeasureScope.layout$default($this$measure_u2d3p2s80s, width, height2, null, new Function1<Placeable.PlacementScope, Unit>() { // from class: androidx.compose.material3.SegmentedButtonContentMeasurePolicy$measure$2
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
                float f3;
                List $this$fastForEach$iv = iconPlaceables;
                int i3 = height2;
                int size3 = $this$fastForEach$iv.size();
                for (int index$iv = 0; index$iv < size3; index$iv++) {
                    Object item$iv = $this$fastForEach$iv.get(index$iv);
                    Placeable it10 = (Placeable) item$iv;
                    Placeable.PlacementScope.place$default($this$layout, it10, 0, (i3 - it10.getHeight()) / 2, 0.0f, 4, null);
                }
                int i4 = $this$measure_u2d3p2s80s.mo307roundToPx0680j_4(SegmentedButtonDefaults.INSTANCE.m2163getIconSizeD9Ej5fM());
                MeasureScope measureScope = $this$measure_u2d3p2s80s;
                f3 = SegmentedButtonKt.IconSpacing;
                int i5 = i4 + measureScope.mo307roundToPx0680j_4(f3);
                Animatable<Integer, AnimationVector1D> animatable = this.getAnimatable();
                int contentOffsetX = i5 + (animatable != null ? animatable.getValue().intValue() : offsetX);
                List $this$fastForEach$iv2 = contentPlaceables;
                int i6 = height2;
                int size4 = $this$fastForEach$iv2.size();
                for (int index$iv2 = 0; index$iv2 < size4; index$iv2++) {
                    Object item$iv2 = $this$fastForEach$iv2.get(index$iv2);
                    Placeable it11 = (Placeable) item$iv2;
                    Placeable.PlacementScope.place$default($this$layout, it11, contentOffsetX, (i6 - it11.getHeight()) / 2, 0.0f, 4, null);
                }
            }
        }, 4, null);
    }
}
