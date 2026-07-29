package androidx.compose.material.icons.filled;

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

/* compiled from: SignalWifiOff.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_signalWifiOff", "Landroidx/compose/ui/graphics/vector/ImageVector;", "SignalWifiOff", "Landroidx/compose/material/icons/Icons$Filled;", "getSignalWifiOff", "(Landroidx/compose/material/icons/Icons$Filled;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class SignalWifiOffKt {
    private static ImageVector _signalWifiOff;

    public static final ImageVector getSignalWifiOff(Icons.Filled $this$SignalWifiOff) {
        if (_signalWifiOff != null) {
            ImageVector imageVector = _signalWifiOff;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_SignalWifiOff__u24lambda_u241 = new ImageVector.Builder("Filled.SignalWifiOff", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(23.64f, 7.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.45f, -0.34f, -4.93f, -4.0f, -11.64f, -4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-1.5f, 0.0f, -2.89f, 0.19f, -4.15f, 0.48f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(18.18f, 13.8f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(23.64f, 7.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(17.04f, 15.22f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(3.27f, 1.44f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(2.0f, 2.72f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(2.05f, 2.06f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(1.91f, 5.76f, 0.59f, 6.82f, 0.36f, 7.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(11.63f, 14.49f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(0.01f, 0.01f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(0.01f, -0.01f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(3.9f, -4.86f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(3.32f, 3.32f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.27f, -1.27f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-3.46f, -3.46f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _signalWifiOff = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_SignalWifiOff__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _signalWifiOff;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
