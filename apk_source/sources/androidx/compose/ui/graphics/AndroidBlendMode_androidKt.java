package androidx.compose.ui.graphics;

import android.graphics.PorterDuff;
import android.os.Build;
import androidx.core.view.MotionEventCompat;
import kotlin.Metadata;

/* compiled from: AndroidBlendMode.android.kt */
@Metadata(d1 = {"\u0000\u001e\n\u0000\n\u0002\u0010\u000b\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0018\u0002\n\u0002\b\u0005\n\u0002\u0018\u0002\n\u0002\b\u0003\u001a\u0014\u0010\u0000\u001a\u00020\u0001*\u00020\u0002ø\u0001\u0000¢\u0006\u0004\b\u0003\u0010\u0004\u001a\u0016\u0010\u0005\u001a\u00020\u0006*\u00020\u0002H\u0001ø\u0001\u0000¢\u0006\u0004\b\u0007\u0010\b\u001a\u0011\u0010\t\u001a\u00020\u0002*\u00020\u0006H\u0001¢\u0006\u0002\u0010\n\u001a\u0016\u0010\u000b\u001a\u00020\f*\u00020\u0002H\u0000ø\u0001\u0000¢\u0006\u0004\b\r\u0010\u000e\u0082\u0002\u0007\n\u0005\b¡\u001e0\u0001¨\u0006\u000f"}, d2 = {"isSupported", "", "Landroidx/compose/ui/graphics/BlendMode;", "isSupported-s9anfk8", "(I)Z", "toAndroidBlendMode", "Landroid/graphics/BlendMode;", "toAndroidBlendMode-s9anfk8", "(I)Landroid/graphics/BlendMode;", "toComposeBlendMode", "(Landroid/graphics/BlendMode;)I", "toPorterDuffMode", "Landroid/graphics/PorterDuff$Mode;", "toPorterDuffMode-s9anfk8", "(I)Landroid/graphics/PorterDuff$Mode;", "ui-graphics_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes11.dex */
public final class AndroidBlendMode_androidKt {

    /* compiled from: AndroidBlendMode.android.kt */
    @Metadata(k = 3, mv = {1, 8, 0}, xi = 48)
    public /* synthetic */ class WhenMappings {
        public static final /* synthetic */ int[] $EnumSwitchMapping$0;

        static {
            int[] iArr = new int[android.graphics.BlendMode.values().length];
            try {
                iArr[android.graphics.BlendMode.CLEAR.ordinal()] = 1;
            } catch (NoSuchFieldError e) {
            }
            try {
                iArr[android.graphics.BlendMode.SRC.ordinal()] = 2;
            } catch (NoSuchFieldError e2) {
            }
            try {
                iArr[android.graphics.BlendMode.DST.ordinal()] = 3;
            } catch (NoSuchFieldError e3) {
            }
            try {
                iArr[android.graphics.BlendMode.SRC_OVER.ordinal()] = 4;
            } catch (NoSuchFieldError e4) {
            }
            try {
                iArr[android.graphics.BlendMode.DST_OVER.ordinal()] = 5;
            } catch (NoSuchFieldError e5) {
            }
            try {
                iArr[android.graphics.BlendMode.SRC_IN.ordinal()] = 6;
            } catch (NoSuchFieldError e6) {
            }
            try {
                iArr[android.graphics.BlendMode.DST_IN.ordinal()] = 7;
            } catch (NoSuchFieldError e7) {
            }
            try {
                iArr[android.graphics.BlendMode.SRC_OUT.ordinal()] = 8;
            } catch (NoSuchFieldError e8) {
            }
            try {
                iArr[android.graphics.BlendMode.DST_OUT.ordinal()] = 9;
            } catch (NoSuchFieldError e9) {
            }
            try {
                iArr[android.graphics.BlendMode.SRC_ATOP.ordinal()] = 10;
            } catch (NoSuchFieldError e10) {
            }
            try {
                iArr[android.graphics.BlendMode.DST_ATOP.ordinal()] = 11;
            } catch (NoSuchFieldError e11) {
            }
            try {
                iArr[android.graphics.BlendMode.XOR.ordinal()] = 12;
            } catch (NoSuchFieldError e12) {
            }
            try {
                iArr[android.graphics.BlendMode.PLUS.ordinal()] = 13;
            } catch (NoSuchFieldError e13) {
            }
            try {
                iArr[android.graphics.BlendMode.MODULATE.ordinal()] = 14;
            } catch (NoSuchFieldError e14) {
            }
            try {
                iArr[android.graphics.BlendMode.SCREEN.ordinal()] = 15;
            } catch (NoSuchFieldError e15) {
            }
            try {
                iArr[android.graphics.BlendMode.OVERLAY.ordinal()] = 16;
            } catch (NoSuchFieldError e16) {
            }
            try {
                iArr[android.graphics.BlendMode.DARKEN.ordinal()] = 17;
            } catch (NoSuchFieldError e17) {
            }
            try {
                iArr[android.graphics.BlendMode.LIGHTEN.ordinal()] = 18;
            } catch (NoSuchFieldError e18) {
            }
            try {
                iArr[android.graphics.BlendMode.COLOR_DODGE.ordinal()] = 19;
            } catch (NoSuchFieldError e19) {
            }
            try {
                iArr[android.graphics.BlendMode.COLOR_BURN.ordinal()] = 20;
            } catch (NoSuchFieldError e20) {
            }
            try {
                iArr[android.graphics.BlendMode.HARD_LIGHT.ordinal()] = 21;
            } catch (NoSuchFieldError e21) {
            }
            try {
                iArr[android.graphics.BlendMode.SOFT_LIGHT.ordinal()] = 22;
            } catch (NoSuchFieldError e22) {
            }
            try {
                iArr[android.graphics.BlendMode.DIFFERENCE.ordinal()] = 23;
            } catch (NoSuchFieldError e23) {
            }
            try {
                iArr[android.graphics.BlendMode.EXCLUSION.ordinal()] = 24;
            } catch (NoSuchFieldError e24) {
            }
            try {
                iArr[android.graphics.BlendMode.MULTIPLY.ordinal()] = 25;
            } catch (NoSuchFieldError e25) {
            }
            try {
                iArr[android.graphics.BlendMode.HUE.ordinal()] = 26;
            } catch (NoSuchFieldError e26) {
            }
            try {
                iArr[android.graphics.BlendMode.SATURATION.ordinal()] = 27;
            } catch (NoSuchFieldError e27) {
            }
            try {
                iArr[android.graphics.BlendMode.COLOR.ordinal()] = 28;
            } catch (NoSuchFieldError e28) {
            }
            try {
                iArr[android.graphics.BlendMode.LUMINOSITY.ordinal()] = 29;
            } catch (NoSuchFieldError e29) {
            }
            $EnumSwitchMapping$0 = iArr;
        }
    }

    /* renamed from: isSupported-s9anfk8, reason: not valid java name */
    public static final boolean m3596isSupporteds9anfk8(int $this$isSupported_u2ds9anfk8) {
        return Build.VERSION.SDK_INT >= 29 || BlendMode.m3657equalsimpl0($this$isSupported_u2ds9anfk8, BlendMode.INSTANCE.m3688getSrcOver0nO6VwU()) || m3598toPorterDuffModes9anfk8($this$isSupported_u2ds9anfk8) != PorterDuff.Mode.SRC_OVER;
    }

    /* renamed from: toPorterDuffMode-s9anfk8, reason: not valid java name */
    public static final PorterDuff.Mode m3598toPorterDuffModes9anfk8(int $this$toPorterDuffMode_u2ds9anfk8) {
        if (BlendMode.m3657equalsimpl0($this$toPorterDuffMode_u2ds9anfk8, BlendMode.INSTANCE.m3661getClear0nO6VwU())) {
            return PorterDuff.Mode.CLEAR;
        }
        if (BlendMode.m3657equalsimpl0($this$toPorterDuffMode_u2ds9anfk8, BlendMode.INSTANCE.m3684getSrc0nO6VwU())) {
            return PorterDuff.Mode.SRC;
        }
        if (BlendMode.m3657equalsimpl0($this$toPorterDuffMode_u2ds9anfk8, BlendMode.INSTANCE.m3667getDst0nO6VwU())) {
            return PorterDuff.Mode.DST;
        }
        if (BlendMode.m3657equalsimpl0($this$toPorterDuffMode_u2ds9anfk8, BlendMode.INSTANCE.m3688getSrcOver0nO6VwU())) {
            return PorterDuff.Mode.SRC_OVER;
        }
        if (BlendMode.m3657equalsimpl0($this$toPorterDuffMode_u2ds9anfk8, BlendMode.INSTANCE.m3671getDstOver0nO6VwU())) {
            return PorterDuff.Mode.DST_OVER;
        }
        if (BlendMode.m3657equalsimpl0($this$toPorterDuffMode_u2ds9anfk8, BlendMode.INSTANCE.m3686getSrcIn0nO6VwU())) {
            return PorterDuff.Mode.SRC_IN;
        }
        if (BlendMode.m3657equalsimpl0($this$toPorterDuffMode_u2ds9anfk8, BlendMode.INSTANCE.m3669getDstIn0nO6VwU())) {
            return PorterDuff.Mode.DST_IN;
        }
        if (BlendMode.m3657equalsimpl0($this$toPorterDuffMode_u2ds9anfk8, BlendMode.INSTANCE.m3687getSrcOut0nO6VwU())) {
            return PorterDuff.Mode.SRC_OUT;
        }
        if (BlendMode.m3657equalsimpl0($this$toPorterDuffMode_u2ds9anfk8, BlendMode.INSTANCE.m3670getDstOut0nO6VwU())) {
            return PorterDuff.Mode.DST_OUT;
        }
        if (BlendMode.m3657equalsimpl0($this$toPorterDuffMode_u2ds9anfk8, BlendMode.INSTANCE.m3685getSrcAtop0nO6VwU())) {
            return PorterDuff.Mode.SRC_ATOP;
        }
        if (BlendMode.m3657equalsimpl0($this$toPorterDuffMode_u2ds9anfk8, BlendMode.INSTANCE.m3668getDstAtop0nO6VwU())) {
            return PorterDuff.Mode.DST_ATOP;
        }
        if (BlendMode.m3657equalsimpl0($this$toPorterDuffMode_u2ds9anfk8, BlendMode.INSTANCE.m3689getXor0nO6VwU())) {
            return PorterDuff.Mode.XOR;
        }
        if (BlendMode.m3657equalsimpl0($this$toPorterDuffMode_u2ds9anfk8, BlendMode.INSTANCE.m3680getPlus0nO6VwU())) {
            return PorterDuff.Mode.ADD;
        }
        if (BlendMode.m3657equalsimpl0($this$toPorterDuffMode_u2ds9anfk8, BlendMode.INSTANCE.m3682getScreen0nO6VwU())) {
            return PorterDuff.Mode.SCREEN;
        }
        if (BlendMode.m3657equalsimpl0($this$toPorterDuffMode_u2ds9anfk8, BlendMode.INSTANCE.m3679getOverlay0nO6VwU())) {
            return PorterDuff.Mode.OVERLAY;
        }
        if (BlendMode.m3657equalsimpl0($this$toPorterDuffMode_u2ds9anfk8, BlendMode.INSTANCE.m3665getDarken0nO6VwU())) {
            return PorterDuff.Mode.DARKEN;
        }
        if (BlendMode.m3657equalsimpl0($this$toPorterDuffMode_u2ds9anfk8, BlendMode.INSTANCE.m3675getLighten0nO6VwU())) {
            return PorterDuff.Mode.LIGHTEN;
        }
        if (BlendMode.m3657equalsimpl0($this$toPorterDuffMode_u2ds9anfk8, BlendMode.INSTANCE.m3677getModulate0nO6VwU())) {
            return PorterDuff.Mode.MULTIPLY;
        }
        return PorterDuff.Mode.SRC_OVER;
    }

    /* renamed from: toAndroidBlendMode-s9anfk8, reason: not valid java name */
    public static final android.graphics.BlendMode m3597toAndroidBlendModes9anfk8(int $this$toAndroidBlendMode_u2ds9anfk8) {
        return BlendMode.m3657equalsimpl0($this$toAndroidBlendMode_u2ds9anfk8, BlendMode.INSTANCE.m3661getClear0nO6VwU()) ? android.graphics.BlendMode.CLEAR : BlendMode.m3657equalsimpl0($this$toAndroidBlendMode_u2ds9anfk8, BlendMode.INSTANCE.m3684getSrc0nO6VwU()) ? android.graphics.BlendMode.SRC : BlendMode.m3657equalsimpl0($this$toAndroidBlendMode_u2ds9anfk8, BlendMode.INSTANCE.m3667getDst0nO6VwU()) ? android.graphics.BlendMode.DST : BlendMode.m3657equalsimpl0($this$toAndroidBlendMode_u2ds9anfk8, BlendMode.INSTANCE.m3688getSrcOver0nO6VwU()) ? android.graphics.BlendMode.SRC_OVER : BlendMode.m3657equalsimpl0($this$toAndroidBlendMode_u2ds9anfk8, BlendMode.INSTANCE.m3671getDstOver0nO6VwU()) ? android.graphics.BlendMode.DST_OVER : BlendMode.m3657equalsimpl0($this$toAndroidBlendMode_u2ds9anfk8, BlendMode.INSTANCE.m3686getSrcIn0nO6VwU()) ? android.graphics.BlendMode.SRC_IN : BlendMode.m3657equalsimpl0($this$toAndroidBlendMode_u2ds9anfk8, BlendMode.INSTANCE.m3669getDstIn0nO6VwU()) ? android.graphics.BlendMode.DST_IN : BlendMode.m3657equalsimpl0($this$toAndroidBlendMode_u2ds9anfk8, BlendMode.INSTANCE.m3687getSrcOut0nO6VwU()) ? android.graphics.BlendMode.SRC_OUT : BlendMode.m3657equalsimpl0($this$toAndroidBlendMode_u2ds9anfk8, BlendMode.INSTANCE.m3670getDstOut0nO6VwU()) ? android.graphics.BlendMode.DST_OUT : BlendMode.m3657equalsimpl0($this$toAndroidBlendMode_u2ds9anfk8, BlendMode.INSTANCE.m3685getSrcAtop0nO6VwU()) ? android.graphics.BlendMode.SRC_ATOP : BlendMode.m3657equalsimpl0($this$toAndroidBlendMode_u2ds9anfk8, BlendMode.INSTANCE.m3668getDstAtop0nO6VwU()) ? android.graphics.BlendMode.DST_ATOP : BlendMode.m3657equalsimpl0($this$toAndroidBlendMode_u2ds9anfk8, BlendMode.INSTANCE.m3689getXor0nO6VwU()) ? android.graphics.BlendMode.XOR : BlendMode.m3657equalsimpl0($this$toAndroidBlendMode_u2ds9anfk8, BlendMode.INSTANCE.m3680getPlus0nO6VwU()) ? android.graphics.BlendMode.PLUS : BlendMode.m3657equalsimpl0($this$toAndroidBlendMode_u2ds9anfk8, BlendMode.INSTANCE.m3677getModulate0nO6VwU()) ? android.graphics.BlendMode.MODULATE : BlendMode.m3657equalsimpl0($this$toAndroidBlendMode_u2ds9anfk8, BlendMode.INSTANCE.m3682getScreen0nO6VwU()) ? android.graphics.BlendMode.SCREEN : BlendMode.m3657equalsimpl0($this$toAndroidBlendMode_u2ds9anfk8, BlendMode.INSTANCE.m3679getOverlay0nO6VwU()) ? android.graphics.BlendMode.OVERLAY : BlendMode.m3657equalsimpl0($this$toAndroidBlendMode_u2ds9anfk8, BlendMode.INSTANCE.m3665getDarken0nO6VwU()) ? android.graphics.BlendMode.DARKEN : BlendMode.m3657equalsimpl0($this$toAndroidBlendMode_u2ds9anfk8, BlendMode.INSTANCE.m3675getLighten0nO6VwU()) ? android.graphics.BlendMode.LIGHTEN : BlendMode.m3657equalsimpl0($this$toAndroidBlendMode_u2ds9anfk8, BlendMode.INSTANCE.m3664getColorDodge0nO6VwU()) ? android.graphics.BlendMode.COLOR_DODGE : BlendMode.m3657equalsimpl0($this$toAndroidBlendMode_u2ds9anfk8, BlendMode.INSTANCE.m3663getColorBurn0nO6VwU()) ? android.graphics.BlendMode.COLOR_BURN : BlendMode.m3657equalsimpl0($this$toAndroidBlendMode_u2ds9anfk8, BlendMode.INSTANCE.m3673getHardlight0nO6VwU()) ? android.graphics.BlendMode.HARD_LIGHT : BlendMode.m3657equalsimpl0($this$toAndroidBlendMode_u2ds9anfk8, BlendMode.INSTANCE.m3683getSoftlight0nO6VwU()) ? android.graphics.BlendMode.SOFT_LIGHT : BlendMode.m3657equalsimpl0($this$toAndroidBlendMode_u2ds9anfk8, BlendMode.INSTANCE.m3666getDifference0nO6VwU()) ? android.graphics.BlendMode.DIFFERENCE : BlendMode.m3657equalsimpl0($this$toAndroidBlendMode_u2ds9anfk8, BlendMode.INSTANCE.m3672getExclusion0nO6VwU()) ? android.graphics.BlendMode.EXCLUSION : BlendMode.m3657equalsimpl0($this$toAndroidBlendMode_u2ds9anfk8, BlendMode.INSTANCE.m3678getMultiply0nO6VwU()) ? android.graphics.BlendMode.MULTIPLY : BlendMode.m3657equalsimpl0($this$toAndroidBlendMode_u2ds9anfk8, BlendMode.INSTANCE.m3674getHue0nO6VwU()) ? android.graphics.BlendMode.HUE : BlendMode.m3657equalsimpl0($this$toAndroidBlendMode_u2ds9anfk8, BlendMode.INSTANCE.m3681getSaturation0nO6VwU()) ? android.graphics.BlendMode.SATURATION : BlendMode.m3657equalsimpl0($this$toAndroidBlendMode_u2ds9anfk8, BlendMode.INSTANCE.m3662getColor0nO6VwU()) ? android.graphics.BlendMode.COLOR : BlendMode.m3657equalsimpl0($this$toAndroidBlendMode_u2ds9anfk8, BlendMode.INSTANCE.m3676getLuminosity0nO6VwU()) ? android.graphics.BlendMode.LUMINOSITY : android.graphics.BlendMode.SRC_OVER;
    }

    public static final int toComposeBlendMode(android.graphics.BlendMode $this$toComposeBlendMode) {
        switch (WhenMappings.$EnumSwitchMapping$0[$this$toComposeBlendMode.ordinal()]) {
            case 1:
                return BlendMode.INSTANCE.m3661getClear0nO6VwU();
            case 2:
                return BlendMode.INSTANCE.m3684getSrc0nO6VwU();
            case 3:
                return BlendMode.INSTANCE.m3667getDst0nO6VwU();
            case 4:
                return BlendMode.INSTANCE.m3688getSrcOver0nO6VwU();
            case 5:
                return BlendMode.INSTANCE.m3671getDstOver0nO6VwU();
            case 6:
                return BlendMode.INSTANCE.m3686getSrcIn0nO6VwU();
            case 7:
                return BlendMode.INSTANCE.m3669getDstIn0nO6VwU();
            case 8:
                return BlendMode.INSTANCE.m3687getSrcOut0nO6VwU();
            case 9:
                return BlendMode.INSTANCE.m3670getDstOut0nO6VwU();
            case 10:
                return BlendMode.INSTANCE.m3685getSrcAtop0nO6VwU();
            case 11:
                return BlendMode.INSTANCE.m3668getDstAtop0nO6VwU();
            case 12:
                return BlendMode.INSTANCE.m3689getXor0nO6VwU();
            case 13:
                return BlendMode.INSTANCE.m3680getPlus0nO6VwU();
            case 14:
                return BlendMode.INSTANCE.m3677getModulate0nO6VwU();
            case 15:
                return BlendMode.INSTANCE.m3682getScreen0nO6VwU();
            case 16:
                return BlendMode.INSTANCE.m3679getOverlay0nO6VwU();
            case 17:
                return BlendMode.INSTANCE.m3665getDarken0nO6VwU();
            case 18:
                return BlendMode.INSTANCE.m3675getLighten0nO6VwU();
            case 19:
                return BlendMode.INSTANCE.m3664getColorDodge0nO6VwU();
            case 20:
                return BlendMode.INSTANCE.m3663getColorBurn0nO6VwU();
            case 21:
                return BlendMode.INSTANCE.m3673getHardlight0nO6VwU();
            case 22:
                return BlendMode.INSTANCE.m3683getSoftlight0nO6VwU();
            case 23:
                return BlendMode.INSTANCE.m3666getDifference0nO6VwU();
            case 24:
                return BlendMode.INSTANCE.m3672getExclusion0nO6VwU();
            case 25:
                return BlendMode.INSTANCE.m3678getMultiply0nO6VwU();
            case 26:
                return BlendMode.INSTANCE.m3674getHue0nO6VwU();
            case 27:
                return BlendMode.INSTANCE.m3681getSaturation0nO6VwU();
            case MotionEventCompat.AXIS_RELATIVE_Y /* 28 */:
                return BlendMode.INSTANCE.m3662getColor0nO6VwU();
            case 29:
                return BlendMode.INSTANCE.m3676getLuminosity0nO6VwU();
            default:
                return BlendMode.INSTANCE.m3688getSrcOver0nO6VwU();
        }
    }
}
