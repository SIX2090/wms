package com.factory.wms.ui.components;

import android.content.Context;
import androidx.compose.foundation.layout.Arrangement;
import androidx.compose.foundation.layout.ColumnKt;
import androidx.compose.foundation.layout.ColumnScopeInstance;
import androidx.compose.foundation.layout.PaddingKt;
import androidx.compose.foundation.layout.SizeKt;
import androidx.compose.foundation.layout.SpacerKt;
import androidx.compose.material.icons.Icons;
import androidx.compose.material.icons.filled.QrCodeScannerKt;
import androidx.compose.material3.ButtonKt;
import androidx.compose.material3.IconKt;
import androidx.compose.material3.MaterialTheme;
import androidx.compose.material3.TextKt;
import androidx.compose.runtime.Applier;
import androidx.compose.runtime.ComposablesKt;
import androidx.compose.runtime.Composer;
import androidx.compose.runtime.ComposerKt;
import androidx.compose.runtime.CompositionLocalMap;
import androidx.compose.runtime.DisposableEffectResult;
import androidx.compose.runtime.DisposableEffectScope;
import androidx.compose.runtime.MutableState;
import androidx.compose.runtime.RecomposeScopeImplKt;
import androidx.compose.runtime.ScopeUpdateScope;
import androidx.compose.runtime.SkippableUpdater;
import androidx.compose.runtime.State;
import androidx.compose.runtime.Updater;
import androidx.compose.ui.Alignment;
import androidx.compose.ui.Modifier;
import androidx.compose.ui.graphics.Color;
import androidx.compose.ui.graphics.ColorKt;
import androidx.compose.ui.layout.LayoutKt;
import androidx.compose.ui.layout.MeasurePolicy;
import androidx.compose.ui.node.ComposeUiNode;
import androidx.compose.ui.text.TextLayoutResult;
import androidx.compose.ui.text.TextStyle;
import androidx.compose.ui.text.font.FontFamily;
import androidx.compose.ui.text.font.FontStyle;
import androidx.compose.ui.text.font.FontWeight;
import androidx.compose.ui.text.style.TextAlign;
import androidx.compose.ui.text.style.TextDecoration;
import androidx.compose.ui.unit.Dp;
import androidx.lifecycle.Lifecycle;
import androidx.lifecycle.LifecycleEventObserver;
import androidx.lifecycle.LifecycleOwner;
import com.journeyapps.barcodescanner.DecoratedBarcodeView;
import kotlin.Metadata;
import kotlin.Unit;
import kotlin.jvm.functions.Function0;
import kotlin.jvm.functions.Function1;
import kotlin.jvm.functions.Function2;
import kotlin.jvm.functions.Function3;
import kotlin.jvm.internal.Intrinsics;

