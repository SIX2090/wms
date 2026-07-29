package com.google.gson;

import java.util.Objects;

/* loaded from: classes11.dex */
public class FormattingStyle {
    public static final FormattingStyle COMPACT = new FormattingStyle("", "", false);
    public static final FormattingStyle PRETTY = new FormattingStyle("\n", "  ", true);
    private final String indent;
    private final String newline;
    private final boolean spaceAfterSeparators;

    private FormattingStyle(String newline, String indent, boolean spaceAfterSeparators) {
        Objects.requireNonNull(newline, "newline == null");
        Objects.requireNonNull(indent, "indent == null");
        if (!newline.matches("[\r\n]*")) {
            throw new IllegalArgumentException("Only combinations of \\n and \\r are allowed in newline.");
        }
        if (!indent.matches("[ \t]*")) {
            throw new IllegalArgumentException("Only combinations of spaces and tabs are allowed in indent.");
        }
        this.newline = newline;
        this.indent = indent;
        this.spaceAfterSeparators = spaceAfterSeparators;
    }

    public FormattingStyle withNewline(String newline) {
        return new FormattingStyle(newline, this.indent, this.spaceAfterSeparators);
    }

    public FormattingStyle withIndent(String indent) {
        return new FormattingStyle(this.newline, indent, this.spaceAfterSeparators);
    }

    public FormattingStyle withSpaceAfterSeparators(boolean spaceAfterSeparators) {
        return new FormattingStyle(this.newline, this.indent, spaceAfterSeparators);
    }

    public String getNewline() {
        return this.newline;
    }

    public String getIndent() {
        return this.indent;
    }

    public boolean usesSpaceAfterSeparators() {
        return this.spaceAfterSeparators;
    }
}
