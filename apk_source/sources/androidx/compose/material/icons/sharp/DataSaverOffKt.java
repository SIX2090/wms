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

/* compiled from: DataSaverOff.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_dataSaverOff", "Landroidx/compose/ui/graphics/vector/ImageVector;", "DataSaverOff", "Landroidx/compose/material/icons/Icons$Sharp;", "getDataSaverOff", "(Landroidx/compose/material/icons/Icons$Sharp;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class DataSaverOffKt {
    private static ImageVector _dataSaverOff;

    public static final ImageVector getDataSaverOff(Icons.Sharp $this$DataSaverOff) {
        if (_dataSaverOff != null) {
            ImageVector imageVector = _dataSaverOff;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_DataSaverOff__u24lambda_u241 = new ImageVector.Builder("Sharp.DataSaverOff", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(13.0f, 2.05f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(3.03f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(3.39f, 0.49f, 6.0f, 3.39f, 6.0f, 6.92f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, 0.9f, -0.18f, 1.75f, -0.48f, 2.54f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(2.6f, 1.53f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(21.68f, 14.83f, 22.0f, 13.45f, 22.0f, 12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(22.0f, 6.82f, 18.05f, 2.55f, 13.0f, 2.05f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(12.0f, 19.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-3.87f, 0.0f, -7.0f, -3.13f, -7.0f, -7.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, -3.53f, 2.61f, -6.43f, 6.0f, -6.92f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(2.05f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(5.94f, 2.55f, 2.0f, 6.81f, 2.0f, 12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, 5.52f, 4.47f, 10.0f, 9.99f, 10.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(3.31f, 0.0f, 6.24f, -1.61f, 8.06f, -4.09f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-2.6f, -1.53f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(16.17f, 17.98f, 14.21f, 19.0f, 12.0f, 19.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _dataSaverOff = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_DataSaverOff__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _dataSaverOff;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
