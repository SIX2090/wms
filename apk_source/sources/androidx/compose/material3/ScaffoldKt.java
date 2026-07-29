package androidx.compose.material3;

import androidx.compose.foundation.layout.PaddingKt;
import androidx.compose.foundation.layout.PaddingValues;
import androidx.compose.foundation.layout.WindowInsets;
import androidx.compose.foundation.layout.WindowInsetsKt;
import androidx.compose.foundation.layout.WindowInsetsPaddingKt;
import androidx.compose.runtime.Composer;
import androidx.compose.runtime.ComposerKt;
import androidx.compose.runtime.CompositionLocalKt;
import androidx.compose.runtime.MutableState;
import androidx.compose.runtime.ProvidableCompositionLocal;
import androidx.compose.runtime.ProvidedValue;
import androidx.compose.runtime.RecomposeScopeImplKt;
import androidx.compose.runtime.ScopeUpdateScope;
import androidx.compose.runtime.SnapshotStateKt__SnapshotStateKt;
import androidx.compose.runtime.State;
import androidx.compose.runtime.internal.ComposableLambdaKt;
import androidx.compose.ui.Modifier;
import androidx.compose.ui.layout.Measurable;
import androidx.compose.ui.layout.MeasureResult;
import androidx.compose.ui.layout.MeasureScope;
import androidx.compose.ui.layout.Placeable;
import androidx.compose.ui.layout.SubcomposeLayoutKt;
import androidx.compose.ui.layout.SubcomposeMeasureScope;
import androidx.compose.ui.unit.Constraints;
import androidx.compose.ui.unit.ConstraintsKt;
import androidx.compose.ui.unit.Dp;
import androidx.compose.ui.unit.LayoutDirection;
import androidx.core.view.accessibility.AccessibilityEventCompat;
import androidx.profileinstaller.ProfileVerifier;
import java.util.ArrayList;
import java.util.List;
import kotlin.Metadata;
import kotlin.Unit;
import kotlin.collections.CollectionsKt;
import kotlin.jvm.functions.Function0;
import kotlin.jvm.functions.Function1;
import kotlin.jvm.functions.Function2;
import kotlin.jvm.functions.Function3;
import kotlin.jvm.internal.Intrinsics;

