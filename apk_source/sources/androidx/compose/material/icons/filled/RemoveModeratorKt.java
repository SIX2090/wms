package androidx.compose.material.icons.filled;

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

/* compiled from: RemoveModerator.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_removeModerator", "Landroidx/compose/ui/graphics/vector/ImageVector;", "RemoveModerator", "Landroidx/compose/material/icons/Icons$Filled;", "getRemoveModerator", "(Landroidx/compose/material/icons/Icons$Filled;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class RemoveModeratorKt {
    private static ImageVector _removeModerator;

    public static final ImageVector getRemoveModerator(Icons.Filled $this$RemoveModerator) {
        if (_removeModerator != null) {
            ImageVector imageVector = _removeModerator;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_RemoveModerator__u24lambda_u241 = new ImageVector.Builder("Filled.RemoveModerator", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(22.27f, 21.73f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-3.54f, -3.55f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(5.78f, 5.23f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(2.27f, 1.72f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(1.0f, 2.99f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(3.01f, 5.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineTo(3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(6.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, 5.55f, 3.84f, 10.74f, 9.0f, 12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(2.16f, -0.53f, 4.08f, -1.76f, 5.6f, -3.41f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(21.0f, 23.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.27f, -1.27f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(13.0f, 9.92f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(6.67f, 6.67f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(20.51f, 14.87f, 21.0f, 12.96f, 21.0f, 11.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(5.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-9.0f, -4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-5.48f, 2.44f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(11.0f, 7.92f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(2.0f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _removeModerator = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_RemoveModerator__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _removeModerator;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
