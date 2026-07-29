package com.factory.wms.ui.screens;

import androidx.compose.foundation.layout.PaddingKt;
import androidx.compose.foundation.layout.PaddingValues;
import androidx.compose.foundation.layout.RowScope;
import androidx.compose.material3.NavigationBarKt;
import androidx.compose.material3.ScaffoldKt;
import androidx.compose.material3.SnackbarHostKt;
import androidx.compose.material3.SnackbarHostState;
import androidx.compose.runtime.Composer;
import androidx.compose.runtime.ComposerKt;
import androidx.compose.runtime.EffectsKt;
import androidx.compose.runtime.RecomposeScopeImplKt;
import androidx.compose.runtime.ScopeUpdateScope;
import androidx.compose.runtime.SnapshotStateKt;
import androidx.compose.runtime.State;
import androidx.compose.runtime.internal.ComposableLambdaKt;
import androidx.compose.ui.Modifier;
import androidx.profileinstaller.ProfileVerifier;
import com.factory.wms.ui.viewmodel.MainTab;
import com.factory.wms.ui.viewmodel.MainUiState;
import com.factory.wms.ui.viewmodel.MainViewModel;
import kotlin.Metadata;
import kotlin.NoWhenBranchMatchedException;
import kotlin.Unit;
import kotlin.jvm.functions.Function2;
import kotlin.jvm.functions.Function3;
import kotlin.jvm.internal.Intrinsics;
import kotlin.reflect.KFunction;

