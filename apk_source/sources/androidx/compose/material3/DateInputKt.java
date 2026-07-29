package androidx.compose.material3;

import androidx.autofill.HintConstants;
import androidx.compose.foundation.interaction.MutableInteractionSource;
import androidx.compose.foundation.layout.PaddingKt;
import androidx.compose.foundation.layout.PaddingValues;
import androidx.compose.foundation.layout.SizeKt;
import androidx.compose.foundation.text.KeyboardActions;
import androidx.compose.foundation.text.KeyboardOptions;
import androidx.compose.material3.Strings;
import androidx.compose.runtime.Composer;
import androidx.compose.runtime.ComposerKt;
import androidx.compose.runtime.MutableState;
import androidx.compose.runtime.RecomposeScopeImplKt;
import androidx.compose.runtime.ScopeUpdateScope;
import androidx.compose.runtime.SnapshotStateKt__SnapshotStateKt;
import androidx.compose.runtime.internal.ComposableLambdaKt;
import androidx.compose.runtime.saveable.RememberSaveableKt;
import androidx.compose.runtime.saveable.Saver;
import androidx.compose.ui.Modifier;
import androidx.compose.ui.graphics.Shape;
import androidx.compose.ui.semantics.SemanticsModifierKt;
import androidx.compose.ui.semantics.SemanticsPropertiesKt;
import androidx.compose.ui.semantics.SemanticsPropertyReceiver;
import androidx.compose.ui.text.TextLayoutResult;
import androidx.compose.ui.text.TextRange;
import androidx.compose.ui.text.TextRangeKt;
import androidx.compose.ui.text.TextStyle;
import androidx.compose.ui.text.font.FontFamily;
import androidx.compose.ui.text.font.FontStyle;
import androidx.compose.ui.text.font.FontWeight;
import androidx.compose.ui.text.input.ImeAction;
import androidx.compose.ui.text.input.KeyboardType;
import androidx.compose.ui.text.input.TextFieldValue;
import androidx.compose.ui.text.input.VisualTransformation;
import androidx.compose.ui.text.style.TextAlign;
import androidx.compose.ui.text.style.TextDecoration;
import androidx.compose.ui.unit.Dp;
import androidx.core.view.accessibility.AccessibilityEventCompat;
import androidx.profileinstaller.ProfileVerifier;
import java.util.Locale;
import kotlin.Metadata;
import kotlin.Unit;
import kotlin.jvm.functions.Function0;
import kotlin.jvm.functions.Function1;
import kotlin.jvm.functions.Function2;
import kotlin.jvm.internal.DefaultConstructorMarker;
import kotlin.jvm.internal.Intrinsics;
import kotlin.ranges.IntRange;
import kotlin.text.StringsKt;

