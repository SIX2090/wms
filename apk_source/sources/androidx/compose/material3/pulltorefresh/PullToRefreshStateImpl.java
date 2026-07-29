package androidx.compose.material3.pulltorefresh;

import androidx.compose.animation.core.SuspendAnimationKt;
import androidx.compose.runtime.FloatState;
import androidx.compose.runtime.MutableFloatState;
import androidx.compose.runtime.MutableState;
import androidx.compose.runtime.PrimitiveSnapshotStateKt;
import androidx.compose.runtime.SnapshotStateKt__SnapshotStateKt;
import androidx.compose.runtime.State;
import androidx.compose.runtime.saveable.Saver;
import androidx.compose.runtime.saveable.SaverKt;
import androidx.compose.runtime.saveable.SaverScope;
import androidx.compose.ui.geometry.Offset;
import androidx.compose.ui.geometry.OffsetKt;
import androidx.compose.ui.input.nestedscroll.NestedScrollConnection;
import androidx.core.app.NotificationCompat;
import kotlin.Metadata;
import kotlin.Unit;
import kotlin.coroutines.Continuation;
import kotlin.coroutines.intrinsics.IntrinsicsKt;
import kotlin.jvm.functions.Function0;
import kotlin.jvm.functions.Function1;
import kotlin.jvm.functions.Function2;
import kotlin.jvm.internal.DefaultConstructorMarker;
import kotlin.ranges.RangesKt;

