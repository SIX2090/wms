package androidx.compose.foundation.gestures;

import androidx.compose.ui.input.pointer.AwaitPointerEventScope;
import androidx.compose.ui.input.pointer.PointerInputScope;
import androidx.core.app.NotificationCompat;
import kotlin.Metadata;
import kotlin.ResultKt;
import kotlin.Unit;
import kotlin.coroutines.Continuation;
import kotlin.coroutines.intrinsics.IntrinsicsKt;
import kotlin.coroutines.jvm.internal.DebugMetadata;
import kotlin.coroutines.jvm.internal.RestrictedSuspendLambda;
import kotlin.coroutines.jvm.internal.SuspendLambda;
import kotlin.jvm.functions.Function2;
import kotlin.jvm.internal.Ref;
import kotlinx.coroutines.BuildersKt__Builders_commonKt;
import kotlinx.coroutines.CoroutineScope;
import kotlinx.coroutines.CoroutineScopeKt;
import kotlinx.coroutines.CoroutineStart;

/* compiled from: Transformable.kt */
@Metadata(d1 = {"\u0000\n\n\u0000\n\u0002\u0010\u0002\n\u0002\u0018\u0002\u0010\u0000\u001a\u00020\u0001*\u00020\u0002H\u008a@"}, d2 = {"<anonymous>", "", "Landroidx/compose/ui/input/pointer/PointerInputScope;"}, k = 3, mv = {1, 8, 0}, xi = 48)
@DebugMetadata(c = "androidx.compose.foundation.gestures.TransformableNode$pointerInputNode$1", f = "Transformable.kt", i = {}, l = {155}, m = "invokeSuspend", n = {}, s = {})
/* loaded from: classes.dex */
final class TransformableNode$pointerInputNode$1 extends SuspendLambda implements Function2<PointerInputScope, Continuation<? super Unit>, Object> {
    private /* synthetic */ Object L$0;
    int label;
    final /* synthetic */ TransformableNode this$0;

    /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
    TransformableNode$pointerInputNode$1(TransformableNode transformableNode, Continuation<? super TransformableNode$pointerInputNode$1> continuation) {
        super(2, continuation);
        this.this$0 = transformableNode;
    }

    @Override // kotlin.coroutines.jvm.internal.BaseContinuationImpl
    public final Continuation<Unit> create(Object obj, Continuation<?> continuation) {
        TransformableNode$pointerInputNode$1 transformableNode$pointerInputNode$1 = new TransformableNode$pointerInputNode$1(this.this$0, continuation);
        transformableNode$pointerInputNode$1.L$0 = obj;
        return transformableNode$pointerInputNode$1;
    }

    @Override // kotlin.jvm.functions.Function2
    public final Object invoke(PointerInputScope pointerInputScope, Continuation<? super Unit> continuation) {
        return ((TransformableNode$pointerInputNode$1) create(pointerInputScope, continuation)).invokeSuspend(Unit.INSTANCE);
    }

