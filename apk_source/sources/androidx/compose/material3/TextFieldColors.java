package androidx.compose.material3;

import androidx.compose.animation.SingleValueAnimationKt;
import androidx.compose.animation.core.AnimationSpecKt;
import androidx.compose.foundation.interaction.FocusInteractionKt;
import androidx.compose.foundation.interaction.InteractionSource;
import androidx.compose.foundation.text.selection.SelectionColors;
import androidx.compose.runtime.Composer;
import androidx.compose.runtime.ComposerKt;
import androidx.compose.runtime.SnapshotStateKt;
import androidx.compose.runtime.State;
import androidx.compose.ui.graphics.Color;
import kotlin.Metadata;
import kotlin.jvm.functions.Function0;
import kotlin.jvm.internal.DefaultConstructorMarker;
import kotlin.jvm.internal.Intrinsics;

/* compiled from: TextFieldDefaults.kt */
@Metadata(d1 = {"\u0000@\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0000\n\u0002\u0018\u0002\n\u0002\b\n\n\u0002\u0018\u0002\n\u0002\bS\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010\u000b\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\b\n\n\u0002\u0010\b\n\u0002\b\u0014\n\u0002\u0018\u0002\n\u0002\b\u0003\b\u0007\u0018\u00002\u00020\u0001BÝ\u0002\u0012\u0006\u0010\u0002\u001a\u00020\u0003\u0012\u0006\u0010\u0004\u001a\u00020\u0003\u0012\u0006\u0010\u0005\u001a\u00020\u0003\u0012\u0006\u0010\u0006\u001a\u00020\u0003\u0012\u0006\u0010\u0007\u001a\u00020\u0003\u0012\u0006\u0010\b\u001a\u00020\u0003\u0012\u0006\u0010\t\u001a\u00020\u0003\u0012\u0006\u0010\n\u001a\u00020\u0003\u0012\u0006\u0010\u000b\u001a\u00020\u0003\u0012\u0006\u0010\f\u001a\u00020\u0003\u0012\u0006\u0010\r\u001a\u00020\u000e\u0012\u0006\u0010\u000f\u001a\u00020\u0003\u0012\u0006\u0010\u0010\u001a\u00020\u0003\u0012\u0006\u0010\u0011\u001a\u00020\u0003\u0012\u0006\u0010\u0012\u001a\u00020\u0003\u0012\u0006\u0010\u0013\u001a\u00020\u0003\u0012\u0006\u0010\u0014\u001a\u00020\u0003\u0012\u0006\u0010\u0015\u001a\u00020\u0003\u0012\u0006\u0010\u0016\u001a\u00020\u0003\u0012\u0006\u0010\u0017\u001a\u00020\u0003\u0012\u0006\u0010\u0018\u001a\u00020\u0003\u0012\u0006\u0010\u0019\u001a\u00020\u0003\u0012\u0006\u0010\u001a\u001a\u00020\u0003\u0012\u0006\u0010\u001b\u001a\u00020\u0003\u0012\u0006\u0010\u001c\u001a\u00020\u0003\u0012\u0006\u0010\u001d\u001a\u00020\u0003\u0012\u0006\u0010\u001e\u001a\u00020\u0003\u0012\u0006\u0010\u001f\u001a\u00020\u0003\u0012\u0006\u0010 \u001a\u00020\u0003\u0012\u0006\u0010!\u001a\u00020\u0003\u0012\u0006\u0010\"\u001a\u00020\u0003\u0012\u0006\u0010#\u001a\u00020\u0003\u0012\u0006\u0010$\u001a\u00020\u0003\u0012\u0006\u0010%\u001a\u00020\u0003\u0012\u0006\u0010&\u001a\u00020\u0003\u0012\u0006\u0010'\u001a\u00020\u0003\u0012\u0006\u0010(\u001a\u00020\u0003\u0012\u0006\u0010)\u001a\u00020\u0003\u0012\u0006\u0010*\u001a\u00020\u0003\u0012\u0006\u0010+\u001a\u00020\u0003\u0012\u0006\u0010,\u001a\u00020\u0003\u0012\u0006\u0010-\u001a\u00020\u0003\u0012\u0006\u0010.\u001a\u00020\u0003¢\u0006\u0002\u0010/J-\u0010a\u001a\b\u0012\u0004\u0012\u00020\u00030b2\u0006\u0010c\u001a\u00020d2\u0006\u0010e\u001a\u00020d2\u0006\u0010f\u001a\u00020gH\u0001¢\u0006\u0004\bh\u0010iJÀ\u0003\u0010j\u001a\u00020\u00002\b\b\u0002\u0010\u0002\u001a\u00020\u00032\b\b\u0002\u0010\u0004\u001a\u00020\u00032\b\b\u0002\u0010\u0005\u001a\u00020\u00032\b\b\u0002\u0010\u0006\u001a\u00020\u00032\b\b\u0002\u0010\u0007\u001a\u00020\u00032\b\b\u0002\u0010\b\u001a\u00020\u00032\b\b\u0002\u0010\t\u001a\u00020\u00032\b\b\u0002\u0010\n\u001a\u00020\u00032\b\b\u0002\u0010\u000b\u001a\u00020\u00032\b\b\u0002\u0010\f\u001a\u00020\u00032\n\b\u0002\u0010\r\u001a\u0004\u0018\u00010\u000e2\b\b\u0002\u0010\u000f\u001a\u00020\u00032\b\b\u0002\u0010\u0010\u001a\u00020\u00032\b\b\u0002\u0010\u0011\u001a\u00020\u00032\b\b\u0002\u0010\u0012\u001a\u00020\u00032\b\b\u0002\u0010\u0013\u001a\u00020\u00032\b\b\u0002\u0010\u0014\u001a\u00020\u00032\b\b\u0002\u0010\u0015\u001a\u00020\u00032\b\b\u0002\u0010\u0016\u001a\u00020\u00032\b\b\u0002\u0010\u0017\u001a\u00020\u00032\b\b\u0002\u0010\u0018\u001a\u00020\u00032\b\b\u0002\u0010\u0019\u001a\u00020\u00032\b\b\u0002\u0010\u001a\u001a\u00020\u00032\b\b\u0002\u0010\u001b\u001a\u00020\u00032\b\b\u0002\u0010\u001c\u001a\u00020\u00032\b\b\u0002\u0010\u001d\u001a\u00020\u00032\b\b\u0002\u0010\u001e\u001a\u00020\u00032\b\b\u0002\u0010\u001f\u001a\u00020\u00032\b\b\u0002\u0010 \u001a\u00020\u00032\b\b\u0002\u0010!\u001a\u00020\u00032\b\b\u0002\u0010\"\u001a\u00020\u00032\b\b\u0002\u0010#\u001a\u00020\u00032\b\b\u0002\u0010$\u001a\u00020\u00032\b\b\u0002\u0010%\u001a\u00020\u00032\b\b\u0002\u0010&\u001a\u00020\u00032\b\b\u0002\u0010'\u001a\u00020\u00032\b\b\u0002\u0010(\u001a\u00020\u00032\b\b\u0002\u0010)\u001a\u00020\u00032\b\b\u0002\u0010*\u001a\u00020\u00032\b\b\u0002\u0010+\u001a\u00020\u00032\b\b\u0002\u0010,\u001a\u00020\u00032\b\b\u0002\u0010-\u001a\u00020\u00032\b\b\u0002\u0010.\u001a\u00020\u0003ø\u0001\u0000¢\u0006\u0004\bk\u0010lJ\u001d\u0010\u000b\u001a\b\u0012\u0004\u0012\u00020\u00030b2\u0006\u0010e\u001a\u00020dH\u0001¢\u0006\u0004\bm\u0010nJ\u0013\u0010o\u001a\u00020d2\b\u0010p\u001a\u0004\u0018\u00010\u0001H\u0096\u0002J\b\u0010q\u001a\u00020rH\u0016J-\u0010s\u001a\b\u0012\u0004\u0012\u00020\u00030b2\u0006\u0010c\u001a\u00020d2\u0006\u0010e\u001a\u00020d2\u0006\u0010f\u001a\u00020gH\u0001¢\u0006\u0004\bt\u0010iJ-\u0010u\u001a\b\u0012\u0004\u0012\u00020\u00030b2\u0006\u0010c\u001a\u00020d2\u0006\u0010e\u001a\u00020d2\u0006\u0010f\u001a\u00020gH\u0001¢\u0006\u0004\bv\u0010iJ-\u0010w\u001a\b\u0012\u0004\u0012\u00020\u00030b2\u0006\u0010c\u001a\u00020d2\u0006\u0010e\u001a\u00020d2\u0006\u0010f\u001a\u00020gH\u0001¢\u0006\u0004\bx\u0010iJ-\u0010y\u001a\b\u0012\u0004\u0012\u00020\u00030b2\u0006\u0010c\u001a\u00020d2\u0006\u0010e\u001a\u00020d2\u0006\u0010f\u001a\u00020gH\u0001¢\u0006\u0004\bz\u0010iJ-\u0010{\u001a\b\u0012\u0004\u0012\u00020\u00030b2\u0006\u0010c\u001a\u00020d2\u0006\u0010e\u001a\u00020d2\u0006\u0010f\u001a\u00020gH\u0001¢\u0006\u0004\b|\u0010iJ-\u0010}\u001a\b\u0012\u0004\u0012\u00020\u00030b2\u0006\u0010c\u001a\u00020d2\u0006\u0010e\u001a\u00020d2\u0006\u0010f\u001a\u00020gH\u0001¢\u0006\u0004\b~\u0010iJ.\u0010\u007f\u001a\b\u0012\u0004\u0012\u00020\u00030b2\u0006\u0010c\u001a\u00020d2\u0006\u0010e\u001a\u00020d2\u0006\u0010f\u001a\u00020gH\u0001¢\u0006\u0005\b\u0080\u0001\u0010iJ/\u0010\u0081\u0001\u001a\b\u0012\u0004\u0012\u00020\u00030b2\u0006\u0010c\u001a\u00020d2\u0006\u0010e\u001a\u00020d2\u0006\u0010f\u001a\u00020gH\u0001¢\u0006\u0005\b\u0082\u0001\u0010iJ/\u0010\u0083\u0001\u001a\b\u0012\u0004\u0012\u00020\u00030b2\u0006\u0010c\u001a\u00020d2\u0006\u0010e\u001a\u00020d2\u0006\u0010f\u001a\u00020gH\u0001¢\u0006\u0005\b\u0084\u0001\u0010iJ%\u0010\u0085\u0001\u001a\u00020\u000e*\u0004\u0018\u00010\u000e2\u000e\u0010\u0086\u0001\u001a\t\u0012\u0004\u0012\u00020\u000e0\u0087\u0001H\u0000¢\u0006\u0003\b\u0088\u0001R\u0019\u0010\u000b\u001a\u00020\u0003ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u00102\u001a\u0004\b0\u00101R\u0019\u0010\t\u001a\u00020\u0003ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u00102\u001a\u0004\b3\u00101R\u0019\u0010\u0011\u001a\u00020\u0003ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u00102\u001a\u0004\b4\u00101R\u0019\u0010\u001d\u001a\u00020\u0003ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u00102\u001a\u0004\b5\u00101R\u0019\u0010\u0015\u001a\u00020\u0003ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u00102\u001a\u0004\b6\u00101R\u0019\u0010!\u001a\u00020\u0003ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u00102\u001a\u0004\b7\u00101R\u0019\u0010)\u001a\u00020\u0003ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u00102\u001a\u0004\b8\u00101R\u0019\u0010-\u001a\u00020\u0003ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u00102\u001a\u0004\b9\u00101R\u0019\u0010%\u001a\u00020\u0003ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u00102\u001a\u0004\b:\u00101R\u0019\u0010\u0005\u001a\u00020\u0003ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u00102\u001a\u0004\b;\u00101R\u0019\u0010\u0019\u001a\u00020\u0003ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u00102\u001a\u0004\b<\u00101R\u0019\u0010\n\u001a\u00020\u0003ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u00102\u001a\u0004\b=\u00101R\u0019\u0010\f\u001a\u00020\u0003ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u00102\u001a\u0004\b>\u00101R\u0019\u0010\u0012\u001a\u00020\u0003ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u00102\u001a\u0004\b?\u00101R\u0019\u0010\u001e\u001a\u00020\u0003ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u00102\u001a\u0004\b@\u00101R\u0019\u0010\u0016\u001a\u00020\u0003ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u00102\u001a\u0004\bA\u00101R\u0019\u0010\"\u001a\u00020\u0003ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u00102\u001a\u0004\bB\u00101R\u0019\u0010*\u001a\u00020\u0003ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u00102\u001a\u0004\bC\u00101R\u0019\u0010.\u001a\u00020\u0003ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u00102\u001a\u0004\bD\u00101R\u0019\u0010&\u001a\u00020\u0003ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u00102\u001a\u0004\bE\u00101R\u0019\u0010\u0006\u001a\u00020\u0003ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u00102\u001a\u0004\bF\u00101R\u0019\u0010\u001a\u001a\u00020\u0003ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u00102\u001a\u0004\bG\u00101R\u0019\u0010\u0007\u001a\u00020\u0003ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u00102\u001a\u0004\bH\u00101R\u0019\u0010\u000f\u001a\u00020\u0003ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u00102\u001a\u0004\bI\u00101R\u0019\u0010\u001b\u001a\u00020\u0003ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u00102\u001a\u0004\bJ\u00101R\u0019\u0010\u0013\u001a\u00020\u0003ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u00102\u001a\u0004\bK\u00101R\u0019\u0010\u001f\u001a\u00020\u0003ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u00102\u001a\u0004\bL\u00101R\u0019\u0010'\u001a\u00020\u0003ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u00102\u001a\u0004\bM\u00101R\u0019\u0010+\u001a\u00020\u0003ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u00102\u001a\u0004\bN\u00101R\u0019\u0010#\u001a\u00020\u0003ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u00102\u001a\u0004\bO\u00101R\u0019\u0010\u0002\u001a\u00020\u0003ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u00102\u001a\u0004\bP\u00101R\u0019\u0010\u0017\u001a\u00020\u0003ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u00102\u001a\u0004\bQ\u00101R\u0014\u0010R\u001a\u00020\u000e8AX\u0080\u0004¢\u0006\u0006\u001a\u0004\bS\u0010TR\u0011\u0010\r\u001a\u00020\u000e¢\u0006\b\n\u0000\u001a\u0004\bU\u0010VR\u0019\u0010\b\u001a\u00020\u0003ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u00102\u001a\u0004\bW\u00101R\u0019\u0010\u0010\u001a\u00020\u0003ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u00102\u001a\u0004\bX\u00101R\u0019\u0010\u001c\u001a\u00020\u0003ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u00102\u001a\u0004\bY\u00101R\u0019\u0010\u0014\u001a\u00020\u0003ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u00102\u001a\u0004\bZ\u00101R\u0019\u0010 \u001a\u00020\u0003ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u00102\u001a\u0004\b[\u00101R\u0019\u0010(\u001a\u00020\u0003ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u00102\u001a\u0004\b\\\u00101R\u0019\u0010,\u001a\u00020\u0003ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u00102\u001a\u0004\b]\u00101R\u0019\u0010$\u001a\u00020\u0003ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u00102\u001a\u0004\b^\u00101R\u0019\u0010\u0004\u001a\u00020\u0003ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u00102\u001a\u0004\b_\u00101R\u0019\u0010\u0018\u001a\u00020\u0003ø\u0001\u0000ø\u0001\u0001¢\u0006\n\n\u0002\u00102\u001a\u0004\b`\u00101\u0082\u0002\u000b\n\u0005\b¡\u001e0\u0001\n\u0002\b!¨\u0006\u0089\u0001²\u0006\u000b\u0010\u008a\u0001\u001a\u00020dX\u008a\u0084\u0002²\u0006\u000b\u0010\u008a\u0001\u001a\u00020dX\u008a\u0084\u0002²\u0006\u000b\u0010\u008a\u0001\u001a\u00020dX\u008a\u0084\u0002²\u0006\u000b\u0010\u008a\u0001\u001a\u00020dX\u008a\u0084\u0002²\u0006\u000b\u0010\u008a\u0001\u001a\u00020dX\u008a\u0084\u0002²\u0006\u000b\u0010\u008a\u0001\u001a\u00020dX\u008a\u0084\u0002²\u0006\u000b\u0010\u008a\u0001\u001a\u00020dX\u008a\u0084\u0002²\u0006\u000b\u0010\u008a\u0001\u001a\u00020dX\u008a\u0084\u0002²\u0006\u000b\u0010\u008a\u0001\u001a\u00020dX\u008a\u0084\u0002²\u0006\u000b\u0010\u008a\u0001\u001a\u00020dX\u008a\u0084\u0002"}, d2 = {"Landroidx/compose/material3/TextFieldColors;", "", "focusedTextColor", "Landroidx/compose/ui/graphics/Color;", "unfocusedTextColor", "disabledTextColor", "errorTextColor", "focusedContainerColor", "unfocusedContainerColor", "disabledContainerColor", "errorContainerColor", "cursorColor", "errorCursorColor", "textSelectionColors", "Landroidx/compose/foundation/text/selection/TextSelectionColors;", "focusedIndicatorColor", "unfocusedIndicatorColor", "disabledIndicatorColor", "errorIndicatorColor", "focusedLeadingIconColor", "unfocusedLeadingIconColor", "disabledLeadingIconColor", "errorLeadingIconColor", "focusedTrailingIconColor", "unfocusedTrailingIconColor", "disabledTrailingIconColor", "errorTrailingIconColor", "focusedLabelColor", "unfocusedLabelColor", "disabledLabelColor", "errorLabelColor", "focusedPlaceholderColor", "unfocusedPlaceholderColor", "disabledPlaceholderColor", "errorPlaceholderColor", "focusedSupportingTextColor", "unfocusedSupportingTextColor", "disabledSupportingTextColor", "errorSupportingTextColor", "focusedPrefixColor", "unfocusedPrefixColor", "disabledPrefixColor", "errorPrefixColor", "focusedSuffixColor", "unfocusedSuffixColor", "disabledSuffixColor", "errorSuffixColor", "(JJJJJJJJJJLandroidx/compose/foundation/text/selection/TextSelectionColors;JJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJLkotlin/jvm/internal/DefaultConstructorMarker;)V", "getCursorColor-0d7_KjU", "()J", "J", "getDisabledContainerColor-0d7_KjU", "getDisabledIndicatorColor-0d7_KjU", "getDisabledLabelColor-0d7_KjU", "getDisabledLeadingIconColor-0d7_KjU", "getDisabledPlaceholderColor-0d7_KjU", "getDisabledPrefixColor-0d7_KjU", "getDisabledSuffixColor-0d7_KjU", "getDisabledSupportingTextColor-0d7_KjU", "getDisabledTextColor-0d7_KjU", "getDisabledTrailingIconColor-0d7_KjU", "getErrorContainerColor-0d7_KjU", "getErrorCursorColor-0d7_KjU", "getErrorIndicatorColor-0d7_KjU", "getErrorLabelColor-0d7_KjU", "getErrorLeadingIconColor-0d7_KjU", "getErrorPlaceholderColor-0d7_KjU", "getErrorPrefixColor-0d7_KjU", "getErrorSuffixColor-0d7_KjU", "getErrorSupportingTextColor-0d7_KjU", "getErrorTextColor-0d7_KjU", "getErrorTrailingIconColor-0d7_KjU", "getFocusedContainerColor-0d7_KjU", "getFocusedIndicatorColor-0d7_KjU", "getFocusedLabelColor-0d7_KjU", "getFocusedLeadingIconColor-0d7_KjU", "getFocusedPlaceholderColor-0d7_KjU", "getFocusedPrefixColor-0d7_KjU", "getFocusedSuffixColor-0d7_KjU", "getFocusedSupportingTextColor-0d7_KjU", "getFocusedTextColor-0d7_KjU", "getFocusedTrailingIconColor-0d7_KjU", "selectionColors", "getSelectionColors", "(Landroidx/compose/runtime/Composer;I)Landroidx/compose/foundation/text/selection/TextSelectionColors;", "getTextSelectionColors", "()Landroidx/compose/foundation/text/selection/TextSelectionColors;", "getUnfocusedContainerColor-0d7_KjU", "getUnfocusedIndicatorColor-0d7_KjU", "getUnfocusedLabelColor-0d7_KjU", "getUnfocusedLeadingIconColor-0d7_KjU", "getUnfocusedPlaceholderColor-0d7_KjU", "getUnfocusedPrefixColor-0d7_KjU", "getUnfocusedSuffixColor-0d7_KjU", "getUnfocusedSupportingTextColor-0d7_KjU", "getUnfocusedTextColor-0d7_KjU", "getUnfocusedTrailingIconColor-0d7_KjU", "containerColor", "Landroidx/compose/runtime/State;", "enabled", "", "isError", "interactionSource", "Landroidx/compose/foundation/interaction/InteractionSource;", "containerColor$material3_release", "(ZZLandroidx/compose/foundation/interaction/InteractionSource;Landroidx/compose/runtime/Composer;I)Landroidx/compose/runtime/State;", "copy", "copy-ejIjP34", "(JJJJJJJJJJLandroidx/compose/foundation/text/selection/TextSelectionColors;JJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJJ)Landroidx/compose/material3/TextFieldColors;", "cursorColor$material3_release", "(ZLandroidx/compose/runtime/Composer;I)Landroidx/compose/runtime/State;", "equals", "other", "hashCode", "", "indicatorColor", "indicatorColor$material3_release", "labelColor", "labelColor$material3_release", "leadingIconColor", "leadingIconColor$material3_release", "placeholderColor", "placeholderColor$material3_release", "prefixColor", "prefixColor$material3_release", "suffixColor", "suffixColor$material3_release", "supportingTextColor", "supportingTextColor$material3_release", "textColor", "textColor$material3_release", "trailingIconColor", "trailingIconColor$material3_release", "takeOrElse", "block", "Lkotlin/Function0;", "takeOrElse$material3_release", "material3_release", "focused"}, k = 1, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class TextFieldColors {
    public static final int $stable = 0;
    private final long cursorColor;
    private final long disabledContainerColor;
    private final long disabledIndicatorColor;
    private final long disabledLabelColor;
    private final long disabledLeadingIconColor;
    private final long disabledPlaceholderColor;
    private final long disabledPrefixColor;
    private final long disabledSuffixColor;
    private final long disabledSupportingTextColor;
    private final long disabledTextColor;
    private final long disabledTrailingIconColor;
    private final long errorContainerColor;
    private final long errorCursorColor;
    private final long errorIndicatorColor;
    private final long errorLabelColor;
    private final long errorLeadingIconColor;
    private final long errorPlaceholderColor;
    private final long errorPrefixColor;
    private final long errorSuffixColor;
    private final long errorSupportingTextColor;
    private final long errorTextColor;
    private final long errorTrailingIconColor;
    private final long focusedContainerColor;
    private final long focusedIndicatorColor;
    private final long focusedLabelColor;
    private final long focusedLeadingIconColor;
    private final long focusedPlaceholderColor;
    private final long focusedPrefixColor;
    private final long focusedSuffixColor;
    private final long focusedSupportingTextColor;
    private final long focusedTextColor;
    private final long focusedTrailingIconColor;
    private final SelectionColors textSelectionColors;
    private final long unfocusedContainerColor;
    private final long unfocusedIndicatorColor;
    private final long unfocusedLabelColor;
    private final long unfocusedLeadingIconColor;
    private final long unfocusedPlaceholderColor;
    private final long unfocusedPrefixColor;
    private final long unfocusedSuffixColor;
    private final long unfocusedSupportingTextColor;
    private final long unfocusedTextColor;
    private final long unfocusedTrailingIconColor;

    public /* synthetic */ TextFieldColors(long j, long j2, long j3, long j4, long j5, long j6, long j7, long j8, long j9, long j10, SelectionColors selectionColors, long j11, long j12, long j13, long j14, long j15, long j16, long j17, long j18, long j19, long j20, long j21, long j22, long j23, long j24, long j25, long j26, long j27, long j28, long j29, long j30, long j31, long j32, long j33, long j34, long j35, long j36, long j37, long j38, long j39, long j40, long j41, long j42, DefaultConstructorMarker defaultConstructorMarker) {
        this(j, j2, j3, j4, j5, j6, j7, j8, j9, j10, selectionColors, j11, j12, j13, j14, j15, j16, j17, j18, j19, j20, j21, j22, j23, j24, j25, j26, j27, j28, j29, j30, j31, j32, j33, j34, j35, j36, j37, j38, j39, j40, j41, j42);
    }

    private TextFieldColors(long focusedTextColor, long unfocusedTextColor, long disabledTextColor, long errorTextColor, long focusedContainerColor, long unfocusedContainerColor, long disabledContainerColor, long errorContainerColor, long cursorColor, long errorCursorColor, SelectionColors textSelectionColors, long focusedIndicatorColor, long unfocusedIndicatorColor, long disabledIndicatorColor, long errorIndicatorColor, long focusedLeadingIconColor, long unfocusedLeadingIconColor, long disabledLeadingIconColor, long errorLeadingIconColor, long focusedTrailingIconColor, long unfocusedTrailingIconColor, long disabledTrailingIconColor, long errorTrailingIconColor, long focusedLabelColor, long unfocusedLabelColor, long disabledLabelColor, long errorLabelColor, long focusedPlaceholderColor, long unfocusedPlaceholderColor, long disabledPlaceholderColor, long errorPlaceholderColor, long focusedSupportingTextColor, long unfocusedSupportingTextColor, long disabledSupportingTextColor, long errorSupportingTextColor, long focusedPrefixColor, long unfocusedPrefixColor, long disabledPrefixColor, long errorPrefixColor, long focusedSuffixColor, long unfocusedSuffixColor, long disabledSuffixColor, long errorSuffixColor) {
        this.focusedTextColor = focusedTextColor;
        this.unfocusedTextColor = unfocusedTextColor;
        this.disabledTextColor = disabledTextColor;
        this.errorTextColor = errorTextColor;
        this.focusedContainerColor = focusedContainerColor;
        this.unfocusedContainerColor = unfocusedContainerColor;
        this.disabledContainerColor = disabledContainerColor;
        this.errorContainerColor = errorContainerColor;
        this.cursorColor = cursorColor;
        this.errorCursorColor = errorCursorColor;
        this.textSelectionColors = textSelectionColors;
        this.focusedIndicatorColor = focusedIndicatorColor;
        this.unfocusedIndicatorColor = unfocusedIndicatorColor;
        this.disabledIndicatorColor = disabledIndicatorColor;
        this.errorIndicatorColor = errorIndicatorColor;
        this.focusedLeadingIconColor = focusedLeadingIconColor;
        this.unfocusedLeadingIconColor = unfocusedLeadingIconColor;
        this.disabledLeadingIconColor = disabledLeadingIconColor;
        this.errorLeadingIconColor = errorLeadingIconColor;
        this.focusedTrailingIconColor = focusedTrailingIconColor;
        this.unfocusedTrailingIconColor = unfocusedTrailingIconColor;
        this.disabledTrailingIconColor = disabledTrailingIconColor;
        this.errorTrailingIconColor = errorTrailingIconColor;
        this.focusedLabelColor = focusedLabelColor;
        this.unfocusedLabelColor = unfocusedLabelColor;
        this.disabledLabelColor = disabledLabelColor;
        this.errorLabelColor = errorLabelColor;
        this.focusedPlaceholderColor = focusedPlaceholderColor;
        this.unfocusedPlaceholderColor = unfocusedPlaceholderColor;
        this.disabledPlaceholderColor = disabledPlaceholderColor;
        this.errorPlaceholderColor = errorPlaceholderColor;
        this.focusedSupportingTextColor = focusedSupportingTextColor;
        this.unfocusedSupportingTextColor = unfocusedSupportingTextColor;
        this.disabledSupportingTextColor = disabledSupportingTextColor;
        this.errorSupportingTextColor = errorSupportingTextColor;
        this.focusedPrefixColor = focusedPrefixColor;
        this.unfocusedPrefixColor = unfocusedPrefixColor;
        this.disabledPrefixColor = disabledPrefixColor;
        this.errorPrefixColor = errorPrefixColor;
        this.focusedSuffixColor = focusedSuffixColor;
        this.unfocusedSuffixColor = unfocusedSuffixColor;
        this.disabledSuffixColor = disabledSuffixColor;
        this.errorSuffixColor = errorSuffixColor;
    }

    /* renamed from: getFocusedTextColor-0d7_KjU, reason: not valid java name and from getter */
    public final long getFocusedTextColor() {
        return this.focusedTextColor;
    }

    /* renamed from: getUnfocusedTextColor-0d7_KjU, reason: not valid java name and from getter */
    public final long getUnfocusedTextColor() {
        return this.unfocusedTextColor;
    }

    /* renamed from: getDisabledTextColor-0d7_KjU, reason: not valid java name and from getter */
    public final long getDisabledTextColor() {
        return this.disabledTextColor;
    }

    /* renamed from: getErrorTextColor-0d7_KjU, reason: not valid java name and from getter */
    public final long getErrorTextColor() {
        return this.errorTextColor;
    }

    /* renamed from: getFocusedContainerColor-0d7_KjU, reason: not valid java name and from getter */
    public final long getFocusedContainerColor() {
        return this.focusedContainerColor;
    }

    /* renamed from: getUnfocusedContainerColor-0d7_KjU, reason: not valid java name and from getter */
    public final long getUnfocusedContainerColor() {
        return this.unfocusedContainerColor;
    }

    /* renamed from: getDisabledContainerColor-0d7_KjU, reason: not valid java name and from getter */
    public final long getDisabledContainerColor() {
        return this.disabledContainerColor;
    }

    /* renamed from: getErrorContainerColor-0d7_KjU, reason: not valid java name and from getter */
    public final long getErrorContainerColor() {
        return this.errorContainerColor;
    }

    /* renamed from: getCursorColor-0d7_KjU, reason: not valid java name and from getter */
    public final long getCursorColor() {
        return this.cursorColor;
    }

    /* renamed from: getErrorCursorColor-0d7_KjU, reason: not valid java name and from getter */
    public final long getErrorCursorColor() {
        return this.errorCursorColor;
    }

    public final SelectionColors getTextSelectionColors() {
        return this.textSelectionColors;
    }

    /* renamed from: getFocusedIndicatorColor-0d7_KjU, reason: not valid java name and from getter */
    public final long getFocusedIndicatorColor() {
        return this.focusedIndicatorColor;
    }

    /* renamed from: getUnfocusedIndicatorColor-0d7_KjU, reason: not valid java name and from getter */
    public final long getUnfocusedIndicatorColor() {
        return this.unfocusedIndicatorColor;
    }

    /* renamed from: getDisabledIndicatorColor-0d7_KjU, reason: not valid java name and from getter */
    public final long getDisabledIndicatorColor() {
        return this.disabledIndicatorColor;
    }

    /* renamed from: getErrorIndicatorColor-0d7_KjU, reason: not valid java name and from getter */
    public final long getErrorIndicatorColor() {
        return this.errorIndicatorColor;
    }

    /* renamed from: getFocusedLeadingIconColor-0d7_KjU, reason: not valid java name and from getter */
    public final long getFocusedLeadingIconColor() {
        return this.focusedLeadingIconColor;
    }

    /* renamed from: getUnfocusedLeadingIconColor-0d7_KjU, reason: not valid java name and from getter */
    public final long getUnfocusedLeadingIconColor() {
        return this.unfocusedLeadingIconColor;
    }

    /* renamed from: getDisabledLeadingIconColor-0d7_KjU, reason: not valid java name and from getter */
    public final long getDisabledLeadingIconColor() {
        return this.disabledLeadingIconColor;
    }

    /* renamed from: getErrorLeadingIconColor-0d7_KjU, reason: not valid java name and from getter */
    public final long getErrorLeadingIconColor() {
        return this.errorLeadingIconColor;
    }

    /* renamed from: getFocusedTrailingIconColor-0d7_KjU, reason: not valid java name and from getter */
    public final long getFocusedTrailingIconColor() {
        return this.focusedTrailingIconColor;
    }

    /* renamed from: getUnfocusedTrailingIconColor-0d7_KjU, reason: not valid java name and from getter */
    public final long getUnfocusedTrailingIconColor() {
        return this.unfocusedTrailingIconColor;
    }

    /* renamed from: getDisabledTrailingIconColor-0d7_KjU, reason: not valid java name and from getter */
    public final long getDisabledTrailingIconColor() {
        return this.disabledTrailingIconColor;
    }

    /* renamed from: getErrorTrailingIconColor-0d7_KjU, reason: not valid java name and from getter */
    public final long getErrorTrailingIconColor() {
        return this.errorTrailingIconColor;
    }

    /* renamed from: getFocusedLabelColor-0d7_KjU, reason: not valid java name and from getter */
    public final long getFocusedLabelColor() {
        return this.focusedLabelColor;
    }

    /* renamed from: getUnfocusedLabelColor-0d7_KjU, reason: not valid java name and from getter */
    public final long getUnfocusedLabelColor() {
        return this.unfocusedLabelColor;
    }

    /* renamed from: getDisabledLabelColor-0d7_KjU, reason: not valid java name and from getter */
    public final long getDisabledLabelColor() {
        return this.disabledLabelColor;
    }

    /* renamed from: getErrorLabelColor-0d7_KjU, reason: not valid java name and from getter */
    public final long getErrorLabelColor() {
        return this.errorLabelColor;
    }

    /* renamed from: getFocusedPlaceholderColor-0d7_KjU, reason: not valid java name and from getter */
    public final long getFocusedPlaceholderColor() {
        return this.focusedPlaceholderColor;
    }

    /* renamed from: getUnfocusedPlaceholderColor-0d7_KjU, reason: not valid java name and from getter */
    public final long getUnfocusedPlaceholderColor() {
        return this.unfocusedPlaceholderColor;
    }

    /* renamed from: getDisabledPlaceholderColor-0d7_KjU, reason: not valid java name and from getter */
    public final long getDisabledPlaceholderColor() {
        return this.disabledPlaceholderColor;
    }

    /* renamed from: getErrorPlaceholderColor-0d7_KjU, reason: not valid java name and from getter */
    public final long getErrorPlaceholderColor() {
        return this.errorPlaceholderColor;
    }

    /* renamed from: getFocusedSupportingTextColor-0d7_KjU, reason: not valid java name and from getter */
    public final long getFocusedSupportingTextColor() {
        return this.focusedSupportingTextColor;
    }

    /* renamed from: getUnfocusedSupportingTextColor-0d7_KjU, reason: not valid java name and from getter */
    public final long getUnfocusedSupportingTextColor() {
        return this.unfocusedSupportingTextColor;
    }

    /* renamed from: getDisabledSupportingTextColor-0d7_KjU, reason: not valid java name and from getter */
    public final long getDisabledSupportingTextColor() {
        return this.disabledSupportingTextColor;
    }

    /* renamed from: getErrorSupportingTextColor-0d7_KjU, reason: not valid java name and from getter */
    public final long getErrorSupportingTextColor() {
        return this.errorSupportingTextColor;
    }

    /* renamed from: getFocusedPrefixColor-0d7_KjU, reason: not valid java name and from getter */
    public final long getFocusedPrefixColor() {
        return this.focusedPrefixColor;
    }

    /* renamed from: getUnfocusedPrefixColor-0d7_KjU, reason: not valid java name and from getter */
    public final long getUnfocusedPrefixColor() {
        return this.unfocusedPrefixColor;
    }

    /* renamed from: getDisabledPrefixColor-0d7_KjU, reason: not valid java name and from getter */
    public final long getDisabledPrefixColor() {
        return this.disabledPrefixColor;
    }

    /* renamed from: getErrorPrefixColor-0d7_KjU, reason: not valid java name and from getter */
    public final long getErrorPrefixColor() {
        return this.errorPrefixColor;
    }

    /* renamed from: getFocusedSuffixColor-0d7_KjU, reason: not valid java name and from getter */
    public final long getFocusedSuffixColor() {
        return this.focusedSuffixColor;
    }

    /* renamed from: getUnfocusedSuffixColor-0d7_KjU, reason: not valid java name and from getter */
    public final long getUnfocusedSuffixColor() {
        return this.unfocusedSuffixColor;
    }

    /* renamed from: getDisabledSuffixColor-0d7_KjU, reason: not valid java name and from getter */
    public final long getDisabledSuffixColor() {
        return this.disabledSuffixColor;
    }

    /* renamed from: getErrorSuffixColor-0d7_KjU, reason: not valid java name and from getter */
    public final long getErrorSuffixColor() {
        return this.errorSuffixColor;
    }

    /* renamed from: copy-ejIjP34$default, reason: not valid java name */
    public static /* synthetic */ TextFieldColors m2380copyejIjP34$default(TextFieldColors textFieldColors, long j, long j2, long j3, long j4, long j5, long j6, long j7, long j8, long j9, long j10, SelectionColors selectionColors, long j11, long j12, long j13, long j14, long j15, long j16, long j17, long j18, long j19, long j20, long j21, long j22, long j23, long j24, long j25, long j26, long j27, long j28, long j29, long j30, long j31, long j32, long j33, long j34, long j35, long j36, long j37, long j38, long j39, long j40, long j41, long j42, int i, int i2, Object obj) {
        long j43;
        long j44;
        long j45;
        long j46;
        long j47;
        long j48;
        long j49;
        long j50;
        long j51;
        long j52;
        long j53;
        long j54;
        long j55;
        long j56;
        long j57;
        long j58;
        long j59;
        long j60;
        long j61;
        long j62;
        long j63;
        long j64;
        long j65;
        long j66;
        long j67;
        long j68;
        long j69;
        long j70;
        long j71;
        long j72;
        long j73;
        long j74;
        long j75;
        long j76;
        long j77;
        long j78;
        long j79;
        long j80;
        long j81;
        long j82;
        long j83;
        long j84;
        long j85;
        long j86;
        long j87;
        long j88;
        long j89;
        long j90;
        long j91;
        long j92;
        long j93;
        long j94;
        long j95;
        long j96;
        long j97;
        long j98;
        long j99;
        long j100;
        long j101;
        long j102;
        long j103;
        long j104;
        long j105;
        long j106;
        long j107;
        long j108;
        long j109;
        long j110;
        long j111;
        long j112;
        long j113 = (i & 1) != 0 ? textFieldColors.focusedTextColor : j;
        long j114 = (i & 2) != 0 ? textFieldColors.unfocusedTextColor : j2;
        long j115 = (i & 4) != 0 ? textFieldColors.disabledTextColor : j3;
        long j116 = (i & 8) != 0 ? textFieldColors.errorTextColor : j4;
        long j117 = (i & 16) != 0 ? textFieldColors.focusedContainerColor : j5;
        long j118 = (i & 32) != 0 ? textFieldColors.unfocusedContainerColor : j6;
        if ((i & 64) != 0) {
            j43 = j118;
            j44 = textFieldColors.disabledContainerColor;
        } else {
            j43 = j118;
            j44 = j7;
        }
        if ((i & 128) != 0) {
            j45 = j44;
            j46 = textFieldColors.errorContainerColor;
        } else {
            j45 = j44;
            j46 = j8;
        }
        if ((i & 256) != 0) {
            j47 = j46;
            j48 = textFieldColors.cursorColor;
        } else {
            j47 = j46;
            j48 = j9;
        }
        if ((i & 512) != 0) {
            j49 = j48;
            j50 = textFieldColors.errorCursorColor;
        } else {
            j49 = j48;
            j50 = j10;
        }
        SelectionColors selectionColors2 = (i & 1024) != 0 ? textFieldColors.textSelectionColors : selectionColors;
        if ((i & 2048) != 0) {
            j51 = j50;
            j52 = textFieldColors.focusedIndicatorColor;
        } else {
            j51 = j50;
            j52 = j11;
        }
        if ((i & 4096) != 0) {
            j53 = j52;
            j54 = textFieldColors.unfocusedIndicatorColor;
        } else {
            j53 = j52;
            j54 = j12;
        }
        if ((i & 8192) != 0) {
            j55 = j54;
            j56 = textFieldColors.disabledIndicatorColor;
        } else {
            j55 = j54;
            j56 = j13;
        }
        if ((i & 16384) != 0) {
            j57 = j56;
            j58 = textFieldColors.errorIndicatorColor;
        } else {
            j57 = j56;
            j58 = j14;
        }
        if ((32768 & i) != 0) {
            j59 = j58;
            j60 = textFieldColors.focusedLeadingIconColor;
        } else {
            j59 = j58;
            j60 = j15;
        }
        if ((65536 & i) != 0) {
            j61 = j60;
            j62 = textFieldColors.unfocusedLeadingIconColor;
        } else {
            j61 = j60;
            j62 = j16;
        }
        if ((131072 & i) != 0) {
            j63 = j62;
            j64 = textFieldColors.disabledLeadingIconColor;
        } else {
            j63 = j62;
            j64 = j17;
        }
        if ((262144 & i) != 0) {
            j65 = j64;
            j66 = textFieldColors.errorLeadingIconColor;
        } else {
            j65 = j64;
            j66 = j18;
        }
        if ((524288 & i) != 0) {
            j67 = j66;
            j68 = textFieldColors.focusedTrailingIconColor;
        } else {
            j67 = j66;
            j68 = j19;
        }
        if ((1048576 & i) != 0) {
            j69 = j68;
            j70 = textFieldColors.unfocusedTrailingIconColor;
        } else {
            j69 = j68;
            j70 = j20;
        }
        if ((2097152 & i) != 0) {
            j71 = j70;
            j72 = textFieldColors.disabledTrailingIconColor;
        } else {
            j71 = j70;
            j72 = j21;
        }
        if ((4194304 & i) != 0) {
            j73 = j72;
            j74 = textFieldColors.errorTrailingIconColor;
        } else {
            j73 = j72;
            j74 = j22;
        }
        if ((8388608 & i) != 0) {
            j75 = j74;
            j76 = textFieldColors.focusedLabelColor;
        } else {
            j75 = j74;
            j76 = j23;
        }
        if ((16777216 & i) != 0) {
            j77 = j76;
            j78 = textFieldColors.unfocusedLabelColor;
        } else {
            j77 = j76;
            j78 = j24;
        }
        if ((33554432 & i) != 0) {
            j79 = j78;
            j80 = textFieldColors.disabledLabelColor;
        } else {
            j79 = j78;
            j80 = j25;
        }
        if ((67108864 & i) != 0) {
            j81 = j80;
            j82 = textFieldColors.errorLabelColor;
        } else {
            j81 = j80;
            j82 = j26;
        }
        if ((134217728 & i) != 0) {
            j83 = j82;
            j84 = textFieldColors.focusedPlaceholderColor;
        } else {
            j83 = j82;
            j84 = j27;
        }
        if ((268435456 & i) != 0) {
            j85 = j84;
            j86 = textFieldColors.unfocusedPlaceholderColor;
        } else {
            j85 = j84;
            j86 = j28;
        }
        if ((536870912 & i) != 0) {
            j87 = j86;
            j88 = textFieldColors.disabledPlaceholderColor;
        } else {
            j87 = j86;
            j88 = j29;
        }
        if ((1073741824 & i) != 0) {
            j89 = j88;
            j90 = textFieldColors.errorPlaceholderColor;
        } else {
            j89 = j88;
            j90 = j30;
        }
        if ((i & Integer.MIN_VALUE) != 0) {
            j91 = j90;
            j92 = textFieldColors.focusedSupportingTextColor;
        } else {
            j91 = j90;
            j92 = j31;
        }
        if ((i2 & 1) != 0) {
            j93 = j92;
            j94 = textFieldColors.unfocusedSupportingTextColor;
        } else {
            j93 = j92;
            j94 = j32;
        }
        if ((i2 & 2) != 0) {
            j95 = j94;
            j96 = textFieldColors.disabledSupportingTextColor;
        } else {
            j95 = j94;
            j96 = j33;
        }
        if ((i2 & 4) != 0) {
            j97 = j96;
            j98 = textFieldColors.errorSupportingTextColor;
        } else {
            j97 = j96;
            j98 = j34;
        }
        if ((i2 & 8) != 0) {
            j99 = j98;
            j100 = textFieldColors.focusedPrefixColor;
        } else {
            j99 = j98;
            j100 = j35;
        }
        if ((i2 & 16) != 0) {
            j101 = j100;
            j102 = textFieldColors.unfocusedPrefixColor;
        } else {
            j101 = j100;
            j102 = j36;
        }
        if ((i2 & 32) != 0) {
            j103 = j102;
            j104 = textFieldColors.disabledPrefixColor;
        } else {
            j103 = j102;
            j104 = j37;
        }
        if ((i2 & 64) != 0) {
            j105 = j104;
            j106 = textFieldColors.errorPrefixColor;
        } else {
            j105 = j104;
            j106 = j38;
        }
        if ((i2 & 128) != 0) {
            j107 = j106;
            j108 = textFieldColors.focusedSuffixColor;
        } else {
            j107 = j106;
            j108 = j39;
        }
        if ((i2 & 256) != 0) {
            j109 = j108;
            j110 = textFieldColors.unfocusedSuffixColor;
        } else {
            j109 = j108;
            j110 = j40;
        }
        if ((i2 & 512) != 0) {
            j111 = j110;
            j112 = textFieldColors.disabledSuffixColor;
        } else {
            j111 = j110;
            j112 = j41;
        }
        return textFieldColors.m2381copyejIjP34(j113, j114, j115, j116, j117, j43, j45, j47, j49, j51, selectionColors2, j53, j55, j57, j59, j61, j63, j65, j67, j69, j71, j73, j75, j77, j79, j81, j83, j85, j87, j89, j91, j93, j95, j97, j99, j101, j103, j105, j107, j109, j111, j112, (i2 & 1024) != 0 ? textFieldColors.errorSuffixColor : j42);
    }

    /* renamed from: copy-ejIjP34, reason: not valid java name */
    public final TextFieldColors m2381copyejIjP34(long focusedTextColor, long unfocusedTextColor, long disabledTextColor, long errorTextColor, long focusedContainerColor, long unfocusedContainerColor, long disabledContainerColor, long errorContainerColor, long cursorColor, long errorCursorColor, SelectionColors textSelectionColors, long focusedIndicatorColor, long unfocusedIndicatorColor, long disabledIndicatorColor, long errorIndicatorColor, long focusedLeadingIconColor, long unfocusedLeadingIconColor, long disabledLeadingIconColor, long errorLeadingIconColor, long focusedTrailingIconColor, long unfocusedTrailingIconColor, long disabledTrailingIconColor, long errorTrailingIconColor, long focusedLabelColor, long unfocusedLabelColor, long disabledLabelColor, long errorLabelColor, long focusedPlaceholderColor, long unfocusedPlaceholderColor, long disabledPlaceholderColor, long errorPlaceholderColor, long focusedSupportingTextColor, long unfocusedSupportingTextColor, long disabledSupportingTextColor, long errorSupportingTextColor, long focusedPrefixColor, long unfocusedPrefixColor, long disabledPrefixColor, long errorPrefixColor, long focusedSuffixColor, long unfocusedSuffixColor, long disabledSuffixColor, long errorSuffixColor) {
        return new TextFieldColors((focusedTextColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (focusedTextColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? focusedTextColor : this.focusedTextColor, (unfocusedTextColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (unfocusedTextColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? unfocusedTextColor : this.unfocusedTextColor, (disabledTextColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (disabledTextColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? disabledTextColor : this.disabledTextColor, (errorTextColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (errorTextColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? errorTextColor : this.errorTextColor, (focusedContainerColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (focusedContainerColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? focusedContainerColor : this.focusedContainerColor, (unfocusedContainerColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (unfocusedContainerColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? unfocusedContainerColor : this.unfocusedContainerColor, (disabledContainerColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (disabledContainerColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? disabledContainerColor : this.disabledContainerColor, (errorContainerColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (errorContainerColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? errorContainerColor : this.errorContainerColor, (cursorColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (cursorColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? cursorColor : this.cursorColor, (errorCursorColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (errorCursorColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? errorCursorColor : this.errorCursorColor, takeOrElse$material3_release(textSelectionColors, new Function0<SelectionColors>() { // from class: androidx.compose.material3.TextFieldColors$copy$11
            {
                super(0);
            }

            /* JADX WARN: Can't rename method to resolve collision */
            @Override // kotlin.jvm.functions.Function0
            public final SelectionColors invoke() {
                return TextFieldColors.this.getTextSelectionColors();
            }
        }), (focusedIndicatorColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (focusedIndicatorColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? focusedIndicatorColor : this.focusedIndicatorColor, (unfocusedIndicatorColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (unfocusedIndicatorColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? unfocusedIndicatorColor : this.unfocusedIndicatorColor, (disabledIndicatorColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (disabledIndicatorColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? disabledIndicatorColor : this.disabledIndicatorColor, (errorIndicatorColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (errorIndicatorColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? errorIndicatorColor : this.errorIndicatorColor, (focusedLeadingIconColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (focusedLeadingIconColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? focusedLeadingIconColor : this.focusedLeadingIconColor, (unfocusedLeadingIconColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (unfocusedLeadingIconColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? unfocusedLeadingIconColor : this.unfocusedLeadingIconColor, (disabledLeadingIconColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (disabledLeadingIconColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? disabledLeadingIconColor : this.disabledLeadingIconColor, (errorLeadingIconColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (errorLeadingIconColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? errorLeadingIconColor : this.errorLeadingIconColor, (focusedTrailingIconColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (focusedTrailingIconColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? focusedTrailingIconColor : this.focusedTrailingIconColor, (unfocusedTrailingIconColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (unfocusedTrailingIconColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? unfocusedTrailingIconColor : this.unfocusedTrailingIconColor, (disabledTrailingIconColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (disabledTrailingIconColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? disabledTrailingIconColor : this.disabledTrailingIconColor, (errorTrailingIconColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (errorTrailingIconColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? errorTrailingIconColor : this.errorTrailingIconColor, (focusedLabelColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (focusedLabelColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? focusedLabelColor : this.focusedLabelColor, (unfocusedLabelColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (unfocusedLabelColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? unfocusedLabelColor : this.unfocusedLabelColor, (disabledLabelColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (disabledLabelColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? disabledLabelColor : this.disabledLabelColor, (errorLabelColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (errorLabelColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? errorLabelColor : this.errorLabelColor, (focusedPlaceholderColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (focusedPlaceholderColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? focusedPlaceholderColor : this.focusedPlaceholderColor, (unfocusedPlaceholderColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (unfocusedPlaceholderColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? unfocusedPlaceholderColor : this.unfocusedPlaceholderColor, (disabledPlaceholderColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (disabledPlaceholderColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? disabledPlaceholderColor : this.disabledPlaceholderColor, (errorPlaceholderColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (errorPlaceholderColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? errorPlaceholderColor : this.errorPlaceholderColor, (focusedSupportingTextColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (focusedSupportingTextColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? focusedSupportingTextColor : this.focusedSupportingTextColor, (unfocusedSupportingTextColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (unfocusedSupportingTextColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? unfocusedSupportingTextColor : this.unfocusedSupportingTextColor, (disabledSupportingTextColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (disabledSupportingTextColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? disabledSupportingTextColor : this.disabledSupportingTextColor, (errorSupportingTextColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (errorSupportingTextColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? errorSupportingTextColor : this.errorSupportingTextColor, (focusedPrefixColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (focusedPrefixColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? focusedPrefixColor : this.focusedPrefixColor, (unfocusedPrefixColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (unfocusedPrefixColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? unfocusedPrefixColor : this.unfocusedPrefixColor, (disabledPrefixColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (disabledPrefixColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? disabledPrefixColor : this.disabledPrefixColor, (errorPrefixColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (errorPrefixColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? errorPrefixColor : this.errorPrefixColor, (focusedSuffixColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (focusedSuffixColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? focusedSuffixColor : this.focusedSuffixColor, (unfocusedSuffixColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (unfocusedSuffixColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? unfocusedSuffixColor : this.unfocusedSuffixColor, (disabledSuffixColor > Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 1 : (disabledSuffixColor == Color.INSTANCE.m3782getUnspecified0d7_KjU() ? 0 : -1)) != 0 ? disabledSuffixColor : this.disabledSuffixColor, errorSuffixColor != Color.INSTANCE.m3782getUnspecified0d7_KjU() ? errorSuffixColor : this.errorSuffixColor, null);
    }

    public final SelectionColors takeOrElse$material3_release(SelectionColors $this$takeOrElse, Function0<SelectionColors> function0) {
        return $this$takeOrElse == null ? function0.invoke() : $this$takeOrElse;
    }

    public final State<Color> leadingIconColor$material3_release(boolean enabled, boolean isError, InteractionSource interactionSource, Composer $composer, int $changed) {
        long j;
        $composer.startReplaceableGroup(925127045);
        ComposerKt.sourceInformation($composer, "C(leadingIconColor)P(!1,2)2028@113395L25,2030@113437L267:TextFieldDefaults.kt#uh7d8r");
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventStart(925127045, $changed, -1, "androidx.compose.material3.TextFieldColors.leadingIconColor (TextFieldDefaults.kt:2027)");
        }
        State focused$delegate = FocusInteractionKt.collectIsFocusedAsState(interactionSource, $composer, ($changed >> 6) & 14);
        if (!enabled) {
            j = this.disabledLeadingIconColor;
        } else if (isError) {
            j = this.errorLeadingIconColor;
        } else {
            j = leadingIconColor$lambda$42(focused$delegate) ? this.focusedLeadingIconColor : this.unfocusedLeadingIconColor;
        }
        State<Color> rememberUpdatedState = SnapshotStateKt.rememberUpdatedState(Color.m3736boximpl(j), $composer, 0);
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventEnd();
        }
        $composer.endReplaceableGroup();
        return rememberUpdatedState;
    }

    private static final boolean leadingIconColor$lambda$42(State<Boolean> state) {
        Object thisObj$iv = state.getValue();
        return ((Boolean) thisObj$iv).booleanValue();
    }

    public final State<Color> trailingIconColor$material3_release(boolean enabled, boolean isError, InteractionSource interactionSource, Composer $composer, int $changed) {
        long j;
        $composer.startReplaceableGroup(-109504137);
        ComposerKt.sourceInformation($composer, "C(trailingIconColor)P(!1,2)2054@114290L25,2056@114332L271:TextFieldDefaults.kt#uh7d8r");
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventStart(-109504137, $changed, -1, "androidx.compose.material3.TextFieldColors.trailingIconColor (TextFieldDefaults.kt:2053)");
        }
        State focused$delegate = FocusInteractionKt.collectIsFocusedAsState(interactionSource, $composer, ($changed >> 6) & 14);
        if (!enabled) {
            j = this.disabledTrailingIconColor;
        } else if (isError) {
            j = this.errorTrailingIconColor;
        } else {
            j = trailingIconColor$lambda$43(focused$delegate) ? this.focusedTrailingIconColor : this.unfocusedTrailingIconColor;
        }
        State<Color> rememberUpdatedState = SnapshotStateKt.rememberUpdatedState(Color.m3736boximpl(j), $composer, 0);
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventEnd();
        }
        $composer.endReplaceableGroup();
        return rememberUpdatedState;
    }

    private static final boolean trailingIconColor$lambda$43(State<Boolean> state) {
        Object thisObj$iv = state.getValue();
        return ((Boolean) thisObj$iv).booleanValue();
    }

    public final State<Color> indicatorColor$material3_release(boolean enabled, boolean isError, InteractionSource interactionSource, Composer $composer, int $changed) {
        long targetValue;
        State<Color> rememberUpdatedState;
        $composer.startReplaceableGroup(-1877482635);
        ComposerKt.sourceInformation($composer, "C(indicatorColor)P(!1,2)2080@115189L25:TextFieldDefaults.kt#uh7d8r");
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventStart(-1877482635, $changed, -1, "androidx.compose.material3.TextFieldColors.indicatorColor (TextFieldDefaults.kt:2079)");
        }
        State focused$delegate = FocusInteractionKt.collectIsFocusedAsState(interactionSource, $composer, ($changed >> 6) & 14);
        if (!enabled) {
            targetValue = this.disabledIndicatorColor;
        } else if (isError) {
            targetValue = this.errorIndicatorColor;
        } else {
            targetValue = indicatorColor$lambda$44(focused$delegate) ? this.focusedIndicatorColor : this.unfocusedIndicatorColor;
        }
        if (enabled) {
            $composer.startReplaceableGroup(715804770);
            ComposerKt.sourceInformation($composer, "2089@115480L75");
            rememberUpdatedState = SingleValueAnimationKt.m104animateColorAsStateeuL9pac(targetValue, AnimationSpecKt.tween$default(150, 0, null, 6, null), null, null, $composer, 48, 12);
            $composer.endReplaceableGroup();
        } else {
            $composer.startReplaceableGroup(715804875);
            ComposerKt.sourceInformation($composer, "2091@115585L33");
            rememberUpdatedState = SnapshotStateKt.rememberUpdatedState(Color.m3736boximpl(targetValue), $composer, 0);
            $composer.endReplaceableGroup();
        }
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventEnd();
        }
        $composer.endReplaceableGroup();
        return rememberUpdatedState;
    }

    private static final boolean indicatorColor$lambda$44(State<Boolean> state) {
        Object thisObj$iv = state.getValue();
        return ((Boolean) thisObj$iv).booleanValue();
    }

    public final State<Color> containerColor$material3_release(boolean enabled, boolean isError, InteractionSource interactionSource, Composer $composer, int $changed) {
        long targetValue;
        $composer.startReplaceableGroup(-1921164569);
        ComposerKt.sourceInformation($composer, "C(containerColor)P(!1,2)2109@116195L25,2117@116459L75:TextFieldDefaults.kt#uh7d8r");
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventStart(-1921164569, $changed, -1, "androidx.compose.material3.TextFieldColors.containerColor (TextFieldDefaults.kt:2108)");
        }
        State focused$delegate = FocusInteractionKt.collectIsFocusedAsState(interactionSource, $composer, ($changed >> 6) & 14);
        if (!enabled) {
            targetValue = this.disabledContainerColor;
        } else if (isError) {
            targetValue = this.errorContainerColor;
        } else {
            targetValue = containerColor$lambda$45(focused$delegate) ? this.focusedContainerColor : this.unfocusedContainerColor;
        }
        State<Color> m104animateColorAsStateeuL9pac = SingleValueAnimationKt.m104animateColorAsStateeuL9pac(targetValue, AnimationSpecKt.tween$default(150, 0, null, 6, null), null, null, $composer, 48, 12);
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventEnd();
        }
        $composer.endReplaceableGroup();
        return m104animateColorAsStateeuL9pac;
    }

    private static final boolean containerColor$lambda$45(State<Boolean> state) {
        Object thisObj$iv = state.getValue();
        return ((Boolean) thisObj$iv).booleanValue();
    }

    public final State<Color> placeholderColor$material3_release(boolean enabled, boolean isError, InteractionSource interactionSource, Composer $composer, int $changed) {
        long targetValue;
        $composer.startReplaceableGroup(653850713);
        ComposerKt.sourceInformation($composer, "C(placeholderColor)P(!1,2)2134@117117L25,2142@117389L33:TextFieldDefaults.kt#uh7d8r");
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventStart(653850713, $changed, -1, "androidx.compose.material3.TextFieldColors.placeholderColor (TextFieldDefaults.kt:2133)");
        }
        State focused$delegate = FocusInteractionKt.collectIsFocusedAsState(interactionSource, $composer, ($changed >> 6) & 14);
        if (!enabled) {
            targetValue = this.disabledPlaceholderColor;
        } else if (isError) {
            targetValue = this.errorPlaceholderColor;
        } else {
            targetValue = placeholderColor$lambda$46(focused$delegate) ? this.focusedPlaceholderColor : this.unfocusedPlaceholderColor;
        }
        State<Color> rememberUpdatedState = SnapshotStateKt.rememberUpdatedState(Color.m3736boximpl(targetValue), $composer, 0);
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventEnd();
        }
        $composer.endReplaceableGroup();
        return rememberUpdatedState;
    }

    private static final boolean placeholderColor$lambda$46(State<Boolean> state) {
        Object thisObj$iv = state.getValue();
        return ((Boolean) thisObj$iv).booleanValue();
    }

    public final State<Color> labelColor$material3_release(boolean enabled, boolean isError, InteractionSource interactionSource, Composer $composer, int $changed) {
        long targetValue;
        $composer.startReplaceableGroup(1167161306);
        ComposerKt.sourceInformation($composer, "C(labelColor)P(!1,2)2159@117993L25,2167@118241L33:TextFieldDefaults.kt#uh7d8r");
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventStart(1167161306, $changed, -1, "androidx.compose.material3.TextFieldColors.labelColor (TextFieldDefaults.kt:2158)");
        }
        State focused$delegate = FocusInteractionKt.collectIsFocusedAsState(interactionSource, $composer, ($changed >> 6) & 14);
        if (!enabled) {
            targetValue = this.disabledLabelColor;
        } else if (isError) {
            targetValue = this.errorLabelColor;
        } else {
            targetValue = labelColor$lambda$47(focused$delegate) ? this.focusedLabelColor : this.unfocusedLabelColor;
        }
        State<Color> rememberUpdatedState = SnapshotStateKt.rememberUpdatedState(Color.m3736boximpl(targetValue), $composer, 0);
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventEnd();
        }
        $composer.endReplaceableGroup();
        return rememberUpdatedState;
    }

    private static final boolean labelColor$lambda$47(State<Boolean> state) {
        Object thisObj$iv = state.getValue();
        return ((Boolean) thisObj$iv).booleanValue();
    }

    public final State<Color> textColor$material3_release(boolean enabled, boolean isError, InteractionSource interactionSource, Composer $composer, int $changed) {
        long targetValue;
        $composer.startReplaceableGroup(68412911);
        ComposerKt.sourceInformation($composer, "C(textColor)P(!1,2)2184@118850L25,2192@119094L33:TextFieldDefaults.kt#uh7d8r");
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventStart(68412911, $changed, -1, "androidx.compose.material3.TextFieldColors.textColor (TextFieldDefaults.kt:2183)");
        }
        State focused$delegate = FocusInteractionKt.collectIsFocusedAsState(interactionSource, $composer, ($changed >> 6) & 14);
        if (!enabled) {
            targetValue = this.disabledTextColor;
        } else if (isError) {
            targetValue = this.errorTextColor;
        } else {
            targetValue = textColor$lambda$48(focused$delegate) ? this.focusedTextColor : this.unfocusedTextColor;
        }
        State<Color> rememberUpdatedState = SnapshotStateKt.rememberUpdatedState(Color.m3736boximpl(targetValue), $composer, 0);
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventEnd();
        }
        $composer.endReplaceableGroup();
        return rememberUpdatedState;
    }

    private static final boolean textColor$lambda$48(State<Boolean> state) {
        Object thisObj$iv = state.getValue();
        return ((Boolean) thisObj$iv).booleanValue();
    }

    public final State<Color> supportingTextColor$material3_release(boolean enabled, boolean isError, InteractionSource interactionSource, Composer $composer, int $changed) {
        long j;
        $composer.startReplaceableGroup(1464709698);
        ComposerKt.sourceInformation($composer, "C(supportingTextColor)P(!1,2)2201@119349L25,2203@119391L279:TextFieldDefaults.kt#uh7d8r");
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventStart(1464709698, $changed, -1, "androidx.compose.material3.TextFieldColors.supportingTextColor (TextFieldDefaults.kt:2200)");
        }
        State focused$delegate = FocusInteractionKt.collectIsFocusedAsState(interactionSource, $composer, ($changed >> 6) & 14);
        if (!enabled) {
            j = this.disabledSupportingTextColor;
        } else if (isError) {
            j = this.errorSupportingTextColor;
        } else {
            j = supportingTextColor$lambda$49(focused$delegate) ? this.focusedSupportingTextColor : this.unfocusedSupportingTextColor;
        }
        State<Color> rememberUpdatedState = SnapshotStateKt.rememberUpdatedState(Color.m3736boximpl(j), $composer, 0);
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventEnd();
        }
        $composer.endReplaceableGroup();
        return rememberUpdatedState;
    }

    private static final boolean supportingTextColor$lambda$49(State<Boolean> state) {
        Object thisObj$iv = state.getValue();
        return ((Boolean) thisObj$iv).booleanValue();
    }

    public final State<Color> prefixColor$material3_release(boolean enabled, boolean isError, InteractionSource interactionSource, Composer $composer, int $changed) {
        long targetValue;
        $composer.startReplaceableGroup(129569364);
        ComposerKt.sourceInformation($composer, "C(prefixColor)P(!1,2)2227@120243L25,2235@120495L33:TextFieldDefaults.kt#uh7d8r");
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventStart(129569364, $changed, -1, "androidx.compose.material3.TextFieldColors.prefixColor (TextFieldDefaults.kt:2226)");
        }
        State focused$delegate = FocusInteractionKt.collectIsFocusedAsState(interactionSource, $composer, ($changed >> 6) & 14);
        if (!enabled) {
            targetValue = this.disabledPrefixColor;
        } else if (isError) {
            targetValue = this.errorPrefixColor;
        } else {
            targetValue = prefixColor$lambda$50(focused$delegate) ? this.focusedPrefixColor : this.unfocusedPrefixColor;
        }
        State<Color> rememberUpdatedState = SnapshotStateKt.rememberUpdatedState(Color.m3736boximpl(targetValue), $composer, 0);
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventEnd();
        }
        $composer.endReplaceableGroup();
        return rememberUpdatedState;
    }

    private static final boolean prefixColor$lambda$50(State<Boolean> state) {
        Object thisObj$iv = state.getValue();
        return ((Boolean) thisObj$iv).booleanValue();
    }

    public final State<Color> suffixColor$material3_release(boolean enabled, boolean isError, InteractionSource interactionSource, Composer $composer, int $changed) {
        long targetValue;
        $composer.startReplaceableGroup(1575329427);
        ComposerKt.sourceInformation($composer, "C(suffixColor)P(!1,2)2252@121101L25,2260@121353L33:TextFieldDefaults.kt#uh7d8r");
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventStart(1575329427, $changed, -1, "androidx.compose.material3.TextFieldColors.suffixColor (TextFieldDefaults.kt:2251)");
        }
        State focused$delegate = FocusInteractionKt.collectIsFocusedAsState(interactionSource, $composer, ($changed >> 6) & 14);
        if (!enabled) {
            targetValue = this.disabledSuffixColor;
        } else if (isError) {
            targetValue = this.errorSuffixColor;
        } else {
            targetValue = suffixColor$lambda$51(focused$delegate) ? this.focusedSuffixColor : this.unfocusedSuffixColor;
        }
        State<Color> rememberUpdatedState = SnapshotStateKt.rememberUpdatedState(Color.m3736boximpl(targetValue), $composer, 0);
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventEnd();
        }
        $composer.endReplaceableGroup();
        return rememberUpdatedState;
    }

    private static final boolean suffixColor$lambda$51(State<Boolean> state) {
        Object thisObj$iv = state.getValue();
        return ((Boolean) thisObj$iv).booleanValue();
    }

    public final State<Color> cursorColor$material3_release(boolean isError, Composer $composer, int $changed) {
        $composer.startReplaceableGroup(-1885422187);
        ComposerKt.sourceInformation($composer, "C(cursorColor)2270@121652L68:TextFieldDefaults.kt#uh7d8r");
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventStart(-1885422187, $changed, -1, "androidx.compose.material3.TextFieldColors.cursorColor (TextFieldDefaults.kt:2269)");
        }
        State<Color> rememberUpdatedState = SnapshotStateKt.rememberUpdatedState(Color.m3736boximpl(isError ? this.errorCursorColor : this.cursorColor), $composer, 0);
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventEnd();
        }
        $composer.endReplaceableGroup();
        return rememberUpdatedState;
    }

    public final SelectionColors getSelectionColors(Composer $composer, int $changed) {
        $composer.startReplaceableGroup(997785083);
        ComposerKt.sourceInformation($composer, "C:TextFieldDefaults.kt#uh7d8r");
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventStart(997785083, $changed, -1, "androidx.compose.material3.TextFieldColors.<get-selectionColors> (TextFieldDefaults.kt:2277)");
        }
        SelectionColors selectionColors = this.textSelectionColors;
        if (ComposerKt.isTraceInProgress()) {
            ComposerKt.traceEventEnd();
        }
        $composer.endReplaceableGroup();
        return selectionColors;
    }

    public boolean equals(Object other) {
        if (this == other) {
            return true;
        }
        if (other != null && (other instanceof TextFieldColors) && Color.m3747equalsimpl0(this.focusedTextColor, ((TextFieldColors) other).focusedTextColor) && Color.m3747equalsimpl0(this.unfocusedTextColor, ((TextFieldColors) other).unfocusedTextColor) && Color.m3747equalsimpl0(this.disabledTextColor, ((TextFieldColors) other).disabledTextColor) && Color.m3747equalsimpl0(this.errorTextColor, ((TextFieldColors) other).errorTextColor) && Color.m3747equalsimpl0(this.focusedContainerColor, ((TextFieldColors) other).focusedContainerColor) && Color.m3747equalsimpl0(this.unfocusedContainerColor, ((TextFieldColors) other).unfocusedContainerColor) && Color.m3747equalsimpl0(this.disabledContainerColor, ((TextFieldColors) other).disabledContainerColor) && Color.m3747equalsimpl0(this.errorContainerColor, ((TextFieldColors) other).errorContainerColor) && Color.m3747equalsimpl0(this.cursorColor, ((TextFieldColors) other).cursorColor) && Color.m3747equalsimpl0(this.errorCursorColor, ((TextFieldColors) other).errorCursorColor) && Intrinsics.areEqual(this.textSelectionColors, ((TextFieldColors) other).textSelectionColors) && Color.m3747equalsimpl0(this.focusedIndicatorColor, ((TextFieldColors) other).focusedIndicatorColor) && Color.m3747equalsimpl0(this.unfocusedIndicatorColor, ((TextFieldColors) other).unfocusedIndicatorColor) && Color.m3747equalsimpl0(this.disabledIndicatorColor, ((TextFieldColors) other).disabledIndicatorColor) && Color.m3747equalsimpl0(this.errorIndicatorColor, ((TextFieldColors) other).errorIndicatorColor) && Color.m3747equalsimpl0(this.focusedLeadingIconColor, ((TextFieldColors) other).focusedLeadingIconColor) && Color.m3747equalsimpl0(this.unfocusedLeadingIconColor, ((TextFieldColors) other).unfocusedLeadingIconColor) && Color.m3747equalsimpl0(this.disabledLeadingIconColor, ((TextFieldColors) other).disabledLeadingIconColor) && Color.m3747equalsimpl0(this.errorLeadingIconColor, ((TextFieldColors) other).errorLeadingIconColor) && Color.m3747equalsimpl0(this.focusedTrailingIconColor, ((TextFieldColors) other).focusedTrailingIconColor) && Color.m3747equalsimpl0(this.unfocusedTrailingIconColor, ((TextFieldColors) other).unfocusedTrailingIconColor) && Color.m3747equalsimpl0(this.disabledTrailingIconColor, ((TextFieldColors) other).disabledTrailingIconColor) && Color.m3747equalsimpl0(this.errorTrailingIconColor, ((TextFieldColors) other).errorTrailingIconColor) && Color.m3747equalsimpl0(this.focusedLabelColor, ((TextFieldColors) other).focusedLabelColor) && Color.m3747equalsimpl0(this.unfocusedLabelColor, ((TextFieldColors) other).unfocusedLabelColor) && Color.m3747equalsimpl0(this.disabledLabelColor, ((TextFieldColors) other).disabledLabelColor) && Color.m3747equalsimpl0(this.errorLabelColor, ((TextFieldColors) other).errorLabelColor) && Color.m3747equalsimpl0(this.focusedPlaceholderColor, ((TextFieldColors) other).focusedPlaceholderColor) && Color.m3747equalsimpl0(this.unfocusedPlaceholderColor, ((TextFieldColors) other).unfocusedPlaceholderColor) && Color.m3747equalsimpl0(this.disabledPlaceholderColor, ((TextFieldColors) other).disabledPlaceholderColor) && Color.m3747equalsimpl0(this.errorPlaceholderColor, ((TextFieldColors) other).errorPlaceholderColor) && Color.m3747equalsimpl0(this.focusedSupportingTextColor, ((TextFieldColors) other).focusedSupportingTextColor) && Color.m3747equalsimpl0(this.unfocusedSupportingTextColor, ((TextFieldColors) other).unfocusedSupportingTextColor) && Color.m3747equalsimpl0(this.disabledSupportingTextColor, ((TextFieldColors) other).disabledSupportingTextColor) && Color.m3747equalsimpl0(this.errorSupportingTextColor, ((TextFieldColors) other).errorSupportingTextColor) && Color.m3747equalsimpl0(this.focusedPrefixColor, ((TextFieldColors) other).focusedPrefixColor) && Color.m3747equalsimpl0(this.unfocusedPrefixColor, ((TextFieldColors) other).unfocusedPrefixColor) && Color.m3747equalsimpl0(this.disabledPrefixColor, ((TextFieldColors) other).disabledPrefixColor) && Color.m3747equalsimpl0(this.errorPrefixColor, ((TextFieldColors) other).errorPrefixColor) && Color.m3747equalsimpl0(this.focusedSuffixColor, ((TextFieldColors) other).focusedSuffixColor) && Color.m3747equalsimpl0(this.unfocusedSuffixColor, ((TextFieldColors) other).unfocusedSuffixColor) && Color.m3747equalsimpl0(this.disabledSuffixColor, ((TextFieldColors) other).disabledSuffixColor) && Color.m3747equalsimpl0(this.errorSuffixColor, ((TextFieldColors) other).errorSuffixColor)) {
            return true;
        }
        return false;
    }

    public int hashCode() {
        int result = Color.m3753hashCodeimpl(this.focusedTextColor);
        return (((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((result * 31) + Color.m3753hashCodeimpl(this.unfocusedTextColor)) * 31) + Color.m3753hashCodeimpl(this.disabledTextColor)) * 31) + Color.m3753hashCodeimpl(this.errorTextColor)) * 31) + Color.m3753hashCodeimpl(this.focusedContainerColor)) * 31) + Color.m3753hashCodeimpl(this.unfocusedContainerColor)) * 31) + Color.m3753hashCodeimpl(this.disabledContainerColor)) * 31) + Color.m3753hashCodeimpl(this.errorContainerColor)) * 31) + Color.m3753hashCodeimpl(this.cursorColor)) * 31) + Color.m3753hashCodeimpl(this.errorCursorColor)) * 31) + this.textSelectionColors.hashCode()) * 31) + Color.m3753hashCodeimpl(this.focusedIndicatorColor)) * 31) + Color.m3753hashCodeimpl(this.unfocusedIndicatorColor)) * 31) + Color.m3753hashCodeimpl(this.disabledIndicatorColor)) * 31) + Color.m3753hashCodeimpl(this.errorIndicatorColor)) * 31) + Color.m3753hashCodeimpl(this.focusedLeadingIconColor)) * 31) + Color.m3753hashCodeimpl(this.unfocusedLeadingIconColor)) * 31) + Color.m3753hashCodeimpl(this.disabledLeadingIconColor)) * 31) + Color.m3753hashCodeimpl(this.errorLeadingIconColor)) * 31) + Color.m3753hashCodeimpl(this.focusedTrailingIconColor)) * 31) + Color.m3753hashCodeimpl(this.unfocusedTrailingIconColor)) * 31) + Color.m3753hashCodeimpl(this.disabledTrailingIconColor)) * 31) + Color.m3753hashCodeimpl(this.errorTrailingIconColor)) * 31) + Color.m3753hashCodeimpl(this.focusedLabelColor)) * 31) + Color.m3753hashCodeimpl(this.unfocusedLabelColor)) * 31) + Color.m3753hashCodeimpl(this.disabledLabelColor)) * 31) + Color.m3753hashCodeimpl(this.errorLabelColor)) * 31) + Color.m3753hashCodeimpl(this.focusedPlaceholderColor)) * 31) + Color.m3753hashCodeimpl(this.unfocusedPlaceholderColor)) * 31) + Color.m3753hashCodeimpl(this.disabledPlaceholderColor)) * 31) + Color.m3753hashCodeimpl(this.errorPlaceholderColor)) * 31) + Color.m3753hashCodeimpl(this.focusedSupportingTextColor)) * 31) + Color.m3753hashCodeimpl(this.unfocusedSupportingTextColor)) * 31) + Color.m3753hashCodeimpl(this.disabledSupportingTextColor)) * 31) + Color.m3753hashCodeimpl(this.errorSupportingTextColor)) * 31) + Color.m3753hashCodeimpl(this.focusedPrefixColor)) * 31) + Color.m3753hashCodeimpl(this.unfocusedPrefixColor)) * 31) + Color.m3753hashCodeimpl(this.disabledPrefixColor)) * 31) + Color.m3753hashCodeimpl(this.errorPrefixColor)) * 31) + Color.m3753hashCodeimpl(this.focusedSuffixColor)) * 31) + Color.m3753hashCodeimpl(this.unfocusedSuffixColor)) * 31) + Color.m3753hashCodeimpl(this.disabledSuffixColor)) * 31) + Color.m3753hashCodeimpl(this.errorSuffixColor);
    }
}
