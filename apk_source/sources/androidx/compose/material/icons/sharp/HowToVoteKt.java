package androidx.compose.material.icons.sharp;

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

/* compiled from: HowToVote.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_howToVote", "Landroidx/compose/ui/graphics/vector/ImageVector;", "HowToVote", "Landroidx/compose/material/icons/Icons$Sharp;", "getHowToVote", "(Landroidx/compose/material/icons/Icons$Sharp;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class HowToVoteKt {
    private static ImageVector _howToVote;

    public static final ImageVector getHowToVote(Icons.Sharp $this$HowToVote) {
        if (_howToVote != null) {
            ImageVector imageVector = _howToVote;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_HowToVote__u24lambda_u241 = new ImageVector.Builder("Sharp.HowToVote", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(18.0f, 13.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(-0.68f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-2.0f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(1.91f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(19.0f, 17.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(5.0f, 17.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.78f, -2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(2.05f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-2.0f, -2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(6.0f, 13.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-3.0f, 3.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(6.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(18.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(-6.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(19.81f, 7.96f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(13.45f, 1.6f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(5.68f, 9.36f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(6.36f, 6.36f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(7.77f, -7.76f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(13.46f, 4.41f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(17.0f, 7.95f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-4.95f, 4.95f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-3.54f, -3.54f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(4.95f, -4.95f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _howToVote = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_HowToVote__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _howToVote;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
