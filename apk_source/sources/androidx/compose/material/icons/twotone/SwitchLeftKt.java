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

/* compiled from: SwitchLeft.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_switchLeft", "Landroidx/compose/ui/graphics/vector/ImageVector;", "SwitchLeft", "Landroidx/compose/material/icons/Icons$TwoTone;", "getSwitchLeft", "(Landroidx/compose/material/icons/Icons$TwoTone;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class SwitchLeftKt {
    private static ImageVector _switchLeft;

    public static final ImageVector getSwitchLeft(Icons.TwoTone $this$SwitchLeft) {
        if (_switchLeft != null) {
            ImageVector imageVector = _switchLeft;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_SwitchLeft__u24lambda_u242 = new ImageVector.Builder("TwoTone.SwitchLeft", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(8.5f, 8.62f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(0.0f, 6.76f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-3.38f, -3.38f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(3.38f, -3.38f);
        ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_SwitchLeft__u24lambda_u242, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 0.3f, null, 0.3f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null);
        int pathFillType$iv2 = VectorKt.getDefaultFillType();
        Brush fill$iv$iv2 = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv2 = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv2 = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv2 = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv2.moveTo(8.5f, 8.62f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.verticalLineToRelative(6.76f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineTo(5.12f, 12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineTo(8.5f, 8.62f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.moveTo(10.0f, 5.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineToRelative(-7.0f, 7.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineToRelative(7.0f, 7.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.verticalLineTo(5.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineTo(10.0f, 5.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.close();
        $this$PathData_u24lambda_u240$iv$iv$iv2.moveTo(14.0f, 5.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.verticalLineToRelative(14.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineToRelative(7.0f, -7.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineTo(14.0f, 5.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.close();
        _switchLeft = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_SwitchLeft__u24lambda_u242, $this$PathData_u24lambda_u240$iv$iv$iv2.getNodes(), pathFillType$iv2, "", fill$iv$iv2, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv2, strokeLineJoin$iv$iv2, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _switchLeft;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
