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
import kotlin.Deprecated;
import kotlin.Metadata;
import kotlin.ReplaceWith;
import kotlin.jvm.internal.Intrinsics;

/* compiled from: DirectionsRun.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0005\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u001e\u0010\u0002\u001a\u00020\u0001*\u00020\u00038FX\u0087\u0004¢\u0006\f\u0012\u0004\b\u0004\u0010\u0005\u001a\u0004\b\u0006\u0010\u0007¨\u0006\b"}, d2 = {"_directionsRun", "Landroidx/compose/ui/graphics/vector/ImageVector;", "DirectionsRun", "Landroidx/compose/material/icons/Icons$Filled;", "getDirectionsRun$annotations", "(Landroidx/compose/material/icons/Icons$Filled;)V", "getDirectionsRun", "(Landroidx/compose/material/icons/Icons$Filled;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class DirectionsRunKt {
    private static ImageVector _directionsRun;

    @Deprecated(message = "Use the AutoMirrored version at Icons.AutoMirrored.Filled.DirectionsRun", replaceWith = @ReplaceWith(expression = "Icons.AutoMirrored.Filled.DirectionsRun", imports = {"androidx.compose.material.icons.automirrored.filled.DirectionsRun"}))
    public static /* synthetic */ void getDirectionsRun$annotations(Icons.Filled filled) {
    }

    public static final ImageVector getDirectionsRun(Icons.Filled $this$DirectionsRun) {
        if (_directionsRun != null) {
            ImageVector imageVector = _directionsRun;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_DirectionsRun__u24lambda_u241 = new ImageVector.Builder("Filled.DirectionsRun", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(13.49f, 5.48f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(1.1f, 0.0f, 2.0f, -0.9f, 2.0f, -2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveToRelative(-0.9f, -2.0f, -2.0f, -2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveToRelative(-2.0f, 0.9f, -2.0f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveToRelative(0.9f, 2.0f, 2.0f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(9.89f, 19.38f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.0f, -4.4f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(2.1f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(6.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(-7.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-2.1f, -2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(0.6f, -3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(1.3f, 1.5f, 3.3f, 2.5f, 5.5f, 2.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(-2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-1.9f, 0.0f, -3.5f, -1.0f, -4.3f, -2.4f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-1.0f, -1.6f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.4f, -0.6f, -1.0f, -1.0f, -1.7f, -1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.3f, 0.0f, -0.5f, 0.1f, -0.8f, 0.1f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-5.2f, 2.2f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(4.7f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(-3.4f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.8f, -0.7f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-1.6f, 8.1f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-4.9f, -1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-0.4f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(7.0f, 1.4f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _directionsRun = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_DirectionsRun__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _directionsRun;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
