package androidx.compose.material;

import androidx.autofill.HintConstants;
import androidx.compose.animation.core.AnimationSpec;
import androidx.compose.animation.core.AnimationSpecKt;
import androidx.compose.animation.core.EasingKt;
import androidx.compose.foundation.ScrollKt;
import androidx.compose.foundation.ScrollState;
import androidx.compose.foundation.layout.SizeKt;
import androidx.compose.foundation.selection.SelectableGroupKt;
import androidx.compose.runtime.Composer;
import androidx.compose.runtime.ComposerKt;
import androidx.compose.runtime.CompositionScopedCoroutineScopeCanceller;
import androidx.compose.runtime.EffectsKt;
import androidx.compose.runtime.RecomposeScopeImplKt;
import androidx.compose.runtime.ScopeUpdateScope;
import androidx.compose.runtime.internal.ComposableLambdaKt;
import androidx.compose.ui.Alignment;
import androidx.compose.ui.Modifier;
import androidx.compose.ui.draw.ClipKt;
import androidx.compose.ui.layout.Measurable;
import androidx.compose.ui.layout.MeasureResult;
import androidx.compose.ui.layout.MeasureScope;
import androidx.compose.ui.layout.Placeable;
import androidx.compose.ui.layout.SubcomposeLayoutKt;
import androidx.compose.ui.layout.SubcomposeMeasureScope;
import androidx.compose.ui.unit.Constraints;
import androidx.compose.ui.unit.Dp;
import androidx.profileinstaller.ProfileVerifier;
import java.util.ArrayList;
import java.util.List;
import kotlin.Metadata;
import kotlin.Unit;
import kotlin.collections.CollectionsKt;
import kotlin.coroutines.EmptyCoroutineContext;
import kotlin.jvm.functions.Function1;
import kotlin.jvm.functions.Function2;
import kotlin.jvm.functions.Function3;
import kotlin.jvm.internal.Ref;
import kotlinx.coroutines.CoroutineScope;

