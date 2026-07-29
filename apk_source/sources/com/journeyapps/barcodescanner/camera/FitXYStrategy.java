package com.journeyapps.barcodescanner.camera;

import android.graphics.Rect;
import com.journeyapps.barcodescanner.Size;

/* loaded from: classes11.dex */
public class FitXYStrategy extends PreviewScalingStrategy {
    private static final String TAG = FitXYStrategy.class.getSimpleName();

    private static float absRatio(float ratio) {
        if (ratio < 1.0f) {
            return 1.0f / ratio;
        }
        return ratio;
    }

    @Override // com.journeyapps.barcodescanner.camera.PreviewScalingStrategy
    protected float getScore(Size size, Size desired) {
        if (size.width <= 0 || size.height <= 0) {
            return 0.0f;
        }
        float scaleX = absRatio((size.width * 1.0f) / desired.width);
        float scaleY = absRatio((size.height * 1.0f) / desired.height);
        float scaleScore = (1.0f / scaleX) / scaleY;
        float distortion = absRatio(((size.width * 1.0f) / size.height) / ((desired.width * 1.0f) / desired.height));
        float distortionScore = ((1.0f / distortion) / distortion) / distortion;
        return scaleScore * distortionScore;
    }

    @Override // com.journeyapps.barcodescanner.camera.PreviewScalingStrategy
    public Rect scalePreview(Size previewSize, Size viewfinderSize) {
        return new Rect(0, 0, viewfinderSize.width, viewfinderSize.height);
    }
}
