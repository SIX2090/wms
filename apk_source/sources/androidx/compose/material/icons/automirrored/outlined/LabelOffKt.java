package androidx.compose.material.icons.automirrored.outlined;

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

/* compiled from: LabelOff.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_labelOff", "Landroidx/compose/ui/graphics/vector/ImageVector;", "LabelOff", "Landroidx/compose/material/icons/Icons$AutoMirrored$Outlined;", "getLabelOff", "(Landroidx/compose/material/icons/Icons$AutoMirrored$Outlined;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class LabelOffKt {
    private static ImageVector _labelOff;

    public static final ImageVector getLabelOff(Icons.AutoMirrored.Outlined $this$LabelOff) {
        if (_labelOff != null) {
            ImageVector imageVector = _labelOff;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_LabelOff__u24lambda_u241 = new ImageVector.Builder("AutoMirrored.Outlined.LabelOff", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, true, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(16.0f, 7.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(3.55f, 5.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-1.63f, 2.29f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.43f, 1.43f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(22.0f, 12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-4.37f, -6.16f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(17.27f, 5.33f, 16.67f, 5.0f, 16.0f, 5.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-7.37f, 0.01f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(2.0f, 1.99f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineTo(16.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(2.0f, 4.03f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.58f, 1.58f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(3.22f, 5.96f, 3.0f, 6.46f, 3.0f, 7.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(10.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, 1.1f, 0.9f, 1.99f, 2.0f, 1.99f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(16.0f, 19.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.28f, 0.0f, 0.55f, -0.07f, 0.79f, -0.18f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(18.97f, 21.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.41f, -1.41f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(3.41f, 2.62f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(2.0f, 4.03f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(14.97f, 17.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineTo(5.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(7.03f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(14.97f, 17.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _labelOff = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_LabelOff__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _labelOff;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
