package androidx.compose.ui.text.platform;

import androidx.compose.ui.text.AnnotatedString;
import androidx.compose.ui.text.EmojiSupportMatch;
import androidx.compose.ui.text.ParagraphIntrinsics;
import androidx.compose.ui.text.Placeholder;
import androidx.compose.ui.text.PlatformParagraphStyle;
import androidx.compose.ui.text.PlatformTextStyle;
import androidx.compose.ui.text.SpanStyle;
import androidx.compose.ui.text.TextStyle;
import androidx.compose.ui.text.font.FontFamily;
import androidx.compose.ui.text.intl.LocaleList;
import androidx.compose.ui.unit.Density;
import java.util.List;
import kotlin.Metadata;

/* compiled from: AndroidParagraphIntrinsics.android.kt */
@Metadata(d1 = {"\u0000P\n\u0000\n\u0002\u0010\u000b\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010\u000e\n\u0002\b\u0002\n\u0002\u0010 \n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010\b\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\u001aP\u0010\u0005\u001a\u00020\u00062\u0006\u0010\u0007\u001a\u00020\b2\u0006\u0010\t\u001a\u00020\u00022\u0012\u0010\n\u001a\u000e\u0012\n\u0012\b\u0012\u0004\u0012\u00020\r0\f0\u000b2\u0012\u0010\u000e\u001a\u000e\u0012\n\u0012\b\u0012\u0004\u0012\u00020\u000f0\f0\u000b2\u0006\u0010\u0010\u001a\u00020\u00112\u0006\u0010\u0012\u001a\u00020\u0013H\u0000\u001a&\u0010\u0014\u001a\u00020\u00152\u0006\u0010\u0016\u001a\u00020\u00172\n\b\u0002\u0010\u0018\u001a\u0004\u0018\u00010\u0019H\u0000ø\u0001\u0000¢\u0006\u0004\b\u001a\u0010\u001b\"\u0018\u0010\u0000\u001a\u00020\u0001*\u00020\u00028BX\u0082\u0004¢\u0006\u0006\u001a\u0004\b\u0003\u0010\u0004\u0082\u0002\u0007\n\u0005\b¡\u001e0\u0001¨\u0006\u001c"}, d2 = {"hasEmojiCompat", "", "Landroidx/compose/ui/text/TextStyle;", "getHasEmojiCompat", "(Landroidx/compose/ui/text/TextStyle;)Z", "ActualParagraphIntrinsics", "Landroidx/compose/ui/text/ParagraphIntrinsics;", "text", "", "style", "spanStyles", "", "Landroidx/compose/ui/text/AnnotatedString$Range;", "Landroidx/compose/ui/text/SpanStyle;", "placeholders", "Landroidx/compose/ui/text/Placeholder;", "density", "Landroidx/compose/ui/unit/Density;", "fontFamilyResolver", "Landroidx/compose/ui/text/font/FontFamily$Resolver;", "resolveTextDirectionHeuristics", "", "textDirection", "Landroidx/compose/ui/text/style/TextDirection;", "localeList", "Landroidx/compose/ui/text/intl/LocaleList;", "resolveTextDirectionHeuristics-HklW4sA", "(ILandroidx/compose/ui/text/intl/LocaleList;)I", "ui-text_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes11.dex */
public final class AndroidParagraphIntrinsics_androidKt {
    /* renamed from: resolveTextDirectionHeuristics-HklW4sA$default, reason: not valid java name */
    public static /* synthetic */ int m5821resolveTextDirectionHeuristicsHklW4sA$default(int i, LocaleList localeList, int i2, Object obj) {
        if ((i2 & 2) != 0) {
            localeList = null;
        }
        return m5820resolveTextDirectionHeuristicsHklW4sA(i, localeList);
    }

    /* JADX WARN: Code restructure failed: missing block: B:22:0x006d, code lost:
    
        if (r0 == null) goto L22;
     */
    /* renamed from: resolveTextDirectionHeuristics-HklW4sA, reason: not valid java name */
    /*
        Code decompiled incorrectly, please refer to instructions dump.
        To view partially-correct add '--show-bad-code' argument
    */
    public static final int m5820resolveTextDirectionHeuristicsHklW4sA(int r6, androidx.compose.ui.text.intl.LocaleList r7) {
        /*
            androidx.compose.ui.text.style.TextDirection$Companion r0 = androidx.compose.ui.text.style.TextDirection.INSTANCE
            int r0 = r0.m5979getContentOrLtrs_7Xco()
            boolean r0 = androidx.compose.ui.text.style.TextDirection.m5974equalsimpl0(r6, r0)
            r1 = 2
            if (r0 == 0) goto L10
            goto L80
        L10:
            androidx.compose.ui.text.style.TextDirection$Companion r0 = androidx.compose.ui.text.style.TextDirection.INSTANCE
            int r0 = r0.m5980getContentOrRtls_7Xco()
            boolean r0 = androidx.compose.ui.text.style.TextDirection.m5974equalsimpl0(r6, r0)
            r2 = 3
            if (r0 == 0) goto L1f
            r1 = r2
            goto L80
        L1f:
            androidx.compose.ui.text.style.TextDirection$Companion r0 = androidx.compose.ui.text.style.TextDirection.INSTANCE
            int r0 = r0.m5981getLtrs_7Xco()
            boolean r0 = androidx.compose.ui.text.style.TextDirection.m5974equalsimpl0(r6, r0)
            r3 = 0
            if (r0 == 0) goto L2e
            r1 = r3
            goto L80
        L2e:
            androidx.compose.ui.text.style.TextDirection$Companion r0 = androidx.compose.ui.text.style.TextDirection.INSTANCE
            int r0 = r0.m5982getRtls_7Xco()
            boolean r0 = androidx.compose.ui.text.style.TextDirection.m5974equalsimpl0(r6, r0)
            r4 = 1
            if (r0 == 0) goto L3d
            r1 = r4
            goto L80
        L3d:
            androidx.compose.ui.text.style.TextDirection$Companion r0 = androidx.compose.ui.text.style.TextDirection.INSTANCE
            int r0 = r0.m5978getContents_7Xco()
            boolean r0 = androidx.compose.ui.text.style.TextDirection.m5974equalsimpl0(r6, r0)
            if (r0 == 0) goto L4a
            goto L54
        L4a:
            androidx.compose.ui.text.style.TextDirection$Companion r0 = androidx.compose.ui.text.style.TextDirection.INSTANCE
            int r0 = r0.m5983getUnspecifieds_7Xco()
            boolean r4 = androidx.compose.ui.text.style.TextDirection.m5974equalsimpl0(r6, r0)
        L54:
            if (r4 == 0) goto L81
            if (r7 == 0) goto L6f
            r0 = r7
            r4 = 0
            androidx.compose.ui.text.intl.Locale r3 = r0.get(r3)
            androidx.compose.ui.text.intl.PlatformLocale r3 = r3.getPlatformLocale()
            java.lang.String r5 = "null cannot be cast to non-null type androidx.compose.ui.text.intl.AndroidLocale"
            kotlin.jvm.internal.Intrinsics.checkNotNull(r3, r5)
            androidx.compose.ui.text.intl.AndroidLocale r3 = (androidx.compose.ui.text.intl.AndroidLocale) r3
            java.util.Locale r0 = r3.getJavaLocale()
            if (r0 != 0) goto L73
        L6f:
            java.util.Locale r0 = java.util.Locale.getDefault()
        L73:
            int r3 = androidx.core.text.TextUtilsCompat.getLayoutDirectionFromLocale(r0)
            switch(r3) {
                case 0: goto L7f;
                case 1: goto L7d;
                default: goto L7c;
            }
        L7c:
            goto L80
        L7d:
            r1 = r2
            goto L80
        L7f:
        L80:
            return r1
        L81:
            java.lang.IllegalStateException r0 = new java.lang.IllegalStateException
            java.lang.String r1 = "Invalid TextDirection."
            java.lang.String r1 = r1.toString()
            r0.<init>(r1)
            throw r0
        */
        throw new UnsupportedOperationException("Method not decompiled: androidx.compose.ui.text.platform.AndroidParagraphIntrinsics_androidKt.m5820resolveTextDirectionHeuristicsHklW4sA(int, androidx.compose.ui.text.intl.LocaleList):int");
    }

    public static final ParagraphIntrinsics ActualParagraphIntrinsics(String text, TextStyle style, List<AnnotatedString.Range<SpanStyle>> list, List<AnnotatedString.Range<Placeholder>> list2, Density density, FontFamily.Resolver fontFamilyResolver) {
        return new AndroidParagraphIntrinsics(text, style, list, list2, fontFamilyResolver, density);
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final boolean getHasEmojiCompat(TextStyle $this$hasEmojiCompat) {
        PlatformParagraphStyle paragraphSyle;
        PlatformTextStyle platformStyle = $this$hasEmojiCompat.getPlatformStyle();
        return !(((platformStyle == null || (paragraphSyle = platformStyle.getParagraphSyle()) == null) ? null : EmojiSupportMatch.m5435boximpl(paragraphSyle.getEmojiSupportMatch())) == null ? false : EmojiSupportMatch.m5438equalsimpl0(r0.getValue(), EmojiSupportMatch.INSTANCE.m5443getNone_3YsG6Y()));
    }
}
