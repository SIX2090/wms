package com.factory.wms.ui.screens;

import androidx.compose.foundation.layout.ColumnScope;
import androidx.compose.foundation.layout.SizeKt;
import androidx.compose.material3.CardKt;
import androidx.compose.runtime.Composer;
import androidx.compose.runtime.ComposerKt;
import androidx.compose.runtime.MutableState;
import androidx.compose.runtime.RecomposeScopeImplKt;
import androidx.compose.runtime.ScopeUpdateScope;
import androidx.compose.runtime.internal.ComposableLambdaKt;
import androidx.compose.ui.Modifier;
import com.factory.wms.data.model.MaterialDto;
import com.factory.wms.ui.viewmodel.MainUiState;
import com.factory.wms.ui.viewmodel.MainViewModel;
import java.util.Arrays;
import kotlin.Metadata;
import kotlin.Unit;
import kotlin.jvm.functions.Function2;
import kotlin.jvm.functions.Function3;
import kotlin.jvm.internal.Intrinsics;

/* compiled from: QueryScreen.kt */
@Metadata(d1 = {"\u00006\n\u0000\n\u0002\u0010\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0010\u000e\n\u0000\n\u0002\u0010\u0006\n\u0002\b\u0003\n\u0002\u0010\u000b\u001a%\u0010\u0000\u001a\u00020\u00012\u0006\u0010\u0002\u001a\u00020\u00032\u0006\u0010\u0004\u001a\u00020\u00052\u0006\u0010\u0006\u001a\u00020\u0007H\u0007¢\u0006\u0002\u0010\b\u001a\u0015\u0010\t\u001a\u00020\u00012\u0006\u0010\n\u001a\u00020\u000bH\u0003¢\u0006\u0002\u0010\f\u001a\u0010\u0010\r\u001a\u00020\u000e2\u0006\u0010\u000f\u001a\u00020\u0010H\u0002¨\u0006\u0011²\u0006\n\u0010\u0012\u001a\u00020\u000eX\u008a\u008e\u0002²\u0006\n\u0010\u0013\u001a\u00020\u0014X\u008a\u008e\u0002"}, d2 = {"QueryScreen", "", "modifier", "Landroidx/compose/ui/Modifier;", "state", "Lcom/factory/wms/ui/viewmodel/MainUiState;", "viewModel", "Lcom/factory/wms/ui/viewmodel/MainViewModel;", "(Landroidx/compose/ui/Modifier;Lcom/factory/wms/ui/viewmodel/MainUiState;Lcom/factory/wms/ui/viewmodel/MainViewModel;Landroidx/compose/runtime/Composer;I)V", "QueryMaterialCard", "material", "Lcom/factory/wms/data/model/MaterialDto;", "(Lcom/factory/wms/data/model/MaterialDto;Landroidx/compose/runtime/Composer;I)V", "formatQuantity", "", "value", "", "app_debug", "manualCode", "scannerOpen", ""}, k = 2, mv = {2, 0, 0}, xi = 48)
/* loaded from: classes4.dex */
public final class QueryScreenKt {
    /* JADX INFO: Access modifiers changed from: private */
    public static final Unit QueryMaterialCard$lambda$22(MaterialDto materialDto, int i, Composer composer, int i2) {
        QueryMaterialCard(materialDto, composer, RecomposeScopeImplKt.updateChangedFlags(i | 1));
        return Unit.INSTANCE;
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final Unit QueryScreen$lambda$21(Modifier modifier, MainUiState mainUiState, MainViewModel mainViewModel, int i, Composer composer, int i2) {
        QueryScreen(modifier, mainUiState, mainViewModel, composer, RecomposeScopeImplKt.updateChangedFlags(i | 1));
        return Unit.INSTANCE;
    }

    /* JADX WARN: Removed duplicated region for block: B:102:0x0731  */
    /* JADX WARN: Removed duplicated region for block: B:105:0x076f  */
    /* JADX WARN: Removed duplicated region for block: B:107:0x06bd A[ADDED_TO_REGION] */
    /* JADX WARN: Removed duplicated region for block: B:108:0x0661  */
    /* JADX WARN: Removed duplicated region for block: B:110:0x05d9 A[ADDED_TO_REGION] */
    /* JADX WARN: Removed duplicated region for block: B:111:0x0590  */
    /* JADX WARN: Removed duplicated region for block: B:113:0x04b9 A[ADDED_TO_REGION] */
    /* JADX WARN: Removed duplicated region for block: B:114:0x044e  */
    /* JADX WARN: Removed duplicated region for block: B:116:0x03a8 A[ADDED_TO_REGION] */
    /* JADX WARN: Removed duplicated region for block: B:117:0x0361  */
    /* JADX WARN: Removed duplicated region for block: B:120:0x01f1  */
    /* JADX WARN: Removed duplicated region for block: B:53:0x01df  */
    /* JADX WARN: Removed duplicated region for block: B:56:0x01eb  */
    /* JADX WARN: Removed duplicated region for block: B:64:0x034f  */
    /* JADX WARN: Removed duplicated region for block: B:67:0x035b  */
    /* JADX WARN: Removed duplicated region for block: B:70:0x0392  */
    /* JADX WARN: Removed duplicated region for block: B:75:0x0440  */
    /* JADX WARN: Removed duplicated region for block: B:78:0x04ac  */
    /* JADX WARN: Removed duplicated region for block: B:83:0x057e  */
    /* JADX WARN: Removed duplicated region for block: B:86:0x058a  */
    /* JADX WARN: Removed duplicated region for block: B:89:0x05c3  */
    /* JADX WARN: Removed duplicated region for block: B:94:0x0653  */
    /* JADX WARN: Removed duplicated region for block: B:97:0x06b0  */
    /*
        Code decompiled incorrectly, please refer to instructions dump.
        To view partially-correct add '--show-bad-code' argument
    */
    public static final void QueryScreen(final androidx.compose.ui.Modifier r93, final com.factory.wms.ui.viewmodel.MainUiState r94, final com.factory.wms.ui.viewmodel.MainViewModel r95, androidx.compose.runtime.Composer r96, final int r97) {
        /*
            Method dump skipped, instructions count: 1934
            To view this dump add '--comments-level debug' option
        */
        throw new UnsupportedOperationException("Method not decompiled: com.factory.wms.ui.screens.QueryScreenKt.QueryScreen(androidx.compose.ui.Modifier, com.factory.wms.ui.viewmodel.MainUiState, com.factory.wms.ui.viewmodel.MainViewModel, androidx.compose.runtime.Composer, int):void");
    }

    private static final String QueryScreen$lambda$1(MutableState<String> mutableState) {
        MutableState<String> $this$getValue$iv = mutableState;
        return $this$getValue$iv.getValue();
    }

    private static final boolean QueryScreen$lambda$4(MutableState<Boolean> mutableState) {
        MutableState<Boolean> $this$getValue$iv = mutableState;
        return $this$getValue$iv.getValue().booleanValue();
    }

    private static final void QueryScreen$lambda$5(MutableState<Boolean> mutableState, boolean z) {
        mutableState.setValue(Boolean.valueOf(z));
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final Unit QueryScreen$lambda$7$lambda$6(MutableState $scannerOpen$delegate) {
        QueryScreen$lambda$5($scannerOpen$delegate, false);
        return Unit.INSTANCE;
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final Unit QueryScreen$lambda$9$lambda$8(MainViewModel $viewModel, String it) {
        Intrinsics.checkNotNullParameter(it, "it");
        $viewModel.scanQuery(it);
        return Unit.INSTANCE;
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final Unit QueryScreen$lambda$20$lambda$14$lambda$11$lambda$10(MutableState $manualCode$delegate, String it) {
        Intrinsics.checkNotNullParameter(it, "it");
        $manualCode$delegate.setValue(it);
        return Unit.INSTANCE;
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final Unit QueryScreen$lambda$20$lambda$14$lambda$13$lambda$12(MainViewModel $viewModel, MutableState $manualCode$delegate) {
        $viewModel.scanQuery(QueryScreen$lambda$1($manualCode$delegate));
        $manualCode$delegate.setValue("");
        return Unit.INSTANCE;
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final Unit QueryScreen$lambda$20$lambda$18$lambda$16$lambda$15(MutableState $scannerOpen$delegate) {
        QueryScreen$lambda$5($scannerOpen$delegate, true);
        return Unit.INSTANCE;
    }

    private static final void QueryMaterialCard(final MaterialDto material, Composer $composer, final int $changed) {
        Composer $composer2 = $composer.startRestartGroup(-1503284232);
        ComposerKt.sourceInformation($composer2, "C(QueryMaterialCard)89@3279L472:QueryScreen.kt#3hfrnz");
        int $dirty = $changed;
        if (($changed & 6) == 0) {
            $dirty |= $composer2.changed(material) ? 4 : 2;
        }
        int $dirty2 = $dirty;
        if (($dirty2 & 3) != 2 || !$composer2.getSkipping()) {
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventStart(-1503284232, $dirty2, -1, "com.factory.wms.ui.screens.QueryMaterialCard (QueryScreen.kt:88)");
            }
            CardKt.Card(SizeKt.fillMaxWidth$default(Modifier.INSTANCE, 0.0f, 1, null), null, null, null, null, ComposableLambdaKt.composableLambda($composer2, 324667242, true, new Function3<ColumnScope, Composer, Integer, Unit>() { // from class: com.factory.wms.ui.screens.QueryScreenKt$QueryMaterialCard$1
                @Override // kotlin.jvm.functions.Function3
                public /* bridge */ /* synthetic */ Unit invoke(ColumnScope columnScope, Composer composer, Integer num) {
                    invoke(columnScope, composer, num.intValue());
                    return Unit.INSTANCE;
                }

                /* JADX WARN: Removed duplicated region for block: B:24:0x01d0  */
                /* JADX WARN: Removed duplicated region for block: B:27:0x0222  */
                /* JADX WARN: Removed duplicated region for block: B:30:0x0275  */
                /* JADX WARN: Removed duplicated region for block: B:33:0x0281  */
                /* JADX WARN: Removed duplicated region for block: B:36:0x02e1  */
                /* JADX WARN: Removed duplicated region for block: B:38:? A[RETURN, SYNTHETIC] */
                /* JADX WARN: Removed duplicated region for block: B:39:0x0278  */
                /*
                    Code decompiled incorrectly, please refer to instructions dump.
                    To view partially-correct add '--show-bad-code' argument
                */
                public final void invoke(androidx.compose.foundation.layout.ColumnScope r76, androidx.compose.runtime.Composer r77, int r78) {
                    /*
                        Method dump skipped, instructions count: 741
                        To view this dump add '--comments-level debug' option
                    */
                    throw new UnsupportedOperationException("Method not decompiled: com.factory.wms.ui.screens.QueryScreenKt$QueryMaterialCard$1.invoke(androidx.compose.foundation.layout.ColumnScope, androidx.compose.runtime.Composer, int):void");
                }
            }), $composer2, 196614, 30);
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventEnd();
            }
        } else {
            $composer2.skipToGroupEnd();
        }
        ScopeUpdateScope endRestartGroup = $composer2.endRestartGroup();
        if (endRestartGroup != null) {
            endRestartGroup.updateScope(new Function2() { // from class: com.factory.wms.ui.screens.QueryScreenKt$$ExternalSyntheticLambda0
                @Override // kotlin.jvm.functions.Function2
                public final Object invoke(Object obj, Object obj2) {
                    Unit QueryMaterialCard$lambda$22;
                    QueryMaterialCard$lambda$22 = QueryScreenKt.QueryMaterialCard$lambda$22(MaterialDto.this, $changed, (Composer) obj, ((Integer) obj2).intValue());
                    return QueryMaterialCard$lambda$22;
                }
            });
        }
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final String formatQuantity(double value) {
        if (value % 1.0d == 0.0d) {
            return String.valueOf((int) value);
        }
        String format = String.format("%.2f", Arrays.copyOf(new Object[]{Double.valueOf(value)}, 1));
        Intrinsics.checkNotNullExpressionValue(format, "format(...)");
        return format;
    }
}
