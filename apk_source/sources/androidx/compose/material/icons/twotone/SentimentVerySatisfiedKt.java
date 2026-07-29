package androidx.compose.material.icons.twotone;

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

/* compiled from: SentimentVerySatisfied.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_sentimentVerySatisfied", "Landroidx/compose/ui/graphics/vector/ImageVector;", "SentimentVerySatisfied", "Landroidx/compose/material/icons/Icons$TwoTone;", "getSentimentVerySatisfied", "(Landroidx/compose/material/icons/Icons$TwoTone;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class SentimentVerySatisfiedKt {
    private static ImageVector _sentimentVerySatisfied;

    public static final ImageVector getSentimentVerySatisfied(Icons.TwoTone $this$SentimentVerySatisfied) {
        if (_sentimentVerySatisfied != null) {
            ImageVector imageVector = _sentimentVerySatisfied;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_SentimentVerySatisfied__u24lambda_u242 = new ImageVector.Builder("TwoTone.SentimentVerySatisfied", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(12.0f, 4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-4.42f, 0.0f, -8.0f, 3.58f, -8.0f, 8.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveToRelative(3.58f, 8.0f, 8.0f, 8.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveToRelative(8.0f, -3.58f, 8.0f, -8.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveToRelative(-3.58f, -8.0f, -8.0f, -8.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(8.88f, 7.82f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(11.0f, 9.94f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(9.94f, 11.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(8.88f, 9.94f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(7.82f, 11.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(6.76f, 9.94f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(2.12f, -2.12f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(12.0f, 17.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-2.33f, 0.0f, -4.31f, -1.46f, -5.11f, -3.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(10.22f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.8f, 2.04f, -2.78f, 3.5f, -5.11f, 3.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(16.18f, 11.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-1.06f, -1.06f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(14.06f, 11.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(13.0f, 9.94f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(2.12f, -2.12f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(2.12f, 2.12f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(16.18f, 11.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_SentimentVerySatisfied__u24lambda_u242, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 0.3f, null, 0.3f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null);
        int pathFillType$iv2 = VectorKt.getDefaultFillType();
        Brush fill$iv$iv2 = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv2 = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv2 = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv2 = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv2.moveTo(8.88f, 9.94f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineTo(9.94f, 11.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineTo(11.0f, 9.94f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineTo(8.88f, 7.82f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineTo(6.76f, 9.94f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineTo(7.82f, 11.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.close();
        $this$PathData_u24lambda_u240$iv$iv$iv2.moveTo(13.0f, 9.94f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineTo(14.06f, 11.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineToRelative(1.06f, -1.06f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineTo(16.18f, 11.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineToRelative(1.06f, -1.06f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineToRelative(-2.12f, -2.12f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.close();
        $this$PathData_u24lambda_u240$iv$iv$iv2.moveTo(11.99f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveTo(6.47f, 2.0f, 2.0f, 6.47f, 2.0f, 12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.reflectiveCurveToRelative(4.47f, 10.0f, 9.99f, 10.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.reflectiveCurveTo(22.0f, 17.53f, 22.0f, 12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.reflectiveCurveTo(17.52f, 2.0f, 11.99f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.close();
        $this$PathData_u24lambda_u240$iv$iv$iv2.moveTo(12.0f, 20.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveToRelative(-4.42f, 0.0f, -8.0f, -3.58f, -8.0f, -8.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.reflectiveCurveToRelative(3.58f, -8.0f, 8.0f, -8.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.reflectiveCurveToRelative(8.0f, 3.58f, 8.0f, 8.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.reflectiveCurveToRelative(-3.58f, 8.0f, -8.0f, 8.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.close();
        $this$PathData_u24lambda_u240$iv$iv$iv2.moveTo(12.0f, 17.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveToRelative(2.33f, 0.0f, 4.31f, -1.46f, 5.11f, -3.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineTo(6.89f, 14.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveToRelative(0.8f, 2.04f, 2.78f, 3.5f, 5.11f, 3.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.close();
        _sentimentVerySatisfied = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_SentimentVerySatisfied__u24lambda_u242, $this$PathData_u24lambda_u240$iv$iv$iv2.getNodes(), pathFillType$iv2, "", fill$iv$iv2, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv2, strokeLineJoin$iv$iv2, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _sentimentVerySatisfied;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
