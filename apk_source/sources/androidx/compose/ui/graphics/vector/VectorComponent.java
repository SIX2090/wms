package androidx.compose.ui.graphics.vector;

import androidx.autofill.HintConstants;
import androidx.compose.runtime.MutableState;
import androidx.compose.runtime.SnapshotStateKt__SnapshotStateKt;
import androidx.compose.runtime.State;
import androidx.compose.ui.geometry.Offset;
import androidx.compose.ui.geometry.Size;
import androidx.compose.ui.graphics.ColorFilter;
import androidx.compose.ui.graphics.ImageBitmap;
import androidx.compose.ui.graphics.ImageBitmapConfig;
import androidx.compose.ui.graphics.drawscope.DrawContext;
import androidx.compose.ui.graphics.drawscope.DrawScope;
import androidx.compose.ui.graphics.drawscope.DrawTransform;
import kotlin.Metadata;
import kotlin.Unit;
import kotlin.jvm.functions.Function0;
import kotlin.jvm.functions.Function1;
import kotlin.jvm.internal.Intrinsics;

/* compiled from: Vector.kt */
@Metadata(d1 = {"\u0000`\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\u0010\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\b\n\u0002\u0018\u0002\n\u0002\b\u0005\n\u0002\u0010\u000b\n\u0000\n\u0002\u0010\u000e\n\u0002\b\u0005\n\u0002\u0018\u0002\n\u0002\b\u0004\n\u0002\u0010\u0007\n\u0002\b\u000e\b\u0000\u0018\u00002\u00020\u0001B\r\u0012\u0006\u0010\u0002\u001a\u00020\u0003¢\u0006\u0002\u0010\u0004J\b\u00106\u001a\u00020\u000eH\u0002J\b\u00107\u001a\u00020\"H\u0016J\f\u00108\u001a\u00020\u000e*\u00020\rH\u0016J\u001c\u00108\u001a\u00020\u000e*\u00020\r2\u0006\u00109\u001a\u00020-2\b\u0010:\u001a\u0004\u0018\u00010\u0011R\u001a\u0010\u0005\u001a\u00020\u00068@X\u0080\u0004ø\u0001\u0000ø\u0001\u0001¢\u0006\u0006\u001a\u0004\b\u0007\u0010\bR\u000e\u0010\t\u001a\u00020\nX\u0082\u0004¢\u0006\u0002\n\u0000R\u001f\u0010\u000b\u001a\u0013\u0012\u0004\u0012\u00020\r\u0012\u0004\u0012\u00020\u000e0\f¢\u0006\u0002\b\u000fX\u0082\u0004¢\u0006\u0002\n\u0000R/\u0010\u0012\u001a\u0004\u0018\u00010\u00112\b\u0010\u0010\u001a\u0004\u0018\u00010\u00118@@@X\u0080\u008e\u0002¢\u0006\u0012\n\u0004\b\u0017\u0010\u0018\u001a\u0004\b\u0013\u0010\u0014\"\u0004\b\u0015\u0010\u0016R \u0010\u0019\u001a\b\u0012\u0004\u0012\u00020\u000e0\u001aX\u0080\u000e¢\u0006\u000e\n\u0000\u001a\u0004\b\u001b\u0010\u001c\"\u0004\b\u001d\u0010\u001eR\u000e\u0010\u001f\u001a\u00020 X\u0082\u000e¢\u0006\u0002\n\u0000R\u001a\u0010!\u001a\u00020\"X\u0086\u000e¢\u0006\u000e\n\u0000\u001a\u0004\b#\u0010$\"\u0004\b%\u0010&R\u0016\u0010'\u001a\u00020(X\u0082\u000eø\u0001\u0000ø\u0001\u0001¢\u0006\u0004\n\u0002\u0010)R\u0011\u0010\u0002\u001a\u00020\u0003¢\u0006\b\n\u0000\u001a\u0004\b*\u0010+R\u000e\u0010,\u001a\u00020-X\u0082\u000e¢\u0006\u0002\n\u0000R\u000e\u0010.\u001a\u00020-X\u0082\u000e¢\u0006\u0002\n\u0000R\u0010\u0010/\u001a\u0004\u0018\u00010\u0011X\u0082\u000e¢\u0006\u0002\n\u0000R1\u00100\u001a\u00020(2\u0006\u0010\u0010\u001a\u00020(8@@@X\u0080\u008e\u0002ø\u0001\u0000ø\u0001\u0001¢\u0006\u0012\n\u0004\b5\u0010\u0018\u001a\u0004\b1\u00102\"\u0004\b3\u00104\u0082\u0002\u000b\n\u0005\b¡\u001e0\u0001\n\u0002\b!¨\u0006;"}, d2 = {"Landroidx/compose/ui/graphics/vector/VectorComponent;", "Landroidx/compose/ui/graphics/vector/VNode;", "root", "Landroidx/compose/ui/graphics/vector/GroupComponent;", "(Landroidx/compose/ui/graphics/vector/GroupComponent;)V", "cacheBitmapConfig", "Landroidx/compose/ui/graphics/ImageBitmapConfig;", "getCacheBitmapConfig-_sVssgQ$ui_release", "()I", "cacheDrawScope", "Landroidx/compose/ui/graphics/vector/DrawCache;", "drawVectorBlock", "Lkotlin/Function1;", "Landroidx/compose/ui/graphics/drawscope/DrawScope;", "", "Lkotlin/ExtensionFunctionType;", "<set-?>", "Landroidx/compose/ui/graphics/ColorFilter;", "intrinsicColorFilter", "getIntrinsicColorFilter$ui_release", "()Landroidx/compose/ui/graphics/ColorFilter;", "setIntrinsicColorFilter$ui_release", "(Landroidx/compose/ui/graphics/ColorFilter;)V", "intrinsicColorFilter$delegate", "Landroidx/compose/runtime/MutableState;", "invalidateCallback", "Lkotlin/Function0;", "getInvalidateCallback$ui_release", "()Lkotlin/jvm/functions/Function0;", "setInvalidateCallback$ui_release", "(Lkotlin/jvm/functions/Function0;)V", "isDirty", "", HintConstants.AUTOFILL_HINT_NAME, "", "getName", "()Ljava/lang/String;", "setName", "(Ljava/lang/String;)V", "previousDrawSize", "Landroidx/compose/ui/geometry/Size;", "J", "getRoot", "()Landroidx/compose/ui/graphics/vector/GroupComponent;", "rootScaleX", "", "rootScaleY", "tintFilter", "viewportSize", "getViewportSize-NH-jbRc$ui_release", "()J", "setViewportSize-uvyYCjk$ui_release", "(J)V", "viewportSize$delegate", "doInvalidate", "toString", "draw", "alpha", "colorFilter", "ui_release"}, k = 1, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes11.dex */
public final class VectorComponent extends VNode {
    public static final int $stable = 8;
    private final DrawCache cacheDrawScope;
    private final Function1<DrawScope, Unit> drawVectorBlock;

    /* renamed from: intrinsicColorFilter$delegate, reason: from kotlin metadata */
    private final MutableState intrinsicColorFilter;
    private Function0<Unit> invalidateCallback;
    private boolean isDirty;
    private String name;
    private long previousDrawSize;
    private final GroupComponent root;
    private float rootScaleX;
    private float rootScaleY;
    private ColorFilter tintFilter;

    /* renamed from: viewportSize$delegate, reason: from kotlin metadata */
    private final MutableState viewportSize;

    public VectorComponent(GroupComponent root) {
        super(null);
        this.root = root;
        this.root.setInvalidateListener$ui_release(new Function1<VNode, Unit>() { // from class: androidx.compose.ui.graphics.vector.VectorComponent.1
            {
                super(1);
            }

            @Override // kotlin.jvm.functions.Function1
            public /* bridge */ /* synthetic */ Unit invoke(VNode vNode) {
                invoke2(vNode);
                return Unit.INSTANCE;
            }

            /* renamed from: invoke, reason: avoid collision after fix types in other method */
            public final void invoke2(VNode it) {
                VectorComponent.this.doInvalidate();
            }
        });
        this.name = "";
        this.isDirty = true;
        this.cacheDrawScope = new DrawCache();
        this.invalidateCallback = new Function0<Unit>() { // from class: androidx.compose.ui.graphics.vector.VectorComponent$invalidateCallback$1
            @Override // kotlin.jvm.functions.Function0
            public /* bridge */ /* synthetic */ Unit invoke() {
                invoke2();
                return Unit.INSTANCE;
            }

            /* renamed from: invoke, reason: avoid collision after fix types in other method */
            public final void invoke2() {
            }
        };
        this.intrinsicColorFilter = SnapshotStateKt__SnapshotStateKt.mutableStateOf$default(null, null, 2, null);
        this.viewportSize = SnapshotStateKt__SnapshotStateKt.mutableStateOf$default(Size.m3562boximpl(Size.INSTANCE.m3583getZeroNHjbRc()), null, 2, null);
        this.previousDrawSize = Size.INSTANCE.m3582getUnspecifiedNHjbRc();
        this.rootScaleX = 1.0f;
        this.rootScaleY = 1.0f;
        this.drawVectorBlock = new Function1<DrawScope, Unit>() { // from class: androidx.compose.ui.graphics.vector.VectorComponent$drawVectorBlock$1
            {
                super(1);
            }

            @Override // kotlin.jvm.functions.Function1
            public /* bridge */ /* synthetic */ Unit invoke(DrawScope drawScope) {
                invoke2(drawScope);
                return Unit.INSTANCE;
            }

            /* renamed from: invoke, reason: avoid collision after fix types in other method */
            public final void invoke2(DrawScope $this$null) {
                float scaleX$iv;
                float scaleY$iv;
                GroupComponent $this$invoke_u24lambda_u241 = VectorComponent.this.getRoot();
                VectorComponent vectorComponent = VectorComponent.this;
                scaleX$iv = vectorComponent.rootScaleX;
                scaleY$iv = vectorComponent.rootScaleY;
                long pivot$iv = Offset.INSTANCE.m3521getZeroF1C5BW0();
                DrawContext $this$withTransform_u24lambda_u246$iv$iv = $this$null.getDrawContext();
                long previousSize$iv$iv = $this$withTransform_u24lambda_u246$iv$iv.mo4220getSizeNHjbRc();
                $this$withTransform_u24lambda_u246$iv$iv.getCanvas().save();
                DrawTransform $this$scale_Fgt4K4Q_u24lambda_u242$iv = $this$withTransform_u24lambda_u246$iv$iv.getTransform();
                $this$scale_Fgt4K4Q_u24lambda_u242$iv.mo4227scale0AR0LA0(scaleX$iv, scaleY$iv, pivot$iv);
                $this$invoke_u24lambda_u241.draw($this$null);
                $this$withTransform_u24lambda_u246$iv$iv.getCanvas().restore();
                $this$withTransform_u24lambda_u246$iv$iv.mo4221setSizeuvyYCjk(previousSize$iv$iv);
            }
        };
    }

    public final GroupComponent getRoot() {
        return this.root;
    }

    public final String getName() {
        return this.name;
    }

    public final void setName(String str) {
        this.name = str;
    }

    /* JADX INFO: Access modifiers changed from: private */
    public final void doInvalidate() {
        this.isDirty = true;
        this.invalidateCallback.invoke();
    }

    /* renamed from: getCacheBitmapConfig-_sVssgQ$ui_release, reason: not valid java name */
    public final int m4389getCacheBitmapConfig_sVssgQ$ui_release() {
        ImageBitmap mCachedImage = this.cacheDrawScope.getMCachedImage();
        return mCachedImage != null ? mCachedImage.mo3613getConfig_sVssgQ() : ImageBitmapConfig.INSTANCE.m3967getArgb8888_sVssgQ();
    }

    public final Function0<Unit> getInvalidateCallback$ui_release() {
        return this.invalidateCallback;
    }

    public final void setInvalidateCallback$ui_release(Function0<Unit> function0) {
        this.invalidateCallback = function0;
    }

    public final ColorFilter getIntrinsicColorFilter$ui_release() {
        State $this$getValue$iv = this.intrinsicColorFilter;
        return (ColorFilter) $this$getValue$iv.getValue();
    }

    public final void setIntrinsicColorFilter$ui_release(ColorFilter colorFilter) {
        MutableState $this$setValue$iv = this.intrinsicColorFilter;
        $this$setValue$iv.setValue(colorFilter);
    }

    /* renamed from: getViewportSize-NH-jbRc$ui_release, reason: not valid java name */
    public final long m4390getViewportSizeNHjbRc$ui_release() {
        State $this$getValue$iv = this.viewportSize;
        return ((Size) $this$getValue$iv.getValue()).getPackedValue();
    }

    /* renamed from: setViewportSize-uvyYCjk$ui_release, reason: not valid java name */
    public final void m4391setViewportSizeuvyYCjk$ui_release(long j) {
        MutableState $this$setValue$iv = this.viewportSize;
        $this$setValue$iv.setValue(Size.m3562boximpl(j));
    }

    /* JADX WARN: Code restructure failed: missing block: B:6:0x001e, code lost:
    
        if ((r2 != androidx.compose.ui.graphics.Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : 0) != 0) goto L11;
     */
    /*
        Code decompiled incorrectly, please refer to instructions dump.
        To view partially-correct add '--show-bad-code' argument
    */
    public final void draw(androidx.compose.ui.graphics.drawscope.DrawScope r11, float r12, androidx.compose.ui.graphics.ColorFilter r13) {
        /*
            r10 = this;
            androidx.compose.ui.graphics.vector.GroupComponent r0 = r10.root
            boolean r0 = r0.getIsTintable()
            r1 = 0
            if (r0 == 0) goto L21
            androidx.compose.ui.graphics.vector.GroupComponent r0 = r10.root
            long r2 = r0.getTintColor()
            r0 = 0
            androidx.compose.ui.graphics.Color$Companion r4 = androidx.compose.ui.graphics.Color.INSTANCE
            long r4 = r4.m3782getUnspecified0d7_KjU()
            int r4 = (r2 > r4 ? 1 : (r2 == r4 ? 0 : -1))
            r5 = 1
            if (r4 == 0) goto L1d
            r0 = r5
            goto L1e
        L1d:
            r0 = r1
        L1e:
            if (r0 == 0) goto L21
            goto L22
        L21:
            r5 = r1
        L22:
            r0 = r5
            if (r0 == 0) goto L3c
            androidx.compose.ui.graphics.ColorFilter r2 = r10.getIntrinsicColorFilter$ui_release()
            boolean r2 = androidx.compose.ui.graphics.vector.VectorKt.tintableWithAlphaMask(r2)
            if (r2 == 0) goto L3c
            boolean r2 = androidx.compose.ui.graphics.vector.VectorKt.tintableWithAlphaMask(r13)
            if (r2 == 0) goto L3c
            androidx.compose.ui.graphics.ImageBitmapConfig$Companion r2 = androidx.compose.ui.graphics.ImageBitmapConfig.INSTANCE
            int r2 = r2.m3966getAlpha8_sVssgQ()
            goto L42
        L3c:
            androidx.compose.ui.graphics.ImageBitmapConfig$Companion r2 = androidx.compose.ui.graphics.ImageBitmapConfig.INSTANCE
            int r2 = r2.m3967getArgb8888_sVssgQ()
        L42:
            boolean r3 = r10.isDirty
            if (r3 != 0) goto L5d
            long r3 = r10.previousDrawSize
            long r5 = r11.mo4295getSizeNHjbRc()
            boolean r3 = androidx.compose.ui.geometry.Size.m3570equalsimpl0(r3, r5)
            if (r3 == 0) goto L5d
            int r3 = r10.m4389getCacheBitmapConfig_sVssgQ$ui_release()
            boolean r3 = androidx.compose.ui.graphics.ImageBitmapConfig.m3962equalsimpl0(r2, r3)
            if (r3 != 0) goto Ldc
        L5d:
            androidx.compose.ui.graphics.ImageBitmapConfig$Companion r3 = androidx.compose.ui.graphics.ImageBitmapConfig.INSTANCE
            int r3 = r3.m3966getAlpha8_sVssgQ()
            boolean r3 = androidx.compose.ui.graphics.ImageBitmapConfig.m3962equalsimpl0(r2, r3)
            if (r3 == 0) goto L79
            androidx.compose.ui.graphics.ColorFilter$Companion r4 = androidx.compose.ui.graphics.ColorFilter.INSTANCE
            androidx.compose.ui.graphics.vector.GroupComponent r3 = r10.root
            long r5 = r3.getTintColor()
            r8 = 2
            r9 = 0
            r7 = 0
            androidx.compose.ui.graphics.ColorFilter r3 = androidx.compose.ui.graphics.ColorFilter.Companion.m3787tintxETnrds$default(r4, r5, r7, r8, r9)
            goto L7a
        L79:
            r3 = 0
        L7a:
            r10.tintFilter = r3
            long r3 = r11.mo4295getSizeNHjbRc()
            float r3 = androidx.compose.ui.geometry.Size.m3574getWidthimpl(r3)
            long r4 = r10.m4390getViewportSizeNHjbRc$ui_release()
            float r4 = androidx.compose.ui.geometry.Size.m3574getWidthimpl(r4)
            float r3 = r3 / r4
            r10.rootScaleX = r3
            long r3 = r11.mo4295getSizeNHjbRc()
            float r3 = androidx.compose.ui.geometry.Size.m3571getHeightimpl(r3)
            long r4 = r10.m4390getViewportSizeNHjbRc$ui_release()
            float r4 = androidx.compose.ui.geometry.Size.m3571getHeightimpl(r4)
            float r3 = r3 / r4
            r10.rootScaleY = r3
            androidx.compose.ui.graphics.vector.DrawCache r3 = r10.cacheDrawScope
            long r4 = r11.mo4295getSizeNHjbRc()
            float r4 = androidx.compose.ui.geometry.Size.m3574getWidthimpl(r4)
            double r4 = (double) r4
            double r4 = java.lang.Math.ceil(r4)
            float r4 = (float) r4
            int r4 = (int) r4
            long r5 = r11.mo4295getSizeNHjbRc()
            float r5 = androidx.compose.ui.geometry.Size.m3571getHeightimpl(r5)
            double r5 = (double) r5
            double r5 = java.lang.Math.ceil(r5)
            float r5 = (float) r5
            int r5 = (int) r5
            long r5 = androidx.compose.ui.unit.IntSizeKt.IntSize(r4, r5)
            r7 = r11
            androidx.compose.ui.unit.Density r7 = (androidx.compose.ui.unit.Density) r7
            androidx.compose.ui.unit.LayoutDirection r8 = r11.getLayoutDirection()
            kotlin.jvm.functions.Function1<androidx.compose.ui.graphics.drawscope.DrawScope, kotlin.Unit> r9 = r10.drawVectorBlock
            r4 = r2
            r3.m4372drawCachedImageFqjB98A(r4, r5, r7, r8, r9)
            r10.isDirty = r1
            long r3 = r11.mo4295getSizeNHjbRc()
            r10.previousDrawSize = r3
        Ldc:
            if (r13 == 0) goto Le0
            r1 = r13
            goto Led
        Le0:
            androidx.compose.ui.graphics.ColorFilter r1 = r10.getIntrinsicColorFilter$ui_release()
            if (r1 == 0) goto Leb
            androidx.compose.ui.graphics.ColorFilter r1 = r10.getIntrinsicColorFilter$ui_release()
            goto Led
        Leb:
            androidx.compose.ui.graphics.ColorFilter r1 = r10.tintFilter
        Led:
            androidx.compose.ui.graphics.vector.DrawCache r3 = r10.cacheDrawScope
            r3.drawInto(r11, r12, r1)
            return
        */
        throw new UnsupportedOperationException("Method not decompiled: androidx.compose.ui.graphics.vector.VectorComponent.draw(androidx.compose.ui.graphics.drawscope.DrawScope, float, androidx.compose.ui.graphics.ColorFilter):void");
    }

    @Override // androidx.compose.ui.graphics.vector.VNode
    public void draw(DrawScope $this$draw) {
        draw($this$draw, 1.0f, null);
    }

    public String toString() {
        StringBuilder $this$toString_u24lambda_u240 = new StringBuilder();
        $this$toString_u24lambda_u240.append("Params: ");
        $this$toString_u24lambda_u240.append("\tname: ").append(this.name).append("\n");
        $this$toString_u24lambda_u240.append("\tviewportWidth: ").append(Size.m3574getWidthimpl(m4390getViewportSizeNHjbRc$ui_release())).append("\n");
        $this$toString_u24lambda_u240.append("\tviewportHeight: ").append(Size.m3571getHeightimpl(m4390getViewportSizeNHjbRc$ui_release())).append("\n");
        String sb = $this$toString_u24lambda_u240.toString();
        Intrinsics.checkNotNullExpressionValue(sb, "StringBuilder().apply(builderAction).toString()");
        return sb;
    }
}
