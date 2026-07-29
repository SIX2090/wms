package androidx.compose.material.icons.filled;

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

/* compiled from: Map.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_map", "Landroidx/compose/ui/graphics/vector/ImageVector;", "Map", "Landroidx/compose/material/icons/Icons$Filled;", "getMap", "(Landroidx/compose/material/icons/Icons$Filled;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class MapKt {
    private static ImageVector _map;

    public static final ImageVector getMap(Icons.Filled $this$Map) {
        if (_map != null) {
            ImageVector imageVector = _map;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_Map__u24lambda_u241 = new ImageVector.Builder("Filled.Map", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(20.5f, 3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-0.16f, 0.03f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(15.0f, 5.1f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(9.0f, 3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(3.36f, 4.9f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.21f, 0.07f, -0.36f, 0.25f, -0.36f, 0.48f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(20.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, 0.28f, 0.22f, 0.5f, 0.5f, 0.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(0.16f, -0.03f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(9.0f, 18.9f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(6.0f, 2.1f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(5.64f, -1.9f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.21f, -0.07f, 0.36f, -0.25f, 0.36f, -0.48f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(3.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, -0.28f, -0.22f, -0.5f, -0.5f, -0.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(15.0f, 19.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-6.0f, -2.11f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(5.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(6.0f, 2.11f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(19.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _map = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_Map__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _map;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
