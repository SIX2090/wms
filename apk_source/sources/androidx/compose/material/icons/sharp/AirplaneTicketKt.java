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
import kotlin.Deprecated;
import kotlin.Metadata;
import kotlin.ReplaceWith;
import kotlin.jvm.internal.Intrinsics;

/* compiled from: AirplaneTicket.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0005\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u001e\u0010\u0002\u001a\u00020\u0001*\u00020\u00038FX\u0087\u0004¢\u0006\f\u0012\u0004\b\u0004\u0010\u0005\u001a\u0004\b\u0006\u0010\u0007¨\u0006\b"}, d2 = {"_airplaneTicket", "Landroidx/compose/ui/graphics/vector/ImageVector;", "AirplaneTicket", "Landroidx/compose/material/icons/Icons$Sharp;", "getAirplaneTicket$annotations", "(Landroidx/compose/material/icons/Icons$Sharp;)V", "getAirplaneTicket", "(Landroidx/compose/material/icons/Icons$Sharp;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class AirplaneTicketKt {
    private static ImageVector _airplaneTicket;

    @Deprecated(message = "Use the AutoMirrored version at Icons.AutoMirrored.Sharp.AirplaneTicket", replaceWith = @ReplaceWith(expression = "Icons.AutoMirrored.Sharp.AirplaneTicket", imports = {"androidx.compose.material.icons.automirrored.sharp.AirplaneTicket"}))
    public static /* synthetic */ void getAirplaneTicket$annotations(Icons.Sharp sharp) {
    }

    public static final ImageVector getAirplaneTicket(Icons.Sharp $this$AirplaneTicket) {
        if (_airplaneTicket != null) {
            ImageVector imageVector = _airplaneTicket;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_AirplaneTicket__u24lambda_u241 = new ImageVector.Builder("Sharp.AirplaneTicket", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(22.0f, 4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineTo(2.01f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(6.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(3.11f, 10.0f, 4.0f, 10.9f, 4.0f, 12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveToRelative(-0.89f, 2.0f, -2.0f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(6.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(20.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(17.73f, 13.3f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-8.86f, 2.36f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-1.66f, -2.88f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(0.93f, -0.25f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.26f, 0.99f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(2.39f, -0.64f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-2.4f, -4.16f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.4f, -0.38f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(4.01f, 3.74f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(2.44f, -0.65f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.51f, -0.14f, 1.04f, 0.17f, 1.18f, 0.68f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(18.55f, 12.62f, 18.25f, 13.15f, 17.73f, 13.3f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _airplaneTicket = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_AirplaneTicket__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _airplaneTicket;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
