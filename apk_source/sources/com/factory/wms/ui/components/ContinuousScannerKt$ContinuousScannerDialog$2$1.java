package com.factory.wms.ui.components;

import android.content.Context;
import androidx.activity.compose.ManagedActivityResultLauncher;
import androidx.compose.runtime.MutableState;
import androidx.core.content.ContextCompat;
import kotlin.Metadata;
import kotlin.ResultKt;
import kotlin.Unit;
import kotlin.coroutines.Continuation;
import kotlin.coroutines.intrinsics.IntrinsicsKt;
import kotlin.coroutines.jvm.internal.DebugMetadata;
import kotlin.coroutines.jvm.internal.SuspendLambda;
import kotlin.jvm.functions.Function2;
import kotlinx.coroutines.CoroutineScope;

/* compiled from: ContinuousScanner.kt */
@Metadata(d1 = {"\u0000\n\n\u0000\n\u0002\u0010\u0002\n\u0002\u0018\u0002\u0010\u0000\u001a\u00020\u0001*\u00020\u0002H\n"}, d2 = {"<anonymous>", "", "Lkotlinx/coroutines/CoroutineScope;"}, k = 3, mv = {2, 0, 0}, xi = 48)
@DebugMetadata(c = "com.factory.wms.ui.components.ContinuousScannerKt$ContinuousScannerDialog$2$1", f = "ContinuousScanner.kt", i = {}, l = {}, m = "invokeSuspend", n = {}, s = {})
/* loaded from: classes4.dex */
final class ContinuousScannerKt$ContinuousScannerDialog$2$1 extends SuspendLambda implements Function2<CoroutineScope, Continuation<? super Unit>, Object> {
    final /* synthetic */ Context $context;
    final /* synthetic */ MutableState<Boolean> $hasCameraPermission$delegate;
    final /* synthetic */ ManagedActivityResultLauncher<String, Boolean> $permissionLauncher;
    int label;

    /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
    ContinuousScannerKt$ContinuousScannerDialog$2$1(Context context, ManagedActivityResultLauncher<String, Boolean> managedActivityResultLauncher, MutableState<Boolean> mutableState, Continuation<? super ContinuousScannerKt$ContinuousScannerDialog$2$1> continuation) {
        super(2, continuation);
        this.$context = context;
        this.$permissionLauncher = managedActivityResultLauncher;
        this.$hasCameraPermission$delegate = mutableState;
    }

    @Override // kotlin.coroutines.jvm.internal.BaseContinuationImpl
    public final Continuation<Unit> create(Object obj, Continuation<?> continuation) {
        return new ContinuousScannerKt$ContinuousScannerDialog$2$1(this.$context, this.$permissionLauncher, this.$hasCameraPermission$delegate, continuation);
    }

    @Override // kotlin.jvm.functions.Function2
    public final Object invoke(CoroutineScope coroutineScope, Continuation<? super Unit> continuation) {
        return ((ContinuousScannerKt$ContinuousScannerDialog$2$1) create(coroutineScope, continuation)).invokeSuspend(Unit.INSTANCE);
    }

    @Override // kotlin.coroutines.jvm.internal.BaseContinuationImpl
    public final Object invokeSuspend(Object obj) {
        boolean ContinuousScannerDialog$lambda$2;
        IntrinsicsKt.getCOROUTINE_SUSPENDED();
        switch (this.label) {
            case 0:
                ResultKt.throwOnFailure(obj);
                ContinuousScannerKt.ContinuousScannerDialog$lambda$3(this.$hasCameraPermission$delegate, ContextCompat.checkSelfPermission(this.$context, "android.permission.CAMERA") == 0);
                ContinuousScannerDialog$lambda$2 = ContinuousScannerKt.ContinuousScannerDialog$lambda$2(this.$hasCameraPermission$delegate);
                if (!ContinuousScannerDialog$lambda$2) {
                    this.$permissionLauncher.launch("android.permission.CAMERA");
                }
                return Unit.INSTANCE;
            default:
                throw new IllegalStateException("call to 'resume' before 'invoke' with coroutine");
        }
    }
}
