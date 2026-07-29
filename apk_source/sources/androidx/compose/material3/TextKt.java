package androidx.compose.material3;

import androidx.compose.foundation.text.BasicTextKt;
import androidx.compose.foundation.text.InlineTextContent;
import androidx.compose.material3.tokens.TypographyTokensKt;
import androidx.compose.runtime.Composer;
import androidx.compose.runtime.ComposerKt;
import androidx.compose.runtime.CompositionLocalKt;
import androidx.compose.runtime.ProvidableCompositionLocal;
import androidx.compose.runtime.ProvidedValue;
import androidx.compose.runtime.RecomposeScopeImplKt;
import androidx.compose.runtime.ScopeUpdateScope;
import androidx.compose.runtime.SnapshotStateKt;
import androidx.compose.ui.Modifier;
import androidx.compose.ui.graphics.Color;
import androidx.compose.ui.graphics.ColorProducer;
import androidx.compose.ui.text.AnnotatedString;
import androidx.compose.ui.text.TextLayoutResult;
import androidx.compose.ui.text.TextStyle;
import androidx.compose.ui.text.font.FontFamily;
import androidx.compose.ui.text.font.FontStyle;
import androidx.compose.ui.text.font.FontWeight;
import androidx.compose.ui.text.style.Hyphens;
import androidx.compose.ui.text.style.LineBreak;
import androidx.compose.ui.text.style.TextAlign;
import androidx.compose.ui.text.style.TextDecoration;
import androidx.compose.ui.text.style.TextDirection;
import androidx.compose.ui.text.style.TextOverflow;
import androidx.compose.ui.unit.TextUnit;
import androidx.core.view.accessibility.AccessibilityEventCompat;
import androidx.profileinstaller.ProfileVerifier;
import java.util.Map;
import kotlin.Deprecated;
import kotlin.DeprecationLevel;
import kotlin.Metadata;
import kotlin.Unit;
import kotlin.collections.MapsKt;
import kotlin.jvm.functions.Function0;
import kotlin.jvm.functions.Function1;
import kotlin.jvm.functions.Function2;

