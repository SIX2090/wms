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
import kotlin.Deprecated;
import kotlin.Metadata;
import kotlin.ReplaceWith;
import kotlin.jvm.internal.Intrinsics;

/* compiled from: AccessibleForward.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0005\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u001e\u0010\u0002\u001a\u00020\u0001*\u00020\u00038FX\u0087\u0004¢\u0006\f\u0012\u0004\b\u0004\u0010\u0005\u001a\u0004\b\u0006\u0010\u0007¨\u0006\b"}, d2 = {"_accessibleForward", "Landroidx/compose/ui/graphics/vector/ImageVector;", "AccessibleForward", "Landroidx/compose/material/icons/Icons$Outlined;", "getAccessibleForward$annotations", "(Landroidx/compose/material/icons/Icons$Outlined;)V", "getAccessibleForward", "(Landroidx/compose/material/icons/Icons$Outlined;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class AccessibleForwardKt {
    private static ImageVector _accessibleForward;

    @Deprecated(message = "Use the AutoMirrored version at Icons.AutoMirrored.Outlined.AccessibleForward", replaceWith = @ReplaceWith(expression = "Icons.AutoMirrored.Outlined.AccessibleForward", imports = {"androidx.compose.material.icons.automirrored.outlined.AccessibleForward"}))
    public static /* synthetic */ void getAccessibleForward$annotations(Icons.Outlined outlined) {
    }

    public static final ImageVector getAccessibleForward(Icons.Outlined $this$AccessibleForward) {
        if (_accessibleForward != null) {
            ImageVector imageVector = _accessibleForward;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_AccessibleForward__u24lambda_u242 = new ImageVector.Builder("Outlined.AccessibleForward", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(18.0f, 4.54f);
        $this$PathData_u24lambda_u240$iv$iv$iv.moveToRelative(-2.0f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.arcToRelative(2.0f, 2.0f, 0.0f, true, true, 4.0f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.arcToRelative(2.0f, 2.0f, 0.0f, true, true, -4.0f, 0.0f);
        ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_AccessibleForward__u24lambda_u242, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null);
        int pathFillType$iv2 = VectorKt.getDefaultFillType();
        Brush fill$iv$iv2 = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv2 = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv2 = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv2 = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv2.moveTo(15.0f, 17.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.horizontalLineToRelative(-2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveToRelative(0.0f, 1.65f, -1.35f, 3.0f, -3.0f, 3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.reflectiveCurveToRelative(-3.0f, -1.35f, -3.0f, -3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.reflectiveCurveToRelative(1.35f, -3.0f, 3.0f, -3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.verticalLineToRelative(-2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveToRelative(-2.76f, 0.0f, -5.0f, 2.24f, -5.0f, 5.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.reflectiveCurveToRelative(2.24f, 5.0f, 5.0f, 5.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.reflectiveCurveToRelative(5.0f, -2.24f, 5.0f, -5.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.close();
        $this$PathData_u24lambda_u240$iv$iv$iv2.moveTo(18.0f, 13.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.horizontalLineToRelative(-1.86f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineToRelative(1.67f, -3.67f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveTo(18.42f, 8.5f, 17.44f, 7.0f, 15.96f, 7.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.horizontalLineToRelative(-5.2f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveToRelative(-0.81f, 0.0f, -1.54f, 0.47f, -1.87f, 1.2f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineTo(8.22f, 10.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineToRelative(1.92f, 0.53f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineToRelative(0.65f, -1.53f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineTo(13.0f, 9.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineToRelative(-1.83f, 4.1f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveToRelative(-0.6f, 1.33f, 0.39f, 2.9f, 1.85f, 2.9f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineTo(18.0f, 16.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.verticalLineToRelative(5.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.horizontalLineToRelative(2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.verticalLineToRelative(-5.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveToRelative(0.0f, -1.1f, -0.9f, -2.0f, -2.0f, -2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.close();
        _accessibleForward = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_AccessibleForward__u24lambda_u242, $this$PathData_u24lambda_u240$iv$iv$iv2.getNodes(), pathFillType$iv2, "", fill$iv$iv2, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv2, strokeLineJoin$iv$iv2, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _accessibleForward;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
