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

/* compiled from: PowerOff.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_powerOff", "Landroidx/compose/ui/graphics/vector/ImageVector;", "PowerOff", "Landroidx/compose/material/icons/Icons$Filled;", "getPowerOff", "(Landroidx/compose/material/icons/Icons$Filled;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class PowerOffKt {
    private static ImageVector _powerOff;

    public static final ImageVector getPowerOff(Icons.Filled $this$PowerOff) {
        if (_powerOff != null) {
            ImageVector imageVector = _powerOff;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_PowerOff__u24lambda_u241 = new ImageVector.Builder("Filled.PowerOff", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(18.0f, 14.49f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(18.0f, 9.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, -1.0f, -1.01f, -2.01f, -2.0f, -2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(16.0f, 3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(-2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(-4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(10.0f, 3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(8.0f, 3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(2.48f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(9.51f, 9.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(0.49f, -0.49f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(16.24f, 16.26f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(7.2f, 7.2f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-0.01f, 0.01f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(3.98f, 4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(2.71f, 5.25f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(3.36f, 3.36f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(6.04f, 8.74f, 6.0f, 8.87f, 6.0f, 9.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(5.48f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(9.5f, 18.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(5.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(-3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(0.48f, -0.48f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(19.45f, 22.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.26f, -1.28f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-4.47f, -4.46f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _powerOff = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_PowerOff__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _powerOff;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
