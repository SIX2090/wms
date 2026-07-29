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

/* compiled from: AdminPanelSettings.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_adminPanelSettings", "Landroidx/compose/ui/graphics/vector/ImageVector;", "AdminPanelSettings", "Landroidx/compose/material/icons/Icons$TwoTone;", "getAdminPanelSettings", "(Landroidx/compose/material/icons/Icons$TwoTone;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class AdminPanelSettingsKt {
    private static ImageVector _adminPanelSettings;

    public static final ImageVector getAdminPanelSettings(Icons.TwoTone $this$AdminPanelSettings) {
        if (_adminPanelSettings != null) {
            ImageVector imageVector = _adminPanelSettings;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_AdminPanelSettings__u24lambda_u245 = new ImageVector.Builder("TwoTone.AdminPanelSettings", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(16.0f, 7.58f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-5.5f, -2.4f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(5.0f, 7.58f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(3.6f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, 3.5f, 2.33f, 6.74f, 5.5f, 7.74f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.25f, -0.08f, 0.49f, -0.2f, 0.73f, -0.3f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(11.08f, 18.11f, 11.0f, 17.56f, 11.0f, 17.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, -2.97f, 2.16f, -5.43f, 5.0f, -5.91f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(7.58f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_AdminPanelSettings__u24lambda_u245, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 0.3f, null, 0.3f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null);
        int pathFillType$iv2 = VectorKt.getDefaultFillType();
        Brush fill$iv$iv2 = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv2 = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv2 = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv2 = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv2.moveTo(17.0f, 13.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveToRelative(-2.21f, 0.0f, -4.0f, 1.79f, -4.0f, 4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveToRelative(0.0f, 2.21f, 1.79f, 4.0f, 4.0f, 4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.reflectiveCurveToRelative(4.0f, -1.79f, 4.0f, -4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveTo(21.0f, 14.79f, 19.21f, 13.0f, 17.0f, 13.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.close();
        $this$PathData_u24lambda_u240$iv$iv$iv2.moveTo(17.0f, 14.38f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveToRelative(0.62f, 0.0f, 1.12f, 0.51f, 1.12f, 1.12f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.reflectiveCurveToRelative(-0.51f, 1.12f, -1.12f, 1.12f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.reflectiveCurveToRelative(-1.12f, -0.51f, -1.12f, -1.12f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.reflectiveCurveTo(16.38f, 14.38f, 17.0f, 14.38f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.close();
        $this$PathData_u24lambda_u240$iv$iv$iv2.moveTo(17.0f, 19.75f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveToRelative(-0.93f, 0.0f, -1.74f, -0.46f, -2.24f, -1.17f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveToRelative(0.05f, -0.72f, 1.51f, -1.08f, 2.24f, -1.08f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.reflectiveCurveToRelative(2.19f, 0.36f, 2.24f, 1.08f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.curveTo(18.74f, 19.29f, 17.93f, 19.75f, 17.0f, 19.75f);
        $this$PathData_u24lambda_u240$iv$iv$iv2.close();
        ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_AdminPanelSettings__u24lambda_u245, $this$PathData_u24lambda_u240$iv$iv$iv2.getNodes(), pathFillType$iv2, "", fill$iv$iv2, 0.3f, null, 0.3f, 1.0f, strokeLineCap$iv$iv2, strokeLineJoin$iv$iv2, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null);
        int pathFillType$iv3 = VectorKt.getDefaultFillType();
        Brush fill$iv$iv3 = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv3 = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv3 = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv3 = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv3.moveTo(17.0f, 15.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.moveToRelative(-1.12f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.arcToRelative(1.12f, 1.12f, 0.0f, true, true, 2.24f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv3.arcToRelative(1.12f, 1.12f, 0.0f, true, true, -2.24f, 0.0f);
        ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_AdminPanelSettings__u24lambda_u245, $this$PathData_u24lambda_u240$iv$iv$iv3.getNodes(), pathFillType$iv3, "", fill$iv$iv3, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv3, strokeLineJoin$iv$iv3, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null);
        int pathFillType$iv4 = VectorKt.getDefaultFillType();
        Brush fill$iv$iv4 = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv4 = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv4 = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv4 = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv4.moveTo(18.0f, 11.09f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.verticalLineTo(6.27f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.lineTo(10.5f, 3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.lineTo(3.0f, 6.27f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.verticalLineToRelative(4.91f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.curveToRelative(0.0f, 4.54f, 3.2f, 8.79f, 7.5f, 9.82f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.curveToRelative(0.55f, -0.13f, 1.08f, -0.32f, 1.6f, -0.55f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.curveTo(13.18f, 21.99f, 14.97f, 23.0f, 17.0f, 23.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.curveToRelative(3.31f, 0.0f, 6.0f, -2.69f, 6.0f, -6.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.curveTo(23.0f, 14.03f, 20.84f, 11.57f, 18.0f, 11.09f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.close();
        $this$PathData_u24lambda_u240$iv$iv$iv4.moveTo(11.0f, 17.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.curveToRelative(0.0f, 0.56f, 0.08f, 1.11f, 0.23f, 1.62f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.curveToRelative(-0.24f, 0.11f, -0.48f, 0.22f, -0.73f, 0.3f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.curveToRelative(-3.17f, -1.0f, -5.5f, -4.24f, -5.5f, -7.74f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.verticalLineToRelative(-3.6f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.lineToRelative(5.5f, -2.4f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.lineToRelative(5.5f, 2.4f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.verticalLineToRelative(3.51f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.curveTo(13.16f, 11.57f, 11.0f, 14.03f, 11.0f, 17.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.close();
        $this$PathData_u24lambda_u240$iv$iv$iv4.moveTo(17.0f, 21.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.curveToRelative(-2.21f, 0.0f, -4.0f, -1.79f, -4.0f, -4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.curveToRelative(0.0f, -2.21f, 1.79f, -4.0f, 4.0f, -4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.reflectiveCurveToRelative(4.0f, 1.79f, 4.0f, 4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.curveTo(21.0f, 19.21f, 19.21f, 21.0f, 17.0f, 21.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv4.close();
        ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_AdminPanelSettings__u24lambda_u245, $this$PathData_u24lambda_u240$iv$iv$iv4.getNodes(), pathFillType$iv4, "", fill$iv$iv4, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv4, strokeLineJoin$iv$iv4, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null);
        int pathFillType$iv5 = VectorKt.getDefaultFillType();
        Brush fill$iv$iv5 = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv5 = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv5 = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv5 = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv5.moveTo(17.0f, 17.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv5.curveToRelative(-0.73f, 0.0f, -2.19f, 0.36f, -2.24f, 1.08f);
        $this$PathData_u24lambda_u240$iv$iv$iv5.curveToRelative(0.5f, 0.71f, 1.32f, 1.17f, 2.24f, 1.17f);
        $this$PathData_u24lambda_u240$iv$iv$iv5.reflectiveCurveToRelative(1.74f, -0.46f, 2.24f, -1.17f);
        $this$PathData_u24lambda_u240$iv$iv$iv5.curveTo(19.19f, 17.86f, 17.73f, 17.5f, 17.0f, 17.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv5.close();
        _adminPanelSettings = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_AdminPanelSettings__u24lambda_u245, $this$PathData_u24lambda_u240$iv$iv$iv5.getNodes(), pathFillType$iv5, "", fill$iv$iv5, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv5, strokeLineJoin$iv$iv5, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _adminPanelSettings;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
