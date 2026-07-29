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

/* compiled from: EditLocation.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_editLocation", "Landroidx/compose/ui/graphics/vector/ImageVector;", "EditLocation", "Landroidx/compose/material/icons/Icons$Sharp;", "getEditLocation", "(Landroidx/compose/material/icons/Icons$Sharp;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class EditLocationKt {
    private static ImageVector _editLocation;

    public static final ImageVector getEditLocation(Icons.Sharp $this$EditLocation) {
        if (_editLocation != null) {
            ImageVector imageVector = _editLocation;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_EditLocation__u24lambda_u241 = new ImageVector.Builder("Sharp.EditLocation", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(18.11f, 1.77f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(19.78f, 0.1f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(2.12f, 2.12f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-1.67f, 1.67f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-2.12f, -2.12f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(17.11f, 2.77f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(2.12f, 2.12f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(13.12f, 11.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(11.0f, 11.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(11.0f, 8.89f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(6.11f, -6.12f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(15.13f, 2.64f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(9.5f, 8.27f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(4.24f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(4.24f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(5.62f, -5.62f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.41f, 0.99f, 0.64f, 2.1f, 0.64f, 3.32f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, 3.32f, -2.67f, 7.25f, -8.0f, 11.8f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-5.33f, -4.55f, -8.0f, -8.48f, -8.0f, -11.8f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, -4.98f, 3.8f, -8.2f, 8.0f, -8.2f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(1.09f, 0.0f, 2.16f, 0.22f, 3.13f, 0.63f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _editLocation = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_EditLocation__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _editLocation;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