/* compiled from: Text.kt */
@Metadata(d1 = {"\u0000\u008a\u0001\n\u0000\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0010\u0002\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010\u000b\n\u0000\n\u0002\u0010\b\n\u0002\b\u0002\n\u0002\u0010$\n\u0002\u0010\u000e\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\b\t\u001a(\u0010\u0005\u001a\u00020\u00062\u0006\u0010\u0007\u001a\u00020\u00022\u0011\u0010\b\u001a\r\u0012\u0004\u0012\u00020\u00060\t¢\u0006\u0002\b\nH\u0007¢\u0006\u0002\u0010\u000b\u001aæ\u0001\u0010\f\u001a\u00020\u00062\u0006\u0010\r\u001a\u00020\u000e2\b\b\u0002\u0010\u000f\u001a\u00020\u00102\b\b\u0002\u0010\u0011\u001a\u00020\u00122\b\b\u0002\u0010\u0013\u001a\u00020\u00142\n\b\u0002\u0010\u0015\u001a\u0004\u0018\u00010\u00162\n\b\u0002\u0010\u0017\u001a\u0004\u0018\u00010\u00182\n\b\u0002\u0010\u0019\u001a\u0004\u0018\u00010\u001a2\b\b\u0002\u0010\u001b\u001a\u00020\u00142\n\b\u0002\u0010\u001c\u001a\u0004\u0018\u00010\u001d2\n\b\u0002\u0010\u001e\u001a\u0004\u0018\u00010\u001f2\b\b\u0002\u0010 \u001a\u00020\u00142\b\b\u0002\u0010!\u001a\u00020\"2\b\b\u0002\u0010#\u001a\u00020$2\b\b\u0002\u0010%\u001a\u00020&2\b\b\u0002\u0010'\u001a\u00020&2\u0014\b\u0002\u0010(\u001a\u000e\u0012\u0004\u0012\u00020*\u0012\u0004\u0012\u00020+0)2\u0014\b\u0002\u0010,\u001a\u000e\u0012\u0004\u0012\u00020.\u0012\u0004\u0012\u00020\u00060-2\b\b\u0002\u0010/\u001a\u00020\u0002H\u0007ø\u0001\u0000¢\u0006\u0004\b0\u00101\u001aÜ\u0001\u0010\f\u001a\u00020\u00062\u0006\u0010\r\u001a\u00020\u000e2\b\b\u0002\u0010\u000f\u001a\u00020\u00102\b\b\u0002\u0010\u0011\u001a\u00020\u00122\b\b\u0002\u0010\u0013\u001a\u00020\u00142\n\b\u0002\u0010\u0015\u001a\u0004\u0018\u00010\u00162\n\b\u0002\u0010\u0017\u001a\u0004\u0018\u00010\u00182\n\b\u0002\u0010\u0019\u001a\u0004\u0018\u00010\u001a2\b\b\u0002\u0010\u001b\u001a\u00020\u00142\n\b\u0002\u0010\u001c\u001a\u0004\u0018\u00010\u001d2\n\b\u0002\u0010\u001e\u001a\u0004\u0018\u00010\u001f2\b\b\u0002\u0010 \u001a\u00020\u00142\b\b\u0002\u0010!\u001a\u00020\"2\b\b\u0002\u0010#\u001a\u00020$2\b\b\u0002\u0010%\u001a\u00020&2\u0014\b\u0002\u0010(\u001a\u000e\u0012\u0004\u0012\u00020*\u0012\u0004\u0012\u00020+0)2\u0014\b\u0002\u0010,\u001a\u000e\u0012\u0004\u0012\u00020.\u0012\u0004\u0012\u00020\u00060-2\b\b\u0002\u0010/\u001a\u00020\u0002H\u0007ø\u0001\u0000¢\u0006\u0004\b2\u00103\u001aÆ\u0001\u0010\f\u001a\u00020\u00062\u0006\u0010\r\u001a\u00020*2\b\b\u0002\u0010\u000f\u001a\u00020\u00102\b\b\u0002\u0010\u0011\u001a\u00020\u00122\b\b\u0002\u0010\u0013\u001a\u00020\u00142\n\b\u0002\u0010\u0015\u001a\u0004\u0018\u00010\u00162\n\b\u0002\u0010\u0017\u001a\u0004\u0018\u00010\u00182\n\b\u0002\u0010\u0019\u001a\u0004\u0018\u00010\u001a2\b\b\u0002\u0010\u001b\u001a\u00020\u00142\n\b\u0002\u0010\u001c\u001a\u0004\u0018\u00010\u001d2\n\b\u0002\u0010\u001e\u001a\u0004\u0018\u00010\u001f2\b\b\u0002\u0010 \u001a\u00020\u00142\b\b\u0002\u0010!\u001a\u00020\"2\b\b\u0002\u0010#\u001a\u00020$2\b\b\u0002\u0010%\u001a\u00020&2\u0014\b\u0002\u0010,\u001a\u000e\u0012\u0004\u0012\u00020.\u0012\u0004\u0012\u00020\u00060-2\b\b\u0002\u0010/\u001a\u00020\u0002H\u0007ø\u0001\u0000¢\u0006\u0004\b4\u00105\u001aÒ\u0001\u0010\f\u001a\u00020\u00062\u0006\u0010\r\u001a\u00020*2\b\b\u0002\u0010\u000f\u001a\u00020\u00102\b\b\u0002\u0010\u0011\u001a\u00020\u00122\b\b\u0002\u0010\u0013\u001a\u00020\u00142\n\b\u0002\u0010\u0015\u001a\u0004\u0018\u00010\u00162\n\b\u0002\u0010\u0017\u001a\u0004\u0018\u00010\u00182\n\b\u0002\u0010\u0019\u001a\u0004\u0018\u00010\u001a2\b\b\u0002\u0010\u001b\u001a\u00020\u00142\n\b\u0002\u0010\u001c\u001a\u0004\u0018\u00010\u001d2\n\b\u0002\u0010\u001e\u001a\u0004\u0018\u00010\u001f2\b\b\u0002\u0010 \u001a\u00020\u00142\b\b\u0002\u0010!\u001a\u00020\"2\b\b\u0002\u0010#\u001a\u00020$2\b\b\u0002\u0010%\u001a\u00020&2\b\b\u0002\u0010'\u001a\u00020&2\u0016\b\u0002\u0010,\u001a\u0010\u0012\u0004\u0012\u00020.\u0012\u0004\u0012\u00020\u0006\u0018\u00010-2\b\b\u0002\u0010/\u001a\u00020\u0002H\u0007ø\u0001\u0000¢\u0006\u0004\b2\u00106\"\u0017\u0010\u0000\u001a\b\u0012\u0004\u0012\u00020\u00020\u0001¢\u0006\b\n\u0000\u001a\u0004\b\u0003\u0010\u0004\u0082\u0002\u0007\n\u0005\b¡\u001e0\u0001¨\u00067"}, d2 = {"LocalTextStyle", "Landroidx/compose/runtime/ProvidableCompositionLocal;", "Landroidx/compose/ui/text/TextStyle;", "getLocalTextStyle", "()Landroidx/compose/runtime/ProvidableCompositionLocal;", "ProvideTextStyle", "", "value", "content", "Lkotlin/Function0;", "Landroidx/compose/runtime/Composable;", "(Landroidx/compose/ui/text/TextStyle;Lkotlin/jvm/functions/Function2;Landroidx/compose/runtime/Composer;I)V", "Text", "text", "Landroidx/compose/ui/text/AnnotatedString;", "modifier", "Landroidx/compose/ui/Modifier;", "color", "Landroidx/compose/ui/graphics/Color;", "fontSize", "Landroidx/compose/ui/unit/TextUnit;", "fontStyle", "Landroidx/compose/ui/text/font/FontStyle;", "fontWeight", "Landroidx/compose/ui/text/font/FontWeight;", "fontFamily", "Landroidx/compose/ui/text/font/FontFamily;", "letterSpacing", "textDecoration", "Landroidx/compose/ui/text/style/TextDecoration;", "textAlign", "Landroidx/compose/ui/text/style/TextAlign;", "lineHeight", "overflow", "Landroidx/compose/ui/text/style/TextOverflow;", "softWrap", "", "maxLines", "", "minLines", "inlineContent", "", "", "Landroidx/compose/foundation/text/InlineTextContent;", "onTextLayout", "Lkotlin/Function1;", "Landroidx/compose/ui/text/TextLayoutResult;", "style", "Text-IbK3jfQ", "(Landroidx/compose/ui/text/AnnotatedString;Landroidx/compose/ui/Modifier;JJLandroidx/compose/ui/text/font/FontStyle;Landroidx/compose/ui/text/font/FontWeight;Landroidx/compose/ui/text/font/FontFamily;JLandroidx/compose/ui/text/style/TextDecoration;Landroidx/compose/ui/text/style/TextAlign;JIZIILjava/util/Map;Lkotlin/jvm/functions/Function1;Landroidx/compose/ui/text/TextStyle;Landroidx/compose/runtime/Composer;III)V", "Text--4IGK_g", "(Landroidx/compose/ui/text/AnnotatedString;Landroidx/compose/ui/Modifier;JJLandroidx/compose/ui/text/font/FontStyle;Landroidx/compose/ui/text/font/FontWeight;Landroidx/compose/ui/text/font/FontFamily;JLandroidx/compose/ui/text/style/TextDecoration;Landroidx/compose/ui/text/style/TextAlign;JIZILjava/util/Map;Lkotlin/jvm/functions/Function1;Landroidx/compose/ui/text/TextStyle;Landroidx/compose/runtime/Composer;III)V", "Text-fLXpl1I", "(Ljava/lang/String;Landroidx/compose/ui/Modifier;JJLandroidx/compose/ui/text/font/FontStyle;Landroidx/compose/ui/text/font/FontWeight;Landroidx/compose/ui/text/font/FontFamily;JLandroidx/compose/ui/text/style/TextDecoration;Landroidx/compose/ui/text/style/TextAlign;JIZILkotlin/jvm/functions/Function1;Landroidx/compose/ui/text/TextStyle;Landroidx/compose/runtime/Composer;III)V", "(Ljava/lang/String;Landroidx/compose/ui/Modifier;JJLandroidx/compose/ui/text/font/FontStyle;Landroidx/compose/ui/text/font/FontWeight;Landroidx/compose/ui/text/font/FontFamily;JLandroidx/compose/ui/text/style/TextDecoration;Landroidx/compose/ui/text/style/TextAlign;JIZIILkotlin/jvm/functions/Function1;Landroidx/compose/ui/text/TextStyle;Landroidx/compose/runtime/Composer;III)V", "material3_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class TextKt {
    private static final ProvidableCompositionLocal<TextStyle> LocalTextStyle = CompositionLocalKt.compositionLocalOf(SnapshotStateKt.structuralEqualityPolicy(), new Function0<TextStyle>() { // from class: androidx.compose.material3.TextKt$LocalTextStyle$1
        /* JADX WARN: Can't rename method to resolve collision */
        @Override // kotlin.jvm.functions.Function0
        public final TextStyle invoke() {
            return TypographyTokensKt.getDefaultTextStyle();
        }
    });

    /* renamed from: Text--4IGK_g, reason: not valid java name */
    public static final void m2464Text4IGK_g(final String text, Modifier modifier, long color, long fontSize, FontStyle fontStyle, FontWeight fontWeight, FontFamily fontFamily, long letterSpacing, TextDecoration textDecoration, TextAlign textAlign, long lineHeight, int overflow, boolean softWrap, int maxLines, int minLines, Function1<? super TextLayoutResult, Unit> function1, TextStyle style, Composer $composer, final int $changed, final int $changed1, final int i) {
        int i2;
        long color2;
        long fontSize2;
        FontStyle fontStyle2;
        FontWeight fontWeight2;
        FontFamily fontFamily2;
        long letterSpacing2;
        TextAlign textAlign2;
        long lineHeight2;
        boolean softWrap2;
        int maxLines2;
        int minLines2;
        Function1 onTextLayout;
        int overflow2;
        TextStyle style2;
        Modifier modifier2;
        int $dirty1;
        TextDecoration textDecoration2;
        int minLines3;
        int maxLines3;
        long textColor;
        TextStyle m5616mergedA7vx0o;
        int minLines4;
        int maxLines4;
        TextDecoration textDecoration3;
        int overflow3;
        TextStyle style3;
        TextAlign textAlign3;
        boolean softWrap3;
        FontStyle fontStyle3;
        Function1 onTextLayout2;
        FontWeight fontWeight3;
        FontFamily fontFamily3;
        long letterSpacing3;
        long fontSize3;
        long lineHeight3;
        Modifier modifier3;
        long color3;
        int i3;
        Composer $composer2 = $composer.startRestartGroup(-2055108902);
        ComposerKt.sourceInformation($composer2, "C(Text)P(14,9,0:c#ui.graphics.Color,2:c#ui.unit.TextUnit,3:c#ui.text.font.FontStyle,4!1,5:c#ui.unit.TextUnit,16,15:c#ui.text.style.TextAlign,6:c#ui.unit.TextUnit,11:c#ui.text.style.TextOverflow,12)108@5588L7,117@5732L530:Text.kt#uh7d8r");
        int $dirty = $changed;
        int $dirty12 = $changed1;
        if ((i & 1) != 0) {
            $dirty |= 6;
        } else if (($changed & 6) == 0) {
            $dirty |= $composer2.changed(text) ? 4 : 2;
        }
        int i4 = i & 2;
        if (i4 != 0) {
            $dirty |= 48;
        } else if (($changed & 48) == 0) {
            $dirty |= $composer2.changed(modifier) ? 32 : 16;
        }
        int i5 = i & 4;
        if (i5 != 0) {
            $dirty |= 384;
        } else if (($changed & 384) == 0) {
            $dirty |= $composer2.changed(color) ? 256 : 128;
        }
        int i6 = i & 8;
        if (i6 != 0) {
            $dirty |= 3072;
        } else if (($changed & 3072) == 0) {
            $dirty |= $composer2.changed(fontSize) ? 2048 : 1024;
        }
        int i7 = i & 16;
        if (i7 != 0) {
            $dirty |= 24576;
        } else if (($changed & 24576) == 0) {
            $dirty |= $composer2.changed(fontStyle) ? 16384 : 8192;
        }
        int i8 = i & 32;
        if (i8 != 0) {
            $dirty |= ProfileVerifier.CompilationStatus.RESULT_CODE_ERROR_CANT_WRITE_PROFILE_VERIFICATION_RESULT_CACHE_FILE;
        } else if (($changed & ProfileVerifier.CompilationStatus.RESULT_CODE_ERROR_CANT_WRITE_PROFILE_VERIFICATION_RESULT_CACHE_FILE) == 0) {
            $dirty |= $composer2.changed(fontWeight) ? 131072 : 65536;
        }
        int i9 = i & 64;
        if (i9 != 0) {
            $dirty |= 1572864;
        } else if (($changed & 1572864) == 0) {
            $dirty |= $composer2.changed(fontFamily) ? 1048576 : 524288;
        }
        int i10 = i & 128;
        if (i10 != 0) {
            $dirty |= 12582912;
        } else if (($changed & 12582912) == 0) {
            $dirty |= $composer2.changed(letterSpacing) ? 8388608 : 4194304;
        }
        int i11 = i & 256;
        if (i11 != 0) {
            $dirty |= 100663296;
        } else if (($changed & 100663296) == 0) {
            $dirty |= $composer2.changed(textDecoration) ? AccessibilityEventCompat.TYPE_VIEW_TARGETED_BY_SCROLL : 33554432;
        }
        int i12 = i & 512;
        if (i12 != 0) {
            $dirty |= 805306368;
        } else if (($changed & 805306368) == 0) {
            $dirty |= $composer2.changed(textAlign) ? 536870912 : 268435456;
        }
        int i13 = i & 1024;
        if (i13 != 0) {
            $dirty12 |= 6;
        } else if (($changed1 & 6) == 0) {
            $dirty12 |= $composer2.changed(lineHeight) ? 4 : 2;
        }
        int i14 = i & 2048;
        if (i14 != 0) {
            $dirty12 |= 48;
        } else if (($changed1 & 48) == 0) {
            $dirty12 |= $composer2.changed(overflow) ? 32 : 16;
        }
        int i15 = i & 4096;
        if (i15 != 0) {
            $dirty12 |= 384;
        } else if (($changed1 & 384) == 0) {
            $dirty12 |= $composer2.changed(softWrap) ? 256 : 128;
        }
        int i16 = i & 8192;
        if (i16 != 0) {
            $dirty12 |= 3072;
        } else if (($changed1 & 3072) == 0) {
            $dirty12 |= $composer2.changed(maxLines) ? 2048 : 1024;
        }
        int i17 = i & 16384;
        if (i17 != 0) {
            $dirty12 |= 24576;
            i2 = i17;
        } else {
            i2 = i17;
            if (($changed1 & 24576) == 0) {
                $dirty12 |= $composer2.changed(minLines) ? 16384 : 8192;
            }
        }
        int i18 = i & 32768;
        if (i18 != 0) {
            $dirty12 |= ProfileVerifier.CompilationStatus.RESULT_CODE_ERROR_CANT_WRITE_PROFILE_VERIFICATION_RESULT_CACHE_FILE;
        } else if (($changed1 & ProfileVerifier.CompilationStatus.RESULT_CODE_ERROR_CANT_WRITE_PROFILE_VERIFICATION_RESULT_CACHE_FILE) == 0) {
            $dirty12 |= $composer2.changedInstance(function1) ? 131072 : 65536;
        }
        if (($changed1 & 1572864) == 0) {
            if ((i & 65536) == 0 && $composer2.changed(style)) {
                i3 = 1048576;
                $dirty12 |= i3;
            }
            i3 = 524288;
            $dirty12 |= i3;
        }
        if (($dirty & 306783379) == 306783378 && (599187 & $dirty12) == 599186 && $composer2.getSkipping()) {
            $composer2.skipToGroupEnd();
            modifier3 = modifier;
            color3 = color;
            fontSize3 = fontSize;
            fontStyle3 = fontStyle;
            fontWeight3 = fontWeight;
            fontFamily3 = fontFamily;
            letterSpacing3 = letterSpacing;
            textDecoration3 = textDecoration;
            textAlign3 = textAlign;
            lineHeight3 = lineHeight;
            overflow3 = overflow;
            softWrap3 = softWrap;
            maxLines4 = maxLines;
            minLines4 = minLines;
            onTextLayout2 = function1;
            style3 = style;
        } else {
            $composer2.startDefaults();
            if (($changed & 1) == 0 || $composer2.getDefaultsInvalid()) {
                Modifier.Companion modifier4 = i4 != 0 ? Modifier.INSTANCE : modifier;
                color2 = i5 != 0 ? Color.INSTANCE.m3782getUnspecified0d7_KjU() : color;
                fontSize2 = i6 != 0 ? TextUnit.INSTANCE.m6296getUnspecifiedXSAIIZE() : fontSize;
                fontStyle2 = i7 != 0 ? null : fontStyle;
                fontWeight2 = i8 != 0 ? null : fontWeight;
                fontFamily2 = i9 != 0 ? null : fontFamily;
                letterSpacing2 = i10 != 0 ? TextUnit.INSTANCE.m6296getUnspecifiedXSAIIZE() : letterSpacing;
                TextDecoration textDecoration4 = i11 != 0 ? null : textDecoration;
                textAlign2 = i12 != 0 ? null : textAlign;
                lineHeight2 = i13 != 0 ? TextUnit.INSTANCE.m6296getUnspecifiedXSAIIZE() : lineHeight;
                int overflow4 = i14 != 0 ? TextOverflow.INSTANCE.m6013getClipgIe3tQ8() : overflow;
                softWrap2 = i15 != 0 ? true : softWrap;
                maxLines2 = i16 != 0 ? Integer.MAX_VALUE : maxLines;
                minLines2 = i2 != 0 ? 1 : minLines;
                onTextLayout = i18 != 0 ? null : function1;
                if ((i & 65536) != 0) {
                    TextDecoration textDecoration5 = textDecoration4;
                    ProvidableCompositionLocal<TextStyle> providableCompositionLocal = LocalTextStyle;
                    Modifier modifier5 = modifier4;
                    ComposerKt.sourceInformationMarkerStart($composer2, 2023513938, "CC:CompositionLocal.kt#9igjgp");
                    Object consume = $composer2.consume(providableCompositionLocal);
                    ComposerKt.sourceInformationMarkerEnd($composer2);
                    TextStyle style4 = (TextStyle) consume;
                    overflow2 = overflow4;
                    style2 = style4;
                    $dirty1 = $dirty12 & (-3670017);
                    textDecoration2 = textDecoration5;
                    modifier2 = modifier5;
                } else {
                    TextDecoration textDecoration6 = textDecoration4;
                    Modifier modifier6 = modifier4;
                    overflow2 = overflow4;
                    style2 = style;
                    modifier2 = modifier6;
                    $dirty1 = $dirty12;
                    textDecoration2 = textDecoration6;
                }
            } else {
                $composer2.skipToGroupEnd();
                if ((i & 65536) != 0) {
                    int i19 = (-3670017) & $dirty12;
                    color2 = color;
                    fontSize2 = fontSize;
                    fontStyle2 = fontStyle;
                    fontWeight2 = fontWeight;
                    fontFamily2 = fontFamily;
                    letterSpacing2 = letterSpacing;
                    textDecoration2 = textDecoration;
                    textAlign2 = textAlign;
                    lineHeight2 = lineHeight;
                    overflow2 = overflow;
                    softWrap2 = softWrap;
                    maxLines2 = maxLines;
                    minLines2 = minLines;
                    onTextLayout = function1;
                    style2 = style;
                    $dirty1 = i19;
                    modifier2 = modifier;
                } else {
                    modifier2 = modifier;
                    color2 = color;
                    fontSize2 = fontSize;
                    fontStyle2 = fontStyle;
                    fontWeight2 = fontWeight;
                    fontFamily2 = fontFamily;
                    letterSpacing2 = letterSpacing;
                    textAlign2 = textAlign;
                    lineHeight2 = lineHeight;
                    overflow2 = overflow;
                    softWrap2 = softWrap;
                    maxLines2 = maxLines;
                    minLines2 = minLines;
                    onTextLayout = function1;
                    style2 = style;
                    $dirty1 = $dirty12;
                    textDecoration2 = textDecoration;
                }
            }
            $composer2.endDefaults();
            if (ComposerKt.isTraceInProgress()) {
                minLines3 = minLines2;
                ComposerKt.traceEventStart(-2055108902, $dirty, $dirty1, "androidx.compose.material3.Text (Text.kt:109)");
            } else {
                minLines3 = minLines2;
            }
            $composer2.startReplaceableGroup(79582827);
            ComposerKt.sourceInformation($composer2, "");
            long $this$takeOrElse_u2dDxMtmZc$iv = color2;
            if ($this$takeOrElse_u2dDxMtmZc$iv != Color.INSTANCE.m3782getUnspecified0d7_KjU()) {
                maxLines3 = maxLines2;
                textColor = $this$takeOrElse_u2dDxMtmZc$iv;
            } else {
                $composer2.startReplaceableGroup(79582860);
                ComposerKt.sourceInformation($composer2, "*113@5703L7");
                long $this$takeOrElse_u2dDxMtmZc$iv2 = style2.m5601getColor0d7_KjU();
                if ($this$takeOrElse_u2dDxMtmZc$iv2 != Color.INSTANCE.m3782getUnspecified0d7_KjU()) {
                    maxLines3 = maxLines2;
                } else {
                    ProvidableCompositionLocal<Color> localContentColor = ContentColorKt.getLocalContentColor();
                    maxLines3 = maxLines2;
                    ComposerKt.sourceInformationMarkerStart($composer2, 2023513938, "CC:CompositionLocal.kt#9igjgp");
                    Object consume2 = $composer2.consume(localContentColor);
                    ComposerKt.sourceInformationMarkerEnd($composer2);
                    $this$takeOrElse_u2dDxMtmZc$iv2 = ((Color) consume2).m3756unboximpl();
                }
                $composer2.endReplaceableGroup();
                textColor = $this$takeOrElse_u2dDxMtmZc$iv2;
            }
            $composer2.endReplaceableGroup();
            m5616mergedA7vx0o = style2.m5616mergedA7vx0o((r58 & 1) != 0 ? Color.INSTANCE.m3782getUnspecified0d7_KjU() : textColor, (r58 & 2) != 0 ? TextUnit.INSTANCE.m6296getUnspecifiedXSAIIZE() : fontSize2, (r58 & 4) != 0 ? null : fontWeight2, (r58 & 8) != 0 ? null : fontStyle2, (r58 & 16) != 0 ? null : null, (r58 & 32) != 0 ? null : fontFamily2, (r58 & 64) != 0 ? null : null, (r58 & 128) != 0 ? TextUnit.INSTANCE.m6296getUnspecifiedXSAIIZE() : letterSpacing2, (r58 & 256) != 0 ? null : null, (r58 & 512) != 0 ? null : null, (r58 & 1024) != 0 ? null : null, (r58 & 2048) != 0 ? Color.INSTANCE.m3782getUnspecified0d7_KjU() : 0L, (r58 & 4096) != 0 ? null : textDecoration2, (r58 & 8192) != 0 ? null : null, (r58 & 16384) != 0 ? null : null, (r58 & 32768) != 0 ? TextAlign.INSTANCE.m5970getUnspecifiede0LSkKk() : textAlign2 != null ? textAlign2.getValue() : TextAlign.INSTANCE.m5970getUnspecifiede0LSkKk(), (r58 & 65536) != 0 ? TextDirection.INSTANCE.m5983getUnspecifieds_7Xco() : 0, (r58 & 131072) != 0 ? TextUnit.INSTANCE.m6296getUnspecifiedXSAIIZE() : lineHeight2, (r58 & 262144) != 0 ? null : null, (r58 & 524288) != 0 ? null : null, (r58 & 1048576) != 0 ? LineBreak.INSTANCE.m5897getUnspecifiedrAG3T2k() : 0, (r58 & 2097152) != 0 ? Hyphens.INSTANCE.m5876getUnspecifiedvmbZdU8() : 0, (r58 & 4194304) != 0 ? null : null, (r58 & 8388608) != 0 ? null : null);
            BasicTextKt.m842BasicTextVhcvRP8(text, modifier2, m5616mergedA7vx0o, (Function1<? super TextLayoutResult, Unit>) onTextLayout, overflow2, softWrap2, maxLines3, minLines3, (ColorProducer) null, $composer2, ($dirty & 14) | ($dirty & 112) | (($dirty1 >> 6) & 7168) | (($dirty1 << 9) & 57344) | (($dirty1 << 9) & 458752) | (($dirty1 << 9) & 3670016) | (($dirty1 << 9) & 29360128), 256);
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventEnd();
            }
            minLines4 = minLines3;
            maxLines4 = maxLines3;
            textDecoration3 = textDecoration2;
            overflow3 = overflow2;
            style3 = style2;
            textAlign3 = textAlign2;
            softWrap3 = softWrap2;
            fontStyle3 = fontStyle2;
            onTextLayout2 = onTextLayout;
            fontWeight3 = fontWeight2;
            fontFamily3 = fontFamily2;
            letterSpacing3 = letterSpacing2;
            fontSize3 = fontSize2;
            lineHeight3 = lineHeight2;
            modifier3 = modifier2;
            color3 = color2;
        }
        ScopeUpdateScope endRestartGroup = $composer2.endRestartGroup();
        if (endRestartGroup != null) {
            final Modifier modifier7 = modifier3;
            final long j = color3;
            final long j2 = fontSize3;
            final FontStyle fontStyle4 = fontStyle3;
            final FontWeight fontWeight4 = fontWeight3;
            final FontFamily fontFamily4 = fontFamily3;
            final long j3 = letterSpacing3;
            final TextDecoration textDecoration7 = textDecoration3;
            final TextAlign textAlign4 = textAlign3;
            final long j4 = lineHeight3;
            final int i20 = overflow3;
            final boolean z = softWrap3;
            final int i21 = maxLines4;
            final int i22 = minLines4;
            final Function1 function12 = onTextLayout2;
            final TextStyle textStyle = style3;
            endRestartGroup.updateScope(new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.TextKt$Text$1
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

                public final void invoke(Composer composer, int i23) {
                    TextKt.m2464Text4IGK_g(text, modifier7, j, j2, fontStyle4, fontWeight4, fontFamily4, j3, textDecoration7, textAlign4, j4, i20, z, i21, i22, function12, textStyle, composer, RecomposeScopeImplKt.updateChangedFlags($changed | 1), RecomposeScopeImplKt.updateChangedFlags($changed1), i);
                }
            });
        }
    }

    /* JADX WARN: Code restructure failed: missing block: B:51:0x020c, code lost:
    
        if (r12.changed(r68) != false) goto L176;
     */
    @kotlin.Deprecated(level = kotlin.DeprecationLevel.HIDDEN, message = "Maintained for binary compatibility. Use version with minLines instead")
    /* renamed from: Text-fLXpl1I, reason: not valid java name */
    /*
        Code decompiled incorrectly, please refer to instructions dump.
        To view partially-correct add '--show-bad-code' argument
    */
    public static final /* synthetic */ void m2466TextfLXpl1I(final java.lang.String r49, androidx.compose.ui.Modifier r50, long r51, long r53, androidx.compose.ui.text.font.FontStyle r55, androidx.compose.ui.text.font.FontWeight r56, androidx.compose.ui.text.font.FontFamily r57, long r58, androidx.compose.ui.text.style.TextDecoration r60, androidx.compose.ui.text.style.TextAlign r61, long r62, int r64, boolean r65, int r66, kotlin.jvm.functions.Function1 r67, androidx.compose.ui.text.TextStyle r68, androidx.compose.runtime.Composer r69, final int r70, final int r71, final int r72) {
        /*
            Method dump skipped, instructions count: 1145
            To view this dump add '--comments-level debug' option
        */
        throw new UnsupportedOperationException("Method not decompiled: androidx.compose.material3.TextKt.m2466TextfLXpl1I(java.lang.String, androidx.compose.ui.Modifier, long, long, androidx.compose.ui.text.font.FontStyle, androidx.compose.ui.text.font.FontWeight, androidx.compose.ui.text.font.FontFamily, long, androidx.compose.ui.text.style.TextDecoration, androidx.compose.ui.text.style.TextAlign, long, int, boolean, int, kotlin.jvm.functions.Function1, androidx.compose.ui.text.TextStyle, androidx.compose.runtime.Composer, int, int, int):void");
    }

    /* renamed from: Text-IbK3jfQ, reason: not valid java name */
    public static final void m2465TextIbK3jfQ(final AnnotatedString text, Modifier modifier, long color, long fontSize, FontStyle fontStyle, FontWeight fontWeight, FontFamily fontFamily, long letterSpacing, TextDecoration textDecoration, TextAlign textAlign, long lineHeight, int overflow, boolean softWrap, int maxLines, int minLines, Map<String, InlineTextContent> map, Function1<? super TextLayoutResult, Unit> function1, TextStyle style, Composer $composer, final int $changed, final int $changed1, final int i) {
        int i2;
        long color2;
        FontStyle fontStyle2;
        FontWeight fontWeight2;
        FontFamily fontFamily2;
        long letterSpacing2;
        TextDecoration textDecoration2;
        TextAlign textAlign2;
        TextStyle style2;
        Modifier modifier2;
        int $dirty1;
        int minLines2;
        Map inlineContent;
        Function1 onTextLayout;
        long fontSize2;
        int minLines3;
        boolean softWrap2;
        int maxLines2;
        long lineHeight2;
        boolean softWrap3;
        int overflow2;
        long textColor;
        TextStyle m5616mergedA7vx0o;
        boolean softWrap4;
        int overflow3;
        Modifier modifier3;
        long fontSize3;
        TextDecoration textDecoration3;
        TextAlign textAlign3;
        long lineHeight3;
        FontStyle fontStyle3;
        FontWeight fontWeight3;
        FontFamily fontFamily3;
        int maxLines3;
        int minLines4;
        Map inlineContent2;
        Function1 onTextLayout2;
        long letterSpacing3;
        long color3;
        int i3;
        Composer $composer2 = $composer.startRestartGroup(2027001676);
        ComposerKt.sourceInformation($composer2, "C(Text)P(15,10,0:c#ui.graphics.Color,2:c#ui.unit.TextUnit,3:c#ui.text.font.FontStyle,4!1,6:c#ui.unit.TextUnit,17,16:c#ui.text.style.TextAlign,7:c#ui.unit.TextUnit,12:c#ui.text.style.TextOverflow,13,8,9)254@11532L7,262@11675L654:Text.kt#uh7d8r");
        int $dirty = $changed;
        int $dirty12 = $changed1;
        if ((i & 1) != 0) {
            $dirty |= 6;
        } else if (($changed & 6) == 0) {
            $dirty |= $composer2.changed(text) ? 4 : 2;
        }
        int i4 = i & 2;
        if (i4 != 0) {
            $dirty |= 48;
        } else if (($changed & 48) == 0) {
            $dirty |= $composer2.changed(modifier) ? 32 : 16;
        }
        int i5 = i & 4;
        if (i5 != 0) {
            $dirty |= 384;
        } else if (($changed & 384) == 0) {
            $dirty |= $composer2.changed(color) ? 256 : 128;
        }
        int i6 = i & 8;
        if (i6 != 0) {
            $dirty |= 3072;
        } else if (($changed & 3072) == 0) {
            $dirty |= $composer2.changed(fontSize) ? 2048 : 1024;
        }
        int i7 = i & 16;
        if (i7 != 0) {
            $dirty |= 24576;
        } else if (($changed & 24576) == 0) {
            $dirty |= $composer2.changed(fontStyle) ? 16384 : 8192;
        }
        int i8 = i & 32;
        if (i8 != 0) {
            $dirty |= ProfileVerifier.CompilationStatus.RESULT_CODE_ERROR_CANT_WRITE_PROFILE_VERIFICATION_RESULT_CACHE_FILE;
        } else if (($changed & ProfileVerifier.CompilationStatus.RESULT_CODE_ERROR_CANT_WRITE_PROFILE_VERIFICATION_RESULT_CACHE_FILE) == 0) {
            $dirty |= $composer2.changed(fontWeight) ? 131072 : 65536;
        }
        int i9 = i & 64;
        if (i9 != 0) {
            $dirty |= 1572864;
        } else if (($changed & 1572864) == 0) {
            $dirty |= $composer2.changed(fontFamily) ? 1048576 : 524288;
        }
        int i10 = i & 128;
        if (i10 != 0) {
            $dirty |= 12582912;
        } else if (($changed & 12582912) == 0) {
            $dirty |= $composer2.changed(letterSpacing) ? 8388608 : 4194304;
        }
        int i11 = i & 256;
        if (i11 != 0) {
            $dirty |= 100663296;
        } else if ((100663296 & $changed) == 0) {
            $dirty |= $composer2.changed(textDecoration) ? AccessibilityEventCompat.TYPE_VIEW_TARGETED_BY_SCROLL : 33554432;
        }
        int i12 = i & 512;
        if (i12 != 0) {
            $dirty |= 805306368;
        } else if (($changed & 805306368) == 0) {
            $dirty |= $composer2.changed(textAlign) ? 536870912 : 268435456;
        }
        int $dirty2 = $dirty;
        int $dirty3 = i & 1024;
        if ($dirty3 != 0) {
            $dirty12 |= 6;
        } else if (($changed1 & 6) == 0) {
            $dirty12 |= $composer2.changed(lineHeight) ? 4 : 2;
        }
        int i13 = i & 2048;
        if (i13 != 0) {
            $dirty12 |= 48;
        } else if (($changed1 & 48) == 0) {
            $dirty12 |= $composer2.changed(overflow) ? 32 : 16;
        }
        int i14 = i & 4096;
        if (i14 != 0) {
            $dirty12 |= 384;
        } else if (($changed1 & 384) == 0) {
            $dirty12 |= $composer2.changed(softWrap) ? 256 : 128;
        }
        int i15 = i & 8192;
        if (i15 != 0) {
            $dirty12 |= 3072;
        } else if (($changed1 & 3072) == 0) {
            $dirty12 |= $composer2.changed(maxLines) ? 2048 : 1024;
        }
        int i16 = i & 16384;
        if (i16 != 0) {
            $dirty12 |= 24576;
            i2 = i16;
        } else {
            i2 = i16;
            if (($changed1 & 24576) == 0) {
                $dirty12 |= $composer2.changed(minLines) ? 16384 : 8192;
            }
        }
        int i17 = i & 32768;
        if (i17 != 0) {
            $dirty12 |= ProfileVerifier.CompilationStatus.RESULT_CODE_ERROR_CANT_WRITE_PROFILE_VERIFICATION_RESULT_CACHE_FILE;
        } else if (($changed1 & ProfileVerifier.CompilationStatus.RESULT_CODE_ERROR_CANT_WRITE_PROFILE_VERIFICATION_RESULT_CACHE_FILE) == 0) {
            $dirty12 |= $composer2.changedInstance(map) ? 131072 : 65536;
        }
        int i18 = i & 65536;
        if (i18 != 0) {
            $dirty12 |= 1572864;
        } else if (($changed1 & 1572864) == 0) {
            $dirty12 |= $composer2.changedInstance(function1) ? 1048576 : 524288;
        }
        if (($changed1 & 12582912) == 0) {
            if ((i & 131072) == 0 && $composer2.changed(style)) {
                i3 = 8388608;
                $dirty12 |= i3;
            }
            i3 = 4194304;
            $dirty12 |= i3;
        }
        if (($dirty2 & 306783379) == 306783378 && (4793491 & $dirty12) == 4793490 && $composer2.getSkipping()) {
            $composer2.skipToGroupEnd();
            modifier3 = modifier;
            color3 = color;
            fontSize3 = fontSize;
            fontStyle3 = fontStyle;
            fontWeight3 = fontWeight;
            fontFamily3 = fontFamily;
            letterSpacing3 = letterSpacing;
            textDecoration3 = textDecoration;
            textAlign3 = textAlign;
            lineHeight3 = lineHeight;
            overflow3 = overflow;
            softWrap4 = softWrap;
            maxLines3 = maxLines;
            minLines4 = minLines;
            inlineContent2 = map;
            onTextLayout2 = function1;
            style2 = style;
        } else {
            $composer2.startDefaults();
            if (($changed & 1) == 0 || $composer2.getDefaultsInvalid()) {
                Modifier.Companion modifier4 = i4 != 0 ? Modifier.INSTANCE : modifier;
                color2 = i5 != 0 ? Color.INSTANCE.m3782getUnspecified0d7_KjU() : color;
                long fontSize4 = i6 != 0 ? TextUnit.INSTANCE.m6296getUnspecifiedXSAIIZE() : fontSize;
                fontStyle2 = i7 != 0 ? null : fontStyle;
                fontWeight2 = i8 != 0 ? null : fontWeight;
                fontFamily2 = i9 != 0 ? null : fontFamily;
                letterSpacing2 = i10 != 0 ? TextUnit.INSTANCE.m6296getUnspecifiedXSAIIZE() : letterSpacing;
                textDecoration2 = i11 != 0 ? null : textDecoration;
                textAlign2 = i12 != 0 ? null : textAlign;
                long lineHeight4 = $dirty3 != 0 ? TextUnit.INSTANCE.m6296getUnspecifiedXSAIIZE() : lineHeight;
                int overflow4 = i13 != 0 ? TextOverflow.INSTANCE.m6013getClipgIe3tQ8() : overflow;
                boolean softWrap5 = i14 != 0 ? true : softWrap;
                int maxLines4 = i15 != 0 ? Integer.MAX_VALUE : maxLines;
                int minLines5 = i2 != 0 ? 1 : minLines;
                Map inlineContent3 = i17 != 0 ? MapsKt.emptyMap() : map;
                Function1 onTextLayout3 = i18 != 0 ? new Function1<TextLayoutResult, Unit>() { // from class: androidx.compose.material3.TextKt$Text$4
                    @Override // kotlin.jvm.functions.Function1
                    public /* bridge */ /* synthetic */ Unit invoke(TextLayoutResult textLayoutResult) {
                        invoke2(textLayoutResult);
                        return Unit.INSTANCE;
                    }

                    /* renamed from: invoke, reason: avoid collision after fix types in other method */
                    public final void invoke2(TextLayoutResult it) {
                    }
                } : function1;
                if ((i & 131072) != 0) {
                    int overflow5 = overflow4;
                    ProvidableCompositionLocal<TextStyle> providableCompositionLocal = LocalTextStyle;
                    Modifier modifier5 = modifier4;
                    ComposerKt.sourceInformationMarkerStart($composer2, 2023513938, "CC:CompositionLocal.kt#9igjgp");
                    Object consume = $composer2.consume(providableCompositionLocal);
                    ComposerKt.sourceInformationMarkerEnd($composer2);
                    textDecoration2 = textDecoration2;
                    style2 = (TextStyle) consume;
                    $dirty1 = $dirty12 & (-29360129);
                    minLines2 = minLines5;
                    inlineContent = inlineContent3;
                    onTextLayout = onTextLayout3;
                    fontSize2 = fontSize4;
                    minLines3 = overflow5;
                    modifier2 = modifier5;
                    softWrap2 = softWrap5;
                    maxLines2 = maxLines4;
                    lineHeight2 = lineHeight4;
                } else {
                    int overflow6 = overflow4;
                    style2 = style;
                    modifier2 = modifier4;
                    $dirty1 = $dirty12;
                    minLines2 = minLines5;
                    inlineContent = inlineContent3;
                    onTextLayout = onTextLayout3;
                    fontSize2 = fontSize4;
                    minLines3 = overflow6;
                    softWrap2 = softWrap5;
                    maxLines2 = maxLines4;
                    lineHeight2 = lineHeight4;
                }
            } else {
                $composer2.skipToGroupEnd();
                if ((i & 131072) != 0) {
                    int i19 = (-29360129) & $dirty12;
                    color2 = color;
                    fontSize2 = fontSize;
                    fontStyle2 = fontStyle;
                    fontWeight2 = fontWeight;
                    fontFamily2 = fontFamily;
                    letterSpacing2 = letterSpacing;
                    textDecoration2 = textDecoration;
                    textAlign2 = textAlign;
                    lineHeight2 = lineHeight;
                    minLines3 = overflow;
                    softWrap2 = softWrap;
                    maxLines2 = maxLines;
                    minLines2 = minLines;
                    inlineContent = map;
                    onTextLayout = function1;
                    style2 = style;
                    $dirty1 = i19;
                    modifier2 = modifier;
                } else {
                    modifier2 = modifier;
                    color2 = color;
                    fontStyle2 = fontStyle;
                    fontWeight2 = fontWeight;
                    fontFamily2 = fontFamily;
                    letterSpacing2 = letterSpacing;
                    textDecoration2 = textDecoration;
                    textAlign2 = textAlign;
                    lineHeight2 = lineHeight;
                    minLines3 = overflow;
                    softWrap2 = softWrap;
                    maxLines2 = maxLines;
                    minLines2 = minLines;
                    inlineContent = map;
                    onTextLayout = function1;
                    style2 = style;
                    $dirty1 = $dirty12;
                    fontSize2 = fontSize;
                }
            }
            $composer2.endDefaults();
            if (ComposerKt.isTraceInProgress()) {
                softWrap3 = softWrap2;
                ComposerKt.traceEventStart(2027001676, $dirty2, $dirty1, "androidx.compose.material3.Text (Text.kt:255)");
            } else {
                softWrap3 = softWrap2;
            }
            $composer2.startReplaceableGroup(79588770);
            ComposerKt.sourceInformation($composer2, "");
            long $this$takeOrElse_u2dDxMtmZc$iv = color2;
            if ($this$takeOrElse_u2dDxMtmZc$iv != Color.INSTANCE.m3782getUnspecified0d7_KjU()) {
                overflow2 = minLines3;
                textColor = $this$takeOrElse_u2dDxMtmZc$iv;
            } else {
                $composer2.startReplaceableGroup(79588803);
                ComposerKt.sourceInformation($composer2, "*258@11646L7");
                long $this$takeOrElse_u2dDxMtmZc$iv2 = style2.m5601getColor0d7_KjU();
                if ($this$takeOrElse_u2dDxMtmZc$iv2 != Color.INSTANCE.m3782getUnspecified0d7_KjU()) {
                    overflow2 = minLines3;
                } else {
                    ProvidableCompositionLocal<Color> localContentColor = ContentColorKt.getLocalContentColor();
                    overflow2 = minLines3;
                    ComposerKt.sourceInformationMarkerStart($composer2, 2023513938, "CC:CompositionLocal.kt#9igjgp");
                    Object consume2 = $composer2.consume(localContentColor);
                    ComposerKt.sourceInformationMarkerEnd($composer2);
                    $this$takeOrElse_u2dDxMtmZc$iv2 = ((Color) consume2).m3756unboximpl();
                }
                $composer2.endReplaceableGroup();
                textColor = $this$takeOrElse_u2dDxMtmZc$iv2;
            }
            $composer2.endReplaceableGroup();
            m5616mergedA7vx0o = style2.m5616mergedA7vx0o((r58 & 1) != 0 ? Color.INSTANCE.m3782getUnspecified0d7_KjU() : textColor, (r58 & 2) != 0 ? TextUnit.INSTANCE.m6296getUnspecifiedXSAIIZE() : fontSize2, (r58 & 4) != 0 ? null : fontWeight2, (r58 & 8) != 0 ? null : fontStyle2, (r58 & 16) != 0 ? null : null, (r58 & 32) != 0 ? null : fontFamily2, (r58 & 64) != 0 ? null : null, (r58 & 128) != 0 ? TextUnit.INSTANCE.m6296getUnspecifiedXSAIIZE() : letterSpacing2, (r58 & 256) != 0 ? null : null, (r58 & 512) != 0 ? null : null, (r58 & 1024) != 0 ? null : null, (r58 & 2048) != 0 ? Color.INSTANCE.m3782getUnspecified0d7_KjU() : 0L, (r58 & 4096) != 0 ? null : textDecoration2, (r58 & 8192) != 0 ? null : null, (r58 & 16384) != 0 ? null : null, (r58 & 32768) != 0 ? TextAlign.INSTANCE.m5970getUnspecifiede0LSkKk() : textAlign2 != null ? textAlign2.getValue() : TextAlign.INSTANCE.m5970getUnspecifiede0LSkKk(), (r58 & 65536) != 0 ? TextDirection.INSTANCE.m5983getUnspecifieds_7Xco() : 0, (r58 & 131072) != 0 ? TextUnit.INSTANCE.m6296getUnspecifiedXSAIIZE() : lineHeight2, (r58 & 262144) != 0 ? null : null, (r58 & 524288) != 0 ? null : null, (r58 & 1048576) != 0 ? LineBreak.INSTANCE.m5897getUnspecifiedrAG3T2k() : 0, (r58 & 2097152) != 0 ? Hyphens.INSTANCE.m5876getUnspecifiedvmbZdU8() : 0, (r58 & 4194304) != 0 ? null : null, (r58 & 8388608) != 0 ? null : null);
            BasicTextKt.m840BasicTextRWo7tUw(text, modifier2, m5616mergedA7vx0o, onTextLayout, overflow2, softWrap3, maxLines2, minLines2, inlineContent, null, $composer2, ($dirty2 & 14) | ($dirty2 & 112) | (($dirty1 >> 9) & 7168) | (($dirty1 << 9) & 57344) | (($dirty1 << 9) & 458752) | (($dirty1 << 9) & 3670016) | (($dirty1 << 9) & 29360128) | (($dirty1 << 9) & 234881024), 512);
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventEnd();
            }
            softWrap4 = softWrap3;
            overflow3 = overflow2;
            modifier3 = modifier2;
            fontSize3 = fontSize2;
            textDecoration3 = textDecoration2;
            textAlign3 = textAlign2;
            lineHeight3 = lineHeight2;
            fontStyle3 = fontStyle2;
            fontWeight3 = fontWeight2;
            fontFamily3 = fontFamily2;
            maxLines3 = maxLines2;
            minLines4 = minLines2;
            inlineContent2 = inlineContent;
            onTextLayout2 = onTextLayout;
            letterSpacing3 = letterSpacing2;
            color3 = color2;
        }
        ScopeUpdateScope endRestartGroup = $composer2.endRestartGroup();
        if (endRestartGroup != null) {
            final Modifier modifier6 = modifier3;
            final long j = color3;
            final long j2 = fontSize3;
            final FontStyle fontStyle4 = fontStyle3;
            final FontWeight fontWeight4 = fontWeight3;
            final FontFamily fontFamily4 = fontFamily3;
            final long j3 = letterSpacing3;
            final TextDecoration textDecoration4 = textDecoration3;
            final TextAlign textAlign4 = textAlign3;
            final long j4 = lineHeight3;
            final int i20 = overflow3;
            final boolean z = softWrap4;
            final int i21 = maxLines3;
            final int i22 = minLines4;
            final Map map2 = inlineContent2;
            final Function1 function12 = onTextLayout2;
            final TextStyle textStyle = style2;
            endRestartGroup.updateScope(new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.TextKt$Text$5
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

                public final void invoke(Composer composer, int i23) {
                    TextKt.m2465TextIbK3jfQ(AnnotatedString.this, modifier6, j, j2, fontStyle4, fontWeight4, fontFamily4, j3, textDecoration4, textAlign4, j4, i20, z, i21, i22, map2, function12, textStyle, composer, RecomposeScopeImplKt.updateChangedFlags($changed | 1), RecomposeScopeImplKt.updateChangedFlags($changed1), i);
                }
            });
        }
    }

    @Deprecated(level = DeprecationLevel.HIDDEN, message = "Maintained for binary compatibility. Use version with minLines instead")
    /* renamed from: Text--4IGK_g, reason: not valid java name */
    public static final /* synthetic */ void m2463Text4IGK_g(final AnnotatedString text, Modifier modifier, long color, long fontSize, FontStyle fontStyle, FontWeight fontWeight, FontFamily fontFamily, long letterSpacing, TextDecoration textDecoration, TextAlign textAlign, long lineHeight, int overflow, boolean softWrap, int maxLines, Map inlineContent, Function1 onTextLayout, TextStyle style, Composer $composer, final int $changed, final int $changed1, final int i) {
        int i2;
        FontStyle fontStyle2;
        FontWeight fontWeight2;
        FontFamily fontFamily2;
        int overflow2;
        TextStyle style2;
        Modifier modifier2;
        int $dirty1;
        boolean softWrap2;
        int maxLines2;
        Map inlineContent2;
        Function1 onTextLayout2;
        long color2;
        long letterSpacing2;
        long lineHeight2;
        TextDecoration textDecoration2;
        TextAlign textAlign2;
        long fontSize2;
        Composer $composer2;
        Modifier modifier3;
        long color3;
        long fontSize3;
        long letterSpacing3;
        TextDecoration textDecoration3;
        FontStyle fontStyle3;
        TextAlign textAlign3;
        FontWeight fontWeight3;
        FontFamily fontFamily3;
        int i3;
        Composer $composer3 = $composer.startRestartGroup(224529679);
        ComposerKt.sourceInformation($composer3, "C(Text)P(14,9,0:c#ui.graphics.Color,2:c#ui.unit.TextUnit,3:c#ui.text.font.FontStyle,4!1,6:c#ui.unit.TextUnit,16,15:c#ui.text.style.TextAlign,7:c#ui.unit.TextUnit,11:c#ui.text.style.TextOverflow,12,8)307@13179L7,309@13195L345:Text.kt#uh7d8r");
        int $dirty = $changed;
        int $dirty12 = $changed1;
        if ((i & 1) != 0) {
            $dirty |= 6;
        } else if (($changed & 6) == 0) {
            $dirty |= $composer3.changed(text) ? 4 : 2;
        }
        int i4 = i & 2;
        if (i4 != 0) {
            $dirty |= 48;
        } else if (($changed & 48) == 0) {
            $dirty |= $composer3.changed(modifier) ? 32 : 16;
        }
        int i5 = i & 4;
        if (i5 != 0) {
            $dirty |= 384;
        } else if (($changed & 384) == 0) {
            $dirty |= $composer3.changed(color) ? 256 : 128;
        }
        int i6 = i & 8;
        if (i6 != 0) {
            $dirty |= 3072;
        } else if (($changed & 3072) == 0) {
            $dirty |= $composer3.changed(fontSize) ? 2048 : 1024;
        }
        int i7 = i & 16;
        if (i7 != 0) {
            $dirty |= 24576;
        } else if (($changed & 24576) == 0) {
            $dirty |= $composer3.changed(fontStyle) ? 16384 : 8192;
        }
        int i8 = i & 32;
        if (i8 != 0) {
            $dirty |= ProfileVerifier.CompilationStatus.RESULT_CODE_ERROR_CANT_WRITE_PROFILE_VERIFICATION_RESULT_CACHE_FILE;
        } else if (($changed & ProfileVerifier.CompilationStatus.RESULT_CODE_ERROR_CANT_WRITE_PROFILE_VERIFICATION_RESULT_CACHE_FILE) == 0) {
            $dirty |= $composer3.changed(fontWeight) ? 131072 : 65536;
        }
        int i9 = i & 64;
        if (i9 != 0) {
            $dirty |= 1572864;
        } else if (($changed & 1572864) == 0) {
            $dirty |= $composer3.changed(fontFamily) ? 1048576 : 524288;
        }
        int i10 = i & 128;
        if (i10 != 0) {
            $dirty |= 12582912;
        } else if (($changed & 12582912) == 0) {
            $dirty |= $composer3.changed(letterSpacing) ? 8388608 : 4194304;
        }
        int i11 = i & 256;
        if (i11 != 0) {
            $dirty |= 100663296;
        } else if (($changed & 100663296) == 0) {
            $dirty |= $composer3.changed(textDecoration) ? AccessibilityEventCompat.TYPE_VIEW_TARGETED_BY_SCROLL : 33554432;
        }
        int i12 = i & 512;
        if (i12 != 0) {
            $dirty |= 805306368;
        } else if (($changed & 805306368) == 0) {
            $dirty |= $composer3.changed(textAlign) ? 536870912 : 268435456;
        }
        int i13 = i & 1024;
        if (i13 != 0) {
            $dirty12 |= 6;
        } else if (($changed1 & 6) == 0) {
            $dirty12 |= $composer3.changed(lineHeight) ? 4 : 2;
        }
        int i14 = i & 2048;
        if (i14 != 0) {
            $dirty12 |= 48;
        } else if (($changed1 & 48) == 0) {
            $dirty12 |= $composer3.changed(overflow) ? 32 : 16;
        }
        int i15 = i & 4096;
        if (i15 != 0) {
            $dirty12 |= 384;
        } else if (($changed1 & 384) == 0) {
            $dirty12 |= $composer3.changed(softWrap) ? 256 : 128;
        }
        int i16 = i & 8192;
        if (i16 != 0) {
            $dirty12 |= 3072;
        } else if (($changed1 & 3072) == 0) {
            $dirty12 |= $composer3.changed(maxLines) ? 2048 : 1024;
        }
        int i17 = i & 16384;
        if (i17 != 0) {
            $dirty12 |= 24576;
            i2 = i17;
        } else {
            i2 = i17;
            if (($changed1 & 24576) == 0) {
                $dirty12 |= $composer3.changedInstance(inlineContent) ? 16384 : 8192;
            }
        }
        int i18 = i & 32768;
        if (i18 != 0) {
            $dirty12 |= ProfileVerifier.CompilationStatus.RESULT_CODE_ERROR_CANT_WRITE_PROFILE_VERIFICATION_RESULT_CACHE_FILE;
        } else if (($changed1 & ProfileVerifier.CompilationStatus.RESULT_CODE_ERROR_CANT_WRITE_PROFILE_VERIFICATION_RESULT_CACHE_FILE) == 0) {
            $dirty12 |= $composer3.changedInstance(onTextLayout) ? 131072 : 65536;
        }
        if (($changed1 & 1572864) == 0) {
            if ((i & 65536) == 0 && $composer3.changed(style)) {
                i3 = 1048576;
                $dirty12 |= i3;
            }
            i3 = 524288;
            $dirty12 |= i3;
        }
        if (($dirty & 306783379) == 306783378 && (599187 & $dirty12) == 599186 && $composer3.getSkipping()) {
            $composer3.skipToGroupEnd();
            modifier3 = modifier;
            color3 = color;
            fontSize3 = fontSize;
            fontStyle3 = fontStyle;
            fontWeight3 = fontWeight;
            fontFamily3 = fontFamily;
            letterSpacing3 = letterSpacing;
            textDecoration3 = textDecoration;
            textAlign3 = textAlign;
            lineHeight2 = lineHeight;
            overflow2 = overflow;
            softWrap2 = softWrap;
            maxLines2 = maxLines;
            inlineContent2 = inlineContent;
            onTextLayout2 = onTextLayout;
            style2 = style;
            $composer2 = $composer3;
        } else {
            $composer3.startDefaults();
            if (($changed & 1) == 0 || $composer3.getDefaultsInvalid()) {
                Modifier.Companion modifier4 = i4 != 0 ? Modifier.INSTANCE : modifier;
                long color4 = i5 != 0 ? Color.INSTANCE.m3782getUnspecified0d7_KjU() : color;
                long fontSize4 = i6 != 0 ? TextUnit.INSTANCE.m6296getUnspecifiedXSAIIZE() : fontSize;
                fontStyle2 = i7 != 0 ? null : fontStyle;
                fontWeight2 = i8 != 0 ? null : fontWeight;
                fontFamily2 = i9 != 0 ? null : fontFamily;
                long letterSpacing4 = i10 != 0 ? TextUnit.INSTANCE.m6296getUnspecifiedXSAIIZE() : letterSpacing;
                TextDecoration textDecoration4 = i11 != 0 ? null : textDecoration;
                TextAlign textAlign4 = i12 != 0 ? null : textAlign;
                long lineHeight3 = i13 != 0 ? TextUnit.INSTANCE.m6296getUnspecifiedXSAIIZE() : lineHeight;
                int overflow3 = i14 != 0 ? TextOverflow.INSTANCE.m6013getClipgIe3tQ8() : overflow;
                boolean softWrap3 = i15 != 0 ? true : softWrap;
                int maxLines3 = i16 != 0 ? Integer.MAX_VALUE : maxLines;
                Map inlineContent3 = i2 != 0 ? MapsKt.emptyMap() : inlineContent;
                TextKt$Text$6 onTextLayout3 = i18 != 0 ? new Function1<TextLayoutResult, Unit>() { // from class: androidx.compose.material3.TextKt$Text$6
                    @Override // kotlin.jvm.functions.Function1
                    public /* bridge */ /* synthetic */ Unit invoke(TextLayoutResult textLayoutResult) {
                        invoke2(textLayoutResult);
                        return Unit.INSTANCE;
                    }

                    /* renamed from: invoke, reason: avoid collision after fix types in other method */
                    public final void invoke2(TextLayoutResult it) {
                    }
                } : onTextLayout;
                if ((i & 65536) != 0) {
                    TextDecoration textDecoration5 = textDecoration4;
                    ProvidableCompositionLocal<TextStyle> providableCompositionLocal = LocalTextStyle;
                    Modifier modifier5 = modifier4;
                    ComposerKt.sourceInformationMarkerStart($composer3, 2023513938, "CC:CompositionLocal.kt#9igjgp");
                    Object consume = $composer3.consume(providableCompositionLocal);
                    ComposerKt.sourceInformationMarkerEnd($composer3);
                    overflow2 = overflow3;
                    style2 = (TextStyle) consume;
                    $dirty1 = $dirty12 & (-3670017);
                    softWrap2 = softWrap3;
                    maxLines2 = maxLines3;
                    inlineContent2 = inlineContent3;
                    onTextLayout2 = onTextLayout3;
                    color2 = color4;
                    letterSpacing2 = letterSpacing4;
                    lineHeight2 = lineHeight3;
                    textDecoration2 = textDecoration5;
                    modifier2 = modifier5;
                    textAlign2 = textAlign4;
                    fontSize2 = fontSize4;
                } else {
                    TextDecoration textDecoration6 = textDecoration4;
                    overflow2 = overflow3;
                    style2 = style;
                    modifier2 = modifier4;
                    $dirty1 = $dirty12;
                    softWrap2 = softWrap3;
                    maxLines2 = maxLines3;
                    inlineContent2 = inlineContent3;
                    onTextLayout2 = onTextLayout3;
                    color2 = color4;
                    letterSpacing2 = letterSpacing4;
                    lineHeight2 = lineHeight3;
                    textDecoration2 = textDecoration6;
                    textAlign2 = textAlign4;
                    fontSize2 = fontSize4;
                }
            } else {
                $composer3.skipToGroupEnd();
                if ((i & 65536) != 0) {
                    int i19 = (-3670017) & $dirty12;
                    color2 = color;
                    fontSize2 = fontSize;
                    fontStyle2 = fontStyle;
                    fontWeight2 = fontWeight;
                    fontFamily2 = fontFamily;
                    letterSpacing2 = letterSpacing;
                    textDecoration2 = textDecoration;
                    textAlign2 = textAlign;
                    lineHeight2 = lineHeight;
                    overflow2 = overflow;
                    softWrap2 = softWrap;
                    maxLines2 = maxLines;
                    inlineContent2 = inlineContent;
                    onTextLayout2 = onTextLayout;
                    style2 = style;
                    $dirty1 = i19;
                    modifier2 = modifier;
                } else {
                    modifier2 = modifier;
                    fontSize2 = fontSize;
                    fontStyle2 = fontStyle;
                    fontWeight2 = fontWeight;
                    fontFamily2 = fontFamily;
                    letterSpacing2 = letterSpacing;
                    textDecoration2 = textDecoration;
                    textAlign2 = textAlign;
                    lineHeight2 = lineHeight;
                    overflow2 = overflow;
                    softWrap2 = softWrap;
                    maxLines2 = maxLines;
                    inlineContent2 = inlineContent;
                    onTextLayout2 = onTextLayout;
                    style2 = style;
                    $dirty1 = $dirty12;
                    color2 = color;
                }
            }
            $composer3.endDefaults();
            if (ComposerKt.isTraceInProgress()) {
                $composer2 = $composer3;
                ComposerKt.traceEventStart(224529679, $dirty, $dirty1, "androidx.compose.material3.Text (Text.kt:308)");
            } else {
                $composer2 = $composer3;
            }
            m2465TextIbK3jfQ(text, modifier2, color2, fontSize2, fontStyle2, fontWeight2, fontFamily2, letterSpacing2, textDecoration2, textAlign2, lineHeight2, overflow2, softWrap2, maxLines2, 1, inlineContent2, onTextLayout2, style2, $composer2, ($dirty & 14) | ($dirty & 112) | ($dirty & 896) | ($dirty & 7168) | (57344 & $dirty) | (458752 & $dirty) | (3670016 & $dirty) | (29360128 & $dirty) | (234881024 & $dirty) | (1879048192 & $dirty), ($dirty1 & 14) | 24576 | ($dirty1 & 112) | ($dirty1 & 896) | ($dirty1 & 7168) | (($dirty1 << 3) & 458752) | (($dirty1 << 3) & 3670016) | (($dirty1 << 3) & 29360128), 0);
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventEnd();
            }
            modifier3 = modifier2;
            color3 = color2;
            fontSize3 = fontSize2;
            letterSpacing3 = letterSpacing2;
            textDecoration3 = textDecoration2;
            fontStyle3 = fontStyle2;
            textAlign3 = textAlign2;
            fontWeight3 = fontWeight2;
            fontFamily3 = fontFamily2;
        }
        ScopeUpdateScope endRestartGroup = $composer2.endRestartGroup();
        if (endRestartGroup != null) {
            final Modifier modifier6 = modifier3;
            final long j = color3;
            final long j2 = fontSize3;
            final FontStyle fontStyle4 = fontStyle3;
            final FontWeight fontWeight4 = fontWeight3;
            final FontFamily fontFamily4 = fontFamily3;
            final long j3 = letterSpacing3;
            final TextDecoration textDecoration7 = textDecoration3;
            final TextAlign textAlign5 = textAlign3;
            final long j4 = lineHeight2;
            final int i20 = overflow2;
            final boolean z = softWrap2;
            final int i21 = maxLines2;
            final Map map = inlineContent2;
            final Function1 function1 = onTextLayout2;
            final TextStyle textStyle = style2;
            endRestartGroup.updateScope(new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.TextKt$Text$7
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

                public final void invoke(Composer composer, int i22) {
                    TextKt.m2463Text4IGK_g(AnnotatedString.this, modifier6, j, j2, fontStyle4, fontWeight4, fontFamily4, j3, textDecoration7, textAlign5, j4, i20, z, i21, map, function1, textStyle, composer, RecomposeScopeImplKt.updateChangedFlags($changed | 1), RecomposeScopeImplKt.updateChangedFlags($changed1), i);
                }
            });
        }
    }

    public static final ProvidableCompositionLocal<TextStyle> getLocalTextStyle() {
        return LocalTextStyle;
    }

    public static final void ProvideTextStyle(final TextStyle value, final Function2<? super Composer, ? super Integer, Unit> function2, Composer $composer, final int $changed) {
        Composer $composer2 = $composer.startRestartGroup(-460300127);
        ComposerKt.sourceInformation($composer2, "C(ProvideTextStyle)P(1)350@14496L7,351@14521L80:Text.kt#uh7d8r");
        int $dirty = $changed;
        if (($changed & 6) == 0) {
            $dirty |= $composer2.changed(value) ? 4 : 2;
        }
        if (($changed & 48) == 0) {
            $dirty |= $composer2.changedInstance(function2) ? 32 : 16;
        }
        if (($dirty & 19) != 18 || !$composer2.getSkipping()) {
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventStart(-460300127, $dirty, -1, "androidx.compose.material3.ProvideTextStyle (Text.kt:349)");
            }
            ProvidableCompositionLocal<TextStyle> providableCompositionLocal = LocalTextStyle;
            ComposerKt.sourceInformationMarkerStart($composer2, 2023513938, "CC:CompositionLocal.kt#9igjgp");
            Object consume = $composer2.consume(providableCompositionLocal);
            ComposerKt.sourceInformationMarkerEnd($composer2);
            TextStyle mergedStyle = ((TextStyle) consume).merge(value);
            CompositionLocalKt.CompositionLocalProvider(LocalTextStyle.provides(mergedStyle), function2, $composer2, ProvidedValue.$stable | 0 | ($dirty & 112));
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventEnd();
            }
        } else {
            $composer2.skipToGroupEnd();
        }
        ScopeUpdateScope endRestartGroup = $composer2.endRestartGroup();
        if (endRestartGroup != null) {
            endRestartGroup.updateScope(new Function2<Composer, Integer, Unit>() { // from class: androidx.compose.material3.TextKt$ProvideTextStyle$1
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
                    TextKt.ProvideTextStyle(TextStyle.this, function2, composer, RecomposeScopeImplKt.updateChangedFlags($changed | 1));
                }
            });
        }
    }
}
