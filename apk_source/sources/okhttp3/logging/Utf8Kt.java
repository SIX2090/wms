package okhttp3.logging;

import java.io.EOFException;
import kotlin.Metadata;
import kotlin.jvm.internal.Intrinsics;
import kotlin.ranges.RangesKt;
import okio.Buffer;

/* compiled from: utf8.kt */
@Metadata(d1 = {"\u0000\f\n\u0000\n\u0002\u0010\u000b\n\u0002\u0018\u0002\n\u0000\u001a\f\u0010\u0000\u001a\u00020\u0001*\u00020\u0002H\u0000¨\u0006\u0003"}, d2 = {"isProbablyUtf8", "", "Lokio/Buffer;", "okhttp-logging-interceptor"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes11.dex */
public final class Utf8Kt {
    public static final boolean isProbablyUtf8(Buffer $this$isProbablyUtf8) {
        Intrinsics.checkNotNullParameter($this$isProbablyUtf8, "<this>");
        try {
            Buffer prefix = new Buffer();
            long byteCount = RangesKt.coerceAtMost($this$isProbablyUtf8.size(), 64L);
            $this$isProbablyUtf8.copyTo(prefix, 0L, byteCount);
            for (int i = 0; i < 16; i++) {
                if (!prefix.exhausted()) {
                    int codePoint = prefix.readUtf8CodePoint();
                    if (Character.isISOControl(codePoint) && !Character.isWhitespace(codePoint)) {
                        return false;
                    }
                } else {
                    return true;
                }
            }
            return true;
        } catch (EOFException e) {
            return false;
        }
    }
}
