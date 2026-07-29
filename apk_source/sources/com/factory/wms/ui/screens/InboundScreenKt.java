package com.factory.wms.ui.screens;

import androidx.compose.foundation.interaction.MutableInteractionSource;
import androidx.compose.foundation.layout.PaddingKt;
import androidx.compose.foundation.layout.SizeKt;
import androidx.compose.foundation.lazy.LazyItemScope;
import androidx.compose.foundation.lazy.LazyListScope;
import androidx.compose.foundation.text.KeyboardActions;
import androidx.compose.foundation.text.KeyboardOptions;
import androidx.compose.material3.OutlinedTextFieldKt;
import androidx.compose.material3.TextFieldColors;
import androidx.compose.runtime.Composer;
import androidx.compose.runtime.ComposerKt;
import androidx.compose.runtime.MutableState;
import androidx.compose.runtime.RecomposeScopeImplKt;
import androidx.compose.runtime.internal.ComposableLambdaKt;
import androidx.compose.ui.Modifier;
import androidx.compose.ui.graphics.Shape;
import androidx.compose.ui.text.TextStyle;
import androidx.compose.ui.text.input.VisualTransformation;
import androidx.compose.ui.unit.Dp;
import com.factory.wms.ui.components.CommonKt;
import com.factory.wms.ui.viewmodel.MainTab;
import com.factory.wms.ui.viewmodel.MainUiState;
import com.factory.wms.ui.viewmodel.MainViewModel;
import com.factory.wms.ui.viewmodel.ScanLine;
import java.util.List;
import kotlin.Metadata;
import kotlin.Unit;
import kotlin.jvm.functions.Function0;
import kotlin.jvm.functions.Function1;
import kotlin.jvm.functions.Function2;
import kotlin.jvm.functions.Function4;
import kotlin.jvm.internal.Intrinsics;

/* compiled from: InboundScreen.kt */
@Metadata(d1 = {"\u0000&\n\u0000\n\u0002\u0010\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0010\u000e\n\u0000\n\u0002\u0010\u000b\u001a%\u0010\u0000\u001a\u00020\u00012\u0006\u0010\u0002\u001a\u00020\u00032\u0006\u0010\u0004\u001a\u00020\u00052\u0006\u0010\u0006\u001a\u00020\u0007H\u0007¢\u0006\u0002\u0010\b¨\u0006\t²\u0006\n\u0010\n\u001a\u00020\u000bX\u008a\u008e\u0002²\u0006\n\u0010\f\u001a\u00020\rX\u008a\u008e\u0002"}, d2 = {"InboundScreen", "", "modifier", "Landroidx/compose/ui/Modifier;", "state", "Lcom/factory/wms/ui/viewmodel/MainUiState;", "viewModel", "Lcom/factory/wms/ui/viewmodel/MainViewModel;", "(Landroidx/compose/ui/Modifier;Lcom/factory/wms/ui/viewmodel/MainUiState;Lcom/factory/wms/ui/viewmodel/MainViewModel;Landroidx/compose/runtime/Composer;I)V", "app_debug", "manualCode", "", "scannerOpen", ""}, k = 2, mv = {2, 0, 0}, xi = 48)
/* loaded from: classes4.dex */
public final class InboundScreenKt {
    /* JADX INFO: Access modifiers changed from: private */
    public static final Unit InboundScreen$lambda$28(Modifier modifier, MainUiState mainUiState, MainViewModel mainViewModel, int i, Composer composer, int i2) {
        InboundScreen(modifier, mainUiState, mainViewModel, composer, RecomposeScopeImplKt.updateChangedFlags(i | 1));
        return Unit.INSTANCE;
    }

