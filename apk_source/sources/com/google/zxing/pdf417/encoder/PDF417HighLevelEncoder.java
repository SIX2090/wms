package com.google.zxing.pdf417.encoder;

import com.google.zxing.WriterException;
import com.google.zxing.common.CharacterSetECI;
import java.math.BigInteger;
import java.nio.charset.Charset;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import kotlin.UByte;
import kotlin.io.encoding.Base64;
import okio.Utf8;

/* loaded from: classes11.dex */
final class PDF417HighLevelEncoder {
    private static final int BYTE_COMPACTION = 1;
    private static final int ECI_CHARSET = 927;
    private static final int ECI_GENERAL_PURPOSE = 926;
    private static final int ECI_USER_DEFINED = 925;
    private static final int LATCH_TO_BYTE = 924;
    private static final int LATCH_TO_BYTE_PADDED = 901;
    private static final int LATCH_TO_NUMERIC = 902;
    private static final int LATCH_TO_TEXT = 900;
    private static final int NUMERIC_COMPACTION = 2;
    private static final int SHIFT_TO_BYTE = 913;
    private static final int SUBMODE_ALPHA = 0;
    private static final int SUBMODE_LOWER = 1;
    private static final int SUBMODE_MIXED = 2;
    private static final int SUBMODE_PUNCTUATION = 3;
    private static final int TEXT_COMPACTION = 0;
    private static final byte[] TEXT_MIXED_RAW = {48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 38, 13, 9, 44, 58, 35, 45, 46, 36, 47, 43, 37, 42, Base64.padSymbol, 94, 0, 32, 0, 0, 0};
    private static final byte[] TEXT_PUNCTUATION_RAW = {59, 60, 62, 64, 91, 92, 93, 95, 96, 126, 33, 13, 9, 44, 58, 10, 45, 46, 36, 47, 34, 124, 42, 40, 41, Utf8.REPLACEMENT_BYTE, 123, 125, 39, 0};
    private static final byte[] MIXED = new byte[128];
    private static final byte[] PUNCTUATION = new byte[128];
    private static final Charset DEFAULT_ENCODING = StandardCharsets.ISO_8859_1;

    static {
        Arrays.fill(MIXED, (byte) -1);
        for (int i = 0; i < TEXT_MIXED_RAW.length; i++) {
            byte b = TEXT_MIXED_RAW[i];
            if (b > 0) {
                MIXED[b] = (byte) i;
            }
        }
        Arrays.fill(PUNCTUATION, (byte) -1);
        for (int i2 = 0; i2 < TEXT_PUNCTUATION_RAW.length; i2++) {
            byte b2 = TEXT_PUNCTUATION_RAW[i2];
            if (b2 > 0) {
                PUNCTUATION[b2] = (byte) i2;
            }
        }
    }

    private PDF417HighLevelEncoder() {
    }

