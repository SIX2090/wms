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

/* compiled from: EditAttributes.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_editAttributes", "Landroidx/compose/ui/graphics/vector/ImageVector;", "EditAttributes", "Landroidx/compose/material/icons/Icons$Outlined;", "getEditAttributes", "(Landroidx/compose/material/icons/Icons$Outlined;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class EditAttributesKt {
    private static ImageVector _editAttributes;

    public static final ImageVector getEditAttributes(Icons.Outlined $this$EditAttributes) {
        if (_editAttributes != null) {
            ImageVector imageVector = _editAttributes;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_EditAttributes__u24lambda_u241 = new ImageVector.Builder("Outlined.EditAttributes", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(17.63f, 7.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(6.37f, 7.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(3.96f, 7.0f, 2.0f, 9.24f, 2.0f, 12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveToRelative(1.96f, 5.0f, 4.37f, 5.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(11.26f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(2.41f, 0.0f, 4.37f, -2.24f, 4.37f, -5.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveToRelative(-1.96f, -5.0f, -4.37f, -5.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(17.63f, 15.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(6.37f, 15.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(5.09f, 15.0f, 4.0f, 13.63f, 4.0f, 12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveToRelative(1.09f, -3.0f, 2.37f, -3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(11.26f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(18.91f, 9.0f, 20.0f, 10.37f, 20.0f, 12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveToRelative(-1.09f, 3.0f, -2.37f, 3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(7.24f, 13.06f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-1.87f, -1.87f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-0.7f, 0.7f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(2.57f, 2.57f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(4.22f, -4.22f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-0.7f, -0.7f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _editAttributes = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_EditAttributes__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _editAttributes;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
