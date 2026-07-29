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

/* compiled from: LocalPolice.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_localPolice", "Landroidx/compose/ui/graphics/vector/ImageVector;", "LocalPolice", "Landroidx/compose/material/icons/Icons$Filled;", "getLocalPolice", "(Landroidx/compose/material/icons/Icons$Filled;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class LocalPoliceKt {
    private static ImageVector _localPolice;

    public static final ImageVector getLocalPolice(Icons.Filled $this$LocalPolice) {
        if (_localPolice != null) {
            ImageVector imageVector = _localPolice;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_LocalPolice__u24lambda_u241 = new ImageVector.Builder("Filled.LocalPolice", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(12.0f, 1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(3.0f, 5.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(6.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, 5.55f, 3.84f, 10.74f, 9.0f, 12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(5.16f, -1.26f, 9.0f, -6.45f, 9.0f, -12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(5.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(12.0f, 1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(14.5f, 12.59f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(0.9f, 3.88f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(12.0f, 14.42f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-3.4f, 2.05f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(0.9f, -3.87f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-3.0f, -2.59f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(3.96f, -0.34f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(12.0f, 6.02f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.54f, 3.64f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(17.5f, 10.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(14.5f, 12.59f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _localPolice = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_LocalPolice__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _localPolice;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
