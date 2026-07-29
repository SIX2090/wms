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

/* compiled from: Icecream.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_icecream", "Landroidx/compose/ui/graphics/vector/ImageVector;", "Icecream", "Landroidx/compose/material/icons/Icons$Rounded;", "getIcecream", "(Landroidx/compose/material/icons/Icons$Rounded;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class IcecreamKt {
    private static ImageVector _icecream;

    public static final ImageVector getIcecream(Icons.Rounded $this$Icecream) {
        if (_icecream != null) {
            ImageVector imageVector = _icecream;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_Icecream__u24lambda_u241 = new ImageVector.Builder("Rounded.Icecream", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(18.38f, 6.24f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(17.79f, 3.24f, 15.14f, 1.0f, 12.0f, 1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveTo(6.21f, 3.24f, 5.62f, 6.24f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(4.08f, 6.81f, 3.0f, 8.29f, 3.0f, 10.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, 2.21f, 1.79f, 4.0f, 4.0f, 4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.12f, 0.0f, 0.23f, -0.02f, 0.34f, -0.02f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(3.83f, 7.31f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.38f, 0.72f, 1.41f, 0.71f, 1.78f, -0.01f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(3.73f, -7.31f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(16.79f, 13.98f, 16.89f, 14.0f, 17.0f, 14.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(2.21f, 0.0f, 4.0f, -1.79f, 4.0f, -4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(21.0f, 8.29f, 19.92f, 6.81f, 18.38f, 6.24f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(12.05f, 18.63f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-2.73f, -5.21f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(10.15f, 13.79f, 11.06f, 14.0f, 12.0f, 14.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.95f, 0.0f, 1.88f, -0.21f, 2.72f, -0.6f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(12.05f, 18.63f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _icecream = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_Icecream__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _icecream;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
