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
import kotlin.Deprecated;
import kotlin.Metadata;
import kotlin.ReplaceWith;
import kotlin.jvm.internal.Intrinsics;

/* compiled from: Note.kt */
@Metadata(d1 = {"\u0000\u0010\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0005\"\u0010\u0010\u0000\u001a\u0004\u0018\u00010\u0001X\u0082\u000e¢\u0006\u0002\n\u0000\"\u001e\u0010\u0002\u001a\u00020\u0001*\u00020\u00038FX\u0087\u0004¢\u0006\f\u0012\u0004\b\u0004\u0010\u0005\u001a\u0004\b\u0006\u0010\u0007¨\u0006\b"}, d2 = {"_note", "Landroidx/compose/ui/graphics/vector/ImageVector;", "Note", "Landroidx/compose/material/icons/Icons$Sharp;", "getNote$annotations", "(Landroidx/compose/material/icons/Icons$Sharp;)V", "getNote", "(Landroidx/compose/material/icons/Icons$Sharp;)Landroidx/compose/ui/graphics/vector/ImageVector;", "material-icons-extended_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class NoteKt {
    private static ImageVector _note;

    @Deprecated(message = "Use the AutoMirrored version at Icons.AutoMirrored.Sharp.Note", replaceWith = @ReplaceWith(expression = "Icons.AutoMirrored.Sharp.Note", imports = {"androidx.compose.material.icons.automirrored.sharp.Note"}))
    public static /* synthetic */ void getNote$annotations(Icons.Sharp sharp) {
    }

    public static final ImageVector getNote(Icons.Sharp $this$Note) {
        if (_note != null) {
            ImageVector imageVector = _note;
            Intrinsics.checkNotNull(imageVector);
            return imageVector;
        }
        ImageVector.Builder $this$_get_Note__u24lambda_u241 = new ImageVector.Builder("Sharp.Note", Dp.m6094constructorimpl(24.0f), Dp.m6094constructorimpl(24.0f), 24.0f, 24.0f, 0L, 0, false, 96, null);
        int pathFillType$iv = VectorKt.getDefaultFillType();
        Brush fill$iv$iv = new SolidColor(Color.INSTANCE.m3772getBlack0d7_KjU(), null);
        int strokeLineCap$iv$iv = StrokeCap.INSTANCE.m4098getButtKaPHkGw();
        int strokeLineJoin$iv$iv = StrokeJoin.INSTANCE.m4108getBevelLxFBmk8();
        PathBuilder $this$PathData_u24lambda_u240$iv$iv$iv = new PathBuilder();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(22.0f, 10.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(-6.0f, -6.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(2.0f, 4.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.verticalLineToRelative(16.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.horizontalLineToRelative(20.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(22.0f, 10.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        $this$PathData_u24lambda_u240$iv$iv$iv.moveTo(15.0f, 5.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineToRelative(5.5f, 5.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(15.0f, 11.0f);
        $this$PathData_u24lambda_u240$iv$iv$iv.lineTo(15.0f, 5.5f);
        $this$PathData_u24lambda_u240$iv$iv$iv.close();
        _note = ImageVector.Builder.m4379addPathoIyEayM$default($this$_get_Note__u24lambda_u241, $this$PathData_u24lambda_u240$iv$iv$iv.getNodes(), pathFillType$iv, "", fill$iv$iv, 1.0f, null, 1.0f, 1.0f, strokeLineCap$iv$iv, strokeLineJoin$iv$iv, 1.0f, 0.0f, 0.0f, 0.0f, 14336, null).build();
        ImageVector imageVector2 = _note;
        Intrinsics.checkNotNull(imageVector2);
        return imageVector2;
    }
}
