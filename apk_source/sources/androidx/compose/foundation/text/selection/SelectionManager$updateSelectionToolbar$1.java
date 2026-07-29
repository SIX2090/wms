package androidx.compose.foundation.text.selection;

import kotlin.Metadata;
import kotlin.Unit;
import kotlin.jvm.functions.Function0;
import kotlin.jvm.internal.FunctionReferenceImpl;

/* compiled from: SelectionManager.kt */
@Metadata(k = 3, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
/* synthetic */ class SelectionManager$updateSelectionToolbar$1 extends FunctionReferenceImpl implements Function0<Unit> {
    SelectionManager$updateSelectionToolbar$1(Object obj) {
        super(0, obj, SelectionManager.class, "toolbarCopy", "toolbarCopy()V", 0);
    }

    @Override // kotlin.jvm.functions.Function0
    public /* bridge */ /* synthetic */ Unit invoke() {
        invoke2();
        return Unit.INSTANCE;
    }

    /* renamed from: invoke, reason: avoid collision after fix types in other method */
    public final void invoke2() {
        ((SelectionManager) this.receiver).toolbarCopy();
    }
}
