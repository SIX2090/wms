package com.google.zxing.qrcode.detector;

import com.google.zxing.NotFoundException;
import com.google.zxing.ResultPointCallback;
import com.google.zxing.common.BitMatrix;
import java.util.ArrayList;
import java.util.List;

/* loaded from: classes11.dex */
final class AlignmentPatternFinder {
    private final int height;
    private final BitMatrix image;
    private final float moduleSize;
    private final ResultPointCallback resultPointCallback;
    private final int startX;
    private final int startY;
    private final int width;
    private final List<AlignmentPattern> possibleCenters = new ArrayList(5);
    private final int[] crossCheckStateCount = new int[3];

    AlignmentPatternFinder(BitMatrix image, int startX, int startY, int width, int height, float moduleSize, ResultPointCallback resultPointCallback) {
        this.image = image;
        this.startX = startX;
        this.startY = startY;
        this.width = width;
        this.height = height;
        this.moduleSize = moduleSize;
        this.resultPointCallback = resultPointCallback;
    }

    AlignmentPattern find() throws NotFoundException {
        AlignmentPattern handlePossibleCenter;
        AlignmentPattern handlePossibleCenter2;
        int i = this.startX;
        int i2 = this.height;
        int i3 = this.width + i;
        int i4 = this.startY + (i2 / 2);
        int[] iArr = new int[3];
        for (int i5 = 0; i5 < i2; i5++) {
            int i6 = ((i5 & 1) == 0 ? (i5 + 1) / 2 : -((i5 + 1) / 2)) + i4;
            iArr[0] = 0;
            iArr[1] = 0;
            iArr[2] = 0;
            int i7 = i;
            while (i7 < i3 && !this.image.get(i7, i6)) {
                i7++;
            }
            int i8 = 0;
            while (i7 < i3) {
                if (this.image.get(i7, i6)) {
                    if (i8 == 1) {
                        iArr[1] = iArr[1] + 1;
                    } else if (i8 == 2) {
                        if (!foundPatternCross(iArr) || (handlePossibleCenter2 = handlePossibleCenter(iArr, i6, i7)) == null) {
                            iArr[0] = iArr[2];
                            iArr[1] = 1;
                            iArr[2] = 0;
                            i8 = 1;
                        } else {
                            return handlePossibleCenter2;
                        }
                    } else {
                        i8++;
                        iArr[i8] = iArr[i8] + 1;
                    }
                } else {
                    if (i8 == 1) {
                        i8++;
                    }
                    iArr[i8] = iArr[i8] + 1;
                }
                i7++;
            }
            if (foundPatternCross(iArr) && (handlePossibleCenter = handlePossibleCenter(iArr, i6, i3)) != null) {
                return handlePossibleCenter;
            }
        }
        if (!this.possibleCenters.isEmpty()) {
            return this.possibleCenters.get(0);
        }
        throw NotFoundException.getNotFoundInstance();
    }

    private static float centerFromEnd(int[] stateCount, int end) {
        return (end - stateCount[2]) - (stateCount[1] / 2.0f);
    }

    private boolean foundPatternCross(int[] stateCount) {
        float moduleSize = this.moduleSize;
        float maxVariance = moduleSize / 2.0f;
        for (int i = 0; i < 3; i++) {
            if (Math.abs(moduleSize - stateCount[i]) >= maxVariance) {
                return false;
            }
        }
        return true;
    }

