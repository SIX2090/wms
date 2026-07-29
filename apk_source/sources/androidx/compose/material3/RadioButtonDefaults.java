package androidx.compose.material3;

import androidx.compose.material3.tokens.RadioButtonTokens;
import androidx.compose.runtime.Composer;
import androidx.compose.runtime.ComposerKt;
import androidx.compose.ui.graphics.Color;
import kotlin.Metadata;

/* compiled from: RadioButton.kt */
@Metadata(d1 = {"\u0000 \n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\b\u0005\n\u0002\u0018\u0002\n\u0002\b\u0006\bÇ\u0002\u0018\u00002\u00020\u0001B\u0007\b\u0002¢\u0006\u0002\u0010\u0002J\r\u0010\b\u001a\u00020\u0004H\u0007¢\u0006\u0002\u0010\tJ:\u0010\b\u001a\u00020\u00042\b\b\u0002\u0010\n\u001a\u00020\u000b2\b\b\u0002\u0010\f\u001a\u00020\u000b2\b\b\u0002\u0010\r\u001a\u00020\u000b2\b\b\u0002\u0010\u000e\u001a\u00020\u000bH\u0007ø\u0001\u0000¢\u0006\u0004\b\u000f\u0010\u0010R\u0018\u0010\u0003\u001a\u00020\u0004*\u00020\u00058@X\u0080\u0004¢\u0006\u0006\u001a\u0004\b\u0006\u0010\u0007\u0082\u0002\u0007\n\u0005\b¡\u001e0\u0001¨\u0006\u0011"}, d2 = {"Landroidx/compose/material3/RadioButtonDefaults;", "", "()V", "defaultRadioButtonColors", "Landroidx/compose/material3/RadioButtonColors;", "Landroidx/compose/material3/ColorScheme;", "getDefaultRadioButtonColors$material3_release", "(Landroidx/compose/material3/ColorScheme;)Landroidx/compose/material3/RadioButtonColors;", "colors", "(Landroidx/compose/runtime/Composer;I)Landroidx/compose/material3/RadioButtonColors;", "selectedColor", "Landroidx/compose/ui/graphics/Color;", "unselectedColor", "disabledSelectedColor", "disabledUnselectedColor", "colors-ro_MJ88", "(JJJJLandroidx/compose/runtime/Composer;II)Landroidx/compose/material3/RadioButtonColors;", "material3_release"}, k = 1, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class RadioButtonDefaults {
    public static final int $stable = 0;
    public static final RadioButtonDefaults INSTANCE = new RadioButtonDefaults();

    private RadioButtonDefaults() {
    }

    public final RadioButtonColors colors(Composer $composer, int $changed) {
        $composer.startReplaceableGroup(-1191566130);
        ComposerKt.sourceInformation($composer, "C(colors)139@5810L11:RadioButton.kt#uh7d8r");
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventStart(-1191566130, $changed, -1, "androidx.compose.material3.RadioButtonDefaults.colors (RadioButton.kt:139)");
        }
        RadioButtonColors defaultRadioButtonColors$material3_release = getDefaultRadioButtonColors$material3_release(MaterialTheme.INSTANCE.getColorScheme($composer, 6));
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventEnd();
        }
        $composer.endReplaceableGroup();
        return defaultRadioButtonColors$material3_release;
    }

    /* renamed from: colors-ro_MJ88, reason: not valid java name */
    public final RadioButtonColors m2110colorsro_MJ88(long selectedColor, long unselectedColor, long disabledSelectedColor, long disabledUnselectedColor, Composer $composer, int $changed, int i) {
        $composer.startReplaceableGroup(-351083046);
        ComposerKt.sourceInformation($composer, "C(colors)P(2:c#ui.graphics.Color,3:c#ui.graphics.Color,0:c#ui.graphics.Color,1:c#ui.graphics.Color)158@6771L11:RadioButton.kt#uh7d8r");
        long selectedColor2 = (i & 1) != 0 ? Color.INSTANCE.m3782getUnspecified0d7_KjU() : selectedColor;
        long unselectedColor2 = (i & 2) != 0 ? Color.INSTANCE.m3782getUnspecified0d7_KjU() : unselectedColor;
        long disabledSelectedColor2 = (i & 4) != 0 ? Color.INSTANCE.m3782getUnspecified0d7_KjU() : disabledSelectedColor;
        long disabledUnselectedColor2 = (i & 8) != 0 ? Color.INSTANCE.m3782getUnspecified0d7_KjU() : disabledUnselectedColor;
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventStart(-351083046, $changed, -1, "androidx.compose.material3.RadioButtonDefaults.colors (RadioButton.kt:158)");
        }
        RadioButtonColors m2105copyjRlVdoo = getDefaultRadioButtonColors$material3_release(MaterialTheme.INSTANCE.getColorScheme($composer, 6)).m2105copyjRlVdoo(selectedColor2, unselectedColor2, disabledSelectedColor2, disabledUnselectedColor2);
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventEnd();
        }
        $composer.endReplaceableGroup();
        return m2105copyjRlVdoo;
    }

    public final RadioButtonColors getDefaultRadioButtonColors$material3_release(ColorScheme $this$defaultRadioButtonColors) {
        long m3744copywmQWz5c;
        long m3744copywmQWz5c2;
        RadioButtonColors defaultRadioButtonColorsCached = $this$defaultRadioButtonColors.getDefaultRadioButtonColorsCached();
        if (defaultRadioButtonColorsCached == null) {
            long fromToken = ColorSchemeKt.fromToken($this$defaultRadioButtonColors, RadioButtonTokens.INSTANCE.getSelectedIconColor());
            long fromToken2 = ColorSchemeKt.fromToken($this$defaultRadioButtonColors, RadioButtonTokens.INSTANCE.getUnselectedIconColor());
            m3744copywmQWz5c = Color.m3744copywmQWz5c(r7, (r12 & 1) != 0 ? Color.m3748getAlphaimpl(r7) : 0.38f, (r12 & 2) != 0 ? Color.m3752getRedimpl(r7) : 0.0f, (r12 & 4) != 0 ? Color.m3751getGreenimpl(r7) : 0.0f, (r12 & 8) != 0 ? Color.m3749getBlueimpl(ColorSchemeKt.fromToken($this$defaultRadioButtonColors, RadioButtonTokens.INSTANCE.getDisabledSelectedIconColor())) : 0.0f);
            m3744copywmQWz5c2 = Color.m3744copywmQWz5c(r9, (r12 & 1) != 0 ? Color.m3748getAlphaimpl(r9) : 0.38f, (r12 & 2) != 0 ? Color.m3752getRedimpl(r9) : 0.0f, (r12 & 4) != 0 ? Color.m3751getGreenimpl(r9) : 0.0f, (r12 & 8) != 0 ? Color.m3749getBlueimpl(ColorSchemeKt.fromToken($this$defaultRadioButtonColors, RadioButtonTokens.INSTANCE.getDisabledUnselectedIconColor())) : 0.0f);
            RadioButtonColors it = new RadioButtonColors(fromToken, fromToken2, m3744copywmQWz5c, m3744copywmQWz5c2, null);
            $this$defaultRadioButtonColors.setDefaultRadioButtonColorsCached$material3_release(it);
            return it;
        }
        return defaultRadioButtonColorsCached;
    }
}
