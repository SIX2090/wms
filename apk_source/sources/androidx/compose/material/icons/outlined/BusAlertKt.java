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

/* compiled from: BusAlert.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_busAlert", "Landroidx/compose/ui/graphics/vector/ImageVector;", "BusAlert", "Landroidx/compose/material/icons/Icons$Outlined;", "getBusAlert", "(Landroidx/compose/material/icons/Icons$Outlined;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class BusAlertKt {
    private static ImageVector _busAlert;

    public static final ImageVector getBusAlert(Icons.Outlined $this$BusAlert) {
        if (_busAlert != null) {
            ImageVector imageVector = _busAlert;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_BusAlert__u24lambda_u244 = new ImageVector.Builder("Outlined.BusAlert", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(6.5f, 15.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.moveToRelative(-1.5f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.arcToRelative(1.5f, 1.5f, 0.0f, true, true, 3.0f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.arcToRelative(1.5f, 1.5f, 0.0f, true, true, -3.0f, 0.0f);
        ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_BusAlert__u24lambda_u244, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null);
        int pathFillType$iv2 = VectorKt.getDefaultFillType();
        Brush fill$iv$iv2 = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv2 = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv2 = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv2 = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv2.moveTo(13.5f, 15.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.moveToRelative(-1.5f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.arcToRelative(1.5f, 1.5f, 0.0f, true, true, 3.0f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.arcToRelative(1.5f, 1.5f, 0.0f, true, true, -3.0f, 0.0f);
        ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_BusAlert__u24lambda_u244, $this$PathData_u24lambda_u240$iv$iv$iv2.getNodes(), pathFillType$iv2, "", fill$iv$iv2, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv2, strokeLineJoin$iv$iv2, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null);
        int pathFillType$iv3 = VectorKt.getDefaultFillType();
        Brush fill$iv$iv3 = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv3 = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv3 = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv3 = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv3.moveTo(4.0f, 11.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.verticalLineTo(8.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.horizontalLineToRelative(7.29f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.curveTo(11.1f, 7.37f, 11.0f, 6.7f, 11.0f, 6.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.horizontalLineTo(4.43f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.curveToRelative(0.83f, -0.71f, 2.98f, -1.09f, 6.65f, -0.98f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.curveToRelative(0.1f, -0.7f, 0.3f, -1.37f, 0.59f, -1.99f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.curveTo(2.97f, 2.67f, 2.0f, 5.02f, 2.0f, 7.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.verticalLineToRelative(9.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.curveToRelative(0.0f, 0.95f, 0.38f, 1.81f, 1.0f, 2.44f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.verticalLineTo(21.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.curveToRelative(0.0f, 0.55f, 0.45f, 1.0f, 1.0f, 1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.horizontalLineToRelative(1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.curveToRelative(0.55f, 0.0f, 1.0f, -0.45f, 1.0f, -1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.verticalLineToRelative(-1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.horizontalLineToRelative(8.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.verticalLineToRelative(1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.curveToRelative(0.0f, 0.55f, 0.45f, 1.0f, 1.0f, 1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.horizontalLineToRelative(1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.curveToRelative(0.55f, 0.0f, 1.0f, -0.45f, 1.0f, -1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.verticalLineToRelative(-2.06f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.curveToRelative(0.62f, -0.63f, 1.0f, -1.49f, 1.0f, -2.44f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.verticalLineTo(13.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.curveToRelative(-1.91f, 0.0f, -3.63f, -0.76f, -4.89f, -2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.horizontalLineTo(4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.close();
        $this$PathData_u24lambda_u240$iv$iv$iv3.moveTo(16.0f, 16.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.curveToRelative(0.0f, 1.1f, -0.9f, 2.0f, -2.0f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.horizontalLineTo(6.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.curveToRelative(-1.1f, 0.0f, -2.0f, -0.9f, -2.0f, -2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.verticalLineToRelative(-3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.horizontalLineToRelative(12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.verticalLineTo(16.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.close();
        ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_BusAlert__u24lambda_u244, $this$PathData_u24lambda_u240$iv$iv$iv3.getNodes(), pathFillType$iv3, "", fill$iv$iv3, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv3, strokeLineJoin$iv$iv3, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null);
        int pathFillType$iv4 = VectorKt.getDefaultFillType();
        Brush fill$iv$iv4 = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv4 = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv4 = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv4 = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv4.moveTo(18.0f, 1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.curveToRelative(-2.76f, 0.0f, -5.0f, 2.24f, -5.0f, 5.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.reflectiveCurveToRelative(2.24f, 5.0f, 5.0f, 5.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.reflectiveCurveToRelative(5.0f, -2.24f, 5.0f, -5.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.reflectiveCurveTo(20.76f, 1.0f, 18.0f, 1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.close();
        $this$PathData_u24lambda_u240$iv$iv$iv4.moveTo(18.5f, 9.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.horizontalLineToRelative(-1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.verticalLineTo(8.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.horizontalLineToRelative(1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.verticalLineTo(9.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.close();
        $this$PathData_u24lambda_u240$iv$iv$iv4.moveTo(18.5f, 7.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.horizontalLineToRelative(-1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.verticalLineTo(3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.horizontalLineToRelative(1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.verticalLineTo(7.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.close();
        _busAlert = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_BusAlert__u24lambda_u244, $this$PathData_u24lambda_u240$iv$iv$iv4.getNodes(), pathFillType$iv4, "", fill$iv$iv4, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv4, strokeLineJoin$iv$iv4, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _busAlert;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