    /* JADX WARN: Code restructure failed: missing block: B:34:0x0067, code lost:
    
        if (r3[1] <= r12) goto L34;
     */
    /* JADX WARN: Code restructure failed: missing block: B:35:0x006a, code lost:
    
        if (r6 >= r0) goto L64;
     */
    /* JADX WARN: Code restructure failed: missing block: B:37:0x0070, code lost:
    
        if (r0.get(r11, r6) != false) goto L62;
     */
    /* JADX WARN: Code restructure failed: missing block: B:39:0x0074, code lost:
    
        if (r3[2] > r12) goto L63;
     */
    /* JADX WARN: Code restructure failed: missing block: B:40:0x0076, code lost:
    
        r3[2] = r3[2] + 1;
        r6 = r6 + 1;
     */
    /* JADX WARN: Code restructure failed: missing block: B:43:0x0080, code lost:
    
        if (r3[2] <= r12) goto L43;
     */
    /* JADX WARN: Code restructure failed: missing block: B:44:0x0082, code lost:
    
        return Float.NaN;
     */
    /* JADX WARN: Code restructure failed: missing block: B:45:0x0083, code lost:
    
        r4 = (r3[0] + r3[1]) + r3[2];
     */
    /* JADX WARN: Code restructure failed: missing block: B:46:0x0095, code lost:
    
        if ((java.lang.Math.abs(r4 - r13) * 5) < (r13 * 2)) goto L46;
     */
    /* JADX WARN: Code restructure failed: missing block: B:47:0x0097, code lost:
    
        return Float.NaN;
     */
    /* JADX WARN: Code restructure failed: missing block: B:49:0x009c, code lost:
    
        if (foundPatternCross(r3) == false) goto L50;
     */
    /* JADX WARN: Code restructure failed: missing block: B:51:0x00a2, code lost:
    
        return centerFromEnd(r3, r6);
     */
    /* JADX WARN: Code restructure failed: missing block: B:52:0x00a3, code lost:
    
        return Float.NaN;
     */
    /*
        Code decompiled incorrectly, please refer to instructions dump.
        To view partially-correct add '--show-bad-code' argument
    */
    private float crossCheckVertical(int r10, int r11, int r12, int r13) {
        /*
            r9 = this;
            com.google.zxing.common.BitMatrix r0 = r9.image
            r1 = 0
            r2 = r1
            r2 = r0
            int r0 = r0.getHeight()
            int[] r3 = r9.crossCheckStateCount
            r1 = r3
            r4 = 0
            r3[r4] = r4
            r3 = 1
            r1[r3] = r4
            r5 = 2
            r1[r5] = r4
            r6 = r10
        L16:
            if (r6 < 0) goto L2a
            boolean r7 = r2.get(r11, r6)
            if (r7 == 0) goto L2a
            r7 = r1[r3]
            if (r7 > r12) goto L2a
            r7 = r1[r3]
            int r7 = r7 + r3
            r1[r3] = r7
            int r6 = r6 + (-1)
            goto L16
        L2a:
            r7 = 2143289344(0x7fc00000, float:NaN)
            if (r6 < 0) goto La5
            r8 = r1[r3]
            if (r8 <= r12) goto L34
            goto La5
        L34:
            if (r6 < 0) goto L48
            boolean r8 = r2.get(r11, r6)
            if (r8 != 0) goto L48
            r8 = r1[r4]
            if (r8 > r12) goto L48
            r8 = r1[r4]
            int r8 = r8 + r3
            r1[r4] = r8
            int r6 = r6 + (-1)
            goto L34
        L48:
            r8 = r1[r4]
            if (r8 <= r12) goto L4d
            return r7
        L4d:
            int r6 = r10 + 1
        L4f:
            if (r6 >= r0) goto L63
            boolean r8 = r2.get(r11, r6)
            if (r8 == 0) goto L63
            r8 = r1[r3]
            if (r8 > r12) goto L63
            r8 = r1[r3]
            int r8 = r8 + r3
            r1[r3] = r8
            int r6 = r6 + 1
            goto L4f
        L63:
            if (r6 == r0) goto La4
            r8 = r1[r3]
            if (r8 <= r12) goto L6a
            goto La4
        L6a:
            if (r6 >= r0) goto L7e
            boolean r8 = r2.get(r11, r6)
            if (r8 != 0) goto L7e
            r8 = r1[r5]
            if (r8 > r12) goto L7e
            r8 = r1[r5]
            int r8 = r8 + r3
            r1[r5] = r8
            int r6 = r6 + 1
            goto L6a
        L7e:
            r8 = r1[r5]
            if (r8 <= r12) goto L83
            return r7
        L83:
            r4 = r1[r4]
            r3 = r1[r3]
            int r4 = r4 + r3
            r3 = r1[r5]
            int r4 = r4 + r3
            int r3 = r4 - r13
            int r3 = java.lang.Math.abs(r3)
            int r3 = r3 * 5
            int r5 = r13 * 2
            if (r3 < r5) goto L98
            return r7
        L98:
            boolean r3 = r9.foundPatternCross(r1)
            if (r3 == 0) goto La3
            float r3 = centerFromEnd(r1, r6)
            return r3
        La3:
            return r7
        La4:
            return r7
        La5:
            return r7
        */
        throw new UnsupportedOperationException("Method not decompiled: com.google.zxing.qrcode.detector.AlignmentPatternFinder.crossCheckVertical(int, int, int, int):float");
    }

    private AlignmentPattern handlePossibleCenter(int[] stateCount, int i, int j) {
        int stateCountTotal = stateCount[0] + stateCount[1] + stateCount[2];
        float centerJ = centerFromEnd(stateCount, j);
        float centerI = crossCheckVertical(i, (int) centerJ, stateCount[1] * 2, stateCountTotal);
        if (!Float.isNaN(centerI)) {
            float estimatedModuleSize = ((stateCount[0] + stateCount[1]) + stateCount[2]) / 3.0f;
            for (AlignmentPattern center : this.possibleCenters) {
                if (center.aboutEquals(estimatedModuleSize, centerI, centerJ)) {
                    return center.combineEstimate(centerI, centerJ, estimatedModuleSize);
                }
            }
            AlignmentPattern point = new AlignmentPattern(centerJ, centerI, estimatedModuleSize);
            this.possibleCenters.add(point);
            if (this.resultPointCallback != null) {
                this.resultPointCallback.foundPossibleResultPoint(point);
                return null;
            }
            return null;
        }
        return null;
    }
}
