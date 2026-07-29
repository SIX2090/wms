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

/* compiled from: RoundaboutLeft.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_roundaboutLeft", "Landroidx/compose/ui/graphics/vector/ImageVector;", "RoundaboutLeft", "Landroidx/compose/material/icons/Icons$TwoTone;", "getRoundaboutLeft", "(Landroidx/compose/material/icons/Icons$TwoTone;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class RoundaboutLeftKt {
    private static ImageVector _roundaboutLeft;

    public static final ImageVector getRoundaboutLeft(Icons.TwoTone $this$RoundaboutLeft) {
        if (_roundaboutLeft != null) {
            ImageVector imageVector = _roundaboutLeft;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_RoundaboutLeft__u24lambda_u241 = new ImageVector.Builder("TwoTone.RoundaboutLeft", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(10.08f, 8.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.48f, -2.84f, 2.94f, -5.0f, 5.92f, -5.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(3.31f, 0.0f, 6.0f, 2.69f, 6.0f, 6.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, 2.97f, -2.16f, 5.44f, -5.0f, 5.92f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(17.0f, 21.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(-2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(0.0f, -6.09f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, -0.98f, 0.71f, -1.8f, 1.67f, -1.97f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(18.56f, 12.63f, 20.0f, 10.98f, 20.0f, 9.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, -2.21f, -1.79f, -4.0f, -4.0f, -4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-1.98f, 0.0f, -3.63f, 1.44f, -3.94f, 3.33f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(11.89f, 9.29f, 11.07f, 10.0f, 10.09f, 10.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-4.26f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.59f, 1.59f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(6.0f, 13.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(2.0f, 9.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(4.0f, -4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.41f, 1.41f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(5.83f, 8.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(10.08f, 8.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _roundaboutLeft = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_RoundaboutLeft__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _roundaboutLeft;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
