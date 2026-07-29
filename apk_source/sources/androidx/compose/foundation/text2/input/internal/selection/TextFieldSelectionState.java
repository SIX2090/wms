package androidx.compose.foundation.text2.input.internal.selection;

import androidx.compose.foundation.gestures.DragGestureDetectorKt;
import androidx.compose.foundation.text.Handle;
import androidx.compose.foundation.text.TextFieldCursorKt;
import androidx.compose.foundation.text.selection.SelectionAdjustment;
import androidx.compose.foundation.text.selection.SelectionLayout;
import androidx.compose.foundation.text.selection.SelectionLayoutKt;
import androidx.compose.foundation.text.selection.SelectionManagerKt;
import androidx.compose.foundation.text.selection.TextSelectionDelegateKt;
import androidx.compose.foundation.text2.input.TextFieldCharSequence;
import androidx.compose.foundation.text2.input.TextFieldCharSequenceKt;
import androidx.compose.foundation.text2.input.internal.TextLayoutState;
import androidx.compose.foundation.text2.input.internal.TextLayoutStateKt;
import androidx.compose.foundation.text2.input.internal.TransformedTextFieldState;
import androidx.compose.foundation.text2.input.internal.undo.TextFieldEditUndoBehavior;
import androidx.compose.runtime.MutableState;
import androidx.compose.runtime.SnapshotStateKt;
import androidx.compose.runtime.SnapshotStateKt__SnapshotStateKt;
import androidx.compose.runtime.State;
import androidx.compose.runtime.snapshots.Snapshot;
import androidx.compose.ui.geometry.Offset;
import androidx.compose.ui.geometry.OffsetKt;
import androidx.compose.ui.geometry.Rect;
import androidx.compose.ui.geometry.RectKt;
import androidx.compose.ui.hapticfeedback.HapticFeedback;
import androidx.compose.ui.hapticfeedback.HapticFeedbackType;
import androidx.compose.ui.input.pointer.PointerInputChange;
import androidx.compose.ui.input.pointer.PointerInputScope;
import androidx.compose.ui.layout.LayoutCoordinates;
import androidx.compose.ui.platform.ClipboardManager;
import androidx.compose.ui.platform.TextToolbar;
import androidx.compose.ui.platform.TextToolbarStatus;
import androidx.compose.ui.text.AnnotatedString;
import androidx.compose.ui.text.TextLayoutResult;
import androidx.compose.ui.text.TextRange;
import androidx.compose.ui.text.TextRangeKt;
import androidx.compose.ui.unit.Density;
import androidx.compose.ui.unit.IntSize;
import androidx.compose.ui.unit.LayoutDirection;
import kotlin.Metadata;
import kotlin.Unit;
import kotlin.coroutines.Continuation;
import kotlin.coroutines.intrinsics.IntrinsicsKt;
import kotlin.jvm.functions.Function0;
import kotlin.jvm.functions.Function1;
import kotlin.jvm.functions.Function2;
import kotlin.jvm.internal.Intrinsics;
import kotlin.jvm.internal.Ref;
import kotlin.ranges.RangesKt;
import kotlinx.coroutines.CoroutineScopeKt;
import kotlinx.coroutines.flow.FlowCollector;
import kotlinx.coroutines.flow.FlowKt;

