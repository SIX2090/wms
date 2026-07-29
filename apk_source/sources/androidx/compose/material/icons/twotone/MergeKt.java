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

/* compiled from: Merge.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_merge", "Landroidx/compose/ui/graphics/vector/ImageVector;", "Merge", "Landroidx/compose/material/icons/Icons$TwoTone;", "getMerge", "(Landroidx/compose/material/icons/Icons$TwoTone;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class MergeKt {
    private static ImageVector _merge;

    public static final ImageVector getMerge(Icons.TwoTone $this$Merge) {
        if (_merge != null) {
            ImageVector imageVector = _merge;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_Merge__u24lambda_u241 = new ImageVector.Builder("TwoTone.Merge", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(6.41f, 21.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(5.0f, 19.59f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(4.83f, -4.83f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.75f, -0.75f, 1.17f, -1.77f, 1.17f, -2.83f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(-5.1f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(9.41f, 8.41f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(8.0f, 7.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(4.0f, -4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(4.0f, 4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-1.41f, 1.41f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(13.0f, 6.83f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(5.1f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, 1.06f, 0.42f, 2.08f, 1.17f, 2.83f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(19.0f, 19.59f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(17.59f, 21.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(12.0f, 15.41f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(6.41f, 21.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _merge = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_Merge__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _merge;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