    /* JADX WARN: Removed duplicated region for block: B:103:0x05c1  */
    /* JADX WARN: Removed duplicated region for block: B:106:0x05cd  */
    /* JADX WARN: Removed duplicated region for block: B:109:0x0606  */
    /* JADX WARN: Removed duplicated region for block: B:114:0x069d  */
    /* JADX WARN: Removed duplicated region for block: B:117:0x06e5  */
    /* JADX WARN: Removed duplicated region for block: B:124:0x0700  */
    /* JADX WARN: Removed duplicated region for block: B:129:0x0753  */
    /* JADX WARN: Removed duplicated region for block: B:136:0x076e  */
    /* JADX WARN: Removed duplicated region for block: B:141:0x07e1  */
    /* JADX WARN: Removed duplicated region for block: B:148:0x07f5  */
    /* JADX WARN: Removed duplicated region for block: B:155:0x080e  */
    /* JADX WARN: Removed duplicated region for block: B:160:0x0863  */
    /* JADX WARN: Removed duplicated region for block: B:165:0x077b A[ADDED_TO_REGION] */
    /* JADX WARN: Removed duplicated region for block: B:168:0x070d A[ADDED_TO_REGION] */
    /* JADX WARN: Removed duplicated region for block: B:170:0x06ab  */
    /* JADX WARN: Removed duplicated region for block: B:172:0x061c A[ADDED_TO_REGION] */
    /* JADX WARN: Removed duplicated region for block: B:173:0x05d3  */
    /* JADX WARN: Removed duplicated region for block: B:175:0x04f2 A[ADDED_TO_REGION] */
    /* JADX WARN: Removed duplicated region for block: B:177:0x0475  */
    /* JADX WARN: Removed duplicated region for block: B:180:0x0389  */
    /* JADX WARN: Removed duplicated region for block: B:77:0x0377  */
    /* JADX WARN: Removed duplicated region for block: B:80:0x0383  */
    /* JADX WARN: Removed duplicated region for block: B:88:0x0467  */
    /* JADX WARN: Removed duplicated region for block: B:91:0x04cb  */
    /* JADX WARN: Removed duplicated region for block: B:98:0x04e5  */
    /*
        Code decompiled incorrectly, please refer to instructions dump.
        To view partially-correct add '--show-bad-code' argument
    */
    public static final void InboundScreen(final androidx.compose.ui.Modifier r92, final com.factory.wms.ui.viewmodel.MainUiState r93, final com.factory.wms.ui.viewmodel.MainViewModel r94, androidx.compose.runtime.Composer r95, final int r96) {
        /*
            Method dump skipped, instructions count: 2174
            To view this dump add '--comments-level debug' option
        */
        throw new UnsupportedOperationException("Method not decompiled: com.factory.wms.ui.screens.InboundScreenKt.InboundScreen(androidx.compose.ui.Modifier, com.factory.wms.ui.viewmodel.MainUiState, com.factory.wms.ui.viewmodel.MainViewModel, androidx.compose.runtime.Composer, int):void");
    }

    private static final String InboundScreen$lambda$1(MutableState<String> mutableState) {
        MutableState<String> $this$getValue$iv = mutableState;
        return $this$getValue$iv.getValue();
    }

    private static final boolean InboundScreen$lambda$4(MutableState<Boolean> mutableState) {
        MutableState<Boolean> $this$getValue$iv = mutableState;
        return $this$getValue$iv.getValue().booleanValue();
    }

