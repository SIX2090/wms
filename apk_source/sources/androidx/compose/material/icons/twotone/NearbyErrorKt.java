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

/* compiled from: NearbyError.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_nearbyError", "Landroidx/compose/ui/graphics/vector/ImageVector;", "NearbyError", "Landroidx/compose/material/icons/Icons$TwoTone;", "getNearbyError", "(Landroidx/compose/material/icons/Icons$TwoTone;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class NearbyErrorKt {
    private static ImageVector _nearbyError;

    public static final ImageVector getNearbyError(Icons.TwoTone $this$NearbyError) {
        if (_nearbyError != null) {
            ImageVector imageVector = _nearbyError;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_NearbyError__u24lambda_u241 = new ImageVector.Builder("TwoTone.NearbyError", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(12.0f, 7.57f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(4.42f, 4.42f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(12.0f, 16.41f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-4.42f, -4.42f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(12.0f, 7.57f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(12.0f, 19.19f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-7.2f, -7.2f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(7.2f, -7.2f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(6.0f, 6.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(7.16f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-4.58f, -4.58f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.78f, -0.78f, -2.05f, -0.78f, -2.83f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-8.01f, 8.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.78f, 0.78f, -0.78f, 2.05f, 0.0f, 2.83f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(8.01f, 8.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.78f, 0.78f, 2.05f, 0.78f, 2.83f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(18.0f, 16.82f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(-3.63f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(12.0f, 19.19f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(20.0f, 20.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(-2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(20.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(22.0f, 10.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(-2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(8.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(10.0f);
        _nearbyError = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_NearbyError__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _nearbyError;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
