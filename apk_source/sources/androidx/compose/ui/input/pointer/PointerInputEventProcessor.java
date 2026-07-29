package androidx.compose.ui.input.pointer;

import androidx.compose.ui.node.HitTestResult;
import androidx.compose.ui.node.LayoutNode;
import kotlin.Metadata;

/* compiled from: PointerInputEventProcessor.kt */
@Metadata(d1 = {"\u0000F\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010\u000b\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0004\n\u0002\u0010\u0002\n\u0000\b\u0000\u0018\u00002\u00020\u0001B\r\u0012\u0006\u0010\u0002\u001a\u00020\u0003¢\u0006\u0002\u0010\u0004J-\u0010\u000f\u001a\u00020\u00102\u0006\u0010\u0011\u001a\u00020\u00122\u0006\u0010\u0013\u001a\u00020\u00142\b\b\u0002\u0010\u0015\u001a\u00020\nø\u0001\u0000ø\u0001\u0001¢\u0006\u0004\b\u0016\u0010\u0017J\u0006\u0010\u0018\u001a\u00020\u0019R\u000e\u0010\u0005\u001a\u00020\u0006X\u0082\u0004¢\u0006\u0002\n\u0000R\u000e\u0010\u0007\u001a\u00020\bX\u0082\u0004¢\u0006\u0002\n\u0000R\u000e\u0010\t\u001a\u00020\nX\u0082\u000e¢\u0006\u0002\n\u0000R\u000e\u0010\u000b\u001a\u00020\fX\u0082\u0004¢\u0006\u0002\n\u0000R\u0011\u0010\u0002\u001a\u00020\u0003¢\u0006\b\n\u0000\u001a\u0004\b\r\u0010\u000e\u0082\u0002\u000b\n\u0002\b!\n\u0005\b¡\u001e0\u0001¨\u0006\u001a"}, d2 = {"Landroidx/compose/ui/input/pointer/PointerInputEventProcessor;", "", "root", "Landroidx/compose/ui/node/LayoutNode;", "(Landroidx/compose/ui/node/LayoutNode;)V", "hitPathTracker", "Landroidx/compose/ui/input/pointer/HitPathTracker;", "hitResult", "Landroidx/compose/ui/node/HitTestResult;", "isProcessing", "", "pointerInputChangeEventProducer", "Landroidx/compose/ui/input/pointer/PointerInputChangeEventProducer;", "getRoot", "()Landroidx/compose/ui/node/LayoutNode;", "process", "Landroidx/compose/ui/input/pointer/ProcessResult;", "pointerEvent", "Landroidx/compose/ui/input/pointer/PointerInputEvent;", "positionCalculator", "Landroidx/compose/ui/input/pointer/PositionCalculator;", "isInBounds", "process-BIzXfog", "(Landroidx/compose/ui/input/pointer/PointerInputEvent;Landroidx/compose/ui/input/pointer/PositionCalculator;Z)I", "processCancel", "", "ui_release"}, k = 1, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes11.dex */
public final class PointerInputEventProcessor {
    public static final int $stable = 8;
    private final HitPathTracker hitPathTracker;
    private boolean isProcessing;
    private final LayoutNode root;
    private final PointerInputChangeEventProducer pointerInputChangeEventProducer = new PointerInputChangeEventProducer();
    private final HitTestResult hitResult = new HitTestResult();

    public PointerInputEventProcessor(LayoutNode root) {
        this.root = root;
        this.hitPathTracker = new HitPathTracker(this.root.getCoordinates());
    }

    public final LayoutNode getRoot() {
        return this.root;
    }

    /* renamed from: process-BIzXfog$default, reason: not valid java name */
    public static /* synthetic */ int m4911processBIzXfog$default(PointerInputEventProcessor pointerInputEventProcessor, PointerInputEvent pointerInputEvent, PositionCalculator positionCalculator, boolean z, int i, Object obj) {
        if ((i & 4) != 0) {
            z = true;
        }
        return pointerInputEventProcessor.m4912processBIzXfog(pointerInputEvent, positionCalculator, z);
    }

    /* renamed from: process-BIzXfog, reason: not valid java name */
    public final int m4912processBIzXfog(PointerInputEvent pointerEvent, PositionCalculator positionCalculator, boolean isInBounds) {
        boolean result;
        if (!this.isProcessing) {
            try {
                this.isProcessing = true;
                try {
                    InternalPointerEvent internalPointerEvent = this.pointerInputChangeEventProducer.produce(pointerEvent, positionCalculator);
                    boolean isHover = true;
                    int size = internalPointerEvent.getChanges().size();
                    for (int i = 0; i < size; i++) {
                        PointerInputChange pointerInputChange = internalPointerEvent.getChanges().valueAt(i);
                        if (!pointerInputChange.getPressed() && !pointerInputChange.getPreviousPressed()) {
                        }
                        isHover = false;
                        break;
                    }
                    int size2 = internalPointerEvent.getChanges().size();
                    for (int i2 = 0; i2 < size2; i2++) {
                        PointerInputChange pointerInputChange2 = internalPointerEvent.getChanges().valueAt(i2);
                        if (isHover || PointerEventKt.changedToDownIgnoreConsumed(pointerInputChange2)) {
                            boolean isTouchEvent = PointerType.m4962equalsimpl0(pointerInputChange2.getType(), PointerType.INSTANCE.m4969getTouchT8wyACA());
                            LayoutNode.m5141hitTestM_7yMNQ$ui_release$default(this.root, pointerInputChange2.getPosition(), this.hitResult, isTouchEvent, false, 8, null);
                            if (!this.hitResult.isEmpty()) {
                                this.hitPathTracker.m4818addHitPathKNwqfcY(pointerInputChange2.getId(), this.hitResult);
                                this.hitResult.clear();
                            }
                        }
                    }
                    this.hitPathTracker.removeDetachedPointerInputFilters();
                    try {
                        boolean dispatchedToSomething = this.hitPathTracker.dispatchChanges(internalPointerEvent, isInBounds);
                        if (internalPointerEvent.getSuppressMovementConsumption()) {
                            result = false;
                        } else {
                            result = false;
                            int i3 = 0;
                            int size3 = internalPointerEvent.getChanges().size();
                            while (true) {
                                if (i3 >= size3) {
                                    break;
                                }
                                PointerInputChange event = internalPointerEvent.getChanges().valueAt(i3);
                                if (!PointerEventKt.positionChangedIgnoreConsumed(event) || !event.isConsumed()) {
                                    i3++;
                                } else {
                                    result = true;
                                    break;
                                }
                            }
                        }
                        int ProcessResult = PointerInputEventProcessorKt.ProcessResult(dispatchedToSomething, result);
                        this.isProcessing = false;
                        return ProcessResult;
                    } catch (Throwable th) {
                        th = th;
                        this.isProcessing = false;
                        throw th;
                    }
                } catch (Throwable th2) {
                    th = th2;
                    this.isProcessing = false;
                    throw th;
                }
            } catch (Throwable th3) {
                th = th3;
            }
        } else {
            return PointerInputEventProcessorKt.ProcessResult(false, false);
        }
    }

    public final void processCancel() {
        if (!this.isProcessing) {
            this.pointerInputChangeEventProducer.clear();
            this.hitPathTracker.processCancel();
        }
    }
}
