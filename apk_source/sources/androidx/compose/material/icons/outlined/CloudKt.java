package androidx.compose.material.icons.outlined;

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

/* compiled from: Cloud.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_cloud", "Landroidx/compose/ui/graphics/vector/ImageVector;", "Cloud", "Landroidx/compose/material/icons/Icons$Outlined;", "getCloud", "(Landroidx/compose/material/icons/Icons$Outlined;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class CloudKt {
    private static ImageVector _cloud;

    public static final ImageVector getCloud(Icons.Outlined $this$Cloud) {
        if (_cloud != null) {
            ImageVector imageVector = _cloud;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_Cloud__u24lambda_u241 = new ImageVector.Builder("Outlined.Cloud", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(12.0f, 6.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(2.62f, 0.0f, 4.88f, 1.86f, 5.39f, 4.43f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(0.3f, 1.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.53f, 0.11f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(1.56f, 0.1f, 2.78f, 1.41f, 2.78f, 2.96f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, 1.65f, -1.35f, 3.0f, -3.0f, 3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineTo(6.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-2.21f, 0.0f, -4.0f, -1.79f, -4.0f, -4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, -2.05f, 1.53f, -3.76f, 3.56f, -3.97f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.07f, -0.11f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(0.5f, -0.95f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(8.08f, 7.14f, 9.94f, 6.0f, 12.0f, 6.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.moveToRelative(0.0f, -2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(9.11f, 4.0f, 6.6f, 5.64f, 5.35f, 8.04f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(2.34f, 8.36f, 0.0f, 10.91f, 0.0f, 14.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, 3.31f, 2.69f, 6.0f, 6.0f, 6.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(13.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(2.76f, 0.0f, 5.0f, -2.24f, 5.0f, -5.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, -2.64f, -2.05f, -4.78f, -4.65f, -4.96f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(18.67f, 6.59f, 15.64f, 4.0f, 12.0f, 4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _cloud = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_Cloud__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _cloud;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
