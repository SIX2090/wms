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

/* compiled from: ThumbUpAlt.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_thumbUpAlt", "Landroidx/compose/ui/graphics/vector/ImageVector;", "ThumbUpAlt", "Landroidx/compose/material/icons/Icons$Filled;", "getThumbUpAlt", "(Landroidx/compose/material/icons/Icons$Filled;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class ThumbUpAltKt {
    private static ImageVector _thumbUpAlt;

    public static final ImageVector getThumbUpAlt(Icons.Filled $this$ThumbUpAlt) {
        if (_thumbUpAlt != null) {
            ImageVector imageVector = _thumbUpAlt;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_ThumbUpAlt__u24lambda_u241 = new ImageVector.Builder("Filled.ThumbUpAlt", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(2.0f, 20.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.55f, 0.0f, 1.0f, -0.45f, 1.0f, -1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(-9.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, -0.55f, -0.45f, -1.0f, -1.0f, -1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(2.0f, 9.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(11.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(21.83f, 12.88f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.11f, -0.25f, 0.17f, -0.52f, 0.17f, -0.8f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(22.0f, 11.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, -1.1f, -0.9f, -2.0f, -2.0f, -2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(-5.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(0.92f, -4.65f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.05f, -0.22f, 0.02f, -0.46f, -0.08f, -0.66f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.23f, -0.45f, -0.52f, -0.86f, -0.88f, -1.22f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(14.0f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(7.59f, 8.41f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(7.21f, 8.79f, 7.0f, 9.3f, 7.0f, 9.83f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(7.84f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(7.0f, 18.95f, 8.05f, 20.0f, 9.34f, 20.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(8.11f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.7f, 0.0f, 1.36f, -0.37f, 1.72f, -0.97f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(2.66f, -6.15f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _thumbUpAlt = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_ThumbUpAlt__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _thumbUpAlt;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
