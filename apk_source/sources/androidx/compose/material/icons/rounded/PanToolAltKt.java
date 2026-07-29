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

/* compiled from: PanToolAlt.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_panToolAlt", "Landroidx/compose/ui/graphics/vector/ImageVector;", "PanToolAlt", "Landroidx/compose/material/icons/Icons$Rounded;", "getPanToolAlt", "(Landroidx/compose/material/icons/Icons$Rounded;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class PanToolAltKt {
    private static ImageVector _panToolAlt;

    public static final ImageVector getPanToolAlt(Icons.Rounded $this$PanToolAlt) {
        if (_panToolAlt != null) {
            ImageVector imageVector = _panToolAlt;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_PanToolAlt__u24lambda_u241 = new ImageVector.Builder("Rounded.PanToolAlt", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(5.2f, 15.43f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, -0.65f, 0.6f, -1.13f, 1.24f, -0.99f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(10.0f, 15.24f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(4.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(10.0f, 3.67f, 10.67f, 3.0f, 11.5f, 3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveTo(13.0f, 3.67f, 13.0f, 4.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(6.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(0.91f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.31f, 0.0f, 0.62f, 0.07f, 0.89f, 0.21f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(4.09f, 2.04f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.77f, 0.38f, 1.21f, 1.22f, 1.09f, 2.07f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-0.63f, 4.46f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(19.21f, 20.27f, 18.36f, 21.0f, 17.37f, 21.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(-6.16f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.53f, 0.0f, -1.29f, -0.21f, -1.66f, -0.59f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-4.07f, -4.29f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(5.3f, 15.94f, 5.2f, 15.69f, 5.2f, 15.43f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _panToolAlt = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_PanToolAlt__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _panToolAlt;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
