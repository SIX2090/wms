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

/* compiled from: TextRotationAngledown.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_textRotationAngledown", "Landroidx/compose/ui/graphics/vector/ImageVector;", "TextRotationAngledown", "Landroidx/compose/material/icons/Icons$Outlined;", "getTextRotationAngledown", "(Landroidx/compose/material/icons/Icons$Outlined;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class TextRotationAngledownKt {
    private static ImageVector _textRotationAngledown;

    public static final ImageVector getTextRotationAngledown(Icons.Outlined $this$TextRotationAngledown) {
        if (_textRotationAngledown != null) {
            ImageVector imageVector = _textRotationAngledown;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_TextRotationAngledown__u24lambda_u241 = new ImageVector.Builder("Outlined.TextRotationAngledown", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(15.0f, 21.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(-4.24f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-1.41f, 1.41f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-9.2f, -9.19f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-1.41f, 1.41f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(9.19f, 9.19f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(10.76f, 21.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(15.0f, 21.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(11.25f, 8.48f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(3.54f, 3.54f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-0.92f, 2.19f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.48f, 1.48f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(4.42f, -11.14f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-1.06f, -1.05f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(7.57f, 7.92f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(9.06f, 9.4f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(2.19f, -0.92f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(17.84f, 5.43f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-2.23f, 4.87f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-2.64f, -2.64f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(4.87f, -2.23f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _textRotationAngledown = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_TextRotationAngledown__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _textRotationAngledown;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
