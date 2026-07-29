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

/* compiled from: PanoramaWideAngleSelect.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_panoramaWideAngleSelect", "Landroidx/compose/ui/graphics/vector/ImageVector;", "PanoramaWideAngleSelect", "Landroidx/compose/material/icons/Icons$Filled;", "getPanoramaWideAngleSelect", "(Landroidx/compose/material/icons/Icons$Filled;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class PanoramaWideAngleSelectKt {
    private static ImageVector _panoramaWideAngleSelect;

    public static final ImageVector getPanoramaWideAngleSelect(Icons.Filled $this$PanoramaWideAngleSelect) {
        if (_panoramaWideAngleSelect != null) {
            ImageVector imageVector = _panoramaWideAngleSelect;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_PanoramaWideAngleSelect__u24lambda_u241 = new ImageVector.Builder("Filled.PanoramaWideAngleSelect", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(12.0f, 4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-2.73f, 0.0f, -5.22f, 0.24f, -7.95f, 0.72f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-0.93f, 0.16f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-0.25f, 0.9f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(2.29f, 7.85f, 2.0f, 9.93f, 2.0f, 12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveToRelative(0.29f, 4.15f, 0.87f, 6.22f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(0.25f, 0.89f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(0.93f, 0.16f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(2.73f, 0.49f, 5.22f, 0.73f, 7.95f, 0.73f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveToRelative(5.22f, -0.24f, 7.95f, -0.72f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(0.93f, -0.16f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(0.25f, -0.89f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.58f, -2.08f, 0.87f, -4.16f, 0.87f, -6.23f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveToRelative(-0.29f, -4.15f, -0.87f, -6.22f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-0.25f, -0.89f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-0.93f, -0.16f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(17.22f, 4.24f, 14.73f, 4.0f, 12.0f, 4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _panoramaWideAngleSelect = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_PanoramaWideAngleSelect__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _panoramaWideAngleSelect;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
