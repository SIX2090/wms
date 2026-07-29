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

/* compiled from: AirlineSeatFlatAngled.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_airlineSeatFlatAngled", "Landroidx/compose/ui/graphics/vector/ImageVector;", "AirlineSeatFlatAngled", "Landroidx/compose/material/icons/Icons$Sharp;", "getAirlineSeatFlatAngled", "(Landroidx/compose/material/icons/Icons$Sharp;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class AirlineSeatFlatAngledKt {
    private static ImageVector _airlineSeatFlatAngled;

    public static final ImageVector getAirlineSeatFlatAngled(Icons.Sharp $this$AirlineSeatFlatAngled) {
        if (_airlineSeatFlatAngled != null) {
            ImageVector imageVector = _airlineSeatFlatAngled;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_AirlineSeatFlatAngled__u24lambda_u241 = new ImageVector.Builder("Sharp.AirlineSeatFlatAngled", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(21.56f, 16.18f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(9.2f, 11.71f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(2.08f, -5.66f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(12.35f, 4.47f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-2.07f, 5.66f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(1.5f, 12.14f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(8.0f, 14.48f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(8.0f, 19.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(8.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(-1.63f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(20.52f, 19.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(0.69f, -1.89f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-19.02f, -6.86f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-0.69f, 1.89f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(7.3f, 10.2f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(1.49f, -0.72f, 2.12f, -2.51f, 1.41f, -4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(7.99f, 4.71f, 6.2f, 4.08f, 4.7f, 4.8f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-1.49f, 0.71f, -2.12f, 2.5f, -1.4f, 4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.71f, 1.49f, 2.5f, 2.12f, 4.0f, 1.4f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _airlineSeatFlatAngled = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_AirlineSeatFlatAngled__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _airlineSeatFlatAngled;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