/* compiled from: TabRow.kt */
@Metadata(d1 = {"\u0000T\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\u0010\u0007\n\u0000\n\u0002\u0010\u0002\n\u0000\n\u0002\u0010\b\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0018\u0002\n\u0002\u0010 \n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0007\u001a©\u0001\u0010\u0006\u001a\u00020\u00072\u0006\u0010\b\u001a\u00020\t2\b\b\u0002\u0010\n\u001a\u00020\u000b2\b\b\u0002\u0010\f\u001a\u00020\r2\b\b\u0002\u0010\u000e\u001a\u00020\r2\b\b\u0002\u0010\u000f\u001a\u00020\u000123\b\u0002\u0010\u0010\u001a-\u0012\u0019\u0012\u0017\u0012\u0004\u0012\u00020\u00130\u0012¢\u0006\f\b\u0014\u0012\b\b\u0015\u0012\u0004\b\b(\u0016\u0012\u0004\u0012\u00020\u00070\u0011¢\u0006\u0002\b\u0017¢\u0006\u0002\b\u00182\u0018\b\u0002\u0010\u0019\u001a\u0012\u0012\u0004\u0012\u00020\u00070\u001a¢\u0006\u0002\b\u0017¢\u0006\u0002\b\u00182\u0016\u0010\u001b\u001a\u0012\u0012\u0004\u0012\u00020\u00070\u001a¢\u0006\u0002\b\u0017¢\u0006\u0002\b\u0018H\u0007ø\u0001\u0000¢\u0006\u0004\b\u001c\u0010\u001d\u001a\u009f\u0001\u0010\u001e\u001a\u00020\u00072\u0006\u0010\b\u001a\u00020\t2\b\b\u0002\u0010\n\u001a\u00020\u000b2\b\b\u0002\u0010\f\u001a\u00020\r2\b\b\u0002\u0010\u000e\u001a\u00020\r23\b\u0002\u0010\u0010\u001a-\u0012\u0019\u0012\u0017\u0012\u0004\u0012\u00020\u00130\u0012¢\u0006\f\b\u0014\u0012\b\b\u0015\u0012\u0004\b\b(\u0016\u0012\u0004\u0012\u00020\u00070\u0011¢\u0006\u0002\b\u0017¢\u0006\u0002\b\u00182\u0018\b\u0002\u0010\u0019\u001a\u0012\u0012\u0004\u0012\u00020\u00070\u001a¢\u0006\u0002\b\u0017¢\u0006\u0002\b\u00182\u0016\u0010\u001b\u001a\u0012\u0012\u0004\u0012\u00020\u00070\u001a¢\u0006\u0002\b\u0017¢\u0006\u0002\b\u0018H\u0007ø\u0001\u0000¢\u0006\u0004\b\u001f\u0010 \"\u0010\u0010\u0000\u001a\u00020\u0001X\u0082\u0004¢\u0006\u0004\n\u0002\u0010\u0002\"\u0014\u0010\u0003\u001a\b\u0012\u0004\u0012\u00020\u00050\u0004X\u0082\u0004¢\u0006\u0002\n\u0000\u0082\u0002\u0007\n\u0005\b¡\u001e0\u0001¨\u0006!"}, d2 = {"ScrollableTabRowMinimumTabWidth", "Landroidx/compose/ui/unit/Dp;", "F", "ScrollableTabRowScrollSpec", "Landroidx/compose/animation/core/AnimationSpec;", "", "ScrollableTabRow", "", "selectedTabIndex", "", "modifier", "Landroidx/compose/ui/Modifier;", "backgroundColor", "Landroidx/compose/ui/graphics/Color;", "contentColor", "edgePadding", "indicator", "Lkotlin/Function1;", "", "Landroidx/compose/material/TabPosition;", "Lkotlin/ParameterName;", HintConstants.AUTOFILL_HINT_NAME, "tabPositions", "Landroidx/compose/runtime/Composable;", "Landroidx/compose/ui/UiComposable;", "divider", "Lkotlin/Function0;", "tabs", "ScrollableTabRow-sKfQg0A", "(ILandroidx/compose/ui/Modifier;JJFLkotlin/jvm/functions/Function3;Lkotlin/jvm/functions/Function2;Lkotlin/jvm/functions/Function2;Landroidx/compose/runtime/Composer;II)V", "TabRow", "TabRow-pAZo6Ak", "(ILandroidx/compose/ui/Modifier;JJLkotlin/jvm/functions/Function3;Lkotlin/jvm/functions/Function2;Lkotlin/jvm/functions/Function2;Landroidx/compose/runtime/Composer;II)V", "material_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class TabRowKt {
    private static final float ScrollableTabRowMinimumTabWidth = Dp.m6094constructorimpl(90);
    private static final AnimationSpec<Float> ScrollableTabRowScrollSpec = AnimationSpecKt.tween$default(250, 0, EasingKt.getFastOutSlowInEasing(), 2, null);

    /* renamed from: TabRow-pAZo6Ak, reason: not valid java name */
    public static final void m1495TabRowpAZo6Ak(final int selectedTabIndex, Modifier modifier, long backgroundColor, long contentColor, Function3<? super List<TabPosition>, ? super Composer, ? super Integer, Unit> function3, Function2<? super Composer, ? super Integer, Unit> function2, final Function2<? super Composer, ? super Integer, Unit> function22, Composer $composer, final int $changed, final int i) {
        long backgroundColor2;
        long contentColor2;
        final Function3 indicator;
        Function2 function23;
        Modifier.Companion modifier2;
        final Function2 divider;
        Modifier modifier3;
        Function2 divider2;
        long backgroundColor3;
        long contentColor3;
        Function3 indicator2;
        int i2;
        int i3;
        Composer $composer2 = $composer.startRestartGroup(-249175289);
        ComposerKt.sourceInformation($composer2, "C(TabRow)P(5,4,0:c#ui.graphics.Color,1:c#ui.graphics.Color,3)135@6677L6,136@6726L32,149@7183L1518:TabRow.kt#jmzs0o");
        int $dirty = $changed;
        if ((i & 1) != 0) {
            $dirty |= 6;
        } else if (($changed & 14) == 0) {
            $dirty |= $composer2.changed(selectedTabIndex) ? 4 : 2;
        }
        int i4 = i & 2;
        if (i4 != 0) {
            $dirty |= 48;
        } else if (($changed & 112) == 0) {
            $dirty |= $composer2.changed(modifier) ? 32 : 16;
        }
        if (($changed & 896) == 0) {
            if ((i & 4) == 0) {
                backgroundColor2 = backgroundColor;
                if ($composer2.changed(backgroundColor2)) {
                    i3 = 256;
                    $dirty |= i3;
                }
            } else {
                backgroundColor2 = backgroundColor;
            }
            i3 = 128;
            $dirty |= i3;
        } else {
            backgroundColor2 = backgroundColor;
        }
        if (($changed & 7168) == 0) {
            if ((i & 8) == 0) {
                contentColor2 = contentColor;
                if ($composer2.changed(contentColor2)) {
                    i2 = 2048;
                    $dirty |= i2;
                }
            } else {
                contentColor2 = contentColor;
            }
            i2 = 1024;
            $dirty |= i2;
        } else {
            contentColor2 = contentColor;
        }
        int i5 = i & 16;
        if (i5 != 0) {
            $dirty |= 24576;
            indicator = function3;
        } else if ((57344 & $changed) == 0) {
            indicator = function3;
            $dirty |= $composer2.changedInstance(indicator) ? 16384 : 8192;
        } else {
            indicator = function3;
        }
        int i6 = i & 32;
        if (i6 != 0) {
            $dirty |= ProfileVerifier.CompilationStatus.RESULT_CODE_ERROR_CANT_WRITE_PROFILE_VERIFICATION_RESULT_CACHE_FILE;
            function23 = function2;
        } else if ((458752 & $changed) == 0) {
            function23 = function2;
            $dirty |= $composer2.changedInstance(function23) ? 131072 : 65536;
        } else {
            function23 = function2;
        }
        if ((i & 64) != 0) {
            $dirty |= 1572864;
        } else if (($changed & 3670016) == 0) {
            $dirty |= $composer2.changedInstance(function22) ? 1048576 : 524288;
        }
        if (($dirty & 2995931) == 599186 && $composer2.getSkipping()) {
            $composer2.skipToGroupEnd();
            backgroundColor3 = backgroundColor2;
            contentColor3 = contentColor2;
            indicator2 = indicator;
            divider2 = function23;
            modifier3 = modifier;
        } else {
            $composer2.startDefaults();
            if (($changed & 1) == 0 || $composer2.getDefaultsInvalid()) {
                modifier2 = i4 != 0 ? Modifier.INSTANCE : modifier;
                if ((i & 4) != 0) {
                    $dirty &= -897;
                    backgroundColor2 = ColorsKt.getPrimarySurface(MaterialTheme.INSTANCE.getColors($composer2, 6));
                }
                if ((i & 8) != 0) {
                    long contentColor4 = ColorsKt.m1304contentColorForek8zF_U(backgroundColor2, $composer2, ($dirty >> 6) & 14);
                    $dirty &= -7169;
                    contentColor2 = contentColor4;
                }
                if (i5 != 0) {
                    indicator = ComposableLambdaKt.composableLambda($composer2, -553782708, true, new Function3<List<? extends TabPosition>, Composer, Integer, Unit>() { // from class: androidx.compose.material.TabRowKt$TabRow$1
                        /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
                        {
                            super(3);
                        }

                        @Override // kotlin.jvm.functions.Function3
                        public /* bridge */ /* synthetic */ Unit invoke(List<? extends TabPosition> list, Composer composer, Integer num) {
                            invoke((List<TabPosition>) list, composer, num.intValue());
                            return Unit.INSTANCE;
                        }

                        public final void invoke(List<TabPosition> list, Composer $composer3, int $changed2) {
                            ComposerKt.sourceInformation($composer3, "C139@6906L92:TabRow.kt#jmzs0o");
                            if (ComposerKt.isTraceInProgress()) {
                                ComposerKt.traceEventStart(-553782708, $changed2, -1, "androidx.compose.material.TabRow.<anonymous> (TabRow.kt:139)");
                            }
                            TabRowDefaults.INSTANCE.m1490Indicator9IZ8Weo(TabRowDefaults.INSTANCE.tabIndicatorOffset(Modifier.INSTANCE, list.get(selectedTabIndex)), 0.0f, 0L, $composer3, 3072, 6);
                            if (ComposerKt.isTraceInProgress()) {
                                ComposerKt.traceEventEnd();
                            }
                        }
                    });
                }
                divider = i6 != 0 ? ComposableSingletons$TabRowKt.INSTANCE.m1323getLambda1$material_release() : function23;
            } else {
                $composer2.skipToGroupEnd();
                if ((i & 4) != 0) {
                    $dirty &= -897;
                }
                if ((i & 8) != 0) {
                    $dirty &= -7169;
                    divider = function23;
                    modifier2 = modifier;
                } else {
                    modifier2 = modifier;
                    divider = function23;
                }
            }
            $composer2.endDefaults();
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventStart(-249175289, $dirty, -1, "androidx.compose.material.TabRow (TabRow.kt:148)");
            }
            SurfaceKt.m1465SurfaceFjzlyU(SelectableGroupKt.selectableGroup(modifier2), null, backgroundColor2, contentColor2, null, 0.0f, ComposableLambdaKt.composableLambda($composer2, -1961746365, true, new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material.TabRowKt$TabRow$2
                /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
                /* JADX WARN: Multi-variable type inference failed */
                {
                    super(2);
                }

                @Override // kotlin.jvm.functions.Function2
                public /* bridge */ /* synthetic */ Unit invoke(Composer composer, Integer num) {
                    invoke(composer, num.intValue());
                    return Unit.INSTANCE;
                }

                public final void invoke(Composer $composer3, int $changed2) {
                    Object value$iv;
                    ComposerKt.sourceInformation($composer3, "C154@7324L1371:TabRow.kt#jmzs0o");
                    if (($changed2 & 11) == 2 && $composer3.getSkipping()) {
                        $composer3.skipToGroupEnd();
                        return;
                    }
                    if (ComposerKt.isTraceInProgress()) {
                        ComposerKt.traceEventStart(-1961746365, $changed2, -1, "androidx.compose.material.TabRow.<anonymous> (TabRow.kt:154)");
                    }
                    Modifier fillMaxWidth$default = SizeKt.fillMaxWidth$default(Modifier.INSTANCE, 0.0f, 1, null);
                    $composer3.startReplaceableGroup(370751195);
                    boolean invalid$iv = $composer3.changedInstance(function22) | $composer3.changedInstance(divider) | $composer3.changedInstance(indicator);
                    final Function2<Composer, Integer, Unit> function24 = function22;
                    final Function2<Composer, Integer, Unit> function25 = divider;
                    final Function3<List<TabPosition>, Composer, Integer, Unit> function32 = indicator;
                    Object it$iv = $composer3.rememberedValue();
                    if (invalid$iv || it$iv == Composer.INSTANCE.getEmpty()) {
                        value$iv = new Function2<SubcomposeMeasureScope, Constraints, MeasureResult>() { // from class: androidx.compose.material.TabRowKt$TabRow$2$1$1
                            /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
                            /* JADX WARN: Multi-variable type inference failed */
                            {
                                super(2);
                            }

                            @Override // kotlin.jvm.functions.Function2
                            public /* bridge */ /* synthetic */ MeasureResult invoke(SubcomposeMeasureScope subcomposeMeasureScope, Constraints constraints) {
                                return m1497invoke0kLqBqw(subcomposeMeasureScope, constraints.getValue());
                            }

                            /* renamed from: invoke-0kLqBqw, reason: not valid java name */
                            public final MeasureResult m1497invoke0kLqBqw(final SubcomposeMeasureScope $this$SubcomposeLayout, final long constraints) {
                                Object maxElem$iv;
                                long m6040copyZbe2FdA;
                                final int tabRowWidth = Constraints.m6050getMaxWidthimpl(constraints);
                                List tabMeasurables = $this$SubcomposeLayout.subcompose(TabSlots.Tabs, function24);
                                int tabCount = tabMeasurables.size();
                                final int tabWidth = tabRowWidth / tabCount;
                                List target$iv = new ArrayList(tabMeasurables.size());
                                int index$iv$iv = 0;
                                for (int size = tabMeasurables.size(); index$iv$iv < size; size = size) {
                                    Object item$iv$iv = tabMeasurables.get(index$iv$iv);
                                    List list = target$iv;
                                    Measurable it = (Measurable) item$iv$iv;
                                    m6040copyZbe2FdA = Constraints.m6040copyZbe2FdA(constraints, (r12 & 1) != 0 ? Constraints.m6052getMinWidthimpl(constraints) : tabWidth, (r12 & 2) != 0 ? Constraints.m6050getMaxWidthimpl(constraints) : tabWidth, (r12 & 4) != 0 ? Constraints.m6051getMinHeightimpl(constraints) : 0, (r12 & 8) != 0 ? Constraints.m6049getMaxHeightimpl(constraints) : 0);
                                    list.add(it.mo5016measureBRTryo0(m6040copyZbe2FdA));
                                    index$iv$iv++;
                                }
                                final List tabPlaceables = target$iv;
                                if (tabPlaceables.isEmpty()) {
                                    maxElem$iv = null;
                                } else {
                                    maxElem$iv = tabPlaceables.get(0);
                                    Placeable it2 = (Placeable) maxElem$iv;
                                    int maxValue$iv = it2.getHeight();
                                    int i$iv = 1;
                                    int lastIndex = CollectionsKt.getLastIndex(tabPlaceables);
                                    if (1 <= lastIndex) {
                                        while (true) {
                                            Object e$iv = tabPlaceables.get(i$iv);
                                            Placeable it3 = (Placeable) e$iv;
                                            int v$iv = it3.getHeight();
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
                                final int tabRowHeight = placeable != null ? placeable.getHeight() : 0;
                                ArrayList arrayList = new ArrayList(tabCount);
                                for (int i7 = 0; i7 < tabCount; i7++) {
                                    int index = i7;
                                    float arg0$iv = $this$SubcomposeLayout.mo310toDpu2uoSUM(tabWidth);
                                    arrayList.add(new TabPosition(Dp.m6094constructorimpl(index * arg0$iv), $this$SubcomposeLayout.mo310toDpu2uoSUM(tabWidth), null));
                                }
                                final ArrayList tabPositions = arrayList;
                                final Function2<Composer, Integer, Unit> function26 = function25;
                                final Function3<List<TabPosition>, Composer, Integer, Unit> function33 = function32;
                                return MeasureScope.layout$default($this$SubcomposeLayout, tabRowWidth, tabRowHeight, null, new Function1<Placeable.PlacementScope, Unit>() { // from class: androidx.compose.material.TabRowKt$TabRow$2$1$1.1
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
                                        long m6040copyZbe2FdA2;
                                        List $this$fastForEachIndexed$iv = tabPlaceables;
                                        int i8 = tabWidth;
                                        int size2 = $this$fastForEachIndexed$iv.size();
                                        for (int index$iv = 0; index$iv < size2; index$iv++) {
                                            Object item$iv = $this$fastForEachIndexed$iv.get(index$iv);
                                            int index2 = index$iv;
                                            Placeable.PlacementScope.placeRelative$default($this$layout, (Placeable) item$iv, index2 * i8, 0, 0.0f, 4, null);
                                        }
                                        List $this$fastForEach$iv = $this$SubcomposeLayout.subcompose(TabSlots.Divider, function26);
                                        long j = constraints;
                                        int i9 = tabRowHeight;
                                        int size3 = $this$fastForEach$iv.size();
                                        int index$iv2 = 0;
                                        while (index$iv2 < size3) {
                                            Object item$iv2 = $this$fastForEach$iv.get(index$iv2);
                                            Measurable it4 = (Measurable) item$iv2;
                                            m6040copyZbe2FdA2 = Constraints.m6040copyZbe2FdA(j, (r12 & 1) != 0 ? Constraints.m6052getMinWidthimpl(j) : 0, (r12 & 2) != 0 ? Constraints.m6050getMaxWidthimpl(j) : 0, (r12 & 4) != 0 ? Constraints.m6051getMinHeightimpl(j) : 0, (r12 & 8) != 0 ? Constraints.m6049getMaxHeightimpl(j) : 0);
                                            Placeable placeable2 = it4.mo5016measureBRTryo0(m6040copyZbe2FdA2);
                                            Placeable.PlacementScope.placeRelative$default($this$layout, placeable2, 0, i9 - placeable2.getHeight(), 0.0f, 4, null);
                                            index$iv2++;
                                            $this$fastForEach$iv = $this$fastForEach$iv;
                                        }
                                        SubcomposeMeasureScope subcomposeMeasureScope = $this$SubcomposeLayout;
                                        TabSlots tabSlots = TabSlots.Indicator;
                                        final Function3<List<TabPosition>, Composer, Integer, Unit> function34 = function33;
                                        final List<TabPosition> list2 = tabPositions;
                                        List $this$fastForEach$iv2 = subcomposeMeasureScope.subcompose(tabSlots, ComposableLambdaKt.composableLambdaInstance(-641946361, true, new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material.TabRowKt.TabRow.2.1.1.1.3
                                            /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
                                            /* JADX WARN: Multi-variable type inference failed */
                                            {
                                                super(2);
                                            }

                                            @Override // kotlin.jvm.functions.Function2
                                            public /* bridge */ /* synthetic */ Unit invoke(Composer composer, Integer num) {
                                                invoke(composer, num.intValue());
                                                return Unit.INSTANCE;
                                            }

                                            public final void invoke(Composer $composer4, int $changed3) {
                                                ComposerKt.sourceInformation($composer4, "C180@8501L23:TabRow.kt#jmzs0o");
                                                if (($changed3 & 11) == 2 && $composer4.getSkipping()) {
                                                    $composer4.skipToGroupEnd();
                                                    return;
                                                }
                                                if (ComposerKt.isTraceInProgress()) {
                                                    ComposerKt.traceEventStart(-641946361, $changed3, -1, "androidx.compose.material.TabRow.<anonymous>.<anonymous>.<anonymous>.<anonymous>.<anonymous> (TabRow.kt:180)");
                                                }
                                                function34.invoke(list2, $composer4, 8);
                                                if (ComposerKt.isTraceInProgress()) {
                                                    ComposerKt.traceEventEnd();
                                                }
                                            }
                                        }));
                                        int i10 = tabRowWidth;
                                        int i11 = tabRowHeight;
                                        int size4 = $this$fastForEach$iv2.size();
                                        for (int index$iv3 = 0; index$iv3 < size4; index$iv3++) {
                                            Object item$iv3 = $this$fastForEach$iv2.get(index$iv3);
                                            Measurable it5 = (Measurable) item$iv3;
                                            Placeable.PlacementScope.placeRelative$default($this$layout, it5.mo5016measureBRTryo0(Constraints.INSTANCE.m6058fixedJhjzzOo(i10, i11)), 0, 0, 0.0f, 4, null);
                                        }
                                    }
                                }, 4, null);
                            }
                        };
                        $composer3.updateRememberedValue(value$iv);
                    } else {
                        value$iv = it$iv;
                    }
                    $composer3.endReplaceableGroup();
                    SubcomposeLayoutKt.SubcomposeLayout(fillMaxWidth$default, (Function2) value$iv, $composer3, 6, 0);
                    if (ComposerKt.isTraceInProgress()) {
                        ComposerKt.traceEventEnd();
                    }
                }
            }), $composer2, ($dirty & 896) | 1572864 | ($dirty & 7168), 50);
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventEnd();
            }
            modifier3 = modifier2;
            divider2 = divider;
            backgroundColor3 = backgroundColor2;
            contentColor3 = contentColor2;
            indicator2 = indicator;
        }
        ScopeUpdateScope endRestartGroup = $composer2.endRestartGroup();
        if (endRestartGroup != null) {
            final Modifier modifier4 = modifier3;
            final long j = backgroundColor3;
            final long j2 = contentColor3;
            final Function3 function32 = indicator2;
            final Function2 function24 = divider2;
            endRestartGroup.updateScope(new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material.TabRowKt$TabRow$3
                /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
                /* JADX WARN: Multi-variable type inference failed */
                {
                    super(2);
                }

                @Override // kotlin.jvm.functions.Function2
                public /* bridge */ /* synthetic */ Unit invoke(Composer composer, Integer num) {
                    invoke(composer, num.intValue());
                    return Unit.INSTANCE;
                }

                public final void invoke(Composer composer, int i7) {
                    TabRowKt.m1495TabRowpAZo6Ak(selectedTabIndex, modifier4, j, j2, function32, function24, function22, composer, RecomposeScopeImplKt.updateChangedFlags($changed | 1), i);
                }
            });
        }
    }

    /* renamed from: ScrollableTabRow-sKfQg0A, reason: not valid java name */
    public static final void m1494ScrollableTabRowsKfQg0A(final int selectedTabIndex, Modifier modifier, long backgroundColor, long contentColor, float edgePadding, Function3<? super List<TabPosition>, ? super Composer, ? super Integer, Unit> function3, Function2<? super Composer, ? super Integer, Unit> function2, final Function2<? super Composer, ? super Integer, Unit> function22, Composer $composer, final int $changed, final int i) {
        long backgroundColor2;
        long contentColor2;
        float edgePadding2;
        Function3 indicator;
        Modifier.Companion modifier2;
        Function2 divider;
        int $dirty;
        Function3 indicator2;
        Modifier modifier3;
        Function3 indicator3;
        Function2 divider2;
        long backgroundColor3;
        long contentColor3;
        float edgePadding3;
        int i2;
        int i3;
        Composer $composer2 = $composer.startRestartGroup(-1473476840);
        ComposerKt.sourceInformation($composer2, "C(ScrollableTabRow)P(6,5,0:c#ui.graphics.Color,1:c#ui.graphics.Color,3:c#ui.unit.Dp,4)229@11309L6,230@11358L32,244@11877L3026:TabRow.kt#jmzs0o");
        int $dirty2 = $changed;
        if ((i & 1) != 0) {
            $dirty2 |= 6;
        } else if (($changed & 14) == 0) {
            $dirty2 |= $composer2.changed(selectedTabIndex) ? 4 : 2;
        }
        int i4 = i & 2;
        if (i4 != 0) {
            $dirty2 |= 48;
        } else if (($changed & 112) == 0) {
            $dirty2 |= $composer2.changed(modifier) ? 32 : 16;
        }
        if (($changed & 896) == 0) {
            if ((i & 4) == 0) {
                backgroundColor2 = backgroundColor;
                if ($composer2.changed(backgroundColor2)) {
                    i3 = 256;
                    $dirty2 |= i3;
                }
            } else {
                backgroundColor2 = backgroundColor;
            }
            i3 = 128;
            $dirty2 |= i3;
        } else {
            backgroundColor2 = backgroundColor;
        }
        if (($changed & 7168) == 0) {
            if ((i & 8) == 0) {
                contentColor2 = contentColor;
                if ($composer2.changed(contentColor2)) {
                    i2 = 2048;
                    $dirty2 |= i2;
                }
            } else {
                contentColor2 = contentColor;
            }
            i2 = 1024;
            $dirty2 |= i2;
        } else {
            contentColor2 = contentColor;
        }
        int i5 = i & 16;
        if (i5 != 0) {
            $dirty2 |= 24576;
            edgePadding2 = edgePadding;
        } else if ((57344 & $changed) == 0) {
            edgePadding2 = edgePadding;
            $dirty2 |= $composer2.changed(edgePadding2) ? 16384 : 8192;
        } else {
            edgePadding2 = edgePadding;
        }
        int i6 = i & 32;
        if (i6 != 0) {
            $dirty2 |= ProfileVerifier.CompilationStatus.RESULT_CODE_ERROR_CANT_WRITE_PROFILE_VERIFICATION_RESULT_CACHE_FILE;
            indicator = function3;
        } else if ((458752 & $changed) == 0) {
            indicator = function3;
            $dirty2 |= $composer2.changedInstance(indicator) ? 131072 : 65536;
        } else {
            indicator = function3;
        }
        int i7 = i & 64;
        if (i7 != 0) {
            $dirty2 |= 1572864;
        } else if (($changed & 3670016) == 0) {
            $dirty2 |= $composer2.changedInstance(function2) ? 1048576 : 524288;
        }
        if ((i & 128) != 0) {
            $dirty2 |= 12582912;
        } else if ((29360128 & $changed) == 0) {
            $dirty2 |= $composer2.changedInstance(function22) ? 8388608 : 4194304;
        }
        if (($dirty2 & 23967451) == 4793490 && $composer2.getSkipping()) {
            $composer2.skipToGroupEnd();
            divider2 = function2;
            backgroundColor3 = backgroundColor2;
            contentColor3 = contentColor2;
            edgePadding3 = edgePadding2;
            indicator3 = indicator;
            modifier3 = modifier;
        } else {
            $composer2.startDefaults();
            if (($changed & 1) == 0 || $composer2.getDefaultsInvalid()) {
                modifier2 = i4 != 0 ? Modifier.INSTANCE : modifier;
                if ((i & 4) != 0) {
                    $dirty2 &= -897;
                    backgroundColor2 = ColorsKt.getPrimarySurface(MaterialTheme.INSTANCE.getColors($composer2, 6));
                }
                if ((i & 8) != 0) {
                    long contentColor4 = ColorsKt.m1304contentColorForek8zF_U(backgroundColor2, $composer2, ($dirty2 >> 6) & 14);
                    $dirty2 &= -7169;
                    contentColor2 = contentColor4;
                }
                if (i5 != 0) {
                    edgePadding2 = TabRowDefaults.INSTANCE.m1493getScrollableTabRowPaddingD9Ej5fM();
                }
                if (i6 != 0) {
                    indicator = ComposableLambdaKt.composableLambda($composer2, -655609869, true, new Function3<List<? extends TabPosition>, Composer, Integer, Unit>() { // from class: androidx.compose.material.TabRowKt$ScrollableTabRow$1
                        /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
                        {
                            super(3);
                        }

                        @Override // kotlin.jvm.functions.Function3
                        public /* bridge */ /* synthetic */ Unit invoke(List<? extends TabPosition> list, Composer composer, Integer num) {
                            invoke((List<TabPosition>) list, composer, num.intValue());
                            return Unit.INSTANCE;
                        }

                        public final void invoke(List<TabPosition> list, Composer $composer3, int $changed2) {
                            ComposerKt.sourceInformation($composer3, "C234@11600L92:TabRow.kt#jmzs0o");
                            if (ComposerKt.isTraceInProgress()) {
                                ComposerKt.traceEventStart(-655609869, $changed2, -1, "androidx.compose.material.ScrollableTabRow.<anonymous> (TabRow.kt:234)");
                            }
                            TabRowDefaults.INSTANCE.m1490Indicator9IZ8Weo(TabRowDefaults.INSTANCE.tabIndicatorOffset(Modifier.INSTANCE, list.get(selectedTabIndex)), 0.0f, 0L, $composer3, 3072, 6);
                            if (ComposerKt.isTraceInProgress()) {
                                ComposerKt.traceEventEnd();
                            }
                        }
                    });
                }
                if (i7 != 0) {
                    divider = ComposableSingletons$TabRowKt.INSTANCE.m1324getLambda2$material_release();
                    $dirty = $dirty2;
                    indicator2 = indicator;
                } else {
                    divider = function2;
                    $dirty = $dirty2;
                    indicator2 = indicator;
                }
            } else {
                $composer2.skipToGroupEnd();
                if ((i & 4) != 0) {
                    $dirty2 &= -897;
                }
                if ((i & 8) != 0) {
                    divider = function2;
                    $dirty = $dirty2 & (-7169);
                    indicator2 = indicator;
                    modifier2 = modifier;
                } else {
                    modifier2 = modifier;
                    divider = function2;
                    $dirty = $dirty2;
                    indicator2 = indicator;
                }
            }
            $composer2.endDefaults();
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventStart(-1473476840, $dirty, -1, "androidx.compose.material.ScrollableTabRow (TabRow.kt:243)");
            }
            final float f = edgePadding2;
            final Function2 function23 = divider;
            final Function3 function32 = indicator2;
            SurfaceKt.m1465SurfaceFjzlyU(modifier2, null, backgroundColor2, contentColor2, null, 0.0f, ComposableLambdaKt.composableLambda($composer2, 1455860572, true, new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material.TabRowKt$ScrollableTabRow$2
                /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
                /* JADX WARN: Multi-variable type inference failed */
                {
                    super(2);
                }

                @Override // kotlin.jvm.functions.Function2
                public /* bridge */ /* synthetic */ Unit invoke(Composer composer, Integer num) {
                    invoke(composer, num.intValue());
                    return Unit.INSTANCE;
                }

                public final void invoke(Composer $composer3, int $changed2) {
                    Object value$iv$iv$iv;
                    Object value$iv$iv;
                    ComposerKt.sourceInformation($composer3, "C249@12018L21,250@12069L24,251@12126L185,257@12320L2577:TabRow.kt#jmzs0o");
                    if (($changed2 & 11) != 2 || !$composer3.getSkipping()) {
                        if (ComposerKt.isTraceInProgress()) {
                            ComposerKt.traceEventStart(1455860572, $changed2, -1, "androidx.compose.material.ScrollableTabRow.<anonymous> (TabRow.kt:249)");
                        }
                        ScrollState scrollState = ScrollKt.rememberScrollState(0, $composer3, 0, 1);
                        $composer3.startReplaceableGroup(773894976);
                        ComposerKt.sourceInformation($composer3, "CC(rememberCoroutineScope)489@20472L144:Effects.kt#9igjgp");
                        $composer3.startReplaceableGroup(-492369756);
                        ComposerKt.sourceInformation($composer3, "CC(remember):Composables.kt#9igjgp");
                        Object it$iv$iv$iv = $composer3.rememberedValue();
                        if (it$iv$iv$iv == Composer.INSTANCE.getEmpty()) {
                            value$iv$iv$iv = new CompositionScopedCoroutineScopeCanceller(EffectsKt.createCompositionCoroutineScope(EmptyCoroutineContext.INSTANCE, $composer3));
                            $composer3.updateRememberedValue(value$iv$iv$iv);
                        } else {
                            value$iv$iv$iv = it$iv$iv$iv;
                        }
                        $composer3.endReplaceableGroup();
                        CompositionScopedCoroutineScopeCanceller wrapper$iv = (CompositionScopedCoroutineScopeCanceller) value$iv$iv$iv;
                        CoroutineScope coroutineScope = wrapper$iv.getCoroutineScope();
                        $composer3.endReplaceableGroup();
                        $composer3.startReplaceableGroup(511388516);
                        ComposerKt.sourceInformation($composer3, "CC(remember)P(1,2):Composables.kt#9igjgp");
                        boolean invalid$iv$iv = $composer3.changed(scrollState) | $composer3.changed(coroutineScope);
                        Object it$iv$iv = $composer3.rememberedValue();
                        if (invalid$iv$iv || it$iv$iv == Composer.INSTANCE.getEmpty()) {
                            value$iv$iv = new ScrollableTabData(scrollState, coroutineScope);
                            $composer3.updateRememberedValue(value$iv$iv);
                        } else {
                            value$iv$iv = it$iv$iv;
                        }
                        $composer3.endReplaceableGroup();
                        final ScrollableTabData scrollableTabData = (ScrollableTabData) value$iv$iv;
                        Modifier clipToBounds = ClipKt.clipToBounds(SelectableGroupKt.selectableGroup(ScrollKt.horizontalScroll$default(SizeKt.wrapContentSize$default(SizeKt.fillMaxWidth$default(Modifier.INSTANCE, 0.0f, 1, null), Alignment.INSTANCE.getCenterStart(), false, 2, null), scrollState, false, null, false, 14, null)));
                        final float f2 = f;
                        final Function2<Composer, Integer, Unit> function24 = function22;
                        final Function2<Composer, Integer, Unit> function25 = function23;
                        final int i8 = selectedTabIndex;
                        final Function3<List<TabPosition>, Composer, Integer, Unit> function33 = function32;
                        SubcomposeLayoutKt.SubcomposeLayout(clipToBounds, new Function2<SubcomposeMeasureScope, Constraints, MeasureResult>() { // from class: androidx.compose.material.TabRowKt$ScrollableTabRow$2.1
                            /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
                            /* JADX WARN: Multi-variable type inference failed */
                            {
                                super(2);
                            }

                            @Override // kotlin.jvm.functions.Function2
                            public /* bridge */ /* synthetic */ MeasureResult invoke(SubcomposeMeasureScope subcomposeMeasureScope, Constraints constraints) {
                                return m1496invoke0kLqBqw(subcomposeMeasureScope, constraints.getValue());
                            }

                            /* renamed from: invoke-0kLqBqw, reason: not valid java name */
                            public final MeasureResult m1496invoke0kLqBqw(final SubcomposeMeasureScope $this$SubcomposeLayout, final long constraints) {
                                float f3;
                                long tabConstraints;
                                f3 = TabRowKt.ScrollableTabRowMinimumTabWidth;
                                int minTabWidth = $this$SubcomposeLayout.mo307roundToPx0680j_4(f3);
                                final int padding = $this$SubcomposeLayout.mo307roundToPx0680j_4(f2);
                                tabConstraints = Constraints.m6040copyZbe2FdA(constraints, (r12 & 1) != 0 ? Constraints.m6052getMinWidthimpl(constraints) : minTabWidth, (r12 & 2) != 0 ? Constraints.m6050getMaxWidthimpl(constraints) : 0, (r12 & 4) != 0 ? Constraints.m6051getMinHeightimpl(constraints) : 0, (r12 & 8) != 0 ? Constraints.m6049getMaxHeightimpl(constraints) : 0);
                                List $this$fastMap$iv = $this$SubcomposeLayout.subcompose(TabSlots.Tabs, function24);
                                int $i$f$fastMap = 0;
                                List target$iv = new ArrayList($this$fastMap$iv.size());
                                int index$iv$iv = 0;
                                int size = $this$fastMap$iv.size();
                                while (index$iv$iv < size) {
                                    Object item$iv$iv = $this$fastMap$iv.get(index$iv$iv);
                                    target$iv.add(((Measurable) item$iv$iv).mo5016measureBRTryo0(tabConstraints));
                                    index$iv$iv++;
                                    $this$fastMap$iv = $this$fastMap$iv;
                                    $i$f$fastMap = $i$f$fastMap;
                                }
                                final List tabPlaceables = target$iv;
                                final Ref.IntRef layoutWidth = new Ref.IntRef();
                                layoutWidth.element = padding * 2;
                                final Ref.IntRef layoutHeight = new Ref.IntRef();
                                List $this$fastForEach$iv = tabPlaceables;
                                int $i$f$fastForEach = 0;
                                int index$iv = 0;
                                int size2 = $this$fastForEach$iv.size();
                                while (index$iv < size2) {
                                    Object item$iv = $this$fastForEach$iv.get(index$iv);
                                    Placeable it = (Placeable) item$iv;
                                    List $this$fastForEach$iv2 = $this$fastForEach$iv;
                                    layoutWidth.element += it.getWidth();
                                    int i9 = layoutHeight.element;
                                    int $i$f$fastForEach2 = $i$f$fastForEach;
                                    int $i$f$fastForEach3 = it.getHeight();
                                    layoutHeight.element = Math.max(i9, $i$f$fastForEach3);
                                    index$iv++;
                                    $this$fastForEach$iv = $this$fastForEach$iv2;
                                    $i$f$fastForEach = $i$f$fastForEach2;
                                }
                                int i10 = layoutWidth.element;
                                int i11 = layoutHeight.element;
                                final Function2<Composer, Integer, Unit> function26 = function25;
                                final ScrollableTabData scrollableTabData2 = scrollableTabData;
                                final int i12 = i8;
                                final Function3<List<TabPosition>, Composer, Integer, Unit> function34 = function33;
                                return MeasureScope.layout$default($this$SubcomposeLayout, i10, i11, null, new Function1<Placeable.PlacementScope, Unit>() { // from class: androidx.compose.material.TabRowKt.ScrollableTabRow.2.1.2
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
                                        long m6040copyZbe2FdA;
                                        final List tabPositions = new ArrayList();
                                        int left = padding;
                                        List $this$fastForEach$iv3 = tabPlaceables;
                                        SubcomposeMeasureScope subcomposeMeasureScope = $this$SubcomposeLayout;
                                        int size3 = $this$fastForEach$iv3.size();
                                        for (int index$iv2 = 0; index$iv2 < size3; index$iv2++) {
                                            Object item$iv2 = $this$fastForEach$iv3.get(index$iv2);
                                            Placeable it2 = (Placeable) item$iv2;
                                            Placeable.PlacementScope.placeRelative$default($this$layout, it2, left, 0, 0.0f, 4, null);
                                            tabPositions.add(new TabPosition(subcomposeMeasureScope.mo310toDpu2uoSUM(left), subcomposeMeasureScope.mo310toDpu2uoSUM(it2.getWidth()), null));
                                            left += it2.getWidth();
                                        }
                                        List $this$fastForEach$iv4 = $this$SubcomposeLayout.subcompose(TabSlots.Divider, function26);
                                        long j = constraints;
                                        Ref.IntRef intRef = layoutWidth;
                                        Ref.IntRef intRef2 = layoutHeight;
                                        int index$iv3 = 0;
                                        for (int size4 = $this$fastForEach$iv4.size(); index$iv3 < size4; size4 = size4) {
                                            Object item$iv3 = $this$fastForEach$iv4.get(index$iv3);
                                            Measurable it3 = (Measurable) item$iv3;
                                            m6040copyZbe2FdA = Constraints.m6040copyZbe2FdA(j, (r12 & 1) != 0 ? Constraints.m6052getMinWidthimpl(j) : intRef.element, (r12 & 2) != 0 ? Constraints.m6050getMaxWidthimpl(j) : intRef.element, (r12 & 4) != 0 ? Constraints.m6051getMinHeightimpl(j) : 0, (r12 & 8) != 0 ? Constraints.m6049getMaxHeightimpl(j) : 0);
                                            Placeable placeable = it3.mo5016measureBRTryo0(m6040copyZbe2FdA);
                                            Placeable.PlacementScope.placeRelative$default($this$layout, placeable, 0, intRef2.element - placeable.getHeight(), 0.0f, 4, null);
                                            index$iv3++;
                                        }
                                        SubcomposeMeasureScope subcomposeMeasureScope2 = $this$SubcomposeLayout;
                                        TabSlots tabSlots = TabSlots.Indicator;
                                        final Function3<List<TabPosition>, Composer, Integer, Unit> function35 = function34;
                                        List $this$fastForEach$iv5 = subcomposeMeasureScope2.subcompose(tabSlots, ComposableLambdaKt.composableLambdaInstance(-411868839, true, new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material.TabRowKt.ScrollableTabRow.2.1.2.3
                                            /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
                                            /* JADX WARN: Multi-variable type inference failed */
                                            {
                                                super(2);
                                            }

                                            @Override // kotlin.jvm.functions.Function2
                                            public /* bridge */ /* synthetic */ Unit invoke(Composer composer, Integer num) {
                                                invoke(composer, num.intValue());
                                                return Unit.INSTANCE;
                                            }

                                            public final void invoke(Composer $composer4, int $changed3) {
                                                ComposerKt.sourceInformation($composer4, "C305@14444L23:TabRow.kt#jmzs0o");
                                                if (($changed3 & 11) == 2 && $composer4.getSkipping()) {
                                                    $composer4.skipToGroupEnd();
                                                    return;
                                                }
                                                if (ComposerKt.isTraceInProgress()) {
                                                    ComposerKt.traceEventStart(-411868839, $changed3, -1, "androidx.compose.material.ScrollableTabRow.<anonymous>.<anonymous>.<anonymous>.<anonymous> (TabRow.kt:305)");
                                                }
                                                function35.invoke(tabPositions, $composer4, 8);
                                                if (ComposerKt.isTraceInProgress()) {
                                                    ComposerKt.traceEventEnd();
                                                }
                                            }
                                        }));
                                        Ref.IntRef intRef3 = layoutWidth;
                                        Ref.IntRef intRef4 = layoutHeight;
                                        int size5 = $this$fastForEach$iv5.size();
                                        for (int index$iv4 = 0; index$iv4 < size5; index$iv4++) {
                                            Object item$iv4 = $this$fastForEach$iv5.get(index$iv4);
                                            Measurable it4 = (Measurable) item$iv4;
                                            Placeable.PlacementScope.placeRelative$default($this$layout, it4.mo5016measureBRTryo0(Constraints.INSTANCE.m6058fixedJhjzzOo(intRef3.element, intRef4.element)), 0, 0, 0.0f, 4, null);
                                        }
                                        scrollableTabData2.onLaidOut($this$SubcomposeLayout, padding, tabPositions, i12);
                                    }
                                }, 4, null);
                            }
                        }, $composer3, 0, 0);
                        if (ComposerKt.isTraceInProgress()) {
                            ComposerKt.traceEventEnd();
                            return;
                        }
                        return;
                    }
                    $composer3.skipToGroupEnd();
                }
            }), $composer2, (($dirty >> 3) & 14) | 1572864 | ($dirty & 896) | ($dirty & 7168), 50);
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventEnd();
            }
            modifier3 = modifier2;
            indicator3 = indicator2;
            divider2 = divider;
            backgroundColor3 = backgroundColor2;
            contentColor3 = contentColor2;
            edgePadding3 = edgePadding2;
        }
        ScopeUpdateScope endRestartGroup = $composer2.endRestartGroup();
        if (endRestartGroup != null) {
            final Modifier modifier4 = modifier3;
            final long j = backgroundColor3;
            final long j2 = contentColor3;
            final float f2 = edgePadding3;
            final Function3 function33 = indicator3;
            final Function2 function24 = divider2;
            endRestartGroup.updateScope(new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material.TabRowKt$ScrollableTabRow$3
                /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
                /* JADX WARN: Multi-variable type inference failed */
                {
                    super(2);
                }

                @Override // kotlin.jvm.functions.Function2
                public /* bridge */ /* synthetic */ Unit invoke(Composer composer, Integer num) {
                    invoke(composer, num.intValue());
                    return Unit.INSTANCE;
                }

                public final void invoke(Composer composer, int i8) {
                    TabRowKt.m1494ScrollableTabRowsKfQg0A(selectedTabIndex, modifier4, j, j2, f2, function33, function24, function22, composer, RecomposeScopeImplKt.updateChangedFlags($changed | 1), i);
                }
            });
        }
    }
}
