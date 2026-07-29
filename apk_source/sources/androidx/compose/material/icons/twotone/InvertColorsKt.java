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

/* compiled from: InvertColors.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_invertColors", "Landroidx/compose/ui/graphics/vector/ImageVector;", "InvertColors", "Landroidx/compose/material/icons/Icons$TwoTone;", "getInvertColors", "(Landroidx/compose/material/icons/Icons$TwoTone;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class InvertColorsKt {
    private static ImageVector _invertColors;

    public static final ImageVector getInvertColors(Icons.TwoTone $this$InvertColors) {
        if (_invertColors != null) {
            ImageVector imageVector = _invertColors;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_InvertColors__u24lambda_u242 = new ImageVector.Builder("TwoTone.InvertColors", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(7.75f, 8.99f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(6.62f, 10.1f, 6.0f, 11.57f, 6.0f, 13.13f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(6.0f, 16.37f, 8.69f, 19.0f, 12.0f, 19.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(0.0f, -14.19f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(7.75f, 8.99f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_InvertColors__u24lambda_u242, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 0.3f, null, 0.3f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null);
        int pathFillType$iv2 = VectorKt.getDefaultFillType();
        Brush fill$iv$iv2 = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv2 = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv2 = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv2 = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv2.moveTo(17.65f, 7.56f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineTo(17.65f, 7.56f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineTo(12.0f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineTo(6.35f, 7.56f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineToRelative(0.0f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveTo(4.9f, 8.99f, 4.0f, 10.96f, 4.0f, 13.13f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveTo(4.0f, 17.48f, 7.58f, 21.0f, 12.0f, 21.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveToRelative(4.42f, 0.0f, 8.0f, -3.52f, 8.0f, -7.87f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveTo(20.0f, 10.96f, 19.1f, 8.99f, 17.65f, 7.56f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.close();
        $this$PathData_u24lambda_u240$iv$iv$iv2.moveTo(6.0f, 13.13f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveToRelative(0.0f, -1.56f, 0.62f, -3.03f, 1.75f, -4.14f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineTo(12.0f, 4.81f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineTo(12.0f, 19.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveTo(8.69f, 19.0f, 6.0f, 16.37f, 6.0f, 13.13f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.close();
        _invertColors = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_InvertColors__u24lambda_u242, $this$PathData_u24lambda_u240$iv$iv$iv2.getNodes(), pathFillType$iv2, "", fill$iv$iv2, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv2, strokeLineJoin$iv$iv2, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _invertColors;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