    static String encodeHighLevel(String msg, Compaction compaction, Charset encoding) throws WriterException {
        CharacterSetECI eci;
        Charset encoding2 = encoding;
        StringBuilder sb = new StringBuilder(msg.length());
        if (encoding2 == null) {
            encoding2 = DEFAULT_ENCODING;
        } else if (!DEFAULT_ENCODING.equals(encoding2) && (eci = CharacterSetECI.getCharacterSetECIByName(encoding.name())) != null) {
            encodingECI(eci.getValue(), sb);
        }
        int len = msg.length();
        int p = 0;
        int textSubMode = 0;
        switch (compaction) {
            case TEXT:
                encodeText(msg, 0, len, sb, 0);
                break;
            case BYTE:
                byte[] msgBytes = msg.getBytes(encoding2);
                encodeBinary(msgBytes, 0, msgBytes.length, 1, sb);
                break;
            case NUMERIC:
                sb.append((char) 902);
                encodeNumeric(msg, 0, len, sb);
                break;
            default:
                int encodingMode = 0;
                while (p < len) {
                    int n = determineConsecutiveDigitCount(msg, p);
                    if (n >= 13) {
                        sb.append((char) 902);
                        encodingMode = 2;
                        textSubMode = 0;
                        encodeNumeric(msg, p, n, sb);
                        p += n;
                    } else {
                        int t = determineConsecutiveTextCount(msg, p);
                        if (t >= 5 || n == len) {
                            if (encodingMode != 0) {
                                sb.append((char) 900);
                                encodingMode = 0;
                                textSubMode = 0;
                            }
                            textSubMode = encodeText(msg, p, t, sb, textSubMode);
                            p += t;
                        } else {
                            int determineConsecutiveBinaryCount = determineConsecutiveBinaryCount(msg, p, encoding2);
                            int b = determineConsecutiveBinaryCount;
                            if (determineConsecutiveBinaryCount == 0) {
                                b = 1;
                            }
                            byte[] bytes = msg.substring(p, p + b).getBytes(encoding2);
                            if (bytes.length != 1 || encodingMode != 0) {
                                encodeBinary(bytes, 0, bytes.length, encodingMode, sb);
                                encodingMode = 1;
                                textSubMode = 0;
                            } else {
                                encodeBinary(bytes, 0, 1, 0, sb);
                            }
                            p += b;
                        }
                    }
                }
                break;
        }
        return sb.toString();
    }

    private static int encodeText(CharSequence charSequence, int i, int i2, StringBuilder sb, int i3) {
        StringBuilder sb2 = new StringBuilder(i2);
        int i4 = i3;
        int i5 = 0;
        while (true) {
            int i6 = i + i5;
            char charAt = charSequence.charAt(i6);
            switch (i4) {
                case 0:
                    if (isAlphaUpper(charAt)) {
                        if (charAt == ' ') {
                            sb2.append((char) 26);
                            break;
                        } else {
                            sb2.append((char) (charAt - 'A'));
                            break;
                        }
                    } else if (isAlphaLower(charAt)) {
                        sb2.append((char) 27);
                        i4 = 1;
                    } else if (isMixed(charAt)) {
                        sb2.append((char) 28);
                        i4 = 2;
                    } else {
                        sb2.append((char) 29);
                        sb2.append((char) PUNCTUATION[charAt]);
                        break;
                    }
                case 1:
                    if (isAlphaLower(charAt)) {
                        if (charAt == ' ') {
                            sb2.append((char) 26);
                            break;
                        } else {
                            sb2.append((char) (charAt - 'a'));
                            break;
                        }
                    } else if (isAlphaUpper(charAt)) {
                        sb2.append((char) 27);
                        sb2.append((char) (charAt - 'A'));
                        break;
                    } else if (isMixed(charAt)) {
                        sb2.append((char) 28);
                        i4 = 2;
                    } else {
                        sb2.append((char) 29);
                        sb2.append((char) PUNCTUATION[charAt]);
                        break;
                    }
                case 2:
                    if (isMixed(charAt)) {
                        sb2.append((char) MIXED[charAt]);
                        break;
                    } else if (isAlphaUpper(charAt)) {
                        sb2.append((char) 28);
                        i4 = 0;
                    } else if (isAlphaLower(charAt)) {
                        sb2.append((char) 27);
                        i4 = 1;
                    } else {
                        int i7 = i6 + 1;
                        if (i7 < i2 && isPunctuation(charSequence.charAt(i7))) {
                            sb2.append((char) 25);
                            i4 = 3;
                        } else {
                            sb2.append((char) 29);
                            sb2.append((char) PUNCTUATION[charAt]);
                            break;
                        }
                    }
                    break;
                default:
                    if (isPunctuation(charAt)) {
                        sb2.append((char) PUNCTUATION[charAt]);
                        break;
                    } else {
                        sb2.append((char) 29);
                        i4 = 0;
                    }
            }
            i5++;
            if (i5 >= i2) {
                int length = sb2.length();
                char c = 0;
                for (int i8 = 0; i8 < length; i8++) {
                    if (i8 % 2 != 0) {
                        c = (char) ((c * 30) + sb2.charAt(i8));
                        sb.append(c);
                    } else {
                        c = sb2.charAt(i8);
                    }
                }
                if (length % 2 != 0) {
                    sb.append((char) ((c * 30) + 29));
                }
                return i4;
            }
        }
    }

