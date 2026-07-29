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

/* compiled from: Style.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_style", "Landroidx/compose/ui/graphics/vector/ImageVector;", "Style", "Landroidx/compose/material/icons/Icons$Outlined;", "getStyle", "(Landroidx/compose/material/icons/Icons$Outlined;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class StyleKt {
    private static ImageVector _style;

    public static final ImageVector getStyle(Icons.Outlined $this$Style) {
        if (_style != null) {
            ImageVector imageVector = _style;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_Style__u24lambda_u243 = new ImageVector.Builder("Outlined.Style", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(2.53f, 19.65f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.34f, 0.56f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(-9.03f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-2.43f, 5.86f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.41f, 1.02f, 0.08f, 2.19f, 1.09f, 2.61f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(22.03f, 15.95f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(17.07f, 3.98f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.31f, -0.75f, -1.04f, -1.21f, -1.81f, -1.23f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.26f, 0.0f, -0.53f, 0.04f, -0.79f, 0.15f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(7.1f, 5.95f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.75f, 0.31f, -1.21f, 1.03f, -1.23f, 1.8f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.01f, 0.27f, 0.04f, 0.54f, 0.15f, 0.8f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(4.96f, 11.97f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.31f, 0.76f, 1.05f, 1.22f, 1.83f, 1.23f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.26f, 0.0f, 0.52f, -0.05f, 0.77f, -0.15f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(7.36f, -3.05f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(1.02f, -0.42f, 1.51f, -1.59f, 1.09f, -2.6f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(12.83f, 19.75f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(7.87f, 7.79f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(7.35f, -3.04f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(0.01f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(4.95f, 11.95f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-7.35f, 3.05f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_Style__u24lambda_u243, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null);
        int pathFillType$iv2 = VectorKt.getDefaultFillType();
        Brush fill$iv$iv2 = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv2 = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv2 = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv2 = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv2.moveTo(11.0f, 9.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.moveToRelative(-1.0f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.arcToRelative(1.0f, 1.0f, 0.0f, true, true, 2.0f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.arcToRelative(1.0f, 1.0f, 0.0f, true, true, -2.0f, 0.0f);
        ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_Style__u24lambda_u243, $this$PathData_u24lambda_u240$iv$iv$iv2.getNodes(), pathFillType$iv2, "", fill$iv$iv2, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv2, strokeLineJoin$iv$iv2, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null);
        int pathFillType$iv3 = VectorKt.getDefaultFillType();
        Brush fill$iv$iv3 = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv3 = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv3 = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv3 = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv3.moveTo(5.88f, 19.75f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.curveToRelative(0.0f, 1.1f, 0.9f, 2.0f, 2.0f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.horizontalLineToRelative(1.45f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.lineToRelative(-3.45f, -8.34f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.verticalLineToRelative(6.34f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.close();
        _style = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_Style__u24lambda_u243, $this$PathData_u24lambda_u240$iv$iv$iv3.getNodes(), pathFillType$iv3, "", fill$iv$iv3, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv3, strokeLineJoin$iv$iv3, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _style;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
