package androidx.compose.ui.text;

import android.os.Build;
import android.text.Spannable;
import android.text.SpannableString;
import androidx.compose.ui.text.android.TextLayout;
import androidx.compose.ui.text.android.style.IndentationFixSpan;
import androidx.compose.ui.text.platform.extensions.SpannableExtensions_androidKt;
import androidx.compose.ui.text.style.Hyphens;
import androidx.compose.ui.text.style.LineBreak;
import androidx.compose.ui.text.style.TextAlign;
import androidx.compose.ui.unit.TextUnit;
import androidx.compose.ui.unit.TextUnitKt;
import kotlin.Metadata;

/* compiled from: AndroidParagraph.android.kt */
@Metadata(d1 = {"\u0000L\n\u0000\n\u0002\u0010\u000b\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0010\b\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0004\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0010\r\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0002\u001a\u0018\u0010\u0000\u001a\u00020\u00012\u0006\u0010\u0002\u001a\u00020\u00032\u0006\u0010\u0004\u001a\u00020\u0001H\u0002\u001a\u001a\u0010\u0005\u001a\u00020\u00062\u0006\u0010\u0007\u001a\u00020\bH\u0002ø\u0001\u0000¢\u0006\u0004\b\t\u0010\n\u001a\u001a\u0010\u000b\u001a\u00020\u00062\u0006\u0010\f\u001a\u00020\rH\u0002ø\u0001\u0000¢\u0006\u0004\b\u000e\u0010\n\u001a\u001a\u0010\u000f\u001a\u00020\u00062\u0006\u0010\u0010\u001a\u00020\u0011H\u0002ø\u0001\u0000¢\u0006\u0004\b\u0012\u0010\n\u001a\u001a\u0010\u0013\u001a\u00020\u00062\u0006\u0010\u0014\u001a\u00020\u0015H\u0002ø\u0001\u0000¢\u0006\u0004\b\u0016\u0010\n\u001a\u001a\u0010\u0017\u001a\u00020\u00062\u0006\u0010\u0018\u001a\u00020\u0019H\u0002ø\u0001\u0000¢\u0006\u0004\b\u001a\u0010\n\u001a\f\u0010\u001b\u001a\u00020\u001c*\u00020\u001cH\u0002\u001a\u0014\u0010\u001d\u001a\u00020\u0006*\u00020\u001e2\u0006\u0010\u001f\u001a\u00020\u0006H\u0002\u0082\u0002\u0007\n\u0005\b¡\u001e0\u0001¨\u0006 "}, d2 = {"shouldAttachIndentationFixSpan", "", "textStyle", "Landroidx/compose/ui/text/TextStyle;", "ellipsis", "toLayoutAlign", "", "align", "Landroidx/compose/ui/text/style/TextAlign;", "toLayoutAlign-aXe7zB0", "(I)I", "toLayoutBreakStrategy", "breakStrategy", "Landroidx/compose/ui/text/style/LineBreak$Strategy;", "toLayoutBreakStrategy-xImikfE", "toLayoutHyphenationFrequency", "hyphens", "Landroidx/compose/ui/text/style/Hyphens;", "toLayoutHyphenationFrequency--3fSNIE", "toLayoutLineBreakStyle", "lineBreakStrictness", "Landroidx/compose/ui/text/style/LineBreak$Strictness;", "toLayoutLineBreakStyle-hpcqdu8", "toLayoutLineBreakWordStyle", "lineBreakWordStyle", "Landroidx/compose/ui/text/style/LineBreak$WordBreak;", "toLayoutLineBreakWordStyle-wPN0Rpw", "attachIndentationFixSpan", "", "numberOfLinesThatFitMaxHeight", "Landroidx/compose/ui/text/android/TextLayout;", "maxHeight", "ui-text_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes11.dex */
public final class AndroidParagraph_androidKt {
    /* JADX INFO: Access modifiers changed from: private */
    /* renamed from: toLayoutAlign-aXe7zB0, reason: not valid java name */
    public static final int m5429toLayoutAlignaXe7zB0(int align) {
        if (TextAlign.m5960equalsimpl0(align, TextAlign.INSTANCE.m5967getLefte0LSkKk())) {
            return 3;
        }
        if (TextAlign.m5960equalsimpl0(align, TextAlign.INSTANCE.m5968getRighte0LSkKk())) {
            return 4;
        }
        if (TextAlign.m5960equalsimpl0(align, TextAlign.INSTANCE.m5964getCentere0LSkKk())) {
            return 2;
        }
        return (!TextAlign.m5960equalsimpl0(align, TextAlign.INSTANCE.m5969getStarte0LSkKk()) && TextAlign.m5960equalsimpl0(align, TextAlign.INSTANCE.m5965getEnde0LSkKk())) ? 1 : 0;
    }

    /* JADX INFO: Access modifiers changed from: private */
    /* renamed from: toLayoutHyphenationFrequency--3fSNIE, reason: not valid java name */
    public static final int m5431toLayoutHyphenationFrequency3fSNIE(int hyphens) {
        if (!Hyphens.m5870equalsimpl0(hyphens, Hyphens.INSTANCE.m5874getAutovmbZdU8())) {
            return Hyphens.m5870equalsimpl0(hyphens, Hyphens.INSTANCE.m5875getNonevmbZdU8()) ? 0 : 0;
        }
        if (Build.VERSION.SDK_INT <= 32) {
            return 2;
        }
        return 4;
    }

    /* JADX INFO: Access modifiers changed from: private */
    /* renamed from: toLayoutBreakStrategy-xImikfE, reason: not valid java name */
    public static final int m5430toLayoutBreakStrategyxImikfE(int breakStrategy) {
        if (LineBreak.Strategy.m5901equalsimpl0(breakStrategy, LineBreak.Strategy.INSTANCE.m5907getSimplefcGXIks())) {
            return 0;
        }
        if (LineBreak.Strategy.m5901equalsimpl0(breakStrategy, LineBreak.Strategy.INSTANCE.m5906getHighQualityfcGXIks())) {
            return 1;
        }
        return LineBreak.Strategy.m5901equalsimpl0(breakStrategy, LineBreak.Strategy.INSTANCE.m5905getBalancedfcGXIks()) ? 2 : 0;
    }

    /* JADX INFO: Access modifiers changed from: private */
    /* renamed from: toLayoutLineBreakStyle-hpcqdu8, reason: not valid java name */
    public static final int m5432toLayoutLineBreakStylehpcqdu8(int lineBreakStrictness) {
        if (LineBreak.Strictness.m5912equalsimpl0(lineBreakStrictness, LineBreak.Strictness.INSTANCE.m5916getDefaultusljTpc())) {
            return 0;
        }
        if (LineBreak.Strictness.m5912equalsimpl0(lineBreakStrictness, LineBreak.Strictness.INSTANCE.m5917getLooseusljTpc())) {
            return 1;
        }
        if (LineBreak.Strictness.m5912equalsimpl0(lineBreakStrictness, LineBreak.Strictness.INSTANCE.m5918getNormalusljTpc())) {
            return 2;
        }
        return LineBreak.Strictness.m5912equalsimpl0(lineBreakStrictness, LineBreak.Strictness.INSTANCE.m5919getStrictusljTpc()) ? 3 : 0;
    }

    /* JADX INFO: Access modifiers changed from: private */
    /* renamed from: toLayoutLineBreakWordStyle-wPN0Rpw, reason: not valid java name */
    public static final int m5433toLayoutLineBreakWordStylewPN0Rpw(int lineBreakWordStyle) {
        return (!LineBreak.WordBreak.m5924equalsimpl0(lineBreakWordStyle, LineBreak.WordBreak.INSTANCE.m5928getDefaultjp8hJ3c()) && LineBreak.WordBreak.m5924equalsimpl0(lineBreakWordStyle, LineBreak.WordBreak.INSTANCE.m5929getPhrasejp8hJ3c())) ? 1 : 0;
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final int numberOfLinesThatFitMaxHeight(TextLayout $this$numberOfLinesThatFitMaxHeight, int maxHeight) {
        int lineCount = $this$numberOfLinesThatFitMaxHeight.getLineCount();
        for (int lineIndex = 0; lineIndex < lineCount; lineIndex++) {
            if ($this$numberOfLinesThatFitMaxHeight.getLineBottom(lineIndex) > maxHeight) {
                return lineIndex;
            }
        }
        int lineIndex2 = $this$numberOfLinesThatFitMaxHeight.getLineCount();
        return lineIndex2;
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final boolean shouldAttachIndentationFixSpan(TextStyle textStyle, boolean ellipsis) {
        return (!ellipsis || TextUnit.m6282equalsimpl0(textStyle.m5607getLetterSpacingXSAIIZE(), TextUnitKt.getSp(0)) || TextUnit.m6282equalsimpl0(textStyle.m5607getLetterSpacingXSAIIZE(), TextUnit.INSTANCE.m6296getUnspecifiedXSAIIZE()) || TextAlign.m5960equalsimpl0(textStyle.m5612getTextAligne0LSkKk(), TextAlign.INSTANCE.m5970getUnspecifiede0LSkKk()) || TextAlign.m5960equalsimpl0(textStyle.m5612getTextAligne0LSkKk(), TextAlign.INSTANCE.m5969getStarte0LSkKk()) || TextAlign.m5960equalsimpl0(textStyle.m5612getTextAligne0LSkKk(), TextAlign.INSTANCE.m5966getJustifye0LSkKk())) ? false : true;
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final CharSequence attachIndentationFixSpan(CharSequence $this$attachIndentationFixSpan) {
        if ($this$attachIndentationFixSpan.length() == 0) {
            return $this$attachIndentationFixSpan;
        }
        SpannableString spannable = $this$attachIndentationFixSpan instanceof Spannable ? (Spannable) $this$attachIndentationFixSpan : new SpannableString($this$attachIndentationFixSpan);
        SpannableExtensions_androidKt.setSpan(spannable, new IndentationFixSpan(), spannable.length() - 1, spannable.length() - 1);
        return spannable;
    }
}
