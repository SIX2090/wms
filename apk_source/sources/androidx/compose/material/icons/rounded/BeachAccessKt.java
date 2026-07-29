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

/* compiled from: BeachAccess.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_beachAccess", "Landroidx/compose/ui/graphics/vector/ImageVector;", "BeachAccess", "Landroidx/compose/material/icons/Icons$Rounded;", "getBeachAccess", "(Landroidx/compose/material/icons/Icons$Rounded;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class BeachAccessKt {
    private static ImageVector _beachAccess;

    public static final ImageVector getBeachAccess(Icons.Rounded $this$BeachAccess) {
        if (_beachAccess != null) {
            ImageVector imageVector = _beachAccess;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_BeachAccess__u24lambda_u241 = new ImageVector.Builder("Rounded.BeachAccess", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(13.13f, 14.56f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.43f, -1.43f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(5.73f, 5.73f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.39f, 0.39f, 0.39f, 1.03f, 0.0f, 1.43f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.39f, 0.39f, -1.03f, 0.39f, -1.43f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-5.73f, -5.73f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(17.42f, 8.83f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.27f, -1.27f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.89f, -0.89f, 0.77f, -2.43f, -0.31f, -3.08f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-3.89f, -2.38f, -9.03f, -1.89f, -12.4f, 1.47f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(3.93f, -1.3f, 8.31f, -0.25f, 11.44f, 2.88f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(5.95f, 5.98f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-3.36f, 3.37f, -3.85f, 8.51f, -1.48f, 12.4f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.66f, 1.08f, 2.19f, 1.21f, 3.08f, 0.31f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.27f, -1.27f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(5.7f, 14.29f, 4.65f, 9.91f, 5.95f, 5.98f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(5.97f, 5.96f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-0.01f, 0.01f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.38f, 3.01f, 1.17f, 6.88f, 4.3f, 10.02f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(5.73f, -5.73f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-3.13f, -3.13f, -7.01f, -4.68f, -10.02f, -4.3f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _beachAccess = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_BeachAccess__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _beachAccess;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
