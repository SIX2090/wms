package com.google.zxing.client.result;

import androidx.core.net.MailTo;
import com.google.zxing.Result;
import java.util.Map;
import java.util.regex.Pattern;

/* loaded from: classes11.dex */
public final class EmailAddressResultParser extends ResultParser {
    private static final Pattern COMMA = Pattern.compile(",");

    @Override // com.google.zxing.client.result.ResultParser
    public EmailAddressParsedResult parse(Result result) {
        String[] strArr;
        String[] strArr2;
        String[] strArr3;
        String[] strArr4;
        String str;
        String str2;
        String[] strArr5;
        String str3;
        String massagedText = getMassagedText(result);
        if (massagedText.startsWith(MailTo.MAILTO_SCHEME) || massagedText.startsWith("MAILTO:")) {
            String substring = massagedText.substring(7);
            int indexOf = substring.indexOf(63);
            if (indexOf >= 0) {
                substring = substring.substring(0, indexOf);
            }
            try {
                String urlDecode = urlDecode(substring);
                if (urlDecode.isEmpty()) {
                    strArr = null;
                } else {
                    strArr = COMMA.split(urlDecode);
                }
                Map<String, String> parseNameValuePairs = parseNameValuePairs(massagedText);
                if (parseNameValuePairs == null) {
                    strArr2 = strArr;
                    strArr3 = null;
                    strArr4 = null;
                    str = null;
                    str2 = null;
                } else {
                    if (strArr == null && (str3 = parseNameValuePairs.get("to")) != null) {
                        strArr = COMMA.split(str3);
                    }
                    String str4 = parseNameValuePairs.get("cc");
                    if (str4 == null) {
                        strArr5 = null;
                    } else {
                        strArr5 = COMMA.split(str4);
                    }
                    String str5 = parseNameValuePairs.get("bcc");
                    String[] split = str5 != null ? COMMA.split(str5) : null;
                    String str6 = parseNameValuePairs.get("subject");
                    str2 = parseNameValuePairs.get("body");
                    strArr2 = strArr;
                    strArr4 = split;
                    strArr3 = strArr5;
                    str = str6;
                }
                return new EmailAddressParsedResult(strArr2, strArr3, strArr4, str, str2);
            } catch (IllegalArgumentException e) {
                return null;
            }
        }
        if (EmailDoCoMoResultParser.isBasicallyValidEmailAddress(massagedText)) {
            return new EmailAddressParsedResult(massagedText);
        }
        return null;
    }
}