/* compiled from: DateInput.kt */
@Metadata(d1 = {"\u0000\u0080\u0001\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0010\u0002\n\u0000\n\u0002\u0010\t\n\u0000\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\b\u0004\n\u0002\u0018\u0002\u001ad\u0010\u0007\u001a\u00020\b2\b\u0010\t\u001a\u0004\u0018\u00010\n2#\u0010\u000b\u001a\u001f\u0012\u0015\u0012\u0013\u0018\u00010\n¢\u0006\f\b\r\u0012\b\b\u000e\u0012\u0004\b\b(\u000f\u0012\u0004\u0012\u00020\b0\f2\u0006\u0010\u0010\u001a\u00020\u00112\u0006\u0010\u0012\u001a\u00020\u00132\u0006\u0010\u0014\u001a\u00020\u00152\u0006\u0010\u0016\u001a\u00020\u00172\u0006\u0010\u0018\u001a\u00020\u0019H\u0001¢\u0006\u0002\u0010\u001a\u001a\u0098\u0001\u0010\u001b\u001a\u00020\b2\u0006\u0010\u001c\u001a\u00020\u001d2\b\u0010\u001e\u001a\u0004\u0018\u00010\n2\u0014\u0010\u000b\u001a\u0010\u0012\u0006\u0012\u0004\u0018\u00010\n\u0012\u0004\u0012\u00020\b0\f2\u0006\u0010\u0010\u001a\u00020\u00112\u0013\u0010\u001f\u001a\u000f\u0012\u0004\u0012\u00020\b\u0018\u00010 ¢\u0006\u0002\b!2\u0013\u0010\"\u001a\u000f\u0012\u0004\u0012\u00020\b\u0018\u00010 ¢\u0006\u0002\b!2\u0006\u0010#\u001a\u00020$2\u0006\u0010%\u001a\u00020&2\u0006\u0010'\u001a\u00020(2\n\u0010)\u001a\u00060*j\u0002`+2\u0006\u0010\u0018\u001a\u00020\u0019H\u0001ø\u0001\u0000¢\u0006\u0004\b,\u0010-\"\u0014\u0010\u0000\u001a\u00020\u0001X\u0080\u0004¢\u0006\b\n\u0000\u001a\u0004\b\u0002\u0010\u0003\"\u0010\u0010\u0004\u001a\u00020\u0005X\u0082\u0004¢\u0006\u0004\n\u0002\u0010\u0006\u0082\u0002\u0007\n\u0005\b¡\u001e0\u0001¨\u0006.²\u0006\n\u0010/\u001a\u000200X\u008a\u008e\u0002"}, d2 = {"InputTextFieldPadding", "Landroidx/compose/foundation/layout/PaddingValues;", "getInputTextFieldPadding", "()Landroidx/compose/foundation/layout/PaddingValues;", "InputTextNonErroneousBottomPadding", "Landroidx/compose/ui/unit/Dp;", "F", "DateInputContent", "", "selectedDateMillis", "", "onDateSelectionChange", "Lkotlin/Function1;", "Lkotlin/ParameterName;", HintConstants.AUTOFILL_HINT_NAME, "dateInMillis", "calendarModel", "Landroidx/compose/material3/CalendarModel;", "yearRange", "Lkotlin/ranges/IntRange;", "dateFormatter", "Landroidx/compose/material3/DatePickerFormatter;", "selectableDates", "Landroidx/compose/material3/SelectableDates;", "colors", "Landroidx/compose/material3/DatePickerColors;", "(Ljava/lang/Long;Lkotlin/jvm/functions/Function1;Landroidx/compose/material3/CalendarModel;Lkotlin/ranges/IntRange;Landroidx/compose/material3/DatePickerFormatter;Landroidx/compose/material3/SelectableDates;Landroidx/compose/material3/DatePickerColors;Landroidx/compose/runtime/Composer;I)V", "DateInputTextField", "modifier", "Landroidx/compose/ui/Modifier;", "initialDateMillis", "label", "Lkotlin/Function0;", "Landroidx/compose/runtime/Composable;", "placeholder", "inputIdentifier", "Landroidx/compose/material3/InputIdentifier;", "dateInputValidator", "Landroidx/compose/material3/DateInputValidator;", "dateInputFormat", "Landroidx/compose/material3/DateInputFormat;", "locale", "Ljava/util/Locale;", "Landroidx/compose/material3/CalendarLocale;", "DateInputTextField-tQNruF0", "(Landroidx/compose/ui/Modifier;Ljava/lang/Long;Lkotlin/jvm/functions/Function1;Landroidx/compose/material3/CalendarModel;Lkotlin/jvm/functions/Function2;Lkotlin/jvm/functions/Function2;ILandroidx/compose/material3/DateInputValidator;Landroidx/compose/material3/DateInputFormat;Ljava/util/Locale;Landroidx/compose/material3/DatePickerColors;Landroidx/compose/runtime/Composer;II)V", "material3_release", "text", "Landroidx/compose/ui/text/input/TextFieldValue;"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class DateInputKt {
    private static final PaddingValues InputTextFieldPadding = PaddingKt.m559PaddingValuesa9UjIt4$default(Dp.m6094constructorimpl(24), Dp.m6094constructorimpl(10), Dp.m6094constructorimpl(24), 0.0f, 8, null);
    private static final float InputTextNonErroneousBottomPadding = Dp.m6094constructorimpl(16);

    public static final void DateInputContent(final Long selectedDateMillis, final Function1<? super Long, Unit> function1, final CalendarModel calendarModel, final IntRange yearRange, final DatePickerFormatter dateFormatter, final SelectableDates selectableDates, final DatePickerColors colors, Composer $composer, final int $changed) {
        Object value$iv;
        Locale defaultLocale;
        DateInputFormat dateInputFormat;
        int $dirty;
        Composer $composer2;
        Composer $composer3;
        Composer $composer4 = $composer.startRestartGroup(643325609);
        ComposerKt.sourceInformation($composer4, "C(DateInputContent)P(5,3!1,6,2,4)57@2329L15,58@2371L87,61@2486L45,62@2566L44,63@2644L45,64@2719L507,77@3315L42,78@3362L891:DateInput.kt#uh7d8r");
        int $dirty2 = $changed;
        if (($changed & 6) == 0) {
            $dirty2 |= $composer4.changed(selectedDateMillis) ? 4 : 2;
        }
        if (($changed & 48) == 0) {
            $dirty2 |= $composer4.changedInstance(function1) ? 32 : 16;
        }
        if (($changed & 384) == 0) {
            $dirty2 |= $composer4.changedInstance(calendarModel) ? 256 : 128;
        }
        if (($changed & 3072) == 0) {
            $dirty2 |= $composer4.changedInstance(yearRange) ? 2048 : 1024;
        }
        if (($changed & 24576) == 0) {
            $dirty2 |= ($changed & 32768) == 0 ? $composer4.changed(dateFormatter) : $composer4.changedInstance(dateFormatter) ? 16384 : 8192;
        }
        if ((196608 & $changed) == 0) {
            $dirty2 |= $composer4.changed(selectableDates) ? 131072 : 65536;
        }
        if ((1572864 & $changed) == 0) {
            $dirty2 |= $composer4.changed(colors) ? 1048576 : 524288;
        }
        int $dirty3 = $dirty2;
        if ((599187 & $dirty3) != 599186 || !$composer4.getSkipping()) {
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventStart(643325609, $dirty3, -1, "androidx.compose.material3.DateInputContent (DateInput.kt:55)");
            }
            Locale defaultLocale2 = ActualAndroid_androidKt.defaultLocale($composer4, 0);
            $composer4.startReplaceableGroup(-356766397);
            ComposerKt.sourceInformation($composer4, "CC(remember):DateInput.kt#9igjgp");
            boolean invalid$iv = $composer4.changed(defaultLocale2);
            Object it$iv = $composer4.rememberedValue();
            if (invalid$iv || it$iv == Composer.INSTANCE.getEmpty()) {
                value$iv = calendarModel.getDateInputFormat(defaultLocale2);
                $composer4.updateRememberedValue(value$iv);
            } else {
                value$iv = it$iv;
            }
            DateInputFormat dateInputFormat2 = (DateInputFormat) value$iv;
            $composer4.endReplaceableGroup();
            Strings.Companion companion = Strings.INSTANCE;
            String errorDatePattern = Strings_androidKt.m2306getStringNWtq28(Strings.m2237constructorimpl(R.string.m3c_date_input_invalid_for_pattern), $composer4, 0);
            Strings.Companion companion2 = Strings.INSTANCE;
            String errorDateOutOfYearRange = Strings_androidKt.m2306getStringNWtq28(Strings.m2237constructorimpl(R.string.m3c_date_input_invalid_year_range), $composer4, 0);
            Strings.Companion companion3 = Strings.INSTANCE;
            String errorInvalidNotAllowed = Strings_androidKt.m2306getStringNWtq28(Strings.m2237constructorimpl(R.string.m3c_date_input_invalid_not_allowed), $composer4, 0);
            $composer4.startReplaceableGroup(-356766049);
            ComposerKt.sourceInformation($composer4, "CC(remember):DateInput.kt#9igjgp");
            boolean invalid$iv2 = $composer4.changed(dateInputFormat2) | ((57344 & $dirty3) == 16384 || ((32768 & $dirty3) != 0 && $composer4.changed(dateFormatter)));
            Object value$iv2 = $composer4.rememberedValue();
            if (invalid$iv2 || value$iv2 == Composer.INSTANCE.getEmpty()) {
                defaultLocale = defaultLocale2;
                dateInputFormat = dateInputFormat2;
                $dirty = $dirty3;
                $composer2 = $composer4;
                value$iv2 = new DateInputValidator(yearRange, selectableDates, dateInputFormat2, dateFormatter, errorDatePattern, errorDateOutOfYearRange, errorInvalidNotAllowed, "", null, null, 768, null);
                $composer4.updateRememberedValue(value$iv2);
            } else {
                defaultLocale = defaultLocale2;
                dateInputFormat = dateInputFormat2;
                $dirty = $dirty3;
                $composer2 = $composer4;
            }
            DateInputValidator dateInputValidator = (DateInputValidator) value$iv2;
            $composer2.endReplaceableGroup();
            final String pattern = dateInputFormat.getPatternWithDelimiters().toUpperCase(Locale.ROOT);
            Intrinsics.checkNotNullExpressionValue(pattern, "this as java.lang.String).toUpperCase(Locale.ROOT)");
            Strings.Companion companion4 = Strings.INSTANCE;
            Composer $composer5 = $composer2;
            final String labelText = Strings_androidKt.m2306getStringNWtq28(Strings.m2237constructorimpl(R.string.m3c_date_input_label), $composer5, 0);
            Modifier padding = PaddingKt.padding(SizeKt.fillMaxWidth$default(Modifier.INSTANCE, 0.0f, 1, null), InputTextFieldPadding);
            int m1959getSingleDateInputJ2x2o4M = InputIdentifier.INSTANCE.m1959getSingleDateInputJ2x2o4M();
            dateInputValidator.setCurrentStartDateMillis$material3_release(selectedDateMillis);
            $composer3 = $composer5;
            m1785DateInputTextFieldtQNruF0(padding, selectedDateMillis, function1, calendarModel, ComposableLambdaKt.composableLambda($composer5, -1819015125, true, new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.DateInputKt$DateInputContent$2
                /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
                {
                    super(2);
                }

                @Override // kotlin.jvm.functions.Function2
                public /* bridge */ /* synthetic */ Unit invoke(Composer composer, Integer num) {
                    invoke(composer, num.intValue());
                    return Unit.INSTANCE;
                }

                public final void invoke(Composer $composer6, int $changed2) {
                    Object value$iv3;
                    ComposerKt.sourceInformation($composer6, "C86@3631L47,84@3552L127:DateInput.kt#uh7d8r");
                    if (($changed2 & 3) == 2 && $composer6.getSkipping()) {
                        $composer6.skipToGroupEnd();
                        return;
                    }
                    if (ComposerKt.isTraceInProgress()) {
                        ComposerKt.traceEventStart(-1819015125, $changed2, -1, "androidx.compose.material3.DateInputContent.<anonymous> (DateInput.kt:84)");
                    }
                    String str = labelText;
                    Modifier.Companion companion5 = Modifier.INSTANCE;
                    $composer6.startReplaceableGroup(-694340528);
                    ComposerKt.sourceInformation($composer6, "CC(remember):DateInput.kt#9igjgp");
                    boolean invalid$iv3 = $composer6.changed(labelText) | $composer6.changed(pattern);
                    final String str2 = labelText;
                    final String str3 = pattern;
                    Object it$iv2 = $composer6.rememberedValue();
                    if (invalid$iv3 || it$iv2 == Composer.INSTANCE.getEmpty()) {
                        value$iv3 = new Function1<SemanticsPropertyReceiver, Unit>() { // from class: androidx.compose.material3.DateInputKt$DateInputContent$2$1$1
                            /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
                            {
                                super(1);
                            }

                            @Override // kotlin.jvm.functions.Function1
                            public /* bridge */ /* synthetic */ Unit invoke(SemanticsPropertyReceiver semanticsPropertyReceiver) {
                                invoke2(semanticsPropertyReceiver);
                                return Unit.INSTANCE;
                            }

                            /* renamed from: invoke, reason: avoid collision after fix types in other method */
                            public final void invoke2(SemanticsPropertyReceiver $this$semantics) {
                                SemanticsPropertiesKt.setContentDescription($this$semantics, str2 + ", " + str3);
                            }
                        };
                        $composer6.updateRememberedValue(value$iv3);
                    } else {
                        value$iv3 = it$iv2;
                    }
                    $composer6.endReplaceableGroup();
                    TextKt.m2464Text4IGK_g(str, SemanticsModifierKt.semantics$default(companion5, false, (Function1) value$iv3, 1, null), 0L, 0L, (FontStyle) null, (FontWeight) null, (FontFamily) null, 0L, (TextDecoration) null, (TextAlign) null, 0L, 0, false, 0, 0, (Function1<? super TextLayoutResult, Unit>) null, (TextStyle) null, $composer6, 0, 0, 131068);
                    if (ComposerKt.isTraceInProgress()) {
                        ComposerKt.traceEventEnd();
                    }
                }
            }), ComposableLambdaKt.composableLambda($composer5, -564233108, true, new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.DateInputKt$DateInputContent$3
                /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
                {
                    super(2);
                }

                @Override // kotlin.jvm.functions.Function2
                public /* bridge */ /* synthetic */ Unit invoke(Composer composer, Integer num) {
                    invoke(composer, num.intValue());
                    return Unit.INSTANCE;
                }

                public final void invoke(Composer $composer6, int $changed2) {
                    ComposerKt.sourceInformation($composer6, "C88@3715L59:DateInput.kt#uh7d8r");
                    if (($changed2 & 3) == 2 && $composer6.getSkipping()) {
                        $composer6.skipToGroupEnd();
                        return;
                    }
                    if (ComposerKt.isTraceInProgress()) {
                        ComposerKt.traceEventStart(-564233108, $changed2, -1, "androidx.compose.material3.DateInputContent.<anonymous> (DateInput.kt:88)");
                    }
                    TextKt.m2464Text4IGK_g(pattern, SemanticsModifierKt.clearAndSetSemantics(Modifier.INSTANCE, new Function1<SemanticsPropertyReceiver, Unit>() { // from class: androidx.compose.material3.DateInputKt$DateInputContent$3.1
                        @Override // kotlin.jvm.functions.Function1
                        public /* bridge */ /* synthetic */ Unit invoke(SemanticsPropertyReceiver semanticsPropertyReceiver) {
                            invoke2(semanticsPropertyReceiver);
                            return Unit.INSTANCE;
                        }

                        /* renamed from: invoke, reason: avoid collision after fix types in other method */
                        public final void invoke2(SemanticsPropertyReceiver $this$clearAndSetSemantics) {
                        }
                    }), 0L, 0L, (FontStyle) null, (FontWeight) null, (FontFamily) null, 0L, (TextDecoration) null, (TextAlign) null, 0L, 0, false, 0, 0, (Function1<? super TextLayoutResult, Unit>) null, (TextStyle) null, $composer6, 0, 0, 131068);
                    if (ComposerKt.isTraceInProgress()) {
                        ComposerKt.traceEventEnd();
                    }
                }
            }), m1959getSingleDateInputJ2x2o4M, dateInputValidator, dateInputFormat, defaultLocale, colors, $composer5, (($dirty << 3) & 112) | 1794054 | (($dirty << 3) & 896) | (($dirty << 3) & 7168), ($dirty >> 18) & 14);
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventEnd();
            }
        } else {
            $composer4.skipToGroupEnd();
            $composer3 = $composer4;
        }
        ScopeUpdateScope endRestartGroup = $composer3.endRestartGroup();
        if (endRestartGroup != null) {
            endRestartGroup.updateScope(new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.DateInputKt$DateInputContent$4
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

                public final void invoke(Composer composer, int i) {
                    DateInputKt.DateInputContent(selectedDateMillis, function1, calendarModel, yearRange, dateFormatter, selectableDates, colors, composer, RecomposeScopeImplKt.updateChangedFlags($changed | 1));
                }
            });
        }
    }

    /* renamed from: DateInputTextField-tQNruF0, reason: not valid java name */
    public static final void m1785DateInputTextFieldtQNruF0(final Modifier modifier, final Long initialDateMillis, final Function1<? super Long, Unit> function1, final CalendarModel calendarModel, final Function2<? super Composer, ? super Integer, Unit> function2, final Function2<? super Composer, ? super Integer, Unit> function22, final int inputIdentifier, final DateInputValidator dateInputValidator, final DateInputFormat dateInputFormat, final Locale locale, final DatePickerColors colors, Composer $composer, final int $changed, final int $changed1) {
        Object value$iv;
        MutableState errorText;
        int $dirty;
        String str;
        float f;
        Object value$iv2;
        Composer $composer2 = $composer.startRestartGroup(-857008589);
        ComposerKt.sourceInformation($composer2, "C(DateInputTextField)P(8,4,9!1,6,10,5:c#material3.InputIdentifier,3,2,7)117@4757L39,118@4865L388,118@4813L440,135@5324L1418,178@7156L88,133@5259L2503:DateInput.kt#uh7d8r");
        int $dirty2 = $changed;
        int $dirty1 = $changed1;
        if (($changed & 6) == 0) {
            $dirty2 |= $composer2.changed(modifier) ? 4 : 2;
        }
        if (($changed & 48) == 0) {
            $dirty2 |= $composer2.changed(initialDateMillis) ? 32 : 16;
        }
        if (($changed & 384) == 0) {
            $dirty2 |= $composer2.changedInstance(function1) ? 256 : 128;
        }
        if (($changed & 3072) == 0) {
            $dirty2 |= $composer2.changedInstance(calendarModel) ? 2048 : 1024;
        }
        if (($changed & 24576) == 0) {
            $dirty2 |= $composer2.changedInstance(function2) ? 16384 : 8192;
        }
        if (($changed & ProfileVerifier.CompilationStatus.RESULT_CODE_ERROR_CANT_WRITE_PROFILE_VERIFICATION_RESULT_CACHE_FILE) == 0) {
            $dirty2 |= $composer2.changedInstance(function22) ? 131072 : 65536;
        }
        if (($changed & 1572864) == 0) {
            $dirty2 |= $composer2.changed(inputIdentifier) ? 1048576 : 524288;
        }
        if (($changed & 12582912) == 0) {
            $dirty2 |= $composer2.changed(dateInputValidator) ? 8388608 : 4194304;
        }
        if (($changed & 100663296) == 0) {
            $dirty2 |= $composer2.changed(dateInputFormat) ? AccessibilityEventCompat.TYPE_VIEW_TARGETED_BY_SCROLL : 33554432;
        }
        if (($changed & 805306368) == 0) {
            $dirty2 |= $composer2.changedInstance(locale) ? 536870912 : 268435456;
        }
        if (($changed1 & 6) == 0) {
            $dirty1 |= $composer2.changed(colors) ? 4 : 2;
        }
        int $dirty12 = $dirty1;
        if ((306783379 & $dirty2) != 306783378 || ($dirty12 & 3) != 2 || !$composer2.getSkipping()) {
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventStart(-857008589, $dirty2, $dirty12, "androidx.compose.material3.DateInputTextField (DateInput.kt:116)");
            }
            int $dirty3 = $dirty2;
            final MutableState errorText2 = (MutableState) RememberSaveableKt.m3363rememberSaveable(new Object[0], (Saver) null, (String) null, (Function0) new Function0<MutableState<String>>() { // from class: androidx.compose.material3.DateInputKt$DateInputTextField$errorText$1
                /* JADX WARN: Can't rename method to resolve collision */
                @Override // kotlin.jvm.functions.Function0
                public final MutableState<String> invoke() {
                    return SnapshotStateKt__SnapshotStateKt.mutableStateOf$default("", null, 2, null);
                }
            }, $composer2, 3072, 6);
            Object[] objArr = new Object[0];
            Saver<TextFieldValue, Object> saver = TextFieldValue.INSTANCE.getSaver();
            $composer2.startReplaceableGroup(1947288557);
            ComposerKt.sourceInformation($composer2, "CC(remember):DateInput.kt#9igjgp");
            boolean invalid$iv = (($dirty3 & 112) == 32) | $composer2.changedInstance(calendarModel) | (($dirty3 & 234881024) == 67108864) | $composer2.changedInstance(locale);
            Object it$iv = $composer2.rememberedValue();
            if (invalid$iv || it$iv == Composer.INSTANCE.getEmpty()) {
                value$iv = (Function0) new Function0<MutableState<TextFieldValue>>() { // from class: androidx.compose.material3.DateInputKt$DateInputTextField$text$2$1
                    /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
                    {
                        super(0);
                    }

                    /* JADX WARN: Can't rename method to resolve collision */
                    @Override // kotlin.jvm.functions.Function0
                    public final MutableState<TextFieldValue> invoke() {
                        String str2;
                        Long l = initialDateMillis;
                        if (l != null) {
                            CalendarModel calendarModel2 = calendarModel;
                            DateInputFormat dateInputFormat2 = dateInputFormat;
                            Locale locale2 = locale;
                            long it = l.longValue();
                            String formatWithPattern = calendarModel2.formatWithPattern(it, dateInputFormat2.getPatternWithoutDelimiters(), locale2);
                            if (formatWithPattern != null) {
                                str2 = formatWithPattern;
                                return SnapshotStateKt__SnapshotStateKt.mutableStateOf$default(new TextFieldValue(str2, TextRangeKt.TextRange(0, 0), (TextRange) null, 4, (DefaultConstructorMarker) null), null, 2, null);
                            }
                        }
                        str2 = "";
                        return SnapshotStateKt__SnapshotStateKt.mutableStateOf$default(new TextFieldValue(str2, TextRangeKt.TextRange(0, 0), (TextRange) null, 4, (DefaultConstructorMarker) null), null, 2, null);
                    }
                };
                $composer2.updateRememberedValue(value$iv);
            } else {
                value$iv = it$iv;
            }
            $composer2.endReplaceableGroup();
            final MutableState text$delegate = RememberSaveableKt.rememberSaveable(objArr, (Saver) saver, (String) null, (Function0) value$iv, $composer2, 0, 4);
            TextFieldValue DateInputTextField_tQNruF0$lambda$4 = DateInputTextField_tQNruF0$lambda$4(text$delegate);
            $composer2.startReplaceableGroup(1947289016);
            ComposerKt.sourceInformation($composer2, "CC(remember):DateInput.kt#9igjgp");
            boolean invalid$iv2 = $composer2.changed(text$delegate) | (($dirty3 & 234881024) == 67108864) | $composer2.changed(errorText2) | (($dirty3 & 896) == 256) | $composer2.changedInstance(calendarModel) | (($dirty3 & 29360128) == 8388608) | (($dirty3 & 3670016) == 1048576) | $composer2.changedInstance(locale);
            Object value$iv3 = $composer2.rememberedValue();
            if (invalid$iv2 || value$iv3 == Composer.INSTANCE.getEmpty()) {
                errorText = errorText2;
                $dirty = $dirty3;
                str = "CC(remember):DateInput.kt#9igjgp";
                value$iv3 = new Function1<TextFieldValue, Unit>() { // from class: androidx.compose.material3.DateInputKt$DateInputTextField$1$1
                    /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
                    /* JADX WARN: Multi-variable type inference failed */
                    {
                        super(1);
                    }

                    @Override // kotlin.jvm.functions.Function1
                    public /* bridge */ /* synthetic */ Unit invoke(TextFieldValue textFieldValue) {
                        invoke2(textFieldValue);
                        return Unit.INSTANCE;
                    }

                    /* renamed from: invoke, reason: avoid collision after fix types in other method */
                    public final void invoke2(TextFieldValue input) {
                        CharSequence $this$all$iv;
                        if (input.getText().length() <= DateInputFormat.this.getPatternWithoutDelimiters().length()) {
                            CharSequence $this$all$iv2 = input.getText();
                            int i = 0;
                            while (true) {
                                if (i < $this$all$iv2.length()) {
                                    char element$iv = $this$all$iv2.charAt(i);
                                    if (!Character.isDigit(element$iv)) {
                                        $this$all$iv = null;
                                        break;
                                    }
                                    i++;
                                } else {
                                    $this$all$iv = 1;
                                    break;
                                }
                            }
                            if ($this$all$iv == null) {
                                return;
                            }
                            text$delegate.setValue(input);
                            String trimmedText = StringsKt.trim((CharSequence) input.getText()).toString();
                            Long l = null;
                            if ((trimmedText.length() == 0) || trimmedText.length() < DateInputFormat.this.getPatternWithoutDelimiters().length()) {
                                errorText2.setValue("");
                                function1.invoke(null);
                                return;
                            }
                            CalendarDate parsedDate = calendarModel.parse(trimmedText, DateInputFormat.this.getPatternWithoutDelimiters());
                            errorText2.setValue(dateInputValidator.m1786validateXivgLIo(parsedDate, inputIdentifier, locale));
                            Function1<Long, Unit> function12 = function1;
                            if ((errorText2.getValue().length() == 0) && parsedDate != null) {
                                l = Long.valueOf(parsedDate.getUtcTimeMillis());
                            }
                            function12.invoke(l);
                        }
                    }
                };
                $composer2.updateRememberedValue(value$iv3);
            } else {
                errorText = errorText2;
                $dirty = $dirty3;
                str = "CC(remember):DateInput.kt#9igjgp";
            }
            Function1 function12 = (Function1) value$iv3;
            $composer2.endReplaceableGroup();
            if (StringsKt.isBlank((CharSequence) errorText.getValue())) {
                f = InputTextNonErroneousBottomPadding;
            } else {
                f = Dp.m6094constructorimpl(0);
            }
            Modifier m566paddingqDBjuR0$default = PaddingKt.m566paddingqDBjuR0$default(modifier, 0.0f, 0.0f, 0.0f, f, 7, null);
            $composer2.startReplaceableGroup(1947290848);
            ComposerKt.sourceInformation($composer2, str);
            final MutableState errorText3 = errorText;
            boolean invalid$iv3 = $composer2.changed(errorText3);
            Object it$iv2 = $composer2.rememberedValue();
            if (invalid$iv3 || it$iv2 == Composer.INSTANCE.getEmpty()) {
                value$iv2 = new Function1<SemanticsPropertyReceiver, Unit>() { // from class: androidx.compose.material3.DateInputKt$DateInputTextField$2$1
                    /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
                    {
                        super(1);
                    }

                    @Override // kotlin.jvm.functions.Function1
                    public /* bridge */ /* synthetic */ Unit invoke(SemanticsPropertyReceiver semanticsPropertyReceiver) {
                        invoke2(semanticsPropertyReceiver);
                        return Unit.INSTANCE;
                    }

                    /* renamed from: invoke, reason: avoid collision after fix types in other method */
                    public final void invoke2(SemanticsPropertyReceiver $this$semantics) {
                        if (!StringsKt.isBlank(errorText3.getValue())) {
                            SemanticsPropertiesKt.error($this$semantics, errorText3.getValue());
                        }
                    }
                };
                $composer2.updateRememberedValue(value$iv2);
            } else {
                value$iv2 = it$iv2;
            }
            $composer2.endReplaceableGroup();
            OutlinedTextFieldKt.OutlinedTextField(DateInputTextField_tQNruF0$lambda$4, (Function1<? super TextFieldValue, Unit>) function12, SemanticsModifierKt.semantics$default(m566paddingqDBjuR0$default, false, (Function1) value$iv2, 1, null), false, false, (TextStyle) null, function2, function22, (Function2<? super Composer, ? super Integer, Unit>) null, (Function2<? super Composer, ? super Integer, Unit>) null, (Function2<? super Composer, ? super Integer, Unit>) null, (Function2<? super Composer, ? super Integer, Unit>) null, (Function2<? super Composer, ? super Integer, Unit>) ComposableLambdaKt.composableLambda($composer2, -591991974, true, new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.DateInputKt$DateInputTextField$3
                /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
                {
                    super(2);
                }

                @Override // kotlin.jvm.functions.Function2
                public /* bridge */ /* synthetic */ Unit invoke(Composer composer, Integer num) {
                    invoke(composer, num.intValue());
                    return Unit.INSTANCE;
                }

                public final void invoke(Composer $composer3, int $changed2) {
                    ComposerKt.sourceInformation($composer3, "C183@7365L21:DateInput.kt#uh7d8r");
                    if (($changed2 & 3) == 2 && $composer3.getSkipping()) {
                        $composer3.skipToGroupEnd();
                        return;
                    }
                    if (ComposerKt.isTraceInProgress()) {
                        ComposerKt.traceEventStart(-591991974, $changed2, -1, "androidx.compose.material3.DateInputTextField.<anonymous> (DateInput.kt:183)");
                    }
                    if (!StringsKt.isBlank(errorText3.getValue())) {
                        TextKt.m2464Text4IGK_g(errorText3.getValue(), (Modifier) null, 0L, 0L, (FontStyle) null, (FontWeight) null, (FontFamily) null, 0L, (TextDecoration) null, (TextAlign) null, 0L, 0, false, 0, 0, (Function1<? super TextLayoutResult, Unit>) null, (TextStyle) null, $composer3, 0, 0, 131070);
                    }
                    if (ComposerKt.isTraceInProgress()) {
                        ComposerKt.traceEventEnd();
                    }
                }
            }), !StringsKt.isBlank((CharSequence) errorText3.getValue()), (VisualTransformation) new DateVisualTransformation(dateInputFormat), new KeyboardOptions(0, false, KeyboardType.INSTANCE.m5798getNumberPjHm6EE(), ImeAction.INSTANCE.m5748getDoneeUduSuo(), null, 17, null), (KeyboardActions) null, true, 0, 0, (MutableInteractionSource) null, (Shape) null, colors.getDateTextFieldColors(), $composer2, (($dirty << 6) & 3670016) | (($dirty << 6) & 29360128), 12779904, 0, 4001592);
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventEnd();
            }
        } else {
            $composer2.skipToGroupEnd();
        }
        ScopeUpdateScope endRestartGroup = $composer2.endRestartGroup();
        if (endRestartGroup != null) {
            endRestartGroup.updateScope(new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.DateInputKt$DateInputTextField$4
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

                public final void invoke(Composer composer, int i) {
                    DateInputKt.m1785DateInputTextFieldtQNruF0(Modifier.this, initialDateMillis, function1, calendarModel, function2, function22, inputIdentifier, dateInputValidator, dateInputFormat, locale, colors, composer, RecomposeScopeImplKt.updateChangedFlags($changed | 1), RecomposeScopeImplKt.updateChangedFlags($changed1));
                }
            });
        }
    }

    private static final TextFieldValue DateInputTextField_tQNruF0$lambda$4(MutableState<TextFieldValue> mutableState) {
        MutableState<TextFieldValue> $this$getValue$iv = mutableState;
        return $this$getValue$iv.getValue();
    }

    public static final PaddingValues getInputTextFieldPadding() {
        return InputTextFieldPadding;
    }
}
