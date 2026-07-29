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
import kotlin.Metadata;
import kotlin.jvm.internal.Intrinsics;

/* compiled from: PartyMode.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_partyMode", "Landroidx/compose/ui/graphics/vector/ImageVector;", "PartyMode", "Landroidx/compose/material/icons/Icons$Outlined;", "getPartyMode", "(Landroidx/compose/material/icons/Icons$Outlined;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class PartyModeKt {
    private static ImageVector _partyMode;

    public static final ImageVector getPartyMode(Icons.Outlined $this$PartyMode) {
        if (_partyMode != null) {
            ImageVector imageVector = _partyMode;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_PartyMode__u24lambda_u241 = new ImageVector.Builder("Outlined.PartyMode", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(20.0f, 4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(-3.17f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(15.0f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(9.0f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(7.17f, 4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(4.0f, 4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-1.1f, 0.0f, -2.0f, 0.9f, -2.0f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, 1.1f, 0.9f, 2.0f, 2.0f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(16.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(1.1f, 0.0f, 2.0f, -0.9f, 2.0f, -2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(22.0f, 6.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, -1.1f, -0.9f, -2.0f, -2.0f, -2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(20.0f, 18.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(4.0f, 18.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(4.0f, 6.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(4.05f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(0.59f, -0.65f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(9.88f, 4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(4.24f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.24f, 1.35f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(0.59f, 0.65f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(20.0f, 6.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(9.0f, 12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, -1.66f, 1.34f, -3.0f, 3.0f, -3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(3.98f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.92f, -1.21f, -2.35f, -2.0f, -3.98f, -2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-2.76f, 0.0f, -5.0f, 2.24f, -5.0f, 5.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, 0.34f, 0.04f, 0.68f, 0.1f, 1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(2.08f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.11f, -0.31f, -0.18f, -0.65f, -0.18f, -1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(15.0f, 12.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, 1.66f, -1.34f, 3.0f, -3.0f, 3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(8.02f, 15.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.92f, 1.21f, 2.35f, 2.0f, 3.98f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(2.76f, 0.0f, 5.0f, -2.24f, 5.0f, -5.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, -0.34f, -0.03f, -0.68f, -0.1f, -1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(-2.08f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.11f, 0.31f, 0.18f, 0.65f, 0.18f, 1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _partyMode = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_PartyMode__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _partyMode;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
