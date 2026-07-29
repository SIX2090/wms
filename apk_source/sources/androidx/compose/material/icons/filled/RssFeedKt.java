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

/* compiled from: RssFeed.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_rssFeed", "Landroidx/compose/ui/graphics/vector/ImageVector;", "RssFeed", "Landroidx/compose/material/icons/Icons$Filled;", "getRssFeed", "(Landroidx/compose/material/icons/Icons$Filled;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class RssFeedKt {
    private static ImageVector _rssFeed;

    public static final ImageVector getRssFeed(Icons.Filled $this$RssFeed) {
        if (_rssFeed != null) {
            ImageVector imageVector = _rssFeed;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_RssFeed__u24lambda_u242 = new ImageVector.Builder("Filled.RssFeed", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(6.18f, 17.82f);
        $this$PathData_u24lambda_u240$iv$iv$iv.moveToRelative(-2.18f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.arcToRelative(2.18f, 2.18f, 0.0f, true, true, 4.36f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.arcToRelative(2.18f, 2.18f, 0.0f, true, true, -4.36f, 0.0f);
        ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_RssFeed__u24lambda_u242, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null);
        int pathFillType$iv2 = VectorKt.getDefaultFillType();
        Brush fill$iv$iv2 = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv2 = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv2 = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv2 = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv2.moveTo(4.0f, 4.44f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.verticalLineToRelative(2.83f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveToRelative(7.03f, 0.0f, 12.73f, 5.7f, 12.73f, 12.73f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.horizontalLineToRelative(2.83f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveToRelative(0.0f, -8.59f, -6.97f, -15.56f, -15.56f, -15.56f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.close();
        $this$PathData_u24lambda_u240$iv$iv$iv2.moveTo(4.0f, 10.1f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.verticalLineToRelative(2.83f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveToRelative(3.9f, 0.0f, 7.07f, 3.17f, 7.07f, 7.07f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.horizontalLineToRelative(2.83f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveToRelative(0.0f, -5.47f, -4.43f, -9.9f, -9.9f, -9.9f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.close();
        _rssFeed = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_RssFeed__u24lambda_u242, $this$PathData_u24lambda_u240$iv$iv$iv2.getNodes(), pathFillType$iv2, "", fill$iv$iv2, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv2, strokeLineJoin$iv$iv2, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _rssFeed;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
