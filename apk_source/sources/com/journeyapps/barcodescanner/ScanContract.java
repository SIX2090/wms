package com.journeyapps.barcodescanner;

import android.content.Context;
import android.content.Intent;
import androidx.activity.result.contract.ActivityResultContract;

/* loaded from: classes11.dex */
public class ScanContract extends ActivityResultContract<ScanOptions, ScanIntentResult> {
    @Override // androidx.activity.result.contract.ActivityResultContract
    public Intent createIntent(Context context, ScanOptions input) {
        return input.createScanIntent(context);
    }

    /* JADX WARN: Can't rename method to resolve collision */
    @Override // androidx.activity.result.contract.ActivityResultContract
    public ScanIntentResult parseResult(int resultCode, Intent intent) {
        return ScanIntentResult.parseActivityResult(resultCode, intent);
    }
}
