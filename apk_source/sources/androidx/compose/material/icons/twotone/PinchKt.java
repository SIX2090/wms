package androidx.compose.material.icons.twotone;

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

/* compiled from: Pinch.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_pinch", "Landroidx/compose/ui/graphics/vector/ImageVector;", "Pinch", "Landroidx/compose/material/icons/Icons$TwoTone;", "getPinch", "(Landroidx/compose/material/icons/Icons$TwoTone;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class PinchKt {
    private static ImageVector _pinch;

    public static final ImageVector getPinch(Icons.TwoTone $this$Pinch) {
        if (_pinch != null) {
            ImageVector imageVector = _pinch;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_Pinch__u24lambda_u242 = new ImageVector.Builder("TwoTone.Pinch", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(21.0f, 15.56f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-4.24f, -1.89f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineTo(15.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(7.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(15.0f, 7.22f, 14.78f, 7.0f, 14.5f, 7.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveTo(14.0f, 7.22f, 14.0f, 7.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(10.61f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-4.17f, -0.89f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(3.7f, 3.78f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(6.55f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(21.0f, 15.56f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_Pinch__u24lambda_u242, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 0.3f, null, 0.3f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null);
        int pathFillType$iv2 = VectorKt.getDefaultFillType();
        Brush fill$iv$iv2 = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv2 = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv2 = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv2 = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv2.moveTo(6.0f, 2.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.verticalLineTo(1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.horizontalLineToRelative(5.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.verticalLineToRelative(5.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.horizontalLineTo(9.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.verticalLineTo(3.56f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineTo(3.56f, 9.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.horizontalLineTo(6.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.verticalLineTo(11.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.horizontalLineTo(1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.verticalLineTo(6.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.horizontalLineToRelative(1.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.verticalLineToRelative(2.44f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineTo(8.44f, 2.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.horizontalLineTo(6.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.close();
        $this$PathData_u24lambda_u240$iv$iv$iv2.moveTo(21.89f, 13.77f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineToRelative(-3.8f, -1.67f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveTo(17.96f, 12.04f, 17.81f, 12.0f, 17.65f, 12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.horizontalLineTo(17.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.verticalLineTo(7.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveTo(17.0f, 6.12f, 15.88f, 5.0f, 14.5f, 5.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.reflectiveCurveTo(12.0f, 6.12f, 12.0f, 7.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.verticalLineToRelative(8.15f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineToRelative(-1.87f, -0.4f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveToRelative(-0.19f, -0.03f, -1.02f, -0.15f, -1.73f, 0.56f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineTo(7.0f, 17.22f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineToRelative(5.12f, 5.19f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveTo(12.49f, 22.79f, 13.0f, 23.0f, 13.53f, 23.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.horizontalLineToRelative(6.55f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveToRelative(0.98f, 0.0f, 1.81f, -0.7f, 1.97f, -1.67f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineToRelative(0.92f, -5.44f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveTo(23.12f, 15.03f, 22.68f, 14.17f, 21.89f, 13.77f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.close();
        $this$PathData_u24lambda_u240$iv$iv$iv2.moveTo(20.08f, 21.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.horizontalLineToRelative(-6.55f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineToRelative(-3.7f, -3.78f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineTo(14.0f, 18.11f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.verticalLineTo(7.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveTo(14.0f, 7.22f, 14.22f, 7.0f, 14.5f, 7.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.reflectiveCurveTo(15.0f, 7.22f, 15.0f, 7.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.verticalLineToRelative(6.18f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.horizontalLineToRelative(1.76f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineTo(21.0f, 15.56f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineTo(20.08f, 21.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.close();
        _pinch = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_Pinch__u24lambda_u242, $this$PathData_u24lambda_u240$iv$iv$iv2.getNodes(), pathFillType$iv2, "", fill$iv$iv2, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv2, strokeLineJoin$iv$iv2, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _pinch;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
