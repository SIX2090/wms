package com.journeyapps.barcodescanner.camera;

import android.graphics.Rect;
import android.util.Log;
import com.journeyapps.barcodescanner.Size;

/* loaded from: classes11.dex */
public class FitCenterStrategy extends PreviewScalingStrategy {
    private static final String TAG = FitCenterStrategy.class.getSimpleName();

    @Override // com.journeyapps.barcodescanner.camera.PreviewScalingStrategy
    protected float getScore(Size size, Size desired) {
        float scaleScore;
        if (size.width <= 0 || size.height <= 0) {
            return 0.0f;
        }
        Size scaled = size.scaleFit(desired);
        float scaleRatio = (scaled.width * 1.0f) / size.width;
        if (scaleRatio > 1.0f) {
            scaleScore = (float) Math.pow(1.0f / scaleRatio, 1.1d);
        } else {
            scaleScore = scaleRatio;
        }
        float cropRatio = ((desired.width * 1.0f) / scaled.width) * ((desired.height * 1.0f) / scaled.height);
        float cropScore = ((1.0f / cropRatio) / cropRatio) / cropRatio;
        return scaleScore * cropScore;
    }

    @Override // com.journeyapps.barcodescanner.camera.PreviewScalingStrategy
    public Rect scalePreview(Size previewSize, Size viewfinderSize) {
        Size scaledPreview = previewSize.scaleFit(viewfinderSize);
        Log.i(TAG, "Preview: " + previewSize + "; Scaled: " + scaledPreview + "; Want: " + viewfinderSize);
        int dx = (scaledPreview.width - viewfinderSize.width) / 2;
        int dy = (scaledPreview.height - viewfinderSize.height) / 2;
        return new Rect(-dx, -dy, scaledPreview.width - dx, scaledPreview.height - dy);
    }
}
