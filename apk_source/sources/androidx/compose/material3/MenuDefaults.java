package androidx.compose.material3;

import androidx.compose.foundation.layout.PaddingKt;
import androidx.compose.foundation.layout.PaddingValues;
import androidx.compose.material3.tokens.MenuTokens;
import androidx.compose.runtime.Composer;
import androidx.compose.runtime.ComposerKt;
import androidx.compose.ui.graphics.Color;
import androidx.compose.ui.unit.Dp;
import kotlin.Metadata;

/* compiled from: Menu.kt */
@Metadata(d1 = {"\u0000(\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\b\u0005\n\u0002\u0018\u0002\n\u0002\b\b\bÇ\u0002\u0018\u00002\u00020\u0001B\u0007\b\u0002¢\u0006\u0002\u0010\u0002J\r\u0010\f\u001a\u00020\bH\u0007¢\u0006\u0002\u0010\rJN\u0010\f\u001a\u00020\b2\b\b\u0002\u0010\u000e\u001a\u00020\u000f2\b\b\u0002\u0010\u0010\u001a\u00020\u000f2\b\b\u0002\u0010\u0011\u001a\u00020\u000f2\b\b\u0002\u0010\u0012\u001a\u00020\u000f2\b\b\u0002\u0010\u0013\u001a\u00020\u000f2\b\b\u0002\u0010\u0014\u001a\u00020\u000fH\u0007ø\u0001\u0000¢\u0006\u0004\b\u0015\u0010\u0016R\u0011\u0010\u0003\u001a\u00020\u0004¢\u0006\b\n\u0000\u001a\u0004\b\u0005\u0010\u0006R\u0018\u0010\u0007\u001a\u00020\b*\u00020\t8@X\u0080\u0004¢\u0006\u0006\u001a\u0004\b\n\u0010\u000b\u0082\u0002\u0007\n\u0005\b¡\u001e0\u0001¨\u0006\u0017"}, d2 = {"Landroidx/compose/material3/MenuDefaults;", "", "()V", "DropdownMenuItemContentPadding", "Landroidx/compose/foundation/layout/PaddingValues;", "getDropdownMenuItemContentPadding", "()Landroidx/compose/foundation/layout/PaddingValues;", "defaultMenuItemColors", "Landroidx/compose/material3/MenuItemColors;", "Landroidx/compose/material3/ColorScheme;", "getDefaultMenuItemColors$material3_release", "(Landroidx/compose/material3/ColorScheme;)Landroidx/compose/material3/MenuItemColors;", "itemColors", "(Landroidx/compose/runtime/Composer;I)Landroidx/compose/material3/MenuItemColors;", "textColor", "Landroidx/compose/ui/graphics/Color;", "leadingIconColor", "trailingIconColor", "disabledTextColor", "disabledLeadingIconColor", "disabledTrailingIconColor", "itemColors-5tl4gsc", "(JJJJJJLandroidx/compose/runtime/Composer;II)Landroidx/compose/material3/MenuItemColors;", "material3_release"}, k = 1, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class MenuDefaults {
    public static final int $stable = 0;
    private static final PaddingValues DropdownMenuItemContentPadding;
    public static final MenuDefaults INSTANCE = new MenuDefaults();

    private MenuDefaults() {
    }

    public final MenuItemColors itemColors(Composer $composer, int $changed) {
        $composer.startReplaceableGroup(1326531516);
        ComposerKt.sourceInformation($composer, "C(itemColors)67@2725L11:Menu.kt#uh7d8r");
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventStart(1326531516, $changed, -1, "androidx.compose.material3.MenuDefaults.itemColors (Menu.kt:67)");
        }
        MenuItemColors defaultMenuItemColors$material3_release = getDefaultMenuItemColors$material3_release(MaterialTheme.INSTANCE.getColorScheme($composer, 6));
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventEnd();
        }
        $composer.endReplaceableGroup();
        return defaultMenuItemColors$material3_release;
    }

    /* renamed from: itemColors-5tl4gsc, reason: not valid java name */
    public final MenuItemColors m1999itemColors5tl4gsc(long textColor, long leadingIconColor, long trailingIconColor, long disabledTextColor, long disabledLeadingIconColor, long disabledTrailingIconColor, Composer $composer, int $changed, int i) {
        $composer.startReplaceableGroup(-1278543580);
        ComposerKt.sourceInformation($composer, "C(itemColors)P(4:c#ui.graphics.Color,3:c#ui.graphics.Color,5:c#ui.graphics.Color,1:c#ui.graphics.Color,0:c#ui.graphics.Color,2:c#ui.graphics.Color)91@3951L11:Menu.kt#uh7d8r");
        long textColor2 = (i & 1) != 0 ? Color.INSTANCE.m3782getUnspecified0d7_KjU() : textColor;
        long leadingIconColor2 = (i & 2) != 0 ? Color.INSTANCE.m3782getUnspecified0d7_KjU() : leadingIconColor;
        long trailingIconColor2 = (i & 4) != 0 ? Color.INSTANCE.m3782getUnspecified0d7_KjU() : trailingIconColor;
        long disabledTextColor2 = (i & 8) != 0 ? Color.INSTANCE.m3782getUnspecified0d7_KjU() : disabledTextColor;
        long disabledLeadingIconColor2 = (i & 16) != 0 ? Color.INSTANCE.m3782getUnspecified0d7_KjU() : disabledLeadingIconColor;
        long disabledTrailingIconColor2 = (i & 32) != 0 ? Color.INSTANCE.m3782getUnspecified0d7_KjU() : disabledTrailingIconColor;
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventStart(-1278543580, $changed, -1, "androidx.compose.material3.MenuDefaults.itemColors (Menu.kt:91)");
        }
        MenuItemColors m2001copytNS2XkQ = getDefaultMenuItemColors$material3_release(MaterialTheme.INSTANCE.getColorScheme($composer, 6)).m2001copytNS2XkQ(textColor2, leadingIconColor2, trailingIconColor2, disabledTextColor2, disabledLeadingIconColor2, disabledTrailingIconColor2);
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventEnd();
        }
        $composer.endReplaceableGroup();
        return m2001copytNS2XkQ;
    }

    public final MenuItemColors getDefaultMenuItemColors$material3_release(ColorScheme $this$defaultMenuItemColors) {
        long m3744copywmQWz5c;
        long m3744copywmQWz5c2;
        long m3744copywmQWz5c3;
        MenuItemColors defaultMenuItemColorsCached = $this$defaultMenuItemColors.getDefaultMenuItemColorsCached();
        if (defaultMenuItemColorsCached == null) {
            long fromToken = ColorSchemeKt.fromToken($this$defaultMenuItemColors, MenuTokens.INSTANCE.getListItemLabelTextColor());
            long fromToken2 = ColorSchemeKt.fromToken($this$defaultMenuItemColors, MenuTokens.INSTANCE.getListItemLeadingIconColor());
            long fromToken3 = ColorSchemeKt.fromToken($this$defaultMenuItemColors, MenuTokens.INSTANCE.getListItemTrailingIconColor());
            m3744copywmQWz5c = Color.m3744copywmQWz5c(r9, (r12 & 1) != 0 ? Color.m3748getAlphaimpl(r9) : 0.38f, (r12 & 2) != 0 ? Color.m3752getRedimpl(r9) : 0.0f, (r12 & 4) != 0 ? Color.m3751getGreenimpl(r9) : 0.0f, (r12 & 8) != 0 ? Color.m3749getBlueimpl(ColorSchemeKt.fromToken($this$defaultMenuItemColors, MenuTokens.INSTANCE.getListItemDisabledLabelTextColor())) : 0.0f);
            m3744copywmQWz5c2 = Color.m3744copywmQWz5c(r11, (r12 & 1) != 0 ? Color.m3748getAlphaimpl(r11) : 0.38f, (r12 & 2) != 0 ? Color.m3752getRedimpl(r11) : 0.0f, (r12 & 4) != 0 ? Color.m3751getGreenimpl(r11) : 0.0f, (r12 & 8) != 0 ? Color.m3749getBlueimpl(ColorSchemeKt.fromToken($this$defaultMenuItemColors, MenuTokens.INSTANCE.getListItemDisabledLeadingIconColor())) : 0.0f);
            m3744copywmQWz5c3 = Color.m3744copywmQWz5c(r13, (r12 & 1) != 0 ? Color.m3748getAlphaimpl(r13) : 0.38f, (r12 & 2) != 0 ? Color.m3752getRedimpl(r13) : 0.0f, (r12 & 4) != 0 ? Color.m3751getGreenimpl(r13) : 0.0f, (r12 & 8) != 0 ? Color.m3749getBlueimpl(ColorSchemeKt.fromToken($this$defaultMenuItemColors, MenuTokens.INSTANCE.getListItemDisabledTrailingIconColor())) : 0.0f);
            MenuItemColors it = new MenuItemColors(fromToken, fromToken2, fromToken3, m3744copywmQWz5c, m3744copywmQWz5c2, m3744copywmQWz5c3, null);
            $this$defaultMenuItemColors.setDefaultMenuItemColorsCached$material3_release(it);
            return it;
        }
        return defaultMenuItemColorsCached;
    }

    static {
        float f;
        f = MenuKt.DropdownMenuItemHorizontalPadding;
        DropdownMenuItemContentPadding = PaddingKt.m556PaddingValuesYgX7TsA(f, Dp.m6094constructorimpl(0));
    }

    public final PaddingValues getDropdownMenuItemContentPadding() {
        return DropdownMenuItemContentPadding;
    }
}
