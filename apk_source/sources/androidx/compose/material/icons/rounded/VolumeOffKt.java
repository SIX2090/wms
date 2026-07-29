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
import kotlin.Deprecated;
import kotlin.Metadata;
import kotlin.ReplaceWith;
import kotlin.jvm.internal.Intrinsics;

/* compiled from: VolumeOff.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0005\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u001e\u0010\u0002\u001a\u00020\u0001*\u00020\u00038FX\u0087\u0004¢\u0006\f\u0012\u0004\b\u0004\u0010\u0005\u001a\u0004\b\u0006\u0010\u0007¨\u0006\b"}, d2 = {"_volumeOff", "Landroidx/compose/ui/graphics/vector/ImageVector;", "VolumeOff", "Landroidx/compose/material/icons/Icons$Rounded;", "getVolumeOff$annotations", "(Landroidx/compose/material/icons/Icons$Rounded;)V", "getVolumeOff", "(Landroidx/compose/material/icons/Icons$Rounded;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class VolumeOffKt {
    private static ImageVector _volumeOff;

    @Deprecated(message = "Use the AutoMirrored version at Icons.AutoMirrored.Rounded.VolumeOff", replaceWith = @ReplaceWith(expression = "Icons.AutoMirrored.Rounded.VolumeOff", imports = {"androidx.compose.material.icons.automirrored.rounded.VolumeOff"}))
    public static /* synthetic */ void getVolumeOff$annotations(Icons.Rounded rounded) {
    }

    public static final ImageVector getVolumeOff(Icons.Rounded $this$VolumeOff) {
        if (_volumeOff != null) {
            ImageVector imageVector = _volumeOff;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_VolumeOff__u24lambda_u241 = new ImageVector.Builder("Rounded.VolumeOff", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(3.63f, 3.63f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.39f, 0.39f, -0.39f, 1.02f, 0.0f, 1.41f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(7.29f, 8.7f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(7.0f, 9.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(4.0f, 9.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.55f, 0.0f, -1.0f, 0.45f, -1.0f, 1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, 0.55f, 0.45f, 1.0f, 1.0f, 1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(3.29f, 3.29f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.63f, 0.63f, 1.71f, 0.18f, 1.71f, -0.71f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(-4.17f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(4.18f, 4.18f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.49f, 0.37f, -1.02f, 0.68f, -1.6f, 0.91f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.36f, 0.15f, -0.58f, 0.53f, -0.58f, 0.92f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, 0.72f, 0.73f, 1.18f, 1.39f, 0.91f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.8f, -0.33f, 1.55f, -0.77f, 2.22f, -1.31f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.34f, 1.34f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.39f, 0.39f, 1.02f, 0.39f, 1.41f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.39f, -0.39f, 0.39f, -1.02f, 0.0f, -1.41f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(5.05f, 3.63f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.39f, -0.39f, -1.02f, -0.39f, -1.42f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(19.0f, 12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, 0.82f, -0.15f, 1.61f, -0.41f, 2.34f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.53f, 1.53f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.56f, -1.17f, 0.88f, -2.48f, 0.88f, -3.87f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, -3.83f, -2.4f, -7.11f, -5.78f, -8.4f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.59f, -0.23f, -1.22f, 0.23f, -1.22f, 0.86f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(0.19f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, 0.38f, 0.25f, 0.71f, 0.61f, 0.85f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(17.18f, 6.54f, 19.0f, 9.06f, 19.0f, 12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(10.29f, 5.71f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-0.17f, 0.17f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(12.0f, 7.76f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(12.0f, 6.41f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, -0.89f, -1.08f, -1.33f, -1.71f, -0.7f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(16.5f, 12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, -1.77f, -1.02f, -3.29f, -2.5f, -4.03f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(1.79f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(2.48f, 2.48f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.01f, -0.08f, 0.02f, -0.16f, 0.02f, -0.24f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _volumeOff = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_VolumeOff__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _volumeOff;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
