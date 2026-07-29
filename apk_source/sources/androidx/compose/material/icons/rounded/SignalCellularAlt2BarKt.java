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

/* compiled from: SignalCellularAlt2Bar.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_signalCellularAlt2Bar", "Landroidx/compose/ui/graphics/vector/ImageVector;", "SignalCellularAlt2Bar", "Landroidx/compose/material/icons/Icons$Rounded;", "getSignalCellularAlt2Bar", "(Landroidx/compose/material/icons/Icons$Rounded;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class SignalCellularAlt2BarKt {
    private static ImageVector _signalCellularAlt2Bar;

    public static final ImageVector getSignalCellularAlt2Bar(Icons.Rounded $this$SignalCellularAlt2Bar) {
        if (_signalCellularAlt2Bar != null) {
            ImageVector imageVector = _signalCellularAlt2Bar;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_SignalCellularAlt2Bar__u24lambda_u241 = new ImageVector.Builder("Rounded.SignalCellularAlt2Bar", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(6.5f, 20.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(5.67f, 20.0f, 5.0f, 19.33f, 5.0f, 18.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(-3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(5.0f, 14.67f, 5.67f, 14.0f, 6.5f, 14.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveTo(8.0f, 14.67f, 8.0f, 15.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(8.0f, 19.33f, 7.33f, 20.0f, 6.5f, 20.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(12.5f, 20.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.83f, 0.0f, -1.5f, -0.67f, -1.5f, -1.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(-8.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(11.0f, 9.67f, 11.67f, 9.0f, 12.5f, 9.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveTo(14.0f, 9.67f, 14.0f, 10.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(8.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(14.0f, 19.33f, 13.33f, 20.0f, 12.5f, 20.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _signalCellularAlt2Bar = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_SignalCellularAlt2Bar__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _signalCellularAlt2Bar;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
