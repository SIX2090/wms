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

/* compiled from: Update.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_update", "Landroidx/compose/ui/graphics/vector/ImageVector;", "Update", "Landroidx/compose/material/icons/Icons$Filled;", "getUpdate", "(Landroidx/compose/material/icons/Icons$Filled;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class UpdateKt {
    private static ImageVector _update;

    public static final ImageVector getUpdate(Icons.Filled $this$Update) {
        if (_update != null) {
            ImageVector imageVector = _update;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_Update__u24lambda_u241 = new ImageVector.Builder("Filled.Update", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(21.0f, 10.12f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(-6.78f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(2.74f, -2.82f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-2.73f, -2.7f, -7.15f, -2.8f, -9.88f, -0.1f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-2.73f, 2.71f, -2.73f, 7.08f, 0.0f, 9.79f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveToRelative(7.15f, 2.71f, 9.88f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(18.32f, 15.65f, 19.0f, 14.08f, 19.0f, 12.1f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, 1.98f, -0.88f, 4.55f, -2.64f, 6.29f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-3.51f, 3.48f, -9.21f, 3.48f, -12.72f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-3.5f, -3.47f, -3.53f, -9.11f, -0.02f, -12.58f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveToRelative(9.14f, -3.47f, 12.65f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(21.0f, 3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(10.12f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(12.5f, 8.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(4.25f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(3.5f, 2.08f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-0.72f, 1.21f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(11.0f, 13.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(8.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineTo(12.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _update = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_Update__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _update;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
