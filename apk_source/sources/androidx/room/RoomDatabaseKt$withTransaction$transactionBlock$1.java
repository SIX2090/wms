package androidx.room;

import kotlin.Metadata;
import kotlin.ResultKt;
import kotlin.Unit;
import kotlin.coroutines.Continuation;
import kotlin.coroutines.CoroutineContext;
import kotlin.coroutines.intrinsics.IntrinsicsKt;
import kotlin.coroutines.jvm.internal.DebugMetadata;
import kotlin.coroutines.jvm.internal.SuspendLambda;
import kotlin.jvm.functions.Function1;
import kotlin.jvm.functions.Function2;
import kotlin.jvm.internal.Intrinsics;
import kotlinx.coroutines.CoroutineScope;

/* JADX INFO: Add missing generic type declarations: [R] */
/* compiled from: RoomDatabaseExt.kt */
@Metadata(d1 = {"\u0000\b\n\u0002\b\u0002\n\u0002\u0018\u0002\u0010\u0000\u001a\u0002H\u0001\"\u0004\b\u0000\u0010\u0001*\u00020\u0002H\u008a@"}, d2 = {"<anonymous>", "R", "Lkotlinx/coroutines/CoroutineScope;"}, k = 3, mv = {1, 8, 0}, xi = 48)
@DebugMetadata(c = "androidx.room.RoomDatabaseKt$withTransaction$transactionBlock$1", f = "RoomDatabaseExt.kt", i = {0}, l = {62}, m = "invokeSuspend", n = {"transactionElement"}, s = {"L$0"})
/* loaded from: classes11.dex */
final class RoomDatabaseKt$withTransaction$transactionBlock$1<R> extends SuspendLambda implements Function2<CoroutineScope, Continuation<? super R>, Object> {
    final /* synthetic */ Function1<Continuation<? super R>, Object> $block;
    final /* synthetic */ RoomDatabase $this_withTransaction;
    private /* synthetic */ Object L$0;
    int label;

    /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
    /* JADX WARN: Multi-variable type inference failed */
    RoomDatabaseKt$withTransaction$transactionBlock$1(RoomDatabase roomDatabase, Function1<? super Continuation<? super R>, ? extends Object> function1, Continuation<? super RoomDatabaseKt$withTransaction$transactionBlock$1> continuation) {
        super(2, continuation);
        this.$this_withTransaction = roomDatabase;
        this.$block = function1;
    }

    @Override // kotlin.coroutines.jvm.internal.BaseContinuationImpl
    public final Continuation<Unit> create(Object obj, Continuation<?> continuation) {
        RoomDatabaseKt$withTransaction$transactionBlock$1 roomDatabaseKt$withTransaction$transactionBlock$1 = new RoomDatabaseKt$withTransaction$transactionBlock$1(this.$this_withTransaction, this.$block, continuation);
        roomDatabaseKt$withTransaction$transactionBlock$1.L$0 = obj;
        return roomDatabaseKt$withTransaction$transactionBlock$1;
    }

    @Override // kotlin.jvm.functions.Function2
    public final Object invoke(CoroutineScope coroutineScope, Continuation<? super R> continuation) {
        return ((RoomDatabaseKt$withTransaction$transactionBlock$1) create(coroutineScope, continuation)).invokeSuspend(Unit.INSTANCE);
    }