    private static final void InboundScreen$lambda$5(MutableState<Boolean> mutableState, boolean z) {
        mutableState.setValue(Boolean.valueOf(z));
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final Unit InboundScreen$lambda$7$lambda$6(MutableState $scannerOpen$delegate) {
        InboundScreen$lambda$5($scannerOpen$delegate, false);
        return Unit.INSTANCE;
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final Unit InboundScreen$lambda$9$lambda$8(MainViewModel $viewModel, String it) {
        Intrinsics.checkNotNullParameter(it, "it");
        $viewModel.scanInbound(it);
        return Unit.INSTANCE;
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final Unit InboundScreen$lambda$27$lambda$14$lambda$11$lambda$10(MutableState $manualCode$delegate, String it) {
        Intrinsics.checkNotNullParameter(it, "it");
        $manualCode$delegate.setValue(it);
        return Unit.INSTANCE;
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final Unit InboundScreen$lambda$27$lambda$14$lambda$13$lambda$12(MainViewModel $viewModel, MutableState $manualCode$delegate) {
        $viewModel.scanInbound(InboundScreen$lambda$1($manualCode$delegate));
        $manualCode$delegate.setValue("");
        return Unit.INSTANCE;
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final Unit InboundScreen$lambda$27$lambda$20$lambda$16$lambda$15(MutableState $scannerOpen$delegate) {
        InboundScreen$lambda$5($scannerOpen$delegate, true);
        return Unit.INSTANCE;
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final Unit InboundScreen$lambda$27$lambda$20$lambda$18$lambda$17(MainViewModel $viewModel) {
        $viewModel.clearLines(MainTab.Inbound);
        return Unit.INSTANCE;
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final Unit InboundScreen$lambda$27$lambda$26$lambda$25(MainUiState $state, final MainViewModel $viewModel, LazyListScope LazyColumn) {
        Intrinsics.checkNotNullParameter(LazyColumn, "$this$LazyColumn");
        final List items$iv = $state.getInboundLines();
        final Function1 key$iv = new Function1() { // from class: com.factory.wms.ui.screens.InboundScreenKt$$ExternalSyntheticLambda8
            @Override // kotlin.jvm.functions.Function1
            public final Object invoke(Object obj) {
                Object InboundScreen$lambda$27$lambda$26$lambda$25$lambda$21;
                InboundScreen$lambda$27$lambda$26$lambda$25$lambda$21 = InboundScreenKt.InboundScreen$lambda$27$lambda$26$lambda$25$lambda$21((ScanLine) obj);
                return InboundScreen$lambda$27$lambda$26$lambda$25$lambda$21;
            }
        };
        final Function1 contentType$iv = new Function1() { // from class: com.factory.wms.ui.screens.InboundScreenKt$InboundScreen$lambda$27$lambda$26$lambda$25$$inlined$items$default$1
            @Override // kotlin.jvm.functions.Function1
            public /* bridge */ /* synthetic */ Object invoke(Object p1) {
                return invoke((ScanLine) p1);
            }

            @Override // kotlin.jvm.functions.Function1
            public final Void invoke(ScanLine scanLine) {
                return null;
            }
        };
        LazyColumn.items(items$iv.size(), new Function1<Integer, Object>() { // from class: com.factory.wms.ui.screens.InboundScreenKt$InboundScreen$lambda$27$lambda$26$lambda$25$$inlined$items$default$2
            /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
            {
                super(1);
            }

            @Override // kotlin.jvm.functions.Function1
            public /* bridge */ /* synthetic */ Object invoke(Integer num) {
                return invoke(num.intValue());
            }

            public final Object invoke(int index) {
                return Function1.this.invoke(items$iv.get(index));
            }
        }, new Function1<Integer, Object>() { // from class: com.factory.wms.ui.screens.InboundScreenKt$InboundScreen$lambda$27$lambda$26$lambda$25$$inlined$items$default$3
            /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
            {
                super(1);
            }

            @Override // kotlin.jvm.functions.Function1
            public /* bridge */ /* synthetic */ Object invoke(Integer num) {
                return invoke(num.intValue());
            }

            public final Object invoke(int index) {
                return Function1.this.invoke(items$iv.get(index));
            }
        }, ComposableLambdaKt.composableLambdaInstance(-632812321, true, new Function4<LazyItemScope, Integer, Composer, Integer, Unit>() { // from class: com.factory.wms.ui.screens.InboundScreenKt$InboundScreen$lambda$27$lambda$26$lambda$25$$inlined$items$default$4
            /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
            {
                super(4);
            }

            @Override // kotlin.jvm.functions.Function4
            public /* bridge */ /* synthetic */ Unit invoke(LazyItemScope lazyItemScope, Integer num, Composer composer, Integer num2) {
                invoke(lazyItemScope, num.intValue(), composer, num2.intValue());
                return Unit.INSTANCE;
            }

            public final void invoke(LazyItemScope $this$items, int it, Composer $composer, int $changed) {
                Object value$iv;
                Object value$iv2;
                ComposerKt.sourceInformation($composer, "C148@6730L22:LazyDsl.kt#428nma");
                int $dirty = $changed;
                if (($changed & 14) == 0) {
                    $dirty |= $composer.changed($this$items) ? 4 : 2;
                }
                if (($changed & 112) == 0) {
                    $dirty |= $composer.changed(it) ? 32 : 16;
                }
                if (($dirty & 731) == 146 && $composer.getSkipping()) {
                    $composer.skipToGroupEnd();
                    return;
                }
                if (ComposerKt.isTraceInProgress()) {
                    ComposerKt.traceEventStart(-632812321, $dirty, -1, "androidx.compose.foundation.lazy.items.<anonymous> (LazyDsl.kt:148)");
                }
                int $changed2 = $dirty & 14;
                final ScanLine line = (ScanLine) items$iv.get(it);
                $composer.startReplaceableGroup(-1946064945);
                ComposerKt.sourceInformation($composer, "C*93@3672L128,96@3833L61,89@3484L882:InboundScreen.kt#3hfrnz");
                String valueOf = String.valueOf(line.getQuantity());
                $composer.startReplaceableGroup(629965634);
                ComposerKt.sourceInformation($composer, "CC(remember):InboundScreen.kt#9igjgp");
                boolean invalid$iv = $composer.changedInstance($viewModel) | (((($changed2 & 112) ^ 48) > 32 && $composer.changed(line)) || ($changed2 & 48) == 32);
                Object it$iv = $composer.rememberedValue();
                if (invalid$iv || it$iv == Composer.INSTANCE.getEmpty()) {
                    final MainViewModel mainViewModel = $viewModel;
                    value$iv = new Function1<String, Unit>() { // from class: com.factory.wms.ui.screens.InboundScreenKt$InboundScreen$3$3$1$2$1$1
                        @Override // kotlin.jvm.functions.Function1
                        public /* bridge */ /* synthetic */ Unit invoke(String str) {
                            invoke2(str);
                            return Unit.INSTANCE;
                        }

                        /* renamed from: invoke, reason: avoid collision after fix types in other method */
                        public final void invoke2(String it2) {
                            Intrinsics.checkNotNullParameter(it2, "it");
                            MainViewModel.this.updateInboundQuantity(line.getMaterial().getCode(), CommonKt.toPositiveDoubleOrZero(it2));
                        }
                    };
                    $composer.updateRememberedValue(value$iv);
                } else {
                    value$iv = it$iv;
                }
                Function1 function1 = (Function1) value$iv;
                $composer.endReplaceableGroup();
                $composer.startReplaceableGroup(629970719);
                ComposerKt.sourceInformation($composer, "CC(remember):InboundScreen.kt#9igjgp");
                boolean invalid$iv2 = $composer.changedInstance($viewModel) | (((($changed2 & 112) ^ 48) > 32 && $composer.changed(line)) || ($changed2 & 48) == 32);
                Object it$iv2 = $composer.rememberedValue();
                if (invalid$iv2 || it$iv2 == Composer.INSTANCE.getEmpty()) {
                    final MainViewModel mainViewModel2 = $viewModel;
                    value$iv2 = new Function0<Unit>() { // from class: com.factory.wms.ui.screens.InboundScreenKt$InboundScreen$3$3$1$2$2$1
                        @Override // kotlin.jvm.functions.Function0
                        public /* bridge */ /* synthetic */ Unit invoke() {
                            invoke2();
                            return Unit.INSTANCE;
                        }

                        /* renamed from: invoke, reason: avoid collision after fix types in other method */
                        public final void invoke2() {
                            MainViewModel.this.deleteLine(MainTab.Inbound, line.getMaterial().getCode());
                        }
                    };
                    $composer.updateRememberedValue(value$iv2);
                } else {
                    value$iv2 = it$iv2;
                }
                $composer.endReplaceableGroup();
                final MainViewModel mainViewModel3 = $viewModel;
                CommonKt.LineCard(line, "入库数量", valueOf, function1, (Function0) value$iv2, ComposableLambdaKt.composableLambda($composer, -1967386290, true, new Function2<Composer, Integer, Unit>() { // from class: com.factory.wms.ui.screens.InboundScreenKt$InboundScreen$3$3$1$2$3
                    @Override // kotlin.jvm.functions.Function2
                    public /* bridge */ /* synthetic */ Unit invoke(Composer composer, Integer num) {
                        invoke(composer, num.intValue());
                        return Unit.INSTANCE;
                    }

                    public final void invoke(Composer $composer2, int $changed3) {
                        Object value$iv3;
                        ComposerKt.sourceInformation($composer2, "C100@4040L56,98@3935L413:InboundScreen.kt#3hfrnz");
                        if (($changed3 & 3) != 2 || !$composer2.getSkipping()) {
                            if (ComposerKt.isTraceInProgress()) {
                                ComposerKt.traceEventStart(-1967386290, $changed3, -1, "com.factory.wms.ui.screens.InboundScreen.<anonymous>.<anonymous>.<anonymous>.<anonymous>.<anonymous> (InboundScreen.kt:98)");
                            }
                            String batchNo = ScanLine.this.getBatchNo();
                            Modifier m566paddingqDBjuR0$default = PaddingKt.m566paddingqDBjuR0$default(SizeKt.fillMaxWidth$default(Modifier.INSTANCE, 0.0f, 1, null), 0.0f, Dp.m6094constructorimpl(8), 0.0f, 0.0f, 13, null);
                            $composer2.startReplaceableGroup(-177840135);
                            ComposerKt.sourceInformation($composer2, "CC(remember):InboundScreen.kt#9igjgp");
                            boolean invalid$iv3 = $composer2.changedInstance(mainViewModel3) | $composer2.changed(ScanLine.this);
                            final MainViewModel mainViewModel4 = mainViewModel3;
                            final ScanLine scanLine = ScanLine.this;
                            Object it$iv3 = $composer2.rememberedValue();
                            if (invalid$iv3 || it$iv3 == Composer.INSTANCE.getEmpty()) {
                                value$iv3 = new Function1<String, Unit>() { // from class: com.factory.wms.ui.screens.InboundScreenKt$InboundScreen$3$3$1$2$3$1$1
                                    @Override // kotlin.jvm.functions.Function1
                                    public /* bridge */ /* synthetic */ Unit invoke(String str) {
                                        invoke2(str);
                                        return Unit.INSTANCE;
                                    }

                                    /* renamed from: invoke, reason: avoid collision after fix types in other method */
                                    public final void invoke2(String it2) {
                                        Intrinsics.checkNotNullParameter(it2, "it");
                                        MainViewModel.this.updateInboundBatch(scanLine.getMaterial().getCode(), it2);
                                    }
                                };
                                $composer2.updateRememberedValue(value$iv3);
                            } else {
                                value$iv3 = it$iv3;
                            }
                            $composer2.endReplaceableGroup();
                            OutlinedTextFieldKt.OutlinedTextField(batchNo, (Function1<? super String, Unit>) value$iv3, m566paddingqDBjuR0$default, false, false, (TextStyle) null, (Function2<? super Composer, ? super Integer, Unit>) ComposableSingletons$InboundScreenKt.INSTANCE.m6418getLambda6$app_debug(), (Function2<? super Composer, ? super Integer, Unit>) null, (Function2<? super Composer, ? super Integer, Unit>) null, (Function2<? super Composer, ? super Integer, Unit>) null, (Function2<? super Composer, ? super Integer, Unit>) null, (Function2<? super Composer, ? super Integer, Unit>) null, (Function2<? super Composer, ? super Integer, Unit>) null, false, (VisualTransformation) null, (KeyboardOptions) null, (KeyboardActions) null, true, 0, 0, (MutableInteractionSource) null, (Shape) null, (TextFieldColors) null, $composer2, 1573248, 12582912, 0, 8257464);
                            if (ComposerKt.isTraceInProgress()) {
                                ComposerKt.traceEventEnd();
                                return;
                            }
                            return;
                        }
                        $composer2.skipToGroupEnd();
                    }
                }), $composer, (($changed2 >> 3) & 14) | 196656, 0);
                $composer.endReplaceableGroup();
                if (ComposerKt.isTraceInProgress()) {
                    ComposerKt.traceEventEnd();
                }
            }
        }));
        return Unit.INSTANCE;
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final Object InboundScreen$lambda$27$lambda$26$lambda$25$lambda$21(ScanLine it) {
        Intrinsics.checkNotNullParameter(it, "it");
        return it.getMaterial().getCode();
    }
}
