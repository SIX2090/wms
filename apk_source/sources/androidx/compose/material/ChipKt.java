package androidx.compose.material;

import androidx.compose.foundation.BorderStroke;
import androidx.compose.foundation.interaction.InteractionSourceKt;
import androidx.compose.foundation.interaction.MutableInteractionSource;
import androidx.compose.foundation.layout.RowScope;
import androidx.compose.foundation.shape.CornerBasedShape;
import androidx.compose.foundation.shape.CornerSizeKt;
import androidx.compose.runtime.Composer;
import androidx.compose.runtime.ComposerKt;
import androidx.compose.runtime.CompositionLocalKt;
import androidx.compose.runtime.ProvidableCompositionLocal;
import androidx.compose.runtime.ProvidedValue;
import androidx.compose.runtime.RecomposeScopeImplKt;
import androidx.compose.runtime.ScopeUpdateScope;
import androidx.compose.runtime.State;
import androidx.compose.runtime.internal.ComposableLambdaKt;
import androidx.compose.ui.Modifier;
import androidx.compose.ui.graphics.Color;
import androidx.compose.ui.graphics.Shape;
import androidx.compose.ui.semantics.Role;
import androidx.compose.ui.semantics.SemanticsModifierKt;
import androidx.compose.ui.semantics.SemanticsPropertiesKt;
import androidx.compose.ui.semantics.SemanticsPropertyReceiver;
import androidx.compose.ui.text.TextStyle;
import androidx.compose.ui.unit.Dp;
import androidx.core.app.FrameMetricsAggregator;
import androidx.core.view.accessibility.AccessibilityEventCompat;
import androidx.profileinstaller.ProfileVerifier;
import kotlin.Metadata;
import kotlin.Unit;
import kotlin.jvm.functions.Function0;
import kotlin.jvm.functions.Function1;
import kotlin.jvm.functions.Function2;
import kotlin.jvm.functions.Function3;

