package androidx.compose.material3;

import androidx.compose.foundation.BorderStroke;
import androidx.compose.foundation.interaction.InteractionSourceKt;
import androidx.compose.foundation.interaction.MutableInteractionSource;
import androidx.compose.foundation.layout.PaddingValues;
import androidx.compose.foundation.layout.RowScope;
import androidx.compose.runtime.Composer;
import androidx.compose.runtime.ComposerKt;
import androidx.compose.runtime.RecomposeScopeImplKt;
import androidx.compose.runtime.ScopeUpdateScope;
import androidx.compose.runtime.State;
import androidx.compose.runtime.internal.ComposableLambdaKt;
import androidx.compose.ui.Modifier;
import androidx.compose.ui.graphics.Shape;
import androidx.compose.ui.semantics.Role;
import androidx.compose.ui.semantics.SemanticsModifierKt;
import androidx.compose.ui.semantics.SemanticsPropertiesKt;
import androidx.compose.ui.semantics.SemanticsPropertyReceiver;
import androidx.compose.ui.text.TextStyle;
import androidx.compose.ui.unit.Dp;
import androidx.core.view.accessibility.AccessibilityEventCompat;
import androidx.profileinstaller.ProfileVerifier;
import kotlin.Metadata;
import kotlin.Unit;
import kotlin.jvm.functions.Function0;
import kotlin.jvm.functions.Function1;
import kotlin.jvm.functions.Function2;
import kotlin.jvm.functions.Function3;

