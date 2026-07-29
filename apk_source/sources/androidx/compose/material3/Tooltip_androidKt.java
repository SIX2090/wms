package androidx.compose.material3;

import android.content.res.Configuration;
import androidx.compose.runtime.Composer;
import androidx.compose.runtime.ComposerKt;
import androidx.compose.runtime.ProvidableCompositionLocal;
import androidx.compose.runtime.RecomposeScopeImplKt;
import androidx.compose.runtime.ScopeUpdateScope;
import androidx.compose.runtime.internal.ComposableLambdaKt;
import androidx.compose.ui.Modifier;
import androidx.compose.ui.draw.CacheDrawScope;
import androidx.compose.ui.draw.DrawResult;
import androidx.compose.ui.geometry.Offset;
import androidx.compose.ui.geometry.OffsetKt;
import androidx.compose.ui.geometry.Rect;
import androidx.compose.ui.geometry.Size;
import androidx.compose.ui.graphics.AndroidPath_androidKt;
import androidx.compose.ui.graphics.Path;
import androidx.compose.ui.graphics.Shape;
import androidx.compose.ui.graphics.drawscope.ContentDrawScope;
import androidx.compose.ui.graphics.drawscope.DrawScope;
import androidx.compose.ui.layout.LayoutCoordinates;
import androidx.compose.ui.layout.LayoutCoordinatesKt;
import androidx.compose.ui.platform.AndroidCompositionLocals_androidKt;
import androidx.compose.ui.platform.CompositionLocalsKt;
import androidx.compose.ui.unit.Density;
import androidx.compose.ui.unit.Dp;
import androidx.core.view.accessibility.AccessibilityEventCompat;
import androidx.profileinstaller.ProfileVerifier;
import kotlin.Metadata;
import kotlin.Unit;
import kotlin.jvm.functions.Function1;
import kotlin.jvm.functions.Function2;

