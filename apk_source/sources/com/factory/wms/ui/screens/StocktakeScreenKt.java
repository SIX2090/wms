package com.factory.wms.ui.screens;

import androidx.compose.foundation.layout.PaddingKt;
import androidx.compose.foundation.lazy.LazyItemScope;
import androidx.compose.foundation.lazy.LazyListScope;
import androidx.compose.material3.TextKt;
import androidx.compose.runtime.Composer;
import androidx.compose.runtime.ComposerKt;
import androidx.compose.runtime.MutableState;
import androidx.compose.runtime.RecomposeScopeImplKt;
import androidx.compose.runtime.internal.ComposableLambdaKt;
import androidx.compose.ui.Modifier;
import androidx.compose.ui.text.TextLayoutResult;
import androidx.compose.ui.text.TextStyle;
import androidx.compose.ui.text.font.FontFamily;
import androidx.compose.ui.text.font.FontStyle;
import androidx.compose.ui.text.font.FontWeight;
import androidx.compose.ui.text.style.TextAlign;
import androidx.compose.ui.text.style.TextDecoration;
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

/* compiled from: StocktakeScreen.kt */
@Metadata(d1 = {"\u0000&\n\u0000\n\u0002\u0010\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0010\u000e\n\u0000\n\u0002\u0010\u000b\u001a%\u0010\u0000\u001a\u00020\u00012\u0006\u0010\u0002\u001a\u00020\u00032\u0006\u0010\u0004\u001a\u00020\u00052\u0006\u0010\u0006\u001a\u00020\u0007H\u0007¢\u0006\u0002\u0010\b¨\u0006\t²\u0006\n\u0010\n\u001a\u00020\u000bX\u008a\u008e\u0002²\u0006\n\u0010\f\u001a\u00020\rX\u008a\u008e\u0002"}, d2 = {"StocktakeScreen", "", "modifier", "Landroidx/compose/ui/Modifier;", "state", "Lcom/factory/wms/ui/viewmodel/MainUiState;", "viewModel", "Lcom/factory/wms/ui/viewmodel/MainViewModel;", "(Landroidx/compose/ui/Modifier;Lcom/factory/wms/ui/viewmodel/MainUiState;Lcom/factory/wms/ui/viewmodel/MainViewModel;Landroidx/compose/runtime/Composer;I)V", "app_debug", "manualCode", "", "scannerOpen", ""}, k = 2, mv = {2, 0, 0}, xi = 48)
/* loaded from: classes4.dex */
public final class StocktakeScreenKt {
    /* JADX INFO: Access modifiers changed from: private */
    public static final Unit StocktakeScreen$lambda$34(Modifier modifier, MainUiState mainUiState, MainViewModel mainViewModel, int i, Composer composer, int i2) {
        StocktakeScreen(modifier, mainUiState, mainViewModel, composer, RecomposeScopeImplKt.updateChangedFlags(i | 1));
        return Unit.INSTANCE;
    }