/* compiled from: Button.kt */
@Metadata(d1 = {"\u0000R\n\u0000\n\u0002\u0010\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010\u000b\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\b\u0006\u001a\u008d\u0001\u0010\u0000\u001a\u00020\u00012\f\u0010\u0002\u001a\b\u0012\u0004\u0012\u00020\u00010\u00032\b\b\u0002\u0010\u0004\u001a\u00020\u00052\b\b\u0002\u0010\u0006\u001a\u00020\u00072\b\b\u0002\u0010\b\u001a\u00020\t2\b\b\u0002\u0010\n\u001a\u00020\u000b2\n\b\u0002\u0010\f\u001a\u0004\u0018\u00010\r2\n\b\u0002\u0010\u000e\u001a\u0004\u0018\u00010\u000f2\b\b\u0002\u0010\u0010\u001a\u00020\u00112\b\b\u0002\u0010\u0012\u001a\u00020\u00132\u001c\u0010\u0014\u001a\u0018\u0012\u0004\u0012\u00020\u0016\u0012\u0004\u0012\u00020\u00010\u0015¢\u0006\u0002\b\u0017¢\u0006\u0002\b\u0018H\u0007¢\u0006\u0002\u0010\u0019\u001a\u008d\u0001\u0010\u001a\u001a\u00020\u00012\f\u0010\u0002\u001a\b\u0012\u0004\u0012\u00020\u00010\u00032\b\b\u0002\u0010\u0004\u001a\u00020\u00052\b\b\u0002\u0010\u0006\u001a\u00020\u00072\b\b\u0002\u0010\b\u001a\u00020\t2\b\b\u0002\u0010\n\u001a\u00020\u000b2\n\b\u0002\u0010\f\u001a\u0004\u0018\u00010\r2\n\b\u0002\u0010\u000e\u001a\u0004\u0018\u00010\u000f2\b\b\u0002\u0010\u0010\u001a\u00020\u00112\b\b\u0002\u0010\u0012\u001a\u00020\u00132\u001c\u0010\u0014\u001a\u0018\u0012\u0004\u0012\u00020\u0016\u0012\u0004\u0012\u00020\u00010\u0015¢\u0006\u0002\b\u0017¢\u0006\u0002\b\u0018H\u0007¢\u0006\u0002\u0010\u0019\u001a\u008d\u0001\u0010\u001b\u001a\u00020\u00012\f\u0010\u0002\u001a\b\u0012\u0004\u0012\u00020\u00010\u00032\b\b\u0002\u0010\u0004\u001a\u00020\u00052\b\b\u0002\u0010\u0006\u001a\u00020\u00072\b\b\u0002\u0010\b\u001a\u00020\t2\b\b\u0002\u0010\n\u001a\u00020\u000b2\n\b\u0002\u0010\f\u001a\u0004\u0018\u00010\r2\n\b\u0002\u0010\u000e\u001a\u0004\u0018\u00010\u000f2\b\b\u0002\u0010\u0010\u001a\u00020\u00112\b\b\u0002\u0010\u0012\u001a\u00020\u00132\u001c\u0010\u0014\u001a\u0018\u0012\u0004\u0012\u00020\u0016\u0012\u0004\u0012\u00020\u00010\u0015¢\u0006\u0002\b\u0017¢\u0006\u0002\b\u0018H\u0007¢\u0006\u0002\u0010\u0019\u001a\u008d\u0001\u0010\u001c\u001a\u00020\u00012\f\u0010\u0002\u001a\b\u0012\u0004\u0012\u00020\u00010\u00032\b\b\u0002\u0010\u0004\u001a\u00020\u00052\b\b\u0002\u0010\u0006\u001a\u00020\u00072\b\b\u0002\u0010\b\u001a\u00020\t2\b\b\u0002\u0010\n\u001a\u00020\u000b2\n\b\u0002\u0010\f\u001a\u0004\u0018\u00010\r2\n\b\u0002\u0010\u000e\u001a\u0004\u0018\u00010\u000f2\b\b\u0002\u0010\u0010\u001a\u00020\u00112\b\b\u0002\u0010\u0012\u001a\u00020\u00132\u001c\u0010\u0014\u001a\u0018\u0012\u0004\u0012\u00020\u0016\u0012\u0004\u0012\u00020\u00010\u0015¢\u0006\u0002\b\u0017¢\u0006\u0002\b\u0018H\u0007¢\u0006\u0002\u0010\u0019\u001a\u008d\u0001\u0010\u001d\u001a\u00020\u00012\f\u0010\u0002\u001a\b\u0012\u0004\u0012\u00020\u00010\u00032\b\b\u0002\u0010\u0004\u001a\u00020\u00052\b\b\u0002\u0010\u0006\u001a\u00020\u00072\b\b\u0002\u0010\b\u001a\u00020\t2\b\b\u0002\u0010\n\u001a\u00020\u000b2\n\b\u0002\u0010\f\u001a\u0004\u0018\u00010\r2\n\b\u0002\u0010\u000e\u001a\u0004\u0018\u00010\u000f2\b\b\u0002\u0010\u0010\u001a\u00020\u00112\b\b\u0002\u0010\u0012\u001a\u00020\u00132\u001c\u0010\u0014\u001a\u0018\u0012\u0004\u0012\u00020\u0016\u0012\u0004\u0012\u00020\u00010\u0015¢\u0006\u0002\b\u0017¢\u0006\u0002\b\u0018H\u0007¢\u0006\u0002\u0010\u0019¨\u0006\u001e"}, d2 = {"Button", "", "onClick", "Lkotlin/Function0;", "modifier", "Landroidx/compose/ui/Modifier;", "enabled", "", "shape", "Landroidx/compose/ui/graphics/Shape;", "colors", "Landroidx/compose/material3/ButtonColors;", "elevation", "Landroidx/compose/material3/ButtonElevation;", androidx.compose.material.OutlinedTextFieldKt.BorderId, "Landroidx/compose/foundation/BorderStroke;", "contentPadding", "Landroidx/compose/foundation/layout/PaddingValues;", "interactionSource", "Landroidx/compose/foundation/interaction/MutableInteractionSource;", "content", "Lkotlin/Function1;", "Landroidx/compose/foundation/layout/RowScope;", "Landroidx/compose/runtime/Composable;", "Lkotlin/ExtensionFunctionType;", "(Lkotlin/jvm/functions/Function0;Landroidx/compose/ui/Modifier;ZLandroidx/compose/ui/graphics/Shape;Landroidx/compose/material3/ButtonColors;Landroidx/compose/material3/ButtonElevation;Landroidx/compose/foundation/BorderStroke;Landroidx/compose/foundation/layout/PaddingValues;Landroidx/compose/foundation/interaction/MutableInteractionSource;Lkotlin/jvm/functions/Function3;Landroidx/compose/runtime/Composer;II)V", "ElevatedButton", "FilledTonalButton", "OutlinedButton", "TextButton", "material3_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class ButtonKt {
    public static final void Button(final Function0<Unit> function0, Modifier modifier, boolean enabled, Shape shape, ButtonColors colors, ButtonElevation elevation, BorderStroke border, PaddingValues contentPadding, MutableInteractionSource interactionSource, final Function3<? super RowScope, ? super Composer, ? super Integer, Unit> function3, Composer $composer, final int $changed, final int i) {
        boolean enabled2;
        Shape shape2;
        ButtonColors colors2;
        ButtonElevation elevation2;
        int i2;
        MutableInteractionSource interactionSource2;
        Modifier.Companion modifier2;
        Shape shape3;
        int $dirty;
        ButtonColors colors3;
        int i3;
        final PaddingValues contentPadding2;
        int $dirty2;
        BorderStroke border2;
        ButtonElevation elevation3;
        Object value$iv;
        ButtonColors colors4;
        float shadowElevation;
        ButtonColors colors5;
        ButtonElevation elevation4;
        Modifier modifier3;
        BorderStroke border3;
        PaddingValues contentPadding3;
        boolean enabled3;
        Shape shape4;
        MutableInteractionSource interactionSource3;
        int i4;
        int i5;
        int i6;
        Composer $composer2 = $composer.startRestartGroup(650121315);
        ComposerKt.sourceInformation($composer2, "C(Button)P(8,7,5,9,1,4!1,3,6)107@5444L5,108@5493L14,109@5558L17,112@5728L39,119@6094L977:Button.kt#uh7d8r");
        int $dirty3 = $changed;
        if ((i & 1) != 0) {
            $dirty3 |= 6;
        } else if (($changed & 6) == 0) {
            $dirty3 |= $composer2.changedInstance(function0) ? 4 : 2;
        }
        int i7 = i & 2;
        if (i7 != 0) {
            $dirty3 |= 48;
        } else if (($changed & 48) == 0) {
            $dirty3 |= $composer2.changed(modifier) ? 32 : 16;
        }
        int i8 = i & 4;
        if (i8 != 0) {
            $dirty3 |= 384;
            enabled2 = enabled;
        } else if (($changed & 384) == 0) {
            enabled2 = enabled;
            $dirty3 |= $composer2.changed(enabled2) ? 256 : 128;
        } else {
            enabled2 = enabled;
        }
        if (($changed & 3072) == 0) {
            if ((i & 8) == 0) {
                shape2 = shape;
                if ($composer2.changed(shape2)) {
                    i6 = 2048;
                    $dirty3 |= i6;
                }
            } else {
                shape2 = shape;
            }
            i6 = 1024;
            $dirty3 |= i6;
        } else {
            shape2 = shape;
        }
        if (($changed & 24576) == 0) {
            if ((i & 16) == 0) {
                colors2 = colors;
                if ($composer2.changed(colors2)) {
                    i5 = 16384;
                    $dirty3 |= i5;
                }
            } else {
                colors2 = colors;
            }
            i5 = 8192;
            $dirty3 |= i5;
        } else {
            colors2 = colors;
        }
        if ((196608 & $changed) == 0) {
            if ((i & 32) == 0) {
                elevation2 = elevation;
                if ($composer2.changed(elevation2)) {
                    i4 = 131072;
                    $dirty3 |= i4;
                }
            } else {
                elevation2 = elevation;
            }
            i4 = 65536;
            $dirty3 |= i4;
        } else {
            elevation2 = elevation;
        }
        int i9 = i & 64;
        if (i9 != 0) {
            $dirty3 |= 1572864;
        } else if ((1572864 & $changed) == 0) {
            $dirty3 |= $composer2.changed(border) ? 1048576 : 524288;
        }
        int i10 = i & 128;
        if (i10 != 0) {
            $dirty3 |= 12582912;
        } else if (($changed & 12582912) == 0) {
            $dirty3 |= $composer2.changed(contentPadding) ? 8388608 : 4194304;
        }
        int i11 = i & 256;
        if (i11 != 0) {
            $dirty3 |= 100663296;
            i2 = i11;
            interactionSource2 = interactionSource;
        } else if (($changed & 100663296) == 0) {
            i2 = i11;
            interactionSource2 = interactionSource;
            $dirty3 |= $composer2.changed(interactionSource2) ? AccessibilityEventCompat.TYPE_VIEW_TARGETED_BY_SCROLL : 33554432;
        } else {
            i2 = i11;
            interactionSource2 = interactionSource;
        }
        if ((i & 512) != 0) {
            $dirty3 |= 805306368;
        } else if (($changed & 805306368) == 0) {
            $dirty3 |= $composer2.changedInstance(function3) ? 536870912 : 268435456;
        }
        if ((306783379 & $dirty3) == 306783378 && $composer2.getSkipping()) {
            $composer2.skipToGroupEnd();
            modifier3 = modifier;
            border3 = border;
            contentPadding3 = contentPadding;
            shape4 = shape2;
            colors5 = colors2;
            interactionSource3 = interactionSource2;
            elevation4 = elevation2;
            enabled3 = enabled2;
        } else {
            $composer2.startDefaults();
            if (($changed & 1) == 0 || $composer2.getDefaultsInvalid()) {
                modifier2 = i7 != 0 ? Modifier.INSTANCE : modifier;
                boolean enabled4 = i8 != 0 ? true : enabled2;
                if ((i & 8) != 0) {
                    $dirty3 &= -7169;
                    shape3 = ButtonDefaults.INSTANCE.getShape($composer2, 6);
                } else {
                    shape3 = shape2;
                }
                if ((i & 16) != 0) {
                    $dirty = $dirty3 & (-57345);
                    colors3 = ButtonDefaults.INSTANCE.buttonColors($composer2, 6);
                } else {
                    $dirty = $dirty3;
                    colors3 = colors2;
                }
                if ((i & 32) != 0) {
                    i3 = i10;
                    $dirty &= -458753;
                    elevation2 = ButtonDefaults.INSTANCE.m1607buttonElevationR_JCAzs(0.0f, 0.0f, 0.0f, 0.0f, 0.0f, $composer2, ProfileVerifier.CompilationStatus.RESULT_CODE_ERROR_CANT_WRITE_PROFILE_VERIFICATION_RESULT_CACHE_FILE, 31);
                } else {
                    i3 = i10;
                }
                BorderStroke border4 = i9 != 0 ? null : border;
                PaddingValues contentPadding4 = i3 != 0 ? ButtonDefaults.INSTANCE.getContentPadding() : contentPadding;
                if (i2 != 0) {
                    $composer2.startReplaceableGroup(823568939);
                    ComposerKt.sourceInformation($composer2, "CC(remember):Button.kt#9igjgp");
                    Object it$iv = $composer2.rememberedValue();
                    if (it$iv == Composer.INSTANCE.getEmpty()) {
                        value$iv = InteractionSourceKt.MutableInteractionSource();
                        $composer2.updateRememberedValue(value$iv);
                    } else {
                        value$iv = it$iv;
                    }
                    $composer2.endReplaceableGroup();
                    interactionSource2 = (MutableInteractionSource) value$iv;
                    enabled2 = enabled4;
                    shape2 = shape3;
                    colors2 = colors3;
                    $dirty2 = $dirty;
                    contentPadding2 = contentPadding4;
                    border2 = border4;
                    elevation3 = elevation2;
                } else {
                    interactionSource2 = interactionSource;
                    contentPadding2 = contentPadding4;
                    enabled2 = enabled4;
                    shape2 = shape3;
                    colors2 = colors3;
                    $dirty2 = $dirty;
                    border2 = border4;
                    elevation3 = elevation2;
                }
            } else {
                $composer2.skipToGroupEnd();
                if ((i & 8) != 0) {
                    $dirty3 &= -7169;
                }
                if ((i & 16) != 0) {
                    $dirty3 &= -57345;
                }
                if ((i & 32) != 0) {
                    border2 = border;
                    contentPadding2 = contentPadding;
                    $dirty2 = $dirty3 & (-458753);
                    elevation3 = elevation2;
                    modifier2 = modifier;
                } else {
                    modifier2 = modifier;
                    border2 = border;
                    contentPadding2 = contentPadding;
                    $dirty2 = $dirty3;
                    elevation3 = elevation2;
                }
            }
            $composer2.endDefaults();
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventStart(650121315, $dirty2, -1, "androidx.compose.material3.Button (Button.kt:114)");
            }
            long containerColor = colors2.m1599containerColorvNxB06k$material3_release(enabled2);
            final long contentColor = colors2.m1600contentColorvNxB06k$material3_release(enabled2);
            $composer2.startReplaceableGroup(823569174);
            ComposerKt.sourceInformation($composer2, "117@5963L43");
            State<Dp> shadowElevation$material3_release = elevation3 == null ? null : elevation3.shadowElevation$material3_release(enabled2, interactionSource2, $composer2, (($dirty2 >> 6) & 14) | (($dirty2 >> 21) & 112) | (($dirty2 >> 9) & 896));
            $composer2.endReplaceableGroup();
            if (shadowElevation$material3_release != null) {
                colors4 = colors2;
                shadowElevation = shadowElevation$material3_release.getValue().m6108unboximpl();
            } else {
                colors4 = colors2;
                shadowElevation = Dp.m6094constructorimpl(0);
            }
            float tonalElevation = elevation3 != null ? elevation3.m1618tonalElevationu2uoSUM$material3_release(enabled2) : Dp.m6094constructorimpl(0);
            ButtonElevation elevation5 = elevation3;
            SurfaceKt.m2319Surfaceo_FOJdg(function0, SemanticsModifierKt.semantics$default(modifier2, false, new Function1<SemanticsPropertyReceiver, Unit>() { // from class: androidx.compose.material3.ButtonKt$Button$2
                @Override // kotlin.jvm.functions.Function1
                public /* bridge */ /* synthetic */ Unit invoke(SemanticsPropertyReceiver semanticsPropertyReceiver) {
                    invoke2(semanticsPropertyReceiver);
                    return Unit.INSTANCE;
                }

                /* renamed from: invoke, reason: avoid collision after fix types in other method */
                public final void invoke2(SemanticsPropertyReceiver $this$semantics) {
                    SemanticsPropertiesKt.m5415setRolekuIjeqM($this$semantics, Role.INSTANCE.m5399getButtono7Vup1c());
                }
            }, 1, null), enabled2, shape2, containerColor, contentColor, tonalElevation, shadowElevation, border2, interactionSource2, ComposableLambdaKt.composableLambda($composer2, 956488494, true, new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.ButtonKt$Button$3
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
                    ComposerKt.sourceInformation($composer3, "C133@6591L10,131@6482L583:Button.kt#uh7d8r");
                    if (($changed2 & 3) != 2 || !$composer3.getSkipping()) {
                        if (ComposerKt.isTraceInProgress()) {
                            ComposerKt.traceEventStart(956488494, $changed2, -1, "androidx.compose.material3.Button.<anonymous> (Button.kt:131)");
                        }
                        long j = contentColor;
                        TextStyle labelLarge = MaterialTheme.INSTANCE.getTypography($composer3, 6).getLabelLarge();
                        final PaddingValues paddingValues = contentPadding2;
                        final Function3<RowScope, Composer, Integer, Unit> function32 = function3;
                        ProvideContentColorTextStyleKt.m2103ProvideContentColorTextStyle3JVO9M(j, labelLarge, ComposableLambdaKt.composableLambda($composer3, 1327513942, true, new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.ButtonKt$Button$3.1
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

                            /* JADX WARN: Removed duplicated region for block: B:24:0x0167  */
                            /* JADX WARN: Removed duplicated region for block: B:26:? A[RETURN, SYNTHETIC] */
                            /*
                                Code decompiled incorrectly, please refer to instructions dump.
                                To view partially-correct add '--show-bad-code' argument
                            */
                            public final void invoke(androidx.compose.runtime.Composer r25, int r26) {
                                /*
                                    Method dump skipped, instructions count: 363
                                    To view this dump add '--comments-level debug' option
                                */
                                throw new UnsupportedOperationException("Method not decompiled: androidx.compose.material3.ButtonKt$Button$3.AnonymousClass1.invoke(androidx.compose.runtime.Composer, int):void");
                            }
                        }), $composer3, 384);
                        if (ComposerKt.isTraceInProgress()) {
                            ComposerKt.traceEventEnd();
                            return;
                        }
                        return;
                    }
                    $composer3.skipToGroupEnd();
                }
            }), $composer2, ($dirty2 & 14) | ($dirty2 & 896) | ($dirty2 & 7168) | (($dirty2 << 6) & 234881024) | (($dirty2 << 3) & 1879048192), 6, 0);
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventEnd();
            }
            colors5 = colors4;
            elevation4 = elevation5;
            modifier3 = modifier2;
            border3 = border2;
            contentPadding3 = contentPadding2;
            enabled3 = enabled2;
            shape4 = shape2;
            interactionSource3 = interactionSource2;
        }
        ScopeUpdateScope endRestartGroup = $composer2.endRestartGroup();
        if (endRestartGroup != null) {
            final Modifier modifier4 = modifier3;
            final boolean z = enabled3;
            final Shape shape5 = shape4;
            final ButtonColors buttonColors = colors5;
            final ButtonElevation buttonElevation = elevation4;
            final BorderStroke borderStroke = border3;
            final PaddingValues paddingValues = contentPadding3;
            final MutableInteractionSource mutableInteractionSource = interactionSource3;
            endRestartGroup.updateScope(new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.ButtonKt$Button$4
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

                public final void invoke(Composer composer, int i12) {
                    ButtonKt.Button(function0, modifier4, z, shape5, buttonColors, buttonElevation, borderStroke, paddingValues, mutableInteractionSource, function3, composer, RecomposeScopeImplKt.updateChangedFlags($changed | 1), i);
                }
            });
        }
    }

    public static final void ElevatedButton(final Function0<Unit> function0, Modifier modifier, boolean enabled, Shape shape, ButtonColors colors, ButtonElevation elevation, BorderStroke border, PaddingValues contentPadding, MutableInteractionSource interactionSource, final Function3<? super RowScope, ? super Composer, ? super Integer, Unit> function3, Composer $composer, final int $changed, final int i) {
        boolean enabled2;
        Shape shape2;
        ButtonColors colors2;
        ButtonElevation elevation2;
        int i2;
        MutableInteractionSource interactionSource2;
        Modifier.Companion modifier2;
        Shape shape3;
        int $dirty;
        ButtonColors colors3;
        int i3;
        PaddingValues contentPadding2;
        int $dirty2;
        BorderStroke border2;
        ButtonElevation elevation3;
        Object value$iv;
        Modifier modifier3;
        ButtonElevation elevation4;
        BorderStroke border3;
        PaddingValues contentPadding3;
        boolean enabled3;
        Shape shape4;
        ButtonColors colors4;
        MutableInteractionSource interactionSource3;
        int i4;
        int i5;
        int i6;
        Composer $composer2 = $composer.startRestartGroup(1466887385);
        ComposerKt.sourceInformation($composer2, "C(ElevatedButton)P(8,7,5,9,1,4!1,3,6)198@9938L13,199@9995L22,200@10068L25,203@10246L39,206@10340L314:Button.kt#uh7d8r");
        int $dirty3 = $changed;
        if ((i & 1) != 0) {
            $dirty3 |= 6;
        } else if (($changed & 6) == 0) {
            $dirty3 |= $composer2.changedInstance(function0) ? 4 : 2;
        }
        int i7 = i & 2;
        if (i7 != 0) {
            $dirty3 |= 48;
        } else if (($changed & 48) == 0) {
            $dirty3 |= $composer2.changed(modifier) ? 32 : 16;
        }
        int i8 = i & 4;
        if (i8 != 0) {
            $dirty3 |= 384;
            enabled2 = enabled;
        } else if (($changed & 384) == 0) {
            enabled2 = enabled;
            $dirty3 |= $composer2.changed(enabled2) ? 256 : 128;
        } else {
            enabled2 = enabled;
        }
        if (($changed & 3072) == 0) {
            if ((i & 8) == 0) {
                shape2 = shape;
                if ($composer2.changed(shape2)) {
                    i6 = 2048;
                    $dirty3 |= i6;
                }
            } else {
                shape2 = shape;
            }
            i6 = 1024;
            $dirty3 |= i6;
        } else {
            shape2 = shape;
        }
        if (($changed & 24576) == 0) {
            if ((i & 16) == 0) {
                colors2 = colors;
                if ($composer2.changed(colors2)) {
                    i5 = 16384;
                    $dirty3 |= i5;
                }
            } else {
                colors2 = colors;
            }
            i5 = 8192;
            $dirty3 |= i5;
        } else {
            colors2 = colors;
        }
        if ((196608 & $changed) == 0) {
            if ((i & 32) == 0) {
                elevation2 = elevation;
                if ($composer2.changed(elevation2)) {
                    i4 = 131072;
                    $dirty3 |= i4;
                }
            } else {
                elevation2 = elevation;
            }
            i4 = 65536;
            $dirty3 |= i4;
        } else {
            elevation2 = elevation;
        }
        int i9 = i & 64;
        if (i9 != 0) {
            $dirty3 |= 1572864;
        } else if ((1572864 & $changed) == 0) {
            $dirty3 |= $composer2.changed(border) ? 1048576 : 524288;
        }
        int i10 = i & 128;
        if (i10 != 0) {
            $dirty3 |= 12582912;
        } else if (($changed & 12582912) == 0) {
            $dirty3 |= $composer2.changed(contentPadding) ? 8388608 : 4194304;
        }
        int i11 = i & 256;
        if (i11 != 0) {
            $dirty3 |= 100663296;
            i2 = i11;
            interactionSource2 = interactionSource;
        } else if (($changed & 100663296) == 0) {
            i2 = i11;
            interactionSource2 = interactionSource;
            $dirty3 |= $composer2.changed(interactionSource2) ? AccessibilityEventCompat.TYPE_VIEW_TARGETED_BY_SCROLL : 33554432;
        } else {
            i2 = i11;
            interactionSource2 = interactionSource;
        }
        if ((i & 512) != 0) {
            $dirty3 |= 805306368;
        } else if (($changed & 805306368) == 0) {
            $dirty3 |= $composer2.changedInstance(function3) ? 536870912 : 268435456;
        }
        if (($dirty3 & 306783379) == 306783378 && $composer2.getSkipping()) {
            $composer2.skipToGroupEnd();
            border3 = border;
            contentPadding3 = contentPadding;
            enabled3 = enabled2;
            shape4 = shape2;
            colors4 = colors2;
            interactionSource3 = interactionSource2;
            elevation4 = elevation2;
            modifier3 = modifier;
        } else {
            $composer2.startDefaults();
            if (($changed & 1) == 0 || $composer2.getDefaultsInvalid()) {
                modifier2 = i7 != 0 ? Modifier.INSTANCE : modifier;
                boolean enabled4 = i8 != 0 ? true : enabled2;
                if ((i & 8) != 0) {
                    $dirty3 &= -7169;
                    shape3 = ButtonDefaults.INSTANCE.getElevatedShape($composer2, 6);
                } else {
                    shape3 = shape2;
                }
                if ((i & 16) != 0) {
                    $dirty = $dirty3 & (-57345);
                    colors3 = ButtonDefaults.INSTANCE.elevatedButtonColors($composer2, 6);
                } else {
                    $dirty = $dirty3;
                    colors3 = colors2;
                }
                if ((i & 32) != 0) {
                    i3 = i10;
                    $dirty &= -458753;
                    elevation2 = ButtonDefaults.INSTANCE.m1609elevatedButtonElevationR_JCAzs(0.0f, 0.0f, 0.0f, 0.0f, 0.0f, $composer2, ProfileVerifier.CompilationStatus.RESULT_CODE_ERROR_CANT_WRITE_PROFILE_VERIFICATION_RESULT_CACHE_FILE, 31);
                } else {
                    i3 = i10;
                }
                BorderStroke border4 = i9 != 0 ? null : border;
                PaddingValues contentPadding4 = i3 != 0 ? ButtonDefaults.INSTANCE.getContentPadding() : contentPadding;
                if (i2 != 0) {
                    $composer2.startReplaceableGroup(-446997561);
                    ComposerKt.sourceInformation($composer2, "CC(remember):Button.kt#9igjgp");
                    Object it$iv = $composer2.rememberedValue();
                    if (it$iv == Composer.INSTANCE.getEmpty()) {
                        value$iv = InteractionSourceKt.MutableInteractionSource();
                        $composer2.updateRememberedValue(value$iv);
                    } else {
                        value$iv = it$iv;
                    }
                    $composer2.endReplaceableGroup();
                    interactionSource2 = (MutableInteractionSource) value$iv;
                    enabled2 = enabled4;
                    shape2 = shape3;
                    colors2 = colors3;
                    $dirty2 = $dirty;
                    contentPadding2 = contentPadding4;
                    border2 = border4;
                    elevation3 = elevation2;
                } else {
                    interactionSource2 = interactionSource;
                    contentPadding2 = contentPadding4;
                    enabled2 = enabled4;
                    shape2 = shape3;
                    colors2 = colors3;
                    $dirty2 = $dirty;
                    border2 = border4;
                    elevation3 = elevation2;
                }
            } else {
                $composer2.skipToGroupEnd();
                if ((i & 8) != 0) {
                    $dirty3 &= -7169;
                }
                if ((i & 16) != 0) {
                    $dirty3 &= -57345;
                }
                if ((i & 32) != 0) {
                    border2 = border;
                    contentPadding2 = contentPadding;
                    $dirty2 = $dirty3 & (-458753);
                    elevation3 = elevation2;
                    modifier2 = modifier;
                } else {
                    modifier2 = modifier;
                    border2 = border;
                    contentPadding2 = contentPadding;
                    $dirty2 = $dirty3;
                    elevation3 = elevation2;
                }
            }
            $composer2.endDefaults();
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventStart(1466887385, $dirty2, -1, "androidx.compose.material3.ElevatedButton (Button.kt:206)");
            }
            Button(function0, modifier2, enabled2, shape2, colors2, elevation3, border2, contentPadding2, interactionSource2, function3, $composer2, ($dirty2 & 14) | ($dirty2 & 112) | ($dirty2 & 896) | ($dirty2 & 7168) | (57344 & $dirty2) | (458752 & $dirty2) | (3670016 & $dirty2) | (29360128 & $dirty2) | (234881024 & $dirty2) | (1879048192 & $dirty2), 0);
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventEnd();
            }
            modifier3 = modifier2;
            elevation4 = elevation3;
            border3 = border2;
            contentPadding3 = contentPadding2;
            enabled3 = enabled2;
            shape4 = shape2;
            colors4 = colors2;
            interactionSource3 = interactionSource2;
        }
        ScopeUpdateScope endRestartGroup = $composer2.endRestartGroup();
        if (endRestartGroup != null) {
            final Modifier modifier4 = modifier3;
            final boolean z = enabled3;
            final Shape shape5 = shape4;
            final ButtonColors buttonColors = colors4;
            final ButtonElevation buttonElevation = elevation4;
            final BorderStroke borderStroke = border3;
            final PaddingValues paddingValues = contentPadding3;
            final MutableInteractionSource mutableInteractionSource = interactionSource3;
            endRestartGroup.updateScope(new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.ButtonKt$ElevatedButton$2
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

                public final void invoke(Composer composer, int i12) {
                    ButtonKt.ElevatedButton(function0, modifier4, z, shape5, buttonColors, buttonElevation, borderStroke, paddingValues, mutableInteractionSource, function3, composer, RecomposeScopeImplKt.updateChangedFlags($changed | 1), i);
                }
            });
        }
    }

    public static final void FilledTonalButton(final Function0<Unit> function0, Modifier modifier, boolean enabled, Shape shape, ButtonColors colors, ButtonElevation elevation, BorderStroke border, PaddingValues contentPadding, MutableInteractionSource interactionSource, final Function3<? super RowScope, ? super Composer, ? super Integer, Unit> function3, Composer $composer, final int $changed, final int i) {
        boolean enabled2;
        Shape shape2;
        ButtonColors colors2;
        ButtonElevation elevation2;
        int i2;
        MutableInteractionSource interactionSource2;
        Modifier.Companion modifier2;
        Shape shape3;
        int $dirty;
        ButtonColors colors3;
        int i3;
        PaddingValues contentPadding2;
        int $dirty2;
        BorderStroke border2;
        ButtonElevation elevation3;
        Object value$iv;
        Modifier modifier3;
        ButtonElevation elevation4;
        BorderStroke border3;
        PaddingValues contentPadding3;
        boolean enabled3;
        Shape shape4;
        ButtonColors colors4;
        MutableInteractionSource interactionSource3;
        int i4;
        int i5;
        int i6;
        Composer $composer2 = $composer.startRestartGroup(-1717924381);
        ComposerKt.sourceInformation($composer2, "C(FilledTonalButton)P(8,7,5,9,1,4!1,3,6)268@13576L16,269@13636L25,270@13712L28,273@13893L39,276@13987L314:Button.kt#uh7d8r");
        int $dirty3 = $changed;
        if ((i & 1) != 0) {
            $dirty3 |= 6;
        } else if (($changed & 6) == 0) {
            $dirty3 |= $composer2.changedInstance(function0) ? 4 : 2;
        }
        int i7 = i & 2;
        if (i7 != 0) {
            $dirty3 |= 48;
        } else if (($changed & 48) == 0) {
            $dirty3 |= $composer2.changed(modifier) ? 32 : 16;
        }
        int i8 = i & 4;
        if (i8 != 0) {
            $dirty3 |= 384;
            enabled2 = enabled;
        } else if (($changed & 384) == 0) {
            enabled2 = enabled;
            $dirty3 |= $composer2.changed(enabled2) ? 256 : 128;
        } else {
            enabled2 = enabled;
        }
        if (($changed & 3072) == 0) {
            if ((i & 8) == 0) {
                shape2 = shape;
                if ($composer2.changed(shape2)) {
                    i6 = 2048;
                    $dirty3 |= i6;
                }
            } else {
                shape2 = shape;
            }
            i6 = 1024;
            $dirty3 |= i6;
        } else {
            shape2 = shape;
        }
        if (($changed & 24576) == 0) {
            if ((i & 16) == 0) {
                colors2 = colors;
                if ($composer2.changed(colors2)) {
                    i5 = 16384;
                    $dirty3 |= i5;
                }
            } else {
                colors2 = colors;
            }
            i5 = 8192;
            $dirty3 |= i5;
        } else {
            colors2 = colors;
        }
        if ((196608 & $changed) == 0) {
            if ((i & 32) == 0) {
                elevation2 = elevation;
                if ($composer2.changed(elevation2)) {
                    i4 = 131072;
                    $dirty3 |= i4;
                }
            } else {
                elevation2 = elevation;
            }
            i4 = 65536;
            $dirty3 |= i4;
        } else {
            elevation2 = elevation;
        }
        int i9 = i & 64;
        if (i9 != 0) {
            $dirty3 |= 1572864;
        } else if ((1572864 & $changed) == 0) {
            $dirty3 |= $composer2.changed(border) ? 1048576 : 524288;
        }
        int i10 = i & 128;
        if (i10 != 0) {
            $dirty3 |= 12582912;
        } else if (($changed & 12582912) == 0) {
            $dirty3 |= $composer2.changed(contentPadding) ? 8388608 : 4194304;
        }
        int i11 = i & 256;
        if (i11 != 0) {
            $dirty3 |= 100663296;
            i2 = i11;
            interactionSource2 = interactionSource;
        } else if (($changed & 100663296) == 0) {
            i2 = i11;
            interactionSource2 = interactionSource;
            $dirty3 |= $composer2.changed(interactionSource2) ? AccessibilityEventCompat.TYPE_VIEW_TARGETED_BY_SCROLL : 33554432;
        } else {
            i2 = i11;
            interactionSource2 = interactionSource;
        }
        if ((i & 512) != 0) {
            $dirty3 |= 805306368;
        } else if (($changed & 805306368) == 0) {
            $dirty3 |= $composer2.changedInstance(function3) ? 536870912 : 268435456;
        }
        if (($dirty3 & 306783379) == 306783378 && $composer2.getSkipping()) {
            $composer2.skipToGroupEnd();
            border3 = border;
            contentPadding3 = contentPadding;
            enabled3 = enabled2;
            shape4 = shape2;
            colors4 = colors2;
            interactionSource3 = interactionSource2;
            elevation4 = elevation2;
            modifier3 = modifier;
        } else {
            $composer2.startDefaults();
            if (($changed & 1) == 0 || $composer2.getDefaultsInvalid()) {
                modifier2 = i7 != 0 ? Modifier.INSTANCE : modifier;
                boolean enabled4 = i8 != 0 ? true : enabled2;
                if ((i & 8) != 0) {
                    $dirty3 &= -7169;
                    shape3 = ButtonDefaults.INSTANCE.getFilledTonalShape($composer2, 6);
                } else {
                    shape3 = shape2;
                }
                if ((i & 16) != 0) {
                    $dirty = $dirty3 & (-57345);
                    colors3 = ButtonDefaults.INSTANCE.filledTonalButtonColors($composer2, 6);
                } else {
                    $dirty = $dirty3;
                    colors3 = colors2;
                }
                if ((i & 32) != 0) {
                    i3 = i10;
                    $dirty &= -458753;
                    elevation2 = ButtonDefaults.INSTANCE.m1611filledTonalButtonElevationR_JCAzs(0.0f, 0.0f, 0.0f, 0.0f, 0.0f, $composer2, ProfileVerifier.CompilationStatus.RESULT_CODE_ERROR_CANT_WRITE_PROFILE_VERIFICATION_RESULT_CACHE_FILE, 31);
                } else {
                    i3 = i10;
                }
                BorderStroke border4 = i9 != 0 ? null : border;
                PaddingValues contentPadding4 = i3 != 0 ? ButtonDefaults.INSTANCE.getContentPadding() : contentPadding;
                if (i2 != 0) {
                    $composer2.startReplaceableGroup(1269258330);
                    ComposerKt.sourceInformation($composer2, "CC(remember):Button.kt#9igjgp");
                    Object it$iv = $composer2.rememberedValue();
                    if (it$iv == Composer.INSTANCE.getEmpty()) {
                        value$iv = InteractionSourceKt.MutableInteractionSource();
                        $composer2.updateRememberedValue(value$iv);
                    } else {
                        value$iv = it$iv;
                    }
                    $composer2.endReplaceableGroup();
                    interactionSource2 = (MutableInteractionSource) value$iv;
                    enabled2 = enabled4;
                    shape2 = shape3;
                    colors2 = colors3;
                    $dirty2 = $dirty;
                    contentPadding2 = contentPadding4;
                    border2 = border4;
                    elevation3 = elevation2;
                } else {
                    interactionSource2 = interactionSource;
                    contentPadding2 = contentPadding4;
                    enabled2 = enabled4;
                    shape2 = shape3;
                    colors2 = colors3;
                    $dirty2 = $dirty;
                    border2 = border4;
                    elevation3 = elevation2;
                }
            } else {
                $composer2.skipToGroupEnd();
                if ((i & 8) != 0) {
                    $dirty3 &= -7169;
                }
                if ((i & 16) != 0) {
                    $dirty3 &= -57345;
                }
                if ((i & 32) != 0) {
                    border2 = border;
                    contentPadding2 = contentPadding;
                    $dirty2 = $dirty3 & (-458753);
                    elevation3 = elevation2;
                    modifier2 = modifier;
                } else {
                    modifier2 = modifier;
                    border2 = border;
                    contentPadding2 = contentPadding;
                    $dirty2 = $dirty3;
                    elevation3 = elevation2;
                }
            }
            $composer2.endDefaults();
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventStart(-1717924381, $dirty2, -1, "androidx.compose.material3.FilledTonalButton (Button.kt:276)");
            }
            Button(function0, modifier2, enabled2, shape2, colors2, elevation3, border2, contentPadding2, interactionSource2, function3, $composer2, ($dirty2 & 14) | ($dirty2 & 112) | ($dirty2 & 896) | ($dirty2 & 7168) | (57344 & $dirty2) | (458752 & $dirty2) | (3670016 & $dirty2) | (29360128 & $dirty2) | (234881024 & $dirty2) | (1879048192 & $dirty2), 0);
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventEnd();
            }
            modifier3 = modifier2;
            elevation4 = elevation3;
            border3 = border2;
            contentPadding3 = contentPadding2;
            enabled3 = enabled2;
            shape4 = shape2;
            colors4 = colors2;
            interactionSource3 = interactionSource2;
        }
        ScopeUpdateScope endRestartGroup = $composer2.endRestartGroup();
        if (endRestartGroup != null) {
            final Modifier modifier4 = modifier3;
            final boolean z = enabled3;
            final Shape shape5 = shape4;
            final ButtonColors buttonColors = colors4;
            final ButtonElevation buttonElevation = elevation4;
            final BorderStroke borderStroke = border3;
            final PaddingValues paddingValues = contentPadding3;
            final MutableInteractionSource mutableInteractionSource = interactionSource3;
            endRestartGroup.updateScope(new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.ButtonKt$FilledTonalButton$2
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

                public final void invoke(Composer composer, int i12) {
                    ButtonKt.FilledTonalButton(function0, modifier4, z, shape5, buttonColors, buttonElevation, borderStroke, paddingValues, mutableInteractionSource, function3, composer, RecomposeScopeImplKt.updateChangedFlags($changed | 1), i);
                }
            });
        }
    }

    public static final void OutlinedButton(final Function0<Unit> function0, Modifier modifier, boolean enabled, Shape shape, ButtonColors colors, ButtonElevation elevation, BorderStroke border, PaddingValues contentPadding, MutableInteractionSource interactionSource, final Function3<? super RowScope, ? super Composer, ? super Integer, Unit> function3, Composer $composer, final int $changed, final int i) {
        Shape shape2;
        ButtonColors buttonColors;
        ButtonElevation buttonElevation;
        BorderStroke borderStroke;
        Modifier.Companion modifier2;
        boolean enabled2;
        Shape shape3;
        ButtonColors colors2;
        ButtonElevation elevation2;
        BorderStroke border2;
        PaddingValues contentPadding2;
        MutableInteractionSource interactionSource2;
        Object value$iv;
        MutableInteractionSource interactionSource3;
        Modifier modifier3;
        boolean enabled3;
        Shape shape4;
        BorderStroke border3;
        ButtonColors colors3;
        ButtonElevation elevation3;
        PaddingValues contentPadding3;
        int i2;
        int i3;
        int i4;
        Composer $composer2 = $composer.startRestartGroup(-1694808287);
        ComposerKt.sourceInformation($composer2, "C(OutlinedButton)P(8,7,5,9,1,4!1,3,6)337@17120L13,338@17177L22,340@17284L20,342@17423L39,345@17517L314:Button.kt#uh7d8r");
        int $dirty = $changed;
        if ((i & 1) != 0) {
            $dirty |= 6;
        } else if (($changed & 6) == 0) {
            $dirty |= $composer2.changedInstance(function0) ? 4 : 2;
        }
        int i5 = i & 2;
        if (i5 != 0) {
            $dirty |= 48;
        } else if (($changed & 48) == 0) {
            $dirty |= $composer2.changed(modifier) ? 32 : 16;
        }
        int i6 = i & 4;
        if (i6 != 0) {
            $dirty |= 384;
        } else if (($changed & 384) == 0) {
            $dirty |= $composer2.changed(enabled) ? 256 : 128;
        }
        if (($changed & 3072) == 0) {
            if ((i & 8) == 0) {
                shape2 = shape;
                if ($composer2.changed(shape2)) {
                    i4 = 2048;
                    $dirty |= i4;
                }
            } else {
                shape2 = shape;
            }
            i4 = 1024;
            $dirty |= i4;
        } else {
            shape2 = shape;
        }
        if (($changed & 24576) == 0) {
            if ((i & 16) == 0) {
                buttonColors = colors;
                if ($composer2.changed(buttonColors)) {
                    i3 = 16384;
                    $dirty |= i3;
                }
            } else {
                buttonColors = colors;
            }
            i3 = 8192;
            $dirty |= i3;
        } else {
            buttonColors = colors;
        }
        int i7 = i & 32;
        if (i7 != 0) {
            $dirty |= ProfileVerifier.CompilationStatus.RESULT_CODE_ERROR_CANT_WRITE_PROFILE_VERIFICATION_RESULT_CACHE_FILE;
            buttonElevation = elevation;
        } else if ((196608 & $changed) == 0) {
            buttonElevation = elevation;
            $dirty |= $composer2.changed(buttonElevation) ? 131072 : 65536;
        } else {
            buttonElevation = elevation;
        }
        if ((1572864 & $changed) == 0) {
            if ((i & 64) == 0) {
                borderStroke = border;
                if ($composer2.changed(borderStroke)) {
                    i2 = 1048576;
                    $dirty |= i2;
                }
            } else {
                borderStroke = border;
            }
            i2 = 524288;
            $dirty |= i2;
        } else {
            borderStroke = border;
        }
        int i8 = i & 128;
        if (i8 != 0) {
            $dirty |= 12582912;
        } else if (($changed & 12582912) == 0) {
            $dirty |= $composer2.changed(contentPadding) ? 8388608 : 4194304;
        }
        int i9 = i & 256;
        if (i9 != 0) {
            $dirty |= 100663296;
        } else if (($changed & 100663296) == 0) {
            $dirty |= $composer2.changed(interactionSource) ? AccessibilityEventCompat.TYPE_VIEW_TARGETED_BY_SCROLL : 33554432;
        }
        if ((i & 512) != 0) {
            $dirty |= 805306368;
        } else if (($changed & 805306368) == 0) {
            $dirty |= $composer2.changedInstance(function3) ? 536870912 : 268435456;
        }
        if (($dirty & 306783379) == 306783378 && $composer2.getSkipping()) {
            $composer2.skipToGroupEnd();
            enabled3 = enabled;
            contentPadding3 = contentPadding;
            interactionSource3 = interactionSource;
            shape4 = shape2;
            colors3 = buttonColors;
            elevation3 = buttonElevation;
            border3 = borderStroke;
            modifier3 = modifier;
        } else {
            $composer2.startDefaults();
            if (($changed & 1) == 0 || $composer2.getDefaultsInvalid()) {
                modifier2 = i5 != 0 ? Modifier.INSTANCE : modifier;
                enabled2 = i6 != 0 ? true : enabled;
                if ((i & 8) != 0) {
                    shape3 = ButtonDefaults.INSTANCE.getOutlinedShape($composer2, 6);
                    $dirty &= -7169;
                } else {
                    shape3 = shape2;
                }
                if ((i & 16) != 0) {
                    colors2 = ButtonDefaults.INSTANCE.outlinedButtonColors($composer2, 6);
                    $dirty &= -57345;
                } else {
                    colors2 = buttonColors;
                }
                elevation2 = i7 != 0 ? null : buttonElevation;
                if ((i & 64) != 0) {
                    border2 = ButtonDefaults.INSTANCE.getOutlinedButtonBorder($composer2, 6);
                    $dirty &= -3670017;
                } else {
                    border2 = borderStroke;
                }
                contentPadding2 = i8 != 0 ? ButtonDefaults.INSTANCE.getContentPadding() : contentPadding;
                if (i9 != 0) {
                    $composer2.startReplaceableGroup(-219967464);
                    ComposerKt.sourceInformation($composer2, "CC(remember):Button.kt#9igjgp");
                    Object it$iv = $composer2.rememberedValue();
                    if (it$iv == Composer.INSTANCE.getEmpty()) {
                        value$iv = InteractionSourceKt.MutableInteractionSource();
                        $composer2.updateRememberedValue(value$iv);
                    } else {
                        value$iv = it$iv;
                    }
                    interactionSource2 = (MutableInteractionSource) value$iv;
                    $composer2.endReplaceableGroup();
                } else {
                    interactionSource2 = interactionSource;
                }
            } else {
                $composer2.skipToGroupEnd();
                if ((i & 8) != 0) {
                    $dirty &= -7169;
                }
                if ((i & 16) != 0) {
                    $dirty &= -57345;
                }
                if ((i & 64) != 0) {
                    modifier2 = modifier;
                    enabled2 = enabled;
                    contentPadding2 = contentPadding;
                    $dirty &= -3670017;
                    shape3 = shape2;
                    colors2 = buttonColors;
                    elevation2 = buttonElevation;
                    border2 = borderStroke;
                    interactionSource2 = interactionSource;
                } else {
                    modifier2 = modifier;
                    enabled2 = enabled;
                    contentPadding2 = contentPadding;
                    interactionSource2 = interactionSource;
                    shape3 = shape2;
                    colors2 = buttonColors;
                    elevation2 = buttonElevation;
                    border2 = borderStroke;
                }
            }
            $composer2.endDefaults();
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventStart(-1694808287, $dirty, -1, "androidx.compose.material3.OutlinedButton (Button.kt:345)");
            }
            Button(function0, modifier2, enabled2, shape3, colors2, elevation2, border2, contentPadding2, interactionSource2, function3, $composer2, ($dirty & 14) | ($dirty & 112) | ($dirty & 896) | ($dirty & 7168) | (57344 & $dirty) | (458752 & $dirty) | (3670016 & $dirty) | (29360128 & $dirty) | (234881024 & $dirty) | (1879048192 & $dirty), 0);
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventEnd();
            }
            interactionSource3 = interactionSource2;
            modifier3 = modifier2;
            enabled3 = enabled2;
            shape4 = shape3;
            border3 = border2;
            colors3 = colors2;
            elevation3 = elevation2;
            contentPadding3 = contentPadding2;
        }
        ScopeUpdateScope endRestartGroup = $composer2.endRestartGroup();
        if (endRestartGroup != null) {
            final Modifier modifier4 = modifier3;
            final boolean z = enabled3;
            final Shape shape5 = shape4;
            final ButtonColors buttonColors2 = colors3;
            final ButtonElevation buttonElevation2 = elevation3;
            final BorderStroke borderStroke2 = border3;
            final PaddingValues paddingValues = contentPadding3;
            final MutableInteractionSource mutableInteractionSource = interactionSource3;
            endRestartGroup.updateScope(new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.ButtonKt$OutlinedButton$2
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
                    ButtonKt.OutlinedButton(function0, modifier4, z, shape5, buttonColors2, buttonElevation2, borderStroke2, paddingValues, mutableInteractionSource, function3, composer, RecomposeScopeImplKt.updateChangedFlags($changed | 1), i);
                }
            });
        }
    }

    public static final void TextButton(final Function0<Unit> function0, Modifier modifier, boolean enabled, Shape shape, ButtonColors colors, ButtonElevation elevation, BorderStroke border, PaddingValues contentPadding, MutableInteractionSource interactionSource, final Function3<? super RowScope, ? super Composer, ? super Integer, Unit> function3, Composer $composer, final int $changed, final int i) {
        ButtonColors colors2;
        ButtonElevation elevation2;
        BorderStroke border2;
        boolean enabled2;
        Shape shape2;
        Modifier modifier2;
        Modifier modifier3;
        PaddingValues contentPadding2;
        MutableInteractionSource interactionSource2;
        int $dirty;
        BorderStroke border3;
        Object value$iv;
        Modifier modifier4;
        BorderStroke border4;
        PaddingValues contentPadding3;
        MutableInteractionSource interactionSource3;
        boolean enabled3;
        Shape shape3;
        ButtonColors colors3;
        ButtonElevation elevation3;
        int i2;
        int i3;
        Composer $composer2 = $composer.startRestartGroup(-2106428362);
        ComposerKt.sourceInformation($composer2, "C(TextButton)P(8,7,5,9,1,4!1,3,6)408@20786L9,409@20839L18,413@21060L39,416@21154L314:Button.kt#uh7d8r");
        int $dirty2 = $changed;
        if ((i & 1) != 0) {
            $dirty2 |= 6;
        } else if (($changed & 6) == 0) {
            $dirty2 |= $composer2.changedInstance(function0) ? 4 : 2;
        }
        int i4 = i & 2;
        if (i4 != 0) {
            $dirty2 |= 48;
        } else if (($changed & 48) == 0) {
            $dirty2 |= $composer2.changed(modifier) ? 32 : 16;
        }
        int i5 = i & 4;
        if (i5 != 0) {
            $dirty2 |= 384;
        } else if (($changed & 384) == 0) {
            $dirty2 |= $composer2.changed(enabled) ? 256 : 128;
        }
        if (($changed & 3072) == 0) {
            if ((i & 8) == 0 && $composer2.changed(shape)) {
                i3 = 2048;
                $dirty2 |= i3;
            }
            i3 = 1024;
            $dirty2 |= i3;
        }
        if (($changed & 24576) == 0) {
            if ((i & 16) == 0) {
                colors2 = colors;
                if ($composer2.changed(colors2)) {
                    i2 = 16384;
                    $dirty2 |= i2;
                }
            } else {
                colors2 = colors;
            }
            i2 = 8192;
            $dirty2 |= i2;
        } else {
            colors2 = colors;
        }
        int i6 = i & 32;
        if (i6 != 0) {
            $dirty2 |= ProfileVerifier.CompilationStatus.RESULT_CODE_ERROR_CANT_WRITE_PROFILE_VERIFICATION_RESULT_CACHE_FILE;
            elevation2 = elevation;
        } else if ((196608 & $changed) == 0) {
            elevation2 = elevation;
            $dirty2 |= $composer2.changed(elevation2) ? 131072 : 65536;
        } else {
            elevation2 = elevation;
        }
        int i7 = i & 64;
        if (i7 != 0) {
            $dirty2 |= 1572864;
            border2 = border;
        } else if ((1572864 & $changed) == 0) {
            border2 = border;
            $dirty2 |= $composer2.changed(border2) ? 1048576 : 524288;
        } else {
            border2 = border;
        }
        int i8 = i & 128;
        if (i8 != 0) {
            $dirty2 |= 12582912;
        } else if (($changed & 12582912) == 0) {
            $dirty2 |= $composer2.changed(contentPadding) ? 8388608 : 4194304;
        }
        int i9 = i & 256;
        if (i9 != 0) {
            $dirty2 |= 100663296;
        } else if (($changed & 100663296) == 0) {
            $dirty2 |= $composer2.changed(interactionSource) ? AccessibilityEventCompat.TYPE_VIEW_TARGETED_BY_SCROLL : 33554432;
        }
        if ((i & 512) != 0) {
            $dirty2 |= 805306368;
        } else if (($changed & 805306368) == 0) {
            $dirty2 |= $composer2.changedInstance(function3) ? 536870912 : 268435456;
        }
        if (($dirty2 & 306783379) == 306783378 && $composer2.getSkipping()) {
            $composer2.skipToGroupEnd();
            modifier4 = modifier;
            shape3 = shape;
            contentPadding3 = contentPadding;
            interactionSource3 = interactionSource;
            colors3 = colors2;
            elevation3 = elevation2;
            border4 = border2;
            enabled3 = enabled;
        } else {
            $composer2.startDefaults();
            if (($changed & 1) == 0 || $composer2.getDefaultsInvalid()) {
                Modifier.Companion modifier5 = i4 != 0 ? Modifier.INSTANCE : modifier;
                enabled2 = i5 != 0 ? true : enabled;
                if ((i & 8) != 0) {
                    shape2 = ButtonDefaults.INSTANCE.getTextShape($composer2, 6);
                    $dirty2 &= -7169;
                } else {
                    shape2 = shape;
                }
                if ((i & 16) != 0) {
                    modifier2 = modifier5;
                    $dirty2 &= -57345;
                    colors2 = ButtonDefaults.INSTANCE.textButtonColors($composer2, 6);
                } else {
                    modifier2 = modifier5;
                }
                if (i6 != 0) {
                    elevation2 = null;
                }
                if (i7 != 0) {
                    border2 = null;
                }
                PaddingValues contentPadding4 = i8 != 0 ? ButtonDefaults.INSTANCE.getTextButtonContentPadding() : contentPadding;
                if (i9 != 0) {
                    $composer2.startReplaceableGroup(593745314);
                    ComposerKt.sourceInformation($composer2, "CC(remember):Button.kt#9igjgp");
                    Object it$iv = $composer2.rememberedValue();
                    PaddingValues contentPadding5 = contentPadding4;
                    if (it$iv == Composer.INSTANCE.getEmpty()) {
                        value$iv = InteractionSourceKt.MutableInteractionSource();
                        $composer2.updateRememberedValue(value$iv);
                    } else {
                        value$iv = it$iv;
                    }
                    $composer2.endReplaceableGroup();
                    contentPadding2 = contentPadding5;
                    interactionSource2 = (MutableInteractionSource) value$iv;
                    $dirty = $dirty2;
                    border3 = border2;
                    modifier3 = modifier2;
                } else {
                    PaddingValues contentPadding6 = contentPadding4;
                    modifier3 = modifier2;
                    contentPadding2 = contentPadding6;
                    interactionSource2 = interactionSource;
                    $dirty = $dirty2;
                    border3 = border2;
                }
            } else {
                $composer2.skipToGroupEnd();
                if ((i & 8) != 0) {
                    $dirty2 &= -7169;
                }
                if ((i & 16) != 0) {
                    enabled2 = enabled;
                    shape2 = shape;
                    contentPadding2 = contentPadding;
                    interactionSource2 = interactionSource;
                    $dirty = $dirty2 & (-57345);
                    border3 = border2;
                    modifier3 = modifier;
                } else {
                    modifier3 = modifier;
                    enabled2 = enabled;
                    shape2 = shape;
                    contentPadding2 = contentPadding;
                    interactionSource2 = interactionSource;
                    $dirty = $dirty2;
                    border3 = border2;
                }
            }
            $composer2.endDefaults();
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventStart(-2106428362, $dirty, -1, "androidx.compose.material3.TextButton (Button.kt:416)");
            }
            Button(function0, modifier3, enabled2, shape2, colors2, elevation2, border3, contentPadding2, interactionSource2, function3, $composer2, ($dirty & 14) | ($dirty & 112) | ($dirty & 896) | ($dirty & 7168) | (57344 & $dirty) | (458752 & $dirty) | (3670016 & $dirty) | (29360128 & $dirty) | (234881024 & $dirty) | (1879048192 & $dirty), 0);
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventEnd();
            }
            modifier4 = modifier3;
            border4 = border3;
            contentPadding3 = contentPadding2;
            interactionSource3 = interactionSource2;
            enabled3 = enabled2;
            shape3 = shape2;
            colors3 = colors2;
            elevation3 = elevation2;
        }
        ScopeUpdateScope endRestartGroup = $composer2.endRestartGroup();
        if (endRestartGroup != null) {
            final Modifier modifier6 = modifier4;
            final boolean z = enabled3;
            final Shape shape4 = shape3;
            final ButtonColors buttonColors = colors3;
            final ButtonElevation buttonElevation = elevation3;
            final BorderStroke borderStroke = border4;
            final PaddingValues paddingValues = contentPadding3;
            final MutableInteractionSource mutableInteractionSource = interactionSource3;
            endRestartGroup.updateScope(new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.ButtonKt$TextButton$2
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
                    ButtonKt.TextButton(function0, modifier6, z, shape4, buttonColors, buttonElevation, borderStroke, paddingValues, mutableInteractionSource, function3, composer, RecomposeScopeImplKt.updateChangedFlags($changed | 1), i);
                }
            });
        }
    }
}
