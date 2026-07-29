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

/* compiled from: NearMeDisabled.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_nearMeDisabled", "Landroidx/compose/ui/graphics/vector/ImageVector;", "NearMeDisabled", "Landroidx/compose/material/icons/Icons$Outlined;", "getNearMeDisabled", "(Landroidx/compose/material/icons/Icons$Outlined;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class NearMeDisabledKt {
    private static ImageVector _nearMeDisabled;

    public static final ImageVector getNearMeDisabled(Icons.Outlined $this$NearMeDisabled) {
        if (_nearMeDisabled != null) {
            ImageVector imageVector = _nearMeDisabled;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_NearMeDisabled__u24lambda_u241 = new ImageVector.Builder("Outlined.NearMeDisabled", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(12.0f, 6.34f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(21.0f, 3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-3.34f, 9.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-1.56f, -1.56f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.5f, -4.05f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-4.05f, 1.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(12.0f, 6.34f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(21.19f, 21.19f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-5.07f, -5.07f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(14.31f, 21.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineTo(12.9f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-2.83f, -7.07f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(3.0f, 11.1f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(9.69f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(4.88f, -1.81f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(2.81f, 2.81f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.41f, -1.41f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(18.38f, 18.38f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(21.19f, 21.19f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(14.57f, 14.57f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(9.43f, 9.43f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-2.71f, 1.01f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(4.89f, 1.95f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.95f, 4.89f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(14.57f, 14.57f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _nearMeDisabled = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_NearMeDisabled__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _nearMeDisabled;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
