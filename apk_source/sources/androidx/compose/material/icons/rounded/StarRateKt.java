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

/* compiled from: StarRate.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_starRate", "Landroidx/compose/ui/graphics/vector/ImageVector;", "StarRate", "Landroidx/compose/material/icons/Icons$Rounded;", "getStarRate", "(Landroidx/compose/material/icons/Icons$Rounded;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class StarRateKt {
    private static ImageVector _starRate;

    public static final ImageVector getStarRate(Icons.Rounded $this$StarRate) {
        if (_starRate != null) {
            ImageVector imageVector = _starRate;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_StarRate__u24lambda_u241 = new ImageVector.Builder("Rounded.StarRate", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(14.43f, 10.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-1.47f, -4.84f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.29f, -0.95f, -1.63f, -0.95f, -1.91f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(9.57f, 10.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineTo(5.12f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.97f, 0.0f, -1.37f, 1.25f, -0.58f, 1.81f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(3.64f, 2.6f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-1.43f, 4.61f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.29f, 0.93f, 0.79f, 1.68f, 1.56f, 1.09f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(12.0f, 17.31f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(3.69f, 2.81f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.77f, 0.59f, 1.85f, -0.16f, 1.56f, -1.09f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-1.43f, -4.61f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(3.64f, -2.6f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.79f, -0.57f, 0.39f, -1.81f, -0.58f, -1.81f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineTo(14.43f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _starRate = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_StarRate__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _starRate;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
