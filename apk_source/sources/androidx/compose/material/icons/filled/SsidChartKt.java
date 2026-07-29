package androidx.compose.material.icons.filled;

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

/* compiled from: SsidChart.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_ssidChart", "Landroidx/compose/ui/graphics/vector/ImageVector;", "SsidChart", "Landroidx/compose/material/icons/Icons$Filled;", "getSsidChart", "(Landroidx/compose/material/icons/Icons$Filled;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class SsidChartKt {
    private static ImageVector _ssidChart;

    public static final ImageVector getSsidChart(Icons.Filled $this$SsidChart) {
        if (_ssidChart != null) {
            ImageVector imageVector = _ssidChart;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_SsidChart__u24lambda_u241 = new ImageVector.Builder("Filled.SsidChart", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(21.0f, 5.47f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(12.0f, 12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(7.62f, 7.62f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(3.0f, 11.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(8.52f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(7.83f, 5.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(4.38f, 4.38f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(21.0f, 3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(21.0f, 5.47f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(21.0f, 15.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(-4.7f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-4.17f, 3.34f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(6.0f, 12.41f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-3.0f, 2.13f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(3.0f, 17.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(2.8f, -2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(6.2f, 6.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(5.0f, -4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(15.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _ssidChart = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_SsidChart__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _ssidChart;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
