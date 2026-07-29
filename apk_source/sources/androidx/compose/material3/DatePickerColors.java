package androidx.compose.material3;

import androidx.compose.animation.SingleValueAnimationKt;
import androidx.compose.animation.core.AnimationSpecKt;
import androidx.compose.runtime.Composer;
import androidx.compose.runtime.ComposerKt;
import androidx.compose.runtime.SnapshotStateKt;
import androidx.compose.runtime.State;
import androidx.compose.ui.graphics.Color;
import kotlin.Metadata;
import kotlin.jvm.functions.Function0;
import kotlin.jvm.internal.DefaultConstructorMarker;

/* compiled from: DatePicker.kt */
@Metadata(d1 = {"\u00008\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0018\n\u0002\u0018\u0002\n\u0002\b!\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010\u000b\n\u0002\b\u000b\n\u0002\u0010\b\n\u0002\b\u0007\n\u0002\u0018\u0002\n\u0002\b\u0002\b\u0007\u0018\u00002\u00020\u0001BÍ\u0001\u0012\u0006\u0010\u0002\u001a\u00020\u0003\u0012\u0006\u0010\u0004\u001a\u00020\u0003\u0012\u0006\u0010\u0005\u001a\u00020\u0003\u0012\u0006\u0010\u0006\u001a\u00020\u0003\u0012\u0006\u0010\u0007\u001a\u00020\u0003\u0012\u0006\u0010\b\u001a\u00020\u0003\u0012\u0006\u0010\t\u001a\u00020\u0003\u0012\u0006\u0010\n\u001a\u00020\u0003\u0012\u0006\u0010\u000b\u001a\u00020\u0003\u0012\u0006\u0010\f\u001a\u00020\u0003\u0012\u0006\u0010\r\u001a\u00020\u0003\u0012\u0006\u0010\u000e\u001a\u00020\u0003\u0012\u0006\u0010\u000f\u001a\u00020\u0003\u0012\u0006\u0010\u0010\u001a\u00020\u0003\u0012\u0006\u0010\u0011\u001a\u00020\u0003\u0012\u0006\u0010\u0012\u001a\u00020\u0003\u0012\u0006\u0010\u0013\u001a\u00020\u0003\u0012\u0006\u0010\u0014\u001a\u00020\u0003\u0012\u0006\u0010\u0015\u001a\u00020\u0003\u0012\u0006\u0010\u0016\u001a\u00020\u0003\u0012\u0006\u0010\u0017\u001a\u00020\u0003\u0012\u0006\u0010\u0018\u001a\u00020\u0003\u0012\u0006\u0010\u0019\u001a\u00020\u0003\u0012\u0006\u0010\u001a\u001a\u00020\u0003\u0012\u0006\u0010\u001b\u001a\u00020\u001c¢\u0006\u0002\u0010\u001dJ\u008c\u0002\u0010:\u001a\u00020\u00002\b\b\u0002\u0010\u0002\u001a\u00020\u00032\b\b\u0002\u0010\u0004\u001a\u00020\u00032\b\b\u0002\u0010\u0005\u001a\u00020\u00032\b\b\u0002\u0010\u0006\u001a\u00020\u00032\b\b\u0002\u0010\u0007\u001a\u00020\u00032\b\b\u0002\u0010\b\u001a\u00020\u00032\b\b\u0002\u0010\t\u001a\u00020\u00032\b\b\u0002\u0010\n\u001a\u00020\u00032\b\b\u0002\u0010\u000b\u001a\u00020\u00032\b\b\u0002\u0010\f\u001a\u00020\u00032\b\b\u0002\u0010\r\u001a\u00020\u00032\b\b\u0002\u0010\u000e\u001a\u00020\u00032\b\b\u0002\u0010\u000f\u001a\u00020\u00032\b\b\u0002\u0010\u0010\u001a\u00020\u00032\b\b\u0002\u0010\u0011\u001a\u00020\u00032\b\b\u0002\u0010\u0012\u001a\u00020\u00032\b\b\u0002\u0010\u0013\u001a\u00020\u00032\b\b\u0002\u0010\u0014\u001a\u00020\u00032\b\b\u0002\u0010\u0015\u001a\u00020\u00032\b\b\u0002\u0010\u0016\u001a\u00020\u00032\b\b\u0002\u0010\u0017\u001a\u00020\u00032\b\b\u0002\u0010\u0018\u001a\u00020\u00032\b\b\u0002\u0010\u0019\u001a\u00020\u00032\b\b\u0002\u0010\u001a\u001a\u00020\u00032\n\b\u0002\u0010\u001b\u001a\u0004\u0018\u00010\u001cø\u0001\u0000¢\u0006\u0004\b;\u0010<J-\u0010=\u001a\b\u0012\u0004\u0012\u00020\u00030>2\u0006\u0010?\u001a\u00020@2\u0006\u0010A\u001a\u00020@2\u0006\u0010B\u001a\u00020@H\u0001¢\u0006\u0004\bC\u0010DJ5\u0010\u0010\u001a\b\u0012\u0004\u0012\u00020\u00030>2\u0006\u0010E\u001a\u00020@2\u0006\u0010?\u001a\u00020@2\u0006\u0010F\u001a\u00020@2\u0006\u0010A\u001a\u00020@H\u0001¢\u0006\u0004\bG\u0010HJ\u0013\u0010I\u001a\u00020@2\b\u0010J\u001a\u0004\u0018\u00010\u0001H\u0096\u0002J\b\u0010K\u001a\u00020LH\u0016J%\u0010M\u001a\b\u0012\u0004\u0012\u00020\u00030>2\u0006\u0010?\u001a\u00020@2\u0006\u0010A\u001a\u00020@H\u0001¢\u0006\u0004\bN\u0010OJ-\u0010\t\u001a\b\u0012\u0004\u0012\u00020\u00030>2\u0006\u0010P\u001a\u00020@2\u0006\u0010?\u001a\u00020@2\u0006\u0010A\u001a\u00020@H\u0001¢\u0006\u0004\bQ\u0010DJ!\u0010R\u001a\u00020\u001c*\u0004\u0018\u00010\u001c2\f\u0010S\u001a\b\u0012\u0004\u0012\u00020\u001c0TH\u0000¢\u0006\u0002\bUR\u0019\u0010\u0002\u001a\u00020\u0003ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u0010 \u001a\u0004\b\u001e\u0010\u001fR\u0019\u0010\u000b\u001a\u00020\u0003ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u0010 \u001a\u0004\b!\u0010\u001fR\u0011\u0010\u001b\u001a\u00020\u001c¢\u0006\b\n\u0000\u001a\u0004\b\"\u0010#R\u0019\u0010\u0010\u001a\u00020\u0003ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u0010 \u001a\u0004\b$\u0010\u001fR\u0019\u0010\u0018\u001a\u00020\u0003ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u0010 \u001a\u0004\b%\u0010\u001fR\u0019\u0010\u0019\u001a\u00020\u0003ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u0010 \u001a\u0004\b&\u0010\u001fR\u0019\u0010\u0011\u001a\u00020\u0003ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u0010 \u001a\u0004\b'\u0010\u001fR\u0019\u0010\u0015\u001a\u00020\u0003ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u0010 \u001a\u0004\b(\u0010\u001fR\u0019\u0010\u0013\u001a\u00020\u0003ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u0010 \u001a\u0004\b)\u0010\u001fR\u0019\u0010\u000f\u001a\u00020\u0003ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u0010 \u001a\u0004\b*\u0010\u001fR\u0019\u0010\r\u001a\u00020\u0003ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u0010 \u001a\u0004\b+\u0010\u001fR\u0019\u0010\n\u001a\u00020\u0003ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u0010 \u001a\u0004\b,\u0010\u001fR\u0019\u0010\u001a\u001a\u00020\u0003ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u0010 \u001a\u0004\b-\u0010\u001fR\u0019\u0010\u0005\u001a\u00020\u0003ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u0010 \u001a\u0004\b.\u0010\u001fR\u0019\u0010\b\u001a\u00020\u0003ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u0010 \u001a\u0004\b/\u0010\u001fR\u0019\u0010\u0014\u001a\u00020\u0003ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u0010 \u001a\u0004\b0\u0010\u001fR\u0019\u0010\u0012\u001a\u00020\u0003ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u0010 \u001a\u0004\b1\u0010\u001fR\u0019\u0010\u000e\u001a\u00020\u0003ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u0010 \u001a\u0004\b2\u0010\u001fR\u0019\u0010\f\u001a\u00020\u0003ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u0010 \u001a\u0004\b3\u0010\u001fR\u0019\u0010\u0007\u001a\u00020\u0003ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u0010 \u001a\u0004\b4\u0010\u001fR\u0019\u0010\u0004\u001a\u00020\u0003ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u0010 \u001a\u0004\b5\u0010\u001fR\u0019\u0010\u0016\u001a\u00020\u0003ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u0010 \u001a\u0004\b6\u0010\u001fR\u0019\u0010\u0017\u001a\u00020\u0003ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u0010 \u001a\u0004\b7\u0010\u001fR\u0019\u0010\u0006\u001a\u00020\u0003ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u0010 \u001a\u0004\b8\u0010\u001fR\u0019\u0010\t\u001a\u00020\u0003ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u0010 \u001a\u0004\b9\u0010\u001f\u0082\u0002\u000b\n\u0005\b¡\u001e0\u0001\n\u0002\b!¨\u0006V"}, d2 = {"Landroidx/compose/material3/DatePickerColors;", "", "containerColor", "Landroidx/compose/ui/graphics/Color;", "titleContentColor", "headlineContentColor", "weekdayContentColor", "subheadContentColor", "navigationContentColor", "yearContentColor", "disabledYearContentColor", "currentYearContentColor", "selectedYearContentColor", "disabledSelectedYearContentColor", "selectedYearContainerColor", "disabledSelectedYearContainerColor", "dayContentColor", "disabledDayContentColor", "selectedDayContentColor", "disabledSelectedDayContentColor", "selectedDayContainerColor", "disabledSelectedDayContainerColor", "todayContentColor", "todayDateBorderColor", "dayInSelectionRangeContainerColor", "dayInSelectionRangeContentColor", "dividerColor", "dateTextFieldColors", "Landroidx/compose/material3/TextFieldColors;", "(JJJJJJJJJJJJJJJJJJJJJJJJLandroidx/compose/material3/TextFieldColors;Lkotlin/jvm/internal/DefaultConstructorMarker;)V", "getContainerColor-0d7_KjU", "()J", "J", "getCurrentYearContentColor-0d7_KjU", "getDateTextFieldColors", "()Landroidx/compose/material3/TextFieldColors;", "getDayContentColor-0d7_KjU", "getDayInSelectionRangeContainerColor-0d7_KjU", "getDayInSelectionRangeContentColor-0d7_KjU", "getDisabledDayContentColor-0d7_KjU", "getDisabledSelectedDayContainerColor-0d7_KjU", "getDisabledSelectedDayContentColor-0d7_KjU", "getDisabledSelectedYearContainerColor-0d7_KjU", "getDisabledSelectedYearContentColor-0d7_KjU", "getDisabledYearContentColor-0d7_KjU", "getDividerColor-0d7_KjU", "getHeadlineContentColor-0d7_KjU", "getNavigationContentColor-0d7_KjU", "getSelectedDayContainerColor-0d7_KjU", "getSelectedDayContentColor-0d7_KjU", "getSelectedYearContainerColor-0d7_KjU", "getSelectedYearContentColor-0d7_KjU", "getSubheadContentColor-0d7_KjU", "getTitleContentColor-0d7_KjU", "getTodayContentColor-0d7_KjU", "getTodayDateBorderColor-0d7_KjU", "getWeekdayContentColor-0d7_KjU", "getYearContentColor-0d7_KjU", "copy", "copy-tNwlRmA", "(JJJJJJJJJJJJJJJJJJJJJJJJLandroidx/compose/material3/TextFieldColors;)Landroidx/compose/material3/DatePickerColors;", "dayContainerColor", "Landroidx/compose/runtime/State;", "selected", "", "enabled", "animate", "dayContainerColor$material3_release", "(ZZZLandroidx/compose/runtime/Composer;I)Landroidx/compose/runtime/State;", "isToday", "inRange", "dayContentColor$material3_release", "(ZZZZLandroidx/compose/runtime/Composer;I)Landroidx/compose/runtime/State;", "equals", "other", "hashCode", "", "yearContainerColor", "yearContainerColor$material3_release", "(ZZLandroidx/compose/runtime/Composer;I)Landroidx/compose/runtime/State;", "currentYear", "yearContentColor$material3_release", "takeOrElse", "block", "Lkotlin/Function0;", "takeOrElse$material3_release", "material3_release"}, k = 1, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class DatePickerColors {
    public static final int $stable = 0;
    private final long containerColor;
    private final long currentYearContentColor;
    private final TextFieldColors dateTextFieldColors;
    private final long dayContentColor;
    private final long dayInSelectionRangeContainerColor;
    private final long dayInSelectionRangeContentColor;
    private final long disabledDayContentColor;
    private final long disabledSelectedDayContainerColor;
    private final long disabledSelectedDayContentColor;
    private final long disabledSelectedYearContainerColor;
    private final long disabledSelectedYearContentColor;
    private final long disabledYearContentColor;
    private final long dividerColor;
    private final long headlineContentColor;
    private final long navigationContentColor;
    private final long selectedDayContainerColor;
    private final long selectedDayContentColor;
    private final long selectedYearContainerColor;
    private final long selectedYearContentColor;
    private final long subheadContentColor;
    private final long titleContentColor;
    private final long todayContentColor;
    private final long todayDateBorderColor;
    private final long weekdayContentColor;
    private final long yearContentColor;

    public /* synthetic */ DatePickerColors(long j, long j2, long j3, long j4, long j5, long j6, long j7, long j8, long j9, long j10, long j11, long j12, long j13, long j14, long j15, long j16, long j17, long j18, long j19, long j20, long j21, long j22, long j23, long j24, TextFieldColors textFieldColors, DefaultConstructorMarker defaultConstructorMarker) {
        this(j, j2, j3, j4, j5, j6, j7, j8, j9, j10, j11, j12, j13, j14, j15, j16, j17, j18, j19, j20, j21, j22, j23, j24, textFieldColors);
    }

    private DatePickerColors(long containerColor, long titleContentColor, long headlineContentColor, long weekdayContentColor, long subheadContentColor, long navigationContentColor, long yearContentColor, long disabledYearContentColor, long currentYearContentColor, long selectedYearContentColor, long disabledSelectedYearContentColor, long selectedYearContainerColor, long disabledSelectedYearContainerColor, long dayContentColor, long disabledDayContentColor, long selectedDayContentColor, long disabledSelectedDayContentColor, long selectedDayContainerColor, long disabledSelectedDayContainerColor, long todayContentColor, long todayDateBorderColor, long dayInSelectionRangeContainerColor, long dayInSelectionRangeContentColor, long dividerColor, TextFieldColors dateTextFieldColors) {
        this.containerColor = containerColor;
        this.titleContentColor = titleContentColor;
        this.headlineContentColor = headlineContentColor;
        this.weekdayContentColor = weekdayContentColor;
        this.subheadContentColor = subheadContentColor;
        this.navigationContentColor = navigationContentColor;
        this.yearContentColor = yearContentColor;
        this.disabledYearContentColor = disabledYearContentColor;
        this.currentYearContentColor = currentYearContentColor;
        this.selectedYearContentColor = selectedYearContentColor;
        this.disabledSelectedYearContentColor = disabledSelectedYearContentColor;
        this.selectedYearContainerColor = selectedYearContainerColor;
        this.disabledSelectedYearContainerColor = disabledSelectedYearContainerColor;
        this.dayContentColor = dayContentColor;
        this.disabledDayContentColor = disabledDayContentColor;
        this.selectedDayContentColor = selectedDayContentColor;
        this.disabledSelectedDayContentColor = disabledSelectedDayContentColor;
        this.selectedDayContainerColor = selectedDayContainerColor;
        this.disabledSelectedDayContainerColor = disabledSelectedDayContainerColor;
        this.todayContentColor = todayContentColor;
        this.todayDateBorderColor = todayDateBorderColor;
        this.dayInSelectionRangeContainerColor = dayInSelectionRangeContainerColor;
        this.dayInSelectionRangeContentColor = dayInSelectionRangeContentColor;
        this.dividerColor = dividerColor;
        this.dateTextFieldColors = dateTextFieldColors;
    }

    /* renamed from: getContainerColor-0d7_KjU, reason: not valid java name and from getter */
    public final long getContainerColor() {
        return this.containerColor;
    }

    /* renamed from: getTitleContentColor-0d7_KjU, reason: not valid java name and from getter */
    public final long getTitleContentColor() {
        return this.titleContentColor;
    }

    /* renamed from: getHeadlineContentColor-0d7_KjU, reason: not valid java name and from getter */
    public final long getHeadlineContentColor() {
        return this.headlineContentColor;
    }

    /* renamed from: getWeekdayContentColor-0d7_KjU, reason: not valid java name and from getter */
    public final long getWeekdayContentColor() {
        return this.weekdayContentColor;
    }

    /* renamed from: getSubheadContentColor-0d7_KjU, reason: not valid java name and from getter */
    public final long getSubheadContentColor() {
        return this.subheadContentColor;
    }

    /* renamed from: getNavigationContentColor-0d7_KjU, reason: not valid java name and from getter */
    public final long getNavigationContentColor() {
        return this.navigationContentColor;
    }

    /* renamed from: getYearContentColor-0d7_KjU, reason: not valid java name and from getter */
    public final long getYearContentColor() {
        return this.yearContentColor;
    }

    /* renamed from: getDisabledYearContentColor-0d7_KjU, reason: not valid java name and from getter */
    public final long getDisabledYearContentColor() {
        return this.disabledYearContentColor;
    }

    /* renamed from: getCurrentYearContentColor-0d7_KjU, reason: not valid java name and from getter */
    public final long getCurrentYearContentColor() {
        return this.currentYearContentColor;
    }

    /* renamed from: getSelectedYearContentColor-0d7_KjU, reason: not valid java name and from getter */
    public final long getSelectedYearContentColor() {
        return this.selectedYearContentColor;
    }

    /* renamed from: getDisabledSelectedYearContentColor-0d7_KjU, reason: not valid java name and from getter */
    public final long getDisabledSelectedYearContentColor() {
        return this.disabledSelectedYearContentColor;
    }

    /* renamed from: getSelectedYearContainerColor-0d7_KjU, reason: not valid java name and from getter */
    public final long getSelectedYearContainerColor() {
        return this.selectedYearContainerColor;
    }

    /* renamed from: getDisabledSelectedYearContainerColor-0d7_KjU, reason: not valid java name and from getter */
    public final long getDisabledSelectedYearContainerColor() {
        return this.disabledSelectedYearContainerColor;
    }

    /* renamed from: getDayContentColor-0d7_KjU, reason: not valid java name and from getter */
    public final long getDayContentColor() {
        return this.dayContentColor;
    }

    /* renamed from: getDisabledDayContentColor-0d7_KjU, reason: not valid java name and from getter */
    public final long getDisabledDayContentColor() {
        return this.disabledDayContentColor;
    }

    /* renamed from: getSelectedDayContentColor-0d7_KjU, reason: not valid java name and from getter */
    public final long getSelectedDayContentColor() {
        return this.selectedDayContentColor;
    }

    /* renamed from: getDisabledSelectedDayContentColor-0d7_KjU, reason: not valid java name and from getter */
    public final long getDisabledSelectedDayContentColor() {
        return this.disabledSelectedDayContentColor;
    }

    /* renamed from: getSelectedDayContainerColor-0d7_KjU, reason: not valid java name and from getter */
    public final long getSelectedDayContainerColor() {
        return this.selectedDayContainerColor;
    }

    /* renamed from: getDisabledSelectedDayContainerColor-0d7_KjU, reason: not valid java name and from getter */
    public final long getDisabledSelectedDayContainerColor() {
        return this.disabledSelectedDayContainerColor;
    }

    /* renamed from: getTodayContentColor-0d7_KjU, reason: not valid java name and from getter */
    public final long getTodayContentColor() {
        return this.todayContentColor;
    }

    /* renamed from: getTodayDateBorderColor-0d7_KjU, reason: not valid java name and from getter */
    public final long getTodayDateBorderColor() {
        return this.todayDateBorderColor;
    }

    /* renamed from: getDayInSelectionRangeContainerColor-0d7_KjU, reason: not valid java name and from getter */
    public final long getDayInSelectionRangeContainerColor() {
        return this.dayInSelectionRangeContainerColor;
    }

    /* renamed from: getDayInSelectionRangeContentColor-0d7_KjU, reason: not valid java name and from getter */
    public final long getDayInSelectionRangeContentColor() {
        return this.dayInSelectionRangeContentColor;
    }

    /* renamed from: getDividerColor-0d7_KjU, reason: not valid java name and from getter */
    public final long getDividerColor() {
        return this.dividerColor;
    }

    public final TextFieldColors getDateTextFieldColors() {
        return this.dateTextFieldColors;
    }

    /* renamed from: copy-tNwlRmA$default, reason: not valid java name */
    public static /* synthetic */ DatePickerColors m1787copytNwlRmA$default(DatePickerColors datePickerColors, long j, long j2, long j3, long j4, long j5, long j6, long j7, long j8, long j9, long j10, long j11, long j12, long j13, long j14, long j15, long j16, long j17, long j18, long j19, long j20, long j21, long j22, long j23, long j24, TextFieldColors textFieldColors, int i, Object obj) {
        long j25;
        long j26;
        long j27;
        long j28;
        long j29;
        long j30;
        long j31;
        long j32;
        long j33;
        long j34;
        long j35;
        long j36;
        long j37;
        long j38;
        long j39;
        long j40;
        long j41;
        long j42;
        long j43 = (i & 1) != 0 ? datePickerColors.containerColor : j;
        long j44 = (i & 2) != 0 ? datePickerColors.titleContentColor : j2;
        long j45 = (i & 4) != 0 ? datePickerColors.headlineContentColor : j3;
        long j46 = (i & 8) != 0 ? datePickerColors.weekdayContentColor : j4;
        long j47 = (i & 16) != 0 ? datePickerColors.subheadContentColor : j5;
        long j48 = (i & 32) != 0 ? datePickerColors.navigationContentColor : j6;
        long j49 = (i & 64) != 0 ? datePickerColors.yearContentColor : j7;
        long j50 = (i & 128) != 0 ? datePickerColors.disabledYearContentColor : j8;
        long j51 = (i & 256) != 0 ? datePickerColors.currentYearContentColor : j9;
        long j52 = (i & 512) != 0 ? datePickerColors.selectedYearContentColor : j10;
        long j53 = (i & 1024) != 0 ? datePickerColors.disabledSelectedYearContentColor : j11;
        long j54 = (i & 2048) != 0 ? datePickerColors.selectedYearContainerColor : j12;
        long j55 = (i & 4096) != 0 ? datePickerColors.disabledSelectedYearContainerColor : j13;
        long j56 = (i & 8192) != 0 ? datePickerColors.dayContentColor : j14;
        long j57 = (i & 16384) != 0 ? datePickerColors.disabledDayContentColor : j15;
        if ((i & 32768) != 0) {
            j25 = j57;
            j26 = datePickerColors.selectedDayContentColor;
        } else {
            j25 = j57;
            j26 = j16;
        }
        if ((i & 65536) != 0) {
            j27 = j26;
            j28 = datePickerColors.disabledSelectedDayContentColor;
        } else {
            j27 = j26;
            j28 = j17;
        }
        if ((i & 131072) != 0) {
            j29 = j28;
            j30 = datePickerColors.selectedDayContainerColor;
        } else {
            j29 = j28;
            j30 = j18;
        }
        if ((i & 262144) != 0) {
            j31 = j30;
            j32 = datePickerColors.disabledSelectedDayContainerColor;
        } else {
            j31 = j30;
            j32 = j19;
        }
        if ((i & 524288) != 0) {
            j33 = j32;
            j34 = datePickerColors.todayContentColor;
        } else {
            j33 = j32;
            j34 = j20;
        }
        if ((i & 1048576) != 0) {
            j35 = j34;
            j36 = datePickerColors.todayDateBorderColor;
        } else {
            j35 = j34;
            j36 = j21;
        }
        if ((i & 2097152) != 0) {
            j37 = j36;
            j38 = datePickerColors.dayInSelectionRangeContainerColor;
        } else {
            j37 = j36;
            j38 = j22;
        }
        if ((i & 4194304) != 0) {
            j39 = j38;
            j40 = datePickerColors.dayInSelectionRangeContentColor;
        } else {
            j39 = j38;
            j40 = j23;
        }
        if ((i & 8388608) != 0) {
            j41 = j40;
            j42 = datePickerColors.dividerColor;
        } else {
            j41 = j40;
            j42 = j24;
        }
        return datePickerColors.m1788copytNwlRmA(j43, j44, j45, j46, j47, j48, j49, j50, j51, j52, j53, j54, j55, j56, j25, j27, j29, j31, j33, j35, j37, j39, j41, j42, (i & 16777216) != 0 ? datePickerColors.dateTextFieldColors : textFieldColors);
    }

    /* renamed from: copy-tNwlRmA, reason: not valid java name */
    public final DatePickerColors m1788copytNwlRmA(long containerColor, long titleContentColor, long headlineContentColor, long weekdayContentColor, long subheadContentColor, long navigationContentColor, long yearContentColor, long disabledYearContentColor, long currentYearContentColor, long selectedYearContentColor, long disabledSelectedYearContentColor, long selectedYearContainerColor, long disabledSelectedYearContainerColor, long dayContentColor, long disabledDayContentColor, long selectedDayContentColor, long disabledSelectedDayContentColor, long selectedDayContainerColor, long disabledSelectedDayContainerColor, long todayContentColor, long todayDateBorderColor, long dayInSelectionRangeContainerColor, long dayInSelectionRangeContentColor, long dividerColor, TextFieldColors dateTextFieldColors) {
        return new DatePickerColors((containerColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (containerColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? containerColor : this.containerColor, (titleContentColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (titleContentColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? titleContentColor : this.titleContentColor, (headlineContentColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (headlineContentColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? headlineContentColor : this.headlineContentColor, (weekdayContentColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (weekdayContentColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? weekdayContentColor : this.weekdayContentColor, (subheadContentColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (subheadContentColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? subheadContentColor : this.subheadContentColor, (navigationContentColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (navigationContentColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? navigationContentColor : this.navigationContentColor, (yearContentColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (yearContentColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? yearContentColor : this.yearContentColor, (disabledYearContentColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (disabledYearContentColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? disabledYearContentColor : this.disabledYearContentColor, (currentYearContentColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (currentYearContentColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? currentYearContentColor : this.currentYearContentColor, (selectedYearContentColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (selectedYearContentColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? selectedYearContentColor : this.selectedYearContentColor, (disabledSelectedYearContentColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (disabledSelectedYearContentColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? disabledSelectedYearContentColor : this.disabledSelectedYearContentColor, (selectedYearContainerColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (selectedYearContainerColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? selectedYearContainerColor : this.selectedYearContainerColor, (disabledSelectedYearContainerColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (disabledSelectedYearContainerColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? disabledSelectedYearContainerColor : this.disabledSelectedYearContainerColor, (dayContentColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (dayContentColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? dayContentColor : this.dayContentColor, (disabledDayContentColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (disabledDayContentColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? disabledDayContentColor : this.disabledDayContentColor, (selectedDayContentColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (selectedDayContentColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? selectedDayContentColor : this.selectedDayContentColor, (disabledSelectedDayContentColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (disabledSelectedDayContentColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? disabledSelectedDayContentColor : this.disabledSelectedDayContentColor, (selectedDayContainerColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (selectedDayContainerColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? selectedDayContainerColor : this.selectedDayContainerColor, (disabledSelectedDayContainerColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (disabledSelectedDayContainerColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? disabledSelectedDayContainerColor : this.disabledSelectedDayContainerColor, (todayContentColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (todayContentColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? todayContentColor : this.todayContentColor, (todayDateBorderColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (todayDateBorderColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? todayDateBorderColor : this.todayDateBorderColor, (dayInSelectionRangeContainerColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (dayInSelectionRangeContainerColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? dayInSelectionRangeContainerColor : this.dayInSelectionRangeContainerColor, (dayInSelectionRangeContentColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (dayInSelectionRangeContentColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? dayInSelectionRangeContentColor : this.dayInSelectionRangeContentColor, dividerColor != Color.INSTANCE.m3782getUnspecified0d7_KjU() ? dividerColor : this.dividerColor, takeOrElse$material3_release(dateTextFieldColors, new Function0<TextFieldColors>() { // from class: androidx.compose.material3.DatePickerColors$copy$25
            {
                super(0);
            }

            /* JADX WARN: Can't rename method to resolve collision */
            @Override // kotlin.jvm.functions.Function0
            public final TextFieldColors invoke() {
                return DatePickerColors.this.getDateTextFieldColors();
            }
        }), null);
    }

    public final TextFieldColors takeOrElse$material3_release(TextFieldColors $this$takeOrElse, Function0<TextFieldColors> function0) {
        return $this$takeOrElse == null ? function0.invoke() : $this$takeOrElse;
    }

    public final State<Color> dayContentColor$material3_release(boolean isToday, boolean selected, boolean inRange, boolean enabled, Composer $composer, int $changed) {
        State<Color> m104animateColorAsStateeuL9pac;
        $composer.startReplaceableGroup(-1233694918);
        ComposerKt.sourceInformation($composer, "C(dayContentColor)P(2,3,1):DatePicker.kt#uh7d8r");
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventStart(-1233694918, $changed, -1, "androidx.compose.material3.DatePickerColors.dayContentColor (DatePicker.kt:890)");
        }
        long target = (selected && enabled) ? this.selectedDayContentColor : (!selected || enabled) ? (inRange && enabled) ? this.dayInSelectionRangeContentColor : (!inRange || enabled) ? isToday ? this.todayContentColor : enabled ? this.dayContentColor : this.disabledDayContentColor : this.disabledDayContentColor : this.disabledSelectedDayContentColor;
        if (inRange) {
            $composer.startReplaceableGroup(379022200);
            ComposerKt.sourceInformation($composer, "902@42285L28");
            m104animateColorAsStateeuL9pac = SnapshotStateKt.rememberUpdatedState(Color.m3736boximpl(target), $composer, 0);
            $composer.endReplaceableGroup();
        } else {
            $composer.startReplaceableGroup(379022258);
            ComposerKt.sourceInformation($composer, "905@42421L134");
            m104animateColorAsStateeuL9pac = SingleValueAnimationKt.m104animateColorAsStateeuL9pac(target, AnimationSpecKt.tween$default(100, 0, null, 6, null), null, null, $composer, 0, 12);
            $composer.endReplaceableGroup();
        }
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventEnd();
        }
        $composer.endReplaceableGroup();
        return m104animateColorAsStateeuL9pac;
    }

    public final State<Color> dayContainerColor$material3_release(boolean selected, boolean enabled, boolean animate, Composer $composer, int $changed) {
        long target;
        State<Color> rememberUpdatedState;
        $composer.startReplaceableGroup(-1240482658);
        ComposerKt.sourceInformation($composer, "C(dayContainerColor)P(2,1):DatePicker.kt#uh7d8r");
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventStart(-1240482658, $changed, -1, "androidx.compose.material3.DatePickerColors.dayContainerColor (DatePicker.kt:924)");
        }
        if (selected) {
            target = enabled ? this.selectedDayContainerColor : this.disabledSelectedDayContainerColor;
        } else {
            target = Color.INSTANCE.m3781getTransparent0d7_KjU();
        }
        if (animate) {
            $composer.startReplaceableGroup(1577421952);
            ComposerKt.sourceInformation($composer, "931@43245L134");
            rememberUpdatedState = SingleValueAnimationKt.m104animateColorAsStateeuL9pac(target, AnimationSpecKt.tween$default(100, 0, null, 6, null), null, null, $composer, 0, 12);
            $composer.endReplaceableGroup();
        } else {
            $composer.startReplaceableGroup(1577422116);
            ComposerKt.sourceInformation($composer, "936@43409L28");
            rememberUpdatedState = SnapshotStateKt.rememberUpdatedState(Color.m3736boximpl(target), $composer, 0);
            $composer.endReplaceableGroup();
        }
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventEnd();
        }
        $composer.endReplaceableGroup();
        return rememberUpdatedState;
    }

    public final State<Color> yearContentColor$material3_release(boolean currentYear, boolean selected, boolean enabled, Composer $composer, int $changed) {
        long target;
        $composer.startReplaceableGroup(874111097);
        ComposerKt.sourceInformation($composer, "C(yearContentColor)P(!1,2)961@44249L122:DatePicker.kt#uh7d8r");
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventStart(874111097, $changed, -1, "androidx.compose.material3.DatePickerColors.yearContentColor (DatePicker.kt:952)");
        }
        if (selected && enabled) {
            target = this.selectedYearContentColor;
        } else if (selected && !enabled) {
            target = this.disabledSelectedYearContentColor;
        } else if (currentYear) {
            target = this.currentYearContentColor;
        } else {
            target = enabled ? this.yearContentColor : this.disabledYearContentColor;
        }
        State<Color> m104animateColorAsStateeuL9pac = SingleValueAnimationKt.m104animateColorAsStateeuL9pac(target, AnimationSpecKt.tween$default(100, 0, null, 6, null), null, null, $composer, 0, 12);
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventEnd();
        }
        $composer.endReplaceableGroup();
        return m104animateColorAsStateeuL9pac;
    }

    public final State<Color> yearContainerColor$material3_release(boolean selected, boolean enabled, Composer $composer, int $changed) {
        long target;
        $composer.startReplaceableGroup(-1306331107);
        ComposerKt.sourceInformation($composer, "C(yearContainerColor)P(1)980@44908L122:DatePicker.kt#uh7d8r");
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventStart(-1306331107, $changed, -1, "androidx.compose.material3.DatePickerColors.yearContainerColor (DatePicker.kt:974)");
        }
        if (selected) {
            target = enabled ? this.selectedYearContainerColor : this.disabledSelectedYearContainerColor;
        } else {
            target = Color.INSTANCE.m3781getTransparent0d7_KjU();
        }
        State<Color> m104animateColorAsStateeuL9pac = SingleValueAnimationKt.m104animateColorAsStateeuL9pac(target, AnimationSpecKt.tween$default(100, 0, null, 6, null), null, null, $composer, 0, 12);
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventEnd();
        }
        $composer.endReplaceableGroup();
        return m104animateColorAsStateeuL9pac;
    }

    public boolean equals(Object other) {
        return (other instanceof DatePickerColors) && Color.m3747equalsimpl0(this.containerColor, ((DatePickerColors) other).containerColor) && Color.m3747equalsimpl0(this.titleContentColor, ((DatePickerColors) other).titleContentColor) && Color.m3747equalsimpl0(this.headlineContentColor, ((DatePickerColors) other).headlineContentColor) && Color.m3747equalsimpl0(this.weekdayContentColor, ((DatePickerColors) other).weekdayContentColor) && Color.m3747equalsimpl0(this.subheadContentColor, ((DatePickerColors) other).subheadContentColor) && Color.m3747equalsimpl0(this.yearContentColor, ((DatePickerColors) other).yearContentColor) && Color.m3747equalsimpl0(this.disabledYearContentColor, ((DatePickerColors) other).disabledYearContentColor) && Color.m3747equalsimpl0(this.currentYearContentColor, ((DatePickerColors) other).currentYearContentColor) && Color.m3747equalsimpl0(this.selectedYearContentColor, ((DatePickerColors) other).selectedYearContentColor) && Color.m3747equalsimpl0(this.disabledSelectedYearContentColor, ((DatePickerColors) other).disabledSelectedYearContentColor) && Color.m3747equalsimpl0(this.selectedYearContainerColor, ((DatePickerColors) other).selectedYearContainerColor) && Color.m3747equalsimpl0(this.disabledSelectedYearContainerColor, ((DatePickerColors) other).disabledSelectedYearContainerColor) && Color.m3747equalsimpl0(this.dayContentColor, ((DatePickerColors) other).dayContentColor) && Color.m3747equalsimpl0(this.disabledDayContentColor, ((DatePickerColors) other).disabledDayContentColor) && Color.m3747equalsimpl0(this.selectedDayContentColor, ((DatePickerColors) other).selectedDayContentColor) && Color.m3747equalsimpl0(this.disabledSelectedDayContentColor, ((DatePickerColors) other).disabledSelectedDayContentColor) && Color.m3747equalsimpl0(this.selectedDayContainerColor, ((DatePickerColors) other).selectedDayContainerColor) && Color.m3747equalsimpl0(this.disabledSelectedDayContainerColor, ((DatePickerColors) other).disabledSelectedDayContainerColor) && Color.m3747equalsimpl0(this.todayContentColor, ((DatePickerColors) other).todayContentColor) && Color.m3747equalsimpl0(this.todayDateBorderColor, ((DatePickerColors) other).todayDateBorderColor) && Color.m3747equalsimpl0(this.dayInSelectionRangeContainerColor, ((DatePickerColors) other).dayInSelectionRangeContainerColor) && Color.m3747equalsimpl0(this.dayInSelectionRangeContentColor, ((DatePickerColors) other).dayInSelectionRangeContentColor);
    }

    public int hashCode() {
        int result = Color.m3753hashCodeimpl(this.containerColor);
        return (((((((((((((((((((((((((((((((((((((((((result * 31) + Color.m3753hashCodeimpl(this.titleContentColor)) * 31) + Color.m3753hashCodeimpl(this.headlineContentColor)) * 31) + Color.m3753hashCodeimpl(this.weekdayContentColor)) * 31) + Color.m3753hashCodeimpl(this.subheadContentColor)) * 31) + Color.m3753hashCodeimpl(this.yearContentColor)) * 31) + Color.m3753hashCodeimpl(this.disabledYearContentColor)) * 31) + Color.m3753hashCodeimpl(this.currentYearContentColor)) * 31) + Color.m3753hashCodeimpl(this.selectedYearContentColor)) * 31) + Color.m3753hashCodeimpl(this.disabledSelectedYearContentColor)) * 31) + Color.m3753hashCodeimpl(this.selectedYearContainerColor)) * 31) + Color.m3753hashCodeimpl(this.disabledSelectedYearContainerColor)) * 31) + Color.m3753hashCodeimpl(this.dayContentColor)) * 31) + Color.m3753hashCodeimpl(this.disabledDayContentColor)) * 31) + Color.m3753hashCodeimpl(this.selectedDayContentColor)) * 31) + Color.m3753hashCodeimpl(this.disabledSelectedDayContentColor)) * 31) + Color.m3753hashCodeimpl(this.selectedDayContainerColor)) * 31) + Color.m3753hashCodeimpl(this.disabledSelectedDayContainerColor)) * 31) + Color.m3753hashCodeimpl(this.todayContentColor)) * 31) + Color.m3753hashCodeimpl(this.todayDateBorderColor)) * 31) + Color.m3753hashCodeimpl(this.dayInSelectionRangeContainerColor)) * 31) + Color.m3753hashCodeimpl(this.dayInSelectionRangeContentColor);
    }
}
