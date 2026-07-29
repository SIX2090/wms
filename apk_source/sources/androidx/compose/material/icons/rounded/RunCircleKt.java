package androidx.compose.material.icons.rounded;

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

/* compiled from: RunCircle.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_runCircle", "Landroidx/compose/ui/graphics/vector/ImageVector;", "RunCircle", "Landroidx/compose/material/icons/Icons$Rounded;", "getRunCircle", "(Landroidx/compose/material/icons/Icons$Rounded;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class RunCircleKt {
    private static ImageVector _runCircle;

    public static final ImageVector getRunCircle(Icons.Rounded $this$RunCircle) {
        if (_runCircle != null) {
            ImageVector imageVector = _runCircle;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_RunCircle__u24lambda_u241 = new ImageVector.Builder("Rounded.RunCircle", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(12.0f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(6.48f, 2.0f, 2.0f, 6.48f, 2.0f, 12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, 5.52f, 4.48f, 10.0f, 10.0f, 10.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveToRelative(10.0f, -4.48f, 10.0f, -10.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(22.0f, 6.48f, 17.52f, 2.0f, 12.0f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(13.5f, 6.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.55f, 0.0f, 1.0f, 0.45f, 1.0f, 1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, 0.55f, -0.45f, 1.0f, -1.0f, 1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveToRelative(-1.0f, -0.45f, -1.0f, -1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(12.5f, 6.45f, 12.95f, 6.0f, 13.5f, 6.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(15.41f, 11.91f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.71f, -0.2f, -1.63f, -0.74f, -2.32f, -1.66f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-0.41f, 2.35f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.19f, 1.3f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(13.95f, 13.98f, 14.0f, 14.1f, 14.0f, 14.22f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(3.28f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, 0.28f, -0.22f, 0.5f, -0.5f, 0.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.28f, 0.0f, -0.5f, -0.22f, -0.5f, -0.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(-3.08f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-1.11f, -1.21f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-0.43f, 2.15f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.05f, 0.27f, -0.32f, 0.45f, -0.59f, 0.39f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-2.78f, -0.57f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.27f, -0.06f, -0.45f, -0.32f, -0.39f, -0.59f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.06f, -0.27f, 0.32f, -0.44f, 0.59f, -0.39f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(2.29f, 0.47f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(0.96f, -4.89f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(10.0f, 10.35f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(1.15f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, 0.28f, -0.22f, 0.5f, -0.5f, 0.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(9.22f, 12.0f, 9.0f, 11.78f, 9.0f, 11.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(10.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, -0.21f, 0.13f, -0.4f, 0.33f, -0.47f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(2.95f, -1.09f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.49f, -0.18f, 1.02f, 0.04f, 1.25f, 0.51f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.65f, 1.35f, 1.55f, 1.85f, 2.1f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(15.85f, 11.0f, 16.0f, 11.18f, 16.0f, 11.4f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(0.04f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(16.0f, 11.75f, 15.71f, 11.99f, 15.41f, 11.91f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _runCircle = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_RunCircle__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _runCircle;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
