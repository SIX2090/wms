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

/* compiled from: StackedLineChart.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_stackedLineChart", "Landroidx/compose/ui/graphics/vector/ImageVector;", "StackedLineChart", "Landroidx/compose/material/icons/Icons$Rounded;", "getStackedLineChart", "(Landroidx/compose/material/icons/Icons$Rounded;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class StackedLineChartKt {
    private static ImageVector _stackedLineChart;

    public static final ImageVector getStackedLineChart(Icons.Rounded $this$StackedLineChart) {
        if (_stackedLineChart != null) {
            ImageVector imageVector = _stackedLineChart;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_StackedLineChart__u24lambda_u241 = new ImageVector.Builder("Rounded.StackedLineChart", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(2.79f, 14.78f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(2.7f, 14.69f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.39f, -0.39f, -0.39f, -1.02f, 0.0f, -1.41f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(6.09f, -6.1f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.39f, -0.39f, 1.02f, -0.39f, 1.41f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(3.29f, 3.29f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(6.39f, -7.18f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.38f, -0.43f, 1.05f, -0.44f, 1.45f, -0.04f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(0.0f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.37f, 0.38f, 0.39f, 0.98f, 0.04f, 1.37f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-7.17f, 8.07f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.38f, 0.43f, -1.04f, 0.45f, -1.45f, 0.04f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(9.5f, 9.48f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-5.3f, 5.3f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(3.82f, 15.17f, 3.18f, 15.17f, 2.79f, 14.78f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(4.2f, 20.78f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(5.3f, -5.3f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(3.25f, 3.25f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.41f, 0.41f, 1.07f, 0.39f, 1.45f, -0.04f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(7.17f, -8.07f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.35f, -0.39f, 0.33f, -0.99f, -0.04f, -1.37f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(0.0f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.4f, -0.4f, -1.07f, -0.39f, -1.45f, 0.04f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-6.39f, 7.18f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-3.29f, -3.29f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.39f, -0.39f, -1.02f, -0.39f, -1.41f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-6.09f, 6.1f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.39f, 0.39f, -0.39f, 1.02f, 0.0f, 1.41f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(0.09f, 0.09f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(3.18f, 21.17f, 3.82f, 21.17f, 4.2f, 20.78f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _stackedLineChart = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_StackedLineChart__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _stackedLineChart;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
