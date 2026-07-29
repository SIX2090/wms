package com.journeyapps.barcodescanner;

import com.google.zxing.BinaryBitmap;
import com.google.zxing.LuminanceSource;
import com.google.zxing.MultiFormatReader;
import com.google.zxing.Reader;
import com.google.zxing.Result;
import com.google.zxing.ResultPoint;
import com.google.zxing.ResultPointCallback;
import com.google.zxing.common.HybridBinarizer;
import java.util.ArrayList;
import java.util.List;

/* loaded from: classes11.dex */
public class Decoder implements ResultPointCallback {
    private List<ResultPoint> possibleResultPoints = new ArrayList();
    private Reader reader;

    public Decoder(Reader reader) {
        this.reader = reader;
    }

    protected Reader getReader() {
        return this.reader;
    }

    public Result decode(LuminanceSource source) {
        return decode(toBitmap(source));
    }

    protected BinaryBitmap toBitmap(LuminanceSource source) {
        return new BinaryBitmap(new HybridBinarizer(source));
    }

    protected Result decode(BinaryBitmap bitmap) {
        this.possibleResultPoints.clear();
        try {
            if (this.reader instanceof MultiFormatReader) {
                Result decodeWithState = ((MultiFormatReader) this.reader).decodeWithState(bitmap);
                this.reader.reset();
                return decodeWithState;
            }
            Result decode = this.reader.decode(bitmap);
            this.reader.reset();
            return decode;
        } catch (Exception e) {
            this.reader.reset();
            return null;
        } catch (Throwable th) {
            this.reader.reset();
            throw th;
        }
    }

    public List<ResultPoint> getPossibleResultPoints() {
        return new ArrayList(this.possibleResultPoints);
    }

    @Override // com.google.zxing.ResultPointCallback
    public void foundPossibleResultPoint(ResultPoint point) {
        this.possibleResultPoints.add(point);
    }
}
