package androidx.compose.material.icons.automirrored.outlined;

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

/* compiled from: TrendingUp.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_trendingUp", "Landroidx/compose/ui/graphics/vector/ImageVector;", "TrendingUp", "Landroidx/compose/material/icons/Icons$AutoMirrored$Outlined;", "getTrendingUp", "(Landroidx/compose/material/icons/Icons$AutoMirrored$Outlined;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class TrendingUpKt {
    private static ImageVector _trendingUp;

    public static final ImageVector getTrendingUp(Icons.AutoMirrored.Outlined $this$TrendingUp) {
        if (_trendingUp != null) {
            ImageVector imageVector = _trendingUp;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_TrendingUp__u24lambda_u241 = new ImageVector.Builder("AutoMirrored.Outlined.TrendingUp", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, true, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(16.0f, 6.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(2.29f, 2.29f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-4.88f, 4.88f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-4.0f, -4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(2.0f, 16.59f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(3.41f, 18.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(6.0f, -6.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(4.0f, 4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(6.3f, -6.29f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(22.0f, 12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(6.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(-6.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _trendingUp = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_TrendingUp__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _trendingUp;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
