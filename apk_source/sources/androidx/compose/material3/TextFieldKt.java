package androidx.compose.material3;

import androidx.compose.foundation.BorderStroke;
import androidx.compose.foundation.interaction.InteractionSourceKt;
import androidx.compose.foundation.interaction.MutableInteractionSource;
import androidx.compose.foundation.layout.PaddingValues;
import androidx.compose.foundation.layout.SizeKt;
import androidx.compose.foundation.text.BasicTextFieldKt;
import androidx.compose.foundation.text.KeyboardActions;
import androidx.compose.foundation.text.KeyboardOptions;
import androidx.compose.foundation.text.selection.TextSelectionColorsKt;
import androidx.compose.material3.Strings;
import androidx.compose.runtime.Composer;
import androidx.compose.runtime.ComposerKt;
import androidx.compose.runtime.CompositionLocalKt;
import androidx.compose.runtime.ProvidableCompositionLocal;
import androidx.compose.runtime.ProvidedValue;
import androidx.compose.runtime.RecomposeScopeImplKt;
import androidx.compose.runtime.ScopeUpdateScope;
import androidx.compose.runtime.internal.ComposableLambdaKt;
import androidx.compose.ui.Alignment;
import androidx.compose.ui.Modifier;
import androidx.compose.ui.draw.DrawModifierKt;
import androidx.compose.ui.geometry.OffsetKt;
import androidx.compose.ui.geometry.Size;
import androidx.compose.ui.graphics.Color;
import androidx.compose.ui.graphics.Shadow;
import androidx.compose.ui.graphics.Shape;
import androidx.compose.ui.graphics.SolidColor;
import androidx.compose.ui.graphics.drawscope.ContentDrawScope;
import androidx.compose.ui.graphics.drawscope.DrawScope;
import androidx.compose.ui.graphics.drawscope.DrawStyle;
import androidx.compose.ui.layout.Placeable;
import androidx.compose.ui.text.PlatformTextStyle;
import androidx.compose.ui.text.TextLayoutResult;
import androidx.compose.ui.text.TextStyle;
import androidx.compose.ui.text.font.FontFamily;
import androidx.compose.ui.text.font.FontStyle;
import androidx.compose.ui.text.font.FontSynthesis;
import androidx.compose.ui.text.font.FontWeight;
import androidx.compose.ui.text.input.TextFieldValue;
import androidx.compose.ui.text.input.VisualTransformation;
import androidx.compose.ui.text.intl.LocaleList;
import androidx.compose.ui.text.style.BaselineShift;
import androidx.compose.ui.text.style.LineHeightStyle;
import androidx.compose.ui.text.style.TextDecoration;
import androidx.compose.ui.text.style.TextGeometricTransform;
import androidx.compose.ui.text.style.TextIndent;
import androidx.compose.ui.text.style.TextMotion;
import androidx.compose.ui.unit.Constraints;
import androidx.compose.ui.unit.Dp;
import androidx.compose.ui.unit.IntOffset;
import androidx.compose.ui.util.MathHelpersKt;
import androidx.core.view.accessibility.AccessibilityEventCompat;
import androidx.profileinstaller.ProfileVerifier;
import kotlin.Deprecated;
import kotlin.DeprecationLevel;
import kotlin.Metadata;
import kotlin.Unit;
import kotlin.comparisons.ComparisonsKt;
import kotlin.jvm.functions.Function1;
import kotlin.jvm.functions.Function2;
import kotlin.jvm.functions.Function3;
import kotlin.jvm.internal.DefaultConstructorMarker;
import kotlin.math.MathKt;

