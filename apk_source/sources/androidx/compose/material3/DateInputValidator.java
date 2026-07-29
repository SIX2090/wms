package androidx.compose.material3;

import kotlin.Metadata;
import kotlin.ranges.IntRange;

/* compiled from: DateInput.kt */
@Metadata(d1 = {"\u0000J\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010\u000e\n\u0002\b\u0004\n\u0002\u0010\t\n\u0002\b\u000b\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\b\u0003\b\u0001\u0018\u00002\u00020\u0001B]\u0012\u0006\u0010\u0002\u001a\u00020\u0003\u0012\u0006\u0010\u0004\u001a\u00020\u0005\u0012\u0006\u0010\u0006\u001a\u00020\u0007\u0012\u0006\u0010\b\u001a\u00020\t\u0012\u0006\u0010\n\u001a\u00020\u000b\u0012\u0006\u0010\f\u001a\u00020\u000b\u0012\u0006\u0010\r\u001a\u00020\u000b\u0012\u0006\u0010\u000e\u001a\u00020\u000b\u0012\n\b\u0002\u0010\u000f\u001a\u0004\u0018\u00010\u0010\u0012\n\b\u0002\u0010\u0011\u001a\u0004\u0018\u00010\u0010¢\u0006\u0002\u0010\u0012J.\u0010\u001a\u001a\u00020\u000b2\b\u0010\u001b\u001a\u0004\u0018\u00010\u001c2\u0006\u0010\u001d\u001a\u00020\u001e2\n\u0010\u001f\u001a\u00060 j\u0002`!ø\u0001\u0000¢\u0006\u0004\b\"\u0010#R\u001e\u0010\u0011\u001a\u0004\u0018\u00010\u0010X\u0080\u000e¢\u0006\u0010\n\u0002\u0010\u0017\u001a\u0004\b\u0013\u0010\u0014\"\u0004\b\u0015\u0010\u0016R\u001e\u0010\u000f\u001a\u0004\u0018\u00010\u0010X\u0080\u000e¢\u0006\u0010\n\u0002\u0010\u0017\u001a\u0004\b\u0018\u0010\u0014\"\u0004\b\u0019\u0010\u0016R\u000e\u0010\b\u001a\u00020\tX\u0082\u0004¢\u0006\u0002\n\u0000R\u000e\u0010\u0006\u001a\u00020\u0007X\u0082\u0004¢\u0006\u0002\n\u0000R\u000e\u0010\f\u001a\u00020\u000bX\u0082\u0004¢\u0006\u0002\n\u0000R\u000e\u0010\n\u001a\u00020\u000bX\u0082\u0004¢\u0006\u0002\n\u0000R\u000e\u0010\r\u001a\u00020\u000bX\u0082\u0004¢\u0006\u0002\n\u0000R\u000e\u0010\u000e\u001a\u00020\u000bX\u0082\u0004¢\u0006\u0002\n\u0000R\u000e\u0010\u0004\u001a\u00020\u0005X\u0082\u0004¢\u0006\u0002\n\u0000R\u000e\u0010\u0002\u001a\u00020\u0003X\u0082\u0004¢\u0006\u0002\n\u0000\u0082\u0002\u0007\n\u0005\b¡\u001e0\u0001¨\u0006$"}, d2 = {"Landroidx/compose/material3/DateInputValidator;", "", "yearRange", "Lkotlin/ranges/IntRange;", "selectableDates", "Landroidx/compose/material3/SelectableDates;", "dateInputFormat", "Landroidx/compose/material3/DateInputFormat;", "dateFormatter", "Landroidx/compose/material3/DatePickerFormatter;", "errorDatePattern", "", "errorDateOutOfYearRange", "errorInvalidNotAllowed", "errorInvalidRangeInput", "currentStartDateMillis", "", "currentEndDateMillis", "(Lkotlin/ranges/IntRange;Landroidx/compose/material3/SelectableDates;Landroidx/compose/material3/DateInputFormat;Landroidx/compose/material3/DatePickerFormatter;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;Ljava/lang/Long;Ljava/lang/Long;)V", "getCurrentEndDateMillis$material3_release", "()Ljava/lang/Long;", "setCurrentEndDateMillis$material3_release", "(Ljava/lang/Long;)V", "Ljava/lang/Long;", "getCurrentStartDateMillis$material3_release", "setCurrentStartDateMillis$material3_release", "validate", "dateToValidate", "Landroidx/compose/material3/CalendarDate;", "inputIdentifier", "Landroidx/compose/material3/InputIdentifier;", "locale", "Ljava/util/Locale;", "Landroidx/compose/material3/CalendarLocale;", "validate-XivgLIo", "(Landroidx/compose/material3/CalendarDate;ILjava/util/Locale;)Ljava/lang/String;", "material3_release"}, k = 1, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class DateInputValidator {
    public static final int $stable = 0;
    private Long currentEndDateMillis;
    private Long currentStartDateMillis;
    private final DatePickerFormatter dateFormatter;
    private final DateInputFormat dateInputFormat;
    private final String errorDateOutOfYearRange;
    private final String errorDatePattern;
    private final String errorInvalidNotAllowed;
    private final String errorInvalidRangeInput;
    private final SelectableDates selectableDates;
    private final IntRange yearRange;

    public DateInputValidator(IntRange yearRange, SelectableDates selectableDates, DateInputFormat dateInputFormat, DatePickerFormatter dateFormatter, String errorDatePattern, String errorDateOutOfYearRange, String errorInvalidNotAllowed, String errorInvalidRangeInput, Long currentStartDateMillis, Long currentEndDateMillis) {
        this.yearRange = yearRange;
        this.selectableDates = selectableDates;
        this.dateInputFormat = dateInputFormat;
        this.dateFormatter = dateFormatter;
        this.errorDatePattern = errorDatePattern;
        this.errorDateOutOfYearRange = errorDateOutOfYearRange;
        this.errorInvalidNotAllowed = errorInvalidNotAllowed;
        this.errorInvalidRangeInput = errorInvalidRangeInput;
        this.currentStartDateMillis = currentStartDateMillis;
        this.currentEndDateMillis = currentEndDateMillis;
    }

    /* JADX WARN: Illegal instructions before constructor call */
    /*
        Code decompiled incorrectly, please refer to instructions dump.
        To view partially-correct add '--show-bad-code' argument
    */
    public /* synthetic */ DateInputValidator(kotlin.ranges.IntRange r15, androidx.compose.material3.SelectableDates r16, androidx.compose.material3.DateInputFormat r17, androidx.compose.material3.DatePickerFormatter r18, java.lang.String r19, java.lang.String r20, java.lang.String r21, java.lang.String r22, java.lang.Long r23, java.lang.Long r24, int r25, kotlin.jvm.internal.DefaultConstructorMarker r26) {
        /*
            r14 = this;
            r0 = r25
            r1 = r0 & 256(0x100, float:3.59E-43)
            r2 = 0
            if (r1 == 0) goto L9
            r12 = r2
            goto Lb
        L9:
            r12 = r23
        Lb:
            r0 = r0 & 512(0x200, float:7.17E-43)
            if (r0 == 0) goto L11
            r13 = r2
            goto L13
        L11:
            r13 = r24
        L13:
            r3 = r14
            r4 = r15
            r5 = r16
            r6 = r17
            r7 = r18
            r8 = r19
            r9 = r20
            r10 = r21
            r11 = r22
            r3.<init>(r4, r5, r6, r7, r8, r9, r10, r11, r12, r13)
            return
        */
        throw new UnsupportedOperationException("Method not decompiled: androidx.compose.material3.DateInputValidator.<init>(kotlin.ranges.IntRange, androidx.compose.material3.SelectableDates, androidx.compose.material3.DateInputFormat, androidx.compose.material3.DatePickerFormatter, java.lang.String, java.lang.String, java.lang.String, java.lang.String, java.lang.Long, java.lang.Long, int, kotlin.jvm.internal.DefaultConstructorMarker):void");
    }

    /* renamed from: getCurrentStartDateMillis$material3_release, reason: from getter */
    public final Long getCurrentStartDateMillis() {
        return this.currentStartDateMillis;
    }

    public final void setCurrentStartDateMillis$material3_release(Long l) {
        this.currentStartDateMillis = l;
    }

    /* renamed from: getCurrentEndDateMillis$material3_release, reason: from getter */
    public final Long getCurrentEndDateMillis() {
        return this.currentEndDateMillis;
    }

    public final void setCurrentEndDateMillis$material3_release(Long l) {
        this.currentEndDateMillis = l;
    }

    /* JADX WARN: Code restructure failed: missing block: B:20:0x00a0, code lost:
    
        if (r0 < (r2 != null ? r2.longValue() : Long.MAX_VALUE)) goto L23;
     */
    /* renamed from: validate-XivgLIo, reason: not valid java name */
    /*
        Code decompiled incorrectly, please refer to instructions dump.
        To view partially-correct add '--show-bad-code' argument
    */
    public final java.lang.String m1786validateXivgLIo(androidx.compose.material3.CalendarDate r12, int r13, java.util.Locale r14) {
        /*
            r11 = this;
            r0 = 1
            java.lang.String r1 = "format(this, *args)"
            if (r12 != 0) goto L2a
            java.lang.String r2 = r11.errorDatePattern
            androidx.compose.material3.DateInputFormat r3 = r11.dateInputFormat
            java.lang.String r3 = r3.getPatternWithDelimiters()
            java.util.Locale r4 = java.util.Locale.ROOT
            java.lang.String r3 = r3.toUpperCase(r4)
            java.lang.String r4 = "this as java.lang.String).toUpperCase(Locale.ROOT)"
            kotlin.jvm.internal.Intrinsics.checkNotNullExpressionValue(r3, r4)
            java.lang.Object[] r3 = new java.lang.Object[]{r3}
            java.lang.Object[] r0 = java.util.Arrays.copyOf(r3, r0)
            java.lang.String r0 = java.lang.String.format(r2, r0)
            kotlin.jvm.internal.Intrinsics.checkNotNullExpressionValue(r0, r1)
            return r0
        L2a:
            kotlin.ranges.IntRange r2 = r11.yearRange
            int r3 = r12.getYear()
            boolean r2 = r2.contains(r3)
            if (r2 != 0) goto L66
            java.lang.String r0 = r11.errorDateOutOfYearRange
            kotlin.ranges.IntRange r2 = r11.yearRange
            int r3 = r2.getFirst()
            r7 = 7
            r8 = 0
            r4 = 0
            r5 = 0
            r6 = 0
            java.lang.String r2 = androidx.compose.material3.ActualJvm_jvmKt.toLocalString$default(r3, r4, r5, r6, r7, r8)
            kotlin.ranges.IntRange r3 = r11.yearRange
            int r4 = r3.getLast()
            r8 = 7
            r9 = 0
            r7 = 0
            java.lang.String r3 = androidx.compose.material3.ActualJvm_jvmKt.toLocalString$default(r4, r5, r6, r7, r8, r9)
            java.lang.Object[] r2 = new java.lang.Object[]{r2, r3}
            r3 = 2
            java.lang.Object[] r2 = java.util.Arrays.copyOf(r2, r3)
            java.lang.String r0 = java.lang.String.format(r0, r2)
            kotlin.jvm.internal.Intrinsics.checkNotNullExpressionValue(r0, r1)
            return r0
        L66:
            androidx.compose.material3.SelectableDates r2 = r11.selectableDates
            r3 = 0
            int r4 = r12.getYear()
            boolean r4 = r2.isSelectableYear(r4)
            if (r4 == 0) goto Lc7
            long r4 = r12.getUtcTimeMillis()
            boolean r4 = r2.isSelectableDate(r4)
            if (r4 != 0) goto L7e
            goto Lc7
        L7e:
            androidx.compose.material3.InputIdentifier$Companion r0 = androidx.compose.material3.InputIdentifier.INSTANCE
            int r0 = r0.m1960getStartDateInputJ2x2o4M()
            boolean r0 = androidx.compose.material3.InputIdentifier.m1954equalsimpl0(r13, r0)
            if (r0 == 0) goto La2
            long r0 = r12.getUtcTimeMillis()
            java.lang.Long r2 = r11.currentEndDateMillis
            if (r2 == 0) goto L99
            long r2 = r2.longValue()
            goto L9e
        L99:
            r2 = 9223372036854775807(0x7fffffffffffffff, double:NaN)
        L9e:
            int r0 = (r0 > r2 ? 1 : (r0 == r2 ? 0 : -1))
            if (r0 >= 0) goto Lc1
        La2:
            androidx.compose.material3.InputIdentifier$Companion r0 = androidx.compose.material3.InputIdentifier.INSTANCE
            int r0 = r0.m1958getEndDateInputJ2x2o4M()
            boolean r0 = androidx.compose.material3.InputIdentifier.m1954equalsimpl0(r13, r0)
            if (r0 == 0) goto Lc4
            long r0 = r12.getUtcTimeMillis()
            java.lang.Long r2 = r11.currentStartDateMillis
            if (r2 == 0) goto Lbb
            long r2 = r2.longValue()
            goto Lbd
        Lbb:
            r2 = -9223372036854775808
        Lbd:
            int r0 = (r0 > r2 ? 1 : (r0 == r2 ? 0 : -1))
            if (r0 >= 0) goto Lc4
        Lc1:
            java.lang.String r0 = r11.errorInvalidRangeInput
            return r0
        Lc4:
            java.lang.String r0 = ""
            return r0
        Lc7:
            java.lang.String r4 = r11.errorInvalidNotAllowed
            androidx.compose.material3.DatePickerFormatter r5 = r11.dateFormatter
            long r6 = r12.getUtcTimeMillis()
            java.lang.Long r6 = java.lang.Long.valueOf(r6)
            r9 = 4
            r10 = 0
            r8 = 0
            r7 = r14
            java.lang.String r5 = androidx.compose.material3.DatePickerFormatter.formatDate$default(r5, r6, r7, r8, r9, r10)
            java.lang.Object[] r5 = new java.lang.Object[]{r5}
            java.lang.Object[] r0 = java.util.Arrays.copyOf(r5, r0)
            java.lang.String r0 = java.lang.String.format(r4, r0)
            kotlin.jvm.internal.Intrinsics.checkNotNullExpressionValue(r0, r1)
            return r0
        */
        throw new UnsupportedOperationException("Method not decompiled: androidx.compose.material3.DateInputValidator.m1786validateXivgLIo(androidx.compose.material3.CalendarDate, int, java.util.Locale):java.lang.String");
    }
}
