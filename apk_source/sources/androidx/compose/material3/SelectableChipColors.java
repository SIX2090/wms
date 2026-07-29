package androidx.compose.material3;

import androidx.compose.runtime.Composer;
import androidx.compose.runtime.ComposerKt;
import androidx.compose.runtime.SnapshotStateKt;
import androidx.compose.runtime.State;
import androidx.compose.ui.graphics.Color;
import kotlin.Metadata;
import kotlin.jvm.internal.DefaultConstructorMarker;

/* compiled from: Chip.kt */
@Metadata(d1 = {"\u0000(\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u000e\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010\u000b\n\u0002\b\t\n\u0002\u0010\b\n\u0002\b\u0007\b\u0007\u0018\u00002\u00020\u0001Bm\u0012\u0006\u0010\u0002\u001a\u00020\u0003\u0012\u0006\u0010\u0004\u001a\u00020\u0003\u0012\u0006\u0010\u0005\u001a\u00020\u0003\u0012\u0006\u0010\u0006\u001a\u00020\u0003\u0012\u0006\u0010\u0007\u001a\u00020\u0003\u0012\u0006\u0010\b\u001a\u00020\u0003\u0012\u0006\u0010\t\u001a\u00020\u0003\u0012\u0006\u0010\n\u001a\u00020\u0003\u0012\u0006\u0010\u000b\u001a\u00020\u0003\u0012\u0006\u0010\f\u001a\u00020\u0003\u0012\u0006\u0010\r\u001a\u00020\u0003\u0012\u0006\u0010\u000e\u001a\u00020\u0003\u0012\u0006\u0010\u000f\u001a\u00020\u0003¢\u0006\u0002\u0010\u0010J%\u0010\u0002\u001a\b\u0012\u0004\u0012\u00020\u00030\u00122\u0006\u0010\u0013\u001a\u00020\u00142\u0006\u0010\u0015\u001a\u00020\u0014H\u0001¢\u0006\u0004\b\u0016\u0010\u0017J\u0092\u0001\u0010\u0018\u001a\u00020\u00002\b\b\u0002\u0010\u0002\u001a\u00020\u00032\b\b\u0002\u0010\u0004\u001a\u00020\u00032\b\b\u0002\u0010\u0005\u001a\u00020\u00032\b\b\u0002\u0010\u0006\u001a\u00020\u00032\b\b\u0002\u0010\u0007\u001a\u00020\u00032\b\b\u0002\u0010\b\u001a\u00020\u00032\b\b\u0002\u0010\t\u001a\u00020\u00032\b\b\u0002\u0010\n\u001a\u00020\u00032\b\b\u0002\u0010\u000b\u001a\u00020\u00032\b\b\u0002\u0010\f\u001a\u00020\u00032\b\b\u0002\u0010\r\u001a\u00020\u00032\b\b\u0002\u0010\u000e\u001a\u00020\u00032\b\b\u0002\u0010\u000f\u001a\u00020\u0003ø\u0001\u0000¢\u0006\u0004\b\u0019\u0010\u001aJ\u0013\u0010\u001b\u001a\u00020\u00142\b\u0010\u001c\u001a\u0004\u0018\u00010\u0001H\u0096\u0002J\b\u0010\u001d\u001a\u00020\u001eH\u0016J%\u0010\u0004\u001a\u00020\u00032\u0006\u0010\u0013\u001a\u00020\u00142\u0006\u0010\u0015\u001a\u00020\u0014H\u0000ø\u0001\u0001ø\u0001\u0000¢\u0006\u0004\b\u001f\u0010 J%\u0010!\u001a\u00020\u00032\u0006\u0010\u0013\u001a\u00020\u00142\u0006\u0010\u0015\u001a\u00020\u0014H\u0000ø\u0001\u0001ø\u0001\u0000¢\u0006\u0004\b\"\u0010 J%\u0010#\u001a\u00020\u00032\u0006\u0010\u0013\u001a\u00020\u00142\u0006\u0010\u0015\u001a\u00020\u0014H\u0000ø\u0001\u0001ø\u0001\u0000¢\u0006\u0004\b$\u0010 R\u0016\u0010\u0002\u001a\u00020\u0003X\u0082\u0004ø\u0001\u0000ø\u0001\u0001¢\u0006\u0004\n\u0002\u0010\u0011R\u0016\u0010\u0007\u001a\u00020\u0003X\u0082\u0004ø\u0001\u0000ø\u0001\u0001¢\u0006\u0004\n\u0002\u0010\u0011R\u0016\u0010\b\u001a\u00020\u0003X\u0082\u0004ø\u0001\u0000ø\u0001\u0001¢\u0006\u0004\n\u0002\u0010\u0011R\u0016\u0010\t\u001a\u00020\u0003X\u0082\u0004ø\u0001\u0000ø\u0001\u0001¢\u0006\u0004\n\u0002\u0010\u0011R\u0016\u0010\f\u001a\u00020\u0003X\u0082\u0004ø\u0001\u0000ø\u0001\u0001¢\u0006\u0004\n\u0002\u0010\u0011R\u0016\u0010\n\u001a\u00020\u0003X\u0082\u0004ø\u0001\u0000ø\u0001\u0001¢\u0006\u0004\n\u0002\u0010\u0011R\u0016\u0010\u0004\u001a\u00020\u0003X\u0082\u0004ø\u0001\u0000ø\u0001\u0001¢\u0006\u0004\n\u0002\u0010\u0011R\u0016\u0010\u0005\u001a\u00020\u0003X\u0082\u0004ø\u0001\u0000ø\u0001\u0001¢\u0006\u0004\n\u0002\u0010\u0011R\u0016\u0010\u000b\u001a\u00020\u0003X\u0082\u0004ø\u0001\u0000ø\u0001\u0001¢\u0006\u0004\n\u0002\u0010\u0011R\u0016\u0010\r\u001a\u00020\u0003X\u0082\u0004ø\u0001\u0000ø\u0001\u0001¢\u0006\u0004\n\u0002\u0010\u0011R\u0016\u0010\u000e\u001a\u00020\u0003X\u0082\u0004ø\u0001\u0000ø\u0001\u0001¢\u0006\u0004\n\u0002\u0010\u0011R\u0016\u0010\u000f\u001a\u00020\u0003X\u0082\u0004ø\u0001\u0000ø\u0001\u0001¢\u0006\u0004\n\u0002\u0010\u0011R\u0016\u0010\u0006\u001a\u00020\u0003X\u0082\u0004ø\u0001\u0000ø\u0001\u0001¢\u0006\u0004\n\u0002\u0010\u0011\u0082\u0002\u000b\n\u0005\b¡\u001e0\u0001\n\u0002\b!¨\u0006%"}, d2 = {"Landroidx/compose/material3/SelectableChipColors;", "", "containerColor", "Landroidx/compose/ui/graphics/Color;", "labelColor", "leadingIconColor", "trailingIconColor", "disabledContainerColor", "disabledLabelColor", "disabledLeadingIconColor", "disabledTrailingIconColor", "selectedContainerColor", "disabledSelectedContainerColor", "selectedLabelColor", "selectedLeadingIconColor", "selectedTrailingIconColor", "(JJJJJJJJJJJJJLkotlin/jvm/internal/DefaultConstructorMarker;)V", "J", "Landroidx/compose/runtime/State;", "enabled", "", "selected", "containerColor$material3_release", "(ZZLandroidx/compose/runtime/Composer;I)Landroidx/compose/runtime/State;", "copy", "copy-daRQuJA", "(JJJJJJJJJJJJJ)Landroidx/compose/material3/SelectableChipColors;", "equals", "other", "hashCode", "", "labelColor-WaAFU9c$material3_release", "(ZZ)J", "leadingIconContentColor", "leadingIconContentColor-WaAFU9c$material3_release", "trailingIconContentColor", "trailingIconContentColor-WaAFU9c$material3_release", "material3_release"}, k = 1, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class SelectableChipColors {
    public static final int $stable = 0;
    private final long containerColor;
    private final long disabledContainerColor;
    private final long disabledLabelColor;
    private final long disabledLeadingIconColor;
    private final long disabledSelectedContainerColor;
    private final long disabledTrailingIconColor;
    private final long labelColor;
    private final long leadingIconColor;
    private final long selectedContainerColor;
    private final long selectedLabelColor;
    private final long selectedLeadingIconColor;
    private final long selectedTrailingIconColor;
    private final long trailingIconColor;

    public /* synthetic */ SelectableChipColors(long j, long j2, long j3, long j4, long j5, long j6, long j7, long j8, long j9, long j10, long j11, long j12, long j13, DefaultConstructorMarker defaultConstructorMarker) {
        this(j, j2, j3, j4, j5, j6, j7, j8, j9, j10, j11, j12, j13);
    }

    private SelectableChipColors(long containerColor, long labelColor, long leadingIconColor, long trailingIconColor, long disabledContainerColor, long disabledLabelColor, long disabledLeadingIconColor, long disabledTrailingIconColor, long selectedContainerColor, long disabledSelectedContainerColor, long selectedLabelColor, long selectedLeadingIconColor, long selectedTrailingIconColor) {
        this.containerColor = containerColor;
        this.labelColor = labelColor;
        this.leadingIconColor = leadingIconColor;
        this.trailingIconColor = trailingIconColor;
        this.disabledContainerColor = disabledContainerColor;
        this.disabledLabelColor = disabledLabelColor;
        this.disabledLeadingIconColor = disabledLeadingIconColor;
        this.disabledTrailingIconColor = disabledTrailingIconColor;
        this.selectedContainerColor = selectedContainerColor;
        this.disabledSelectedContainerColor = disabledSelectedContainerColor;
        this.selectedLabelColor = selectedLabelColor;
        this.selectedLeadingIconColor = selectedLeadingIconColor;
        this.selectedTrailingIconColor = selectedTrailingIconColor;
    }

    /* renamed from: copy-daRQuJA$default, reason: not valid java name */
    public static /* synthetic */ SelectableChipColors m2167copydaRQuJA$default(SelectableChipColors selectableChipColors, long j, long j2, long j3, long j4, long j5, long j6, long j7, long j8, long j9, long j10, long j11, long j12, long j13, int i, Object obj) {
        long j14;
        long j15;
        long j16 = (i & 1) != 0 ? selectableChipColors.containerColor : j;
        long j17 = (i & 2) != 0 ? selectableChipColors.labelColor : j2;
        long j18 = (i & 4) != 0 ? selectableChipColors.leadingIconColor : j3;
        long j19 = (i & 8) != 0 ? selectableChipColors.trailingIconColor : j4;
        long j20 = (i & 16) != 0 ? selectableChipColors.disabledContainerColor : j5;
        long j21 = (i & 32) != 0 ? selectableChipColors.disabledLabelColor : j6;
        long j22 = (i & 64) != 0 ? selectableChipColors.disabledLeadingIconColor : j7;
        long j23 = (i & 128) != 0 ? selectableChipColors.disabledTrailingIconColor : j8;
        long j24 = (i & 256) != 0 ? selectableChipColors.selectedContainerColor : j9;
        long j25 = (i & 512) != 0 ? selectableChipColors.disabledSelectedContainerColor : j10;
        long j26 = (i & 1024) != 0 ? selectableChipColors.selectedLabelColor : j11;
        long j27 = (i & 2048) != 0 ? selectableChipColors.selectedLeadingIconColor : j12;
        if ((i & 4096) != 0) {
            j14 = j27;
            j15 = selectableChipColors.selectedTrailingIconColor;
        } else {
            j14 = j27;
            j15 = j13;
        }
        return selectableChipColors.m2168copydaRQuJA(j16, j17, j18, j19, j20, j21, j22, j23, j24, j25, j26, j14, j15);
    }

    /* renamed from: copy-daRQuJA, reason: not valid java name */
    public final SelectableChipColors m2168copydaRQuJA(long containerColor, long labelColor, long leadingIconColor, long trailingIconColor, long disabledContainerColor, long disabledLabelColor, long disabledLeadingIconColor, long disabledTrailingIconColor, long selectedContainerColor, long disabledSelectedContainerColor, long selectedLabelColor, long selectedLeadingIconColor, long selectedTrailingIconColor) {
        return new SelectableChipColors((containerColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (containerColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? containerColor : this.containerColor, (labelColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (labelColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? labelColor : this.labelColor, (leadingIconColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (leadingIconColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? leadingIconColor : this.leadingIconColor, (trailingIconColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (trailingIconColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? trailingIconColor : this.trailingIconColor, (disabledContainerColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (disabledContainerColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? disabledContainerColor : this.disabledContainerColor, (disabledLabelColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (disabledLabelColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? disabledLabelColor : this.disabledLabelColor, (disabledLeadingIconColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (disabledLeadingIconColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? disabledLeadingIconColor : this.disabledLeadingIconColor, (disabledTrailingIconColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (disabledTrailingIconColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? disabledTrailingIconColor : this.disabledTrailingIconColor, (selectedContainerColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (selectedContainerColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? selectedContainerColor : this.selectedContainerColor, (disabledSelectedContainerColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (disabledSelectedContainerColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? disabledSelectedContainerColor : this.disabledSelectedContainerColor, (selectedLabelColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (selectedLabelColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? selectedLabelColor : this.selectedLabelColor, (selectedLeadingIconColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (selectedLeadingIconColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? selectedLeadingIconColor : this.selectedLeadingIconColor, selectedTrailingIconColor != Color.INSTANCE.m3782getUnspecified0d7_KjU() ? selectedTrailingIconColor : this.selectedTrailingIconColor, null);
    }

    public final State<Color> containerColor$material3_release(boolean enabled, boolean selected, Composer $composer, int $changed) {
        long target;
        $composer.startReplaceableGroup(-2126903408);
        ComposerKt.sourceInformation($composer, "C(containerColor)2572@121754L28:Chip.kt#uh7d8r");
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventStart(-2126903408, $changed, -1, "androidx.compose.material3.SelectableChipColors.containerColor (Chip.kt:2566)");
        }
        if (enabled) {
            target = !selected ? this.containerColor : this.selectedContainerColor;
        } else {
            target = selected ? this.disabledSelectedContainerColor : this.disabledContainerColor;
        }
        State<Color> rememberUpdatedState = SnapshotStateKt.rememberUpdatedState(Color.m3736boximpl(target), $composer, 0);
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventEnd();
        }
        $composer.endReplaceableGroup();
        return rememberUpdatedState;
    }

    /* renamed from: labelColor-WaAFU9c$material3_release, reason: not valid java name */
    public final long m2169labelColorWaAFU9c$material3_release(boolean enabled, boolean selected) {
        return !enabled ? this.disabledLabelColor : !selected ? this.labelColor : this.selectedLabelColor;
    }

    /* renamed from: leadingIconContentColor-WaAFU9c$material3_release, reason: not valid java name */
    public final long m2170leadingIconContentColorWaAFU9c$material3_release(boolean enabled, boolean selected) {
        return !enabled ? this.disabledLeadingIconColor : !selected ? this.leadingIconColor : this.selectedLeadingIconColor;
    }

    /* renamed from: trailingIconContentColor-WaAFU9c$material3_release, reason: not valid java name */
    public final long m2171trailingIconContentColorWaAFU9c$material3_release(boolean enabled, boolean selected) {
        return !enabled ? this.disabledTrailingIconColor : !selected ? this.trailingIconColor : this.selectedTrailingIconColor;
    }

    public boolean equals(Object other) {
        if (this == other) {
            return true;
        }
        if (other != null && (other instanceof SelectableChipColors) && Color.m3747equalsimpl0(this.containerColor, ((SelectableChipColors) other).containerColor) && Color.m3747equalsimpl0(this.labelColor, ((SelectableChipColors) other).labelColor) && Color.m3747equalsimpl0(this.leadingIconColor, ((SelectableChipColors) other).leadingIconColor) && Color.m3747equalsimpl0(this.trailingIconColor, ((SelectableChipColors) other).trailingIconColor) && Color.m3747equalsimpl0(this.disabledContainerColor, ((SelectableChipColors) other).disabledContainerColor) && Color.m3747equalsimpl0(this.disabledLabelColor, ((SelectableChipColors) other).disabledLabelColor) && Color.m3747equalsimpl0(this.disabledLeadingIconColor, ((SelectableChipColors) other).disabledLeadingIconColor) && Color.m3747equalsimpl0(this.disabledTrailingIconColor, ((SelectableChipColors) other).disabledTrailingIconColor) && Color.m3747equalsimpl0(this.selectedContainerColor, ((SelectableChipColors) other).selectedContainerColor) && Color.m3747equalsimpl0(this.disabledSelectedContainerColor, ((SelectableChipColors) other).disabledSelectedContainerColor) && Color.m3747equalsimpl0(this.selectedLabelColor, ((SelectableChipColors) other).selectedLabelColor) && Color.m3747equalsimpl0(this.selectedLeadingIconColor, ((SelectableChipColors) other).selectedLeadingIconColor) && Color.m3747equalsimpl0(this.selectedTrailingIconColor, ((SelectableChipColors) other).selectedTrailingIconColor)) {
            return true;
        }
        return false;
    }

    public int hashCode() {
        int result = Color.m3753hashCodeimpl(this.containerColor);
        return (((((((((((((((((((((((result * 31) + Color.m3753hashCodeimpl(this.labelColor)) * 31) + Color.m3753hashCodeimpl(this.leadingIconColor)) * 31) + Color.m3753hashCodeimpl(this.trailingIconColor)) * 31) + Color.m3753hashCodeimpl(this.disabledContainerColor)) * 31) + Color.m3753hashCodeimpl(this.disabledLabelColor)) * 31) + Color.m3753hashCodeimpl(this.disabledLeadingIconColor)) * 31) + Color.m3753hashCodeimpl(this.disabledTrailingIconColor)) * 31) + Color.m3753hashCodeimpl(this.selectedContainerColor)) * 31) + Color.m3753hashCodeimpl(this.disabledSelectedContainerColor)) * 31) + Color.m3753hashCodeimpl(this.selectedLabelColor)) * 31) + Color.m3753hashCodeimpl(this.selectedLeadingIconColor)) * 31) + Color.m3753hashCodeimpl(this.selectedTrailingIconColor);
    }
}