/* compiled from: ContinuousScanner.kt */
@Metadata(d1 = {"\u0000&\n\u0000\n\u0002\u0010\u0002\n\u0000\n\u0002\u0010\u000b\n\u0000\n\u0002\u0010\u000e\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\n\n\u0002\u0018\u0002\u001a?\u0010\u0000\u001a\u00020\u00012\u0006\u0010\u0002\u001a\u00020\u00032\u0006\u0010\u0004\u001a\u00020\u00052\f\u0010\u0006\u001a\b\u0012\u0004\u0012\u00020\u00010\u00072\u0012\u0010\b\u001a\u000e\u0012\u0004\u0012\u00020\u0005\u0012\u0004\u0012\u00020\u00010\tH\u0007¢\u0006\u0002\u0010\n\u001a7\u0010\u000b\u001a\u00020\u00012\u0006\u0010\u0004\u001a\u00020\u00052\f\u0010\u0006\u001a\b\u0012\u0004\u0012\u00020\u00010\u00072\u0012\u0010\b\u001a\u000e\u0012\u0004\u0012\u00020\u0005\u0012\u0004\u0012\u00020\u00010\tH\u0003¢\u0006\u0002\u0010\f\u001a1\u0010\r\u001a\u00020\u00012\u0006\u0010\u0004\u001a\u00020\u00052\f\u0010\u0006\u001a\b\u0012\u0004\u0012\u00020\u00010\u00072\f\u0010\u000e\u001a\b\u0012\u0004\u0012\u00020\u00010\u0007H\u0003¢\u0006\u0002\u0010\u000f¨\u0006\u0010²\u0006\n\u0010\u0011\u001a\u00020\u0003X\u008a\u008e\u0002²\u0006\u0016\u0010\u0012\u001a\u000e\u0012\u0004\u0012\u00020\u0005\u0012\u0004\u0012\u00020\u00010\tX\u008a\u0084\u0002²\u0006\f\u0010\u0013\u001a\u0004\u0018\u00010\u0014X\u008a\u008e\u0002"}, d2 = {"ContinuousScannerDialog", "", "visible", "", "title", "", "onClose", "Lkotlin/Function0;", "onScanned", "Lkotlin/Function1;", "(ZLjava/lang/String;Lkotlin/jvm/functions/Function0;Lkotlin/jvm/functions/Function1;Landroidx/compose/runtime/Composer;I)V", "ScannerPreview", "(Ljava/lang/String;Lkotlin/jvm/functions/Function0;Lkotlin/jvm/functions/Function1;Landroidx/compose/runtime/Composer;I)V", "PermissionNeeded", "onRequestPermission", "(Ljava/lang/String;Lkotlin/jvm/functions/Function0;Lkotlin/jvm/functions/Function0;Landroidx/compose/runtime/Composer;I)V", "app_debug", "hasCameraPermission", "latestOnScanned", "scannerView", "Lcom/journeyapps/barcodescanner/DecoratedBarcodeView;"}, k = 2, mv = {2, 0, 0}, xi = 48)
/* loaded from: classes4.dex */
public final class ContinuousScannerKt {

