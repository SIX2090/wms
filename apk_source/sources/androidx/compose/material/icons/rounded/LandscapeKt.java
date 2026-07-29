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

/* compiled from: Landscape.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_landscape", "Landroidx/compose/ui/graphics/vector/ImageVector;", "Landscape", "Landroidx/compose/material/icons/Icons$Rounded;", "getLandscape", "(Landroidx/compose/material/icons/Icons$Rounded;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class LandscapeKt {
    private static ImageVector _landscape;

    public static final ImageVector getLandscape(Icons.Rounded $this$Landscape) {
        if (_landscape != null) {
            ImageVector imageVector = _landscape;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_Landscape__u24lambda_u241 = new ImageVector.Builder("Rounded.Landscape", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(13.2f, 7.07f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(10.25f, 11.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(2.25f, 3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.33f, 0.44f, 0.24f, 1.07f, -0.2f, 1.4f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.44f, 0.33f, -1.07f, 0.25f, -1.4f, -0.2f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-1.05f, -1.4f, -2.31f, -3.07f, -3.1f, -4.14f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.4f, -0.53f, -1.2f, -0.53f, -1.6f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-4.0f, 5.33f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.49f, 0.67f, -0.02f, 1.61f, 0.8f, 1.61f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(18.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.82f, 0.0f, 1.29f, -0.94f, 0.8f, -1.6f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-7.0f, -9.33f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.4f, -0.54f, -1.2f, -0.54f, -1.6f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _landscape = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_Landscape__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _landscape;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
