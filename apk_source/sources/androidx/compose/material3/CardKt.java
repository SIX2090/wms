package androidx.compose.material3;

import androidx.compose.foundation.BorderStroke;
import androidx.compose.foundation.interaction.InteractionSourceKt;
import androidx.compose.foundation.interaction.MutableInteractionSource;
import androidx.compose.foundation.layout.ColumnScope;
import androidx.compose.runtime.Composer;
import androidx.compose.runtime.ComposerKt;
import androidx.compose.runtime.RecomposeScopeImplKt;
import androidx.compose.runtime.ScopeUpdateScope;
import androidx.compose.runtime.internal.ComposableLambdaKt;
import androidx.compose.ui.Modifier;
import androidx.compose.ui.graphics.Shape;
import androidx.core.view.accessibility.AccessibilityEventCompat;
import androidx.profileinstaller.ProfileVerifier;
import kotlin.Metadata;
import kotlin.Unit;
import kotlin.jvm.functions.Function0;
import kotlin.jvm.functions.Function2;
import kotlin.jvm.functions.Function3;

/* compiled from: Card.kt */
@Metadata(d1 = {"\u0000L\n\u0000\n\u0002\u0010\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010\u000b\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\b\u0007\u001a\u0081\u0001\u0010\u0000\u001a\u00020\u00012\f\u0010\u0002\u001a\b\u0012\u0004\u0012\u00020\u00010\u00032\b\b\u0002\u0010\u0004\u001a\u00020\u00052\b\b\u0002\u0010\u0006\u001a\u00020\u00072\b\b\u0002\u0010\b\u001a\u00020\t2\b\b\u0002\u0010\n\u001a\u00020\u000b2\b\b\u0002\u0010\f\u001a\u00020\r2\n\b\u0002\u0010\u000e\u001a\u0004\u0018\u00010\u000f2\b\b\u0002\u0010\u0010\u001a\u00020\u00112\u001c\u0010\u0012\u001a\u0018\u0012\u0004\u0012\u00020\u0014\u0012\u0004\u0012\u00020\u00010\u0013¢\u0006\u0002\b\u0015¢\u0006\u0002\b\u0016H\u0007¢\u0006\u0002\u0010\u0017\u001a_\u0010\u0000\u001a\u00020\u00012\b\b\u0002\u0010\u0004\u001a\u00020\u00052\b\b\u0002\u0010\b\u001a\u00020\t2\b\b\u0002\u0010\n\u001a\u00020\u000b2\b\b\u0002\u0010\f\u001a\u00020\r2\n\b\u0002\u0010\u000e\u001a\u0004\u0018\u00010\u000f2\u001c\u0010\u0012\u001a\u0018\u0012\u0004\u0012\u00020\u0014\u0012\u0004\u0012\u00020\u00010\u0013¢\u0006\u0002\b\u0015¢\u0006\u0002\b\u0016H\u0007¢\u0006\u0002\u0010\u0018\u001au\u0010\u0019\u001a\u00020\u00012\f\u0010\u0002\u001a\b\u0012\u0004\u0012\u00020\u00010\u00032\b\b\u0002\u0010\u0004\u001a\u00020\u00052\b\b\u0002\u0010\u0006\u001a\u00020\u00072\b\b\u0002\u0010\b\u001a\u00020\t2\b\b\u0002\u0010\n\u001a\u00020\u000b2\b\b\u0002\u0010\f\u001a\u00020\r2\b\b\u0002\u0010\u0010\u001a\u00020\u00112\u001c\u0010\u0012\u001a\u0018\u0012\u0004\u0012\u00020\u0014\u0012\u0004\u0012\u00020\u00010\u0013¢\u0006\u0002\b\u0015¢\u0006\u0002\b\u0016H\u0007¢\u0006\u0002\u0010\u001a\u001aS\u0010\u0019\u001a\u00020\u00012\b\b\u0002\u0010\u0004\u001a\u00020\u00052\b\b\u0002\u0010\b\u001a\u00020\t2\b\b\u0002\u0010\n\u001a\u00020\u000b2\b\b\u0002\u0010\f\u001a\u00020\r2\u001c\u0010\u0012\u001a\u0018\u0012\u0004\u0012\u00020\u0014\u0012\u0004\u0012\u00020\u00010\u0013¢\u0006\u0002\b\u0015¢\u0006\u0002\b\u0016H\u0007¢\u0006\u0002\u0010\u001b\u001a\u007f\u0010\u001c\u001a\u00020\u00012\f\u0010\u0002\u001a\b\u0012\u0004\u0012\u00020\u00010\u00032\b\b\u0002\u0010\u0004\u001a\u00020\u00052\b\b\u0002\u0010\u0006\u001a\u00020\u00072\b\b\u0002\u0010\b\u001a\u00020\t2\b\b\u0002\u0010\n\u001a\u00020\u000b2\b\b\u0002\u0010\f\u001a\u00020\r2\b\b\u0002\u0010\u000e\u001a\u00020\u000f2\b\b\u0002\u0010\u0010\u001a\u00020\u00112\u001c\u0010\u0012\u001a\u0018\u0012\u0004\u0012\u00020\u0014\u0012\u0004\u0012\u00020\u00010\u0013¢\u0006\u0002\b\u0015¢\u0006\u0002\b\u0016H\u0007¢\u0006\u0002\u0010\u0017\u001a]\u0010\u001c\u001a\u00020\u00012\b\b\u0002\u0010\u0004\u001a\u00020\u00052\b\b\u0002\u0010\b\u001a\u00020\t2\b\b\u0002\u0010\n\u001a\u00020\u000b2\b\b\u0002\u0010\f\u001a\u00020\r2\b\b\u0002\u0010\u000e\u001a\u00020\u000f2\u001c\u0010\u0012\u001a\u0018\u0012\u0004\u0012\u00020\u0014\u0012\u0004\u0012\u00020\u00010\u0013¢\u0006\u0002\b\u0015¢\u0006\u0002\b\u0016H\u0007¢\u0006\u0002\u0010\u0018¨\u0006\u001d"}, d2 = {"Card", "", "onClick", "Lkotlin/Function0;", "modifier", "Landroidx/compose/ui/Modifier;", "enabled", "", "shape", "Landroidx/compose/ui/graphics/Shape;", "colors", "Landroidx/compose/material3/CardColors;", "elevation", "Landroidx/compose/material3/CardElevation;", androidx.compose.material.OutlinedTextFieldKt.BorderId, "Landroidx/compose/foundation/BorderStroke;", "interactionSource", "Landroidx/compose/foundation/interaction/MutableInteractionSource;", "content", "Lkotlin/Function1;", "Landroidx/compose/foundation/layout/ColumnScope;", "Landroidx/compose/runtime/Composable;", "Lkotlin/ExtensionFunctionType;", "(Lkotlin/jvm/functions/Function0;Landroidx/compose/ui/Modifier;ZLandroidx/compose/ui/graphics/Shape;Landroidx/compose/material3/CardColors;Landroidx/compose/material3/CardElevation;Landroidx/compose/foundation/BorderStroke;Landroidx/compose/foundation/interaction/MutableInteractionSource;Lkotlin/jvm/functions/Function3;Landroidx/compose/runtime/Composer;II)V", "(Landroidx/compose/ui/Modifier;Landroidx/compose/ui/graphics/Shape;Landroidx/compose/material3/CardColors;Landroidx/compose/material3/CardElevation;Landroidx/compose/foundation/BorderStroke;Lkotlin/jvm/functions/Function3;Landroidx/compose/runtime/Composer;II)V", "ElevatedCard", "(Lkotlin/jvm/functions/Function0;Landroidx/compose/ui/Modifier;ZLandroidx/compose/ui/graphics/Shape;Landroidx/compose/material3/CardColors;Landroidx/compose/material3/CardElevation;Landroidx/compose/foundation/interaction/MutableInteractionSource;Lkotlin/jvm/functions/Function3;Landroidx/compose/runtime/Composer;II)V", "(Landroidx/compose/ui/Modifier;Landroidx/compose/ui/graphics/Shape;Landroidx/compose/material3/CardColors;Landroidx/compose/material3/CardElevation;Lkotlin/jvm/functions/Function3;Landroidx/compose/runtime/Composer;II)V", "OutlinedCard", "material3_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class CardKt {
    public static final void Card(Modifier modifier, Shape shape, CardColors colors, CardElevation elevation, BorderStroke border, final Function3<? super ColumnScope, ? super Composer, ? super Integer, Unit> function3, Composer $composer, final int $changed, final int i) {
        Modifier modifier2;
        Shape shape2;
        CardColors cardColors;
        CardElevation cardElevation;
        BorderStroke border2;
        Modifier.Companion modifier3;
        Shape shape3;
        CardColors colors2;
        CardElevation elevation2;
        BorderStroke border3;
        Modifier modifier4;
        Shape shape4;
        CardColors colors3;
        CardElevation elevation3;
        int i2;
        int i3;
        int i4;
        Composer $composer2 = $composer.startRestartGroup(1179621553);
        ComposerKt.sourceInformation($composer2, "C(Card)P(4,5,1,3)78@3662L5,79@3707L12,80@3765L15,90@4151L57,84@3872L416:Card.kt#uh7d8r");
        int $dirty = $changed;
        int i5 = i & 1;
        if (i5 != 0) {
            $dirty |= 6;
            modifier2 = modifier;
        } else if (($changed & 6) == 0) {
            modifier2 = modifier;
            $dirty |= $composer2.changed(modifier2) ? 4 : 2;
        } else {
            modifier2 = modifier;
        }
        if (($changed & 48) == 0) {
            if ((i & 2) == 0) {
                shape2 = shape;
                if ($composer2.changed(shape2)) {
                    i4 = 32;
                    $dirty |= i4;
                }
            } else {
                shape2 = shape;
            }
            i4 = 16;
            $dirty |= i4;
        } else {
            shape2 = shape;
        }
        if (($changed & 384) == 0) {
            if ((i & 4) == 0) {
                cardColors = colors;
                if ($composer2.changed(cardColors)) {
                    i3 = 256;
                    $dirty |= i3;
                }
            } else {
                cardColors = colors;
            }
            i3 = 128;
            $dirty |= i3;
        } else {
            cardColors = colors;
        }
        if (($changed & 3072) == 0) {
            if ((i & 8) == 0) {
                cardElevation = elevation;
                if ($composer2.changed(cardElevation)) {
                    i2 = 2048;
                    $dirty |= i2;
                }
            } else {
                cardElevation = elevation;
            }
            i2 = 1024;
            $dirty |= i2;
        } else {
            cardElevation = elevation;
        }
        int i6 = i & 16;
        if (i6 != 0) {
            $dirty |= 24576;
            border2 = border;
        } else if (($changed & 24576) == 0) {
            border2 = border;
            $dirty |= $composer2.changed(border2) ? 16384 : 8192;
        } else {
            border2 = border;
        }
        if ((i & 32) != 0) {
            $dirty |= ProfileVerifier.CompilationStatus.RESULT_CODE_ERROR_CANT_WRITE_PROFILE_VERIFICATION_RESULT_CACHE_FILE;
        } else if (($changed & ProfileVerifier.CompilationStatus.RESULT_CODE_ERROR_CANT_WRITE_PROFILE_VERIFICATION_RESULT_CACHE_FILE) == 0) {
            $dirty |= $composer2.changedInstance(function3) ? 131072 : 65536;
        }
        if ((74899 & $dirty) == 74898 && $composer2.getSkipping()) {
            $composer2.skipToGroupEnd();
            modifier4 = modifier2;
            shape4 = shape2;
            colors3 = cardColors;
            elevation3 = cardElevation;
        } else {
            $composer2.startDefaults();
            if (($changed & 1) == 0 || $composer2.getDefaultsInvalid()) {
                modifier3 = i5 != 0 ? Modifier.INSTANCE : modifier2;
                if ((i & 2) != 0) {
                    shape3 = CardDefaults.INSTANCE.getShape($composer2, 6);
                    $dirty &= -113;
                } else {
                    shape3 = shape2;
                }
                if ((i & 4) != 0) {
                    colors2 = CardDefaults.INSTANCE.cardColors($composer2, 6);
                    $dirty &= -897;
                } else {
                    colors2 = cardColors;
                }
                if ((i & 8) != 0) {
                    elevation2 = CardDefaults.INSTANCE.m1628cardElevationaqJV_2Y(0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, $composer2, 1572864, 63);
                    $dirty &= -7169;
                } else {
                    elevation2 = cardElevation;
                }
                border3 = i6 != 0 ? null : border;
            } else {
                $composer2.skipToGroupEnd();
                if ((i & 2) != 0) {
                    $dirty &= -113;
                }
                if ((i & 4) != 0) {
                    $dirty &= -897;
                }
                if ((i & 8) != 0) {
                    $dirty &= -7169;
                }
                modifier3 = modifier2;
                shape3 = shape2;
                colors2 = cardColors;
                elevation2 = cardElevation;
                border3 = border2;
            }
            $composer2.endDefaults();
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventStart(1179621553, $dirty, -1, "androidx.compose.material3.Card (Card.kt:83)");
            }
            SurfaceKt.m2316SurfaceT9BRK9s(modifier3, shape3, colors2.m1620containerColorvNxB06k$material3_release(true), colors2.m1621contentColorvNxB06k$material3_release(true), elevation2.m1633tonalElevationu2uoSUM$material3_release(true), elevation2.shadowElevation$material3_release(true, null, $composer2, (($dirty >> 3) & 896) | 54).getValue().m6108unboximpl(), border3, ComposableLambdaKt.composableLambda($composer2, 664103990, true, new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.CardKt$Card$1
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

                /* JADX WARN: Removed duplicated region for block: B:24:0x014b  */
                /* JADX WARN: Removed duplicated region for block: B:26:? A[RETURN, SYNTHETIC] */
                /*
                    Code decompiled incorrectly, please refer to instructions dump.
                    To view partially-correct add '--show-bad-code' argument
                */
                public final void invoke(androidx.compose.runtime.Composer r25, int r26) {
                    /*
                        Method dump skipped, instructions count: 335
                        To view this dump add '--comments-level debug' option
                    */
                    throw new UnsupportedOperationException("Method not decompiled: androidx.compose.material3.CardKt$Card$1.invoke(androidx.compose.runtime.Composer, int):void");
                }
            }), $composer2, ($dirty & 14) | 12582912 | ($dirty & 112) | (($dirty << 6) & 3670016), 0);
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventEnd();
            }
            modifier4 = modifier3;
            shape4 = shape3;
            colors3 = colors2;
            elevation3 = elevation2;
            border2 = border3;
        }
        ScopeUpdateScope endRestartGroup = $composer2.endRestartGroup();
        if (endRestartGroup != null) {
            final Modifier modifier5 = modifier4;
            final Shape shape5 = shape4;
            final CardColors cardColors2 = colors3;
            final CardElevation cardElevation2 = elevation3;
            final BorderStroke borderStroke = border2;
            endRestartGroup.updateScope(new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.CardKt$Card$2
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
                    CardKt.Card(Modifier.this, shape5, cardColors2, cardElevation2, borderStroke, function3, composer, RecomposeScopeImplKt.updateChangedFlags($changed | 1), i);
                }
            });
        }
    }

    public static final void Card(final Function0<Unit> function0, Modifier modifier, boolean enabled, Shape shape, CardColors colors, CardElevation elevation, BorderStroke border, MutableInteractionSource interactionSource, final Function3<? super ColumnScope, ? super Composer, ? super Integer, Unit> function3, Composer $composer, final int $changed, final int i) {
        boolean enabled2;
        Shape shape2;
        CardColors colors2;
        CardElevation elevation2;
        BorderStroke border2;
        Modifier.Companion modifier2;
        Shape shape3;
        int $dirty;
        CardColors colors3;
        int i2;
        CardElevation elevation3;
        MutableInteractionSource interactionSource2;
        Object value$iv;
        Composer $composer2;
        Modifier modifier3;
        MutableInteractionSource interactionSource3;
        boolean enabled3;
        Shape shape4;
        CardColors colors4;
        BorderStroke border3;
        CardElevation elevation4;
        int i3;
        int i4;
        int i5;
        Composer $composer3 = $composer.startRestartGroup(-2024281376);
        ComposerKt.sourceInformation($composer3, "C(Card)P(7,6,4,8,1,3!1,5)135@6329L5,136@6374L12,137@6432L15,139@6533L39,150@6942L43,142@6630L482:Card.kt#uh7d8r");
        int $dirty2 = $changed;
        if ((i & 1) != 0) {
            $dirty2 |= 6;
        } else if (($changed & 6) == 0) {
            $dirty2 |= $composer3.changedInstance(function0) ? 4 : 2;
        }
        int i6 = i & 2;
        if (i6 != 0) {
            $dirty2 |= 48;
        } else if (($changed & 48) == 0) {
            $dirty2 |= $composer3.changed(modifier) ? 32 : 16;
        }
        int i7 = i & 4;
        if (i7 != 0) {
            $dirty2 |= 384;
            enabled2 = enabled;
        } else if (($changed & 384) == 0) {
            enabled2 = enabled;
            $dirty2 |= $composer3.changed(enabled2) ? 256 : 128;
        } else {
            enabled2 = enabled;
        }
        if (($changed & 3072) == 0) {
            if ((i & 8) == 0) {
                shape2 = shape;
                if ($composer3.changed(shape2)) {
                    i5 = 2048;
                    $dirty2 |= i5;
                }
            } else {
                shape2 = shape;
            }
            i5 = 1024;
            $dirty2 |= i5;
        } else {
            shape2 = shape;
        }
        if (($changed & 24576) == 0) {
            if ((i & 16) == 0) {
                colors2 = colors;
                if ($composer3.changed(colors2)) {
                    i4 = 16384;
                    $dirty2 |= i4;
                }
            } else {
                colors2 = colors;
            }
            i4 = 8192;
            $dirty2 |= i4;
        } else {
            colors2 = colors;
        }
        if ((196608 & $changed) == 0) {
            if ((i & 32) == 0) {
                elevation2 = elevation;
                if ($composer3.changed(elevation2)) {
                    i3 = 131072;
                    $dirty2 |= i3;
                }
            } else {
                elevation2 = elevation;
            }
            i3 = 65536;
            $dirty2 |= i3;
        } else {
            elevation2 = elevation;
        }
        int i8 = i & 64;
        if (i8 != 0) {
            $dirty2 |= 1572864;
            border2 = border;
        } else if ((1572864 & $changed) == 0) {
            border2 = border;
            $dirty2 |= $composer3.changed(border2) ? 1048576 : 524288;
        } else {
            border2 = border;
        }
        int i9 = i & 128;
        if (i9 != 0) {
            $dirty2 |= 12582912;
        } else if (($changed & 12582912) == 0) {
            $dirty2 |= $composer3.changed(interactionSource) ? 8388608 : 4194304;
        }
        if ((i & 256) != 0) {
            $dirty2 |= 100663296;
        } else if (($changed & 100663296) == 0) {
            $dirty2 |= $composer3.changedInstance(function3) ? AccessibilityEventCompat.TYPE_VIEW_TARGETED_BY_SCROLL : 33554432;
        }
        if ((38347923 & $dirty2) == 38347922 && $composer3.getSkipping()) {
            $composer3.skipToGroupEnd();
            modifier3 = modifier;
            interactionSource3 = interactionSource;
            shape4 = shape2;
            colors4 = colors2;
            border3 = border2;
            elevation4 = elevation2;
            $composer2 = $composer3;
            enabled3 = enabled2;
        } else {
            $composer3.startDefaults();
            if (($changed & 1) == 0 || $composer3.getDefaultsInvalid()) {
                modifier2 = i6 != 0 ? Modifier.INSTANCE : modifier;
                boolean enabled4 = i7 != 0 ? true : enabled2;
                if ((i & 8) != 0) {
                    $dirty2 &= -7169;
                    shape3 = CardDefaults.INSTANCE.getShape($composer3, 6);
                } else {
                    shape3 = shape2;
                }
                if ((i & 16) != 0) {
                    $dirty = $dirty2 & (-57345);
                    colors3 = CardDefaults.INSTANCE.cardColors($composer3, 6);
                } else {
                    $dirty = $dirty2;
                    colors3 = colors2;
                }
                if ((i & 32) != 0) {
                    i2 = i9;
                    elevation3 = CardDefaults.INSTANCE.m1628cardElevationaqJV_2Y(0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, $composer3, 1572864, 63);
                    $dirty &= -458753;
                } else {
                    i2 = i9;
                    elevation3 = elevation;
                }
                BorderStroke border4 = i8 != 0 ? null : border;
                if (i2 != 0) {
                    $composer3.startReplaceableGroup(63758450);
                    ComposerKt.sourceInformation($composer3, "CC(remember):Card.kt#9igjgp");
                    Object it$iv = $composer3.rememberedValue();
                    if (it$iv == Composer.INSTANCE.getEmpty()) {
                        value$iv = InteractionSourceKt.MutableInteractionSource();
                        $composer3.updateRememberedValue(value$iv);
                    } else {
                        value$iv = it$iv;
                    }
                    interactionSource2 = (MutableInteractionSource) value$iv;
                    $composer3.endReplaceableGroup();
                    elevation2 = elevation3;
                    border2 = border4;
                    enabled2 = enabled4;
                    shape2 = shape3;
                    colors2 = colors3;
                    $dirty2 = $dirty;
                } else {
                    interactionSource2 = interactionSource;
                    elevation2 = elevation3;
                    border2 = border4;
                    enabled2 = enabled4;
                    shape2 = shape3;
                    colors2 = colors3;
                    $dirty2 = $dirty;
                }
            } else {
                $composer3.skipToGroupEnd();
                if ((i & 8) != 0) {
                    $dirty2 &= -7169;
                }
                if ((i & 16) != 0) {
                    $dirty2 &= -57345;
                }
                if ((i & 32) != 0) {
                    interactionSource2 = interactionSource;
                    $dirty2 &= -458753;
                    modifier2 = modifier;
                } else {
                    modifier2 = modifier;
                    interactionSource2 = interactionSource;
                }
            }
            $composer3.endDefaults();
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventStart(-2024281376, $dirty2, -1, "androidx.compose.material3.Card (Card.kt:141)");
            }
            $composer2 = $composer3;
            SurfaceKt.m2319Surfaceo_FOJdg(function0, modifier2, enabled2, shape2, colors2.m1620containerColorvNxB06k$material3_release(enabled2), colors2.m1621contentColorvNxB06k$material3_release(enabled2), elevation2.m1633tonalElevationu2uoSUM$material3_release(enabled2), elevation2.shadowElevation$material3_release(enabled2, interactionSource2, $composer3, (($dirty2 >> 6) & 14) | (($dirty2 >> 18) & 112) | (($dirty2 >> 9) & 896)).getValue().m6108unboximpl(), border2, interactionSource2, ComposableLambdaKt.composableLambda($composer3, 776921067, true, new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.CardKt$Card$4
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

                /* JADX WARN: Removed duplicated region for block: B:24:0x014b  */
                /* JADX WARN: Removed duplicated region for block: B:26:? A[RETURN, SYNTHETIC] */
                /*
                    Code decompiled incorrectly, please refer to instructions dump.
                    To view partially-correct add '--show-bad-code' argument
                */
                public final void invoke(androidx.compose.runtime.Composer r25, int r26) {
                    /*
                        Method dump skipped, instructions count: 335
                        To view this dump add '--comments-level debug' option
                    */
                    throw new UnsupportedOperationException("Method not decompiled: androidx.compose.material3.CardKt$Card$4.invoke(androidx.compose.runtime.Composer, int):void");
                }
            }), $composer2, ($dirty2 & 14) | ($dirty2 & 112) | ($dirty2 & 896) | ($dirty2 & 7168) | (($dirty2 << 6) & 234881024) | (($dirty2 << 6) & 1879048192), 6, 0);
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventEnd();
            }
            modifier3 = modifier2;
            interactionSource3 = interactionSource2;
            enabled3 = enabled2;
            shape4 = shape2;
            colors4 = colors2;
            border3 = border2;
            elevation4 = elevation2;
        }
        ScopeUpdateScope endRestartGroup = $composer2.endRestartGroup();
        if (endRestartGroup != null) {
            final Modifier modifier4 = modifier3;
            final boolean z = enabled3;
            final Shape shape5 = shape4;
            final CardColors cardColors = colors4;
            final CardElevation cardElevation = elevation4;
            final BorderStroke borderStroke = border3;
            final MutableInteractionSource mutableInteractionSource = interactionSource3;
            endRestartGroup.updateScope(new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.CardKt$Card$5
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
                    CardKt.Card(function0, modifier4, z, shape5, cardColors, cardElevation, borderStroke, mutableInteractionSource, function3, composer, RecomposeScopeImplKt.updateChangedFlags($changed | 1), i);
                }
            });
        }
    }

    public static final void ElevatedCard(Modifier modifier, Shape shape, CardColors colors, CardElevation elevation, final Function3<? super ColumnScope, ? super Composer, ? super Integer, Unit> function3, Composer $composer, final int $changed, final int i) {
        Modifier modifier2;
        Shape shape2;
        CardColors cardColors;
        CardElevation elevation2;
        Modifier.Companion modifier3;
        Shape shape3;
        CardColors colors2;
        Modifier modifier4;
        Shape shape4;
        CardColors colors3;
        CardElevation elevation3;
        int i2;
        int i3;
        int i4;
        Composer $composer2 = $composer.startRestartGroup(895940201);
        ComposerKt.sourceInformation($composer2, "C(ElevatedCard)P(3,4!1,2)185@8559L13,186@8612L20,187@8678L23,189@8755L140:Card.kt#uh7d8r");
        int $dirty = $changed;
        int i5 = i & 1;
        if (i5 != 0) {
            $dirty |= 6;
            modifier2 = modifier;
        } else if (($changed & 6) == 0) {
            modifier2 = modifier;
            $dirty |= $composer2.changed(modifier2) ? 4 : 2;
        } else {
            modifier2 = modifier;
        }
        if (($changed & 48) == 0) {
            if ((i & 2) == 0) {
                shape2 = shape;
                if ($composer2.changed(shape2)) {
                    i4 = 32;
                    $dirty |= i4;
                }
            } else {
                shape2 = shape;
            }
            i4 = 16;
            $dirty |= i4;
        } else {
            shape2 = shape;
        }
        if (($changed & 384) == 0) {
            if ((i & 4) == 0) {
                cardColors = colors;
                if ($composer2.changed(cardColors)) {
                    i3 = 256;
                    $dirty |= i3;
                }
            } else {
                cardColors = colors;
            }
            i3 = 128;
            $dirty |= i3;
        } else {
            cardColors = colors;
        }
        if (($changed & 3072) == 0) {
            if ((i & 8) == 0) {
                elevation2 = elevation;
                if ($composer2.changed(elevation2)) {
                    i2 = 2048;
                    $dirty |= i2;
                }
            } else {
                elevation2 = elevation;
            }
            i2 = 1024;
            $dirty |= i2;
        } else {
            elevation2 = elevation;
        }
        if ((i & 16) != 0) {
            $dirty |= 24576;
        } else if (($changed & 24576) == 0) {
            $dirty |= $composer2.changedInstance(function3) ? 16384 : 8192;
        }
        if (($dirty & 9363) == 9362 && $composer2.getSkipping()) {
            $composer2.skipToGroupEnd();
            modifier4 = modifier2;
            shape4 = shape2;
            colors3 = cardColors;
            elevation3 = elevation2;
        } else {
            $composer2.startDefaults();
            if (($changed & 1) == 0 || $composer2.getDefaultsInvalid()) {
                modifier3 = i5 != 0 ? Modifier.INSTANCE : modifier2;
                if ((i & 2) != 0) {
                    shape3 = CardDefaults.INSTANCE.getElevatedShape($composer2, 6);
                    $dirty &= -113;
                } else {
                    shape3 = shape2;
                }
                if ((i & 4) != 0) {
                    colors2 = CardDefaults.INSTANCE.elevatedCardColors($composer2, 6);
                    $dirty &= -897;
                } else {
                    colors2 = cardColors;
                }
                if ((i & 8) != 0) {
                    $dirty &= -7169;
                    elevation2 = CardDefaults.INSTANCE.m1630elevatedCardElevationaqJV_2Y(0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, $composer2, 1572864, 63);
                }
            } else {
                $composer2.skipToGroupEnd();
                if ((i & 2) != 0) {
                    $dirty &= -113;
                }
                if ((i & 4) != 0) {
                    $dirty &= -897;
                }
                if ((i & 8) != 0) {
                    $dirty &= -7169;
                }
                modifier3 = modifier2;
                shape3 = shape2;
                colors2 = cardColors;
            }
            $composer2.endDefaults();
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventStart(895940201, $dirty, -1, "androidx.compose.material3.ElevatedCard (Card.kt:189)");
            }
            Card(modifier3, shape3, colors2, elevation2, null, function3, $composer2, ($dirty & 14) | 24576 | ($dirty & 112) | ($dirty & 896) | ($dirty & 7168) | (($dirty << 3) & 458752), 0);
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventEnd();
            }
            modifier4 = modifier3;
            shape4 = shape3;
            colors3 = colors2;
            elevation3 = elevation2;
        }
        ScopeUpdateScope endRestartGroup = $composer2.endRestartGroup();
        if (endRestartGroup != null) {
            final Modifier modifier5 = modifier4;
            final Shape shape5 = shape4;
            final CardColors cardColors2 = colors3;
            final CardElevation cardElevation = elevation3;
            endRestartGroup.updateScope(new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.CardKt$ElevatedCard$1
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

                public final void invoke(Composer composer, int i6) {
                    CardKt.ElevatedCard(Modifier.this, shape5, cardColors2, cardElevation, function3, composer, RecomposeScopeImplKt.updateChangedFlags($changed | 1), i);
                }
            });
        }
    }

    public static final void ElevatedCard(final Function0<Unit> function0, Modifier modifier, boolean enabled, Shape shape, CardColors colors, CardElevation elevation, MutableInteractionSource interactionSource, final Function3<? super ColumnScope, ? super Composer, ? super Integer, Unit> function3, Composer $composer, final int $changed, final int i) {
        Modifier modifier2;
        boolean enabled2;
        Shape shape2;
        CardColors colors2;
        CardElevation cardElevation;
        MutableInteractionSource mutableInteractionSource;
        Modifier.Companion modifier3;
        CardElevation elevation2;
        MutableInteractionSource interactionSource2;
        Object value$iv;
        Modifier modifier4;
        CardElevation elevation3;
        MutableInteractionSource interactionSource3;
        boolean enabled3;
        Shape shape3;
        CardColors colors3;
        int i2;
        int i3;
        int i4;
        Composer $composer2 = $composer.startRestartGroup(-1850977784);
        ComposerKt.sourceInformation($composer2, "C(ElevatedCard)P(6,5,3,7!1,2,4)233@10876L13,234@10929L20,235@10995L23,236@11070L39,238@11163L229:Card.kt#uh7d8r");
        int $dirty = $changed;
        if ((i & 1) != 0) {
            $dirty |= 6;
        } else if (($changed & 6) == 0) {
            $dirty |= $composer2.changedInstance(function0) ? 4 : 2;
        }
        int i5 = i & 2;
        if (i5 != 0) {
            $dirty |= 48;
            modifier2 = modifier;
        } else if (($changed & 48) == 0) {
            modifier2 = modifier;
            $dirty |= $composer2.changed(modifier2) ? 32 : 16;
        } else {
            modifier2 = modifier;
        }
        int i6 = i & 4;
        if (i6 != 0) {
            $dirty |= 384;
            enabled2 = enabled;
        } else if (($changed & 384) == 0) {
            enabled2 = enabled;
            $dirty |= $composer2.changed(enabled2) ? 256 : 128;
        } else {
            enabled2 = enabled;
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
                colors2 = colors;
                if ($composer2.changed(colors2)) {
                    i3 = 16384;
                    $dirty |= i3;
                }
            } else {
                colors2 = colors;
            }
            i3 = 8192;
            $dirty |= i3;
        } else {
            colors2 = colors;
        }
        if ((196608 & $changed) == 0) {
            if ((i & 32) == 0) {
                cardElevation = elevation;
                if ($composer2.changed(cardElevation)) {
                    i2 = 131072;
                    $dirty |= i2;
                }
            } else {
                cardElevation = elevation;
            }
            i2 = 65536;
            $dirty |= i2;
        } else {
            cardElevation = elevation;
        }
        int i7 = i & 64;
        if (i7 != 0) {
            $dirty |= 1572864;
            mutableInteractionSource = interactionSource;
        } else if (($changed & 1572864) == 0) {
            mutableInteractionSource = interactionSource;
            $dirty |= $composer2.changed(mutableInteractionSource) ? 1048576 : 524288;
        } else {
            mutableInteractionSource = interactionSource;
        }
        if ((i & 128) != 0) {
            $dirty |= 12582912;
        } else if (($changed & 12582912) == 0) {
            $dirty |= $composer2.changedInstance(function3) ? 8388608 : 4194304;
        }
        if ((4793491 & $dirty) == 4793490 && $composer2.getSkipping()) {
            $composer2.skipToGroupEnd();
            modifier4 = modifier2;
            enabled3 = enabled2;
            interactionSource3 = mutableInteractionSource;
            elevation3 = cardElevation;
            shape3 = shape2;
            colors3 = colors2;
        } else {
            $composer2.startDefaults();
            if (($changed & 1) == 0 || $composer2.getDefaultsInvalid()) {
                modifier3 = i5 != 0 ? Modifier.INSTANCE : modifier2;
                if (i6 != 0) {
                    enabled2 = true;
                }
                if ((i & 8) != 0) {
                    $dirty &= -7169;
                    shape2 = CardDefaults.INSTANCE.getElevatedShape($composer2, 6);
                }
                if ((i & 16) != 0) {
                    $dirty &= -57345;
                    colors2 = CardDefaults.INSTANCE.elevatedCardColors($composer2, 6);
                }
                if ((i & 32) != 0) {
                    elevation2 = CardDefaults.INSTANCE.m1630elevatedCardElevationaqJV_2Y(0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, $composer2, 1572864, 63);
                    $dirty &= -458753;
                } else {
                    elevation2 = elevation;
                }
                if (i7 != 0) {
                    $composer2.startReplaceableGroup(1166350241);
                    ComposerKt.sourceInformation($composer2, "CC(remember):Card.kt#9igjgp");
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
                if ((i & 32) != 0) {
                    $dirty &= -458753;
                    modifier3 = modifier2;
                    interactionSource2 = mutableInteractionSource;
                    elevation2 = cardElevation;
                } else {
                    modifier3 = modifier2;
                    interactionSource2 = mutableInteractionSource;
                    elevation2 = cardElevation;
                }
            }
            $composer2.endDefaults();
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventStart(-1850977784, $dirty, -1, "androidx.compose.material3.ElevatedCard (Card.kt:238)");
            }
            Card(function0, modifier3, enabled2, shape2, colors2, elevation2, null, interactionSource2, function3, $composer2, ($dirty & 14) | 1572864 | ($dirty & 112) | ($dirty & 896) | ($dirty & 7168) | (57344 & $dirty) | (458752 & $dirty) | (($dirty << 3) & 29360128) | (234881024 & ($dirty << 3)), 0);
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventEnd();
            }
            modifier4 = modifier3;
            elevation3 = elevation2;
            interactionSource3 = interactionSource2;
            enabled3 = enabled2;
            shape3 = shape2;
            colors3 = colors2;
        }
        ScopeUpdateScope endRestartGroup = $composer2.endRestartGroup();
        if (endRestartGroup != null) {
            final Modifier modifier5 = modifier4;
            final boolean z = enabled3;
            final Shape shape4 = shape3;
            final CardColors cardColors = colors3;
            final CardElevation cardElevation2 = elevation3;
            final MutableInteractionSource mutableInteractionSource2 = interactionSource3;
            endRestartGroup.updateScope(new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.CardKt$ElevatedCard$3
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
                    CardKt.ElevatedCard(function0, modifier5, z, shape4, cardColors, cardElevation2, mutableInteractionSource2, function3, composer, RecomposeScopeImplKt.updateChangedFlags($changed | 1), i);
                }
            });
        }
    }

    public static final void OutlinedCard(Modifier modifier, Shape shape, CardColors colors, CardElevation elevation, BorderStroke border, final Function3<? super ColumnScope, ? super Composer, ? super Integer, Unit> function3, Composer $composer, final int $changed, final int i) {
        Modifier modifier2;
        Shape shape2;
        CardColors cardColors;
        CardElevation cardElevation;
        BorderStroke border2;
        Modifier.Companion modifier3;
        Shape shape3;
        CardColors colors2;
        CardElevation elevation2;
        Modifier modifier4;
        Shape shape4;
        CardColors colors3;
        CardElevation elevation3;
        BorderStroke border3;
        int i2;
        int i3;
        int i4;
        int i5;
        Composer $composer2 = $composer.startRestartGroup(740336179);
        ComposerKt.sourceInformation($composer2, "C(OutlinedCard)P(4,5,1,3)278@12927L13,279@12980L20,280@13046L23,281@13111L20,283@13185L142:Card.kt#uh7d8r");
        int $dirty = $changed;
        int i6 = i & 1;
        if (i6 != 0) {
            $dirty |= 6;
            modifier2 = modifier;
        } else if (($changed & 6) == 0) {
            modifier2 = modifier;
            $dirty |= $composer2.changed(modifier2) ? 4 : 2;
        } else {
            modifier2 = modifier;
        }
        if (($changed & 48) == 0) {
            if ((i & 2) == 0) {
                shape2 = shape;
                if ($composer2.changed(shape2)) {
                    i5 = 32;
                    $dirty |= i5;
                }
            } else {
                shape2 = shape;
            }
            i5 = 16;
            $dirty |= i5;
        } else {
            shape2 = shape;
        }
        if (($changed & 384) == 0) {
            if ((i & 4) == 0) {
                cardColors = colors;
                if ($composer2.changed(cardColors)) {
                    i4 = 256;
                    $dirty |= i4;
                }
            } else {
                cardColors = colors;
            }
            i4 = 128;
            $dirty |= i4;
        } else {
            cardColors = colors;
        }
        if (($changed & 3072) == 0) {
            if ((i & 8) == 0) {
                cardElevation = elevation;
                if ($composer2.changed(cardElevation)) {
                    i3 = 2048;
                    $dirty |= i3;
                }
            } else {
                cardElevation = elevation;
            }
            i3 = 1024;
            $dirty |= i3;
        } else {
            cardElevation = elevation;
        }
        if (($changed & 24576) == 0) {
            if ((i & 16) == 0) {
                border2 = border;
                if ($composer2.changed(border2)) {
                    i2 = 16384;
                    $dirty |= i2;
                }
            } else {
                border2 = border;
            }
            i2 = 8192;
            $dirty |= i2;
        } else {
            border2 = border;
        }
        if ((i & 32) != 0) {
            $dirty |= ProfileVerifier.CompilationStatus.RESULT_CODE_ERROR_CANT_WRITE_PROFILE_VERIFICATION_RESULT_CACHE_FILE;
        } else if (($changed & ProfileVerifier.CompilationStatus.RESULT_CODE_ERROR_CANT_WRITE_PROFILE_VERIFICATION_RESULT_CACHE_FILE) == 0) {
            $dirty |= $composer2.changedInstance(function3) ? 131072 : 65536;
        }
        if ((74899 & $dirty) == 74898 && $composer2.getSkipping()) {
            $composer2.skipToGroupEnd();
            modifier4 = modifier2;
            shape4 = shape2;
            colors3 = cardColors;
            elevation3 = cardElevation;
            border3 = border2;
        } else {
            $composer2.startDefaults();
            if (($changed & 1) == 0 || $composer2.getDefaultsInvalid()) {
                modifier3 = i6 != 0 ? Modifier.INSTANCE : modifier2;
                if ((i & 2) != 0) {
                    shape3 = CardDefaults.INSTANCE.getOutlinedShape($composer2, 6);
                    $dirty &= -113;
                } else {
                    shape3 = shape2;
                }
                if ((i & 4) != 0) {
                    colors2 = CardDefaults.INSTANCE.outlinedCardColors($composer2, 6);
                    $dirty &= -897;
                } else {
                    colors2 = cardColors;
                }
                if ((i & 8) != 0) {
                    elevation2 = CardDefaults.INSTANCE.m1632outlinedCardElevationaqJV_2Y(0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, $composer2, 1572864, 63);
                    $dirty &= -7169;
                } else {
                    elevation2 = cardElevation;
                }
                if ((i & 16) != 0) {
                    $dirty &= -57345;
                    border2 = CardDefaults.INSTANCE.outlinedCardBorder(false, $composer2, 48, 1);
                }
            } else {
                $composer2.skipToGroupEnd();
                if ((i & 2) != 0) {
                    $dirty &= -113;
                }
                if ((i & 4) != 0) {
                    $dirty &= -897;
                }
                if ((i & 8) != 0) {
                    $dirty &= -7169;
                }
                if ((i & 16) != 0) {
                    $dirty &= -57345;
                }
                modifier3 = modifier2;
                shape3 = shape2;
                colors2 = cardColors;
                elevation2 = cardElevation;
            }
            $composer2.endDefaults();
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventStart(740336179, $dirty, -1, "androidx.compose.material3.OutlinedCard (Card.kt:283)");
            }
            Card(modifier3, shape3, colors2, elevation2, border2, function3, $composer2, ($dirty & 14) | ($dirty & 112) | ($dirty & 896) | ($dirty & 7168) | (57344 & $dirty) | (458752 & $dirty), 0);
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventEnd();
            }
            modifier4 = modifier3;
            shape4 = shape3;
            colors3 = colors2;
            elevation3 = elevation2;
            border3 = border2;
        }
        ScopeUpdateScope endRestartGroup = $composer2.endRestartGroup();
        if (endRestartGroup != null) {
            final Modifier modifier5 = modifier4;
            final Shape shape5 = shape4;
            final CardColors cardColors2 = colors3;
            final CardElevation cardElevation2 = elevation3;
            final BorderStroke borderStroke = border3;
            endRestartGroup.updateScope(new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.CardKt$OutlinedCard$1
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
                    CardKt.OutlinedCard(Modifier.this, shape5, cardColors2, cardElevation2, borderStroke, function3, composer, RecomposeScopeImplKt.updateChangedFlags($changed | 1), i);
                }
            });
        }
    }

    public static final void OutlinedCard(final Function0<Unit> function0, Modifier modifier, boolean enabled, Shape shape, CardColors colors, CardElevation elevation, BorderStroke border, MutableInteractionSource interactionSource, final Function3<? super ColumnScope, ? super Composer, ? super Integer, Unit> function3, Composer $composer, final int $changed, final int i) {
        boolean enabled2;
        Shape shape2;
        CardColors colors2;
        CardElevation elevation2;
        BorderStroke border2;
        MutableInteractionSource interactionSource2;
        Modifier.Companion modifier2;
        Shape shape3;
        int $dirty;
        CardColors colors3;
        boolean enabled3;
        int i2;
        BorderStroke border3;
        CardElevation elevation3;
        int $dirty2;
        Object value$iv;
        Composer $composer2;
        Modifier modifier3;
        CardElevation elevation4;
        boolean enabled4;
        Shape shape4;
        CardColors colors4;
        MutableInteractionSource interactionSource3;
        BorderStroke border4;
        int i3;
        int i4;
        int i5;
        int i6;
        Composer $composer3 = $composer.startRestartGroup(-727137250);
        ComposerKt.sourceInformation($composer3, "C(OutlinedCard)P(7,6,4,8,1,3!1,5)328@15398L13,329@15451L20,330@15517L23,331@15582L27,332@15661L39,334@15754L231:Card.kt#uh7d8r");
        int $dirty3 = $changed;
        if ((i & 1) != 0) {
            $dirty3 |= 6;
        } else if (($changed & 6) == 0) {
            $dirty3 |= $composer3.changedInstance(function0) ? 4 : 2;
        }
        int i7 = i & 2;
        if (i7 != 0) {
            $dirty3 |= 48;
        } else if (($changed & 48) == 0) {
            $dirty3 |= $composer3.changed(modifier) ? 32 : 16;
        }
        int i8 = i & 4;
        if (i8 != 0) {
            $dirty3 |= 384;
            enabled2 = enabled;
        } else if (($changed & 384) == 0) {
            enabled2 = enabled;
            $dirty3 |= $composer3.changed(enabled2) ? 256 : 128;
        } else {
            enabled2 = enabled;
        }
        if (($changed & 3072) == 0) {
            if ((i & 8) == 0) {
                shape2 = shape;
                if ($composer3.changed(shape2)) {
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
                if ($composer3.changed(colors2)) {
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
                if ($composer3.changed(elevation2)) {
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
        if ((1572864 & $changed) == 0) {
            if ((i & 64) == 0) {
                border2 = border;
                if ($composer3.changed(border2)) {
                    i3 = 1048576;
                    $dirty3 |= i3;
                }
            } else {
                border2 = border;
            }
            i3 = 524288;
            $dirty3 |= i3;
        } else {
            border2 = border;
        }
        int i9 = i & 128;
        if (i9 != 0) {
            $dirty3 |= 12582912;
            interactionSource2 = interactionSource;
        } else if ((12582912 & $changed) == 0) {
            interactionSource2 = interactionSource;
            $dirty3 |= $composer3.changed(interactionSource2) ? 8388608 : 4194304;
        } else {
            interactionSource2 = interactionSource;
        }
        if ((i & 256) != 0) {
            $dirty3 |= 100663296;
        } else if (($changed & 100663296) == 0) {
            $dirty3 |= $composer3.changedInstance(function3) ? AccessibilityEventCompat.TYPE_VIEW_TARGETED_BY_SCROLL : 33554432;
        }
        if (($dirty3 & 38347923) == 38347922 && $composer3.getSkipping()) {
            $composer3.skipToGroupEnd();
            enabled4 = enabled2;
            colors4 = colors2;
            interactionSource3 = interactionSource2;
            border4 = border2;
            elevation4 = elevation2;
            $composer2 = $composer3;
            modifier3 = modifier;
            shape4 = shape2;
        } else {
            $composer3.startDefaults();
            if (($changed & 1) == 0 || $composer3.getDefaultsInvalid()) {
                modifier2 = i7 != 0 ? Modifier.INSTANCE : modifier;
                if (i8 != 0) {
                    enabled2 = true;
                }
                if ((i & 8) != 0) {
                    $dirty3 &= -7169;
                    shape3 = CardDefaults.INSTANCE.getOutlinedShape($composer3, 6);
                } else {
                    shape3 = shape2;
                }
                if ((i & 16) != 0) {
                    $dirty = $dirty3 & (-57345);
                    colors3 = CardDefaults.INSTANCE.outlinedCardColors($composer3, 6);
                } else {
                    $dirty = $dirty3;
                    colors3 = colors2;
                }
                if ((i & 32) != 0) {
                    enabled3 = enabled2;
                    i2 = i9;
                    $dirty &= -458753;
                    elevation2 = CardDefaults.INSTANCE.m1632outlinedCardElevationaqJV_2Y(0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, $composer3, 1572864, 63);
                } else {
                    enabled3 = enabled2;
                    i2 = i9;
                }
                if ((i & 64) != 0) {
                    enabled2 = enabled3;
                    border3 = CardDefaults.INSTANCE.outlinedCardBorder(enabled2, $composer3, (($dirty >> 6) & 14) | 48, 0);
                    $dirty &= -3670017;
                } else {
                    enabled2 = enabled3;
                    border3 = border;
                }
                if (i2 != 0) {
                    $composer3.startReplaceableGroup(1028043736);
                    ComposerKt.sourceInformation($composer3, "CC(remember):Card.kt#9igjgp");
                    Object it$iv = $composer3.rememberedValue();
                    if (it$iv == Composer.INSTANCE.getEmpty()) {
                        value$iv = InteractionSourceKt.MutableInteractionSource();
                        $composer3.updateRememberedValue(value$iv);
                    } else {
                        value$iv = it$iv;
                    }
                    $composer3.endReplaceableGroup();
                    border2 = border3;
                    interactionSource2 = (MutableInteractionSource) value$iv;
                    elevation3 = elevation2;
                    shape2 = shape3;
                    colors2 = colors3;
                    $dirty2 = $dirty;
                } else {
                    interactionSource2 = interactionSource;
                    border2 = border3;
                    elevation3 = elevation2;
                    shape2 = shape3;
                    colors2 = colors3;
                    $dirty2 = $dirty;
                }
            } else {
                $composer3.skipToGroupEnd();
                if ((i & 8) != 0) {
                    $dirty3 &= -7169;
                }
                if ((i & 16) != 0) {
                    $dirty3 &= -57345;
                }
                if ((i & 32) != 0) {
                    $dirty3 &= -458753;
                }
                if ((i & 64) != 0) {
                    $dirty2 = $dirty3 & (-3670017);
                    elevation3 = elevation2;
                    modifier2 = modifier;
                } else {
                    modifier2 = modifier;
                    $dirty2 = $dirty3;
                    elevation3 = elevation2;
                }
            }
            $composer3.endDefaults();
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventStart(-727137250, $dirty2, -1, "androidx.compose.material3.OutlinedCard (Card.kt:334)");
            }
            $composer2 = $composer3;
            Card(function0, modifier2, enabled2, shape2, colors2, elevation3, border2, interactionSource2, function3, $composer2, ($dirty2 & 14) | ($dirty2 & 112) | ($dirty2 & 896) | ($dirty2 & 7168) | (57344 & $dirty2) | (458752 & $dirty2) | (3670016 & $dirty2) | (29360128 & $dirty2) | (234881024 & $dirty2), 0);
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventEnd();
            }
            modifier3 = modifier2;
            elevation4 = elevation3;
            enabled4 = enabled2;
            shape4 = shape2;
            colors4 = colors2;
            interactionSource3 = interactionSource2;
            border4 = border2;
        }
        ScopeUpdateScope endRestartGroup = $composer2.endRestartGroup();
        if (endRestartGroup != null) {
            final Modifier modifier4 = modifier3;
            final boolean z = enabled4;
            final Shape shape5 = shape4;
            final CardColors cardColors = colors4;
            final CardElevation cardElevation = elevation4;
            final BorderStroke borderStroke = border4;
            final MutableInteractionSource mutableInteractionSource = interactionSource3;
            endRestartGroup.updateScope(new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.CardKt$OutlinedCard$3
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
                    CardKt.OutlinedCard(function0, modifier4, z, shape5, cardColors, cardElevation, borderStroke, mutableInteractionSource, function3, composer, RecomposeScopeImplKt.updateChangedFlags($changed | 1), i);
                }
            });
        }
    }
}
