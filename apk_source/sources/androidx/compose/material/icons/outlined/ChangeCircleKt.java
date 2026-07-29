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

/* compiled from: ChangeCircle.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_changeCircle", "Landroidx/compose/ui/graphics/vector/ImageVector;", "ChangeCircle", "Landroidx/compose/material/icons/Icons$Outlined;", "getChangeCircle", "(Landroidx/compose/material/icons/Icons$Outlined;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class ChangeCircleKt {
    private static ImageVector _changeCircle;

    public static final ImageVector getChangeCircle(Icons.Outlined $this$ChangeCircle) {
        if (_changeCircle != null) {
            ImageVector imageVector = _changeCircle;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_ChangeCircle__u24lambda_u241 = new ImageVector.Builder("Outlined.ChangeCircle", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(12.0f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(6.48f, 2.0f, 2.0f, 6.48f, 2.0f, 12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveToRelative(4.48f, 10.0f, 10.0f, 10.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveToRelative(10.0f, -4.48f, 10.0f, -10.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveTo(17.52f, 2.0f, 12.0f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(12.0f, 20.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-4.41f, 0.0f, -8.0f, -3.59f, -8.0f, -8.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveToRelative(3.59f, -8.0f, 8.0f, -8.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveToRelative(8.0f, 3.59f, 8.0f, 8.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveTo(16.41f, 20.0f, 12.0f, 20.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(16.17f, 14.76f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-1.1f, -1.1f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.71f, -1.33f, 0.53f, -3.01f, -0.59f, -4.13f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(13.79f, 8.84f, 12.9f, 8.5f, 12.0f, 8.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.03f, 0.0f, -0.06f, 0.01f, -0.09f, 0.01f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(13.0f, 9.6f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-1.06f, 1.06f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(9.11f, 7.83f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(11.94f, 5.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(13.0f, 6.06f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-0.96f, 0.96f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(1.27f, 0.01f, 2.53f, 0.48f, 3.5f, 1.44f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(17.24f, 10.17f, 17.45f, 12.82f, 16.17f, 14.76f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(14.89f, 16.17f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(12.06f, 19.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(11.0f, 17.94f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(0.95f, -0.95f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-1.26f, -0.01f, -2.52f, -0.5f, -3.48f, -1.46f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-1.71f, -1.71f, -1.92f, -4.35f, -0.64f, -6.29f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.1f, 1.1f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.71f, 1.33f, -0.53f, 3.01f, 0.59f, 4.13f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.7f, 0.7f, 1.63f, 1.04f, 2.56f, 1.01f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(11.0f, 14.4f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.06f, -1.06f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(14.89f, 16.17f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _changeCircle = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_ChangeCircle__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _changeCircle;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
