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

/* compiled from: PhotoFilter.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_photoFilter", "Landroidx/compose/ui/graphics/vector/ImageVector;", "PhotoFilter", "Landroidx/compose/material/icons/Icons$TwoTone;", "getPhotoFilter", "(Landroidx/compose/material/icons/Icons$TwoTone;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class PhotoFilterKt {
    private static ImageVector _photoFilter;

    public static final ImageVector getPhotoFilter(Icons.TwoTone $this$PhotoFilter) {
        if (_photoFilter != null) {
            ImageVector imageVector = _photoFilter;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_PhotoFilter__u24lambda_u241 = new ImageVector.Builder("TwoTone.PhotoFilter", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(19.0f, 10.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(9.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(4.98f, 19.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(4.98f, 5.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(9.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(13.98f, 3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(5.0f, 3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-1.1f, 0.0f, -2.0f, 0.9f, -2.0f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(14.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, 1.1f, 0.9f, 2.0f, 2.0f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(14.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(1.1f, 0.0f, 2.0f, -0.9f, 2.0f, -2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(-9.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(-2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(16.06f, 7.94f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(17.0f, 10.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(0.94f, -2.06f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(20.0f, 7.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-2.06f, -0.94f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(17.0f, 4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-0.94f, 2.06f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(14.0f, 7.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(12.0f, 8.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-1.25f, 2.75f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(8.0f, 12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(2.75f, 1.25f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(12.0f, 16.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.25f, -2.75f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(16.0f, 12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-2.75f, -1.25f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _photoFilter = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_PhotoFilter__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _photoFilter;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