    /* JADX WARN: Code restructure failed: missing block: B:197:0x0ae3, code lost:
    
        if (r4.changedInstance(r0) != false) goto L249;
     */
    /* JADX WARN: Removed duplicated region for block: B:100:0x04cb  */
    /* JADX WARN: Removed duplicated region for block: B:107:0x04e6  */
    /* JADX WARN: Removed duplicated region for block: B:112:0x055c  */
    /* JADX WARN: Removed duplicated region for block: B:130:0x0674  */
    /* JADX WARN: Removed duplicated region for block: B:133:0x0680  */
    /* JADX WARN: Removed duplicated region for block: B:136:0x06b9  */
    /* JADX WARN: Removed duplicated region for block: B:141:0x0760  */
    /* JADX WARN: Removed duplicated region for block: B:144:0x07c4  */
    /* JADX WARN: Removed duplicated region for block: B:151:0x07de  */
    /* JADX WARN: Removed duplicated region for block: B:156:0x08b6  */
    /* JADX WARN: Removed duplicated region for block: B:159:0x08c2  */
    /* JADX WARN: Removed duplicated region for block: B:162:0x08fb  */
    /* JADX WARN: Removed duplicated region for block: B:167:0x098e  */
    /* JADX WARN: Removed duplicated region for block: B:170:0x09dc  */
    /* JADX WARN: Removed duplicated region for block: B:177:0x09f8  */
    /* JADX WARN: Removed duplicated region for block: B:182:0x0a4b  */
    /* JADX WARN: Removed duplicated region for block: B:189:0x0a66  */
    /* JADX WARN: Removed duplicated region for block: B:194:0x0ad9  */
    /* JADX WARN: Removed duplicated region for block: B:201:0x0af3  */
    /* JADX WARN: Removed duplicated region for block: B:208:0x0b0d  */
    /* JADX WARN: Removed duplicated region for block: B:213:0x0b62  */
    /* JADX WARN: Removed duplicated region for block: B:218:0x0aea  */
    /* JADX WARN: Removed duplicated region for block: B:220:0x0a73 A[ADDED_TO_REGION] */
    /* JADX WARN: Removed duplicated region for block: B:223:0x0a05 A[ADDED_TO_REGION] */
    /* JADX WARN: Removed duplicated region for block: B:225:0x09a0  */
    /* JADX WARN: Removed duplicated region for block: B:227:0x0911 A[ADDED_TO_REGION] */
    /* JADX WARN: Removed duplicated region for block: B:228:0x08c8  */
    /* JADX WARN: Removed duplicated region for block: B:230:0x07eb A[ADDED_TO_REGION] */
    /* JADX WARN: Removed duplicated region for block: B:232:0x076e  */
    /* JADX WARN: Removed duplicated region for block: B:234:0x06cf A[ADDED_TO_REGION] */
    /* JADX WARN: Removed duplicated region for block: B:235:0x0686  */
    /* JADX WARN: Removed duplicated region for block: B:237:0x04f3 A[ADDED_TO_REGION] */
    /* JADX WARN: Removed duplicated region for block: B:240:0x0477 A[ADDED_TO_REGION] */
    /* JADX WARN: Removed duplicated region for block: B:244:0x0388  */
    /* JADX WARN: Removed duplicated region for block: B:77:0x0376  */
    /* JADX WARN: Removed duplicated region for block: B:80:0x0382  */
    /* JADX WARN: Removed duplicated region for block: B:88:0x044e  */
    /* JADX WARN: Removed duplicated region for block: B:95:0x046a  */
    /*
        Code decompiled incorrectly, please refer to instructions dump.
        To view partially-correct add '--show-bad-code' argument
    */
    public static final void StocktakeScreen(final androidx.compose.ui.Modifier r113, com.factory.wms.ui.viewmodel.MainUiState r114, final com.factory.wms.ui.viewmodel.MainViewModel r115, androidx.compose.runtime.Composer r116, final int r117) {
        /*
            Method dump skipped, instructions count: 2941
            To view this dump add '--comments-level debug' option
        */
        throw new UnsupportedOperationException("Method not decompiled: com.factory.wms.ui.screens.StocktakeScreenKt.StocktakeScreen(androidx.compose.ui.Modifier, com.factory.wms.ui.viewmodel.MainUiState, com.factory.wms.ui.viewmodel.MainViewModel, androidx.compose.runtime.Composer, int):void");
    }

    private static final String StocktakeScreen$lambda$1(MutableState<String> mutableState) {
        MutableState<String> $this$getValue$iv = mutableState;
        return $this$getValue$iv.getValue();
    }

    private static final boolean StocktakeScreen$lambda$4(MutableState<Boolean> mutableState) {
        MutableState<Boolean> $this$getValue$iv = mutableState;
        return $this$getValue$iv.getValue().booleanValue();
    }

