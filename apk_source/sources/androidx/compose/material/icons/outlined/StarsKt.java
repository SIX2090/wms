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

/* compiled from: Stars.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_stars", "Landroidx/compose/ui/graphics/vector/ImageVector;", "Stars", "Landroidx/compose/material/icons/Icons$Outlined;", "getStars", "(Landroidx/compose/material/icons/Icons$Outlined;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class StarsKt {
    private static ImageVector _stars;

    public static final ImageVector getStars(Icons.Outlined $this$Stars) {
        if (_stars != null) {
            ImageVector imageVector = _stars;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_Stars__u24lambda_u241 = new ImageVector.Builder("Outlined.Stars", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(11.99f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(6.47f, 2.0f, 2.0f, 6.48f, 2.0f, 12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveToRelative(4.47f, 10.0f, 9.99f, 10.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(17.52f, 22.0f, 22.0f, 17.52f, 22.0f, 12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveTo(17.52f, 2.0f, 11.99f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(19.47f, 9.16f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-5.01f, -0.43f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-2.0f, -4.71f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(3.21f, 0.19f, 5.91f, 2.27f, 7.01f, 5.14f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(14.4f, 15.42f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(12.0f, 13.98f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-2.39f, 1.44f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(0.63f, -2.72f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-2.11f, -1.83f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(2.78f, -0.24f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(12.0f, 8.06f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.09f, 2.56f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(2.78f, 0.24f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-2.11f, 1.83f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(0.64f, 2.73f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(11.54f, 4.02f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-2.0f, 4.72f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-5.02f, 0.43f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(1.1f, -2.88f, 3.8f, -4.97f, 7.02f, -5.15f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(4.0f, 12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, -0.64f, 0.08f, -1.26f, 0.23f, -1.86f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(3.79f, 3.28f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-1.11f, 4.75f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(5.13f, 16.7f, 4.0f, 14.48f, 4.0f, 12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(7.84f, 18.82f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(12.0f, 16.31f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(4.16f, 2.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-1.22f, 0.75f, -2.64f, 1.19f, -4.17f, 1.19f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-1.52f, 0.0f, -2.94f, -0.44f, -4.15f, -1.18f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(17.09f, 18.17f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-1.11f, -4.75f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(3.79f, -3.28f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.14f, 0.59f, 0.23f, 1.22f, 0.23f, 1.86f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, 2.48f, -1.14f, 4.7f, -2.91f, 6.17f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _stars = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_Stars__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _stars;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
