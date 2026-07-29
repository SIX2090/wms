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

/* compiled from: HeartBroken.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_heartBroken", "Landroidx/compose/ui/graphics/vector/ImageVector;", "HeartBroken", "Landroidx/compose/material/icons/Icons$Rounded;", "getHeartBroken", "(Landroidx/compose/material/icons/Icons$Rounded;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class HeartBrokenKt {
    private static ImageVector _heartBroken;

    public static final ImageVector getHeartBroken(Icons.Rounded $this$HeartBroken) {
        if (_heartBroken != null) {
            ImageVector imageVector = _heartBroken;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_HeartBroken__u24lambda_u241 = new ImageVector.Builder("Rounded.HeartBroken", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(19.57f, 3.95f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-1.92f, -1.29f, -4.08f, -1.17f, -5.8f, -0.26f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(12.0f, 9.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(1.66f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.67f, 0.0f, 1.15f, 0.65f, 0.96f, 1.29f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-1.82f, 6.07f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.09f, 0.29f, -0.52f, 0.2f, -0.49f, -0.1f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(13.0f, 10.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(-1.67f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.66f, 0.0f, -1.14f, -0.64f, -0.96f, -1.27f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.18f, -4.11f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(9.7f, 2.89f, 6.71f, 2.32f, 4.27f, 4.04f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(2.82f, 5.07f, 2.0f, 6.7f, 2.0f, 8.49f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.01f, 3.81f, 3.53f, 6.71f, 8.66f, 11.3f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.76f, 0.68f, 1.92f, 0.69f, 2.69f, 0.01f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(4.98f, -4.42f, 8.87f, -7.58f, 8.64f, -11.62f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(21.9f, 6.45f, 21.0f, 4.92f, 19.57f, 3.95f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _heartBroken = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_HeartBroken__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _heartBroken;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