/* compiled from: WmsApp.kt */
@Metadata(d1 = {"\u0000\u0014\n\u0000\n\u0002\u0010\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0018\u0002\u001a\u0015\u0010\u0000\u001a\u00020\u00012\u0006\u0010\u0002\u001a\u00020\u0003H\u0007¢\u0006\u0002\u0010\u0004¨\u0006\u0005²\u0006\n\u0010\u0006\u001a\u00020\u0007X\u008a\u0084\u0002"}, d2 = {"WmsApp", "", "viewModel", "Lcom/factory/wms/ui/viewmodel/MainViewModel;", "(Lcom/factory/wms/ui/viewmodel/MainViewModel;Landroidx/compose/runtime/Composer;I)V", "app_debug", "state", "Lcom/factory/wms/ui/viewmodel/MainUiState;"}, k = 2, mv = {2, 0, 0}, xi = 48)
/* loaded from: classes4.dex */
public final class WmsAppKt {
    /* JADX INFO: Access modifiers changed from: private */
    public static final Unit WmsApp$lambda$4(MainViewModel mainViewModel, int i, Composer composer, int i2) {
        WmsApp(mainViewModel, composer, RecomposeScopeImplKt.updateChangedFlags(i | 1));
        return Unit.INSTANCE;
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final Unit WmsApp$lambda$5(MainViewModel mainViewModel, int i, Composer composer, int i2) {
        WmsApp(mainViewModel, composer, RecomposeScopeImplKt.updateChangedFlags(i | 1));
        return Unit.INSTANCE;
    }

    public static final void WmsApp(final MainViewModel viewModel, Composer $composer, final int $changed) {
        Object value$iv;
        Object value$iv2;
        Composer $composer2;
        Object value$iv3;
        Intrinsics.checkNotNullParameter(viewModel, "viewModel");
        Composer $composer3 = $composer.startRestartGroup(-1937646262);
        ComposerKt.sourceInformation($composer3, "C(WmsApp)27@1167L16,28@1212L32,30@1293L188,30@1250L231,43@1601L1638:WmsApp.kt#3hfrnz");
        int $dirty = $changed;
        if (($changed & 6) == 0) {
            $dirty |= $composer3.changedInstance(viewModel) ? 4 : 2;
        }
        int $dirty2 = $dirty;
        if (($dirty2 & 3) != 2 || !$composer3.getSkipping()) {
            if (ComposerKt.isTraceInProgress()) {
                ComposerKt.traceEventStart(-1937646262, $dirty2, -1, "com.factory.wms.ui.screens.WmsApp (WmsApp.kt:26)");
            }
            final State state$delegate = SnapshotStateKt.collectAsState(viewModel.getUiState(), null, $composer3, 0, 1);
            $composer3.startReplaceableGroup(1594112899);
            ComposerKt.sourceInformation($composer3, "CC(remember):WmsApp.kt#9igjgp");
            Object it$iv = $composer3.rememberedValue();
            if (it$iv == Composer.INSTANCE.getEmpty()) {
                value$iv = new SnackbarHostState();
                $composer3.updateRememberedValue(value$iv);
            } else {
                value$iv = it$iv;
            }
            final SnackbarHostState snackbarHostState = (SnackbarHostState) value$iv;
            $composer3.endReplaceableGroup();
            String message = WmsApp$lambda$0(state$delegate).getMessage();
            String error = WmsApp$lambda$0(state$delegate).getError();
            $composer3.startReplaceableGroup(1594115647);
            ComposerKt.sourceInformation($composer3, "CC(remember):WmsApp.kt#9igjgp");
            boolean invalid$iv = $composer3.changed(state$delegate) | $composer3.changedInstance(viewModel);
            Object it$iv2 = $composer3.rememberedValue();
            if (invalid$iv || it$iv2 == Composer.INSTANCE.getEmpty()) {
                value$iv2 = new WmsAppKt$WmsApp$1$1(snackbarHostState, viewModel, state$delegate, null);
                $composer3.updateRememberedValue(value$iv2);
            } else {
                value$iv2 = it$iv2;
            }
            $composer3.endReplaceableGroup();
            EffectsKt.LaunchedEffect(message, error, (Function2) value$iv2, $composer3, 0);
            $composer3.startReplaceableGroup(1594121775);
            ComposerKt.sourceInformation($composer3, "39@1557L16,39@1520L54");
            if (!WmsApp$lambda$0(state$delegate).isLoggedIn()) {
                MainUiState WmsApp$lambda$0 = WmsApp$lambda$0(state$delegate);
                $composer3.startReplaceableGroup(1594123923);
                ComposerKt.sourceInformation($composer3, "CC(remember):WmsApp.kt#9igjgp");
                boolean invalid$iv2 = $composer3.changedInstance(viewModel);
                Object it$iv3 = $composer3.rememberedValue();
                if (invalid$iv2 || it$iv3 == Composer.INSTANCE.getEmpty()) {
                    value$iv3 = new WmsAppKt$WmsApp$2$1(viewModel);
                    $composer3.updateRememberedValue(value$iv3);
                } else {
                    value$iv3 = it$iv3;
                }
                $composer3.endReplaceableGroup();
                LoginScreenKt.LoginScreen(WmsApp$lambda$0, (Function3) ((KFunction) value$iv3), $composer3, 0);
                $composer3.endReplaceableGroup();
                if (ComposerKt.isTraceInProgress()) {
                    ComposerKt.traceEventEnd();
                }
                ScopeUpdateScope endRestartGroup = $composer3.endRestartGroup();
                if (endRestartGroup != null) {
                    endRestartGroup.updateScope(new Function2() { // from class: com.factory.wms.ui.screens.WmsAppKt$$ExternalSyntheticLambda0
                        @Override // kotlin.jvm.functions.Function2
                        public final Object invoke(Object obj, Object obj2) {
                            Unit WmsApp$lambda$4;
                            WmsApp$lambda$4 = WmsAppKt.WmsApp$lambda$4(MainViewModel.this, $changed, (Composer) obj, ((Integer) obj2).intValue());
                            return WmsApp$lambda$4;
                        }
                    });
                    return;
                }
                return;
            }
            $composer3.endReplaceableGroup();
            $composer2 = $composer3;
            ScaffoldKt.m2119ScaffoldTvnljyQ(null, null, ComposableLambdaKt.composableLambda($composer3, -1569278513, true, new Function2<Composer, Integer, Unit>() { // from class: com.factory.wms.ui.screens.WmsAppKt$WmsApp$4

                /* compiled from: WmsApp.kt */
                @Metadata(k = 3, mv = {2, 0, 0}, xi = 48)
                /* renamed from: com.factory.wms.ui.screens.WmsAppKt$WmsApp$4$1, reason: invalid class name */
                static final class AnonymousClass1 implements Function3<RowScope, Composer, Integer, Unit> {
                    final /* synthetic */ State<MainUiState> $state$delegate;
                    final /* synthetic */ MainViewModel $viewModel;

                    AnonymousClass1(MainViewModel mainViewModel, State<MainUiState> state) {
                        this.$viewModel = mainViewModel;
                        this.$state$delegate = state;
                    }

                    @Override // kotlin.jvm.functions.Function3
                    public /* bridge */ /* synthetic */ Unit invoke(RowScope rowScope, Composer composer, Integer num) {
                        invoke(rowScope, composer, num.intValue());
                        return Unit.INSTANCE;
                    }

                    public final void invoke(RowScope NavigationBar, Composer $composer, int $changed) {
                        MainUiState WmsApp$lambda$0;
                        Object value$iv;
                        Intrinsics.checkNotNullParameter(NavigationBar, "$this$NavigationBar");
                        ComposerKt.sourceInformation($composer, "C*50@1904L28,48@1790L891:WmsApp.kt#3hfrnz");
                        int $dirty = $changed;
                        if (($changed & 6) == 0) {
                            $dirty |= $composer.changed(NavigationBar) ? 4 : 2;
                        }
                        int $dirty2 = $dirty;
                        if (($dirty2 & 19) != 18 || !$composer.getSkipping()) {
                            if (ComposerKt.isTraceInProgress()) {
                                ComposerKt.traceEventStart(-697761546, $dirty2, -1, "com.factory.wms.ui.screens.WmsApp.<anonymous>.<anonymous> (WmsApp.kt:47)");
                            }
                            Iterable $this$forEach$iv = MainTab.getEntries();
                            final MainViewModel mainViewModel = this.$viewModel;
                            State<MainUiState> state = this.$state$delegate;
                            for (Object element$iv : $this$forEach$iv) {
                                final MainTab tab = (MainTab) element$iv;
                                WmsApp$lambda$0 = WmsAppKt.WmsApp$lambda$0(state);
                                boolean z = WmsApp$lambda$0.getSelectedTab() == tab;
                                $composer.startReplaceableGroup(487526140);
                                ComposerKt.sourceInformation($composer, "CC(remember):WmsApp.kt#9igjgp");
                                boolean invalid$iv = $composer.changedInstance(mainViewModel) | $composer.changed(tab);
                                Object it$iv = $composer.rememberedValue();
                                if (invalid$iv || it$iv == Composer.INSTANCE.getEmpty()) {
                                    value$iv = 
                                    /*  JADX ERROR: Method code generation error
                                        jadx.core.utils.exceptions.CodegenException: Error generate insn: 0x00a6: CONSTRUCTOR (r8v1 'value$iv' java.lang.Object A[D('$i$a$-cache-WmsAppKt$WmsApp$4$1$1$1' int)]) = 
                                          (r12v1 'mainViewModel' com.factory.wms.ui.viewmodel.MainViewModel A[DONT_INLINE])
                                          (r10v1 'tab' com.factory.wms.ui.viewmodel.MainTab A[D('tab' com.factory.wms.ui.viewmodel.MainTab), DONT_INLINE])
                                         A[MD:(com.factory.wms.ui.viewmodel.MainViewModel, com.factory.wms.ui.viewmodel.MainTab):void (m)] (LINE:51) call: com.factory.wms.ui.screens.WmsAppKt$WmsApp$4$1$$ExternalSyntheticLambda0.<init>(com.factory.wms.ui.viewmodel.MainViewModel, com.factory.wms.ui.viewmodel.MainTab):void type: CONSTRUCTOR in method: com.factory.wms.ui.screens.WmsAppKt$WmsApp$4.1.invoke(androidx.compose.foundation.layout.RowScope, androidx.compose.runtime.Composer, int):void, file: classes4.dex
                                        	at jadx.core.codegen.InsnGen.makeInsn(InsnGen.java:310)
                                        	at jadx.core.codegen.InsnGen.makeInsn(InsnGen.java:273)
                                        	at jadx.core.codegen.RegionGen.makeSimpleBlock(RegionGen.java:94)
                                        	at jadx.core.dex.nodes.IBlock.generate(IBlock.java:15)
                                        	at jadx.core.codegen.RegionGen.makeRegion(RegionGen.java:66)
                                        	at jadx.core.dex.regions.Region.generate(Region.java:35)
                                        	at jadx.core.codegen.RegionGen.makeRegion(RegionGen.java:66)
                                        	at jadx.core.codegen.RegionGen.makeRegionIndent(RegionGen.java:83)
                                        	at jadx.core.codegen.RegionGen.makeIf(RegionGen.java:126)
                                        	at jadx.core.dex.regions.conditions.IfRegion.generate(IfRegion.java:90)
                                        	at jadx.core.codegen.RegionGen.makeRegion(RegionGen.java:66)
                                        	at jadx.core.dex.regions.Region.generate(Region.java:35)
                                        	at jadx.core.codegen.RegionGen.makeRegion(RegionGen.java:66)
                                        	at jadx.core.codegen.RegionGen.makeRegionIndent(RegionGen.java:83)
                                        	at jadx.core.codegen.RegionGen.makeLoop(RegionGen.java:207)
                                        	at jadx.core.dex.regions.loops.LoopRegion.generate(LoopRegion.java:171)
                                        	at jadx.core.codegen.RegionGen.makeRegion(RegionGen.java:66)
                                        	at jadx.core.dex.regions.Region.generate(Region.java:35)
                                        	at jadx.core.codegen.RegionGen.makeRegion(RegionGen.java:66)
                                        	at jadx.core.codegen.RegionGen.makeRegionIndent(RegionGen.java:83)
                                        	at jadx.core.codegen.RegionGen.makeIf(RegionGen.java:126)
                                        	at jadx.core.dex.regions.conditions.IfRegion.generate(IfRegion.java:90)
                                        	at jadx.core.codegen.RegionGen.makeRegion(RegionGen.java:66)
                                        	at jadx.core.dex.regions.Region.generate(Region.java:35)
                                        	at jadx.core.codegen.RegionGen.makeRegion(RegionGen.java:66)
                                        	at jadx.core.dex.regions.Region.generate(Region.java:35)
                                        	at jadx.core.codegen.RegionGen.makeRegion(RegionGen.java:66)
                                        	at jadx.core.codegen.MethodGen.addRegionInsns(MethodGen.java:297)
                                        	at jadx.core.codegen.MethodGen.addInstructions(MethodGen.java:276)
                                        	at jadx.core.codegen.ClassGen.addMethodCode(ClassGen.java:406)
                                        	at jadx.core.codegen.ClassGen.addMethod(ClassGen.java:335)
                                        	at jadx.core.codegen.ClassGen.lambda$addInnerClsAndMethods$3(ClassGen.java:301)
                                        	at java.base/java.util.stream.ForEachOps$ForEachOp$OfRef.accept(ForEachOps.java:186)
                                        	at java.base/java.util.ArrayList.forEach(ArrayList.java:1604)
                                        	at java.base/java.util.stream.SortedOps$RefSortingSink.end(SortedOps.java:395)
                                        	at java.base/java.util.stream.Sink$ChainedReference.end(Sink.java:261)
                                        	at java.base/java.util.stream.ReferencePipeline$7$1FlatMap.end(ReferencePipeline.java:284)
                                        	at java.base/java.util.stream.AbstractPipeline.copyInto(AbstractPipeline.java:571)
                                        	at java.base/java.util.stream.AbstractPipeline.wrapAndCopyInto(AbstractPipeline.java:560)
                                        	at java.base/java.util.stream.ForEachOps$ForEachOp.evaluateSequential(ForEachOps.java:153)
                                        	at java.base/java.util.stream.ForEachOps$ForEachOp$OfRef.evaluateSequential(ForEachOps.java:176)
                                        	at java.base/java.util.stream.AbstractPipeline.evaluate(AbstractPipeline.java:265)
                                        	at java.base/java.util.stream.ReferencePipeline.forEach(ReferencePipeline.java:632)
                                        	at jadx.core.codegen.ClassGen.addInnerClsAndMethods(ClassGen.java:297)
                                        	at jadx.core.codegen.ClassGen.addClassBody(ClassGen.java:286)
                                        	at jadx.core.codegen.ClassGen.addClassBody(ClassGen.java:270)
                                        	at jadx.core.codegen.ClassGen.addClassCode(ClassGen.java:161)
                                        	at jadx.core.codegen.ClassGen.addInnerClass(ClassGen.java:310)
                                        	at jadx.core.codegen.ClassGen.lambda$addInnerClsAndMethods$3(ClassGen.java:299)
                                        	at java.base/java.util.stream.ForEachOps$ForEachOp$OfRef.accept(ForEachOps.java:186)
                                        	at java.base/java.util.ArrayList.forEach(ArrayList.java:1604)
                                        	at java.base/java.util.stream.SortedOps$RefSortingSink.end(SortedOps.java:395)
                                        	at java.base/java.util.stream.Sink$ChainedReference.end(Sink.java:261)
                                        	at java.base/java.util.stream.ReferencePipeline$7$1FlatMap.end(ReferencePipeline.java:284)
                                        	at java.base/java.util.stream.AbstractPipeline.copyInto(AbstractPipeline.java:571)
                                        	at java.base/java.util.stream.AbstractPipeline.wrapAndCopyInto(AbstractPipeline.java:560)
                                        	at java.base/java.util.stream.ForEachOps$ForEachOp.evaluateSequential(ForEachOps.java:153)
                                        	at java.base/java.util.stream.ForEachOps$ForEachOp$OfRef.evaluateSequential(ForEachOps.java:176)
                                        	at java.base/java.util.stream.AbstractPipeline.evaluate(AbstractPipeline.java:265)
                                        	at java.base/java.util.stream.ReferencePipeline.forEach(ReferencePipeline.java:632)
                                        	at jadx.core.codegen.ClassGen.addInnerClsAndMethods(ClassGen.java:297)
                                        	at jadx.core.codegen.ClassGen.addClassBody(ClassGen.java:286)
                                        	at jadx.core.codegen.InsnGen.inlineAnonymousConstructor(InsnGen.java:845)
                                        	at jadx.core.codegen.InsnGen.makeConstructor(InsnGen.java:730)
                                        	at jadx.core.codegen.InsnGen.makeInsnBody(InsnGen.java:418)
                                        	at jadx.core.codegen.InsnGen.addWrappedArg(InsnGen.java:145)
                                        	at jadx.core.codegen.InsnGen.addArg(InsnGen.java:121)
                                        	at jadx.core.codegen.InsnGen.addArg(InsnGen.java:108)
                                        	at jadx.core.codegen.InsnGen.generateMethodArguments(InsnGen.java:1143)
                                        	at jadx.core.codegen.InsnGen.makeInvoke(InsnGen.java:910)
                                        	at jadx.core.codegen.InsnGen.makeInsnBody(InsnGen.java:422)
                                        	at jadx.core.codegen.InsnGen.addWrappedArg(InsnGen.java:145)
                                        	at jadx.core.codegen.InsnGen.addArg(InsnGen.java:121)
                                        	at jadx.core.codegen.InsnGen.addArg(InsnGen.java:108)
                                        	at jadx.core.codegen.InsnGen.generateMethodArguments(InsnGen.java:1143)
                                        	at jadx.core.codegen.InsnGen.makeInvoke(InsnGen.java:910)
                                        	at jadx.core.codegen.InsnGen.makeInsnBody(InsnGen.java:422)
                                        	at jadx.core.codegen.InsnGen.makeInsn(InsnGen.java:303)
                                        	at jadx.core.codegen.InsnGen.makeInsn(InsnGen.java:273)
                                        	at jadx.core.codegen.RegionGen.makeSimpleBlock(RegionGen.java:94)
                                        	at jadx.core.dex.nodes.IBlock.generate(IBlock.java:15)
                                        	at jadx.core.codegen.RegionGen.makeRegion(RegionGen.java:66)
                                        	at jadx.core.dex.regions.Region.generate(Region.java:35)
                                        	at jadx.core.codegen.RegionGen.makeRegion(RegionGen.java:66)
                                        	at jadx.core.dex.regions.Region.generate(Region.java:35)
                                        	at jadx.core.codegen.RegionGen.makeRegion(RegionGen.java:66)
                                        	at jadx.core.dex.regions.Region.generate(Region.java:35)
                                        	at jadx.core.codegen.RegionGen.makeRegion(RegionGen.java:66)
                                        	at jadx.core.codegen.RegionGen.makeRegionIndent(RegionGen.java:83)
                                        	at jadx.core.codegen.RegionGen.makeIf(RegionGen.java:126)
                                        	at jadx.core.dex.regions.conditions.IfRegion.generate(IfRegion.java:90)
                                        	at jadx.core.codegen.RegionGen.makeRegion(RegionGen.java:66)
                                        	at jadx.core.dex.regions.Region.generate(Region.java:35)
                                        	at jadx.core.codegen.RegionGen.makeRegion(RegionGen.java:66)
                                        	at jadx.core.codegen.MethodGen.addRegionInsns(MethodGen.java:297)
                                        	at jadx.core.codegen.MethodGen.addInstructions(MethodGen.java:276)
                                        	at jadx.core.codegen.ClassGen.addMethodCode(ClassGen.java:406)
                                        	at jadx.core.codegen.ClassGen.addMethod(ClassGen.java:335)
                                        	at jadx.core.codegen.ClassGen.lambda$addInnerClsAndMethods$3(ClassGen.java:301)
                                        	at java.base/java.util.stream.ForEachOps$ForEachOp$OfRef.accept(ForEachOps.java:186)
                                        	at java.base/java.util.ArrayList.forEach(ArrayList.java:1604)
                                        	at java.base/java.util.stream.SortedOps$RefSortingSink.end(SortedOps.java:395)
                                        	at java.base/java.util.stream.Sink$ChainedReference.end(Sink.java:261)
                                        	at java.base/java.util.stream.ReferencePipeline$7$1FlatMap.end(ReferencePipeline.java:284)
                                        	at java.base/java.util.stream.AbstractPipeline.copyInto(AbstractPipeline.java:571)
                                        	at java.base/java.util.stream.AbstractPipeline.wrapAndCopyInto(AbstractPipeline.java:560)
                                        	at java.base/java.util.stream.ForEachOps$ForEachOp.evaluateSequential(ForEachOps.java:153)
                                        	at java.base/java.util.stream.ForEachOps$ForEachOp$OfRef.evaluateSequential(ForEachOps.java:176)
                                        	at java.base/java.util.stream.AbstractPipeline.evaluate(AbstractPipeline.java:265)
                                        	at java.base/java.util.stream.ReferencePipeline.forEach(ReferencePipeline.java:632)
                                        	at jadx.core.codegen.ClassGen.addInnerClsAndMethods(ClassGen.java:297)
                                        	at jadx.core.codegen.ClassGen.addClassBody(ClassGen.java:286)
                                        	at jadx.core.codegen.ClassGen.addClassBody(ClassGen.java:270)
                                        	at jadx.core.codegen.ClassGen.addClassCode(ClassGen.java:161)
                                        	at jadx.core.codegen.ClassGen.makeClass(ClassGen.java:103)
                                        	at jadx.core.codegen.CodeGen.wrapCodeGen(CodeGen.java:45)
                                        	at jadx.core.codegen.CodeGen.generateJavaCode(CodeGen.java:34)
                                        	at jadx.core.codegen.CodeGen.generate(CodeGen.java:22)
                                        	at jadx.core.ProcessClass.process(ProcessClass.java:79)
                                        	at jadx.core.ProcessClass.generateCode(ProcessClass.java:117)
                                        	at jadx.core.dex.nodes.ClassNode.generateClassCode(ClassNode.java:402)
                                        	at jadx.core.dex.nodes.ClassNode.decompile(ClassNode.java:390)
                                        	at jadx.core.dex.nodes.ClassNode.getCode(ClassNode.java:340)
                                        Caused by: jadx.core.utils.exceptions.JadxRuntimeException: Expected class to be processed at this point, class: com.factory.wms.ui.screens.WmsAppKt$WmsApp$4$1$$ExternalSyntheticLambda0, state: NOT_LOADED
                                        	at jadx.core.dex.nodes.ClassNode.ensureProcessed(ClassNode.java:305)
                                        	at jadx.core.codegen.InsnGen.inlineAnonymousConstructor(InsnGen.java:807)
                                        	at jadx.core.codegen.InsnGen.makeConstructor(InsnGen.java:730)
                                        	at jadx.core.codegen.InsnGen.makeInsnBody(InsnGen.java:418)
                                        	at jadx.core.codegen.InsnGen.makeInsn(InsnGen.java:303)
                                        	... 122 more
                                        */
                                    /*
                                        Method dump skipped, instructions count: 275
                                        To view this dump add '--comments-level debug' option
                                    */
                                    throw new UnsupportedOperationException("Method not decompiled: com.factory.wms.ui.screens.WmsAppKt$WmsApp$4.AnonymousClass1.invoke(androidx.compose.foundation.layout.RowScope, androidx.compose.runtime.Composer, int):void");
                                }

                                /* JADX INFO: Access modifiers changed from: private */
                                public static final Unit invoke$lambda$2$lambda$1$lambda$0(MainViewModel $viewModel, MainTab $tab) {
                                    $viewModel.selectTab($tab);
                                    return Unit.INSTANCE;
                                }
                            }

                            @Override // kotlin.jvm.functions.Function2
                            public /* bridge */ /* synthetic */ Unit invoke(Composer composer, Integer num) {
                                invoke(composer, num.intValue());
                                return Unit.INSTANCE;
                            }

                            public final void invoke(Composer $composer4, int $changed2) {
                                ComposerKt.sourceInformation($composer4, "C46@1705L1008:WmsApp.kt#3hfrnz");
                                if (($changed2 & 3) != 2 || !$composer4.getSkipping()) {
                                    if (ComposerKt.isTraceInProgress()) {
                                        ComposerKt.traceEventStart(-1569278513, $changed2, -1, "com.factory.wms.ui.screens.WmsApp.<anonymous> (WmsApp.kt:46)");
                                    }
                                    NavigationBarKt.m2030NavigationBarHsRjFd4(null, 0L, 0L, 0.0f, null, ComposableLambdaKt.composableLambda($composer4, -697761546, true, new AnonymousClass1(MainViewModel.this, state$delegate)), $composer4, ProfileVerifier.CompilationStatus.RESULT_CODE_ERROR_CANT_WRITE_PROFILE_VERIFICATION_RESULT_CACHE_FILE, 31);
                                    if (ComposerKt.isTraceInProgress()) {
                                        ComposerKt.traceEventEnd();
                                        return;
                                    }
                                    return;
                                }
                                $composer4.skipToGroupEnd();
                            }
                        }), ComposableLambdaKt.composableLambda($composer3, 1755397776, true, new Function2<Composer, Integer, Unit>() { // from class: com.factory.wms.ui.screens.WmsAppKt$WmsApp$5
                            @Override // kotlin.jvm.functions.Function2
                            public /* bridge */ /* synthetic */ Unit invoke(Composer composer, Integer num) {
                                invoke(composer, num.intValue());
                                return Unit.INSTANCE;
                            }

                            public final void invoke(Composer $composer4, int $changed2) {
                                ComposerKt.sourceInformation($composer4, "C44@1636L31:WmsApp.kt#3hfrnz");
                                if (($changed2 & 3) == 2 && $composer4.getSkipping()) {
                                    $composer4.skipToGroupEnd();
                                    return;
                                }
                                if (ComposerKt.isTraceInProgress()) {
                                    ComposerKt.traceEventStart(1755397776, $changed2, -1, "com.factory.wms.ui.screens.WmsApp.<anonymous> (WmsApp.kt:44)");
                                }
                                SnackbarHostKt.SnackbarHost(SnackbarHostState.this, null, null, $composer4, 6, 6);
                                if (ComposerKt.isTraceInProgress()) {
                                    ComposerKt.traceEventEnd();
                                }
                            }
                        }), null, 0, 0L, 0L, null, ComposableLambdaKt.composableLambda($composer3, -1415503335, true, new Function3<PaddingValues, Composer, Integer, Unit>() { // from class: com.factory.wms.ui.screens.WmsAppKt$WmsApp$6

                            /* compiled from: WmsApp.kt */
                            @Metadata(k = 3, mv = {2, 0, 0}, xi = 48)
                            public /* synthetic */ class WhenMappings {
                                public static final /* synthetic */ int[] $EnumSwitchMapping$0;

                                static {
                                    int[] iArr = new int[MainTab.values().length];
                                    try {
                                        iArr[MainTab.Inbound.ordinal()] = 1;
                                    } catch (NoSuchFieldError e) {
                                    }
                                    try {
                                        iArr[MainTab.Outbound.ordinal()] = 2;
                                    } catch (NoSuchFieldError e2) {
                                    }
                                    try {
                                        iArr[MainTab.Query.ordinal()] = 3;
                                    } catch (NoSuchFieldError e3) {
                                    }
                                    try {
                                        iArr[MainTab.Stocktake.ordinal()] = 4;
                                    } catch (NoSuchFieldError e4) {
                                    }
                                    try {
                                        iArr[MainTab.Mine.ordinal()] = 5;
                                    } catch (NoSuchFieldError e5) {
                                    }
                                    $EnumSwitchMapping$0 = iArr;
                                }
                            }

                            @Override // kotlin.jvm.functions.Function3
                            public /* bridge */ /* synthetic */ Unit invoke(PaddingValues paddingValues, Composer composer, Integer num) {
                                invoke(paddingValues, composer, num.intValue());
                                return Unit.INSTANCE;
                            }

                            public final void invoke(PaddingValues padding, Composer $composer4, int $changed2) {
                                MainUiState WmsApp$lambda$02;
                                MainUiState WmsApp$lambda$03;
                                MainUiState WmsApp$lambda$04;
                                MainUiState WmsApp$lambda$05;
                                MainUiState WmsApp$lambda$06;
                                MainUiState WmsApp$lambda$07;
                                Intrinsics.checkNotNullParameter(padding, "padding");
                                ComposerKt.sourceInformation($composer4, "C:WmsApp.kt#3hfrnz");
                                int $dirty3 = $changed2;
                                if (($changed2 & 6) == 0) {
                                    $dirty3 |= $composer4.changed(padding) ? 4 : 2;
                                }
                                if (($dirty3 & 19) != 18 || !$composer4.getSkipping()) {
                                    if (ComposerKt.isTraceInProgress()) {
                                        ComposerKt.traceEventStart(-1415503335, $dirty3, -1, "com.factory.wms.ui.screens.WmsApp.<anonymous> (WmsApp.kt:69)");
                                    }
                                    WmsApp$lambda$02 = WmsAppKt.WmsApp$lambda$0(state$delegate);
                                    switch (WhenMappings.$EnumSwitchMapping$0[WmsApp$lambda$02.getSelectedTab().ordinal()]) {
                                        case 1:
                                            $composer4.startReplaceableGroup(1136691388);
                                            ComposerKt.sourceInformation($composer4, "70@2809L58");
                                            Modifier padding2 = PaddingKt.padding(Modifier.INSTANCE, padding);
                                            WmsApp$lambda$03 = WmsAppKt.WmsApp$lambda$0(state$delegate);
                                            InboundScreenKt.InboundScreen(padding2, WmsApp$lambda$03, MainViewModel.this, $composer4, 0);
                                            $composer4.endReplaceableGroup();
                                            break;
                                        case 2:
                                            $composer4.startReplaceableGroup(1136694301);
                                            ComposerKt.sourceInformation($composer4, "71@2900L59");
                                            Modifier padding3 = PaddingKt.padding(Modifier.INSTANCE, padding);
                                            WmsApp$lambda$04 = WmsAppKt.WmsApp$lambda$0(state$delegate);
                                            OutboundScreenKt.OutboundScreen(padding3, WmsApp$lambda$04, MainViewModel.this, $composer4, 0);
                                            $composer4.endReplaceableGroup();
                                            break;
                                        case 3:
                                            $composer4.startReplaceableGroup(1136697146);
                                            ComposerKt.sourceInformation($composer4, "72@2989L56");
                                            Modifier padding4 = PaddingKt.padding(Modifier.INSTANCE, padding);
                                            WmsApp$lambda$05 = WmsAppKt.WmsApp$lambda$0(state$delegate);
                                            QueryScreenKt.QueryScreen(padding4, WmsApp$lambda$05, MainViewModel.this, $composer4, 0);
                                            $composer4.endReplaceableGroup();
                                            break;
                                        case 4:
                                            $composer4.startReplaceableGroup(1136700030);
                                            ComposerKt.sourceInformation($composer4, "73@3079L60");
                                            Modifier padding5 = PaddingKt.padding(Modifier.INSTANCE, padding);
                                            WmsApp$lambda$06 = WmsAppKt.WmsApp$lambda$0(state$delegate);
                                            StocktakeScreenKt.StocktakeScreen(padding5, WmsApp$lambda$06, MainViewModel.this, $composer4, 0);
                                            $composer4.endReplaceableGroup();
                                            break;
                                        case 5:
                                            $composer4.startReplaceableGroup(1136702873);
                                            ComposerKt.sourceInformation($composer4, "74@3168L55");
                                            Modifier padding6 = PaddingKt.padding(Modifier.INSTANCE, padding);
                                            WmsApp$lambda$07 = WmsAppKt.WmsApp$lambda$0(state$delegate);
                                            MineScreenKt.MineScreen(padding6, WmsApp$lambda$07, MainViewModel.this, $composer4, 0);
                                            $composer4.endReplaceableGroup();
                                            break;
                                        default:
                                            $composer4.startReplaceableGroup(1136689956);
                                            $composer4.endReplaceableGroup();
                                            throw new NoWhenBranchMatchedException();
                                    }
                                    if (ComposerKt.isTraceInProgress()) {
                                        ComposerKt.traceEventEnd();
                                        return;
                                    }
                                    return;
                                }
                                $composer4.skipToGroupEnd();
                            }
                        }), $composer3, 805309824, 499);
                        if (ComposerKt.isTraceInProgress()) {
                            ComposerKt.traceEventEnd();
                        }
                    } else {
                        $composer3.skipToGroupEnd();
                        $composer2 = $composer3;
                    }
                    ScopeUpdateScope endRestartGroup2 = $composer2.endRestartGroup();
                    if (endRestartGroup2 != null) {
                        endRestartGroup2.updateScope(new Function2() { // from class: com.factory.wms.ui.screens.WmsAppKt$$ExternalSyntheticLambda1
                            @Override // kotlin.jvm.functions.Function2
                            public final Object invoke(Object obj, Object obj2) {
                                Unit WmsApp$lambda$5;
                                WmsApp$lambda$5 = WmsAppKt.WmsApp$lambda$5(MainViewModel.this, $changed, (Composer) obj, ((Integer) obj2).intValue());
                                return WmsApp$lambda$5;
                            }
                        });
                    }
                }

                /* JADX INFO: Access modifiers changed from: private */
                public static final MainUiState WmsApp$lambda$0(State<MainUiState> state) {
                    Object thisObj$iv = state.getValue();
                    return (MainUiState) thisObj$iv;
                }
            }