    private static void encodeBinary(byte[] bytes, int startpos, int count, int startmode, StringBuilder sb) {
        if (count == 1 && startmode == 0) {
            sb.append((char) 913);
        } else if (count % 6 == 0) {
            sb.append((char) 924);
        } else {
            sb.append((char) 901);
        }
        int idx = startpos;
        if (count >= 6) {
            char[] chars = new char[5];
            while ((startpos + count) - idx >= 6) {
                long t = 0;
                for (int i = 0; i < 6; i++) {
                    t = (t << 8) + (bytes[idx + i] & UByte.MAX_VALUE);
                }
                for (int i2 = 0; i2 < 5; i2++) {
                    chars[i2] = (char) (t % 900);
                    t /= 900;
                }
                for (int i3 = 4; i3 >= 0; i3--) {
                    sb.append(chars[i3]);
                }
                idx += 6;
            }
        }
        for (int i4 = idx; i4 < startpos + count; i4++) {
            int ch = bytes[i4] & UByte.MAX_VALUE;
            sb.append((char) ch);
        }
    }

    private static void encodeNumeric(String msg, int startpos, int count, StringBuilder sb) {
        BigInteger divide;
        int idx = 0;
        StringBuilder tmp = new StringBuilder((count / 3) + 1);
        BigInteger num900 = BigInteger.valueOf(900L);
        BigInteger num0 = BigInteger.valueOf(0L);
        while (idx < count) {
            tmp.setLength(0);
            int len = Math.min(44, count - idx);
            String part = "1" + msg.substring(startpos + idx, startpos + idx + len);
            BigInteger bigint = new BigInteger(part);
            do {
                tmp.append((char) bigint.mod(num900).intValue());
                divide = bigint.divide(num900);
                bigint = divide;
            } while (!divide.equals(num0));
            for (int i = tmp.length() - 1; i >= 0; i--) {
                sb.append(tmp.charAt(i));
            }
            idx += len;
        }
    }

    private static boolean isDigit(char ch) {
        return ch >= '0' && ch <= '9';
    }

    private static boolean isAlphaUpper(char ch) {
        if (ch != ' ') {
            return ch >= 'A' && ch <= 'Z';
        }
        return true;
    }

    private static boolean isAlphaLower(char ch) {
        if (ch != ' ') {
            return ch >= 'a' && ch <= 'z';
        }
        return true;
    }

    private static boolean isMixed(char ch) {
        return MIXED[ch] != -1;
    }

    private static boolean isPunctuation(char ch) {
        return PUNCTUATION[ch] != -1;
    }

    private static boolean isText(char ch) {
        if (ch == '\t' || ch == '\n' || ch == '\r') {
            return true;
        }
        return ch >= ' ' && ch <= '~';
    }

    private static int determineConsecutiveDigitCount(CharSequence msg, int startpos) {
        int count = 0;
        int len = msg.length();
        int idx = startpos;
        if (startpos < len) {
            char ch = msg.charAt(startpos);
            while (isDigit(ch) && idx < len) {
                count++;
                idx++;
                if (idx < len) {
                    ch = msg.charAt(idx);
                }
            }
        }
        return count;
    }