/* compiled from: Tooltip.android.kt */
@Metadata(d1 = {"\u0000X\n\u0000\n\u0002\u0010\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\u001aq\u0010\u0000\u001a\u00020\u0001*\u00020\u00022\b\b\u0002\u0010\u0003\u001a\u00020\u00042\n\b\u0002\u0010\u0005\u001a\u0004\u0018\u00010\u00062\b\b\u0002\u0010\u0007\u001a\u00020\b2\b\b\u0002\u0010\t\u001a\u00020\n2\b\b\u0002\u0010\u000b\u001a\u00020\n2\b\b\u0002\u0010\f\u001a\u00020\r2\b\b\u0002\u0010\u000e\u001a\u00020\r2\u0011\u0010\u000f\u001a\r\u0012\u0004\u0012\u00020\u00010\u0010¢\u0006\u0002\b\u0011H\u0007ø\u0001\u0000¢\u0006\u0004\b\u0012\u0010\u0013\u001a@\u0010\u0014\u001a\u00020\u0015*\u00020\u00162\u0006\u0010\u0017\u001a\u00020\u00182\u0006\u0010\u0019\u001a\u00020\u001a2\u0006\u0010\u000b\u001a\u00020\n2\u0006\u0010\u0005\u001a\u00020\u00062\b\u0010\u001b\u001a\u0004\u0018\u00010\u001cH\u0003ø\u0001\u0000¢\u0006\u0004\b\u001d\u0010\u001e\u0082\u0002\u0007\n\u0005\b¡\u001e0\u0001¨\u0006\u001f"}, d2 = {"PlainTooltip", "", "Landroidx/compose/material3/CaretScope;", "modifier", "Landroidx/compose/ui/Modifier;", "caretProperties", "Landroidx/compose/material3/CaretProperties;", "shape", "Landroidx/compose/ui/graphics/Shape;", "contentColor", "Landroidx/compose/ui/graphics/Color;", "containerColor", "tonalElevation", "Landroidx/compose/ui/unit/Dp;", "shadowElevation", "content", "Lkotlin/Function0;", "Landroidx/compose/runtime/Composable;", "PlainTooltip-Fg7CxbU", "(Landroidx/compose/material3/CaretScope;Landroidx/compose/ui/Modifier;Landroidx/compose/material3/CaretProperties;Landroidx/compose/ui/graphics/Shape;JJFFLkotlin/jvm/functions/Function2;Landroidx/compose/runtime/Composer;II)V", "drawCaretWithPath", "Landroidx/compose/ui/draw/DrawResult;", "Landroidx/compose/ui/draw/CacheDrawScope;", "density", "Landroidx/compose/ui/unit/Density;", "configuration", "Landroid/content/res/Configuration;", "anchorLayoutCoordinates", "Landroidx/compose/ui/layout/LayoutCoordinates;", "drawCaretWithPath-Bx497Mc", "(Landroidx/compose/ui/draw/CacheDrawScope;Landroidx/compose/ui/unit/Density;Landroid/content/res/Configuration;JLandroidx/compose/material3/CaretProperties;Landroidx/compose/ui/layout/LayoutCoordinates;)Landroidx/compose/ui/draw/DrawResult;", "material3_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class Tooltip_androidKt {
    /* renamed from: PlainTooltip-Fg7CxbU, reason: not valid java name */
    public static final void m2608PlainTooltipFg7CxbU(final CaretScope $this$PlainTooltip_u2dFg7CxbU, Modifier modifier, CaretProperties caretProperties, Shape shape, long contentColor, long containerColor, float tonalElevation, float shadowElevation, final Function2<? super Composer, ? super Integer, Unit> function2, Composer $composer, final int $changed, final int i) {
        Shape shape2;
        long j;
        long containerColor2;
        float tonalElevation2;
        CaretProperties caretProperties2;
        Shape shape3;
        final long contentColor2;
        Modifier modifier2;
        Modifier modifier3;
        int $dirty;
        float shadowElevation2;
        float shadowElevation3;
        Shape shape4;
        float tonalElevation3;
        Modifier customModifier;
        float shadowElevation4;
        float tonalElevation4;
        Modifier modifier4;
        CaretProperties caretProperties3;
        long containerColor3;
        long contentColor3;
        Object value$iv;
        int i2;
        int i3;
        int i4;
        Composer $composer2 = $composer.startRestartGroup(419109811);
        ComposerKt.sourceInformation($composer2, "C(PlainTooltip)P(4!1,6,3:c#ui.graphics.Color,1:c#ui.graphics.Color,7:c#ui.unit.Dp,5:c#ui.unit.Dp)184@7877L26,184@7947L24,184@8017L26,83@3344L784:Tooltip.android.kt#uh7d8r");
        int $dirty2 = $changed;
        if ((Integer.MIN_VALUE & i) != 0) {
            $dirty2 |= 6;
        } else if (($changed & 6) == 0) {
            $dirty2 |= ($changed & 8) == 0 ? $composer2.changed($this$PlainTooltip_u2dFg7CxbU) : $composer2.changedInstance($this$PlainTooltip_u2dFg7CxbU) ? 4 : 2;
        }
        int i5 = i & 1;
        if (i5 != 0) {
            $dirty2 |= 48;
        } else if (($changed & 48) == 0) {
            $dirty2 |= $composer2.changed(modifier) ? 32 : 16;
        }
        int i6 = i & 2;
        if (i6 != 0) {
            $dirty2 |= 384;
        } else if (($changed & 384) == 0) {
            $dirty2 |= $composer2.changed(caretProperties) ? 256 : 128;
        }
        if (($changed & 3072) == 0) {
            if ((i & 4) == 0) {
                shape2 = shape;
                if ($composer2.changed(shape2)) {
                    i4 = 2048;
                    $dirty2 |= i4;
                }
            } else {
                shape2 = shape;
            }
            i4 = 1024;
            $dirty2 |= i4;
        } else {
            shape2 = shape;
        }
        if (($changed & 24576) == 0) {
            if ((i & 8) == 0) {
                j = contentColor;
                if ($composer2.changed(j)) {
                    i3 = 16384;
                    $dirty2 |= i3;
                }
            } else {
                j = contentColor;
            }
            i3 = 8192;
            $dirty2 |= i3;
        } else {
            j = contentColor;
        }
        if (($changed & ProfileVerifier.CompilationStatus.RESULT_CODE_ERROR_CANT_WRITE_PROFILE_VERIFICATION_RESULT_CACHE_FILE) == 0) {
            if ((i & 16) == 0) {
                containerColor2 = containerColor;
                if ($composer2.changed(containerColor2)) {
                    i2 = 131072;
                    $dirty2 |= i2;
                }
            } else {
                containerColor2 = containerColor;
            }
            i2 = 65536;
            $dirty2 |= i2;
        } else {
            containerColor2 = containerColor;
        }
        int i7 = i & 32;
        if (i7 != 0) {
            $dirty2 |= 1572864;
            tonalElevation2 = tonalElevation;
        } else if (($changed & 1572864) == 0) {
            tonalElevation2 = tonalElevation;
            $dirty2 |= $composer2.changed(tonalElevation2) ? 1048576 : 524288;
        } else {
            tonalElevation2 = tonalElevation;
        }
        int i8 = i & 64;
        if (i8 != 0) {
            $dirty2 |= 12582912;
        } else if (($changed & 12582912) == 0) {
            $dirty2 |= $composer2.changed(shadowElevation) ? 8388608 : 4194304;
        }
        if ((i & 128) != 0) {
            $dirty2 |= 100663296;
        } else if (($changed & 100663296) == 0) {
            $dirty2 |= $composer2.changedInstance(function2) ? AccessibilityEventCompat.TYPE_VIEW_TARGETED_BY_SCROLL : 33554432;
        }
        if ((38347923 & $dirty2) == 38347922 && $composer2.getSkipping()) {
            $composer2.skipToGroupEnd();
            modifier4 = modifier;
            caretProperties3 = caretProperties;
            shadowElevation4 = shadowElevation;
            containerColor3 = containerColor2;
            shape4 = shape2;
            contentColor3 = j;
            tonalElevation4 = tonalElevation2;
        } else {
            $composer2.startDefaults();
            if (($changed & 1) == 0 || $composer2.getDefaultsInvalid()) {
                Modifier.Companion modifier5 = i5 != 0 ? Modifier.INSTANCE : modifier;
                caretProperties2 = i6 != 0 ? null : caretProperties;
                if ((i & 4) != 0) {
                    shape3 = TooltipDefaults.INSTANCE.getPlainTooltipContainerShape($composer2, 6);
                    $dirty2 &= -7169;
                } else {
                    shape3 = shape2;
                }
                if ((i & 8) != 0) {
                    contentColor2 = TooltipDefaults.INSTANCE.getPlainTooltipContentColor($composer2, 6);
                    $dirty2 &= -57345;
                } else {
                    contentColor2 = j;
                }
                if ((i & 16) != 0) {
                    containerColor2 = TooltipDefaults.INSTANCE.getPlainTooltipContainerColor($composer2, 6);
                    $dirty2 &= -458753;
                }
                if (i7 != 0) {
                    modifier2 = modifier5;
                    tonalElevation2 = Dp.m6094constructorimpl(0);
                } else {
                    modifier2 = modifier5;
                }
                if (i8 != 0) {
                    $dirty = $dirty2;
                    shadowElevation2 = Dp.m6094constructorimpl(0);
                    modifier3 = modifier2;
                } else {
                    modifier3 = modifier2;
                    $dirty = $dirty2;
                    shadowElevation2 = shadowElevation;
                }
            } else {
                $composer2.skipToGroupEnd();
                if ((i & 4) != 0) {
                    $dirty2 &= -7169;
                }
                if ((i & 8) != 0) {
                    $dirty2 &= -57345;
                }
                if ((i & 16) != 0) {
                    int i9 = $dirty2 & (-458753);
                    caretProperties2 = caretProperties;
                    shadowElevation2 = shadowElevation;
                    $dirty = i9;
                    shape3 = shape2;
                    contentColor2 = j;
                    modifier3 = modifier;
                } else {
                    modifier3 = modifier;
                    caretProperties2 = caretProperties;
                    $dirty = $dirty2;
                    shape3 = shape2;
                    contentColor2 = j;
                    shadowElevation2 = shadowElevation;
                }
            }
            $composer2.endDefaults();
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventStart(419109811, $dirty, -1, "androidx.compose.material3.PlainTooltip (Tooltip.android.kt:67)");
            }
            $composer2.startReplaceableGroup(2067440203);
            ComposerKt.sourceInformation($composer2, "70@2893L7,71@2952L7,72@2991L308");
            if (caretProperties2 != null) {
                ProvidableCompositionLocal<Density> localDensity = CompositionLocalsKt.getLocalDensity();
                ComposerKt.sourceInformationMarkerStart($composer2, 2023513938, "CC:CompositionLocal.kt#9igjgp");
                Object consume = $composer2.consume(localDensity);
                ComposerKt.sourceInformationMarkerEnd($composer2);
                final Density density = (Density) consume;
                ProvidableCompositionLocal<Configuration> localConfiguration = AndroidCompositionLocals_androidKt.getLocalConfiguration();
                shadowElevation3 = shadowElevation2;
                ComposerKt.sourceInformationMarkerStart($composer2, 2023513938, "CC:CompositionLocal.kt#9igjgp");
                Object consume2 = $composer2.consume(localConfiguration);
                ComposerKt.sourceInformationMarkerEnd($composer2);
                final Configuration configuration = (Configuration) consume2;
                Modifier.Companion companion = Modifier.INSTANCE;
                $composer2.startReplaceableGroup(2067440371);
                ComposerKt.sourceInformation($composer2, "CC(remember):Tooltip.android.kt#9igjgp");
                tonalElevation3 = tonalElevation2;
                shape4 = shape3;
                boolean invalid$iv = (((($dirty & 458752) ^ ProfileVerifier.CompilationStatus.RESULT_CODE_ERROR_CANT_WRITE_PROFILE_VERIFICATION_RESULT_CACHE_FILE) > 131072 && $composer2.changed(containerColor2)) || (196608 & $dirty) == 131072) | $composer2.changed(density) | $composer2.changedInstance(configuration) | (($dirty & 896) == 256);
                Object it$iv = $composer2.rememberedValue();
                if (!invalid$iv && it$iv != Composer.INSTANCE.getEmpty()) {
                    value$iv = it$iv;
                    $composer2.endReplaceableGroup();
                    customModifier = $this$PlainTooltip_u2dFg7CxbU.drawCaret(companion, (Function2) value$iv).then(modifier3);
                }
                final long j2 = containerColor2;
                final CaretProperties caretProperties4 = caretProperties2;
                value$iv = (Function2) new Function2<CacheDrawScope, LayoutCoordinates, DrawResult>() { // from class: androidx.compose.material3.Tooltip_androidKt$PlainTooltip$customModifier$1$1
                    /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
                    {
                        super(2);
                    }

                    @Override // kotlin.jvm.functions.Function2
                    public final DrawResult invoke(CacheDrawScope $this$drawCaret, LayoutCoordinates anchorLayoutCoordinates) {
                        DrawResult m2610drawCaretWithPathBx497Mc;
                        m2610drawCaretWithPathBx497Mc = Tooltip_androidKt.m2610drawCaretWithPathBx497Mc($this$drawCaret, Density.this, configuration, j2, caretProperties4, anchorLayoutCoordinates);
                        return m2610drawCaretWithPathBx497Mc;
                    }
                };
                $composer2.updateRememberedValue(value$iv);
                $composer2.endReplaceableGroup();
                customModifier = $this$PlainTooltip_u2dFg7CxbU.drawCaret(companion, (Function2) value$iv).then(modifier3);
            } else {
                shadowElevation3 = shadowElevation2;
                shape4 = shape3;
                tonalElevation3 = tonalElevation2;
                customModifier = modifier3;
            }
            $composer2.endReplaceableGroup();
            SurfaceKt.m2316SurfaceT9BRK9s(customModifier, shape4, containerColor2, 0L, tonalElevation3, shadowElevation3, null, ComposableLambdaKt.composableLambda($composer2, -705895688, true, new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.Tooltip_androidKt$PlainTooltip$1
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

                /* JADX WARN: Removed duplicated region for block: B:24:0x01bc  */
                /* JADX WARN: Removed duplicated region for block: B:26:? A[RETURN, SYNTHETIC] */
                /*
                    Code decompiled incorrectly, please refer to instructions dump.
                    To view partially-correct add '--show-bad-code' argument
                */
                public final void invoke(androidx.compose.runtime.Composer r30, int r31) {
                    /*
                        Method dump skipped, instructions count: 448
                        To view this dump add '--comments-level debug' option
                    */
                    throw new UnsupportedOperationException("Method not decompiled: androidx.compose.material3.Tooltip_androidKt$PlainTooltip$1.invoke(androidx.compose.runtime.Composer, int):void");
                }
            }), $composer2, (($dirty >> 6) & 112) | 12582912 | (($dirty >> 9) & 896) | (($dirty >> 6) & 57344) | (($dirty >> 6) & 458752), 72);
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventEnd();
            }
            shadowElevation4 = shadowElevation3;
            tonalElevation4 = tonalElevation3;
            modifier4 = modifier3;
            caretProperties3 = caretProperties2;
            containerColor3 = containerColor2;
            contentColor3 = contentColor2;
        }
        ScopeUpdateScope endRestartGroup = $composer2.endRestartGroup();
        if (endRestartGroup != null) {
            final Modifier modifier6 = modifier4;
            final CaretProperties caretProperties5 = caretProperties3;
            final Shape shape5 = shape4;
            final long j3 = contentColor3;
            final long j4 = containerColor3;
            final float f = tonalElevation4;
            final float f2 = shadowElevation4;
            endRestartGroup.updateScope(new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.Tooltip_androidKt$PlainTooltip$2
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

                public final void invoke(Composer composer, int i10) {
                    Tooltip_androidKt.m2608PlainTooltipFg7CxbU(CaretScope.this, modifier6, caretProperties5, shape5, j3, j4, f, f2, function2, composer, RecomposeScopeImplKt.updateChangedFlags($changed | 1), i);
                }
            });
        }
    }

    /* JADX INFO: Access modifiers changed from: private */
    /* renamed from: drawCaretWithPath-Bx497Mc, reason: not valid java name */
    public static final DrawResult m2610drawCaretWithPathBx497Mc(CacheDrawScope $this$drawCaretWithPath_u2dBx497Mc, Density density, Configuration configuration, final long containerColor, CaretProperties caretProperties, final LayoutCoordinates anchorLayoutCoordinates) {
        float caretY;
        long position;
        final Path path = AndroidPath_androidKt.Path();
        if (anchorLayoutCoordinates != null) {
            int caretHeightPx = density.mo307roundToPx0680j_4(caretProperties.m1638getCaretHeightD9Ej5fM());
            int caretWidthPx = density.mo307roundToPx0680j_4(caretProperties.m1639getCaretWidthD9Ej5fM());
            int $this$dp$iv = configuration.screenWidthDp;
            int screenWidthPx = density.mo307roundToPx0680j_4(Dp.m6094constructorimpl($this$dp$iv));
            int tooltipAnchorSpacing = density.mo307roundToPx0680j_4(TooltipKt.getSpacingBetweenTooltipAndAnchor());
            Rect anchorBounds = LayoutCoordinatesKt.boundsInWindow(anchorLayoutCoordinates);
            float anchorLeft = anchorBounds.getLeft();
            float anchorRight = anchorBounds.getRight();
            float anchorTop = anchorBounds.getTop();
            float f = 2;
            float anchorMid = (anchorRight + anchorLeft) / f;
            float anchorWidth = anchorRight - anchorLeft;
            float tooltipWidth = Size.m3574getWidthimpl($this$drawCaretWithPath_u2dBx497Mc.m3412getSizeNHjbRc());
            float tooltipHeight = Size.m3571getHeightimpl($this$drawCaretWithPath_u2dBx497Mc.m3412getSizeNHjbRc());
            boolean isCaretTop = (anchorTop - tooltipHeight) - ((float) tooltipAnchorSpacing) < 0.0f;
            float caretY2 = isCaretTop ? 0.0f : tooltipHeight;
            if (anchorMid + (tooltipWidth / f) > screenWidthPx) {
                float anchorMidFromRightScreenEdge = screenWidthPx - anchorMid;
                float caretX = tooltipWidth - anchorMidFromRightScreenEdge;
                caretY = caretY2;
                position = OffsetKt.Offset(caretX, caretY);
            } else {
                caretY = caretY2;
                float tooltipLeft = anchorLeft - ((Size.m3574getWidthimpl($this$drawCaretWithPath_u2dBx497Mc.m3412getSizeNHjbRc()) / f) - (anchorWidth / f));
                float caretX2 = anchorMid - Math.max(tooltipLeft, 0.0f);
                position = OffsetKt.Offset(caretX2, caretY);
            }
            if (isCaretTop) {
                path.moveTo(Offset.m3505getXimpl(position), Offset.m3506getYimpl(position));
                path.lineTo(Offset.m3505getXimpl(position) + (caretWidthPx / 2), Offset.m3506getYimpl(position));
                path.lineTo(Offset.m3505getXimpl(position), Offset.m3506getYimpl(position) - caretHeightPx);
                path.lineTo(Offset.m3505getXimpl(position) - (caretWidthPx / 2), Offset.m3506getYimpl(position));
                path.close();
            } else {
                path.moveTo(Offset.m3505getXimpl(position), Offset.m3506getYimpl(position));
                path.lineTo(Offset.m3505getXimpl(position) + (caretWidthPx / 2), Offset.m3506getYimpl(position));
                path.lineTo(Offset.m3505getXimpl(position), Offset.m3506getYimpl(position) + caretHeightPx);
                path.lineTo(Offset.m3505getXimpl(position) - (caretWidthPx / 2), Offset.m3506getYimpl(position));
                path.close();
            }
        }
        return $this$drawCaretWithPath_u2dBx497Mc.onDrawWithContent(new Function1<ContentDrawScope, Unit>() { // from class: androidx.compose.material3.Tooltip_androidKt$drawCaretWithPath$4
            /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
            {
                super(1);
            }

            @Override // kotlin.jvm.functions.Function1
            public /* bridge */ /* synthetic */ Unit invoke(ContentDrawScope contentDrawScope) {
                invoke2(contentDrawScope);
                return Unit.INSTANCE;
            }

            /* renamed from: invoke, reason: avoid collision after fix types in other method */
            public final void invoke2(ContentDrawScope $this$onDrawWithContent) {
                if (LayoutCoordinates.this != null) {
                    $this$onDrawWithContent.drawContent();
                    DrawScope.m4286drawPathLG529CI$default($this$onDrawWithContent, path, containerColor, 0.0f, null, null, 0, 60, null);
                }
            }
        });
    }
}
