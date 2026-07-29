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

/* compiled from: CallEnd.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_callEnd", "Landroidx/compose/ui/graphics/vector/ImageVector;", "CallEnd", "Landroidx/compose/material/icons/Icons$Rounded;", "getCallEnd", "(Landroidx/compose/material/icons/Icons$Rounded;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class CallEndKt {
    private static ImageVector _callEnd;

    public static final ImageVector getCallEnd(Icons.Rounded $this$CallEnd) {
        if (_callEnd != null) {
            ImageVector imageVector = _callEnd;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_CallEnd__u24lambda_u241 = new ImageVector.Builder("Rounded.CallEnd", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(4.51f, 15.48f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(2.0f, -1.59f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.48f, -0.38f, 0.76f, -0.96f, 0.76f, -1.57f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(-2.6f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(3.02f, -0.98f, 6.29f, -0.99f, 9.32f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(2.61f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, 0.61f, 0.28f, 1.19f, 0.76f, 1.57f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.99f, 1.58f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.8f, 0.63f, 1.94f, 0.57f, 2.66f, -0.15f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.22f, -1.22f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.8f, -0.8f, 0.8f, -2.13f, -0.05f, -2.88f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-6.41f, -5.66f, -16.07f, -5.66f, -22.48f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.85f, 0.75f, -0.85f, 2.08f, -0.05f, 2.88f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.22f, 1.22f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.71f, 0.72f, 1.85f, 0.78f, 2.65f, 0.15f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _callEnd = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_CallEnd__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _callEnd;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