/* compiled from: TextFieldSelectionState.kt */
@Metadata(d1 = {"\u0000¤\u0001\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010\u000b\n\u0002\b\u0004\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0018\u0002\n\u0002\b\t\n\u0002\u0018\u0002\n\u0002\b\u0004\n\u0002\u0018\u0002\n\u0002\b\u000f\n\u0002\u0018\u0002\n\u0002\b\u0006\n\u0002\u0010\b\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0011\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\b\u0007\n\u0002\u0010\u0002\n\u0002\b\f\n\u0002\u0018\u0002\n\u0002\b\u0004\n\u0002\u0018\u0002\n\u0002\b\u0013\n\u0002\u0018\u0002\n\u0002\b\u0007\n\u0002\u0018\u0002\n\u0002\b\u0006\n\u0002\u0018\u0002\n\u0002\b\b\b\u0000\u0018\u00002\u00020\u0001B5\u0012\u0006\u0010\u0002\u001a\u00020\u0003\u0012\u0006\u0010\u0004\u001a\u00020\u0005\u0012\u0006\u0010\u0006\u001a\u00020\u0007\u0012\u0006\u0010\b\u001a\u00020\t\u0012\u0006\u0010\n\u001a\u00020\t\u0012\u0006\u0010\u000b\u001a\u00020\t¢\u0006\u0002\u0010\fJ\b\u0010Z\u001a\u00020[H\u0002J\u0010\u0010\\\u001a\u00020[2\b\b\u0002\u0010]\u001a\u00020\tJ\u0006\u0010^\u001a\u00020[J\u0006\u0010_\u001a\u00020[J\u0006\u0010`\u001a\u00020[J\b\u0010a\u001a\u00020\u001eH\u0002J\u001d\u0010b\u001a\u00020\u00102\u0006\u0010c\u001a\u00020\tH\u0002ø\u0001\u0001ø\u0001\u0000¢\u0006\u0004\bd\u0010eJ\u0010\u0010f\u001a\u00020\u00142\u0006\u0010c\u001a\u00020\tH\u0002J<\u0010g\u001a\u00020h2\u0006\u0010i\u001a\u00020:2\u0006\u0010j\u001a\u00020:2\b\u0010k\u001a\u0004\u0018\u00010h2\u0006\u0010c\u001a\u00020\t2\u0006\u0010l\u001a\u00020mH\u0002ø\u0001\u0000¢\u0006\u0004\bn\u0010oJ\b\u0010p\u001a\u00020[H\u0002J\b\u0010q\u001a\u00020[H\u0002J\u000e\u0010r\u001a\u00020[H\u0086@¢\u0006\u0002\u0010sJ\u000e\u0010t\u001a\u00020[H\u0082@¢\u0006\u0002\u0010sJ\u000e\u0010u\u001a\u00020[H\u0082@¢\u0006\u0002\u0010sJ\u0006\u0010v\u001a\u00020[J\u0010\u0010w\u001a\u00020[2\u0006\u0010x\u001a\u00020\u001eH\u0002J6\u0010y\u001a\u00020[2\u0006\u00102\u001a\u0002032\u0006\u0010\r\u001a\u00020\u000e2\u0006\u0010Q\u001a\u00020R2\u0006\u0010\u0006\u001a\u00020\u00072\u0006\u0010\b\u001a\u00020\t2\u0006\u0010\n\u001a\u00020\tJ\"\u0010z\u001a\u00020[2\u0006\u0010{\u001a\u00020#2\u0006\u0010|\u001a\u00020\u0010H\u0002ø\u0001\u0000¢\u0006\u0004\b}\u0010~JN\u0010\u007f\u001a\u00020h2\b\u0010\u0080\u0001\u001a\u00030\u0081\u00012\u0007\u0010\u0082\u0001\u001a\u00020:2\u0007\u0010\u0083\u0001\u001a\u00020:2\u0006\u0010c\u001a\u00020\t2\u0006\u0010l\u001a\u00020m2\t\b\u0002\u0010\u0084\u0001\u001a\u00020\tH\u0002ø\u0001\u0001ø\u0001\u0000¢\u0006\u0006\b\u0085\u0001\u0010\u0086\u0001J\u000f\u0010\u0087\u0001\u001a\u00020[2\u0006\u0010T\u001a\u00020SJ\u0015\u0010\u0088\u0001\u001a\u00020[*\u00030\u0089\u0001H\u0086@¢\u0006\u0003\u0010\u008a\u0001J\u0015\u0010\u008b\u0001\u001a\u00020[*\u00030\u0089\u0001H\u0082@¢\u0006\u0003\u0010\u008a\u0001J\u001d\u0010\u008c\u0001\u001a\u00020[*\u00030\u0089\u00012\u0006\u0010c\u001a\u00020\tH\u0082@¢\u0006\u0003\u0010\u008d\u0001J%\u0010\u008e\u0001\u001a\u00020[*\u00030\u0089\u00012\u000e\u0010\u008f\u0001\u001a\t\u0012\u0004\u0012\u00020[0\u0090\u0001H\u0082@¢\u0006\u0003\u0010\u0091\u0001J5\u0010\u0092\u0001\u001a\u00020[*\u00030\u0089\u00012\u000e\u0010\u008f\u0001\u001a\t\u0012\u0004\u0012\u00020[0\u0090\u00012\u000e\u0010\u0093\u0001\u001a\t\u0012\u0004\u0012\u00020[0\u0090\u0001H\u0082@¢\u0006\u0003\u0010\u0094\u0001J\u0015\u0010\u0095\u0001\u001a\u00020[*\u00030\u0089\u0001H\u0082@¢\u0006\u0003\u0010\u008a\u0001J\u001d\u0010\u0096\u0001\u001a\u00020[*\u00030\u0089\u00012\u0006\u0010c\u001a\u00020\tH\u0086@¢\u0006\u0003\u0010\u008d\u0001J5\u0010\u0097\u0001\u001a\u00020[*\u00030\u0089\u00012\u000e\u0010\u008f\u0001\u001a\t\u0012\u0004\u0012\u00020[0\u0090\u00012\u000e\u0010\u0093\u0001\u001a\t\u0012\u0004\u0012\u00020[0\u0090\u0001H\u0086@¢\u0006\u0003\u0010\u0094\u0001R\u0010\u0010\r\u001a\u0004\u0018\u00010\u000eX\u0082\u000e¢\u0006\u0002\n\u0000R\u001a\u0010\u000f\u001a\u00020\u00108BX\u0082\u0004ø\u0001\u0000ø\u0001\u0001¢\u0006\u0006\u001a\u0004\b\u0011\u0010\u0012R\u001b\u0010\u0013\u001a\u00020\u00148FX\u0086\u0084\u0002¢\u0006\f\n\u0004\b\u0017\u0010\u0018\u001a\u0004\b\u0015\u0010\u0016R\u001b\u0010\u0019\u001a\u00020\t8BX\u0082\u0084\u0002¢\u0006\f\n\u0004\b\u001c\u0010\u0018\u001a\u0004\b\u001a\u0010\u001bR\u001b\u0010\u001d\u001a\u00020\u001e8FX\u0086\u0084\u0002¢\u0006\f\n\u0004\b!\u0010\u0018\u001a\u0004\b\u001f\u0010 R\u000e\u0010\u0006\u001a\u00020\u0007X\u0082\u000e¢\u0006\u0002\n\u0000R/\u0010$\u001a\u0004\u0018\u00010#2\b\u0010\"\u001a\u0004\u0018\u00010#8F@FX\u0086\u008e\u0002¢\u0006\u0012\n\u0004\b)\u0010*\u001a\u0004\b%\u0010&\"\u0004\b'\u0010(R\u0014\u0010+\u001a\u00020\t8BX\u0082\u0004¢\u0006\u0006\u001a\u0004\b,\u0010\u001bR\u000e\u0010\b\u001a\u00020\tX\u0082\u000e¢\u0006\u0002\n\u0000R\u001b\u0010-\u001a\u00020\u00148FX\u0086\u0084\u0002¢\u0006\f\n\u0004\b/\u0010\u0018\u001a\u0004\b.\u0010\u0016R\u0017\u00100\u001a\u00020\u00108Fø\u0001\u0000ø\u0001\u0001¢\u0006\u0006\u001a\u0004\b1\u0010\u0012R\u0010\u00102\u001a\u0004\u0018\u000103X\u0082\u000e¢\u0006\u0002\n\u0000R\u001a\u0010\u000b\u001a\u00020\tX\u0086\u000e¢\u0006\u000e\n\u0000\u001a\u0004\b\u000b\u0010\u001b\"\u0004\b4\u00105R+\u00106\u001a\u00020\t2\u0006\u0010\"\u001a\u00020\t8F@BX\u0086\u008e\u0002¢\u0006\u0012\n\u0004\b8\u0010*\u001a\u0004\b6\u0010\u001b\"\u0004\b7\u00105R\u000e\u00109\u001a\u00020:X\u0082\u000e¢\u0006\u0002\n\u0000R\u0010\u0010;\u001a\u0004\u0018\u00010<X\u0082\u000e¢\u0006\u0002\n\u0000R1\u0010=\u001a\u00020\u00102\u0006\u0010\"\u001a\u00020\u00108B@BX\u0082\u008e\u0002ø\u0001\u0000ø\u0001\u0001¢\u0006\u0012\n\u0004\bA\u0010*\u001a\u0004\b>\u0010\u0012\"\u0004\b?\u0010@R\u000e\u0010\n\u001a\u00020\tX\u0082\u000e¢\u0006\u0002\n\u0000R+\u0010B\u001a\u00020\t2\u0006\u0010\"\u001a\u00020\t8B@BX\u0082\u008e\u0002¢\u0006\u0012\n\u0004\bE\u0010*\u001a\u0004\bC\u0010\u001b\"\u0004\bD\u00105R1\u0010F\u001a\u00020\u00102\u0006\u0010\"\u001a\u00020\u00108B@BX\u0082\u008e\u0002ø\u0001\u0000ø\u0001\u0001¢\u0006\u0012\n\u0004\bI\u0010*\u001a\u0004\bG\u0010\u0012\"\u0004\bH\u0010@R\u001b\u0010J\u001a\u00020\u00148FX\u0086\u0084\u0002¢\u0006\f\n\u0004\bL\u0010\u0018\u001a\u0004\bK\u0010\u0016R\u000e\u0010\u0002\u001a\u00020\u0003X\u0082\u0004¢\u0006\u0002\n\u0000R\u0016\u0010M\u001a\u0004\u0018\u00010N8BX\u0082\u0004¢\u0006\u0006\u001a\u0004\bO\u0010PR\u000e\u0010\u0004\u001a\u00020\u0005X\u0082\u0004¢\u0006\u0002\n\u0000R\u0010\u0010Q\u001a\u0004\u0018\u00010RX\u0082\u000e¢\u0006\u0002\n\u0000R+\u0010T\u001a\u00020S2\u0006\u0010\"\u001a\u00020S8B@BX\u0082\u008e\u0002¢\u0006\u0012\n\u0004\bY\u0010*\u001a\u0004\bU\u0010V\"\u0004\bW\u0010X\u0082\u0002\u000b\n\u0005\b¡\u001e0\u0001\n\u0002\b!¨\u0006\u0098\u0001"}, d2 = {"Landroidx/compose/foundation/text2/input/internal/selection/TextFieldSelectionState;", "", "textFieldState", "Landroidx/compose/foundation/text2/input/internal/TransformedTextFieldState;", "textLayoutState", "Landroidx/compose/foundation/text2/input/internal/TextLayoutState;", "density", "Landroidx/compose/ui/unit/Density;", "enabled", "", "readOnly", "isFocused", "(Landroidx/compose/foundation/text2/input/internal/TransformedTextFieldState;Landroidx/compose/foundation/text2/input/internal/TextLayoutState;Landroidx/compose/ui/unit/Density;ZZZ)V", "clipboardManager", "Landroidx/compose/ui/platform/ClipboardManager;", "currentContentVisibleOffset", "Landroidx/compose/ui/geometry/Offset;", "getCurrentContentVisibleOffset-F1C5BW0", "()J", "cursorHandle", "Landroidx/compose/foundation/text2/input/internal/selection/TextFieldHandleState;", "getCursorHandle", "()Landroidx/compose/foundation/text2/input/internal/selection/TextFieldHandleState;", "cursorHandle$delegate", "Landroidx/compose/runtime/State;", "cursorHandleInBounds", "getCursorHandleInBounds", "()Z", "cursorHandleInBounds$delegate", "cursorRect", "Landroidx/compose/ui/geometry/Rect;", "getCursorRect", "()Landroidx/compose/ui/geometry/Rect;", "cursorRect$delegate", "<set-?>", "Landroidx/compose/foundation/text/Handle;", "draggingHandle", "getDraggingHandle", "()Landroidx/compose/foundation/text/Handle;", "setDraggingHandle", "(Landroidx/compose/foundation/text/Handle;)V", "draggingHandle$delegate", "Landroidx/compose/runtime/MutableState;", "editable", "getEditable", "endSelectionHandle", "getEndSelectionHandle", "endSelectionHandle$delegate", "handleDragPosition", "getHandleDragPosition-F1C5BW0", "hapticFeedBack", "Landroidx/compose/ui/hapticfeedback/HapticFeedback;", "setFocused", "(Z)V", "isInTouchMode", "setInTouchMode", "isInTouchMode$delegate", "previousRawDragOffset", "", "previousSelectionLayout", "Landroidx/compose/foundation/text/selection/SelectionLayout;", "rawHandleDragPosition", "getRawHandleDragPosition-F1C5BW0", "setRawHandleDragPosition-k-4lQ0M", "(J)V", "rawHandleDragPosition$delegate", "showCursorHandle", "getShowCursorHandle", "setShowCursorHandle", "showCursorHandle$delegate", "startContentVisibleOffset", "getStartContentVisibleOffset-F1C5BW0", "setStartContentVisibleOffset-k-4lQ0M", "startContentVisibleOffset$delegate", "startSelectionHandle", "getStartSelectionHandle", "startSelectionHandle$delegate", "textLayoutCoordinates", "Landroidx/compose/ui/layout/LayoutCoordinates;", "getTextLayoutCoordinates", "()Landroidx/compose/ui/layout/LayoutCoordinates;", "textToolbar", "Landroidx/compose/ui/platform/TextToolbar;", "Landroidx/compose/foundation/text2/input/internal/selection/TextToolbarState;", "textToolbarState", "getTextToolbarState", "()Landroidx/compose/foundation/text2/input/internal/selection/TextToolbarState;", "setTextToolbarState", "(Landroidx/compose/foundation/text2/input/internal/selection/TextToolbarState;)V", "textToolbarState$delegate", "clearHandleDragging", "", "copy", "cancelSelection", "cut", "deselect", "dispose", "getContentRect", "getHandlePosition", "isStartHandle", "getHandlePosition-tuRUvjQ", "(Z)J", "getSelectionHandleState", "getTextFieldSelection", "Landroidx/compose/ui/text/TextRange;", "rawStartOffset", "rawEndOffset", "previousSelection", "adjustment", "Landroidx/compose/foundation/text/selection/SelectionAdjustment;", "getTextFieldSelection-qeG_v_k", "(IILandroidx/compose/ui/text/TextRange;ZLandroidx/compose/foundation/text/selection/SelectionAdjustment;)J", "hideTextToolbar", "markStartContentVisibleOffset", "observeChanges", "(Lkotlin/coroutines/Continuation;)Ljava/lang/Object;", "observeTextChanges", "observeTextToolbarVisibility", "paste", "showTextToolbar", "contentRect", "update", "updateHandleDragging", "handle", "position", "updateHandleDragging-Uv8p0NA", "(Landroidx/compose/foundation/text/Handle;J)V", "updateSelection", "textFieldCharSequence", "Landroidx/compose/foundation/text2/input/TextFieldCharSequence;", "startOffset", "endOffset", "allowPreviousSelectionCollapsed", "updateSelection-QNhciaU", "(Landroidx/compose/foundation/text2/input/TextFieldCharSequence;IIZLandroidx/compose/foundation/text/selection/SelectionAdjustment;Z)J", "updateTextToolbarState", "cursorHandleGestures", "Landroidx/compose/ui/input/pointer/PointerInputScope;", "(Landroidx/compose/ui/input/pointer/PointerInputScope;Lkotlin/coroutines/Continuation;)Ljava/lang/Object;", "detectCursorHandleDragGestures", "detectSelectionHandleDragGestures", "(Landroidx/compose/ui/input/pointer/PointerInputScope;ZLkotlin/coroutines/Continuation;)Ljava/lang/Object;", "detectTextFieldLongPressAndAfterDrag", "requestFocus", "Lkotlin/Function0;", "(Landroidx/compose/ui/input/pointer/PointerInputScope;Lkotlin/jvm/functions/Function0;Lkotlin/coroutines/Continuation;)Ljava/lang/Object;", "detectTextFieldTapGestures", "showKeyboard", "(Landroidx/compose/ui/input/pointer/PointerInputScope;Lkotlin/jvm/functions/Function0;Lkotlin/jvm/functions/Function0;Lkotlin/coroutines/Continuation;)Ljava/lang/Object;", "detectTouchMode", "selectionHandleGestures", "textFieldGestures", "foundation_release"}, k = 1, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class TextFieldSelectionState {
    public static final int $stable = 8;
    private ClipboardManager clipboardManager;
    private Density density;
    private boolean enabled;
    private HapticFeedback hapticFeedBack;
    private boolean isFocused;
    private SelectionLayout previousSelectionLayout;
    private boolean readOnly;
    private final TransformedTextFieldState textFieldState;
    private final TextLayoutState textLayoutState;
    private TextToolbar textToolbar;

    /* renamed from: isInTouchMode$delegate, reason: from kotlin metadata */
    private final MutableState isInTouchMode = SnapshotStateKt__SnapshotStateKt.mutableStateOf$default(true, null, 2, null);

    /* renamed from: startContentVisibleOffset$delegate, reason: from kotlin metadata */
    private final MutableState startContentVisibleOffset = SnapshotStateKt__SnapshotStateKt.mutableStateOf$default(Offset.m3494boximpl(Offset.INSTANCE.m3520getUnspecifiedF1C5BW0()), null, 2, null);

    /* renamed from: rawHandleDragPosition$delegate, reason: from kotlin metadata */
    private final MutableState rawHandleDragPosition = SnapshotStateKt__SnapshotStateKt.mutableStateOf$default(Offset.m3494boximpl(Offset.INSTANCE.m3520getUnspecifiedF1C5BW0()), null, 2, null);

    /* renamed from: draggingHandle$delegate, reason: from kotlin metadata */
    private final MutableState draggingHandle = SnapshotStateKt__SnapshotStateKt.mutableStateOf$default(null, null, 2, null);

    /* renamed from: showCursorHandle$delegate, reason: from kotlin metadata */
    private final MutableState showCursorHandle = SnapshotStateKt__SnapshotStateKt.mutableStateOf$default(false, null, 2, null);

    /* renamed from: textToolbarState$delegate, reason: from kotlin metadata */
    private final MutableState textToolbarState = SnapshotStateKt__SnapshotStateKt.mutableStateOf$default(TextToolbarState.None, null, 2, null);
    private int previousRawDragOffset = -1;

    /* renamed from: cursorHandle$delegate, reason: from kotlin metadata */
    private final State cursorHandle = SnapshotStateKt.derivedStateOf(new Function0<TextFieldHandleState>() { // from class: androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState$cursorHandle$2
        {
            super(0);
        }

        /* JADX WARN: Can't rename method to resolve collision */
        /* JADX WARN: Code restructure failed: missing block: B:12:0x003c, code lost:
        
            if (r1 != false) goto L15;
         */
        @Override // kotlin.jvm.functions.Function0
        /*
            Code decompiled incorrectly, please refer to instructions dump.
            To view partially-correct add '--show-bad-code' argument
        */
        public final androidx.compose.foundation.text2.input.internal.selection.TextFieldHandleState invoke() {
            /*
                r10 = this;
                androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState r0 = androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState.this
                androidx.compose.foundation.text2.input.internal.TransformedTextFieldState r0 = androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState.access$getTextFieldState$p(r0)
                androidx.compose.foundation.text2.input.TextFieldCharSequence r0 = r0.getText()
                androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState r1 = androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState.this
                boolean r1 = androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState.access$getShowCursorHandle(r1)
                r2 = 0
                if (r1 == 0) goto L40
                long r3 = r0.getSelectionInChars()
                boolean r1 = androidx.compose.ui.text.TextRange.m5565getCollapsedimpl(r3)
                if (r1 == 0) goto L40
                r1 = r0
                java.lang.CharSequence r1 = (java.lang.CharSequence) r1
                int r1 = r1.length()
                r3 = 1
                if (r1 <= 0) goto L29
                r1 = r3
                goto L2a
            L29:
                r1 = r2
            L2a:
                if (r1 == 0) goto L40
                androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState r1 = androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState.this
                androidx.compose.foundation.text.Handle r1 = r1.getDraggingHandle()
                androidx.compose.foundation.text.Handle r4 = androidx.compose.foundation.text.Handle.Cursor
                if (r1 == r4) goto L3e
                androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState r1 = androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState.this
                boolean r1 = androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState.access$getCursorHandleInBounds(r1)
                if (r1 == 0) goto L40
            L3e:
                r2 = r3
                goto L41
            L40:
            L41:
                r1 = r2
                if (r1 != 0) goto L4b
                androidx.compose.foundation.text2.input.internal.selection.TextFieldHandleState$Companion r2 = androidx.compose.foundation.text2.input.internal.selection.TextFieldHandleState.INSTANCE
                androidx.compose.foundation.text2.input.internal.selection.TextFieldHandleState r2 = r2.getHidden()
                return r2
            L4b:
                androidx.compose.foundation.text2.input.internal.selection.TextFieldHandleState r2 = new androidx.compose.foundation.text2.input.internal.selection.TextFieldHandleState
                androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState r3 = androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState.this
                androidx.compose.ui.geometry.Rect r3 = r3.getCursorRect()
                long r5 = r3.m3532getBottomCenterF1C5BW0()
                androidx.compose.ui.text.style.ResolvedTextDirection r7 = androidx.compose.ui.text.style.ResolvedTextDirection.Ltr
                r4 = 1
                r8 = 0
                r9 = 0
                r3 = r2
                r3.<init>(r4, r5, r7, r8, r9)
                return r2
            */
            throw new UnsupportedOperationException("Method not decompiled: androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState$cursorHandle$2.invoke():androidx.compose.foundation.text2.input.internal.selection.TextFieldHandleState");
        }
    });

    /* renamed from: cursorHandleInBounds$delegate, reason: from kotlin metadata */
    private final State cursorHandleInBounds = SnapshotStateKt.derivedStateOf(SnapshotStateKt.structuralEqualityPolicy(), new Function0<Boolean>() { // from class: androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState$cursorHandleInBounds$2
        {
            super(0);
        }

        /* JADX WARN: Can't rename method to resolve collision */
        @Override // kotlin.jvm.functions.Function0
        public final Boolean invoke() {
            LayoutCoordinates textLayoutCoordinates;
            Rect visibleBounds;
            Snapshot.Companion this_$iv = Snapshot.INSTANCE;
            TextFieldSelectionState textFieldSelectionState = TextFieldSelectionState.this;
            Snapshot snapshot$iv = this_$iv.createNonObservableSnapshot();
            try {
                Snapshot previous$iv$iv = snapshot$iv.makeCurrent();
                try {
                    long position = textFieldSelectionState.getCursorRect().m3532getBottomCenterF1C5BW0();
                    snapshot$iv.dispose();
                    textLayoutCoordinates = TextFieldSelectionState.this.getTextLayoutCoordinates();
                    return Boolean.valueOf((textLayoutCoordinates == null || (visibleBounds = SelectionManagerKt.visibleBounds(textLayoutCoordinates)) == null) ? false : SelectionManagerKt.m1041containsInclusiveUv8p0NA(visibleBounds, position));
                } finally {
                    snapshot$iv.restoreCurrent(previous$iv$iv);
                }
            } catch (Throwable th) {
                snapshot$iv.dispose();
                throw th;
            }
        }
    });

    /* renamed from: cursorRect$delegate, reason: from kotlin metadata */
    private final State cursorRect = SnapshotStateKt.derivedStateOf(new Function0<Rect>() { // from class: androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState$cursorRect$2
        {
            super(0);
        }

        /* JADX WARN: Can't rename method to resolve collision */
        @Override // kotlin.jvm.functions.Function0
        public final Rect invoke() {
            TextLayoutState textLayoutState;
            TransformedTextFieldState transformedTextFieldState;
            Density $this$invoke_u24lambda_u240;
            float cursorCenterX;
            textLayoutState = TextFieldSelectionState.this.textLayoutState;
            TextLayoutResult layoutResult = textLayoutState.getLayoutResult();
            if (layoutResult == null) {
                return Rect.INSTANCE.getZero();
            }
            transformedTextFieldState = TextFieldSelectionState.this.textFieldState;
            TextFieldCharSequence value = transformedTextFieldState.getText();
            if (!TextRange.m5565getCollapsedimpl(value.getSelectionInChars())) {
                return Rect.INSTANCE.getZero();
            }
            Rect cursorRect = layoutResult.getCursorRect(TextRange.m5571getStartimpl(value.getSelectionInChars()));
            $this$invoke_u24lambda_u240 = TextFieldSelectionState.this.density;
            float cursorWidth = $this$invoke_u24lambda_u240.mo313toPx0680j_4(TextFieldCursorKt.getDefaultCursorThickness());
            if (layoutResult.getLayoutInput().getLayoutDirection() == LayoutDirection.Ltr) {
                cursorCenterX = cursorRect.getLeft() + (cursorWidth / 2);
            } else {
                cursorCenterX = cursorRect.getRight() - (cursorWidth / 2);
            }
            float f = 2;
            float coercedCursorCenterX = RangesKt.coerceAtLeast(RangesKt.coerceAtMost(cursorCenterX, IntSize.m6264getWidthimpl(layoutResult.getSize()) - (cursorWidth / f)), cursorWidth / f);
            return new Rect(coercedCursorCenterX - (cursorWidth / f), cursorRect.getTop(), (cursorWidth / f) + coercedCursorCenterX, cursorRect.getBottom());
        }
    });

    /* renamed from: startSelectionHandle$delegate, reason: from kotlin metadata */
    private final State startSelectionHandle = SnapshotStateKt.derivedStateOf(new Function0<TextFieldHandleState>() { // from class: androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState$startSelectionHandle$2
        {
            super(0);
        }

        /* JADX WARN: Can't rename method to resolve collision */
        @Override // kotlin.jvm.functions.Function0
        public final TextFieldHandleState invoke() {
            TextFieldHandleState selectionHandleState;
            selectionHandleState = TextFieldSelectionState.this.getSelectionHandleState(true);
            return selectionHandleState;
        }
    });

    /* renamed from: endSelectionHandle$delegate, reason: from kotlin metadata */
    private final State endSelectionHandle = SnapshotStateKt.derivedStateOf(new Function0<TextFieldHandleState>() { // from class: androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState$endSelectionHandle$2
        {
            super(0);
        }

        /* JADX WARN: Can't rename method to resolve collision */
        @Override // kotlin.jvm.functions.Function0
        public final TextFieldHandleState invoke() {
            TextFieldHandleState selectionHandleState;
            selectionHandleState = TextFieldSelectionState.this.getSelectionHandleState(false);
            return selectionHandleState;
        }
    });

    public TextFieldSelectionState(TransformedTextFieldState textFieldState, TextLayoutState textLayoutState, Density density, boolean enabled, boolean readOnly, boolean isFocused) {
        this.textFieldState = textFieldState;
        this.textLayoutState = textLayoutState;
        this.density = density;
        this.enabled = enabled;
        this.readOnly = readOnly;
        this.isFocused = isFocused;
    }

    /* renamed from: isFocused, reason: from getter */
    public final boolean getIsFocused() {
        return this.isFocused;
    }

    public final void setFocused(boolean z) {
        this.isFocused = z;
    }

    /* JADX INFO: Access modifiers changed from: private */
    public final void setInTouchMode(boolean z) {
        MutableState $this$setValue$iv = this.isInTouchMode;
        $this$setValue$iv.setValue(Boolean.valueOf(z));
    }

    public final boolean isInTouchMode() {
        State $this$getValue$iv = this.isInTouchMode;
        return ((Boolean) $this$getValue$iv.getValue()).booleanValue();
    }

    /* renamed from: getStartContentVisibleOffset-F1C5BW0, reason: not valid java name */
    private final long m1183getStartContentVisibleOffsetF1C5BW0() {
        State $this$getValue$iv = this.startContentVisibleOffset;
        return ((Offset) $this$getValue$iv.getValue()).getPackedValue();
    }

    /* renamed from: setStartContentVisibleOffset-k-4lQ0M, reason: not valid java name */
    private final void m1186setStartContentVisibleOffsetk4lQ0M(long j) {
        MutableState $this$setValue$iv = this.startContentVisibleOffset;
        $this$setValue$iv.setValue(Offset.m3494boximpl(j));
    }

    /* renamed from: getCurrentContentVisibleOffset-F1C5BW0, reason: not valid java name */
    private final long m1180getCurrentContentVisibleOffsetF1C5BW0() {
        Rect visibleBounds;
        LayoutCoordinates textLayoutCoordinates = getTextLayoutCoordinates();
        return (textLayoutCoordinates == null || (visibleBounds = SelectionManagerKt.visibleBounds(textLayoutCoordinates)) == null) ? Offset.INSTANCE.m3520getUnspecifiedF1C5BW0() : visibleBounds.m3540getTopLeftF1C5BW0();
    }

    /* renamed from: getRawHandleDragPosition-F1C5BW0, reason: not valid java name */
    private final long m1182getRawHandleDragPositionF1C5BW0() {
        State $this$getValue$iv = this.rawHandleDragPosition;
        return ((Offset) $this$getValue$iv.getValue()).getPackedValue();
    }

    /* renamed from: setRawHandleDragPosition-k-4lQ0M, reason: not valid java name */
    private final void m1185setRawHandleDragPositionk4lQ0M(long j) {
        MutableState $this$setValue$iv = this.rawHandleDragPosition;
        $this$setValue$iv.setValue(Offset.m3494boximpl(j));
    }

    /* renamed from: getHandleDragPosition-F1C5BW0, reason: not valid java name */
    public final long m1190getHandleDragPositionF1C5BW0() {
        if (OffsetKt.m3526isUnspecifiedk4lQ0M(m1182getRawHandleDragPositionF1C5BW0())) {
            return Offset.INSTANCE.m3520getUnspecifiedF1C5BW0();
        }
        if (OffsetKt.m3526isUnspecifiedk4lQ0M(m1183getStartContentVisibleOffsetF1C5BW0())) {
            return TextLayoutStateKt.m1148fromDecorationToTextLayoutUv8p0NA(this.textLayoutState, m1182getRawHandleDragPositionF1C5BW0());
        }
        return Offset.m3509minusMKHz9U(Offset.m3510plusMKHz9U(m1182getRawHandleDragPositionF1C5BW0(), m1180getCurrentContentVisibleOffsetF1C5BW0()), m1183getStartContentVisibleOffsetF1C5BW0());
    }

    public final Handle getDraggingHandle() {
        State $this$getValue$iv = this.draggingHandle;
        return (Handle) $this$getValue$iv.getValue();
    }

    public final void setDraggingHandle(Handle handle) {
        MutableState $this$setValue$iv = this.draggingHandle;
        $this$setValue$iv.setValue(handle);
    }

    /* JADX INFO: Access modifiers changed from: private */
    public final boolean getShowCursorHandle() {
        State $this$getValue$iv = this.showCursorHandle;
        return ((Boolean) $this$getValue$iv.getValue()).booleanValue();
    }

    /* JADX INFO: Access modifiers changed from: private */
    public final void setShowCursorHandle(boolean z) {
        MutableState $this$setValue$iv = this.showCursorHandle;
        $this$setValue$iv.setValue(Boolean.valueOf(z));
    }

    /* JADX INFO: Access modifiers changed from: private */
    public final TextToolbarState getTextToolbarState() {
        State $this$getValue$iv = this.textToolbarState;
        return (TextToolbarState) $this$getValue$iv.getValue();
    }

    /* JADX INFO: Access modifiers changed from: private */
    public final void setTextToolbarState(TextToolbarState textToolbarState) {
        MutableState $this$setValue$iv = this.textToolbarState;
        $this$setValue$iv.setValue(textToolbarState);
    }

    /* JADX INFO: Access modifiers changed from: private */
    public final LayoutCoordinates getTextLayoutCoordinates() {
        LayoutCoordinates it = this.textLayoutState.getTextLayoutNodeCoordinates();
        if (it == null || !it.isAttached()) {
            return null;
        }
        return it;
    }

    /* JADX INFO: Access modifiers changed from: private */
    public final boolean getEditable() {
        return this.enabled && !this.readOnly;
    }

    public final TextFieldHandleState getCursorHandle() {
        State $this$getValue$iv = this.cursorHandle;
        return (TextFieldHandleState) $this$getValue$iv.getValue();
    }

    /* JADX INFO: Access modifiers changed from: private */
    public final boolean getCursorHandleInBounds() {
        State $this$getValue$iv = this.cursorHandleInBounds;
        return ((Boolean) $this$getValue$iv.getValue()).booleanValue();
    }

    public final Rect getCursorRect() {
        State $this$getValue$iv = this.cursorRect;
        return (Rect) $this$getValue$iv.getValue();
    }

    public final TextFieldHandleState getStartSelectionHandle() {
        State $this$getValue$iv = this.startSelectionHandle;
        return (TextFieldHandleState) $this$getValue$iv.getValue();
    }

    public final TextFieldHandleState getEndSelectionHandle() {
        State $this$getValue$iv = this.endSelectionHandle;
        return (TextFieldHandleState) $this$getValue$iv.getValue();
    }

    public final void update(HapticFeedback hapticFeedBack, ClipboardManager clipboardManager, TextToolbar textToolbar, Density density, boolean enabled, boolean readOnly) {
        if (!enabled) {
            hideTextToolbar();
        }
        this.hapticFeedBack = hapticFeedBack;
        this.clipboardManager = clipboardManager;
        this.textToolbar = textToolbar;
        this.density = density;
        this.enabled = enabled;
        this.readOnly = readOnly;
    }

    public final Object cursorHandleGestures(PointerInputScope $this$cursorHandleGestures, Continuation<? super Unit> continuation) {
        Object coroutineScope = CoroutineScopeKt.coroutineScope(new TextFieldSelectionState$cursorHandleGestures$2(this, $this$cursorHandleGestures, null), continuation);
        return coroutineScope == IntrinsicsKt.getCOROUTINE_SUSPENDED() ? coroutineScope : Unit.INSTANCE;
    }

    public final Object textFieldGestures(PointerInputScope $this$textFieldGestures, Function0<Unit> function0, Function0<Unit> function02, Continuation<? super Unit> continuation) {
        Object coroutineScope = CoroutineScopeKt.coroutineScope(new TextFieldSelectionState$textFieldGestures$2(this, $this$textFieldGestures, function0, function02, null), continuation);
        return coroutineScope == IntrinsicsKt.getCOROUTINE_SUSPENDED() ? coroutineScope : Unit.INSTANCE;
    }

    public final Object selectionHandleGestures(PointerInputScope $this$selectionHandleGestures, boolean isStartHandle, Continuation<? super Unit> continuation) {
        Object coroutineScope = CoroutineScopeKt.coroutineScope(new TextFieldSelectionState$selectionHandleGestures$2(this, $this$selectionHandleGestures, isStartHandle, null), continuation);
        return coroutineScope == IntrinsicsKt.getCOROUTINE_SUSPENDED() ? coroutineScope : Unit.INSTANCE;
    }

    /* JADX WARN: Removed duplicated region for block: B:11:0x002f  */
    /* JADX WARN: Removed duplicated region for block: B:16:0x005e  */
    /* JADX WARN: Removed duplicated region for block: B:23:0x0074  */
    /* JADX WARN: Removed duplicated region for block: B:25:0x0039  */
    /* JADX WARN: Removed duplicated region for block: B:8:0x0026  */
    /*
        Code decompiled incorrectly, please refer to instructions dump.
        To view partially-correct add '--show-bad-code' argument
    */
    public final java.lang.Object observeChanges(kotlin.coroutines.Continuation<? super kotlin.Unit> r8) {
        /*
            r7 = this;
            boolean r0 = r8 instanceof androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState$observeChanges$1
            if (r0 == 0) goto L14
            r0 = r8
            androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState$observeChanges$1 r0 = (androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState$observeChanges$1) r0
            int r1 = r0.label
            r2 = -2147483648(0xffffffff80000000, float:-0.0)
            r1 = r1 & r2
            if (r1 == 0) goto L14
            int r8 = r0.label
            int r8 = r8 - r2
            r0.label = r8
            goto L19
        L14:
            androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState$observeChanges$1 r0 = new androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState$observeChanges$1
            r0.<init>(r7, r8)
        L19:
            r8 = r0
            java.lang.Object r0 = r8.result
            java.lang.Object r1 = kotlin.coroutines.intrinsics.IntrinsicsKt.getCOROUTINE_SUSPENDED()
            int r2 = r8.label
            r3 = 0
            switch(r2) {
                case 0: goto L39;
                case 1: goto L2f;
                default: goto L26;
            }
        L26:
            java.lang.IllegalStateException r8 = new java.lang.IllegalStateException
            java.lang.String r0 = "call to 'resume' before 'invoke' with coroutine"
            r8.<init>(r0)
            throw r8
        L2f:
            java.lang.Object r1 = r8.L$0
            androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState r1 = (androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState) r1
            kotlin.ResultKt.throwOnFailure(r0)     // Catch: java.lang.Throwable -> L37
            goto L53
        L37:
            r2 = move-exception
            goto L69
        L39:
            kotlin.ResultKt.throwOnFailure(r0)
            r2 = r7
            androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState$observeChanges$2 r4 = new androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState$observeChanges$2     // Catch: java.lang.Throwable -> L65
            r5 = 0
            r4.<init>(r2, r5)     // Catch: java.lang.Throwable -> L65
            kotlin.jvm.functions.Function2 r4 = (kotlin.jvm.functions.Function2) r4     // Catch: java.lang.Throwable -> L65
            r8.L$0 = r2     // Catch: java.lang.Throwable -> L65
            r5 = 1
            r8.label = r5     // Catch: java.lang.Throwable -> L65
            java.lang.Object r4 = kotlinx.coroutines.CoroutineScopeKt.coroutineScope(r4, r8)     // Catch: java.lang.Throwable -> L65
            if (r4 != r1) goto L52
            return r1
        L52:
            r1 = r2
        L53:
            r1.setShowCursorHandle(r3)
            androidx.compose.foundation.text2.input.internal.selection.TextToolbarState r2 = r1.getTextToolbarState()
            androidx.compose.foundation.text2.input.internal.selection.TextToolbarState r3 = androidx.compose.foundation.text2.input.internal.selection.TextToolbarState.None
            if (r2 == r3) goto L61
            r1.hideTextToolbar()
        L61:
            kotlin.Unit r1 = kotlin.Unit.INSTANCE
            return r1
        L65:
            r1 = move-exception
            r6 = r2
            r2 = r1
            r1 = r6
        L69:
            r1.setShowCursorHandle(r3)
            androidx.compose.foundation.text2.input.internal.selection.TextToolbarState r3 = r1.getTextToolbarState()
            androidx.compose.foundation.text2.input.internal.selection.TextToolbarState r4 = androidx.compose.foundation.text2.input.internal.selection.TextToolbarState.None
            if (r3 == r4) goto L77
            r1.hideTextToolbar()
        L77:
            throw r2
        */
        throw new UnsupportedOperationException("Method not decompiled: androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState.observeChanges(kotlin.coroutines.Continuation):java.lang.Object");
    }

    public final void updateTextToolbarState(TextToolbarState textToolbarState) {
        setTextToolbarState(textToolbarState);
    }

    public final void dispose() {
        hideTextToolbar();
        this.textToolbar = null;
        this.clipboardManager = null;
        this.hapticFeedBack = null;
    }

    /* JADX INFO: Access modifiers changed from: private */
    public final Object detectTouchMode(PointerInputScope $this$detectTouchMode, Continuation<? super Unit> continuation) {
        Object awaitPointerEventScope = $this$detectTouchMode.awaitPointerEventScope(new TextFieldSelectionState$detectTouchMode$2(this, null), continuation);
        return awaitPointerEventScope == IntrinsicsKt.getCOROUTINE_SUSPENDED() ? awaitPointerEventScope : Unit.INSTANCE;
    }

    /* JADX INFO: Access modifiers changed from: private */
    public final Object detectTextFieldTapGestures(PointerInputScope $this$detectTextFieldTapGestures, final Function0<Unit> function0, final Function0<Unit> function02, Continuation<? super Unit> continuation) {
        Object detectTapAndDoubleTap = TapAndDoubleTapGestureKt.detectTapAndDoubleTap($this$detectTextFieldTapGestures, new TapOnPosition() { // from class: androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState$detectTextFieldTapGestures$2
            @Override // androidx.compose.foundation.text2.input.internal.selection.TapOnPosition
            /* renamed from: onEvent-k-4lQ0M */
            public final void mo1163onEventk4lQ0M(long offset) {
                boolean editable;
                TransformedTextFieldState transformedTextFieldState;
                TextLayoutState textLayoutState;
                TransformedTextFieldState transformedTextFieldState2;
                TextFieldSelectionStateKt.logDebug(new Function0<String>() { // from class: androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState$detectTextFieldTapGestures$2.1
                    @Override // kotlin.jvm.functions.Function0
                    public final String invoke() {
                        return "onTapTextField";
                    }
                });
                function0.invoke();
                editable = this.getEditable();
                if (editable && this.getIsFocused()) {
                    function02.invoke();
                    transformedTextFieldState = this.textFieldState;
                    if (transformedTextFieldState.getText().length() > 0) {
                        this.setShowCursorHandle(true);
                    }
                    this.updateTextToolbarState(TextToolbarState.None);
                    textLayoutState = this.textLayoutState;
                    int cursorIndex = TextLayoutState.m1141getOffsetForPosition3MmeM6k$default(textLayoutState, offset, false, 2, null);
                    if (cursorIndex >= 0) {
                        transformedTextFieldState2 = this.textFieldState;
                        transformedTextFieldState2.placeCursorBeforeCharAt(cursorIndex);
                    }
                }
            }
        }, new TapOnPosition() { // from class: androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState$detectTextFieldTapGestures$3
            @Override // androidx.compose.foundation.text2.input.internal.selection.TapOnPosition
            /* renamed from: onEvent-k-4lQ0M */
            public final void mo1163onEventk4lQ0M(long offset) {
                TextLayoutState textLayoutState;
                TransformedTextFieldState transformedTextFieldState;
                TransformedTextFieldState transformedTextFieldState2;
                TextFieldSelectionStateKt.logDebug(new Function0<String>() { // from class: androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState$detectTextFieldTapGestures$3.1
                    @Override // kotlin.jvm.functions.Function0
                    public final String invoke() {
                        return "onDoubleTapTextField";
                    }
                });
                TextFieldSelectionState.this.setShowCursorHandle(false);
                TextFieldSelectionState.this.updateTextToolbarState(TextToolbarState.Selection);
                textLayoutState = TextFieldSelectionState.this.textLayoutState;
                int index = TextLayoutState.m1141getOffsetForPosition3MmeM6k$default(textLayoutState, offset, false, 2, null);
                TextFieldSelectionState textFieldSelectionState = TextFieldSelectionState.this;
                transformedTextFieldState = TextFieldSelectionState.this.textFieldState;
                long newSelection = TextFieldSelectionState.m1189updateSelectionQNhciaU$default(textFieldSelectionState, TextFieldCharSequenceKt.m1088TextFieldCharSequence3r_uNRQ$default(transformedTextFieldState.getText(), TextRange.INSTANCE.m5576getZerod9O1mEE(), null, 4, null), index, index, false, SelectionAdjustment.INSTANCE.getWord(), false, 32, null);
                transformedTextFieldState2 = TextFieldSelectionState.this.textFieldState;
                transformedTextFieldState2.m1157selectCharsIn5zctL8(newSelection);
            }
        }, continuation);
        return detectTapAndDoubleTap == IntrinsicsKt.getCOROUTINE_SUSPENDED() ? detectTapAndDoubleTap : Unit.INSTANCE;
    }

    /* JADX INFO: Access modifiers changed from: private */
    /* JADX WARN: Removed duplicated region for block: B:11:0x002e  */
    /* JADX WARN: Removed duplicated region for block: B:20:0x0040  */
    /* JADX WARN: Removed duplicated region for block: B:8:0x0025  */
    /*
        Code decompiled incorrectly, please refer to instructions dump.
        To view partially-correct add '--show-bad-code' argument
    */
    public final java.lang.Object detectCursorHandleDragGestures(androidx.compose.ui.input.pointer.PointerInputScope r11, kotlin.coroutines.Continuation<? super kotlin.Unit> r12) {
        /*
            r10 = this;
            boolean r0 = r12 instanceof androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState$detectCursorHandleDragGestures$1
            if (r0 == 0) goto L14
            r0 = r12
            androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState$detectCursorHandleDragGestures$1 r0 = (androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState$detectCursorHandleDragGestures$1) r0
            int r1 = r0.label
            r2 = -2147483648(0xffffffff80000000, float:-0.0)
            r1 = r1 & r2
            if (r1 == 0) goto L14
            int r12 = r0.label
            int r12 = r12 - r2
            r0.label = r12
            goto L19
        L14:
            androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState$detectCursorHandleDragGestures$1 r0 = new androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState$detectCursorHandleDragGestures$1
            r0.<init>(r10, r12)
        L19:
            r12 = r0
            java.lang.Object r6 = r12.result
            java.lang.Object r7 = kotlin.coroutines.intrinsics.IntrinsicsKt.getCOROUTINE_SUSPENDED()
            int r0 = r12.label
            switch(r0) {
                case 0: goto L40;
                case 1: goto L2e;
                default: goto L25;
            }
        L25:
            java.lang.IllegalStateException r11 = new java.lang.IllegalStateException
            java.lang.String r12 = "call to 'resume' before 'invoke' with coroutine"
            r11.<init>(r12)
            throw r11
        L2e:
            java.lang.Object r11 = r12.L$2
            kotlin.jvm.internal.Ref$LongRef r11 = (kotlin.jvm.internal.Ref.LongRef) r11
            java.lang.Object r0 = r12.L$1
            kotlin.jvm.internal.Ref$LongRef r0 = (kotlin.jvm.internal.Ref.LongRef) r0
            java.lang.Object r1 = r12.L$0
            androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState r1 = (androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState) r1
            kotlin.ResultKt.throwOnFailure(r6)     // Catch: java.lang.Throwable -> L3e
            goto L91
        L3e:
            r2 = move-exception
            goto L9c
        L40:
            kotlin.ResultKt.throwOnFailure(r6)
            r8 = r10
            r0 = r11
            kotlin.jvm.internal.Ref$LongRef r11 = new kotlin.jvm.internal.Ref$LongRef
            r11.<init>()
            androidx.compose.ui.geometry.Offset$Companion r1 = androidx.compose.ui.geometry.Offset.INSTANCE
            long r1 = r1.m3520getUnspecifiedF1C5BW0()
            r11.element = r1
            kotlin.jvm.internal.Ref$LongRef r1 = new kotlin.jvm.internal.Ref$LongRef
            r1.<init>()
            r9 = r1
            androidx.compose.ui.geometry.Offset$Companion r1 = androidx.compose.ui.geometry.Offset.INSTANCE
            long r1 = r1.m3520getUnspecifiedF1C5BW0()
            r9.element = r1
            androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState$detectCursorHandleDragGestures$2 r1 = new androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState$detectCursorHandleDragGestures$2     // Catch: java.lang.Throwable -> L98
            r1.<init>()     // Catch: java.lang.Throwable -> L98
            kotlin.jvm.functions.Function1 r1 = (kotlin.jvm.functions.Function1) r1     // Catch: java.lang.Throwable -> L98
            androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState$detectCursorHandleDragGestures$3 r2 = new androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState$detectCursorHandleDragGestures$3     // Catch: java.lang.Throwable -> L98
            r2.<init>()     // Catch: java.lang.Throwable -> L98
            kotlin.jvm.functions.Function0 r2 = (kotlin.jvm.functions.Function0) r2     // Catch: java.lang.Throwable -> L98
            androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState$detectCursorHandleDragGestures$4 r3 = new androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState$detectCursorHandleDragGestures$4     // Catch: java.lang.Throwable -> L98
            r3.<init>()     // Catch: java.lang.Throwable -> L98
            kotlin.jvm.functions.Function0 r3 = (kotlin.jvm.functions.Function0) r3     // Catch: java.lang.Throwable -> L98
            androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState$detectCursorHandleDragGestures$5 r4 = new androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState$detectCursorHandleDragGestures$5     // Catch: java.lang.Throwable -> L98
            r4.<init>()     // Catch: java.lang.Throwable -> L98
            kotlin.jvm.functions.Function2 r4 = (kotlin.jvm.functions.Function2) r4     // Catch: java.lang.Throwable -> L98
            r12.L$0 = r8     // Catch: java.lang.Throwable -> L98
            r12.L$1 = r11     // Catch: java.lang.Throwable -> L98
            r12.L$2 = r9     // Catch: java.lang.Throwable -> L98
            r5 = 1
            r12.label = r5     // Catch: java.lang.Throwable -> L98
            r5 = r12
            java.lang.Object r1 = androidx.compose.foundation.gestures.DragGestureDetectorKt.detectDragGestures(r0, r1, r2, r3, r4, r5)     // Catch: java.lang.Throwable -> L98
            if (r1 != r7) goto L8e
            return r7
        L8e:
            r0 = r11
            r1 = r8
            r11 = r9
        L91:
            detectCursorHandleDragGestures$onDragStop(r0, r11, r1)
            kotlin.Unit r2 = kotlin.Unit.INSTANCE
            return r2
        L98:
            r2 = move-exception
            r0 = r11
            r1 = r8
            r11 = r9
        L9c:
            detectCursorHandleDragGestures$onDragStop(r0, r11, r1)
            throw r2
        */
        throw new UnsupportedOperationException("Method not decompiled: androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState.detectCursorHandleDragGestures(androidx.compose.ui.input.pointer.PointerInputScope, kotlin.coroutines.Continuation):java.lang.Object");
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final void detectCursorHandleDragGestures$onDragStop(Ref.LongRef cursorDragStart, Ref.LongRef cursorDragDelta, TextFieldSelectionState this$0) {
        if (OffsetKt.m3524isSpecifiedk4lQ0M(cursorDragStart.element)) {
            cursorDragStart.element = Offset.INSTANCE.m3520getUnspecifiedF1C5BW0();
            cursorDragDelta.element = Offset.INSTANCE.m3520getUnspecifiedF1C5BW0();
            this$0.clearHandleDragging();
        }
    }

    /* JADX INFO: Access modifiers changed from: private */
    /* JADX WARN: Type inference failed for: r0v9, types: [T, androidx.compose.foundation.text.Handle] */
    public final Object detectTextFieldLongPressAndAfterDrag(PointerInputScope $this$detectTextFieldLongPressAndAfterDrag, final Function0<Unit> function0, Continuation<? super Unit> continuation) {
        final Ref.IntRef dragBeginOffsetInText = new Ref.IntRef();
        dragBeginOffsetInText.element = -1;
        final Ref.LongRef dragBeginPosition = new Ref.LongRef();
        dragBeginPosition.element = Offset.INSTANCE.m3520getUnspecifiedF1C5BW0();
        final Ref.LongRef dragTotalDistance = new Ref.LongRef();
        dragTotalDistance.element = Offset.INSTANCE.m3521getZeroF1C5BW0();
        final Ref.ObjectRef actingHandle = new Ref.ObjectRef();
        actingHandle.element = Handle.SelectionEnd;
        Object detectDragGesturesAfterLongPress = DragGestureDetectorKt.detectDragGesturesAfterLongPress($this$detectTextFieldLongPressAndAfterDrag, new Function1<Offset, Unit>() { // from class: androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState$detectTextFieldLongPressAndAfterDrag$2
            /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
            {
                super(1);
            }

            @Override // kotlin.jvm.functions.Function1
            public /* bridge */ /* synthetic */ Unit invoke(Offset offset) {
                m1196invokek4lQ0M(offset.getPackedValue());
                return Unit.INSTANCE;
            }

            /* renamed from: invoke-k-4lQ0M, reason: not valid java name */
            public final void m1196invokek4lQ0M(final long dragStartOffset) {
                TextLayoutState textLayoutState;
                TransformedTextFieldState transformedTextFieldState;
                TextLayoutState textLayoutState2;
                TransformedTextFieldState transformedTextFieldState2;
                TransformedTextFieldState transformedTextFieldState3;
                TextLayoutState textLayoutState3;
                HapticFeedback hapticFeedback;
                TransformedTextFieldState transformedTextFieldState4;
                TextFieldSelectionStateKt.logDebug(new Function0<String>() { // from class: androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState$detectTextFieldLongPressAndAfterDrag$2.1
                    /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
                    {
                        super(0);
                    }

                    @Override // kotlin.jvm.functions.Function0
                    public final String invoke() {
                        return "onDragStart after longPress " + ((Object) Offset.m3513toStringimpl(dragStartOffset));
                    }
                });
                function0.invoke();
                this.m1187updateHandleDraggingUv8p0NA(actingHandle.element, dragStartOffset);
                dragBeginPosition.element = dragStartOffset;
                dragTotalDistance.element = Offset.INSTANCE.m3521getZeroF1C5BW0();
                this.previousRawDragOffset = -1;
                textLayoutState = this.textLayoutState;
                if (!textLayoutState.m1144isPositionOnTextk4lQ0M(dragStartOffset)) {
                    textLayoutState3 = this.textLayoutState;
                    int offset = TextLayoutState.m1141getOffsetForPosition3MmeM6k$default(textLayoutState3, dragStartOffset, false, 2, null);
                    hapticFeedback = this.hapticFeedBack;
                    if (hapticFeedback != null) {
                        hapticFeedback.mo4417performHapticFeedbackCdsT49E(HapticFeedbackType.INSTANCE.m4426getTextHandleMove5zf0vsI());
                    }
                    transformedTextFieldState4 = this.textFieldState;
                    transformedTextFieldState4.placeCursorBeforeCharAt(offset);
                    this.setShowCursorHandle(true);
                    this.updateTextToolbarState(TextToolbarState.Cursor);
                    return;
                }
                transformedTextFieldState = this.textFieldState;
                if (transformedTextFieldState.getText().length() == 0) {
                    return;
                }
                textLayoutState2 = this.textLayoutState;
                int offset2 = TextLayoutState.m1141getOffsetForPosition3MmeM6k$default(textLayoutState2, dragStartOffset, false, 2, null);
                TextFieldSelectionState textFieldSelectionState = this;
                transformedTextFieldState2 = this.textFieldState;
                long newSelection = TextFieldSelectionState.m1189updateSelectionQNhciaU$default(textFieldSelectionState, TextFieldCharSequenceKt.m1088TextFieldCharSequence3r_uNRQ$default(transformedTextFieldState2.getText(), TextRange.INSTANCE.m5576getZerod9O1mEE(), null, 4, null), offset2, offset2, false, SelectionAdjustment.INSTANCE.getCharacterWithWordAccelerate(), false, 32, null);
                transformedTextFieldState3 = this.textFieldState;
                transformedTextFieldState3.m1157selectCharsIn5zctL8(newSelection);
                this.updateTextToolbarState(TextToolbarState.Selection);
                dragBeginOffsetInText.element = TextRange.m5571getStartimpl(newSelection);
            }
        }, new Function0<Unit>() { // from class: androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState$detectTextFieldLongPressAndAfterDrag$3
            /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
            {
                super(0);
            }

            @Override // kotlin.jvm.functions.Function0
            public /* bridge */ /* synthetic */ Unit invoke() {
                invoke2();
                return Unit.INSTANCE;
            }

            /* renamed from: invoke, reason: avoid collision after fix types in other method */
            public final void invoke2() {
                TextFieldSelectionState.detectTextFieldLongPressAndAfterDrag$onDragStop$1(Ref.LongRef.this, this, dragBeginOffsetInText, dragTotalDistance);
            }
        }, new Function0<Unit>() { // from class: androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState$detectTextFieldLongPressAndAfterDrag$4
            /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
            {
                super(0);
            }

            @Override // kotlin.jvm.functions.Function0
            public /* bridge */ /* synthetic */ Unit invoke() {
                invoke2();
                return Unit.INSTANCE;
            }

            /* renamed from: invoke, reason: avoid collision after fix types in other method */
            public final void invoke2() {
                TextFieldSelectionState.detectTextFieldLongPressAndAfterDrag$onDragStop$1(Ref.LongRef.this, this, dragBeginOffsetInText, dragTotalDistance);
            }
        }, new Function2<PointerInputChange, Offset, Unit>() { // from class: androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState$detectTextFieldLongPressAndAfterDrag$5
            /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
            {
                super(2);
            }

            @Override // kotlin.jvm.functions.Function2
            public /* bridge */ /* synthetic */ Unit invoke(PointerInputChange pointerInputChange, Offset offset) {
                m1197invokeUv8p0NA(pointerInputChange, offset.getPackedValue());
                return Unit.INSTANCE;
            }

            /* JADX WARN: Multi-variable type inference failed */
            /* JADX WARN: Removed duplicated region for block: B:16:0x0103  */
            /* JADX WARN: Removed duplicated region for block: B:24:0x0122  */
            /* renamed from: invoke-Uv8p0NA, reason: not valid java name */
            /*
                Code decompiled incorrectly, please refer to instructions dump.
                To view partially-correct add '--show-bad-code' argument
            */
            public final void m1197invokeUv8p0NA(androidx.compose.ui.input.pointer.PointerInputChange r19, long r20) {
                /*
                    Method dump skipped, instructions count: 409
                    To view this dump add '--comments-level debug' option
                */
                throw new UnsupportedOperationException("Method not decompiled: androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState$detectTextFieldLongPressAndAfterDrag$5.m1197invokeUv8p0NA(androidx.compose.ui.input.pointer.PointerInputChange, long):void");
            }
        }, continuation);
        return detectDragGesturesAfterLongPress == IntrinsicsKt.getCOROUTINE_SUSPENDED() ? detectDragGesturesAfterLongPress : Unit.INSTANCE;
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final void detectTextFieldLongPressAndAfterDrag$onDragStop$1(Ref.LongRef dragBeginPosition, TextFieldSelectionState this$0, Ref.IntRef dragBeginOffsetInText, Ref.LongRef dragTotalDistance) {
        if (OffsetKt.m3524isSpecifiedk4lQ0M(dragBeginPosition.element)) {
            this$0.clearHandleDragging();
            dragBeginOffsetInText.element = -1;
            dragBeginPosition.element = Offset.INSTANCE.m3520getUnspecifiedF1C5BW0();
            dragTotalDistance.element = Offset.INSTANCE.m3521getZeroF1C5BW0();
            this$0.previousRawDragOffset = -1;
        }
    }

    /* JADX INFO: Access modifiers changed from: private */
    /* JADX WARN: Removed duplicated region for block: B:11:0x0035  */
    /* JADX WARN: Removed duplicated region for block: B:16:0x00ed  */
    /* JADX WARN: Removed duplicated region for block: B:23:0x0113  */
    /* JADX WARN: Removed duplicated region for block: B:25:0x0051  */
    /* JADX WARN: Removed duplicated region for block: B:8:0x002c  */
    /*
        Code decompiled incorrectly, please refer to instructions dump.
        To view partially-correct add '--show-bad-code' argument
    */
    public final java.lang.Object detectSelectionHandleDragGestures(androidx.compose.ui.input.pointer.PointerInputScope r22, boolean r23, kotlin.coroutines.Continuation<? super kotlin.Unit> r24) {
        /*
            Method dump skipped, instructions count: 288
            To view this dump add '--comments-level debug' option
        */
        throw new UnsupportedOperationException("Method not decompiled: androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState.detectSelectionHandleDragGestures(androidx.compose.ui.input.pointer.PointerInputScope, boolean, kotlin.coroutines.Continuation):java.lang.Object");
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final void detectSelectionHandleDragGestures$onDragStop$2(Ref.LongRef dragBeginPosition, TextFieldSelectionState this$0, Ref.LongRef dragTotalDistance) {
        if (OffsetKt.m3524isSpecifiedk4lQ0M(dragBeginPosition.element)) {
            this$0.clearHandleDragging();
            dragBeginPosition.element = Offset.INSTANCE.m3520getUnspecifiedF1C5BW0();
            dragTotalDistance.element = Offset.INSTANCE.m3521getZeroF1C5BW0();
            this$0.previousRawDragOffset = -1;
        }
    }

    /* JADX INFO: Access modifiers changed from: private */
    public final Object observeTextChanges(Continuation<? super Unit> continuation) {
        Object collect = FlowKt.drop(FlowKt.distinctUntilChanged(SnapshotStateKt.snapshotFlow(new Function0<TextFieldCharSequence>() { // from class: androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState$observeTextChanges$2
            {
                super(0);
            }

            /* JADX WARN: Can't rename method to resolve collision */
            @Override // kotlin.jvm.functions.Function0
            public final TextFieldCharSequence invoke() {
                TransformedTextFieldState transformedTextFieldState;
                transformedTextFieldState = TextFieldSelectionState.this.textFieldState;
                return transformedTextFieldState.getText();
            }
        }), TextFieldSelectionState$observeTextChanges$3.INSTANCE), 1).collect(new FlowCollector() { // from class: androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState$observeTextChanges$4
            @Override // kotlinx.coroutines.flow.FlowCollector
            public /* bridge */ /* synthetic */ Object emit(Object value, Continuation $completion) {
                return emit((TextFieldCharSequence) value, (Continuation<? super Unit>) $completion);
            }

            public final Object emit(TextFieldCharSequence it, Continuation<? super Unit> continuation2) {
                TextFieldSelectionState.this.setShowCursorHandle(false);
                TextFieldSelectionState.this.updateTextToolbarState(TextToolbarState.None);
                return Unit.INSTANCE;
            }
        }, continuation);
        return collect == IntrinsicsKt.getCOROUTINE_SUSPENDED() ? collect : Unit.INSTANCE;
    }

    /* JADX INFO: Access modifiers changed from: private */
    public final Object observeTextToolbarVisibility(Continuation<? super Unit> continuation) {
        Object collect = SnapshotStateKt.snapshotFlow(new Function0<Rect>() { // from class: androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState$observeTextToolbarVisibility$2
            {
                super(0);
            }

            /* JADX WARN: Can't rename method to resolve collision */
            /* JADX WARN: Code restructure failed: missing block: B:39:0x002a, code lost:
            
                if (r3 == androidx.compose.foundation.text2.input.internal.selection.TextToolbarState.Selection) goto L9;
             */
            /* JADX WARN: Code restructure failed: missing block: B:4:0x001e, code lost:
            
                if (r3 != androidx.compose.foundation.text2.input.internal.selection.TextToolbarState.Cursor) goto L6;
             */
            /* JADX WARN: Code restructure failed: missing block: B:5:0x002c, code lost:
            
                r3 = true;
             */
            @Override // kotlin.jvm.functions.Function0
            /*
                Code decompiled incorrectly, please refer to instructions dump.
                To view partially-correct add '--show-bad-code' argument
            */
            public final androidx.compose.ui.geometry.Rect invoke() {
                /*
                    r10 = this;
                    androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState r0 = androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState.this
                    androidx.compose.foundation.text2.input.internal.TransformedTextFieldState r0 = androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState.access$getTextFieldState$p(r0)
                    androidx.compose.foundation.text2.input.TextFieldCharSequence r0 = r0.getText()
                    long r0 = r0.getSelectionInChars()
                    boolean r0 = androidx.compose.ui.text.TextRange.m5565getCollapsedimpl(r0)
                    r1 = 1
                    r2 = 0
                    if (r0 == 0) goto L20
                    androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState r3 = androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState.this
                    androidx.compose.foundation.text2.input.internal.selection.TextToolbarState r3 = androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState.access$getTextToolbarState(r3)
                    androidx.compose.foundation.text2.input.internal.selection.TextToolbarState r4 = androidx.compose.foundation.text2.input.internal.selection.TextToolbarState.Cursor
                    if (r3 == r4) goto L2c
                L20:
                    if (r0 != 0) goto L2e
                    androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState r3 = androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState.this
                    androidx.compose.foundation.text2.input.internal.selection.TextToolbarState r3 = androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState.access$getTextToolbarState(r3)
                    androidx.compose.foundation.text2.input.internal.selection.TextToolbarState r4 = androidx.compose.foundation.text2.input.internal.selection.TextToolbarState.Selection
                    if (r3 != r4) goto L2e
                L2c:
                    r3 = r1
                    goto L2f
                L2e:
                    r3 = r2
                L2f:
                    if (r3 == 0) goto L43
                    androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState r4 = androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState.this
                    androidx.compose.foundation.text.Handle r4 = r4.getDraggingHandle()
                    if (r4 != 0) goto L43
                    androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState r4 = androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState.this
                    boolean r4 = r4.isInTouchMode()
                    if (r4 == 0) goto L43
                    goto L44
                L43:
                    r1 = r2
                L44:
                    if (r1 != 0) goto L4f
                    androidx.compose.ui.geometry.Rect$Companion r2 = androidx.compose.ui.geometry.Rect.INSTANCE
                    androidx.compose.ui.geometry.Rect r2 = r2.getZero()
                    goto Lb0
                L4f:
                    androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState r2 = androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState.this
                    androidx.compose.ui.layout.LayoutCoordinates r2 = androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState.access$getTextLayoutCoordinates(r2)
                    r4 = 0
                    if (r2 == 0) goto L5d
                    androidx.compose.ui.geometry.Rect r2 = androidx.compose.foundation.text.selection.SelectionManagerKt.visibleBounds(r2)
                    goto L5e
                L5d:
                    r2 = r4
                L5e:
                    if (r2 == 0) goto La9
                    androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState r5 = androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState.this
                    androidx.compose.ui.layout.LayoutCoordinates r5 = androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState.access$getTextLayoutCoordinates(r5)
                    if (r5 == 0) goto L75
                    long r6 = r2.m3540getTopLeftF1C5BW0()
                    long r5 = r5.mo5025localToRootMKHz9U(r6)
                    androidx.compose.ui.geometry.Offset r5 = androidx.compose.ui.geometry.Offset.m3494boximpl(r5)
                    goto L76
                L75:
                    r5 = r4
                L76:
                    kotlin.jvm.internal.Intrinsics.checkNotNull(r5)
                    long r6 = r5.getPackedValue()
                    long r8 = r2.m3538getSizeNHjbRc()
                    androidx.compose.ui.geometry.Rect r6 = androidx.compose.ui.geometry.RectKt.m3545Recttz77jQw(r6, r8)
                    androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState r7 = androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState.this
                    androidx.compose.ui.geometry.Rect r7 = androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState.access$getContentRect(r7)
                    r8 = r7
                    r9 = 0
                    boolean r8 = r6.overlaps(r8)
                    if (r8 == 0) goto L96
                    r4 = r7
                L96:
                    if (r4 == 0) goto La1
                L99:
                    androidx.compose.ui.geometry.Rect r4 = r4.intersect(r6)
                    if (r4 == 0) goto La1
                    r2 = r4
                    goto Lb0
                La1:
                    androidx.compose.ui.geometry.Rect$Companion r4 = androidx.compose.ui.geometry.Rect.INSTANCE
                    androidx.compose.ui.geometry.Rect r4 = r4.getZero()
                    r2 = r4
                    goto Lb0
                La9:
                    androidx.compose.ui.geometry.Rect$Companion r4 = androidx.compose.ui.geometry.Rect.INSTANCE
                    androidx.compose.ui.geometry.Rect r4 = r4.getZero()
                    r2 = r4
                Lb0:
                    return r2
                */
                throw new UnsupportedOperationException("Method not decompiled: androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState$observeTextToolbarVisibility$2.invoke():androidx.compose.ui.geometry.Rect");
            }
        }).collect(new FlowCollector() { // from class: androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState$observeTextToolbarVisibility$3
            @Override // kotlinx.coroutines.flow.FlowCollector
            public /* bridge */ /* synthetic */ Object emit(Object value, Continuation $completion) {
                return emit((Rect) value, (Continuation<? super Unit>) $completion);
            }

            public final Object emit(Rect rect, Continuation<? super Unit> continuation2) {
                if (Intrinsics.areEqual(rect, Rect.INSTANCE.getZero())) {
                    TextFieldSelectionState.this.hideTextToolbar();
                } else {
                    TextFieldSelectionState.this.showTextToolbar(rect);
                }
                return Unit.INSTANCE;
            }
        }, continuation);
        return collect == IntrinsicsKt.getCOROUTINE_SUSPENDED() ? collect : Unit.INSTANCE;
    }

    /* JADX INFO: Access modifiers changed from: private */
    public final Rect getContentRect() {
        float startTop;
        Rect cursorRect;
        Rect cursorRect2;
        TextFieldCharSequence text = this.textFieldState.getText();
        if (TextRange.m5565getCollapsedimpl(text.getSelectionInChars())) {
            LayoutCoordinates textLayoutCoordinates = getTextLayoutCoordinates();
            long topLeft = textLayoutCoordinates != null ? textLayoutCoordinates.mo5025localToRootMKHz9U(getCursorRect().m3540getTopLeftF1C5BW0()) : Offset.INSTANCE.m3521getZeroF1C5BW0();
            return RectKt.m3545Recttz77jQw(topLeft, getCursorRect().m3538getSizeNHjbRc());
        }
        LayoutCoordinates textLayoutCoordinates2 = getTextLayoutCoordinates();
        long startOffset = textLayoutCoordinates2 != null ? textLayoutCoordinates2.mo5025localToRootMKHz9U(m1181getHandlePositiontuRUvjQ(true)) : Offset.INSTANCE.m3521getZeroF1C5BW0();
        LayoutCoordinates textLayoutCoordinates3 = getTextLayoutCoordinates();
        long endOffset = textLayoutCoordinates3 != null ? textLayoutCoordinates3.mo5025localToRootMKHz9U(m1181getHandlePositiontuRUvjQ(false)) : Offset.INSTANCE.m3521getZeroF1C5BW0();
        LayoutCoordinates textLayoutCoordinates4 = getTextLayoutCoordinates();
        float endTop = 0.0f;
        if (textLayoutCoordinates4 != null) {
            TextLayoutResult layoutResult = this.textLayoutState.getLayoutResult();
            startTop = Offset.m3506getYimpl(textLayoutCoordinates4.mo5025localToRootMKHz9U(OffsetKt.Offset(0.0f, (layoutResult == null || (cursorRect2 = layoutResult.getCursorRect(TextRange.m5571getStartimpl(text.getSelectionInChars()))) == null) ? 0.0f : cursorRect2.getTop())));
        } else {
            startTop = 0.0f;
        }
        LayoutCoordinates textLayoutCoordinates5 = getTextLayoutCoordinates();
        if (textLayoutCoordinates5 != null) {
            TextLayoutResult layoutResult2 = this.textLayoutState.getLayoutResult();
            endTop = Offset.m3506getYimpl(textLayoutCoordinates5.mo5025localToRootMKHz9U(OffsetKt.Offset(0.0f, (layoutResult2 == null || (cursorRect = layoutResult2.getCursorRect(TextRange.m5566getEndimpl(text.getSelectionInChars()))) == null) ? 0.0f : cursorRect.getTop())));
        }
        return new Rect(Math.min(Offset.m3505getXimpl(startOffset), Offset.m3505getXimpl(endOffset)), Math.min(startTop, endTop), Math.max(Offset.m3505getXimpl(startOffset), Offset.m3505getXimpl(endOffset)), Math.max(Offset.m3506getYimpl(startOffset), Offset.m3506getYimpl(endOffset)));
    }

    /* JADX INFO: Access modifiers changed from: private */
    /* JADX WARN: Removed duplicated region for block: B:23:0x0058  */
    /* JADX WARN: Removed duplicated region for block: B:25:0x005f  */
    /*
        Code decompiled incorrectly, please refer to instructions dump.
        To view partially-correct add '--show-bad-code' argument
    */
    public final androidx.compose.foundation.text2.input.internal.selection.TextFieldHandleState getSelectionHandleState(boolean r20) {
        /*
            r19 = this;
            r0 = r19
            if (r20 == 0) goto L7
            androidx.compose.foundation.text.Handle r1 = androidx.compose.foundation.text.Handle.SelectionStart
            goto L9
        L7:
            androidx.compose.foundation.text.Handle r1 = androidx.compose.foundation.text.Handle.SelectionEnd
        L9:
            androidx.compose.foundation.text2.input.internal.TextLayoutState r2 = r0.textLayoutState
            androidx.compose.ui.text.TextLayoutResult r2 = r2.getLayoutResult()
            if (r2 != 0) goto L18
            androidx.compose.foundation.text2.input.internal.selection.TextFieldHandleState$Companion r2 = androidx.compose.foundation.text2.input.internal.selection.TextFieldHandleState.INSTANCE
            androidx.compose.foundation.text2.input.internal.selection.TextFieldHandleState r2 = r2.getHidden()
            return r2
        L18:
            androidx.compose.foundation.text2.input.internal.TransformedTextFieldState r3 = r0.textFieldState
            androidx.compose.foundation.text2.input.TextFieldCharSequence r3 = r3.getText()
            long r3 = r3.getSelectionInChars()
            boolean r5 = androidx.compose.ui.text.TextRange.m5565getCollapsedimpl(r3)
            if (r5 == 0) goto L2f
            androidx.compose.foundation.text2.input.internal.selection.TextFieldHandleState$Companion r5 = androidx.compose.foundation.text2.input.internal.selection.TextFieldHandleState.INSTANCE
            androidx.compose.foundation.text2.input.internal.selection.TextFieldHandleState r5 = r5.getHidden()
            return r5
        L2f:
            long r5 = r19.m1181getHandlePositiontuRUvjQ(r20)
            androidx.compose.foundation.text.Handle r7 = r19.getDraggingHandle()
            r8 = 1
            r9 = 0
            if (r7 == r1) goto L54
            androidx.compose.ui.layout.LayoutCoordinates r7 = r19.getTextLayoutCoordinates()
            if (r7 == 0) goto L4e
        L42:
            androidx.compose.ui.geometry.Rect r7 = androidx.compose.foundation.text.selection.SelectionManagerKt.visibleBounds(r7)
            if (r7 == 0) goto L4e
        L49:
            boolean r7 = androidx.compose.foundation.text.selection.SelectionManagerKt.m1041containsInclusiveUv8p0NA(r7, r5)
            goto L4f
        L4e:
            r7 = r9
        L4f:
            if (r7 == 0) goto L52
            goto L54
        L52:
            r7 = r9
            goto L55
        L54:
            r7 = r8
        L55:
            if (r7 != 0) goto L5f
            androidx.compose.foundation.text2.input.internal.selection.TextFieldHandleState$Companion r8 = androidx.compose.foundation.text2.input.internal.selection.TextFieldHandleState.INSTANCE
            androidx.compose.foundation.text2.input.internal.selection.TextFieldHandleState r8 = r8.getHidden()
            return r8
        L5f:
            if (r20 == 0) goto L66
            int r8 = androidx.compose.ui.text.TextRange.m5571getStartimpl(r3)
            goto L6f
        L66:
            int r10 = androidx.compose.ui.text.TextRange.m5566getEndimpl(r3)
            int r10 = r10 - r8
            int r8 = java.lang.Math.max(r10, r9)
        L6f:
            androidx.compose.ui.text.style.ResolvedTextDirection r16 = r2.getBidiRunDirection(r8)
            boolean r17 = androidx.compose.ui.text.TextRange.m5570getReversedimpl(r3)
            androidx.compose.ui.layout.LayoutCoordinates r9 = r19.getTextLayoutCoordinates()
            if (r9 == 0) goto L8a
            androidx.compose.ui.geometry.Rect r9 = androidx.compose.foundation.text.selection.SelectionManagerKt.visibleBounds(r9)
            if (r9 == 0) goto L8a
            r10 = 0
            long r9 = androidx.compose.foundation.text2.input.internal.TextLayoutStateKt.m1147coerceIn3MmeM6k(r5, r9)
            r11 = r9
            goto L8b
        L8a:
            r11 = r5
        L8b:
            androidx.compose.foundation.text2.input.internal.selection.TextFieldHandleState r18 = new androidx.compose.foundation.text2.input.internal.selection.TextFieldHandleState
            r10 = 1
            r15 = 0
            r9 = r18
            r13 = r16
            r14 = r17
            r9.<init>(r10, r11, r13, r14, r15)
            return r18
        */
        throw new UnsupportedOperationException("Method not decompiled: androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState.getSelectionHandleState(boolean):androidx.compose.foundation.text2.input.internal.selection.TextFieldHandleState");
    }

    /* JADX INFO: Access modifiers changed from: private */
    /* renamed from: getHandlePosition-tuRUvjQ, reason: not valid java name */
    public final long m1181getHandlePositiontuRUvjQ(boolean isStartHandle) {
        int offset;
        TextLayoutResult layoutResult = this.textLayoutState.getLayoutResult();
        if (layoutResult == null) {
            return Offset.INSTANCE.m3521getZeroF1C5BW0();
        }
        long selection = this.textFieldState.getText().getSelectionInChars();
        if (isStartHandle) {
            offset = TextRange.m5571getStartimpl(selection);
        } else {
            offset = TextRange.m5566getEndimpl(selection);
        }
        return TextSelectionDelegateKt.getSelectionHandleCoordinates(layoutResult, offset, isStartHandle, TextRange.m5570getReversedimpl(selection));
    }

    /* JADX INFO: Access modifiers changed from: private */
    /* renamed from: updateHandleDragging-Uv8p0NA, reason: not valid java name */
    public final void m1187updateHandleDraggingUv8p0NA(Handle handle, long position) {
        setDraggingHandle(handle);
        m1185setRawHandleDragPositionk4lQ0M(position);
    }

    /* JADX INFO: Access modifiers changed from: private */
    public final void markStartContentVisibleOffset() {
        Rect visibleBounds;
        LayoutCoordinates textLayoutCoordinates = getTextLayoutCoordinates();
        m1186setStartContentVisibleOffsetk4lQ0M((textLayoutCoordinates == null || (visibleBounds = SelectionManagerKt.visibleBounds(textLayoutCoordinates)) == null) ? Offset.INSTANCE.m3520getUnspecifiedF1C5BW0() : visibleBounds.m3540getTopLeftF1C5BW0());
    }

    /* JADX INFO: Access modifiers changed from: private */
    public final void clearHandleDragging() {
        setDraggingHandle(null);
        m1185setRawHandleDragPositionk4lQ0M(Offset.INSTANCE.m3520getUnspecifiedF1C5BW0());
        m1186setStartContentVisibleOffsetk4lQ0M(Offset.INSTANCE.m3520getUnspecifiedF1C5BW0());
    }

    public final void cut() {
        TextFieldCharSequence text = this.textFieldState.getText();
        if (TextRange.m5565getCollapsedimpl(text.getSelectionInChars())) {
            return;
        }
        ClipboardManager clipboardManager = this.clipboardManager;
        if (clipboardManager != null) {
            clipboardManager.setText(new AnnotatedString(TextFieldCharSequenceKt.getSelectedText(text).toString(), null, null, 6, null));
        }
        this.textFieldState.deleteSelectedText();
    }

    public static /* synthetic */ void copy$default(TextFieldSelectionState textFieldSelectionState, boolean z, int i, Object obj) {
        if ((i & 1) != 0) {
            z = true;
        }
        textFieldSelectionState.copy(z);
    }

    public final void copy(boolean cancelSelection) {
        TextFieldCharSequence text = this.textFieldState.getText();
        if (TextRange.m5565getCollapsedimpl(text.getSelectionInChars())) {
            return;
        }
        ClipboardManager clipboardManager = this.clipboardManager;
        if (clipboardManager != null) {
            clipboardManager.setText(new AnnotatedString(TextFieldCharSequenceKt.getSelectedText(text).toString(), null, null, 6, null));
        }
        if (cancelSelection) {
            this.textFieldState.collapseSelectionToMax();
        }
    }

    public final void paste() {
        AnnotatedString text;
        String clipboardText;
        ClipboardManager clipboardManager = this.clipboardManager;
        if (clipboardManager == null || (text = clipboardManager.getText()) == null || (clipboardText = text.getText()) == null) {
            return;
        }
        TransformedTextFieldState.replaceSelectedText$default(this.textFieldState, clipboardText, false, TextFieldEditUndoBehavior.NeverMerge, 2, null);
    }

    /* JADX INFO: Access modifiers changed from: private */
    /* JADX WARN: Removed duplicated region for block: B:12:0x0031  */
    /* JADX WARN: Removed duplicated region for block: B:20:0x0063  */
    /* JADX WARN: Removed duplicated region for block: B:23:0x0078  */
    /* JADX WARN: Removed duplicated region for block: B:26:? A[RETURN, SYNTHETIC] */
    /* JADX WARN: Removed duplicated region for block: B:27:0x006d  */
    /* JADX WARN: Removed duplicated region for block: B:29:0x003a  */
    /*
        Code decompiled incorrectly, please refer to instructions dump.
        To view partially-correct add '--show-bad-code' argument
    */
    public final void showTextToolbar(androidx.compose.ui.geometry.Rect r11) {
        /*
            r10 = this;
            androidx.compose.foundation.text2.input.internal.TransformedTextFieldState r0 = r10.textFieldState
            androidx.compose.foundation.text2.input.TextFieldCharSequence r0 = r0.getText()
            long r0 = r0.getSelectionInChars()
            boolean r2 = r10.getEditable()
            r3 = 0
            if (r2 == 0) goto L29
            androidx.compose.ui.platform.ClipboardManager r2 = r10.clipboardManager
            r4 = 0
            if (r2 == 0) goto L1e
            boolean r2 = r2.hasText()
            r5 = 1
            if (r2 != r5) goto L1e
            r4 = r5
        L1e:
            if (r4 == 0) goto L29
            androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState$showTextToolbar$paste$1 r2 = new androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState$showTextToolbar$paste$1
            r2.<init>()
            kotlin.jvm.functions.Function0 r2 = (kotlin.jvm.functions.Function0) r2
            r7 = r2
            goto L2a
        L29:
            r7 = r3
        L2a:
            boolean r2 = androidx.compose.ui.text.TextRange.m5565getCollapsedimpl(r0)
            if (r2 != 0) goto L3a
            androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState$showTextToolbar$copy$1 r2 = new androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState$showTextToolbar$copy$1
            r2.<init>()
            kotlin.jvm.functions.Function0 r2 = (kotlin.jvm.functions.Function0) r2
            r6 = r2
            goto L3b
        L3a:
            r6 = r3
        L3b:
            boolean r2 = androidx.compose.ui.text.TextRange.m5565getCollapsedimpl(r0)
            if (r2 != 0) goto L51
            boolean r2 = r10.getEditable()
            if (r2 == 0) goto L51
            androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState$showTextToolbar$cut$1 r2 = new androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState$showTextToolbar$cut$1
            r2.<init>()
            kotlin.jvm.functions.Function0 r2 = (kotlin.jvm.functions.Function0) r2
            r8 = r2
            goto L52
        L51:
            r8 = r3
        L52:
            int r2 = androidx.compose.ui.text.TextRange.m5567getLengthimpl(r0)
            androidx.compose.foundation.text2.input.internal.TransformedTextFieldState r4 = r10.textFieldState
            androidx.compose.foundation.text2.input.TextFieldCharSequence r4 = r4.getText()
            int r4 = r4.length()
            if (r2 == r4) goto L6d
            androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState$showTextToolbar$selectAll$1 r2 = new androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState$showTextToolbar$selectAll$1
            r2.<init>()
            r3 = r2
            kotlin.jvm.functions.Function0 r3 = (kotlin.jvm.functions.Function0) r3
            r9 = r3
            goto L6e
        L6d:
            r9 = r3
        L6e:
            androidx.compose.ui.platform.TextToolbar r4 = r10.textToolbar
            if (r4 == 0) goto L7c
        L78:
            r5 = r11
            r4.showMenu(r5, r6, r7, r8, r9)
        L7c:
            return
        */
        throw new UnsupportedOperationException("Method not decompiled: androidx.compose.foundation.text2.input.internal.selection.TextFieldSelectionState.showTextToolbar(androidx.compose.ui.geometry.Rect):void");
    }

    public final void deselect() {
        if (!TextRange.m5565getCollapsedimpl(this.textFieldState.getText().getSelectionInChars())) {
            this.textFieldState.collapseSelectionToEnd();
        }
        setShowCursorHandle(false);
        updateTextToolbarState(TextToolbarState.None);
    }

    /* JADX INFO: Access modifiers changed from: private */
    public final void hideTextToolbar() {
        TextToolbar textToolbar;
        TextToolbar textToolbar2 = this.textToolbar;
        if ((textToolbar2 != null ? textToolbar2.getStatus() : null) != TextToolbarStatus.Shown || (textToolbar = this.textToolbar) == null) {
            return;
        }
        textToolbar.hide();
    }

    /* renamed from: updateSelection-QNhciaU$default, reason: not valid java name */
    static /* synthetic */ long m1189updateSelectionQNhciaU$default(TextFieldSelectionState textFieldSelectionState, TextFieldCharSequence textFieldCharSequence, int i, int i2, boolean z, SelectionAdjustment selectionAdjustment, boolean z2, int i3, Object obj) {
        boolean z3;
        if ((i3 & 32) == 0) {
            z3 = z2;
        } else {
            z3 = false;
        }
        return textFieldSelectionState.m1188updateSelectionQNhciaU(textFieldCharSequence, i, i2, z, selectionAdjustment, z3);
    }

    /* JADX INFO: Access modifiers changed from: private */
    /* renamed from: updateSelection-QNhciaU, reason: not valid java name */
    public final long m1188updateSelectionQNhciaU(TextFieldCharSequence textFieldCharSequence, int startOffset, int endOffset, boolean isStartHandle, SelectionAdjustment adjustment, boolean allowPreviousSelectionCollapsed) {
        TextRange m5559boximpl = TextRange.m5559boximpl(textFieldCharSequence.getSelectionInChars());
        long it = m5559boximpl.getPackedValue();
        boolean z = false;
        if (!(allowPreviousSelectionCollapsed || !TextRange.m5565getCollapsedimpl(it))) {
            m5559boximpl = null;
        }
        long newSelection = m1184getTextFieldSelectionqeG_v_k(startOffset, endOffset, m5559boximpl, isStartHandle, adjustment);
        if (TextRange.m5564equalsimpl0(newSelection, textFieldCharSequence.getSelectionInChars())) {
            return newSelection;
        }
        if (TextRange.m5570getReversedimpl(newSelection) != TextRange.m5570getReversedimpl(textFieldCharSequence.getSelectionInChars())) {
            long $this$updateSelection_QNhciaU_u24lambda_u245 = TextRangeKt.TextRange(TextRange.m5566getEndimpl(newSelection), TextRange.m5571getStartimpl(newSelection));
            if (TextRange.m5564equalsimpl0($this$updateSelection_QNhciaU_u24lambda_u245, textFieldCharSequence.getSelectionInChars())) {
                z = true;
            }
        }
        boolean onlyChangeIsReversed = z;
        if (isInTouchMode() && !onlyChangeIsReversed) {
            HapticFeedback hapticFeedback = this.hapticFeedBack;
            if (hapticFeedback != null) {
                hapticFeedback.mo4417performHapticFeedbackCdsT49E(HapticFeedbackType.INSTANCE.m4426getTextHandleMove5zf0vsI());
            }
        }
        return newSelection;
    }

    /* renamed from: getTextFieldSelection-qeG_v_k, reason: not valid java name */
    private final long m1184getTextFieldSelectionqeG_v_k(int rawStartOffset, int rawEndOffset, TextRange previousSelection, boolean isStartHandle, SelectionAdjustment adjustment) {
        TextLayoutResult layoutResult = this.textLayoutState.getLayoutResult();
        if (layoutResult == null) {
            return TextRange.INSTANCE.m5576getZerod9O1mEE();
        }
        if (previousSelection == null && Intrinsics.areEqual(adjustment, SelectionAdjustment.INSTANCE.getCharacter())) {
            return TextRangeKt.TextRange(rawStartOffset, rawEndOffset);
        }
        SelectionLayout selectionLayout = SelectionLayoutKt.m1007getTextFieldSelectionLayoutRcvTLA(layoutResult, rawStartOffset, rawEndOffset, this.previousRawDragOffset, previousSelection != null ? previousSelection.getPackedValue() : TextRange.INSTANCE.m5576getZerod9O1mEE(), previousSelection == null, isStartHandle);
        if (previousSelection != null && !selectionLayout.shouldRecomputeSelection(this.previousSelectionLayout)) {
            return previousSelection.getPackedValue();
        }
        long result = adjustment.adjust(selectionLayout).m995toTextRanged9O1mEE();
        this.previousSelectionLayout = selectionLayout;
        this.previousRawDragOffset = isStartHandle ? rawStartOffset : rawEndOffset;
        return result;
    }
}
