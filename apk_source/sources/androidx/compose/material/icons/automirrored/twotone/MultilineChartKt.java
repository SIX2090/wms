package androidx.compose.material.icons.automirrored.twotone;

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

/* compiled from: MultilineChart.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_multilineChart", "Landroidx/compose/ui/graphics/vector/ImageVector;", "MultilineChart", "Landroidx/compose/material/icons/Icons$AutoMirrored$TwoTone;", "getMultilineChart", "(Landroidx/compose/material/icons/Icons$AutoMirrored$TwoTone;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class MultilineChartKt {
    private static ImageVector _multilineChart;

    public static final ImageVector getMultilineChart(Icons.AutoMirrored.TwoTone $this$MultilineChart) {
        if (_multilineChart != null) {
            ImageVector imageVector = _multilineChart;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_MultilineChart__u24lambda_u241 = new ImageVector.Builder("AutoMirrored.TwoTone.MultilineChart", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, true, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(22.0f, 6.92f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-1.41f, -1.41f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-2.85f, 3.21f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(15.68f, 6.4f, 12.83f, 5.0f, 9.61f, 5.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(6.72f, 5.0f, 4.07f, 6.16f, 2.0f, 8.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.42f, 1.42f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(5.12f, 7.93f, 7.27f, 7.0f, 9.61f, 7.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(2.74f, 0.0f, 5.09f, 1.26f, 6.77f, 3.24f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-2.88f, 3.24f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-4.0f, -4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(2.0f, 16.99f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.5f, 1.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(6.0f, -6.01f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(4.0f, 4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(4.05f, -4.55f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.75f, 1.35f, 1.25f, 2.9f, 1.44f, 4.55f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineTo(21.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.22f, -2.3f, -0.95f, -4.39f, -2.04f, -6.14f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(22.0f, 6.92f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _multilineChart = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_MultilineChart__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _multilineChart;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
