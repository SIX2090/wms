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

/* compiled from: Directions.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_directions", "Landroidx/compose/ui/graphics/vector/ImageVector;", "Directions", "Landroidx/compose/material/icons/Icons$Filled;", "getDirections", "(Landroidx/compose/material/icons/Icons$Filled;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class DirectionsKt {
    private static ImageVector _directions;

    public static final ImageVector getDirections(Icons.Filled $this$Directions) {
        if (_directions != null) {
            ImageVector imageVector = _directions;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_Directions__u24lambda_u241 = new ImageVector.Builder("Filled.Directions", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(21.41f, 10.59f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-7.99f, -8.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.78f, -0.78f, -2.05f, -0.78f, -2.83f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-8.01f, 8.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.78f, 0.78f, -0.78f, 2.05f, 0.0f, 2.83f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(8.01f, 8.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.78f, 0.78f, 2.05f, 0.78f, 2.83f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(7.99f, -8.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(22.2f, 12.63f, 22.2f, 11.37f, 21.41f, 10.59f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(13.5f, 14.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineTo(10.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineTo(8.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(-4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, -0.55f, 0.45f, -1.0f, 1.0f, -1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(4.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(7.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(17.0f, 11.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(13.5f, 14.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _directions = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_Directions__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _directions;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
