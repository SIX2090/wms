package com.google.zxing.aztec;

import com.google.zxing.BinaryBitmap;
import com.google.zxing.FormatException;
import com.google.zxing.NotFoundException;
import com.google.zxing.Reader;
import com.google.zxing.Result;

/* loaded from: classes11.dex */
public final class AztecReader implements Reader {
    @Override // com.google.zxing.Reader
    public Result decode(BinaryBitmap image) throws NotFoundException, FormatException {
        return decode(image, null);
    }

    /* JADX WARN: Removed duplicated region for block: B:14:0x0056  */
    /* JADX WARN: Removed duplicated region for block: B:18:0x0063 A[LOOP:0: B:17:0x0061->B:18:0x0063, LOOP_END] */
    /* JADX WARN: Removed duplicated region for block: B:22:0x0089  */
    /* JADX WARN: Removed duplicated region for block: B:25:0x0094  */
    /* JADX WARN: Removed duplicated region for block: B:35:0x0053  */
    /* JADX WARN: Removed duplicated region for block: B:9:0x0035  */
    @Override // com.google.zxing.Reader
    /*
        Code decompiled incorrectly, please refer to instructions dump.
        To view partially-correct add '--show-bad-code' argument
    */
    public com.google.zxing.Result decode(com.google.zxing.BinaryBitmap r11, java.util.Map<com.google.zxing.DecodeHintType, ?> r12) throws com.google.zxing.NotFoundException, com.google.zxing.FormatException {
        /*
            r10 = this;
            com.google.zxing.aztec.detector.Detector r0 = new com.google.zxing.aztec.detector.Detector
            com.google.zxing.common.BitMatrix r11 = r11.getBlackMatrix()
            r0.<init>(r11)
            r11 = 0
            r1 = 0
            com.google.zxing.aztec.AztecDetectorResult r2 = r0.detect(r11)     // Catch: com.google.zxing.FormatException -> L29 com.google.zxing.NotFoundException -> L2f
            com.google.zxing.ResultPoint[] r3 = r2.getPoints()     // Catch: com.google.zxing.FormatException -> L29 com.google.zxing.NotFoundException -> L2f
            com.google.zxing.aztec.decoder.Decoder r4 = new com.google.zxing.aztec.decoder.Decoder     // Catch: com.google.zxing.FormatException -> L25 com.google.zxing.NotFoundException -> L27
            r4.<init>()     // Catch: com.google.zxing.FormatException -> L25 com.google.zxing.NotFoundException -> L27
            com.google.zxing.common.DecoderResult r2 = r4.decode(r2)     // Catch: com.google.zxing.FormatException -> L25 com.google.zxing.NotFoundException -> L27
            r4 = r3
            r3 = r1
            r1 = r2
            r2 = r3
            goto L33
        L25:
            r2 = move-exception
            goto L2b
        L27:
            r2 = move-exception
            goto L31
        L29:
            r2 = move-exception
            r3 = r1
        L2b:
            r4 = r3
            r3 = r2
            r2 = r1
            goto L33
        L2f:
            r2 = move-exception
            r3 = r1
        L31:
            r4 = r3
            r3 = r1
        L33:
            if (r1 != 0) goto L53
            r1 = 1
            com.google.zxing.aztec.AztecDetectorResult r0 = r0.detect(r1)     // Catch: com.google.zxing.FormatException -> L49 com.google.zxing.NotFoundException -> L4b
            com.google.zxing.ResultPoint[] r4 = r0.getPoints()     // Catch: com.google.zxing.FormatException -> L49 com.google.zxing.NotFoundException -> L4b
            com.google.zxing.aztec.decoder.Decoder r1 = new com.google.zxing.aztec.decoder.Decoder     // Catch: com.google.zxing.FormatException -> L49 com.google.zxing.NotFoundException -> L4b
            r1.<init>()     // Catch: com.google.zxing.FormatException -> L49 com.google.zxing.NotFoundException -> L4b
            com.google.zxing.common.DecoderResult r1 = r1.decode(r0)     // Catch: com.google.zxing.FormatException -> L49 com.google.zxing.NotFoundException -> L4b
            r6 = r4
            goto L54
        L49:
            r11 = move-exception
            goto L4c
        L4b:
            r11 = move-exception
        L4c:
            if (r2 != 0) goto L52
            if (r3 == 0) goto L51
            throw r3
        L51:
            throw r11
        L52:
            throw r2
        L53:
            r6 = r4
        L54:
            if (r12 == 0) goto L6b
            com.google.zxing.DecodeHintType r0 = com.google.zxing.DecodeHintType.NEED_RESULT_POINT_CALLBACK
            java.lang.Object r12 = r12.get(r0)
            com.google.zxing.ResultPointCallback r12 = (com.google.zxing.ResultPointCallback) r12
            if (r12 == 0) goto L6b
            int r0 = r6.length
        L61:
            if (r11 >= r0) goto L6b
            r2 = r6[r11]
            r12.foundPossibleResultPoint(r2)
            int r11 = r11 + 1
            goto L61
        L6b:
            com.google.zxing.Result r11 = new com.google.zxing.Result
            java.lang.String r3 = r1.getText()
            byte[] r4 = r1.getRawBytes()
            int r5 = r1.getNumBits()
            com.google.zxing.BarcodeFormat r7 = com.google.zxing.BarcodeFormat.AZTEC
            long r8 = java.lang.System.currentTimeMillis()
            r2 = r11
            r2.<init>(r3, r4, r5, r6, r7, r8)
            java.util.List r12 = r1.getByteSegments()
            if (r12 == 0) goto L8e
            com.google.zxing.ResultMetadataType r0 = com.google.zxing.ResultMetadataType.BYTE_SEGMENTS
            r11.putMetadata(r0, r12)
        L8e:
            java.lang.String r12 = r1.getECLevel()
            if (r12 == 0) goto L99
            com.google.zxing.ResultMetadataType r0 = com.google.zxing.ResultMetadataType.ERROR_CORRECTION_LEVEL
            r11.putMetadata(r0, r12)
        L99:
            return r11
        */
        throw new UnsupportedOperationException("Method not decompiled: com.google.zxing.aztec.AztecReader.decode(com.google.zxing.BinaryBitmap, java.util.Map):com.google.zxing.Result");
    }

    @Override // com.google.zxing.Reader
    public void reset() {
    }
}
