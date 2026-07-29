package androidx.compose.material;

import androidx.compose.foundation.BorderStroke;
import androidx.compose.foundation.BorderStrokeKt;
import androidx.compose.runtime.Composer;
import androidx.compose.runtime.ComposerKt;
import androidx.compose.ui.graphics.Color;
import androidx.compose.ui.graphics.ColorKt;
import androidx.compose.ui.unit.Dp;
import kotlin.Metadata;

/* compiled from: Chip.kt */
@Metadata(d1 = {"\u0000:\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0002\b\u0002\n\u0002\u0010\u0007\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\b\u000b\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\b\n\u0002\u0018\u0002\n\u0002\b\f\bÇ\u0002\u0018\u00002\u00020\u0001B\u0007\b\u0002¢\u0006\u0002\u0010\u0002JN\u0010\u0016\u001a\u00020\u00172\b\b\u0002\u0010\u0018\u001a\u00020\u00192\b\b\u0002\u0010\u001a\u001a\u00020\u00192\b\b\u0002\u0010\u001b\u001a\u00020\u00192\b\b\u0002\u0010\u001c\u001a\u00020\u00192\b\b\u0002\u0010\u001d\u001a\u00020\u00192\b\b\u0002\u0010\u001e\u001a\u00020\u0019H\u0007ø\u0001\u0000¢\u0006\u0004\b\u001f\u0010 Jl\u0010!\u001a\u00020\"2\b\b\u0002\u0010\u0018\u001a\u00020\u00192\b\b\u0002\u0010\u001a\u001a\u00020\u00192\b\b\u0002\u0010#\u001a\u00020\u00192\b\b\u0002\u0010\u001c\u001a\u00020\u00192\b\b\u0002\u0010\u001d\u001a\u00020\u00192\b\b\u0002\u0010$\u001a\u00020\u00192\b\b\u0002\u0010%\u001a\u00020\u00192\b\b\u0002\u0010&\u001a\u00020\u00192\b\b\u0002\u0010'\u001a\u00020\u0019H\u0007ø\u0001\u0000¢\u0006\u0004\b(\u0010)JN\u0010*\u001a\u00020\u00172\b\b\u0002\u0010\u0018\u001a\u00020\u00192\b\b\u0002\u0010\u001a\u001a\u00020\u00192\b\b\u0002\u0010\u001b\u001a\u00020\u00192\b\b\u0002\u0010\u001c\u001a\u00020\u00192\b\b\u0002\u0010\u001d\u001a\u00020\u00192\b\b\u0002\u0010\u001e\u001a\u00020\u0019H\u0007ø\u0001\u0000¢\u0006\u0004\b+\u0010 Jl\u0010,\u001a\u00020\"2\b\b\u0002\u0010\u0018\u001a\u00020\u00192\b\b\u0002\u0010\u001a\u001a\u00020\u00192\b\b\u0002\u0010#\u001a\u00020\u00192\b\b\u0002\u0010\u001c\u001a\u00020\u00192\b\b\u0002\u0010\u001d\u001a\u00020\u00192\b\b\u0002\u0010$\u001a\u00020\u00192\b\b\u0002\u0010%\u001a\u00020\u00192\b\b\u0002\u0010&\u001a\u00020\u00192\b\b\u0002\u0010'\u001a\u00020\u0019H\u0007ø\u0001\u0000¢\u0006\u0004\b-\u0010)R\u000e\u0010\u0003\u001a\u00020\u0004X\u0086T¢\u0006\u0002\n\u0000R\u000e\u0010\u0005\u001a\u00020\u0004X\u0086T¢\u0006\u0002\n\u0000R\u0019\u0010\u0006\u001a\u00020\u0007ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u0010\n\u001a\u0004\b\b\u0010\tR\u0019\u0010\u000b\u001a\u00020\u0007ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u0010\n\u001a\u0004\b\f\u0010\tR\u000e\u0010\r\u001a\u00020\u0004X\u0086T¢\u0006\u0002\n\u0000R\u0019\u0010\u000e\u001a\u00020\u0007ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u0010\n\u001a\u0004\b\u000f\u0010\tR\u0019\u0010\u0010\u001a\u00020\u0007ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u0010\n\u001a\u0004\b\u0011\u0010\tR\u0011\u0010\u0012\u001a\u00020\u00138G¢\u0006\u0006\u001a\u0004\b\u0014\u0010\u0015\u0082\u0002\u000b\n\u0005\b¡\u001e0\u0001\n\u0002\b!¨\u0006."}, d2 = {"Landroidx/compose/material/ChipDefaults;", "", "()V", "ContentOpacity", "", "LeadingIconOpacity", "LeadingIconSize", "Landroidx/compose/ui/unit/Dp;", "getLeadingIconSize-D9Ej5fM", "()F", "F", "MinHeight", "getMinHeight-D9Ej5fM", "OutlinedBorderOpacity", "OutlinedBorderSize", "getOutlinedBorderSize-D9Ej5fM", "SelectedIconSize", "getSelectedIconSize-D9Ej5fM", "outlinedBorder", "Landroidx/compose/foundation/BorderStroke;", "getOutlinedBorder", "(Landroidx/compose/runtime/Composer;I)Landroidx/compose/foundation/BorderStroke;", "chipColors", "Landroidx/compose/material/ChipColors;", "backgroundColor", "Landroidx/compose/ui/graphics/Color;", "contentColor", "leadingIconContentColor", "disabledBackgroundColor", "disabledContentColor", "disabledLeadingIconContentColor", "chipColors-5tl4gsc", "(JJJJJJLandroidx/compose/runtime/Composer;II)Landroidx/compose/material/ChipColors;", "filterChipColors", "Landroidx/compose/material/SelectableChipColors;", "leadingIconColor", "disabledLeadingIconColor", "selectedBackgroundColor", "selectedContentColor", "selectedLeadingIconColor", "filterChipColors-J08w3-E", "(JJJJJJJJJLandroidx/compose/runtime/Composer;II)Landroidx/compose/material/SelectableChipColors;", "outlinedChipColors", "outlinedChipColors-5tl4gsc", "outlinedFilterChipColors", "outlinedFilterChipColors-J08w3-E", "material_release"}, k = 1, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class ChipDefaults {
    public static final int $stable = 0;
    public static final float ContentOpacity = 0.87f;
    public static final float LeadingIconOpacity = 0.54f;
    public static final float OutlinedBorderOpacity = 0.12f;
    public static final ChipDefaults INSTANCE = new ChipDefaults();
    private static final float MinHeight = Dp.m6094constructorimpl(32);
    private static final float OutlinedBorderSize = Dp.m6094constructorimpl(1);
    private static final float LeadingIconSize = Dp.m6094constructorimpl(20);
    private static final float SelectedIconSize = Dp.m6094constructorimpl(18);

    private ChipDefaults() {
    }

    /* renamed from: getMinHeight-D9Ej5fM, reason: not valid java name */
    public final float m1272getMinHeightD9Ej5fM() {
        return MinHeight;
    }

    /* renamed from: chipColors-5tl4gsc, reason: not valid java name */
    public final ChipColors m1269chipColors5tl4gsc(long backgroundColor, long contentColor, long leadingIconContentColor, long disabledBackgroundColor, long disabledContentColor, long disabledLeadingIconContentColor, Composer $composer, int $changed, int i) {
        long backgroundColor2;
        long contentColor2;
        long leadingIconContentColor2;
        long disabledBackgroundColor2;
        long disabledContentColor2;
        long m3744copywmQWz5c;
        long m3744copywmQWz5c2;
        long m3744copywmQWz5c3;
        long m3744copywmQWz5c4;
        long m3744copywmQWz5c5;
        $composer.startReplaceableGroup(1838505436);
        ComposerKt.sourceInformation($composer, "C(chipColors)P(0:c#ui.graphics.Color,1:c#ui.graphics.Color,5:c#ui.graphics.Color,2:c#ui.graphics.Color,3:c#ui.graphics.Color,4:c#ui.graphics.Color)392@17235L6,393@17329L6,394@17390L6,397@17592L6,398@17652L8,399@17727L6,401@17834L8,404@17982L8:Chip.kt#jmzs0o");
        if ((i & 1) != 0) {
            m3744copywmQWz5c5 = Color.m3744copywmQWz5c(r4, (r12 & 1) != 0 ? Color.m3748getAlphaimpl(r4) : 0.12f, (r12 & 2) != 0 ? Color.m3752getRedimpl(r4) : 0.0f, (r12 & 4) != 0 ? Color.m3751getGreenimpl(r4) : 0.0f, (r12 & 8) != 0 ? Color.m3749getBlueimpl(MaterialTheme.INSTANCE.getColors($composer, 6).m1285getOnSurface0d7_KjU()) : 0.0f);
            backgroundColor2 = ColorKt.m3791compositeOverOWjLjI(m3744copywmQWz5c5, MaterialTheme.INSTANCE.getColors($composer, 6).m1290getSurface0d7_KjU());
        } else {
            backgroundColor2 = backgroundColor;
        }
        if ((i & 2) != 0) {
            m3744copywmQWz5c4 = Color.m3744copywmQWz5c(r6, (r12 & 1) != 0 ? Color.m3748getAlphaimpl(r6) : 0.87f, (r12 & 2) != 0 ? Color.m3752getRedimpl(r6) : 0.0f, (r12 & 4) != 0 ? Color.m3751getGreenimpl(r6) : 0.0f, (r12 & 8) != 0 ? Color.m3749getBlueimpl(MaterialTheme.INSTANCE.getColors($composer, 6).m1285getOnSurface0d7_KjU()) : 0.0f);
            contentColor2 = m3744copywmQWz5c4;
        } else {
            contentColor2 = contentColor;
        }
        if ((i & 4) != 0) {
            m3744copywmQWz5c3 = Color.m3744copywmQWz5c(r8, (r12 & 1) != 0 ? Color.m3748getAlphaimpl(r8) : 0.54f, (r12 & 2) != 0 ? Color.m3752getRedimpl(r8) : 0.0f, (r12 & 4) != 0 ? Color.m3751getGreenimpl(r8) : 0.0f, (r12 & 8) != 0 ? Color.m3749getBlueimpl(contentColor2) : 0.0f);
            leadingIconContentColor2 = m3744copywmQWz5c3;
        } else {
            leadingIconContentColor2 = leadingIconContentColor;
        }
        if ((i & 8) != 0) {
            m3744copywmQWz5c2 = Color.m3744copywmQWz5c(r6, (r12 & 1) != 0 ? Color.m3748getAlphaimpl(r6) : 0.12f * ContentAlpha.INSTANCE.getDisabled($composer, 6), (r12 & 2) != 0 ? Color.m3752getRedimpl(r6) : 0.0f, (r12 & 4) != 0 ? Color.m3751getGreenimpl(r6) : 0.0f, (r12 & 8) != 0 ? Color.m3749getBlueimpl(MaterialTheme.INSTANCE.getColors($composer, 6).m1285getOnSurface0d7_KjU()) : 0.0f);
            disabledBackgroundColor2 = ColorKt.m3791compositeOverOWjLjI(m3744copywmQWz5c2, MaterialTheme.INSTANCE.getColors($composer, 6).m1290getSurface0d7_KjU());
        } else {
            disabledBackgroundColor2 = disabledBackgroundColor;
        }
        if ((i & 16) != 0) {
            m3744copywmQWz5c = Color.m3744copywmQWz5c(r29, (r12 & 1) != 0 ? Color.m3748getAlphaimpl(r29) : ContentAlpha.INSTANCE.getDisabled($composer, 6) * 0.87f, (r12 & 2) != 0 ? Color.m3752getRedimpl(r29) : 0.0f, (r12 & 4) != 0 ? Color.m3751getGreenimpl(r29) : 0.0f, (r12 & 8) != 0 ? Color.m3749getBlueimpl(contentColor2) : 0.0f);
            disabledContentColor2 = m3744copywmQWz5c;
        } else {
            disabledContentColor2 = disabledContentColor;
        }
        long disabledLeadingIconContentColor2 = (i & 32) != 0 ? Color.m3744copywmQWz5c(r29, (r12 & 1) != 0 ? Color.m3748getAlphaimpl(r29) : ContentAlpha.INSTANCE.getDisabled($composer, 6) * 0.54f, (r12 & 2) != 0 ? Color.m3752getRedimpl(r29) : 0.0f, (r12 & 4) != 0 ? Color.m3751getGreenimpl(r29) : 0.0f, (r12 & 8) != 0 ? Color.m3749getBlueimpl(leadingIconContentColor2) : 0.0f) : disabledLeadingIconContentColor;
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventStart(1838505436, $changed, -1, "androidx.compose.material.ChipDefaults.chipColors (Chip.kt:405)");
        }
        DefaultChipColors defaultChipColors = new DefaultChipColors(backgroundColor2, contentColor2, leadingIconContentColor2, disabledBackgroundColor2, disabledContentColor2, disabledLeadingIconContentColor2, null);
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventEnd();
        }
        $composer.endReplaceableGroup();
        return defaultChipColors;
    }

    /* renamed from: outlinedChipColors-5tl4gsc, reason: not valid java name */
    public final ChipColors m1275outlinedChipColors5tl4gsc(long backgroundColor, long contentColor, long leadingIconContentColor, long disabledBackgroundColor, long disabledContentColor, long disabledLeadingIconContentColor, Composer $composer, int $changed, int i) {
        long contentColor2;
        long leadingIconContentColor2;
        long disabledContentColor2;
        long disabledLeadingIconContentColor2;
        long m3744copywmQWz5c;
        long m3744copywmQWz5c2;
        long m3744copywmQWz5c3;
        long m3744copywmQWz5c4;
        $composer.startReplaceableGroup(-1763922662);
        ComposerKt.sourceInformation($composer, "C(outlinedChipColors)P(0:c#ui.graphics.Color,1:c#ui.graphics.Color,5:c#ui.graphics.Color,2:c#ui.graphics.Color,3:c#ui.graphics.Color,4:c#ui.graphics.Color)428@19178L6,429@19238L6,433@19521L8,436@19669L8,437@19721L342:Chip.kt#jmzs0o");
        long backgroundColor2 = (i & 1) != 0 ? MaterialTheme.INSTANCE.getColors($composer, 6).m1290getSurface0d7_KjU() : backgroundColor;
        if ((i & 2) != 0) {
            m3744copywmQWz5c4 = Color.m3744copywmQWz5c(r3, (r12 & 1) != 0 ? Color.m3748getAlphaimpl(r3) : 0.87f, (r12 & 2) != 0 ? Color.m3752getRedimpl(r3) : 0.0f, (r12 & 4) != 0 ? Color.m3751getGreenimpl(r3) : 0.0f, (r12 & 8) != 0 ? Color.m3749getBlueimpl(MaterialTheme.INSTANCE.getColors($composer, 6).m1285getOnSurface0d7_KjU()) : 0.0f);
            contentColor2 = m3744copywmQWz5c4;
        } else {
            contentColor2 = contentColor;
        }
        if ((i & 4) != 0) {
            m3744copywmQWz5c3 = Color.m3744copywmQWz5c(r5, (r12 & 1) != 0 ? Color.m3748getAlphaimpl(r5) : 0.54f, (r12 & 2) != 0 ? Color.m3752getRedimpl(r5) : 0.0f, (r12 & 4) != 0 ? Color.m3751getGreenimpl(r5) : 0.0f, (r12 & 8) != 0 ? Color.m3749getBlueimpl(contentColor2) : 0.0f);
            leadingIconContentColor2 = m3744copywmQWz5c3;
        } else {
            leadingIconContentColor2 = leadingIconContentColor;
        }
        long disabledBackgroundColor2 = (i & 8) != 0 ? backgroundColor2 : disabledBackgroundColor;
        if ((i & 16) != 0) {
            m3744copywmQWz5c2 = Color.m3744copywmQWz5c(r31, (r12 & 1) != 0 ? Color.m3748getAlphaimpl(r31) : ContentAlpha.INSTANCE.getDisabled($composer, 6) * 0.87f, (r12 & 2) != 0 ? Color.m3752getRedimpl(r31) : 0.0f, (r12 & 4) != 0 ? Color.m3751getGreenimpl(r31) : 0.0f, (r12 & 8) != 0 ? Color.m3749getBlueimpl(contentColor2) : 0.0f);
            disabledContentColor2 = m3744copywmQWz5c2;
        } else {
            disabledContentColor2 = disabledContentColor;
        }
        if ((i & 32) != 0) {
            m3744copywmQWz5c = Color.m3744copywmQWz5c(r31, (r12 & 1) != 0 ? Color.m3748getAlphaimpl(r31) : ContentAlpha.INSTANCE.getDisabled($composer, 6) * 0.54f, (r12 & 2) != 0 ? Color.m3752getRedimpl(r31) : 0.0f, (r12 & 4) != 0 ? Color.m3751getGreenimpl(r31) : 0.0f, (r12 & 8) != 0 ? Color.m3749getBlueimpl(leadingIconContentColor2) : 0.0f);
            disabledLeadingIconContentColor2 = m3744copywmQWz5c;
        } else {
            disabledLeadingIconContentColor2 = disabledLeadingIconContentColor;
        }
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventStart(-1763922662, $changed, -1, "androidx.compose.material.ChipDefaults.outlinedChipColors (Chip.kt:437)");
        }
        ChipColors m1269chipColors5tl4gsc = m1269chipColors5tl4gsc(backgroundColor2, contentColor2, leadingIconContentColor2, disabledBackgroundColor2, disabledContentColor2, disabledLeadingIconContentColor2, $composer, ($changed & 14) | ($changed & 112) | ($changed & 896) | ($changed & 7168) | (57344 & $changed) | (458752 & $changed) | (3670016 & $changed), 0);
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventEnd();
        }
        $composer.endReplaceableGroup();
        return m1269chipColors5tl4gsc;
    }

    /* renamed from: filterChipColors-J08w3-E, reason: not valid java name */
    public final SelectableChipColors m1270filterChipColorsJ08w3E(long backgroundColor, long contentColor, long leadingIconColor, long disabledBackgroundColor, long disabledContentColor, long disabledLeadingIconColor, long selectedBackgroundColor, long selectedContentColor, long selectedLeadingIconColor, Composer $composer, int $changed, int i) {
        long backgroundColor2;
        long leadingIconColor2;
        long disabledBackgroundColor2;
        long disabledContentColor2;
        long disabledLeadingIconColor2;
        long selectedBackgroundColor2;
        long selectedContentColor2;
        long selectedLeadingIconColor2;
        long m3744copywmQWz5c;
        long m3744copywmQWz5c2;
        long m3744copywmQWz5c3;
        long m3744copywmQWz5c4;
        long m3744copywmQWz5c5;
        long m3744copywmQWz5c6;
        long m3744copywmQWz5c7;
        long m3744copywmQWz5c8;
        $composer.startReplaceableGroup(830140629);
        ComposerKt.sourceInformation($composer, "C(filterChipColors)P(0:c#ui.graphics.Color,1:c#ui.graphics.Color,5:c#ui.graphics.Color,2:c#ui.graphics.Color,3:c#ui.graphics.Color,4:c#ui.graphics.Color,6:c#ui.graphics.Color,7:c#ui.graphics.Color,8:c#ui.graphics.Color)462@21060L6,463@21154L6,464@21215L6,467@21402L6,468@21462L8,469@21537L6,471@21644L8,474@21779L8,476@21875L6,479@22034L6,482@22195L6:Chip.kt#jmzs0o");
        if ((i & 1) != 0) {
            m3744copywmQWz5c8 = Color.m3744copywmQWz5c(r5, (r12 & 1) != 0 ? Color.m3748getAlphaimpl(r5) : 0.12f, (r12 & 2) != 0 ? Color.m3752getRedimpl(r5) : 0.0f, (r12 & 4) != 0 ? Color.m3751getGreenimpl(r5) : 0.0f, (r12 & 8) != 0 ? Color.m3749getBlueimpl(MaterialTheme.INSTANCE.getColors($composer, 6).m1285getOnSurface0d7_KjU()) : 0.0f);
            backgroundColor2 = ColorKt.m3791compositeOverOWjLjI(m3744copywmQWz5c8, MaterialTheme.INSTANCE.getColors($composer, 6).m1290getSurface0d7_KjU());
        } else {
            backgroundColor2 = backgroundColor;
        }
        long contentColor2 = (i & 2) != 0 ? Color.m3744copywmQWz5c(r7, (r12 & 1) != 0 ? Color.m3748getAlphaimpl(r7) : 0.87f, (r12 & 2) != 0 ? Color.m3752getRedimpl(r7) : 0.0f, (r12 & 4) != 0 ? Color.m3751getGreenimpl(r7) : 0.0f, (r12 & 8) != 0 ? Color.m3749getBlueimpl(MaterialTheme.INSTANCE.getColors($composer, 6).m1285getOnSurface0d7_KjU()) : 0.0f) : contentColor;
        if ((i & 4) != 0) {
            m3744copywmQWz5c7 = Color.m3744copywmQWz5c(r9, (r12 & 1) != 0 ? Color.m3748getAlphaimpl(r9) : 0.54f, (r12 & 2) != 0 ? Color.m3752getRedimpl(r9) : 0.0f, (r12 & 4) != 0 ? Color.m3751getGreenimpl(r9) : 0.0f, (r12 & 8) != 0 ? Color.m3749getBlueimpl(contentColor2) : 0.0f);
            leadingIconColor2 = m3744copywmQWz5c7;
        } else {
            leadingIconColor2 = leadingIconColor;
        }
        if ((i & 8) != 0) {
            m3744copywmQWz5c6 = Color.m3744copywmQWz5c(r16, (r12 & 1) != 0 ? Color.m3748getAlphaimpl(r16) : ContentAlpha.INSTANCE.getDisabled($composer, 6) * 0.12f, (r12 & 2) != 0 ? Color.m3752getRedimpl(r16) : 0.0f, (r12 & 4) != 0 ? Color.m3751getGreenimpl(r16) : 0.0f, (r12 & 8) != 0 ? Color.m3749getBlueimpl(MaterialTheme.INSTANCE.getColors($composer, 6).m1285getOnSurface0d7_KjU()) : 0.0f);
            disabledBackgroundColor2 = ColorKt.m3791compositeOverOWjLjI(m3744copywmQWz5c6, MaterialTheme.INSTANCE.getColors($composer, 6).m1290getSurface0d7_KjU());
        } else {
            disabledBackgroundColor2 = disabledBackgroundColor;
        }
        if ((i & 16) != 0) {
            m3744copywmQWz5c5 = Color.m3744copywmQWz5c(r42, (r12 & 1) != 0 ? Color.m3748getAlphaimpl(r42) : ContentAlpha.INSTANCE.getDisabled($composer, 6) * 0.87f, (r12 & 2) != 0 ? Color.m3752getRedimpl(r42) : 0.0f, (r12 & 4) != 0 ? Color.m3751getGreenimpl(r42) : 0.0f, (r12 & 8) != 0 ? Color.m3749getBlueimpl(contentColor2) : 0.0f);
            disabledContentColor2 = m3744copywmQWz5c5;
        } else {
            disabledContentColor2 = disabledContentColor;
        }
        if ((i & 32) != 0) {
            m3744copywmQWz5c4 = Color.m3744copywmQWz5c(r42, (r12 & 1) != 0 ? Color.m3748getAlphaimpl(r42) : ContentAlpha.INSTANCE.getDisabled($composer, 6) * 0.54f, (r12 & 2) != 0 ? Color.m3752getRedimpl(r42) : 0.0f, (r12 & 4) != 0 ? Color.m3751getGreenimpl(r42) : 0.0f, (r12 & 8) != 0 ? Color.m3749getBlueimpl(leadingIconColor2) : 0.0f);
            disabledLeadingIconColor2 = m3744copywmQWz5c4;
        } else {
            disabledLeadingIconColor2 = disabledLeadingIconColor;
        }
        if ((i & 64) != 0) {
            m3744copywmQWz5c3 = Color.m3744copywmQWz5c(r9, (r12 & 1) != 0 ? Color.m3748getAlphaimpl(r9) : 0.12f, (r12 & 2) != 0 ? Color.m3752getRedimpl(r9) : 0.0f, (r12 & 4) != 0 ? Color.m3751getGreenimpl(r9) : 0.0f, (r12 & 8) != 0 ? Color.m3749getBlueimpl(MaterialTheme.INSTANCE.getColors($composer, 6).m1285getOnSurface0d7_KjU()) : 0.0f);
            selectedBackgroundColor2 = ColorKt.m3791compositeOverOWjLjI(m3744copywmQWz5c3, backgroundColor2);
        } else {
            selectedBackgroundColor2 = selectedBackgroundColor;
        }
        if ((i & 128) != 0) {
            m3744copywmQWz5c2 = Color.m3744copywmQWz5c(r9, (r12 & 1) != 0 ? Color.m3748getAlphaimpl(r9) : 0.16f, (r12 & 2) != 0 ? Color.m3752getRedimpl(r9) : 0.0f, (r12 & 4) != 0 ? Color.m3751getGreenimpl(r9) : 0.0f, (r12 & 8) != 0 ? Color.m3749getBlueimpl(MaterialTheme.INSTANCE.getColors($composer, 6).m1285getOnSurface0d7_KjU()) : 0.0f);
            selectedContentColor2 = ColorKt.m3791compositeOverOWjLjI(m3744copywmQWz5c2, contentColor2);
        } else {
            selectedContentColor2 = selectedContentColor;
        }
        if ((i & 256) != 0) {
            m3744copywmQWz5c = Color.m3744copywmQWz5c(r3, (r12 & 1) != 0 ? Color.m3748getAlphaimpl(r3) : 0.16f, (r12 & 2) != 0 ? Color.m3752getRedimpl(r3) : 0.0f, (r12 & 4) != 0 ? Color.m3751getGreenimpl(r3) : 0.0f, (r12 & 8) != 0 ? Color.m3749getBlueimpl(MaterialTheme.INSTANCE.getColors($composer, 6).m1285getOnSurface0d7_KjU()) : 0.0f);
            selectedLeadingIconColor2 = ColorKt.m3791compositeOverOWjLjI(m3744copywmQWz5c, leadingIconColor2);
        } else {
            selectedLeadingIconColor2 = selectedLeadingIconColor;
        }
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventStart(830140629, $changed, -1, "androidx.compose.material.ChipDefaults.filterChipColors (Chip.kt:485)");
        }
        long j = leadingIconColor2;
        long leadingIconColor3 = disabledBackgroundColor2;
        DefaultSelectableChipColors defaultSelectableChipColors = new DefaultSelectableChipColors(backgroundColor2, contentColor2, j, leadingIconColor3, disabledContentColor2, disabledLeadingIconColor2, selectedBackgroundColor2, selectedContentColor2, selectedLeadingIconColor2, null);
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventEnd();
        }
        $composer.endReplaceableGroup();
        return defaultSelectableChipColors;
    }

    /* renamed from: outlinedFilterChipColors-J08w3-E, reason: not valid java name */
    public final SelectableChipColors m1276outlinedFilterChipColorsJ08w3E(long backgroundColor, long contentColor, long leadingIconColor, long disabledBackgroundColor, long disabledContentColor, long disabledLeadingIconColor, long selectedBackgroundColor, long selectedContentColor, long selectedLeadingIconColor, Composer $composer, int $changed, int i) {
        long leadingIconColor2;
        long disabledContentColor2;
        long disabledLeadingIconColor2;
        long selectedBackgroundColor2;
        long selectedContentColor2;
        long selectedLeadingIconColor2;
        long m3744copywmQWz5c;
        long m3744copywmQWz5c2;
        long m3744copywmQWz5c3;
        long m3744copywmQWz5c4;
        long m3744copywmQWz5c5;
        long m3744copywmQWz5c6;
        $composer.startReplaceableGroup(346878099);
        ComposerKt.sourceInformation($composer, "C(outlinedFilterChipColors)P(0:c#ui.graphics.Color,1:c#ui.graphics.Color,5:c#ui.graphics.Color,2:c#ui.graphics.Color,3:c#ui.graphics.Color,4:c#ui.graphics.Color,6:c#ui.graphics.Color,7:c#ui.graphics.Color,8:c#ui.graphics.Color)513@23845L6,514@23905L6,518@24165L8,521@24300L8,523@24396L6,526@24556L6,529@24717L6:Chip.kt#jmzs0o");
        long backgroundColor2 = (i & 1) != 0 ? MaterialTheme.INSTANCE.getColors($composer, 6).m1290getSurface0d7_KjU() : backgroundColor;
        long contentColor2 = (i & 2) != 0 ? Color.m3744copywmQWz5c(r7, (r12 & 1) != 0 ? Color.m3748getAlphaimpl(r7) : 0.87f, (r12 & 2) != 0 ? Color.m3752getRedimpl(r7) : 0.0f, (r12 & 4) != 0 ? Color.m3751getGreenimpl(r7) : 0.0f, (r12 & 8) != 0 ? Color.m3749getBlueimpl(MaterialTheme.INSTANCE.getColors($composer, 6).m1285getOnSurface0d7_KjU()) : 0.0f) : contentColor;
        if ((i & 4) != 0) {
            m3744copywmQWz5c6 = Color.m3744copywmQWz5c(r9, (r12 & 1) != 0 ? Color.m3748getAlphaimpl(r9) : 0.54f, (r12 & 2) != 0 ? Color.m3752getRedimpl(r9) : 0.0f, (r12 & 4) != 0 ? Color.m3751getGreenimpl(r9) : 0.0f, (r12 & 8) != 0 ? Color.m3749getBlueimpl(contentColor2) : 0.0f);
            leadingIconColor2 = m3744copywmQWz5c6;
        } else {
            leadingIconColor2 = leadingIconColor;
        }
        long disabledBackgroundColor2 = (i & 8) != 0 ? backgroundColor2 : disabledBackgroundColor;
        if ((i & 16) != 0) {
            m3744copywmQWz5c5 = Color.m3744copywmQWz5c(r42, (r12 & 1) != 0 ? Color.m3748getAlphaimpl(r42) : ContentAlpha.INSTANCE.getDisabled($composer, 6) * 0.87f, (r12 & 2) != 0 ? Color.m3752getRedimpl(r42) : 0.0f, (r12 & 4) != 0 ? Color.m3751getGreenimpl(r42) : 0.0f, (r12 & 8) != 0 ? Color.m3749getBlueimpl(contentColor2) : 0.0f);
            disabledContentColor2 = m3744copywmQWz5c5;
        } else {
            disabledContentColor2 = disabledContentColor;
        }
        if ((i & 32) != 0) {
            m3744copywmQWz5c4 = Color.m3744copywmQWz5c(r42, (r12 & 1) != 0 ? Color.m3748getAlphaimpl(r42) : ContentAlpha.INSTANCE.getDisabled($composer, 6) * 0.54f, (r12 & 2) != 0 ? Color.m3752getRedimpl(r42) : 0.0f, (r12 & 4) != 0 ? Color.m3751getGreenimpl(r42) : 0.0f, (r12 & 8) != 0 ? Color.m3749getBlueimpl(leadingIconColor2) : 0.0f);
            disabledLeadingIconColor2 = m3744copywmQWz5c4;
        } else {
            disabledLeadingIconColor2 = disabledLeadingIconColor;
        }
        if ((i & 64) != 0) {
            m3744copywmQWz5c3 = Color.m3744copywmQWz5c(r9, (r12 & 1) != 0 ? Color.m3748getAlphaimpl(r9) : 0.16f, (r12 & 2) != 0 ? Color.m3752getRedimpl(r9) : 0.0f, (r12 & 4) != 0 ? Color.m3751getGreenimpl(r9) : 0.0f, (r12 & 8) != 0 ? Color.m3749getBlueimpl(MaterialTheme.INSTANCE.getColors($composer, 6).m1285getOnSurface0d7_KjU()) : 0.0f);
            selectedBackgroundColor2 = ColorKt.m3791compositeOverOWjLjI(m3744copywmQWz5c3, backgroundColor2);
        } else {
            selectedBackgroundColor2 = selectedBackgroundColor;
        }
        if ((i & 128) != 0) {
            m3744copywmQWz5c2 = Color.m3744copywmQWz5c(r9, (r12 & 1) != 0 ? Color.m3748getAlphaimpl(r9) : 0.16f, (r12 & 2) != 0 ? Color.m3752getRedimpl(r9) : 0.0f, (r12 & 4) != 0 ? Color.m3751getGreenimpl(r9) : 0.0f, (r12 & 8) != 0 ? Color.m3749getBlueimpl(MaterialTheme.INSTANCE.getColors($composer, 6).m1285getOnSurface0d7_KjU()) : 0.0f);
            selectedContentColor2 = ColorKt.m3791compositeOverOWjLjI(m3744copywmQWz5c2, contentColor2);
        } else {
            selectedContentColor2 = selectedContentColor;
        }
        if ((i & 256) != 0) {
            m3744copywmQWz5c = Color.m3744copywmQWz5c(r3, (r12 & 1) != 0 ? Color.m3748getAlphaimpl(r3) : 0.16f, (r12 & 2) != 0 ? Color.m3752getRedimpl(r3) : 0.0f, (r12 & 4) != 0 ? Color.m3751getGreenimpl(r3) : 0.0f, (r12 & 8) != 0 ? Color.m3749getBlueimpl(MaterialTheme.INSTANCE.getColors($composer, 6).m1285getOnSurface0d7_KjU()) : 0.0f);
            selectedLeadingIconColor2 = ColorKt.m3791compositeOverOWjLjI(m3744copywmQWz5c, leadingIconColor2);
        } else {
            selectedLeadingIconColor2 = selectedLeadingIconColor;
        }
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventStart(346878099, $changed, -1, "androidx.compose.material.ChipDefaults.outlinedFilterChipColors (Chip.kt:532)");
        }
        long j = leadingIconColor2;
        long leadingIconColor3 = disabledBackgroundColor2;
        DefaultSelectableChipColors defaultSelectableChipColors = new DefaultSelectableChipColors(backgroundColor2, contentColor2, j, leadingIconColor3, disabledContentColor2, disabledLeadingIconColor2, selectedBackgroundColor2, selectedContentColor2, selectedLeadingIconColor2, null);
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventEnd();
        }
        $composer.endReplaceableGroup();
        return defaultSelectableChipColors;
    }

    public final BorderStroke getOutlinedBorder(Composer $composer, int $changed) {
        long m3744copywmQWz5c;
        $composer.startReplaceableGroup(-1650225597);
        ComposerKt.sourceInformation($composer, "C550@25564L6:Chip.kt#jmzs0o");
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventStart(-1650225597, $changed, -1, "androidx.compose.material.ChipDefaults.<get-outlinedBorder> (Chip.kt:549)");
        }
        float f = OutlinedBorderSize;
        m3744copywmQWz5c = Color.m3744copywmQWz5c(r2, (r12 & 1) != 0 ? Color.m3748getAlphaimpl(r2) : 0.12f, (r12 & 2) != 0 ? Color.m3752getRedimpl(r2) : 0.0f, (r12 & 4) != 0 ? Color.m3751getGreenimpl(r2) : 0.0f, (r12 & 8) != 0 ? Color.m3749getBlueimpl(MaterialTheme.INSTANCE.getColors($composer, 6).m1285getOnSurface0d7_KjU()) : 0.0f);
        BorderStroke m237BorderStrokecXLIe8U = BorderStrokeKt.m237BorderStrokecXLIe8U(f, m3744copywmQWz5c);
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventEnd();
        }
        $composer.endReplaceableGroup();
        return m237BorderStrokecXLIe8U;
    }

    /* renamed from: getOutlinedBorderSize-D9Ej5fM, reason: not valid java name */
    public final float m1273getOutlinedBorderSizeD9Ej5fM() {
        return OutlinedBorderSize;
    }

    /* renamed from: getLeadingIconSize-D9Ej5fM, reason: not valid java name */
    public final float m1271getLeadingIconSizeD9Ej5fM() {
        return LeadingIconSize;
    }

    /* renamed from: getSelectedIconSize-D9Ej5fM, reason: not valid java name */
    public final float m1274getSelectedIconSizeD9Ej5fM() {
        return SelectedIconSize;
    }
}
