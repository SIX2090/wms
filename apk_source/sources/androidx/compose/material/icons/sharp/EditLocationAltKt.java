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

/* compiled from: EditLocationAlt.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_editLocationAlt", "Landroidx/compose/ui/graphics/vector/ImageVector;", "EditLocationAlt", "Landroidx/compose/material/icons/Icons$Sharp;", "getEditLocationAlt", "(Landroidx/compose/material/icons/Icons$Sharp;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class EditLocationAltKt {
    private static ImageVector _editLocationAlt;

    public static final ImageVector getEditLocationAlt(Icons.Sharp $this$EditLocationAlt) {
        if (_editLocationAlt != null) {
            ImageVector imageVector = _editLocationAlt;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_EditLocationAlt__u24lambda_u241 = new ImageVector.Builder("Sharp.EditLocationAlt", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(13.95f, 13.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineTo(9.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(8.05f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(5.61f, -5.61f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(13.78f, 2.16f, 12.9f, 2.0f, 12.0f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-4.2f, 0.0f, -8.0f, 3.22f, -8.0f, 8.2f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, 3.32f, 2.67f, 7.25f, 8.0f, 11.8f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(5.33f, -4.55f, 8.0f, -8.48f, 8.0f, -11.8f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, -1.01f, -0.16f, -1.94f, -0.45f, -2.8f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(13.95f, 13.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(11.0f, 11.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(2.12f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(6.16f, -6.16f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-2.12f, -2.12f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(11.0f, 8.88f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(11.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(19.29f, 0.59f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-1.42f, 1.42f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(2.12f, 2.12f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.42f, -1.42f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(19.29f, 0.59f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _editLocationAlt = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_EditLocationAlt__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _editLocationAlt;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
