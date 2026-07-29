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

/* compiled from: Pin.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_pin", "Landroidx/compose/ui/graphics/vector/ImageVector;", "Pin", "Landroidx/compose/material/icons/Icons$Outlined;", "getPin", "(Landroidx/compose/material/icons/Icons$Outlined;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class PinKt {
    private static ImageVector _pin;

    public static final ImageVector getPin(Icons.Outlined $this$Pin) {
        if (_pin != null) {
            ImageVector imageVector = _pin;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_Pin__u24lambda_u244 = new ImageVector.Builder("Outlined.Pin", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(20.0f, 4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineTo(4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(2.9f, 4.0f, 2.0f, 4.9f, 2.0f, 6.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, 1.1f, 0.9f, 2.0f, 2.0f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(16.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(1.1f, 0.0f, 2.0f, -0.9f, 2.0f, -2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(6.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(22.0f, 4.9f, 21.1f, 4.0f, 20.0f, 4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(20.0f, 18.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineTo(4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(6.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(16.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(18.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_Pin__u24lambda_u244, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null);
        int pathFillType$iv2 = VectorKt.getDefaultFillType();
        Brush fill$iv$iv2 = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv2 = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv2 = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv2 = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv2.moveTo(6.49f, 10.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineToRelative(0.0f, 4.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineToRelative(1.15f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineToRelative(0.0f, -6.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineToRelative(-0.87f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineToRelative(-1.76f, 1.27f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineToRelative(0.58f, 0.89f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.close();
        ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_Pin__u24lambda_u244, $this$PathData_u24lambda_u240$iv$iv$iv2.getNodes(), pathFillType$iv2, "", fill$iv$iv2, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv2, strokeLineJoin$iv$iv2, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null);
        int pathFillType$iv3 = VectorKt.getDefaultFillType();
        Brush fill$iv$iv3 = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv3 = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv3 = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv3 = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv3.moveTo(11.47f, 10.05f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.curveToRelative(0.5f, 0.0f, 0.81f, 0.32f, 0.81f, 0.72f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.curveToRelative(0.0f, 0.37f, -0.14f, 0.64f, -0.54f, 1.06f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.curveToRelative(-0.36f, 0.38f, -1.06f, 1.08f, -2.13f, 2.15f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.verticalLineTo(15.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.horizontalLineToRelative(3.89f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.verticalLineToRelative(-0.99f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.horizontalLineToRelative(-2.37f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.lineToRelative(-0.03f, -0.05f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.curveToRelative(0.68f, -0.68f, 1.15f, -1.14f, 1.4f, -1.39f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.curveToRelative(0.61f, -0.6f, 0.92f, -1.22f, 0.92f, -1.86f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.curveToRelative(0.0f, -0.24f, -0.05f, -1.04f, -0.91f, -1.48f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.curveTo(12.04f, 9.0f, 11.25f, 8.87f, 10.56f, 9.2f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.curveToRelative(-0.82f, 0.39f, -0.99f, 1.13f, -1.0f, 1.15f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.lineToRelative(1.01f, 0.42f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.curveTo(10.67f, 10.44f, 10.95f, 10.05f, 11.47f, 10.05f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.close();
        ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_Pin__u24lambda_u244, $this$PathData_u24lambda_u240$iv$iv$iv3.getNodes(), pathFillType$iv3, "", fill$iv$iv3, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv3, strokeLineJoin$iv$iv3, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null);
        int pathFillType$iv4 = VectorKt.getDefaultFillType();
        Brush fill$iv$iv4 = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv4 = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv4 = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv4 = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv4.moveTo(16.99f, 13.94f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.curveToRelative(-0.83f, 0.0f, -0.99f, -0.76f, -1.02f, -0.86f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.lineToRelative(-1.03f, 0.41f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.curveToRelative(0.45f, 1.59f, 2.01f, 1.51f, 2.05f, 1.51f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.curveToRelative(1.2f, 0.0f, 1.68f, -0.72f, 1.76f, -0.85f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.curveToRelative(0.32f, -0.49f, 0.36f, -1.24f, -0.01f, -1.76f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.curveToRelative(-0.17f, -0.24f, -0.4f, -0.41f, -0.68f, -0.52f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.verticalLineTo(11.8f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.curveToRelative(0.2f, -0.1f, 0.37f, -0.26f, 0.52f, -0.48f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.curveToRelative(0.26f, -0.41f, 0.31f, -1.07f, -0.02f, -1.57f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.curveTo(18.48f, 9.64f, 18.03f, 9.0f, 16.94f, 9.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.curveToRelative(-1.26f, 0.0f, -1.74f, 0.9f, -1.85f, 1.24f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.lineToRelative(0.99f, 0.41f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.curveToRelative(0.11f, -0.32f, 0.35f, -0.64f, 0.85f, -0.64f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.curveToRelative(0.44f, 0.0f, 0.75f, 0.26f, 0.75f, 0.65f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.curveToRelative(0.0f, 0.58f, -0.55f, 0.72f, -0.88f, 0.72f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.horizontalLineToRelative(-0.46f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.verticalLineToRelative(1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.horizontalLineToRelative(0.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.curveToRelative(0.56f, 0.0f, 1.04f, 0.24f, 1.04f, 0.79f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.curveTo(17.88f, 13.66f, 17.4f, 13.94f, 16.99f, 13.94f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.close();
        _pin = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_Pin__u24lambda_u244, $this$PathData_u24lambda_u240$iv$iv$iv4.getNodes(), pathFillType$iv4, "", fill$iv$iv4, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv4, strokeLineJoin$iv$iv4, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _pin;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
