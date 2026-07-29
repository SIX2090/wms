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

/* compiled from: BreakfastDining.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_breakfastDining", "Landroidx/compose/ui/graphics/vector/ImageVector;", "BreakfastDining", "Landroidx/compose/material/icons/Icons$TwoTone;", "getBreakfastDining", "(Landroidx/compose/material/icons/Icons$TwoTone;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class BreakfastDiningKt {
    private static ImageVector _breakfastDining;

    public static final ImageVector getBreakfastDining(Icons.TwoTone $this$BreakfastDining) {
        if (_breakfastDining != null) {
            ImageVector imageVector = _breakfastDining;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_BreakfastDining__u24lambda_u243 = new ImageVector.Builder("TwoTone.BreakfastDining", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(18.0f, 5.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineTo(6.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(4.9f, 5.0f, 4.0f, 5.9f, 4.0f, 7.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, 0.71f, 0.38f, 1.35f, 1.01f, 1.73f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(6.0f, 9.31f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(19.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(9.3f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.0f, -0.58f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.63f, -0.36f, 1.0f, -1.01f, 1.0f, -1.72f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(20.0f, 5.9f, 19.1f, 5.0f, 18.0f, 5.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(15.71f, 13.7f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-3.0f, 3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(12.51f, 16.9f, 12.26f, 17.0f, 12.0f, 17.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveToRelative(-0.51f, -0.1f, -0.71f, -0.29f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-3.0f, -3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.39f, -0.39f, -0.39f, -1.02f, 0.0f, -1.41f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(3.0f, -3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(11.49f, 9.1f, 11.74f, 9.0f, 12.0f, 9.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveToRelative(0.51f, 0.1f, 0.71f, 0.29f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(3.0f, 3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(16.1f, 12.68f, 16.1f, 13.31f, 15.71f, 13.7f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_BreakfastDining__u24lambda_u243, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 0.3f, null, 0.3f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null);
        int pathFillType$iv2 = VectorKt.getDefaultFillType();
        Brush fill$iv$iv2 = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv2 = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv2 = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv2 = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv2.moveTo(18.0f, 3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.horizontalLineTo(6.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveTo(3.79f, 3.0f, 2.0f, 4.79f, 2.0f, 7.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveToRelative(0.0f, 1.48f, 0.81f, 2.75f, 2.0f, 3.45f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.verticalLineTo(19.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveToRelative(0.0f, 1.1f, 0.9f, 2.0f, 2.0f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.horizontalLineToRelative(12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveToRelative(1.1f, 0.0f, 2.0f, -0.9f, 2.0f, -2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.verticalLineToRelative(-8.55f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveToRelative(1.19f, -0.69f, 2.0f, -1.97f, 2.0f, -3.45f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveTo(22.0f, 4.79f, 20.21f, 3.0f, 18.0f, 3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.close();
        $this$PathData_u24lambda_u240$iv$iv$iv2.moveTo(19.0f, 8.72f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineTo(18.0f, 9.3f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.verticalLineTo(19.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.horizontalLineTo(6.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.verticalLineTo(9.31f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineTo(5.01f, 8.73f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveTo(4.38f, 8.35f, 4.0f, 7.71f, 4.0f, 7.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveToRelative(0.0f, -1.1f, 0.9f, -2.0f, 2.0f, -2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.horizontalLineToRelative(12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveToRelative(1.1f, 0.0f, 2.0f, 0.9f, 2.0f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveTo(20.0f, 7.71f, 19.62f, 8.36f, 19.0f, 8.72f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.close();
        ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_BreakfastDining__u24lambda_u243, $this$PathData_u24lambda_u240$iv$iv$iv2.getNodes(), pathFillType$iv2, "", fill$iv$iv2, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv2, strokeLineJoin$iv$iv2, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null);
        int pathFillType$iv3 = VectorKt.getDefaultFillType();
        Brush fill$iv$iv3 = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv3 = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv3 = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv3 = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv3.moveTo(12.71f, 9.29f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.curveTo(12.51f, 9.1f, 12.26f, 9.0f, 12.0f, 9.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.reflectiveCurveToRelative(-0.51f, 0.1f, -0.71f, 0.29f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.lineToRelative(-3.0f, 3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.curveToRelative(-0.39f, 0.39f, -0.39f, 1.02f, 0.0f, 1.41f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.lineToRelative(3.0f, 3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.curveTo(11.49f, 16.9f, 11.74f, 17.0f, 12.0f, 17.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.reflectiveCurveToRelative(0.51f, -0.1f, 0.71f, -0.29f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.lineToRelative(3.0f, -3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.curveToRelative(0.39f, -0.39f, 0.39f, -1.02f, 0.0f, -1.41f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.lineTo(12.71f, 9.29f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.close();
        $this$PathData_u24lambda_u240$iv$iv$iv3.moveTo(12.0f, 14.58f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.lineTo(10.41f, 13.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.lineTo(12.0f, 11.41f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.lineTo(13.59f, 13.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.lineTo(12.0f, 14.58f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.close();
        _breakfastDining = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_BreakfastDining__u24lambda_u243, $this$PathData_u24lambda_u240$iv$iv$iv3.getNodes(), pathFillType$iv3, "", fill$iv$iv3, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv3, strokeLineJoin$iv$iv3, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _breakfastDining;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
