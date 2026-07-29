package androidx.compose.material.icons.sharp;

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
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_loyalty", "Landroidx/compose/ui/graphics/vector/ImageVector;", "Loyalty", "Landroidx/compose/material/icons/Icons$Sharp;", "getLoyalty", "(Landroidx/compose/material/icons/Icons$Sharp;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class LoyaltyKt {
    private static ImageVector _loyalty;

    public static final ImageVector getLoyalty(Icons.Sharp $this$Loyalty) {
        if (_loyalty != null) {
            ImageVector imageVector = _loyalty;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_Loyalty__u24lambda_u241 = new ImageVector.Builder("Sharp.Loyalty", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(11.83f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineTo(2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(9.83f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(10.99f, 11.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveToRelative(1.05f, -1.05f, 1.41f, -1.42f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(22.82f, 13.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(11.83f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(5.5f, 7.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(4.67f, 7.0f, 4.0f, 6.33f, 4.0f, 5.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveTo(4.67f, 4.0f, 5.5f, 4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveTo(7.0f, 4.67f, 7.0f, 5.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveTo(6.33f, 7.0f, 5.5f, 7.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(13.0f, 19.54f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-4.27f, -4.27f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(8.28f, 14.81f, 8.0f, 14.19f, 8.0f, 13.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, -1.38f, 1.12f, -2.5f, 2.5f, -2.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.69f, 0.0f, 1.32f, 0.28f, 1.77f, 0.74f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(0.73f, 0.72f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(0.73f, -0.73f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.45f, -0.45f, 1.08f, -0.73f, 1.77f, -0.73f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(1.38f, 0.0f, 2.5f, 1.12f, 2.5f, 2.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, 0.69f, -0.28f, 1.32f, -0.73f, 1.77f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(13.0f, 19.54f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _loyalty = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_Loyalty__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _loyalty;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
