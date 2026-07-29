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

/* compiled from: DoneOutline.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_doneOutline", "Landroidx/compose/ui/graphics/vector/ImageVector;", "DoneOutline", "Landroidx/compose/material/icons/Icons$Filled;", "getDoneOutline", "(Landroidx/compose/material/icons/Icons$Filled;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class DoneOutlineKt {
    private static ImageVector _doneOutline;

    public static final ImageVector getDoneOutline(Icons.Filled $this$DoneOutline) {
        if (_doneOutline != null) {
            ImageVector imageVector = _doneOutline;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_DoneOutline__u24lambda_u241 = new ImageVector.Builder("Filled.DoneOutline", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(19.77f, 5.03f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.4f, 1.4f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(8.43f, 19.17f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-5.6f, -5.6f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.4f, -1.4f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(4.2f, 4.2f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(19.77f, 5.03f);
        $this$PathData_u24lambda_u240$iv$iv$iv.moveToRelative(0.0f, -2.83f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(8.43f, 13.54f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-4.2f, -4.2f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(0.0f, 13.57f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(8.43f, 22.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(24.0f, 6.43f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(19.77f, 2.2f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _doneOutline = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_DoneOutline__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _doneOutline;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
