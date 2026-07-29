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

/* compiled from: Loyalty.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_loyalty", "Landroidx/compose/ui/graphics/vector/ImageVector;", "Loyalty", "Landroidx/compose/material/icons/Icons$TwoTone;", "getLoyalty", "(Landroidx/compose/material/icons/Icons$TwoTone;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class LoyaltyKt {
    private static ImageVector _loyalty;

    public static final ImageVector getLoyalty(Icons.TwoTone $this$Loyalty) {
        if (_loyalty != null) {
            ImageVector imageVector = _loyalty;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_Loyalty__u24lambda_u244 = new ImageVector.Builder("TwoTone.Loyalty", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(11.0f, 4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(4.0f, 4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(7.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(9.0f, 9.01f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(20.0f, 13.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-9.0f, -9.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(6.5f, 8.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(5.67f, 8.0f, 5.0f, 7.33f, 5.0f, 6.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveTo(5.67f, 5.0f, 6.5f, 5.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveTo(8.0f, 5.67f, 8.0f, 6.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveTo(7.33f, 8.0f, 6.5f, 8.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(13.0f, 11.7f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(0.6f, -0.6f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.37f, -0.37f, 0.89f, -0.6f, 1.45f, -0.6f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(1.13f, 0.0f, 2.05f, 0.92f, 2.05f, 2.05f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, 0.57f, -0.23f, 1.08f, -0.6f, 1.45f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(13.0f, 17.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(9.5f, 14.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.37f, -0.38f, -0.6f, -0.89f, -0.6f, -1.45f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, -1.13f, 0.92f, -2.05f, 2.05f, -2.05f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.57f, 0.0f, 1.08f, 0.23f, 1.45f, 0.61f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(0.6f, 0.59f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_Loyalty__u24lambda_u244, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 0.3f, null, 0.3f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null);
        int pathFillType$iv2 = VectorKt.getDefaultFillType();
        Brush fill$iv$iv2 = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv2 = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv2 = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv2 = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv2.moveTo(21.41f, 11.58f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineToRelative(-9.0f, -9.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveTo(12.05f, 2.22f, 11.55f, 2.0f, 11.0f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.horizontalLineTo(4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveToRelative(-1.1f, 0.0f, -2.0f, 0.9f, -2.0f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.verticalLineToRelative(7.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveToRelative(0.0f, 0.55f, 0.22f, 1.05f, 0.59f, 1.42f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineToRelative(9.0f, 9.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveToRelative(0.36f, 0.36f, 0.86f, 0.58f, 1.41f, 0.58f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.reflectiveCurveToRelative(1.05f, -0.22f, 1.41f, -0.59f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineToRelative(7.0f, -7.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveToRelative(0.37f, -0.36f, 0.59f, -0.86f, 0.59f, -1.41f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.reflectiveCurveToRelative(-0.23f, -1.06f, -0.59f, -1.42f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.close();
        $this$PathData_u24lambda_u240$iv$iv$iv2.moveTo(13.0f, 20.01f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineTo(4.0f, 11.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.verticalLineTo(4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.horizontalLineToRelative(7.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.verticalLineToRelative(-0.01f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineToRelative(9.0f, 9.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineToRelative(-7.0f, 7.02f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.close();
        ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_Loyalty__u24lambda_u244, $this$PathData_u24lambda_u240$iv$iv$iv2.getNodes(), pathFillType$iv2, "", fill$iv$iv2, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv2, strokeLineJoin$iv$iv2, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null);
        int pathFillType$iv3 = VectorKt.getDefaultFillType();
        Brush fill$iv$iv3 = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv3 = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv3 = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv3 = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv3.moveTo(6.5f, 6.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.moveToRelative(-1.5f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.arcToRelative(1.5f, 1.5f, 0.0f, true, true, 3.0f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.arcToRelative(1.5f, 1.5f, 0.0f, true, true, -3.0f, 0.0f);
        ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_Loyalty__u24lambda_u244, $this$PathData_u24lambda_u240$iv$iv$iv3.getNodes(), pathFillType$iv3, "", fill$iv$iv3, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv3, strokeLineJoin$iv$iv3, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null);
        int pathFillType$iv4 = VectorKt.getDefaultFillType();
        Brush fill$iv$iv4 = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv4 = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv4 = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv4 = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv4.moveTo(8.9f, 12.55f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.curveToRelative(0.0f, 0.57f, 0.23f, 1.07f, 0.6f, 1.45f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.lineToRelative(3.5f, 3.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.lineToRelative(3.5f, -3.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.curveToRelative(0.37f, -0.37f, 0.6f, -0.89f, 0.6f, -1.45f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.curveToRelative(0.0f, -1.13f, -0.92f, -2.05f, -2.05f, -2.05f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.curveToRelative(-0.57f, 0.0f, -1.08f, 0.23f, -1.45f, 0.6f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.lineToRelative(-0.6f, 0.6f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.lineToRelative(-0.6f, -0.59f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.curveToRelative(-0.37f, -0.38f, -0.89f, -0.61f, -1.45f, -0.61f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.curveToRelative(-1.13f, 0.0f, -2.05f, 0.92f, -2.05f, 2.05f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.close();
        _loyalty = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_Loyalty__u24lambda_u244, $this$PathData_u24lambda_u240$iv$iv$iv4.getNodes(), pathFillType$iv4, "", fill$iv$iv4, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv4, strokeLineJoin$iv$iv4, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _loyalty;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
