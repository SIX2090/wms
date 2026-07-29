package androidx.compose.material.icons.filled;

import androidx.compose.material.icons.Icons;
import androidx.compose.ui.graphics.Brush;
import androidx.compose.ui.graphics.Color;
import androidx.compose.ui.graphics.PathFillType;
import androidx.compose.ui.graphics.SolidColor;
import androidx.compose.ui.graphics.StrokeCap;
import androidx.compose.ui.graphics.StrokeJoin;
import androidx.compose.ui.graphics.vector.ImageVector;
import androidx.compose.ui.graphics.vector.PathBuilder;
import androidx.compose.ui.unit.Dp;
import kotlin.Metadata;
import kotlin.jvm.internal.Intrinsics;

/* compiled from: Icecream.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_icecream", "Landroidx/compose/ui/graphics/vector/ImageVector;", "Icecream", "Landroidx/compose/material/icons/Icons$Filled;", "getIcecream", "(Landroidx/compose/material/icons/Icons$Filled;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class IcecreamKt {
    private static ImageVector _icecream;

    public static final ImageVector getIcecream(Icons.Filled $this$Icecream) {
        if (_icecream != null) {
            ImageVector imageVector = _icecream;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_Icecream__u24lambda_u241 = new ImageVector.Builder("Filled.Icecream", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = PathFillType.INSTANCE.m4028getEvenOddRgk1Os();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(8.79f, 12.4f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(3.26f, 6.22f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(3.17f, -6.21f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.11f, -0.08f, -0.21f, -0.16f, -0.3f, -0.25f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(14.08f, 12.69f, 13.07f, 13.0f, 12.0f, 13.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveToRelative(-2.08f, -0.31f, -2.92f, -0.84f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(8.99f, 12.25f, 8.89f, 12.33f, 8.79f, 12.4f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(6.83f, 12.99f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(5.25f, 12.9f, 4.0f, 11.6f, 4.0f, 10.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, -1.49f, 1.09f, -2.73f, 2.52f, -2.96f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(6.75f, 4.22f, 9.12f, 2.0f, 12.0f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveToRelative(5.25f, 2.22f, 5.48f, 5.04f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(18.91f, 7.27f, 20.0f, 8.51f, 20.0f, 10.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, 1.59f, -1.24f, 2.9f, -2.81f, 2.99f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(12.07f, 23.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(6.83f, 12.99f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _icecream = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_Icecream__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _icecream;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
