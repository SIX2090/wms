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

/* compiled from: Flight.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_flight", "Landroidx/compose/ui/graphics/vector/ImageVector;", "Flight", "Landroidx/compose/material/icons/Icons$Rounded;", "getFlight", "(Landroidx/compose/material/icons/Icons$Rounded;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class FlightKt {
    private static ImageVector _flight;

    public static final ImageVector getFlight(Icons.Rounded $this$Flight) {
        if (_flight != null) {
            ImageVector imageVector = _flight;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_Flight__u24lambda_u241 = new ImageVector.Builder("Rounded.Flight", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(21.0f, 14.58f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, -0.36f, -0.19f, -0.69f, -0.49f, -0.89f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(13.0f, 9.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(3.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, -0.83f, -0.67f, -1.5f, -1.5f, -1.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveTo(10.0f, 2.67f, 10.0f, 3.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(9.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-7.51f, 4.69f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.3f, 0.19f, -0.49f, 0.53f, -0.49f, 0.89f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, 0.7f, 0.68f, 1.21f, 1.36f, 1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(10.0f, 13.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(19.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-1.8f, 1.35f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.13f, 0.09f, -0.2f, 0.24f, -0.2f, 0.4f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(0.59f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, 0.33f, 0.32f, 0.57f, 0.64f, 0.48f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(11.5f, 21.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(2.86f, 0.82f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.32f, 0.09f, 0.64f, -0.15f, 0.64f, -0.48f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(-0.59f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, -0.16f, -0.07f, -0.31f, -0.2f, -0.4f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(13.0f, 19.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(-5.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(6.64f, 2.08f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.68f, 0.21f, 1.36f, -0.3f, 1.36f, -1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _flight = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_Flight__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _flight;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
