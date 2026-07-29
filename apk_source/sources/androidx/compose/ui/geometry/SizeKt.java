package androidx.compose.ui.geometry;

import androidx.compose.ui.util.MathHelpersKt;
import kotlin.Metadata;
import kotlin.jvm.functions.Function0;

/* compiled from: Size.kt */
@Metadata(d1 = {"\u0000>\n\u0000\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\b\u0005\n\u0002\u0010\u000b\n\u0002\b\b\n\u0002\u0010\u0007\n\u0002\b\n\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0010\u0006\n\u0002\b\u0004\n\u0002\u0010\b\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\b\u0003\u001a\u001d\u0010\u000f\u001a\u00020\u00022\u0006\u0010\u0010\u001a\u00020\u00112\u0006\u0010\u0012\u001a\u00020\u0011H\u0007¢\u0006\u0002\u0010\u0013\u001a*\u0010\u0014\u001a\u00020\u00022\u0006\u0010\u0015\u001a\u00020\u00022\u0006\u0010\u0016\u001a\u00020\u00022\u0006\u0010\u0017\u001a\u00020\u0011H\u0007ø\u0001\u0000¢\u0006\u0004\b\u0018\u0010\u0019\u001a%\u0010\u001a\u001a\u00020\u0002*\u00020\u00022\f\u0010\u001b\u001a\b\u0012\u0004\u0012\u00020\u00020\u001cH\u0086\bø\u0001\u0000¢\u0006\u0004\b\u001d\u0010\u001e\u001a\u001f\u0010\u001f\u001a\u00020\u0002*\u00020 2\u0006\u0010!\u001a\u00020\u0002H\u0087\nø\u0001\u0000¢\u0006\u0004\b\"\u0010#\u001a\u001f\u0010\u001f\u001a\u00020\u0002*\u00020\u00112\u0006\u0010!\u001a\u00020\u0002H\u0087\nø\u0001\u0000¢\u0006\u0004\b\"\u0010$\u001a\u001f\u0010\u001f\u001a\u00020\u0002*\u00020%2\u0006\u0010!\u001a\u00020\u0002H\u0087\nø\u0001\u0000¢\u0006\u0004\b\"\u0010&\u001a\u0016\u0010'\u001a\u00020(*\u00020\u0002H\u0007ø\u0001\u0000¢\u0006\u0004\b)\u0010*\"\u001e\u0010\u0000\u001a\u00020\u0001*\u00020\u00028FX\u0087\u0004¢\u0006\f\u0012\u0004\b\u0003\u0010\u0004\u001a\u0004\b\u0005\u0010\u0006\"\u001f\u0010\u0007\u001a\u00020\b*\u00020\u00028Æ\u0002X\u0087\u0004¢\u0006\f\u0012\u0004\b\t\u0010\u0004\u001a\u0004\b\n\u0010\u000b\"\u001f\u0010\f\u001a\u00020\b*\u00020\u00028Æ\u0002X\u0087\u0004¢\u0006\f\u0012\u0004\b\r\u0010\u0004\u001a\u0004\b\u000e\u0010\u000b\u0082\u0002\u0007\n\u0005\b¡\u001e0\u0001¨\u0006+"}, d2 = {"center", "Landroidx/compose/ui/geometry/Offset;", "Landroidx/compose/ui/geometry/Size;", "getCenter-uvyYCjk$annotations", "(J)V", "getCenter-uvyYCjk", "(J)J", "isSpecified", "", "isSpecified-uvyYCjk$annotations", "isSpecified-uvyYCjk", "(J)Z", "isUnspecified", "isUnspecified-uvyYCjk$annotations", "isUnspecified-uvyYCjk", "Size", "width", "", "height", "(FF)J", "lerp", "start", "stop", "fraction", "lerp-VgWVRYQ", "(JJF)J", "takeOrElse", "block", "Lkotlin/Function0;", "takeOrElse-TmRCtEA", "(JLkotlin/jvm/functions/Function0;)J", "times", "", "size", "times-d16Qtg0", "(DJ)J", "(FJ)J", "", "(IJ)J", "toRect", "Landroidx/compose/ui/geometry/Rect;", "toRect-uvyYCjk", "(J)Landroidx/compose/ui/geometry/Rect;", "ui-geometry_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class SizeKt {
    /* renamed from: getCenter-uvyYCjk$annotations, reason: not valid java name */
    public static /* synthetic */ void m3585getCenteruvyYCjk$annotations(long j) {
    }

    /* renamed from: isSpecified-uvyYCjk$annotations, reason: not valid java name */
    public static /* synthetic */ void m3587isSpecifieduvyYCjk$annotations(long j) {
    }

    /* renamed from: isUnspecified-uvyYCjk$annotations, reason: not valid java name */
    public static /* synthetic */ void m3589isUnspecifieduvyYCjk$annotations(long j) {
    }

    public static final long Size(float width, float height) {
        long v1$iv = Float.floatToRawIntBits(width);
        long v2$iv = Float.floatToRawIntBits(height);
        return Size.m3565constructorimpl((v1$iv << 32) | (4294967295L & v2$iv));
    }

    /* renamed from: isSpecified-uvyYCjk, reason: not valid java name */
    public static final boolean m3586isSpecifieduvyYCjk(long $this$isSpecified) {
        return $this$isSpecified != Size.INSTANCE.m3582getUnspecifiedNHjbRc();
    }

    /* renamed from: isUnspecified-uvyYCjk, reason: not valid java name */
    public static final boolean m3588isUnspecifieduvyYCjk(long $this$isUnspecified) {
        return $this$isUnspecified == Size.INSTANCE.m3582getUnspecifiedNHjbRc();
    }

    /* renamed from: takeOrElse-TmRCtEA, reason: not valid java name */
    public static final long m3591takeOrElseTmRCtEA(long $this$takeOrElse_u2dTmRCtEA, Function0<Size> function0) {
        return ($this$takeOrElse_u2dTmRCtEA > Size.INSTANCE.m3582getUnspecifiedNHjbRc() ? 1 : ($this$takeOrElse_u2dTmRCtEA == Size.INSTANCE.m3582getUnspecifiedNHjbRc() ? 0 : -1)) != 0 ? $this$takeOrElse_u2dTmRCtEA : function0.invoke().getPackedValue();
    }

    /* renamed from: lerp-VgWVRYQ, reason: not valid java name */
    public static final long m3590lerpVgWVRYQ(long start, long stop, float fraction) {
        return Size(MathHelpersKt.lerp(Size.m3574getWidthimpl(start), Size.m3574getWidthimpl(stop), fraction), MathHelpersKt.lerp(Size.m3571getHeightimpl(start), Size.m3571getHeightimpl(stop), fraction));
    }

    /* renamed from: times-d16Qtg0, reason: not valid java name */
    public static final long m3594timesd16Qtg0(int $this$times_u2dd16Qtg0, long size) {
        return Size.m3577times7Ah8Wj8(size, $this$times_u2dd16Qtg0);
    }

    /* renamed from: times-d16Qtg0, reason: not valid java name */
    public static final long m3592timesd16Qtg0(double $this$times_u2dd16Qtg0, long size) {
        return Size.m3577times7Ah8Wj8(size, (float) $this$times_u2dd16Qtg0);
    }

    /* renamed from: toRect-uvyYCjk, reason: not valid java name */
    public static final Rect m3595toRectuvyYCjk(long $this$toRect_u2duvyYCjk) {
        return RectKt.m3545Recttz77jQw(Offset.INSTANCE.m3521getZeroF1C5BW0(), $this$toRect_u2duvyYCjk);
    }

    /* renamed from: times-d16Qtg0, reason: not valid java name */
    public static final long m3593timesd16Qtg0(float $this$times_u2dd16Qtg0, long size) {
        return Size.m3577times7Ah8Wj8(size, $this$times_u2dd16Qtg0);
    }

    /* renamed from: getCenter-uvyYCjk, reason: not valid java name */
    public static final long m3584getCenteruvyYCjk(long $this$center) {
        return OffsetKt.Offset(Size.m3574getWidthimpl($this$center) / 2.0f, Size.m3571getHeightimpl($this$center) / 2.0f);
    }
}
