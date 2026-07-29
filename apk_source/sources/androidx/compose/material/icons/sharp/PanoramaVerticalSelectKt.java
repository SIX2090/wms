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

/* compiled from: PanoramaVerticalSelect.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_panoramaVerticalSelect", "Landroidx/compose/ui/graphics/vector/ImageVector;", "PanoramaVerticalSelect", "Landroidx/compose/material/icons/Icons$Sharp;", "getPanoramaVerticalSelect", "(Landroidx/compose/material/icons/Icons$Sharp;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class PanoramaVerticalSelectKt {
    private static ImageVector _panoramaVerticalSelect;

    public static final ImageVector getPanoramaVerticalSelect(Icons.Sharp $this$PanoramaVerticalSelect) {
        if (_panoramaVerticalSelect != null) {
            ImageVector imageVector = _panoramaVerticalSelect;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_PanoramaVerticalSelect__u24lambda_u241 = new ImageVector.Builder("Sharp.PanoramaVerticalSelect", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(18.49f, 11.99f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, -5.25f, 1.54f, -9.01f, 1.92f, -10.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-16.82f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.76f, 2.16f, 1.9f, 5.21f, 1.9f, 10.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, 4.78f, -1.17f, 7.91f, -1.9f, 10.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(16.81f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(19.66f, 19.91f, 18.49f, 16.76f, 18.49f, 11.99f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _panoramaVerticalSelect = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_PanoramaVerticalSelect__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _panoramaVerticalSelect;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
