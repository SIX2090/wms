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

/* compiled from: LayersClear.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_layersClear", "Landroidx/compose/ui/graphics/vector/ImageVector;", "LayersClear", "Landroidx/compose/material/icons/Icons$Sharp;", "getLayersClear", "(Landroidx/compose/material/icons/Icons$Sharp;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class LayersClearKt {
    private static ImageVector _layersClear;

    public static final ImageVector getLayersClear(Icons.Sharp $this$LayersClear) {
        if (_layersClear != null) {
            ImageVector imageVector = _layersClear;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_LayersClear__u24lambda_u241 = new ImageVector.Builder("Sharp.LayersClear", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(21.0f, 9.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-9.0f, -7.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-2.59f, 2.02f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(7.87f, 7.87f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(21.0f, 14.07f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-1.63f, -1.27f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-0.67f, 0.52f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.43f, 1.43f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(3.41f, 0.86f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(2.0f, 2.27f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(4.22f, 4.22f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(3.0f, 9.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(9.0f, 7.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(2.1f, -1.63f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.42f, 1.42f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-3.53f, 2.75f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-7.37f, -5.73f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(3.0f, 14.07f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(9.0f, 7.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(4.95f, -3.85f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(20.73f, 21.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.41f, -1.41f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _layersClear = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_LayersClear__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _layersClear;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
