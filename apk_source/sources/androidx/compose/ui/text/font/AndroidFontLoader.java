package androidx.compose.ui.text.font;

import android.content.Context;
import kotlin.Metadata;
import kotlin.Result;
import kotlin.ResultKt;

/* compiled from: AndroidFontLoader.android.kt */
@Metadata(d1 = {"\u0000(\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0010\u0000\n\u0002\b\u0004\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\b\u0000\u0018\u00002\u00020\u0001B\r\u0012\u0006\u0010\u0002\u001a\u00020\u0003¢\u0006\u0002\u0010\u0004J\u0018\u0010\n\u001a\u0004\u0018\u00010\u000b2\u0006\u0010\f\u001a\u00020\rH\u0096@¢\u0006\u0002\u0010\u000eJ\u0012\u0010\u000f\u001a\u0004\u0018\u00010\u000b2\u0006\u0010\f\u001a\u00020\rH\u0016R\u0016\u0010\u0005\u001a\u0004\u0018\u00010\u0006X\u0096\u0004¢\u0006\b\n\u0000\u001a\u0004\b\u0007\u0010\bR\u0016\u0010\u0002\u001a\n \t*\u0004\u0018\u00010\u00030\u0003X\u0082\u0004¢\u0006\u0002\n\u0000¨\u0006\u0010"}, d2 = {"Landroidx/compose/ui/text/font/AndroidFontLoader;", "Landroidx/compose/ui/text/font/PlatformFontLoader;", "context", "Landroid/content/Context;", "(Landroid/content/Context;)V", "cacheKey", "", "getCacheKey", "()Ljava/lang/Object;", "kotlin.jvm.PlatformType", "awaitLoad", "Landroid/graphics/Typeface;", "font", "Landroidx/compose/ui/text/font/Font;", "(Landroidx/compose/ui/text/font/Font;Lkotlin/coroutines/Continuation;)Ljava/lang/Object;", "loadBlocking", "ui-text_release"}, k = 1, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes11.dex */
public final class AndroidFontLoader implements PlatformFontLoader {
    public static final int $stable = 8;
    private final Object cacheKey;
    private final Context context;

    public AndroidFontLoader(Context context) {
        this.context = context.getApplicationContext();
    }

    @Override // androidx.compose.ui.text.font.PlatformFontLoader
    public android.graphics.Typeface loadBlocking(Font font) {
        Object m6478constructorimpl;
        android.graphics.Typeface typeface;
        android.graphics.Typeface load;
        if (font instanceof AndroidFont) {
            return ((AndroidFont) font).getTypefaceLoader().loadBlocking(this.context, (AndroidFont) font);
        }
        if (!(font instanceof ResourceFont)) {
            return null;
        }
        int loadingStrategy = font.getLoadingStrategy();
        if (FontLoadingStrategy.m5667equalsimpl0(loadingStrategy, FontLoadingStrategy.INSTANCE.m5672getBlockingPKNRLFQ())) {
            typeface = AndroidFontLoader_androidKt.load((ResourceFont) font, this.context);
        } else if (FontLoadingStrategy.m5667equalsimpl0(loadingStrategy, FontLoadingStrategy.INSTANCE.m5673getOptionalLocalPKNRLFQ())) {
            try {
                Result.Companion companion = Result.INSTANCE;
                AndroidFontLoader $this$loadBlocking_u24lambda_u240 = this;
                load = AndroidFontLoader_androidKt.load((ResourceFont) font, $this$loadBlocking_u24lambda_u240.context);
                m6478constructorimpl = Result.m6478constructorimpl(load);
            } catch (Throwable th) {
                Result.Companion companion2 = Result.INSTANCE;
                m6478constructorimpl = Result.m6478constructorimpl(ResultKt.createFailure(th));
            }
            typeface = (android.graphics.Typeface) (Result.m6484isFailureimpl(m6478constructorimpl) ? null : m6478constructorimpl);
        } else {
            if (FontLoadingStrategy.m5667equalsimpl0(loadingStrategy, FontLoadingStrategy.INSTANCE.m5671getAsyncPKNRLFQ())) {
                throw new UnsupportedOperationException("Unsupported Async font load path");
            }
            throw new IllegalArgumentException("Unknown loading type " + ((Object) FontLoadingStrategy.m5669toStringimpl(font.getLoadingStrategy())));
        }
        return PlatformTypefaces_androidKt.setFontVariationSettings(typeface, ((ResourceFont) font).getVariationSettings(), this.context);
    }

    /* JADX WARN: Removed duplicated region for block: B:11:0x002d  */
    /* JADX WARN: Removed duplicated region for block: B:14:0x003a  */
    /* JADX WARN: Removed duplicated region for block: B:16:0x003f  */
    /* JADX WARN: Removed duplicated region for block: B:8:0x0025  */
    @Override // androidx.compose.ui.text.font.PlatformFontLoader
    /*
        Code decompiled incorrectly, please refer to instructions dump.
        To view partially-correct add '--show-bad-code' argument
    */
    public java.lang.Object awaitLoad(androidx.compose.ui.text.font.Font r8, kotlin.coroutines.Continuation<? super android.graphics.Typeface> r9) {
        /*
            r7 = this;
            boolean r0 = r9 instanceof androidx.compose.ui.text.font.AndroidFontLoader$awaitLoad$1
            if (r0 == 0) goto L14
            r0 = r9
            androidx.compose.ui.text.font.AndroidFontLoader$awaitLoad$1 r0 = (androidx.compose.ui.text.font.AndroidFontLoader$awaitLoad$1) r0
            int r1 = r0.label
            r2 = -2147483648(0xffffffff80000000, float:-0.0)
            r1 = r1 & r2
            if (r1 == 0) goto L14
            int r9 = r0.label
            int r9 = r9 - r2
            r0.label = r9
            goto L19
        L14:
            androidx.compose.ui.text.font.AndroidFontLoader$awaitLoad$1 r0 = new androidx.compose.ui.text.font.AndroidFontLoader$awaitLoad$1
            r0.<init>(r7, r9)
        L19:
            r9 = r0
            java.lang.Object r0 = r9.result
            java.lang.Object r1 = kotlin.coroutines.intrinsics.IntrinsicsKt.getCOROUTINE_SUSPENDED()
            int r2 = r9.label
            switch(r2) {
                case 0: goto L3f;
                case 1: goto L3a;
                case 2: goto L2d;
                default: goto L25;
            }
        L25:
            java.lang.IllegalStateException r8 = new java.lang.IllegalStateException
            java.lang.String r9 = "call to 'resume' before 'invoke' with coroutine"
            r8.<init>(r9)
            throw r8
        L2d:
            java.lang.Object r8 = r9.L$1
            androidx.compose.ui.text.font.Font r8 = (androidx.compose.ui.text.font.Font) r8
            java.lang.Object r1 = r9.L$0
            androidx.compose.ui.text.font.AndroidFontLoader r1 = (androidx.compose.ui.text.font.AndroidFontLoader) r1
            kotlin.ResultKt.throwOnFailure(r0)
            r3 = r0
            goto L77
        L3a:
            kotlin.ResultKt.throwOnFailure(r0)
            r8 = r0
            goto L5e
        L3f:
            kotlin.ResultKt.throwOnFailure(r0)
            r2 = r7
            boolean r3 = r8 instanceof androidx.compose.ui.text.font.AndroidFont
            if (r3 == 0) goto L5f
            r3 = r8
            androidx.compose.ui.text.font.AndroidFont r3 = (androidx.compose.ui.text.font.AndroidFont) r3
            androidx.compose.ui.text.font.AndroidFont$TypefaceLoader r3 = r3.getTypefaceLoader()
            android.content.Context r4 = r2.context
            r5 = r8
            androidx.compose.ui.text.font.AndroidFont r5 = (androidx.compose.ui.text.font.AndroidFont) r5
            r6 = 1
            r9.label = r6
            java.lang.Object r8 = r3.awaitLoad(r4, r5, r9)
            if (r8 != r1) goto L5e
            return r1
        L5e:
            return r8
        L5f:
            boolean r3 = r8 instanceof androidx.compose.ui.text.font.ResourceFont
            if (r3 == 0) goto L87
            r3 = r8
            androidx.compose.ui.text.font.ResourceFont r3 = (androidx.compose.ui.text.font.ResourceFont) r3
            android.content.Context r4 = r2.context
            r9.L$0 = r2
            r9.L$1 = r8
            r5 = 2
            r9.label = r5
            java.lang.Object r3 = androidx.compose.ui.text.font.AndroidFontLoader_androidKt.access$loadAsync(r3, r4, r9)
            if (r3 != r1) goto L76
            return r1
        L76:
            r1 = r2
        L77:
            android.graphics.Typeface r3 = (android.graphics.Typeface) r3
            r2 = r8
            androidx.compose.ui.text.font.ResourceFont r2 = (androidx.compose.ui.text.font.ResourceFont) r2
            androidx.compose.ui.text.font.FontVariation$Settings r2 = r2.getVariationSettings()
            android.content.Context r4 = r1.context
            android.graphics.Typeface r2 = androidx.compose.ui.text.font.PlatformTypefaces_androidKt.setFontVariationSettings(r3, r2, r4)
            return r2
        L87:
            java.lang.IllegalArgumentException r1 = new java.lang.IllegalArgumentException
            java.lang.StringBuilder r3 = new java.lang.StringBuilder
            r3.<init>()
            java.lang.String r4 = "Unknown font type: "
            java.lang.StringBuilder r3 = r3.append(r4)
            java.lang.StringBuilder r3 = r3.append(r8)
            java.lang.String r3 = r3.toString()
            r1.<init>(r3)
            throw r1
        */
        throw new UnsupportedOperationException("Method not decompiled: androidx.compose.ui.text.font.AndroidFontLoader.awaitLoad(androidx.compose.ui.text.font.Font, kotlin.coroutines.Continuation):java.lang.Object");
    }

    @Override // androidx.compose.ui.text.font.PlatformFontLoader
    public Object getCacheKey() {
        return this.cacheKey;
    }
}
