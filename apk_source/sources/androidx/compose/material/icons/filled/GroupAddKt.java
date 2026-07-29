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

/* compiled from: GroupAdd.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_groupAdd", "Landroidx/compose/ui/graphics/vector/ImageVector;", "GroupAdd", "Landroidx/compose/material/icons/Icons$Filled;", "getGroupAdd", "(Landroidx/compose/material/icons/Icons$Filled;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class GroupAddKt {
    private static ImageVector _groupAdd;

    public static final ImageVector getGroupAdd(Icons.Filled $this$GroupAdd) {
        if (_groupAdd != null) {
            ImageVector imageVector = _groupAdd;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_GroupAdd__u24lambda_u245 = new ImageVector.Builder("Filled.GroupAdd", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(22.0f, 9.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(0.0f, -2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-2.0f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(0.0f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-2.0f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(0.0f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(2.0f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(0.0f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(2.0f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(0.0f, -2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(2.0f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(0.0f, -2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_GroupAdd__u24lambda_u245, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null);
        int pathFillType$iv2 = VectorKt.getDefaultFillType();
        Brush fill$iv$iv2 = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv2 = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv2 = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv2 = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv2.moveTo(8.0f, 12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveToRelative(2.21f, 0.0f, 4.0f, -1.79f, 4.0f, -4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.reflectiveCurveToRelative(-1.79f, -4.0f, -4.0f, -4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.reflectiveCurveTo(4.0f, 5.79f, 4.0f, 8.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.reflectiveCurveTo(5.79f, 12.0f, 8.0f, 12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.close();
        ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_GroupAdd__u24lambda_u245, $this$PathData_u24lambda_u240$iv$iv$iv2.getNodes(), pathFillType$iv2, "", fill$iv$iv2, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv2, strokeLineJoin$iv$iv2, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null);
        int pathFillType$iv3 = VectorKt.getDefaultFillType();
        Brush fill$iv$iv3 = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv3 = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv3 = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv3 = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv3.moveTo(8.0f, 13.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.curveToRelative(-2.67f, 0.0f, -8.0f, 1.34f, -8.0f, 4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.verticalLineToRelative(3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.horizontalLineToRelative(16.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.verticalLineToRelative(-3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.curveTo(16.0f, 14.34f, 10.67f, 13.0f, 8.0f, 13.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.close();
        ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_GroupAdd__u24lambda_u245, $this$PathData_u24lambda_u240$iv$iv$iv3.getNodes(), pathFillType$iv3, "", fill$iv$iv3, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv3, strokeLineJoin$iv$iv3, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null);
        int pathFillType$iv4 = VectorKt.getDefaultFillType();
        Brush fill$iv$iv4 = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv4 = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv4 = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv4 = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv4.moveTo(12.51f, 4.05f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.curveTo(13.43f, 5.11f, 14.0f, 6.49f, 14.0f, 8.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.reflectiveCurveToRelative(-0.57f, 2.89f, -1.49f, 3.95f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.curveTo(14.47f, 11.7f, 16.0f, 10.04f, 16.0f, 8.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.reflectiveCurveTo(14.47f, 4.3f, 12.51f, 4.05f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.close();
        ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_GroupAdd__u24lambda_u245, $this$PathData_u24lambda_u240$iv$iv$iv4.getNodes(), pathFillType$iv4, "", fill$iv$iv4, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv4, strokeLineJoin$iv$iv4, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null);
        int pathFillType$iv5 = VectorKt.getDefaultFillType();
        Brush fill$iv$iv5 = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv5 = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv5 = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv5 = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv5.moveTo(16.53f, 13.83f);
        $this$PathData_u24lambda_u240$iv$iv$iv5.curveTo(17.42f, 14.66f, 18.0f, 15.7f, 18.0f, 17.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv5.verticalLineToRelative(3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv5.horizontalLineToRelative(2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv5.verticalLineToRelative(-3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv5.curveTo(20.0f, 15.55f, 18.41f, 14.49f, 16.53f, 13.83f);
        $this$PathData_u24lambda_u240$iv$iv$iv5.close();
        _groupAdd = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_GroupAdd__u24lambda_u245, $this$PathData_u24lambda_u240$iv$iv$iv5.getNodes(), pathFillType$iv5, "", fill$iv$iv5, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv5, strokeLineJoin$iv$iv5, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _groupAdd;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
