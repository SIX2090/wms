package com.factory.wms.ui.components;

import androidx.activity.compose.ActivityResultRegistryKt;
import androidx.activity.compose.ManagedActivityResultLauncher;
import androidx.compose.runtime.Composer;
import androidx.compose.runtime.ComposerKt;
import com.journeyapps.barcodescanner.ScanContract;
import com.journeyapps.barcodescanner.ScanIntentResult;
import com.journeyapps.barcodescanner.ScanOptions;
import kotlin.Metadata;
import kotlin.Unit;
import kotlin.jvm.functions.Function0;
import kotlin.jvm.functions.Function1;
import kotlin.jvm.internal.Intrinsics;
import kotlin.text.StringsKt;

/* compiled from: ScannerLauncher.kt */
@Metadata(d1 = {"\u0000\u0018\n\u0000\n\u0002\u0018\u0002\n\u0002\u0010\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\u0010\u000e\n\u0002\b\u0002\u001a'\u0010\u0000\u001a\b\u0012\u0004\u0012\u00020\u00020\u00012\u0012\u0010\u0003\u001a\u000e\u0012\u0004\u0012\u00020\u0005\u0012\u0004\u0012\u00020\u00020\u0004H\u0007¢\u0006\u0002\u0010\u0006¨\u0006\u0007"}, d2 = {"rememberScannerLauncher", "Lkotlin/Function0;", "", "onScanned", "Lkotlin/Function1;", "", "(Lkotlin/jvm/functions/Function1;Landroidx/compose/runtime/Composer;I)Lkotlin/jvm/functions/Function0;", "app_debug"}, k = 2, mv = {2, 0, 0}, xi = 48)
/* loaded from: classes4.dex */
public final class ScannerLauncherKt {
    public static final Function0<Unit> rememberScannerLauncher(final Function1<? super String, Unit> onScanned, Composer $composer, int $changed) {
        Object value$iv;
        Object value$iv2;
        Intrinsics.checkNotNullParameter(onScanned, "onScanned");
        $composer.startReplaceableGroup(10835644);
        ComposerKt.sourceInformation($composer, "C(rememberScannerLauncher)10@444L116,10@394L166,14@572L365:ScannerLauncher.kt#qrwxji");
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventStart(10835644, $changed, -1, "com.factory.wms.ui.components.rememberScannerLauncher (ScannerLauncher.kt:9)");
        }
        ScanContract scanContract = new ScanContract();
        $composer.startReplaceableGroup(451801093);
        ComposerKt.sourceInformation($composer, "CC(remember):ScannerLauncher.kt#9igjgp");
        boolean invalid$iv = ((($changed & 14) ^ 6) > 4 && $composer.changed(onScanned)) || ($changed & 6) == 4;
        Object it$iv = $composer.rememberedValue();
        if (invalid$iv || it$iv == Composer.INSTANCE.getEmpty()) {
            value$iv = new Function1() { // from class: com.factory.wms.ui.components.ScannerLauncherKt$$ExternalSyntheticLambda0
                @Override // kotlin.jvm.functions.Function1
                public final Object invoke(Object obj) {
                    Unit rememberScannerLauncher$lambda$1$lambda$0;
                    rememberScannerLauncher$lambda$1$lambda$0 = ScannerLauncherKt.rememberScannerLauncher$lambda$1$lambda$0(Function1.this, (ScanIntentResult) obj);
                    return rememberScannerLauncher$lambda$1$lambda$0;
                }
            };
            $composer.updateRememberedValue(value$iv);
        } else {
            value$iv = it$iv;
        }
        $composer.endReplaceableGroup();
        final ManagedActivityResultLauncher launcher = ActivityResultRegistryKt.rememberLauncherForActivityResult(scanContract, (Function1) value$iv, $composer, 0);
        $composer.startReplaceableGroup(451805438);
        ComposerKt.sourceInformation($composer, "CC(remember):ScannerLauncher.kt#9igjgp");
        boolean invalid$iv2 = $composer.changed(launcher);
        Object it$iv2 = $composer.rememberedValue();
        if (invalid$iv2 || it$iv2 == Composer.INSTANCE.getEmpty()) {
            value$iv2 = new Function0() { // from class: com.factory.wms.ui.components.ScannerLauncherKt$$ExternalSyntheticLambda1
                @Override // kotlin.jvm.functions.Function0
                public final Object invoke() {
                    Unit rememberScannerLauncher$lambda$3$lambda$2;
                    rememberScannerLauncher$lambda$3$lambda$2 = ScannerLauncherKt.rememberScannerLauncher$lambda$3$lambda$2(ManagedActivityResultLauncher.this);
                    return rememberScannerLauncher$lambda$3$lambda$2;
                }
            };
            $composer.updateRememberedValue(value$iv2);
        } else {
            value$iv2 = it$iv2;
        }
        Function0<Unit> function0 = (Function0) value$iv2;
        $composer.endReplaceableGroup();
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventEnd();
        }
        $composer.endReplaceableGroup();
        return function0;
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final Unit rememberScannerLauncher$lambda$1$lambda$0(Function1 $onScanned, ScanIntentResult result) {
        String contents = result.getContents();
        if (contents == null) {
            contents = "";
        }
        String text = StringsKt.trim((CharSequence) contents).toString();
        if (!StringsKt.isBlank(text)) {
            $onScanned.invoke(text);
        }
        return Unit.INSTANCE;
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final Unit rememberScannerLauncher$lambda$3$lambda$2(ManagedActivityResultLauncher $launcher) {
        ScanOptions options = new ScanOptions().setDesiredBarcodeFormats(ScanOptions.ALL_CODE_TYPES).setPrompt("扫描物料编码或仓位编码").setBeepEnabled(true).setBarcodeImageEnabled(false).setOrientationLocked(false);
        $launcher.launch(options);
        return Unit.INSTANCE;
    }
}
