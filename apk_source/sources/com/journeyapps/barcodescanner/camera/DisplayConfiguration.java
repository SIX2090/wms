package com.journeyapps.barcodescanner.camera;

import android.graphics.Rect;
import com.journeyapps.barcodescanner.Size;
import java.util.List;

/* loaded from: classes11.dex */
public class DisplayConfiguration {
    private static final String TAG = DisplayConfiguration.class.getSimpleName();
    private boolean center = false;
    private PreviewScalingStrategy previewScalingStrategy = new FitCenterStrategy();
    private int rotation;
    private Size viewfinderSize;

    public DisplayConfiguration(int rotation) {
        this.rotation = rotation;
    }

    public DisplayConfiguration(int rotation, Size viewfinderSize) {
        this.rotation = rotation;
        this.viewfinderSize = viewfinderSize;
    }

    public int getRotation() {
        return this.rotation;
    }

    public Size getViewfinderSize() {
        return this.viewfinderSize;
    }

    public PreviewScalingStrategy getPreviewScalingStrategy() {
        return this.previewScalingStrategy;
    }

    public void setPreviewScalingStrategy(PreviewScalingStrategy previewScalingStrategy) {
        this.previewScalingStrategy = previewScalingStrategy;
    }

    public Size getDesiredPreviewSize(boolean rotate) {
        if (this.viewfinderSize == null) {
            return null;
        }
        if (rotate) {
            return this.viewfinderSize.rotate();
        }
        return this.viewfinderSize;
    }

    public Size getBestPreviewSize(List<Size> sizes, boolean isRotated) {
        Size desired = getDesiredPreviewSize(isRotated);
        return this.previewScalingStrategy.getBestPreviewSize(sizes, desired);
    }

    public Rect scalePreview(Size previewSize) {
        return this.previewScalingStrategy.scalePreview(previewSize, this.viewfinderSize);
    }
}