    @Override // kotlin.coroutines.jvm.internal.BaseContinuationImpl
    public final Object invokeSuspend(Object $result) {
        boolean z;
        Object coroutine_suspended = IntrinsicsKt.getCOROUTINE_SUSPENDED();
        switch (this.label) {
            case 0:
                ResultKt.throwOnFailure($result);
                PointerInputScope $this$SuspendingPointerInputModifierNode = (PointerInputScope) this.L$0;
                z = this.this$0.enabled;
                if (!z) {
                    return Unit.INSTANCE;
                }
                this.label = 1;
                if (CoroutineScopeKt.coroutineScope(new AnonymousClass1($this$SuspendingPointerInputModifierNode, this.this$0, null), this) != coroutine_suspended) {
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

    /* compiled from: Transformable.kt */
    @Metadata(d1 = {"\u0000\n\n\u0000\n\u0002\u0010\u0002\n\u0002\u0018\u0002\u0010\u0000\u001a\u00020\u0001*\u00020\u0002H\u008a@"}, d2 = {"<anonymous>", "", "Lkotlinx/coroutines/CoroutineScope;"}, k = 3, mv = {1, 8, 0}, xi = 48)
    @DebugMetadata(c = "androidx.compose.foundation.gestures.TransformableNode$pointerInputNode$1$1", f = "Transformable.kt", i = {}, l = {174}, m = "invokeSuspend", n = {}, s = {})
    /* renamed from: androidx.compose.foundation.gestures.TransformableNode$pointerInputNode$1$1, reason: invalid class name */
    static final class AnonymousClass1 extends SuspendLambda implements Function2<CoroutineScope, Continuation<? super Unit>, Object> {
        final /* synthetic */ PointerInputScope $$this$SuspendingPointerInputModifierNode;
        private /* synthetic */ Object L$0;
        int label;
        final /* synthetic */ TransformableNode this$0;

        /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
        AnonymousClass1(PointerInputScope pointerInputScope, TransformableNode transformableNode, Continuation<? super AnonymousClass1> continuation) {
            super(2, continuation);
            this.$$this$SuspendingPointerInputModifierNode = pointerInputScope;
            this.this$0 = transformableNode;
        }

        @Override // kotlin.coroutines.jvm.internal.BaseContinuationImpl
        public final Continuation<Unit> create(Object obj, Continuation<?> continuation) {
            AnonymousClass1 anonymousClass1 = new AnonymousClass1(this.$$this$SuspendingPointerInputModifierNode, this.this$0, continuation);
            anonymousClass1.L$0 = obj;
            return anonymousClass1;
        }

        @Override // kotlin.jvm.functions.Function2
        public final Object invoke(CoroutineScope coroutineScope, Continuation<? super Unit> continuation) {
            return ((AnonymousClass1) create(coroutineScope, continuation)).invokeSuspend(Unit.INSTANCE);
        }

        /* compiled from: Transformable.kt */
        @Metadata(d1 = {"\u0000\n\n\u0000\n\u0002\u0010\u0002\n\u0002\u0018\u0002\u0010\u0000\u001a\u00020\u0001*\u00020\u0002H\u008a@"}, d2 = {"<anonymous>", "", "Lkotlinx/coroutines/CoroutineScope;"}, k = 3, mv = {1, 8, 0}, xi = 48)
        @DebugMetadata(c = "androidx.compose.foundation.gestures.TransformableNode$pointerInputNode$1$1$1", f = "Transformable.kt", i = {0, 0, 1}, l = {158, 161}, m = "invokeSuspend", n = {"$this$launch", NotificationCompat.CATEGORY_EVENT, "$this$launch"}, s = {"L$0", "L$1", "L$0"})
        /* renamed from: androidx.compose.foundation.gestures.TransformableNode$pointerInputNode$1$1$1, reason: invalid class name and collision with other inner class name */
        static final class C00141 extends SuspendLambda implements Function2<CoroutineScope, Continuation<? super Unit>, Object> {
            private /* synthetic */ Object L$0;
            Object L$1;
            Object L$2;
            int label;
            final /* synthetic */ TransformableNode this$0;

            /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
            C00141(TransformableNode transformableNode, Continuation<? super C00141> continuation) {
                super(2, continuation);
                this.this$0 = transformableNode;
            }

            @Override // kotlin.coroutines.jvm.internal.BaseContinuationImpl
            public final Continuation<Unit> create(Object obj, Continuation<?> continuation) {
                C00141 c00141 = new C00141(this.this$0, continuation);
                c00141.L$0 = obj;
                return c00141;
            }

            @Override // kotlin.jvm.functions.Function2
            public final Object invoke(CoroutineScope coroutineScope, Continuation<? super Unit> continuation) {
                return ((C00141) create(coroutineScope, continuation)).invokeSuspend(Unit.INSTANCE);
            }

            /* JADX WARN: Multi-variable type inference failed */
            /* JADX WARN: Removed duplicated region for block: B:11:0x0042  */
            /* JADX WARN: Removed duplicated region for block: B:17:0x00a0  */
            /* JADX WARN: Removed duplicated region for block: B:18:0x0070 A[EXC_TOP_SPLITTER, SYNTHETIC] */
            /* JADX WARN: Removed duplicated region for block: B:26:0x00a5  */
            /* JADX WARN: Unsupported multi-entry loop pattern (BACK_EDGE: B:17:0x00a0 -> B:9:0x003c). Please report as a decompilation issue!!! */
            /* JADX WARN: Unsupported multi-entry loop pattern (BACK_EDGE: B:22:0x0095 -> B:9:0x003c). Please report as a decompilation issue!!! */
            /* JADX WARN: Unsupported multi-entry loop pattern (BACK_EDGE: B:25:0x009b -> B:9:0x003c). Please report as a decompilation issue!!! */
            @Override // kotlin.coroutines.jvm.internal.BaseContinuationImpl
            /*
                Code decompiled incorrectly, please refer to instructions dump.
                To view partially-correct add '--show-bad-code' argument
            */
            public final java.lang.Object invokeSuspend(java.lang.Object r11) {
                /*
                    r10 = this;
                    java.lang.Object r0 = kotlin.coroutines.intrinsics.IntrinsicsKt.getCOROUTINE_SUSPENDED()
                    int r1 = r10.label
                    switch(r1) {
                        case 0: goto L34;
                        case 1: goto L1e;
                        case 2: goto L12;
                        default: goto L9;
                    }
                L9:
                    java.lang.IllegalStateException r11 = new java.lang.IllegalStateException
                    java.lang.String r0 = "call to 'resume' before 'invoke' with coroutine"
                    r11.<init>(r0)
                    throw r11
                L12:
                    r1 = r10
                    java.lang.Object r2 = r1.L$0
                    kotlinx.coroutines.CoroutineScope r2 = (kotlinx.coroutines.CoroutineScope) r2
                    kotlin.ResultKt.throwOnFailure(r11)     // Catch: java.util.concurrent.CancellationException -> L1c
                    goto L99
                L1c:
                    r3 = move-exception
                    goto L3c
                L1e:
                    r1 = r10
                    java.lang.Object r2 = r1.L$2
                    kotlin.jvm.internal.Ref$ObjectRef r2 = (kotlin.jvm.internal.Ref.ObjectRef) r2
                    java.lang.Object r3 = r1.L$1
                    kotlin.jvm.internal.Ref$ObjectRef r3 = (kotlin.jvm.internal.Ref.ObjectRef) r3
                    java.lang.Object r4 = r1.L$0
                    kotlinx.coroutines.CoroutineScope r4 = (kotlinx.coroutines.CoroutineScope) r4
                    kotlin.ResultKt.throwOnFailure(r11)
                    r5 = r3
                    r3 = r2
                    r2 = r1
                    r1 = r0
                    r0 = r11
                    goto L67
                L34:
                    kotlin.ResultKt.throwOnFailure(r11)
                    r1 = r10
                    java.lang.Object r2 = r1.L$0
                    kotlinx.coroutines.CoroutineScope r2 = (kotlinx.coroutines.CoroutineScope) r2
                L3c:
                    boolean r3 = kotlinx.coroutines.CoroutineScopeKt.isActive(r2)
                    if (r3 == 0) goto La5
                    kotlin.jvm.internal.Ref$ObjectRef r3 = new kotlin.jvm.internal.Ref$ObjectRef
                    r3.<init>()
                    androidx.compose.foundation.gestures.TransformableNode r4 = r1.this$0
                    kotlinx.coroutines.channels.Channel r4 = androidx.compose.foundation.gestures.TransformableNode.access$getChannel$p(r4)
                    r5 = r1
                    kotlin.coroutines.Continuation r5 = (kotlin.coroutines.Continuation) r5
                    r1.L$0 = r2
                    r1.L$1 = r3
                    r1.L$2 = r3
                    r6 = 1
                    r1.label = r6
                    java.lang.Object r4 = r4.receive(r5)
                    if (r4 != r0) goto L60
                    return r0
                L60:
                    r5 = r3
                    r9 = r0
                    r0 = r11
                    r11 = r4
                    r4 = r2
                    r2 = r1
                    r1 = r9
                L67:
                    r3.element = r11
                    T r11 = r5.element
                    boolean r11 = r11 instanceof androidx.compose.foundation.gestures.TransformEvent.TransformStarted
                    if (r11 == 0) goto La0
                L70:
                    androidx.compose.foundation.gestures.TransformableNode r11 = r2.this$0     // Catch: java.util.concurrent.CancellationException -> L9a
                    androidx.compose.foundation.gestures.TransformableState r11 = androidx.compose.foundation.gestures.TransformableNode.access$getState$p(r11)     // Catch: java.util.concurrent.CancellationException -> L9a
                    androidx.compose.foundation.MutatePriority r3 = androidx.compose.foundation.MutatePriority.UserInput     // Catch: java.util.concurrent.CancellationException -> L9a
                    androidx.compose.foundation.gestures.TransformableNode$pointerInputNode$1$1$1$1 r6 = new androidx.compose.foundation.gestures.TransformableNode$pointerInputNode$1$1$1$1     // Catch: java.util.concurrent.CancellationException -> L9a
                    androidx.compose.foundation.gestures.TransformableNode r7 = r2.this$0     // Catch: java.util.concurrent.CancellationException -> L9a
                    r8 = 0
                    r6.<init>(r5, r7, r8)     // Catch: java.util.concurrent.CancellationException -> L9a
                    kotlin.jvm.functions.Function2 r6 = (kotlin.jvm.functions.Function2) r6     // Catch: java.util.concurrent.CancellationException -> L9a
                    r7 = r2
                    kotlin.coroutines.Continuation r7 = (kotlin.coroutines.Continuation) r7     // Catch: java.util.concurrent.CancellationException -> L9a
                    r2.L$0 = r4     // Catch: java.util.concurrent.CancellationException -> L9a
                    r2.L$1 = r8     // Catch: java.util.concurrent.CancellationException -> L9a
                    r2.L$2 = r8     // Catch: java.util.concurrent.CancellationException -> L9a
                    r8 = 2
                    r2.label = r8     // Catch: java.util.concurrent.CancellationException -> L9a
                    java.lang.Object r11 = r11.transform(r3, r6, r7)     // Catch: java.util.concurrent.CancellationException -> L9a
                    if (r11 != r1) goto L95
                    return r1
                L95:
                    r11 = r0
                    r0 = r1
                    r1 = r2
                    r2 = r4
                L99:
                    goto L3c
                L9a:
                    r11 = move-exception
                    r11 = r0
                    r0 = r1
                    r1 = r2
                    r2 = r4
                    goto L3c
                La0:
                    r11 = r0
                    r0 = r1
                    r1 = r2
                    r2 = r4
                    goto L3c
                La5:
                    kotlin.Unit r0 = kotlin.Unit.INSTANCE
                    return r0
                */
                throw new UnsupportedOperationException("Method not decompiled: androidx.compose.foundation.gestures.TransformableNode$pointerInputNode$1.AnonymousClass1.C00141.invokeSuspend(java.lang.Object):java.lang.Object");
            }

            /* compiled from: Transformable.kt */
            @Metadata(d1 = {"\u0000\n\n\u0000\n\u0002\u0010\u0002\n\u0002\u0018\u0002\u0010\u0000\u001a\u00020\u0001*\u00020\u0002H\u008a@"}, d2 = {"<anonymous>", "", "Landroidx/compose/foundation/gestures/TransformScope;"}, k = 3, mv = {1, 8, 0}, xi = 48)
            @DebugMetadata(c = "androidx.compose.foundation.gestures.TransformableNode$pointerInputNode$1$1$1$1", f = "Transformable.kt", i = {0}, l = {166}, m = "invokeSuspend", n = {"$this$transform"}, s = {"L$0"})
            /* renamed from: androidx.compose.foundation.gestures.TransformableNode$pointerInputNode$1$1$1$1, reason: invalid class name and collision with other inner class name */
            static final class C00151 extends SuspendLambda implements Function2<TransformScope, Continuation<? super Unit>, Object> {
                final /* synthetic */ Ref.ObjectRef<TransformEvent> $event;
                private /* synthetic */ Object L$0;
                Object L$1;
                int label;
                final /* synthetic */ TransformableNode this$0;

                /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
                C00151(Ref.ObjectRef<TransformEvent> objectRef, TransformableNode transformableNode, Continuation<? super C00151> continuation) {
                    super(2, continuation);
                    this.$event = objectRef;
                    this.this$0 = transformableNode;
                }

                @Override // kotlin.coroutines.jvm.internal.BaseContinuationImpl
                public final Continuation<Unit> create(Object obj, Continuation<?> continuation) {
                    C00151 c00151 = new C00151(this.$event, this.this$0, continuation);
                    c00151.L$0 = obj;
                    return c00151;
                }

                @Override // kotlin.jvm.functions.Function2
                public final Object invoke(TransformScope transformScope, Continuation<? super Unit> continuation) {
                    return ((C00151) create(transformScope, continuation)).invokeSuspend(Unit.INSTANCE);
                }

                /* JADX WARN: Multi-variable type inference failed */
                /* JADX WARN: Removed duplicated region for block: B:10:0x0035  */
                /* JADX WARN: Removed duplicated region for block: B:20:0x007c  */
                /* JADX WARN: Unsupported multi-entry loop pattern (BACK_EDGE: B:18:0x006e -> B:7:0x0075). Please report as a decompilation issue!!! */
                @Override // kotlin.coroutines.jvm.internal.BaseContinuationImpl
                /*
                    Code decompiled incorrectly, please refer to instructions dump.
                    To view partially-correct add '--show-bad-code' argument
                */
                public final java.lang.Object invokeSuspend(java.lang.Object r11) {
                    /*
                        r10 = this;
                        java.lang.Object r0 = kotlin.coroutines.intrinsics.IntrinsicsKt.getCOROUTINE_SUSPENDED()
                        int r1 = r10.label
                        switch(r1) {
                            case 0: goto L24;
                            case 1: goto L12;
                            default: goto L9;
                        }
                    L9:
                        java.lang.IllegalStateException r11 = new java.lang.IllegalStateException
                        java.lang.String r0 = "call to 'resume' before 'invoke' with coroutine"
                        r11.<init>(r0)
                        throw r11
                    L12:
                        r1 = r10
                        java.lang.Object r2 = r1.L$1
                        kotlin.jvm.internal.Ref$ObjectRef r2 = (kotlin.jvm.internal.Ref.ObjectRef) r2
                        java.lang.Object r3 = r1.L$0
                        androidx.compose.foundation.gestures.TransformScope r3 = (androidx.compose.foundation.gestures.TransformScope) r3
                        kotlin.ResultKt.throwOnFailure(r11)
                        r4 = r3
                        r3 = r2
                        r2 = r1
                        r1 = r0
                        r0 = r11
                        goto L75
                    L24:
                        kotlin.ResultKt.throwOnFailure(r11)
                        r1 = r10
                        java.lang.Object r2 = r1.L$0
                        androidx.compose.foundation.gestures.TransformScope r2 = (androidx.compose.foundation.gestures.TransformScope) r2
                        r3 = r2
                    L2d:
                        kotlin.jvm.internal.Ref$ObjectRef<androidx.compose.foundation.gestures.TransformEvent> r2 = r1.$event
                        T r2 = r2.element
                        boolean r2 = r2 instanceof androidx.compose.foundation.gestures.TransformEvent.TransformStopped
                        if (r2 != 0) goto L7c
                        kotlin.jvm.internal.Ref$ObjectRef<androidx.compose.foundation.gestures.TransformEvent> r2 = r1.$event
                        T r2 = r2.element
                        boolean r4 = r2 instanceof androidx.compose.foundation.gestures.TransformEvent.TransformDelta
                        if (r4 == 0) goto L40
                        androidx.compose.foundation.gestures.TransformEvent$TransformDelta r2 = (androidx.compose.foundation.gestures.TransformEvent.TransformDelta) r2
                        goto L41
                    L40:
                        r2 = 0
                    L41:
                        if (r2 == 0) goto L55
                        r4 = 0
                        float r5 = r2.getZoomChange()
                        long r6 = r2.getPanChange()
                        float r8 = r2.getRotationChange()
                        r3.mo329transformByd4ec7I(r5, r6, r8)
                    L55:
                        kotlin.jvm.internal.Ref$ObjectRef<androidx.compose.foundation.gestures.TransformEvent> r2 = r1.$event
                        androidx.compose.foundation.gestures.TransformableNode r4 = r1.this$0
                        kotlinx.coroutines.channels.Channel r4 = androidx.compose.foundation.gestures.TransformableNode.access$getChannel$p(r4)
                        r5 = r1
                        kotlin.coroutines.Continuation r5 = (kotlin.coroutines.Continuation) r5
                        r1.L$0 = r3
                        r1.L$1 = r2
                        r6 = 1
                        r1.label = r6
                        java.lang.Object r4 = r4.receive(r5)
                        if (r4 != r0) goto L6e
                        return r0
                    L6e:
                        r9 = r0
                        r0 = r11
                        r11 = r4
                        r4 = r3
                        r3 = r2
                        r2 = r1
                        r1 = r9
                    L75:
                        r3.element = r11
                        r11 = r0
                        r0 = r1
                        r1 = r2
                        r3 = r4
                        goto L2d
                    L7c:
                        kotlin.Unit r0 = kotlin.Unit.INSTANCE
                        return r0
                    */
                    throw new UnsupportedOperationException("Method not decompiled: androidx.compose.foundation.gestures.TransformableNode$pointerInputNode$1.AnonymousClass1.C00141.C00151.invokeSuspend(java.lang.Object):java.lang.Object");
                }
            }
        }

        @Override // kotlin.coroutines.jvm.internal.BaseContinuationImpl
        public final Object invokeSuspend(Object $result) {
            Object coroutine_suspended = IntrinsicsKt.getCOROUTINE_SUSPENDED();
            switch (this.label) {
                case 0:
                    ResultKt.throwOnFailure($result);
                    CoroutineScope $this$coroutineScope = (CoroutineScope) this.L$0;
                    BuildersKt__Builders_commonKt.launch$default($this$coroutineScope, null, CoroutineStart.UNDISPATCHED, new C00141(this.this$0, null), 1, null);
                    this.label = 1;
                    if (ForEachGestureKt.awaitEachGesture(this.$$this$SuspendingPointerInputModifierNode, new AnonymousClass2(this.this$0, $this$coroutineScope, null), this) != coroutine_suspended) {
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

        /* compiled from: Transformable.kt */
        @Metadata(d1 = {"\u0000\n\n\u0000\n\u0002\u0010\u0002\n\u0002\u0018\u0002\u0010\u0000\u001a\u00020\u0001*\u00020\u0002H\u008a@"}, d2 = {"<anonymous>", "", "Landroidx/compose/ui/input/pointer/AwaitPointerEventScope;"}, k = 3, mv = {1, 8, 0}, xi = 48)
        @DebugMetadata(c = "androidx.compose.foundation.gestures.TransformableNode$pointerInputNode$1$1$2", f = "Transformable.kt", i = {}, l = {176}, m = "invokeSuspend", n = {}, s = {})
        /* renamed from: androidx.compose.foundation.gestures.TransformableNode$pointerInputNode$1$1$2, reason: invalid class name */
        static final class AnonymousClass2 extends RestrictedSuspendLambda implements Function2<AwaitPointerEventScope, Continuation<? super Unit>, Object> {
            final /* synthetic */ CoroutineScope $$this$coroutineScope;
            private /* synthetic */ Object L$0;
            int label;
            final /* synthetic */ TransformableNode this$0;

            /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
            AnonymousClass2(TransformableNode transformableNode, CoroutineScope coroutineScope, Continuation<? super AnonymousClass2> continuation) {
                super(2, continuation);
                this.this$0 = transformableNode;
                this.$$this$coroutineScope = coroutineScope;
            }

            @Override // kotlin.coroutines.jvm.internal.BaseContinuationImpl
            public final Continuation<Unit> create(Object obj, Continuation<?> continuation) {
                AnonymousClass2 anonymousClass2 = new AnonymousClass2(this.this$0, this.$$this$coroutineScope, continuation);
                anonymousClass2.L$0 = obj;
                return anonymousClass2;
            }

            @Override // kotlin.jvm.functions.Function2
            public final Object invoke(AwaitPointerEventScope awaitPointerEventScope, Continuation<? super Unit> continuation) {
                return ((AnonymousClass2) create(awaitPointerEventScope, continuation)).invokeSuspend(Unit.INSTANCE);
            }

            /* JADX WARN: Multi-variable type inference failed */
            /* JADX WARN: Removed duplicated region for block: B:17:0x0065 A[Catch: all -> 0x0017, TRY_ENTER, TRY_LEAVE, TryCatch #1 {all -> 0x0017, blocks: (B:9:0x0013, B:15:0x0059, B:17:0x0065), top: B:2:0x0006 }] */
            /* JADX WARN: Type inference failed for: r0v0, types: [java.lang.Object] */
            /* JADX WARN: Type inference failed for: r0v3 */
            @Override // kotlin.coroutines.jvm.internal.BaseContinuationImpl
            /*
                Code decompiled incorrectly, please refer to instructions dump.
                To view partially-correct add '--show-bad-code' argument
            */
            public final java.lang.Object invokeSuspend(java.lang.Object r10) {
                /*
                    r9 = this;
                    java.lang.Object r0 = kotlin.coroutines.intrinsics.IntrinsicsKt.getCOROUTINE_SUSPENDED()
                    int r1 = r9.label
                    switch(r1) {
                        case 0: goto L1b;
                        case 1: goto L12;
                        default: goto L9;
                    }
                L9:
                    java.lang.IllegalStateException r10 = new java.lang.IllegalStateException
                    java.lang.String r0 = "call to 'resume' before 'invoke' with coroutine"
                    r10.<init>(r0)
                    throw r10
                L12:
                    r0 = r9
                    kotlin.ResultKt.throwOnFailure(r10)     // Catch: java.lang.Throwable -> L17 java.util.concurrent.CancellationException -> L19
                    goto L44
                L17:
                    r1 = move-exception
                    goto L66
                L19:
                    r1 = move-exception
                    goto L59
                L1b:
                    kotlin.ResultKt.throwOnFailure(r10)
                    r1 = r9
                    java.lang.Object r2 = r1.L$0
                    androidx.compose.ui.input.pointer.AwaitPointerEventScope r2 = (androidx.compose.ui.input.pointer.AwaitPointerEventScope) r2
                    androidx.compose.foundation.gestures.TransformableNode r3 = r1.this$0     // Catch: java.lang.Throwable -> L50 java.util.concurrent.CancellationException -> L55
                    boolean r3 = androidx.compose.foundation.gestures.TransformableNode.access$getLockRotationOnZoomPan$p(r3)     // Catch: java.lang.Throwable -> L50 java.util.concurrent.CancellationException -> L55
                    androidx.compose.foundation.gestures.TransformableNode r4 = r1.this$0     // Catch: java.lang.Throwable -> L50 java.util.concurrent.CancellationException -> L55
                    kotlinx.coroutines.channels.Channel r4 = androidx.compose.foundation.gestures.TransformableNode.access$getChannel$p(r4)     // Catch: java.lang.Throwable -> L50 java.util.concurrent.CancellationException -> L55
                    androidx.compose.foundation.gestures.TransformableNode r5 = r1.this$0     // Catch: java.lang.Throwable -> L50 java.util.concurrent.CancellationException -> L55
                    kotlin.jvm.functions.Function1 r5 = androidx.compose.foundation.gestures.TransformableNode.access$getUpdatedCanPan$p(r5)     // Catch: java.lang.Throwable -> L50 java.util.concurrent.CancellationException -> L55
                    r6 = r1
                    kotlin.coroutines.Continuation r6 = (kotlin.coroutines.Continuation) r6     // Catch: java.lang.Throwable -> L50 java.util.concurrent.CancellationException -> L55
                    r7 = 1
                    r1.label = r7     // Catch: java.lang.Throwable -> L50 java.util.concurrent.CancellationException -> L55
                    java.lang.Object r3 = androidx.compose.foundation.gestures.TransformableKt.access$detectZoom(r2, r3, r4, r5, r6)     // Catch: java.lang.Throwable -> L50 java.util.concurrent.CancellationException -> L55
                    if (r3 != r0) goto L43
                    return r0
                L43:
                    r0 = r1
                L44:
                    androidx.compose.foundation.gestures.TransformableNode r1 = r0.this$0
                    kotlinx.coroutines.channels.Channel r1 = androidx.compose.foundation.gestures.TransformableNode.access$getChannel$p(r1)
                    androidx.compose.foundation.gestures.TransformEvent$TransformStopped r2 = androidx.compose.foundation.gestures.TransformEvent.TransformStopped.INSTANCE
                    r1.mo7981trySendJP2dKIU(r2)
                    goto L62
                L50:
                    r0 = move-exception
                    r8 = r1
                    r1 = r0
                    r0 = r8
                    goto L66
                L55:
                    r0 = move-exception
                    r8 = r1
                    r1 = r0
                    r0 = r8
                L59:
                    kotlinx.coroutines.CoroutineScope r2 = r0.$$this$coroutineScope     // Catch: java.lang.Throwable -> L17
                    boolean r2 = kotlinx.coroutines.CoroutineScopeKt.isActive(r2)     // Catch: java.lang.Throwable -> L17
                    if (r2 == 0) goto L65
                    goto L44
                L62:
                    kotlin.Unit r1 = kotlin.Unit.INSTANCE
                    return r1
                L65:
                    throw r1     // Catch: java.lang.Throwable -> L17
                L66:
                    androidx.compose.foundation.gestures.TransformableNode r2 = r0.this$0
                    kotlinx.coroutines.channels.Channel r2 = androidx.compose.foundation.gestures.TransformableNode.access$getChannel$p(r2)
                    androidx.compose.foundation.gestures.TransformEvent$TransformStopped r3 = androidx.compose.foundation.gestures.TransformEvent.TransformStopped.INSTANCE
                    r2.mo7981trySendJP2dKIU(r3)
                    throw r1
                */
                throw new UnsupportedOperationException("Method not decompiled: androidx.compose.foundation.gestures.TransformableNode$pointerInputNode$1.AnonymousClass1.AnonymousClass2.invokeSuspend(java.lang.Object):java.lang.Object");
            }
        }
    }
}
