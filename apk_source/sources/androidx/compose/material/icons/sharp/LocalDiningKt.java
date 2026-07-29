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

/* compiled from: LocalDining.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_localDining", "Landroidx/compose/ui/graphics/vector/ImageVector;", "LocalDining", "Landroidx/compose/material/icons/Icons$Sharp;", "getLocalDining", "(Landroidx/compose/material/icons/Icons$Sharp;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class LocalDiningKt {
    private static ImageVector _localDining;

    public static final ImageVector getLocalDining(Icons.Sharp $this$LocalDining) {
        if (_localDining != null) {
            ImageVector imageVector = _localDining;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_LocalDining__u24lambda_u241 = new ImageVector.Builder("Sharp.LocalDining", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(8.1f, 13.34f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(2.83f, -2.83f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(3.91f, 3.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-1.56f, 1.56f, -1.56f, 4.09f, 0.0f, 5.66f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(4.19f, 4.18f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(14.88f, 11.53f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(1.53f, 0.71f, 3.68f, 0.21f, 5.27f, -1.38f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(1.91f, -1.91f, 2.28f, -4.65f, 0.81f, -6.12f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-1.46f, -1.46f, -4.2f, -1.1f, -6.12f, 0.81f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-1.59f, 1.59f, -2.09f, 3.74f, -1.38f, 5.27f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(3.7f, 19.87f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.41f, 1.41f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(12.0f, 14.41f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(6.88f, 6.88f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.41f, -1.41f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(13.41f, 13.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.47f, -1.47f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _localDining = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_LocalDining__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _localDining;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
