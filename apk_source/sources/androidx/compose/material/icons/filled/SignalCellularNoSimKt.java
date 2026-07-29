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

/* compiled from: SignalCellularNoSim.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_signalCellularNoSim", "Landroidx/compose/ui/graphics/vector/ImageVector;", "SignalCellularNoSim", "Landroidx/compose/material/icons/Icons$Filled;", "getSignalCellularNoSim", "(Landroidx/compose/material/icons/Icons$Filled;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class SignalCellularNoSimKt {
    private static ImageVector _signalCellularNoSim;

    public static final ImageVector getSignalCellularNoSim(Icons.Filled $this$SignalCellularNoSim) {
        if (_signalCellularNoSim != null) {
            ImageVector imageVector = _signalCellularNoSim;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_SignalCellularNoSim__u24lambda_u241 = new ImageVector.Builder("Filled.SignalCellularNoSim", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(18.99f, 5.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, -1.1f, -0.89f, -2.0f, -1.99f, -2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(-7.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(7.66f, 5.34f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(19.0f, 16.68f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(18.99f, 5.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(3.65f, 3.88f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(2.38f, 5.15f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(5.0f, 7.77f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(19.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, 1.1f, 0.9f, 2.0f, 2.0f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(10.01f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.35f, 0.0f, 0.67f, -0.1f, 0.96f, -0.26f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.88f, 1.88f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.27f, -1.27f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(3.65f, 3.88f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _signalCellularNoSim = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_SignalCellularNoSim__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _signalCellularNoSim;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
