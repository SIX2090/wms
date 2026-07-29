package androidx.compose.material.icons.sharp;

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

/* compiled from: PhoneDisabled.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_phoneDisabled", "Landroidx/compose/ui/graphics/vector/ImageVector;", "PhoneDisabled", "Landroidx/compose/material/icons/Icons$Sharp;", "getPhoneDisabled", "(Landroidx/compose/material/icons/Icons$Sharp;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class PhoneDisabledKt {
    private static ImageVector _phoneDisabled;

    public static final ImageVector getPhoneDisabled(Icons.Sharp $this$PhoneDisabled) {
        if (_phoneDisabled != null) {
            ImageVector imageVector = _phoneDisabled;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_PhoneDisabled__u24lambda_u241 = new ImageVector.Builder("Sharp.PhoneDisabled", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(14.52f, 17.35f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(11.39f, 19.83f, 7.36f, 21.22f, 3.0f, 20.97f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(-5.51f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(5.27f, -0.61f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(2.52f, 2.52f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.81f, -0.41f, 1.58f, -0.9f, 2.3f, -1.45f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(1.39f, 4.22f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.42f, -1.41f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(21.19f, 21.2f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-1.41f, 1.41f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(14.52f, 17.35f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(15.91f, 13.11f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.56f, -0.73f, 1.05f, -1.51f, 1.47f, -2.33f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-2.53f, -2.53f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(15.46f, 3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(5.51f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.25f, 4.37f, -1.15f, 8.4f, -3.63f, 11.54f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(15.91f, 13.11f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _phoneDisabled = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_PhoneDisabled__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _phoneDisabled;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
