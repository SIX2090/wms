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

/* compiled from: BatteryStd.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_batteryStd", "Landroidx/compose/ui/graphics/vector/ImageVector;", "BatteryStd", "Landroidx/compose/material/icons/Icons$Rounded;", "getBatteryStd", "(Landroidx/compose/material/icons/Icons$Rounded;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class BatteryStdKt {
    private static ImageVector _batteryStd;

    public static final ImageVector getBatteryStd(Icons.Rounded $this$BatteryStd) {
        if (_batteryStd != null) {
            ImageVector imageVector = _batteryStd;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_BatteryStd__u24lambda_u241 = new ImageVector.Builder("Rounded.BatteryStd", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(15.67f, 4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineTo(14.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, -0.55f, -0.45f, -1.0f, -1.0f, -1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(-2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.55f, 0.0f, -1.0f, 0.45f, -1.0f, 1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineTo(8.33f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(7.6f, 4.0f, 7.0f, 4.6f, 7.0f, 5.33f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(15.33f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(7.0f, 21.4f, 7.6f, 22.0f, 8.34f, 22.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(7.32f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.74f, 0.0f, 1.34f, -0.6f, 1.34f, -1.33f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(5.33f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(17.0f, 4.6f, 16.4f, 4.0f, 15.67f, 4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _batteryStd = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_BatteryStd__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _batteryStd;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
