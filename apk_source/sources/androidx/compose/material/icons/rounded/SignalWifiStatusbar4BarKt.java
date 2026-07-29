package androidx.compose.material.icons.rounded;

import androidx.compose.material.icons.Icons;
import androidx.compose.ui.graphics.Brush;
import androidx.compose.ui.graphics.Color;
import androidx.compose.ui.graphics.SolidColor;
import androidx.compose.ui.graphics.StrokeCap;
import androidx.compose.ui.graphics.StrokeJoin;
import androidx.compose.ui.graphics.vector.ImageVector;
import androidx.compose.ui.graphics.vector.PathBuilder;
import androidx.compose.ui.graphics.vector.VectorKt;
import androidx.compose.ui.unit.Dp;
import kotlin.Metadata;
import kotlin.jvm.internal.Intrinsics;

/* compiled from: SignalWifiStatusbar4Bar.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_signalWifiStatusbar4Bar", "Landroidx/compose/ui/graphics/vector/ImageVector;", "SignalWifiStatusbar4Bar", "Landroidx/compose/material/icons/Icons$Rounded;", "getSignalWifiStatusbar4Bar", "(Landroidx/compose/material/icons/Icons$Rounded;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class SignalWifiStatusbar4BarKt {
    private static ImageVector _signalWifiStatusbar4Bar;

    public static final ImageVector getSignalWifiStatusbar4Bar(Icons.Rounded $this$SignalWifiStatusbar4Bar) {
        if (_signalWifiStatusbar4Bar != null) {
            ImageVector imageVector = _signalWifiStatusbar4Bar;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_SignalWifiStatusbar4Bar__u24lambda_u241 = new ImageVector.Builder("Rounded.SignalWifiStatusbar4Bar", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(12.0f, 4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(7.7f, 4.0f, 3.78f, 5.6f, 0.79f, 8.24f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(0.35f, 8.63f, 0.32f, 9.3f, 0.73f, 9.71f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(10.56f, 10.58f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.39f, 0.39f, 1.02f, 0.39f, 1.42f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(23.27f, 9.71f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.41f, -0.41f, 0.38f, -1.08f, -0.06f, -1.47f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(20.22f, 5.6f, 16.3f, 4.0f, 12.0f, 4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _signalWifiStatusbar4Bar = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_SignalWifiStatusbar4Bar__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _signalWifiStatusbar4Bar;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