/* compiled from: TextField.kt */
@Metadata(d1 = {"\u0000¢\u0001\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0004\n\u0002\u0010\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010\u000b\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\b\b\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0010\b\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0010\u000e\n\u0002\b\u0007\n\u0002\u0010\u0007\n\u0002\b\u0003\n\u0002\u0018\u0002\n\u0002\b\u000b\n\u0002\u0018\u0002\n\u0002\b\u000f\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0018\u0002\n\u0002\b\u000f\u001aÖ\u0002\u0010\u0005\u001a\u00020\u00062\u0006\u0010\u0007\u001a\u00020\b2\u0012\u0010\t\u001a\u000e\u0012\u0004\u0012\u00020\b\u0012\u0004\u0012\u00020\u00060\n2\b\b\u0002\u0010\u000b\u001a\u00020\f2\b\b\u0002\u0010\r\u001a\u00020\u000e2\b\b\u0002\u0010\u000f\u001a\u00020\u000e2\b\b\u0002\u0010\u0010\u001a\u00020\u00112\u0015\b\u0002\u0010\u0012\u001a\u000f\u0012\u0004\u0012\u00020\u0006\u0018\u00010\u0013¢\u0006\u0002\b\u00142\u0015\b\u0002\u0010\u0015\u001a\u000f\u0012\u0004\u0012\u00020\u0006\u0018\u00010\u0013¢\u0006\u0002\b\u00142\u0015\b\u0002\u0010\u0016\u001a\u000f\u0012\u0004\u0012\u00020\u0006\u0018\u00010\u0013¢\u0006\u0002\b\u00142\u0015\b\u0002\u0010\u0017\u001a\u000f\u0012\u0004\u0012\u00020\u0006\u0018\u00010\u0013¢\u0006\u0002\b\u00142\u0015\b\u0002\u0010\u0018\u001a\u000f\u0012\u0004\u0012\u00020\u0006\u0018\u00010\u0013¢\u0006\u0002\b\u00142\u0015\b\u0002\u0010\u0019\u001a\u000f\u0012\u0004\u0012\u00020\u0006\u0018\u00010\u0013¢\u0006\u0002\b\u00142\u0015\b\u0002\u0010\u001a\u001a\u000f\u0012\u0004\u0012\u00020\u0006\u0018\u00010\u0013¢\u0006\u0002\b\u00142\b\b\u0002\u0010\u001b\u001a\u00020\u000e2\b\b\u0002\u0010\u001c\u001a\u00020\u001d2\b\b\u0002\u0010\u001e\u001a\u00020\u001f2\b\b\u0002\u0010 \u001a\u00020!2\b\b\u0002\u0010\"\u001a\u00020\u000e2\b\b\u0002\u0010#\u001a\u00020$2\b\b\u0002\u0010%\u001a\u00020$2\b\b\u0002\u0010&\u001a\u00020'2\b\b\u0002\u0010(\u001a\u00020)2\b\b\u0002\u0010*\u001a\u00020+H\u0007¢\u0006\u0002\u0010,\u001a¨\u0002\u0010\u0005\u001a\u00020\u00062\u0006\u0010\u0007\u001a\u00020\b2\u0012\u0010\t\u001a\u000e\u0012\u0004\u0012\u00020\b\u0012\u0004\u0012\u00020\u00060\n2\b\b\u0002\u0010\u000b\u001a\u00020\f2\b\b\u0002\u0010\r\u001a\u00020\u000e2\b\b\u0002\u0010\u000f\u001a\u00020\u000e2\b\b\u0002\u0010\u0010\u001a\u00020\u00112\u0015\b\u0002\u0010\u0012\u001a\u000f\u0012\u0004\u0012\u00020\u0006\u0018\u00010\u0013¢\u0006\u0002\b\u00142\u0015\b\u0002\u0010\u0015\u001a\u000f\u0012\u0004\u0012\u00020\u0006\u0018\u00010\u0013¢\u0006\u0002\b\u00142\u0015\b\u0002\u0010\u0016\u001a\u000f\u0012\u0004\u0012\u00020\u0006\u0018\u00010\u0013¢\u0006\u0002\b\u00142\u0015\b\u0002\u0010\u0017\u001a\u000f\u0012\u0004\u0012\u00020\u0006\u0018\u00010\u0013¢\u0006\u0002\b\u00142\u0015\b\u0002\u0010\u001a\u001a\u000f\u0012\u0004\u0012\u00020\u0006\u0018\u00010\u0013¢\u0006\u0002\b\u00142\b\b\u0002\u0010\u001b\u001a\u00020\u000e2\b\b\u0002\u0010\u001c\u001a\u00020\u001d2\b\b\u0002\u0010\u001e\u001a\u00020\u001f2\b\b\u0002\u0010 \u001a\u00020!2\b\b\u0002\u0010\"\u001a\u00020\u000e2\b\b\u0002\u0010#\u001a\u00020$2\b\b\u0002\u0010%\u001a\u00020$2\b\b\u0002\u0010&\u001a\u00020'2\b\b\u0002\u0010(\u001a\u00020)2\b\b\u0002\u0010*\u001a\u00020+H\u0007¢\u0006\u0002\u0010-\u001aÖ\u0002\u0010\u0005\u001a\u00020\u00062\u0006\u0010\u0007\u001a\u00020.2\u0012\u0010\t\u001a\u000e\u0012\u0004\u0012\u00020.\u0012\u0004\u0012\u00020\u00060\n2\b\b\u0002\u0010\u000b\u001a\u00020\f2\b\b\u0002\u0010\r\u001a\u00020\u000e2\b\b\u0002\u0010\u000f\u001a\u00020\u000e2\b\b\u0002\u0010\u0010\u001a\u00020\u00112\u0015\b\u0002\u0010\u0012\u001a\u000f\u0012\u0004\u0012\u00020\u0006\u0018\u00010\u0013¢\u0006\u0002\b\u00142\u0015\b\u0002\u0010\u0015\u001a\u000f\u0012\u0004\u0012\u00020\u0006\u0018\u00010\u0013¢\u0006\u0002\b\u00142\u0015\b\u0002\u0010\u0016\u001a\u000f\u0012\u0004\u0012\u00020\u0006\u0018\u00010\u0013¢\u0006\u0002\b\u00142\u0015\b\u0002\u0010\u0017\u001a\u000f\u0012\u0004\u0012\u00020\u0006\u0018\u00010\u0013¢\u0006\u0002\b\u00142\u0015\b\u0002\u0010\u0018\u001a\u000f\u0012\u0004\u0012\u00020\u0006\u0018\u00010\u0013¢\u0006\u0002\b\u00142\u0015\b\u0002\u0010\u0019\u001a\u000f\u0012\u0004\u0012\u00020\u0006\u0018\u00010\u0013¢\u0006\u0002\b\u00142\u0015\b\u0002\u0010\u001a\u001a\u000f\u0012\u0004\u0012\u00020\u0006\u0018\u00010\u0013¢\u0006\u0002\b\u00142\b\b\u0002\u0010\u001b\u001a\u00020\u000e2\b\b\u0002\u0010\u001c\u001a\u00020\u001d2\b\b\u0002\u0010\u001e\u001a\u00020\u001f2\b\b\u0002\u0010 \u001a\u00020!2\b\b\u0002\u0010\"\u001a\u00020\u000e2\b\b\u0002\u0010#\u001a\u00020$2\b\b\u0002\u0010%\u001a\u00020$2\b\b\u0002\u0010&\u001a\u00020'2\b\b\u0002\u0010(\u001a\u00020)2\b\b\u0002\u0010*\u001a\u00020+H\u0007¢\u0006\u0002\u0010/\u001a¨\u0002\u0010\u0005\u001a\u00020\u00062\u0006\u0010\u0007\u001a\u00020.2\u0012\u0010\t\u001a\u000e\u0012\u0004\u0012\u00020.\u0012\u0004\u0012\u00020\u00060\n2\b\b\u0002\u0010\u000b\u001a\u00020\f2\b\b\u0002\u0010\r\u001a\u00020\u000e2\b\b\u0002\u0010\u000f\u001a\u00020\u000e2\b\b\u0002\u0010\u0010\u001a\u00020\u00112\u0015\b\u0002\u0010\u0012\u001a\u000f\u0012\u0004\u0012\u00020\u0006\u0018\u00010\u0013¢\u0006\u0002\b\u00142\u0015\b\u0002\u0010\u0015\u001a\u000f\u0012\u0004\u0012\u00020\u0006\u0018\u00010\u0013¢\u0006\u0002\b\u00142\u0015\b\u0002\u0010\u0016\u001a\u000f\u0012\u0004\u0012\u00020\u0006\u0018\u00010\u0013¢\u0006\u0002\b\u00142\u0015\b\u0002\u0010\u0017\u001a\u000f\u0012\u0004\u0012\u00020\u0006\u0018\u00010\u0013¢\u0006\u0002\b\u00142\u0015\b\u0002\u0010\u001a\u001a\u000f\u0012\u0004\u0012\u00020\u0006\u0018\u00010\u0013¢\u0006\u0002\b\u00142\b\b\u0002\u0010\u001b\u001a\u00020\u000e2\b\b\u0002\u0010\u001c\u001a\u00020\u001d2\b\b\u0002\u0010\u001e\u001a\u00020\u001f2\b\b\u0002\u0010 \u001a\u00020!2\b\b\u0002\u0010\"\u001a\u00020\u000e2\b\b\u0002\u0010#\u001a\u00020$2\b\b\u0002\u0010%\u001a\u00020$2\b\b\u0002\u0010&\u001a\u00020'2\b\b\u0002\u0010(\u001a\u00020)2\b\b\u0002\u0010*\u001a\u00020+H\u0007¢\u0006\u0002\u00100\u001aì\u0001\u00101\u001a\u00020\u00062\u0006\u0010\u000b\u001a\u00020\f2\u0011\u00102\u001a\r\u0012\u0004\u0012\u00020\u00060\u0013¢\u0006\u0002\b\u00142\u0013\u0010\u0012\u001a\u000f\u0012\u0004\u0012\u00020\u0006\u0018\u00010\u0013¢\u0006\u0002\b\u00142\u0019\u0010\u0015\u001a\u0015\u0012\u0004\u0012\u00020\f\u0012\u0004\u0012\u00020\u0006\u0018\u00010\n¢\u0006\u0002\b\u00142\u0013\u00103\u001a\u000f\u0012\u0004\u0012\u00020\u0006\u0018\u00010\u0013¢\u0006\u0002\b\u00142\u0013\u00104\u001a\u000f\u0012\u0004\u0012\u00020\u0006\u0018\u00010\u0013¢\u0006\u0002\b\u00142\u0013\u0010\u0018\u001a\u000f\u0012\u0004\u0012\u00020\u0006\u0018\u00010\u0013¢\u0006\u0002\b\u00142\u0013\u0010\u0019\u001a\u000f\u0012\u0004\u0012\u00020\u0006\u0018\u00010\u0013¢\u0006\u0002\b\u00142\u0006\u0010\"\u001a\u00020\u000e2\u0006\u00105\u001a\u0002062\u0011\u00107\u001a\r\u0012\u0004\u0012\u00020\u00060\u0013¢\u0006\u0002\b\u00142\u0013\u00108\u001a\u000f\u0012\u0004\u0012\u00020\u0006\u0018\u00010\u0013¢\u0006\u0002\b\u00142\u0006\u00109\u001a\u00020:H\u0001¢\u0006\u0002\u0010;\u001ar\u0010<\u001a\u00020$2\u0006\u0010=\u001a\u00020$2\u0006\u0010>\u001a\u00020$2\u0006\u0010?\u001a\u00020$2\u0006\u0010@\u001a\u00020$2\u0006\u0010A\u001a\u00020$2\u0006\u0010B\u001a\u00020$2\u0006\u0010C\u001a\u00020$2\u0006\u0010D\u001a\u00020$2\u0006\u00105\u001a\u0002062\u0006\u0010E\u001a\u00020F2\u0006\u0010G\u001a\u0002062\u0006\u00109\u001a\u00020:H\u0002ø\u0001\u0000¢\u0006\u0004\bH\u0010I\u001aR\u0010J\u001a\u00020$2\u0006\u0010K\u001a\u00020$2\u0006\u0010L\u001a\u00020$2\u0006\u0010M\u001a\u00020$2\u0006\u0010N\u001a\u00020$2\u0006\u0010O\u001a\u00020$2\u0006\u0010P\u001a\u00020$2\u0006\u0010Q\u001a\u00020$2\u0006\u0010E\u001a\u00020FH\u0002ø\u0001\u0000¢\u0006\u0004\bR\u0010S\u001a\u0014\u0010T\u001a\u00020\f*\u00020\f2\u0006\u0010U\u001a\u00020VH\u0000\u001a\u009a\u0001\u0010W\u001a\u00020\u0006*\u00020X2\u0006\u0010Y\u001a\u00020$2\u0006\u0010Z\u001a\u00020$2\u0006\u0010[\u001a\u00020\\2\b\u0010]\u001a\u0004\u0018\u00010\\2\b\u0010^\u001a\u0004\u0018\u00010\\2\b\u0010_\u001a\u0004\u0018\u00010\\2\b\u0010`\u001a\u0004\u0018\u00010\\2\b\u0010a\u001a\u0004\u0018\u00010\\2\b\u0010b\u001a\u0004\u0018\u00010\\2\u0006\u0010c\u001a\u00020\\2\b\u0010d\u001a\u0004\u0018\u00010\\2\u0006\u0010\"\u001a\u00020\u000e2\u0006\u0010e\u001a\u00020$2\u0006\u0010f\u001a\u00020$2\u0006\u00105\u001a\u0002062\u0006\u0010G\u001a\u000206H\u0002\u001a\u0080\u0001\u0010g\u001a\u00020\u0006*\u00020X2\u0006\u0010Y\u001a\u00020$2\u0006\u0010Z\u001a\u00020$2\u0006\u0010h\u001a\u00020\\2\b\u0010^\u001a\u0004\u0018\u00010\\2\b\u0010_\u001a\u0004\u0018\u00010\\2\b\u0010`\u001a\u0004\u0018\u00010\\2\b\u0010a\u001a\u0004\u0018\u00010\\2\b\u0010b\u001a\u0004\u0018\u00010\\2\u0006\u0010c\u001a\u00020\\2\b\u0010d\u001a\u0004\u0018\u00010\\2\u0006\u0010\"\u001a\u00020\u000e2\u0006\u0010G\u001a\u0002062\u0006\u00109\u001a\u00020:H\u0002\u001a\u0014\u0010i\u001a\u00020$*\u00020$2\u0006\u0010j\u001a\u00020$H\u0002\"\u0016\u0010\u0000\u001a\u00020\u0001X\u0080\u0004¢\u0006\n\n\u0002\u0010\u0004\u001a\u0004\b\u0002\u0010\u0003\u0082\u0002\u0007\n\u0005\b¡\u001e0\u0001¨\u0006k"}, d2 = {"TextFieldWithLabelVerticalPadding", "Landroidx/compose/ui/unit/Dp;", "getTextFieldWithLabelVerticalPadding", "()F", "F", "TextField", "", "value", "Landroidx/compose/ui/text/input/TextFieldValue;", "onValueChange", "Lkotlin/Function1;", "modifier", "Landroidx/compose/ui/Modifier;", "enabled", "", "readOnly", "textStyle", "Landroidx/compose/ui/text/TextStyle;", "label", "Lkotlin/Function0;", "Landroidx/compose/runtime/Composable;", "placeholder", "leadingIcon", "trailingIcon", "prefix", "suffix", "supportingText", "isError", "visualTransformation", "Landroidx/compose/ui/text/input/VisualTransformation;", "keyboardOptions", "Landroidx/compose/foundation/text/KeyboardOptions;", "keyboardActions", "Landroidx/compose/foundation/text/KeyboardActions;", "singleLine", "maxLines", "", "minLines", "interactionSource", "Landroidx/compose/foundation/interaction/MutableInteractionSource;", "shape", "Landroidx/compose/ui/graphics/Shape;", "colors", "Landroidx/compose/material3/TextFieldColors;", "(Landroidx/compose/ui/text/input/TextFieldValue;Lkotlin/jvm/functions/Function1;Landroidx/compose/ui/Modifier;ZZLandroidx/compose/ui/text/TextStyle;Lkotlin/jvm/functions/Function2;Lkotlin/jvm/functions/Function2;Lkotlin/jvm/functions/Function2;Lkotlin/jvm/functions/Function2;Lkotlin/jvm/functions/Function2;Lkotlin/jvm/functions/Function2;Lkotlin/jvm/functions/Function2;ZLandroidx/compose/ui/text/input/VisualTransformation;Landroidx/compose/foundation/text/KeyboardOptions;Landroidx/compose/foundation/text/KeyboardActions;ZIILandroidx/compose/foundation/interaction/MutableInteractionSource;Landroidx/compose/ui/graphics/Shape;Landroidx/compose/material3/TextFieldColors;Landroidx/compose/runtime/Composer;IIII)V", "(Landroidx/compose/ui/text/input/TextFieldValue;Lkotlin/jvm/functions/Function1;Landroidx/compose/ui/Modifier;ZZLandroidx/compose/ui/text/TextStyle;Lkotlin/jvm/functions/Function2;Lkotlin/jvm/functions/Function2;Lkotlin/jvm/functions/Function2;Lkotlin/jvm/functions/Function2;Lkotlin/jvm/functions/Function2;ZLandroidx/compose/ui/text/input/VisualTransformation;Landroidx/compose/foundation/text/KeyboardOptions;Landroidx/compose/foundation/text/KeyboardActions;ZIILandroidx/compose/foundation/interaction/MutableInteractionSource;Landroidx/compose/ui/graphics/Shape;Landroidx/compose/material3/TextFieldColors;Landroidx/compose/runtime/Composer;IIII)V", "", "(Ljava/lang/String;Lkotlin/jvm/functions/Function1;Landroidx/compose/ui/Modifier;ZZLandroidx/compose/ui/text/TextStyle;Lkotlin/jvm/functions/Function2;Lkotlin/jvm/functions/Function2;Lkotlin/jvm/functions/Function2;Lkotlin/jvm/functions/Function2;Lkotlin/jvm/functions/Function2;Lkotlin/jvm/functions/Function2;Lkotlin/jvm/functions/Function2;ZLandroidx/compose/ui/text/input/VisualTransformation;Landroidx/compose/foundation/text/KeyboardOptions;Landroidx/compose/foundation/text/KeyboardActions;ZIILandroidx/compose/foundation/interaction/MutableInteractionSource;Landroidx/compose/ui/graphics/Shape;Landroidx/compose/material3/TextFieldColors;Landroidx/compose/runtime/Composer;IIII)V", "(Ljava/lang/String;Lkotlin/jvm/functions/Function1;Landroidx/compose/ui/Modifier;ZZLandroidx/compose/ui/text/TextStyle;Lkotlin/jvm/functions/Function2;Lkotlin/jvm/functions/Function2;Lkotlin/jvm/functions/Function2;Lkotlin/jvm/functions/Function2;Lkotlin/jvm/functions/Function2;ZLandroidx/compose/ui/text/input/VisualTransformation;Landroidx/compose/foundation/text/KeyboardOptions;Landroidx/compose/foundation/text/KeyboardActions;ZIILandroidx/compose/foundation/interaction/MutableInteractionSource;Landroidx/compose/ui/graphics/Shape;Landroidx/compose/material3/TextFieldColors;Landroidx/compose/runtime/Composer;IIII)V", "TextFieldLayout", "textField", "leading", "trailing", "animationProgress", "", "container", "supporting", "paddingValues", "Landroidx/compose/foundation/layout/PaddingValues;", "(Landroidx/compose/ui/Modifier;Lkotlin/jvm/functions/Function2;Lkotlin/jvm/functions/Function2;Lkotlin/jvm/functions/Function3;Lkotlin/jvm/functions/Function2;Lkotlin/jvm/functions/Function2;Lkotlin/jvm/functions/Function2;Lkotlin/jvm/functions/Function2;ZFLkotlin/jvm/functions/Function2;Lkotlin/jvm/functions/Function2;Landroidx/compose/foundation/layout/PaddingValues;Landroidx/compose/runtime/Composer;II)V", "calculateHeight", "textFieldHeight", "labelHeight", "leadingHeight", "trailingHeight", "prefixHeight", "suffixHeight", "placeholderHeight", "supportingHeight", "constraints", "Landroidx/compose/ui/unit/Constraints;", "density", "calculateHeight-mKXJcVc", "(IIIIIIIIFJFLandroidx/compose/foundation/layout/PaddingValues;)I", "calculateWidth", "leadingWidth", "trailingWidth", "prefixWidth", "suffixWidth", "textFieldWidth", "labelWidth", "placeholderWidth", "calculateWidth-yeHjK3Y", "(IIIIIIIJ)I", "drawIndicatorLine", "indicatorBorder", "Landroidx/compose/foundation/BorderStroke;", "placeWithLabel", "Landroidx/compose/ui/layout/Placeable$PlacementScope;", "width", "totalHeight", "textfieldPlaceable", "Landroidx/compose/ui/layout/Placeable;", "labelPlaceable", "placeholderPlaceable", "leadingPlaceable", "trailingPlaceable", "prefixPlaceable", "suffixPlaceable", "containerPlaceable", "supportingPlaceable", "labelEndPosition", "textPosition", "placeWithoutLabel", "textPlaceable", "substractConstraintSafely", "from", "material3_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class TextFieldKt {
    private static final float TextFieldWithLabelVerticalPadding = Dp.m6094constructorimpl(8);

    public static final void TextField(final String value, final Function1<? super String, Unit> function1, Modifier modifier, boolean enabled, boolean readOnly, TextStyle textStyle, Function2<? super Composer, ? super Integer, Unit> function2, Function2<? super Composer, ? super Integer, Unit> function22, Function2<? super Composer, ? super Integer, Unit> function23, Function2<? super Composer, ? super Integer, Unit> function24, Function2<? super Composer, ? super Integer, Unit> function25, Function2<? super Composer, ? super Integer, Unit> function26, Function2<? super Composer, ? super Integer, Unit> function27, boolean isError, VisualTransformation visualTransformation, KeyboardOptions keyboardOptions, KeyboardActions keyboardActions, boolean singleLine, int maxLines, int minLines, MutableInteractionSource interactionSource, Shape shape, TextFieldColors colors, Composer $composer, final int $changed, final int $changed1, final int $changed2, final int i) {
        int i2;
        int i3;
        Modifier modifier2;
        boolean enabled2;
        TextStyle textStyle2;
        Function2 label;
        Function2 placeholder;
        Function2 leadingIcon;
        Function2 trailingIcon;
        Function2 prefix;
        Function2 suffix;
        Function2 supportingText;
        boolean isError2;
        int maxLines2;
        int $dirty;
        int $dirty1;
        MutableInteractionSource interactionSource2;
        Shape shape2;
        Modifier modifier3;
        boolean enabled3;
        int $dirty2;
        MutableInteractionSource interactionSource3;
        Shape shape3;
        int $dirty12;
        TextFieldColors colors2;
        int $dirty22;
        boolean readOnly2;
        VisualTransformation visualTransformation2;
        KeyboardOptions keyboardOptions2;
        KeyboardActions keyboardActions2;
        boolean singleLine2;
        int maxLines3;
        int minLines2;
        Object value$iv;
        Function2 supportingText2;
        int $dirty3;
        long textColor;
        TextStyle textStyle3;
        Modifier modifier4;
        boolean enabled4;
        Function2 supportingText3;
        boolean readOnly3;
        Function2 placeholder2;
        Function2 leadingIcon2;
        Function2 trailingIcon2;
        Function2 prefix2;
        Function2 suffix2;
        Function2 label2;
        boolean isError3;
        TextFieldColors colors3;
        int i4;
        int i5;
        int i6;
        int i7;
        Composer $composer2 = $composer.startRestartGroup(-676242365);
        ComposerKt.sourceInformation($composer2, "C(TextField)P(21,11,10,1,14,19,6,12,7,20,13,17,18,3,22,5,4,16,8,9,2,15)174@9072L7,189@9824L39,190@9902L5,191@9957L8,199@10319L15,199@10253L1913:TextField.kt#uh7d8r");
        int $dirty4 = $changed;
        int $dirty13 = $changed1;
        int $dirty23 = $changed2;
        if ((i & 1) != 0) {
            $dirty4 |= 6;
        } else if (($changed & 6) == 0) {
            $dirty4 |= $composer2.changed(value) ? 4 : 2;
        }
        if ((i & 2) != 0) {
            $dirty4 |= 48;
        } else if (($changed & 48) == 0) {
            $dirty4 |= $composer2.changedInstance(function1) ? 32 : 16;
        }
        int i8 = i & 4;
        if (i8 != 0) {
            $dirty4 |= 384;
        } else if (($changed & 384) == 0) {
            $dirty4 |= $composer2.changed(modifier) ? 256 : 128;
        }
        int i9 = i & 8;
        if (i9 != 0) {
            $dirty4 |= 3072;
        } else if (($changed & 3072) == 0) {
            $dirty4 |= $composer2.changed(enabled) ? 2048 : 1024;
        }
        int i10 = i & 16;
        if (i10 != 0) {
            $dirty4 |= 24576;
        } else if (($changed & 24576) == 0) {
            $dirty4 |= $composer2.changed(readOnly) ? 16384 : 8192;
        }
        if (($changed & ProfileVerifier.CompilationStatus.RESULT_CODE_ERROR_CANT_WRITE_PROFILE_VERIFICATION_RESULT_CACHE_FILE) == 0) {
            if ((i & 32) == 0 && $composer2.changed(textStyle)) {
                i7 = 131072;
                $dirty4 |= i7;
            }
            i7 = 65536;
            $dirty4 |= i7;
        }
        int i11 = i & 64;
        if (i11 != 0) {
            $dirty4 |= 1572864;
        } else if (($changed & 1572864) == 0) {
            $dirty4 |= $composer2.changedInstance(function2) ? 1048576 : 524288;
        }
        int i12 = i & 128;
        if (i12 != 0) {
            $dirty4 |= 12582912;
        } else if (($changed & 12582912) == 0) {
            $dirty4 |= $composer2.changedInstance(function22) ? 8388608 : 4194304;
        }
        int i13 = i & 256;
        if (i13 != 0) {
            $dirty4 |= 100663296;
        } else if (($changed & 100663296) == 0) {
            $dirty4 |= $composer2.changedInstance(function23) ? AccessibilityEventCompat.TYPE_VIEW_TARGETED_BY_SCROLL : 33554432;
        }
        int i14 = i & 512;
        if (i14 != 0) {
            $dirty4 |= 805306368;
        } else if (($changed & 805306368) == 0) {
            $dirty4 |= $composer2.changedInstance(function24) ? 536870912 : 268435456;
        }
        int i15 = i & 1024;
        if (i15 != 0) {
            $dirty13 |= 6;
        } else if (($changed1 & 6) == 0) {
            $dirty13 |= $composer2.changedInstance(function25) ? 4 : 2;
        }
        int i16 = i & 2048;
        if (i16 != 0) {
            $dirty13 |= 48;
        } else if (($changed1 & 48) == 0) {
            $dirty13 |= $composer2.changedInstance(function26) ? 32 : 16;
        }
        int i17 = i & 4096;
        if (i17 != 0) {
            $dirty13 |= 384;
        } else if (($changed1 & 384) == 0) {
            $dirty13 |= $composer2.changedInstance(function27) ? 256 : 128;
        }
        int i18 = i & 8192;
        if (i18 != 0) {
            $dirty13 |= 3072;
            i2 = i18;
        } else {
            i2 = i18;
            if (($changed1 & 3072) == 0) {
                $dirty13 |= $composer2.changed(isError) ? 2048 : 1024;
            }
        }
        int i19 = i & 16384;
        if (i19 != 0) {
            $dirty13 |= 24576;
            i3 = i19;
        } else {
            i3 = i19;
            if (($changed1 & 24576) == 0) {
                $dirty13 |= $composer2.changed(visualTransformation) ? 16384 : 8192;
            }
        }
        int i20 = i & 32768;
        if (i20 != 0) {
            $dirty13 |= ProfileVerifier.CompilationStatus.RESULT_CODE_ERROR_CANT_WRITE_PROFILE_VERIFICATION_RESULT_CACHE_FILE;
        } else if (($changed1 & ProfileVerifier.CompilationStatus.RESULT_CODE_ERROR_CANT_WRITE_PROFILE_VERIFICATION_RESULT_CACHE_FILE) == 0) {
            $dirty13 |= $composer2.changed(keyboardOptions) ? 131072 : 65536;
        }
        int i21 = i & 65536;
        if (i21 != 0) {
            $dirty13 |= 1572864;
        } else if (($changed1 & 1572864) == 0) {
            $dirty13 |= $composer2.changed(keyboardActions) ? 1048576 : 524288;
        }
        int i22 = i & 131072;
        if (i22 != 0) {
            $dirty13 |= 12582912;
        } else if (($changed1 & 12582912) == 0) {
            $dirty13 |= $composer2.changed(singleLine) ? 8388608 : 4194304;
        }
        if (($changed1 & 100663296) == 0) {
            if ((i & 262144) == 0 && $composer2.changed(maxLines)) {
                i6 = AccessibilityEventCompat.TYPE_VIEW_TARGETED_BY_SCROLL;
                $dirty13 |= i6;
            }
            i6 = 33554432;
            $dirty13 |= i6;
        }
        int i23 = i & 524288;
        if (i23 != 0) {
            $dirty13 |= 805306368;
        } else if (($changed1 & 805306368) == 0) {
            $dirty13 |= $composer2.changed(minLines) ? 536870912 : 268435456;
        }
        int i24 = i & 1048576;
        if (i24 != 0) {
            $dirty23 |= 6;
        } else if (($changed2 & 6) == 0) {
            $dirty23 |= $composer2.changed(interactionSource) ? 4 : 2;
        }
        if (($changed2 & 48) == 0) {
            if ((i & 2097152) == 0 && $composer2.changed(shape)) {
                i5 = 32;
                $dirty23 |= i5;
            }
            i5 = 16;
            $dirty23 |= i5;
        }
        if (($changed2 & 384) == 0) {
            if ((i & 4194304) == 0 && $composer2.changed(colors)) {
                i4 = 256;
                $dirty23 |= i4;
            }
            i4 = 128;
            $dirty23 |= i4;
        }
        if (($dirty4 & 306783379) == 306783378 && (306783379 & $dirty13) == 306783378 && ($dirty23 & 147) == 146 && $composer2.getSkipping()) {
            $composer2.skipToGroupEnd();
            modifier4 = modifier;
            enabled4 = enabled;
            readOnly3 = readOnly;
            textStyle3 = textStyle;
            label2 = function2;
            placeholder2 = function22;
            leadingIcon2 = function23;
            trailingIcon2 = function24;
            prefix2 = function25;
            suffix2 = function26;
            supportingText3 = function27;
            isError3 = isError;
            visualTransformation2 = visualTransformation;
            keyboardOptions2 = keyboardOptions;
            keyboardActions2 = keyboardActions;
            singleLine2 = singleLine;
            maxLines3 = maxLines;
            minLines2 = minLines;
            interactionSource3 = interactionSource;
            shape3 = shape;
            colors3 = colors;
        } else {
            $composer2.startDefaults();
            if (($changed & 1) == 0 || $composer2.getDefaultsInvalid()) {
                Modifier.Companion modifier5 = i8 != 0 ? Modifier.INSTANCE : modifier;
                boolean enabled5 = i9 != 0 ? true : enabled;
                boolean readOnly4 = i10 != 0 ? false : readOnly;
                if ((i & 32) != 0) {
                    ProvidableCompositionLocal<TextStyle> localTextStyle = TextKt.getLocalTextStyle();
                    modifier2 = modifier5;
                    enabled2 = enabled5;
                    ComposerKt.sourceInformationMarkerStart($composer2, 2023513938, "CC:CompositionLocal.kt#9igjgp");
                    Object consume = $composer2.consume(localTextStyle);
                    ComposerKt.sourceInformationMarkerEnd($composer2);
                    textStyle2 = (TextStyle) consume;
                    $dirty4 &= -458753;
                } else {
                    modifier2 = modifier5;
                    enabled2 = enabled5;
                    textStyle2 = textStyle;
                }
                label = i11 != 0 ? null : function2;
                placeholder = i12 != 0 ? null : function22;
                leadingIcon = i13 != 0 ? null : function23;
                trailingIcon = i14 != 0 ? null : function24;
                prefix = i15 != 0 ? null : function25;
                suffix = i16 != 0 ? null : function26;
                supportingText = i17 != 0 ? null : function27;
                isError2 = i2 != 0 ? false : isError;
                VisualTransformation visualTransformation3 = i3 != 0 ? VisualTransformation.INSTANCE.getNone() : visualTransformation;
                KeyboardOptions keyboardOptions3 = i20 != 0 ? KeyboardOptions.INSTANCE.getDefault() : keyboardOptions;
                KeyboardActions keyboardActions3 = i21 != 0 ? KeyboardActions.INSTANCE.getDefault() : keyboardActions;
                boolean singleLine3 = i22 != 0 ? false : singleLine;
                if ((i & 262144) != 0) {
                    maxLines2 = singleLine3 ? 1 : Integer.MAX_VALUE;
                    $dirty13 &= -234881025;
                } else {
                    maxLines2 = maxLines;
                }
                int minLines3 = i23 != 0 ? 1 : minLines;
                if (i24 != 0) {
                    $dirty = $dirty4;
                    $composer2.startReplaceableGroup(-1263331754);
                    ComposerKt.sourceInformation($composer2, "CC(remember):TextField.kt#9igjgp");
                    Object it$iv = $composer2.rememberedValue();
                    $dirty1 = $dirty13;
                    if (it$iv == Composer.INSTANCE.getEmpty()) {
                        value$iv = InteractionSourceKt.MutableInteractionSource();
                        $composer2.updateRememberedValue(value$iv);
                    } else {
                        value$iv = it$iv;
                    }
                    interactionSource2 = (MutableInteractionSource) value$iv;
                    $composer2.endReplaceableGroup();
                } else {
                    $dirty = $dirty4;
                    $dirty1 = $dirty13;
                    interactionSource2 = interactionSource;
                }
                MutableInteractionSource interactionSource4 = interactionSource2;
                if ((2097152 & i) != 0) {
                    shape2 = TextFieldDefaults.INSTANCE.getShape($composer2, 6);
                    $dirty23 &= -113;
                } else {
                    shape2 = shape;
                }
                if ((i & 4194304) != 0) {
                    $dirty2 = $dirty;
                    interactionSource3 = interactionSource4;
                    shape3 = shape2;
                    $dirty12 = $dirty1;
                    colors2 = TextFieldDefaults.INSTANCE.colors($composer2, 6);
                    $dirty22 = $dirty23 & (-897);
                    readOnly2 = readOnly4;
                    visualTransformation2 = visualTransformation3;
                    keyboardOptions2 = keyboardOptions3;
                    keyboardActions2 = keyboardActions3;
                    singleLine2 = singleLine3;
                    maxLines3 = maxLines2;
                    minLines2 = minLines3;
                    modifier3 = modifier2;
                    enabled3 = enabled2;
                } else {
                    Shape shape4 = shape2;
                    modifier3 = modifier2;
                    enabled3 = enabled2;
                    $dirty2 = $dirty;
                    interactionSource3 = interactionSource4;
                    shape3 = shape4;
                    $dirty12 = $dirty1;
                    colors2 = colors;
                    $dirty22 = $dirty23;
                    readOnly2 = readOnly4;
                    visualTransformation2 = visualTransformation3;
                    keyboardOptions2 = keyboardOptions3;
                    keyboardActions2 = keyboardActions3;
                    singleLine2 = singleLine3;
                    maxLines3 = maxLines2;
                    minLines2 = minLines3;
                }
            } else {
                $composer2.skipToGroupEnd();
                if ((i & 32) != 0) {
                    $dirty4 &= -458753;
                }
                if ((262144 & i) != 0) {
                    $dirty13 &= -234881025;
                }
                if ((2097152 & i) != 0) {
                    $dirty23 &= -113;
                }
                if ((i & 4194304) != 0) {
                    $dirty23 &= -897;
                }
                textStyle2 = textStyle;
                label = function2;
                placeholder = function22;
                leadingIcon = function23;
                trailingIcon = function24;
                prefix = function25;
                suffix = function26;
                supportingText = function27;
                isError2 = isError;
                visualTransformation2 = visualTransformation;
                keyboardOptions2 = keyboardOptions;
                keyboardActions2 = keyboardActions;
                singleLine2 = singleLine;
                maxLines3 = maxLines;
                minLines2 = minLines;
                interactionSource3 = interactionSource;
                shape3 = shape;
                colors2 = colors;
                $dirty2 = $dirty4;
                $dirty12 = $dirty13;
                $dirty22 = $dirty23;
                modifier3 = modifier;
                enabled3 = enabled;
                readOnly2 = readOnly;
            }
            $composer2.endDefaults();
            if (ComposerKt.isTraceInProgress()) {
                supportingText2 = supportingText;
                ComposerKt.traceEventStart(-676242365, $dirty2, $dirty12, "androidx.compose.material3.TextField (TextField.kt:192)");
            } else {
                supportingText2 = supportingText;
            }
            $composer2.startReplaceableGroup(-1263331489);
            ComposerKt.sourceInformation($composer2, "*195@10117L46");
            long $this$takeOrElse_u2dDxMtmZc$iv = textStyle2.m5601getColor0d7_KjU();
            if ($this$takeOrElse_u2dDxMtmZc$iv != Color.INSTANCE.m3782getUnspecified0d7_KjU()) {
                $dirty3 = $dirty2;
                textColor = $this$takeOrElse_u2dDxMtmZc$iv;
            } else {
                $dirty3 = $dirty2;
                textColor = colors2.textColor$material3_release(enabled3, isError2, interactionSource3, $composer2, (($dirty2 >> 9) & 14) | (($dirty12 >> 6) & 112) | (($dirty22 << 6) & 896) | (($dirty22 << 3) & 7168)).getValue().m3756unboximpl();
            }
            $composer2.endReplaceableGroup();
            final TextStyle mergedTextStyle = textStyle2.merge(new TextStyle(textColor, 0L, (FontWeight) null, (FontStyle) null, (FontSynthesis) null, (FontFamily) null, (String) null, 0L, (BaselineShift) null, (TextGeometricTransform) null, (LocaleList) null, 0L, (TextDecoration) null, (Shadow) null, (DrawStyle) null, 0, 0, 0L, (TextIndent) null, (PlatformTextStyle) null, (LineHeightStyle) null, 0, 0, (TextMotion) null, 16777214, (DefaultConstructorMarker) null));
            TextStyle textStyle4 = textStyle2;
            final TextFieldColors colors4 = colors2;
            final Modifier modifier6 = modifier3;
            final boolean z = isError2;
            final boolean z2 = enabled3;
            final boolean z3 = readOnly2;
            final KeyboardOptions keyboardOptions4 = keyboardOptions2;
            final KeyboardActions keyboardActions4 = keyboardActions2;
            final boolean z4 = singleLine2;
            final int i25 = maxLines3;
            final int i26 = minLines2;
            final VisualTransformation visualTransformation4 = visualTransformation2;
            final MutableInteractionSource mutableInteractionSource = interactionSource3;
            final Function2 function28 = label;
            final Function2 function29 = placeholder;
            final Function2 function210 = leadingIcon;
            final Function2 function211 = trailingIcon;
            final Function2 function212 = prefix;
            final Function2 function213 = suffix;
            final Function2 function214 = supportingText2;
            final Shape shape5 = shape3;
            Modifier modifier7 = modifier3;
            boolean enabled6 = enabled3;
            CompositionLocalKt.CompositionLocalProvider(TextSelectionColorsKt.getLocalTextSelectionColors().provides(colors4.getSelectionColors($composer2, ($dirty22 >> 6) & 14)), ComposableLambdaKt.composableLambda($composer2, 1859145987, true, new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.TextFieldKt$TextField$2
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

                public final void invoke(Composer $composer3, int $changed3) {
                    ComposerKt.sourceInformation($composer3, "C203@10469L38,212@10872L20,200@10346L1814:TextField.kt#uh7d8r");
                    if (($changed3 & 3) != 2 || !$composer3.getSkipping()) {
                        if (ComposerKt.isTraceInProgress()) {
                            ComposerKt.traceEventStart(1859145987, $changed3, -1, "androidx.compose.material3.TextField.<anonymous> (TextField.kt:200)");
                        }
                        Modifier modifier8 = Modifier.this;
                        boolean z5 = z;
                        Strings.Companion companion = Strings.INSTANCE;
                        Modifier m595defaultMinSizeVpY3zN4 = SizeKt.m595defaultMinSizeVpY3zN4(TextFieldImplKt.defaultErrorSemantics(modifier8, z5, Strings_androidKt.m2306getStringNWtq28(Strings.m2237constructorimpl(androidx.compose.ui.R.string.default_error_message), $composer3, 0)), TextFieldDefaults.INSTANCE.m2440getMinWidthD9Ej5fM(), TextFieldDefaults.INSTANCE.m2439getMinHeightD9Ej5fM());
                        SolidColor solidColor = new SolidColor(colors4.cursorColor$material3_release(z, $composer3, 0).getValue().m3756unboximpl(), null);
                        String str = value;
                        Function1<String, Unit> function12 = function1;
                        boolean z6 = z2;
                        boolean z7 = z3;
                        TextStyle textStyle5 = mergedTextStyle;
                        KeyboardOptions keyboardOptions5 = keyboardOptions4;
                        KeyboardActions keyboardActions5 = keyboardActions4;
                        boolean z8 = z4;
                        int i27 = i25;
                        int i28 = i26;
                        VisualTransformation visualTransformation5 = visualTransformation4;
                        MutableInteractionSource mutableInteractionSource2 = mutableInteractionSource;
                        SolidColor solidColor2 = solidColor;
                        final String str2 = value;
                        final boolean z9 = z2;
                        final boolean z10 = z4;
                        final VisualTransformation visualTransformation6 = visualTransformation4;
                        final MutableInteractionSource mutableInteractionSource3 = mutableInteractionSource;
                        final boolean z11 = z;
                        final Function2<Composer, Integer, Unit> function215 = function28;
                        final Function2<Composer, Integer, Unit> function216 = function29;
                        final Function2<Composer, Integer, Unit> function217 = function210;
                        final Function2<Composer, Integer, Unit> function218 = function211;
                        final Function2<Composer, Integer, Unit> function219 = function212;
                        final Function2<Composer, Integer, Unit> function220 = function213;
                        final Function2<Composer, Integer, Unit> function221 = function214;
                        final Shape shape6 = shape5;
                        final TextFieldColors textFieldColors = colors4;
                        BasicTextFieldKt.BasicTextField(str, function12, m595defaultMinSizeVpY3zN4, z6, z7, textStyle5, keyboardOptions5, keyboardActions5, z8, i27, i28, visualTransformation5, (Function1<? super TextLayoutResult, Unit>) null, mutableInteractionSource2, solidColor2, ComposableLambdaKt.composableLambda($composer3, -288211827, true, new Function3<Function2<? super Composer, ? super Integer, ? extends Unit>, Composer, Integer, Unit>() { // from class: androidx.compose.material3.TextFieldKt$TextField$2.1
                            /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
                            /* JADX WARN: Multi-variable type inference failed */
                            {
                                super(3);
                            }

                            @Override // kotlin.jvm.functions.Function3
                            public /* bridge */ /* synthetic */ Unit invoke(Function2<? super Composer, ? super Integer, ? extends Unit> function222, Composer composer, Integer num) {
                                invoke((Function2<? super Composer, ? super Integer, Unit>) function222, composer, num.intValue());
                                return Unit.INSTANCE;
                            }

                            public final void invoke(Function2<? super Composer, ? super Integer, Unit> function222, Composer $composer4, int $changed4) {
                                ComposerKt.sourceInformation($composer4, "C222@11393L743:TextField.kt#uh7d8r");
                                int $dirty5 = $changed4;
                                if (($changed4 & 6) == 0) {
                                    $dirty5 |= $composer4.changedInstance(function222) ? 4 : 2;
                                }
                                int $dirty6 = $dirty5;
                                if (($dirty6 & 19) != 18 || !$composer4.getSkipping()) {
                                    if (ComposerKt.isTraceInProgress()) {
                                        ComposerKt.traceEventStart(-288211827, $dirty6, -1, "androidx.compose.material3.TextField.<anonymous>.<anonymous> (TextField.kt:222)");
                                    }
                                    TextFieldDefaults.INSTANCE.DecorationBox(str2, function222, z9, z10, visualTransformation6, mutableInteractionSource3, z11, function215, function216, function217, function218, function219, function220, function221, shape6, textFieldColors, null, null, $composer4, ($dirty6 << 3) & 112, 100663296, ProfileVerifier.CompilationStatus.RESULT_CODE_ERROR_CANT_WRITE_PROFILE_VERIFICATION_RESULT_CACHE_FILE);
                                    if (ComposerKt.isTraceInProgress()) {
                                        ComposerKt.traceEventEnd();
                                        return;
                                    }
                                    return;
                                }
                                $composer4.skipToGroupEnd();
                            }
                        }), $composer3, 0, ProfileVerifier.CompilationStatus.RESULT_CODE_ERROR_CANT_WRITE_PROFILE_VERIFICATION_RESULT_CACHE_FILE, 4096);
                        if (ComposerKt.isTraceInProgress()) {
                            ComposerKt.traceEventEnd();
                            return;
                        }
                        return;
                    }
                    $composer3.skipToGroupEnd();
                }
            }), $composer2, ProvidedValue.$stable | 0 | 48);
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventEnd();
            }
            textStyle3 = textStyle4;
            modifier4 = modifier7;
            enabled4 = enabled6;
            supportingText3 = supportingText2;
            readOnly3 = readOnly2;
            placeholder2 = placeholder;
            leadingIcon2 = leadingIcon;
            trailingIcon2 = trailingIcon;
            prefix2 = prefix;
            suffix2 = suffix;
            label2 = label;
            isError3 = isError2;
            colors3 = colors4;
        }
        ScopeUpdateScope endRestartGroup = $composer2.endRestartGroup();
        if (endRestartGroup != null) {
            final Modifier modifier8 = modifier4;
            final boolean z5 = enabled4;
            final boolean z6 = readOnly3;
            final TextStyle textStyle5 = textStyle3;
            final Function2 function215 = label2;
            final Function2 function216 = placeholder2;
            final Function2 function217 = leadingIcon2;
            final Function2 function218 = trailingIcon2;
            final Function2 function219 = prefix2;
            final Function2 function220 = suffix2;
            final Function2 function221 = supportingText3;
            final boolean z7 = isError3;
            final VisualTransformation visualTransformation5 = visualTransformation2;
            final KeyboardOptions keyboardOptions5 = keyboardOptions2;
            final KeyboardActions keyboardActions5 = keyboardActions2;
            final boolean z8 = singleLine2;
            final int i27 = maxLines3;
            final int i28 = minLines2;
            final MutableInteractionSource mutableInteractionSource2 = interactionSource3;
            final Shape shape6 = shape3;
            final TextFieldColors textFieldColors = colors3;
            endRestartGroup.updateScope(new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.TextFieldKt$TextField$3
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

                public final void invoke(Composer composer, int i29) {
                    TextFieldKt.TextField(value, function1, modifier8, z5, z6, textStyle5, function215, function216, function217, function218, function219, function220, function221, z7, visualTransformation5, keyboardOptions5, keyboardActions5, z8, i27, i28, mutableInteractionSource2, shape6, textFieldColors, composer, RecomposeScopeImplKt.updateChangedFlags($changed | 1), RecomposeScopeImplKt.updateChangedFlags($changed1), RecomposeScopeImplKt.updateChangedFlags($changed2), i);
                }
            });
        }
    }

    public static final void TextField(final TextFieldValue value, final Function1<? super TextFieldValue, Unit> function1, Modifier modifier, boolean enabled, boolean readOnly, TextStyle textStyle, Function2<? super Composer, ? super Integer, Unit> function2, Function2<? super Composer, ? super Integer, Unit> function22, Function2<? super Composer, ? super Integer, Unit> function23, Function2<? super Composer, ? super Integer, Unit> function24, Function2<? super Composer, ? super Integer, Unit> function25, Function2<? super Composer, ? super Integer, Unit> function26, Function2<? super Composer, ? super Integer, Unit> function27, boolean isError, VisualTransformation visualTransformation, KeyboardOptions keyboardOptions, KeyboardActions keyboardActions, boolean singleLine, int maxLines, int minLines, MutableInteractionSource interactionSource, Shape shape, TextFieldColors colors, Composer $composer, final int $changed, final int $changed1, final int $changed2, final int i) {
        int i2;
        int i3;
        Modifier modifier2;
        boolean enabled2;
        TextStyle textStyle2;
        Function2 label;
        Function2 placeholder;
        Function2 leadingIcon;
        Function2 trailingIcon;
        Function2 prefix;
        Function2 suffix;
        Function2 supportingText;
        boolean isError2;
        int maxLines2;
        int $dirty;
        int $dirty1;
        MutableInteractionSource interactionSource2;
        Shape shape2;
        Modifier modifier3;
        boolean enabled3;
        int $dirty2;
        MutableInteractionSource interactionSource3;
        Shape shape3;
        int $dirty12;
        TextFieldColors colors2;
        int $dirty22;
        boolean readOnly2;
        VisualTransformation visualTransformation2;
        KeyboardOptions keyboardOptions2;
        KeyboardActions keyboardActions2;
        boolean singleLine2;
        int maxLines3;
        int minLines2;
        Object value$iv;
        Function2 supportingText2;
        int $dirty3;
        long textColor;
        TextStyle textStyle3;
        Modifier modifier4;
        boolean enabled4;
        Function2 supportingText3;
        boolean readOnly3;
        Function2 placeholder2;
        Function2 leadingIcon2;
        Function2 trailingIcon2;
        Function2 prefix2;
        Function2 suffix2;
        Function2 label2;
        boolean isError3;
        TextFieldColors colors3;
        int i4;
        int i5;
        int i6;
        int i7;
        Composer $composer2 = $composer.startRestartGroup(-1268528240);
        ComposerKt.sourceInformation($composer2, "C(TextField)P(21,11,10,1,14,19,6,12,7,20,13,17,18,3,22,5,4,16,8,9,2,15)320@17250L7,335@18002L39,336@18080L5,337@18135L8,345@18497L15,345@18431L1918:TextField.kt#uh7d8r");
        int $dirty4 = $changed;
        int $dirty13 = $changed1;
        int $dirty23 = $changed2;
        if ((i & 1) != 0) {
            $dirty4 |= 6;
        } else if (($changed & 6) == 0) {
            $dirty4 |= $composer2.changed(value) ? 4 : 2;
        }
        if ((i & 2) != 0) {
            $dirty4 |= 48;
        } else if (($changed & 48) == 0) {
            $dirty4 |= $composer2.changedInstance(function1) ? 32 : 16;
        }
        int i8 = i & 4;
        if (i8 != 0) {
            $dirty4 |= 384;
        } else if (($changed & 384) == 0) {
            $dirty4 |= $composer2.changed(modifier) ? 256 : 128;
        }
        int i9 = i & 8;
        if (i9 != 0) {
            $dirty4 |= 3072;
        } else if (($changed & 3072) == 0) {
            $dirty4 |= $composer2.changed(enabled) ? 2048 : 1024;
        }
        int i10 = i & 16;
        if (i10 != 0) {
            $dirty4 |= 24576;
        } else if (($changed & 24576) == 0) {
            $dirty4 |= $composer2.changed(readOnly) ? 16384 : 8192;
        }
        if (($changed & ProfileVerifier.CompilationStatus.RESULT_CODE_ERROR_CANT_WRITE_PROFILE_VERIFICATION_RESULT_CACHE_FILE) == 0) {
            if ((i & 32) == 0 && $composer2.changed(textStyle)) {
                i7 = 131072;
                $dirty4 |= i7;
            }
            i7 = 65536;
            $dirty4 |= i7;
        }
        int i11 = i & 64;
        if (i11 != 0) {
            $dirty4 |= 1572864;
        } else if (($changed & 1572864) == 0) {
            $dirty4 |= $composer2.changedInstance(function2) ? 1048576 : 524288;
        }
        int i12 = i & 128;
        if (i12 != 0) {
            $dirty4 |= 12582912;
        } else if (($changed & 12582912) == 0) {
            $dirty4 |= $composer2.changedInstance(function22) ? 8388608 : 4194304;
        }
        int i13 = i & 256;
        if (i13 != 0) {
            $dirty4 |= 100663296;
        } else if (($changed & 100663296) == 0) {
            $dirty4 |= $composer2.changedInstance(function23) ? AccessibilityEventCompat.TYPE_VIEW_TARGETED_BY_SCROLL : 33554432;
        }
        int i14 = i & 512;
        if (i14 != 0) {
            $dirty4 |= 805306368;
        } else if (($changed & 805306368) == 0) {
            $dirty4 |= $composer2.changedInstance(function24) ? 536870912 : 268435456;
        }
        int i15 = i & 1024;
        if (i15 != 0) {
            $dirty13 |= 6;
        } else if (($changed1 & 6) == 0) {
            $dirty13 |= $composer2.changedInstance(function25) ? 4 : 2;
        }
        int i16 = i & 2048;
        if (i16 != 0) {
            $dirty13 |= 48;
        } else if (($changed1 & 48) == 0) {
            $dirty13 |= $composer2.changedInstance(function26) ? 32 : 16;
        }
        int i17 = i & 4096;
        if (i17 != 0) {
            $dirty13 |= 384;
        } else if (($changed1 & 384) == 0) {
            $dirty13 |= $composer2.changedInstance(function27) ? 256 : 128;
        }
        int i18 = i & 8192;
        if (i18 != 0) {
            $dirty13 |= 3072;
            i2 = i18;
        } else {
            i2 = i18;
            if (($changed1 & 3072) == 0) {
                $dirty13 |= $composer2.changed(isError) ? 2048 : 1024;
            }
        }
        int i19 = i & 16384;
        if (i19 != 0) {
            $dirty13 |= 24576;
            i3 = i19;
        } else {
            i3 = i19;
            if (($changed1 & 24576) == 0) {
                $dirty13 |= $composer2.changed(visualTransformation) ? 16384 : 8192;
            }
        }
        int i20 = i & 32768;
        if (i20 != 0) {
            $dirty13 |= ProfileVerifier.CompilationStatus.RESULT_CODE_ERROR_CANT_WRITE_PROFILE_VERIFICATION_RESULT_CACHE_FILE;
        } else if (($changed1 & ProfileVerifier.CompilationStatus.RESULT_CODE_ERROR_CANT_WRITE_PROFILE_VERIFICATION_RESULT_CACHE_FILE) == 0) {
            $dirty13 |= $composer2.changed(keyboardOptions) ? 131072 : 65536;
        }
        int i21 = i & 65536;
        if (i21 != 0) {
            $dirty13 |= 1572864;
        } else if (($changed1 & 1572864) == 0) {
            $dirty13 |= $composer2.changed(keyboardActions) ? 1048576 : 524288;
        }
        int i22 = i & 131072;
        if (i22 != 0) {
            $dirty13 |= 12582912;
        } else if (($changed1 & 12582912) == 0) {
            $dirty13 |= $composer2.changed(singleLine) ? 8388608 : 4194304;
        }
        if (($changed1 & 100663296) == 0) {
            if ((i & 262144) == 0 && $composer2.changed(maxLines)) {
                i6 = AccessibilityEventCompat.TYPE_VIEW_TARGETED_BY_SCROLL;
                $dirty13 |= i6;
            }
            i6 = 33554432;
            $dirty13 |= i6;
        }
        int i23 = i & 524288;
        if (i23 != 0) {
            $dirty13 |= 805306368;
        } else if (($changed1 & 805306368) == 0) {
            $dirty13 |= $composer2.changed(minLines) ? 536870912 : 268435456;
        }
        int i24 = i & 1048576;
        if (i24 != 0) {
            $dirty23 |= 6;
        } else if (($changed2 & 6) == 0) {
            $dirty23 |= $composer2.changed(interactionSource) ? 4 : 2;
        }
        if (($changed2 & 48) == 0) {
            if ((i & 2097152) == 0 && $composer2.changed(shape)) {
                i5 = 32;
                $dirty23 |= i5;
            }
            i5 = 16;
            $dirty23 |= i5;
        }
        if (($changed2 & 384) == 0) {
            if ((i & 4194304) == 0 && $composer2.changed(colors)) {
                i4 = 256;
                $dirty23 |= i4;
            }
            i4 = 128;
            $dirty23 |= i4;
        }
        if (($dirty4 & 306783379) == 306783378 && (306783379 & $dirty13) == 306783378 && ($dirty23 & 147) == 146 && $composer2.getSkipping()) {
            $composer2.skipToGroupEnd();
            modifier4 = modifier;
            enabled4 = enabled;
            readOnly3 = readOnly;
            textStyle3 = textStyle;
            label2 = function2;
            placeholder2 = function22;
            leadingIcon2 = function23;
            trailingIcon2 = function24;
            prefix2 = function25;
            suffix2 = function26;
            supportingText3 = function27;
            isError3 = isError;
            visualTransformation2 = visualTransformation;
            keyboardOptions2 = keyboardOptions;
            keyboardActions2 = keyboardActions;
            singleLine2 = singleLine;
            maxLines3 = maxLines;
            minLines2 = minLines;
            interactionSource3 = interactionSource;
            shape3 = shape;
            colors3 = colors;
        } else {
            $composer2.startDefaults();
            if (($changed & 1) == 0 || $composer2.getDefaultsInvalid()) {
                Modifier.Companion modifier5 = i8 != 0 ? Modifier.INSTANCE : modifier;
                boolean enabled5 = i9 != 0 ? true : enabled;
                boolean readOnly4 = i10 != 0 ? false : readOnly;
                if ((i & 32) != 0) {
                    ProvidableCompositionLocal<TextStyle> localTextStyle = TextKt.getLocalTextStyle();
                    modifier2 = modifier5;
                    enabled2 = enabled5;
                    ComposerKt.sourceInformationMarkerStart($composer2, 2023513938, "CC:CompositionLocal.kt#9igjgp");
                    Object consume = $composer2.consume(localTextStyle);
                    ComposerKt.sourceInformationMarkerEnd($composer2);
                    textStyle2 = (TextStyle) consume;
                    $dirty4 &= -458753;
                } else {
                    modifier2 = modifier5;
                    enabled2 = enabled5;
                    textStyle2 = textStyle;
                }
                label = i11 != 0 ? null : function2;
                placeholder = i12 != 0 ? null : function22;
                leadingIcon = i13 != 0 ? null : function23;
                trailingIcon = i14 != 0 ? null : function24;
                prefix = i15 != 0 ? null : function25;
                suffix = i16 != 0 ? null : function26;
                supportingText = i17 != 0 ? null : function27;
                isError2 = i2 != 0 ? false : isError;
                VisualTransformation visualTransformation3 = i3 != 0 ? VisualTransformation.INSTANCE.getNone() : visualTransformation;
                KeyboardOptions keyboardOptions3 = i20 != 0 ? KeyboardOptions.INSTANCE.getDefault() : keyboardOptions;
                KeyboardActions keyboardActions3 = i21 != 0 ? KeyboardActions.INSTANCE.getDefault() : keyboardActions;
                boolean singleLine3 = i22 != 0 ? false : singleLine;
                if ((i & 262144) != 0) {
                    maxLines2 = singleLine3 ? 1 : Integer.MAX_VALUE;
                    $dirty13 &= -234881025;
                } else {
                    maxLines2 = maxLines;
                }
                int minLines3 = i23 != 0 ? 1 : minLines;
                if (i24 != 0) {
                    $dirty = $dirty4;
                    $composer2.startReplaceableGroup(-1263323576);
                    ComposerKt.sourceInformation($composer2, "CC(remember):TextField.kt#9igjgp");
                    Object it$iv = $composer2.rememberedValue();
                    $dirty1 = $dirty13;
                    if (it$iv == Composer.INSTANCE.getEmpty()) {
                        value$iv = InteractionSourceKt.MutableInteractionSource();
                        $composer2.updateRememberedValue(value$iv);
                    } else {
                        value$iv = it$iv;
                    }
                    interactionSource2 = (MutableInteractionSource) value$iv;
                    $composer2.endReplaceableGroup();
                } else {
                    $dirty = $dirty4;
                    $dirty1 = $dirty13;
                    interactionSource2 = interactionSource;
                }
                MutableInteractionSource interactionSource4 = interactionSource2;
                if ((2097152 & i) != 0) {
                    shape2 = TextFieldDefaults.INSTANCE.getShape($composer2, 6);
                    $dirty23 &= -113;
                } else {
                    shape2 = shape;
                }
                if ((i & 4194304) != 0) {
                    $dirty2 = $dirty;
                    interactionSource3 = interactionSource4;
                    shape3 = shape2;
                    $dirty12 = $dirty1;
                    colors2 = TextFieldDefaults.INSTANCE.colors($composer2, 6);
                    $dirty22 = $dirty23 & (-897);
                    readOnly2 = readOnly4;
                    visualTransformation2 = visualTransformation3;
                    keyboardOptions2 = keyboardOptions3;
                    keyboardActions2 = keyboardActions3;
                    singleLine2 = singleLine3;
                    maxLines3 = maxLines2;
                    minLines2 = minLines3;
                    modifier3 = modifier2;
                    enabled3 = enabled2;
                } else {
                    Shape shape4 = shape2;
                    modifier3 = modifier2;
                    enabled3 = enabled2;
                    $dirty2 = $dirty;
                    interactionSource3 = interactionSource4;
                    shape3 = shape4;
                    $dirty12 = $dirty1;
                    colors2 = colors;
                    $dirty22 = $dirty23;
                    readOnly2 = readOnly4;
                    visualTransformation2 = visualTransformation3;
                    keyboardOptions2 = keyboardOptions3;
                    keyboardActions2 = keyboardActions3;
                    singleLine2 = singleLine3;
                    maxLines3 = maxLines2;
                    minLines2 = minLines3;
                }
            } else {
                $composer2.skipToGroupEnd();
                if ((i & 32) != 0) {
                    $dirty4 &= -458753;
                }
                if ((262144 & i) != 0) {
                    $dirty13 &= -234881025;
                }
                if ((2097152 & i) != 0) {
                    $dirty23 &= -113;
                }
                if ((i & 4194304) != 0) {
                    $dirty23 &= -897;
                }
                textStyle2 = textStyle;
                label = function2;
                placeholder = function22;
                leadingIcon = function23;
                trailingIcon = function24;
                prefix = function25;
                suffix = function26;
                supportingText = function27;
                isError2 = isError;
                visualTransformation2 = visualTransformation;
                keyboardOptions2 = keyboardOptions;
                keyboardActions2 = keyboardActions;
                singleLine2 = singleLine;
                maxLines3 = maxLines;
                minLines2 = minLines;
                interactionSource3 = interactionSource;
                shape3 = shape;
                colors2 = colors;
                $dirty2 = $dirty4;
                $dirty12 = $dirty13;
                $dirty22 = $dirty23;
                modifier3 = modifier;
                enabled3 = enabled;
                readOnly2 = readOnly;
            }
            $composer2.endDefaults();
            if (ComposerKt.isTraceInProgress()) {
                supportingText2 = supportingText;
                ComposerKt.traceEventStart(-1268528240, $dirty2, $dirty12, "androidx.compose.material3.TextField (TextField.kt:338)");
            } else {
                supportingText2 = supportingText;
            }
            $composer2.startReplaceableGroup(-1263323311);
            ComposerKt.sourceInformation($composer2, "*341@18295L46");
            long $this$takeOrElse_u2dDxMtmZc$iv = textStyle2.m5601getColor0d7_KjU();
            if ($this$takeOrElse_u2dDxMtmZc$iv != Color.INSTANCE.m3782getUnspecified0d7_KjU()) {
                $dirty3 = $dirty2;
                textColor = $this$takeOrElse_u2dDxMtmZc$iv;
            } else {
                $dirty3 = $dirty2;
                textColor = colors2.textColor$material3_release(enabled3, isError2, interactionSource3, $composer2, (($dirty2 >> 9) & 14) | (($dirty12 >> 6) & 112) | (($dirty22 << 6) & 896) | (($dirty22 << 3) & 7168)).getValue().m3756unboximpl();
            }
            $composer2.endReplaceableGroup();
            final TextStyle mergedTextStyle = textStyle2.merge(new TextStyle(textColor, 0L, (FontWeight) null, (FontStyle) null, (FontSynthesis) null, (FontFamily) null, (String) null, 0L, (BaselineShift) null, (TextGeometricTransform) null, (LocaleList) null, 0L, (TextDecoration) null, (Shadow) null, (DrawStyle) null, 0, 0, 0L, (TextIndent) null, (PlatformTextStyle) null, (LineHeightStyle) null, 0, 0, (TextMotion) null, 16777214, (DefaultConstructorMarker) null));
            TextStyle textStyle4 = textStyle2;
            final TextFieldColors colors4 = colors2;
            final Modifier modifier6 = modifier3;
            final boolean z = isError2;
            final boolean z2 = enabled3;
            final boolean z3 = readOnly2;
            final KeyboardOptions keyboardOptions4 = keyboardOptions2;
            final KeyboardActions keyboardActions4 = keyboardActions2;
            final boolean z4 = singleLine2;
            final int i25 = maxLines3;
            final int i26 = minLines2;
            final VisualTransformation visualTransformation4 = visualTransformation2;
            final MutableInteractionSource mutableInteractionSource = interactionSource3;
            final Function2 function28 = label;
            final Function2 function29 = placeholder;
            final Function2 function210 = leadingIcon;
            final Function2 function211 = trailingIcon;
            final Function2 function212 = prefix;
            final Function2 function213 = suffix;
            final Function2 function214 = supportingText2;
            final Shape shape5 = shape3;
            Modifier modifier7 = modifier3;
            boolean enabled6 = enabled3;
            CompositionLocalKt.CompositionLocalProvider(TextSelectionColorsKt.getLocalTextSelectionColors().provides(colors4.getSelectionColors($composer2, ($dirty22 >> 6) & 14)), ComposableLambdaKt.composableLambda($composer2, -1163788208, true, new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.TextFieldKt$TextField$5
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

                public final void invoke(Composer $composer3, int $changed3) {
                    ComposerKt.sourceInformation($composer3, "C349@18647L38,358@19050L20,346@18524L1819:TextField.kt#uh7d8r");
                    if (($changed3 & 3) != 2 || !$composer3.getSkipping()) {
                        if (ComposerKt.isTraceInProgress()) {
                            ComposerKt.traceEventStart(-1163788208, $changed3, -1, "androidx.compose.material3.TextField.<anonymous> (TextField.kt:346)");
                        }
                        Modifier modifier8 = Modifier.this;
                        boolean z5 = z;
                        Strings.Companion companion = Strings.INSTANCE;
                        Modifier m595defaultMinSizeVpY3zN4 = SizeKt.m595defaultMinSizeVpY3zN4(TextFieldImplKt.defaultErrorSemantics(modifier8, z5, Strings_androidKt.m2306getStringNWtq28(Strings.m2237constructorimpl(androidx.compose.ui.R.string.default_error_message), $composer3, 0)), TextFieldDefaults.INSTANCE.m2440getMinWidthD9Ej5fM(), TextFieldDefaults.INSTANCE.m2439getMinHeightD9Ej5fM());
                        SolidColor solidColor = new SolidColor(colors4.cursorColor$material3_release(z, $composer3, 0).getValue().m3756unboximpl(), null);
                        TextFieldValue textFieldValue = value;
                        Function1<TextFieldValue, Unit> function12 = function1;
                        boolean z6 = z2;
                        boolean z7 = z3;
                        TextStyle textStyle5 = mergedTextStyle;
                        KeyboardOptions keyboardOptions5 = keyboardOptions4;
                        KeyboardActions keyboardActions5 = keyboardActions4;
                        boolean z8 = z4;
                        int i27 = i25;
                        int i28 = i26;
                        VisualTransformation visualTransformation5 = visualTransformation4;
                        MutableInteractionSource mutableInteractionSource2 = mutableInteractionSource;
                        SolidColor solidColor2 = solidColor;
                        final TextFieldValue textFieldValue2 = value;
                        final boolean z9 = z2;
                        final boolean z10 = z4;
                        final VisualTransformation visualTransformation6 = visualTransformation4;
                        final MutableInteractionSource mutableInteractionSource3 = mutableInteractionSource;
                        final boolean z11 = z;
                        final Function2<Composer, Integer, Unit> function215 = function28;
                        final Function2<Composer, Integer, Unit> function216 = function29;
                        final Function2<Composer, Integer, Unit> function217 = function210;
                        final Function2<Composer, Integer, Unit> function218 = function211;
                        final Function2<Composer, Integer, Unit> function219 = function212;
                        final Function2<Composer, Integer, Unit> function220 = function213;
                        final Function2<Composer, Integer, Unit> function221 = function214;
                        final Shape shape6 = shape5;
                        final TextFieldColors textFieldColors = colors4;
                        BasicTextFieldKt.BasicTextField(textFieldValue, function12, m595defaultMinSizeVpY3zN4, z6, z7, textStyle5, keyboardOptions5, keyboardActions5, z8, i27, i28, visualTransformation5, (Function1<? super TextLayoutResult, Unit>) null, mutableInteractionSource2, solidColor2, ComposableLambdaKt.composableLambda($composer3, 1751957978, true, new Function3<Function2<? super Composer, ? super Integer, ? extends Unit>, Composer, Integer, Unit>() { // from class: androidx.compose.material3.TextFieldKt$TextField$5.1
                            /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
                            /* JADX WARN: Multi-variable type inference failed */
                            {
                                super(3);
                            }

                            @Override // kotlin.jvm.functions.Function3
                            public /* bridge */ /* synthetic */ Unit invoke(Function2<? super Composer, ? super Integer, ? extends Unit> function222, Composer composer, Integer num) {
                                invoke((Function2<? super Composer, ? super Integer, Unit>) function222, composer, num.intValue());
                                return Unit.INSTANCE;
                            }

                            public final void invoke(Function2<? super Composer, ? super Integer, Unit> function222, Composer $composer4, int $changed4) {
                                ComposerKt.sourceInformation($composer4, "C368@19571L748:TextField.kt#uh7d8r");
                                int $dirty5 = $changed4;
                                if (($changed4 & 6) == 0) {
                                    $dirty5 |= $composer4.changedInstance(function222) ? 4 : 2;
                                }
                                int $dirty6 = $dirty5;
                                if (($dirty6 & 19) == 18 && $composer4.getSkipping()) {
                                    $composer4.skipToGroupEnd();
                                    return;
                                }
                                if (ComposerKt.isTraceInProgress()) {
                                    ComposerKt.traceEventStart(1751957978, $dirty6, -1, "androidx.compose.material3.TextField.<anonymous>.<anonymous> (TextField.kt:368)");
                                }
                                TextFieldDefaults.INSTANCE.DecorationBox(TextFieldValue.this.getText(), function222, z9, z10, visualTransformation6, mutableInteractionSource3, z11, function215, function216, function217, function218, function219, function220, function221, shape6, textFieldColors, null, null, $composer4, ($dirty6 << 3) & 112, 100663296, ProfileVerifier.CompilationStatus.RESULT_CODE_ERROR_CANT_WRITE_PROFILE_VERIFICATION_RESULT_CACHE_FILE);
                                if (ComposerKt.isTraceInProgress()) {
                                    ComposerKt.traceEventEnd();
                                }
                            }
                        }), $composer3, 0, ProfileVerifier.CompilationStatus.RESULT_CODE_ERROR_CANT_WRITE_PROFILE_VERIFICATION_RESULT_CACHE_FILE, 4096);
                        if (ComposerKt.isTraceInProgress()) {
                            ComposerKt.traceEventEnd();
                            return;
                        }
                        return;
                    }
                    $composer3.skipToGroupEnd();
                }
            }), $composer2, ProvidedValue.$stable | 0 | 48);
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventEnd();
            }
            textStyle3 = textStyle4;
            modifier4 = modifier7;
            enabled4 = enabled6;
            supportingText3 = supportingText2;
            readOnly3 = readOnly2;
            placeholder2 = placeholder;
            leadingIcon2 = leadingIcon;
            trailingIcon2 = trailingIcon;
            prefix2 = prefix;
            suffix2 = suffix;
            label2 = label;
            isError3 = isError2;
            colors3 = colors4;
        }
        ScopeUpdateScope endRestartGroup = $composer2.endRestartGroup();
        if (endRestartGroup != null) {
            final Modifier modifier8 = modifier4;
            final boolean z5 = enabled4;
            final boolean z6 = readOnly3;
            final TextStyle textStyle5 = textStyle3;
            final Function2 function215 = label2;
            final Function2 function216 = placeholder2;
            final Function2 function217 = leadingIcon2;
            final Function2 function218 = trailingIcon2;
            final Function2 function219 = prefix2;
            final Function2 function220 = suffix2;
            final Function2 function221 = supportingText3;
            final boolean z7 = isError3;
            final VisualTransformation visualTransformation5 = visualTransformation2;
            final KeyboardOptions keyboardOptions5 = keyboardOptions2;
            final KeyboardActions keyboardActions5 = keyboardActions2;
            final boolean z8 = singleLine2;
            final int i27 = maxLines3;
            final int i28 = minLines2;
            final MutableInteractionSource mutableInteractionSource2 = interactionSource3;
            final Shape shape6 = shape3;
            final TextFieldColors textFieldColors = colors3;
            endRestartGroup.updateScope(new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.TextFieldKt$TextField$6
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

                public final void invoke(Composer composer, int i29) {
                    TextFieldKt.TextField(TextFieldValue.this, function1, modifier8, z5, z6, textStyle5, function215, function216, function217, function218, function219, function220, function221, z7, visualTransformation5, keyboardOptions5, keyboardActions5, z8, i27, i28, mutableInteractionSource2, shape6, textFieldColors, composer, RecomposeScopeImplKt.updateChangedFlags($changed | 1), RecomposeScopeImplKt.updateChangedFlags($changed1), RecomposeScopeImplKt.updateChangedFlags($changed2), i);
                }
            });
        }
    }

    @Deprecated(level = DeprecationLevel.HIDDEN, message = "Use overload with prefix and suffix parameters")
    public static final /* synthetic */ void TextField(final String value, final Function1 onValueChange, Modifier modifier, boolean enabled, boolean readOnly, TextStyle textStyle, Function2 label, Function2 placeholder, Function2 leadingIcon, Function2 trailingIcon, Function2 supportingText, boolean isError, VisualTransformation visualTransformation, KeyboardOptions keyboardOptions, KeyboardActions keyboardActions, boolean singleLine, int maxLines, int minLines, MutableInteractionSource interactionSource, Shape shape, TextFieldColors colors, Composer $composer, final int $changed, final int $changed1, final int $changed2, final int i) {
        int i2;
        Modifier modifier2;
        boolean enabled2;
        boolean readOnly2;
        TextStyle textStyle2;
        Function2 label2;
        Function2 placeholder2;
        Function2 leadingIcon2;
        Function2 trailingIcon2;
        Function2 supportingText2;
        boolean isError2;
        VisualTransformation visualTransformation2;
        KeyboardOptions keyboardOptions2;
        KeyboardActions keyboardActions2;
        int maxLines2;
        int $dirty;
        TextStyle textStyle3;
        MutableInteractionSource interactionSource2;
        Shape shape2;
        Modifier modifier3;
        boolean enabled3;
        int $dirty2;
        MutableInteractionSource interactionSource3;
        int $dirty1;
        TextFieldColors colors2;
        int $dirty22;
        Shape shape3;
        boolean singleLine2;
        int maxLines3;
        int minLines2;
        boolean readOnly3;
        TextStyle textStyle4;
        Object value$iv;
        Composer $composer2;
        KeyboardActions keyboardActions3;
        KeyboardActions keyboardActions4;
        Modifier modifier4;
        boolean enabled4;
        boolean readOnly4;
        TextStyle textStyle5;
        Function2 leadingIcon3;
        Function2 placeholder3;
        Function2 trailingIcon3;
        Function2 supportingText3;
        boolean isError3;
        VisualTransformation visualTransformation3;
        KeyboardOptions keyboardOptions3;
        Function2 label3;
        int i3;
        int i4;
        int i5;
        int i6;
        Composer $composer3 = $composer.startRestartGroup(-1500728277);
        ComposerKt.sourceInformation($composer3, "C(TextField)P(19,11,10,1,13,17,6,12,7,18,16,3,20,5,4,15,8,9,2,14)400@20694L7,413@21354L39,414@21432L5,415@21487L8,417@21504L763:TextField.kt#uh7d8r");
        int $dirty3 = $changed;
        int $dirty12 = $changed1;
        int $dirty23 = $changed2;
        if ((i & 1) != 0) {
            $dirty3 |= 6;
        } else if (($changed & 6) == 0) {
            $dirty3 |= $composer3.changed(value) ? 4 : 2;
        }
        if ((i & 2) != 0) {
            $dirty3 |= 48;
        } else if (($changed & 48) == 0) {
            $dirty3 |= $composer3.changedInstance(onValueChange) ? 32 : 16;
        }
        int i7 = i & 4;
        if (i7 != 0) {
            $dirty3 |= 384;
        } else if (($changed & 384) == 0) {
            $dirty3 |= $composer3.changed(modifier) ? 256 : 128;
        }
        int i8 = i & 8;
        if (i8 != 0) {
            $dirty3 |= 3072;
        } else if (($changed & 3072) == 0) {
            $dirty3 |= $composer3.changed(enabled) ? 2048 : 1024;
        }
        int i9 = i & 16;
        if (i9 != 0) {
            $dirty3 |= 24576;
        } else if (($changed & 24576) == 0) {
            $dirty3 |= $composer3.changed(readOnly) ? 16384 : 8192;
        }
        if (($changed & ProfileVerifier.CompilationStatus.RESULT_CODE_ERROR_CANT_WRITE_PROFILE_VERIFICATION_RESULT_CACHE_FILE) == 0) {
            if ((i & 32) == 0 && $composer3.changed(textStyle)) {
                i6 = 131072;
                $dirty3 |= i6;
            }
            i6 = 65536;
            $dirty3 |= i6;
        }
        int i10 = i & 64;
        if (i10 != 0) {
            $dirty3 |= 1572864;
        } else if (($changed & 1572864) == 0) {
            $dirty3 |= $composer3.changedInstance(label) ? 1048576 : 524288;
        }
        int i11 = i & 128;
        if (i11 != 0) {
            $dirty3 |= 12582912;
        } else if (($changed & 12582912) == 0) {
            $dirty3 |= $composer3.changedInstance(placeholder) ? 8388608 : 4194304;
        }
        int i12 = i & 256;
        if (i12 != 0) {
            $dirty3 |= 100663296;
        } else if (($changed & 100663296) == 0) {
            $dirty3 |= $composer3.changedInstance(leadingIcon) ? AccessibilityEventCompat.TYPE_VIEW_TARGETED_BY_SCROLL : 33554432;
        }
        int i13 = i & 512;
        if (i13 != 0) {
            $dirty3 |= 805306368;
        } else if (($changed & 805306368) == 0) {
            $dirty3 |= $composer3.changedInstance(trailingIcon) ? 536870912 : 268435456;
        }
        int i14 = i & 1024;
        if (i14 != 0) {
            $dirty12 |= 6;
        } else if (($changed1 & 6) == 0) {
            $dirty12 |= $composer3.changedInstance(supportingText) ? 4 : 2;
        }
        int i15 = i & 2048;
        if (i15 != 0) {
            $dirty12 |= 48;
        } else if (($changed1 & 48) == 0) {
            $dirty12 |= $composer3.changed(isError) ? 32 : 16;
        }
        int i16 = i & 4096;
        if (i16 != 0) {
            $dirty12 |= 384;
        } else if (($changed1 & 384) == 0) {
            $dirty12 |= $composer3.changed(visualTransformation) ? 256 : 128;
        }
        int i17 = i & 8192;
        if (i17 != 0) {
            $dirty12 |= 3072;
        } else if (($changed1 & 3072) == 0) {
            $dirty12 |= $composer3.changed(keyboardOptions) ? 2048 : 1024;
        }
        int i18 = i & 16384;
        if (i18 != 0) {
            $dirty12 |= 24576;
            i2 = i18;
        } else {
            i2 = i18;
            if (($changed1 & 24576) == 0) {
                $dirty12 |= $composer3.changed(keyboardActions) ? 16384 : 8192;
            }
        }
        int i19 = i & 32768;
        if (i19 != 0) {
            $dirty12 |= ProfileVerifier.CompilationStatus.RESULT_CODE_ERROR_CANT_WRITE_PROFILE_VERIFICATION_RESULT_CACHE_FILE;
        } else if (($changed1 & ProfileVerifier.CompilationStatus.RESULT_CODE_ERROR_CANT_WRITE_PROFILE_VERIFICATION_RESULT_CACHE_FILE) == 0) {
            $dirty12 |= $composer3.changed(singleLine) ? 131072 : 65536;
        }
        if (($changed1 & 1572864) == 0) {
            if ((i & 65536) == 0 && $composer3.changed(maxLines)) {
                i5 = 1048576;
                $dirty12 |= i5;
            }
            i5 = 524288;
            $dirty12 |= i5;
        }
        int i20 = i & 131072;
        if (i20 != 0) {
            $dirty12 |= 12582912;
        } else if (($changed1 & 12582912) == 0) {
            $dirty12 |= $composer3.changed(minLines) ? 8388608 : 4194304;
        }
        int i21 = i & 262144;
        if (i21 != 0) {
            $dirty12 |= 100663296;
        } else if (($changed1 & 100663296) == 0) {
            $dirty12 |= $composer3.changed(interactionSource) ? AccessibilityEventCompat.TYPE_VIEW_TARGETED_BY_SCROLL : 33554432;
        }
        if (($changed1 & 805306368) == 0) {
            if ((i & 524288) == 0 && $composer3.changed(shape)) {
                i4 = 536870912;
                $dirty12 |= i4;
            }
            i4 = 268435456;
            $dirty12 |= i4;
        }
        if (($changed2 & 6) == 0) {
            if ((i & 1048576) == 0 && $composer3.changed(colors)) {
                i3 = 4;
                $dirty23 |= i3;
            }
            i3 = 2;
            $dirty23 |= i3;
        }
        if (($dirty3 & 306783379) == 306783378 && (306783379 & $dirty12) == 306783378 && ($dirty23 & 3) == 2 && $composer3.getSkipping()) {
            $composer3.skipToGroupEnd();
            modifier4 = modifier;
            enabled4 = enabled;
            readOnly4 = readOnly;
            textStyle5 = textStyle;
            label3 = label;
            placeholder3 = placeholder;
            leadingIcon3 = leadingIcon;
            trailingIcon3 = trailingIcon;
            supportingText3 = supportingText;
            isError3 = isError;
            visualTransformation3 = visualTransformation;
            keyboardOptions3 = keyboardOptions;
            keyboardActions4 = keyboardActions;
            singleLine2 = singleLine;
            maxLines3 = maxLines;
            minLines2 = minLines;
            interactionSource3 = interactionSource;
            shape3 = shape;
            colors2 = colors;
            $composer2 = $composer3;
        } else {
            $composer3.startDefaults();
            if (($changed & 1) == 0 || $composer3.getDefaultsInvalid()) {
                Modifier.Companion modifier5 = i7 != 0 ? Modifier.INSTANCE : modifier;
                boolean enabled5 = i8 != 0 ? true : enabled;
                boolean readOnly5 = i9 != 0 ? false : readOnly;
                if ((i & 32) != 0) {
                    modifier2 = modifier5;
                    ProvidableCompositionLocal<TextStyle> localTextStyle = TextKt.getLocalTextStyle();
                    enabled2 = enabled5;
                    readOnly2 = readOnly5;
                    ComposerKt.sourceInformationMarkerStart($composer3, 2023513938, "CC:CompositionLocal.kt#9igjgp");
                    Object consume = $composer3.consume(localTextStyle);
                    ComposerKt.sourceInformationMarkerEnd($composer3);
                    textStyle2 = (TextStyle) consume;
                    $dirty3 &= -458753;
                } else {
                    modifier2 = modifier5;
                    enabled2 = enabled5;
                    readOnly2 = readOnly5;
                    textStyle2 = textStyle;
                }
                label2 = i10 != 0 ? null : label;
                placeholder2 = i11 != 0 ? null : placeholder;
                leadingIcon2 = i12 != 0 ? null : leadingIcon;
                trailingIcon2 = i13 != 0 ? null : trailingIcon;
                supportingText2 = i14 != 0 ? null : supportingText;
                isError2 = i15 != 0 ? false : isError;
                visualTransformation2 = i16 != 0 ? VisualTransformation.INSTANCE.getNone() : visualTransformation;
                keyboardOptions2 = i17 != 0 ? KeyboardOptions.INSTANCE.getDefault() : keyboardOptions;
                keyboardActions2 = i2 != 0 ? KeyboardActions.INSTANCE.getDefault() : keyboardActions;
                boolean singleLine3 = i19 != 0 ? false : singleLine;
                if ((i & 65536) != 0) {
                    maxLines2 = singleLine3 ? 1 : Integer.MAX_VALUE;
                    $dirty12 &= -3670017;
                } else {
                    maxLines2 = maxLines;
                }
                int minLines3 = i20 != 0 ? 1 : minLines;
                if (i21 != 0) {
                    $dirty = $dirty3;
                    $composer3.startReplaceableGroup(-1263320224);
                    ComposerKt.sourceInformation($composer3, "CC(remember):TextField.kt#9igjgp");
                    Object it$iv = $composer3.rememberedValue();
                    textStyle3 = textStyle2;
                    if (it$iv == Composer.INSTANCE.getEmpty()) {
                        value$iv = InteractionSourceKt.MutableInteractionSource();
                        $composer3.updateRememberedValue(value$iv);
                    } else {
                        value$iv = it$iv;
                    }
                    interactionSource2 = (MutableInteractionSource) value$iv;
                    $composer3.endReplaceableGroup();
                } else {
                    $dirty = $dirty3;
                    textStyle3 = textStyle2;
                    interactionSource2 = interactionSource;
                }
                MutableInteractionSource interactionSource4 = interactionSource2;
                if ((i & 524288) != 0) {
                    shape2 = TextFieldDefaults.INSTANCE.getShape($composer3, 6);
                    $dirty12 &= -1879048193;
                } else {
                    shape2 = shape;
                }
                if ((i & 1048576) != 0) {
                    int $dirty13 = $dirty12;
                    int i22 = $dirty23 & (-15);
                    readOnly3 = readOnly2;
                    $dirty2 = $dirty;
                    interactionSource3 = interactionSource4;
                    $dirty1 = $dirty13;
                    colors2 = TextFieldDefaults.INSTANCE.colors($composer3, 6);
                    $dirty22 = i22;
                    shape3 = shape2;
                    singleLine2 = singleLine3;
                    maxLines3 = maxLines2;
                    minLines2 = minLines3;
                    modifier3 = modifier2;
                    enabled3 = enabled2;
                    textStyle4 = textStyle3;
                } else {
                    int $dirty14 = $dirty12;
                    modifier3 = modifier2;
                    enabled3 = enabled2;
                    $dirty2 = $dirty;
                    interactionSource3 = interactionSource4;
                    $dirty1 = $dirty14;
                    colors2 = colors;
                    $dirty22 = $dirty23;
                    shape3 = shape2;
                    singleLine2 = singleLine3;
                    maxLines3 = maxLines2;
                    minLines2 = minLines3;
                    readOnly3 = readOnly2;
                    textStyle4 = textStyle3;
                }
            } else {
                $composer3.skipToGroupEnd();
                if ((i & 32) != 0) {
                    $dirty3 &= -458753;
                }
                if ((i & 65536) != 0) {
                    $dirty12 &= -3670017;
                }
                if ((i & 524288) != 0) {
                    $dirty12 &= -1879048193;
                }
                if ((i & 1048576) != 0) {
                    $dirty23 &= -15;
                }
                textStyle4 = textStyle;
                label2 = label;
                placeholder2 = placeholder;
                leadingIcon2 = leadingIcon;
                trailingIcon2 = trailingIcon;
                supportingText2 = supportingText;
                isError2 = isError;
                visualTransformation2 = visualTransformation;
                keyboardOptions2 = keyboardOptions;
                keyboardActions2 = keyboardActions;
                singleLine2 = singleLine;
                maxLines3 = maxLines;
                minLines2 = minLines;
                interactionSource3 = interactionSource;
                shape3 = shape;
                colors2 = colors;
                $dirty2 = $dirty3;
                $dirty1 = $dirty12;
                $dirty22 = $dirty23;
                modifier3 = modifier;
                enabled3 = enabled;
                readOnly3 = readOnly;
            }
            $composer3.endDefaults();
            if (ComposerKt.isTraceInProgress()) {
                $composer2 = $composer3;
                keyboardActions3 = keyboardActions2;
                ComposerKt.traceEventStart(-1500728277, $dirty2, $dirty1, "androidx.compose.material3.TextField (TextField.kt:416)");
            } else {
                $composer2 = $composer3;
                keyboardActions3 = keyboardActions2;
            }
            TextField(value, (Function1<? super String, Unit>) onValueChange, modifier3, enabled3, readOnly3, textStyle4, (Function2<? super Composer, ? super Integer, Unit>) label2, (Function2<? super Composer, ? super Integer, Unit>) placeholder2, (Function2<? super Composer, ? super Integer, Unit>) leadingIcon2, (Function2<? super Composer, ? super Integer, Unit>) trailingIcon2, (Function2<? super Composer, ? super Integer, Unit>) null, (Function2<? super Composer, ? super Integer, Unit>) null, (Function2<? super Composer, ? super Integer, Unit>) supportingText2, isError2, visualTransformation2, keyboardOptions2, keyboardActions3, singleLine2, maxLines3, minLines2, interactionSource3, shape3, colors2, $composer2, ($dirty2 & 14) | ($dirty2 & 112) | ($dirty2 & 896) | ($dirty2 & 7168) | (57344 & $dirty2) | (458752 & $dirty2) | (3670016 & $dirty2) | (29360128 & $dirty2) | (234881024 & $dirty2) | (1879048192 & $dirty2), (($dirty1 << 6) & 896) | 54 | (($dirty1 << 6) & 7168) | (($dirty1 << 6) & 57344) | (($dirty1 << 6) & 458752) | (($dirty1 << 6) & 3670016) | (($dirty1 << 6) & 29360128) | (($dirty1 << 6) & 234881024) | (($dirty1 << 6) & 1879048192), (($dirty1 >> 24) & 14) | (($dirty1 >> 24) & 112) | (($dirty22 << 6) & 896), 0);
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventEnd();
            }
            keyboardActions4 = keyboardActions3;
            modifier4 = modifier3;
            enabled4 = enabled3;
            readOnly4 = readOnly3;
            textStyle5 = textStyle4;
            leadingIcon3 = leadingIcon2;
            placeholder3 = placeholder2;
            trailingIcon3 = trailingIcon2;
            supportingText3 = supportingText2;
            isError3 = isError2;
            visualTransformation3 = visualTransformation2;
            keyboardOptions3 = keyboardOptions2;
            label3 = label2;
        }
        ScopeUpdateScope endRestartGroup = $composer2.endRestartGroup();
        if (endRestartGroup != null) {
            final Modifier modifier6 = modifier4;
            final boolean z = enabled4;
            final boolean z2 = readOnly4;
            final TextStyle textStyle6 = textStyle5;
            final Function2 function2 = label3;
            final Function2 function22 = placeholder3;
            final Function2 function23 = leadingIcon3;
            final Function2 function24 = trailingIcon3;
            final Function2 function25 = supportingText3;
            final boolean z3 = isError3;
            final VisualTransformation visualTransformation4 = visualTransformation3;
            final KeyboardOptions keyboardOptions4 = keyboardOptions3;
            final KeyboardActions keyboardActions5 = keyboardActions4;
            final boolean z4 = singleLine2;
            final int i23 = maxLines3;
            final int i24 = minLines2;
            final MutableInteractionSource mutableInteractionSource = interactionSource3;
            final Shape shape4 = shape3;
            final TextFieldColors textFieldColors = colors2;
            endRestartGroup.updateScope(new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.TextFieldKt$TextField$8
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

                public final void invoke(Composer composer, int i25) {
                    TextFieldKt.TextField(value, onValueChange, modifier6, z, z2, textStyle6, function2, function22, function23, function24, function25, z3, visualTransformation4, keyboardOptions4, keyboardActions5, z4, i23, i24, mutableInteractionSource, shape4, textFieldColors, composer, RecomposeScopeImplKt.updateChangedFlags($changed | 1), RecomposeScopeImplKt.updateChangedFlags($changed1), RecomposeScopeImplKt.updateChangedFlags($changed2), i);
                }
            });
        }
    }

    @Deprecated(level = DeprecationLevel.HIDDEN, message = "Use overload with prefix and suffix parameters")
    public static final /* synthetic */ void TextField(final TextFieldValue value, final Function1 onValueChange, Modifier modifier, boolean enabled, boolean readOnly, TextStyle textStyle, Function2 label, Function2 placeholder, Function2 leadingIcon, Function2 trailingIcon, Function2 supportingText, boolean isError, VisualTransformation visualTransformation, KeyboardOptions keyboardOptions, KeyboardActions keyboardActions, boolean singleLine, int maxLines, int minLines, MutableInteractionSource interactionSource, Shape shape, TextFieldColors colors, Composer $composer, final int $changed, final int $changed1, final int $changed2, final int i) {
        int i2;
        Modifier modifier2;
        boolean enabled2;
        boolean readOnly2;
        TextStyle textStyle2;
        Function2 label2;
        Function2 placeholder2;
        Function2 leadingIcon2;
        Function2 trailingIcon2;
        Function2 supportingText2;
        boolean isError2;
        VisualTransformation visualTransformation2;
        KeyboardOptions keyboardOptions2;
        KeyboardActions keyboardActions2;
        int maxLines2;
        int $dirty;
        TextStyle textStyle3;
        MutableInteractionSource interactionSource2;
        Shape shape2;
        Modifier modifier3;
        boolean enabled3;
        int $dirty2;
        MutableInteractionSource interactionSource3;
        int $dirty1;
        TextFieldColors colors2;
        int $dirty22;
        Shape shape3;
        boolean singleLine2;
        int maxLines3;
        int minLines2;
        boolean readOnly3;
        TextStyle textStyle4;
        Object value$iv;
        Composer $composer2;
        KeyboardActions keyboardActions3;
        KeyboardActions keyboardActions4;
        Modifier modifier4;
        boolean enabled4;
        boolean readOnly4;
        TextStyle textStyle5;
        Function2 leadingIcon3;
        Function2 placeholder3;
        Function2 trailingIcon3;
        Function2 supportingText3;
        boolean isError3;
        VisualTransformation visualTransformation3;
        KeyboardOptions keyboardOptions3;
        Function2 label3;
        int i3;
        int i4;
        int i5;
        int i6;
        Composer $composer3 = $composer.startRestartGroup(1523846136);
        ComposerKt.sourceInformation($composer3, "C(TextField)P(19,11,10,1,13,17,6,12,7,18,16,3,20,5,4,15,8,9,2,14)453@22628L7,466@23288L39,467@23366L5,468@23421L8,470@23438L763:TextField.kt#uh7d8r");
        int $dirty3 = $changed;
        int $dirty12 = $changed1;
        int $dirty23 = $changed2;
        if ((i & 1) != 0) {
            $dirty3 |= 6;
        } else if (($changed & 6) == 0) {
            $dirty3 |= $composer3.changed(value) ? 4 : 2;
        }
        if ((i & 2) != 0) {
            $dirty3 |= 48;
        } else if (($changed & 48) == 0) {
            $dirty3 |= $composer3.changedInstance(onValueChange) ? 32 : 16;
        }
        int i7 = i & 4;
        if (i7 != 0) {
            $dirty3 |= 384;
        } else if (($changed & 384) == 0) {
            $dirty3 |= $composer3.changed(modifier) ? 256 : 128;
        }
        int i8 = i & 8;
        if (i8 != 0) {
            $dirty3 |= 3072;
        } else if (($changed & 3072) == 0) {
            $dirty3 |= $composer3.changed(enabled) ? 2048 : 1024;
        }
        int i9 = i & 16;
        if (i9 != 0) {
            $dirty3 |= 24576;
        } else if (($changed & 24576) == 0) {
            $dirty3 |= $composer3.changed(readOnly) ? 16384 : 8192;
        }
        if (($changed & ProfileVerifier.CompilationStatus.RESULT_CODE_ERROR_CANT_WRITE_PROFILE_VERIFICATION_RESULT_CACHE_FILE) == 0) {
            if ((i & 32) == 0 && $composer3.changed(textStyle)) {
                i6 = 131072;
                $dirty3 |= i6;
            }
            i6 = 65536;
            $dirty3 |= i6;
        }
        int i10 = i & 64;
        if (i10 != 0) {
            $dirty3 |= 1572864;
        } else if (($changed & 1572864) == 0) {
            $dirty3 |= $composer3.changedInstance(label) ? 1048576 : 524288;
        }
        int i11 = i & 128;
        if (i11 != 0) {
            $dirty3 |= 12582912;
        } else if (($changed & 12582912) == 0) {
            $dirty3 |= $composer3.changedInstance(placeholder) ? 8388608 : 4194304;
        }
        int i12 = i & 256;
        if (i12 != 0) {
            $dirty3 |= 100663296;
        } else if (($changed & 100663296) == 0) {
            $dirty3 |= $composer3.changedInstance(leadingIcon) ? AccessibilityEventCompat.TYPE_VIEW_TARGETED_BY_SCROLL : 33554432;
        }
        int i13 = i & 512;
        if (i13 != 0) {
            $dirty3 |= 805306368;
        } else if (($changed & 805306368) == 0) {
            $dirty3 |= $composer3.changedInstance(trailingIcon) ? 536870912 : 268435456;
        }
        int i14 = i & 1024;
        if (i14 != 0) {
            $dirty12 |= 6;
        } else if (($changed1 & 6) == 0) {
            $dirty12 |= $composer3.changedInstance(supportingText) ? 4 : 2;
        }
        int i15 = i & 2048;
        if (i15 != 0) {
            $dirty12 |= 48;
        } else if (($changed1 & 48) == 0) {
            $dirty12 |= $composer3.changed(isError) ? 32 : 16;
        }
        int i16 = i & 4096;
        if (i16 != 0) {
            $dirty12 |= 384;
        } else if (($changed1 & 384) == 0) {
            $dirty12 |= $composer3.changed(visualTransformation) ? 256 : 128;
        }
        int i17 = i & 8192;
        if (i17 != 0) {
            $dirty12 |= 3072;
        } else if (($changed1 & 3072) == 0) {
            $dirty12 |= $composer3.changed(keyboardOptions) ? 2048 : 1024;
        }
        int i18 = i & 16384;
        if (i18 != 0) {
            $dirty12 |= 24576;
            i2 = i18;
        } else {
            i2 = i18;
            if (($changed1 & 24576) == 0) {
                $dirty12 |= $composer3.changed(keyboardActions) ? 16384 : 8192;
            }
        }
        int i19 = i & 32768;
        if (i19 != 0) {
            $dirty12 |= ProfileVerifier.CompilationStatus.RESULT_CODE_ERROR_CANT_WRITE_PROFILE_VERIFICATION_RESULT_CACHE_FILE;
        } else if (($changed1 & ProfileVerifier.CompilationStatus.RESULT_CODE_ERROR_CANT_WRITE_PROFILE_VERIFICATION_RESULT_CACHE_FILE) == 0) {
            $dirty12 |= $composer3.changed(singleLine) ? 131072 : 65536;
        }
        if (($changed1 & 1572864) == 0) {
            if ((i & 65536) == 0 && $composer3.changed(maxLines)) {
                i5 = 1048576;
                $dirty12 |= i5;
            }
            i5 = 524288;
            $dirty12 |= i5;
        }
        int i20 = i & 131072;
        if (i20 != 0) {
            $dirty12 |= 12582912;
        } else if (($changed1 & 12582912) == 0) {
            $dirty12 |= $composer3.changed(minLines) ? 8388608 : 4194304;
        }
        int i21 = i & 262144;
        if (i21 != 0) {
            $dirty12 |= 100663296;
        } else if (($changed1 & 100663296) == 0) {
            $dirty12 |= $composer3.changed(interactionSource) ? AccessibilityEventCompat.TYPE_VIEW_TARGETED_BY_SCROLL : 33554432;
        }
        if (($changed1 & 805306368) == 0) {
            if ((i & 524288) == 0 && $composer3.changed(shape)) {
                i4 = 536870912;
                $dirty12 |= i4;
            }
            i4 = 268435456;
            $dirty12 |= i4;
        }
        if (($changed2 & 6) == 0) {
            if ((i & 1048576) == 0 && $composer3.changed(colors)) {
                i3 = 4;
                $dirty23 |= i3;
            }
            i3 = 2;
            $dirty23 |= i3;
        }
        if (($dirty3 & 306783379) == 306783378 && (306783379 & $dirty12) == 306783378 && ($dirty23 & 3) == 2 && $composer3.getSkipping()) {
            $composer3.skipToGroupEnd();
            modifier4 = modifier;
            enabled4 = enabled;
            readOnly4 = readOnly;
            textStyle5 = textStyle;
            label3 = label;
            placeholder3 = placeholder;
            leadingIcon3 = leadingIcon;
            trailingIcon3 = trailingIcon;
            supportingText3 = supportingText;
            isError3 = isError;
            visualTransformation3 = visualTransformation;
            keyboardOptions3 = keyboardOptions;
            keyboardActions4 = keyboardActions;
            singleLine2 = singleLine;
            maxLines3 = maxLines;
            minLines2 = minLines;
            interactionSource3 = interactionSource;
            shape3 = shape;
            colors2 = colors;
            $composer2 = $composer3;
        } else {
            $composer3.startDefaults();
            if (($changed & 1) == 0 || $composer3.getDefaultsInvalid()) {
                Modifier.Companion modifier5 = i7 != 0 ? Modifier.INSTANCE : modifier;
                boolean enabled5 = i8 != 0 ? true : enabled;
                boolean readOnly5 = i9 != 0 ? false : readOnly;
                if ((i & 32) != 0) {
                    modifier2 = modifier5;
                    ProvidableCompositionLocal<TextStyle> localTextStyle = TextKt.getLocalTextStyle();
                    enabled2 = enabled5;
                    readOnly2 = readOnly5;
                    ComposerKt.sourceInformationMarkerStart($composer3, 2023513938, "CC:CompositionLocal.kt#9igjgp");
                    Object consume = $composer3.consume(localTextStyle);
                    ComposerKt.sourceInformationMarkerEnd($composer3);
                    textStyle2 = (TextStyle) consume;
                    $dirty3 &= -458753;
                } else {
                    modifier2 = modifier5;
                    enabled2 = enabled5;
                    readOnly2 = readOnly5;
                    textStyle2 = textStyle;
                }
                label2 = i10 != 0 ? null : label;
                placeholder2 = i11 != 0 ? null : placeholder;
                leadingIcon2 = i12 != 0 ? null : leadingIcon;
                trailingIcon2 = i13 != 0 ? null : trailingIcon;
                supportingText2 = i14 != 0 ? null : supportingText;
                isError2 = i15 != 0 ? false : isError;
                visualTransformation2 = i16 != 0 ? VisualTransformation.INSTANCE.getNone() : visualTransformation;
                keyboardOptions2 = i17 != 0 ? KeyboardOptions.INSTANCE.getDefault() : keyboardOptions;
                keyboardActions2 = i2 != 0 ? KeyboardActions.INSTANCE.getDefault() : keyboardActions;
                boolean singleLine3 = i19 != 0 ? false : singleLine;
                if ((i & 65536) != 0) {
                    maxLines2 = singleLine3 ? 1 : Integer.MAX_VALUE;
                    $dirty12 &= -3670017;
                } else {
                    maxLines2 = maxLines;
                }
                int minLines3 = i20 != 0 ? 1 : minLines;
                if (i21 != 0) {
                    $dirty = $dirty3;
                    $composer3.startReplaceableGroup(-1263318290);
                    ComposerKt.sourceInformation($composer3, "CC(remember):TextField.kt#9igjgp");
                    Object it$iv = $composer3.rememberedValue();
                    textStyle3 = textStyle2;
                    if (it$iv == Composer.INSTANCE.getEmpty()) {
                        value$iv = InteractionSourceKt.MutableInteractionSource();
                        $composer3.updateRememberedValue(value$iv);
                    } else {
                        value$iv = it$iv;
                    }
                    interactionSource2 = (MutableInteractionSource) value$iv;
                    $composer3.endReplaceableGroup();
                } else {
                    $dirty = $dirty3;
                    textStyle3 = textStyle2;
                    interactionSource2 = interactionSource;
                }
                MutableInteractionSource interactionSource4 = interactionSource2;
                if ((i & 524288) != 0) {
                    shape2 = TextFieldDefaults.INSTANCE.getShape($composer3, 6);
                    $dirty12 &= -1879048193;
                } else {
                    shape2 = shape;
                }
                if ((i & 1048576) != 0) {
                    int $dirty13 = $dirty12;
                    int i22 = $dirty23 & (-15);
                    readOnly3 = readOnly2;
                    $dirty2 = $dirty;
                    interactionSource3 = interactionSource4;
                    $dirty1 = $dirty13;
                    colors2 = TextFieldDefaults.INSTANCE.colors($composer3, 6);
                    $dirty22 = i22;
                    shape3 = shape2;
                    singleLine2 = singleLine3;
                    maxLines3 = maxLines2;
                    minLines2 = minLines3;
                    modifier3 = modifier2;
                    enabled3 = enabled2;
                    textStyle4 = textStyle3;
                } else {
                    int $dirty14 = $dirty12;
                    modifier3 = modifier2;
                    enabled3 = enabled2;
                    $dirty2 = $dirty;
                    interactionSource3 = interactionSource4;
                    $dirty1 = $dirty14;
                    colors2 = colors;
                    $dirty22 = $dirty23;
                    shape3 = shape2;
                    singleLine2 = singleLine3;
                    maxLines3 = maxLines2;
                    minLines2 = minLines3;
                    readOnly3 = readOnly2;
                    textStyle4 = textStyle3;
                }
            } else {
                $composer3.skipToGroupEnd();
                if ((i & 32) != 0) {
                    $dirty3 &= -458753;
                }
                if ((i & 65536) != 0) {
                    $dirty12 &= -3670017;
                }
                if ((i & 524288) != 0) {
                    $dirty12 &= -1879048193;
                }
                if ((i & 1048576) != 0) {
                    $dirty23 &= -15;
                }
                textStyle4 = textStyle;
                label2 = label;
                placeholder2 = placeholder;
                leadingIcon2 = leadingIcon;
                trailingIcon2 = trailingIcon;
                supportingText2 = supportingText;
                isError2 = isError;
                visualTransformation2 = visualTransformation;
                keyboardOptions2 = keyboardOptions;
                keyboardActions2 = keyboardActions;
                singleLine2 = singleLine;
                maxLines3 = maxLines;
                minLines2 = minLines;
                interactionSource3 = interactionSource;
                shape3 = shape;
                colors2 = colors;
                $dirty2 = $dirty3;
                $dirty1 = $dirty12;
                $dirty22 = $dirty23;
                modifier3 = modifier;
                enabled3 = enabled;
                readOnly3 = readOnly;
            }
            $composer3.endDefaults();
            if (ComposerKt.isTraceInProgress()) {
                $composer2 = $composer3;
                keyboardActions3 = keyboardActions2;
                ComposerKt.traceEventStart(1523846136, $dirty2, $dirty1, "androidx.compose.material3.TextField (TextField.kt:469)");
            } else {
                $composer2 = $composer3;
                keyboardActions3 = keyboardActions2;
            }
            TextField(value, (Function1<? super TextFieldValue, Unit>) onValueChange, modifier3, enabled3, readOnly3, textStyle4, (Function2<? super Composer, ? super Integer, Unit>) label2, (Function2<? super Composer, ? super Integer, Unit>) placeholder2, (Function2<? super Composer, ? super Integer, Unit>) leadingIcon2, (Function2<? super Composer, ? super Integer, Unit>) trailingIcon2, (Function2<? super Composer, ? super Integer, Unit>) null, (Function2<? super Composer, ? super Integer, Unit>) null, (Function2<? super Composer, ? super Integer, Unit>) supportingText2, isError2, visualTransformation2, keyboardOptions2, keyboardActions3, singleLine2, maxLines3, minLines2, interactionSource3, shape3, colors2, $composer2, ($dirty2 & 14) | ($dirty2 & 112) | ($dirty2 & 896) | ($dirty2 & 7168) | (57344 & $dirty2) | (458752 & $dirty2) | (3670016 & $dirty2) | (29360128 & $dirty2) | (234881024 & $dirty2) | (1879048192 & $dirty2), (($dirty1 << 6) & 896) | 54 | (($dirty1 << 6) & 7168) | (($dirty1 << 6) & 57344) | (($dirty1 << 6) & 458752) | (($dirty1 << 6) & 3670016) | (($dirty1 << 6) & 29360128) | (($dirty1 << 6) & 234881024) | (($dirty1 << 6) & 1879048192), (($dirty1 >> 24) & 14) | (($dirty1 >> 24) & 112) | (($dirty22 << 6) & 896), 0);
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventEnd();
            }
            keyboardActions4 = keyboardActions3;
            modifier4 = modifier3;
            enabled4 = enabled3;
            readOnly4 = readOnly3;
            textStyle5 = textStyle4;
            leadingIcon3 = leadingIcon2;
            placeholder3 = placeholder2;
            trailingIcon3 = trailingIcon2;
            supportingText3 = supportingText2;
            isError3 = isError2;
            visualTransformation3 = visualTransformation2;
            keyboardOptions3 = keyboardOptions2;
            label3 = label2;
        }
        ScopeUpdateScope endRestartGroup = $composer2.endRestartGroup();
        if (endRestartGroup != null) {
            final Modifier modifier6 = modifier4;
            final boolean z = enabled4;
            final boolean z2 = readOnly4;
            final TextStyle textStyle6 = textStyle5;
            final Function2 function2 = label3;
            final Function2 function22 = placeholder3;
            final Function2 function23 = leadingIcon3;
            final Function2 function24 = trailingIcon3;
            final Function2 function25 = supportingText3;
            final boolean z3 = isError3;
            final VisualTransformation visualTransformation4 = visualTransformation3;
            final KeyboardOptions keyboardOptions4 = keyboardOptions3;
            final KeyboardActions keyboardActions5 = keyboardActions4;
            final boolean z4 = singleLine2;
            final int i23 = maxLines3;
            final int i24 = minLines2;
            final MutableInteractionSource mutableInteractionSource = interactionSource3;
            final Shape shape4 = shape3;
            final TextFieldColors textFieldColors = colors2;
            endRestartGroup.updateScope(new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.TextFieldKt$TextField$10
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

                public final void invoke(Composer composer, int i25) {
                    TextFieldKt.TextField(TextFieldValue.this, onValueChange, modifier6, z, z2, textStyle6, function2, function22, function23, function24, function25, z3, visualTransformation4, keyboardOptions4, keyboardActions5, z4, i23, i24, mutableInteractionSource, shape4, textFieldColors, composer, RecomposeScopeImplKt.updateChangedFlags($changed | 1), RecomposeScopeImplKt.updateChangedFlags($changed1), RecomposeScopeImplKt.updateChangedFlags($changed2), i);
                }
            });
        }
    }

    /* JADX WARN: Removed duplicated region for block: B:123:0x01fe  */
    /* JADX WARN: Removed duplicated region for block: B:126:0x020a  */
    /* JADX WARN: Removed duplicated region for block: B:134:0x02ba  */
    /* JADX WARN: Removed duplicated region for block: B:148:0x042c  */
    /* JADX WARN: Removed duplicated region for block: B:165:0x0588  */
    /* JADX WARN: Removed duplicated region for block: B:167:0x05ac  */
    /* JADX WARN: Removed duplicated region for block: B:170:0x05dd  */
    /* JADX WARN: Removed duplicated region for block: B:184:0x075d  */
    /* JADX WARN: Removed duplicated region for block: B:201:0x08d2  */
    /* JADX WARN: Removed duplicated region for block: B:218:0x0a5a  */
    /* JADX WARN: Removed duplicated region for block: B:220:0x0a69  */
    /* JADX WARN: Removed duplicated region for block: B:223:0x0a91  */
    /* JADX WARN: Removed duplicated region for block: B:226:0x0b1f  */
    /* JADX WARN: Removed duplicated region for block: B:229:0x0b2b  */
    /* JADX WARN: Removed duplicated region for block: B:232:0x0b62  */
    /* JADX WARN: Removed duplicated region for block: B:237:0x0c0c  */
    /* JADX WARN: Removed duplicated region for block: B:251:0x0d91  */
    /* JADX WARN: Removed duplicated region for block: B:255:0x0d76  */
    /* JADX WARN: Removed duplicated region for block: B:257:0x0b78 A[ADDED_TO_REGION] */
    /* JADX WARN: Removed duplicated region for block: B:258:0x0b31  */
    /* JADX WARN: Removed duplicated region for block: B:259:0x0a6c  */
    /* JADX WARN: Removed duplicated region for block: B:260:0x0a5d  */
    /* JADX WARN: Removed duplicated region for block: B:264:0x0745  */
    /* JADX WARN: Removed duplicated region for block: B:265:0x05cb  */
    /* JADX WARN: Removed duplicated region for block: B:266:0x05a7  */
    /* JADX WARN: Removed duplicated region for block: B:270:0x0414  */
    /* JADX WARN: Removed duplicated region for block: B:273:0x0210  */
    /*
        Code decompiled incorrectly, please refer to instructions dump.
        To view partially-correct add '--show-bad-code' argument
    */
    public static final void TextFieldLayout(final androidx.compose.ui.Modifier r61, final kotlin.jvm.functions.Function2<? super androidx.compose.runtime.Composer, ? super java.lang.Integer, kotlin.Unit> r62, final kotlin.jvm.functions.Function2<? super androidx.compose.runtime.Composer, ? super java.lang.Integer, kotlin.Unit> r63, final kotlin.jvm.functions.Function3<? super androidx.compose.ui.Modifier, ? super androidx.compose.runtime.Composer, ? super java.lang.Integer, kotlin.Unit> r64, final kotlin.jvm.functions.Function2<? super androidx.compose.runtime.Composer, ? super java.lang.Integer, kotlin.Unit> r65, final kotlin.jvm.functions.Function2<? super androidx.compose.runtime.Composer, ? super java.lang.Integer, kotlin.Unit> r66, final kotlin.jvm.functions.Function2<? super androidx.compose.runtime.Composer, ? super java.lang.Integer, kotlin.Unit> r67, final kotlin.jvm.functions.Function2<? super androidx.compose.runtime.Composer, ? super java.lang.Integer, kotlin.Unit> r68, final boolean r69, final float r70, final kotlin.jvm.functions.Function2<? super androidx.compose.runtime.Composer, ? super java.lang.Integer, kotlin.Unit> r71, final kotlin.jvm.functions.Function2<? super androidx.compose.runtime.Composer, ? super java.lang.Integer, kotlin.Unit> r72, final androidx.compose.foundation.layout.PaddingValues r73, androidx.compose.runtime.Composer r74, final int r75, final int r76) {
        /*
            Method dump skipped, instructions count: 3545
            To view this dump add '--comments-level debug' option
        */
        throw new UnsupportedOperationException("Method not decompiled: androidx.compose.material3.TextFieldKt.TextFieldLayout(androidx.compose.ui.Modifier, kotlin.jvm.functions.Function2, kotlin.jvm.functions.Function2, kotlin.jvm.functions.Function3, kotlin.jvm.functions.Function2, kotlin.jvm.functions.Function2, kotlin.jvm.functions.Function2, kotlin.jvm.functions.Function2, boolean, float, kotlin.jvm.functions.Function2, kotlin.jvm.functions.Function2, androidx.compose.foundation.layout.PaddingValues, androidx.compose.runtime.Composer, int, int):void");
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final int substractConstraintSafely(int $this$substractConstraintSafely, int from) {
        if ($this$substractConstraintSafely == Integer.MAX_VALUE) {
            return $this$substractConstraintSafely;
        }
        return $this$substractConstraintSafely - from;
    }

    /* JADX INFO: Access modifiers changed from: private */
    /* renamed from: calculateWidth-yeHjK3Y, reason: not valid java name */
    public static final int m2461calculateWidthyeHjK3Y(int leadingWidth, int trailingWidth, int prefixWidth, int suffixWidth, int textFieldWidth, int labelWidth, int placeholderWidth, long constraints) {
        int affixTotalWidth = prefixWidth + suffixWidth;
        int middleSection = Math.max(textFieldWidth + affixTotalWidth, Math.max(placeholderWidth + affixTotalWidth, labelWidth));
        int wrappedWidth = leadingWidth + middleSection + trailingWidth;
        return Math.max(wrappedWidth, Constraints.m6052getMinWidthimpl(constraints));
    }

    /* JADX INFO: Access modifiers changed from: private */
    /* renamed from: calculateHeight-mKXJcVc, reason: not valid java name */
    public static final int m2460calculateHeightmKXJcVc(int textFieldHeight, int labelHeight, int leadingHeight, int trailingHeight, int prefixHeight, int suffixHeight, int placeholderHeight, int supportingHeight, float animationProgress, long constraints, float density, PaddingValues paddingValues) {
        float actualVerticalPadding;
        boolean hasLabel = labelHeight > 0;
        float arg0$iv = paddingValues.getTop();
        float other$iv = paddingValues.getBottom();
        float verticalPadding = Dp.m6094constructorimpl(arg0$iv + other$iv) * density;
        if (hasLabel) {
            float arg0$iv2 = TextFieldImplKt.getTextFieldPadding();
            actualVerticalPadding = MathHelpersKt.lerp(Dp.m6094constructorimpl(2 * arg0$iv2) * density, verticalPadding, animationProgress);
        } else {
            actualVerticalPadding = verticalPadding;
        }
        int inputFieldHeight = ComparisonsKt.maxOf(textFieldHeight, placeholderHeight, prefixHeight, suffixHeight, MathHelpersKt.lerp(labelHeight, 0, animationProgress));
        float middleSectionHeight = MathHelpersKt.lerp(0, labelHeight, animationProgress) + actualVerticalPadding + inputFieldHeight;
        return Math.max(Constraints.m6051getMinHeightimpl(constraints), Math.max(leadingHeight, Math.max(trailingHeight, MathKt.roundToInt(middleSectionHeight))) + supportingHeight);
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final void placeWithLabel(Placeable.PlacementScope $this$placeWithLabel, int width, int totalHeight, Placeable textfieldPlaceable, Placeable labelPlaceable, Placeable placeholderPlaceable, Placeable leadingPlaceable, Placeable trailingPlaceable, Placeable prefixPlaceable, Placeable suffixPlaceable, Placeable containerPlaceable, Placeable supportingPlaceable, boolean singleLine, int labelEndPosition, int textPosition, float animationProgress, float density) {
        int roundToInt;
        Placeable.PlacementScope.m5067place70tqf50$default($this$placeWithLabel, containerPlaceable, IntOffset.INSTANCE.m6232getZeronOccac(), 0.0f, 2, null);
        int height = totalHeight - TextFieldImplKt.heightOrZero(supportingPlaceable);
        if (leadingPlaceable != null) {
            Placeable.PlacementScope.placeRelative$default($this$placeWithLabel, leadingPlaceable, 0, Alignment.INSTANCE.getCenterVertically().align(leadingPlaceable.getHeight(), height), 0.0f, 4, null);
        }
        if (trailingPlaceable != null) {
            Placeable.PlacementScope.placeRelative$default($this$placeWithLabel, trailingPlaceable, width - trailingPlaceable.getWidth(), Alignment.INSTANCE.getCenterVertically().align(trailingPlaceable.getHeight(), height), 0.0f, 4, null);
        }
        if (labelPlaceable != null) {
            if (singleLine) {
                roundToInt = Alignment.INSTANCE.getCenterVertically().align(labelPlaceable.getHeight(), height);
            } else {
                roundToInt = MathKt.roundToInt(TextFieldImplKt.getTextFieldPadding() * density);
            }
            int startPosition = roundToInt;
            int distance = startPosition - labelEndPosition;
            int positionY = startPosition - MathKt.roundToInt(distance * animationProgress);
            Placeable.PlacementScope.placeRelative$default($this$placeWithLabel, labelPlaceable, TextFieldImplKt.widthOrZero(leadingPlaceable), positionY, 0.0f, 4, null);
        }
        if (prefixPlaceable != null) {
            Placeable.PlacementScope.placeRelative$default($this$placeWithLabel, prefixPlaceable, TextFieldImplKt.widthOrZero(leadingPlaceable), textPosition, 0.0f, 4, null);
        }
        if (suffixPlaceable != null) {
            Placeable.PlacementScope.placeRelative$default($this$placeWithLabel, suffixPlaceable, (width - TextFieldImplKt.widthOrZero(trailingPlaceable)) - suffixPlaceable.getWidth(), textPosition, 0.0f, 4, null);
        }
        int textHorizontalPosition = TextFieldImplKt.widthOrZero(leadingPlaceable) + TextFieldImplKt.widthOrZero(prefixPlaceable);
        Placeable.PlacementScope.placeRelative$default($this$placeWithLabel, textfieldPlaceable, textHorizontalPosition, textPosition, 0.0f, 4, null);
        if (placeholderPlaceable != null) {
            Placeable.PlacementScope.placeRelative$default($this$placeWithLabel, placeholderPlaceable, textHorizontalPosition, textPosition, 0.0f, 4, null);
        }
        if (supportingPlaceable != null) {
            Placeable.PlacementScope.placeRelative$default($this$placeWithLabel, supportingPlaceable, 0, height, 0.0f, 4, null);
        }
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final void placeWithoutLabel(Placeable.PlacementScope $this$placeWithoutLabel, int width, int totalHeight, Placeable textPlaceable, Placeable placeholderPlaceable, Placeable leadingPlaceable, Placeable trailingPlaceable, Placeable prefixPlaceable, Placeable suffixPlaceable, Placeable containerPlaceable, Placeable supportingPlaceable, boolean singleLine, float density, PaddingValues paddingValues) {
        Placeable.PlacementScope.m5067place70tqf50$default($this$placeWithoutLabel, containerPlaceable, IntOffset.INSTANCE.m6232getZeronOccac(), 0.0f, 2, null);
        int height = totalHeight - TextFieldImplKt.heightOrZero(supportingPlaceable);
        int topPadding = MathKt.roundToInt(paddingValues.getTop() * density);
        if (leadingPlaceable != null) {
            Placeable.PlacementScope.placeRelative$default($this$placeWithoutLabel, leadingPlaceable, 0, Alignment.INSTANCE.getCenterVertically().align(leadingPlaceable.getHeight(), height), 0.0f, 4, null);
        }
        if (trailingPlaceable != null) {
            Placeable.PlacementScope.placeRelative$default($this$placeWithoutLabel, trailingPlaceable, width - trailingPlaceable.getWidth(), Alignment.INSTANCE.getCenterVertically().align(trailingPlaceable.getHeight(), height), 0.0f, 4, null);
        }
        if (prefixPlaceable != null) {
            Placeable.PlacementScope.placeRelative$default($this$placeWithoutLabel, prefixPlaceable, TextFieldImplKt.widthOrZero(leadingPlaceable), placeWithoutLabel$calculateVerticalPosition(singleLine, height, topPadding, prefixPlaceable), 0.0f, 4, null);
        }
        if (suffixPlaceable != null) {
            Placeable.PlacementScope.placeRelative$default($this$placeWithoutLabel, suffixPlaceable, (width - TextFieldImplKt.widthOrZero(trailingPlaceable)) - suffixPlaceable.getWidth(), placeWithoutLabel$calculateVerticalPosition(singleLine, height, topPadding, suffixPlaceable), 0.0f, 4, null);
        }
        int textHorizontalPosition = TextFieldImplKt.widthOrZero(leadingPlaceable) + TextFieldImplKt.widthOrZero(prefixPlaceable);
        Placeable.PlacementScope.placeRelative$default($this$placeWithoutLabel, textPlaceable, textHorizontalPosition, placeWithoutLabel$calculateVerticalPosition(singleLine, height, topPadding, textPlaceable), 0.0f, 4, null);
        if (placeholderPlaceable != null) {
            Placeable.PlacementScope.placeRelative$default($this$placeWithoutLabel, placeholderPlaceable, textHorizontalPosition, placeWithoutLabel$calculateVerticalPosition(singleLine, height, topPadding, placeholderPlaceable), 0.0f, 4, null);
        }
        if (supportingPlaceable != null) {
            Placeable.PlacementScope.placeRelative$default($this$placeWithoutLabel, supportingPlaceable, 0, height, 0.0f, 4, null);
        }
    }

    private static final int placeWithoutLabel$calculateVerticalPosition(boolean $singleLine, int height, int topPadding, Placeable placeable) {
        if ($singleLine) {
            return Alignment.INSTANCE.getCenterVertically().align(placeable.getHeight(), height);
        }
        return topPadding;
    }

    public static final Modifier drawIndicatorLine(Modifier $this$drawIndicatorLine, final BorderStroke indicatorBorder) {
        final float strokeWidthDp = indicatorBorder.getWidth();
        return DrawModifierKt.drawWithContent($this$drawIndicatorLine, new Function1<ContentDrawScope, Unit>() { // from class: androidx.compose.material3.TextFieldKt$drawIndicatorLine$1
            /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
            {
                super(1);
            }

            @Override // kotlin.jvm.functions.Function1
            public /* bridge */ /* synthetic */ Unit invoke(ContentDrawScope contentDrawScope) {
                invoke2(contentDrawScope);
                return Unit.INSTANCE;
            }

            /* renamed from: invoke, reason: avoid collision after fix types in other method */
            public final void invoke2(ContentDrawScope $this$drawWithContent) {
                $this$drawWithContent.drawContent();
                if (Dp.m6099equalsimpl0(strokeWidthDp, Dp.INSTANCE.m6112getHairlineD9Ej5fM())) {
                    return;
                }
                float strokeWidth = strokeWidthDp * $this$drawWithContent.getDensity();
                float y = Size.m3571getHeightimpl($this$drawWithContent.mo4295getSizeNHjbRc()) - (strokeWidth / 2);
                DrawScope.m4281drawLine1RTmtNc$default($this$drawWithContent, indicatorBorder.getBrush(), OffsetKt.Offset(0.0f, y), OffsetKt.Offset(Size.m3574getWidthimpl($this$drawWithContent.mo4295getSizeNHjbRc()), y), strokeWidth, 0, null, 0.0f, null, 0, 496, null);
            }
        });
    }

    public static final float getTextFieldWithLabelVerticalPadding() {
        return TextFieldWithLabelVerticalPadding;
    }
}
