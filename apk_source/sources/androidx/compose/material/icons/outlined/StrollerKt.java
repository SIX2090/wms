package androidx.compose.material.icons.outlined;

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

/* compiled from: Stroller.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_stroller", "Landroidx/compose/ui/graphics/vector/ImageVector;", "Stroller", "Landroidx/compose/material/icons/Icons$Outlined;", "getStroller", "(Landroidx/compose/material/icons/Icons$Outlined;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class StrollerKt {
    private static ImageVector _stroller;

    public static final ImageVector getStroller(Icons.Outlined $this$Stroller) {
        if (_stroller != null) {
            ImageVector imageVector = _stroller;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_Stroller__u24lambda_u241 = new ImageVector.Builder("Outlined.Stroller", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(18.0f, 20.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, 1.1f, -0.9f, 2.0f, -2.0f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveToRelative(-2.0f, -0.9f, -2.0f, -2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveToRelative(0.9f, -2.0f, 2.0f, -2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveTo(18.0f, 18.9f, 18.0f, 20.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(6.0f, 18.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-1.1f, 0.0f, -2.0f, 0.9f, -2.0f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveToRelative(0.9f, 2.0f, 2.0f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveToRelative(2.0f, -0.9f, 2.0f, -2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveTo(7.1f, 18.0f, 6.0f, 18.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(15.0f, 8.66f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(9.6f, 15.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineTo(15.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(8.66f);
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(18.65f, 3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(20.52f, 3.0f, 22.0f, 4.56f, 22.0f, 6.48f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(7.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(-2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(6.48f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(20.0f, 5.66f, 19.42f, 5.0f, 18.65f, 5.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(17.97f, 5.0f, 17.58f, 5.59f, 17.0f, 6.27f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(15.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, 1.1f, -0.9f, 2.0f, -2.0f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineTo(7.43f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.85f, 0.0f, -1.31f, -1.0f, -0.76f, -1.65f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(8.8f, -10.32f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(16.11f, 4.27f, 16.99f, 3.0f, 18.65f, 3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(18.65f, 3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(10.0f, 5.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(9.35f, 5.0f, 8.71f, 5.09f, 8.09f, 5.27f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.4f, 1.4f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.37f, -1.61f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(10.58f, 5.02f, 10.29f, 5.0f, 10.0f, 5.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(10.0f, 3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(1.56f, 0.0f, 3.03f, 0.4f, 4.3f, 1.1f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-4.7f, 5.51f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(4.72f, 4.72f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(6.21f, 3.64f, 8.03f, 3.0f, 10.0f, 3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(10.0f, 3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _stroller = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_Stroller__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _stroller;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
