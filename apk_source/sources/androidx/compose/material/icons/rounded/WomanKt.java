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

/* compiled from: Woman.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_woman", "Landroidx/compose/ui/graphics/vector/ImageVector;", "Woman", "Landroidx/compose/material/icons/Icons$Rounded;", "getWoman", "(Landroidx/compose/material/icons/Icons$Rounded;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class WomanKt {
    private static ImageVector _woman;

    public static final ImageVector getWoman(Icons.Rounded $this$Woman) {
        if (_woman != null) {
            ImageVector imageVector = _woman;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_Woman__u24lambda_u242 = new ImageVector.Builder("Rounded.Woman", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(12.0f, 4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.moveToRelative(-2.0f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.arcToRelative(2.0f, 2.0f, 0.0f, true, true, 4.0f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.arcToRelative(2.0f, 2.0f, 0.0f, true, true, -4.0f, 0.0f);
        ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_Woman__u24lambda_u242, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null);
        int pathFillType$iv2 = VectorKt.getDefaultFillType();
        Brush fill$iv$iv2 = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv2 = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv2 = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv2 = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv2.moveTo(16.45f, 14.63f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineToRelative(-2.52f, -6.32f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveToRelative(-0.32f, -0.79f, -1.08f, -1.3f, -1.94f, -1.31f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveToRelative(-0.85f, 0.0f, -1.62f, 0.51f, -1.94f, 1.31f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineToRelative(-2.52f, 6.32f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveTo(7.28f, 15.29f, 7.77f, 16.0f, 8.47f, 16.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.horizontalLineTo(10.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.verticalLineToRelative(5.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveToRelative(0.0f, 0.55f, 0.45f, 1.0f, 1.0f, 1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.horizontalLineToRelative(1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.horizontalLineToRelative(1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveToRelative(0.55f, 0.0f, 1.0f, -0.45f, 1.0f, -1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.verticalLineToRelative(-5.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.horizontalLineToRelative(1.53f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveTo(16.23f, 16.0f, 16.72f, 15.29f, 16.45f, 14.63f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.close();
        _woman = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_Woman__u24lambda_u242, $this$PathData_u24lambda_u240$iv$iv$iv2.getNodes(), pathFillType$iv2, "", fill$iv$iv2, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv2, strokeLineJoin$iv$iv2, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _woman;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
