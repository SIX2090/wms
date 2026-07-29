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

/* compiled from: Park.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_park", "Landroidx/compose/ui/graphics/vector/ImageVector;", "Park", "Landroidx/compose/material/icons/Icons$Rounded;", "getPark", "(Landroidx/compose/material/icons/Icons$Rounded;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class ParkKt {
    private static ImageVector _park;

    public static final ImageVector getPark(Icons.Rounded $this$Park) {
        if (_park != null) {
            ImageVector imageVector = _park;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_Park__u24lambda_u241 = new ImageVector.Builder("Rounded.Park", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(16.96f, 12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(0.08f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.81f, 0.0f, 1.28f, -0.91f, 0.82f, -1.57f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-5.08f, -7.25f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.4f, -0.57f, -1.24f, -0.57f, -1.64f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(6.1f, 10.43f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(5.64f, 11.09f, 6.12f, 12.0f, 6.93f, 12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(0.04f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-2.9f, 4.46f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(3.63f, 17.12f, 4.11f, 18.0f, 4.91f, 18.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(5.08f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(2.02f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, 1.09f, 0.89f, 1.98f, 1.98f, 1.98f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(1.09f, 0.0f, 1.98f, -0.89f, 1.98f, -1.98f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(18.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(5.15f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.8f, 0.0f, 1.28f, -0.89f, 0.83f, -1.55f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(16.96f, 12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _park = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_Park__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _park;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
