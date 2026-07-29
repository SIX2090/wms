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

/* compiled from: SwipeVertical.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_swipeVertical", "Landroidx/compose/ui/graphics/vector/ImageVector;", "SwipeVertical", "Landroidx/compose/material/icons/Icons$Filled;", "getSwipeVertical", "(Landroidx/compose/material/icons/Icons$Filled;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class SwipeVerticalKt {
    private static ImageVector _swipeVertical;

    public static final ImageVector getSwipeVertical(Icons.Filled $this$SwipeVertical) {
        if (_swipeVertical != null) {
            ImageVector imageVector = _swipeVertical;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_SwipeVertical__u24lambda_u241 = new ImageVector.Builder("Filled.SwipeVertical", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(1.0f, 3.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(2.02f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(1.13f, 5.82f, 0.0f, 8.78f, 0.0f, 12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveToRelative(1.13f, 6.18f, 3.02f, 8.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineTo(1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(22.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(5.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(-5.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineTo(4.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(2.91f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-1.86f, -2.11f, -3.0f, -4.88f, -3.0f, -7.91f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveToRelative(1.14f, -5.79f, 3.0f, -7.91f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(7.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineTo(6.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineTo(1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(3.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(13.85f, 11.62f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-2.68f, -5.37f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.37f, -0.74f, -1.27f, -1.04f, -2.01f, -0.67f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(8.41f, 5.96f, 8.11f, 6.86f, 8.48f, 7.6f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(4.81f, 9.6f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(10.05f, 18.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.33f, 0.09f, -0.59f, 0.33f, -0.7f, 0.66f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(9.0f, 19.78f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(6.19f, 2.25f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.5f, 0.17f, 1.28f, 0.02f, 1.75f, -0.22f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(5.51f, -2.75f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.89f, -0.45f, 1.32f, -1.48f, 1.0f, -2.42f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-1.43f, -4.27f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.27f, -0.82f, -1.04f, -1.37f, -1.9f, -1.37f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(-4.56f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.31f, 0.0f, -0.62f, 0.07f, -0.89f, 0.21f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(13.85f, 11.62f);
        _swipeVertical = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_SwipeVertical__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _swipeVertical;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
