package androidx.compose.material.icons.automirrored.rounded;

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

/* compiled from: StarHalf.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_starHalf", "Landroidx/compose/ui/graphics/vector/ImageVector;", "StarHalf", "Landroidx/compose/material/icons/Icons$AutoMirrored$Rounded;", "getStarHalf", "(Landroidx/compose/material/icons/Icons$AutoMirrored$Rounded;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class StarHalfKt {
    private static ImageVector _starHalf;

    public static final ImageVector getStarHalf(Icons.AutoMirrored.Rounded $this$StarHalf) {
        if (_starHalf != null) {
            ImageVector imageVector = _starHalf;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_StarHalf__u24lambda_u241 = new ImageVector.Builder("AutoMirrored.Rounded.StarHalf", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, true, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(19.65f, 9.04f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-4.84f, -0.42f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-1.89f, -4.45f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.34f, -0.81f, -1.5f, -0.81f, -1.84f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(9.19f, 8.63f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-4.83f, 0.41f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.88f, 0.07f, -1.24f, 1.17f, -0.57f, 1.75f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(3.67f, 3.18f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-1.1f, 4.72f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.2f, 0.86f, 0.73f, 1.54f, 1.49f, 1.08f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(4.15f, -2.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(4.15f, 2.51f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.76f, 0.46f, 1.69f, -0.22f, 1.49f, -1.08f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-1.1f, -4.73f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(3.67f, -3.18f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.67f, -0.58f, 0.32f, -1.68f, -0.56f, -1.75f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(12.0f, 15.4f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(6.1f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.71f, 4.04f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(4.38f, 0.38f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-3.32f, 2.88f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.0f, 4.28f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(12.0f, 15.4f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _starHalf = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_StarHalf__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _starHalf;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
