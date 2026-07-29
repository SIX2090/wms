package com.factory.wms.ui.components;

import android.content.Context;
import android.os.Handler;
import android.os.SystemClock;
import android.widget.Toast;
import androidx.compose.runtime.State;
import com.journeyapps.barcodescanner.BarcodeCallback;
import com.journeyapps.barcodescanner.BarcodeResult;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.atomic.AtomicReference;
import kotlin.Metadata;
import kotlin.Unit;
import kotlin.jvm.functions.Function1;
import kotlin.jvm.internal.Intrinsics;
import kotlin.text.StringsKt;

/* compiled from: ContinuousScanner.kt */
@Metadata(d1 = {"\u0000\u0017\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000*\u0001\u0000\b\n\u0018\u00002\u00020\u0001J\u0012\u0010\u0002\u001a\u00020\u00032\b\u0010\u0004\u001a\u0004\u0018\u00010\u0005H\u0016¨\u0006\u0006"}, d2 = {"com/factory/wms/ui/components/ContinuousScannerKt$ScannerPreview$callback$1$1", "Lcom/journeyapps/barcodescanner/BarcodeCallback;", "barcodeResult", "", "result", "Lcom/journeyapps/barcodescanner/BarcodeResult;", "app_debug"}, k = 1, mv = {2, 0, 0}, xi = 48)
/* loaded from: classes4.dex */
public final class ContinuousScannerKt$ScannerPreview$callback$1$1 implements BarcodeCallback {
    final /* synthetic */ Context $context;
    final /* synthetic */ AtomicLong $lastAt;
    final /* synthetic */ AtomicReference<String> $lastCode;
    final /* synthetic */ State<Function1<String, Unit>> $latestOnScanned$delegate;
    final /* synthetic */ Handler $mainHandler;

    /* JADX WARN: Multi-variable type inference failed */
    ContinuousScannerKt$ScannerPreview$callback$1$1(AtomicReference<String> atomicReference, AtomicLong $lastAt, Handler $mainHandler, Context $context, State<? extends Function1<? super String, Unit>> state) {
        this.$lastCode = atomicReference;
        this.$lastAt = $lastAt;
        this.$mainHandler = $mainHandler;
        this.$context = $context;
        this.$latestOnScanned$delegate = state;
    }

    @Override // com.journeyapps.barcodescanner.BarcodeCallback
    public void barcodeResult(BarcodeResult result) {
        String text;
        final String text2 = (result == null || (text = result.getText()) == null) ? null : StringsKt.trim((CharSequence) text).toString();
        if (text2 == null) {
            text2 = "";
        }
        if (StringsKt.isBlank(text2)) {
            return;
        }
        long now = SystemClock.elapsedRealtime();
        boolean sameCodeTooSoon = Intrinsics.areEqual(this.$lastCode.get(), text2) && now - this.$lastAt.get() < 1500;
        if (sameCodeTooSoon) {
            return;
        }
        this.$lastCode.set(text2);
        this.$lastAt.set(now);
        Handler handler = this.$mainHandler;
        final Context context = this.$context;
        final State<Function1<String, Unit>> state = this.$latestOnScanned$delegate;
        handler.post(new Runnable() { // from class: com.factory.wms.ui.components.ContinuousScannerKt$ScannerPreview$callback$1$1$$ExternalSyntheticLambda0
            @Override // java.lang.Runnable
            public final void run() {
                ContinuousScannerKt$ScannerPreview$callback$1$1.barcodeResult$lambda$0(text2, context, state);
            }
        });
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final void barcodeResult$lambda$0(String $text, Context $context, State $latestOnScanned$delegate) {
        Function1 ScannerPreview$lambda$8;
        ScannerPreview$lambda$8 = ContinuousScannerKt.ScannerPreview$lambda$8($latestOnScanned$delegate);
        ScannerPreview$lambda$8.invoke($text);
        Toast.makeText($context, "已扫：" + $text, 0).show();
    }
}
