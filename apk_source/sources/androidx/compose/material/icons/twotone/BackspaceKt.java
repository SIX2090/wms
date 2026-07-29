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
import kotlin.Deprecated;
import kotlin.Metadata;
import kotlin.ReplaceWith;
import kotlin.jvm.internal.Intrinsics;

/* compiled from: Backspace.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0005\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u001e\u0010\u0002\u001a\u00020\u0001*\u00020\u00038FX\u0087\u0004¢\u0006\f\u0012\u0004\b\u0004\u0010\u0005\u001a\u0004\b\u0006\u0010\u0007¨\u0006\b"}, d2 = {"_backspace", "Landroidx/compose/ui/graphics/vector/ImageVector;", "Backspace", "Landroidx/compose/material/icons/Icons$TwoTone;", "getBackspace$annotations", "(Landroidx/compose/material/icons/Icons$TwoTone;)V", "getBackspace", "(Landroidx/compose/material/icons/Icons$TwoTone;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class BackspaceKt {
    private static ImageVector _backspace;

    @Deprecated(message = "Use the AutoMirrored version at Icons.AutoMirrored.TwoTone.Backspace", replaceWith = @ReplaceWith(expression = "Icons.AutoMirrored.TwoTone.Backspace", imports = {"androidx.compose.material.icons.automirrored.twotone.Backspace"}))
    public static /* synthetic */ void getBackspace$annotations(Icons.TwoTone twoTone) {
    }

    public static final ImageVector getBackspace(Icons.TwoTone $this$Backspace) {
        if (_backspace != null) {
            ImageVector imageVector = _backspace;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_Backspace__u24lambda_u242 = new ImageVector.Builder("TwoTone.Backspace", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(7.06f, 5.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(2.4f, 12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(4.67f, 7.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineTo(22.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(5.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineTo(7.06f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.01f, 0.0f, 0.01f, 0.0f, 0.0f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(9.0f, 8.41f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(10.41f, 7.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(14.0f, 10.59f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(17.59f, 7.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(19.0f, 8.41f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(15.41f, 12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(19.0f, 15.59f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(17.59f, 17.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(14.0f, 13.41f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(10.41f, 17.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(9.0f, 15.59f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(12.59f, 12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(9.0f, 8.41f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_Backspace__u24lambda_u242, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 0.3f, null, 0.3f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null);
        int pathFillType$iv2 = VectorKt.getDefaultFillType();
        Brush fill$iv$iv2 = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv2 = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv2 = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv2 = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv2.moveTo(22.0f, 3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineTo(7.0f, 3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveToRelative(-0.69f, 0.0f, -1.23f, 0.35f, -1.59f, 0.88f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineTo(0.0f, 12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineToRelative(5.41f, 8.11f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveToRelative(0.36f, 0.53f, 0.9f, 0.89f, 1.59f, 0.89f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.horizontalLineToRelative(15.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveToRelative(1.1f, 0.0f, 2.0f, -0.9f, 2.0f, -2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineTo(24.0f, 5.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveToRelative(0.0f, -1.1f, -0.9f, -2.0f, -2.0f, -2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.close();
        $this$PathData_u24lambda_u240$iv$iv$iv2.moveTo(22.0f, 19.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineTo(7.07f, 19.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineTo(2.4f, 12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineToRelative(4.66f, -7.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineTo(22.0f, 5.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.verticalLineToRelative(14.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.close();
        $this$PathData_u24lambda_u240$iv$iv$iv2.moveTo(10.41f, 17.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineTo(14.0f, 13.41f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineTo(17.59f, 17.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineTo(19.0f, 15.59f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineTo(15.41f, 12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineTo(19.0f, 8.41f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineTo(17.59f, 7.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineTo(14.0f, 10.59f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineTo(10.41f, 7.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineTo(9.0f, 8.41f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineTo(12.59f, 12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineTo(9.0f, 15.59f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.close();
        _backspace = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_Backspace__u24lambda_u242, $this$PathData_u24lambda_u240$iv$iv$iv2.getNodes(), pathFillType$iv2, "", fill$iv$iv2, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv2, strokeLineJoin$iv$iv2, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _backspace;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
