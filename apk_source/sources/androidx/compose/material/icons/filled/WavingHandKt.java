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

/* compiled from: WavingHand.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_wavingHand", "Landroidx/compose/ui/graphics/vector/ImageVector;", "WavingHand", "Landroidx/compose/material/icons/Icons$Filled;", "getWavingHand", "(Landroidx/compose/material/icons/Icons$Filled;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class WavingHandKt {
    private static ImageVector _wavingHand;

    public static final ImageVector getWavingHand(Icons.Filled $this$WavingHand) {
        if (_wavingHand != null) {
            ImageVector imageVector = _wavingHand;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_WavingHand__u24lambda_u241 = new ImageVector.Builder("Filled.WavingHand", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(23.0f, 17.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, 3.31f, -2.69f, 6.0f, -6.0f, 6.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(-1.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(2.48f, 0.0f, 4.5f, -2.02f, 4.5f, -4.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineTo(23.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(1.0f, 7.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, -3.31f, 2.69f, -6.0f, 6.0f, -6.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(1.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(4.52f, 2.5f, 2.5f, 4.52f, 2.5f, 7.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineTo(1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(8.01f, 4.32f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-4.6f, 4.6f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-3.22f, 3.22f, -3.22f, 8.45f, 0.0f, 11.67f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveToRelative(8.45f, 3.22f, 11.67f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(7.07f, -7.07f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.49f, -0.49f, 0.49f, -1.28f, 0.0f, -1.77f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.49f, -0.49f, -1.28f, -0.49f, -1.77f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-4.42f, 4.42f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-0.71f, -0.71f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(6.54f, -6.54f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.49f, -0.49f, 0.49f, -1.28f, 0.0f, -1.77f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveToRelative(-1.28f, -0.49f, -1.77f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-5.83f, 5.83f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-0.71f, -0.71f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(6.89f, -6.89f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.49f, -0.49f, 0.49f, -1.28f, 0.0f, -1.77f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveToRelative(-1.28f, -0.49f, -1.77f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-6.89f, 6.89f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(11.02f, 9.8f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(5.48f, -5.48f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.49f, -0.49f, 0.49f, -1.28f, 0.0f, -1.77f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveToRelative(-1.28f, -0.49f, -1.77f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-7.62f, 7.62f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(1.22f, 1.57f, 1.11f, 3.84f, -0.33f, 5.28f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-0.71f, -0.71f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(1.17f, -1.17f, 1.17f, -3.07f, 0.0f, -4.24f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-0.35f, -0.35f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(4.07f, -4.07f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.49f, -0.49f, 0.49f, -1.28f, 0.0f, -1.77f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(9.29f, 3.83f, 8.5f, 3.83f, 8.01f, 4.32f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _wavingHand = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_WavingHand__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _wavingHand;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
