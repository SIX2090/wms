package androidx.compose.ui.layout;

import androidx.compose.ui.geometry.Size;
import androidx.compose.ui.geometry.SizeKt;
import androidx.compose.ui.util.MathHelpersKt;
import kotlin.Metadata;
import kotlin.jvm.functions.Function0;

/* compiled from: ScaleFactor.kt */
@Metadata(d1 = {"\u0000&\n\u0000\n\u0002\u0010\u000b\n\u0002\u0018\u0002\n\u0002\b\t\n\u0002\u0010\u0007\n\u0002\b\t\n\u0002\u0018\u0002\n\u0002\b\u0006\n\u0002\u0018\u0002\n\u0002\b\u0007\u001a\u001d\u0010\n\u001a\u00020\u00022\u0006\u0010\u000b\u001a\u00020\f2\u0006\u0010\r\u001a\u00020\fH\u0007¢\u0006\u0002\u0010\u000e\u001a*\u0010\u000f\u001a\u00020\u00022\u0006\u0010\u0010\u001a\u00020\u00022\u0006\u0010\u0011\u001a\u00020\u00022\u0006\u0010\u0012\u001a\u00020\fH\u0007ø\u0001\u0000¢\u0006\u0004\b\u0013\u0010\u0014\u001a\u001f\u0010\u0015\u001a\u00020\u0016*\u00020\u00162\u0006\u0010\u0017\u001a\u00020\u0002H\u0087\u0002ø\u0001\u0000¢\u0006\u0004\b\u0018\u0010\u0019\u001a\f\u0010\u001a\u001a\u00020\f*\u00020\fH\u0002\u001a%\u0010\u001b\u001a\u00020\u0002*\u00020\u00022\f\u0010\u001c\u001a\b\u0012\u0004\u0012\u00020\u00020\u001dH\u0086\bø\u0001\u0000¢\u0006\u0004\b\u001e\u0010\u001f\u001a\u001f\u0010 \u001a\u00020\u0016*\u00020\u00162\u0006\u0010\u0017\u001a\u00020\u0002H\u0087\u0002ø\u0001\u0000¢\u0006\u0004\b!\u0010\u0019\u001a\u001f\u0010 \u001a\u00020\u0016*\u00020\u00022\u0006\u0010\"\u001a\u00020\u0016H\u0087\u0002ø\u0001\u0000¢\u0006\u0004\b#\u0010\u0019\"\u001f\u0010\u0000\u001a\u00020\u0001*\u00020\u00028Æ\u0002X\u0087\u0004¢\u0006\f\u0012\u0004\b\u0003\u0010\u0004\u001a\u0004\b\u0005\u0010\u0006\"\u001f\u0010\u0007\u001a\u00020\u0001*\u00020\u00028Æ\u0002X\u0087\u0004¢\u0006\f\u0012\u0004\b\b\u0010\u0004\u001a\u0004\b\t\u0010\u0006\u0082\u0002\u0007\n\u0005\b¡\u001e0\u0001¨\u0006$"}, d2 = {"isSpecified", "", "Landroidx/compose/ui/layout/ScaleFactor;", "isSpecified-FK8aYYs$annotations", "(J)V", "isSpecified-FK8aYYs", "(J)Z", "isUnspecified", "isUnspecified-FK8aYYs$annotations", "isUnspecified-FK8aYYs", "ScaleFactor", "scaleX", "", "scaleY", "(FF)J", "lerp", "start", "stop", "fraction", "lerp--bDIf60", "(JJF)J", "div", "Landroidx/compose/ui/geometry/Size;", "scaleFactor", "div-UQTWf7w", "(JJ)J", "roundToTenths", "takeOrElse", "block", "Lkotlin/Function0;", "takeOrElse-oyDd2qo", "(JLkotlin/jvm/functions/Function0;)J", "times", "times-UQTWf7w", "size", "times-m-w2e94", "ui_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes11.dex */
public final class ScaleFactorKt {
    /* renamed from: isSpecified-FK8aYYs$annotations, reason: not valid java name */
    public static /* synthetic */ void m5096isSpecifiedFK8aYYs$annotations(long j) {
    }

    /* renamed from: isUnspecified-FK8aYYs$annotations, reason: not valid java name */
    public static /* synthetic */ void m5098isUnspecifiedFK8aYYs$annotations(long j) {
    }

    public static final long ScaleFactor(float scaleX, float scaleY) {
        long v1$iv = Float.floatToRawIntBits(scaleX);
        long v2$iv = Float.floatToRawIntBits(scaleY);
        return ScaleFactor.m5080constructorimpl((v1$iv << 32) | (4294967295L & v2$iv));
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final float roundToTenths(float $this$roundToTenths) {
        int roundedShifted;
        float f = 10;
        float shifted = $this$roundToTenths * f;
        float decimal = shifted - ((int) shifted);
        if (decimal >= 0.5f) {
            roundedShifted = ((int) shifted) + 1;
        } else {
            roundedShifted = (int) shifted;
        }
        return roundedShifted / f;
    }

    /* renamed from: isSpecified-FK8aYYs, reason: not valid java name */
    public static final boolean m5095isSpecifiedFK8aYYs(long $this$isSpecified) {
        return $this$isSpecified != ScaleFactor.Companion.m5093getUnspecified_hLwfpc();
    }

    /* renamed from: isUnspecified-FK8aYYs, reason: not valid java name */
    public static final boolean m5097isUnspecifiedFK8aYYs(long $this$isUnspecified) {
        return $this$isUnspecified == ScaleFactor.Companion.m5093getUnspecified_hLwfpc();
    }

    /* renamed from: takeOrElse-oyDd2qo, reason: not valid java name */
    public static final long m5100takeOrElseoyDd2qo(long $this$takeOrElse_u2doyDd2qo, Function0<ScaleFactor> function0) {
        return ($this$takeOrElse_u2doyDd2qo > ScaleFactor.Companion.m5093getUnspecified_hLwfpc() ? 1 : ($this$takeOrElse_u2doyDd2qo == ScaleFactor.Companion.m5093getUnspecified_hLwfpc() ? 0 : -1)) != 0 ? $this$takeOrElse_u2doyDd2qo : function0.invoke().m5091unboximpl();
    }

    /* renamed from: times-UQTWf7w, reason: not valid java name */
    public static final long m5101timesUQTWf7w(long $this$times_u2dUQTWf7w, long scaleFactor) {
        return SizeKt.Size(Size.m3574getWidthimpl($this$times_u2dUQTWf7w) * ScaleFactor.m5086getScaleXimpl(scaleFactor), Size.m3571getHeightimpl($this$times_u2dUQTWf7w) * ScaleFactor.m5087getScaleYimpl(scaleFactor));
    }

    /* renamed from: times-m-w2e94, reason: not valid java name */
    public static final long m5102timesmw2e94(long $this$times_u2dm_u2dw2e94, long size) {
        return m5101timesUQTWf7w(size, $this$times_u2dm_u2dw2e94);
    }

    /* renamed from: div-UQTWf7w, reason: not valid java name */
    public static final long m5094divUQTWf7w(long $this$div_u2dUQTWf7w, long scaleFactor) {
        return SizeKt.Size(Size.m3574getWidthimpl($this$div_u2dUQTWf7w) / ScaleFactor.m5086getScaleXimpl(scaleFactor), Size.m3571getHeightimpl($this$div_u2dUQTWf7w) / ScaleFactor.m5087getScaleYimpl(scaleFactor));
    }

    /* renamed from: lerp--bDIf60, reason: not valid java name */
    public static final long m5099lerpbDIf60(long start, long stop, float fraction) {
        return ScaleFactor(MathHelpersKt.lerp(ScaleFactor.m5086getScaleXimpl(start), ScaleFactor.m5086getScaleXimpl(stop), fraction), MathHelpersKt.lerp(ScaleFactor.m5087getScaleYimpl(start), ScaleFactor.m5087getScaleYimpl(stop), fraction));
    }
}
