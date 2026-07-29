package androidx.compose.material.icons.twotone;

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

/* compiled from: FlightLand.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_flightLand", "Landroidx/compose/ui/graphics/vector/ImageVector;", "FlightLand", "Landroidx/compose/material/icons/Icons$TwoTone;", "getFlightLand", "(Landroidx/compose/material/icons/Icons$TwoTone;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class FlightLandKt {
    private static ImageVector _flightLand;

    public static final ImageVector getFlightLand(Icons.TwoTone $this$FlightLand) {
        if (_flightLand != null) {
            ImageVector imageVector = _flightLand;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_FlightLand__u24lambda_u241 = new ImageVector.Builder("TwoTone.FlightLand", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(2.5f, 19.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(19.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(-19.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(-2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(19.34f, 15.85f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.8f, 0.21f, 1.62f, -0.26f, 1.84f, -1.06f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.21f, -0.8f, -0.26f, -1.62f, -1.06f, -1.84f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-5.31f, -1.42f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-2.76f, -9.02f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(10.12f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(8.28f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(5.15f, 8.95f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-0.93f, -2.32f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-1.45f, -0.39f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(5.17f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(16.57f, 4.44f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _flightLand = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_FlightLand__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _flightLand;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
