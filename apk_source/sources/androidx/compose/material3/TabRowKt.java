package androidx.compose.material3;

import androidx.autofill.HintConstants;
import androidx.compose.animation.core.AnimateAsStateKt;
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
import androidx.compose.runtime.State;
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
import androidx.core.view.accessibility.AccessibilityEventCompat;
import androidx.profileinstaller.ProfileVerifier;
import java.util.ArrayList;
import java.util.List;
import kotlin.Metadata;
import kotlin.Unit;
import kotlin.comparisons.ComparisonsKt;
import kotlin.coroutines.EmptyCoroutineContext;
import kotlin.jvm.functions.Function1;
import kotlin.jvm.functions.Function2;
import kotlin.jvm.functions.Function3;
import kotlin.jvm.internal.Ref;
import kotlinx.coroutines.CoroutineScope;

/* compiled from: TabRow.kt */
@Metadata(d1 = {"\u0000b\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\u0010\u0007\n\u0000\n\u0002\u0010\u0002\n\u0000\n\u0002\u0010\b\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0018\u0002\n\u0002\u0010 \n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0004\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\b\u0014\u001a¤\u0001\u0010\u0006\u001a\u00020\u00072\u0006\u0010\b\u001a\u00020\t2\b\b\u0002\u0010\n\u001a\u00020\u000b2\b\b\u0002\u0010\f\u001a\u00020\r2\b\b\u0002\u0010\u000e\u001a\u00020\u000f2\b\b\u0002\u0010\u0010\u001a\u00020\u000f2\b\b\u0002\u0010\u0011\u001a\u00020\u00012.\b\u0002\u0010\u0012\u001a(\u0012\u0019\u0012\u0017\u0012\u0004\u0012\u00020\u00150\u0014¢\u0006\f\b\u0016\u0012\b\b\u0017\u0012\u0004\b\b(\u0018\u0012\u0004\u0012\u00020\u00070\u0013¢\u0006\u0002\b\u00192\u0013\b\u0002\u0010\u001a\u001a\r\u0012\u0004\u0012\u00020\u00070\u001b¢\u0006\u0002\b\u00192\u0011\u0010\u001c\u001a\r\u0012\u0004\u0012\u00020\u00070\u001b¢\u0006\u0002\b\u0019H\u0007ø\u0001\u0000¢\u0006\u0004\b\u001d\u0010\u001e\u001a\u0080\u0001\u0010\u001f\u001a\u00020\u00072\u0006\u0010\b\u001a\u00020\t2\b\b\u0002\u0010\n\u001a\u00020\u000b2\b\b\u0002\u0010\u000e\u001a\u00020\u000f2\b\b\u0002\u0010\u0010\u001a\u00020\u000f2\u001e\b\u0002\u0010\u0012\u001a\u0018\u0012\u0004\u0012\u00020 \u0012\u0004\u0012\u00020\u00070\u0013¢\u0006\u0002\b\u0019¢\u0006\u0002\b!2\u0013\b\u0002\u0010\u001a\u001a\r\u0012\u0004\u0012\u00020\u00070\u001b¢\u0006\u0002\b\u00192\u0011\u0010\u001c\u001a\r\u0012\u0004\u0012\u00020\u00070\u001b¢\u0006\u0002\b\u0019H\u0007ø\u0001\u0000¢\u0006\u0004\b\"\u0010#\u001a\u009a\u0001\u0010$\u001a\u00020\u00072\u0006\u0010\b\u001a\u00020\t2\b\b\u0002\u0010\n\u001a\u00020\u000b2\b\b\u0002\u0010\u000e\u001a\u00020\u000f2\b\b\u0002\u0010\u0010\u001a\u00020\u000f2\b\b\u0002\u0010\u0011\u001a\u00020\u00012.\b\u0002\u0010\u0012\u001a(\u0012\u0019\u0012\u0017\u0012\u0004\u0012\u00020\u00150\u0014¢\u0006\f\b\u0016\u0012\b\b\u0017\u0012\u0004\b\b(\u0018\u0012\u0004\u0012\u00020\u00070\u0013¢\u0006\u0002\b\u00192\u0013\b\u0002\u0010\u001a\u001a\r\u0012\u0004\u0012\u00020\u00070\u001b¢\u0006\u0002\b\u00192\u0011\u0010\u001c\u001a\r\u0012\u0004\u0012\u00020\u00070\u001b¢\u0006\u0002\b\u0019H\u0007ø\u0001\u0000¢\u0006\u0004\b%\u0010&\u001a \u0001\u0010'\u001a\u00020\u00072\u0006\u0010\b\u001a\u00020\t2,\u0010\u0012\u001a(\u0012\u0019\u0012\u0017\u0012\u0004\u0012\u00020\u00150\u0014¢\u0006\f\b\u0016\u0012\b\b\u0017\u0012\u0004\b\b(\u0018\u0012\u0004\u0012\u00020\u00070\u0013¢\u0006\u0002\b\u00192\b\b\u0002\u0010\n\u001a\u00020\u000b2\b\b\u0002\u0010\u000e\u001a\u00020\u000f2\b\b\u0002\u0010\u0010\u001a\u00020\u000f2\b\b\u0002\u0010\u0011\u001a\u00020\u00012\u0013\b\u0002\u0010\u001a\u001a\r\u0012\u0004\u0012\u00020\u00070\u001b¢\u0006\u0002\b\u00192\u0011\u0010\u001c\u001a\r\u0012\u0004\u0012\u00020\u00070\u001b¢\u0006\u0002\b\u00192\u0006\u0010\f\u001a\u00020\rH\u0003ø\u0001\u0000¢\u0006\u0004\b(\u0010)\u001a¤\u0001\u0010*\u001a\u00020\u00072\u0006\u0010\b\u001a\u00020\t2\b\b\u0002\u0010\n\u001a\u00020\u000b2\b\b\u0002\u0010\f\u001a\u00020\r2\b\b\u0002\u0010\u000e\u001a\u00020\u000f2\b\b\u0002\u0010\u0010\u001a\u00020\u000f2\b\b\u0002\u0010\u0011\u001a\u00020\u00012.\b\u0002\u0010\u0012\u001a(\u0012\u0019\u0012\u0017\u0012\u0004\u0012\u00020\u00150\u0014¢\u0006\f\b\u0016\u0012\b\b\u0017\u0012\u0004\b\b(\u0018\u0012\u0004\u0012\u00020\u00070\u0013¢\u0006\u0002\b\u00192\u0013\b\u0002\u0010\u001a\u001a\r\u0012\u0004\u0012\u00020\u00070\u001b¢\u0006\u0002\b\u00192\u0011\u0010\u001c\u001a\r\u0012\u0004\u0012\u00020\u00070\u001b¢\u0006\u0002\b\u0019H\u0007ø\u0001\u0000¢\u0006\u0004\b+\u0010\u001e\u001a\u0080\u0001\u0010,\u001a\u00020\u00072\u0006\u0010\b\u001a\u00020\t2\b\b\u0002\u0010\n\u001a\u00020\u000b2\b\b\u0002\u0010\u000e\u001a\u00020\u000f2\b\b\u0002\u0010\u0010\u001a\u00020\u000f2\u001e\b\u0002\u0010\u0012\u001a\u0018\u0012\u0004\u0012\u00020 \u0012\u0004\u0012\u00020\u00070\u0013¢\u0006\u0002\b\u0019¢\u0006\u0002\b!2\u0013\b\u0002\u0010\u001a\u001a\r\u0012\u0004\u0012\u00020\u00070\u001b¢\u0006\u0002\b\u00192\u0011\u0010\u001c\u001a\r\u0012\u0004\u0012\u00020\u00070\u001b¢\u0006\u0002\b\u0019H\u0007ø\u0001\u0000¢\u0006\u0004\b-\u0010#\u001a\u0090\u0001\u0010.\u001a\u00020\u00072\u0006\u0010\b\u001a\u00020\t2\b\b\u0002\u0010\n\u001a\u00020\u000b2\b\b\u0002\u0010\u000e\u001a\u00020\u000f2\b\b\u0002\u0010\u0010\u001a\u00020\u000f2.\b\u0002\u0010\u0012\u001a(\u0012\u0019\u0012\u0017\u0012\u0004\u0012\u00020\u00150\u0014¢\u0006\f\b\u0016\u0012\b\b\u0017\u0012\u0004\b\b(\u0018\u0012\u0004\u0012\u00020\u00070\u0013¢\u0006\u0002\b\u00192\u0013\b\u0002\u0010\u001a\u001a\r\u0012\u0004\u0012\u00020\u00070\u001b¢\u0006\u0002\b\u00192\u0011\u0010\u001c\u001a\r\u0012\u0004\u0012\u00020\u00070\u001b¢\u0006\u0002\b\u0019H\u0007ø\u0001\u0000¢\u0006\u0004\b/\u0010#\u001an\u00100\u001a\u00020\u00072\u0006\u0010\n\u001a\u00020\u000b2\u0006\u0010\u000e\u001a\u00020\u000f2\u0006\u0010\u0010\u001a\u00020\u000f2\u001c\u0010\u0012\u001a\u0018\u0012\u0004\u0012\u00020 \u0012\u0004\u0012\u00020\u00070\u0013¢\u0006\u0002\b\u0019¢\u0006\u0002\b!2\u0011\u0010\u001a\u001a\r\u0012\u0004\u0012\u00020\u00070\u001b¢\u0006\u0002\b\u00192\u0011\u0010\u001c\u001a\r\u0012\u0004\u0012\u00020\u00070\u001b¢\u0006\u0002\b\u0019H\u0003ø\u0001\u0000¢\u0006\u0004\b1\u00102\u001a~\u00103\u001a\u00020\u00072\u0006\u0010\n\u001a\u00020\u000b2\u0006\u0010\u000e\u001a\u00020\u000f2\u0006\u0010\u0010\u001a\u00020\u000f2,\u0010\u0012\u001a(\u0012\u0019\u0012\u0017\u0012\u0004\u0012\u00020\u00150\u0014¢\u0006\f\b\u0016\u0012\b\b\u0017\u0012\u0004\b\b(\u0018\u0012\u0004\u0012\u00020\u00070\u0013¢\u0006\u0002\b\u00192\u0011\u0010\u001a\u001a\r\u0012\u0004\u0012\u00020\u00070\u001b¢\u0006\u0002\b\u00192\u0011\u0010\u001c\u001a\r\u0012\u0004\u0012\u00020\u00070\u001b¢\u0006\u0002\b\u0019H\u0003ø\u0001\u0000¢\u0006\u0004\b4\u00102\"\u0010\u0010\u0000\u001a\u00020\u0001X\u0082\u0004¢\u0006\u0004\n\u0002\u0010\u0002\"\u0014\u0010\u0003\u001a\b\u0012\u0004\u0012\u00020\u00050\u0004X\u0082\u0004¢\u0006\u0002\n\u0000\u0082\u0002\u0007\n\u0005\b¡\u001e0\u0001¨\u00065"}, d2 = {"ScrollableTabRowMinimumTabWidth", "Landroidx/compose/ui/unit/Dp;", "F", "ScrollableTabRowScrollSpec", "Landroidx/compose/animation/core/AnimationSpec;", "", "PrimaryScrollableTabRow", "", "selectedTabIndex", "", "modifier", "Landroidx/compose/ui/Modifier;", "scrollState", "Landroidx/compose/foundation/ScrollState;", "containerColor", "Landroidx/compose/ui/graphics/Color;", "contentColor", "edgePadding", "indicator", "Lkotlin/Function1;", "", "Landroidx/compose/material3/TabPosition;", "Lkotlin/ParameterName;", HintConstants.AUTOFILL_HINT_NAME, "tabPositions", "Landroidx/compose/runtime/Composable;", "divider", "Lkotlin/Function0;", "tabs", "PrimaryScrollableTabRow-qhFBPw4", "(ILandroidx/compose/ui/Modifier;Landroidx/compose/foundation/ScrollState;JJFLkotlin/jvm/functions/Function3;Lkotlin/jvm/functions/Function2;Lkotlin/jvm/functions/Function2;Landroidx/compose/runtime/Composer;II)V", "PrimaryTabRow", "Landroidx/compose/material3/TabIndicatorScope;", "Lkotlin/ExtensionFunctionType;", "PrimaryTabRow-pAZo6Ak", "(ILandroidx/compose/ui/Modifier;JJLkotlin/jvm/functions/Function3;Lkotlin/jvm/functions/Function2;Lkotlin/jvm/functions/Function2;Landroidx/compose/runtime/Composer;II)V", "ScrollableTabRow", "ScrollableTabRow-sKfQg0A", "(ILandroidx/compose/ui/Modifier;JJFLkotlin/jvm/functions/Function3;Lkotlin/jvm/functions/Function2;Lkotlin/jvm/functions/Function2;Landroidx/compose/runtime/Composer;II)V", "ScrollableTabRowImp", "ScrollableTabRowImp-qhFBPw4", "(ILkotlin/jvm/functions/Function3;Landroidx/compose/ui/Modifier;JJFLkotlin/jvm/functions/Function2;Lkotlin/jvm/functions/Function2;Landroidx/compose/foundation/ScrollState;Landroidx/compose/runtime/Composer;II)V", "SecondaryScrollableTabRow", "SecondaryScrollableTabRow-qhFBPw4", "SecondaryTabRow", "SecondaryTabRow-pAZo6Ak", "TabRow", "TabRow-pAZo6Ak", "TabRowImpl", "TabRowImpl-DTcfvLk", "(Landroidx/compose/ui/Modifier;JJLkotlin/jvm/functions/Function3;Lkotlin/jvm/functions/Function2;Lkotlin/jvm/functions/Function2;Landroidx/compose/runtime/Composer;I)V", "TabRowWithSubcomposeImpl", "TabRowWithSubcomposeImpl-DTcfvLk", "material3_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class TabRowKt {
    private static final float ScrollableTabRowMinimumTabWidth = Dp.m6094constructorimpl(90);
    private static final AnimationSpec<Float> ScrollableTabRowScrollSpec = AnimationSpecKt.tween$default(250, 0, EasingKt.getFastOutSlowInEasing(), 2, null);

    /* renamed from: PrimaryTabRow-pAZo6Ak, reason: not valid java name */
    public static final void m2366PrimaryTabRowpAZo6Ak(final int selectedTabIndex, Modifier modifier, long containerColor, long contentColor, Function3<? super TabIndicatorScope, ? super Composer, ? super Integer, Unit> function3, Function2<? super Composer, ? super Integer, Unit> function2, final Function2<? super Composer, ? super Integer, Unit> function22, Composer $composer, final int $changed, final int i) {
        long containerColor2;
        long contentColor2;
        Function3 indicator;
        Function2 function23;
        Modifier.Companion modifier2;
        int $dirty;
        long containerColor3;
        long contentColor3;
        Function2 divider;
        Function3 indicator2;
        Function3 indicator3;
        Function2 divider2;
        Modifier modifier3;
        int i2;
        int i3;
        Composer $composer2 = $composer.startRestartGroup(-1884787284);
        ComposerKt.sourceInformation($composer2, "C(PrimaryTabRow)P(5,4,0:c#ui.graphics.Color,1:c#ui.graphics.Color,3)150@7456L21,151@7520L19,166@7964L76:TabRow.kt#uh7d8r");
        int $dirty2 = $changed;
        if ((i & 1) != 0) {
            $dirty2 |= 6;
        } else if (($changed & 6) == 0) {
            $dirty2 |= $composer2.changed(selectedTabIndex) ? 4 : 2;
        }
        int i4 = i & 2;
        if (i4 != 0) {
            $dirty2 |= 48;
        } else if (($changed & 48) == 0) {
            $dirty2 |= $composer2.changed(modifier) ? 32 : 16;
        }
        if (($changed & 384) == 0) {
            if ((i & 4) == 0) {
                containerColor2 = containerColor;
                if ($composer2.changed(containerColor2)) {
                    i3 = 256;
                    $dirty2 |= i3;
                }
            } else {
                containerColor2 = containerColor;
            }
            i3 = 128;
            $dirty2 |= i3;
        } else {
            containerColor2 = containerColor;
        }
        if (($changed & 3072) == 0) {
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
            indicator = function3;
        } else if (($changed & 24576) == 0) {
            indicator = function3;
            $dirty2 |= $composer2.changedInstance(indicator) ? 16384 : 8192;
        } else {
            indicator = function3;
        }
        int i6 = i & 32;
        if (i6 != 0) {
            $dirty2 |= ProfileVerifier.CompilationStatus.RESULT_CODE_ERROR_CANT_WRITE_PROFILE_VERIFICATION_RESULT_CACHE_FILE;
            function23 = function2;
        } else if ((196608 & $changed) == 0) {
            function23 = function2;
            $dirty2 |= $composer2.changedInstance(function23) ? 131072 : 65536;
        } else {
            function23 = function2;
        }
        if ((i & 64) != 0) {
            $dirty2 |= 1572864;
        } else if (($changed & 1572864) == 0) {
            $dirty2 |= $composer2.changedInstance(function22) ? 1048576 : 524288;
        }
        if (($dirty2 & 599187) == 599186 && $composer2.getSkipping()) {
            $composer2.skipToGroupEnd();
            modifier3 = modifier;
            containerColor3 = containerColor2;
            contentColor3 = contentColor2;
            indicator3 = indicator;
            divider2 = function23;
        } else {
            $composer2.startDefaults();
            if (($changed & 1) == 0 || $composer2.getDefaultsInvalid()) {
                modifier2 = i4 != 0 ? Modifier.INSTANCE : modifier;
                if ((i & 4) != 0) {
                    containerColor2 = TabRowDefaults.INSTANCE.getPrimaryContainerColor($composer2, 6);
                    $dirty2 &= -897;
                }
                if ((i & 8) != 0) {
                    $dirty2 &= -7169;
                    contentColor2 = TabRowDefaults.INSTANCE.getPrimaryContentColor($composer2, 6);
                }
                if (i5 != 0) {
                    indicator = ComposableLambdaKt.composableLambda($composer2, -2021049253, true, new Function3<TabIndicatorScope, Composer, Integer, Unit>() { // from class: androidx.compose.material3.TabRowKt$PrimaryTabRow$1
                        /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
                        {
                            super(3);
                        }

                        @Override // kotlin.jvm.functions.Function3
                        public /* bridge */ /* synthetic */ Unit invoke(TabIndicatorScope tabIndicatorScope, Composer composer, Integer num) {
                            invoke(tabIndicatorScope, composer, num.intValue());
                            return Unit.INSTANCE;
                        }

                        public final void invoke(TabIndicatorScope $this$null, Composer $composer3, int $changed2) {
                            ComposerKt.sourceInformation($composer3, "C153@7624L204:TabRow.kt#uh7d8r");
                            int $dirty3 = $changed2;
                            if (($changed2 & 6) == 0) {
                                $dirty3 |= ($changed2 & 8) == 0 ? $composer3.changed($this$null) : $composer3.changedInstance($this$null) ? 4 : 2;
                            }
                            int $dirty4 = $dirty3;
                            if (($dirty4 & 19) != 18 || !$composer3.getSkipping()) {
                                if (ComposerKt.isTraceInProgress()) {
                                    ComposerKt.traceEventStart(-2021049253, $dirty4, -1, "androidx.compose.material3.PrimaryTabRow.<anonymous> (TabRow.kt:153)");
                                }
                                TabRowDefaults.INSTANCE.m2362PrimaryIndicator10LGxhE($this$null.tabIndicatorOffset(Modifier.INSTANCE, selectedTabIndex, true), Dp.INSTANCE.m6114getUnspecifiedD9Ej5fM(), 0.0f, 0L, null, $composer3, 196656, 28);
                                if (ComposerKt.isTraceInProgress()) {
                                    ComposerKt.traceEventEnd();
                                    return;
                                }
                                return;
                            }
                            $composer3.skipToGroupEnd();
                        }
                    });
                }
                if (i6 != 0) {
                    $dirty = $dirty2;
                    divider = ComposableSingletons$TabRowKt.INSTANCE.m1775getLambda1$material3_release();
                    containerColor3 = containerColor2;
                    contentColor3 = contentColor2;
                    indicator2 = indicator;
                } else {
                    $dirty = $dirty2;
                    containerColor3 = containerColor2;
                    contentColor3 = contentColor2;
                    divider = function23;
                    indicator2 = indicator;
                }
            } else {
                $composer2.skipToGroupEnd();
                if ((i & 4) != 0) {
                    $dirty2 &= -897;
                }
                if ((i & 8) != 0) {
                    $dirty = $dirty2 & (-7169);
                    containerColor3 = containerColor2;
                    contentColor3 = contentColor2;
                    divider = function23;
                    modifier2 = modifier;
                    indicator2 = indicator;
                } else {
                    modifier2 = modifier;
                    $dirty = $dirty2;
                    containerColor3 = containerColor2;
                    contentColor3 = contentColor2;
                    divider = function23;
                    indicator2 = indicator;
                }
            }
            $composer2.endDefaults();
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventStart(-1884787284, $dirty, -1, "androidx.compose.material3.PrimaryTabRow (TabRow.kt:165)");
            }
            m2372TabRowImplDTcfvLk(modifier2, containerColor3, contentColor3, indicator2, divider, function22, $composer2, (($dirty >> 3) & 14) | (($dirty >> 3) & 112) | (($dirty >> 3) & 896) | (($dirty >> 3) & 7168) | (($dirty >> 3) & 57344) | (458752 & ($dirty >> 3)));
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventEnd();
            }
            indicator3 = indicator2;
            divider2 = divider;
            modifier3 = modifier2;
        }
        ScopeUpdateScope endRestartGroup = $composer2.endRestartGroup();
        if (endRestartGroup != null) {
            final Modifier modifier4 = modifier3;
            final long j = containerColor3;
            final long j2 = contentColor3;
            final Function3 function32 = indicator3;
            final Function2 function24 = divider2;
            endRestartGroup.updateScope(new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.TabRowKt$PrimaryTabRow$2
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
                    TabRowKt.m2366PrimaryTabRowpAZo6Ak(selectedTabIndex, modifier4, j, j2, function32, function24, function22, composer, RecomposeScopeImplKt.updateChangedFlags($changed | 1), i);
                }
            });
        }
    }

    /* renamed from: SecondaryTabRow-pAZo6Ak, reason: not valid java name */
    public static final void m2370SecondaryTabRowpAZo6Ak(final int selectedTabIndex, Modifier modifier, long containerColor, long contentColor, Function3<? super TabIndicatorScope, ? super Composer, ? super Integer, Unit> function3, Function2<? super Composer, ? super Integer, Unit> function2, final Function2<? super Composer, ? super Integer, Unit> function22, Composer $composer, final int $changed, final int i) {
        long containerColor2;
        long contentColor2;
        Function3 indicator;
        Function2 function23;
        Modifier.Companion modifier2;
        int $dirty;
        long containerColor3;
        long contentColor3;
        Function2 divider;
        Function3 indicator2;
        Function3 indicator3;
        Function2 divider2;
        Modifier modifier3;
        int i2;
        int i3;
        Composer $composer2 = $composer.startRestartGroup(-1909540706);
        ComposerKt.sourceInformation($composer2, "C(SecondaryTabRow)P(5,4,0:c#ui.graphics.Color,1:c#ui.graphics.Color,3)207@10434L23,208@10500L21,219@10867L76:TabRow.kt#uh7d8r");
        int $dirty2 = $changed;
        if ((i & 1) != 0) {
            $dirty2 |= 6;
        } else if (($changed & 6) == 0) {
            $dirty2 |= $composer2.changed(selectedTabIndex) ? 4 : 2;
        }
        int i4 = i & 2;
        if (i4 != 0) {
            $dirty2 |= 48;
        } else if (($changed & 48) == 0) {
            $dirty2 |= $composer2.changed(modifier) ? 32 : 16;
        }
        if (($changed & 384) == 0) {
            if ((i & 4) == 0) {
                containerColor2 = containerColor;
                if ($composer2.changed(containerColor2)) {
                    i3 = 256;
                    $dirty2 |= i3;
                }
            } else {
                containerColor2 = containerColor;
            }
            i3 = 128;
            $dirty2 |= i3;
        } else {
            containerColor2 = containerColor;
        }
        if (($changed & 3072) == 0) {
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
            indicator = function3;
        } else if (($changed & 24576) == 0) {
            indicator = function3;
            $dirty2 |= $composer2.changedInstance(indicator) ? 16384 : 8192;
        } else {
            indicator = function3;
        }
        int i6 = i & 32;
        if (i6 != 0) {
            $dirty2 |= ProfileVerifier.CompilationStatus.RESULT_CODE_ERROR_CANT_WRITE_PROFILE_VERIFICATION_RESULT_CACHE_FILE;
            function23 = function2;
        } else if ((196608 & $changed) == 0) {
            function23 = function2;
            $dirty2 |= $composer2.changedInstance(function23) ? 131072 : 65536;
        } else {
            function23 = function2;
        }
        if ((i & 64) != 0) {
            $dirty2 |= 1572864;
        } else if (($changed & 1572864) == 0) {
            $dirty2 |= $composer2.changedInstance(function22) ? 1048576 : 524288;
        }
        if (($dirty2 & 599187) == 599186 && $composer2.getSkipping()) {
            $composer2.skipToGroupEnd();
            modifier3 = modifier;
            containerColor3 = containerColor2;
            contentColor3 = contentColor2;
            indicator3 = indicator;
            divider2 = function23;
        } else {
            $composer2.startDefaults();
            if (($changed & 1) == 0 || $composer2.getDefaultsInvalid()) {
                modifier2 = i4 != 0 ? Modifier.INSTANCE : modifier;
                if ((i & 4) != 0) {
                    containerColor2 = TabRowDefaults.INSTANCE.getSecondaryContainerColor($composer2, 6);
                    $dirty2 &= -897;
                }
                if ((i & 8) != 0) {
                    $dirty2 &= -7169;
                    contentColor2 = TabRowDefaults.INSTANCE.getSecondaryContentColor($composer2, 6);
                }
                if (i5 != 0) {
                    indicator = ComposableLambdaKt.composableLambda($composer2, 286693261, true, new Function3<TabIndicatorScope, Composer, Integer, Unit>() { // from class: androidx.compose.material3.TabRowKt$SecondaryTabRow$1
                        /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
                        {
                            super(3);
                        }

                        @Override // kotlin.jvm.functions.Function3
                        public /* bridge */ /* synthetic */ Unit invoke(TabIndicatorScope tabIndicatorScope, Composer composer, Integer num) {
                            invoke(tabIndicatorScope, composer, num.intValue());
                            return Unit.INSTANCE;
                        }

                        public final void invoke(TabIndicatorScope $this$null, Composer $composer3, int $changed2) {
                            ComposerKt.sourceInformation($composer3, "C210@10618L113:TabRow.kt#uh7d8r");
                            int $dirty3 = $changed2;
                            if (($changed2 & 6) == 0) {
                                $dirty3 |= ($changed2 & 8) == 0 ? $composer3.changed($this$null) : $composer3.changedInstance($this$null) ? 4 : 2;
                            }
                            if (($dirty3 & 19) != 18 || !$composer3.getSkipping()) {
                                if (ComposerKt.isTraceInProgress()) {
                                    ComposerKt.traceEventStart(286693261, $dirty3, -1, "androidx.compose.material3.SecondaryTabRow.<anonymous> (TabRow.kt:210)");
                                }
                                TabRowDefaults.INSTANCE.m2363SecondaryIndicator9IZ8Weo($this$null.tabIndicatorOffset(Modifier.INSTANCE, selectedTabIndex, false), 0.0f, 0L, $composer3, 3072, 6);
                                if (ComposerKt.isTraceInProgress()) {
                                    ComposerKt.traceEventEnd();
                                    return;
                                }
                                return;
                            }
                            $composer3.skipToGroupEnd();
                        }
                    });
                }
                if (i6 != 0) {
                    $dirty = $dirty2;
                    divider = ComposableSingletons$TabRowKt.INSTANCE.m1776getLambda2$material3_release();
                    containerColor3 = containerColor2;
                    contentColor3 = contentColor2;
                    indicator2 = indicator;
                } else {
                    $dirty = $dirty2;
                    containerColor3 = containerColor2;
                    contentColor3 = contentColor2;
                    divider = function23;
                    indicator2 = indicator;
                }
            } else {
                $composer2.skipToGroupEnd();
                if ((i & 4) != 0) {
                    $dirty2 &= -897;
                }
                if ((i & 8) != 0) {
                    $dirty = $dirty2 & (-7169);
                    containerColor3 = containerColor2;
                    contentColor3 = contentColor2;
                    divider = function23;
                    modifier2 = modifier;
                    indicator2 = indicator;
                } else {
                    modifier2 = modifier;
                    $dirty = $dirty2;
                    containerColor3 = containerColor2;
                    contentColor3 = contentColor2;
                    divider = function23;
                    indicator2 = indicator;
                }
            }
            $composer2.endDefaults();
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventStart(-1909540706, $dirty, -1, "androidx.compose.material3.SecondaryTabRow (TabRow.kt:218)");
            }
            m2372TabRowImplDTcfvLk(modifier2, containerColor3, contentColor3, indicator2, divider, function22, $composer2, (($dirty >> 3) & 14) | (($dirty >> 3) & 112) | (($dirty >> 3) & 896) | (($dirty >> 3) & 7168) | (($dirty >> 3) & 57344) | (458752 & ($dirty >> 3)));
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventEnd();
            }
            indicator3 = indicator2;
            divider2 = divider;
            modifier3 = modifier2;
        }
        ScopeUpdateScope endRestartGroup = $composer2.endRestartGroup();
        if (endRestartGroup != null) {
            final Modifier modifier4 = modifier3;
            final long j = containerColor3;
            final long j2 = contentColor3;
            final Function3 function32 = indicator3;
            final Function2 function24 = divider2;
            endRestartGroup.updateScope(new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.TabRowKt$SecondaryTabRow$2
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
                    TabRowKt.m2370SecondaryTabRowpAZo6Ak(selectedTabIndex, modifier4, j, j2, function32, function24, function22, composer, RecomposeScopeImplKt.updateChangedFlags($changed | 1), i);
                }
            });
        }
    }

    /* renamed from: TabRow-pAZo6Ak, reason: not valid java name */
    public static final void m2371TabRowpAZo6Ak(final int selectedTabIndex, Modifier modifier, long containerColor, long contentColor, Function3<? super List<TabPosition>, ? super Composer, ? super Integer, Unit> function3, Function2<? super Composer, ? super Integer, Unit> function2, final Function2<? super Composer, ? super Integer, Unit> function22, Composer $composer, final int $changed, final int i) {
        long containerColor2;
        long contentColor2;
        Function3 indicator;
        Function2 function23;
        Modifier.Companion modifier2;
        int $dirty;
        long containerColor3;
        long contentColor3;
        Function2 divider;
        Function3 indicator2;
        Function3 indicator3;
        Function2 divider2;
        Modifier modifier3;
        int i2;
        int i3;
        Composer $composer2 = $composer.startRestartGroup(-1199178586);
        ComposerKt.sourceInformation($composer2, "C(TabRow)P(5,4,0:c#ui.graphics.Color,1:c#ui.graphics.Color,3)299@15165L21,300@15229L19,313@15685L90:TabRow.kt#uh7d8r");
        int $dirty2 = $changed;
        if ((i & 1) != 0) {
            $dirty2 |= 6;
        } else if (($changed & 6) == 0) {
            $dirty2 |= $composer2.changed(selectedTabIndex) ? 4 : 2;
        }
        int i4 = i & 2;
        if (i4 != 0) {
            $dirty2 |= 48;
        } else if (($changed & 48) == 0) {
            $dirty2 |= $composer2.changed(modifier) ? 32 : 16;
        }
        if (($changed & 384) == 0) {
            if ((i & 4) == 0) {
                containerColor2 = containerColor;
                if ($composer2.changed(containerColor2)) {
                    i3 = 256;
                    $dirty2 |= i3;
                }
            } else {
                containerColor2 = containerColor;
            }
            i3 = 128;
            $dirty2 |= i3;
        } else {
            containerColor2 = containerColor;
        }
        if (($changed & 3072) == 0) {
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
            indicator = function3;
        } else if (($changed & 24576) == 0) {
            indicator = function3;
            $dirty2 |= $composer2.changedInstance(indicator) ? 16384 : 8192;
        } else {
            indicator = function3;
        }
        int i6 = i & 32;
        if (i6 != 0) {
            $dirty2 |= ProfileVerifier.CompilationStatus.RESULT_CODE_ERROR_CANT_WRITE_PROFILE_VERIFICATION_RESULT_CACHE_FILE;
            function23 = function2;
        } else if ((196608 & $changed) == 0) {
            function23 = function2;
            $dirty2 |= $composer2.changedInstance(function23) ? 131072 : 65536;
        } else {
            function23 = function2;
        }
        if ((i & 64) != 0) {
            $dirty2 |= 1572864;
        } else if (($changed & 1572864) == 0) {
            $dirty2 |= $composer2.changedInstance(function22) ? 1048576 : 524288;
        }
        if (($dirty2 & 599187) == 599186 && $composer2.getSkipping()) {
            $composer2.skipToGroupEnd();
            modifier3 = modifier;
            containerColor3 = containerColor2;
            contentColor3 = contentColor2;
            indicator3 = indicator;
            divider2 = function23;
        } else {
            $composer2.startDefaults();
            if (($changed & 1) == 0 || $composer2.getDefaultsInvalid()) {
                modifier2 = i4 != 0 ? Modifier.INSTANCE : modifier;
                if ((i & 4) != 0) {
                    containerColor2 = TabRowDefaults.INSTANCE.getPrimaryContainerColor($composer2, 6);
                    $dirty2 &= -897;
                }
                if ((i & 8) != 0) {
                    $dirty2 &= -7169;
                    contentColor2 = TabRowDefaults.INSTANCE.getPrimaryContentColor($composer2, 6);
                }
                if (i5 != 0) {
                    indicator = ComposableLambdaKt.composableLambda($composer2, -2052073983, true, new Function3<List<? extends TabPosition>, Composer, Integer, Unit>() { // from class: androidx.compose.material3.TabRowKt$TabRow$1
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
                            ComposerKt.sourceInformation($composer3, "C303@15430L109:TabRow.kt#uh7d8r");
                            if (ComposerKt.isTraceInProgress()) {
                                ComposerKt.traceEventStart(-2052073983, $changed2, -1, "androidx.compose.material3.TabRow.<anonymous> (TabRow.kt:302)");
                            }
                            if (selectedTabIndex < list.size()) {
                                TabRowDefaults.INSTANCE.m2363SecondaryIndicator9IZ8Weo(TabRowDefaults.INSTANCE.tabIndicatorOffset(Modifier.INSTANCE, list.get(selectedTabIndex)), 0.0f, 0L, $composer3, 3072, 6);
                            }
                            if (ComposerKt.isTraceInProgress()) {
                                ComposerKt.traceEventEnd();
                            }
                        }
                    });
                }
                if (i6 != 0) {
                    $dirty = $dirty2;
                    divider = ComposableSingletons$TabRowKt.INSTANCE.m1777getLambda3$material3_release();
                    containerColor3 = containerColor2;
                    contentColor3 = contentColor2;
                    indicator2 = indicator;
                } else {
                    $dirty = $dirty2;
                    containerColor3 = containerColor2;
                    contentColor3 = contentColor2;
                    divider = function23;
                    indicator2 = indicator;
                }
            } else {
                $composer2.skipToGroupEnd();
                if ((i & 4) != 0) {
                    $dirty2 &= -897;
                }
                if ((i & 8) != 0) {
                    $dirty = $dirty2 & (-7169);
                    containerColor3 = containerColor2;
                    contentColor3 = contentColor2;
                    divider = function23;
                    modifier2 = modifier;
                    indicator2 = indicator;
                } else {
                    modifier2 = modifier;
                    $dirty = $dirty2;
                    containerColor3 = containerColor2;
                    contentColor3 = contentColor2;
                    divider = function23;
                    indicator2 = indicator;
                }
            }
            $composer2.endDefaults();
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventStart(-1199178586, $dirty, -1, "androidx.compose.material3.TabRow (TabRow.kt:312)");
            }
            m2373TabRowWithSubcomposeImplDTcfvLk(modifier2, containerColor3, contentColor3, indicator2, divider, function22, $composer2, (($dirty >> 3) & 14) | (($dirty >> 3) & 112) | (($dirty >> 3) & 896) | (($dirty >> 3) & 7168) | (($dirty >> 3) & 57344) | (458752 & ($dirty >> 3)));
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventEnd();
            }
            indicator3 = indicator2;
            divider2 = divider;
            modifier3 = modifier2;
        }
        ScopeUpdateScope endRestartGroup = $composer2.endRestartGroup();
        if (endRestartGroup != null) {
            final Modifier modifier4 = modifier3;
            final long j = containerColor3;
            final long j2 = contentColor3;
            final Function3 function32 = indicator3;
            final Function2 function24 = divider2;
            endRestartGroup.updateScope(new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.TabRowKt$TabRow$2
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
                    TabRowKt.m2371TabRowpAZo6Ak(selectedTabIndex, modifier4, j, j2, function32, function24, function22, composer, RecomposeScopeImplKt.updateChangedFlags($changed | 1), i);
                }
            });
        }
    }

    /* JADX INFO: Access modifiers changed from: private */
    /* renamed from: TabRowImpl-DTcfvLk, reason: not valid java name */
    public static final void m2372TabRowImplDTcfvLk(final Modifier modifier, final long containerColor, final long contentColor, final Function3<? super TabIndicatorScope, ? super Composer, ? super Integer, Unit> function3, final Function2<? super Composer, ? super Integer, Unit> function2, final Function2<? super Composer, ? super Integer, Unit> function22, Composer $composer, final int $changed) {
        Composer $composer2 = $composer.startRestartGroup(1757425411);
        ComposerKt.sourceInformation($composer2, "C(TabRowImpl)P(4,0:c#ui.graphics.Color,1:c#ui.graphics.Color,3)366@17359L4073:TabRow.kt#uh7d8r");
        int $dirty = $changed;
        if (($changed & 6) == 0) {
            $dirty |= $composer2.changed(modifier) ? 4 : 2;
        }
        if (($changed & 48) == 0) {
            $dirty |= $composer2.changed(containerColor) ? 32 : 16;
        }
        if (($changed & 384) == 0) {
            $dirty |= $composer2.changed(contentColor) ? 256 : 128;
        }
        if (($changed & 3072) == 0) {
            $dirty |= $composer2.changedInstance(function3) ? 2048 : 1024;
        }
        if (($changed & 24576) == 0) {
            $dirty |= $composer2.changedInstance(function2) ? 16384 : 8192;
        }
        if ((196608 & $changed) == 0) {
            $dirty |= $composer2.changedInstance(function22) ? 131072 : 65536;
        }
        int $dirty2 = $dirty;
        if ((74899 & $dirty2) != 74898 || !$composer2.getSkipping()) {
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventStart(1757425411, $dirty2, -1, "androidx.compose.material3.TabRowImpl (TabRow.kt:365)");
            }
            SurfaceKt.m2316SurfaceT9BRK9s(SelectableGroupKt.selectableGroup(modifier), null, containerColor, contentColor, 0.0f, 0.0f, null, ComposableLambdaKt.composableLambda($composer2, -65106680, true, new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.TabRowKt$TabRowImpl$1
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

                /* JADX WARN: Removed duplicated region for block: B:35:0x01e0  */
                /* JADX WARN: Removed duplicated region for block: B:37:? A[RETURN, SYNTHETIC] */
                /*
                    Code decompiled incorrectly, please refer to instructions dump.
                    To view partially-correct add '--show-bad-code' argument
                */
                public final void invoke(androidx.compose.runtime.Composer r23, int r24) {
                    /*
                        Method dump skipped, instructions count: 484
                        To view this dump add '--comments-level debug' option
                    */
                    throw new UnsupportedOperationException("Method not decompiled: androidx.compose.material3.TabRowKt$TabRowImpl$1.invoke(androidx.compose.runtime.Composer, int):void");
                }
            }), $composer2, (($dirty2 << 3) & 896) | 12582912 | (($dirty2 << 3) & 7168), 114);
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventEnd();
            }
        } else {
            $composer2.skipToGroupEnd();
        }
        ScopeUpdateScope endRestartGroup = $composer2.endRestartGroup();
        if (endRestartGroup != null) {
            endRestartGroup.updateScope(new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.TabRowKt$TabRowImpl$2
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

                public final void invoke(Composer composer, int i) {
                    TabRowKt.m2372TabRowImplDTcfvLk(Modifier.this, containerColor, contentColor, function3, function2, function22, composer, RecomposeScopeImplKt.updateChangedFlags($changed | 1));
                }
            });
        }
    }

    /* JADX INFO: Access modifiers changed from: private */
    /* renamed from: TabRowWithSubcomposeImpl-DTcfvLk, reason: not valid java name */
    public static final void m2373TabRowWithSubcomposeImplDTcfvLk(final Modifier modifier, final long containerColor, final long contentColor, final Function3<? super List<TabPosition>, ? super Composer, ? super Integer, Unit> function3, final Function2<? super Composer, ? super Integer, Unit> function2, final Function2<? super Composer, ? super Integer, Unit> function22, Composer $composer, final int $changed) {
        Composer $composer2 = $composer.startRestartGroup(-160898917);
        ComposerKt.sourceInformation($composer2, "C(TabRowWithSubcomposeImpl)P(4,0:c#ui.graphics.Color,1:c#ui.graphics.Color,3)583@24853L2206:TabRow.kt#uh7d8r");
        int $dirty = $changed;
        if (($changed & 6) == 0) {
            $dirty |= $composer2.changed(modifier) ? 4 : 2;
        }
        if (($changed & 48) == 0) {
            $dirty |= $composer2.changed(containerColor) ? 32 : 16;
        }
        if (($changed & 384) == 0) {
            $dirty |= $composer2.changed(contentColor) ? 256 : 128;
        }
        if (($changed & 3072) == 0) {
            $dirty |= $composer2.changedInstance(function3) ? 2048 : 1024;
        }
        if (($changed & 24576) == 0) {
            $dirty |= $composer2.changedInstance(function2) ? 16384 : 8192;
        }
        if ((196608 & $changed) == 0) {
            $dirty |= $composer2.changedInstance(function22) ? 131072 : 65536;
        }
        int $dirty2 = $dirty;
        if ((74899 & $dirty2) != 74898 || !$composer2.getSkipping()) {
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventStart(-160898917, $dirty2, -1, "androidx.compose.material3.TabRowWithSubcomposeImpl (TabRow.kt:582)");
            }
            SurfaceKt.m2316SurfaceT9BRK9s(SelectableGroupKt.selectableGroup(modifier), null, containerColor, contentColor, 0.0f, 0.0f, null, ComposableLambdaKt.composableLambda($composer2, -1617702432, true, new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.TabRowKt$TabRowWithSubcomposeImpl$1
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
                    ComposerKt.sourceInformation($composer3, "C588@25035L2018,588@24993L2060:TabRow.kt#uh7d8r");
                    if (($changed2 & 3) == 2 && $composer3.getSkipping()) {
                        $composer3.skipToGroupEnd();
                        return;
                    }
                    if (ComposerKt.isTraceInProgress()) {
                        ComposerKt.traceEventStart(-1617702432, $changed2, -1, "androidx.compose.material3.TabRowWithSubcomposeImpl.<anonymous> (TabRow.kt:588)");
                    }
                    Modifier fillMaxWidth$default = SizeKt.fillMaxWidth$default(Modifier.INSTANCE, 0.0f, 1, null);
                    $composer3.startReplaceableGroup(-1028159188);
                    ComposerKt.sourceInformation($composer3, "CC(remember):TabRow.kt#9igjgp");
                    boolean invalid$iv = $composer3.changed(function22) | $composer3.changed(function2) | $composer3.changed(function3);
                    final Function2<Composer, Integer, Unit> function23 = function22;
                    final Function2<Composer, Integer, Unit> function24 = function2;
                    final Function3<List<TabPosition>, Composer, Integer, Unit> function32 = function3;
                    Object it$iv = $composer3.rememberedValue();
                    if (invalid$iv || it$iv == Composer.INSTANCE.getEmpty()) {
                        value$iv = new Function2<SubcomposeMeasureScope, Constraints, MeasureResult>() { // from class: androidx.compose.material3.TabRowKt$TabRowWithSubcomposeImpl$1$1$1
                            /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
                            /* JADX WARN: Multi-variable type inference failed */
                            {
                                super(2);
                            }

                            @Override // kotlin.jvm.functions.Function2
                            public /* bridge */ /* synthetic */ MeasureResult invoke(SubcomposeMeasureScope subcomposeMeasureScope, Constraints constraints) {
                                return m2379invoke0kLqBqw(subcomposeMeasureScope, constraints.getValue());
                            }

                            /* renamed from: invoke-0kLqBqw, reason: not valid java name */
                            public final MeasureResult m2379invoke0kLqBqw(final SubcomposeMeasureScope $this$SubcomposeLayout, final long constraints) {
                                int tabRowWidth = Constraints.m6050getMaxWidthimpl(constraints);
                                List tabMeasurables = $this$SubcomposeLayout.subcompose(TabSlots.Tabs, function23);
                                int tabCount = tabMeasurables.size();
                                final Ref.IntRef tabWidth = new Ref.IntRef();
                                if (tabCount > 0) {
                                    tabWidth.element = tabRowWidth / tabCount;
                                }
                                Object initial$iv = 0;
                                Object accumulator$iv = initial$iv;
                                int index$iv$iv = 0;
                                int size = tabMeasurables.size();
                                while (index$iv$iv < size) {
                                    Object item$iv$iv = tabMeasurables.get(index$iv$iv);
                                    Measurable curr = (Measurable) item$iv$iv;
                                    int max = ((Number) accumulator$iv).intValue();
                                    accumulator$iv = Integer.valueOf(Math.max(curr.maxIntrinsicHeight(tabWidth.element), max));
                                    index$iv$iv++;
                                    initial$iv = initial$iv;
                                }
                                final int tabRowHeight = ((Number) accumulator$iv).intValue();
                                List $this$fastMap$iv = tabMeasurables;
                                int $i$f$fastMap = 0;
                                List target$iv = new ArrayList($this$fastMap$iv.size());
                                List $this$fastForEach$iv$iv = $this$fastMap$iv;
                                int size2 = $this$fastForEach$iv$iv.size();
                                int index$iv$iv2 = 0;
                                while (index$iv$iv2 < size2) {
                                    Object item$iv$iv2 = $this$fastForEach$iv$iv.get(index$iv$iv2);
                                    List list = target$iv;
                                    Measurable it = (Measurable) item$iv$iv2;
                                    list.add(it.mo5016measureBRTryo0(Constraints.m6040copyZbe2FdA(constraints, tabWidth.element, tabWidth.element, tabRowHeight, tabRowHeight)));
                                    index$iv$iv2++;
                                    size2 = size2;
                                    $this$fastMap$iv = $this$fastMap$iv;
                                    $i$f$fastMap = $i$f$fastMap;
                                    tabRowWidth = tabRowWidth;
                                    $this$fastForEach$iv$iv = $this$fastForEach$iv$iv;
                                }
                                final int tabRowWidth2 = tabRowWidth;
                                final List tabPlaceables = target$iv;
                                ArrayList arrayList = new ArrayList(tabCount);
                                for (int i = 0; i < tabCount; i++) {
                                    int index = i;
                                    float contentWidth = $this$SubcomposeLayout.mo310toDpu2uoSUM(Math.min(tabMeasurables.get(index).maxIntrinsicWidth(tabRowHeight), tabWidth.element));
                                    float arg0$iv = TabKt.getHorizontalTextPadding();
                                    float other$iv = Dp.m6094constructorimpl(contentWidth - Dp.m6094constructorimpl(2 * arg0$iv));
                                    float indicatorWidth = ((Dp) ComparisonsKt.maxOf(Dp.m6092boximpl(other$iv), Dp.m6092boximpl(Dp.m6094constructorimpl(24)))).m6108unboximpl();
                                    float arg0$iv2 = $this$SubcomposeLayout.mo310toDpu2uoSUM(tabWidth.element);
                                    arrayList.add(new TabPosition(Dp.m6094constructorimpl(index * arg0$iv2), $this$SubcomposeLayout.mo310toDpu2uoSUM(tabWidth.element), indicatorWidth, null));
                                }
                                final ArrayList tabPositions = arrayList;
                                final Function2<Composer, Integer, Unit> function25 = function24;
                                final Function3<List<TabPosition>, Composer, Integer, Unit> function33 = function32;
                                return MeasureScope.layout$default($this$SubcomposeLayout, tabRowWidth2, tabRowHeight, null, new Function1<Placeable.PlacementScope, Unit>() { // from class: androidx.compose.material3.TabRowKt$TabRowWithSubcomposeImpl$1$1$1.1
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
                                        List $this$fastForEachIndexed$iv = tabPlaceables;
                                        Ref.IntRef intRef = tabWidth;
                                        int size3 = $this$fastForEachIndexed$iv.size();
                                        for (int index$iv = 0; index$iv < size3; index$iv++) {
                                            Object item$iv = $this$fastForEachIndexed$iv.get(index$iv);
                                            int index2 = index$iv;
                                            Placeable.PlacementScope.placeRelative$default($this$layout, (Placeable) item$iv, index2 * intRef.element, 0, 0.0f, 4, null);
                                        }
                                        List $this$fastForEach$iv = $this$SubcomposeLayout.subcompose(TabSlots.Divider, function25);
                                        long j = constraints;
                                        int i2 = tabRowHeight;
                                        int size4 = $this$fastForEach$iv.size();
                                        int index$iv2 = 0;
                                        while (index$iv2 < size4) {
                                            Object item$iv2 = $this$fastForEach$iv.get(index$iv2);
                                            Measurable it2 = (Measurable) item$iv2;
                                            m6040copyZbe2FdA = Constraints.m6040copyZbe2FdA(j, (r12 & 1) != 0 ? Constraints.m6052getMinWidthimpl(j) : 0, (r12 & 2) != 0 ? Constraints.m6050getMaxWidthimpl(j) : 0, (r12 & 4) != 0 ? Constraints.m6051getMinHeightimpl(j) : 0, (r12 & 8) != 0 ? Constraints.m6049getMaxHeightimpl(j) : 0);
                                            Placeable placeable = it2.mo5016measureBRTryo0(m6040copyZbe2FdA);
                                            Placeable.PlacementScope.placeRelative$default($this$layout, placeable, 0, i2 - placeable.getHeight(), 0.0f, 4, null);
                                            index$iv2++;
                                            $this$fastForEach$iv = $this$fastForEach$iv;
                                        }
                                        SubcomposeMeasureScope subcomposeMeasureScope = $this$SubcomposeLayout;
                                        TabSlots tabSlots = TabSlots.Indicator;
                                        final Function3<List<TabPosition>, Composer, Integer, Unit> function34 = function33;
                                        final List<TabPosition> list2 = tabPositions;
                                        List $this$fastForEach$iv2 = subcomposeMeasureScope.subcompose(tabSlots, ComposableLambdaKt.composableLambdaInstance(1621992604, true, new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.TabRowKt.TabRowWithSubcomposeImpl.1.1.1.1.3
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
                                                ComposerKt.sourceInformation($composer4, "C631@26859L23:TabRow.kt#uh7d8r");
                                                if (($changed3 & 3) == 2 && $composer4.getSkipping()) {
                                                    $composer4.skipToGroupEnd();
                                                    return;
                                                }
                                                if (ComposerKt.isTraceInProgress()) {
                                                    ComposerKt.traceEventStart(1621992604, $changed3, -1, "androidx.compose.material3.TabRowWithSubcomposeImpl.<anonymous>.<anonymous>.<anonymous>.<anonymous>.<anonymous> (TabRow.kt:631)");
                                                }
                                                function34.invoke(list2, $composer4, 0);
                                                if (ComposerKt.isTraceInProgress()) {
                                                    ComposerKt.traceEventEnd();
                                                }
                                            }
                                        }));
                                        int i3 = tabRowWidth2;
                                        int i4 = tabRowHeight;
                                        int size5 = $this$fastForEach$iv2.size();
                                        for (int index$iv3 = 0; index$iv3 < size5; index$iv3++) {
                                            Object item$iv3 = $this$fastForEach$iv2.get(index$iv3);
                                            Measurable it3 = (Measurable) item$iv3;
                                            Placeable.PlacementScope.placeRelative$default($this$layout, it3.mo5016measureBRTryo0(Constraints.INSTANCE.m6058fixedJhjzzOo(i3, i4)), 0, 0, 0.0f, 4, null);
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
            }), $composer2, (($dirty2 << 3) & 896) | 12582912 | (($dirty2 << 3) & 7168), 114);
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventEnd();
            }
        } else {
            $composer2.skipToGroupEnd();
        }
        ScopeUpdateScope endRestartGroup = $composer2.endRestartGroup();
        if (endRestartGroup != null) {
            endRestartGroup.updateScope(new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.TabRowKt$TabRowWithSubcomposeImpl$2
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

                public final void invoke(Composer composer, int i) {
                    TabRowKt.m2373TabRowWithSubcomposeImplDTcfvLk(Modifier.this, containerColor, contentColor, function3, function2, function22, composer, RecomposeScopeImplKt.updateChangedFlags($changed | 1));
                }
            });
        }
    }

    /* renamed from: PrimaryScrollableTabRow-qhFBPw4, reason: not valid java name */
    public static final void m2365PrimaryScrollableTabRowqhFBPw4(final int selectedTabIndex, Modifier modifier, ScrollState scrollState, long containerColor, long contentColor, float edgePadding, Function3<? super List<TabPosition>, ? super Composer, ? super Integer, Unit> function3, Function2<? super Composer, ? super Integer, Unit> function2, final Function2<? super Composer, ? super Integer, Unit> function22, Composer $composer, final int $changed, final int i) {
        long containerColor2;
        long contentColor2;
        float f;
        ScrollState scrollState2;
        Modifier modifier2;
        Function2 divider;
        int $dirty;
        float edgePadding2;
        ScrollState scrollState3;
        Function3 indicator;
        long containerColor3;
        long contentColor3;
        Composer $composer2;
        int i2;
        int i3;
        int i4;
        Composer $composer3 = $composer.startRestartGroup(-1763241113);
        ComposerKt.sourceInformation($composer3, "C(PrimaryScrollableTabRow)P(7,5,6,0:c#ui.graphics.Color,1:c#ui.graphics.Color,3:c#ui.unit.Dp,4)677@29409L21,678@29475L21,679@29539L19,695@30196L327:TabRow.kt#uh7d8r");
        int $dirty2 = $changed;
        if ((i & 1) != 0) {
            $dirty2 |= 6;
        } else if (($changed & 6) == 0) {
            $dirty2 |= $composer3.changed(selectedTabIndex) ? 4 : 2;
        }
        int i5 = i & 2;
        if (i5 != 0) {
            $dirty2 |= 48;
        } else if (($changed & 48) == 0) {
            $dirty2 |= $composer3.changed(modifier) ? 32 : 16;
        }
        if (($changed & 384) == 0) {
            if ((i & 4) == 0 && $composer3.changed(scrollState)) {
                i4 = 256;
                $dirty2 |= i4;
            }
            i4 = 128;
            $dirty2 |= i4;
        }
        if (($changed & 3072) == 0) {
            if ((i & 8) == 0) {
                containerColor2 = containerColor;
                if ($composer3.changed(containerColor2)) {
                    i3 = 2048;
                    $dirty2 |= i3;
                }
            } else {
                containerColor2 = containerColor;
            }
            i3 = 1024;
            $dirty2 |= i3;
        } else {
            containerColor2 = containerColor;
        }
        if (($changed & 24576) == 0) {
            if ((i & 16) == 0) {
                contentColor2 = contentColor;
                if ($composer3.changed(contentColor2)) {
                    i2 = 16384;
                    $dirty2 |= i2;
                }
            } else {
                contentColor2 = contentColor;
            }
            i2 = 8192;
            $dirty2 |= i2;
        } else {
            contentColor2 = contentColor;
        }
        int i6 = i & 32;
        if (i6 != 0) {
            $dirty2 |= ProfileVerifier.CompilationStatus.RESULT_CODE_ERROR_CANT_WRITE_PROFILE_VERIFICATION_RESULT_CACHE_FILE;
            f = edgePadding;
        } else if ((196608 & $changed) == 0) {
            f = edgePadding;
            $dirty2 |= $composer3.changed(f) ? 131072 : 65536;
        } else {
            f = edgePadding;
        }
        int i7 = i & 64;
        if (i7 != 0) {
            $dirty2 |= 1572864;
        } else if (($changed & 1572864) == 0) {
            $dirty2 |= $composer3.changedInstance(function3) ? 1048576 : 524288;
        }
        int i8 = i & 128;
        if (i8 != 0) {
            $dirty2 |= 12582912;
        } else if (($changed & 12582912) == 0) {
            $dirty2 |= $composer3.changedInstance(function2) ? 8388608 : 4194304;
        }
        if ((i & 256) != 0) {
            $dirty2 |= 100663296;
        } else if (($changed & 100663296) == 0) {
            $dirty2 |= $composer3.changedInstance(function22) ? AccessibilityEventCompat.TYPE_VIEW_TARGETED_BY_SCROLL : 33554432;
        }
        if (($dirty2 & 38347923) == 38347922 && $composer3.getSkipping()) {
            $composer3.skipToGroupEnd();
            modifier2 = modifier;
            scrollState3 = scrollState;
            indicator = function3;
            divider = function2;
            containerColor3 = containerColor2;
            contentColor3 = contentColor2;
            edgePadding2 = f;
            $composer2 = $composer3;
        } else {
            $composer3.startDefaults();
            if (($changed & 1) == 0 || $composer3.getDefaultsInvalid()) {
                Modifier.Companion modifier3 = i5 != 0 ? Modifier.INSTANCE : modifier;
                if ((i & 4) != 0) {
                    scrollState2 = ScrollKt.rememberScrollState(0, $composer3, 0, 1);
                    $dirty2 &= -897;
                } else {
                    scrollState2 = scrollState;
                }
                if ((i & 8) != 0) {
                    modifier2 = modifier3;
                    containerColor2 = TabRowDefaults.INSTANCE.getPrimaryContainerColor($composer3, 6);
                    $dirty2 &= -7169;
                } else {
                    modifier2 = modifier3;
                }
                if ((i & 16) != 0) {
                    contentColor2 = TabRowDefaults.INSTANCE.getPrimaryContentColor($composer3, 6);
                    $dirty2 &= -57345;
                }
                float edgePadding3 = i6 != 0 ? TabRowDefaults.INSTANCE.m2364getScrollableTabRowEdgeStartPaddingD9Ej5fM() : f;
                Function3 indicator2 = i7 != 0 ? ComposableLambdaKt.composableLambda($composer3, 438091970, true, new Function3<List<? extends TabPosition>, Composer, Integer, Unit>() { // from class: androidx.compose.material3.TabRowKt$PrimaryScrollableTabRow$1
                    /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
                    {
                        super(3);
                    }

                    @Override // kotlin.jvm.functions.Function3
                    public /* bridge */ /* synthetic */ Unit invoke(List<? extends TabPosition> list, Composer composer, Integer num) {
                        invoke((List<TabPosition>) list, composer, num.intValue());
                        return Unit.INSTANCE;
                    }

                    public final void invoke(List<TabPosition> list, Composer $composer4, int $changed2) {
                        ComposerKt.sourceInformation($composer4, "C683@29809L75,684@29912L138:TabRow.kt#uh7d8r");
                        if (ComposerKt.isTraceInProgress()) {
                            ComposerKt.traceEventStart(438091970, $changed2, -1, "androidx.compose.material3.PrimaryScrollableTabRow.<anonymous> (TabRow.kt:682)");
                        }
                        if (selectedTabIndex < list.size()) {
                            State width$delegate = AnimateAsStateKt.m116animateDpAsStateAjpBEmI(list.get(selectedTabIndex).getContentWidth(), null, null, null, $composer4, 0, 14);
                            TabRowDefaults.INSTANCE.m2362PrimaryIndicator10LGxhE(TabRowDefaults.INSTANCE.tabIndicatorOffset(Modifier.INSTANCE, list.get(selectedTabIndex)), invoke$lambda$0(width$delegate), 0.0f, 0L, null, $composer4, ProfileVerifier.CompilationStatus.RESULT_CODE_ERROR_CANT_WRITE_PROFILE_VERIFICATION_RESULT_CACHE_FILE, 28);
                        }
                        if (ComposerKt.isTraceInProgress()) {
                            ComposerKt.traceEventEnd();
                        }
                    }

                    private static final float invoke$lambda$0(State<Dp> state) {
                        Object thisObj$iv = state.getValue();
                        return ((Dp) thisObj$iv).m6108unboximpl();
                    }
                }) : function3;
                if (i8 != 0) {
                    divider = ComposableSingletons$TabRowKt.INSTANCE.m1778getLambda4$material3_release();
                    $dirty = $dirty2;
                    edgePadding2 = edgePadding3;
                    scrollState3 = scrollState2;
                    indicator = indicator2;
                    containerColor3 = containerColor2;
                    contentColor3 = contentColor2;
                } else {
                    divider = function2;
                    $dirty = $dirty2;
                    edgePadding2 = edgePadding3;
                    scrollState3 = scrollState2;
                    indicator = indicator2;
                    containerColor3 = containerColor2;
                    contentColor3 = contentColor2;
                }
            } else {
                $composer3.skipToGroupEnd();
                if ((i & 4) != 0) {
                    $dirty2 &= -897;
                }
                if ((i & 8) != 0) {
                    $dirty2 &= -7169;
                }
                if ((i & 16) != 0) {
                    modifier2 = modifier;
                    scrollState3 = scrollState;
                    indicator = function3;
                    divider = function2;
                    $dirty = $dirty2 & (-57345);
                    containerColor3 = containerColor2;
                    contentColor3 = contentColor2;
                    edgePadding2 = f;
                } else {
                    modifier2 = modifier;
                    scrollState3 = scrollState;
                    indicator = function3;
                    divider = function2;
                    $dirty = $dirty2;
                    containerColor3 = containerColor2;
                    contentColor3 = contentColor2;
                    edgePadding2 = f;
                }
            }
            $composer3.endDefaults();
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventStart(-1763241113, $dirty, -1, "androidx.compose.material3.PrimaryScrollableTabRow (TabRow.kt:694)");
            }
            $composer2 = $composer3;
            m2368ScrollableTabRowImpqhFBPw4(selectedTabIndex, indicator, modifier2, containerColor3, contentColor3, edgePadding2, divider, function22, scrollState3, $composer3, ($dirty & 14) | (($dirty >> 15) & 112) | (($dirty << 3) & 896) | ($dirty & 7168) | (57344 & $dirty) | (458752 & $dirty) | (($dirty >> 3) & 3670016) | (29360128 & ($dirty >> 3)) | (($dirty << 18) & 234881024), 0);
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventEnd();
            }
        }
        ScopeUpdateScope endRestartGroup = $composer2.endRestartGroup();
        if (endRestartGroup != null) {
            final Modifier modifier4 = modifier2;
            final ScrollState scrollState4 = scrollState3;
            final long j = containerColor3;
            final long j2 = contentColor3;
            final float f2 = edgePadding2;
            final Function3 function32 = indicator;
            final Function2 function23 = divider;
            endRestartGroup.updateScope(new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.TabRowKt$PrimaryScrollableTabRow$2
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

                public final void invoke(Composer composer, int i9) {
                    TabRowKt.m2365PrimaryScrollableTabRowqhFBPw4(selectedTabIndex, modifier4, scrollState4, j, j2, f2, function32, function23, function22, composer, RecomposeScopeImplKt.updateChangedFlags($changed | 1), i);
                }
            });
        }
    }

    /* renamed from: SecondaryScrollableTabRow-qhFBPw4, reason: not valid java name */
    public static final void m2369SecondaryScrollableTabRowqhFBPw4(final int selectedTabIndex, Modifier modifier, ScrollState scrollState, long containerColor, long contentColor, float edgePadding, Function3<? super List<TabPosition>, ? super Composer, ? super Integer, Unit> function3, Function2<? super Composer, ? super Integer, Unit> function2, final Function2<? super Composer, ? super Integer, Unit> function22, Composer $composer, final int $changed, final int i) {
        long containerColor2;
        long contentColor2;
        float f;
        ScrollState scrollState2;
        Modifier modifier2;
        Function2 divider;
        int $dirty;
        float edgePadding2;
        ScrollState scrollState3;
        Function3 indicator;
        long containerColor3;
        long contentColor3;
        Composer $composer2;
        int i2;
        int i3;
        int i4;
        Composer $composer3 = $composer.startRestartGroup(1821940917);
        ComposerKt.sourceInformation($composer3, "C(SecondaryScrollableTabRow)P(7,5,6,0:c#ui.graphics.Color,1:c#ui.graphics.Color,3:c#ui.unit.Dp,4)749@33144L21,750@33210L23,751@33276L21,763@33731L326:TabRow.kt#uh7d8r");
        int $dirty2 = $changed;
        if ((i & 1) != 0) {
            $dirty2 |= 6;
        } else if (($changed & 6) == 0) {
            $dirty2 |= $composer3.changed(selectedTabIndex) ? 4 : 2;
        }
        int i5 = i & 2;
        if (i5 != 0) {
            $dirty2 |= 48;
        } else if (($changed & 48) == 0) {
            $dirty2 |= $composer3.changed(modifier) ? 32 : 16;
        }
        if (($changed & 384) == 0) {
            if ((i & 4) == 0 && $composer3.changed(scrollState)) {
                i4 = 256;
                $dirty2 |= i4;
            }
            i4 = 128;
            $dirty2 |= i4;
        }
        if (($changed & 3072) == 0) {
            if ((i & 8) == 0) {
                containerColor2 = containerColor;
                if ($composer3.changed(containerColor2)) {
                    i3 = 2048;
                    $dirty2 |= i3;
                }
            } else {
                containerColor2 = containerColor;
            }
            i3 = 1024;
            $dirty2 |= i3;
        } else {
            containerColor2 = containerColor;
        }
        if (($changed & 24576) == 0) {
            if ((i & 16) == 0) {
                contentColor2 = contentColor;
                if ($composer3.changed(contentColor2)) {
                    i2 = 16384;
                    $dirty2 |= i2;
                }
            } else {
                contentColor2 = contentColor;
            }
            i2 = 8192;
            $dirty2 |= i2;
        } else {
            contentColor2 = contentColor;
        }
        int i6 = i & 32;
        if (i6 != 0) {
            $dirty2 |= ProfileVerifier.CompilationStatus.RESULT_CODE_ERROR_CANT_WRITE_PROFILE_VERIFICATION_RESULT_CACHE_FILE;
            f = edgePadding;
        } else if ((196608 & $changed) == 0) {
            f = edgePadding;
            $dirty2 |= $composer3.changed(f) ? 131072 : 65536;
        } else {
            f = edgePadding;
        }
        int i7 = i & 64;
        if (i7 != 0) {
            $dirty2 |= 1572864;
        } else if (($changed & 1572864) == 0) {
            $dirty2 |= $composer3.changedInstance(function3) ? 1048576 : 524288;
        }
        int i8 = i & 128;
        if (i8 != 0) {
            $dirty2 |= 12582912;
        } else if (($changed & 12582912) == 0) {
            $dirty2 |= $composer3.changedInstance(function2) ? 8388608 : 4194304;
        }
        if ((i & 256) != 0) {
            $dirty2 |= 100663296;
        } else if (($changed & 100663296) == 0) {
            $dirty2 |= $composer3.changedInstance(function22) ? AccessibilityEventCompat.TYPE_VIEW_TARGETED_BY_SCROLL : 33554432;
        }
        if (($dirty2 & 38347923) == 38347922 && $composer3.getSkipping()) {
            $composer3.skipToGroupEnd();
            modifier2 = modifier;
            scrollState3 = scrollState;
            indicator = function3;
            divider = function2;
            containerColor3 = containerColor2;
            contentColor3 = contentColor2;
            edgePadding2 = f;
            $composer2 = $composer3;
        } else {
            $composer3.startDefaults();
            if (($changed & 1) == 0 || $composer3.getDefaultsInvalid()) {
                Modifier.Companion modifier3 = i5 != 0 ? Modifier.INSTANCE : modifier;
                if ((i & 4) != 0) {
                    scrollState2 = ScrollKt.rememberScrollState(0, $composer3, 0, 1);
                    $dirty2 &= -897;
                } else {
                    scrollState2 = scrollState;
                }
                if ((i & 8) != 0) {
                    modifier2 = modifier3;
                    containerColor2 = TabRowDefaults.INSTANCE.getSecondaryContainerColor($composer3, 6);
                    $dirty2 &= -7169;
                } else {
                    modifier2 = modifier3;
                }
                if ((i & 16) != 0) {
                    contentColor2 = TabRowDefaults.INSTANCE.getSecondaryContentColor($composer3, 6);
                    $dirty2 &= -57345;
                }
                float edgePadding3 = i6 != 0 ? TabRowDefaults.INSTANCE.m2364getScrollableTabRowEdgeStartPaddingD9Ej5fM() : f;
                Function3 indicator2 = i7 != 0 ? ComposableLambdaKt.composableLambda($composer3, -115843248, true, new Function3<List<? extends TabPosition>, Composer, Integer, Unit>() { // from class: androidx.compose.material3.TabRowKt$SecondaryScrollableTabRow$1
                    /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
                    {
                        super(3);
                    }

                    @Override // kotlin.jvm.functions.Function3
                    public /* bridge */ /* synthetic */ Unit invoke(List<? extends TabPosition> list, Composer composer, Integer num) {
                        invoke((List<TabPosition>) list, composer, num.intValue());
                        return Unit.INSTANCE;
                    }

                    public final void invoke(List<TabPosition> list, Composer $composer4, int $changed2) {
                        ComposerKt.sourceInformation($composer4, "C754@33494L101:TabRow.kt#uh7d8r");
                        if (ComposerKt.isTraceInProgress()) {
                            ComposerKt.traceEventStart(-115843248, $changed2, -1, "androidx.compose.material3.SecondaryScrollableTabRow.<anonymous> (TabRow.kt:754)");
                        }
                        TabRowDefaults.INSTANCE.m2363SecondaryIndicator9IZ8Weo(TabRowDefaults.INSTANCE.tabIndicatorOffset(Modifier.INSTANCE, list.get(selectedTabIndex)), 0.0f, 0L, $composer4, 3072, 6);
                        if (ComposerKt.isTraceInProgress()) {
                            ComposerKt.traceEventEnd();
                        }
                    }
                }) : function3;
                if (i8 != 0) {
                    divider = ComposableSingletons$TabRowKt.INSTANCE.m1779getLambda5$material3_release();
                    $dirty = $dirty2;
                    edgePadding2 = edgePadding3;
                    scrollState3 = scrollState2;
                    indicator = indicator2;
                    containerColor3 = containerColor2;
                    contentColor3 = contentColor2;
                } else {
                    divider = function2;
                    $dirty = $dirty2;
                    edgePadding2 = edgePadding3;
                    scrollState3 = scrollState2;
                    indicator = indicator2;
                    containerColor3 = containerColor2;
                    contentColor3 = contentColor2;
                }
            } else {
                $composer3.skipToGroupEnd();
                if ((i & 4) != 0) {
                    $dirty2 &= -897;
                }
                if ((i & 8) != 0) {
                    $dirty2 &= -7169;
                }
                if ((i & 16) != 0) {
                    modifier2 = modifier;
                    scrollState3 = scrollState;
                    indicator = function3;
                    divider = function2;
                    $dirty = $dirty2 & (-57345);
                    containerColor3 = containerColor2;
                    contentColor3 = contentColor2;
                    edgePadding2 = f;
                } else {
                    modifier2 = modifier;
                    scrollState3 = scrollState;
                    indicator = function3;
                    divider = function2;
                    $dirty = $dirty2;
                    containerColor3 = containerColor2;
                    contentColor3 = contentColor2;
                    edgePadding2 = f;
                }
            }
            $composer3.endDefaults();
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventStart(1821940917, $dirty, -1, "androidx.compose.material3.SecondaryScrollableTabRow (TabRow.kt:762)");
            }
            $composer2 = $composer3;
            m2368ScrollableTabRowImpqhFBPw4(selectedTabIndex, indicator, modifier2, containerColor3, contentColor3, edgePadding2, divider, function22, scrollState3, $composer3, ($dirty & 14) | (($dirty >> 15) & 112) | (($dirty << 3) & 896) | ($dirty & 7168) | (57344 & $dirty) | (458752 & $dirty) | (($dirty >> 3) & 3670016) | (29360128 & ($dirty >> 3)) | (($dirty << 18) & 234881024), 0);
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventEnd();
            }
        }
        ScopeUpdateScope endRestartGroup = $composer2.endRestartGroup();
        if (endRestartGroup != null) {
            final Modifier modifier4 = modifier2;
            final ScrollState scrollState4 = scrollState3;
            final long j = containerColor3;
            final long j2 = contentColor3;
            final float f2 = edgePadding2;
            final Function3 function32 = indicator;
            final Function2 function23 = divider;
            endRestartGroup.updateScope(new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.TabRowKt$SecondaryScrollableTabRow$2
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

                public final void invoke(Composer composer, int i9) {
                    TabRowKt.m2369SecondaryScrollableTabRowqhFBPw4(selectedTabIndex, modifier4, scrollState4, j, j2, f2, function32, function23, function22, composer, RecomposeScopeImplKt.updateChangedFlags($changed | 1), i);
                }
            });
        }
    }

    /* renamed from: ScrollableTabRow-sKfQg0A, reason: not valid java name */
    public static final void m2367ScrollableTabRowsKfQg0A(final int selectedTabIndex, Modifier modifier, long containerColor, long contentColor, float edgePadding, Function3<? super List<TabPosition>, ? super Composer, ? super Integer, Unit> function3, Function2<? super Composer, ? super Integer, Unit> function2, final Function2<? super Composer, ? super Integer, Unit> function22, Composer $composer, final int $changed, final int i) {
        long containerColor2;
        long contentColor2;
        float edgePadding2;
        Function3 indicator;
        Function2 divider;
        Modifier modifier2;
        long containerColor3;
        long contentColor3;
        float edgePadding3;
        Function3 indicator2;
        int $dirty;
        Composer $composer2;
        int i2;
        int i3;
        Composer $composer3 = $composer.startRestartGroup(-497821003);
        ComposerKt.sourceInformation($composer3, "C(ScrollableTabRow)P(6,5,0:c#ui.graphics.Color,1:c#ui.graphics.Color,3:c#ui.unit.Dp,4)816@36583L21,817@36647L19,838@37409L21,829@37100L336:TabRow.kt#uh7d8r");
        int $dirty2 = $changed;
        if ((i & 1) != 0) {
            $dirty2 |= 6;
        } else if (($changed & 6) == 0) {
            $dirty2 |= $composer3.changed(selectedTabIndex) ? 4 : 2;
        }
        int i4 = i & 2;
        if (i4 != 0) {
            $dirty2 |= 48;
        } else if (($changed & 48) == 0) {
            $dirty2 |= $composer3.changed(modifier) ? 32 : 16;
        }
        if (($changed & 384) == 0) {
            if ((i & 4) == 0) {
                containerColor2 = containerColor;
                if ($composer3.changed(containerColor2)) {
                    i3 = 256;
                    $dirty2 |= i3;
                }
            } else {
                containerColor2 = containerColor;
            }
            i3 = 128;
            $dirty2 |= i3;
        } else {
            containerColor2 = containerColor;
        }
        if (($changed & 3072) == 0) {
            if ((i & 8) == 0) {
                contentColor2 = contentColor;
                if ($composer3.changed(contentColor2)) {
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
        } else if (($changed & 24576) == 0) {
            edgePadding2 = edgePadding;
            $dirty2 |= $composer3.changed(edgePadding2) ? 16384 : 8192;
        } else {
            edgePadding2 = edgePadding;
        }
        int i6 = i & 32;
        if (i6 != 0) {
            $dirty2 |= ProfileVerifier.CompilationStatus.RESULT_CODE_ERROR_CANT_WRITE_PROFILE_VERIFICATION_RESULT_CACHE_FILE;
            indicator = function3;
        } else if ((196608 & $changed) == 0) {
            indicator = function3;
            $dirty2 |= $composer3.changedInstance(indicator) ? 131072 : 65536;
        } else {
            indicator = function3;
        }
        int i7 = i & 64;
        if (i7 != 0) {
            $dirty2 |= 1572864;
        } else if (($changed & 1572864) == 0) {
            $dirty2 |= $composer3.changedInstance(function2) ? 1048576 : 524288;
        }
        if ((i & 128) != 0) {
            $dirty2 |= 12582912;
        } else if (($changed & 12582912) == 0) {
            $dirty2 |= $composer3.changedInstance(function22) ? 8388608 : 4194304;
        }
        if (($dirty2 & 4793491) == 4793490 && $composer3.getSkipping()) {
            $composer3.skipToGroupEnd();
            modifier2 = modifier;
            divider = function2;
            containerColor3 = containerColor2;
            contentColor3 = contentColor2;
            edgePadding3 = edgePadding2;
            indicator2 = indicator;
            $composer2 = $composer3;
        } else {
            $composer3.startDefaults();
            if (($changed & 1) == 0 || $composer3.getDefaultsInvalid()) {
                Modifier.Companion modifier3 = i4 != 0 ? Modifier.INSTANCE : modifier;
                if ((i & 4) != 0) {
                    containerColor2 = TabRowDefaults.INSTANCE.getPrimaryContainerColor($composer3, 6);
                    $dirty2 &= -897;
                }
                if ((i & 8) != 0) {
                    $dirty2 &= -7169;
                    contentColor2 = TabRowDefaults.INSTANCE.getPrimaryContentColor($composer3, 6);
                }
                if (i5 != 0) {
                    edgePadding2 = TabRowDefaults.INSTANCE.m2364getScrollableTabRowEdgeStartPaddingD9Ej5fM();
                }
                if (i6 != 0) {
                    indicator = ComposableLambdaKt.composableLambda($composer3, -913748678, true, new Function3<List<? extends TabPosition>, Composer, Integer, Unit>() { // from class: androidx.compose.material3.TabRowKt$ScrollableTabRow$1
                        /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
                        {
                            super(3);
                        }

                        @Override // kotlin.jvm.functions.Function3
                        public /* bridge */ /* synthetic */ Unit invoke(List<? extends TabPosition> list, Composer composer, Integer num) {
                            invoke((List<TabPosition>) list, composer, num.intValue());
                            return Unit.INSTANCE;
                        }

                        public final void invoke(List<TabPosition> list, Composer $composer4, int $changed2) {
                            ComposerKt.sourceInformation($composer4, "C820@36863L101:TabRow.kt#uh7d8r");
                            if (ComposerKt.isTraceInProgress()) {
                                ComposerKt.traceEventStart(-913748678, $changed2, -1, "androidx.compose.material3.ScrollableTabRow.<anonymous> (TabRow.kt:820)");
                            }
                            TabRowDefaults.INSTANCE.m2363SecondaryIndicator9IZ8Weo(TabRowDefaults.INSTANCE.tabIndicatorOffset(Modifier.INSTANCE, list.get(selectedTabIndex)), 0.0f, 0L, $composer4, 3072, 6);
                            if (ComposerKt.isTraceInProgress()) {
                                ComposerKt.traceEventEnd();
                            }
                        }
                    });
                }
                if (i7 != 0) {
                    modifier2 = modifier3;
                    divider = ComposableSingletons$TabRowKt.INSTANCE.m1780getLambda6$material3_release();
                    containerColor3 = containerColor2;
                    contentColor3 = contentColor2;
                    edgePadding3 = edgePadding2;
                    indicator2 = indicator;
                    $dirty = $dirty2;
                } else {
                    divider = function2;
                    modifier2 = modifier3;
                    containerColor3 = containerColor2;
                    contentColor3 = contentColor2;
                    edgePadding3 = edgePadding2;
                    indicator2 = indicator;
                    $dirty = $dirty2;
                }
            } else {
                $composer3.skipToGroupEnd();
                if ((i & 4) != 0) {
                    $dirty2 &= -897;
                }
                if ((i & 8) != 0) {
                    modifier2 = modifier;
                    divider = function2;
                    containerColor3 = containerColor2;
                    contentColor3 = contentColor2;
                    edgePadding3 = edgePadding2;
                    indicator2 = indicator;
                    $dirty = $dirty2 & (-7169);
                } else {
                    modifier2 = modifier;
                    divider = function2;
                    containerColor3 = containerColor2;
                    contentColor3 = contentColor2;
                    edgePadding3 = edgePadding2;
                    indicator2 = indicator;
                    $dirty = $dirty2;
                }
            }
            $composer3.endDefaults();
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventStart(-497821003, $dirty, -1, "androidx.compose.material3.ScrollableTabRow (TabRow.kt:828)");
            }
            $composer2 = $composer3;
            m2368ScrollableTabRowImpqhFBPw4(selectedTabIndex, indicator2, modifier2, containerColor3, contentColor3, edgePadding3, divider, function22, ScrollKt.rememberScrollState(0, $composer3, 0, 1), $composer3, ($dirty & 14) | (($dirty >> 12) & 112) | (($dirty << 3) & 896) | (($dirty << 3) & 7168) | (($dirty << 3) & 57344) | (458752 & ($dirty << 3)) | (3670016 & $dirty) | (29360128 & $dirty), 0);
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventEnd();
            }
        }
        ScopeUpdateScope endRestartGroup = $composer2.endRestartGroup();
        if (endRestartGroup != null) {
            final Modifier modifier4 = modifier2;
            final long j = containerColor3;
            final long j2 = contentColor3;
            final float f = edgePadding3;
            final Function3 function32 = indicator2;
            final Function2 function23 = divider;
            endRestartGroup.updateScope(new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.TabRowKt$ScrollableTabRow$2
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
                    TabRowKt.m2367ScrollableTabRowsKfQg0A(selectedTabIndex, modifier4, j, j2, f, function32, function23, function22, composer, RecomposeScopeImplKt.updateChangedFlags($changed | 1), i);
                }
            });
        }
    }

    /* JADX INFO: Access modifiers changed from: private */
    /* renamed from: ScrollableTabRowImp-qhFBPw4, reason: not valid java name */
    public static final void m2368ScrollableTabRowImpqhFBPw4(final int selectedTabIndex, final Function3<? super List<TabPosition>, ? super Composer, ? super Integer, Unit> function3, Modifier modifier, long containerColor, long contentColor, float edgePadding, Function2<? super Composer, ? super Integer, Unit> function2, final Function2<? super Composer, ? super Integer, Unit> function22, final ScrollState scrollState, Composer $composer, final int $changed, final int i) {
        long containerColor2;
        long j;
        float f;
        Modifier.Companion modifier2;
        long contentColor2;
        float edgePadding2;
        Function2 divider;
        Modifier modifier3;
        long contentColor3;
        long containerColor3;
        float edgePadding3;
        Function2 divider2;
        int i2;
        int i3;
        Composer $composer2 = $composer.startRestartGroup(-1696166011);
        ComposerKt.sourceInformation($composer2, "C(ScrollableTabRowImp)P(7,4,5,0:c#ui.graphics.Color,1:c#ui.graphics.Color,3:c#ui.unit.Dp!1,8)847@37660L21,848@37724L19,856@37975L3984:TabRow.kt#uh7d8r");
        int $dirty = $changed;
        if ((i & 1) != 0) {
            $dirty |= 6;
        } else if (($changed & 6) == 0) {
            $dirty |= $composer2.changed(selectedTabIndex) ? 4 : 2;
        }
        if ((i & 2) != 0) {
            $dirty |= 48;
        } else if (($changed & 48) == 0) {
            $dirty |= $composer2.changedInstance(function3) ? 32 : 16;
        }
        int i4 = i & 4;
        if (i4 != 0) {
            $dirty |= 384;
        } else if (($changed & 384) == 0) {
            $dirty |= $composer2.changed(modifier) ? 256 : 128;
        }
        if (($changed & 3072) == 0) {
            if ((i & 8) == 0) {
                containerColor2 = containerColor;
                if ($composer2.changed(containerColor2)) {
                    i3 = 2048;
                    $dirty |= i3;
                }
            } else {
                containerColor2 = containerColor;
            }
            i3 = 1024;
            $dirty |= i3;
        } else {
            containerColor2 = containerColor;
        }
        if (($changed & 24576) == 0) {
            if ((i & 16) == 0) {
                j = contentColor;
                if ($composer2.changed(j)) {
                    i2 = 16384;
                    $dirty |= i2;
                }
            } else {
                j = contentColor;
            }
            i2 = 8192;
            $dirty |= i2;
        } else {
            j = contentColor;
        }
        int i5 = i & 32;
        if (i5 != 0) {
            $dirty |= ProfileVerifier.CompilationStatus.RESULT_CODE_ERROR_CANT_WRITE_PROFILE_VERIFICATION_RESULT_CACHE_FILE;
            f = edgePadding;
        } else if ((196608 & $changed) == 0) {
            f = edgePadding;
            $dirty |= $composer2.changed(f) ? 131072 : 65536;
        } else {
            f = edgePadding;
        }
        int i6 = i & 64;
        if (i6 != 0) {
            $dirty |= 1572864;
        } else if (($changed & 1572864) == 0) {
            $dirty |= $composer2.changedInstance(function2) ? 1048576 : 524288;
        }
        if ((i & 128) != 0) {
            $dirty |= 12582912;
        } else if (($changed & 12582912) == 0) {
            $dirty |= $composer2.changedInstance(function22) ? 8388608 : 4194304;
        }
        if ((i & 256) != 0) {
            $dirty |= 100663296;
        } else if (($changed & 100663296) == 0) {
            $dirty |= $composer2.changed(scrollState) ? AccessibilityEventCompat.TYPE_VIEW_TARGETED_BY_SCROLL : 33554432;
        }
        if (($dirty & 38347923) == 38347922 && $composer2.getSkipping()) {
            $composer2.skipToGroupEnd();
            modifier3 = modifier;
            divider2 = function2;
            containerColor3 = containerColor2;
            contentColor3 = j;
            edgePadding3 = f;
        } else {
            $composer2.startDefaults();
            if (($changed & 1) == 0 || $composer2.getDefaultsInvalid()) {
                modifier2 = i4 != 0 ? Modifier.INSTANCE : modifier;
                if ((i & 8) != 0) {
                    containerColor2 = TabRowDefaults.INSTANCE.getPrimaryContainerColor($composer2, 6);
                    $dirty &= -7169;
                }
                if ((i & 16) != 0) {
                    contentColor2 = TabRowDefaults.INSTANCE.getPrimaryContentColor($composer2, 6);
                    $dirty &= -57345;
                } else {
                    contentColor2 = j;
                }
                edgePadding2 = i5 != 0 ? TabRowDefaults.INSTANCE.m2364getScrollableTabRowEdgeStartPaddingD9Ej5fM() : f;
                divider = i6 != 0 ? ComposableSingletons$TabRowKt.INSTANCE.m1781getLambda7$material3_release() : function2;
            } else {
                $composer2.skipToGroupEnd();
                if ((i & 8) != 0) {
                    $dirty &= -7169;
                }
                if ((i & 16) != 0) {
                    $dirty &= -57345;
                    contentColor2 = j;
                    edgePadding2 = f;
                    modifier2 = modifier;
                    divider = function2;
                } else {
                    modifier2 = modifier;
                    contentColor2 = j;
                    edgePadding2 = f;
                    divider = function2;
                }
            }
            $composer2.endDefaults();
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventStart(-1696166011, $dirty, -1, "androidx.compose.material3.ScrollableTabRowImp (TabRow.kt:855)");
            }
            final float f2 = edgePadding2;
            final Function2 function23 = divider;
            SurfaceKt.m2316SurfaceT9BRK9s(modifier2, null, containerColor2, contentColor2, 0.0f, 0.0f, null, ComposableLambdaKt.composableLambda($composer2, -1178901494, true, new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.TabRowKt$ScrollableTabRowImp$1
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
                    Object value$iv;
                    Object value$iv2;
                    ComposerKt.sourceInformation($composer3, "C861@38118L24,862@38175L185,875@38628L3325,868@38369L3584:TabRow.kt#uh7d8r");
                    if (($changed2 & 3) != 2 || !$composer3.getSkipping()) {
                        if (ComposerKt.isTraceInProgress()) {
                            ComposerKt.traceEventStart(-1178901494, $changed2, -1, "androidx.compose.material3.ScrollableTabRowImp.<anonymous> (TabRow.kt:861)");
                        }
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
                        $composer3.startReplaceableGroup(121290627);
                        ComposerKt.sourceInformation($composer3, "CC(remember):TabRow.kt#9igjgp");
                        boolean invalid$iv = $composer3.changed(ScrollState.this) | $composer3.changed(coroutineScope);
                        ScrollState scrollState2 = ScrollState.this;
                        Object it$iv = $composer3.rememberedValue();
                        if (invalid$iv || it$iv == Composer.INSTANCE.getEmpty()) {
                            value$iv = new ScrollableTabData(scrollState2, coroutineScope);
                            $composer3.updateRememberedValue(value$iv);
                        } else {
                            value$iv = it$iv;
                        }
                        final ScrollableTabData scrollableTabData = (ScrollableTabData) value$iv;
                        $composer3.endReplaceableGroup();
                        Modifier clipToBounds = ClipKt.clipToBounds(SelectableGroupKt.selectableGroup(ScrollKt.horizontalScroll$default(SizeKt.wrapContentSize$default(SizeKt.fillMaxWidth$default(Modifier.INSTANCE, 0.0f, 1, null), Alignment.INSTANCE.getCenterStart(), false, 2, null), ScrollState.this, false, null, false, 14, null)));
                        $composer3.startReplaceableGroup(121291080);
                        ComposerKt.sourceInformation($composer3, "CC(remember):TabRow.kt#9igjgp");
                        boolean invalid$iv2 = $composer3.changed(f2) | $composer3.changed(function22) | $composer3.changed(function23) | $composer3.changed(function3) | $composer3.changedInstance(scrollableTabData) | $composer3.changed(selectedTabIndex);
                        final float f3 = f2;
                        final Function2<Composer, Integer, Unit> function24 = function22;
                        final Function2<Composer, Integer, Unit> function25 = function23;
                        final int i7 = selectedTabIndex;
                        final Function3<List<TabPosition>, Composer, Integer, Unit> function32 = function3;
                        Object it$iv2 = $composer3.rememberedValue();
                        if (invalid$iv2 || it$iv2 == Composer.INSTANCE.getEmpty()) {
                            value$iv2 = new Function2<SubcomposeMeasureScope, Constraints, MeasureResult>() { // from class: androidx.compose.material3.TabRowKt$ScrollableTabRowImp$1$1$1
                                /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
                                /* JADX WARN: Multi-variable type inference failed */
                                {
                                    super(2);
                                }

                                @Override // kotlin.jvm.functions.Function2
                                public /* bridge */ /* synthetic */ MeasureResult invoke(SubcomposeMeasureScope subcomposeMeasureScope, Constraints constraints) {
                                    return m2377invoke0kLqBqw(subcomposeMeasureScope, constraints.getValue());
                                }

                                /* renamed from: invoke-0kLqBqw, reason: not valid java name */
                                public final MeasureResult m2377invoke0kLqBqw(final SubcomposeMeasureScope $this$SubcomposeLayout, final long constraints) {
                                    float f4;
                                    long tabConstraints;
                                    f4 = TabRowKt.ScrollableTabRowMinimumTabWidth;
                                    int minTabWidth = $this$SubcomposeLayout.mo307roundToPx0680j_4(f4);
                                    final int padding = $this$SubcomposeLayout.mo307roundToPx0680j_4(f3);
                                    List tabMeasurables = $this$SubcomposeLayout.subcompose(TabSlots.Tabs, function24);
                                    Object initial$iv = 0;
                                    Object accumulator$iv = initial$iv;
                                    int index$iv$iv = 0;
                                    int size = tabMeasurables.size();
                                    while (index$iv$iv < size) {
                                        Object item$iv$iv = tabMeasurables.get(index$iv$iv);
                                        Measurable measurable = (Measurable) item$iv$iv;
                                        int curr = ((Number) accumulator$iv).intValue();
                                        accumulator$iv = Integer.valueOf(Math.max(curr, measurable.maxIntrinsicHeight(Integer.MAX_VALUE)));
                                        index$iv$iv++;
                                        initial$iv = initial$iv;
                                    }
                                    final int layoutHeight = ((Number) accumulator$iv).intValue();
                                    tabConstraints = Constraints.m6040copyZbe2FdA(constraints, (r12 & 1) != 0 ? Constraints.m6052getMinWidthimpl(constraints) : minTabWidth, (r12 & 2) != 0 ? Constraints.m6050getMaxWidthimpl(constraints) : 0, (r12 & 4) != 0 ? Constraints.m6051getMinHeightimpl(constraints) : layoutHeight, (r12 & 8) != 0 ? Constraints.m6049getMaxHeightimpl(constraints) : layoutHeight);
                                    final List tabPlaceables = new ArrayList();
                                    final List tabContentWidths = new ArrayList();
                                    List $this$fastForEach$iv = tabMeasurables;
                                    int $i$f$fastForEach = 0;
                                    int index$iv = 0;
                                    for (int size2 = $this$fastForEach$iv.size(); index$iv < size2; size2 = size2) {
                                        Object item$iv = $this$fastForEach$iv.get(index$iv);
                                        Measurable it = (Measurable) item$iv;
                                        Placeable placeable = it.mo5016measureBRTryo0(tabConstraints);
                                        List $this$fastForEach$iv2 = $this$fastForEach$iv;
                                        float contentWidth = $this$SubcomposeLayout.mo310toDpu2uoSUM(Math.min(it.maxIntrinsicWidth(placeable.getHeight()), placeable.getWidth()));
                                        float arg0$iv = TabKt.getHorizontalTextPadding();
                                        int $i$f$fastForEach2 = $i$f$fastForEach;
                                        float other$iv = Dp.m6094constructorimpl(2 * arg0$iv);
                                        float other$iv2 = Dp.m6094constructorimpl(contentWidth - other$iv);
                                        tabPlaceables.add(placeable);
                                        tabContentWidths.add(Dp.m6092boximpl(other$iv2));
                                        index$iv++;
                                        $this$fastForEach$iv = $this$fastForEach$iv2;
                                        $i$f$fastForEach = $i$f$fastForEach2;
                                    }
                                    Object accumulator$iv2 = Integer.valueOf(padding * 2);
                                    int size3 = tabPlaceables.size();
                                    for (int index$iv$iv2 = 0; index$iv$iv2 < size3; index$iv$iv2++) {
                                        Object item$iv$iv2 = tabPlaceables.get(index$iv$iv2);
                                        Placeable measurable2 = (Placeable) item$iv$iv2;
                                        int curr2 = ((Number) accumulator$iv2).intValue();
                                        accumulator$iv2 = Integer.valueOf(curr2 + measurable2.getWidth());
                                    }
                                    final int layoutWidth = ((Number) accumulator$iv2).intValue();
                                    final Function2<Composer, Integer, Unit> function26 = function25;
                                    final ScrollableTabData scrollableTabData2 = scrollableTabData;
                                    final int i8 = i7;
                                    final Function3<List<TabPosition>, Composer, Integer, Unit> function33 = function32;
                                    return MeasureScope.layout$default($this$SubcomposeLayout, layoutWidth, layoutHeight, null, new Function1<Placeable.PlacementScope, Unit>() { // from class: androidx.compose.material3.TabRowKt$ScrollableTabRowImp$1$1$1.2
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
                                            List $this$fastForEachIndexed$iv = tabPlaceables;
                                            SubcomposeMeasureScope subcomposeMeasureScope = $this$SubcomposeLayout;
                                            List<Dp> list = tabContentWidths;
                                            int index$iv2 = 0;
                                            int size4 = $this$fastForEachIndexed$iv.size();
                                            while (index$iv2 < size4) {
                                                Object item$iv2 = $this$fastForEachIndexed$iv.get(index$iv2);
                                                Placeable placeable2 = (Placeable) item$iv2;
                                                int index = index$iv2;
                                                Placeable.PlacementScope.placeRelative$default($this$layout, placeable2, left, 0, 0.0f, 4, null);
                                                tabPositions.add(new TabPosition(subcomposeMeasureScope.mo310toDpu2uoSUM(left), subcomposeMeasureScope.mo310toDpu2uoSUM(placeable2.getWidth()), list.get(index).m6108unboximpl(), null));
                                                left += placeable2.getWidth();
                                                index$iv2++;
                                                $this$fastForEachIndexed$iv = $this$fastForEachIndexed$iv;
                                            }
                                            List $this$fastForEach$iv3 = $this$SubcomposeLayout.subcompose(TabSlots.Divider, function26);
                                            long j2 = constraints;
                                            int i9 = layoutWidth;
                                            int i10 = layoutHeight;
                                            int index$iv3 = 0;
                                            for (int size5 = $this$fastForEach$iv3.size(); index$iv3 < size5; size5 = size5) {
                                                Object item$iv3 = $this$fastForEach$iv3.get(index$iv3);
                                                Measurable it2 = (Measurable) item$iv3;
                                                m6040copyZbe2FdA = Constraints.m6040copyZbe2FdA(j2, (r12 & 1) != 0 ? Constraints.m6052getMinWidthimpl(j2) : i9, (r12 & 2) != 0 ? Constraints.m6050getMaxWidthimpl(j2) : i9, (r12 & 4) != 0 ? Constraints.m6051getMinHeightimpl(j2) : 0, (r12 & 8) != 0 ? Constraints.m6049getMaxHeightimpl(j2) : 0);
                                                Placeable placeable3 = it2.mo5016measureBRTryo0(m6040copyZbe2FdA);
                                                Placeable.PlacementScope.placeRelative$default($this$layout, placeable3, 0, i10 - placeable3.getHeight(), 0.0f, 4, null);
                                                index$iv3++;
                                            }
                                            SubcomposeMeasureScope subcomposeMeasureScope2 = $this$SubcomposeLayout;
                                            TabSlots tabSlots = TabSlots.Indicator;
                                            final Function3<List<TabPosition>, Composer, Integer, Unit> function34 = function33;
                                            List $this$fastForEach$iv4 = subcomposeMeasureScope2.subcompose(tabSlots, ComposableLambdaKt.composableLambdaInstance(358596038, true, new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.TabRowKt.ScrollableTabRowImp.1.1.1.2.3
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
                                                    ComposerKt.sourceInformation($composer4, "C942@41500L23:TabRow.kt#uh7d8r");
                                                    if (($changed3 & 3) == 2 && $composer4.getSkipping()) {
                                                        $composer4.skipToGroupEnd();
                                                        return;
                                                    }
                                                    if (ComposerKt.isTraceInProgress()) {
                                                        ComposerKt.traceEventStart(358596038, $changed3, -1, "androidx.compose.material3.ScrollableTabRowImp.<anonymous>.<anonymous>.<anonymous>.<anonymous>.<anonymous> (TabRow.kt:942)");
                                                    }
                                                    function34.invoke(tabPositions, $composer4, 0);
                                                    if (ComposerKt.isTraceInProgress()) {
                                                        ComposerKt.traceEventEnd();
                                                    }
                                                }
                                            }));
                                            int i11 = layoutWidth;
                                            int i12 = layoutHeight;
                                            int size6 = $this$fastForEach$iv4.size();
                                            for (int index$iv4 = 0; index$iv4 < size6; index$iv4++) {
                                                Object item$iv4 = $this$fastForEach$iv4.get(index$iv4);
                                                Measurable it3 = (Measurable) item$iv4;
                                                Placeable.PlacementScope.placeRelative$default($this$layout, it3.mo5016measureBRTryo0(Constraints.INSTANCE.m6058fixedJhjzzOo(i11, i12)), 0, 0, 0.0f, 4, null);
                                            }
                                            scrollableTabData2.onLaidOut($this$SubcomposeLayout, padding, tabPositions, i8);
                                        }
                                    }, 4, null);
                                }
                            };
                            $composer3.updateRememberedValue(value$iv2);
                        } else {
                            value$iv2 = it$iv2;
                        }
                        $composer3.endReplaceableGroup();
                        SubcomposeLayoutKt.SubcomposeLayout(clipToBounds, (Function2) value$iv2, $composer3, 0, 0);
                        if (ComposerKt.isTraceInProgress()) {
                            ComposerKt.traceEventEnd();
                            return;
                        }
                        return;
                    }
                    $composer3.skipToGroupEnd();
                }
            }), $composer2, (($dirty >> 6) & 14) | 12582912 | (($dirty >> 3) & 896) | (($dirty >> 3) & 7168), 114);
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventEnd();
            }
            modifier3 = modifier2;
            contentColor3 = contentColor2;
            containerColor3 = containerColor2;
            edgePadding3 = edgePadding2;
            divider2 = divider;
        }
        ScopeUpdateScope endRestartGroup = $composer2.endRestartGroup();
        if (endRestartGroup != null) {
            final Modifier modifier4 = modifier3;
            final long j2 = containerColor3;
            final long j3 = contentColor3;
            final float f3 = edgePadding3;
            final Function2 function24 = divider2;
            endRestartGroup.updateScope(new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.TabRowKt$ScrollableTabRowImp$2
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
                    TabRowKt.m2368ScrollableTabRowImpqhFBPw4(selectedTabIndex, function3, modifier4, j2, j3, f3, function24, function22, scrollState, composer, RecomposeScopeImplKt.updateChangedFlags($changed | 1), i);
                }
            });
        }
    }
}
