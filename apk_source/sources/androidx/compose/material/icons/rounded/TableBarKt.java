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

/* compiled from: TableBar.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_tableBar", "Landroidx/compose/ui/graphics/vector/ImageVector;", "TableBar", "Landroidx/compose/material/icons/Icons$Rounded;", "getTableBar", "(Landroidx/compose/material/icons/Icons$Rounded;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class TableBarKt {
    private static ImageVector _tableBar;

    public static final ImageVector getTableBar(Icons.Rounded $this$TableBar) {
        if (_tableBar != null) {
            ImageVector imageVector = _tableBar;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_TableBar__u24lambda_u241 = new ImageVector.Builder("Rounded.TableBar", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(22.0f, 7.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(22.0f, 5.57f, 17.52f, 4.0f, 12.0f, 4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveTo(2.0f, 5.57f, 2.0f, 7.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, 1.81f, 3.95f, 3.31f, 9.0f, 3.48f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(15.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineTo(9.35f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.82f, 0.0f, -1.55f, 0.5f, -1.86f, 1.26f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-0.99f, 2.47f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(6.27f, 19.34f, 6.71f, 20.0f, 7.37f, 20.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.38f, 0.0f, 0.72f, -0.23f, 0.86f, -0.58f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(9.2f, 17.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(5.6f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(0.97f, 2.42f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.14f, 0.35f, 0.48f, 0.58f, 0.86f, 0.58f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.66f, 0.0f, 1.11f, -0.66f, 0.86f, -1.27f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-0.99f, -2.47f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(16.2f, 15.5f, 15.46f, 15.0f, 14.65f, 15.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineTo(13.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(-4.02f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(18.05f, 10.81f, 22.0f, 9.31f, 22.0f, 7.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _tableBar = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_TableBar__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _tableBar;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