/* compiled from: Scaffold.kt */
@Metadata(d1 = {"\u0000X\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0010\u000b\n\u0002\b\n\n\u0002\u0010\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0018\u0002\n\u0002\b\u0005\n\u0002\u0018\u0002\n\u0002\b\u0004\n\u0002\u0018\u0002\n\u0002\b\b\u001a\u0087\u0001\u0010\u0013\u001a\u00020\u00142\u0006\u0010\u0015\u001a\u00020\u00162\u0011\u0010\u0017\u001a\r\u0012\u0004\u0012\u00020\u00140\u0018¢\u0006\u0002\b\u00192\u0017\u0010\u001a\u001a\u0013\u0012\u0004\u0012\u00020\u001c\u0012\u0004\u0012\u00020\u00140\u001b¢\u0006\u0002\b\u00192\u0011\u0010\u001d\u001a\r\u0012\u0004\u0012\u00020\u00140\u0018¢\u0006\u0002\b\u00192\u0011\u0010\u001e\u001a\r\u0012\u0004\u0012\u00020\u00140\u0018¢\u0006\u0002\b\u00192\u0006\u0010\u001f\u001a\u00020 2\u0011\u0010!\u001a\r\u0012\u0004\u0012\u00020\u00140\u0018¢\u0006\u0002\b\u0019H\u0003ø\u0001\u0000¢\u0006\u0004\b\"\u0010#\u001a±\u0001\u0010$\u001a\u00020\u00142\b\b\u0002\u0010%\u001a\u00020&2\u0013\b\u0002\u0010\u0017\u001a\r\u0012\u0004\u0012\u00020\u00140\u0018¢\u0006\u0002\b\u00192\u0013\b\u0002\u0010!\u001a\r\u0012\u0004\u0012\u00020\u00140\u0018¢\u0006\u0002\b\u00192\u0013\b\u0002\u0010'\u001a\r\u0012\u0004\u0012\u00020\u00140\u0018¢\u0006\u0002\b\u00192\u0013\b\u0002\u0010(\u001a\r\u0012\u0004\u0012\u00020\u00140\u0018¢\u0006\u0002\b\u00192\b\b\u0002\u0010)\u001a\u00020\u00162\b\b\u0002\u0010*\u001a\u00020+2\b\b\u0002\u0010,\u001a\u00020+2\b\b\u0002\u0010\u001f\u001a\u00020 2\u0017\u0010\u001a\u001a\u0013\u0012\u0004\u0012\u00020\u001c\u0012\u0004\u0012\u00020\u00140\u001b¢\u0006\u0002\b\u0019H\u0007ø\u0001\u0000¢\u0006\u0004\b-\u0010.\u001a\u0087\u0001\u0010/\u001a\u00020\u00142\u0006\u0010\u0015\u001a\u00020\u00162\u0011\u0010\u0017\u001a\r\u0012\u0004\u0012\u00020\u00140\u0018¢\u0006\u0002\b\u00192\u0017\u0010\u001a\u001a\u0013\u0012\u0004\u0012\u00020\u001c\u0012\u0004\u0012\u00020\u00140\u001b¢\u0006\u0002\b\u00192\u0011\u0010\u001d\u001a\r\u0012\u0004\u0012\u00020\u00140\u0018¢\u0006\u0002\b\u00192\u0011\u0010\u001e\u001a\r\u0012\u0004\u0012\u00020\u00140\u0018¢\u0006\u0002\b\u00192\u0006\u0010\u001f\u001a\u00020 2\u0011\u0010!\u001a\r\u0012\u0004\u0012\u00020\u00140\u0018¢\u0006\u0002\b\u0019H\u0003ø\u0001\u0000¢\u0006\u0004\b0\u0010#\u001a\u0087\u0001\u00101\u001a\u00020\u00142\u0006\u0010\u0015\u001a\u00020\u00162\u0011\u0010\u0017\u001a\r\u0012\u0004\u0012\u00020\u00140\u0018¢\u0006\u0002\b\u00192\u0017\u0010\u001a\u001a\u0013\u0012\u0004\u0012\u00020\u001c\u0012\u0004\u0012\u00020\u00140\u001b¢\u0006\u0002\b\u00192\u0011\u0010\u001d\u001a\r\u0012\u0004\u0012\u00020\u00140\u0018¢\u0006\u0002\b\u00192\u0011\u0010\u001e\u001a\r\u0012\u0004\u0012\u00020\u00140\u0018¢\u0006\u0002\b\u00192\u0006\u0010\u001f\u001a\u00020 2\u0011\u0010!\u001a\r\u0012\u0004\u0012\u00020\u00140\u0018¢\u0006\u0002\b\u0019H\u0003ø\u0001\u0000¢\u0006\u0004\b2\u0010#\"\u0010\u0010\u0000\u001a\u00020\u0001X\u0082\u0004¢\u0006\u0004\n\u0002\u0010\u0002\"\u001c\u0010\u0003\u001a\n\u0012\u0006\u0012\u0004\u0018\u00010\u00050\u0004X\u0080\u0004¢\u0006\b\n\u0000\u001a\u0004\b\u0006\u0010\u0007\"1\u0010\n\u001a\u00020\t2\u0006\u0010\b\u001a\u00020\t8G@GX\u0087\u008e\u0002¢\u0006\u0018\n\u0004\b\u0011\u0010\u0012\u0012\u0004\b\u000b\u0010\f\u001a\u0004\b\r\u0010\u000e\"\u0004\b\u000f\u0010\u0010\u0082\u0002\u0007\n\u0005\b¡\u001e0\u0001¨\u00063"}, d2 = {"FabSpacing", "Landroidx/compose/ui/unit/Dp;", "F", "LocalFabPlacement", "Landroidx/compose/runtime/ProvidableCompositionLocal;", "Landroidx/compose/material3/FabPlacement;", "getLocalFabPlacement", "()Landroidx/compose/runtime/ProvidableCompositionLocal;", "<set-?>", "", "ScaffoldSubcomposeInMeasureFix", "getScaffoldSubcomposeInMeasureFix$annotations", "()V", "getScaffoldSubcomposeInMeasureFix", "()Z", "setScaffoldSubcomposeInMeasureFix", "(Z)V", "ScaffoldSubcomposeInMeasureFix$delegate", "Landroidx/compose/runtime/MutableState;", "LegacyScaffoldLayout", "", "fabPosition", "Landroidx/compose/material3/FabPosition;", "topBar", "Lkotlin/Function0;", "Landroidx/compose/runtime/Composable;", "content", "Lkotlin/Function1;", "Landroidx/compose/foundation/layout/PaddingValues;", "snackbar", "fab", "contentWindowInsets", "Landroidx/compose/foundation/layout/WindowInsets;", "bottomBar", "LegacyScaffoldLayout-FMILGgc", "(ILkotlin/jvm/functions/Function2;Lkotlin/jvm/functions/Function3;Lkotlin/jvm/functions/Function2;Lkotlin/jvm/functions/Function2;Landroidx/compose/foundation/layout/WindowInsets;Lkotlin/jvm/functions/Function2;Landroidx/compose/runtime/Composer;I)V", "Scaffold", "modifier", "Landroidx/compose/ui/Modifier;", "snackbarHost", "floatingActionButton", "floatingActionButtonPosition", "containerColor", "Landroidx/compose/ui/graphics/Color;", "contentColor", "Scaffold-TvnljyQ", "(Landroidx/compose/ui/Modifier;Lkotlin/jvm/functions/Function2;Lkotlin/jvm/functions/Function2;Lkotlin/jvm/functions/Function2;Lkotlin/jvm/functions/Function2;IJJLandroidx/compose/foundation/layout/WindowInsets;Lkotlin/jvm/functions/Function3;Landroidx/compose/runtime/Composer;II)V", "ScaffoldLayout", "ScaffoldLayout-FMILGgc", "ScaffoldLayoutWithMeasureFix", "ScaffoldLayoutWithMeasureFix-FMILGgc", "material3_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class ScaffoldKt {
    private static final MutableState ScaffoldSubcomposeInMeasureFix$delegate = SnapshotStateKt__SnapshotStateKt.mutableStateOf$default(true, null, 2, null);
    private static final ProvidableCompositionLocal<FabPlacement> LocalFabPlacement = CompositionLocalKt.staticCompositionLocalOf(new Function0<FabPlacement>() { // from class: androidx.compose.material3.ScaffoldKt$LocalFabPlacement$1
        /* JADX WARN: Can't rename method to resolve collision */
        @Override // kotlin.jvm.functions.Function0
        public final FabPlacement invoke() {
            return null;
        }
    });
    private static final float FabSpacing = Dp.m6094constructorimpl(16);

    public static /* synthetic */ void getScaffoldSubcomposeInMeasureFix$annotations() {
    }

    /* renamed from: Scaffold-TvnljyQ, reason: not valid java name */
    public static final void m2119ScaffoldTvnljyQ(Modifier modifier, Function2<? super Composer, ? super Integer, Unit> function2, Function2<? super Composer, ? super Integer, Unit> function22, Function2<? super Composer, ? super Integer, Unit> function23, Function2<? super Composer, ? super Integer, Unit> function24, int floatingActionButtonPosition, long containerColor, long contentColor, WindowInsets contentWindowInsets, final Function3<? super PaddingValues, ? super Composer, ? super Integer, Unit> function3, Composer $composer, final int $changed, final int i) {
        Function2 function25;
        Function2 function26;
        Function2 function27;
        int i2;
        long j;
        Modifier.Companion modifier2;
        Function2 bottomBar;
        long containerColor2;
        long contentColor2;
        Function2 bottomBar2;
        final WindowInsets contentWindowInsets2;
        Function2 topBar;
        long containerColor3;
        Function2 snackbarHost;
        Function2 floatingActionButton;
        int floatingActionButtonPosition2;
        long contentColor3;
        int $dirty;
        Object value$iv;
        Object value$iv2;
        WindowInsets contentWindowInsets3;
        Composer $composer2;
        Modifier modifier3;
        int i3;
        int i4;
        int i5;
        Composer $composer3 = $composer.startRestartGroup(-1219521777);
        ComposerKt.sourceInformation($composer3, "C(Scaffold)P(7,9!1,8,5,6:c#material3.FabPosition,1:c#ui.graphics.Color,3:c#ui.graphics.Color,4)92@4736L11,93@4786L31,94@4876L19,97@4971L86,101@5129L212,100@5062L664:Scaffold.kt#uh7d8r");
        int $dirty2 = $changed;
        int i6 = i & 1;
        if (i6 != 0) {
            $dirty2 |= 6;
        } else if (($changed & 6) == 0) {
            $dirty2 |= $composer3.changed(modifier) ? 4 : 2;
        }
        int i7 = i & 2;
        if (i7 != 0) {
            $dirty2 |= 48;
            function25 = function2;
        } else if (($changed & 48) == 0) {
            function25 = function2;
            $dirty2 |= $composer3.changedInstance(function25) ? 32 : 16;
        } else {
            function25 = function2;
        }
        int i8 = i & 4;
        if (i8 != 0) {
            $dirty2 |= 384;
            function26 = function22;
        } else if (($changed & 384) == 0) {
            function26 = function22;
            $dirty2 |= $composer3.changedInstance(function26) ? 256 : 128;
        } else {
            function26 = function22;
        }
        int i9 = i & 8;
        if (i9 != 0) {
            $dirty2 |= 3072;
            function27 = function23;
        } else if (($changed & 3072) == 0) {
            function27 = function23;
            $dirty2 |= $composer3.changedInstance(function27) ? 2048 : 1024;
        } else {
            function27 = function23;
        }
        int i10 = i & 16;
        if (i10 != 0) {
            $dirty2 |= 24576;
        } else if (($changed & 24576) == 0) {
            $dirty2 |= $composer3.changedInstance(function24) ? 16384 : 8192;
        }
        int i11 = i & 32;
        if (i11 != 0) {
            $dirty2 |= ProfileVerifier.CompilationStatus.RESULT_CODE_ERROR_CANT_WRITE_PROFILE_VERIFICATION_RESULT_CACHE_FILE;
        } else if (($changed & ProfileVerifier.CompilationStatus.RESULT_CODE_ERROR_CANT_WRITE_PROFILE_VERIFICATION_RESULT_CACHE_FILE) == 0) {
            $dirty2 |= $composer3.changed(floatingActionButtonPosition) ? 131072 : 65536;
        }
        if (($changed & 1572864) == 0) {
            if ((i & 64) == 0) {
                i2 = i11;
                if ($composer3.changed(containerColor)) {
                    i5 = 1048576;
                    $dirty2 |= i5;
                }
            } else {
                i2 = i11;
            }
            i5 = 524288;
            $dirty2 |= i5;
        } else {
            i2 = i11;
        }
        if (($changed & 12582912) == 0) {
            if ((i & 128) == 0) {
                j = contentColor;
                if ($composer3.changed(j)) {
                    i4 = 8388608;
                    $dirty2 |= i4;
                }
            } else {
                j = contentColor;
            }
            i4 = 4194304;
            $dirty2 |= i4;
        } else {
            j = contentColor;
        }
        if (($changed & 100663296) == 0) {
            if ((i & 256) == 0 && $composer3.changed(contentWindowInsets)) {
                i3 = AccessibilityEventCompat.TYPE_VIEW_TARGETED_BY_SCROLL;
                $dirty2 |= i3;
            }
            i3 = 33554432;
            $dirty2 |= i3;
        }
        if ((i & 512) != 0) {
            $dirty2 |= 805306368;
        } else if (($changed & 805306368) == 0) {
            $dirty2 |= $composer3.changedInstance(function3) ? 536870912 : 268435456;
        }
        if (($dirty2 & 306783379) == 306783378 && $composer3.getSkipping()) {
            $composer3.skipToGroupEnd();
            modifier3 = modifier;
            floatingActionButton = function24;
            floatingActionButtonPosition2 = floatingActionButtonPosition;
            containerColor3 = containerColor;
            contentWindowInsets3 = contentWindowInsets;
            topBar = function25;
            bottomBar2 = function26;
            snackbarHost = function27;
            contentColor3 = j;
            $composer2 = $composer3;
        } else {
            $composer3.startDefaults();
            if (($changed & 1) == 0 || $composer3.getDefaultsInvalid()) {
                modifier2 = i6 != 0 ? Modifier.INSTANCE : modifier;
                Function2 topBar2 = i7 != 0 ? ComposableSingletons$ScaffoldKt.INSTANCE.m1767getLambda1$material3_release() : function25;
                Function2 bottomBar3 = i8 != 0 ? ComposableSingletons$ScaffoldKt.INSTANCE.m1768getLambda2$material3_release() : function26;
                Function2 snackbarHost2 = i9 != 0 ? ComposableSingletons$ScaffoldKt.INSTANCE.m1769getLambda3$material3_release() : function27;
                Function2 floatingActionButton2 = i10 != 0 ? ComposableSingletons$ScaffoldKt.INSTANCE.m1770getLambda4$material3_release() : function24;
                int floatingActionButtonPosition3 = i2 != 0 ? FabPosition.INSTANCE.m1896getEndERTFSPs() : floatingActionButtonPosition;
                if ((i & 64) != 0) {
                    $dirty2 &= -3670017;
                    bottomBar = bottomBar3;
                    containerColor2 = MaterialTheme.INSTANCE.getColorScheme($composer3, 6).getBackground();
                } else {
                    bottomBar = bottomBar3;
                    containerColor2 = containerColor;
                }
                if ((i & 128) != 0) {
                    contentColor2 = ColorSchemeKt.m1732contentColorForek8zF_U(containerColor2, $composer3, ($dirty2 >> 18) & 14);
                    $dirty2 &= -29360129;
                } else {
                    contentColor2 = j;
                }
                if ((i & 256) != 0) {
                    bottomBar2 = bottomBar;
                    topBar = topBar2;
                    containerColor3 = containerColor2;
                    snackbarHost = snackbarHost2;
                    floatingActionButton = floatingActionButton2;
                    floatingActionButtonPosition2 = floatingActionButtonPosition3;
                    contentWindowInsets2 = ScaffoldDefaults.INSTANCE.getContentWindowInsets($composer3, 6);
                    contentColor3 = contentColor2;
                    $dirty = $dirty2 & (-234881025);
                } else {
                    bottomBar2 = bottomBar;
                    contentWindowInsets2 = contentWindowInsets;
                    topBar = topBar2;
                    containerColor3 = containerColor2;
                    snackbarHost = snackbarHost2;
                    floatingActionButton = floatingActionButton2;
                    floatingActionButtonPosition2 = floatingActionButtonPosition3;
                    contentColor3 = contentColor2;
                    $dirty = $dirty2;
                }
            } else {
                $composer3.skipToGroupEnd();
                if ((i & 64) != 0) {
                    $dirty2 &= -3670017;
                }
                if ((i & 128) != 0) {
                    $dirty2 &= -29360129;
                }
                if ((i & 256) != 0) {
                    floatingActionButton = function24;
                    floatingActionButtonPosition2 = floatingActionButtonPosition;
                    containerColor3 = containerColor;
                    topBar = function25;
                    bottomBar2 = function26;
                    snackbarHost = function27;
                    contentColor3 = j;
                    contentWindowInsets2 = contentWindowInsets;
                    $dirty = $dirty2 & (-234881025);
                    modifier2 = modifier;
                } else {
                    modifier2 = modifier;
                    floatingActionButton = function24;
                    floatingActionButtonPosition2 = floatingActionButtonPosition;
                    containerColor3 = containerColor;
                    topBar = function25;
                    bottomBar2 = function26;
                    snackbarHost = function27;
                    contentColor3 = j;
                    contentWindowInsets2 = contentWindowInsets;
                    $dirty = $dirty2;
                }
            }
            $composer3.endDefaults();
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventStart(-1219521777, $dirty, -1, "androidx.compose.material3.Scaffold (Scaffold.kt:96)");
            }
            $composer3.startReplaceableGroup(-889185358);
            ComposerKt.sourceInformation($composer3, "CC(remember):Scaffold.kt#9igjgp");
            boolean invalid$iv = (((234881024 & $dirty) ^ 100663296) > 67108864 && $composer3.changed(contentWindowInsets2)) || ($dirty & 100663296) == 67108864;
            Object it$iv = $composer3.rememberedValue();
            if (invalid$iv || it$iv == Composer.INSTANCE.getEmpty()) {
                value$iv = new MutableWindowInsets(contentWindowInsets2);
                $composer3.updateRememberedValue(value$iv);
            } else {
                value$iv = it$iv;
            }
            final MutableWindowInsets safeInsets = (MutableWindowInsets) value$iv;
            $composer3.endReplaceableGroup();
            $composer3.startReplaceableGroup(-889185200);
            ComposerKt.sourceInformation($composer3, "CC(remember):Scaffold.kt#9igjgp");
            boolean invalid$iv2 = $composer3.changed(safeInsets) | ((((234881024 & $dirty) ^ 100663296) > 67108864 && $composer3.changed(contentWindowInsets2)) || (100663296 & $dirty) == 67108864);
            Object it$iv2 = $composer3.rememberedValue();
            if (invalid$iv2 || it$iv2 == Composer.INSTANCE.getEmpty()) {
                value$iv2 = new Function1<WindowInsets, Unit>() { // from class: androidx.compose.material3.ScaffoldKt$Scaffold$1$1
                    /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
                    {
                        super(1);
                    }

                    @Override // kotlin.jvm.functions.Function1
                    public /* bridge */ /* synthetic */ Unit invoke(WindowInsets windowInsets) {
                        invoke2(windowInsets);
                        return Unit.INSTANCE;
                    }

                    /* renamed from: invoke, reason: avoid collision after fix types in other method */
                    public final void invoke2(WindowInsets consumedWindowInsets) {
                        MutableWindowInsets.this.setInsets(WindowInsetsKt.exclude(contentWindowInsets2, consumedWindowInsets));
                    }
                };
                $composer3.updateRememberedValue(value$iv2);
            } else {
                value$iv2 = it$iv2;
            }
            $composer3.endReplaceableGroup();
            final int i12 = floatingActionButtonPosition2;
            final Function2 function28 = topBar;
            final Function2 function29 = snackbarHost;
            final Function2 function210 = floatingActionButton;
            final Function2 function211 = bottomBar2;
            contentWindowInsets3 = contentWindowInsets2;
            $composer2 = $composer3;
            SurfaceKt.m2316SurfaceT9BRK9s(WindowInsetsPaddingKt.onConsumedWindowInsetsChanged(modifier2, (Function1) value$iv2), null, containerColor3, contentColor3, 0.0f, 0.0f, null, ComposableLambdaKt.composableLambda($composer3, -1979205334, true, new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.ScaffoldKt$Scaffold$2
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

                public final void invoke(Composer $composer4, int $changed2) {
                    ComposerKt.sourceInformation($composer4, "C107@5422L298:Scaffold.kt#uh7d8r");
                    if (($changed2 & 3) != 2 || !$composer4.getSkipping()) {
                        if (ComposerKt.isTraceInProgress()) {
                            ComposerKt.traceEventStart(-1979205334, $changed2, -1, "androidx.compose.material3.Scaffold.<anonymous> (Scaffold.kt:107)");
                        }
                        ScaffoldKt.m2120ScaffoldLayoutFMILGgc(i12, function28, function3, function29, function210, safeInsets, function211, $composer4, 0);
                        if (ComposerKt.isTraceInProgress()) {
                            ComposerKt.traceEventEnd();
                            return;
                        }
                        return;
                    }
                    $composer4.skipToGroupEnd();
                }
            }), $composer3, (($dirty >> 12) & 896) | 12582912 | (($dirty >> 12) & 7168), 114);
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventEnd();
            }
            modifier3 = modifier2;
        }
        ScopeUpdateScope endRestartGroup = $composer2.endRestartGroup();
        if (endRestartGroup != null) {
            final Modifier modifier4 = modifier3;
            final Function2 function212 = topBar;
            final Function2 function213 = bottomBar2;
            final Function2 function214 = snackbarHost;
            final Function2 function215 = floatingActionButton;
            final int i13 = floatingActionButtonPosition2;
            final long j2 = containerColor3;
            final long j3 = contentColor3;
            final WindowInsets windowInsets = contentWindowInsets3;
            endRestartGroup.updateScope(new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.ScaffoldKt$Scaffold$3
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

                public final void invoke(Composer composer, int i14) {
                    ScaffoldKt.m2119ScaffoldTvnljyQ(Modifier.this, function212, function213, function214, function215, i13, j2, j3, windowInsets, function3, composer, RecomposeScopeImplKt.updateChangedFlags($changed | 1), i);
                }
            });
        }
    }

    /* JADX INFO: Access modifiers changed from: private */
    /* renamed from: ScaffoldLayout-FMILGgc, reason: not valid java name */
    public static final void m2120ScaffoldLayoutFMILGgc(final int fabPosition, final Function2<? super Composer, ? super Integer, Unit> function2, final Function3<? super PaddingValues, ? super Composer, ? super Integer, Unit> function3, final Function2<? super Composer, ? super Integer, Unit> function22, final Function2<? super Composer, ? super Integer, Unit> function23, final WindowInsets contentWindowInsets, final Function2<? super Composer, ? super Integer, Unit> function24, Composer $composer, final int $changed) {
        Composer $composer2 = $composer.startRestartGroup(-975511942);
        ComposerKt.sourceInformation($composer2, "C(ScaffoldLayout)P(4:c#material3.FabPosition,6,1,5,3,2):Scaffold.kt#uh7d8r");
        int $dirty = $changed;
        if (($changed & 6) == 0) {
            $dirty |= $composer2.changed(fabPosition) ? 4 : 2;
        }
        if (($changed & 48) == 0) {
            $dirty |= $composer2.changedInstance(function2) ? 32 : 16;
        }
        if (($changed & 384) == 0) {
            $dirty |= $composer2.changedInstance(function3) ? 256 : 128;
        }
        if (($changed & 3072) == 0) {
            $dirty |= $composer2.changedInstance(function22) ? 2048 : 1024;
        }
        if (($changed & 24576) == 0) {
            $dirty |= $composer2.changedInstance(function23) ? 16384 : 8192;
        }
        if ((196608 & $changed) == 0) {
            $dirty |= $composer2.changed(contentWindowInsets) ? 131072 : 65536;
        }
        if ((1572864 & $changed) == 0) {
            $dirty |= $composer2.changedInstance(function24) ? 1048576 : 524288;
        }
        if ((599187 & $dirty) != 599186 || !$composer2.getSkipping()) {
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventStart(-975511942, $dirty, -1, "androidx.compose.material3.ScaffoldLayout (Scaffold.kt:141)");
            }
            if (getScaffoldSubcomposeInMeasureFix()) {
                $composer2.startReplaceableGroup(-915303637);
                ComposerKt.sourceInformation($composer2, "143@6712L283");
                m2121ScaffoldLayoutWithMeasureFixFMILGgc(fabPosition, function2, function3, function22, function23, contentWindowInsets, function24, $composer2, ($dirty & 14) | ($dirty & 112) | ($dirty & 896) | ($dirty & 7168) | (57344 & $dirty) | (458752 & $dirty) | (3670016 & $dirty));
                $composer2.endReplaceableGroup();
            } else {
                $composer2.startReplaceableGroup(-915303332);
                ComposerKt.sourceInformation($composer2, "153@7017L275");
                m2118LegacyScaffoldLayoutFMILGgc(fabPosition, function2, function3, function22, function23, contentWindowInsets, function24, $composer2, ($dirty & 14) | ($dirty & 112) | ($dirty & 896) | ($dirty & 7168) | (57344 & $dirty) | (458752 & $dirty) | (3670016 & $dirty));
                $composer2.endReplaceableGroup();
            }
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventEnd();
            }
        } else {
            $composer2.skipToGroupEnd();
        }
        ScopeUpdateScope endRestartGroup = $composer2.endRestartGroup();
        if (endRestartGroup != null) {
            endRestartGroup.updateScope(new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.ScaffoldKt$ScaffoldLayout$1
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
                    ScaffoldKt.m2120ScaffoldLayoutFMILGgc(fabPosition, function2, function3, function22, function23, contentWindowInsets, function24, composer, RecomposeScopeImplKt.updateChangedFlags($changed | 1));
                }
            });
        }
    }

    /* JADX INFO: Access modifiers changed from: private */
    /* renamed from: ScaffoldLayoutWithMeasureFix-FMILGgc, reason: not valid java name */
    public static final void m2121ScaffoldLayoutWithMeasureFixFMILGgc(final int fabPosition, final Function2<? super Composer, ? super Integer, Unit> function2, final Function3<? super PaddingValues, ? super Composer, ? super Integer, Unit> function3, final Function2<? super Composer, ? super Integer, Unit> function22, final Function2<? super Composer, ? super Integer, Unit> function23, final WindowInsets contentWindowInsets, final Function2<? super Composer, ? super Integer, Unit> function24, Composer $composer, final int $changed) {
        int i;
        Composer $composer2 = $composer.startRestartGroup(-2037614249);
        ComposerKt.sourceInformation($composer2, "C(ScaffoldLayoutWithMeasureFix)P(4:c#material3.FabPosition,6,1,5,3,2)178@7738L6567,178@7721L6584:Scaffold.kt#uh7d8r");
        int $dirty = $changed;
        if (($changed & 6) == 0) {
            $dirty |= $composer2.changed(fabPosition) ? 4 : 2;
        }
        if (($changed & 48) == 0) {
            $dirty |= $composer2.changedInstance(function2) ? 32 : 16;
        }
        if (($changed & 384) == 0) {
            $dirty |= $composer2.changedInstance(function3) ? 256 : 128;
        }
        if (($changed & 3072) == 0) {
            $dirty |= $composer2.changedInstance(function22) ? 2048 : 1024;
        }
        if (($changed & 24576) == 0) {
            $dirty |= $composer2.changedInstance(function23) ? 16384 : 8192;
        }
        if ((196608 & $changed) == 0) {
            $dirty |= $composer2.changed(contentWindowInsets) ? 131072 : 65536;
        }
        if (($changed & 1572864) == 0) {
            $dirty |= $composer2.changedInstance(function24) ? 1048576 : 524288;
        }
        if (($dirty & 599187) != 599186 || !$composer2.getSkipping()) {
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventStart(-2037614249, $dirty, -1, "androidx.compose.material3.ScaffoldLayoutWithMeasureFix (Scaffold.kt:177)");
            }
            $composer2.startReplaceableGroup(-273325894);
            ComposerKt.sourceInformation($composer2, "CC(remember):Scaffold.kt#9igjgp");
            boolean invalid$iv = (($dirty & 112) == 32) | (($dirty & 7168) == 2048) | ((458752 & $dirty) == 131072) | ((57344 & $dirty) == 16384) | (($dirty & 14) == 4) | ((3670016 & $dirty) == 1048576) | (($dirty & 896) == 256);
            Object value$iv = $composer2.rememberedValue();
            if (invalid$iv || value$iv == Composer.INSTANCE.getEmpty()) {
                i = 0;
                value$iv = new Function2<SubcomposeMeasureScope, Constraints, MeasureResult>() { // from class: androidx.compose.material3.ScaffoldKt$ScaffoldLayoutWithMeasureFix$1$1
                    /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
                    /* JADX WARN: Multi-variable type inference failed */
                    {
                        super(2);
                    }

                    @Override // kotlin.jvm.functions.Function2
                    public /* bridge */ /* synthetic */ MeasureResult invoke(SubcomposeMeasureScope subcomposeMeasureScope, Constraints constraints) {
                        return m2126invoke0kLqBqw(subcomposeMeasureScope, constraints.getValue());
                    }

                    /* renamed from: invoke-0kLqBqw, reason: not valid java name */
                    public final MeasureResult m2126invoke0kLqBqw(final SubcomposeMeasureScope $this$SubcomposeLayout, long constraints) {
                        long looseConstraints;
                        Object maxElem$iv;
                        Object maxElem$iv2;
                        Object maxElem$iv3;
                        FabPlacement fabPlacement;
                        Object maxElem$iv4;
                        Integer num;
                        float f;
                        int i2;
                        float f2;
                        Object maxElem$iv5;
                        Object maxElem$iv6;
                        int fabLeftOffset;
                        float f3;
                        float f4;
                        float f5;
                        float f6;
                        final int layoutWidth = Constraints.m6050getMaxWidthimpl(constraints);
                        final int layoutHeight = Constraints.m6049getMaxHeightimpl(constraints);
                        looseConstraints = Constraints.m6040copyZbe2FdA(constraints, (r12 & 1) != 0 ? Constraints.m6052getMinWidthimpl(constraints) : 0, (r12 & 2) != 0 ? Constraints.m6050getMaxWidthimpl(constraints) : 0, (r12 & 4) != 0 ? Constraints.m6051getMinHeightimpl(constraints) : 0, (r12 & 8) != 0 ? Constraints.m6049getMaxHeightimpl(constraints) : 0);
                        List $this$fastMap$iv = $this$SubcomposeLayout.subcompose(ScaffoldLayoutContent.TopBar, function2);
                        List target$iv = new ArrayList($this$fastMap$iv.size());
                        int size = $this$fastMap$iv.size();
                        for (int index$iv$iv = 0; index$iv$iv < size; index$iv$iv++) {
                            Object item$iv$iv = $this$fastMap$iv.get(index$iv$iv);
                            Measurable it = (Measurable) item$iv$iv;
                            target$iv.add(it.mo5016measureBRTryo0(looseConstraints));
                        }
                        final List topBarPlaceables = target$iv;
                        if (topBarPlaceables.isEmpty()) {
                            maxElem$iv = null;
                        } else {
                            maxElem$iv = topBarPlaceables.get(0);
                            Placeable it2 = (Placeable) maxElem$iv;
                            int maxValue$iv = it2.getHeight();
                            int i$iv = 1;
                            int lastIndex = CollectionsKt.getLastIndex(topBarPlaceables);
                            if (1 <= lastIndex) {
                                while (true) {
                                    Object e$iv = topBarPlaceables.get(i$iv);
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
                        final int topBarHeight = placeable != null ? placeable.getHeight() : 0;
                        List $this$fastMap$iv2 = $this$SubcomposeLayout.subcompose(ScaffoldLayoutContent.Snackbar, function22);
                        WindowInsets windowInsets = contentWindowInsets;
                        int $i$f$fastMap = 0;
                        List target$iv2 = new ArrayList($this$fastMap$iv2.size());
                        List $this$fastForEach$iv$iv = $this$fastMap$iv2;
                        int index$iv$iv2 = 0;
                        int size2 = $this$fastForEach$iv$iv.size();
                        while (index$iv$iv2 < size2) {
                            Object item$iv$iv2 = $this$fastForEach$iv$iv.get(index$iv$iv2);
                            Measurable it4 = (Measurable) item$iv$iv2;
                            List $this$fastMap$iv3 = $this$fastMap$iv2;
                            int $i$f$fastMap2 = $i$f$fastMap;
                            int leftInset = windowInsets.getLeft($this$SubcomposeLayout, $this$SubcomposeLayout.getLayoutDirection());
                            List $this$fastForEach$iv$iv2 = $this$fastForEach$iv$iv;
                            int rightInset = windowInsets.getRight($this$SubcomposeLayout, $this$SubcomposeLayout.getLayoutDirection());
                            int bottomInset = windowInsets.getBottom($this$SubcomposeLayout);
                            WindowInsets windowInsets2 = windowInsets;
                            int i3 = (-leftInset) - rightInset;
                            int leftInset2 = -bottomInset;
                            target$iv2.add(it4.mo5016measureBRTryo0(ConstraintsKt.m6066offsetNN6EwU(looseConstraints, i3, leftInset2)));
                            index$iv$iv2++;
                            $this$fastMap$iv2 = $this$fastMap$iv3;
                            $i$f$fastMap = $i$f$fastMap2;
                            $this$fastForEach$iv$iv = $this$fastForEach$iv$iv2;
                            windowInsets = windowInsets2;
                        }
                        final List snackbarPlaceables = target$iv2;
                        if (snackbarPlaceables.isEmpty()) {
                            maxElem$iv2 = null;
                        } else {
                            maxElem$iv2 = snackbarPlaceables.get(0);
                            Placeable it5 = (Placeable) maxElem$iv2;
                            int maxValue$iv2 = it5.getHeight();
                            int i$iv2 = 1;
                            int lastIndex2 = CollectionsKt.getLastIndex(snackbarPlaceables);
                            if (1 <= lastIndex2) {
                                while (true) {
                                    Object e$iv2 = snackbarPlaceables.get(i$iv2);
                                    Placeable it6 = (Placeable) e$iv2;
                                    int v$iv2 = it6.getHeight();
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
                        int snackbarHeight = placeable2 != null ? placeable2.getHeight() : 0;
                        if (snackbarPlaceables.isEmpty()) {
                            maxElem$iv3 = null;
                        } else {
                            maxElem$iv3 = snackbarPlaceables.get(0);
                            Placeable it7 = (Placeable) maxElem$iv3;
                            int maxValue$iv3 = it7.getWidth();
                            int i$iv3 = 1;
                            int lastIndex3 = CollectionsKt.getLastIndex(snackbarPlaceables);
                            if (1 <= lastIndex3) {
                                while (true) {
                                    Object e$iv3 = snackbarPlaceables.get(i$iv3);
                                    Placeable it8 = (Placeable) e$iv3;
                                    int v$iv3 = it8.getWidth();
                                    if (maxValue$iv3 < v$iv3) {
                                        maxElem$iv3 = e$iv3;
                                        maxValue$iv3 = v$iv3;
                                    }
                                    if (i$iv3 == lastIndex3) {
                                        break;
                                    }
                                    i$iv3++;
                                }
                            }
                        }
                        Placeable placeable3 = (Placeable) maxElem$iv3;
                        final int snackbarWidth = placeable3 != null ? placeable3.getWidth() : 0;
                        List $this$fastMapNotNull$iv = $this$SubcomposeLayout.subcompose(ScaffoldLayoutContent.Fab, function23);
                        WindowInsets windowInsets3 = contentWindowInsets;
                        int $i$f$fastMapNotNull = 0;
                        List target$iv3 = new ArrayList($this$fastMapNotNull$iv.size());
                        List $this$fastForEach$iv$iv3 = $this$fastMapNotNull$iv;
                        int index$iv$iv3 = 0;
                        int size3 = $this$fastForEach$iv$iv3.size();
                        while (index$iv$iv3 < size3) {
                            Object item$iv$iv3 = $this$fastForEach$iv$iv3.get(index$iv$iv3);
                            Measurable measurable = (Measurable) item$iv$iv3;
                            List $this$fastMapNotNull$iv2 = $this$fastMapNotNull$iv;
                            int $i$f$fastMapNotNull2 = $i$f$fastMapNotNull;
                            int leftInset3 = windowInsets3.getLeft($this$SubcomposeLayout, $this$SubcomposeLayout.getLayoutDirection());
                            List $this$fastForEach$iv$iv4 = $this$fastForEach$iv$iv3;
                            int rightInset2 = windowInsets3.getRight($this$SubcomposeLayout, $this$SubcomposeLayout.getLayoutDirection());
                            int bottomInset2 = windowInsets3.getBottom($this$SubcomposeLayout);
                            WindowInsets windowInsets4 = windowInsets3;
                            int i4 = (-leftInset3) - rightInset2;
                            int leftInset4 = -bottomInset2;
                            Placeable it9 = measurable.mo5016measureBRTryo0(ConstraintsKt.m6066offsetNN6EwU(looseConstraints, i4, leftInset4));
                            if (!((it9.getHeight() == 0 || it9.getWidth() == 0) ? false : true)) {
                                it9 = null;
                            }
                            if (it9 != null) {
                                target$iv3.add(it9);
                            }
                            index$iv$iv3++;
                            $this$fastMapNotNull$iv = $this$fastMapNotNull$iv2;
                            $i$f$fastMapNotNull = $i$f$fastMapNotNull2;
                            $this$fastForEach$iv$iv3 = $this$fastForEach$iv$iv4;
                            windowInsets3 = windowInsets4;
                        }
                        final List fabPlaceables = target$iv3;
                        if (fabPlaceables.isEmpty()) {
                            fabPlacement = null;
                        } else {
                            if (fabPlaceables.isEmpty()) {
                                maxElem$iv5 = null;
                            } else {
                                maxElem$iv5 = fabPlaceables.get(0);
                                Placeable it10 = (Placeable) maxElem$iv5;
                                int maxValue$iv4 = it10.getWidth();
                                int i$iv4 = 1;
                                int lastIndex4 = CollectionsKt.getLastIndex(fabPlaceables);
                                if (1 <= lastIndex4) {
                                    while (true) {
                                        Object e$iv4 = fabPlaceables.get(i$iv4);
                                        Placeable it11 = (Placeable) e$iv4;
                                        int v$iv4 = it11.getWidth();
                                        if (maxValue$iv4 < v$iv4) {
                                            maxElem$iv5 = e$iv4;
                                            maxValue$iv4 = v$iv4;
                                        }
                                        if (i$iv4 == lastIndex4) {
                                            break;
                                        }
                                        i$iv4++;
                                    }
                                }
                            }
                            Intrinsics.checkNotNull(maxElem$iv5);
                            int fabWidth = ((Placeable) maxElem$iv5).getWidth();
                            if (fabPlaceables.isEmpty()) {
                                maxElem$iv6 = null;
                            } else {
                                maxElem$iv6 = fabPlaceables.get(0);
                                Placeable it12 = (Placeable) maxElem$iv6;
                                int maxValue$iv5 = it12.getHeight();
                                int i$iv5 = 1;
                                int lastIndex5 = CollectionsKt.getLastIndex(fabPlaceables);
                                if (1 <= lastIndex5) {
                                    while (true) {
                                        Object e$iv5 = fabPlaceables.get(i$iv5);
                                        Placeable it13 = (Placeable) e$iv5;
                                        int v$iv5 = it13.getHeight();
                                        if (maxValue$iv5 < v$iv5) {
                                            maxElem$iv6 = e$iv5;
                                            maxValue$iv5 = v$iv5;
                                        }
                                        if (i$iv5 == lastIndex5) {
                                            break;
                                        }
                                        i$iv5++;
                                    }
                                }
                            }
                            Intrinsics.checkNotNull(maxElem$iv6);
                            int fabHeight = ((Placeable) maxElem$iv6).getHeight();
                            int i5 = fabPosition;
                            if (!FabPosition.m1891equalsimpl0(i5, FabPosition.INSTANCE.m1898getStartERTFSPs())) {
                                if (!(FabPosition.m1891equalsimpl0(i5, FabPosition.INSTANCE.m1896getEndERTFSPs()) ? true : FabPosition.m1891equalsimpl0(i5, FabPosition.INSTANCE.m1897getEndOverlayERTFSPs()))) {
                                    fabLeftOffset = (layoutWidth - fabWidth) / 2;
                                } else if ($this$SubcomposeLayout.getLayoutDirection() == LayoutDirection.Ltr) {
                                    f4 = ScaffoldKt.FabSpacing;
                                    fabLeftOffset = (layoutWidth - $this$SubcomposeLayout.mo307roundToPx0680j_4(f4)) - fabWidth;
                                } else {
                                    f3 = ScaffoldKt.FabSpacing;
                                    fabLeftOffset = $this$SubcomposeLayout.mo307roundToPx0680j_4(f3);
                                }
                            } else if ($this$SubcomposeLayout.getLayoutDirection() == LayoutDirection.Ltr) {
                                f6 = ScaffoldKt.FabSpacing;
                                fabLeftOffset = $this$SubcomposeLayout.mo307roundToPx0680j_4(f6);
                            } else {
                                f5 = ScaffoldKt.FabSpacing;
                                fabLeftOffset = (layoutWidth - $this$SubcomposeLayout.mo307roundToPx0680j_4(f5)) - fabWidth;
                            }
                            fabPlacement = new FabPlacement(fabLeftOffset, fabWidth, fabHeight);
                        }
                        final FabPlacement fabPlacement2 = fabPlacement;
                        ScaffoldLayoutContent scaffoldLayoutContent = ScaffoldLayoutContent.BottomBar;
                        final Function2<Composer, Integer, Unit> function25 = function24;
                        List $this$fastMap$iv4 = $this$SubcomposeLayout.subcompose(scaffoldLayoutContent, ComposableLambdaKt.composableLambdaInstance(1843374446, true, new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.ScaffoldKt$ScaffoldLayoutWithMeasureFix$1$1$bottomBarPlaceables$1
                            /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
                            /* JADX WARN: Multi-variable type inference failed */
                            {
                                super(2);
                            }

                            @Override // kotlin.jvm.functions.Function2
                            public /* bridge */ /* synthetic */ Unit invoke(Composer composer, Integer num2) {
                                invoke(composer, num2.intValue());
                                return Unit.INSTANCE;
                            }

                            public final void invoke(Composer $composer3, int $changed2) {
                                ComposerKt.sourceInformation($composer3, "C258@11166L132:Scaffold.kt#uh7d8r");
                                if (($changed2 & 3) != 2 || !$composer3.getSkipping()) {
                                    if (ComposerKt.isTraceInProgress()) {
                                        ComposerKt.traceEventStart(1843374446, $changed2, -1, "androidx.compose.material3.ScaffoldLayoutWithMeasureFix.<anonymous>.<anonymous>.<anonymous> (Scaffold.kt:258)");
                                    }
                                    CompositionLocalKt.CompositionLocalProvider(ScaffoldKt.getLocalFabPlacement().provides(FabPlacement.this), function25, $composer3, ProvidedValue.$stable | 0);
                                    if (ComposerKt.isTraceInProgress()) {
                                        ComposerKt.traceEventEnd();
                                        return;
                                    }
                                    return;
                                }
                                $composer3.skipToGroupEnd();
                            }
                        }));
                        int $i$f$fastMap3 = 0;
                        List target$iv4 = new ArrayList($this$fastMap$iv4.size());
                        int index$iv$iv4 = 0;
                        int size4 = $this$fastMap$iv4.size();
                        while (index$iv$iv4 < size4) {
                            Object item$iv$iv4 = $this$fastMap$iv4.get(index$iv$iv4);
                            int $i$f$fastMap4 = $i$f$fastMap3;
                            Measurable it14 = (Measurable) item$iv$iv4;
                            target$iv4.add(it14.mo5016measureBRTryo0(looseConstraints));
                            index$iv$iv4++;
                            $this$fastMap$iv4 = $this$fastMap$iv4;
                            $i$f$fastMap3 = $i$f$fastMap4;
                        }
                        final List bottomBarPlaceables = target$iv4;
                        if (bottomBarPlaceables.isEmpty()) {
                            maxElem$iv4 = null;
                        } else {
                            maxElem$iv4 = bottomBarPlaceables.get(0);
                            Placeable it15 = (Placeable) maxElem$iv4;
                            int maxValue$iv6 = it15.getHeight();
                            int i$iv6 = 1;
                            int lastIndex6 = CollectionsKt.getLastIndex(bottomBarPlaceables);
                            if (1 <= lastIndex6) {
                                while (true) {
                                    Object e$iv6 = bottomBarPlaceables.get(i$iv6);
                                    Placeable it16 = (Placeable) e$iv6;
                                    int height = it16.getHeight();
                                    if (maxValue$iv6 < height) {
                                        maxElem$iv4 = e$iv6;
                                        maxValue$iv6 = height;
                                    }
                                    if (i$iv6 == lastIndex6) {
                                        break;
                                    }
                                    i$iv6++;
                                }
                            }
                        }
                        Placeable placeable4 = (Placeable) maxElem$iv4;
                        final Integer bottomBarHeight = placeable4 != null ? Integer.valueOf(placeable4.getHeight()) : null;
                        if (fabPlacement2 != null) {
                            int i6 = fabPosition;
                            WindowInsets windowInsets5 = contentWindowInsets;
                            if (bottomBarHeight == null || FabPosition.m1891equalsimpl0(i6, FabPosition.INSTANCE.m1897getEndOverlayERTFSPs())) {
                                int height2 = fabPlacement2.getHeight();
                                f = ScaffoldKt.FabSpacing;
                                i2 = height2 + $this$SubcomposeLayout.mo307roundToPx0680j_4(f) + windowInsets5.getBottom($this$SubcomposeLayout);
                            } else {
                                int intValue = bottomBarHeight.intValue() + fabPlacement2.getHeight();
                                f2 = ScaffoldKt.FabSpacing;
                                i2 = intValue + $this$SubcomposeLayout.mo307roundToPx0680j_4(f2);
                            }
                            num = Integer.valueOf(i2);
                        } else {
                            num = null;
                        }
                        final Integer fabOffsetFromBottom = num;
                        final int snackbarOffsetFromBottom = snackbarHeight != 0 ? snackbarHeight + (fabOffsetFromBottom != null ? fabOffsetFromBottom.intValue() : bottomBarHeight != null ? bottomBarHeight.intValue() : contentWindowInsets.getBottom($this$SubcomposeLayout)) : 0;
                        ScaffoldLayoutContent scaffoldLayoutContent2 = ScaffoldLayoutContent.MainContent;
                        final WindowInsets windowInsets6 = contentWindowInsets;
                        final Function3<PaddingValues, Composer, Integer, Unit> function32 = function3;
                        List $this$fastMap$iv5 = $this$SubcomposeLayout.subcompose(scaffoldLayoutContent2, ComposableLambdaKt.composableLambdaInstance(1655277373, true, new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.ScaffoldKt$ScaffoldLayoutWithMeasureFix$1$1$bodyContentPlaceables$1
                            /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
                            /* JADX WARN: Multi-variable type inference failed */
                            {
                                super(2);
                            }

                            @Override // kotlin.jvm.functions.Function2
                            public /* bridge */ /* synthetic */ Unit invoke(Composer composer, Integer num2) {
                                invoke(composer, num2.intValue());
                                return Unit.INSTANCE;
                            }

                            public final void invoke(Composer $composer3, int $changed2) {
                                float f7;
                                float bottom;
                                ComposerKt.sourceInformation($composer3, "C302@13090L21:Scaffold.kt#uh7d8r");
                                if (($changed2 & 3) != 2 || !$composer3.getSkipping()) {
                                    if (ComposerKt.isTraceInProgress()) {
                                        ComposerKt.traceEventStart(1655277373, $changed2, -1, "androidx.compose.material3.ScaffoldLayoutWithMeasureFix.<anonymous>.<anonymous>.<anonymous> (Scaffold.kt:285)");
                                    }
                                    PaddingValues insets = WindowInsetsKt.asPaddingValues(WindowInsets.this, $this$SubcomposeLayout);
                                    if (topBarPlaceables.isEmpty()) {
                                        f7 = insets.getTop();
                                    } else {
                                        f7 = $this$SubcomposeLayout.mo310toDpu2uoSUM(topBarHeight);
                                    }
                                    if (bottomBarPlaceables.isEmpty() || bottomBarHeight == null) {
                                        bottom = insets.getBottom();
                                    } else {
                                        bottom = $this$SubcomposeLayout.mo310toDpu2uoSUM(bottomBarHeight.intValue());
                                    }
                                    PaddingValues innerPadding = PaddingKt.m558PaddingValuesa9UjIt4(PaddingKt.calculateStartPadding(insets, $this$SubcomposeLayout.getLayoutDirection()), f7, PaddingKt.calculateEndPadding(insets, $this$SubcomposeLayout.getLayoutDirection()), bottom);
                                    function32.invoke(innerPadding, $composer3, 0);
                                    if (ComposerKt.isTraceInProgress()) {
                                        ComposerKt.traceEventEnd();
                                        return;
                                    }
                                    return;
                                }
                                $composer3.skipToGroupEnd();
                            }
                        }));
                        int $i$f$fastMap5 = 0;
                        List target$iv5 = new ArrayList($this$fastMap$iv5.size());
                        int index$iv$iv5 = 0;
                        int size5 = $this$fastMap$iv5.size();
                        while (index$iv$iv5 < size5) {
                            Object item$iv$iv5 = $this$fastMap$iv5.get(index$iv$iv5);
                            int $i$f$fastMap6 = $i$f$fastMap5;
                            Measurable it17 = (Measurable) item$iv$iv5;
                            target$iv5.add(it17.mo5016measureBRTryo0(looseConstraints));
                            index$iv$iv5++;
                            $this$fastMap$iv5 = $this$fastMap$iv5;
                            $i$f$fastMap5 = $i$f$fastMap6;
                        }
                        final List bodyContentPlaceables = target$iv5;
                        final WindowInsets windowInsets7 = contentWindowInsets;
                        return MeasureScope.layout$default($this$SubcomposeLayout, layoutWidth, layoutHeight, null, new Function1<Placeable.PlacementScope, Unit>() { // from class: androidx.compose.material3.ScaffoldKt$ScaffoldLayoutWithMeasureFix$1$1.1
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
                                List $this$fastForEach$iv = bodyContentPlaceables;
                                int size6 = $this$fastForEach$iv.size();
                                for (int index$iv = 0; index$iv < size6; index$iv++) {
                                    Object item$iv = $this$fastForEach$iv.get(index$iv);
                                    Placeable it18 = (Placeable) item$iv;
                                    Placeable.PlacementScope.place$default($this$layout, it18, 0, 0, 0.0f, 4, null);
                                }
                                List $this$fastForEach$iv2 = topBarPlaceables;
                                int size7 = $this$fastForEach$iv2.size();
                                for (int index$iv2 = 0; index$iv2 < size7; index$iv2++) {
                                    Object item$iv2 = $this$fastForEach$iv2.get(index$iv2);
                                    Placeable it19 = (Placeable) item$iv2;
                                    Placeable.PlacementScope.place$default($this$layout, it19, 0, 0, 0.0f, 4, null);
                                }
                                List $this$fastForEach$iv3 = snackbarPlaceables;
                                int i7 = layoutWidth;
                                int i8 = snackbarWidth;
                                WindowInsets windowInsets8 = windowInsets7;
                                SubcomposeMeasureScope subcomposeMeasureScope = $this$SubcomposeLayout;
                                int i9 = layoutHeight;
                                int i10 = snackbarOffsetFromBottom;
                                int size8 = $this$fastForEach$iv3.size();
                                for (int index$iv3 = 0; index$iv3 < size8; index$iv3++) {
                                    Object item$iv3 = $this$fastForEach$iv3.get(index$iv3);
                                    Placeable it20 = (Placeable) item$iv3;
                                    Placeable.PlacementScope.place$default($this$layout, it20, ((i7 - i8) / 2) + windowInsets8.getLeft(subcomposeMeasureScope, subcomposeMeasureScope.getLayoutDirection()), i9 - i10, 0.0f, 4, null);
                                }
                                List $this$fastForEach$iv4 = bottomBarPlaceables;
                                int i11 = layoutHeight;
                                Integer num2 = bottomBarHeight;
                                int size9 = $this$fastForEach$iv4.size();
                                for (int index$iv4 = 0; index$iv4 < size9; index$iv4++) {
                                    Object item$iv4 = $this$fastForEach$iv4.get(index$iv4);
                                    Placeable it21 = (Placeable) item$iv4;
                                    Placeable.PlacementScope.place$default($this$layout, it21, 0, i11 - (num2 != null ? num2.intValue() : 0), 0.0f, 4, null);
                                }
                                FabPlacement placement = fabPlacement2;
                                if (placement != null) {
                                    List $this$fastForEach$iv5 = fabPlaceables;
                                    int i12 = layoutHeight;
                                    Integer num3 = fabOffsetFromBottom;
                                    int size10 = $this$fastForEach$iv5.size();
                                    for (int index$iv5 = 0; index$iv5 < size10; index$iv5++) {
                                        Object item$iv5 = $this$fastForEach$iv5.get(index$iv5);
                                        Placeable it22 = (Placeable) item$iv5;
                                        int left = placement.getLeft();
                                        Intrinsics.checkNotNull(num3);
                                        Placeable.PlacementScope.place$default($this$layout, it22, left, i12 - num3.intValue(), 0.0f, 4, null);
                                    }
                                }
                            }
                        }, 4, null);
                    }
                };
                $composer2.updateRememberedValue(value$iv);
            } else {
                i = 0;
            }
            $composer2.endReplaceableGroup();
            SubcomposeLayoutKt.SubcomposeLayout(null, (Function2) value$iv, $composer2, i, 1);
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventEnd();
            }
        } else {
            $composer2.skipToGroupEnd();
        }
        ScopeUpdateScope endRestartGroup = $composer2.endRestartGroup();
        if (endRestartGroup != null) {
            endRestartGroup.updateScope(new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.ScaffoldKt$ScaffoldLayoutWithMeasureFix$2
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

                public final void invoke(Composer composer, int i2) {
                    ScaffoldKt.m2121ScaffoldLayoutWithMeasureFixFMILGgc(fabPosition, function2, function3, function22, function23, contentWindowInsets, function24, composer, RecomposeScopeImplKt.updateChangedFlags($changed | 1));
                }
            });
        }
    }

    /* JADX INFO: Access modifiers changed from: private */
    /* renamed from: LegacyScaffoldLayout-FMILGgc, reason: not valid java name */
    public static final void m2118LegacyScaffoldLayoutFMILGgc(final int fabPosition, final Function2<? super Composer, ? super Integer, Unit> function2, final Function3<? super PaddingValues, ? super Composer, ? super Integer, Unit> function3, final Function2<? super Composer, ? super Integer, Unit> function22, final Function2<? super Composer, ? super Integer, Unit> function23, final WindowInsets contentWindowInsets, final Function2<? super Composer, ? super Integer, Unit> function24, Composer $composer, final int $changed) {
        int i;
        Composer $composer2 = $composer.startRestartGroup(1307205667);
        ComposerKt.sourceInformation($composer2, "C(LegacyScaffoldLayout)P(4:c#material3.FabPosition,6,1,5,3,2)348@14737L6941,348@14720L6958:Scaffold.kt#uh7d8r");
        int $dirty = $changed;
        if (($changed & 6) == 0) {
            $dirty |= $composer2.changed(fabPosition) ? 4 : 2;
        }
        if (($changed & 48) == 0) {
            $dirty |= $composer2.changedInstance(function2) ? 32 : 16;
        }
        if (($changed & 384) == 0) {
            $dirty |= $composer2.changedInstance(function3) ? 256 : 128;
        }
        if (($changed & 3072) == 0) {
            $dirty |= $composer2.changedInstance(function22) ? 2048 : 1024;
        }
        if (($changed & 24576) == 0) {
            $dirty |= $composer2.changedInstance(function23) ? 16384 : 8192;
        }
        if ((196608 & $changed) == 0) {
            $dirty |= $composer2.changed(contentWindowInsets) ? 131072 : 65536;
        }
        if (($changed & 1572864) == 0) {
            $dirty |= $composer2.changedInstance(function24) ? 1048576 : 524288;
        }
        if (($dirty & 599187) != 599186 || !$composer2.getSkipping()) {
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventStart(1307205667, $dirty, -1, "androidx.compose.material3.LegacyScaffoldLayout (Scaffold.kt:347)");
            }
            $composer2.startReplaceableGroup(1646578117);
            ComposerKt.sourceInformation($composer2, "CC(remember):Scaffold.kt#9igjgp");
            boolean invalid$iv = (($dirty & 112) == 32) | (($dirty & 7168) == 2048) | ((458752 & $dirty) == 131072) | ((57344 & $dirty) == 16384) | (($dirty & 14) == 4) | ((3670016 & $dirty) == 1048576) | (($dirty & 896) == 256);
            Object value$iv = $composer2.rememberedValue();
            if (invalid$iv || value$iv == Composer.INSTANCE.getEmpty()) {
                i = 0;
                value$iv = new Function2<SubcomposeMeasureScope, Constraints, MeasureResult>() { // from class: androidx.compose.material3.ScaffoldKt$LegacyScaffoldLayout$1$1
                    /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
                    /* JADX WARN: Multi-variable type inference failed */
                    {
                        super(2);
                    }

                    @Override // kotlin.jvm.functions.Function2
                    public /* bridge */ /* synthetic */ MeasureResult invoke(SubcomposeMeasureScope subcomposeMeasureScope, Constraints constraints) {
                        return m2125invoke0kLqBqw(subcomposeMeasureScope, constraints.getValue());
                    }

                    /* renamed from: invoke-0kLqBqw, reason: not valid java name */
                    public final MeasureResult m2125invoke0kLqBqw(final SubcomposeMeasureScope $this$SubcomposeLayout, long constraints) {
                        final long looseConstraints;
                        final Function3<PaddingValues, Composer, Integer, Unit> function32;
                        final int layoutWidth = Constraints.m6050getMaxWidthimpl(constraints);
                        final int layoutHeight = Constraints.m6049getMaxHeightimpl(constraints);
                        looseConstraints = Constraints.m6040copyZbe2FdA(constraints, (r12 & 1) != 0 ? Constraints.m6052getMinWidthimpl(constraints) : 0, (r12 & 2) != 0 ? Constraints.m6050getMaxWidthimpl(constraints) : 0, (r12 & 4) != 0 ? Constraints.m6051getMinHeightimpl(constraints) : 0, (r12 & 8) != 0 ? Constraints.m6049getMaxHeightimpl(constraints) : 0);
                        final Function2<Composer, Integer, Unit> function25 = function2;
                        final Function2<Composer, Integer, Unit> function26 = function22;
                        final Function2<Composer, Integer, Unit> function27 = function23;
                        final int i2 = fabPosition;
                        final WindowInsets windowInsets = contentWindowInsets;
                        final Function2<Composer, Integer, Unit> function28 = function24;
                        function32 = function3;
                        return MeasureScope.layout$default($this$SubcomposeLayout, layoutWidth, layoutHeight, null, new Function1<Placeable.PlacementScope, Unit>() { // from class: androidx.compose.material3.ScaffoldKt$LegacyScaffoldLayout$1$1.1
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
                                Object maxElem$iv;
                                Object maxElem$iv2;
                                Object maxElem$iv3;
                                FabPlacement fabPlacement;
                                Object maxElem$iv4;
                                Integer num;
                                float f;
                                int i3;
                                float f2;
                                Object maxElem$iv5;
                                Object maxElem$iv6;
                                int fabLeftOffset;
                                float f3;
                                float f4;
                                float f5;
                                float f6;
                                List $this$fastMap$iv = SubcomposeMeasureScope.this.subcompose(ScaffoldLayoutContent.TopBar, function25);
                                long j = looseConstraints;
                                List target$iv = new ArrayList($this$fastMap$iv.size());
                                int size = $this$fastMap$iv.size();
                                for (int index$iv$iv = 0; index$iv$iv < size; index$iv$iv++) {
                                    Object item$iv$iv = $this$fastMap$iv.get(index$iv$iv);
                                    Measurable it = (Measurable) item$iv$iv;
                                    target$iv.add(it.mo5016measureBRTryo0(j));
                                }
                                final List topBarPlaceables = target$iv;
                                if (topBarPlaceables.isEmpty()) {
                                    maxElem$iv = null;
                                } else {
                                    maxElem$iv = topBarPlaceables.get(0);
                                    Placeable it2 = (Placeable) maxElem$iv;
                                    int maxValue$iv = it2.getHeight();
                                    int i$iv = 1;
                                    int lastIndex = CollectionsKt.getLastIndex(topBarPlaceables);
                                    if (1 <= lastIndex) {
                                        while (true) {
                                            Object e$iv = topBarPlaceables.get(i$iv);
                                            Placeable it3 = (Placeable) e$iv;
                                            int v$iv = it3.getHeight();
                                            if (maxValue$iv < v$iv) {
                                                maxElem$iv = e$iv;
                                                maxValue$iv = v$iv;
                                            }
                                            if (i$iv == lastIndex) {
                                                break;
                                            } else {
                                                i$iv++;
                                            }
                                        }
                                    }
                                }
                                Placeable placeable = (Placeable) maxElem$iv;
                                final int topBarHeight = placeable != null ? placeable.getHeight() : 0;
                                List $this$fastMap$iv2 = SubcomposeMeasureScope.this.subcompose(ScaffoldLayoutContent.Snackbar, function26);
                                WindowInsets windowInsets2 = windowInsets;
                                SubcomposeMeasureScope subcomposeMeasureScope = SubcomposeMeasureScope.this;
                                long j2 = looseConstraints;
                                int $i$f$fastMap = 0;
                                List target$iv2 = new ArrayList($this$fastMap$iv2.size());
                                List $this$fastForEach$iv$iv = $this$fastMap$iv2;
                                int index$iv$iv2 = 0;
                                int size2 = $this$fastForEach$iv$iv.size();
                                while (index$iv$iv2 < size2) {
                                    Object item$iv$iv2 = $this$fastForEach$iv$iv.get(index$iv$iv2);
                                    Measurable it4 = (Measurable) item$iv$iv2;
                                    List $this$fastMap$iv3 = $this$fastMap$iv2;
                                    SubcomposeMeasureScope subcomposeMeasureScope2 = subcomposeMeasureScope;
                                    int $i$f$fastMap2 = $i$f$fastMap;
                                    int leftInset = windowInsets2.getLeft(subcomposeMeasureScope2, subcomposeMeasureScope.getLayoutDirection());
                                    List $this$fastForEach$iv$iv2 = $this$fastForEach$iv$iv;
                                    int rightInset = windowInsets2.getRight(subcomposeMeasureScope2, subcomposeMeasureScope.getLayoutDirection());
                                    int bottomInset = windowInsets2.getBottom(subcomposeMeasureScope2);
                                    target$iv2.add(it4.mo5016measureBRTryo0(ConstraintsKt.m6066offsetNN6EwU(j2, (-leftInset) - rightInset, -bottomInset)));
                                    index$iv$iv2++;
                                    $this$fastMap$iv2 = $this$fastMap$iv3;
                                    $i$f$fastMap = $i$f$fastMap2;
                                    $this$fastForEach$iv$iv = $this$fastForEach$iv$iv2;
                                    windowInsets2 = windowInsets2;
                                    subcomposeMeasureScope = subcomposeMeasureScope;
                                }
                                List snackbarPlaceables = target$iv2;
                                if (snackbarPlaceables.isEmpty()) {
                                    maxElem$iv2 = null;
                                } else {
                                    maxElem$iv2 = snackbarPlaceables.get(0);
                                    Placeable it5 = (Placeable) maxElem$iv2;
                                    int maxValue$iv2 = it5.getHeight();
                                    int i$iv2 = 1;
                                    int lastIndex2 = CollectionsKt.getLastIndex(snackbarPlaceables);
                                    if (1 <= lastIndex2) {
                                        while (true) {
                                            Object e$iv2 = snackbarPlaceables.get(i$iv2);
                                            Placeable it6 = (Placeable) e$iv2;
                                            int v$iv2 = it6.getHeight();
                                            if (maxValue$iv2 < v$iv2) {
                                                maxElem$iv2 = e$iv2;
                                                maxValue$iv2 = v$iv2;
                                            }
                                            if (i$iv2 == lastIndex2) {
                                                break;
                                            } else {
                                                i$iv2++;
                                            }
                                        }
                                    }
                                }
                                Placeable placeable2 = (Placeable) maxElem$iv2;
                                int snackbarHeight = placeable2 != null ? placeable2.getHeight() : 0;
                                if (snackbarPlaceables.isEmpty()) {
                                    maxElem$iv3 = null;
                                } else {
                                    maxElem$iv3 = snackbarPlaceables.get(0);
                                    Placeable it7 = (Placeable) maxElem$iv3;
                                    int maxValue$iv3 = it7.getWidth();
                                    int i$iv3 = 1;
                                    int lastIndex3 = CollectionsKt.getLastIndex(snackbarPlaceables);
                                    if (1 <= lastIndex3) {
                                        while (true) {
                                            Object e$iv3 = snackbarPlaceables.get(i$iv3);
                                            Placeable it8 = (Placeable) e$iv3;
                                            int v$iv3 = it8.getWidth();
                                            if (maxValue$iv3 < v$iv3) {
                                                maxElem$iv3 = e$iv3;
                                                maxValue$iv3 = v$iv3;
                                            }
                                            if (i$iv3 == lastIndex3) {
                                                break;
                                            } else {
                                                i$iv3++;
                                            }
                                        }
                                    }
                                }
                                Placeable placeable3 = (Placeable) maxElem$iv3;
                                int snackbarWidth = placeable3 != null ? placeable3.getWidth() : 0;
                                List $this$fastMapNotNull$iv = SubcomposeMeasureScope.this.subcompose(ScaffoldLayoutContent.Fab, function27);
                                WindowInsets windowInsets3 = windowInsets;
                                SubcomposeMeasureScope subcomposeMeasureScope3 = SubcomposeMeasureScope.this;
                                long j3 = looseConstraints;
                                int $i$f$fastMapNotNull = 0;
                                List target$iv3 = new ArrayList($this$fastMapNotNull$iv.size());
                                List $this$fastForEach$iv$iv3 = $this$fastMapNotNull$iv;
                                int $i$f$fastForEach = 0;
                                int index$iv$iv3 = 0;
                                int size3 = $this$fastForEach$iv$iv3.size();
                                while (true) {
                                    int $i$f$fastMapNotNull2 = $i$f$fastMapNotNull;
                                    if (index$iv$iv3 >= size3) {
                                        break;
                                    }
                                    Object item$iv$iv3 = $this$fastForEach$iv$iv3.get(index$iv$iv3);
                                    Measurable measurable = (Measurable) item$iv$iv3;
                                    int i4 = size3;
                                    SubcomposeMeasureScope subcomposeMeasureScope4 = subcomposeMeasureScope3;
                                    List $this$fastForEach$iv$iv4 = $this$fastForEach$iv$iv3;
                                    int leftInset2 = windowInsets3.getLeft(subcomposeMeasureScope4, subcomposeMeasureScope3.getLayoutDirection());
                                    int $i$f$fastForEach2 = $i$f$fastForEach;
                                    int rightInset2 = windowInsets3.getRight(subcomposeMeasureScope4, subcomposeMeasureScope3.getLayoutDirection());
                                    int bottomInset2 = windowInsets3.getBottom(subcomposeMeasureScope4);
                                    WindowInsets windowInsets4 = windowInsets3;
                                    SubcomposeMeasureScope subcomposeMeasureScope5 = subcomposeMeasureScope3;
                                    Placeable it9 = measurable.mo5016measureBRTryo0(ConstraintsKt.m6066offsetNN6EwU(j3, (-leftInset2) - rightInset2, -bottomInset2));
                                    if (!((it9.getHeight() == 0 || it9.getWidth() == 0) ? false : true)) {
                                        it9 = null;
                                    }
                                    if (it9 != null) {
                                        target$iv3.add(it9);
                                    }
                                    index$iv$iv3++;
                                    $i$f$fastMapNotNull = $i$f$fastMapNotNull2;
                                    size3 = i4;
                                    $this$fastForEach$iv$iv3 = $this$fastForEach$iv$iv4;
                                    $i$f$fastForEach = $i$f$fastForEach2;
                                    windowInsets3 = windowInsets4;
                                    subcomposeMeasureScope3 = subcomposeMeasureScope5;
                                }
                                List fabPlaceables = target$iv3;
                                if (fabPlaceables.isEmpty()) {
                                    fabPlacement = null;
                                } else {
                                    if (fabPlaceables.isEmpty()) {
                                        maxElem$iv5 = null;
                                    } else {
                                        maxElem$iv5 = fabPlaceables.get(0);
                                        Placeable it10 = (Placeable) maxElem$iv5;
                                        int maxValue$iv4 = it10.getWidth();
                                        int i$iv4 = 1;
                                        int lastIndex4 = CollectionsKt.getLastIndex(fabPlaceables);
                                        if (1 <= lastIndex4) {
                                            while (true) {
                                                Object e$iv4 = fabPlaceables.get(i$iv4);
                                                Placeable it11 = (Placeable) e$iv4;
                                                int v$iv4 = it11.getWidth();
                                                if (maxValue$iv4 < v$iv4) {
                                                    maxElem$iv5 = e$iv4;
                                                    maxValue$iv4 = v$iv4;
                                                }
                                                if (i$iv4 == lastIndex4) {
                                                    break;
                                                } else {
                                                    i$iv4++;
                                                }
                                            }
                                        }
                                    }
                                    Intrinsics.checkNotNull(maxElem$iv5);
                                    int fabWidth = ((Placeable) maxElem$iv5).getWidth();
                                    if (fabPlaceables.isEmpty()) {
                                        maxElem$iv6 = null;
                                    } else {
                                        maxElem$iv6 = fabPlaceables.get(0);
                                        Placeable it12 = (Placeable) maxElem$iv6;
                                        int maxValue$iv5 = it12.getHeight();
                                        int i$iv5 = 1;
                                        int lastIndex5 = CollectionsKt.getLastIndex(fabPlaceables);
                                        if (1 <= lastIndex5) {
                                            while (true) {
                                                Object e$iv5 = fabPlaceables.get(i$iv5);
                                                Placeable it13 = (Placeable) e$iv5;
                                                int v$iv5 = it13.getHeight();
                                                if (maxValue$iv5 < v$iv5) {
                                                    maxElem$iv6 = e$iv5;
                                                    maxValue$iv5 = v$iv5;
                                                }
                                                if (i$iv5 == lastIndex5) {
                                                    break;
                                                } else {
                                                    i$iv5++;
                                                }
                                            }
                                        }
                                    }
                                    Intrinsics.checkNotNull(maxElem$iv6);
                                    int fabHeight = ((Placeable) maxElem$iv6).getHeight();
                                    int i5 = i2;
                                    if (FabPosition.m1891equalsimpl0(i5, FabPosition.INSTANCE.m1898getStartERTFSPs())) {
                                        if (SubcomposeMeasureScope.this.getLayoutDirection() == LayoutDirection.Ltr) {
                                            SubcomposeMeasureScope subcomposeMeasureScope6 = SubcomposeMeasureScope.this;
                                            f6 = ScaffoldKt.FabSpacing;
                                            fabLeftOffset = subcomposeMeasureScope6.mo307roundToPx0680j_4(f6);
                                        } else {
                                            int i6 = layoutWidth;
                                            SubcomposeMeasureScope subcomposeMeasureScope7 = SubcomposeMeasureScope.this;
                                            f5 = ScaffoldKt.FabSpacing;
                                            fabLeftOffset = (i6 - subcomposeMeasureScope7.mo307roundToPx0680j_4(f5)) - fabWidth;
                                        }
                                    } else if (!FabPosition.m1891equalsimpl0(i5, FabPosition.INSTANCE.m1896getEndERTFSPs())) {
                                        fabLeftOffset = (layoutWidth - fabWidth) / 2;
                                    } else if (SubcomposeMeasureScope.this.getLayoutDirection() == LayoutDirection.Ltr) {
                                        int i7 = layoutWidth;
                                        SubcomposeMeasureScope subcomposeMeasureScope8 = SubcomposeMeasureScope.this;
                                        f4 = ScaffoldKt.FabSpacing;
                                        fabLeftOffset = (i7 - subcomposeMeasureScope8.mo307roundToPx0680j_4(f4)) - fabWidth;
                                    } else {
                                        SubcomposeMeasureScope subcomposeMeasureScope9 = SubcomposeMeasureScope.this;
                                        f3 = ScaffoldKt.FabSpacing;
                                        fabLeftOffset = subcomposeMeasureScope9.mo307roundToPx0680j_4(f3);
                                    }
                                    fabPlacement = new FabPlacement(fabLeftOffset, fabWidth, fabHeight);
                                }
                                final FabPlacement fabPlacement2 = fabPlacement;
                                SubcomposeMeasureScope subcomposeMeasureScope10 = SubcomposeMeasureScope.this;
                                ScaffoldLayoutContent scaffoldLayoutContent = ScaffoldLayoutContent.BottomBar;
                                final Function2<Composer, Integer, Unit> function29 = function28;
                                List $this$fastMap$iv4 = subcomposeMeasureScope10.subcompose(scaffoldLayoutContent, ComposableLambdaKt.composableLambdaInstance(-791102355, true, new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.ScaffoldKt$LegacyScaffoldLayout$1$1$1$bottomBarPlaceables$1
                                    /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
                                    /* JADX WARN: Multi-variable type inference failed */
                                    {
                                        super(2);
                                    }

                                    @Override // kotlin.jvm.functions.Function2
                                    public /* bridge */ /* synthetic */ Unit invoke(Composer composer, Integer num2) {
                                        invoke(composer, num2.intValue());
                                        return Unit.INSTANCE;
                                    }

                                    public final void invoke(Composer $composer3, int $changed2) {
                                        ComposerKt.sourceInformation($composer3, "C429@18457L144:Scaffold.kt#uh7d8r");
                                        if (($changed2 & 3) != 2 || !$composer3.getSkipping()) {
                                            if (ComposerKt.isTraceInProgress()) {
                                                ComposerKt.traceEventStart(-791102355, $changed2, -1, "androidx.compose.material3.LegacyScaffoldLayout.<anonymous>.<anonymous>.<anonymous>.<anonymous> (Scaffold.kt:429)");
                                            }
                                            CompositionLocalKt.CompositionLocalProvider(ScaffoldKt.getLocalFabPlacement().provides(FabPlacement.this), function29, $composer3, ProvidedValue.$stable | 0);
                                            if (ComposerKt.isTraceInProgress()) {
                                                ComposerKt.traceEventEnd();
                                                return;
                                            }
                                            return;
                                        }
                                        $composer3.skipToGroupEnd();
                                    }
                                }));
                                long j4 = looseConstraints;
                                int $i$f$fastMap3 = 0;
                                List target$iv4 = new ArrayList($this$fastMap$iv4.size());
                                int index$iv$iv4 = 0;
                                int size4 = $this$fastMap$iv4.size();
                                while (index$iv$iv4 < size4) {
                                    Object item$iv$iv4 = $this$fastMap$iv4.get(index$iv$iv4);
                                    int $i$f$fastMap4 = $i$f$fastMap3;
                                    Measurable it14 = (Measurable) item$iv$iv4;
                                    target$iv4.add(it14.mo5016measureBRTryo0(j4));
                                    index$iv$iv4++;
                                    size4 = size4;
                                    $i$f$fastMap3 = $i$f$fastMap4;
                                }
                                final List bottomBarPlaceables = target$iv4;
                                if (bottomBarPlaceables.isEmpty()) {
                                    maxElem$iv4 = null;
                                } else {
                                    maxElem$iv4 = bottomBarPlaceables.get(0);
                                    Placeable it15 = (Placeable) maxElem$iv4;
                                    int maxValue$iv6 = it15.getHeight();
                                    int i$iv6 = 1;
                                    int lastIndex6 = CollectionsKt.getLastIndex(bottomBarPlaceables);
                                    if (1 <= lastIndex6) {
                                        while (true) {
                                            Object e$iv6 = bottomBarPlaceables.get(i$iv6);
                                            Placeable it16 = (Placeable) e$iv6;
                                            int height = it16.getHeight();
                                            if (maxValue$iv6 < height) {
                                                maxElem$iv4 = e$iv6;
                                                maxValue$iv6 = height;
                                            }
                                            if (i$iv6 == lastIndex6) {
                                                break;
                                            } else {
                                                i$iv6++;
                                            }
                                        }
                                    }
                                }
                                Placeable placeable4 = (Placeable) maxElem$iv4;
                                Integer bottomBarHeight = placeable4 != null ? Integer.valueOf(placeable4.getHeight()) : null;
                                if (fabPlacement2 != null) {
                                    SubcomposeMeasureScope subcomposeMeasureScope11 = SubcomposeMeasureScope.this;
                                    WindowInsets windowInsets5 = windowInsets;
                                    if (bottomBarHeight == null) {
                                        int height2 = fabPlacement2.getHeight();
                                        f2 = ScaffoldKt.FabSpacing;
                                        i3 = height2 + subcomposeMeasureScope11.mo307roundToPx0680j_4(f2) + windowInsets5.getBottom(subcomposeMeasureScope11);
                                    } else {
                                        int intValue = bottomBarHeight.intValue() + fabPlacement2.getHeight();
                                        f = ScaffoldKt.FabSpacing;
                                        i3 = intValue + subcomposeMeasureScope11.mo307roundToPx0680j_4(f);
                                    }
                                    num = Integer.valueOf(i3);
                                } else {
                                    num = null;
                                }
                                Integer fabOffsetFromBottom = num;
                                int snackbarOffsetFromBottom = snackbarHeight != 0 ? (fabOffsetFromBottom != null ? fabOffsetFromBottom.intValue() : bottomBarHeight != null ? bottomBarHeight.intValue() : windowInsets.getBottom(SubcomposeMeasureScope.this)) + snackbarHeight : 0;
                                SubcomposeMeasureScope subcomposeMeasureScope12 = SubcomposeMeasureScope.this;
                                ScaffoldLayoutContent scaffoldLayoutContent2 = ScaffoldLayoutContent.MainContent;
                                final WindowInsets windowInsets6 = windowInsets;
                                final SubcomposeMeasureScope subcomposeMeasureScope13 = SubcomposeMeasureScope.this;
                                final Function3<PaddingValues, Composer, Integer, Unit> function33 = function32;
                                final Integer num2 = bottomBarHeight;
                                List $this$fastMap$iv5 = subcomposeMeasureScope12.subcompose(scaffoldLayoutContent2, ComposableLambdaKt.composableLambdaInstance(495329982, true, new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.ScaffoldKt$LegacyScaffoldLayout$1$1$1$bodyContentPlaceables$1
                                    /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
                                    /* JADX WARN: Multi-variable type inference failed */
                                    {
                                        super(2);
                                    }

                                    @Override // kotlin.jvm.functions.Function2
                                    public /* bridge */ /* synthetic */ Unit invoke(Composer composer, Integer num3) {
                                        invoke(composer, num3.intValue());
                                        return Unit.INSTANCE;
                                    }

                                    public final void invoke(Composer $composer3, int $changed2) {
                                        float f7;
                                        float bottom;
                                        ComposerKt.sourceInformation($composer3, "C473@20504L21:Scaffold.kt#uh7d8r");
                                        if (($changed2 & 3) != 2 || !$composer3.getSkipping()) {
                                            if (ComposerKt.isTraceInProgress()) {
                                                ComposerKt.traceEventStart(495329982, $changed2, -1, "androidx.compose.material3.LegacyScaffoldLayout.<anonymous>.<anonymous>.<anonymous>.<anonymous> (Scaffold.kt:456)");
                                            }
                                            PaddingValues insets = WindowInsetsKt.asPaddingValues(WindowInsets.this, subcomposeMeasureScope13);
                                            if (topBarPlaceables.isEmpty()) {
                                                f7 = insets.getTop();
                                            } else {
                                                f7 = subcomposeMeasureScope13.mo310toDpu2uoSUM(topBarHeight);
                                            }
                                            if (bottomBarPlaceables.isEmpty() || num2 == null) {
                                                bottom = insets.getBottom();
                                            } else {
                                                bottom = subcomposeMeasureScope13.mo310toDpu2uoSUM(num2.intValue());
                                            }
                                            PaddingValues innerPadding = PaddingKt.m558PaddingValuesa9UjIt4(PaddingKt.calculateStartPadding(insets, subcomposeMeasureScope13.getLayoutDirection()), f7, PaddingKt.calculateEndPadding(insets, subcomposeMeasureScope13.getLayoutDirection()), bottom);
                                            function33.invoke(innerPadding, $composer3, 0);
                                            if (ComposerKt.isTraceInProgress()) {
                                                ComposerKt.traceEventEnd();
                                                return;
                                            }
                                            return;
                                        }
                                        $composer3.skipToGroupEnd();
                                    }
                                }));
                                long j5 = looseConstraints;
                                int $i$f$fastMap5 = 0;
                                List target$iv5 = new ArrayList($this$fastMap$iv5.size());
                                int index$iv$iv5 = 0;
                                int size5 = $this$fastMap$iv5.size();
                                while (index$iv$iv5 < size5) {
                                    Object item$iv$iv5 = $this$fastMap$iv5.get(index$iv$iv5);
                                    int $i$f$fastMap6 = $i$f$fastMap5;
                                    Measurable it17 = (Measurable) item$iv$iv5;
                                    target$iv5.add(it17.mo5016measureBRTryo0(j5));
                                    index$iv$iv5++;
                                    size5 = size5;
                                    $i$f$fastMap5 = $i$f$fastMap6;
                                }
                                List bodyContentPlaceables = target$iv5;
                                int size6 = bodyContentPlaceables.size();
                                for (int index$iv = 0; index$iv < size6; index$iv++) {
                                    Object item$iv = bodyContentPlaceables.get(index$iv);
                                    Placeable it18 = (Placeable) item$iv;
                                    Placeable.PlacementScope.place$default($this$layout, it18, 0, 0, 0.0f, 4, null);
                                }
                                int size7 = topBarPlaceables.size();
                                for (int index$iv2 = 0; index$iv2 < size7; index$iv2++) {
                                    Object item$iv2 = topBarPlaceables.get(index$iv2);
                                    Placeable it19 = (Placeable) item$iv2;
                                    Placeable.PlacementScope.place$default($this$layout, it19, 0, 0, 0.0f, 4, null);
                                }
                                int i8 = layoutWidth;
                                WindowInsets windowInsets7 = windowInsets;
                                SubcomposeMeasureScope subcomposeMeasureScope14 = SubcomposeMeasureScope.this;
                                int i9 = layoutHeight;
                                int index$iv3 = 0;
                                int size8 = snackbarPlaceables.size();
                                while (index$iv3 < size8) {
                                    Object item$iv3 = snackbarPlaceables.get(index$iv3);
                                    Placeable it20 = (Placeable) item$iv3;
                                    Placeable.PlacementScope.place$default($this$layout, it20, ((i8 - snackbarWidth) / 2) + windowInsets7.getLeft(subcomposeMeasureScope14, subcomposeMeasureScope14.getLayoutDirection()), i9 - snackbarOffsetFromBottom, 0.0f, 4, null);
                                    index$iv3++;
                                    size8 = size8;
                                    bodyContentPlaceables = bodyContentPlaceables;
                                }
                                int i10 = layoutHeight;
                                int size9 = bottomBarPlaceables.size();
                                for (int index$iv4 = 0; index$iv4 < size9; index$iv4++) {
                                    Object item$iv4 = bottomBarPlaceables.get(index$iv4);
                                    Placeable it21 = (Placeable) item$iv4;
                                    Placeable.PlacementScope.place$default($this$layout, it21, 0, i10 - (bottomBarHeight != null ? bottomBarHeight.intValue() : 0), 0.0f, 4, null);
                                }
                                if (fabPlacement2 != null) {
                                    int i11 = layoutHeight;
                                    int size10 = fabPlaceables.size();
                                    for (int index$iv5 = 0; index$iv5 < size10; index$iv5++) {
                                        Object item$iv5 = fabPlaceables.get(index$iv5);
                                        Placeable it22 = (Placeable) item$iv5;
                                        int left = fabPlacement2.getLeft();
                                        Intrinsics.checkNotNull(fabOffsetFromBottom);
                                        Placeable.PlacementScope.place$default($this$layout, it22, left, i11 - fabOffsetFromBottom.intValue(), 0.0f, 4, null);
                                    }
                                    Unit unit = Unit.INSTANCE;
                                    Unit unit2 = Unit.INSTANCE;
                                }
                            }
                        }, 4, null);
                    }
                };
                $composer2.updateRememberedValue(value$iv);
            } else {
                i = 0;
            }
            $composer2.endReplaceableGroup();
            SubcomposeLayoutKt.SubcomposeLayout(null, (Function2) value$iv, $composer2, i, 1);
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventEnd();
            }
        } else {
            $composer2.skipToGroupEnd();
        }
        ScopeUpdateScope endRestartGroup = $composer2.endRestartGroup();
        if (endRestartGroup != null) {
            endRestartGroup.updateScope(new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.ScaffoldKt$LegacyScaffoldLayout$2
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

                public final void invoke(Composer composer, int i2) {
                    ScaffoldKt.m2118LegacyScaffoldLayoutFMILGgc(fabPosition, function2, function3, function22, function23, contentWindowInsets, function24, composer, RecomposeScopeImplKt.updateChangedFlags($changed | 1));
                }
            });
        }
    }

    public static final boolean getScaffoldSubcomposeInMeasureFix() {
        State $this$getValue$iv = ScaffoldSubcomposeInMeasureFix$delegate;
        return ((Boolean) $this$getValue$iv.getValue()).booleanValue();
    }

    public static final void setScaffoldSubcomposeInMeasureFix(boolean z) {
        MutableState $this$setValue$iv = ScaffoldSubcomposeInMeasureFix$delegate;
        $this$setValue$iv.setValue(Boolean.valueOf(z));
    }

    public static final ProvidableCompositionLocal<FabPlacement> getLocalFabPlacement() {
        return LocalFabPlacement;
    }
}
