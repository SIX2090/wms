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

/* compiled from: SnippetFolder.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u0015\u0010\u0002\u001a\u00020\u0001*\u00020\u00038F¢\u0006\u0006\u001a\u0004\b\u0004\u0010\u0005¨\u0006\u0006"}, d2 = {"_snippetFolder", "Landroidx/compose/ui/graphics/vector/ImageVector;", "SnippetFolder", "Landroidx/compose/material/icons/Icons$Filled;", "getSnippetFolder", "(Landroidx/compose/material/icons/Icons$Filled;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class SnippetFolderKt {
    private static ImageVector _snippetFolder;

    public static final ImageVector getSnippetFolder(Icons.Filled $this$SnippetFolder) {
        if (_snippetFolder != null) {
            ImageVector imageVector = _snippetFolder;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_SnippetFolder__u24lambda_u241 = new ImageVector.Builder("Filled.SnippetFolder", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(15.88f, 10.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(1.62f, 1.62f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(3.38f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-3.0f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(-5.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineTo(15.88f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(22.0f, 8.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(10.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, 1.1f, -0.9f, 2.0f, -2.0f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineTo(4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-1.1f, 0.0f, -2.0f, -0.9f, -2.0f, -2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(2.01f, 6.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(2.01f, 4.9f, 2.9f, 4.0f, 4.0f, 4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(6.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(2.0f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(8.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveTo(21.1f, 6.0f, 22.0f, 6.9f, 22.0f, 8.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(19.0f, 11.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(16.5f, 9.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineTo(13.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(8.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(6.0f, 0.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineTo(11.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _snippetFolder = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_SnippetFolder__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _snippetFolder;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
