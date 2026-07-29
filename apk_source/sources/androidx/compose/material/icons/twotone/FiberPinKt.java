package androidx.compose.material.icons.twotone;

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

/* compiled from: FiberPin.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_fiberPin", "Landroidx/compose/ui/graphics/vector/ImageVector;", "FiberPin", "Landroidx/compose/material/icons/Icons$TwoTone;", "getFiberPin", "(Landroidx/compose/material/icons/Icons$TwoTone;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class FiberPinKt {
    private static ImageVector _fiberPin;

    public static final ImageVector getFiberPin(Icons.TwoTone $this$FiberPin) {
        if (_fiberPin != null) {
            ImageVector imageVector = _fiberPin;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_FiberPin__u24lambda_u243 = new ImageVector.Builder("TwoTone.FiberPin", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(5.0f, 14.62f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(1.31f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(-1.75f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(1.75f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.74f, 0.0f, 1.31f, -0.57f, 1.31f, -1.31f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(-0.88f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, -0.74f, -0.57f, -1.31f, -1.31f, -1.31f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(5.0f, 9.37f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(5.25f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(6.31f, 10.69f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(1.75f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(0.88f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(6.31f, 11.57f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(-0.88f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(11.34f, 9.38f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(1.31f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(5.25f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(-1.31f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(14.62f, 14.62f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(1.1f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(-3.06f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(2.23f, 3.06f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(19.0f, 14.62f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(19.0f, 9.38f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(-1.09f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(3.06f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-2.19f, -3.06f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(-1.1f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_FiberPin__u24lambda_u243, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null);
        int pathFillType$iv2 = VectorKt.getDefaultFillType();
        Brush fill$iv$iv2 = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv2 = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv2 = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv2 = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv2.moveTo(4.0f, 6.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.horizontalLineToRelative(16.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.verticalLineToRelative(12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.horizontalLineTo(4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.close();
        ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_FiberPin__u24lambda_u243, $this$PathData_u24lambda_u240$iv$iv$iv2.getNodes(), pathFillType$iv2, "", fill$iv$iv2, 0.3f, null, 0.3f, 1.0f, strokeLineCap$iv$iv2, strokeLineJoin$iv$iv2, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null);
        int pathFillType$iv3 = VectorKt.getDefaultFillType();
        Brush fill$iv$iv3 = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv3 = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv3 = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv3 = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv3.moveTo(20.0f, 4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.lineTo(4.0f, 4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.curveToRelative(-1.11f, 0.0f, -1.99f, 0.89f, -1.99f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.lineTo(2.0f, 18.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.curveToRelative(0.0f, 1.11f, 0.89f, 2.0f, 2.0f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.horizontalLineToRelative(16.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.curveToRelative(1.11f, 0.0f, 2.0f, -0.89f, 2.0f, -2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.lineTo(22.0f, 6.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.curveToRelative(0.0f, -1.11f, -0.89f, -2.0f, -2.0f, -2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.close();
        $this$PathData_u24lambda_u240$iv$iv$iv3.moveTo(20.0f, 18.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.lineTo(4.0f, 18.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.lineTo(4.0f, 6.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.horizontalLineToRelative(16.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.verticalLineToRelative(12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.close();
        _fiberPin = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_FiberPin__u24lambda_u243, $this$PathData_u24lambda_u240$iv$iv$iv3.getNodes(), pathFillType$iv3, "", fill$iv$iv3, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv3, strokeLineJoin$iv$iv3, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _fiberPin;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