    /* JADX WARN: Code restructure failed: missing block: B:32:0x0028, code lost:
    
        return (r1 - r7) - r3;
     */
    /*
        Code decompiled incorrectly, please refer to instructions dump.
        To view partially-correct add '--show-bad-code' argument
    */
    private static int determineConsecutiveTextCount(java.lang.CharSequence r6, int r7) {
        /*
            int r0 = r6.length()
            r1 = r7
        L5:
            if (r1 >= r0) goto L39
            char r2 = r6.charAt(r1)
            r3 = 0
        Lc:
            r4 = 13
            if (r3 >= r4) goto L23
            boolean r5 = isDigit(r2)
            if (r5 == 0) goto L23
            if (r1 >= r0) goto L23
            int r3 = r3 + 1
            int r1 = r1 + 1
            if (r1 >= r0) goto Lc
            char r2 = r6.charAt(r1)
            goto Lc
        L23:
            if (r3 < r4) goto L29
            int r4 = r1 - r7
            int r4 = r4 - r3
            return r4
        L29:
            if (r3 > 0) goto L5
            char r4 = r6.charAt(r1)
            boolean r4 = isText(r4)
            if (r4 == 0) goto L39
        L36:
            int r1 = r1 + 1
            goto L5
        L39:
            int r2 = r1 - r7
            return r2
        */
        throw new UnsupportedOperationException("Method not decompiled: com.google.zxing.pdf417.encoder.PDF417HighLevelEncoder.determineConsecutiveTextCount(java.lang.CharSequence, int):int");
    }

    /* JADX WARN: Code restructure failed: missing block: B:22:0x002b, code lost:
    
        return r2 - r9;
     */
    /*
        Code decompiled incorrectly, please refer to instructions dump.
        To view partially-correct add '--show-bad-code' argument
    */
    private static int determineConsecutiveBinaryCount(java.lang.String r8, int r9, java.nio.charset.Charset r10) throws com.google.zxing.WriterException {
        /*
            java.nio.charset.CharsetEncoder r0 = r10.newEncoder()
            int r1 = r8.length()
            r2 = r9
            r3 = 0
        La:
            if (r2 >= r1) goto L5f
            char r4 = r8.charAt(r2)
            r5 = 0
        L11:
            r6 = 13
            if (r5 >= r6) goto L27
            boolean r7 = isDigit(r4)
            if (r7 == 0) goto L27
            int r5 = r5 + 1
            int r7 = r2 + r5
            r3 = r7
            if (r7 >= r1) goto L27
            char r4 = r8.charAt(r3)
            goto L11
        L27:
            if (r5 < r6) goto L2c
            int r3 = r2 - r9
            return r3
        L2c:
            char r4 = r8.charAt(r2)
            boolean r6 = r0.canEncode(r4)
            if (r6 == 0) goto L3a
        L37:
            int r2 = r2 + 1
            goto La
        L3a:
            com.google.zxing.WriterException r3 = new com.google.zxing.WriterException
            java.lang.StringBuilder r6 = new java.lang.StringBuilder
            java.lang.String r7 = "Non-encodable character detected: "
            r6.<init>(r7)
            java.lang.StringBuilder r6 = r6.append(r4)
            java.lang.String r7 = " (Unicode: "
            java.lang.StringBuilder r6 = r6.append(r7)
            java.lang.StringBuilder r6 = r6.append(r4)
            r7 = 41
            java.lang.StringBuilder r6 = r6.append(r7)
            java.lang.String r6 = r6.toString()
            r3.<init>(r6)
            throw r3
        L5f:
            int r3 = r2 - r9
            return r3
        */
        throw new UnsupportedOperationException("Method not decompiled: com.google.zxing.pdf417.encoder.PDF417HighLevelEncoder.determineConsecutiveBinaryCount(java.lang.String, int, java.nio.charset.Charset):int");
    }

    private static void encodingECI(int eci, StringBuilder sb) throws WriterException {
        if (eci >= 0 && eci < LATCH_TO_TEXT) {
            sb.append((char) 927);
            sb.append((char) eci);
        } else if (eci < 810900) {
            sb.append((char) 926);
            sb.append((char) ((eci / LATCH_TO_TEXT) - 1));
            sb.append((char) (eci % LATCH_TO_TEXT));
        } else {
            if (eci < 811800) {
                sb.append((char) 925);
                sb.append((char) (810900 - eci));
                return;
            }
            throw new WriterException("ECI number not in valid range from 0..811799, but was ".concat(String.valueOf(eci)));
        }
    }
}
