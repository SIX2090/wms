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

/* compiled from: Terrain.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_terrain", "Landroidx/compose/ui/graphics/vector/ImageVector;", "Terrain", "Landroidx/compose/material/icons/Icons$Outlined;", "getTerrain", "(Landroidx/compose/material/icons/Icons$Outlined;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class TerrainKt {
    private static ImageVector _terrain;

    public static final ImageVector getTerrain(Icons.Outlined $this$Terrain) {
        if (_terrain != null) {
            ImageVector imageVector = _terrain;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_Terrain__u24lambda_u241 = new ImageVector.Builder("Outlined.Terrain", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(14.0f, 6.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-4.22f, 5.63f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.25f, 1.67f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(14.0f, 9.33f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(19.0f, 16.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(-8.46f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-4.01f, -5.37f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(1.0f, 18.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(22.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(14.0f, 6.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(5.0f, 16.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.52f, -2.03f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(8.04f, 16.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineTo(5.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _terrain = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_Terrain__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _terrain;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
