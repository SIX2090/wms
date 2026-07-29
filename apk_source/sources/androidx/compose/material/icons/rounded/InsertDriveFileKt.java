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

/* compiled from: InsertDriveFile.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0005\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u001e\u0010\u0002\u001a\u00020\u0001*\u00020\u00038FX\u0087\u0004¢\u0006\f\u0012\u0004\b\u0004\u0010\u0005\u001a\u0004\b\u0006\u0010\u0007¨\u0006\b"}, d2 = {"_insertDriveFile", "Landroidx/compose/ui/graphics/vector/ImageVector;", "InsertDriveFile", "Landroidx/compose/material/icons/Icons$Rounded;", "getInsertDriveFile$annotations", "(Landroidx/compose/material/icons/Icons$Rounded;)V", "getInsertDriveFile", "(Landroidx/compose/material/icons/Icons$Rounded;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class InsertDriveFileKt {
    private static ImageVector _insertDriveFile;

    @Deprecated(message = "Use the AutoMirrored version at Icons.AutoMirrored.Rounded.InsertDriveFile", replaceWith = @ReplaceWith(expression = "Icons.AutoMirrored.Rounded.InsertDriveFile", imports = {"androidx.compose.material.icons.automirrored.rounded.InsertDriveFile"}))
    public static /* synthetic */ void getInsertDriveFile$annotations(Icons.Rounded rounded) {
    }

    public static final ImageVector getInsertDriveFile(Icons.Rounded $this$InsertDriveFile) {
        if (_insertDriveFile != null) {
            ImageVector imageVector = _insertDriveFile;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_InsertDriveFile__u24lambda_u241 = new ImageVector.Builder("Rounded.InsertDriveFile", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(6.0f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-1.1f, 0.0f, -1.99f, 0.9f, -1.99f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(4.0f, 20.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, 1.1f, 0.89f, 2.0f, 1.99f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(18.0f, 22.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(1.1f, 0.0f, 2.0f, -0.9f, 2.0f, -2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(20.0f, 8.83f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(0.0f, -0.53f, -0.21f, -1.04f, -0.59f, -1.41f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-4.83f, -4.83f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.37f, -0.38f, -0.88f, -0.59f, -1.41f, -0.59f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(6.0f, 2.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(13.0f, 8.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(13.0f, 3.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(18.5f, 9.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(14.0f, 9.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.curveToRelative(-0.55f, 0.0f, -1.0f, -0.45f, -1.0f, -1.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _insertDriveFile = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_InsertDriveFile__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _insertDriveFile;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
