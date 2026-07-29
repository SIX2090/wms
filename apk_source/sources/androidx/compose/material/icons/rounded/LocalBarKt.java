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

/* compiled from: LocalBar.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_localBar", "Landroidx/compose/ui/graphics/vector/ImageVector;", "LocalBar", "Landroidx/compose/material/icons/Icons$Rounded;", "getLocalBar", "(Landroidx/compose/material/icons/Icons$Rounded;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class LocalBarKt {
    private static ImageVector _localBar;

    public static final ImageVector getLocalBar(Icons.Rounded $this$LocalBar) {
        if (_localBar != null) {
            ImageVector imageVector = _localBar;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_LocalBar__u24lambda_u241 = new ImageVector.Builder("Rounded.LocalBar", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(21.0f, 4.45f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, -0.8f, -0.65f, -1.45f, -1.45f, -1.45f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineTo(4.45f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(3.65f, 3.0f, 3.0f, 3.65f, 3.0f, 4.45f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, 0.35f, 0.13f, 0.7f, 0.37f, 0.96f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(11.0f, 14.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(5.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineTo(7.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.55f, 0.0f, -1.0f, 0.45f, -1.0f, 1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveToRelative(0.45f, 1.0f, 1.0f, 1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(10.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.55f, 0.0f, 1.0f, -0.45f, 1.0f, -1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveToRelative(-0.45f, -1.0f, -1.0f, -1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(-4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(-5.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(7.63f, -8.59f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.24f, -0.26f, 0.37f, -0.61f, 0.37f, -0.96f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(7.43f, 7.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(5.66f, 5.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(12.69f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-1.78f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineTo(7.43f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _localBar = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_LocalBar__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _localBar;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
