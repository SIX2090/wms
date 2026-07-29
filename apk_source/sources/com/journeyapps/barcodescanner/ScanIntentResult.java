package com.journeyapps.barcodescanner;

import android.content.Intent;
import com.google.zxing.client.android.Intents;

/* loaded from: classes11.dex */
public final class ScanIntentResult {
    private final String barcodeImagePath;
    private final String contents;
    private final String errorCorrectionLevel;
    private final String formatName;
    private final Integer orientation;
    private final Intent originalIntent;
    private final byte[] rawBytes;

    ScanIntentResult() {
        this(null, null, null, null, null, null, null);
    }

    ScanIntentResult(Intent intent) {
        this(null, null, null, null, null, null, intent);
    }

    ScanIntentResult(String contents, String formatName, byte[] rawBytes, Integer orientation, String errorCorrectionLevel, String barcodeImagePath, Intent originalIntent) {
        this.contents = contents;
        this.formatName = formatName;
        this.rawBytes = rawBytes;
        this.orientation = orientation;
        this.errorCorrectionLevel = errorCorrectionLevel;
        this.barcodeImagePath = barcodeImagePath;
        this.originalIntent = originalIntent;
    }

    public String getContents() {
        return this.contents;
    }

    public String getFormatName() {
        return this.formatName;
    }

    public byte[] getRawBytes() {
        return this.rawBytes;
    }

    public Integer getOrientation() {
        return this.orientation;
    }

    public String getErrorCorrectionLevel() {
        return this.errorCorrectionLevel;
    }

    public String getBarcodeImagePath() {
        return this.barcodeImagePath;
    }

    public Intent getOriginalIntent() {
        return this.originalIntent;
    }

    public String toString() {
        int rawBytesLength = this.rawBytes == null ? 0 : this.rawBytes.length;
        return "Format: " + this.formatName + "\nContents: " + this.contents + "\nRaw bytes: (" + rawBytesLength + " bytes)\nOrientation: " + this.orientation + "\nEC level: " + this.errorCorrectionLevel + "\nBarcode image: " + this.barcodeImagePath + "\nOriginal intent: " + this.originalIntent + '\n';
    }

    public static ScanIntentResult parseActivityResult(int resultCode, Intent intent) {
        if (resultCode == -1) {
            String contents = intent.getStringExtra(Intents.Scan.RESULT);
            String formatName = intent.getStringExtra(Intents.Scan.RESULT_FORMAT);
            byte[] rawBytes = intent.getByteArrayExtra(Intents.Scan.RESULT_BYTES);
            int intentOrientation = intent.getIntExtra(Intents.Scan.RESULT_ORIENTATION, Integer.MIN_VALUE);
            Integer orientation = intentOrientation == Integer.MIN_VALUE ? null : Integer.valueOf(intentOrientation);
            String errorCorrectionLevel = intent.getStringExtra(Intents.Scan.RESULT_ERROR_CORRECTION_LEVEL);
            String barcodeImagePath = intent.getStringExtra(Intents.Scan.RESULT_BARCODE_IMAGE_PATH);
            return new ScanIntentResult(contents, formatName, rawBytes, orientation, errorCorrectionLevel, barcodeImagePath, intent);
        }
        return new ScanIntentResult(intent);
    }
}
