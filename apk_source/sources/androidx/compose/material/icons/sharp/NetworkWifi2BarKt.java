package androidx.compose.material.icons.sharp;

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

/* compiled from: NetworkWifi2Bar.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_networkWifi2Bar", "Landroidx/compose/ui/graphics/vector/ImageVector;", "NetworkWifi2Bar", "Landroidx/compose/material/icons/Icons$Sharp;", "getNetworkWifi2Bar", "(Landroidx/compose/material/icons/Icons$Sharp;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class NetworkWifi2BarKt {
    private static ImageVector _networkWifi2Bar;

    public static final ImageVector getNetworkWifi2Bar(Icons.Sharp $this$NetworkWifi2Bar) {
        if (_networkWifi2Bar != null) {
            ImageVector imageVector = _networkWifi2Bar;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_NetworkWifi2Bar__u24lambda_u241 = new ImageVector.Builder("Sharp.NetworkWifi2Bar", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(12.0f, 4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(7.31f, 4.0f, 3.07f, 5.9f, 0.0f, 8.98f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(12.0f, 21.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(24.0f, 8.98f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(20.93f, 5.9f, 16.69f, 4.0f, 12.0f, 4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(16.78f, 13.38f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(15.4f, 12.5f, 13.76f, 12.0f, 12.0f, 12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-1.76f, 0.0f, -3.4f, 0.5f, -4.78f, 1.38f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-4.3f, -4.3f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(5.51f, 7.08f, 8.67f, 6.0f, 12.0f, 6.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveToRelative(6.49f, 1.08f, 9.08f, 3.07f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(16.78f, 13.38f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _networkWifi2Bar = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_NetworkWifi2Bar__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _networkWifi2Bar;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
