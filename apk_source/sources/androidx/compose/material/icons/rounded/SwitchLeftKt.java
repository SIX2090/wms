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

/* compiled from: SwitchLeft.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_switchLeft", "Landroidx/compose/ui/graphics/vector/ImageVector;", "SwitchLeft", "Landroidx/compose/material/icons/Icons$Rounded;", "getSwitchLeft", "(Landroidx/compose/material/icons/Icons$Rounded;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class SwitchLeftKt {
    private static ImageVector _switchLeft;

    public static final ImageVector getSwitchLeft(Icons.Rounded $this$SwitchLeft) {
        if (_switchLeft != null) {
            ImageVector imageVector = _switchLeft;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_SwitchLeft__u24lambda_u241 = new ImageVector.Builder("Rounded.SwitchLeft", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(8.5f, 8.62f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(6.76f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(5.12f, 12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(8.5f, 8.62f);
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(3.71f, 11.29f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.39f, 0.39f, -0.39f, 1.02f, 0.0f, 1.41f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(4.59f, 4.59f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(8.92f, 17.92f, 10.0f, 17.48f, 10.0f, 16.59f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(7.41f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, -0.89f, -1.08f, -1.34f, -1.71f, -0.71f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(3.71f, 11.29f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(14.0f, 7.41f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(9.17f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, 0.89f, 1.08f, 1.34f, 1.71f, 0.71f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(4.59f, -4.59f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.39f, -0.39f, 0.39f, -1.02f, 0.0f, -1.41f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-4.59f, -4.59f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(15.08f, 6.08f, 14.0f, 6.52f, 14.0f, 7.41f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _switchLeft = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_SwitchLeft__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _switchLeft;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
