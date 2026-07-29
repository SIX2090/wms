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
import kotlin.Deprecated;
import kotlin.Metadata;
import kotlin.ReplaceWith;
import kotlin.jvm.internal.Intrinsics;

/* compiled from: TrendingUp.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0005\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u001e\u0010\u0002\u001a\u00020\u0001*\u00020\u00038FX\u0087\u0004¢\u0006\f\u0012\u0004\b\u0004\u0010\u0005\u001a\u0004\b\u0006\u0010\u0007¨\u0006\b"}, d2 = {"_trendingUp", "Landroidx/compose/ui/graphics/vector/ImageVector;", "TrendingUp", "Landroidx/compose/material/icons/Icons$Rounded;", "getTrendingUp$annotations", "(Landroidx/compose/material/icons/Icons$Rounded;)V", "getTrendingUp", "(Landroidx/compose/material/icons/Icons$Rounded;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class TrendingUpKt {
    private static ImageVector _trendingUp;

    @Deprecated(message = "Use the AutoMirrored version at Icons.AutoMirrored.Rounded.TrendingUp", replaceWith = @ReplaceWith(expression = "Icons.AutoMirrored.Rounded.TrendingUp", imports = {"androidx.compose.material.icons.automirrored.rounded.TrendingUp"}))
    public static /* synthetic */ void getTrendingUp$annotations(Icons.Rounded rounded) {
    }

    public static final ImageVector getTrendingUp(Icons.Rounded $this$TrendingUp) {
        if (_trendingUp != null) {
            ImageVector imageVector = _trendingUp;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_TrendingUp__u24lambda_u241 = new ImageVector.Builder("Rounded.TrendingUp", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(16.85f, 6.85f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.44f, 1.44f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-4.88f, 4.88f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-3.29f, -3.29f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.39f, -0.39f, -1.02f, -0.39f, -1.41f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-6.0f, 6.01f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.39f, 0.39f, -0.39f, 1.02f, 0.0f, 1.41f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.39f, 0.39f, 1.02f, 0.39f, 1.41f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(9.41f, 12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(3.29f, 3.29f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.39f, 0.39f, 1.02f, 0.39f, 1.41f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(5.59f, -5.58f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.44f, 1.44f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.31f, 0.31f, 0.85f, 0.09f, 0.85f, -0.35f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(6.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.01f, -0.28f, -0.21f, -0.5f, -0.49f, -0.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(-4.29f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.45f, 0.0f, -0.67f, 0.54f, -0.36f, 0.85f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _trendingUp = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_TrendingUp__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _trendingUp;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
