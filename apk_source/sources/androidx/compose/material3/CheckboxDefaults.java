package androidx.compose.material3;

import androidx.compose.material3.tokens.CheckboxTokens;
import androidx.compose.runtime.Composer;
import androidx.compose.runtime.ComposerKt;
import androidx.compose.ui.graphics.Color;
import kotlin.Metadata;

/* compiled from: Checkbox.kt */
@Metadata(d1 = {"\u0000 \n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\b\u0005\n\u0002\u0018\u0002\n\u0002\b\b\bÇ\u0002\u0018\u00002\u00020\u0001B\u0007\b\u0002¢\u0006\u0002\u0010\u0002J\r\u0010\b\u001a\u00020\u0004H\u0007¢\u0006\u0002\u0010\tJN\u0010\b\u001a\u00020\u00042\b\b\u0002\u0010\n\u001a\u00020\u000b2\b\b\u0002\u0010\f\u001a\u00020\u000b2\b\b\u0002\u0010\r\u001a\u00020\u000b2\b\b\u0002\u0010\u000e\u001a\u00020\u000b2\b\b\u0002\u0010\u000f\u001a\u00020\u000b2\b\b\u0002\u0010\u0010\u001a\u00020\u000bH\u0007ø\u0001\u0000¢\u0006\u0004\b\u0011\u0010\u0012R\u0018\u0010\u0003\u001a\u00020\u0004*\u00020\u00058@X\u0080\u0004¢\u0006\u0006\u001a\u0004\b\u0006\u0010\u0007\u0082\u0002\u0007\n\u0005\b¡\u001e0\u0001¨\u0006\u0013"}, d2 = {"Landroidx/compose/material3/CheckboxDefaults;", "", "()V", "defaultCheckboxColors", "Landroidx/compose/material3/CheckboxColors;", "Landroidx/compose/material3/ColorScheme;", "getDefaultCheckboxColors$material3_release", "(Landroidx/compose/material3/ColorScheme;)Landroidx/compose/material3/CheckboxColors;", "colors", "(Landroidx/compose/runtime/Composer;I)Landroidx/compose/material3/CheckboxColors;", "checkedColor", "Landroidx/compose/ui/graphics/Color;", "uncheckedColor", "checkmarkColor", "disabledCheckedColor", "disabledUncheckedColor", "disabledIndeterminateColor", "colors-5tl4gsc", "(JJJJJJLandroidx/compose/runtime/Composer;II)Landroidx/compose/material3/CheckboxColors;", "material3_release"}, k = 1, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class CheckboxDefaults {
    public static final int $stable = 0;
    public static final CheckboxDefaults INSTANCE = new CheckboxDefaults();

    private CheckboxDefaults() {
    }

    public final CheckboxColors colors(Composer $composer, int $changed) {
        $composer.startReplaceableGroup(-9530498);
        ComposerKt.sourceInformation($composer, "C(colors)188@8037L11:Checkbox.kt#uh7d8r");
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventStart(-9530498, $changed, -1, "androidx.compose.material3.CheckboxDefaults.colors (Checkbox.kt:188)");
        }
        CheckboxColors defaultCheckboxColors$material3_release = getDefaultCheckboxColors$material3_release(MaterialTheme.INSTANCE.getColorScheme($composer, 6));
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventEnd();
        }
        $composer.endReplaceableGroup();
        return defaultCheckboxColors$material3_release;
    }

    /* renamed from: colors-5tl4gsc, reason: not valid java name */
    public final CheckboxColors m1654colors5tl4gsc(long checkedColor, long uncheckedColor, long checkmarkColor, long disabledCheckedColor, long disabledUncheckedColor, long disabledIndeterminateColor, Composer $composer, int $changed, int i) {
        $composer.startReplaceableGroup(-89536160);
        ComposerKt.sourceInformation($composer, "C(colors)P(0:c#ui.graphics.Color,5:c#ui.graphics.Color,1:c#ui.graphics.Color,2:c#ui.graphics.Color,4:c#ui.graphics.Color,3:c#ui.graphics.Color)213@9410L11:Checkbox.kt#uh7d8r");
        long checkedColor2 = (i & 1) != 0 ? Color.INSTANCE.m3782getUnspecified0d7_KjU() : checkedColor;
        long uncheckedColor2 = (i & 2) != 0 ? Color.INSTANCE.m3782getUnspecified0d7_KjU() : uncheckedColor;
        long checkmarkColor2 = (i & 4) != 0 ? Color.INSTANCE.m3782getUnspecified0d7_KjU() : checkmarkColor;
        long disabledCheckedColor2 = (i & 8) != 0 ? Color.INSTANCE.m3782getUnspecified0d7_KjU() : disabledCheckedColor;
        long disabledUncheckedColor2 = (i & 16) != 0 ? Color.INSTANCE.m3782getUnspecified0d7_KjU() : disabledUncheckedColor;
        long disabledIndeterminateColor2 = (i & 32) != 0 ? Color.INSTANCE.m3782getUnspecified0d7_KjU() : disabledIndeterminateColor;
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventStart(-89536160, $changed, -1, "androidx.compose.material3.CheckboxDefaults.colors (Checkbox.kt:213)");
        }
        CheckboxColors m1641copy2qZNXz8 = getDefaultCheckboxColors$material3_release(MaterialTheme.INSTANCE.getColorScheme($composer, 6)).m1641copy2qZNXz8(checkmarkColor2, Color.INSTANCE.m3781getTransparent0d7_KjU(), checkedColor2, Color.INSTANCE.m3781getTransparent0d7_KjU(), disabledCheckedColor2, Color.INSTANCE.m3781getTransparent0d7_KjU(), disabledIndeterminateColor2, checkedColor2, uncheckedColor2, disabledCheckedColor2, disabledUncheckedColor2, disabledIndeterminateColor2);
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventEnd();
        }
        $composer.endReplaceableGroup();
        return m1641copy2qZNXz8;
    }

    public final CheckboxColors getDefaultCheckboxColors$material3_release(ColorScheme $this$defaultCheckboxColors) {
        long m3744copywmQWz5c;
        long m3744copywmQWz5c2;
        long m3744copywmQWz5c3;
        long m3744copywmQWz5c4;
        long m3744copywmQWz5c5;
        CheckboxColors defaultCheckboxColorsCached = $this$defaultCheckboxColors.getDefaultCheckboxColorsCached();
        if (defaultCheckboxColorsCached == null) {
            long fromToken = ColorSchemeKt.fromToken($this$defaultCheckboxColors, CheckboxTokens.INSTANCE.getSelectedIconColor());
            long m3781getTransparent0d7_KjU = Color.INSTANCE.m3781getTransparent0d7_KjU();
            long fromToken2 = ColorSchemeKt.fromToken($this$defaultCheckboxColors, CheckboxTokens.INSTANCE.getSelectedContainerColor());
            long m3781getTransparent0d7_KjU2 = Color.INSTANCE.m3781getTransparent0d7_KjU();
            m3744copywmQWz5c = Color.m3744copywmQWz5c(r12, (r12 & 1) != 0 ? Color.m3748getAlphaimpl(r12) : 0.38f, (r12 & 2) != 0 ? Color.m3752getRedimpl(r12) : 0.0f, (r12 & 4) != 0 ? Color.m3751getGreenimpl(r12) : 0.0f, (r12 & 8) != 0 ? Color.m3749getBlueimpl(ColorSchemeKt.fromToken($this$defaultCheckboxColors, CheckboxTokens.INSTANCE.getSelectedDisabledContainerColor())) : 0.0f);
            long m3781getTransparent0d7_KjU3 = Color.INSTANCE.m3781getTransparent0d7_KjU();
            m3744copywmQWz5c2 = Color.m3744copywmQWz5c(r16, (r12 & 1) != 0 ? Color.m3748getAlphaimpl(r16) : 0.38f, (r12 & 2) != 0 ? Color.m3752getRedimpl(r16) : 0.0f, (r12 & 4) != 0 ? Color.m3751getGreenimpl(r16) : 0.0f, (r12 & 8) != 0 ? Color.m3749getBlueimpl(ColorSchemeKt.fromToken($this$defaultCheckboxColors, CheckboxTokens.INSTANCE.getSelectedDisabledContainerColor())) : 0.0f);
            long fromToken3 = ColorSchemeKt.fromToken($this$defaultCheckboxColors, CheckboxTokens.INSTANCE.getSelectedContainerColor());
            long fromToken4 = ColorSchemeKt.fromToken($this$defaultCheckboxColors, CheckboxTokens.INSTANCE.getUnselectedOutlineColor());
            m3744copywmQWz5c3 = Color.m3744copywmQWz5c(r29, (r12 & 1) != 0 ? Color.m3748getAlphaimpl(r29) : 0.38f, (r12 & 2) != 0 ? Color.m3752getRedimpl(r29) : 0.0f, (r12 & 4) != 0 ? Color.m3751getGreenimpl(r29) : 0.0f, (r12 & 8) != 0 ? Color.m3749getBlueimpl(ColorSchemeKt.fromToken($this$defaultCheckboxColors, CheckboxTokens.INSTANCE.getSelectedDisabledContainerColor())) : 0.0f);
            m3744copywmQWz5c4 = Color.m3744copywmQWz5c(r29, (r12 & 1) != 0 ? Color.m3748getAlphaimpl(r29) : 0.38f, (r12 & 2) != 0 ? Color.m3752getRedimpl(r29) : 0.0f, (r12 & 4) != 0 ? Color.m3751getGreenimpl(r29) : 0.0f, (r12 & 8) != 0 ? Color.m3749getBlueimpl(ColorSchemeKt.fromToken($this$defaultCheckboxColors, CheckboxTokens.INSTANCE.getUnselectedDisabledOutlineColor())) : 0.0f);
            m3744copywmQWz5c5 = Color.m3744copywmQWz5c(r29, (r12 & 1) != 0 ? Color.m3748getAlphaimpl(r29) : 0.38f, (r12 & 2) != 0 ? Color.m3752getRedimpl(r29) : 0.0f, (r12 & 4) != 0 ? Color.m3751getGreenimpl(r29) : 0.0f, (r12 & 8) != 0 ? Color.m3749getBlueimpl(ColorSchemeKt.fromToken($this$defaultCheckboxColors, CheckboxTokens.INSTANCE.getSelectedDisabledContainerColor())) : 0.0f);
            CheckboxColors it = new CheckboxColors(fromToken, m3781getTransparent0d7_KjU, fromToken2, m3781getTransparent0d7_KjU2, m3744copywmQWz5c, m3781getTransparent0d7_KjU3, m3744copywmQWz5c2, fromToken3, fromToken4, m3744copywmQWz5c3, m3744copywmQWz5c4, m3744copywmQWz5c5, null);
            $this$defaultCheckboxColors.setDefaultCheckboxColorsCached$material3_release(it);
            return it;
        }
        return defaultCheckboxColorsCached;
    }
}