    /* compiled from: ContinuousScanner.kt */
    @Metadata(k = 3, mv = {2, 0, 0}, xi = 48)
    public /* synthetic */ class WhenMappings {
        public static final /* synthetic */ int[] $EnumSwitchMapping$0;

        static {
            int[] iArr = new int[Lifecycle.Event.values().length];
            try {
                iArr[Lifecycle.Event.ON_RESUME.ordinal()] = 1;
            } catch (NoSuchFieldError e) {
            }
            try {
                iArr[Lifecycle.Event.ON_PAUSE.ordinal()] = 2;
            } catch (NoSuchFieldError e2) {
            }
            $EnumSwitchMapping$0 = iArr;
        }
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final Unit ContinuousScannerDialog$lambda$0(boolean z, String str, Function0 function0, Function1 function1, int i, Composer composer, int i2) {
        ContinuousScannerDialog(z, str, function0, function1, composer, RecomposeScopeImplKt.updateChangedFlags(i | 1));
        return Unit.INSTANCE;
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final Unit ContinuousScannerDialog$lambda$7(boolean z, String str, Function0 function0, Function1 function1, int i, Composer composer, int i2) {
        ContinuousScannerDialog(z, str, function0, function1, composer, RecomposeScopeImplKt.updateChangedFlags(i | 1));
        return Unit.INSTANCE;
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final Unit PermissionNeeded$lambda$29(String str, Function0 function0, Function0 function02, int i, Composer composer, int i2) {
        PermissionNeeded(str, function0, function02, composer, RecomposeScopeImplKt.updateChangedFlags(i | 1));
        return Unit.INSTANCE;
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final Unit ScannerPreview$lambda$27(String str, Function0 function0, Function1 function1, int i, Composer composer, int i2) {
        ScannerPreview(str, function0, function1, composer, RecomposeScopeImplKt.updateChangedFlags(i | 1));
        return Unit.INSTANCE;
    }

    /* JADX WARN: Removed duplicated region for block: B:68:0x01e1  */
    /*
        Code decompiled incorrectly, please refer to instructions dump.
        To view partially-correct add '--show-bad-code' argument
    */
    public static final void ContinuousScannerDialog(final boolean r25, final java.lang.String r26, final kotlin.jvm.functions.Function0<kotlin.Unit> r27, final kotlin.jvm.functions.Function1<? super java.lang.String, kotlin.Unit> r28, androidx.compose.runtime.Composer r29, final int r30) {
        /*
            Method dump skipped, instructions count: 510
            To view this dump add '--comments-level debug' option
        */
        throw new UnsupportedOperationException("Method not decompiled: com.factory.wms.ui.components.ContinuousScannerKt.ContinuousScannerDialog(boolean, java.lang.String, kotlin.jvm.functions.Function0, kotlin.jvm.functions.Function1, androidx.compose.runtime.Composer, int):void");
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final boolean ContinuousScannerDialog$lambda$2(MutableState<Boolean> mutableState) {
        MutableState<Boolean> $this$getValue$iv = mutableState;
        return $this$getValue$iv.getValue().booleanValue();
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final void ContinuousScannerDialog$lambda$3(MutableState<Boolean> mutableState, boolean z) {
        mutableState.setValue(Boolean.valueOf(z));
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final Unit ContinuousScannerDialog$lambda$5$lambda$4(MutableState $hasCameraPermission$delegate, boolean granted) {
        ContinuousScannerDialog$lambda$3($hasCameraPermission$delegate, granted);
        return Unit.INSTANCE;
    }

    /* JADX INFO: Access modifiers changed from: private */
    /* JADX WARN: Removed duplicated region for block: B:100:0x0796  */
    /* JADX WARN: Removed duplicated region for block: B:102:0x0613  */
    /* JADX WARN: Removed duplicated region for block: B:103:0x05ce  */
    /* JADX WARN: Removed duplicated region for block: B:105:0x04b0 A[ADDED_TO_REGION] */
    /* JADX WARN: Removed duplicated region for block: B:106:0x046b  */
    /* JADX WARN: Removed duplicated region for block: B:107:0x0392  */
    /* JADX WARN: Removed duplicated region for block: B:110:0x02be  */
    /* JADX WARN: Removed duplicated region for block: B:64:0x02ac  */
    /* JADX WARN: Removed duplicated region for block: B:67:0x02b8  */
    /* JADX WARN: Removed duplicated region for block: B:75:0x0384  */
    /* JADX WARN: Removed duplicated region for block: B:78:0x045b  */
    /* JADX WARN: Removed duplicated region for block: B:81:0x0467  */
    /* JADX WARN: Removed duplicated region for block: B:84:0x049a  */
    /* JADX WARN: Removed duplicated region for block: B:89:0x05be  */
    /* JADX WARN: Removed duplicated region for block: B:92:0x05ca  */
    /* JADX WARN: Removed duplicated region for block: B:95:0x05fd  */
    /*
        Code decompiled incorrectly, please refer to instructions dump.
        To view partially-correct add '--show-bad-code' argument
    */
    public static final void ScannerPreview(final java.lang.String r124, final kotlin.jvm.functions.Function0<kotlin.Unit> r125, final kotlin.jvm.functions.Function1<? super java.lang.String, kotlin.Unit> r126, androidx.compose.runtime.Composer r127, final int r128) {
        /*
            Method dump skipped, instructions count: 1977
            To view this dump add '--comments-level debug' option
        */
        throw new UnsupportedOperationException("Method not decompiled: com.factory.wms.ui.components.ContinuousScannerKt.ScannerPreview(java.lang.String, kotlin.jvm.functions.Function0, kotlin.jvm.functions.Function1, androidx.compose.runtime.Composer, int):void");
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final Function1<String, Unit> ScannerPreview$lambda$8(State<? extends Function1<? super String, Unit>> state) {
        Object thisObj$iv = state.getValue();
        return (Function1) thisObj$iv;
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final DecoratedBarcodeView ScannerPreview$lambda$13(MutableState<DecoratedBarcodeView> mutableState) {
        MutableState<DecoratedBarcodeView> $this$getValue$iv = mutableState;
        return $this$getValue$iv.getValue();
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final DisposableEffectResult ScannerPreview$lambda$20$lambda$19(final LifecycleOwner $lifecycleOwner, final MutableState $scannerView$delegate, DisposableEffectScope DisposableEffect) {
        Intrinsics.checkNotNullParameter(DisposableEffect, "$this$DisposableEffect");
        final LifecycleEventObserver observer = new LifecycleEventObserver() { // from class: com.factory.wms.ui.components.ContinuousScannerKt$$ExternalSyntheticLambda3
            @Override // androidx.lifecycle.LifecycleEventObserver
            public final void onStateChanged(LifecycleOwner lifecycleOwner, Lifecycle.Event event) {
                ContinuousScannerKt.ScannerPreview$lambda$20$lambda$19$lambda$17(MutableState.this, lifecycleOwner, event);
            }
        };
        $lifecycleOwner.getLifecycleRegistry().addObserver(observer);
        return new DisposableEffectResult() { // from class: com.factory.wms.ui.components.ContinuousScannerKt$ScannerPreview$lambda$20$lambda$19$$inlined$onDispose$1
            @Override // androidx.compose.runtime.DisposableEffectResult
            public void dispose() {
                DecoratedBarcodeView ScannerPreview$lambda$13;
                LifecycleOwner.this.getLifecycleRegistry().removeObserver(observer);
                ScannerPreview$lambda$13 = ContinuousScannerKt.ScannerPreview$lambda$13($scannerView$delegate);
                if (ScannerPreview$lambda$13 != null) {
                    ScannerPreview$lambda$13.pause();
                }
            }
        };
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final void ScannerPreview$lambda$20$lambda$19$lambda$17(MutableState $scannerView$delegate, LifecycleOwner lifecycleOwner, Lifecycle.Event event) {
        Intrinsics.checkNotNullParameter(lifecycleOwner, "<unused var>");
        Intrinsics.checkNotNullParameter(event, "event");
        switch (WhenMappings.$EnumSwitchMapping$0[event.ordinal()]) {
            case 1:
                DecoratedBarcodeView ScannerPreview$lambda$13 = ScannerPreview$lambda$13($scannerView$delegate);
                if (ScannerPreview$lambda$13 != null) {
                    ScannerPreview$lambda$13.resume();
                    break;
                }
                break;
            case 2:
                DecoratedBarcodeView ScannerPreview$lambda$132 = ScannerPreview$lambda$13($scannerView$delegate);
                if (ScannerPreview$lambda$132 != null) {
                    ScannerPreview$lambda$132.pause();
                    break;
                }
                break;
        }
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final DecoratedBarcodeView ScannerPreview$lambda$26$lambda$23$lambda$22(ContinuousScannerKt$ScannerPreview$callback$1$1 $callback, MutableState $scannerView$delegate, Context viewContext) {
        Intrinsics.checkNotNullParameter(viewContext, "viewContext");
        DecoratedBarcodeView $this$ScannerPreview_u24lambda_u2426_u24lambda_u2423_u24lambda_u2422_u24lambda_u2421 = new DecoratedBarcodeView(viewContext);
        $this$ScannerPreview_u24lambda_u2426_u24lambda_u2423_u24lambda_u2422_u24lambda_u2421.setStatusText("对准条码，扫到后自动加入；点关闭返回");
        $this$ScannerPreview_u24lambda_u2426_u24lambda_u2423_u24lambda_u2422_u24lambda_u2421.decodeContinuous($callback);
        $this$ScannerPreview_u24lambda_u2426_u24lambda_u2423_u24lambda_u2422_u24lambda_u2421.resume();
        $scannerView$delegate.setValue($this$ScannerPreview_u24lambda_u2426_u24lambda_u2423_u24lambda_u2422_u24lambda_u2421);
        return $this$ScannerPreview_u24lambda_u2426_u24lambda_u2423_u24lambda_u2422_u24lambda_u2421;
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final void PermissionNeeded(final String title, final Function0<Unit> function0, final Function0<Unit> function02, Composer $composer, final int $changed) {
        Composer $composer2;
        Composer $composer3 = $composer.startRestartGroup(1645902102);
        ComposerKt.sourceInformation($composer3, "C(PermissionNeeded)P(2)204@7273L806:ContinuousScanner.kt#qrwxji");
        int $dirty = $changed;
        if (($changed & 6) == 0) {
            $dirty |= $composer3.changed(title) ? 4 : 2;
        }
        if (($changed & 48) == 0) {
            $dirty |= $composer3.changedInstance(function0) ? 32 : 16;
        }
        if (($changed & 384) == 0) {
            $dirty |= $composer3.changedInstance(function02) ? 256 : 128;
        }
        int $dirty2 = $dirty;
        if (($dirty2 & 147) != 146 || !$composer3.getSkipping()) {
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventStart(1645902102, $dirty2, -1, "com.factory.wms.ui.components.PermissionNeeded (ContinuousScanner.kt:203)");
            }
            Modifier modifier$iv = PaddingKt.m562padding3ABfNKs(SizeKt.fillMaxSize$default(Modifier.INSTANCE, 0.0f, 1, null), Dp.m6094constructorimpl(24));
            Alignment.Horizontal horizontalAlignment$iv = Alignment.INSTANCE.getCenterHorizontally();
            $composer3.startReplaceableGroup(-483455358);
            ComposerKt.sourceInformation($composer3, "CC(Column)P(2,3,1)77@3865L61,78@3931L133:Column.kt#2w3rfo");
            Arrangement.Vertical verticalArrangement$iv = Arrangement.INSTANCE.getTop();
            MeasurePolicy measurePolicy$iv = ColumnKt.columnMeasurePolicy(verticalArrangement$iv, horizontalAlignment$iv, $composer3, ((390 >> 3) & 14) | ((390 >> 3) & 112));
            int $changed$iv$iv = (390 << 3) & 112;
            $composer3.startReplaceableGroup(-1323940314);
            ComposerKt.sourceInformation($composer3, "CC(Layout)P(!1,2)78@3182L23,80@3272L420:Layout.kt#80mrfh");
            int compositeKeyHash$iv$iv = ComposablesKt.getCurrentCompositeKeyHash($composer3, 0);
            CompositionLocalMap localMap$iv$iv = $composer3.getCurrentCompositionLocalMap();
            Function0 factory$iv$iv$iv = ComposeUiNode.INSTANCE.getConstructor();
            Function3 skippableUpdate$iv$iv$iv = LayoutKt.modifierMaterializerOf(modifier$iv);
            int $changed$iv$iv$iv = (($changed$iv$iv << 9) & 7168) | 6;
            if (!($composer3.getApplier() instanceof Applier)) {
                ComposablesKt.invalidApplier();
            }
            $composer3.startReusableNode();
            if ($composer3.getInserting()) {
                $composer3.createNode(factory$iv$iv$iv);
            } else {
                $composer3.useNode();
            }
            Composer $this$Layout_u24lambda_u240$iv$iv = Updater.m3276constructorimpl($composer3);
            Updater.m3283setimpl($this$Layout_u24lambda_u240$iv$iv, measurePolicy$iv, ComposeUiNode.INSTANCE.getSetMeasurePolicy());
            Updater.m3283setimpl($this$Layout_u24lambda_u240$iv$iv, localMap$iv$iv, ComposeUiNode.INSTANCE.getSetResolvedCompositionLocals());
            Function2 block$iv$iv$iv = ComposeUiNode.INSTANCE.getSetCompositeKeyHash();
            if ($this$Layout_u24lambda_u240$iv$iv.getInserting() || !Intrinsics.areEqual($this$Layout_u24lambda_u240$iv$iv.rememberedValue(), Integer.valueOf(compositeKeyHash$iv$iv))) {
                $this$Layout_u24lambda_u240$iv$iv.updateRememberedValue(Integer.valueOf(compositeKeyHash$iv$iv));
                $this$Layout_u24lambda_u240$iv$iv.apply(Integer.valueOf(compositeKeyHash$iv$iv), block$iv$iv$iv);
            }
            skippableUpdate$iv$iv$iv.invoke(SkippableUpdater.m3267boximpl(SkippableUpdater.m3268constructorimpl($composer3)), $composer3, Integer.valueOf(($changed$iv$iv$iv >> 3) & 112));
            $composer3.startReplaceableGroup(2058660585);
            int i = ($changed$iv$iv$iv >> 9) & 14;
            ComposerKt.sourceInformationMarkerStart($composer3, 276693656, "C79@3979L9:Column.kt#2w3rfo");
            ColumnScopeInstance columnScopeInstance = ColumnScopeInstance.INSTANCE;
            int i2 = ((390 >> 6) & 112) | 6;
            ComposerKt.sourceInformationMarkerStart($composer3, 795705447, "C210@7440L30,211@7479L183,217@7726L10,217@7671L77,218@7757L29,219@7795L48,220@7852L30,221@7891L75,224@7975L29,225@8013L60:ContinuousScanner.kt#qrwxji");
            SpacerKt.Spacer(SizeKt.m597height3ABfNKs(Modifier.INSTANCE, Dp.m6094constructorimpl(80)), $composer3, 6);
            IconKt.m1937Iconww6aTOc(QrCodeScannerKt.getQrCodeScanner(Icons.INSTANCE.getDefault()), (String) null, PaddingKt.m566paddingqDBjuR0$default(Modifier.INSTANCE, 0.0f, 0.0f, 0.0f, Dp.m6094constructorimpl(16), 7, null), Color.INSTANCE.m3783getWhite0d7_KjU(), $composer3, 3504, 0);
            $composer2 = $composer3;
            TextKt.m2464Text4IGK_g(title, (Modifier) null, Color.INSTANCE.m3783getWhite0d7_KjU(), 0L, (FontStyle) null, (FontWeight) null, (FontFamily) null, 0L, (TextDecoration) null, (TextAlign) null, 0L, 0, false, 0, 0, (Function1<? super TextLayoutResult, Unit>) null, MaterialTheme.INSTANCE.getTypography($composer3, MaterialTheme.$stable).getTitleLarge(), $composer3, ($dirty2 & 14) | 384, 0, 65530);
            SpacerKt.Spacer(SizeKt.m597height3ABfNKs(Modifier.INSTANCE, Dp.m6094constructorimpl(8)), $composer3, 6);
            TextKt.m2464Text4IGK_g("需要允许摄像头权限才能扫码", (Modifier) null, ColorKt.Color(4291941851L), 0L, (FontStyle) null, (FontWeight) null, (FontFamily) null, 0L, (TextDecoration) null, (TextAlign) null, 0L, 0, false, 0, 0, (Function1<? super TextLayoutResult, Unit>) null, (TextStyle) null, $composer3, 390, 0, 131066);
            SpacerKt.Spacer(SizeKt.m597height3ABfNKs(Modifier.INSTANCE, Dp.m6094constructorimpl(24)), $composer3, 6);
            ButtonKt.Button(function02, null, false, null, null, null, null, null, null, ComposableSingletons$ContinuousScannerKt.INSTANCE.m6408getLambda2$app_debug(), $composer3, (($dirty2 >> 6) & 14) | 805306368, 510);
            SpacerKt.Spacer(SizeKt.m597height3ABfNKs(Modifier.INSTANCE, Dp.m6094constructorimpl(8)), $composer3, 6);
            ButtonKt.Button(function0, null, false, null, null, null, null, null, null, ComposableSingletons$ContinuousScannerKt.INSTANCE.m6409getLambda3$app_debug(), $composer3, (($dirty2 >> 3) & 14) | 805306368, 510);
            ComposerKt.sourceInformationMarkerEnd($composer3);
            ComposerKt.sourceInformationMarkerEnd($composer3);
            $composer2.endReplaceableGroup();
            $composer2.endNode();
            $composer2.endReplaceableGroup();
            $composer2.endReplaceableGroup();
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventEnd();
            }
        } else {
            $composer3.skipToGroupEnd();
            $composer2 = $composer3;
        }
        ScopeUpdateScope endRestartGroup = $composer2.endRestartGroup();
        if (endRestartGroup != null) {
            endRestartGroup.updateScope(new Function2() { // from class: com.factory.wms.ui.components.ContinuousScannerKt$$ExternalSyntheticLambda4
                @Override // kotlin.jvm.functions.Function2
                public final Object invoke(Object obj, Object obj2) {
                    Unit PermissionNeeded$lambda$29;
                    PermissionNeeded$lambda$29 = ContinuousScannerKt.PermissionNeeded$lambda$29(title, function0, function02, $changed, (Composer) obj, ((Integer) obj2).intValue());
                    return PermissionNeeded$lambda$29;
                }
            });
        }
    }
}
