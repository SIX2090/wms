package androidx.compose.material3;

import androidx.compose.animation.core.AnimateAsStateKt;
import androidx.compose.animation.core.AnimationSpecKt;
import androidx.compose.foundation.CanvasKt;
import androidx.compose.foundation.interaction.InteractionSourceKt;
import androidx.compose.foundation.interaction.MutableInteractionSource;
import androidx.compose.foundation.layout.PaddingKt;
import androidx.compose.foundation.layout.SizeKt;
import androidx.compose.foundation.selection.SelectableKt;
import androidx.compose.material.ripple.RippleKt;
import androidx.compose.material3.tokens.RadioButtonTokens;
import androidx.compose.runtime.Composer;
import androidx.compose.runtime.ComposerKt;
import androidx.compose.runtime.RecomposeScopeImplKt;
import androidx.compose.runtime.ScopeUpdateScope;
import androidx.compose.runtime.State;
import androidx.compose.ui.Alignment;
import androidx.compose.ui.Modifier;
import androidx.compose.ui.graphics.drawscope.DrawScope;
import androidx.compose.ui.graphics.drawscope.Fill;
import androidx.compose.ui.graphics.drawscope.Stroke;
import androidx.compose.ui.semantics.Role;
import androidx.compose.ui.unit.Dp;
import androidx.profileinstaller.ProfileVerifier;
import kotlin.Metadata;
import kotlin.Unit;
import kotlin.jvm.functions.Function0;
import kotlin.jvm.functions.Function1;
import kotlin.jvm.functions.Function2;

