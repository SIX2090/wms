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

/* compiled from: OfflineShare.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0005\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u001e\u0010\u0002\u001a\u00020\u0001*\u00020\u00038FX\u0087\u0004¢\u0006\f\u0012\u0004\b\u0004\u0010\u0005\u001a\u0004\b\u0006\u0010\u0007¨\u0006\b"}, d2 = {"_offlineShare", "Landroidx/compose/ui/graphics/vector/ImageVector;", "OfflineShare", "Landroidx/compose/material/icons/Icons$Outlined;", "getOfflineShare$annotations", "(Landroidx/compose/material/icons/Icons$Outlined;)V", "getOfflineShare", "(Landroidx/compose/material/icons/Icons$Outlined;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class OfflineShareKt {
    private static ImageVector _offlineShare;

    @Deprecated(message = "Use the AutoMirrored version at Icons.AutoMirrored.Outlined.OfflineShare", replaceWith = @ReplaceWith(expression = "Icons.AutoMirrored.Outlined.OfflineShare", imports = {"androidx.compose.material.icons.automirrored.outlined.OfflineShare"}))
    public static /* synthetic */ void getOfflineShare$annotations(Icons.Outlined outlined) {
    }

    public static final ImageVector getOfflineShare(Icons.Outlined $this$OfflineShare) {
        if (_offlineShare != null) {
            ImageVector imageVector = _offlineShare;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_OfflineShare__u24lambda_u243 = new ImageVector.Builder("Outlined.OfflineShare", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(6.0f, 5.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineTo(4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(16.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, 1.1f, 0.9f, 2.0f, 2.0f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(10.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(-2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineTo(6.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(5.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_OfflineShare__u24lambda_u243, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null);
        int pathFillType$iv2 = VectorKt.getDefaultFillType();
        Brush fill$iv$iv2 = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv2 = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv2 = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv2 = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv2.moveTo(18.0f, 1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.horizontalLineToRelative(-8.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveTo(8.9f, 1.0f, 8.0f, 1.9f, 8.0f, 3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.verticalLineToRelative(14.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveToRelative(0.0f, 1.1f, 0.9f, 2.0f, 2.0f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.horizontalLineToRelative(8.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveToRelative(1.1f, 0.0f, 2.0f, -0.9f, 2.0f, -2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.verticalLineTo(3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveTo(20.0f, 1.9f, 19.1f, 1.0f, 18.0f, 1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.close();
        $this$PathData_u24lambda_u240$iv$iv$iv2.moveTo(18.0f, 17.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.horizontalLineToRelative(-8.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.verticalLineToRelative(-1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.horizontalLineToRelative(8.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.verticalLineTo(17.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.close();
        $this$PathData_u24lambda_u240$iv$iv$iv2.moveTo(18.0f, 14.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.horizontalLineToRelative(-8.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.verticalLineTo(6.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.horizontalLineToRelative(8.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.verticalLineTo(14.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.close();
        $this$PathData_u24lambda_u240$iv$iv$iv2.moveTo(18.0f, 4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.horizontalLineToRelative(-8.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.verticalLineTo(3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.horizontalLineToRelative(8.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.verticalLineTo(4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.close();
        ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_OfflineShare__u24lambda_u243, $this$PathData_u24lambda_u240$iv$iv$iv2.getNodes(), pathFillType$iv2, "", fill$iv$iv2, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv2, strokeLineJoin$iv$iv2, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null);
        int pathFillType$iv3 = VectorKt.getDefaultFillType();
        Brush fill$iv$iv3 = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv3 = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv3 = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv3 = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv3.moveTo(12.5f, 10.25f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.horizontalLineToRelative(1.63f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.lineToRelative(-0.69f, 0.69f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.lineTo(14.5f, 12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.lineTo(17.0f, 9.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.lineTo(14.5f, 7.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.lineToRelative(-1.06f, 1.06f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.lineToRelative(0.69f, 0.69f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.horizontalLineTo(12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.curveToRelative(-0.55f, 0.0f, -1.0f, 0.45f, -1.0f, 1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.verticalLineTo(12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.horizontalLineToRelative(1.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.verticalLineTo(10.25f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.close();
        _offlineShare = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_OfflineShare__u24lambda_u243, $this$PathData_u24lambda_u240$iv$iv$iv3.getNodes(), pathFillType$iv3, "", fill$iv$iv3, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv3, strokeLineJoin$iv$iv3, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _offlineShare;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
