package androidx.compose.ui.platform;

import android.os.Parcel;
import android.util.Base64;
import androidx.compose.ui.geometry.OffsetKt;
import androidx.compose.ui.graphics.Color;
import androidx.compose.ui.graphics.Shadow;
import androidx.compose.ui.text.SpanStyle;
import androidx.compose.ui.text.font.FontStyle;
import androidx.compose.ui.text.font.FontSynthesis;
import androidx.compose.ui.text.font.FontWeight;
import androidx.compose.ui.text.style.BaselineShift;
import androidx.compose.ui.text.style.TextDecoration;
import androidx.compose.ui.text.style.TextGeometricTransform;
import androidx.compose.ui.unit.TextUnit;
import androidx.compose.ui.unit.TextUnitKt;
import androidx.compose.ui.unit.TextUnitType;
import kotlin.Metadata;
import kotlin.ULong;
import kotlin.collections.CollectionsKt;

/* compiled from: AndroidClipboardManager.android.kt */
@Metadata(d1 = {"\u0000|\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0000\n\u0002\u0010\u000e\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010\b\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0010\u0005\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0010\u0007\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\b\u0002\b\u0000\u0018\u00002\u00020\u0001B\r\u0012\u0006\u0010\u0002\u001a\u00020\u0003¢\u0006\u0002\u0010\u0004J\b\u0010\u0007\u001a\u00020\bH\u0002J\u0015\u0010\t\u001a\u00020\nH\u0002ø\u0001\u0000ø\u0001\u0001¢\u0006\u0004\b\u000b\u0010\fJ\b\u0010\r\u001a\u00020\u000eH\u0002J\u0013\u0010\u000f\u001a\u00020\u0010ø\u0001\u0000ø\u0001\u0001¢\u0006\u0004\b\u0011\u0010\u0012J\b\u0010\u0013\u001a\u00020\u0014H\u0002J\u0013\u0010\u0015\u001a\u00020\u0016ø\u0001\u0000ø\u0001\u0001¢\u0006\u0004\b\u0017\u0010\u0018J\u0013\u0010\u0019\u001a\u00020\u001aø\u0001\u0000ø\u0001\u0001¢\u0006\u0004\b\u001b\u0010\u0018J\u0006\u0010\u001c\u001a\u00020\u001dJ\b\u0010\u001e\u001a\u00020\bH\u0002J\b\u0010\u001f\u001a\u00020 H\u0002J\u0006\u0010!\u001a\u00020\"J\n\u0010#\u001a\u0004\u0018\u00010\u0003H\u0002J\b\u0010$\u001a\u00020%H\u0002J\b\u0010&\u001a\u00020'H\u0002J\u0013\u0010(\u001a\u00020)ø\u0001\u0000ø\u0001\u0001¢\u0006\u0004\b*\u0010\u0012J\u0015\u0010+\u001a\u00020,H\u0002ø\u0001\u0000ø\u0001\u0001¢\u0006\u0004\b-\u0010\u0012R\u000e\u0010\u0005\u001a\u00020\u0006X\u0082\u0004¢\u0006\u0002\n\u0000\u0082\u0002\u000b\n\u0002\b!\n\u0005\b¡\u001e0\u0001¨\u0006."}, d2 = {"Landroidx/compose/ui/platform/DecodeHelper;", "", "string", "", "(Ljava/lang/String;)V", "parcel", "Landroid/os/Parcel;", "dataAvailable", "", "decodeBaselineShift", "Landroidx/compose/ui/text/style/BaselineShift;", "decodeBaselineShift-y9eOQZs", "()F", "decodeByte", "", "decodeColor", "Landroidx/compose/ui/graphics/Color;", "decodeColor-0d7_KjU", "()J", "decodeFloat", "", "decodeFontStyle", "Landroidx/compose/ui/text/font/FontStyle;", "decodeFontStyle-_-LCdwA", "()I", "decodeFontSynthesis", "Landroidx/compose/ui/text/font/FontSynthesis;", "decodeFontSynthesis-GVVA2EU", "decodeFontWeight", "Landroidx/compose/ui/text/font/FontWeight;", "decodeInt", "decodeShadow", "Landroidx/compose/ui/graphics/Shadow;", "decodeSpanStyle", "Landroidx/compose/ui/text/SpanStyle;", "decodeString", "decodeTextDecoration", "Landroidx/compose/ui/text/style/TextDecoration;", "decodeTextGeometricTransform", "Landroidx/compose/ui/text/style/TextGeometricTransform;", "decodeTextUnit", "Landroidx/compose/ui/unit/TextUnit;", "decodeTextUnit-XSAIIZE", "decodeULong", "Lkotlin/ULong;", "decodeULong-s-VKNKU", "ui_release"}, k = 1, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes11.dex */
public final class DecodeHelper {
    public static final int $stable = 8;
    private final Parcel parcel = Parcel.obtain();

    public DecodeHelper(String string) {
        byte[] bytes = Base64.decode(string, 0);
        this.parcel.unmarshall(bytes, 0, bytes.length);
        this.parcel.setDataPosition(0);
    }

    public final SpanStyle decodeSpanStyle() {
        MutableSpanStyle mutableSpanStyle = new MutableSpanStyle(0L, 0L, null, null, null, null, null, 0L, null, null, null, 0L, null, null, 16383, null);
        while (this.parcel.dataAvail() > 1) {
            byte decodeByte = decodeByte();
            if (decodeByte == 1) {
                if (dataAvailable() < 8) {
                    break;
                }
                mutableSpanStyle.m5359setColor8_81llA(m5329decodeColor0d7_KjU());
            } else if (decodeByte == 2) {
                if (dataAvailable() < 5) {
                    break;
                }
                mutableSpanStyle.m5360setFontSizeR2X_6o(m5332decodeTextUnitXSAIIZE());
            } else if (decodeByte == 3) {
                if (dataAvailable() < 4) {
                    break;
                }
                mutableSpanStyle.setFontWeight(decodeFontWeight());
            } else if (decodeByte == 4) {
                if (dataAvailable() < 1) {
                    break;
                }
                mutableSpanStyle.m5361setFontStylemLjRB2g(FontStyle.m5677boximpl(m5330decodeFontStyle_LCdwA()));
            } else if (decodeByte == 5) {
                if (dataAvailable() < 1) {
                    break;
                }
                mutableSpanStyle.m5362setFontSynthesistDdu0R4(FontSynthesis.m5688boximpl(m5331decodeFontSynthesisGVVA2EU()));
            } else if (decodeByte == 6) {
                mutableSpanStyle.setFontFeatureSettings(decodeString());
            } else if (decodeByte == 7) {
                if (dataAvailable() < 5) {
                    break;
                }
                mutableSpanStyle.m5363setLetterSpacingR2X_6o(m5332decodeTextUnitXSAIIZE());
            } else if (decodeByte == 8) {
                if (dataAvailable() < 4) {
                    break;
                }
                mutableSpanStyle.m5358setBaselineShift_isdbwI(BaselineShift.m5848boximpl(m5327decodeBaselineShifty9eOQZs()));
            } else if (decodeByte == 9) {
                if (dataAvailable() < 8) {
                    break;
                }
                mutableSpanStyle.setTextGeometricTransform(decodeTextGeometricTransform());
            } else if (decodeByte == 10) {
                if (dataAvailable() < 8) {
                    break;
                }
                mutableSpanStyle.m5357setBackground8_81llA(m5329decodeColor0d7_KjU());
            } else if (decodeByte == 11) {
                if (dataAvailable() < 4) {
                    break;
                }
                mutableSpanStyle.setTextDecoration(decodeTextDecoration());
            } else if (decodeByte == 12) {
                if (dataAvailable() < 20) {
                    break;
                }
                mutableSpanStyle.setShadow(decodeShadow());
            } else {
                continue;
            }
        }
        return mutableSpanStyle.toSpanStyle();
    }

    /* renamed from: decodeColor-0d7_KjU, reason: not valid java name */
    public final long m5329decodeColor0d7_KjU() {
        return Color.m3742constructorimpl(m5328decodeULongsVKNKU());
    }

    /* renamed from: decodeTextUnit-XSAIIZE, reason: not valid java name */
    public final long m5332decodeTextUnitXSAIIZE() {
        long type;
        byte decodeByte = decodeByte();
        if (decodeByte == 1) {
            type = TextUnitType.INSTANCE.m6318getSpUIouoOA();
        } else {
            type = decodeByte == 2 ? TextUnitType.INSTANCE.m6317getEmUIouoOA() : TextUnitType.INSTANCE.m6319getUnspecifiedUIouoOA();
        }
        if (TextUnitType.m6313equalsimpl0(type, TextUnitType.INSTANCE.m6319getUnspecifiedUIouoOA())) {
            return TextUnit.INSTANCE.m6296getUnspecifiedXSAIIZE();
        }
        float value = decodeFloat();
        return TextUnitKt.m6297TextUnitanM5pPY(value, type);
    }

    public final FontWeight decodeFontWeight() {
        return new FontWeight(decodeInt());
    }

    /* renamed from: decodeFontStyle-_-LCdwA, reason: not valid java name */
    public final int m5330decodeFontStyle_LCdwA() {
        byte decodeByte = decodeByte();
        return decodeByte == 0 ? FontStyle.INSTANCE.m5687getNormal_LCdwA() : decodeByte == 1 ? FontStyle.INSTANCE.m5686getItalic_LCdwA() : FontStyle.INSTANCE.m5687getNormal_LCdwA();
    }

    /* renamed from: decodeFontSynthesis-GVVA2EU, reason: not valid java name */
    public final int m5331decodeFontSynthesisGVVA2EU() {
        byte decodeByte = decodeByte();
        return decodeByte == 0 ? FontSynthesis.INSTANCE.m5698getNoneGVVA2EU() : decodeByte == 1 ? FontSynthesis.INSTANCE.m5697getAllGVVA2EU() : decodeByte == 3 ? FontSynthesis.INSTANCE.m5699getStyleGVVA2EU() : decodeByte == 2 ? FontSynthesis.INSTANCE.m5700getWeightGVVA2EU() : FontSynthesis.INSTANCE.m5698getNoneGVVA2EU();
    }

    /* renamed from: decodeBaselineShift-y9eOQZs, reason: not valid java name */
    private final float m5327decodeBaselineShifty9eOQZs() {
        return BaselineShift.m5849constructorimpl(decodeFloat());
    }

    private final TextGeometricTransform decodeTextGeometricTransform() {
        return new TextGeometricTransform(decodeFloat(), decodeFloat());
    }

    private final TextDecoration decodeTextDecoration() {
        int mask = decodeInt();
        boolean hasLineThrough = (TextDecoration.INSTANCE.getLineThrough().getMask() & mask) != 0;
        boolean hasUnderline = (TextDecoration.INSTANCE.getUnderline().getMask() & mask) != 0;
        if (hasLineThrough && hasUnderline) {
            return TextDecoration.INSTANCE.combine(CollectionsKt.listOf((Object[]) new TextDecoration[]{TextDecoration.INSTANCE.getLineThrough(), TextDecoration.INSTANCE.getUnderline()}));
        }
        if (hasLineThrough) {
            return TextDecoration.INSTANCE.getLineThrough();
        }
        if (hasUnderline) {
            return TextDecoration.INSTANCE.getUnderline();
        }
        return TextDecoration.INSTANCE.getNone();
    }

    private final Shadow decodeShadow() {
        return new Shadow(m5329decodeColor0d7_KjU(), OffsetKt.Offset(decodeFloat(), decodeFloat()), decodeFloat(), null);
    }

    private final byte decodeByte() {
        return this.parcel.readByte();
    }

    private final int decodeInt() {
        return this.parcel.readInt();
    }

    /* renamed from: decodeULong-s-VKNKU, reason: not valid java name */
    private final long m5328decodeULongsVKNKU() {
        return ULong.m6652constructorimpl(this.parcel.readLong());
    }

    private final float decodeFloat() {
        return this.parcel.readFloat();
    }

    private final String decodeString() {
        return this.parcel.readString();
    }

    private final int dataAvailable() {
        return this.parcel.dataAvail();
    }
}
