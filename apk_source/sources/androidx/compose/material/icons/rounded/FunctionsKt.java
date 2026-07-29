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

/* compiled from: Functions.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_functions", "Landroidx/compose/ui/graphics/vector/ImageVector;", "Functions", "Landroidx/compose/material/icons/Icons$Rounded;", "getFunctions", "(Landroidx/compose/material/icons/Icons$Rounded;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class FunctionsKt {
    private static ImageVector _functions;

    public static final ImageVector getFunctions(Icons.Rounded $this$Functions) {
        if (_functions != null) {
            ImageVector imageVector = _functions;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_Functions__u24lambda_u241 = new ImageVector.Builder("Rounded.Functions", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(16.5f, 4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineTo(7.56f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(6.7f, 4.0f, 6.0f, 4.7f, 6.0f, 5.56f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, 0.28f, 0.12f, 0.55f, 0.32f, 0.74f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(12.5f, 12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-6.18f, 5.7f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.2f, 0.19f, -0.32f, 0.46f, -0.32f, 0.74f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(6.0f, 19.3f, 6.7f, 20.0f, 7.56f, 20.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(8.94f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.83f, 0.0f, 1.5f, -0.67f, 1.5f, -1.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveToRelative(-0.67f, -1.5f, -1.5f, -1.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineTo(11.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(3.59f, -3.59f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.78f, -0.78f, 0.78f, -2.05f, 0.0f, -2.83f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(11.0f, 7.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(5.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.83f, 0.0f, 1.5f, -0.67f, 1.5f, -1.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveTo(17.33f, 4.0f, 16.5f, 4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _functions = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_Functions__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _functions;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
