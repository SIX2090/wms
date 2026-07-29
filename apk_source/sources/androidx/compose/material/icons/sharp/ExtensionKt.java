package androidx.compose.material.icons.sharp;

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

/* compiled from: Extension.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_extension", "Landroidx/compose/ui/graphics/vector/ImageVector;", "Extension", "Landroidx/compose/material/icons/Icons$Sharp;", "getExtension", "(Landroidx/compose/material/icons/Icons$Sharp;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class ExtensionKt {
    private static ImageVector _extension;

    public static final ImageVector getExtension(Icons.Sharp $this$Extension) {
        if (_extension != null) {
            ImageVector imageVector = _extension;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_Extension__u24lambda_u241 = new ImageVector.Builder("Sharp.Extension", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(20.36f, 11.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineTo(19.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(5.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(-6.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(3.64f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, -1.31f, -0.94f, -2.5f, -2.24f, -2.63f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(9.26f, 0.86f, 8.0f, 2.03f, 8.0f, 3.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(5.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineTo(2.01f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(5.8f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineTo(3.4f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(1.31f, 0.0f, 2.5f, 0.88f, 2.75f, 2.16f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.33f, 1.72f, -0.98f, 3.24f, -2.65f, 3.24f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineTo(2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(22.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(5.8f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(-1.4f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, -1.31f, 0.88f, -2.5f, 2.16f, -2.75f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(1.72f, -0.33f, 3.24f, 0.98f, 3.24f, 2.65f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(22.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineTo(19.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(-6.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(1.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(1.47f, 0.0f, 2.64f, -1.26f, 2.49f, -2.76f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.13f, -1.3f, -1.33f, -2.24f, -2.63f, -2.24f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _extension = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_Extension__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _extension;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
