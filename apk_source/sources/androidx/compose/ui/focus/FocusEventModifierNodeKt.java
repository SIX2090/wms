package androidx.compose.ui.focus;

import androidx.compose.runtime.collection.MutableVector;
import androidx.compose.ui.Modifier;
import androidx.compose.ui.node.DelegatableNode;
import androidx.compose.ui.node.DelegatableNodeKt;
import androidx.compose.ui.node.DelegatingNode;
import androidx.compose.ui.node.LayoutNode;
import androidx.compose.ui.node.NodeChain;
import androidx.compose.ui.node.NodeKind;
import kotlin.Metadata;

/* compiled from: FocusEventModifierNode.kt */
@Metadata(d1 = {"\u0000\u0018\n\u0000\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\u001a\f\u0010\u0000\u001a\u00020\u0001*\u00020\u0002H\u0000\u001a\f\u0010\u0003\u001a\u00020\u0004*\u00020\u0002H\u0000\u001a\f\u0010\u0005\u001a\u00020\u0004*\u00020\u0006H\u0000¨\u0006\u0007"}, d2 = {"getFocusState", "Landroidx/compose/ui/focus/FocusState;", "Landroidx/compose/ui/focus/FocusEventModifierNode;", "invalidateFocusEvent", "", "refreshFocusEventNodes", "Landroidx/compose/ui/focus/FocusTargetNode;", "ui_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class FocusEventModifierNodeKt {

    /* compiled from: FocusEventModifierNode.kt */
    @Metadata(k = 3, mv = {1, 8, 0}, xi = 48)
    public /* synthetic */ class WhenMappings {
        public static final /* synthetic */ int[] $EnumSwitchMapping$0;

        static {
            int[] iArr = new int[FocusStateImpl.values().length];
            try {
                iArr[FocusStateImpl.Active.ordinal()] = 1;
            } catch (NoSuchFieldError e) {
            }
            try {
                iArr[FocusStateImpl.ActiveParent.ordinal()] = 2;
            } catch (NoSuchFieldError e2) {
            }
            try {
                iArr[FocusStateImpl.Captured.ordinal()] = 3;
            } catch (NoSuchFieldError e3) {
            }
            try {
                iArr[FocusStateImpl.Inactive.ordinal()] = 4;
            } catch (NoSuchFieldError e4) {
            }
            $EnumSwitchMapping$0 = iArr;
        }
    }

    public static final void invalidateFocusEvent(FocusEventModifierNode $this$invalidateFocusEvent) {
        DelegatableNodeKt.requireOwner($this$invalidateFocusEvent).getFocusOwner().scheduleInvalidation($this$invalidateFocusEvent);
    }

    public static final FocusState getFocusState(FocusEventModifierNode $this$getFocusState) {
        DelegatableNode $this$visitSelfAndChildren_u2d6rFNWt0$iv;
        int type$iv;
        int mask$iv$iv;
        DelegatableNode $this$visitSelfAndChildren_u2d6rFNWt0$iv2;
        DelegatableNode $this$visitSelfAndChildren_u2d6rFNWt0$iv3;
        int type$iv2;
        int mask$iv$iv2;
        MutableVector mutableVector;
        int i;
        Modifier.Node $this$dispatchForKind_u2d6rFNWt0$iv$iv;
        int i2;
        Modifier.Node $this$dispatchForKind_u2d6rFNWt0$iv$iv2;
        MutableVector mutableVector2;
        FocusEventModifierNode $this$visitSelfAndChildren_u2d6rFNWt0$iv4 = $this$getFocusState;
        int type$iv3 = NodeKind.m5222constructorimpl(1024);
        int i3 = 0;
        Modifier.Node $this$dispatchForKind_u2d6rFNWt0$iv$iv3 = $this$visitSelfAndChildren_u2d6rFNWt0$iv4.getNode();
        MutableVector mutableVector3 = null;
        Modifier.Node node = $this$dispatchForKind_u2d6rFNWt0$iv$iv3;
        while (true) {
            DelegatableNode delegatableNode = null;
            int i4 = 1;
            if (node == null) {
                int mask$iv$iv3 = type$iv3;
                if (!$this$visitSelfAndChildren_u2d6rFNWt0$iv4.getNode().getIsAttached()) {
                    throw new IllegalStateException("visitChildren called on an unattached node".toString());
                }
                MutableVector branches$iv$iv = new MutableVector(new Modifier.Node[16], 0);
                Modifier.Node child$iv$iv = $this$visitSelfAndChildren_u2d6rFNWt0$iv4.getNode().getChild();
                if (child$iv$iv == null) {
                    DelegatableNodeKt.addLayoutNodeChildren(branches$iv$iv, $this$visitSelfAndChildren_u2d6rFNWt0$iv4.getNode());
                } else {
                    branches$iv$iv.add(child$iv$iv);
                }
                while (branches$iv$iv.isNotEmpty()) {
                    Modifier.Node branch$iv$iv = (Modifier.Node) branches$iv$iv.removeAt(branches$iv$iv.getSize() - 1);
                    if ((branch$iv$iv.getAggregateChildKindSet() & mask$iv$iv3) == 0) {
                        DelegatableNodeKt.addLayoutNodeChildren(branches$iv$iv, branch$iv$iv);
                    } else {
                        Modifier.Node node$iv$iv = branch$iv$iv;
                        while (true) {
                            if (node$iv$iv == null) {
                                $this$visitSelfAndChildren_u2d6rFNWt0$iv4 = $this$visitSelfAndChildren_u2d6rFNWt0$iv4;
                                type$iv3 = type$iv3;
                            } else if ((node$iv$iv.getKindSet() & mask$iv$iv3) != 0) {
                                Modifier.Node it$iv = node$iv$iv;
                                MutableVector mutableVector4 = null;
                                Modifier.Node node2 = it$iv;
                                while (node2 != null) {
                                    if (node2 instanceof FocusTargetNode) {
                                        FocusTargetNode it = (FocusTargetNode) node2;
                                        FocusStateImpl focusState = it.getFocusState();
                                        switch (WhenMappings.$EnumSwitchMapping$0[focusState.ordinal()]) {
                                            case 1:
                                            case 2:
                                            case 3:
                                                return focusState;
                                            case 4:
                                            default:
                                                $this$visitSelfAndChildren_u2d6rFNWt0$iv = $this$visitSelfAndChildren_u2d6rFNWt0$iv4;
                                                type$iv = type$iv3;
                                                mask$iv$iv = mask$iv$iv3;
                                                $this$visitSelfAndChildren_u2d6rFNWt0$iv2 = null;
                                                break;
                                        }
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
                                                    $this$visitSelfAndChildren_u2d6rFNWt0$iv3 = $this$visitSelfAndChildren_u2d6rFNWt0$iv4;
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
                                                    $this$visitSelfAndChildren_u2d6rFNWt0$iv3 = $this$visitSelfAndChildren_u2d6rFNWt0$iv4;
                                                    type$iv2 = type$iv3;
                                                    mask$iv$iv2 = mask$iv$iv3;
                                                }
                                                node$iv$iv$iv = node$iv$iv$iv.getChild();
                                                $this$visitSelfAndChildren_u2d6rFNWt0$iv4 = $this$visitSelfAndChildren_u2d6rFNWt0$iv3;
                                                type$iv3 = type$iv2;
                                                mask$iv$iv3 = mask$iv$iv2;
                                            }
                                            $this$visitSelfAndChildren_u2d6rFNWt0$iv = $this$visitSelfAndChildren_u2d6rFNWt0$iv4;
                                            type$iv = type$iv3;
                                            mask$iv$iv = mask$iv$iv3;
                                            $this$visitSelfAndChildren_u2d6rFNWt0$iv2 = null;
                                            if (count$iv$iv == 1) {
                                                delegatableNode = null;
                                                $this$visitSelfAndChildren_u2d6rFNWt0$iv4 = $this$visitSelfAndChildren_u2d6rFNWt0$iv;
                                                type$iv3 = type$iv;
                                                mask$iv$iv3 = mask$iv$iv;
                                            }
                                        } else {
                                            $this$visitSelfAndChildren_u2d6rFNWt0$iv = $this$visitSelfAndChildren_u2d6rFNWt0$iv4;
                                            type$iv = type$iv3;
                                            mask$iv$iv = mask$iv$iv3;
                                            $this$visitSelfAndChildren_u2d6rFNWt0$iv2 = null;
                                        }
                                    }
                                    node2 = DelegatableNodeKt.pop(mutableVector4);
                                    delegatableNode = $this$visitSelfAndChildren_u2d6rFNWt0$iv2;
                                    $this$visitSelfAndChildren_u2d6rFNWt0$iv4 = $this$visitSelfAndChildren_u2d6rFNWt0$iv;
                                    type$iv3 = type$iv;
                                    mask$iv$iv3 = mask$iv$iv;
                                }
                                $this$visitSelfAndChildren_u2d6rFNWt0$iv4 = $this$visitSelfAndChildren_u2d6rFNWt0$iv4;
                                type$iv3 = type$iv3;
                            } else {
                                node$iv$iv = node$iv$iv.getChild();
                                $this$visitSelfAndChildren_u2d6rFNWt0$iv4 = $this$visitSelfAndChildren_u2d6rFNWt0$iv4;
                                type$iv3 = type$iv3;
                            }
                        }
                    }
                }
                return FocusStateImpl.Inactive;
            }
            if (node instanceof FocusTargetNode) {
                FocusTargetNode it2 = (FocusTargetNode) node;
                FocusStateImpl focusState2 = it2.getFocusState();
                switch (WhenMappings.$EnumSwitchMapping$0[focusState2.ordinal()]) {
                    case 1:
                    case 2:
                    case 3:
                        return focusState2;
                    case 4:
                    default:
                        i = i3;
                        $this$dispatchForKind_u2d6rFNWt0$iv$iv = $this$dispatchForKind_u2d6rFNWt0$iv$iv3;
                        break;
                }
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

    public static final void refreshFocusEventNodes(FocusTargetNode $this$refreshFocusEventNodes) {
        DelegatableNode $this$visitSelfAndAncestors_u2d5BbP62I$iv;
        int type$iv;
        int untilType$iv;
        int i;
        NodeChain nodes;
        DelegatableNode $this$visitSelfAndAncestors_u2d5BbP62I$iv2;
        int type$iv2;
        int untilType$iv2;
        int i2;
        int type$iv3;
        int untilType$iv3;
        int i3;
        int count$iv$iv;
        MutableVector mutableVector;
        FocusTargetNode $this$visitSelfAndAncestors_u2d5BbP62I$iv3 = $this$refreshFocusEventNodes;
        int type$iv4 = NodeKind.m5222constructorimpl(4096);
        int untilType$iv4 = NodeKind.m5222constructorimpl(1024);
        int i4 = 0;
        Modifier.Node self$iv = $this$visitSelfAndAncestors_u2d5BbP62I$iv3.getNode();
        int mask$iv$iv = type$iv4 | untilType$iv4;
        if (!$this$visitSelfAndAncestors_u2d5BbP62I$iv3.getNode().getIsAttached()) {
            throw new IllegalStateException("visitAncestors called on an unattached node".toString());
        }
        Modifier.Node node$iv$iv = $this$visitSelfAndAncestors_u2d5BbP62I$iv3.getNode();
        LayoutNode layout$iv$iv = DelegatableNodeKt.requireLayoutNode($this$visitSelfAndAncestors_u2d5BbP62I$iv3);
        while (layout$iv$iv != null) {
            Modifier.Node head$iv$iv = layout$iv$iv.getNodes().getHead();
            if ((head$iv$iv.getAggregateChildKindSet() & mask$iv$iv) != 0) {
                while (node$iv$iv != null) {
                    if ((node$iv$iv.getKindSet() & mask$iv$iv) != 0) {
                        Modifier.Node it$iv = node$iv$iv;
                        if (it$iv != self$iv) {
                            if ((it$iv.getKindSet() & untilType$iv4) != 0) {
                                return;
                            }
                        }
                        if ((it$iv.getKindSet() & type$iv4) != 0) {
                            MutableVector mutableVector2 = null;
                            Modifier.Node node = it$iv;
                            while (node != null) {
                                if (node instanceof FocusEventModifierNode) {
                                    FocusEventModifierNode it = (FocusEventModifierNode) node;
                                    $this$visitSelfAndAncestors_u2d5BbP62I$iv2 = $this$visitSelfAndAncestors_u2d5BbP62I$iv3;
                                    it.onFocusEvent(getFocusState(it));
                                    type$iv2 = type$iv4;
                                    untilType$iv2 = untilType$iv4;
                                    i2 = i4;
                                } else {
                                    $this$visitSelfAndAncestors_u2d5BbP62I$iv2 = $this$visitSelfAndAncestors_u2d5BbP62I$iv3;
                                    Modifier.Node this_$iv$iv$iv = node;
                                    if (((this_$iv$iv$iv.getKindSet() & type$iv4) != 0) && (node instanceof DelegatingNode)) {
                                        int count$iv$iv2 = 0;
                                        DelegatingNode this_$iv$iv$iv2 = (DelegatingNode) node;
                                        Modifier.Node node$iv$iv$iv = this_$iv$iv$iv2.getDelegate();
                                        while (node$iv$iv$iv != null) {
                                            Modifier.Node next$iv$iv = node$iv$iv$iv;
                                            if ((next$iv$iv.getKindSet() & type$iv4) != 0) {
                                                count$iv$iv2++;
                                                type$iv3 = type$iv4;
                                                if (count$iv$iv2 == 1) {
                                                    node = next$iv$iv;
                                                    untilType$iv3 = untilType$iv4;
                                                    i3 = i4;
                                                } else {
                                                    if (mutableVector2 == null) {
                                                        count$iv$iv = count$iv$iv2;
                                                        untilType$iv3 = untilType$iv4;
                                                        i3 = i4;
                                                        mutableVector = new MutableVector(new Modifier.Node[16], 0);
                                                    } else {
                                                        count$iv$iv = count$iv$iv2;
                                                        untilType$iv3 = untilType$iv4;
                                                        i3 = i4;
                                                        mutableVector = mutableVector2;
                                                    }
                                                    MutableVector mutableVector3 = mutableVector;
                                                    Modifier.Node theNode$iv$iv = node;
                                                    if (theNode$iv$iv != null) {
                                                        if (mutableVector3 != null) {
                                                            mutableVector3.add(theNode$iv$iv);
                                                        }
                                                        node = null;
                                                    }
                                                    if (mutableVector3 != null) {
                                                        mutableVector3.add(next$iv$iv);
                                                    }
                                                    mutableVector2 = mutableVector3;
                                                    count$iv$iv2 = count$iv$iv;
                                                }
                                            } else {
                                                type$iv3 = type$iv4;
                                                untilType$iv3 = untilType$iv4;
                                                i3 = i4;
                                            }
                                            node$iv$iv$iv = node$iv$iv$iv.getChild();
                                            type$iv4 = type$iv3;
                                            untilType$iv4 = untilType$iv3;
                                            i4 = i3;
                                        }
                                        type$iv2 = type$iv4;
                                        untilType$iv2 = untilType$iv4;
                                        i2 = i4;
                                        if (count$iv$iv2 == 1) {
                                            $this$visitSelfAndAncestors_u2d5BbP62I$iv3 = $this$visitSelfAndAncestors_u2d5BbP62I$iv2;
                                            type$iv4 = type$iv2;
                                            untilType$iv4 = untilType$iv2;
                                            i4 = i2;
                                        }
                                    } else {
                                        type$iv2 = type$iv4;
                                        untilType$iv2 = untilType$iv4;
                                        i2 = i4;
                                    }
                                }
                                node = DelegatableNodeKt.pop(mutableVector2);
                                $this$visitSelfAndAncestors_u2d5BbP62I$iv3 = $this$visitSelfAndAncestors_u2d5BbP62I$iv2;
                                type$iv4 = type$iv2;
                                untilType$iv4 = untilType$iv2;
                                i4 = i2;
                            }
                        }
                    }
                    node$iv$iv = node$iv$iv.getParent();
                    $this$visitSelfAndAncestors_u2d5BbP62I$iv3 = $this$visitSelfAndAncestors_u2d5BbP62I$iv3;
                    type$iv4 = type$iv4;
                    untilType$iv4 = untilType$iv4;
                    i4 = i4;
                }
                $this$visitSelfAndAncestors_u2d5BbP62I$iv = $this$visitSelfAndAncestors_u2d5BbP62I$iv3;
                type$iv = type$iv4;
                untilType$iv = untilType$iv4;
                i = i4;
            } else {
                $this$visitSelfAndAncestors_u2d5BbP62I$iv = $this$visitSelfAndAncestors_u2d5BbP62I$iv3;
                type$iv = type$iv4;
                untilType$iv = untilType$iv4;
                i = i4;
            }
            layout$iv$iv = layout$iv$iv.getParent$ui_release();
            node$iv$iv = (layout$iv$iv == null || (nodes = layout$iv$iv.getNodes()) == null) ? null : nodes.getTail();
            $this$visitSelfAndAncestors_u2d5BbP62I$iv3 = $this$visitSelfAndAncestors_u2d5BbP62I$iv;
            type$iv4 = type$iv;
            untilType$iv4 = untilType$iv;
            i4 = i;
        }
    }
}
