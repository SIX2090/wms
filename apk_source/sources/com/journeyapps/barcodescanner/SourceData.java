package com.journeyapps.barcodescanner;

import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Matrix;
import android.graphics.Rect;
import android.graphics.YuvImage;
import com.google.zxing.PlanarYUVLuminanceSource;
import com.google.zxing.ResultPoint;
import java.io.ByteArrayOutputStream;

/* loaded from: classes11.dex */
public class SourceData {
    private Rect cropRect;
    private RawImageData data;
    private int imageFormat;
    private boolean previewMirrored;
    private int rotation;
    private int scalingFactor = 1;

    public SourceData(byte[] data, int dataWidth, int dataHeight, int imageFormat, int rotation) {
        this.data = new RawImageData(data, dataWidth, dataHeight);
        this.rotation = rotation;
        this.imageFormat = imageFormat;
        if (dataWidth * dataHeight > data.length) {
            throw new IllegalArgumentException("Image data does not match the resolution. " + dataWidth + "x" + dataHeight + " > " + data.length);
        }
    }

    public Rect getCropRect() {
        return this.cropRect;
    }

    public void setCropRect(Rect cropRect) {
        this.cropRect = cropRect;
    }

    public boolean isPreviewMirrored() {
        return this.previewMirrored;
    }

    public void setPreviewMirrored(boolean previewMirrored) {
        this.previewMirrored = previewMirrored;
    }

    public int getScalingFactor() {
        return this.scalingFactor;
    }

    public void setScalingFactor(int scalingFactor) {
        this.scalingFactor = scalingFactor;
    }

    public byte[] getData() {
        return this.data.getData();
    }

    public int getDataWidth() {
        return this.data.getWidth();
    }

    public int getDataHeight() {
        return this.data.getHeight();
    }

    public ResultPoint translateResultPoint(ResultPoint point) {
        float x = (point.getX() * this.scalingFactor) + this.cropRect.left;
        float y = (point.getY() * this.scalingFactor) + this.cropRect.top;
        if (this.previewMirrored) {
            x = this.data.getWidth() - x;
        }
        return new ResultPoint(x, y);
    }

    public boolean isRotated() {
        return this.rotation % 180 != 0;
    }

    public int getImageFormat() {
        return this.imageFormat;
    }

    public PlanarYUVLuminanceSource createSource() {
        RawImageData rotated = this.data.rotateCameraPreview(this.rotation);
        RawImageData scaled = rotated.cropAndScale(this.cropRect, this.scalingFactor);
        return new PlanarYUVLuminanceSource(scaled.getData(), scaled.getWidth(), scaled.getHeight(), 0, 0, scaled.getWidth(), scaled.getHeight(), false);
    }

    public Bitmap getBitmap() {
        return getBitmap(1);
    }

    public Bitmap getBitmap(int scaleFactor) {
        return getBitmap(this.cropRect, scaleFactor);
    }

    public Bitmap getBitmap(Rect cropRect, int scaleFactor) {
        if (cropRect == null) {
            cropRect = new Rect(0, 0, this.data.getWidth(), this.data.getHeight());
        } else if (isRotated()) {
            cropRect = new Rect(cropRect.top, cropRect.left, cropRect.bottom, cropRect.right);
        }
        YuvImage img = new YuvImage(this.data.getData(), this.imageFormat, this.data.getWidth(), this.data.getHeight(), null);
        ByteArrayOutputStream buffer = new ByteArrayOutputStream();
        img.compressToJpeg(cropRect, 90, buffer);
        byte[] jpegData = buffer.toByteArray();
        BitmapFactory.Options options = new BitmapFactory.Options();
        options.inSampleSize = scaleFactor;
        Bitmap bitmap = BitmapFactory.decodeByteArray(jpegData, 0, jpegData.length, options);
        if (this.rotation != 0) {
            Matrix imageMatrix = new Matrix();
            imageMatrix.postRotate(this.rotation);
            return Bitmap.createBitmap(bitmap, 0, 0, bitmap.getWidth(), bitmap.getHeight(), imageMatrix, false);
        }
        return bitmap;
    }
}
