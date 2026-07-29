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

/* compiled from: PhotoCameraFront.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_photoCameraFront", "Landroidx/compose/ui/graphics/vector/ImageVector;", "PhotoCameraFront", "Landroidx/compose/material/icons/Icons$TwoTone;", "getPhotoCameraFront", "(Landroidx/compose/material/icons/Icons$TwoTone;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class PhotoCameraFrontKt {
    private static ImageVector _photoCameraFront;

    public static final ImageVector getPhotoCameraFront(Icons.TwoTone $this$PhotoCameraFront) {
        if (_photoCameraFront != null) {
            ImageVector imageVector = _photoCameraFront;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_PhotoCameraFront__u24lambda_u242 = new ImageVector.Builder("TwoTone.PhotoCameraFront", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(15.95f, 7.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-1.83f, -2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineTo(9.88f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(8.05f, 7.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineTo(4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(16.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(7.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineTo(15.95f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(12.0f, 9.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(1.1f, 0.0f, 2.0f, 0.9f, 2.0f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, 1.1f, -0.9f, 2.0f, -2.0f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveToRelative(-2.0f, -0.9f, -2.0f, -2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(10.0f, 9.9f, 10.9f, 9.0f, 12.0f, 9.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(16.0f, 17.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineTo(8.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(-0.57f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, -0.81f, 0.48f, -1.53f, 1.22f, -1.85f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(10.07f, 14.21f, 11.01f, 14.0f, 12.0f, 14.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveToRelative(1.93f, 0.21f, 2.78f, 0.58f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(15.52f, 14.9f, 16.0f, 15.62f, 16.0f, 16.43f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(17.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_PhotoCameraFront__u24lambda_u242, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 0.3f, null, 0.3f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null);
        int pathFillType$iv2 = VectorKt.getDefaultFillType();
        Brush fill$iv$iv2 = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv2 = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv2 = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv2 = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv2.moveTo(20.0f, 5.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.horizontalLineToRelative(-3.17f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineTo(15.0f, 3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.horizontalLineTo(9.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineTo(7.17f, 5.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.horizontalLineTo(4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveTo(2.9f, 5.0f, 2.0f, 5.9f, 2.0f, 7.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.verticalLineToRelative(12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveToRelative(0.0f, 1.1f, 0.9f, 2.0f, 2.0f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.horizontalLineToRelative(16.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveToRelative(1.1f, 0.0f, 2.0f, -0.9f, 2.0f, -2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.verticalLineTo(7.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveTo(22.0f, 5.9f, 21.1f, 5.0f, 20.0f, 5.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.close();
        $this$PathData_u24lambda_u240$iv$iv$iv2.moveTo(20.0f, 19.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.horizontalLineTo(4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.verticalLineTo(7.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.horizontalLineToRelative(4.05f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineToRelative(1.83f, -2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.horizontalLineToRelative(4.24f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineToRelative(1.83f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.horizontalLineTo(20.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.verticalLineTo(19.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.close();
        $this$PathData_u24lambda_u240$iv$iv$iv2.moveTo(12.0f, 13.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveToRelative(1.1f, 0.0f, 2.0f, -0.9f, 2.0f, -2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveToRelative(0.0f, -1.1f, -0.9f, -2.0f, -2.0f, -2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.reflectiveCurveToRelative(-2.0f, 0.9f, -2.0f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveTo(10.0f, 12.1f, 10.9f, 13.0f, 12.0f, 13.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.close();
        $this$PathData_u24lambda_u240$iv$iv$iv2.moveTo(14.78f, 14.58f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveTo(13.93f, 14.21f, 12.99f, 14.0f, 12.0f, 14.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.reflectiveCurveToRelative(-1.93f, 0.21f, -2.78f, 0.58f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveTo(8.48f, 14.9f, 8.0f, 15.62f, 8.0f, 16.43f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.verticalLineTo(17.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.horizontalLineToRelative(8.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.verticalLineToRelative(-0.57f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveTo(16.0f, 15.62f, 15.52f, 14.9f, 14.78f, 14.58f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.close();
        _photoCameraFront = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_PhotoCameraFront__u24lambda_u242, $this$PathData_u24lambda_u240$iv$iv$iv2.getNodes(), pathFillType$iv2, "", fill$iv$iv2, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv2, strokeLineJoin$iv$iv2, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _photoCameraFront;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
