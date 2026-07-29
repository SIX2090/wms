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

/* compiled from: OpenInFull.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_openInFull", "Landroidx/compose/ui/graphics/vector/ImageVector;", "OpenInFull", "Landroidx/compose/material/icons/Icons$Rounded;", "getOpenInFull", "(Landroidx/compose/material/icons/Icons$Rounded;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class OpenInFullKt {
    private static ImageVector _openInFull;

    public static final ImageVector getOpenInFull(Icons.Rounded $this$OpenInFull) {
        if (_openInFull != null) {
            ImageVector imageVector = _openInFull;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_OpenInFull__u24lambda_u241 = new ImageVector.Builder("Rounded.OpenInFull", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(21.0f, 8.59f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, -0.55f, -0.45f, -1.0f, -1.0f, -1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(-4.59f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.89f, 0.0f, -1.34f, 1.08f, -0.71f, 1.71f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.59f, 1.59f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-10.0f, 10.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-1.59f, -1.59f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(4.08f, 14.08f, 3.0f, 14.52f, 3.0f, 15.41f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(20.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, 0.55f, 0.45f, 1.0f, 1.0f, 1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(4.59f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.89f, 0.0f, 1.34f, -1.08f, 0.71f, -1.71f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-1.59f, -1.59f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(10.0f, -10.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.59f, 1.59f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(19.92f, 9.92f, 21.0f, 9.48f, 21.0f, 8.59f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _openInFull = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_OpenInFull__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _openInFull;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
