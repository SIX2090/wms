package androidx.compose.ui.focus;

import androidx.compose.runtime.collection.MutableVector;
import androidx.compose.ui.Modifier;
import androidx.compose.ui.node.DelegatableNode;
import androidx.compose.ui.node.DelegatableNodeKt;
import androidx.compose.ui.node.DelegatingNode;
import androidx.compose.ui.node.NodeKind;
import kotlin.Metadata;
import kotlin.jvm.functions.Function1;

/* compiled from: FocusRequesterModifierNode.kt */
@Metadata(d1 = {"\u0000\u000e\n\u0000\n\u0002\u0010\u000b\n\u0002\u0018\u0002\n\u0002\b\u0005\u001a\n\u0010\u0000\u001a\u00020\u0001*\u00020\u0002\u001a\n\u0010\u0003\u001a\u00020\u0001*\u00020\u0002\u001a\n\u0010\u0004\u001a\u00020\u0001*\u00020\u0002\u001a\f\u0010\u0005\u001a\u00020\u0001*\u00020\u0002H\u0007\u001a\f\u0010\u0006\u001a\u00020\u0001*\u00020\u0002H\u0007¨\u0006\u0007"}, d2 = {"captureFocus", "", "Landroidx/compose/ui/focus/FocusRequesterModifierNode;", "freeFocus", "requestFocus", "restoreFocusedChild", "saveFocusedChild", "ui_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class FocusRequesterModifierNodeKt {
    public static final boolean requestFocus(FocusRequesterModifierNode $this$requestFocus) {
        int type$iv;
        int type$iv2;
        DelegatingNode this_$iv$iv$iv;
        int count$iv$iv;
        MutableVector mutableVector;
        int i;
        Modifier.Node $this$dispatchForKind_u2d6rFNWt0$iv$iv;
        int i2;
        Modifier.Node $this$dispatchForKind_u2d6rFNWt0$iv$iv2;
        MutableVector mutableVector2;
        FocusRequesterModifierNode $this$visitSelfAndChildren_u2d6rFNWt0$iv = $this$requestFocus;
        int type$iv3 = NodeKind.m5222constructorimpl(1024);
        int i3 = 0;
        Modifier.Node $this$dispatchForKind_u2d6rFNWt0$iv$iv3 = $this$visitSelfAndChildren_u2d6rFNWt0$iv.getNode();
        MutableVector mutableVector3 = null;
        Modifier.Node node = $this$dispatchForKind_u2d6rFNWt0$iv$iv3;
        while (true) {
            int i4 = 1;
            if (node == null) {
                int mask$iv$iv = type$iv3;
                if (!$this$visitSelfAndChildren_u2d6rFNWt0$iv.getNode().getIsAttached()) {
                    throw new IllegalStateException("visitChildren called on an unattached node".toString());
                }
                MutableVector branches$iv$iv = new MutableVector(new Modifier.Node[16], 0);
                Modifier.Node child$iv$iv = $this$visitSelfAndChildren_u2d6rFNWt0$iv.getNode().getChild();
                if (child$iv$iv == null) {
                    DelegatableNodeKt.addLayoutNodeChildren(branches$iv$iv, $this$visitSelfAndChildren_u2d6rFNWt0$iv.getNode());
                } else {
                    branches$iv$iv.add(child$iv$iv);
                }
                while (branches$iv$iv.isNotEmpty()) {
                    Modifier.Node branch$iv$iv = (Modifier.Node) branches$iv$iv.removeAt(branches$iv$iv.getSize() - 1);
                    if ((branch$iv$iv.getAggregateChildKindSet() & mask$iv$iv) != 0) {
                        Modifier.Node node$iv$iv = branch$iv$iv;
                        while (true) {
                            if (node$iv$iv == null) {
                                type$iv3 = type$iv3;
                                break;
                            }
                            if ((node$iv$iv.getKindSet() & mask$iv$iv) != 0) {
                                Modifier.Node it$iv = node$iv$iv;
                                MutableVector mutableVector4 = null;
                                Modifier.Node this_$iv$iv$iv2 = it$iv;
                                while (this_$iv$iv$iv2 != null) {
                                    if (this_$iv$iv$iv2 instanceof FocusTargetNode) {
                                        FocusTargetNode focusTarget = (FocusTargetNode) this_$iv$iv$iv2;
                                        FocusProperties focusProperties = focusTarget.fetchFocusProperties$ui_release();
                                        return focusProperties.getCanFocus() ? FocusTransactionsKt.requestFocus(focusTarget) : TwoDimensionalFocusSearchKt.m3466findChildCorrespondingToFocusEnterOMvw8(focusTarget, FocusDirection.INSTANCE.m3432getEnterdhqQ8s(), new Function1<FocusTargetNode, Boolean>() { // from class: androidx.compose.ui.focus.FocusRequesterModifierNodeKt$requestFocus$1$1
                                            @Override // kotlin.jvm.functions.Function1
                                            public final Boolean invoke(FocusTargetNode it) {
                                                return Boolean.valueOf(FocusTransactionsKt.requestFocus(it));
                                            }
                                        });
                                    }
                                    DelegatableNode $this$visitSelfAndChildren_u2d6rFNWt0$iv2 = $this$visitSelfAndChildren_u2d6rFNWt0$iv;
                                    int mask$iv$iv2 = mask$iv$iv;
                                    if (((this_$iv$iv$iv2.getKindSet() & type$iv3) != 0) && (this_$iv$iv$iv2 instanceof DelegatingNode)) {
                                        int count$iv$iv2 = 0;
                                        DelegatingNode this_$iv$iv$iv3 = (DelegatingNode) this_$iv$iv$iv2;
                                        Modifier.Node node$iv$iv$iv = this_$iv$iv$iv3.getDelegate();
                                        while (node$iv$iv$iv != null) {
                                            Modifier.Node next$iv$iv = node$iv$iv$iv;
                                            if ((next$iv$iv.getKindSet() & type$iv3) != 0) {
                                                count$iv$iv2++;
                                                type$iv2 = type$iv3;
                                                if (count$iv$iv2 == 1) {
                                                    this_$iv$iv$iv2 = next$iv$iv;
                                                    this_$iv$iv$iv = this_$iv$iv$iv3;
                                                } else {
                                                    if (mutableVector4 == null) {
                                                        count$iv$iv = count$iv$iv2;
                                                        this_$iv$iv$iv = this_$iv$iv$iv3;
                                                        mutableVector = new MutableVector(new Modifier.Node[16], 0);
                                                    } else {
                                                        count$iv$iv = count$iv$iv2;
                                                        this_$iv$iv$iv = this_$iv$iv$iv3;
                                                        mutableVector = mutableVector4;
                                                    }
                                                    mutableVector4 = mutableVector;
                                                    Modifier.Node theNode$iv$iv = this_$iv$iv$iv2;
                                                    if (theNode$iv$iv != null) {
                                                        if (mutableVector4 != null) {
                                                            mutableVector4.add(theNode$iv$iv);
                                                        }
                                                        this_$iv$iv$iv2 = null;
                                                    }
                                                    if (mutableVector4 != null) {
                                                        mutableVector4.add(next$iv$iv);
                                                    }
                                                    count$iv$iv2 = count$iv$iv;
                                                }
                                            } else {
                                                type$iv2 = type$iv3;
                                                this_$iv$iv$iv = this_$iv$iv$iv3;
                                            }
                                            node$iv$iv$iv = node$iv$iv$iv.getChild();
                                            type$iv3 = type$iv2;
                                            this_$iv$iv$iv3 = this_$iv$iv$iv;
                                        }
                                        type$iv = type$iv3;
                                        if (count$iv$iv2 == 1) {
                                            $this$visitSelfAndChildren_u2d6rFNWt0$iv = $this$visitSelfAndChildren_u2d6rFNWt0$iv2;
                                            mask$iv$iv = mask$iv$iv2;
                                            type$iv3 = type$iv;
                                        }
                                    } else {
                                        type$iv = type$iv3;
                                    }
                                    this_$iv$iv$iv2 = DelegatableNodeKt.pop(mutableVector4);
                                    $this$visitSelfAndChildren_u2d6rFNWt0$iv = $this$visitSelfAndChildren_u2d6rFNWt0$iv2;
                                    mask$iv$iv = mask$iv$iv2;
                                    type$iv3 = type$iv;
                                }
                                type$iv3 = type$iv3;
                            } else {
                                node$iv$iv = node$iv$iv.getChild();
                                type$iv3 = type$iv3;
                            }
                        }
                    } else {
                        DelegatableNodeKt.addLayoutNodeChildren(branches$iv$iv, branch$iv$iv);
                    }
                }
                return false;
            }
            if (node instanceof FocusTargetNode) {
                FocusTargetNode focusTarget2 = (FocusTargetNode) node;
                FocusProperties focusProperties2 = focusTarget2.fetchFocusProperties$ui_release();
                return focusProperties2.getCanFocus() ? FocusTransactionsKt.requestFocus(focusTarget2) : TwoDimensionalFocusSearchKt.m3466findChildCorrespondingToFocusEnterOMvw8(focusTarget2, FocusDirection.INSTANCE.m3432getEnterdhqQ8s(), new Function1<FocusTargetNode, Boolean>() { // from class: androidx.compose.ui.focus.FocusRequesterModifierNodeKt$requestFocus$1$1
                    @Override // kotlin.jvm.functions.Function1
                    public final Boolean invoke(FocusTargetNode it) {
                        return Boolean.valueOf(FocusTransactionsKt.requestFocus(it));
                    }
                });
            }
            Modifier.Node this_$iv$iv$iv4 = node;
            Modifier.Node this_$iv$iv$iv5 = (this_$iv$iv$iv4.getKindSet() & type$iv3) != 0 ? 1 : null;
            if (this_$iv$iv$iv5 == null || !(node instanceof DelegatingNode)) {
                i = i3;
                $this$dispatchForKind_u2d6rFNWt0$iv$iv = $this$dispatchForKind_u2d6rFNWt0$iv$iv3;
            } else {
                int count$iv$iv3 = 0;
                DelegatingNode this_$iv$iv$iv6 = (DelegatingNode) node;
                Modifier.Node node$iv$iv$iv2 = this_$iv$iv$iv6.getDelegate();
                while (node$iv$iv$iv2 != null) {
                    Modifier.Node next$iv$iv2 = node$iv$iv$iv2;
                    if (((next$iv$iv2.getKindSet() & type$iv3) != 0 ? i4 : 0) != 0) {
                        count$iv$iv3++;
                        if (count$iv$iv3 == i4) {
                            node = next$iv$iv2;
                            i2 = i3;
                            $this$dispatchForKind_u2d6rFNWt0$iv$iv2 = $this$dispatchForKind_u2d6rFNWt0$iv$iv3;
                        } else {
                            if (mutableVector3 == null) {
                                i2 = i3;
                                $this$dispatchForKind_u2d6rFNWt0$iv$iv2 = $this$dispatchForKind_u2d6rFNWt0$iv$iv3;
                                mutableVector2 = new MutableVector(new Modifier.Node[16], 0);
                            } else {
                                i2 = i3;
                                $this$dispatchForKind_u2d6rFNWt0$iv$iv2 = $this$dispatchForKind_u2d6rFNWt0$iv$iv3;
                                mutableVector2 = mutableVector3;
                            }
                            mutableVector3 = mutableVector2;
                            Modifier.Node theNode$iv$iv2 = node;
                            if (theNode$iv$iv2 != null) {
                                if (mutableVector3 != null) {
                                    mutableVector3.add(theNode$iv$iv2);
                                }
                                node = null;
                            }
                            if (mutableVector3 != null) {
                                mutableVector3.add(next$iv$iv2);
                            }
                        }
                    } else {
                        i2 = i3;
                        $this$dispatchForKind_u2d6rFNWt0$iv$iv2 = $this$dispatchForKind_u2d6rFNWt0$iv$iv3;
                    }
                    node$iv$iv$iv2 = node$iv$iv$iv2.getChild();
                    i3 = i2;
                    $this$dispatchForKind_u2d6rFNWt0$iv$iv3 = $this$dispatchForKind_u2d6rFNWt0$iv$iv2;
                    i4 = 1;
                }
                i = i3;
                $this$dispatchForKind_u2d6rFNWt0$iv$iv = $this$dispatchForKind_u2d6rFNWt0$iv$iv3;
                if (count$iv$iv3 == 1) {
                    i3 = i;
                    $this$dispatchForKind_u2d6rFNWt0$iv$iv3 = $this$dispatchForKind_u2d6rFNWt0$iv$iv;
                }
            }
            node = DelegatableNodeKt.pop(mutableVector3);
            i3 = i;
            $this$dispatchForKind_u2d6rFNWt0$iv$iv3 = $this$dispatchForKind_u2d6rFNWt0$iv$iv;
        }
    }

    public static final boolean captureFocus(FocusRequesterModifierNode $this$captureFocus) {
        DelegatableNode $this$visitSelfAndChildren_u2d6rFNWt0$iv;
        int type$iv;
        int mask$iv$iv;
        DelegatableNode $this$visitSelfAndChildren_u2d6rFNWt0$iv2;
        int type$iv2;
        int mask$iv$iv2;
        MutableVector mutableVector;
        int i;
        Modifier.Node $this$dispatchForKind_u2d6rFNWt0$iv$iv;
        int i2;
        Modifier.Node $this$dispatchForKind_u2d6rFNWt0$iv$iv2;
        MutableVector mutableVector2;
        FocusRequesterModifierNode $this$visitSelfAndChildren_u2d6rFNWt0$iv3 = $this$captureFocus;
        int type$iv3 = NodeKind.m5222constructorimpl(1024);
        int i3 = 0;
        Modifier.Node $this$dispatchForKind_u2d6rFNWt0$iv$iv3 = $this$visitSelfAndChildren_u2d6rFNWt0$iv3.getNode();
        MutableVector mutableVector3 = null;
        Modifier.Node node = $this$dispatchForKind_u2d6rFNWt0$iv$iv3;
        while (true) {
            int i4 = 1;
            if (node == null) {
                int mask$iv$iv3 = type$iv3;
                if (!$this$visitSelfAndChildren_u2d6rFNWt0$iv3.getNode().getIsAttached()) {
                    throw new IllegalStateException("visitChildren called on an unattached node".toString());
                }
                MutableVector branches$iv$iv = new MutableVector(new Modifier.Node[16], 0);
                Modifier.Node child$iv$iv = $this$visitSelfAndChildren_u2d6rFNWt0$iv3.getNode().getChild();
                if (child$iv$iv == null) {
                    DelegatableNodeKt.addLayoutNodeChildren(branches$iv$iv, $this$visitSelfAndChildren_u2d6rFNWt0$iv3.getNode());
                } else {
                    branches$iv$iv.add(child$iv$iv);
                }
                while (branches$iv$iv.isNotEmpty()) {
                    Modifier.Node branch$iv$iv = (Modifier.Node) branches$iv$iv.removeAt(branches$iv$iv.getSize() - 1);
                    if ((branch$iv$iv.getAggregateChildKindSet() & mask$iv$iv3) != 0) {
                        Modifier.Node node$iv$iv = branch$iv$iv;
                        while (true) {
                            if (node$iv$iv == null) {
                                $this$visitSelfAndChildren_u2d6rFNWt0$iv3 = $this$visitSelfAndChildren_u2d6rFNWt0$iv3;
                                break;
                            }
                            if ((node$iv$iv.getKindSet() & mask$iv$iv3) != 0) {
                                Modifier.Node it$iv = node$iv$iv;
                                MutableVector mutableVector4 = null;
                                Modifier.Node node2 = it$iv;
                                while (node2 != null) {
                                    if (node2 instanceof FocusTargetNode) {
                                        FocusTargetNode it = (FocusTargetNode) node2;
                                        if (FocusTransactionsKt.captureFocus(it)) {
                                            return true;
                                        }
                                        $this$visitSelfAndChildren_u2d6rFNWt0$iv = $this$visitSelfAndChildren_u2d6rFNWt0$iv3;
                                        type$iv = type$iv3;
                                        mask$iv$iv = mask$iv$iv3;
                                    } else {
                                        Modifier.Node this_$iv$iv$iv = node2;
                                        if (((this_$iv$iv$iv.getKindSet() & type$iv3) != 0) && (node2 instanceof DelegatingNode)) {
                                            int count$iv$iv = 0;
                                            DelegatingNode this_$iv$iv$iv2 = (DelegatingNode) node2;
                                            Modifier.Node node$iv$iv$iv = this_$iv$iv$iv2.getDelegate();
                                            while (node$iv$iv$iv != null) {
                                                Modifier.Node next$iv$iv = node$iv$iv$iv;
                                                if ((next$iv$iv.getKindSet() & type$iv3) != 0) {
                                                    count$iv$iv++;
                                                    $this$visitSelfAndChildren_u2d6rFNWt0$iv2 = $this$visitSelfAndChildren_u2d6rFNWt0$iv3;
                                                    if (count$iv$iv == 1) {
                                                        node2 = next$iv$iv;
                                                        type$iv2 = type$iv3;
                                                        mask$iv$iv2 = mask$iv$iv3;
                                                    } else {
                                                        if (mutableVector4 == null) {
                                                            type$iv2 = type$iv3;
                                                            mask$iv$iv2 = mask$iv$iv3;
                                                            mutableVector = new MutableVector(new Modifier.Node[16], 0);
                                                        } else {
                                                            type$iv2 = type$iv3;
                                                            mask$iv$iv2 = mask$iv$iv3;
                                                            mutableVector = mutableVector4;
                                                        }
                                                        mutableVector4 = mutableVector;
                                                        Modifier.Node theNode$iv$iv = node2;
                                                        if (theNode$iv$iv != null) {
                                                            if (mutableVector4 != null) {
                                                                mutableVector4.add(theNode$iv$iv);
                                                            }
                                                            node2 = null;
                                                        }
                                                        if (mutableVector4 != null) {
                                                            mutableVector4.add(next$iv$iv);
                                                        }
                                                    }
                                                } else {
                                                    $this$visitSelfAndChildren_u2d6rFNWt0$iv2 = $this$visitSelfAndChildren_u2d6rFNWt0$iv3;
                                                    type$iv2 = type$iv3;
                                                    mask$iv$iv2 = mask$iv$iv3;
                                                }
                                                node$iv$iv$iv = node$iv$iv$iv.getChild();
                                                $this$visitSelfAndChildren_u2d6rFNWt0$iv3 = $this$visitSelfAndChildren_u2d6rFNWt0$iv2;
                                                type$iv3 = type$iv2;
                                                mask$iv$iv3 = mask$iv$iv2;
                                            }
                                            $this$visitSelfAndChildren_u2d6rFNWt0$iv = $this$visitSelfAndChildren_u2d6rFNWt0$iv3;
                                            type$iv = type$iv3;
                                            mask$iv$iv = mask$iv$iv3;
                                            if (count$iv$iv == 1) {
                                                $this$visitSelfAndChildren_u2d6rFNWt0$iv3 = $this$visitSelfAndChildren_u2d6rFNWt0$iv;
                                                type$iv3 = type$iv;
                                                mask$iv$iv3 = mask$iv$iv;
                                            }
                                        } else {
                                            $this$visitSelfAndChildren_u2d6rFNWt0$iv = $this$visitSelfAndChildren_u2d6rFNWt0$iv3;
                                            type$iv = type$iv3;
                                            mask$iv$iv = mask$iv$iv3;
                                        }
                                    }
                                    node2 = DelegatableNodeKt.pop(mutableVector4);
                                    $this$visitSelfAndChildren_u2d6rFNWt0$iv3 = $this$visitSelfAndChildren_u2d6rFNWt0$iv;
                                    type$iv3 = type$iv;
                                    mask$iv$iv3 = mask$iv$iv;
                                }
                                $this$visitSelfAndChildren_u2d6rFNWt0$iv3 = $this$visitSelfAndChildren_u2d6rFNWt0$iv3;
                            } else {
                                node$iv$iv = node$iv$iv.getChild();
                                $this$visitSelfAndChildren_u2d6rFNWt0$iv3 = $this$visitSelfAndChildren_u2d6rFNWt0$iv3;
                            }
                        }
                    } else {
                        DelegatableNodeKt.addLayoutNodeChildren(branches$iv$iv, branch$iv$iv);
                    }
                }
                return false;
            }
            if (node instanceof FocusTargetNode) {
                FocusTargetNode it2 = (FocusTargetNode) node;
                if (FocusTransactionsKt.captureFocus(it2)) {
                    return true;
                }
                i = i3;
                $this$dispatchForKind_u2d6rFNWt0$iv$iv = $this$dispatchForKind_u2d6rFNWt0$iv$iv3;
            } else {
                Modifier.Node this_$iv$iv$iv3 = node;
                Modifier.Node this_$iv$iv$iv4 = (this_$iv$iv$iv3.getKindSet() & type$iv3) != 0 ? 1 : null;
                if (this_$iv$iv$iv4 == null || !(node instanceof DelegatingNode)) {
                    i = i3;
                    $this$dispatchForKind_u2d6rFNWt0$iv$iv = $this$dispatchForKind_u2d6rFNWt0$iv$iv3;
                } else {
                    int count$iv$iv2 = 0;
                    DelegatingNode this_$iv$iv$iv5 = (DelegatingNode) node;
                    Modifier.Node node$iv$iv$iv2 = this_$iv$iv$iv5.getDelegate();
                    while (node$iv$iv$iv2 != null) {
                        Modifier.Node next$iv$iv2 = node$iv$iv$iv2;
                        if (((next$iv$iv2.getKindSet() & type$iv3) != 0 ? i4 : 0) != 0) {
                            count$iv$iv2++;
                            if (count$iv$iv2 == i4) {
                                node = next$iv$iv2;
                                i2 = i3;
                                $this$dispatchForKind_u2d6rFNWt0$iv$iv2 = $this$dispatchForKind_u2d6rFNWt0$iv$iv3;
                            } else {
                                if (mutableVector3 == null) {
                                    i2 = i3;
                                    $this$dispatchForKind_u2d6rFNWt0$iv$iv2 = $this$dispatchForKind_u2d6rFNWt0$iv$iv3;
                                    mutableVector2 = new MutableVector(new Modifier.Node[16], 0);
                                } else {
                                    i2 = i3;
                                    $this$dispatchForKind_u2d6rFNWt0$iv$iv2 = $this$dispatchForKind_u2d6rFNWt0$iv$iv3;
                                    mutableVector2 = mutableVector3;
                                }
                                mutableVector3 = mutableVector2;
                                Modifier.Node theNode$iv$iv2 = node;
                                if (theNode$iv$iv2 != null) {
                                    if (mutableVector3 != null) {
                                        mutableVector3.add(theNode$iv$iv2);
                                    }
                                    node = null;
                                }
                                if (mutableVector3 != null) {
                                    mutableVector3.add(next$iv$iv2);
                                }
                            }
                        } else {
                            i2 = i3;
                            $this$dispatchForKind_u2d6rFNWt0$iv$iv2 = $this$dispatchForKind_u2d6rFNWt0$iv$iv3;
                        }
                        node$iv$iv$iv2 = node$iv$iv$iv2.getChild();
                        i3 = i2;
                        $this$dispatchForKind_u2d6rFNWt0$iv$iv3 = $this$dispatchForKind_u2d6rFNWt0$iv$iv2;
                        i4 = 1;
                    }
                    i = i3;
                    $this$dispatchForKind_u2d6rFNWt0$iv$iv = $this$dispatchForKind_u2d6rFNWt0$iv$iv3;
                    if (count$iv$iv2 == 1) {
                        i3 = i;
                        $this$dispatchForKind_u2d6rFNWt0$iv$iv3 = $this$dispatchForKind_u2d6rFNWt0$iv$iv;
                    }
                }
            }
            node = DelegatableNodeKt.pop(mutableVector3);
            i3 = i;
            $this$dispatchForKind_u2d6rFNWt0$iv$iv3 = $this$dispatchForKind_u2d6rFNWt0$iv$iv;
        }
    }

    public static final boolean freeFocus(FocusRequesterModifierNode $this$freeFocus) {
        DelegatableNode $this$visitSelfAndChildren_u2d6rFNWt0$iv;
        int type$iv;
        int mask$iv$iv;
        DelegatableNode $this$visitSelfAndChildren_u2d6rFNWt0$iv2;
        int type$iv2;
        int mask$iv$iv2;
        MutableVector mutableVector;
        int i;
        Modifier.Node $this$dispatchForKind_u2d6rFNWt0$iv$iv;
        int i2;
        Modifier.Node $this$dispatchForKind_u2d6rFNWt0$iv$iv2;
        MutableVector mutableVector2;
        FocusRequesterModifierNode $this$visitSelfAndChildren_u2d6rFNWt0$iv3 = $this$freeFocus;
        int type$iv3 = NodeKind.m5222constructorimpl(1024);
        int i3 = 0;
        Modifier.Node $this$dispatchForKind_u2d6rFNWt0$iv$iv3 = $this$visitSelfAndChildren_u2d6rFNWt0$iv3.getNode();
        MutableVector mutableVector3 = null;
        Modifier.Node node = $this$dispatchForKind_u2d6rFNWt0$iv$iv3;
        while (true) {
            int i4 = 1;
            if (node == null) {
                int mask$iv$iv3 = type$iv3;
                if (!$this$visitSelfAndChildren_u2d6rFNWt0$iv3.getNode().getIsAttached()) {
                    throw new IllegalStateException("visitChildren called on an unattached node".toString());
                }
                MutableVector branches$iv$iv = new MutableVector(new Modifier.Node[16], 0);
                Modifier.Node child$iv$iv = $this$visitSelfAndChildren_u2d6rFNWt0$iv3.getNode().getChild();
                if (child$iv$iv == null) {
                    DelegatableNodeKt.addLayoutNodeChildren(branches$iv$iv, $this$visitSelfAndChildren_u2d6rFNWt0$iv3.getNode());
                } else {
                    branches$iv$iv.add(child$iv$iv);
                }
                while (branches$iv$iv.isNotEmpty()) {
                    Modifier.Node branch$iv$iv = (Modifier.Node) branches$iv$iv.removeAt(branches$iv$iv.getSize() - 1);
                    if ((branch$iv$iv.getAggregateChildKindSet() & mask$iv$iv3) != 0) {
                        Modifier.Node node$iv$iv = branch$iv$iv;
                        while (true) {
                            if (node$iv$iv == null) {
                                $this$visitSelfAndChildren_u2d6rFNWt0$iv3 = $this$visitSelfAndChildren_u2d6rFNWt0$iv3;
                                break;
                            }
                            if ((node$iv$iv.getKindSet() & mask$iv$iv3) != 0) {
                                Modifier.Node it$iv = node$iv$iv;
                                MutableVector mutableVector4 = null;
                                Modifier.Node node2 = it$iv;
                                while (node2 != null) {
                                    if (node2 instanceof FocusTargetNode) {
                                        FocusTargetNode it = (FocusTargetNode) node2;
                                        if (FocusTransactionsKt.freeFocus(it)) {
                                            return true;
                                        }
                                        $this$visitSelfAndChildren_u2d6rFNWt0$iv = $this$visitSelfAndChildren_u2d6rFNWt0$iv3;
                                        type$iv = type$iv3;
                                        mask$iv$iv = mask$iv$iv3;
                                    } else {
                                        Modifier.Node this_$iv$iv$iv = node2;
                                        if (((this_$iv$iv$iv.getKindSet() & type$iv3) != 0) && (node2 instanceof DelegatingNode)) {
                                            int count$iv$iv = 0;
                                            DelegatingNode this_$iv$iv$iv2 = (DelegatingNode) node2;
                                            Modifier.Node node$iv$iv$iv = this_$iv$iv$iv2.getDelegate();
                                            while (node$iv$iv$iv != null) {
                                                Modifier.Node next$iv$iv = node$iv$iv$iv;
                                                if ((next$iv$iv.getKindSet() & type$iv3) != 0) {
                                                    count$iv$iv++;
                                                    $this$visitSelfAndChildren_u2d6rFNWt0$iv2 = $this$visitSelfAndChildren_u2d6rFNWt0$iv3;
                                                    if (count$iv$iv == 1) {
                                                        node2 = next$iv$iv;
                                                        type$iv2 = type$iv3;
                                                        mask$iv$iv2 = mask$iv$iv3;
                                                    } else {
                                                        if (mutableVector4 == null) {
                                                            type$iv2 = type$iv3;
                                                            mask$iv$iv2 = mask$iv$iv3;
                                                            mutableVector = new MutableVector(new Modifier.Node[16], 0);
                                                        } else {
                                                            type$iv2 = type$iv3;
                                                            mask$iv$iv2 = mask$iv$iv3;
                                                            mutableVector = mutableVector4;
                                                        }
                                                        mutableVector4 = mutableVector;
                                                        Modifier.Node theNode$iv$iv = node2;
                                                        if (theNode$iv$iv != null) {
                                                            if (mutableVector4 != null) {
                                                                mutableVector4.add(theNode$iv$iv);
                                                            }
                                                            node2 = null;
                                                        }
                                                        if (mutableVector4 != null) {
                                                            mutableVector4.add(next$iv$iv);
                                                        }
                                                    }
                                                } else {
                                                    $this$visitSelfAndChildren_u2d6rFNWt0$iv2 = $this$visitSelfAndChildren_u2d6rFNWt0$iv3;
                                                    type$iv2 = type$iv3;
                                                    mask$iv$iv2 = mask$iv$iv3;
                                                }
                                                node$iv$iv$iv = node$iv$iv$iv.getChild();
                                                $this$visitSelfAndChildren_u2d6rFNWt0$iv3 = $this$visitSelfAndChildren_u2d6rFNWt0$iv2;
                                                type$iv3 = type$iv2;
                                                mask$iv$iv3 = mask$iv$iv2;
                                            }
                                            $this$visitSelfAndChildren_u2d6rFNWt0$iv = $this$visitSelfAndChildren_u2d6rFNWt0$iv3;
                                            type$iv = type$iv3;
                                            mask$iv$iv = mask$iv$iv3;
                                            if (count$iv$iv == 1) {
                                                $this$visitSelfAndChildren_u2d6rFNWt0$iv3 = $this$visitSelfAndChildren_u2d6rFNWt0$iv;
                                                type$iv3 = type$iv;
                                                mask$iv$iv3 = mask$iv$iv;
                                            }
                                        } else {
                                            $this$visitSelfAndChildren_u2d6rFNWt0$iv = $this$visitSelfAndChildren_u2d6rFNWt0$iv3;
                                            type$iv = type$iv3;
                                            mask$iv$iv = mask$iv$iv3;
                                        }
                                    }
                                    node2 = DelegatableNodeKt.pop(mutableVector4);
                                    $this$visitSelfAndChildren_u2d6rFNWt0$iv3 = $this$visitSelfAndChildren_u2d6rFNWt0$iv;
                                    type$iv3 = type$iv;
                                    mask$iv$iv3 = mask$iv$iv;
                                }
                                $this$visitSelfAndChildren_u2d6rFNWt0$iv3 = $this$visitSelfAndChildren_u2d6rFNWt0$iv3;
                            } else {
                                node$iv$iv = node$iv$iv.getChild();
                                $this$visitSelfAndChildren_u2d6rFNWt0$iv3 = $this$visitSelfAndChildren_u2d6rFNWt0$iv3;
                            }
                        }
                    } else {
                        DelegatableNodeKt.addLayoutNodeChildren(branches$iv$iv, branch$iv$iv);
                    }
                }
                return false;
            }
            if (node instanceof FocusTargetNode) {
                FocusTargetNode it2 = (FocusTargetNode) node;
                if (FocusTransactionsKt.freeFocus(it2)) {
                    return true;
                }
                i = i3;
                $this$dispatchForKind_u2d6rFNWt0$iv$iv = $this$dispatchForKind_u2d6rFNWt0$iv$iv3;
            } else {
                Modifier.Node this_$iv$iv$iv3 = node;
                Modifier.Node this_$iv$iv$iv4 = (this_$iv$iv$iv3.getKindSet() & type$iv3) != 0 ? 1 : null;
                if (this_$iv$iv$iv4 == null || !(node instanceof DelegatingNode)) {
                    i = i3;
                    $this$dispatchForKind_u2d6rFNWt0$iv$iv = $this$dispatchForKind_u2d6rFNWt0$iv$iv3;
                } else {
                    int count$iv$iv2 = 0;
                    DelegatingNode this_$iv$iv$iv5 = (DelegatingNode) node;
                    Modifier.Node node$iv$iv$iv2 = this_$iv$iv$iv5.getDelegate();
                    while (node$iv$iv$iv2 != null) {
                        Modifier.Node next$iv$iv2 = node$iv$iv$iv2;
                        if (((next$iv$iv2.getKindSet() & type$iv3) != 0 ? i4 : 0) != 0) {
                            count$iv$iv2++;
                            if (count$iv$iv2 == i4) {
                                node = next$iv$iv2;
                                i2 = i3;
                                $this$dispatchForKind_u2d6rFNWt0$iv$iv2 = $this$dispatchForKind_u2d6rFNWt0$iv$iv3;
                            } else {
                                if (mutableVector3 == null) {
                                    i2 = i3;
                                    $this$dispatchForKind_u2d6rFNWt0$iv$iv2 = $this$dispatchForKind_u2d6rFNWt0$iv$iv3;
                                    mutableVector2 = new MutableVector(new Modifier.Node[16], 0);
                                } else {
                                    i2 = i3;
                                    $this$dispatchForKind_u2d6rFNWt0$iv$iv2 = $this$dispatchForKind_u2d6rFNWt0$iv$iv3;
                                    mutableVector2 = mutableVector3;
                                }
                                mutableVector3 = mutableVector2;
                                Modifier.Node theNode$iv$iv2 = node;
                                if (theNode$iv$iv2 != null) {
                                    if (mutableVector3 != null) {
                                        mutableVector3.add(theNode$iv$iv2);
                                    }
                                    node = null;
                                }
                                if (mutableVector3 != null) {
                                    mutableVector3.add(next$iv$iv2);
                                }
                            }
                        } else {
                            i2 = i3;
                            $this$dispatchForKind_u2d6rFNWt0$iv$iv2 = $this$dispatchForKind_u2d6rFNWt0$iv$iv3;
                        }
                        node$iv$iv$iv2 = node$iv$iv$iv2.getChild();
                        i3 = i2;
                        $this$dispatchForKind_u2d6rFNWt0$iv$iv3 = $this$dispatchForKind_u2d6rFNWt0$iv$iv2;
                        i4 = 1;
                    }
                    i = i3;
                    $this$dispatchForKind_u2d6rFNWt0$iv$iv = $this$dispatchForKind_u2d6rFNWt0$iv$iv3;
                    if (count$iv$iv2 == 1) {
                        i3 = i;
                        $this$dispatchForKind_u2d6rFNWt0$iv$iv3 = $this$dispatchForKind_u2d6rFNWt0$iv$iv;
                    }
                }
            }
            node = DelegatableNodeKt.pop(mutableVector3);
            i3 = i;
            $this$dispatchForKind_u2d6rFNWt0$iv$iv3 = $this$dispatchForKind_u2d6rFNWt0$iv$iv;
        }
    }

    public static final boolean saveFocusedChild(FocusRequesterModifierNode $this$saveFocusedChild) {
        DelegatableNode $this$visitSelfAndChildren_u2d6rFNWt0$iv;
        int type$iv;
        int mask$iv$iv;
        DelegatableNode $this$visitSelfAndChildren_u2d6rFNWt0$iv2;
        int type$iv2;
        int mask$iv$iv2;
        MutableVector mutableVector;
        int i;
        Modifier.Node $this$dispatchForKind_u2d6rFNWt0$iv$iv;
        int i2;
        Modifier.Node $this$dispatchForKind_u2d6rFNWt0$iv$iv2;
        MutableVector mutableVector2;
        FocusRequesterModifierNode $this$visitSelfAndChildren_u2d6rFNWt0$iv3 = $this$saveFocusedChild;
        int type$iv3 = NodeKind.m5222constructorimpl(1024);
        int i3 = 0;
        Modifier.Node $this$dispatchForKind_u2d6rFNWt0$iv$iv3 = $this$visitSelfAndChildren_u2d6rFNWt0$iv3.getNode();
        MutableVector mutableVector3 = null;
        Modifier.Node node = $this$dispatchForKind_u2d6rFNWt0$iv$iv3;
        while (true) {
            int i4 = 1;
            if (node == null) {
                int mask$iv$iv3 = type$iv3;
                if (!$this$visitSelfAndChildren_u2d6rFNWt0$iv3.getNode().getIsAttached()) {
                    throw new IllegalStateException("visitChildren called on an unattached node".toString());
                }
                MutableVector branches$iv$iv = new MutableVector(new Modifier.Node[16], 0);
                Modifier.Node child$iv$iv = $this$visitSelfAndChildren_u2d6rFNWt0$iv3.getNode().getChild();
                if (child$iv$iv == null) {
                    DelegatableNodeKt.addLayoutNodeChildren(branches$iv$iv, $this$visitSelfAndChildren_u2d6rFNWt0$iv3.getNode());
                } else {
                    branches$iv$iv.add(child$iv$iv);
                }
                while (branches$iv$iv.isNotEmpty()) {
                    Modifier.Node branch$iv$iv = (Modifier.Node) branches$iv$iv.removeAt(branches$iv$iv.getSize() - 1);
                    if ((branch$iv$iv.getAggregateChildKindSet() & mask$iv$iv3) != 0) {
                        Modifier.Node node$iv$iv = branch$iv$iv;
                        while (true) {
                            if (node$iv$iv == null) {
                                $this$visitSelfAndChildren_u2d6rFNWt0$iv3 = $this$visitSelfAndChildren_u2d6rFNWt0$iv3;
                                break;
                            }
                            if ((node$iv$iv.getKindSet() & mask$iv$iv3) != 0) {
                                Modifier.Node it$iv = node$iv$iv;
                                MutableVector mutableVector4 = null;
                                Modifier.Node node2 = it$iv;
                                while (node2 != null) {
                                    if (node2 instanceof FocusTargetNode) {
                                        FocusTargetNode it = (FocusTargetNode) node2;
                                        if (FocusRestorerKt.saveFocusedChild(it)) {
                                            return true;
                                        }
                                        $this$visitSelfAndChildren_u2d6rFNWt0$iv = $this$visitSelfAndChildren_u2d6rFNWt0$iv3;
                                        type$iv = type$iv3;
                                        mask$iv$iv = mask$iv$iv3;
                                    } else {
                                        Modifier.Node this_$iv$iv$iv = node2;
                                        if (((this_$iv$iv$iv.getKindSet() & type$iv3) != 0) && (node2 instanceof DelegatingNode)) {
                                            int count$iv$iv = 0;
                                            DelegatingNode this_$iv$iv$iv2 = (DelegatingNode) node2;
                                            Modifier.Node node$iv$iv$iv = this_$iv$iv$iv2.getDelegate();
                                            while (node$iv$iv$iv != null) {
                                                Modifier.Node next$iv$iv = node$iv$iv$iv;
                                                if ((next$iv$iv.getKindSet() & type$iv3) != 0) {
                                                    count$iv$iv++;
                                                    $this$visitSelfAndChildren_u2d6rFNWt0$iv2 = $this$visitSelfAndChildren_u2d6rFNWt0$iv3;
                                                    if (count$iv$iv == 1) {
                                                        node2 = next$iv$iv;
                                                        type$iv2 = type$iv3;
                                                        mask$iv$iv2 = mask$iv$iv3;
                                                    } else {
                                                        if (mutableVector4 == null) {
                                                            type$iv2 = type$iv3;
                                                            mask$iv$iv2 = mask$iv$iv3;
                                                            mutableVector = new MutableVector(new Modifier.Node[16], 0);
                                                        } else {
                                                            type$iv2 = type$iv3;
                                                            mask$iv$iv2 = mask$iv$iv3;
                                                            mutableVector = mutableVector4;
                                                        }
                                                        mutableVector4 = mutableVector;
                                                        Modifier.Node theNode$iv$iv = node2;
                                                        if (theNode$iv$iv != null) {
                                                            if (mutableVector4 != null) {
                                                                mutableVector4.add(theNode$iv$iv);
                                                            }
                                                            node2 = null;
                                                        }
                                                        if (mutableVector4 != null) {
                                                            mutableVector4.add(next$iv$iv);
                                                        }
                                                    }
                                                } else {
                                                    $this$visitSelfAndChildren_u2d6rFNWt0$iv2 = $this$visitSelfAndChildren_u2d6rFNWt0$iv3;
                                                    type$iv2 = type$iv3;
                                                    mask$iv$iv2 = mask$iv$iv3;
                                                }
                                                node$iv$iv$iv = node$iv$iv$iv.getChild();
                                                $this$visitSelfAndChildren_u2d6rFNWt0$iv3 = $this$visitSelfAndChildren_u2d6rFNWt0$iv2;
                                                type$iv3 = type$iv2;
                                                mask$iv$iv3 = mask$iv$iv2;
                                            }
                                            $this$visitSelfAndChildren_u2d6rFNWt0$iv = $this$visitSelfAndChildren_u2d6rFNWt0$iv3;
                                            type$iv = type$iv3;
                                            mask$iv$iv = mask$iv$iv3;
                                            if (count$iv$iv == 1) {
                                                $this$visitSelfAndChildren_u2d6rFNWt0$iv3 = $this$visitSelfAndChildren_u2d6rFNWt0$iv;
                                                type$iv3 = type$iv;
                                                mask$iv$iv3 = mask$iv$iv;
                                            }
                                        } else {
                                            $this$visitSelfAndChildren_u2d6rFNWt0$iv = $this$visitSelfAndChildren_u2d6rFNWt0$iv3;
                                            type$iv = type$iv3;
                                            mask$iv$iv = mask$iv$iv3;
                                        }
                                    }
                                    node2 = DelegatableNodeKt.pop(mutableVector4);
                                    $this$visitSelfAndChildren_u2d6rFNWt0$iv3 = $this$visitSelfAndChildren_u2d6rFNWt0$iv;
                                    type$iv3 = type$iv;
                                    mask$iv$iv3 = mask$iv$iv;
                                }
                                $this$visitSelfAndChildren_u2d6rFNWt0$iv3 = $this$visitSelfAndChildren_u2d6rFNWt0$iv3;
                            } else {
                                node$iv$iv = node$iv$iv.getChild();
                                $this$visitSelfAndChildren_u2d6rFNWt0$iv3 = $this$visitSelfAndChildren_u2d6rFNWt0$iv3;
                            }
                        }
                    } else {
                        DelegatableNodeKt.addLayoutNodeChildren(branches$iv$iv, branch$iv$iv);
                    }
                }
                return false;
            }
            if (node instanceof FocusTargetNode) {
                FocusTargetNode it2 = (FocusTargetNode) node;
                if (FocusRestorerKt.saveFocusedChild(it2)) {
                    return true;
                }
                i = i3;
                $this$dispatchForKind_u2d6rFNWt0$iv$iv = $this$dispatchForKind_u2d6rFNWt0$iv$iv3;
            } else {
                Modifier.Node this_$iv$iv$iv3 = node;
                Modifier.Node this_$iv$iv$iv4 = (this_$iv$iv$iv3.getKindSet() & type$iv3) != 0 ? 1 : null;
                if (this_$iv$iv$iv4 == null || !(node instanceof DelegatingNode)) {
                    i = i3;
                    $this$dispatchForKind_u2d6rFNWt0$iv$iv = $this$dispatchForKind_u2d6rFNWt0$iv$iv3;
                } else {
                    int count$iv$iv2 = 0;
                    DelegatingNode this_$iv$iv$iv5 = (DelegatingNode) node;
                    Modifier.Node node$iv$iv$iv2 = this_$iv$iv$iv5.getDelegate();
                    while (node$iv$iv$iv2 != null) {
                        Modifier.Node next$iv$iv2 = node$iv$iv$iv2;
                        if (((next$iv$iv2.getKindSet() & type$iv3) != 0 ? i4 : 0) != 0) {
                            count$iv$iv2++;
                            if (count$iv$iv2 == i4) {
                                node = next$iv$iv2;
                                i2 = i3;
                                $this$dispatchForKind_u2d6rFNWt0$iv$iv2 = $this$dispatchForKind_u2d6rFNWt0$iv$iv3;
                            } else {
                                if (mutableVector3 == null) {
                                    i2 = i3;
                                    $this$dispatchForKind_u2d6rFNWt0$iv$iv2 = $this$dispatchForKind_u2d6rFNWt0$iv$iv3;
                                    mutableVector2 = new MutableVector(new Modifier.Node[16], 0);
                                } else {
                                    i2 = i3;
                                    $this$dispatchForKind_u2d6rFNWt0$iv$iv2 = $this$dispatchForKind_u2d6rFNWt0$iv$iv3;
                                    mutableVector2 = mutableVector3;
                                }
                                mutableVector3 = mutableVector2;
                                Modifier.Node theNode$iv$iv2 = node;
                                if (theNode$iv$iv2 != null) {
                                    if (mutableVector3 != null) {
                                        mutableVector3.add(theNode$iv$iv2);
                                    }
                                    node = null;
                                }
                                if (mutableVector3 != null) {
                                    mutableVector3.add(next$iv$iv2);
                                }
                            }
                        } else {
                            i2 = i3;
                            $this$dispatchForKind_u2d6rFNWt0$iv$iv2 = $this$dispatchForKind_u2d6rFNWt0$iv$iv3;
                        }
                        node$iv$iv$iv2 = node$iv$iv$iv2.getChild();
                        i3 = i2;
                        $this$dispatchForKind_u2d6rFNWt0$iv$iv3 = $this$dispatchForKind_u2d6rFNWt0$iv$iv2;
                        i4 = 1;
                    }
                    i = i3;
                    $this$dispatchForKind_u2d6rFNWt0$iv$iv = $this$dispatchForKind_u2d6rFNWt0$iv$iv3;
                    if (count$iv$iv2 == 1) {
                        i3 = i;
                        $this$dispatchForKind_u2d6rFNWt0$iv$iv3 = $this$dispatchForKind_u2d6rFNWt0$iv$iv;
                    }
                }
            }
            node = DelegatableNodeKt.pop(mutableVector3);
            i3 = i;
            $this$dispatchForKind_u2d6rFNWt0$iv$iv3 = $this$dispatchForKind_u2d6rFNWt0$iv$iv;
        }
    }

    public static final boolean restoreFocusedChild(FocusRequesterModifierNode $this$restoreFocusedChild) {
        DelegatableNode $this$visitSelfAndChildren_u2d6rFNWt0$iv;
        int type$iv;
        int mask$iv$iv;
        DelegatableNode $this$visitSelfAndChildren_u2d6rFNWt0$iv2;
        int type$iv2;
        int mask$iv$iv2;
        MutableVector mutableVector;
        int i;
        Modifier.Node $this$dispatchForKind_u2d6rFNWt0$iv$iv;
        int i2;
        Modifier.Node $this$dispatchForKind_u2d6rFNWt0$iv$iv2;
        MutableVector mutableVector2;
        FocusRequesterModifierNode $this$visitSelfAndChildren_u2d6rFNWt0$iv3 = $this$restoreFocusedChild;
        int type$iv3 = NodeKind.m5222constructorimpl(1024);
        int i3 = 0;
        Modifier.Node $this$dispatchForKind_u2d6rFNWt0$iv$iv3 = $this$visitSelfAndChildren_u2d6rFNWt0$iv3.getNode();
        MutableVector mutableVector3 = null;
        Modifier.Node node = $this$dispatchForKind_u2d6rFNWt0$iv$iv3;
        while (true) {
            int i4 = 1;
            if (node == null) {
                int mask$iv$iv3 = type$iv3;
                if (!$this$visitSelfAndChildren_u2d6rFNWt0$iv3.getNode().getIsAttached()) {
                    throw new IllegalStateException("visitChildren called on an unattached node".toString());
                }
                MutableVector branches$iv$iv = new MutableVector(new Modifier.Node[16], 0);
                Modifier.Node child$iv$iv = $this$visitSelfAndChildren_u2d6rFNWt0$iv3.getNode().getChild();
                if (child$iv$iv == null) {
                    DelegatableNodeKt.addLayoutNodeChildren(branches$iv$iv, $this$visitSelfAndChildren_u2d6rFNWt0$iv3.getNode());
                } else {
                    branches$iv$iv.add(child$iv$iv);
                }
                while (branches$iv$iv.isNotEmpty()) {
                    Modifier.Node branch$iv$iv = (Modifier.Node) branches$iv$iv.removeAt(branches$iv$iv.getSize() - 1);
                    if ((branch$iv$iv.getAggregateChildKindSet() & mask$iv$iv3) != 0) {
                        Modifier.Node node$iv$iv = branch$iv$iv;
                        while (true) {
                            if (node$iv$iv == null) {
                                $this$visitSelfAndChildren_u2d6rFNWt0$iv3 = $this$visitSelfAndChildren_u2d6rFNWt0$iv3;
                                break;
                            }
                            if ((node$iv$iv.getKindSet() & mask$iv$iv3) != 0) {
                                Modifier.Node it$iv = node$iv$iv;
                                MutableVector mutableVector4 = null;
                                Modifier.Node node2 = it$iv;
                                while (node2 != null) {
                                    if (node2 instanceof FocusTargetNode) {
                                        FocusTargetNode it = (FocusTargetNode) node2;
                                        if (FocusRestorerKt.restoreFocusedChild(it)) {
                                            return true;
                                        }
                                        $this$visitSelfAndChildren_u2d6rFNWt0$iv = $this$visitSelfAndChildren_u2d6rFNWt0$iv3;
                                        type$iv = type$iv3;
                                        mask$iv$iv = mask$iv$iv3;
                                    } else {
                                        Modifier.Node this_$iv$iv$iv = node2;
                                        if (((this_$iv$iv$iv.getKindSet() & type$iv3) != 0) && (node2 instanceof DelegatingNode)) {
                                            int count$iv$iv = 0;
                                            DelegatingNode this_$iv$iv$iv2 = (DelegatingNode) node2;
                                            Modifier.Node node$iv$iv$iv = this_$iv$iv$iv2.getDelegate();
                                            while (node$iv$iv$iv != null) {
                                                Modifier.Node next$iv$iv = node$iv$iv$iv;
                                                if ((next$iv$iv.getKindSet() & type$iv3) != 0) {
                                                    count$iv$iv++;
                                                    $this$visitSelfAndChildren_u2d6rFNWt0$iv2 = $this$visitSelfAndChildren_u2d6rFNWt0$iv3;
                                                    if (count$iv$iv == 1) {
                                                        node2 = next$iv$iv;
                                                        type$iv2 = type$iv3;
                                                        mask$iv$iv2 = mask$iv$iv3;
                                                    } else {
                                                        if (mutableVector4 == null) {
                                                            type$iv2 = type$iv3;
                                                            mask$iv$iv2 = mask$iv$iv3;
                                                            mutableVector = new MutableVector(new Modifier.Node[16], 0);
                                                        } else {
                                                            type$iv2 = type$iv3;
                                                            mask$iv$iv2 = mask$iv$iv3;
                                                            mutableVector = mutableVector4;
                                                        }
                                                        mutableVector4 = mutableVector;
                                                        Modifier.Node theNode$iv$iv = node2;
                                                        if (theNode$iv$iv != null) {
                                                            if (mutableVector4 != null) {
                                                                mutableVector4.add(theNode$iv$iv);
                                                            }
                                                            node2 = null;
                                                        }
                                                        if (mutableVector4 != null) {
                                                            mutableVector4.add(next$iv$iv);
                                                        }
                                                    }
                                                } else {
                                                    $this$visitSelfAndChildren_u2d6rFNWt0$iv2 = $this$visitSelfAndChildren_u2d6rFNWt0$iv3;
                                                    type$iv2 = type$iv3;
                                                    mask$iv$iv2 = mask$iv$iv3;
                                                }
                                                node$iv$iv$iv = node$iv$iv$iv.getChild();
                                                $this$visitSelfAndChildren_u2d6rFNWt0$iv3 = $this$visitSelfAndChildren_u2d6rFNWt0$iv2;
                                                type$iv3 = type$iv2;
                                                mask$iv$iv3 = mask$iv$iv2;
                                            }
                                            $this$visitSelfAndChildren_u2d6rFNWt0$iv = $this$visitSelfAndChildren_u2d6rFNWt0$iv3;
                                            type$iv = type$iv3;
                                            mask$iv$iv = mask$iv$iv3;
                                            if (count$iv$iv == 1) {
                                                $this$visitSelfAndChildren_u2d6rFNWt0$iv3 = $this$visitSelfAndChildren_u2d6rFNWt0$iv;
                                                type$iv3 = type$iv;
                                                mask$iv$iv3 = mask$iv$iv;
                                            }
                                        } else {
                                            $this$visitSelfAndChildren_u2d6rFNWt0$iv = $this$visitSelfAndChildren_u2d6rFNWt0$iv3;
                                            type$iv = type$iv3;
                                            mask$iv$iv = mask$iv$iv3;
                                        }
                                    }
                                    node2 = DelegatableNodeKt.pop(mutableVector4);
                                    $this$visitSelfAndChildren_u2d6rFNWt0$iv3 = $this$visitSelfAndChildren_u2d6rFNWt0$iv;
                                    type$iv3 = type$iv;
                                    mask$iv$iv3 = mask$iv$iv;
                                }
                                $this$visitSelfAndChildren_u2d6rFNWt0$iv3 = $this$visitSelfAndChildren_u2d6rFNWt0$iv3;
                            } else {
                                node$iv$iv = node$iv$iv.getChild();
                                $this$visitSelfAndChildren_u2d6rFNWt0$iv3 = $this$visitSelfAndChildren_u2d6rFNWt0$iv3;
                            }
                        }
                    } else {
                        DelegatableNodeKt.addLayoutNodeChildren(branches$iv$iv, branch$iv$iv);
                    }
                }
                return false;
            }
            if (node instanceof FocusTargetNode) {
                FocusTargetNode it2 = (FocusTargetNode) node;
                if (FocusRestorerKt.restoreFocusedChild(it2)) {
                    return true;
                }
                i = i3;
                $this$dispatchForKind_u2d6rFNWt0$iv$iv = $this$dispatchForKind_u2d6rFNWt0$iv$iv3;
            } else {
                Modifier.Node this_$iv$iv$iv3 = node;
                Modifier.Node this_$iv$iv$iv4 = (this_$iv$iv$iv3.getKindSet() & type$iv3) != 0 ? 1 : null;
                if (this_$iv$iv$iv4 == null || !(node instanceof DelegatingNode)) {
                    i = i3;
                    $this$dispatchForKind_u2d6rFNWt0$iv$iv = $this$dispatchForKind_u2d6rFNWt0$iv$iv3;
                } else {
                    int count$iv$iv2 = 0;
                    DelegatingNode this_$iv$iv$iv5 = (DelegatingNode) node;
                    Modifier.Node node$iv$iv$iv2 = this_$iv$iv$iv5.getDelegate();
                    while (node$iv$iv$iv2 != null) {
                        Modifier.Node next$iv$iv2 = node$iv$iv$iv2;
                        if (((next$iv$iv2.getKindSet() & type$iv3) != 0 ? i4 : 0) != 0) {
                            count$iv$iv2++;
                            if (count$iv$iv2 == i4) {
                                node = next$iv$iv2;
                                i2 = i3;
                                $this$dispatchForKind_u2d6rFNWt0$iv$iv2 = $this$dispatchForKind_u2d6rFNWt0$iv$iv3;
                            } else {
                                if (mutableVector3 == null) {
                                    i2 = i3;
                                    $this$dispatchForKind_u2d6rFNWt0$iv$iv2 = $this$dispatchForKind_u2d6rFNWt0$iv$iv3;
                                    mutableVector2 = new MutableVector(new Modifier.Node[16], 0);
                                } else {
                                    i2 = i3;
                                    $this$dispatchForKind_u2d6rFNWt0$iv$iv2 = $this$dispatchForKind_u2d6rFNWt0$iv$iv3;
                                    mutableVector2 = mutableVector3;
                                }
                                mutableVector3 = mutableVector2;
                                Modifier.Node theNode$iv$iv2 = node;
                                if (theNode$iv$iv2 != null) {
                                    if (mutableVector3 != null) {
                                        mutableVector3.add(theNode$iv$iv2);
                                    }
                                    node = null;
                                }
                                if (mutableVector3 != null) {
                                    mutableVector3.add(next$iv$iv2);
                                }
                            }
                        } else {
                            i2 = i3;
                            $this$dispatchForKind_u2d6rFNWt0$iv$iv2 = $this$dispatchForKind_u2d6rFNWt0$iv$iv3;
                        }
                        node$iv$iv$iv2 = node$iv$iv$iv2.getChild();
                        i3 = i2;
                        $this$dispatchForKind_u2d6rFNWt0$iv$iv3 = $this$dispatchForKind_u2d6rFNWt0$iv$iv2;
                        i4 = 1;
                    }
                    i = i3;
                    $this$dispatchForKind_u2d6rFNWt0$iv$iv = $this$dispatchForKind_u2d6rFNWt0$iv$iv3;
                    if (count$iv$iv2 == 1) {
                        i3 = i;
                        $this$dispatchForKind_u2d6rFNWt0$iv$iv3 = $this$dispatchForKind_u2d6rFNWt0$iv$iv;
                    }
                }
            }
            node = DelegatableNodeKt.pop(mutableVector3);
            i3 = i;
            $this$dispatchForKind_u2d6rFNWt0$iv$iv3 = $this$dispatchForKind_u2d6rFNWt0$iv$iv;
        }
    }
}
