package androidx.compose.foundation.lazy.layout;

import androidx.compose.animation.core.FiniteAnimationSpec;
import kotlin.Metadata;
import kotlin.Unit;
import kotlin.coroutines.Continuation;
import kotlin.coroutines.jvm.internal.DebugMetadata;
import kotlin.coroutines.jvm.internal.SuspendLambda;
import kotlin.jvm.functions.Function2;
import kotlinx.coroutines.CoroutineScope;

/* compiled from: LazyLayoutAnimation.kt */
@Metadata(d1 = {"\u0000\n\n\u0000\n\u0002\u0010\u0002\n\u0002\u0018\u0002\u0010\u0000\u001a\u00020\u0001*\u00020\u0002H\u008a@"}, d2 = {"<anonymous>", "", "Lkotlinx/coroutines/CoroutineScope;"}, k = 3, mv = {1, 8, 0}, xi = 48)
@DebugMetadata(c = "androidx.compose.foundation.lazy.layout.LazyLayoutAnimation$animateAppearance$1", f = "LazyLayoutAnimation.kt", i = {}, l = {155, 156}, m = "invokeSuspend", n = {}, s = {})
/* loaded from: classes.dex */
final class LazyLayoutAnimation$animateAppearance$1 extends SuspendLambda implements Function2<CoroutineScope, Continuation<? super Unit>, Object> {
    final /* synthetic */ FiniteAnimationSpec<Float> $spec;
    int label;
    final /* synthetic */ LazyLayoutAnimation this$0;

    /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
    LazyLayoutAnimation$animateAppearance$1(LazyLayoutAnimation lazyLayoutAnimation, FiniteAnimationSpec<Float> finiteAnimationSpec, Continuation<? super LazyLayoutAnimation$animateAppearance$1> continuation) {
        super(2, continuation);
        this.this$0 = lazyLayoutAnimation;
        this.$spec = finiteAnimationSpec;
    }

    @Override // kotlin.coroutines.jvm.internal.BaseContinuationImpl
    public final Continuation<Unit> create(Object obj, Continuation<?> continuation) {
        return new LazyLayoutAnimation$animateAppearance$1(this.this$0, this.$spec, continuation);
    }

    @Override // kotlin.jvm.functions.Function2
    public final Object invoke(CoroutineScope coroutineScope, Continuation<? super Unit> continuation) {
        return ((LazyLayoutAnimation$animateAppearance$1) create(coroutineScope, continuation)).invokeSuspend(Unit.INSTANCE);
    }

