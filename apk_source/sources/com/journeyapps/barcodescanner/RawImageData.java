package com.journeyapps.barcodescanner;

import android.graphics.Rect;
import com.google.zxing.pdf417.PDF417Common;

/* loaded from: classes11.dex */
public class RawImageData {
    private byte[] data;
    private int height;
    private int width;

    public RawImageData(byte[] data, int width, int height) {
        this.data = data;
        this.width = width;
        this.height = height;
    }

    public byte[] getData() {
        return this.data;
    }

    public int getWidth() {
        return this.width;
    }

    public int getHeight() {
        return this.height;
    }

    public RawImageData cropAndScale(Rect cropRect, int scale) {
        int width = cropRect.width() / scale;
        int height = cropRect.height() / scale;
        int top = cropRect.top;
        int area = width * height;
        byte[] matrix = new byte[area];
        if (scale == 1) {
            int inputOffset = (this.width * top) + cropRect.left;
            for (int y = 0; y < height; y++) {
                int outputOffset = y * width;
                System.arraycopy(this.data, inputOffset, matrix, outputOffset, width);
                inputOffset += this.width;
            }
        } else {
            int inputOffset2 = (this.width * top) + cropRect.left;
            for (int y2 = 0; y2 < height; y2++) {
                int outputOffset2 = y2 * width;
                int xOffset = inputOffset2;
                for (int x = 0; x < width; x++) {
                    matrix[outputOffset2] = this.data[xOffset];
                    xOffset += scale;
                    outputOffset2++;
                }
                int x2 = this.width;
                inputOffset2 += x2 * scale;
            }
        }
        return new RawImageData(matrix, width, height);
    }

    public RawImageData rotateCameraPreview(int cameraRotation) {
        switch (cameraRotation) {
            case PDF417Common.MAX_ROWS_IN_BARCODE /* 90 */:
                return new RawImageData(rotateCW(this.data, this.width, this.height), this.height, this.width);
            case 180:
                return new RawImageData(rotate180(this.data, this.width, this.height), this.width, this.height);
            case 270:
                return new RawImageData(rotateCCW(this.data, this.width, this.height), this.height, this.width);
            default:
                return this;
        }
    }

    public static byte[] rotateCW(byte[] data, int imageWidth, int imageHeight) {
        byte[] yuv = new byte[imageWidth * imageHeight];
        int i = 0;
        for (int x = 0; x < imageWidth; x++) {
            for (int y = imageHeight - 1; y >= 0; y--) {
                yuv[i] = data[(y * imageWidth) + x];
                i++;
            }
        }
        return yuv;
    }

    public static byte[] rotate180(byte[] data, int imageWidth, int imageHeight) {
        int n = imageWidth * imageHeight;
        byte[] yuv = new byte[n];
        int i = n - 1;
        for (int j = 0; j < n; j++) {
            yuv[i] = data[j];
            i--;
        }
        return yuv;
    }

    public static byte[] rotateCCW(byte[] data, int imageWidth, int imageHeight) {
        int n = imageWidth * imageHeight;
        byte[] yuv = new byte[n];
        int i = n - 1;
        for (int x = 0; x < imageWidth; x++) {
            for (int y = imageHeight - 1; y >= 0; y--) {
                yuv[i] = data[(y * imageWidth) + x];
                i--;
            }
        }
        return yuv;
    }
}
