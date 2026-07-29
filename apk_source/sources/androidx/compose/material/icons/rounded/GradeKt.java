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

/* compiled from: Grade.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_grade", "Landroidx/compose/ui/graphics/vector/ImageVector;", "Grade", "Landroidx/compose/material/icons/Icons$Rounded;", "getGrade", "(Landroidx/compose/material/icons/Icons$Rounded;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class GradeKt {
    private static ImageVector _grade;

    public static final ImageVector getGrade(Icons.Rounded $this$Grade) {
        if (_grade != null) {
            ImageVector imageVector = _grade;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_Grade__u24lambda_u241 = new ImageVector.Builder("Rounded.Grade", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(12.0f, 17.27f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(5.17f, 3.12f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.38f, 0.23f, 0.85f, -0.11f, 0.75f, -0.54f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-1.37f, -5.88f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(4.56f, -3.95f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.33f, -0.29f, 0.16f, -0.84f, -0.29f, -0.88f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-6.01f, -0.51f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-2.35f, -5.54f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.17f, -0.41f, -0.75f, -0.41f, -0.92f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(9.19f, 8.63f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-6.01f, 0.51f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.44f, 0.04f, -0.62f, 0.59f, -0.28f, 0.88f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(4.56f, 3.95f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-1.37f, 5.88f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.1f, 0.43f, 0.37f, 0.77f, 0.75f, 0.54f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(12.0f, 17.27f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _grade = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_Grade__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _grade;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
