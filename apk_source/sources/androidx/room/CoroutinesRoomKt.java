package androidx.room;

import java.util.Map;
import kotlin.Metadata;
import kotlin.jvm.internal.Intrinsics;
import kotlinx.coroutines.CoroutineDispatcher;
import kotlinx.coroutines.ExecutorsKt;

/* compiled from: CoroutinesRoom.kt */
@Metadata(d1 = {"\u0000\u000e\n\u0000\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\b\u0004\u001a\f\u0010\u0005\u001a\u00020\u0001*\u00020\u0002H\u0007\"\u0018\u0010\u0000\u001a\u00020\u0001*\u00020\u00028@X\u0080\u0004¢\u0006\u0006\u001a\u0004\b\u0003\u0010\u0004¨\u0006\u0006"}, d2 = {"transactionDispatcher", "Lkotlinx/coroutines/CoroutineDispatcher;", "Landroidx/room/RoomDatabase;", "getTransactionDispatcher", "(Landroidx/room/RoomDatabase;)Lkotlinx/coroutines/CoroutineDispatcher;", "getQueryDispatcher", "room-ktx_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes11.dex */
public final class CoroutinesRoomKt {
    public static final CoroutineDispatcher getQueryDispatcher(RoomDatabase $this$getQueryDispatcher) {
        Object answer$iv;
        Map $this$getOrPut$iv = $this$getQueryDispatcher.getBackingFieldMap();
        Object value$iv = $this$getOrPut$iv.get("QueryDispatcher");
        if (value$iv == null) {
            answer$iv = ExecutorsKt.from($this$getQueryDispatcher.getQueryExecutor());
            $this$getOrPut$iv.put("QueryDispatcher", answer$iv);
        } else {
            answer$iv = value$iv;
        }
        Intrinsics.checkNotNull(answer$iv, "null cannot be cast to non-null type kotlinx.coroutines.CoroutineDispatcher");
        return (CoroutineDispatcher) answer$iv;
    }

    public static final CoroutineDispatcher getTransactionDispatcher(RoomDatabase $this$transactionDispatcher) {
        Object answer$iv;
        Map $this$getOrPut$iv = $this$transactionDispatcher.getBackingFieldMap();
        Object value$iv = $this$getOrPut$iv.get("TransactionDispatcher");
        if (value$iv == null) {
            answer$iv = ExecutorsKt.from($this$transactionDispatcher.getTransactionExecutor());
            $this$getOrPut$iv.put("TransactionDispatcher", answer$iv);
        } else {
            answer$iv = value$iv;
        }
        Intrinsics.checkNotNull(answer$iv, "null cannot be cast to non-null type kotlinx.coroutines.CoroutineDispatcher");
        return (CoroutineDispatcher) answer$iv;
    }
}