    @Override // kotlin.coroutines.jvm.internal.BaseContinuationImpl
    public final Object invokeSuspend(Object $result) {
        RoomDatabaseKt$withTransaction$transactionBlock$1 roomDatabaseKt$withTransaction$transactionBlock$1;
        TransactionElement transactionElement;
        Throwable th;
        Throwable th2;
        RoomDatabaseKt$withTransaction$transactionBlock$1 roomDatabaseKt$withTransaction$transactionBlock$12;
        TransactionElement transactionElement2;
        Object $result2;
        Object coroutine_suspended = IntrinsicsKt.getCOROUTINE_SUSPENDED();
        switch (this.label) {
            case 0:
                ResultKt.throwOnFailure($result);
                roomDatabaseKt$withTransaction$transactionBlock$1 = this;
                CoroutineScope $this$transaction = (CoroutineScope) roomDatabaseKt$withTransaction$transactionBlock$1.L$0;
                CoroutineContext.Element element = $this$transaction.getCoroutineContext().get(TransactionElement.INSTANCE);
                Intrinsics.checkNotNull(element);
                transactionElement = (TransactionElement) element;
                transactionElement.acquire();
                try {
                    roomDatabaseKt$withTransaction$transactionBlock$1.$this_withTransaction.beginTransaction();
                    try {
                        Function1<Continuation<? super R>, Object> function1 = roomDatabaseKt$withTransaction$transactionBlock$1.$block;
                        roomDatabaseKt$withTransaction$transactionBlock$1.L$0 = transactionElement;
                        roomDatabaseKt$withTransaction$transactionBlock$1.label = 1;
                        Object invoke = function1.invoke(roomDatabaseKt$withTransaction$transactionBlock$1);
                        if (invoke == coroutine_suspended) {
                            return coroutine_suspended;
                        }
                        $result2 = $result;
                        $result = invoke;
                        try {
                            roomDatabaseKt$withTransaction$transactionBlock$1.$this_withTransaction.setTransactionSuccessful();
                            try {
                                roomDatabaseKt$withTransaction$transactionBlock$1.$this_withTransaction.endTransaction();
                                transactionElement.release();
                                return $result;
                            } catch (Throwable th3) {
                                th = th3;
                                transactionElement.release();
                                throw th;
                            }
                        } catch (Throwable th4) {
                            TransactionElement transactionElement3 = transactionElement;
                            th2 = th4;
                            $result = $result2;
                            roomDatabaseKt$withTransaction$transactionBlock$12 = roomDatabaseKt$withTransaction$transactionBlock$1;
                            transactionElement2 = transactionElement3;
                            try {
                                roomDatabaseKt$withTransaction$transactionBlock$12.$this_withTransaction.endTransaction();
                                throw th2;
                            } catch (Throwable th5) {
                                th = th5;
                                transactionElement = transactionElement2;
                                transactionElement.release();
                                throw th;
                            }
                        }
                    } catch (Throwable th6) {
                        th2 = th6;
                        roomDatabaseKt$withTransaction$transactionBlock$12 = roomDatabaseKt$withTransaction$transactionBlock$1;
                        transactionElement2 = transactionElement;
                        roomDatabaseKt$withTransaction$transactionBlock$12.$this_withTransaction.endTransaction();
                        throw th2;
                    }
                } catch (Throwable th7) {
                    th = th7;
                    transactionElement.release();
                    throw th;
                }
            case 1:
                roomDatabaseKt$withTransaction$transactionBlock$12 = this;
                transactionElement2 = (TransactionElement) roomDatabaseKt$withTransaction$transactionBlock$12.L$0;
                try {
                    ResultKt.throwOnFailure($result);
                    transactionElement = transactionElement2;
                    roomDatabaseKt$withTransaction$transactionBlock$1 = roomDatabaseKt$withTransaction$transactionBlock$12;
                    $result2 = $result;
                    roomDatabaseKt$withTransaction$transactionBlock$1.$this_withTransaction.setTransactionSuccessful();
                    roomDatabaseKt$withTransaction$transactionBlock$1.$this_withTransaction.endTransaction();
                    transactionElement.release();
                    return $result;
                } catch (Throwable th8) {
                    th2 = th8;
                    roomDatabaseKt$withTransaction$transactionBlock$12.$this_withTransaction.endTransaction();
                    throw th2;
                }
            default:
                throw new IllegalStateException("call to 'resume' before 'invoke' with coroutine");
        }
    }
}
