package com.journeyapps.barcodescanner.camera;

import android.graphics.Rect;
import android.util.Log;
import com.journeyapps.barcodescanner.Size;
import java.util.Collections;
import java.util.Comparator;
import java.util.List;

/* loaded from: classes11.dex */
public abstract class PreviewScalingStrategy {
    private static final String TAG = PreviewScalingStrategy.class.getSimpleName();

    public abstract Rect scalePreview(Size size, Size size2);

    public Size getBestPreviewSize(List<Size> sizes, Size desired) {
        List<Size> ordered = getBestPreviewOrder(sizes, desired);
        Log.i(TAG, "Viewfinder size: " + desired);
        Log.i(TAG, "Preview in order of preference: " + ordered);
        return ordered.get(0);
    }

    public List<Size> getBestPreviewOrder(List<Size> sizes, final Size desired) {
        if (desired == null) {
            return sizes;
        }
        Collections.sort(sizes, new Comparator<Size>() { // from class: com.journeyapps.barcodescanner.camera.PreviewScalingStrategy.1
            @Override // java.util.Comparator
            public int compare(Size a, Size b) {
                float aScore = PreviewScalingStrategy.this.getScore(a, desired);
                float bScore = PreviewScalingStrategy.this.getScore(b, desired);
                return Float.compare(bScore, aScore);
            }
        });
        return sizes;
    }

    protected float getScore(Size size, Size desired) {
        return 0.5f;
    }
}
