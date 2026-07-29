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

/* compiled from: Doorbell.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_doorbell", "Landroidx/compose/ui/graphics/vector/ImageVector;", "Doorbell", "Landroidx/compose/material/icons/Icons$TwoTone;", "getDoorbell", "(Landroidx/compose/material/icons/Icons$TwoTone;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class DoorbellKt {
    private static ImageVector _doorbell;

    public static final ImageVector getDoorbell(Icons.TwoTone $this$Doorbell) {
        if (_doorbell != null) {
            ImageVector imageVector = _doorbell;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_Doorbell__u24lambda_u244 = new ImageVector.Builder("TwoTone.Doorbell", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(6.0f, 10.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(9.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(-9.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-6.0f, -4.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(6.0f, 10.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(12.0f, 17.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.55f, 0.0f, -1.0f, -0.45f, -1.0f, -1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(13.0f, 17.05f, 12.55f, 17.5f, 12.0f, 17.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(12.75f, 9.25f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(9.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(14.19f, 9.84f, 15.0f, 11.12f, 15.0f, 12.66f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(15.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineTo(8.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(-1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(-2.34f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, -1.54f, 0.82f, -2.82f, 2.25f, -3.16f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(9.25f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, -0.41f, 0.34f, -0.75f, 0.75f, -0.75f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveTo(12.75f, 8.84f, 12.75f, 9.25f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_Doorbell__u24lambda_u244, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 0.3f, null, 0.3f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null);
        int pathFillType$iv2 = VectorKt.getDefaultFillType();
        Brush fill$iv$iv2 = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv2 = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv2 = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv2 = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv2.moveTo(12.0f, 3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineTo(4.0f, 9.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.verticalLineToRelative(12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.horizontalLineToRelative(16.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.verticalLineTo(9.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineTo(12.0f, 3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.close();
        $this$PathData_u24lambda_u240$iv$iv$iv2.moveTo(18.0f, 19.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.horizontalLineTo(6.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.verticalLineToRelative(-9.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineToRelative(6.0f, -4.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineToRelative(6.0f, 4.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.verticalLineTo(19.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.close();
        ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_Doorbell__u24lambda_u244, $this$PathData_u24lambda_u240$iv$iv$iv2.getNodes(), pathFillType$iv2, "", fill$iv$iv2, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv2, strokeLineJoin$iv$iv2, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null);
        int pathFillType$iv3 = VectorKt.getDefaultFillType();
        Brush fill$iv$iv3 = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv3 = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv3 = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv3 = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv3.moveTo(11.25f, 9.25f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.verticalLineTo(9.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.curveTo(9.82f, 9.84f, 9.0f, 11.12f, 9.0f, 12.66f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.verticalLineTo(15.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.horizontalLineTo(8.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.verticalLineToRelative(1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.horizontalLineToRelative(8.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.verticalLineToRelative(-1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.horizontalLineToRelative(-1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.verticalLineToRelative(-2.34f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.curveToRelative(0.0f, -1.54f, -0.81f, -2.82f, -2.25f, -3.16f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.verticalLineTo(9.25f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.curveToRelative(0.0f, -0.41f, -0.34f, -0.75f, -0.75f, -0.75f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.reflectiveCurveTo(11.25f, 8.84f, 11.25f, 9.25f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.close();
        ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_Doorbell__u24lambda_u244, $this$PathData_u24lambda_u240$iv$iv$iv3.getNodes(), pathFillType$iv3, "", fill$iv$iv3, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv3, strokeLineJoin$iv$iv3, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null);
        int pathFillType$iv4 = VectorKt.getDefaultFillType();
        Brush fill$iv$iv4 = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv4 = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv4 = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv4 = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv4.moveTo(12.0f, 17.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.curveToRelative(0.55f, 0.0f, 1.0f, -0.45f, 1.0f, -1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.horizontalLineToRelative(-2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.curveTo(11.0f, 17.05f, 11.45f, 17.5f, 12.0f, 17.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.close();
        _doorbell = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_Doorbell__u24lambda_u244, $this$PathData_u24lambda_u240$iv$iv$iv4.getNodes(), pathFillType$iv4, "", fill$iv$iv4, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv4, strokeLineJoin$iv$iv4, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _doorbell;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