    /* JADX WARN: Multi-variable type inference failed */
    /* JADX WARN: Removed duplicated region for block: B:20:0x006b A[RETURN] */
    /* JADX WARN: Removed duplicated region for block: B:21:0x006c  */
    /* JADX WARN: Type inference failed for: r1v0, types: [int] */
    /* JADX WARN: Type inference failed for: r1v1 */
    /* JADX WARN: Type inference failed for: r1v10 */
    /* JADX WARN: Type inference failed for: r1v5, types: [androidx.compose.foundation.lazy.layout.LazyLayoutAnimation$animateAppearance$1] */
    /* JADX WARN: Type inference failed for: r1v6 */
    @Override // kotlin.coroutines.jvm.internal.BaseContinuationImpl
    /*
        Code decompiled incorrectly, please refer to instructions dump.
        To view partially-correct add '--show-bad-code' argument
    */
    public final java.lang.Object invokeSuspend(java.lang.Object r14) {
        /*
            r13 = this;
            java.lang.Object r0 = kotlin.coroutines.intrinsics.IntrinsicsKt.getCOROUTINE_SUSPENDED()
            int r1 = r13.label
            r2 = 0
            switch(r1) {
                case 0: goto L24;
                case 1: goto L1a;
                case 2: goto L13;
                default: goto La;
            }
        La:
            java.lang.IllegalStateException r14 = new java.lang.IllegalStateException
            java.lang.String r0 = "call to 'resume' before 'invoke' with coroutine"
            r14.<init>(r0)
            throw r14
        L13:
            r0 = r13
            kotlin.ResultKt.throwOnFailure(r14)     // Catch: java.lang.Throwable -> L18
            goto L6d
        L18:
            r1 = move-exception
            goto L76
        L1a:
            r1 = r13
            kotlin.ResultKt.throwOnFailure(r14)     // Catch: java.lang.Throwable -> L1f
            goto L41
        L1f:
            r0 = move-exception
            r12 = r1
            r1 = r0
            r0 = r12
            goto L76
        L24:
            kotlin.ResultKt.throwOnFailure(r14)
            r1 = r13
            androidx.compose.foundation.lazy.layout.LazyLayoutAnimation r3 = r1.this$0     // Catch: java.lang.Throwable -> L1f
            androidx.compose.animation.core.Animatable r3 = androidx.compose.foundation.lazy.layout.LazyLayoutAnimation.access$getVisibilityAnimation$p(r3)     // Catch: java.lang.Throwable -> L1f
            r4 = 0
            java.lang.Float r4 = kotlin.coroutines.jvm.internal.Boxing.boxFloat(r4)     // Catch: java.lang.Throwable -> L1f
            r5 = r1
            kotlin.coroutines.Continuation r5 = (kotlin.coroutines.Continuation) r5     // Catch: java.lang.Throwable -> L1f
            r6 = 1
            r1.label = r6     // Catch: java.lang.Throwable -> L1f
            java.lang.Object r3 = r3.snapTo(r4, r5)     // Catch: java.lang.Throwable -> L1f
            if (r3 != r0) goto L41
            return r0
        L41:
            androidx.compose.foundation.lazy.layout.LazyLayoutAnimation r3 = r1.this$0     // Catch: java.lang.Throwable -> L1f
            androidx.compose.animation.core.Animatable r4 = androidx.compose.foundation.lazy.layout.LazyLayoutAnimation.access$getVisibilityAnimation$p(r3)     // Catch: java.lang.Throwable -> L1f
            r3 = 1065353216(0x3f800000, float:1.0)
            java.lang.Float r5 = kotlin.coroutines.jvm.internal.Boxing.boxFloat(r3)     // Catch: java.lang.Throwable -> L1f
            androidx.compose.animation.core.FiniteAnimationSpec<java.lang.Float> r3 = r1.$spec     // Catch: java.lang.Throwable -> L1f
            r6 = r3
            androidx.compose.animation.core.AnimationSpec r6 = (androidx.compose.animation.core.AnimationSpec) r6     // Catch: java.lang.Throwable -> L1f
            androidx.compose.foundation.lazy.layout.LazyLayoutAnimation$animateAppearance$1$1 r3 = new androidx.compose.foundation.lazy.layout.LazyLayoutAnimation$animateAppearance$1$1     // Catch: java.lang.Throwable -> L1f
            androidx.compose.foundation.lazy.layout.LazyLayoutAnimation r7 = r1.this$0     // Catch: java.lang.Throwable -> L1f
            r3.<init>()     // Catch: java.lang.Throwable -> L1f
            r8 = r3
            kotlin.jvm.functions.Function1 r8 = (kotlin.jvm.functions.Function1) r8     // Catch: java.lang.Throwable -> L1f
            r9 = r1
            kotlin.coroutines.Continuation r9 = (kotlin.coroutines.Continuation) r9     // Catch: java.lang.Throwable -> L1f
            r3 = 2
            r1.label = r3     // Catch: java.lang.Throwable -> L1f
            r7 = 0
            r10 = 4
            r11 = 0
            java.lang.Object r3 = androidx.compose.animation.core.Animatable.animateTo$default(r4, r5, r6, r7, r8, r9, r10, r11)     // Catch: java.lang.Throwable -> L1f
            if (r3 != r0) goto L6c
            return r0
        L6c:
            r0 = r1
        L6d:
            androidx.compose.foundation.lazy.layout.LazyLayoutAnimation r1 = r0.this$0
            androidx.compose.foundation.lazy.layout.LazyLayoutAnimation.access$setAppearanceAnimationInProgress(r1, r2)
            kotlin.Unit r1 = kotlin.Unit.INSTANCE
            return r1
        L76:
            androidx.compose.foundation.lazy.layout.LazyLayoutAnimation r3 = r0.this$0
            androidx.compose.foundation.lazy.layout.LazyLayoutAnimation.access$setAppearanceAnimationInProgress(r3, r2)
            throw r1
        */
        throw new UnsupportedOperationException("Method not decompiled: androidx.compose.foundation.lazy.layout.LazyLayoutAnimation$animateAppearance$1.invokeSuspend(java.lang.Object):java.lang.Object");
    }
}