/* compiled from: Chip.kt */
@Metadata(d1 = {"\u0000f\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0005\n\u0002\u0010\u0007\n\u0002\b\u0003\n\u0002\u0010\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010\u000b\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0018\u0002\n\u0002\b\u0005\n\u0002\u0018\u0002\n\u0000\u001a\u008e\u0001\u0010\n\u001a\u00020\u000b2\f\u0010\f\u001a\b\u0012\u0004\u0012\u00020\u000b0\r2\b\b\u0002\u0010\u000e\u001a\u00020\u000f2\b\b\u0002\u0010\u0010\u001a\u00020\u00112\b\b\u0002\u0010\u0012\u001a\u00020\u00132\b\b\u0002\u0010\u0014\u001a\u00020\u00152\n\b\u0002\u0010\u0016\u001a\u0004\u0018\u00010\u00172\b\b\u0002\u0010\u0018\u001a\u00020\u00192\u0015\b\u0002\u0010\u001a\u001a\u000f\u0012\u0004\u0012\u00020\u000b\u0018\u00010\r¢\u0006\u0002\b\u001b2\u001c\u0010\u001c\u001a\u0018\u0012\u0004\u0012\u00020\u001e\u0012\u0004\u0012\u00020\u000b0\u001d¢\u0006\u0002\b\u001b¢\u0006\u0002\b\u001fH\u0007¢\u0006\u0002\u0010 \u001aÄ\u0001\u0010!\u001a\u00020\u000b2\u0006\u0010\"\u001a\u00020\u00112\f\u0010\f\u001a\b\u0012\u0004\u0012\u00020\u000b0\r2\b\b\u0002\u0010\u000e\u001a\u00020\u000f2\b\b\u0002\u0010\u0010\u001a\u00020\u00112\b\b\u0002\u0010\u0012\u001a\u00020\u00132\b\b\u0002\u0010\u0014\u001a\u00020\u00152\n\b\u0002\u0010\u0016\u001a\u0004\u0018\u00010\u00172\b\b\u0002\u0010\u0018\u001a\u00020#2\u0015\b\u0002\u0010\u001a\u001a\u000f\u0012\u0004\u0012\u00020\u000b\u0018\u00010\r¢\u0006\u0002\b\u001b2\u0015\b\u0002\u0010$\u001a\u000f\u0012\u0004\u0012\u00020\u000b\u0018\u00010\r¢\u0006\u0002\b\u001b2\u0015\b\u0002\u0010%\u001a\u000f\u0012\u0004\u0012\u00020\u000b\u0018\u00010\r¢\u0006\u0002\b\u001b2\u001c\u0010\u001c\u001a\u0018\u0012\u0004\u0012\u00020\u001e\u0012\u0004\u0012\u00020\u000b0\u001d¢\u0006\u0002\b\u001b¢\u0006\u0002\b\u001fH\u0007¢\u0006\u0002\u0010&\"\u0010\u0010\u0000\u001a\u00020\u0001X\u0082\u0004¢\u0006\u0004\n\u0002\u0010\u0002\"\u0010\u0010\u0003\u001a\u00020\u0001X\u0082\u0004¢\u0006\u0004\n\u0002\u0010\u0002\"\u0010\u0010\u0004\u001a\u00020\u0001X\u0082\u0004¢\u0006\u0004\n\u0002\u0010\u0002\"\u0010\u0010\u0005\u001a\u00020\u0001X\u0082\u0004¢\u0006\u0004\n\u0002\u0010\u0002\"\u000e\u0010\u0006\u001a\u00020\u0007X\u0082T¢\u0006\u0002\n\u0000\"\u000e\u0010\b\u001a\u00020\u0007X\u0082T¢\u0006\u0002\n\u0000\"\u0010\u0010\t\u001a\u00020\u0001X\u0082\u0004¢\u0006\u0004\n\u0002\u0010\u0002¨\u0006'²\u0006\n\u0010(\u001a\u00020)X\u008a\u0084\u0002²\u0006\n\u0010*\u001a\u00020)X\u008a\u0084\u0002"}, d2 = {"HorizontalPadding", "Landroidx/compose/ui/unit/Dp;", "F", "LeadingIconEndSpacing", "LeadingIconStartSpacing", "SelectedIconContainerSize", "SelectedOverlayOpacity", "", "SurfaceOverlayOpacity", "TrailingIconSpacing", "Chip", "", "onClick", "Lkotlin/Function0;", "modifier", "Landroidx/compose/ui/Modifier;", "enabled", "", "interactionSource", "Landroidx/compose/foundation/interaction/MutableInteractionSource;", "shape", "Landroidx/compose/ui/graphics/Shape;", OutlinedTextFieldKt.BorderId, "Landroidx/compose/foundation/BorderStroke;", "colors", "Landroidx/compose/material/ChipColors;", "leadingIcon", "Landroidx/compose/runtime/Composable;", "content", "Lkotlin/Function1;", "Landroidx/compose/foundation/layout/RowScope;", "Lkotlin/ExtensionFunctionType;", "(Lkotlin/jvm/functions/Function0;Landroidx/compose/ui/Modifier;ZLandroidx/compose/foundation/interaction/MutableInteractionSource;Landroidx/compose/ui/graphics/Shape;Landroidx/compose/foundation/BorderStroke;Landroidx/compose/material/ChipColors;Lkotlin/jvm/functions/Function2;Lkotlin/jvm/functions/Function3;Landroidx/compose/runtime/Composer;II)V", "FilterChip", "selected", "Landroidx/compose/material/SelectableChipColors;", "selectedIcon", "trailingIcon", "(ZLkotlin/jvm/functions/Function0;Landroidx/compose/ui/Modifier;ZLandroidx/compose/foundation/interaction/MutableInteractionSource;Landroidx/compose/ui/graphics/Shape;Landroidx/compose/foundation/BorderStroke;Landroidx/compose/material/SelectableChipColors;Lkotlin/jvm/functions/Function2;Lkotlin/jvm/functions/Function2;Lkotlin/jvm/functions/Function2;Lkotlin/jvm/functions/Function3;Landroidx/compose/runtime/Composer;III)V", "material_release", "contentColor", "Landroidx/compose/ui/graphics/Color;", "leadingIconContentColor"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class ChipKt {
    private static final float SelectedOverlayOpacity = 0.16f;
    private static final float SurfaceOverlayOpacity = 0.12f;
    private static final float HorizontalPadding = Dp.m6094constructorimpl(12);
    private static final float LeadingIconStartSpacing = Dp.m6094constructorimpl(4);
    private static final float LeadingIconEndSpacing = Dp.m6094constructorimpl(8);
    private static final float TrailingIconSpacing = Dp.m6094constructorimpl(8);
    private static final float SelectedIconContainerSize = Dp.m6094constructorimpl(24);

    public static final void Chip(final Function0<Unit> function0, Modifier modifier, boolean enabled, MutableInteractionSource interactionSource, Shape shape, BorderStroke border, ChipColors colors, Function2<? super Composer, ? super Integer, Unit> function2, final Function3<? super RowScope, ? super Composer, ? super Integer, Unit> function3, Composer $composer, final int $changed, final int i) {
        MutableInteractionSource interactionSource2;
        Shape shape2;
        ChipColors chipColors;
        Function2 function22;
        Modifier modifier2;
        boolean enabled2;
        BorderStroke border2;
        ChipColors colors2;
        Function2 leadingIcon;
        int $dirty;
        Modifier modifier3;
        boolean enabled3;
        Object value$iv$iv;
        long m3744copywmQWz5c;
        Modifier modifier4;
        boolean enabled4;
        BorderStroke border3;
        ChipColors colors3;
        Function2 leadingIcon2;
        MutableInteractionSource interactionSource3;
        Shape shape3;
        int i2;
        int i3;
        Composer $composer2 = $composer.startRestartGroup(-368396408);
        ComposerKt.sourceInformation($composer2, "C(Chip)P(7,6,3,4,8!2,5)92@4249L39,93@4323L6,95@4440L12,99@4585L21,105@4782L24,100@4611L1787:Chip.kt#jmzs0o");
        int $dirty2 = $changed;
        if ((i & 1) != 0) {
            $dirty2 |= 6;
        } else if (($changed & 14) == 0) {
            $dirty2 |= $composer2.changedInstance(function0) ? 4 : 2;
        }
        int i4 = i & 2;
        if (i4 != 0) {
            $dirty2 |= 48;
        } else if (($changed & 112) == 0) {
            $dirty2 |= $composer2.changed(modifier) ? 32 : 16;
        }
        int i5 = i & 4;
        if (i5 != 0) {
            $dirty2 |= 384;
        } else if (($changed & 896) == 0) {
            $dirty2 |= $composer2.changed(enabled) ? 256 : 128;
        }
        int i6 = i & 8;
        if (i6 != 0) {
            $dirty2 |= 3072;
            interactionSource2 = interactionSource;
        } else if (($changed & 7168) == 0) {
            interactionSource2 = interactionSource;
            $dirty2 |= $composer2.changed(interactionSource2) ? 2048 : 1024;
        } else {
            interactionSource2 = interactionSource;
        }
        if ((57344 & $changed) == 0) {
            if ((i & 16) == 0) {
                shape2 = shape;
                if ($composer2.changed(shape2)) {
                    i3 = 16384;
                    $dirty2 |= i3;
                }
            } else {
                shape2 = shape;
            }
            i3 = 8192;
            $dirty2 |= i3;
        } else {
            shape2 = shape;
        }
        int i7 = i & 32;
        if (i7 != 0) {
            $dirty2 |= ProfileVerifier.CompilationStatus.RESULT_CODE_ERROR_CANT_WRITE_PROFILE_VERIFICATION_RESULT_CACHE_FILE;
        } else if ((458752 & $changed) == 0) {
            $dirty2 |= $composer2.changed(border) ? 131072 : 65536;
        }
        if (($changed & 3670016) == 0) {
            if ((i & 64) == 0) {
                chipColors = colors;
                if ($composer2.changed(chipColors)) {
                    i2 = 1048576;
                    $dirty2 |= i2;
                }
            } else {
                chipColors = colors;
            }
            i2 = 524288;
            $dirty2 |= i2;
        } else {
            chipColors = colors;
        }
        int i8 = i & 128;
        if (i8 != 0) {
            $dirty2 |= 12582912;
            function22 = function2;
        } else if (($changed & 29360128) == 0) {
            function22 = function2;
            $dirty2 |= $composer2.changedInstance(function22) ? 8388608 : 4194304;
        } else {
            function22 = function2;
        }
        if ((i & 256) != 0) {
            $dirty2 |= 100663296;
        } else if (($changed & 234881024) == 0) {
            $dirty2 |= $composer2.changedInstance(function3) ? AccessibilityEventCompat.TYPE_VIEW_TARGETED_BY_SCROLL : 33554432;
        }
        if (($dirty2 & 191739611) == 38347922 && $composer2.getSkipping()) {
            $composer2.skipToGroupEnd();
            modifier4 = modifier;
            border3 = border;
            shape3 = shape2;
            leadingIcon2 = function22;
            colors3 = chipColors;
            enabled4 = enabled;
            interactionSource3 = interactionSource2;
        } else {
            $composer2.startDefaults();
            if (($changed & 1) == 0 || $composer2.getDefaultsInvalid()) {
                Modifier.Companion modifier5 = i4 != 0 ? Modifier.INSTANCE : modifier;
                boolean enabled5 = i5 != 0 ? true : enabled;
                if (i6 != 0) {
                    $composer2.startReplaceableGroup(-492369756);
                    ComposerKt.sourceInformation($composer2, "CC(remember):Composables.kt#9igjgp");
                    modifier2 = modifier5;
                    Object it$iv$iv = $composer2.rememberedValue();
                    enabled2 = enabled5;
                    if (it$iv$iv == Composer.INSTANCE.getEmpty()) {
                        value$iv$iv = InteractionSourceKt.MutableInteractionSource();
                        $composer2.updateRememberedValue(value$iv$iv);
                    } else {
                        value$iv$iv = it$iv$iv;
                    }
                    $composer2.endReplaceableGroup();
                    interactionSource2 = (MutableInteractionSource) value$iv$iv;
                } else {
                    modifier2 = modifier5;
                    enabled2 = enabled5;
                }
                if ((i & 16) != 0) {
                    $dirty2 &= -57345;
                    shape2 = MaterialTheme.INSTANCE.getShapes($composer2, 6).getSmall().copy(CornerSizeKt.CornerSize(50));
                }
                border2 = i7 != 0 ? null : border;
                if ((i & 64) != 0) {
                    colors2 = ChipDefaults.INSTANCE.m1269chipColors5tl4gsc(0L, 0L, 0L, 0L, 0L, 0L, $composer2, 1572864, 63);
                    $dirty2 &= -3670017;
                } else {
                    colors2 = colors;
                }
                if (i8 != 0) {
                    leadingIcon = null;
                    $dirty = $dirty2;
                    modifier3 = modifier2;
                    enabled3 = enabled2;
                } else {
                    leadingIcon = function2;
                    $dirty = $dirty2;
                    modifier3 = modifier2;
                    enabled3 = enabled2;
                }
            } else {
                $composer2.skipToGroupEnd();
                if ((i & 16) != 0) {
                    $dirty2 &= -57345;
                }
                if ((i & 64) != 0) {
                    int i9 = $dirty2 & (-3670017);
                    enabled3 = enabled;
                    border2 = border;
                    $dirty = i9;
                    leadingIcon = function22;
                    colors2 = chipColors;
                    modifier3 = modifier;
                } else {
                    modifier3 = modifier;
                    border2 = border;
                    $dirty = $dirty2;
                    leadingIcon = function22;
                    colors2 = chipColors;
                    enabled3 = enabled;
                }
            }
            $composer2.endDefaults();
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventStart(-368396408, $dirty, -1, "androidx.compose.material.Chip (Chip.kt:98)");
            }
            final State contentColor$delegate = colors2.contentColor(enabled3, $composer2, (($dirty >> 6) & 14) | (($dirty >> 15) & 112));
            Modifier semantics$default = SemanticsModifierKt.semantics$default(modifier3, false, new Function1<SemanticsPropertyReceiver, Unit>() { // from class: androidx.compose.material.ChipKt$Chip$2
                @Override // kotlin.jvm.functions.Function1
                public /* bridge */ /* synthetic */ Unit invoke(SemanticsPropertyReceiver semanticsPropertyReceiver) {
                    invoke2(semanticsPropertyReceiver);
                    return Unit.INSTANCE;
                }

                /* renamed from: invoke, reason: avoid collision after fix types in other method */
                public final void invoke2(SemanticsPropertyReceiver $this$semantics) {
                    SemanticsPropertiesKt.m5415setRolekuIjeqM($this$semantics, Role.INSTANCE.m5399getButtono7Vup1c());
                }
            }, 1, null);
            long m3756unboximpl = colors2.backgroundColor(enabled3, $composer2, (($dirty >> 6) & 14) | (($dirty >> 15) & 112)).getValue().m3756unboximpl();
            m3744copywmQWz5c = Color.m3744copywmQWz5c(r19, (r12 & 1) != 0 ? Color.m3748getAlphaimpl(r19) : 1.0f, (r12 & 2) != 0 ? Color.m3752getRedimpl(r19) : 0.0f, (r12 & 4) != 0 ? Color.m3751getGreenimpl(r19) : 0.0f, (r12 & 8) != 0 ? Color.m3749getBlueimpl(Chip$lambda$1(contentColor$delegate)) : 0.0f);
            final Function2 function23 = leadingIcon;
            final ChipColors chipColors2 = colors2;
            final boolean z = enabled3;
            SurfaceKt.m1466SurfaceLPr_se0(function0, semantics$default, enabled3, shape2, m3756unboximpl, m3744copywmQWz5c, border2, 0.0f, interactionSource2, ComposableLambdaKt.composableLambda($composer2, 139076687, true, new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material.ChipKt$Chip$3
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
                    long Chip$lambda$1;
                    ComposerKt.sourceInformation($composer3, "C110@4950L1442:Chip.kt#jmzs0o");
                    if (($changed2 & 11) != 2 || !$composer3.getSkipping()) {
                        if (ComposerKt.isTraceInProgress()) {
                            ComposerKt.traceEventStart(139076687, $changed2, -1, "androidx.compose.material.Chip.<anonymous> (Chip.kt:110)");
                        }
                        ProvidableCompositionLocal<Float> localContentAlpha = ContentAlphaKt.getLocalContentAlpha();
                        Chip$lambda$1 = ChipKt.Chip$lambda$1(contentColor$delegate);
                        ProvidedValue<Float> provides = localContentAlpha.provides(Float.valueOf(Color.m3748getAlphaimpl(Chip$lambda$1)));
                        final Function2<Composer, Integer, Unit> function24 = function23;
                        final ChipColors chipColors3 = chipColors2;
                        final boolean z2 = z;
                        final Function3<RowScope, Composer, Integer, Unit> function32 = function3;
                        CompositionLocalKt.CompositionLocalProvider(provides, ComposableLambdaKt.composableLambda($composer3, 667535631, true, new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material.ChipKt$Chip$3.1
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
                                ComposerKt.sourceInformation($composer4, "C112@5092L10,111@5036L1346:Chip.kt#jmzs0o");
                                if (($changed3 & 11) != 2 || !$composer4.getSkipping()) {
                                    if (ComposerKt.isTraceInProgress()) {
                                        ComposerKt.traceEventStart(667535631, $changed3, -1, "androidx.compose.material.Chip.<anonymous>.<anonymous> (Chip.kt:111)");
                                    }
                                    TextStyle body2 = MaterialTheme.INSTANCE.getTypography($composer4, 6).getBody2();
                                    final Function2<Composer, Integer, Unit> function25 = function24;
                                    final ChipColors chipColors4 = chipColors3;
                                    final boolean z3 = z2;
                                    final Function3<RowScope, Composer, Integer, Unit> function33 = function32;
                                    TextKt.ProvideTextStyle(body2, ComposableLambdaKt.composableLambda($composer4, -1131213696, true, new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material.ChipKt.Chip.3.1.1
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

                                        /* JADX WARN: Removed duplicated region for block: B:27:0x018e  */
                                        /* JADX WARN: Removed duplicated region for block: B:30:0x0214  */
                                        /* JADX WARN: Removed duplicated region for block: B:32:? A[RETURN, SYNTHETIC] */
                                        /* JADX WARN: Removed duplicated region for block: B:33:0x01e9  */
                                        /*
                                            Code decompiled incorrectly, please refer to instructions dump.
                                            To view partially-correct add '--show-bad-code' argument
                                        */
                                        public final void invoke(androidx.compose.runtime.Composer r33, int r34) {
                                            /*
                                                Method dump skipped, instructions count: 536
                                                To view this dump add '--comments-level debug' option
                                            */
                                            throw new UnsupportedOperationException("Method not decompiled: androidx.compose.material.ChipKt$Chip$3.AnonymousClass1.C00381.invoke(androidx.compose.runtime.Composer, int):void");
                                        }

                                        private static final long invoke$lambda$1$lambda$0(State<Color> state) {
                                            Object thisObj$iv = state.getValue();
                                            return ((Color) thisObj$iv).m3756unboximpl();
                                        }
                                    }), $composer4, 48);
                                    if (ComposerKt.isTraceInProgress()) {
                                        ComposerKt.traceEventEnd();
                                        return;
                                    }
                                    return;
                                }
                                $composer4.skipToGroupEnd();
                            }
                        }), $composer3, ProvidedValue.$stable | 0 | 48);
                        if (ComposerKt.isTraceInProgress()) {
                            ComposerKt.traceEventEnd();
                            return;
                        }
                        return;
                    }
                    $composer3.skipToGroupEnd();
                }
            }), $composer2, ($dirty & 14) | 805306368 | ($dirty & 896) | (($dirty >> 3) & 7168) | (($dirty << 3) & 3670016) | (($dirty << 15) & 234881024), 128);
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventEnd();
            }
            modifier4 = modifier3;
            enabled4 = enabled3;
            border3 = border2;
            colors3 = colors2;
            leadingIcon2 = leadingIcon;
            interactionSource3 = interactionSource2;
            shape3 = shape2;
        }
        ScopeUpdateScope endRestartGroup = $composer2.endRestartGroup();
        if (endRestartGroup != null) {
            final Modifier modifier6 = modifier4;
            final boolean z2 = enabled4;
            final MutableInteractionSource mutableInteractionSource = interactionSource3;
            final Shape shape4 = shape3;
            final BorderStroke borderStroke = border3;
            final ChipColors chipColors3 = colors3;
            final Function2 function24 = leadingIcon2;
            endRestartGroup.updateScope(new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material.ChipKt$Chip$4
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
                    ChipKt.Chip(function0, modifier6, z2, mutableInteractionSource, shape4, borderStroke, chipColors3, function24, function3, composer, RecomposeScopeImplKt.updateChangedFlags($changed | 1), i);
                }
            });
        }
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final long Chip$lambda$1(State<Color> state) {
        Object thisObj$iv = state.getValue();
        return ((Color) thisObj$iv).m3756unboximpl();
    }

    public static final void FilterChip(final boolean selected, final Function0<Unit> function0, Modifier modifier, boolean enabled, MutableInteractionSource interactionSource, Shape shape, BorderStroke border, SelectableChipColors colors, Function2<? super Composer, ? super Integer, Unit> function2, Function2<? super Composer, ? super Integer, Unit> function22, Function2<? super Composer, ? super Integer, Unit> function23, final Function3<? super RowScope, ? super Composer, ? super Integer, Unit> function3, Composer $composer, final int $changed, final int $changed1, final int i) {
        Modifier modifier2;
        Shape shape2;
        BorderStroke borderStroke;
        SelectableChipColors colors2;
        int i2;
        int i3;
        Function2 function24;
        Modifier modifier3;
        MutableInteractionSource interactionSource2;
        CornerBasedShape shape3;
        int i4;
        int i5;
        Function2 trailingIcon;
        Function2 leadingIcon;
        int $dirty;
        MutableInteractionSource interactionSource3;
        Shape shape4;
        BorderStroke border2;
        Function2 selectedIcon;
        SelectableChipColors colors3;
        boolean enabled2;
        Modifier modifier4;
        Object value$iv$iv;
        long m3744copywmQWz5c;
        SelectableChipColors colors4;
        boolean enabled3;
        Modifier modifier5;
        Composer $composer2;
        int i6;
        int i7;
        Composer $composer3 = $composer.startRestartGroup(-1259208246);
        ComposerKt.sourceInformation($composer3, "C(FilterChip)P(8,7,6,3,4,10!2,5,9,11)189@8789L39,190@8863L6,192@8990L18,199@9321L31,206@9559L34,200@9357L4342:Chip.kt#jmzs0o");
        int $dirty2 = $changed;
        int $dirty1 = $changed1;
        if ((i & 1) != 0) {
            $dirty2 |= 6;
        } else if (($changed & 14) == 0) {
            $dirty2 |= $composer3.changed(selected) ? 4 : 2;
        }
        if ((i & 2) != 0) {
            $dirty2 |= 48;
        } else if (($changed & 112) == 0) {
            $dirty2 |= $composer3.changedInstance(function0) ? 32 : 16;
        }
        int i8 = i & 4;
        if (i8 != 0) {
            $dirty2 |= 384;
            modifier2 = modifier;
        } else if (($changed & 896) == 0) {
            modifier2 = modifier;
            $dirty2 |= $composer3.changed(modifier2) ? 256 : 128;
        } else {
            modifier2 = modifier;
        }
        int i9 = i & 8;
        if (i9 != 0) {
            $dirty2 |= 3072;
        } else if (($changed & 7168) == 0) {
            $dirty2 |= $composer3.changed(enabled) ? 2048 : 1024;
        }
        int i10 = i & 16;
        if (i10 != 0) {
            $dirty2 |= 24576;
        } else if (($changed & 57344) == 0) {
            $dirty2 |= $composer3.changed(interactionSource) ? 16384 : 8192;
        }
        if (($changed & 458752) == 0) {
            if ((i & 32) == 0) {
                shape2 = shape;
                if ($composer3.changed(shape2)) {
                    i7 = 131072;
                    $dirty2 |= i7;
                }
            } else {
                shape2 = shape;
            }
            i7 = 65536;
            $dirty2 |= i7;
        } else {
            shape2 = shape;
        }
        int i11 = i & 64;
        if (i11 != 0) {
            $dirty2 |= 1572864;
            borderStroke = border;
        } else if (($changed & 3670016) == 0) {
            borderStroke = border;
            $dirty2 |= $composer3.changed(borderStroke) ? 1048576 : 524288;
        } else {
            borderStroke = border;
        }
        if (($changed & 29360128) == 0) {
            if ((i & 128) == 0) {
                colors2 = colors;
                if ($composer3.changed(colors2)) {
                    i6 = 8388608;
                    $dirty2 |= i6;
                }
            } else {
                colors2 = colors;
            }
            i6 = 4194304;
            $dirty2 |= i6;
        } else {
            colors2 = colors;
        }
        int i12 = i & 256;
        if (i12 != 0) {
            $dirty2 |= 100663296;
        } else if (($changed & 234881024) == 0) {
            $dirty2 |= $composer3.changedInstance(function2) ? AccessibilityEventCompat.TYPE_VIEW_TARGETED_BY_SCROLL : 33554432;
        }
        int i13 = i & 512;
        if (i13 != 0) {
            $dirty2 |= 805306368;
            i2 = i13;
        } else if (($changed & 1879048192) == 0) {
            i2 = i13;
            $dirty2 |= $composer3.changedInstance(function22) ? 536870912 : 268435456;
        } else {
            i2 = i13;
        }
        int i14 = i & 1024;
        if (i14 != 0) {
            $dirty1 |= 6;
            i3 = i14;
            function24 = function23;
        } else if (($changed1 & 14) == 0) {
            i3 = i14;
            function24 = function23;
            $dirty1 |= $composer3.changedInstance(function24) ? 4 : 2;
        } else {
            i3 = i14;
            function24 = function23;
        }
        if ((i & 2048) != 0) {
            $dirty1 |= 48;
        } else if (($changed1 & 112) == 0) {
            $dirty1 |= $composer3.changedInstance(function3) ? 32 : 16;
        }
        if (($dirty2 & 1533916891) == 306783378 && ($dirty1 & 91) == 18 && $composer3.getSkipping()) {
            $composer3.skipToGroupEnd();
            enabled3 = enabled;
            interactionSource3 = interactionSource;
            leadingIcon = function2;
            selectedIcon = function22;
            $composer2 = $composer3;
            shape4 = shape2;
            border2 = borderStroke;
            colors4 = colors2;
            modifier5 = modifier2;
            trailingIcon = function24;
        } else {
            $composer3.startDefaults();
            if (($changed & 1) == 0 || $composer3.getDefaultsInvalid()) {
                Modifier.Companion modifier6 = i8 != 0 ? Modifier.INSTANCE : modifier2;
                boolean enabled4 = i9 != 0 ? true : enabled;
                if (i10 != 0) {
                    $composer3.startReplaceableGroup(-492369756);
                    ComposerKt.sourceInformation($composer3, "CC(remember):Composables.kt#9igjgp");
                    modifier3 = modifier6;
                    Object it$iv$iv = $composer3.rememberedValue();
                    if (it$iv$iv == Composer.INSTANCE.getEmpty()) {
                        value$iv$iv = InteractionSourceKt.MutableInteractionSource();
                        $composer3.updateRememberedValue(value$iv$iv);
                    } else {
                        value$iv$iv = it$iv$iv;
                    }
                    $composer3.endReplaceableGroup();
                    interactionSource2 = (MutableInteractionSource) value$iv$iv;
                } else {
                    modifier3 = modifier6;
                    interactionSource2 = interactionSource;
                }
                if ((i & 32) != 0) {
                    shape3 = MaterialTheme.INSTANCE.getShapes($composer3, 6).getSmall().copy(CornerSizeKt.CornerSize(50));
                    $dirty2 &= -458753;
                } else {
                    shape3 = shape2;
                }
                BorderStroke border3 = i11 != 0 ? null : borderStroke;
                if ((i & 128) != 0) {
                    i4 = i2;
                    i5 = i3;
                    colors2 = ChipDefaults.INSTANCE.m1270filterChipColorsJ08w3E(0L, 0L, 0L, 0L, 0L, 0L, 0L, 0L, 0L, $composer3, 805306368, FrameMetricsAggregator.EVERY_DURATION);
                    $dirty2 &= -29360129;
                } else {
                    i4 = i2;
                    i5 = i3;
                }
                Function2 leadingIcon2 = i12 != 0 ? null : function2;
                Function2 selectedIcon2 = i4 != 0 ? null : function22;
                if (i5 != 0) {
                    leadingIcon = leadingIcon2;
                    $dirty = $dirty2;
                    interactionSource3 = interactionSource2;
                    shape4 = shape3;
                    border2 = border3;
                    selectedIcon = selectedIcon2;
                    colors3 = colors2;
                    enabled2 = enabled4;
                    trailingIcon = null;
                    modifier4 = modifier3;
                } else {
                    trailingIcon = function23;
                    leadingIcon = leadingIcon2;
                    $dirty = $dirty2;
                    interactionSource3 = interactionSource2;
                    shape4 = shape3;
                    border2 = border3;
                    selectedIcon = selectedIcon2;
                    colors3 = colors2;
                    enabled2 = enabled4;
                    modifier4 = modifier3;
                }
            } else {
                $composer3.skipToGroupEnd();
                if ((i & 32) != 0) {
                    $dirty2 &= -458753;
                }
                if ((i & 128) != 0) {
                    int i15 = (-29360129) & $dirty2;
                    enabled2 = enabled;
                    interactionSource3 = interactionSource;
                    leadingIcon = function2;
                    selectedIcon = function22;
                    shape4 = shape2;
                    border2 = borderStroke;
                    modifier4 = modifier2;
                    trailingIcon = function24;
                    $dirty = i15;
                    colors3 = colors2;
                } else {
                    interactionSource3 = interactionSource;
                    leadingIcon = function2;
                    selectedIcon = function22;
                    shape4 = shape2;
                    border2 = borderStroke;
                    colors3 = colors2;
                    modifier4 = modifier2;
                    trailingIcon = function24;
                    $dirty = $dirty2;
                    enabled2 = enabled;
                }
            }
            $composer3.endDefaults();
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventStart(-1259208246, $dirty, $dirty1, "androidx.compose.material.FilterChip (Chip.kt:197)");
            }
            final State contentColor = colors3.contentColor(enabled2, selected, $composer3, (($dirty >> 9) & 14) | (($dirty << 3) & 112) | (($dirty >> 15) & 896));
            Modifier semantics$default = SemanticsModifierKt.semantics$default(modifier4, false, new Function1<SemanticsPropertyReceiver, Unit>() { // from class: androidx.compose.material.ChipKt$FilterChip$2
                @Override // kotlin.jvm.functions.Function1
                public /* bridge */ /* synthetic */ Unit invoke(SemanticsPropertyReceiver semanticsPropertyReceiver) {
                    invoke2(semanticsPropertyReceiver);
                    return Unit.INSTANCE;
                }

                /* renamed from: invoke, reason: avoid collision after fix types in other method */
                public final void invoke2(SemanticsPropertyReceiver $this$semantics) {
                    SemanticsPropertiesKt.m5415setRolekuIjeqM($this$semantics, Role.INSTANCE.m5400getCheckboxo7Vup1c());
                }
            }, 1, null);
            long m3756unboximpl = colors3.backgroundColor(enabled2, selected, $composer3, (($dirty >> 9) & 14) | (($dirty << 3) & 112) | (($dirty >> 15) & 896)).getValue().m3756unboximpl();
            m3744copywmQWz5c = Color.m3744copywmQWz5c(r7, (r12 & 1) != 0 ? Color.m3748getAlphaimpl(r7) : 1.0f, (r12 & 2) != 0 ? Color.m3752getRedimpl(r7) : 0.0f, (r12 & 4) != 0 ? Color.m3751getGreenimpl(r7) : 0.0f, (r12 & 8) != 0 ? Color.m3749getBlueimpl(contentColor.getValue().m3756unboximpl()) : 0.0f);
            final Function2 function25 = leadingIcon;
            final Function2 function26 = selectedIcon;
            final Function2 function27 = trailingIcon;
            final SelectableChipColors selectableChipColors = colors3;
            final boolean z = enabled2;
            colors4 = colors3;
            enabled3 = enabled2;
            modifier5 = modifier4;
            $composer2 = $composer3;
            SurfaceKt.m1467SurfaceNy5ogXk(selected, function0, semantics$default, enabled3, shape4, m3756unboximpl, m3744copywmQWz5c, border2, 0.0f, interactionSource3, ComposableLambdaKt.composableLambda($composer3, 722126431, true, new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material.ChipKt$FilterChip$3
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
                    ComposerKt.sourceInformation($composer4, "C211@9743L3950:Chip.kt#jmzs0o");
                    if (($changed2 & 11) != 2 || !$composer4.getSkipping()) {
                        if (ComposerKt.isTraceInProgress()) {
                            ComposerKt.traceEventStart(722126431, $changed2, -1, "androidx.compose.material.FilterChip.<anonymous> (Chip.kt:211)");
                        }
                        ProvidedValue<Float> provides = ContentAlphaKt.getLocalContentAlpha().provides(Float.valueOf(Color.m3748getAlphaimpl(contentColor.getValue().m3756unboximpl())));
                        final Function2<Composer, Integer, Unit> function28 = function25;
                        final boolean z2 = selected;
                        final Function2<Composer, Integer, Unit> function29 = function26;
                        final Function2<Composer, Integer, Unit> function210 = function27;
                        final Function3<RowScope, Composer, Integer, Unit> function32 = function3;
                        final SelectableChipColors selectableChipColors2 = selectableChipColors;
                        final boolean z3 = z;
                        final State<Color> state = contentColor;
                        CompositionLocalKt.CompositionLocalProvider(provides, ComposableLambdaKt.composableLambda($composer4, 1582291359, true, new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material.ChipKt$FilterChip$3.1
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

                            public final void invoke(Composer $composer5, int $changed3) {
                                ComposerKt.sourceInformation($composer5, "C213@9891L10,212@9835L3848:Chip.kt#jmzs0o");
                                if (($changed3 & 11) != 2 || !$composer5.getSkipping()) {
                                    if (ComposerKt.isTraceInProgress()) {
                                        ComposerKt.traceEventStart(1582291359, $changed3, -1, "androidx.compose.material.FilterChip.<anonymous>.<anonymous> (Chip.kt:212)");
                                    }
                                    TextStyle body2 = MaterialTheme.INSTANCE.getTypography($composer5, 6).getBody2();
                                    final Function2<Composer, Integer, Unit> function211 = function28;
                                    final boolean z4 = z2;
                                    final Function2<Composer, Integer, Unit> function212 = function29;
                                    final Function2<Composer, Integer, Unit> function213 = function210;
                                    final Function3<RowScope, Composer, Integer, Unit> function33 = function32;
                                    final SelectableChipColors selectableChipColors3 = selectableChipColors2;
                                    final boolean z5 = z3;
                                    final State<Color> state2 = state;
                                    TextKt.ProvideTextStyle(body2, ComposableLambdaKt.composableLambda($composer5, -1543702066, true, new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material.ChipKt.FilterChip.3.1.1
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

                                        /* JADX WARN: Removed duplicated region for block: B:39:0x05a8  */
                                        /* JADX WARN: Removed duplicated region for block: B:42:0x05b4  */
                                        /* JADX WARN: Removed duplicated region for block: B:45:0x05e7  */
                                        /* JADX WARN: Removed duplicated region for block: B:50:0x0674  */
                                        /* JADX WARN: Removed duplicated region for block: B:53:0x06bd  */
                                        /* JADX WARN: Removed duplicated region for block: B:55:? A[RETURN, SYNTHETIC] */
                                        /* JADX WARN: Removed duplicated region for block: B:57:0x05fd A[ADDED_TO_REGION] */
                                        /* JADX WARN: Removed duplicated region for block: B:58:0x05b8  */
                                        /* JADX WARN: Removed duplicated region for block: B:61:0x024c  */
                                        /* JADX WARN: Removed duplicated region for block: B:64:0x0258  */
                                        /* JADX WARN: Removed duplicated region for block: B:72:0x0318  */
                                        /* JADX WARN: Removed duplicated region for block: B:75:0x036c A[ADDED_TO_REGION] */
                                        /* JADX WARN: Removed duplicated region for block: B:78:0x038c  */
                                        /* JADX WARN: Removed duplicated region for block: B:81:0x0427  */
                                        /* JADX WARN: Removed duplicated region for block: B:84:0x0433  */
                                        /* JADX WARN: Removed duplicated region for block: B:93:0x0439  */
                                        /* JADX WARN: Removed duplicated region for block: B:95:0x0358  */
                                        /* JADX WARN: Removed duplicated region for block: B:98:0x025e  */
                                        /*
                                            Code decompiled incorrectly, please refer to instructions dump.
                                            To view partially-correct add '--show-bad-code' argument
                                        */
                                        public final void invoke(androidx.compose.runtime.Composer r80, int r81) {
                                            /*
                                                Method dump skipped, instructions count: 1729
                                                To view this dump add '--comments-level debug' option
                                            */
                                            throw new UnsupportedOperationException("Method not decompiled: androidx.compose.material.ChipKt$FilterChip$3.AnonymousClass1.C00391.invoke(androidx.compose.runtime.Composer, int):void");
                                        }
                                    }), $composer5, 48);
                                    if (ComposerKt.isTraceInProgress()) {
                                        ComposerKt.traceEventEnd();
                                        return;
                                    }
                                    return;
                                }
                                $composer5.skipToGroupEnd();
                            }
                        }), $composer4, ProvidedValue.$stable | 0 | 48);
                        if (ComposerKt.isTraceInProgress()) {
                            ComposerKt.traceEventEnd();
                            return;
                        }
                        return;
                    }
                    $composer4.skipToGroupEnd();
                }
            }), $composer2, (($dirty << 15) & 1879048192) | ($dirty & 14) | ($dirty & 112) | ($dirty & 7168) | (($dirty >> 3) & 57344) | (($dirty << 3) & 29360128), 6, 256);
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventEnd();
            }
        }
        ScopeUpdateScope endRestartGroup = $composer2.endRestartGroup();
        if (endRestartGroup != null) {
            final Modifier modifier7 = modifier5;
            final boolean z2 = enabled3;
            final MutableInteractionSource mutableInteractionSource = interactionSource3;
            final Shape shape5 = shape4;
            final BorderStroke borderStroke2 = border2;
            final SelectableChipColors selectableChipColors2 = colors4;
            final Function2 function28 = leadingIcon;
            final Function2 function29 = selectedIcon;
            final Function2 function210 = trailingIcon;
            endRestartGroup.updateScope(new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material.ChipKt$FilterChip$4
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

                public final void invoke(Composer composer, int i16) {
                    ChipKt.FilterChip(selected, function0, modifier7, z2, mutableInteractionSource, shape5, borderStroke2, selectableChipColors2, function28, function29, function210, function3, composer, RecomposeScopeImplKt.updateChangedFlags($changed | 1), RecomposeScopeImplKt.updateChangedFlags($changed1), i);
                }
            });
        }
    }
}
