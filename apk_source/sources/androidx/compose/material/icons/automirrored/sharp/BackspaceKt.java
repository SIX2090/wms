package androidx.compose.material.icons.automirrored.sharp;

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

/* compiled from: Backspace.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_backspace", "Landroidx/compose/ui/graphics/vector/ImageVector;", "Backspace", "Landroidx/compose/material/icons/Icons$AutoMirrored$Sharp;", "getBackspace", "(Landroidx/compose/material/icons/Icons$AutoMirrored$Sharp;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class BackspaceKt {
    private static ImageVector _backspace;

    public static final ImageVector getBackspace(Icons.AutoMirrored.Sharp $this$Backspace) {
        if (_backspace != null) {
            ImageVector imageVector = _backspace;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_Backspace__u24lambda_u241 = new ImageVector.Builder("AutoMirrored.Sharp.Backspace", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, true, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(24.0f, 3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(6.0f, 3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-6.0f, 9.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(6.0f, 9.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(18.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(24.0f, 3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(19.0f, 15.59f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(17.59f, 17.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(14.0f, 13.41f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(10.41f, 17.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(9.0f, 15.59f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(12.59f, 12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(9.0f, 8.41f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(10.41f, 7.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(14.0f, 10.59f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(17.59f, 7.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(19.0f, 8.41f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(15.41f, 12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(19.0f, 15.59f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _backspace = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_Backspace__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _backspace;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
