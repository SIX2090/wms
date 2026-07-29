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

/* compiled from: Navigation.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_navigation", "Landroidx/compose/ui/graphics/vector/ImageVector;", "Navigation", "Landroidx/compose/material/icons/Icons$Rounded;", "getNavigation", "(Landroidx/compose/material/icons/Icons$Rounded;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class NavigationKt {
    private static ImageVector _navigation;

    public static final ImageVector getNavigation(Icons.Rounded $this$Navigation) {
        if (_navigation != null) {
            ImageVector imageVector = _navigation;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_Navigation__u24lambda_u241 = new ImageVector.Builder("Rounded.Navigation", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(12.93f, 4.26f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(6.15f, 14.99f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.34f, 0.83f, -0.51f, 1.66f, -1.33f, 1.29f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-5.34f, -2.36f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.26f, -0.11f, -0.55f, -0.11f, -0.81f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-5.34f, 2.36f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.82f, 0.36f, -1.67f, -0.46f, -1.33f, -1.29f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(6.15f, -14.99f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.33f, -0.83f, 1.51f, -0.83f, 1.85f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _navigation = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_Navigation__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _navigation;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
