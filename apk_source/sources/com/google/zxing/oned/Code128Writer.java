package com.google.zxing.oned;

import com.google.zxing.BarcodeFormat;
import java.util.ArrayList;
import java.util.Collection;
import java.util.Collections;
import java.util.Iterator;

/* loaded from: classes11.dex */
public final class Code128Writer extends OneDimensionalCodeWriter {
    private static final int CODE_CODE_A = 101;
    private static final int CODE_CODE_B = 100;
    private static final int CODE_CODE_C = 99;
    private static final int CODE_FNC_1 = 102;
    private static final int CODE_FNC_2 = 97;
    private static final int CODE_FNC_3 = 96;
    private static final int CODE_FNC_4_A = 101;
    private static final int CODE_FNC_4_B = 100;
    private static final int CODE_START_A = 103;
    private static final int CODE_START_B = 104;
    private static final int CODE_START_C = 105;
    private static final int CODE_STOP = 106;
    private static final char ESCAPE_FNC_1 = 241;
    private static final char ESCAPE_FNC_2 = 242;
    private static final char ESCAPE_FNC_3 = 243;
    private static final char ESCAPE_FNC_4 = 244;

    private enum CType {
        UNCODABLE,
        ONE_DIGIT,
        TWO_DIGITS,
        FNC_1
    }

    @Override // com.google.zxing.oned.OneDimensionalCodeWriter
    protected Collection<BarcodeFormat> getSupportedWriteFormats() {
        return Collections.singleton(BarcodeFormat.CODE_128);
    }

    @Override // com.google.zxing.oned.OneDimensionalCodeWriter
    public boolean[] encode(String str) {
        int length = str.length();
        if (length <= 0 || length > 80) {
            throw new IllegalArgumentException("Contents length should be between 1 and 80 characters, but got ".concat(String.valueOf(length)));
        }
        int i = 0;
        for (int i2 = 0; i2 < length; i2++) {
            char charAt = str.charAt(i2);
            switch (charAt) {
                case 241:
                case 242:
                case 243:
                case 244:
                    break;
                default:
                    if (charAt > 127) {
                        throw new IllegalArgumentException("Bad character in input: ".concat(String.valueOf(charAt)));
                    }
                    break;
            }
        }
        ArrayList<int[]> arrayList = new ArrayList();
        int i3 = 0;
        int i4 = 0;
        int i5 = 0;
        int i6 = 1;
        while (true) {
            int i7 = CODE_START_A;
            if (i3 < length) {
                int chooseCode = chooseCode(str, i3, i5);
                if (chooseCode == i5) {
                    switch (str.charAt(i3)) {
                        case 241:
                            i7 = 102;
                            break;
                        case 242:
                            i7 = CODE_FNC_2;
                            break;
                        case 243:
                            i7 = CODE_FNC_3;
                            break;
                        case 244:
                            i7 = 101;
                            if (i5 != 101) {
                                i7 = 100;
                                break;
                            }
                            break;
                        default:
                            switch (i5) {
                                case 100:
                                    i7 = str.charAt(i3) - ' ';
                                    break;
                                case 101:
                                    i7 = str.charAt(i3) - ' ';
                                    if (i7 < 0) {
                                        i7 += CODE_FNC_3;
                                        break;
                                    }
                                    break;
                                default:
                                    i7 = Integer.parseInt(str.substring(i3, i3 + 2));
                                    i3++;
                                    break;
                            }
                    }
                    i3++;
                } else {
                    if (i5 == 0) {
                        switch (chooseCode) {
                            case 100:
                                i7 = 104;
                                break;
                            case 101:
                                break;
                            default:
                                i7 = CODE_START_C;
                                break;
                        }
                    } else {
                        i7 = chooseCode;
                    }
                    i5 = chooseCode;
                }
                arrayList.add(Code128Reader.CODE_PATTERNS[i7]);
                i4 += i7 * i6;
                if (i3 != 0) {
                    i6++;
                }
            } else {
                arrayList.add(Code128Reader.CODE_PATTERNS[i4 % CODE_START_A]);
                arrayList.add(Code128Reader.CODE_PATTERNS[CODE_STOP]);
                int i8 = 0;
                for (int[] iArr : arrayList) {
                    for (int i9 : iArr) {
                        i8 += i9;
                    }
                }
                boolean[] zArr = new boolean[i8];
                Iterator it = arrayList.iterator();
                while (it.hasNext()) {
                    i += appendPattern(zArr, i, (int[]) it.next(), true);
                }
                return zArr;
            }
        }
    }

    private static CType findCType(CharSequence value, int start) {
        int last = value.length();
        if (start >= last) {
            return CType.UNCODABLE;
        }
        char c = value.charAt(start);
        if (c != 241) {
            if (c < '0' || c > '9') {
                return CType.UNCODABLE;
            }
            if (start + 1 >= last) {
                return CType.ONE_DIGIT;
            }
            char c2 = value.charAt(start + 1);
            if (c2 < '0' || c2 > '9') {
                return CType.ONE_DIGIT;
            }
            return CType.TWO_DIGITS;
        }
        return CType.FNC_1;
    }

    private static int chooseCode(CharSequence value, int start, int oldCode) {
        CType lookahead;
        CType lookahead2;
        char c;
        CType findCType = findCType(value, start);
        CType lookahead3 = findCType;
        if (findCType == CType.ONE_DIGIT) {
            return oldCode == 101 ? 101 : 100;
        }
        if (lookahead3 == CType.UNCODABLE) {
            return (start >= value.length() || ((c = value.charAt(start)) >= ' ' && (oldCode != 101 || (c >= CODE_FNC_3 && (c < 241 || c > 244))))) ? 100 : 101;
        }
        if (oldCode == 101 && lookahead3 == CType.FNC_1) {
            return 101;
        }
        if (oldCode == CODE_CODE_C) {
            return CODE_CODE_C;
        }
        if (oldCode == 100) {
            if (lookahead3 == CType.FNC_1 || (lookahead = findCType(value, start + 2)) == CType.UNCODABLE || lookahead == CType.ONE_DIGIT) {
                return 100;
            }
            if (lookahead == CType.FNC_1) {
                if (findCType(value, start + 3) == CType.TWO_DIGITS) {
                    return CODE_CODE_C;
                }
                return 100;
            }
            int index = start + 4;
            while (true) {
                lookahead2 = findCType(value, index);
                if (lookahead2 != CType.TWO_DIGITS) {
                    break;
                }
                index += 2;
            }
            if (lookahead2 == CType.ONE_DIGIT) {
                return 100;
            }
            return CODE_CODE_C;
        }
        if (lookahead3 == CType.FNC_1) {
            lookahead3 = findCType(value, start + 1);
        }
        if (lookahead3 == CType.TWO_DIGITS) {
            return CODE_CODE_C;
        }
        return 100;
    }
}
