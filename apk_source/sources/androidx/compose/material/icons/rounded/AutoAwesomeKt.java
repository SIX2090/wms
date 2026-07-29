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

/* compiled from: AutoAwesome.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_autoAwesome", "Landroidx/compose/ui/graphics/vector/ImageVector;", "AutoAwesome", "Landroidx/compose/material/icons/Icons$Rounded;", "getAutoAwesome", "(Landroidx/compose/material/icons/Icons$Rounded;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class AutoAwesomeKt {
    private static ImageVector _autoAwesome;

    public static final ImageVector getAutoAwesome(Icons.Rounded $this$AutoAwesome) {
        if (_autoAwesome != null) {
            ImageVector imageVector = _autoAwesome;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_AutoAwesome__u24lambda_u241 = new ImageVector.Builder("Rounded.AutoAwesome", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(19.46f, 8.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(0.79f, -1.75f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(22.0f, 5.46f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.39f, -0.18f, 0.39f, -0.73f, 0.0f, -0.91f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-1.75f, -0.79f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(19.46f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.18f, -0.39f, -0.73f, -0.39f, -0.91f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-0.79f, 1.75f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(16.0f, 4.54f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.39f, 0.18f, -0.39f, 0.73f, 0.0f, 0.91f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.75f, 0.79f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(18.54f, 8.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(18.72f, 8.39f, 19.28f, 8.39f, 19.46f, 8.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(11.5f, 9.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(9.91f, 6.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(9.56f, 5.22f, 8.44f, 5.22f, 8.09f, 6.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(6.5f, 9.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(3.0f, 11.09f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.78f, 0.36f, -0.78f, 1.47f, 0.0f, 1.82f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(3.5f, 1.59f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(8.09f, 18.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.36f, 0.78f, 1.47f, 0.78f, 1.82f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.59f, -3.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(3.5f, -1.59f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.78f, -0.36f, 0.78f, -1.47f, 0.0f, -1.82f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(11.5f, 9.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(18.54f, 16.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-0.79f, 1.75f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(16.0f, 18.54f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.39f, 0.18f, -0.39f, 0.73f, 0.0f, 0.91f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.75f, 0.79f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(18.54f, 22.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.18f, 0.39f, 0.73f, 0.39f, 0.91f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(0.79f, -1.75f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(22.0f, 19.46f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.39f, -0.18f, 0.39f, -0.73f, 0.0f, -0.91f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-1.75f, -0.79f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(19.46f, 16.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(19.28f, 15.61f, 18.72f, 15.61f, 18.54f, 16.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _autoAwesome = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_AutoAwesome__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _autoAwesome;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
