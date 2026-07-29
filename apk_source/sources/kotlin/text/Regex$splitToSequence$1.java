package kotlin.text;

import kotlin.Metadata;
import kotlin.Unit;
import kotlin.coroutines.Continuation;
import kotlin.coroutines.jvm.internal.DebugMetadata;
import kotlin.coroutines.jvm.internal.RestrictedSuspendLambda;
import kotlin.jvm.functions.Function2;
import kotlin.sequences.SequenceScope;

/* compiled from: Regex.kt */
@Metadata(d1 = {"\u0000\u000e\n\u0000\n\u0002\u0010\u0002\n\u0002\u0018\u0002\n\u0002\u0010\u000e\u0010\u0000\u001a\u00020\u0001*\b\u0012\u0004\u0012\u00020\u00030\u0002H\u008a@"}, d2 = {"<anonymous>", "", "Lkotlin/sequences/SequenceScope;", ""}, k = 3, mv = {1, 9, 0}, xi = 48)
@DebugMetadata(c = "kotlin.text.Regex$splitToSequence$1", f = "Regex.kt", i = {1, 1, 1}, l = {275, 283, 287}, m = "invokeSuspend", n = {"$this$sequence", "matcher", "splitCount"}, s = {"L$0", "L$1", "I$0"})
/* loaded from: classes11.dex */
final class Regex$splitToSequence$1 extends RestrictedSuspendLambda implements Function2<SequenceScope<? super String>, Continuation<? super Unit>, Object> {
    final /* synthetic */ CharSequence $input;
    final /* synthetic */ int $limit;
    int I$0;
    private /* synthetic */ Object L$0;
    Object L$1;
    int label;
    final /* synthetic */ Regex this$0;

    /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
    Regex$splitToSequence$1(Regex regex, CharSequence charSequence, int i, Continuation<? super Regex$splitToSequence$1> continuation) {
        super(2, continuation);
        this.this$0 = regex;
        this.$input = charSequence;
        this.$limit = i;
    }

    @Override // kotlin.coroutines.jvm.internal.BaseContinuationImpl
    public final Continuation<Unit> create(Object obj, Continuation<?> continuation) {
        Regex$splitToSequence$1 regex$splitToSequence$1 = new Regex$splitToSequence$1(this.this$0, this.$input, this.$limit, continuation);
        regex$splitToSequence$1.L$0 = obj;
        return regex$splitToSequence$1;
    }

    @Override // kotlin.jvm.functions.Function2
    public final Object invoke(SequenceScope<? super String> sequenceScope, Continuation<? super Unit> continuation) {
        return ((Regex$splitToSequence$1) create(sequenceScope, continuation)).invokeSuspend(Unit.INSTANCE);
    }

    /* JADX WARN: Removed duplicated region for block: B:12:0x007c  */
    /* JADX WARN: Removed duplicated region for block: B:16:0x0071 A[RETURN] */
    /* JADX WARN: Removed duplicated region for block: B:19:0x00a4 A[RETURN] */
    /* JADX WARN: Unsupported multi-entry loop pattern (BACK_EDGE: B:15:0x006f -> B:10:0x0072). Please report as a decompilation issue!!! */
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
            r2 = 1
            switch(r1) {
                case 0: goto L2c;
                case 1: goto L27;
                case 2: goto L18;
                case 3: goto L12;
                default: goto La;
            }
        La:
            java.lang.IllegalStateException r11 = new java.lang.IllegalStateException
            java.lang.String r0 = "call to 'resume' before 'invoke' with coroutine"
            r11.<init>(r0)
            throw r11
        L12:
            kotlin.ResultKt.throwOnFailure(r11)
            r6 = r10
            goto La5
        L18:
            int r1 = r10.I$0
            java.lang.Object r3 = r10.L$1
            java.util.regex.Matcher r3 = (java.util.regex.Matcher) r3
            java.lang.Object r4 = r10.L$0
            kotlin.sequences.SequenceScope r4 = (kotlin.sequences.SequenceScope) r4
            kotlin.ResultKt.throwOnFailure(r11)
            r6 = r10
            goto L72
        L27:
            kotlin.ResultKt.throwOnFailure(r11)
            goto Lba
        L2c:
            kotlin.ResultKt.throwOnFailure(r11)
            java.lang.Object r1 = r10.L$0
            kotlin.sequences.SequenceScope r1 = (kotlin.sequences.SequenceScope) r1
            kotlin.text.Regex r3 = r10.this$0
            java.util.regex.Pattern r3 = kotlin.text.Regex.access$getNativePattern$p(r3)
            java.lang.CharSequence r4 = r10.$input
            java.util.regex.Matcher r3 = r3.matcher(r4)
            int r4 = r10.$limit
            if (r4 == r2) goto La8
            boolean r4 = r3.find()
            if (r4 != 0) goto L4a
            goto La8
        L4a:
            r4 = 0
            r5 = 0
            r6 = r10
            r9 = r4
            r4 = r1
            r1 = r5
            r5 = r9
        L51:
            java.lang.CharSequence r7 = r6.$input
            int r8 = r3.start()
            java.lang.CharSequence r7 = r7.subSequence(r5, r8)
            java.lang.String r5 = r7.toString()
            r7 = r6
            kotlin.coroutines.Continuation r7 = (kotlin.coroutines.Continuation) r7
            r6.L$0 = r4
            r6.L$1 = r3
            r6.I$0 = r1
            r8 = 2
            r6.label = r8
            java.lang.Object r5 = r4.yield(r5, r7)
            if (r5 != r0) goto L72
            return r0
        L72:
            int r5 = r3.end()
            int r1 = r1 + r2
            int r7 = r6.$limit
            int r7 = r7 - r2
            if (r1 == r7) goto L82
            boolean r7 = r3.find()
            if (r7 != 0) goto L51
        L82:
        L83:
            java.lang.CharSequence r1 = r6.$input
            java.lang.CharSequence r2 = r6.$input
            int r2 = r2.length()
            java.lang.CharSequence r1 = r1.subSequence(r5, r2)
            java.lang.String r1 = r1.toString()
            r2 = r6
            kotlin.coroutines.Continuation r2 = (kotlin.coroutines.Continuation) r2
            r3 = 0
            r6.L$0 = r3
            r6.L$1 = r3
            r3 = 3
            r6.label = r3
            java.lang.Object r1 = r4.yield(r1, r2)
            if (r1 != r0) goto La5
            return r0
        La5:
            kotlin.Unit r0 = kotlin.Unit.INSTANCE
            return r0
        La8:
            java.lang.CharSequence r3 = r10.$input
            java.lang.String r3 = r3.toString()
            r4 = r10
            kotlin.coroutines.Continuation r4 = (kotlin.coroutines.Continuation) r4
            r10.label = r2
            java.lang.Object r1 = r1.yield(r3, r4)
            if (r1 != r0) goto Lba
            return r0
        Lba:
            kotlin.Unit r0 = kotlin.Unit.INSTANCE
            return r0
        */
        throw new UnsupportedOperationException("Method not decompiled: kotlin.text.Regex$splitToSequence$1.invokeSuspend(java.lang.Object):java.lang.Object");
    }
}