/* compiled from: PullToRefresh.kt */
@Metadata(d1 = {"\u00006\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010\u000b\n\u0000\n\u0002\u0010\u0007\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0018\n\u0002\u0018\u0002\n\u0002\b\n\n\u0002\u0010\u0002\n\u0002\b\u0004\n\u0002\u0018\u0002\n\u0002\b\t\b\u0001\u0018\u0000 82\u00020\u0001:\u00018B#\u0012\u0006\u0010\u0002\u001a\u00020\u0003\u0012\u0006\u0010\u0004\u001a\u00020\u0005\u0012\f\u0010\u0006\u001a\b\u0012\u0004\u0012\u00020\u00030\u0007¢\u0006\u0002\u0010\bJ\u0016\u0010*\u001a\u00020+2\u0006\u0010,\u001a\u00020\u0005H\u0086@¢\u0006\u0002\u0010-J\u0006\u0010.\u001a\u00020\u0005J\u0018\u0010/\u001a\u0002002\u0006\u00101\u001a\u000200ø\u0001\u0000¢\u0006\u0004\b2\u00103J\b\u00104\u001a\u00020+H\u0016J\u0016\u00105\u001a\u00020\u00052\u0006\u00106\u001a\u00020\u0005H\u0086@¢\u0006\u0002\u0010-J\b\u00107\u001a\u00020+H\u0016R+\u0010\n\u001a\u00020\u00032\u0006\u0010\t\u001a\u00020\u00038B@BX\u0082\u008e\u0002¢\u0006\u0012\n\u0004\b\u000f\u0010\u0010\u001a\u0004\b\u000b\u0010\f\"\u0004\b\r\u0010\u000eR+\u0010\u0011\u001a\u00020\u00052\u0006\u0010\t\u001a\u00020\u00058B@BX\u0082\u008e\u0002¢\u0006\u0012\n\u0004\b\u0016\u0010\u0017\u001a\u0004\b\u0012\u0010\u0013\"\u0004\b\u0014\u0010\u0015R\u0014\u0010\u0018\u001a\u00020\u00058BX\u0082\u0004¢\u0006\u0006\u001a\u0004\b\u0019\u0010\u0013R+\u0010\u001a\u001a\u00020\u00052\u0006\u0010\t\u001a\u00020\u00058@@@X\u0080\u008e\u0002¢\u0006\u0012\n\u0004\b\u001d\u0010\u0017\u001a\u0004\b\u001b\u0010\u0013\"\u0004\b\u001c\u0010\u0015R\u0014\u0010\u001e\u001a\u00020\u00038VX\u0096\u0004¢\u0006\u0006\u001a\u0004\b\u001e\u0010\fR\u001a\u0010\u001f\u001a\u00020 X\u0096\u000e¢\u0006\u000e\n\u0000\u001a\u0004\b!\u0010\"\"\u0004\b#\u0010$R\u0014\u0010\u0004\u001a\u00020\u0005X\u0096\u0004¢\u0006\b\n\u0000\u001a\u0004\b%\u0010\u0013R\u0014\u0010&\u001a\u00020\u00058VX\u0096\u0004¢\u0006\u0006\u001a\u0004\b'\u0010\u0013R\u0014\u0010(\u001a\u00020\u00058VX\u0096\u0004¢\u0006\u0006\u001a\u0004\b)\u0010\u0013\u0082\u0002\u0007\n\u0005\b¡\u001e0\u0001¨\u00069"}, d2 = {"Landroidx/compose/material3/pulltorefresh/PullToRefreshStateImpl;", "Landroidx/compose/material3/pulltorefresh/PullToRefreshState;", "initialRefreshing", "", "positionalThreshold", "", "enabled", "Lkotlin/Function0;", "(ZFLkotlin/jvm/functions/Function0;)V", "<set-?>", "_refreshing", "get_refreshing", "()Z", "set_refreshing", "(Z)V", "_refreshing$delegate", "Landroidx/compose/runtime/MutableState;", "_verticalOffset", "get_verticalOffset", "()F", "set_verticalOffset", "(F)V", "_verticalOffset$delegate", "Landroidx/compose/runtime/MutableFloatState;", "adjustedDistancePulled", "getAdjustedDistancePulled", "distancePulled", "getDistancePulled$material3_release", "setDistancePulled$material3_release", "distancePulled$delegate", "isRefreshing", "nestedScrollConnection", "Landroidx/compose/ui/input/nestedscroll/NestedScrollConnection;", "getNestedScrollConnection", "()Landroidx/compose/ui/input/nestedscroll/NestedScrollConnection;", "setNestedScrollConnection", "(Landroidx/compose/ui/input/nestedscroll/NestedScrollConnection;)V", "getPositionalThreshold", NotificationCompat.CATEGORY_PROGRESS, "getProgress", "verticalOffset", "getVerticalOffset", "animateTo", "", "offset", "(FLkotlin/coroutines/Continuation;)Ljava/lang/Object;", "calculateVerticalOffset", "consumeAvailableOffset", "Landroidx/compose/ui/geometry/Offset;", "available", "consumeAvailableOffset-MK-Hz9U", "(J)J", "endRefresh", "onRelease", "velocity", "startRefresh", "Companion", "material3_release"}, k = 1, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class PullToRefreshStateImpl implements PullToRefreshState {
    public static final int $stable = 0;

    /* renamed from: Companion, reason: from kotlin metadata */
    public static final Companion INSTANCE = new Companion(null);

    /* renamed from: _refreshing$delegate, reason: from kotlin metadata */
    private final MutableState _refreshing;
    private NestedScrollConnection nestedScrollConnection;
    private final float positionalThreshold;

    /* renamed from: distancePulled$delegate, reason: from kotlin metadata */
    private final MutableFloatState distancePulled = PrimitiveSnapshotStateKt.mutableFloatStateOf(0.0f);

    /* renamed from: _verticalOffset$delegate, reason: from kotlin metadata */
    private final MutableFloatState _verticalOffset = PrimitiveSnapshotStateKt.mutableFloatStateOf(0.0f);

    public PullToRefreshStateImpl(boolean initialRefreshing, float positionalThreshold, Function0<Boolean> function0) {
        this.positionalThreshold = positionalThreshold;
        this.nestedScrollConnection = new PullToRefreshStateImpl$nestedScrollConnection$1(function0, this);
        this._refreshing = SnapshotStateKt__SnapshotStateKt.mutableStateOf$default(Boolean.valueOf(initialRefreshing), null, 2, null);
    }

    @Override // androidx.compose.material3.pulltorefresh.PullToRefreshState
    public float getPositionalThreshold() {
        return this.positionalThreshold;
    }

    @Override // androidx.compose.material3.pulltorefresh.PullToRefreshState
    public float getProgress() {
        return getAdjustedDistancePulled() / getPositionalThreshold();
    }

    @Override // androidx.compose.material3.pulltorefresh.PullToRefreshState
    public float getVerticalOffset() {
        return get_verticalOffset();
    }

    @Override // androidx.compose.material3.pulltorefresh.PullToRefreshState
    public boolean isRefreshing() {
        return get_refreshing();
    }

    @Override // androidx.compose.material3.pulltorefresh.PullToRefreshState
    public void startRefresh() {
        set_refreshing(true);
        set_verticalOffset(getPositionalThreshold());
    }

    @Override // androidx.compose.material3.pulltorefresh.PullToRefreshState
    public void endRefresh() {
        set_verticalOffset(0.0f);
        set_refreshing(false);
    }

    @Override // androidx.compose.material3.pulltorefresh.PullToRefreshState
    public NestedScrollConnection getNestedScrollConnection() {
        return this.nestedScrollConnection;
    }

    @Override // androidx.compose.material3.pulltorefresh.PullToRefreshState
    public void setNestedScrollConnection(NestedScrollConnection nestedScrollConnection) {
        this.nestedScrollConnection = nestedScrollConnection;
    }

    /* renamed from: consumeAvailableOffset-MK-Hz9U, reason: not valid java name */
    public final long m2639consumeAvailableOffsetMKHz9U(long available) {
        float dragConsumed;
        if (isRefreshing()) {
            dragConsumed = 0.0f;
        } else {
            float newOffset = RangesKt.coerceAtLeast(getDistancePulled$material3_release() + Offset.m3506getYimpl(available), 0.0f);
            dragConsumed = newOffset - getDistancePulled$material3_release();
            setDistancePulled$material3_release(newOffset);
            set_verticalOffset(calculateVerticalOffset());
        }
        return OffsetKt.Offset(0.0f, dragConsumed);
    }

    /* JADX WARN: Removed duplicated region for block: B:11:0x0030  */
    /* JADX WARN: Removed duplicated region for block: B:15:0x0071  */
    /* JADX WARN: Removed duplicated region for block: B:17:0x0074  */
    /* JADX WARN: Removed duplicated region for block: B:20:0x0076  */
    /* JADX WARN: Removed duplicated region for block: B:23:0x003a  */
    /* JADX WARN: Removed duplicated region for block: B:8:0x0027  */
    /*
        Code decompiled incorrectly, please refer to instructions dump.
        To view partially-correct add '--show-bad-code' argument
    */
    public final java.lang.Object onRelease(float r8, kotlin.coroutines.Continuation<? super java.lang.Float> r9) {
        /*
            r7 = this;
            boolean r0 = r9 instanceof androidx.compose.material3.pulltorefresh.PullToRefreshStateImpl$onRelease$1
            if (r0 == 0) goto L14
            r0 = r9
            androidx.compose.material3.pulltorefresh.PullToRefreshStateImpl$onRelease$1 r0 = (androidx.compose.material3.pulltorefresh.PullToRefreshStateImpl$onRelease$1) r0
            int r1 = r0.label
            r2 = -2147483648(0xffffffff80000000, float:-0.0)
            r1 = r1 & r2
            if (r1 == 0) goto L14
            int r9 = r0.label
            int r9 = r9 - r2
            r0.label = r9
            goto L19
        L14:
            androidx.compose.material3.pulltorefresh.PullToRefreshStateImpl$onRelease$1 r0 = new androidx.compose.material3.pulltorefresh.PullToRefreshStateImpl$onRelease$1
            r0.<init>(r7, r9)
        L19:
            r9 = r0
            java.lang.Object r0 = r9.result
            java.lang.Object r1 = kotlin.coroutines.intrinsics.IntrinsicsKt.getCOROUTINE_SUSPENDED()
            int r2 = r9.label
            r3 = 1
            r4 = 0
            switch(r2) {
                case 0: goto L3a;
                case 1: goto L30;
                default: goto L27;
            }
        L27:
            java.lang.IllegalStateException r8 = new java.lang.IllegalStateException
            java.lang.String r9 = "call to 'resume' before 'invoke' with coroutine"
            r8.<init>(r9)
            throw r8
        L30:
            float r8 = r9.F$0
            java.lang.Object r1 = r9.L$0
            androidx.compose.material3.pulltorefresh.PullToRefreshStateImpl r1 = (androidx.compose.material3.pulltorefresh.PullToRefreshStateImpl) r1
            kotlin.ResultKt.throwOnFailure(r0)
            goto L67
        L3a:
            kotlin.ResultKt.throwOnFailure(r0)
            r2 = r7
            boolean r5 = r2.isRefreshing()
            if (r5 == 0) goto L49
            java.lang.Float r1 = kotlin.coroutines.jvm.internal.Boxing.boxFloat(r4)
            return r1
        L49:
            float r5 = r2.getAdjustedDistancePulled()
            float r6 = r2.getPositionalThreshold()
            int r5 = (r5 > r6 ? 1 : (r5 == r6 ? 0 : -1))
            if (r5 <= 0) goto L59
            r2.startRefresh()
            goto L68
        L59:
            r9.L$0 = r2
            r9.F$0 = r8
            r9.label = r3
            java.lang.Object r5 = r2.animateTo(r4, r9)
            if (r5 != r1) goto L66
            return r1
        L66:
            r1 = r2
        L67:
            r2 = r1
        L68:
            float r1 = r2.getDistancePulled$material3_release()
            int r1 = (r1 > r4 ? 1 : (r1 == r4 ? 0 : -1))
            if (r1 != 0) goto L71
            goto L72
        L71:
            r3 = 0
        L72:
            if (r3 == 0) goto L76
            r8 = r4
            goto L7d
        L76:
            int r1 = (r8 > r4 ? 1 : (r8 == r4 ? 0 : -1))
            if (r1 >= 0) goto L7c
            r8 = r4
            goto L7d
        L7c:
        L7d:
            r2.setDistancePulled$material3_release(r4)
            java.lang.Float r1 = kotlin.coroutines.jvm.internal.Boxing.boxFloat(r8)
            return r1
        */
        throw new UnsupportedOperationException("Method not decompiled: androidx.compose.material3.pulltorefresh.PullToRefreshStateImpl.onRelease(float, kotlin.coroutines.Continuation):java.lang.Object");
    }

    public final Object animateTo(float offset, Continuation<? super Unit> continuation) {
        Object animate$default = SuspendAnimationKt.animate$default(get_verticalOffset(), offset, 0.0f, null, new Function2<Float, Float, Unit>() { // from class: androidx.compose.material3.pulltorefresh.PullToRefreshStateImpl$animateTo$2
            {
                super(2);
            }

            @Override // kotlin.jvm.functions.Function2
            public /* bridge */ /* synthetic */ Unit invoke(Float f, Float f2) {
                invoke(f.floatValue(), f2.floatValue());
                return Unit.INSTANCE;
            }

            public final void invoke(float value, float f) {
                PullToRefreshStateImpl.this.set_verticalOffset(value);
            }
        }, continuation, 12, null);
        return animate$default == IntrinsicsKt.getCOROUTINE_SUSPENDED() ? animate$default : Unit.INSTANCE;
    }

    public final float calculateVerticalOffset() {
        if (getAdjustedDistancePulled() > getPositionalThreshold()) {
            float overshootPercent = Math.abs(getProgress()) - 1.0f;
            float linearTension = RangesKt.coerceIn(overshootPercent, 0.0f, 2.0f);
            float tensionPercent = linearTension - (((float) Math.pow(linearTension, 2)) / 4);
            float extraOffset = getPositionalThreshold() * tensionPercent;
            float overshootPercent2 = getPositionalThreshold() + extraOffset;
            return overshootPercent2;
        }
        float overshootPercent3 = getAdjustedDistancePulled();
        return overshootPercent3;
    }

    /* compiled from: PullToRefresh.kt */
    @Metadata(d1 = {"\u0000&\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\u0010\u000b\n\u0000\n\u0002\u0010\u0007\n\u0000\n\u0002\u0018\u0002\n\u0000\b\u0086\u0003\u0018\u00002\u00020\u0001B\u0007\b\u0002¢\u0006\u0002\u0010\u0002J(\u0010\u0003\u001a\u000e\u0012\u0004\u0012\u00020\u0005\u0012\u0004\u0012\u00020\u00060\u00042\u0006\u0010\u0007\u001a\u00020\b2\f\u0010\t\u001a\b\u0012\u0004\u0012\u00020\u00060\n¨\u0006\u000b"}, d2 = {"Landroidx/compose/material3/pulltorefresh/PullToRefreshStateImpl$Companion;", "", "()V", "Saver", "Landroidx/compose/runtime/saveable/Saver;", "Landroidx/compose/material3/pulltorefresh/PullToRefreshState;", "", "positionalThreshold", "", "enabled", "Lkotlin/Function0;", "material3_release"}, k = 1, mv = {1, 8, 0}, xi = 48)
    public static final class Companion {
        public /* synthetic */ Companion(DefaultConstructorMarker defaultConstructorMarker) {
            this();
        }

        private Companion() {
        }

        public final Saver<PullToRefreshState, Boolean> Saver(final float positionalThreshold, final Function0<Boolean> enabled) {
            return SaverKt.Saver(new Function2<SaverScope, PullToRefreshState, Boolean>() { // from class: androidx.compose.material3.pulltorefresh.PullToRefreshStateImpl$Companion$Saver$1
                @Override // kotlin.jvm.functions.Function2
                public final Boolean invoke(SaverScope $this$Saver, PullToRefreshState it) {
                    return Boolean.valueOf(it.isRefreshing());
                }
            }, new Function1<Boolean, PullToRefreshState>() { // from class: androidx.compose.material3.pulltorefresh.PullToRefreshStateImpl$Companion$Saver$2
                /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
                {
                    super(1);
                }

                @Override // kotlin.jvm.functions.Function1
                public /* bridge */ /* synthetic */ PullToRefreshState invoke(Boolean bool) {
                    return invoke(bool.booleanValue());
                }

                public final PullToRefreshState invoke(boolean isRefreshing) {
                    return new PullToRefreshStateImpl(isRefreshing, positionalThreshold, enabled);
                }
            });
        }
    }

    public final float getDistancePulled$material3_release() {
        FloatState $this$getValue$iv = this.distancePulled;
        return $this$getValue$iv.getFloatValue();
    }

    public final void setDistancePulled$material3_release(float f) {
        MutableFloatState $this$setValue$iv = this.distancePulled;
        $this$setValue$iv.setFloatValue(f);
    }

    private final float getAdjustedDistancePulled() {
        return getDistancePulled$material3_release() * 0.5f;
    }

    private final float get_verticalOffset() {
        FloatState $this$getValue$iv = this._verticalOffset;
        return $this$getValue$iv.getFloatValue();
    }

    /* JADX INFO: Access modifiers changed from: private */
    public final void set_verticalOffset(float f) {
        MutableFloatState $this$setValue$iv = this._verticalOffset;
        $this$setValue$iv.setFloatValue(f);
    }

    private final boolean get_refreshing() {
        State $this$getValue$iv = this._refreshing;
        return ((Boolean) $this$getValue$iv.getValue()).booleanValue();
    }

    private final void set_refreshing(boolean z) {
        MutableState $this$setValue$iv = this._refreshing;
        $this$setValue$iv.setValue(Boolean.valueOf(z));
    }
}
