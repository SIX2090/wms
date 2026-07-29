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

/* compiled from: EditLocation.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_editLocation", "Landroidx/compose/ui/graphics/vector/ImageVector;", "EditLocation", "Landroidx/compose/material/icons/Icons$Rounded;", "getEditLocation", "(Landroidx/compose/material/icons/Icons$Rounded;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class EditLocationKt {
    private static ImageVector _editLocation;

    public static final ImageVector getEditLocation(Icons.Rounded $this$EditLocation) {
        if (_editLocation != null) {
            ImageVector imageVector = _editLocation;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_EditLocation__u24lambda_u241 = new ImageVector.Builder("Rounded.EditLocation", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(12.0f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-4.2f, 0.0f, -8.0f, 3.22f, -8.0f, 8.2f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, 3.18f, 2.45f, 6.92f, 7.34f, 11.23f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.38f, 0.33f, 0.95f, 0.33f, 1.33f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(17.55f, 17.12f, 20.0f, 13.38f, 20.0f, 10.2f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(20.0f, 5.22f, 16.2f, 2.0f, 12.0f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(9.73f, 13.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineTo(8.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(-1.44f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(3.93f, -3.92f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.43f, 1.43f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-3.77f, 3.78f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(9.99f, 13.45f, 9.87f, 13.5f, 9.73f, 13.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(15.28f, 8.16f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-0.7f, 0.7f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-1.44f, -1.44f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(0.7f, -0.7f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.15f, -0.15f, 0.39f, -0.15f, 0.54f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(0.9f, 0.9f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(15.43f, 7.77f, 15.43f, 8.01f, 15.28f, 8.16f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _editLocation = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_EditLocation__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _editLocation;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
