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

/* compiled from: FormatColorText.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_formatColorText", "Landroidx/compose/ui/graphics/vector/ImageVector;", "FormatColorText", "Landroidx/compose/material/icons/Icons$Rounded;", "getFormatColorText", "(Landroidx/compose/material/icons/Icons$Rounded;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class FormatColorTextKt {
    private static ImageVector _formatColorText;

    public static final ImageVector getFormatColorText(Icons.Rounded $this$FormatColorText) {
        if (_formatColorText != null) {
            ImageVector imageVector = _formatColorText;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_FormatColorText__u24lambda_u242 = new ImageVector.Builder("Rounded.FormatColorText", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(20.0f, 20.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineTo(4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-1.1f, 0.0f, -2.0f, 0.9f, -2.0f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveToRelative(0.9f, 2.0f, 2.0f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(16.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(1.1f, 0.0f, 2.0f, -0.9f, 2.0f, -2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveTo(21.1f, 20.0f, 20.0f, 20.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_FormatColorText__u24lambda_u242, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null);
        int pathFillType$iv2 = VectorKt.getDefaultFillType();
        Brush fill$iv$iv2 = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv2 = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv2 = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv2 = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv2.moveTo(7.11f, 17.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineTo(7.11f, 17.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveToRelative(0.48f, 0.0f, 0.91f, -0.3f, 1.06f, -0.75f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineToRelative(1.01f, -2.83f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.horizontalLineToRelative(5.65f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineToRelative(0.99f, 2.82f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveTo(15.98f, 16.7f, 16.41f, 17.0f, 16.89f, 17.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveToRelative(0.79f, 0.0f, 1.33f, -0.79f, 1.05f, -1.52f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineTo(13.69f, 4.17f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveTo(13.43f, 3.47f, 12.75f, 3.0f, 12.0f, 3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.reflectiveCurveToRelative(-1.43f, 0.47f, -1.69f, 1.17f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineTo(6.06f, 15.48f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveTo(5.78f, 16.21f, 6.33f, 17.0f, 7.11f, 17.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.close();
        $this$PathData_u24lambda_u240$iv$iv$iv2.moveTo(11.94f, 5.6f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.horizontalLineToRelative(0.12f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineToRelative(2.03f, 5.79f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.horizontalLineTo(9.91f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineTo(11.94f, 5.6f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.close();
        _formatColorText = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_FormatColorText__u24lambda_u242, $this$PathData_u24lambda_u240$iv$iv$iv2.getNodes(), pathFillType$iv2, "", fill$iv$iv2, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv2, strokeLineJoin$iv$iv2, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _formatColorText;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
