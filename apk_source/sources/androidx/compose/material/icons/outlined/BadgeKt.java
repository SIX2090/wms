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

/* compiled from: Badge.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_badge", "Landroidx/compose/ui/graphics/vector/ImageVector;", "Badge", "Landroidx/compose/material/icons/Icons$Outlined;", "getBadge", "(Landroidx/compose/material/icons/Icons$Outlined;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class BadgeKt {
    private static ImageVector _badge;

    public static final ImageVector getBadge(Icons.Outlined $this$Badge) {
        if (_badge != null) {
            ImageVector imageVector = _badge;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_Badge__u24lambda_u245 = new ImageVector.Builder("Outlined.Badge", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(14.0f, 12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(1.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(-4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_Badge__u24lambda_u245, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null);
        int pathFillType$iv2 = VectorKt.getDefaultFillType();
        Brush fill$iv$iv2 = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv2 = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv2 = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv2 = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv2.moveTo(14.0f, 15.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.horizontalLineToRelative(4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.verticalLineToRelative(1.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.horizontalLineToRelative(-4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.close();
        ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_Badge__u24lambda_u245, $this$PathData_u24lambda_u240$iv$iv$iv2.getNodes(), pathFillType$iv2, "", fill$iv$iv2, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv2, strokeLineJoin$iv$iv2, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null);
        int pathFillType$iv3 = VectorKt.getDefaultFillType();
        Brush fill$iv$iv3 = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv3 = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv3 = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv3 = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv3.moveTo(20.0f, 7.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.horizontalLineToRelative(-5.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.verticalLineTo(4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.curveToRelative(0.0f, -1.1f, -0.9f, -2.0f, -2.0f, -2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.horizontalLineToRelative(-2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.curveTo(9.9f, 2.0f, 9.0f, 2.9f, 9.0f, 4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.verticalLineToRelative(3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.horizontalLineTo(4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.curveTo(2.9f, 7.0f, 2.0f, 7.9f, 2.0f, 9.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.verticalLineToRelative(11.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.curveToRelative(0.0f, 1.1f, 0.9f, 2.0f, 2.0f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.horizontalLineToRelative(16.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.curveToRelative(1.1f, 0.0f, 2.0f, -0.9f, 2.0f, -2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.verticalLineTo(9.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.curveTo(22.0f, 7.9f, 21.1f, 7.0f, 20.0f, 7.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.close();
        $this$PathData_u24lambda_u240$iv$iv$iv3.moveTo(11.0f, 7.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.verticalLineTo(4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.horizontalLineToRelative(2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.verticalLineToRelative(3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.verticalLineToRelative(2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.horizontalLineToRelative(-2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.verticalLineTo(7.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.close();
        $this$PathData_u24lambda_u240$iv$iv$iv3.moveTo(20.0f, 20.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.horizontalLineTo(4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.verticalLineTo(9.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.horizontalLineToRelative(5.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.curveToRelative(0.0f, 1.1f, 0.9f, 2.0f, 2.0f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.horizontalLineToRelative(2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.curveToRelative(1.1f, 0.0f, 2.0f, -0.9f, 2.0f, -2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.horizontalLineToRelative(5.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.verticalLineTo(20.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.close();
        ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_Badge__u24lambda_u245, $this$PathData_u24lambda_u240$iv$iv$iv3.getNodes(), pathFillType$iv3, "", fill$iv$iv3, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv3, strokeLineJoin$iv$iv3, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null);
        int pathFillType$iv4 = VectorKt.getDefaultFillType();
        Brush fill$iv$iv4 = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv4 = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv4 = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv4 = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv4.moveTo(9.0f, 13.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.moveToRelative(-1.5f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.arcToRelative(1.5f, 1.5f, 0.0f, true, true, 3.0f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.arcToRelative(1.5f, 1.5f, 0.0f, true, true, -3.0f, 0.0f);
        ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_Badge__u24lambda_u245, $this$PathData_u24lambda_u240$iv$iv$iv4.getNodes(), pathFillType$iv4, "", fill$iv$iv4, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv4, strokeLineJoin$iv$iv4, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null);
        int pathFillType$iv5 = VectorKt.getDefaultFillType();
        Brush fill$iv$iv5 = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv5 = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv5 = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv5 = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv5.moveTo(11.08f, 16.18f);
        $this$PathData_u24lambda_u240$iv$iv$iv5.curveTo(10.44f, 15.9f, 9.74f, 15.75f, 9.0f, 15.75f);
        $this$PathData_u24lambda_u240$iv$iv$iv5.reflectiveCurveToRelative(-1.44f, 0.15f, -2.08f, 0.43f);
        $this$PathData_u24lambda_u240$iv$iv$iv5.curveTo(6.36f, 16.42f, 6.0f, 16.96f, 6.0f, 17.57f);
        $this$PathData_u24lambda_u240$iv$iv$iv5.verticalLineTo(18.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv5.horizontalLineToRelative(6.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv5.verticalLineToRelative(-0.43f);
        $this$PathData_u24lambda_u240$iv$iv$iv5.curveTo(12.0f, 16.96f, 11.64f, 16.42f, 11.08f, 16.18f);
        $this$PathData_u24lambda_u240$iv$iv$iv5.close();
        _badge = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_Badge__u24lambda_u245, $this$PathData_u24lambda_u240$iv$iv$iv5.getNodes(), pathFillType$iv5, "", fill$iv$iv5, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv5, strokeLineJoin$iv$iv5, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _badge;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
