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

/* compiled from: AssistantDirection.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0005\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u001e\u0010\u0002\u001a\u00020\u0001*\u00020\u00038FX\u0087\u0004¢\u0006\f\u0012\u0004\b\u0004\u0010\u0005\u001a\u0004\b\u0006\u0010\u0007¨\u0006\b"}, d2 = {"_assistantDirection", "Landroidx/compose/ui/graphics/vector/ImageVector;", "AssistantDirection", "Landroidx/compose/material/icons/Icons$Rounded;", "getAssistantDirection$annotations", "(Landroidx/compose/material/icons/Icons$Rounded;)V", "getAssistantDirection", "(Landroidx/compose/material/icons/Icons$Rounded;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class AssistantDirectionKt {
    private static ImageVector _assistantDirection;

    @Deprecated(message = "Use the AutoMirrored version at Icons.AutoMirrored.Rounded.AssistantDirection", replaceWith = @ReplaceWith(expression = "Icons.AutoMirrored.Rounded.AssistantDirection", imports = {"androidx.compose.material.icons.automirrored.rounded.AssistantDirection"}))
    public static /* synthetic */ void getAssistantDirection$annotations(Icons.Rounded rounded) {
    }

    public static final ImageVector getAssistantDirection(Icons.Rounded $this$AssistantDirection) {
        if (_assistantDirection != null) {
            ImageVector imageVector = _assistantDirection;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_AssistantDirection__u24lambda_u241 = new ImageVector.Builder("Rounded.AssistantDirection", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(13.5f, 10.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineTo(9.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.55f, 0.0f, -1.0f, 0.45f, -1.0f, 1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, 0.55f, 0.45f, 1.0f, 1.0f, 1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.55f, 0.0f, 1.0f, -0.45f, 1.0f, -1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(-2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(3.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(1.29f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, 0.45f, 0.54f, 0.67f, 0.85f, 0.35f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(2.29f, -2.29f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.2f, -0.2f, 0.2f, -0.51f, 0.0f, -0.71f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-2.29f, -2.29f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.31f, -0.31f, -0.85f, -0.09f, -0.85f, 0.35f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(10.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(12.0f, 1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(5.9f, 1.0f, 1.0f, 5.9f, 1.0f, 12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveToRelative(4.9f, 11.0f, 11.0f, 11.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveToRelative(11.0f, -4.9f, 11.0f, -11.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.reflectiveCurveTo(18.1f, 1.0f, 12.0f, 1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(19.73f, 12.58f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-7.19f, 7.22f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.35f, 0.27f, -0.79f, 0.27f, -1.15f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(4.2f, 12.58f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.27f, -0.36f, -0.27f, -0.8f, 0.0f, -1.16f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(7.19f, -7.22f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.35f, -0.27f, 0.79f, -0.27f, 1.15f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(7.19f, 7.22f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(20.09f, 11.69f, 20.09f, 12.22f, 19.73f, 12.58f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _assistantDirection = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_AssistantDirection__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _assistantDirection;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
