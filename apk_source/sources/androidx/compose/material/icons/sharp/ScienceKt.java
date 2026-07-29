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

/* compiled from: Science.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_science", "Landroidx/compose/ui/graphics/vector/ImageVector;", "Science", "Landroidx/compose/material/icons/Icons$Sharp;", "getScience", "(Landroidx/compose/material/icons/Icons$Sharp;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class ScienceKt {
    private static ImageVector _science;

    public static final ImageVector getScience(Icons.Sharp $this$Science) {
        if (_science != null) {
            ImageVector imageVector = _science;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_Science__u24lambda_u241 = new ImageVector.Builder("Sharp.Science", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(19.8f, 18.4f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(14.0f, 10.67f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(6.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.35f, -1.69f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(15.61f, 4.48f, 15.38f, 4.0f, 14.96f, 4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineTo(9.04f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(8.62f, 4.0f, 8.39f, 4.48f, 8.65f, 4.81f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(10.0f, 6.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(4.17f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(4.2f, 18.4f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(3.71f, 19.06f, 4.18f, 20.0f, 5.0f, 20.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(14.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(19.82f, 20.0f, 20.29f, 19.06f, 19.8f, 18.4f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _science = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_Science__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _science;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