    private static final void StocktakeScreen$lambda$5(MutableState<Boolean> mutableState, boolean z) {
        mutableState.setValue(Boolean.valueOf(z));
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final Unit StocktakeScreen$lambda$7$lambda$6(MutableState $scannerOpen$delegate) {
        StocktakeScreen$lambda$5($scannerOpen$delegate, false);
        return Unit.INSTANCE;
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final Unit StocktakeScreen$lambda$9$lambda$8(MainViewModel $viewModel, String it) {
        Intrinsics.checkNotNullParameter(it, "it");
        $viewModel.scanStocktake(it);
        return Unit.INSTANCE;
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final Unit StocktakeScreen$lambda$33$lambda$14$lambda$11$lambda$10(MainViewModel $viewModel) {
        $viewModel.setStocktakeMode("all");
        return Unit.INSTANCE;
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final Unit StocktakeScreen$lambda$33$lambda$14$lambda$13$lambda$12(MainViewModel $viewModel) {
        $viewModel.setStocktakeMode("warehouse");
        return Unit.INSTANCE;
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final Unit StocktakeScreen$lambda$33$lambda$20$lambda$17$lambda$16(MutableState $manualCode$delegate, String it) {
        Intrinsics.checkNotNullParameter(it, "it");
        $manualCode$delegate.setValue(it);
        return Unit.INSTANCE;
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final Unit StocktakeScreen$lambda$33$lambda$20$lambda$19$lambda$18(MainViewModel $viewModel, MutableState $manualCode$delegate) {
        $viewModel.scanStocktake(StocktakeScreen$lambda$1($manualCode$delegate));
        $manualCode$delegate.setValue("");
        return Unit.INSTANCE;
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final Unit StocktakeScreen$lambda$33$lambda$26$lambda$22$lambda$21(MutableState $scannerOpen$delegate) {
        StocktakeScreen$lambda$5($scannerOpen$delegate, true);
        return Unit.INSTANCE;
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final Unit StocktakeScreen$lambda$33$lambda$26$lambda$24$lambda$23(MainViewModel $viewModel) {
        $viewModel.clearLines(MainTab.Stocktake);
        return Unit.INSTANCE;
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final Unit StocktakeScreen$lambda$33$lambda$32$lambda$31(MainUiState $state, final MainViewModel $viewModel, LazyListScope LazyColumn) {
        Intrinsics.checkNotNullParameter(LazyColumn, "$this$LazyColumn");
        final List items$iv = $state.getStocktakeLines();
        final Function1 key$iv = new Function1() { // from class: com.factory.wms.ui.screens.StocktakeScreenKt$$ExternalSyntheticLambda0
            @Override // kotlin.jvm.functions.Function1
            public final Object invoke(Object obj) {
                Object StocktakeScreen$lambda$33$lambda$32$lambda$31$lambda$27;
                StocktakeScreen$lambda$33$lambda$32$lambda$31$lambda$27 = StocktakeScreenKt.StocktakeScreen$lambda$33$lambda$32$lambda$31$lambda$27((ScanLine) obj);
                return StocktakeScreen$lambda$33$lambda$32$lambda$31$lambda$27;
            }
        };
        final Function1 contentType$iv = new Function1() { // from class: com.factory.wms.ui.screens.StocktakeScreenKt$StocktakeScreen$lambda$33$lambda$32$lambda$31$$inlined$items$default$1
            @Override // kotlin.jvm.functions.Function1
            public /* bridge */ /* synthetic */ Object invoke(Object p1) {
                return invoke((ScanLine) p1);
            }

            @Override // kotlin.jvm.functions.Function1
            public final Void invoke(ScanLine scanLine) {
                return null;
            }
        };
        LazyColumn.items(items$iv.size(), new Function1<Integer, Object>() { // from class: com.factory.wms.ui.screens.StocktakeScreenKt$StocktakeScreen$lambda$33$lambda$32$lambda$31$$inlined$items$default$2
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
        }, new Function1<Integer, Object>() { // from class: com.factory.wms.ui.screens.StocktakeScreenKt$StocktakeScreen$lambda$33$lambda$32$lambda$31$$inlined$items$default$3
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
        }, ComposableLambdaKt.composableLambdaInstance(-632812321, true, new Function4<LazyItemScope, Integer, Composer, Integer, Unit>() { // from class: com.factory.wms.ui.screens.StocktakeScreenKt$StocktakeScreen$lambda$33$lambda$32$lambda$31$$inlined$items$default$4
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
                $composer.startReplaceableGroup(301874875);
                ComposerKt.sourceInformation($composer, "C*115@4566L124,118@4723L63,111@4375L706:StocktakeScreen.kt#3hfrnz");
                String valueOf = String.valueOf(line.getActualStock());
                $composer.startReplaceableGroup(979574754);
                ComposerKt.sourceInformation($composer, "CC(remember):StocktakeScreen.kt#9igjgp");
                boolean invalid$iv = $composer.changedInstance($viewModel) | (((($changed2 & 112) ^ 48) > 32 && $composer.changed(line)) || ($changed2 & 48) == 32);
                Object it$iv = $composer.rememberedValue();
                if (invalid$iv || it$iv == Composer.INSTANCE.getEmpty()) {
                    final MainViewModel mainViewModel = $viewModel;
                    value$iv = new Function1<String, Unit>() { // from class: com.factory.wms.ui.screens.StocktakeScreenKt$StocktakeScreen$3$5$1$2$1$1
                        @Override // kotlin.jvm.functions.Function1
                        public /* bridge */ /* synthetic */ Unit invoke(String str) {
                            invoke2(str);
                            return Unit.INSTANCE;
                        }

                        /* renamed from: invoke, reason: avoid collision after fix types in other method */
                        public final void invoke2(String it2) {
                            Intrinsics.checkNotNullParameter(it2, "it");
                            MainViewModel.this.updateActualStock(line.getMaterial().getCode(), CommonKt.toPositiveDoubleOrZero(it2));
                        }
                    };
                    $composer.updateRememberedValue(value$iv);
                } else {
                    value$iv = it$iv;
                }
                Function1 function1 = (Function1) value$iv;
                $composer.endReplaceableGroup();
                $composer.startReplaceableGroup(979579717);
                ComposerKt.sourceInformation($composer, "CC(remember):StocktakeScreen.kt#9igjgp");
                boolean invalid$iv2 = $composer.changedInstance($viewModel) | (((($changed2 & 112) ^ 48) > 32 && $composer.changed(line)) || ($changed2 & 48) == 32);
                Object it$iv2 = $composer.rememberedValue();
                if (invalid$iv2 || it$iv2 == Composer.INSTANCE.getEmpty()) {
                    final MainViewModel mainViewModel2 = $viewModel;
                    value$iv2 = new Function0<Unit>() { // from class: com.factory.wms.ui.screens.StocktakeScreenKt$StocktakeScreen$3$5$1$2$2$1
                        @Override // kotlin.jvm.functions.Function0
                        public /* bridge */ /* synthetic */ Unit invoke() {
                            invoke2();
                            return Unit.INSTANCE;
                        }

                        /* renamed from: invoke, reason: avoid collision after fix types in other method */
                        public final void invoke2() {
                            MainViewModel.this.deleteLine(MainTab.Stocktake, line.getMaterial().getCode());
                        }
                    };
                    $composer.updateRememberedValue(value$iv2);
                } else {
                    value$iv2 = it$iv2;
                }
                $composer.endReplaceableGroup();
                CommonKt.LineCard(line, "实盘数量", valueOf, function1, (Function0) value$iv2, ComposableLambdaKt.composableLambda($composer, 34116934, true, new Function2<Composer, Integer, Unit>() { // from class: com.factory.wms.ui.screens.StocktakeScreenKt$StocktakeScreen$3$5$1$2$3
                    @Override // kotlin.jvm.functions.Function2
                    public /* bridge */ /* synthetic */ Unit invoke(Composer composer, Integer num) {
                        invoke(composer, num.intValue());
                        return Unit.INSTANCE;
                    }

                    public final void invoke(Composer $composer2, int $changed3) {
                        ComposerKt.sourceInformation($composer2, "C121@4897L166:StocktakeScreen.kt#3hfrnz");
                        if (($changed3 & 3) != 2 || !$composer2.getSkipping()) {
                            if (ComposerKt.isTraceInProgress()) {
                                ComposerKt.traceEventStart(34116934, $changed3, -1, "com.factory.wms.ui.screens.StocktakeScreen.<anonymous>.<anonymous>.<anonymous>.<anonymous>.<anonymous> (StocktakeScreen.kt:120)");
                            }
                            double diff = ScanLine.this.getActualStock() - ScanLine.this.getMaterial().getStock();
                            TextKt.m2464Text4IGK_g((diff > 0.0d ? 1 : (diff == 0.0d ? 0 : -1)) == 0 ? "已盘点，无差异" : "差异：" + diff, PaddingKt.m566paddingqDBjuR0$default(Modifier.INSTANCE, 0.0f, Dp.m6094constructorimpl(8), 0.0f, 0.0f, 13, null), 0L, 0L, (FontStyle) null, (FontWeight) null, (FontFamily) null, 0L, (TextDecoration) null, (TextAlign) null, 0L, 0, false, 0, 0, (Function1<? super TextLayoutResult, Unit>) null, (TextStyle) null, $composer2, 48, 0, 131068);
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
    public static final Object StocktakeScreen$lambda$33$lambda$32$lambda$31$lambda$27(ScanLine it) {
        Intrinsics.checkNotNullParameter(it, "it");
        return it.getMaterial().getCode();
    }
}
