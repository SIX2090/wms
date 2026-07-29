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

/* compiled from: PlayForWork.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_playForWork", "Landroidx/compose/ui/graphics/vector/ImageVector;", "PlayForWork", "Landroidx/compose/material/icons/Icons$Rounded;", "getPlayForWork", "(Landroidx/compose/material/icons/Icons$Rounded;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class PlayForWorkKt {
    private static ImageVector _playForWork;

    public static final ImageVector getPlayForWork(Icons.Rounded $this$PlayForWork) {
        if (_playForWork != null) {
            ImageVector imageVector = _playForWork;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_PlayForWork__u24lambda_u241 = new ImageVector.Builder("Rounded.PlayForWork", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(11.0f, 6.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(4.59f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(8.71f, 10.59f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.45f, 0.0f, -0.67f, 0.54f, -0.35f, 0.85f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(3.29f, 3.29f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.2f, 0.2f, 0.51f, 0.2f, 0.71f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(3.29f, -3.29f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.31f, -0.31f, 0.09f, -0.85f, -0.35f, -0.85f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(13.0f, 10.59f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(13.0f, 6.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, -0.55f, -0.45f, -1.0f, -1.0f, -1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveToRelative(-1.0f, 0.45f, -1.0f, 1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(7.1f, 14.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.61f, 0.0f, -1.11f, 0.55f, -0.99f, 1.15f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(6.65f, 17.91f, 9.08f, 20.0f, 12.0f, 20.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveToRelative(5.35f, -2.09f, 5.89f, -4.85f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.12f, -0.6f, -0.38f, -1.15f, -0.99f, -1.15f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.49f, 0.0f, -0.88f, 0.35f, -0.98f, 0.83f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(15.53f, 16.64f, 13.93f, 18.0f, 12.0f, 18.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveToRelative(-3.53f, -1.36f, -3.91f, -3.17f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.1f, -0.48f, -0.5f, -0.83f, -0.99f, -0.83f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _playForWork = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_PlayForWork__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _playForWork;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
