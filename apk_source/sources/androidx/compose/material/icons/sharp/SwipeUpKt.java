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
import kotlin.Metadata;
import kotlin.jvm.internal.Intrinsics;

/* compiled from: SwipeUp.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_swipeUp", "Landroidx/compose/ui/graphics/vector/ImageVector;", "SwipeUp", "Landroidx/compose/material/icons/Icons$Sharp;", "getSwipeUp", "(Landroidx/compose/material/icons/Icons$Sharp;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class SwipeUpKt {
    private static ImageVector _swipeUp;

    public static final ImageVector getSwipeUp(Icons.Sharp $this$SwipeUp) {
        if (_swipeUp != null) {
            ImageVector imageVector = _swipeUp;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_SwipeUp__u24lambda_u241 = new ImageVector.Builder("Sharp.SwipeUp", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(2.06f, 5.56f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(1.0f, 4.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(4.5f, 1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(8.0f, 4.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(6.94f, 5.56f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(5.32f, 3.94f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(5.11f, 4.76f, 5.0f, 5.62f, 5.0f, 6.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, 2.42f, 0.82f, 4.65f, 2.2f, 6.43f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(6.13f, 14.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(4.49f, 11.95f, 3.5f, 9.34f, 3.5f, 6.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, -0.92f, 0.1f, -1.82f, 0.3f, -2.68f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(2.06f, 5.56f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(21.71f, 11.18f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(2.09f, 7.39f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-8.23f, 3.65f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-6.84f, -2.85f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(0.61f, -1.62f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(3.8f, -0.75f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(8.79f, 7.17f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.34f, -0.76f, 0.0f, -1.64f, 0.76f, -1.98f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.76f, -0.34f, 1.64f, 0.0f, 1.98f, 0.76f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(2.43f, 5.49f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.26f, -0.56f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(21.71f, 11.18f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _swipeUp = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_SwipeUp__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _swipeUp;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
