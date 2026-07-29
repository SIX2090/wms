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

/* compiled from: PanToolAlt.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_panToolAlt", "Landroidx/compose/ui/graphics/vector/ImageVector;", "PanToolAlt", "Landroidx/compose/material/icons/Icons$Sharp;", "getPanToolAlt", "(Landroidx/compose/material/icons/Icons$Sharp;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class PanToolAltKt {
    private static ImageVector _panToolAlt;

    public static final ImageVector getPanToolAlt(Icons.Sharp $this$PanToolAlt) {
        if (_panToolAlt != null) {
            ImageVector imageVector = _panToolAlt;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_PanToolAlt__u24lambda_u241 = new ImageVector.Builder("Sharp.PanToolAlt", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(20.18f, 13.4f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(19.1f, 21.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(-9.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(5.0f, 15.62f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.22f, -1.23f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(10.0f, 15.24f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(4.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(10.0f, 3.67f, 10.67f, 3.0f, 11.5f, 3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveTo(13.0f, 3.67f, 13.0f, 4.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(6.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(1.38f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(20.18f, 13.4f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _panToolAlt = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_PanToolAlt__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _panToolAlt;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