/* compiled from: RadioButton.kt */
@Metadata(d1 = {"\u00008\n\u0000\n\u0002\u0010\b\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0004\n\u0002\u0010\u0002\n\u0000\n\u0002\u0010\u000b\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0002\u001aM\u0010\u0007\u001a\u00020\b2\u0006\u0010\t\u001a\u00020\n2\u000e\u0010\u000b\u001a\n\u0012\u0004\u0012\u00020\b\u0018\u00010\f2\b\b\u0002\u0010\r\u001a\u00020\u000e2\b\b\u0002\u0010\u000f\u001a\u00020\n2\b\b\u0002\u0010\u0010\u001a\u00020\u00112\b\b\u0002\u0010\u0012\u001a\u00020\u0013H\u0007¢\u0006\u0002\u0010\u0014\"\u000e\u0010\u0000\u001a\u00020\u0001X\u0082T¢\u0006\u0002\n\u0000\"\u0010\u0010\u0002\u001a\u00020\u0003X\u0082\u0004¢\u0006\u0004\n\u0002\u0010\u0004\"\u0010\u0010\u0005\u001a\u00020\u0003X\u0082\u0004¢\u0006\u0004\n\u0002\u0010\u0004\"\u0010\u0010\u0006\u001a\u00020\u0003X\u0082\u0004¢\u0006\u0004\n\u0002\u0010\u0004¨\u0006\u0015"}, d2 = {"RadioAnimationDuration", "", "RadioButtonDotSize", "Landroidx/compose/ui/unit/Dp;", "F", "RadioButtonPadding", "RadioStrokeWidth", "RadioButton", "", "selected", "", "onClick", "Lkotlin/Function0;", "modifier", "Landroidx/compose/ui/Modifier;", "enabled", "colors", "Landroidx/compose/material3/RadioButtonColors;", "interactionSource", "Landroidx/compose/foundation/interaction/MutableInteractionSource;", "(ZLkotlin/jvm/functions/Function0;Landroidx/compose/ui/Modifier;ZLandroidx/compose/material3/RadioButtonColors;Landroidx/compose/foundation/interaction/MutableInteractionSource;Landroidx/compose/runtime/Composer;II)V", "material3_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class RadioButtonKt {
    private static final int RadioAnimationDuration = 100;
    private static final float RadioButtonPadding = Dp.m6094constructorimpl(2);
    private static final float RadioButtonDotSize = Dp.m6094constructorimpl(12);
    private static final float RadioStrokeWidth = Dp.m6094constructorimpl(2);

    public static final void RadioButton(final boolean selected, final Function0<Unit> function0, Modifier modifier, boolean enabled, RadioButtonColors colors, MutableInteractionSource interactionSource, Composer $composer, final int $changed, final int i) {
        Modifier modifier2;
        boolean z;
        RadioButtonColors radioButtonColors;
        MutableInteractionSource mutableInteractionSource;
        RadioButtonColors colors2;
        int $dirty;
        Modifier modifier3;
        RadioButtonColors colors3;
        MutableInteractionSource interactionSource2;
        boolean enabled2;
        Object value$iv;
        float m6094constructorimpl;
        final State radioColor;
        final State dotRadius;
        Modifier.Companion selectableModifier;
        Object value$iv2;
        Modifier modifier4;
        int i2;
        Composer $composer2 = $composer.startRestartGroup(408580840);
        ComposerKt.sourceInformation($composer2, "C(RadioButton)P(5,4,3,1)77@3753L8,78@3813L39,80@3877L164,84@4070L29,115@5122L415,102@4704L833:RadioButton.kt#uh7d8r");
        int $dirty2 = $changed;
        if ((i & 1) != 0) {
            $dirty2 |= 6;
        } else if (($changed & 6) == 0) {
            $dirty2 |= $composer2.changed(selected) ? 4 : 2;
        }
        if ((i & 2) != 0) {
            $dirty2 |= 48;
        } else if (($changed & 48) == 0) {
            $dirty2 |= $composer2.changedInstance(function0) ? 32 : 16;
        }
        int i3 = i & 4;
        if (i3 != 0) {
            $dirty2 |= 384;
            modifier2 = modifier;
        } else if (($changed & 384) == 0) {
            modifier2 = modifier;
            $dirty2 |= $composer2.changed(modifier2) ? 256 : 128;
        } else {
            modifier2 = modifier;
        }
        int i4 = i & 8;
        if (i4 != 0) {
            $dirty2 |= 3072;
            z = enabled;
        } else if (($changed & 3072) == 0) {
            z = enabled;
            $dirty2 |= $composer2.changed(z) ? 2048 : 1024;
        } else {
            z = enabled;
        }
        if (($changed & 24576) == 0) {
            if ((i & 16) == 0) {
                radioButtonColors = colors;
                if ($composer2.changed(radioButtonColors)) {
                    i2 = 16384;
                    $dirty2 |= i2;
                }
            } else {
                radioButtonColors = colors;
            }
            i2 = 8192;
            $dirty2 |= i2;
        } else {
            radioButtonColors = colors;
        }
        int i5 = i & 32;
        if (i5 != 0) {
            $dirty2 |= ProfileVerifier.CompilationStatus.RESULT_CODE_ERROR_CANT_WRITE_PROFILE_VERIFICATION_RESULT_CACHE_FILE;
            mutableInteractionSource = interactionSource;
        } else if ((196608 & $changed) == 0) {
            mutableInteractionSource = interactionSource;
            $dirty2 |= $composer2.changed(mutableInteractionSource) ? 131072 : 65536;
        } else {
            mutableInteractionSource = interactionSource;
        }
        if ((74899 & $dirty2) == 74898 && $composer2.getSkipping()) {
            $composer2.skipToGroupEnd();
            modifier4 = modifier2;
            colors3 = radioButtonColors;
            interactionSource2 = mutableInteractionSource;
            enabled2 = z;
        } else {
            $composer2.startDefaults();
            if (($changed & 1) == 0 || $composer2.getDefaultsInvalid()) {
                Modifier.Companion modifier5 = i3 != 0 ? Modifier.INSTANCE : modifier2;
                boolean enabled3 = i4 != 0 ? true : z;
                if ((i & 16) != 0) {
                    colors2 = RadioButtonDefaults.INSTANCE.colors($composer2, 6);
                    $dirty2 &= -57345;
                } else {
                    colors2 = radioButtonColors;
                }
                if (i5 != 0) {
                    $composer2.startReplaceableGroup(735546075);
                    ComposerKt.sourceInformation($composer2, "CC(remember):RadioButton.kt#9igjgp");
                    Object it$iv = $composer2.rememberedValue();
                    if (it$iv == Composer.INSTANCE.getEmpty()) {
                        value$iv = InteractionSourceKt.MutableInteractionSource();
                        $composer2.updateRememberedValue(value$iv);
                    } else {
                        value$iv = it$iv;
                    }
                    MutableInteractionSource interactionSource3 = (MutableInteractionSource) value$iv;
                    $composer2.endReplaceableGroup();
                    $dirty = $dirty2;
                    modifier3 = modifier5;
                    enabled2 = enabled3;
                    colors3 = colors2;
                    interactionSource2 = interactionSource3;
                } else {
                    $dirty = $dirty2;
                    modifier3 = modifier5;
                    colors3 = colors2;
                    interactionSource2 = mutableInteractionSource;
                    enabled2 = enabled3;
                }
            } else {
                $composer2.skipToGroupEnd();
                if ((i & 16) != 0) {
                    $dirty2 &= -57345;
                }
                $dirty = $dirty2;
                modifier3 = modifier2;
                colors3 = radioButtonColors;
                interactionSource2 = mutableInteractionSource;
                enabled2 = z;
            }
            $composer2.endDefaults();
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventStart(408580840, $dirty, -1, "androidx.compose.material3.RadioButton (RadioButton.kt:79)");
            }
            if (selected) {
                float arg0$iv = RadioButtonDotSize;
                m6094constructorimpl = Dp.m6094constructorimpl(arg0$iv / 2);
            } else {
                m6094constructorimpl = Dp.m6094constructorimpl(0);
            }
            int $dirty3 = $dirty;
            State dotRadius2 = AnimateAsStateKt.m116animateDpAsStateAjpBEmI(m6094constructorimpl, AnimationSpecKt.tween$default(100, 0, null, 6, null), null, null, $composer2, 48, 12);
            State radioColor2 = colors3.radioColor$material3_release(enabled2, selected, $composer2, (($dirty3 >> 9) & 14) | (($dirty3 << 3) & 112) | (($dirty3 >> 6) & 896));
            $composer2.startReplaceableGroup(735546399);
            ComposerKt.sourceInformation($composer2, "94@4501L136");
            if (function0 != null) {
                Modifier.Companion companion = Modifier.INSTANCE;
                int m5403getRadioButtono7Vup1c = Role.INSTANCE.m5403getRadioButtono7Vup1c();
                float arg0$iv2 = RadioButtonTokens.INSTANCE.m3108getStateLayerSizeD9Ej5fM();
                radioColor = radioColor2;
                dotRadius = dotRadius2;
                selectableModifier = SelectableKt.m803selectableO2vRcR0(companion, selected, interactionSource2, RippleKt.m1553rememberRipple9IZ8Weo(false, Dp.m6094constructorimpl(arg0$iv2 / 2), 0L, $composer2, 54, 4), enabled2, Role.m5392boximpl(m5403getRadioButtono7Vup1c), function0);
            } else {
                radioColor = radioColor2;
                dotRadius = dotRadius2;
                selectableModifier = Modifier.INSTANCE;
            }
            $composer2.endReplaceableGroup();
            Modifier m603requiredSize3ABfNKs = SizeKt.m603requiredSize3ABfNKs(PaddingKt.m562padding3ABfNKs(SizeKt.wrapContentSize$default(modifier3.then(function0 != null ? InteractiveComponentSizeKt.minimumInteractiveComponentSize(Modifier.INSTANCE) : Modifier.INSTANCE).then(selectableModifier), Alignment.INSTANCE.getCenter(), false, 2, null), RadioButtonPadding), RadioButtonTokens.INSTANCE.m3107getIconSizeD9Ej5fM());
            $composer2.startReplaceableGroup(735547384);
            ComposerKt.sourceInformation($composer2, "CC(remember):RadioButton.kt#9igjgp");
            boolean invalid$iv = $composer2.changed(radioColor) | $composer2.changed(dotRadius);
            Object it$iv2 = $composer2.rememberedValue();
            if (invalid$iv || it$iv2 == Composer.INSTANCE.getEmpty()) {
                value$iv2 = (Function1) new Function1<DrawScope, Unit>() { // from class: androidx.compose.material3.RadioButtonKt$RadioButton$2$1
                    /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
                    {
                        super(1);
                    }

                    @Override // kotlin.jvm.functions.Function1
                    public /* bridge */ /* synthetic */ Unit invoke(DrawScope drawScope) {
                        invoke2(drawScope);
                        return Unit.INSTANCE;
                    }

                    /* renamed from: invoke, reason: avoid collision after fix types in other method */
                    public final void invoke2(DrawScope $this$Canvas) {
                        float f;
                        f = RadioButtonKt.RadioStrokeWidth;
                        float strokeWidth = $this$Canvas.mo313toPx0680j_4(f);
                        long m3756unboximpl = radioColor.getValue().m3756unboximpl();
                        float arg0$iv3 = RadioButtonTokens.INSTANCE.m3107getIconSizeD9Ej5fM();
                        float f2 = 2;
                        DrawScope.m4277drawCircleVaOC9Bg$default($this$Canvas, m3756unboximpl, $this$Canvas.mo313toPx0680j_4(Dp.m6094constructorimpl(arg0$iv3 / 2)) - (strokeWidth / f2), 0L, 0.0f, new Stroke(strokeWidth, 0.0f, 0, 0, null, 30, null), null, 0, 108, null);
                        if (Dp.m6093compareTo0680j_4(dotRadius.getValue().m6108unboximpl(), Dp.m6094constructorimpl(0)) > 0) {
                            DrawScope.m4277drawCircleVaOC9Bg$default($this$Canvas, radioColor.getValue().m3756unboximpl(), $this$Canvas.mo313toPx0680j_4(dotRadius.getValue().m6108unboximpl()) - (strokeWidth / f2), 0L, 0.0f, Fill.INSTANCE, null, 0, 108, null);
                        }
                    }
                };
                $composer2.updateRememberedValue(value$iv2);
            } else {
                value$iv2 = it$iv2;
            }
            $composer2.endReplaceableGroup();
            CanvasKt.Canvas(m603requiredSize3ABfNKs, (Function1) value$iv2, $composer2, 0);
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventEnd();
            }
            modifier4 = modifier3;
        }
        ScopeUpdateScope endRestartGroup = $composer2.endRestartGroup();
        if (endRestartGroup != null) {
            final Modifier modifier6 = modifier4;
            final boolean z2 = enabled2;
            final RadioButtonColors radioButtonColors2 = colors3;
            final MutableInteractionSource mutableInteractionSource2 = interactionSource2;
            endRestartGroup.updateScope(new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.RadioButtonKt$RadioButton$3
                /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
                {
                    super(2);
                }

                @Override // kotlin.jvm.functions.Function2
                public /* bridge */ /* synthetic */ Unit invoke(Composer composer, Integer num) {
                    invoke(composer, num.intValue());
                    return Unit.INSTANCE;
                }

                public final void invoke(Composer composer, int i6) {
                    RadioButtonKt.RadioButton(selected, function0, modifier6, z2, radioButtonColors2, mutableInteractionSource2, composer, RecomposeScopeImplKt.updateChangedFlags($changed | 1), i);
                }
            });
        }
    }
}
