package androidx.compose.ui.graphics;

import kotlin.Metadata;

/* compiled from: AndroidMatrixConversions.android.kt */
@Metadata(d1 = {"\u0000\u0014\n\u0000\n\u0002\u0010\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0005\u001a\u001c\u0010\u0000\u001a\u00020\u0001*\u00020\u00022\u0006\u0010\u0003\u001a\u00020\u0004ø\u0001\u0000¢\u0006\u0004\b\u0005\u0010\u0006\u001a\u001c\u0010\u0000\u001a\u00020\u0001*\u00020\u00042\u0006\u0010\u0003\u001a\u00020\u0002ø\u0001\u0000¢\u0006\u0004\b\u0007\u0010\b\u0082\u0002\u0007\n\u0005\b¡\u001e0\u0001¨\u0006\t"}, d2 = {"setFrom", "", "Landroid/graphics/Matrix;", "matrix", "Landroidx/compose/ui/graphics/Matrix;", "setFrom-EL8BTi8", "(Landroid/graphics/Matrix;[F)V", "setFrom-tU-YjHk", "([FLandroid/graphics/Matrix;)V", "ui-graphics_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes11.dex */
public final class AndroidMatrixConversions_androidKt {
    /* renamed from: setFrom-tU-YjHk, reason: not valid java name */
    public static final void m3617setFromtUYjHk(float[] $this$setFrom_u2dtU_u2dYjHk, android.graphics.Matrix matrix) {
        matrix.getValues($this$setFrom_u2dtU_u2dYjHk);
        float scaleX = $this$setFrom_u2dtU_u2dYjHk[0];
        float skewX = $this$setFrom_u2dtU_u2dYjHk[1];
        float translateX = $this$setFrom_u2dtU_u2dYjHk[2];
        float skewY = $this$setFrom_u2dtU_u2dYjHk[3];
        float scaleY = $this$setFrom_u2dtU_u2dYjHk[4];
        float translateY = $this$setFrom_u2dtU_u2dYjHk[5];
        float persp0 = $this$setFrom_u2dtU_u2dYjHk[6];
        float persp1 = $this$setFrom_u2dtU_u2dYjHk[7];
        float persp2 = $this$setFrom_u2dtU_u2dYjHk[8];
        $this$setFrom_u2dtU_u2dYjHk[0] = scaleX;
        $this$setFrom_u2dtU_u2dYjHk[1] = skewY;
        $this$setFrom_u2dtU_u2dYjHk[2] = 0.0f;
        $this$setFrom_u2dtU_u2dYjHk[3] = persp0;
        $this$setFrom_u2dtU_u2dYjHk[4] = skewX;
        $this$setFrom_u2dtU_u2dYjHk[5] = scaleY;
        $this$setFrom_u2dtU_u2dYjHk[6] = 0.0f;
        $this$setFrom_u2dtU_u2dYjHk[7] = persp1;
        $this$setFrom_u2dtU_u2dYjHk[8] = 0.0f;
        $this$setFrom_u2dtU_u2dYjHk[9] = 0.0f;
        $this$setFrom_u2dtU_u2dYjHk[10] = 1.0f;
        $this$setFrom_u2dtU_u2dYjHk[11] = 0.0f;
        $this$setFrom_u2dtU_u2dYjHk[12] = translateX;
        $this$setFrom_u2dtU_u2dYjHk[13] = translateY;
        $this$setFrom_u2dtU_u2dYjHk[14] = 0.0f;
        $this$setFrom_u2dtU_u2dYjHk[15] = persp2;
    }

    /* JADX WARN: Removed duplicated region for block: B:31:0x0081  */
    /* JADX WARN: Removed duplicated region for block: B:34:0x00d9  */
    /* renamed from: setFrom-EL8BTi8, reason: not valid java name */
    /*
        Code decompiled incorrectly, please refer to instructions dump.
        To view partially-correct add '--show-bad-code' argument
    */
    public static final void m3616setFromEL8BTi8(android.graphics.Matrix r22, float[] r23) {
        /*
            Method dump skipped, instructions count: 233
            To view this dump add '--comments-level debug' option
        */
        throw new UnsupportedOperationException("Method not decompiled: androidx.compose.ui.graphics.AndroidMatrixConversions_androidKt.m3616setFromEL8BTi8(android.graphics.Matrix, float[]):void");
    }
}
