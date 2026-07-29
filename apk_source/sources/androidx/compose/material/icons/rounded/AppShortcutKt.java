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
import kotlin.Metadata;
import kotlin.jvm.internal.Intrinsics;

/* compiled from: AppShortcut.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_appShortcut", "Landroidx/compose/ui/graphics/vector/ImageVector;", "AppShortcut", "Landroidx/compose/material/icons/Icons$Rounded;", "getAppShortcut", "(Landroidx/compose/material/icons/Icons$Rounded;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class AppShortcutKt {
    private static ImageVector _appShortcut;

    public static final ImageVector getAppShortcut(Icons.Rounded $this$AppShortcut) {
        if (_appShortcut != null) {
            ImageVector imageVector = _appShortcut;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_AppShortcut__u24lambda_u244 = new ImageVector.Builder("Rounded.AppShortcut", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(17.0f, 18.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineTo(7.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(6.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(10.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, -1.1f, -0.9f, -2.0f, -2.0f, -2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineTo(7.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(5.9f, 1.0f, 5.0f, 1.9f, 5.0f, 3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(18.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, 1.1f, 0.9f, 2.0f, 2.0f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(10.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(1.1f, 0.0f, 2.0f, -0.9f, 2.0f, -2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(-4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(-2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(18.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_AppShortcut__u24lambda_u244, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null);
        int pathFillType$iv2 = VectorKt.getDefaultFillType();
        Brush fill$iv$iv2 = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv2 = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv2 = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv2 = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv2.moveTo(20.38f, 9.62f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineToRelative(0.4f, 0.87f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveToRelative(0.09f, 0.2f, 0.37f, 0.2f, 0.46f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineToRelative(0.4f, -0.87f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineToRelative(0.87f, -0.4f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveToRelative(0.2f, -0.09f, 0.2f, -0.37f, 0.0f, -0.46f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineToRelative(-0.87f, -0.4f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineToRelative(-0.4f, -0.87f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveToRelative(-0.09f, -0.2f, -0.37f, -0.2f, -0.46f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineToRelative(-0.4f, 0.87f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineToRelative(-0.87f, 0.4f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveToRelative(-0.2f, 0.09f, -0.2f, 0.37f, 0.0f, 0.46f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.lineTo(20.38f, 9.62f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.close();
        ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_AppShortcut__u24lambda_u244, $this$PathData_u24lambda_u240$iv$iv$iv2.getNodes(), pathFillType$iv2, "", fill$iv$iv2, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv2, strokeLineJoin$iv$iv2, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null);
        int pathFillType$iv3 = VectorKt.getDefaultFillType();
        Brush fill$iv$iv3 = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv3 = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv3 = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv3 = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv3.moveTo(15.54f, 9.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.lineToRelative(-0.79f, 1.75f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.lineTo(13.0f, 11.54f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.curveToRelative(-0.39f, 0.18f, -0.39f, 0.73f, 0.0f, 0.91f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.lineToRelative(1.75f, 0.79f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.lineTo(15.54f, 15.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.curveToRelative(0.18f, 0.39f, 0.73f, 0.39f, 0.91f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.lineToRelative(0.79f, -1.75f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.lineTo(19.0f, 12.46f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.curveToRelative(0.39f, -0.18f, 0.39f, -0.73f, 0.0f, -0.91f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.lineToRelative(-1.75f, -0.79f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.lineTo(16.46f, 9.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.curveTo(16.28f, 8.61f, 15.72f, 8.61f, 15.54f, 9.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.close();
        ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_AppShortcut__u24lambda_u244, $this$PathData_u24lambda_u240$iv$iv$iv3.getNodes(), pathFillType$iv3, "", fill$iv$iv3, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv3, strokeLineJoin$iv$iv3, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null);
        int pathFillType$iv4 = VectorKt.getDefaultFillType();
        Brush fill$iv$iv4 = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv4 = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv4 = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv4 = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv4.moveTo(20.77f, 13.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.lineToRelative(-0.4f, 0.87f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.lineToRelative(-0.87f, 0.4f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.curveToRelative(-0.2f, 0.09f, -0.2f, 0.37f, 0.0f, 0.46f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.lineToRelative(0.87f, 0.4f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.lineToRelative(0.4f, 0.87f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.curveToRelative(0.09f, 0.2f, 0.37f, 0.2f, 0.46f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.lineToRelative(0.4f, -0.87f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.lineToRelative(0.87f, -0.4f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.curveToRelative(0.2f, -0.09f, 0.2f, -0.37f, 0.0f, -0.46f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.lineToRelative(-0.87f, -0.4f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.lineToRelative(-0.4f, -0.87f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.curveTo(21.14f, 13.31f, 20.86f, 13.31f, 20.77f, 13.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.close();
        _appShortcut = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_AppShortcut__u24lambda_u244, $this$PathData_u24lambda_u240$iv$iv$iv4.getNodes(), pathFillType$iv4, "", fill$iv$iv4, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv4, strokeLineJoin$iv$iv4, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _appShortcut;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
