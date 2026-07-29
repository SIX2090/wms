package androidx.compose.foundation.gestures;

import androidx.compose.ui.input.pointer.AwaitPointerEventScope;
import androidx.compose.ui.input.pointer.PointerInputScope;
import androidx.compose.ui.input.pointer.SuspendingPointerInputFilterKt;
import androidx.compose.ui.node.CompositionLocalConsumerModifierNode;
import androidx.compose.ui.node.DelegatingNode;
import kotlin.Metadata;
import kotlin.ResultKt;
import kotlin.Unit;
import kotlin.coroutines.Continuation;
import kotlin.coroutines.intrinsics.IntrinsicsKt;
import kotlin.coroutines.jvm.internal.DebugMetadata;
import kotlin.coroutines.jvm.internal.RestrictedSuspendLambda;
import kotlin.coroutines.jvm.internal.SuspendLambda;
import kotlin.jvm.functions.Function2;

/* compiled from: Scrollable.kt */
@Metadata(d1 = {"\u0000$\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\b\u0005\n\u0002\u0010\u0002\n\u0000\b\u0002\u0018\u00002\u00020\u00012\u00020\u0002B\r\u0012\u0006\u0010\u0003\u001a\u00020\u0004¢\u0006\u0002\u0010\u0005J\b\u0010\f\u001a\u00020\rH\u0016R\u001c\u0010\u0006\u001a\u0004\u0018\u00010\u0007X\u0086\u000e¢\u0006\u000e\n\u0000\u001a\u0004\b\b\u0010\t\"\u0004\b\n\u0010\u000bR\u000e\u0010\u0003\u001a\u00020\u0004X\u0082\u0004¢\u0006\u0002\n\u0000¨\u0006\u000e"}, d2 = {"Landroidx/compose/foundation/gestures/MouseWheelScrollNode;", "Landroidx/compose/ui/node/DelegatingNode;", "Landroidx/compose/ui/node/CompositionLocalConsumerModifierNode;", "scrollingLogic", "Landroidx/compose/foundation/gestures/ScrollingLogic;", "(Landroidx/compose/foundation/gestures/ScrollingLogic;)V", "scrollConfig", "Landroidx/compose/foundation/gestures/ScrollConfig;", "getScrollConfig", "()Landroidx/compose/foundation/gestures/ScrollConfig;", "setScrollConfig", "(Landroidx/compose/foundation/gestures/ScrollConfig;)V", "onAttach", "", "foundation_release"}, k = 1, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
final class MouseWheelScrollNode extends DelegatingNode implements CompositionLocalConsumerModifierNode {
    private ScrollConfig scrollConfig;
    private final ScrollingLogic scrollingLogic;

    public MouseWheelScrollNode(ScrollingLogic scrollingLogic) {
        this.scrollingLogic = scrollingLogic;
        delegate(SuspendingPointerInputFilterKt.SuspendingPointerInputModifierNode(new AnonymousClass1(null)));
    }

    public final ScrollConfig getScrollConfig() {
        return this.scrollConfig;
    }

    public final void setScrollConfig(ScrollConfig scrollConfig) {
        this.scrollConfig = scrollConfig;
    }

    @Override // androidx.compose.ui.Modifier.Node
    public void onAttach() {
        this.scrollConfig = AndroidScrollable_androidKt.platformScrollConfig(this);
    }

    /* compiled from: Scrollable.kt */
    @Metadata(d1 = {"\u0000\n\n\u0000\n\u0002\u0010\u0002\n\u0002\u0018\u0002\u0010\u0000\u001a\u00020\u0001*\u00020\u0002H\u008a@"}, d2 = {"<anonymous>", "", "Landroidx/compose/ui/input/pointer/PointerInputScope;"}, k = 3, mv = {1, 8, 0}, xi = 48)
    @DebugMetadata(c = "androidx.compose.foundation.gestures.MouseWheelScrollNode$1", f = "Scrollable.kt", i = {}, l = {669}, m = "invokeSuspend", n = {}, s = {})
    /* renamed from: androidx.compose.foundation.gestures.MouseWheelScrollNode$1, reason: invalid class name */
    static final class AnonymousClass1 extends SuspendLambda implements Function2<PointerInputScope, Continuation<? super Unit>, Object> {
        private /* synthetic */ Object L$0;
        int label;

        AnonymousClass1(Continuation<? super AnonymousClass1> continuation) {
            super(2, continuation);
        }

        @Override // kotlin.coroutines.jvm.internal.BaseContinuationImpl
        public final Continuation<Unit> create(Object obj, Continuation<?> continuation) {
            AnonymousClass1 anonymousClass1 = MouseWheelScrollNode.this.new AnonymousClass1(continuation);
            anonymousClass1.L$0 = obj;
            return anonymousClass1;
        }

        @Override // kotlin.jvm.functions.Function2
        public final Object invoke(PointerInputScope pointerInputScope, Continuation<? super Unit> continuation) {
            return ((AnonymousClass1) create(pointerInputScope, continuation)).invokeSuspend(Unit.INSTANCE);
        }

        /* compiled from: Scrollable.kt */
        @Metadata(d1 = {"\u0000\n\n\u0000\n\u0002\u0010\u0002\n\u0002\u0018\u0002\u0010\u0000\u001a\u00020\u0001*\u00020\u0002H\u008a@"}, d2 = {"<anonymous>", "", "Landroidx/compose/ui/input/pointer/AwaitPointerEventScope;"}, k = 3, mv = {1, 8, 0}, xi = 48)
        @DebugMetadata(c = "androidx.compose.foundation.gestures.MouseWheelScrollNode$1$1", f = "Scrollable.kt", i = {0}, l = {671}, m = "invokeSuspend", n = {"$this$awaitPointerEventScope"}, s = {"L$0"})
        /* renamed from: androidx.compose.foundation.gestures.MouseWheelScrollNode$1$1, reason: invalid class name and collision with other inner class name */
        static final class C00101 extends RestrictedSuspendLambda implements Function2<AwaitPointerEventScope, Continuation<? super Unit>, Object> {
            private /* synthetic */ Object L$0;
            int label;
            final /* synthetic */ MouseWheelScrollNode this$0;

            /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
            C00101(MouseWheelScrollNode mouseWheelScrollNode, Continuation<? super C00101> continuation) {
                super(2, continuation);
                this.this$0 = mouseWheelScrollNode;
            }

            @Override // kotlin.coroutines.jvm.internal.BaseContinuationImpl
            public final Continuation<Unit> create(Object obj, Continuation<?> continuation) {
                C00101 c00101 = new C00101(this.this$0, continuation);
                c00101.L$0 = obj;
                return c00101;
            }

            @Override // kotlin.jvm.functions.Function2
            public final Object invoke(AwaitPointerEventScope awaitPointerEventScope, Continuation<? super Unit> continuation) {
                return ((C00101) create(awaitPointerEventScope, continuation)).invokeSuspend(Unit.INSTANCE);
            }

            /* JADX WARN: Removed duplicated region for block: B:16:0x0076  */
            /* JADX WARN: Removed duplicated region for block: B:23:0x003c A[RETURN] */
            /* JADX WARN: Removed duplicated region for block: B:24:0x003d  */
            /* JADX WARN: Removed duplicated region for block: B:26:0x0071 A[SYNTHETIC] */
            /* JADX WARN: Removed duplicated region for block: B:9:0x0055  */
            /* JADX WARN: Unsupported multi-entry loop pattern (BACK_EDGE: B:22:0x003d -> B:7:0x0043). Please report as a decompilation issue!!! */
            @Override // kotlin.coroutines.jvm.internal.BaseContinuationImpl
            /*
                Code decompiled incorrectly, please refer to instructions dump.
                To view partially-correct add '--show-bad-code' argument
            */
            public final java.lang.Object invokeSuspend(java.lang.Object r21) {
                /*
                    r20 = this;
                    java.lang.Object r0 = kotlin.coroutines.intrinsics.IntrinsicsKt.getCOROUTINE_SUSPENDED()
                    r1 = r20
                    int r2 = r1.label
                    r3 = 1
                    switch(r2) {
                        case 0: goto L23;
                        case 1: goto L15;
                        default: goto Lc;
                    }
                Lc:
                    java.lang.IllegalStateException r0 = new java.lang.IllegalStateException
                    java.lang.String r2 = "call to 'resume' before 'invoke' with coroutine"
                    r0.<init>(r2)
                    throw r0
                L15:
                    r2 = r20
                    r4 = r21
                    java.lang.Object r5 = r2.L$0
                    androidx.compose.ui.input.pointer.AwaitPointerEventScope r5 = (androidx.compose.ui.input.pointer.AwaitPointerEventScope) r5
                    kotlin.ResultKt.throwOnFailure(r4)
                    r6 = r5
                    r5 = r4
                    goto L43
                L23:
                    kotlin.ResultKt.throwOnFailure(r21)
                    r2 = r20
                    r4 = r21
                    java.lang.Object r5 = r2.L$0
                    androidx.compose.ui.input.pointer.AwaitPointerEventScope r5 = (androidx.compose.ui.input.pointer.AwaitPointerEventScope) r5
                L2e:
                    r6 = r2
                    kotlin.coroutines.Continuation r6 = (kotlin.coroutines.Continuation) r6
                    r2.L$0 = r5
                    r2.label = r3
                    java.lang.Object r6 = androidx.compose.foundation.gestures.ScrollableKt.access$awaitScrollEvent(r5, r6)
                    if (r6 != r0) goto L3d
                    return r0
                L3d:
                    r19 = r5
                    r5 = r4
                    r4 = r6
                    r6 = r19
                L43:
                    androidx.compose.ui.input.pointer.PointerEvent r4 = (androidx.compose.ui.input.pointer.PointerEvent) r4
                    java.util.List r7 = r4.getChanges()
                    r8 = 0
                    r9 = 0
                    r10 = 0
                    int r11 = r7.size()
                L53:
                    if (r10 >= r11) goto L71
                    java.lang.Object r12 = r7.get(r10)
                    r13 = 0
                    androidx.compose.ui.input.pointer.PointerInputChange r12 = (androidx.compose.ui.input.pointer.PointerInputChange) r12
                    r14 = 0
                    boolean r15 = r12.isConsumed()
                    r16 = 0
                    if (r15 != 0) goto L68
                    r12 = r3
                    goto L6a
                L68:
                    r12 = r16
                L6a:
                    if (r12 != 0) goto L6d
                    goto L74
                L6d:
                    int r10 = r10 + 1
                    goto L53
                L71:
                    r16 = r3
                L74:
                    if (r16 == 0) goto Lc9
                    androidx.compose.foundation.gestures.MouseWheelScrollNode r7 = r2.this$0
                    androidx.compose.foundation.gestures.ScrollConfig r7 = r7.getScrollConfig()
                    kotlin.jvm.internal.Intrinsics.checkNotNull(r7)
                    androidx.compose.foundation.gestures.MouseWheelScrollNode r8 = r2.this$0
                    r9 = 0
                    r10 = r6
                    androidx.compose.ui.unit.Density r10 = (androidx.compose.ui.unit.Density) r10
                    long r11 = r6.mo4802getSizeYbymL2g()
                    long r10 = r7.mo319calculateMouseWheelScroll8xgXZGE(r10, r4, r11)
                    androidx.compose.foundation.gestures.ScrollingLogic r7 = androidx.compose.foundation.gestures.MouseWheelScrollNode.access$getScrollingLogic$p(r8)
                    r12 = 0
                    kotlinx.coroutines.CoroutineScope r13 = r8.getCoroutineScope()
                    androidx.compose.foundation.gestures.MouseWheelScrollNode$1$1$2$1$1 r8 = new androidx.compose.foundation.gestures.MouseWheelScrollNode$1$1$2$1$1
                    r14 = 0
                    r8.<init>(r7, r10, r14)
                    r16 = r8
                    kotlin.jvm.functions.Function2 r16 = (kotlin.jvm.functions.Function2) r16
                    r17 = 3
                    r18 = 0
                    r15 = 0
                    kotlinx.coroutines.BuildersKt.launch$default(r13, r14, r15, r16, r17, r18)
                    java.util.List r4 = r4.getChanges()
                    r7 = 0
                    r8 = 0
                    int r10 = r4.size()
                Lb3:
                    if (r8 >= r10) goto Lc4
                    java.lang.Object r11 = r4.get(r8)
                    r13 = r11
                    androidx.compose.ui.input.pointer.PointerInputChange r13 = (androidx.compose.ui.input.pointer.PointerInputChange) r13
                    r14 = 0
                    r13.consume()
                    int r8 = r8 + 1
                    goto Lb3
                Lc4:
                Lc9:
                    r4 = r5
                    r5 = r6
                    goto L2e
                */
                throw new UnsupportedOperationException("Method not decompiled: androidx.compose.foundation.gestures.MouseWheelScrollNode.AnonymousClass1.C00101.invokeSuspend(java.lang.Object):java.lang.Object");
            }
        }

        @Override // kotlin.coroutines.jvm.internal.BaseContinuationImpl
        public final Object invokeSuspend(Object $result) {
            Object coroutine_suspended = IntrinsicsKt.getCOROUTINE_SUSPENDED();
            switch (this.label) {
                case 0:
                    ResultKt.throwOnFailure($result);
                    PointerInputScope $this$SuspendingPointerInputModifierNode = (PointerInputScope) this.L$0;
                    this.label = 1;
                    if ($this$SuspendingPointerInputModifierNode.awaitPointerEventScope(new C00101(MouseWheelScrollNode.this, null), this) != coroutine_suspended) {
                        break;
                    } else {
                        return coroutine_suspended;
                    }
                case 1:
                    ResultKt.throwOnFailure($result);
                    break;
                default:
                    throw new IllegalStateException("call to 'resume' before 'invoke' with coroutine");
            }
            return Unit.INSTANCE;
        }
    }
}
