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

/* compiled from: ScreenRotation.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_screenRotation", "Landroidx/compose/ui/graphics/vector/ImageVector;", "ScreenRotation", "Landroidx/compose/material/icons/Icons$Sharp;", "getScreenRotation", "(Landroidx/compose/material/icons/Icons$Sharp;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class ScreenRotationKt {
    private static ImageVector _screenRotation;

    public static final ImageVector getScreenRotation(Icons.Sharp $this$ScreenRotation) {
        if (_screenRotation != null) {
            ImageVector imageVector = _screenRotation;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_ScreenRotation__u24lambda_u241 = new ImageVector.Builder("Sharp.ScreenRotation", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(16.48f, 2.52f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(3.27f, 1.55f, 5.61f, 4.72f, 5.97f, 8.48f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(1.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(23.44f, 4.84f, 18.29f, 0.0f, 12.0f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-0.66f, 0.03f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(3.81f, 3.81f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.33f, -1.32f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(7.52f, 21.48f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(4.25f, 19.94f, 1.91f, 16.76f, 1.55f, 13.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(0.05f, 13.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(0.56f, 19.16f, 5.71f, 24.0f, 12.0f, 24.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(0.66f, -0.03f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-3.81f, -3.81f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-1.33f, 1.32f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(9.17f, 0.69f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(0.69f, 9.17f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(14.14f, 14.14f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(8.48f, -8.48f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(9.17f, 0.69f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(14.83f, 21.19f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(2.81f, 9.17f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(6.36f, -6.36f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(12.02f, 12.02f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-6.36f, 6.36f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _screenRotation = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_ScreenRotation__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _screenRotation;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
