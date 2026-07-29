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

/* compiled from: BreakfastDining.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_breakfastDining", "Landroidx/compose/ui/graphics/vector/ImageVector;", "BreakfastDining", "Landroidx/compose/material/icons/Icons$Sharp;", "getBreakfastDining", "(Landroidx/compose/material/icons/Icons$Sharp;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class BreakfastDiningKt {
    private static ImageVector _breakfastDining;

    public static final ImageVector getBreakfastDining(Icons.Sharp $this$BreakfastDining) {
        if (_breakfastDining != null) {
            ImageVector imageVector = _breakfastDining;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_BreakfastDining__u24lambda_u241 = new ImageVector.Builder("Sharp.BreakfastDining", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(17.85f, 3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(6.14f, 3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(4.15f, 3.0f, 2.36f, 4.39f, 2.05f, 6.36f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(1.78f, 8.11f, 2.64f, 9.65f, 4.0f, 10.45f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(21.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(16.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(10.45f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(1.36f, -0.79f, 2.23f, -2.36f, 1.95f, -4.11f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(21.63f, 4.38f, 19.83f, 3.0f, 17.85f, 3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(16.41f, 13.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(12.0f, 17.42f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(7.59f, 13.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(12.0f, 8.59f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(16.41f, 13.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _breakfastDining = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_BreakfastDining__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _breakfastDining;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
