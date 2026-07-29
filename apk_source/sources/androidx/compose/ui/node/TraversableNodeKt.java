package androidx.compose.ui.node;

import androidx.compose.runtime.collection.MutableVector;
import androidx.compose.ui.Actual_jvmKt;
import androidx.compose.ui.Modifier;
import androidx.compose.ui.node.TraversableNode;
import kotlin.Metadata;
import kotlin.jvm.functions.Function1;
import kotlin.jvm.internal.Intrinsics;

/* compiled from: TraversableNode.kt */
@Metadata(d1 = {"\u0000.\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010\u0000\n\u0000\n\u0002\u0010\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\u0010\u000b\n\u0002\b\u0003\n\u0002\u0018\u0002\n\u0000\u001a\u001b\u0010\u0000\u001a\u0004\u0018\u0001H\u0001\"\b\b\u0000\u0010\u0001*\u00020\u0002*\u0002H\u0001¢\u0006\u0002\u0010\u0003\u001a\u0016\u0010\u0000\u001a\u0004\u0018\u00010\u0002*\u00020\u00042\b\u0010\u0005\u001a\u0004\u0018\u00010\u0006\u001a-\u0010\u0007\u001a\u00020\b\"\b\b\u0000\u0010\u0001*\u00020\u0002*\u0002H\u00012\u0012\u0010\t\u001a\u000e\u0012\u0004\u0012\u0002H\u0001\u0012\u0004\u0012\u00020\u000b0\n¢\u0006\u0002\u0010\f\u001a(\u0010\u0007\u001a\u00020\b*\u00020\u00042\b\u0010\u0005\u001a\u0004\u0018\u00010\u00062\u0012\u0010\t\u001a\u000e\u0012\u0004\u0012\u00020\u0002\u0012\u0004\u0012\u00020\u000b0\n\u001a-\u0010\r\u001a\u00020\b\"\b\b\u0000\u0010\u0001*\u00020\u0002*\u0002H\u00012\u0012\u0010\t\u001a\u000e\u0012\u0004\u0012\u0002H\u0001\u0012\u0004\u0012\u00020\u000b0\n¢\u0006\u0002\u0010\f\u001a(\u0010\r\u001a\u00020\b*\u00020\u00042\b\u0010\u0005\u001a\u0004\u0018\u00010\u00062\u0012\u0010\t\u001a\u000e\u0012\u0004\u0012\u00020\u0002\u0012\u0004\u0012\u00020\u000b0\n\u001a-\u0010\u000e\u001a\u00020\b\"\b\b\u0000\u0010\u0001*\u00020\u0002*\u0002H\u00012\u0012\u0010\t\u001a\u000e\u0012\u0004\u0012\u0002H\u0001\u0012\u0004\u0012\u00020\u000f0\n¢\u0006\u0002\u0010\f\u001a(\u0010\u000e\u001a\u00020\b*\u00020\u00042\b\u0010\u0005\u001a\u0004\u0018\u00010\u00062\u0012\u0010\t\u001a\u000e\u0012\u0004\u0012\u00020\u0002\u0012\u0004\u0012\u00020\u000f0\n¨\u0006\u0010"}, d2 = {"findNearestAncestor", "T", "Landroidx/compose/ui/node/TraversableNode;", "(Landroidx/compose/ui/node/TraversableNode;)Landroidx/compose/ui/node/TraversableNode;", "Landroidx/compose/ui/node/DelegatableNode;", "key", "", "traverseAncestors", "", "block", "Lkotlin/Function1;", "", "(Landroidx/compose/ui/node/TraversableNode;Lkotlin/jvm/functions/Function1;)V", "traverseChildren", "traverseDescendants", "Landroidx/compose/ui/node/TraversableNode$Companion$TraverseDescendantsAction;", "ui_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes11.dex */
public final class TraversableNodeKt {
    public static final TraversableNode findNearestAncestor(DelegatableNode $this$findNearestAncestor, Object key) {
        int type$iv;
        DelegatableNode $this$visitAncestors_u2dY_u2dYKmho_u24default$iv;
        boolean includeSelf$iv;
        int i;
        NodeChain nodes;
        boolean includeSelf$iv2;
        int i2;
        int type$iv2;
        int type$iv3;
        int count$iv$iv;
        MutableVector mutableVector;
        Modifier.Node next$iv$iv;
        int type$iv4 = NodeKind.m5222constructorimpl(262144);
        DelegatableNode $this$visitAncestors_u2dY_u2dYKmho_u24default$iv2 = $this$findNearestAncestor;
        boolean includeSelf$iv3 = false;
        int i3 = 0;
        if (!$this$visitAncestors_u2dY_u2dYKmho_u24default$iv2.getNode().getIsAttached()) {
            throw new IllegalStateException("visitAncestors called on an unattached node".toString());
        }
        Modifier.Node node$iv$iv = $this$visitAncestors_u2dY_u2dYKmho_u24default$iv2.getNode().getParent();
        LayoutNode layout$iv$iv = DelegatableNodeKt.requireLayoutNode($this$visitAncestors_u2dY_u2dYKmho_u24default$iv2);
        while (layout$iv$iv != null) {
            Modifier.Node head$iv$iv = layout$iv$iv.getNodes().getHead();
            if ((head$iv$iv.getAggregateChildKindSet() & type$iv4) != 0) {
                while (node$iv$iv != null) {
                    if ((node$iv$iv.getKindSet() & type$iv4) != 0) {
                        Modifier.Node it$iv = node$iv$iv;
                        MutableVector mutableVector2 = null;
                        Modifier.Node node = it$iv;
                        while (node != null) {
                            DelegatableNode $this$visitAncestors_u2dY_u2dYKmho_u24default$iv3 = $this$visitAncestors_u2dY_u2dYKmho_u24default$iv2;
                            if (node instanceof TraversableNode) {
                                TraversableNode it = (TraversableNode) node;
                                includeSelf$iv2 = includeSelf$iv3;
                                i2 = i3;
                                if (Intrinsics.areEqual(key, it.getTraverseKey())) {
                                    return it;
                                }
                                type$iv2 = type$iv4;
                            } else {
                                includeSelf$iv2 = includeSelf$iv3;
                                i2 = i3;
                                Modifier.Node this_$iv$iv$iv = node;
                                int kindSet = this_$iv$iv$iv.getKindSet() & type$iv4;
                                int i4 = 1;
                                if ((kindSet != 0 ? 1 : 0) == 0 || !(node instanceof DelegatingNode)) {
                                    type$iv2 = type$iv4;
                                } else {
                                    int count$iv$iv2 = 0;
                                    DelegatingNode this_$iv$iv$iv2 = (DelegatingNode) node;
                                    Modifier.Node node$iv$iv$iv = this_$iv$iv$iv2.getDelegate();
                                    while (node$iv$iv$iv != null) {
                                        Modifier.Node next$iv$iv2 = node$iv$iv$iv;
                                        if (((next$iv$iv2.getKindSet() & type$iv4) != 0 ? i4 : 0) != 0) {
                                            count$iv$iv2++;
                                            if (count$iv$iv2 == i4) {
                                                node = next$iv$iv2;
                                                type$iv3 = type$iv4;
                                            } else {
                                                if (mutableVector2 == null) {
                                                    type$iv3 = type$iv4;
                                                    count$iv$iv = count$iv$iv2;
                                                    mutableVector = new MutableVector(new Modifier.Node[16], 0);
                                                } else {
                                                    type$iv3 = type$iv4;
                                                    count$iv$iv = count$iv$iv2;
                                                    mutableVector = mutableVector2;
                                                }
                                                mutableVector2 = mutableVector;
                                                Modifier.Node theNode$iv$iv = node;
                                                if (theNode$iv$iv != null) {
                                                    if (mutableVector2 != null) {
                                                        mutableVector2.add(theNode$iv$iv);
                                                    }
                                                    node = null;
                                                }
                                                if (mutableVector2 != null) {
                                                    next$iv$iv = next$iv$iv2;
                                                    mutableVector2.add(next$iv$iv);
                                                } else {
                                                    next$iv$iv = next$iv$iv2;
                                                }
                                                count$iv$iv2 = count$iv$iv;
                                            }
                                        } else {
                                            type$iv3 = type$iv4;
                                        }
                                        node$iv$iv$iv = node$iv$iv$iv.getChild();
                                        type$iv4 = type$iv3;
                                        i4 = 1;
                                    }
                                    type$iv2 = type$iv4;
                                    if (count$iv$iv2 == 1) {
                                        $this$visitAncestors_u2dY_u2dYKmho_u24default$iv2 = $this$visitAncestors_u2dY_u2dYKmho_u24default$iv3;
                                        includeSelf$iv3 = includeSelf$iv2;
                                        i3 = i2;
                                        type$iv4 = type$iv2;
                                    }
                                }
                            }
                            node = DelegatableNodeKt.pop(mutableVector2);
                            $this$visitAncestors_u2dY_u2dYKmho_u24default$iv2 = $this$visitAncestors_u2dY_u2dYKmho_u24default$iv3;
                            includeSelf$iv3 = includeSelf$iv2;
                            i3 = i2;
                            type$iv4 = type$iv2;
                        }
                    }
                    node$iv$iv = node$iv$iv.getParent();
                    $this$visitAncestors_u2dY_u2dYKmho_u24default$iv2 = $this$visitAncestors_u2dY_u2dYKmho_u24default$iv2;
                    includeSelf$iv3 = includeSelf$iv3;
                    i3 = i3;
                    type$iv4 = type$iv4;
                }
                type$iv = type$iv4;
                $this$visitAncestors_u2dY_u2dYKmho_u24default$iv = $this$visitAncestors_u2dY_u2dYKmho_u24default$iv2;
                includeSelf$iv = includeSelf$iv3;
                i = i3;
            } else {
                type$iv = type$iv4;
                $this$visitAncestors_u2dY_u2dYKmho_u24default$iv = $this$visitAncestors_u2dY_u2dYKmho_u24default$iv2;
                includeSelf$iv = includeSelf$iv3;
                i = i3;
            }
            layout$iv$iv = layout$iv$iv.getParent$ui_release();
            node$iv$iv = (layout$iv$iv == null || (nodes = layout$iv$iv.getNodes()) == null) ? null : nodes.getTail();
            $this$visitAncestors_u2dY_u2dYKmho_u24default$iv2 = $this$visitAncestors_u2dY_u2dYKmho_u24default$iv;
            includeSelf$iv3 = includeSelf$iv;
            i3 = i;
            type$iv4 = type$iv;
        }
        return null;
    }

    public static final <T extends TraversableNode> T findNearestAncestor(T t) {
        T $this$visitAncestors_u2dY_u2dYKmho_u24default$iv;
        int type$iv;
        boolean includeSelf$iv;
        int i;
        NodeChain nodes;
        boolean includeSelf$iv2;
        int i2;
        int type$iv2;
        int type$iv3;
        int count$iv$iv;
        MutableVector mutableVector;
        T t2 = t;
        T $this$visitAncestors_u2dY_u2dYKmho_u24default$iv2 = t2;
        int type$iv4 = NodeKind.m5222constructorimpl(262144);
        boolean includeSelf$iv3 = false;
        int i3 = 0;
        if (!$this$visitAncestors_u2dY_u2dYKmho_u24default$iv2.getNode().getIsAttached()) {
            throw new IllegalStateException("visitAncestors called on an unattached node".toString());
        }
        Modifier.Node node$iv$iv = $this$visitAncestors_u2dY_u2dYKmho_u24default$iv2.getNode().getParent();
        LayoutNode layout$iv$iv = DelegatableNodeKt.requireLayoutNode($this$visitAncestors_u2dY_u2dYKmho_u24default$iv2);
        while (layout$iv$iv != null) {
            Modifier.Node head$iv$iv = layout$iv$iv.getNodes().getHead();
            if ((head$iv$iv.getAggregateChildKindSet() & type$iv4) != 0) {
                while (node$iv$iv != null) {
                    if ((node$iv$iv.getKindSet() & type$iv4) != 0) {
                        Modifier.Node it$iv = node$iv$iv;
                        MutableVector mutableVector2 = null;
                        Modifier.Node node = it$iv;
                        while (node != null) {
                            T $this$visitAncestors_u2dY_u2dYKmho_u24default$iv3 = $this$visitAncestors_u2dY_u2dYKmho_u24default$iv2;
                            if (node instanceof TraversableNode) {
                                T t3 = (T) node;
                                includeSelf$iv2 = includeSelf$iv3;
                                i2 = i3;
                                if (Intrinsics.areEqual(t.getTraverseKey(), t3.getTraverseKey()) && Actual_jvmKt.areObjectsOfSameType(t2, t3)) {
                                    return t3;
                                }
                                type$iv2 = type$iv4;
                            } else {
                                includeSelf$iv2 = includeSelf$iv3;
                                i2 = i3;
                                Modifier.Node this_$iv$iv$iv = node;
                                int i4 = 1;
                                Modifier.Node this_$iv$iv$iv2 = (this_$iv$iv$iv.getKindSet() & type$iv4) != 0 ? 1 : null;
                                if (this_$iv$iv$iv2 == null || !(node instanceof DelegatingNode)) {
                                    type$iv2 = type$iv4;
                                } else {
                                    int count$iv$iv2 = 0;
                                    DelegatingNode this_$iv$iv$iv3 = (DelegatingNode) node;
                                    Modifier.Node node$iv$iv$iv = this_$iv$iv$iv3.getDelegate();
                                    while (node$iv$iv$iv != null) {
                                        Modifier.Node next$iv$iv = node$iv$iv$iv;
                                        if (((next$iv$iv.getKindSet() & type$iv4) != 0 ? i4 : 0) != 0) {
                                            count$iv$iv2++;
                                            if (count$iv$iv2 == i4) {
                                                node = next$iv$iv;
                                                type$iv3 = type$iv4;
                                            } else {
                                                if (mutableVector2 == null) {
                                                    count$iv$iv = count$iv$iv2;
                                                    type$iv3 = type$iv4;
                                                    mutableVector = new MutableVector(new Modifier.Node[16], 0);
                                                } else {
                                                    count$iv$iv = count$iv$iv2;
                                                    type$iv3 = type$iv4;
                                                    mutableVector = mutableVector2;
                                                }
                                                Modifier.Node theNode$iv$iv = node;
                                                if (theNode$iv$iv != null) {
                                                    if (mutableVector != null) {
                                                        mutableVector.add(theNode$iv$iv);
                                                    }
                                                    node = null;
                                                }
                                                if (mutableVector != null) {
                                                    mutableVector.add(next$iv$iv);
                                                }
                                                mutableVector2 = mutableVector;
                                                count$iv$iv2 = count$iv$iv;
                                            }
                                        } else {
                                            type$iv3 = type$iv4;
                                        }
                                        node$iv$iv$iv = node$iv$iv$iv.getChild();
                                        type$iv4 = type$iv3;
                                        i4 = 1;
                                    }
                                    type$iv2 = type$iv4;
                                    if (count$iv$iv2 == 1) {
                                        t2 = t;
                                        $this$visitAncestors_u2dY_u2dYKmho_u24default$iv2 = $this$visitAncestors_u2dY_u2dYKmho_u24default$iv3;
                                        includeSelf$iv3 = includeSelf$iv2;
                                        i3 = i2;
                                        type$iv4 = type$iv2;
                                    }
                                }
                            }
                            node = DelegatableNodeKt.pop(mutableVector2);
                            t2 = t;
                            $this$visitAncestors_u2dY_u2dYKmho_u24default$iv2 = $this$visitAncestors_u2dY_u2dYKmho_u24default$iv3;
                            includeSelf$iv3 = includeSelf$iv2;
                            i3 = i2;
                            type$iv4 = type$iv2;
                        }
                    }
                    node$iv$iv = node$iv$iv.getParent();
                    t2 = t;
                    $this$visitAncestors_u2dY_u2dYKmho_u24default$iv2 = $this$visitAncestors_u2dY_u2dYKmho_u24default$iv2;
                    includeSelf$iv3 = includeSelf$iv3;
                    i3 = i3;
                    type$iv4 = type$iv4;
                }
                $this$visitAncestors_u2dY_u2dYKmho_u24default$iv = $this$visitAncestors_u2dY_u2dYKmho_u24default$iv2;
                type$iv = type$iv4;
                includeSelf$iv = includeSelf$iv3;
                i = i3;
            } else {
                $this$visitAncestors_u2dY_u2dYKmho_u24default$iv = $this$visitAncestors_u2dY_u2dYKmho_u24default$iv2;
                type$iv = type$iv4;
                includeSelf$iv = includeSelf$iv3;
                i = i3;
            }
            layout$iv$iv = layout$iv$iv.getParent$ui_release();
            node$iv$iv = (layout$iv$iv == null || (nodes = layout$iv$iv.getNodes()) == null) ? null : nodes.getTail();
            t2 = t;
            $this$visitAncestors_u2dY_u2dYKmho_u24default$iv2 = $this$visitAncestors_u2dY_u2dYKmho_u24default$iv;
            includeSelf$iv3 = includeSelf$iv;
            i3 = i;
            type$iv4 = type$iv;
        }
        return null;
    }

    public static final void traverseAncestors(DelegatableNode $this$traverseAncestors, Object key, Function1<? super TraversableNode, Boolean> function1) {
        int type$iv;
        DelegatableNode $this$visitAncestors_u2dY_u2dYKmho_u24default$iv;
        boolean includeSelf$iv;
        int i;
        NodeChain nodes;
        int i2;
        int type$iv2;
        int type$iv3;
        int count$iv$iv;
        MutableVector mutableVector;
        int type$iv4 = NodeKind.m5222constructorimpl(262144);
        DelegatableNode $this$visitAncestors_u2dY_u2dYKmho_u24default$iv2 = $this$traverseAncestors;
        boolean includeSelf$iv2 = false;
        int i3 = 0;
        if (!$this$visitAncestors_u2dY_u2dYKmho_u24default$iv2.getNode().getIsAttached()) {
            throw new IllegalStateException("visitAncestors called on an unattached node".toString());
        }
        Modifier.Node node$iv$iv = $this$visitAncestors_u2dY_u2dYKmho_u24default$iv2.getNode().getParent();
        LayoutNode layout$iv$iv = DelegatableNodeKt.requireLayoutNode($this$visitAncestors_u2dY_u2dYKmho_u24default$iv2);
        while (layout$iv$iv != null) {
            Modifier.Node head$iv$iv = layout$iv$iv.getNodes().getHead();
            if ((head$iv$iv.getAggregateChildKindSet() & type$iv4) != 0) {
                while (node$iv$iv != null) {
                    if ((node$iv$iv.getKindSet() & type$iv4) != 0) {
                        Modifier.Node it$iv = node$iv$iv;
                        MutableVector mutableVector2 = null;
                        Modifier.Node node = it$iv;
                        while (node != null) {
                            DelegatableNode $this$visitAncestors_u2dY_u2dYKmho_u24default$iv3 = $this$visitAncestors_u2dY_u2dYKmho_u24default$iv2;
                            boolean includeSelf$iv3 = includeSelf$iv2;
                            if (node instanceof TraversableNode) {
                                TraversableNode it = (TraversableNode) node;
                                i2 = i3;
                                boolean continueTraversal = Intrinsics.areEqual(key, it.getTraverseKey()) ? function1.invoke(it).booleanValue() : true;
                                if (!continueTraversal) {
                                    return;
                                } else {
                                    type$iv2 = type$iv4;
                                }
                            } else {
                                i2 = i3;
                                Modifier.Node this_$iv$iv$iv = node;
                                if (((this_$iv$iv$iv.getKindSet() & type$iv4) != 0 ? 1 : 0) == 0 || !(node instanceof DelegatingNode)) {
                                    type$iv2 = type$iv4;
                                } else {
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
                                            } else {
                                                if (mutableVector2 == null) {
                                                    count$iv$iv = count$iv$iv2;
                                                    mutableVector = new MutableVector(new Modifier.Node[16], 0);
                                                } else {
                                                    count$iv$iv = count$iv$iv2;
                                                    mutableVector = mutableVector2;
                                                }
                                                mutableVector2 = mutableVector;
                                                Modifier.Node theNode$iv$iv = node;
                                                if (theNode$iv$iv != null) {
                                                    if (mutableVector2 != null) {
                                                        mutableVector2.add(theNode$iv$iv);
                                                    }
                                                    node = null;
                                                }
                                                if (mutableVector2 != null) {
                                                    mutableVector2.add(next$iv$iv);
                                                }
                                                count$iv$iv2 = count$iv$iv;
                                            }
                                        } else {
                                            type$iv3 = type$iv4;
                                        }
                                        node$iv$iv$iv = node$iv$iv$iv.getChild();
                                        type$iv4 = type$iv3;
                                    }
                                    type$iv2 = type$iv4;
                                    if (count$iv$iv2 == 1) {
                                        $this$visitAncestors_u2dY_u2dYKmho_u24default$iv2 = $this$visitAncestors_u2dY_u2dYKmho_u24default$iv3;
                                        includeSelf$iv2 = includeSelf$iv3;
                                        i3 = i2;
                                        type$iv4 = type$iv2;
                                    }
                                }
                            }
                            node = DelegatableNodeKt.pop(mutableVector2);
                            $this$visitAncestors_u2dY_u2dYKmho_u24default$iv2 = $this$visitAncestors_u2dY_u2dYKmho_u24default$iv3;
                            includeSelf$iv2 = includeSelf$iv3;
                            i3 = i2;
                            type$iv4 = type$iv2;
                        }
                    }
                    node$iv$iv = node$iv$iv.getParent();
                    $this$visitAncestors_u2dY_u2dYKmho_u24default$iv2 = $this$visitAncestors_u2dY_u2dYKmho_u24default$iv2;
                    includeSelf$iv2 = includeSelf$iv2;
                    i3 = i3;
                    type$iv4 = type$iv4;
                }
                type$iv = type$iv4;
                $this$visitAncestors_u2dY_u2dYKmho_u24default$iv = $this$visitAncestors_u2dY_u2dYKmho_u24default$iv2;
                includeSelf$iv = includeSelf$iv2;
                i = i3;
            } else {
                type$iv = type$iv4;
                $this$visitAncestors_u2dY_u2dYKmho_u24default$iv = $this$visitAncestors_u2dY_u2dYKmho_u24default$iv2;
                includeSelf$iv = includeSelf$iv2;
                i = i3;
            }
            layout$iv$iv = layout$iv$iv.getParent$ui_release();
            node$iv$iv = (layout$iv$iv == null || (nodes = layout$iv$iv.getNodes()) == null) ? null : nodes.getTail();
            $this$visitAncestors_u2dY_u2dYKmho_u24default$iv2 = $this$visitAncestors_u2dY_u2dYKmho_u24default$iv;
            includeSelf$iv2 = includeSelf$iv;
            i3 = i;
            type$iv4 = type$iv;
        }
    }

    public static final <T extends TraversableNode> void traverseAncestors(T t, Function1<? super T, Boolean> function1) {
        DelegatableNode $this$visitAncestors_u2dY_u2dYKmho_u24default$iv;
        int type$iv;
        boolean includeSelf$iv;
        int i;
        int mask$iv$iv;
        NodeChain nodes;
        DelegatableNode $this$visitAncestors_u2dY_u2dYKmho_u24default$iv2;
        int mask$iv$iv2;
        int type$iv2;
        int type$iv3;
        int count$iv$iv;
        MutableVector mutableVector;
        Modifier.Node next$iv$iv;
        DelegatableNode delegatableNode = t;
        DelegatableNode $this$visitAncestors_u2dY_u2dYKmho_u24default$iv3 = delegatableNode;
        int type$iv4 = NodeKind.m5222constructorimpl(262144);
        boolean includeSelf$iv2 = false;
        int i2 = 0;
        int mask$iv$iv3 = type$iv4;
        if (!$this$visitAncestors_u2dY_u2dYKmho_u24default$iv3.getNode().getIsAttached()) {
            throw new IllegalStateException("visitAncestors called on an unattached node".toString());
        }
        Modifier.Node node$iv$iv = $this$visitAncestors_u2dY_u2dYKmho_u24default$iv3.getNode().getParent();
        LayoutNode layout$iv$iv = DelegatableNodeKt.requireLayoutNode($this$visitAncestors_u2dY_u2dYKmho_u24default$iv3);
        while (layout$iv$iv != null) {
            Modifier.Node head$iv$iv = layout$iv$iv.getNodes().getHead();
            if ((head$iv$iv.getAggregateChildKindSet() & mask$iv$iv3) != 0) {
                while (node$iv$iv != null) {
                    if ((node$iv$iv.getKindSet() & mask$iv$iv3) != 0) {
                        Modifier.Node it$iv = node$iv$iv;
                        MutableVector mutableVector2 = null;
                        $this$visitAncestors_u2dY_u2dYKmho_u24default$iv2 = $this$visitAncestors_u2dY_u2dYKmho_u24default$iv3;
                        Modifier.Node node = it$iv;
                        while (node != null) {
                            boolean includeSelf$iv3 = includeSelf$iv2;
                            boolean includeSelf$iv4 = node instanceof TraversableNode;
                            int i3 = i2;
                            if (includeSelf$iv4) {
                                TraversableNode it = (TraversableNode) node;
                                mask$iv$iv2 = mask$iv$iv3;
                                boolean continueTraversal = (Intrinsics.areEqual(t.getTraverseKey(), it.getTraverseKey()) && Actual_jvmKt.areObjectsOfSameType(delegatableNode, it)) ? function1.invoke(it).booleanValue() : true;
                                if (!continueTraversal) {
                                    return;
                                } else {
                                    type$iv2 = type$iv4;
                                }
                            } else {
                                mask$iv$iv2 = mask$iv$iv3;
                                Modifier.Node this_$iv$iv$iv = node;
                                if (((this_$iv$iv$iv.getKindSet() & type$iv4) != 0) && (node instanceof DelegatingNode)) {
                                    int count$iv$iv2 = 0;
                                    DelegatingNode this_$iv$iv$iv2 = (DelegatingNode) node;
                                    Modifier.Node node$iv$iv$iv = this_$iv$iv$iv2.getDelegate();
                                    while (node$iv$iv$iv != null) {
                                        Modifier.Node next$iv$iv2 = node$iv$iv$iv;
                                        if ((next$iv$iv2.getKindSet() & type$iv4) != 0) {
                                            count$iv$iv2++;
                                            if (count$iv$iv2 == 1) {
                                                node = next$iv$iv2;
                                                type$iv3 = type$iv4;
                                            } else {
                                                if (mutableVector2 == null) {
                                                    type$iv3 = type$iv4;
                                                    count$iv$iv = count$iv$iv2;
                                                    mutableVector = new MutableVector(new Modifier.Node[16], 0);
                                                } else {
                                                    type$iv3 = type$iv4;
                                                    count$iv$iv = count$iv$iv2;
                                                    mutableVector = mutableVector2;
                                                }
                                                mutableVector2 = mutableVector;
                                                Modifier.Node theNode$iv$iv = node;
                                                if (theNode$iv$iv != null) {
                                                    if (mutableVector2 != null) {
                                                        mutableVector2.add(theNode$iv$iv);
                                                    }
                                                    node = null;
                                                }
                                                if (mutableVector2 != null) {
                                                    next$iv$iv = next$iv$iv2;
                                                    mutableVector2.add(next$iv$iv);
                                                } else {
                                                    next$iv$iv = next$iv$iv2;
                                                }
                                                count$iv$iv2 = count$iv$iv;
                                            }
                                        } else {
                                            type$iv3 = type$iv4;
                                        }
                                        node$iv$iv$iv = node$iv$iv$iv.getChild();
                                        type$iv4 = type$iv3;
                                    }
                                    type$iv2 = type$iv4;
                                    if (count$iv$iv2 == 1) {
                                        delegatableNode = t;
                                        includeSelf$iv2 = includeSelf$iv3;
                                        i2 = i3;
                                        mask$iv$iv3 = mask$iv$iv2;
                                        type$iv4 = type$iv2;
                                    }
                                } else {
                                    type$iv2 = type$iv4;
                                }
                            }
                            node = DelegatableNodeKt.pop(mutableVector2);
                            delegatableNode = t;
                            includeSelf$iv2 = includeSelf$iv3;
                            i2 = i3;
                            mask$iv$iv3 = mask$iv$iv2;
                            type$iv4 = type$iv2;
                        }
                    } else {
                        $this$visitAncestors_u2dY_u2dYKmho_u24default$iv2 = $this$visitAncestors_u2dY_u2dYKmho_u24default$iv3;
                    }
                    node$iv$iv = node$iv$iv.getParent();
                    delegatableNode = t;
                    $this$visitAncestors_u2dY_u2dYKmho_u24default$iv3 = $this$visitAncestors_u2dY_u2dYKmho_u24default$iv2;
                    includeSelf$iv2 = includeSelf$iv2;
                    i2 = i2;
                    mask$iv$iv3 = mask$iv$iv3;
                    type$iv4 = type$iv4;
                }
                $this$visitAncestors_u2dY_u2dYKmho_u24default$iv = $this$visitAncestors_u2dY_u2dYKmho_u24default$iv3;
                type$iv = type$iv4;
                includeSelf$iv = includeSelf$iv2;
                i = i2;
                mask$iv$iv = mask$iv$iv3;
            } else {
                $this$visitAncestors_u2dY_u2dYKmho_u24default$iv = $this$visitAncestors_u2dY_u2dYKmho_u24default$iv3;
                type$iv = type$iv4;
                includeSelf$iv = includeSelf$iv2;
                i = i2;
                mask$iv$iv = mask$iv$iv3;
            }
            layout$iv$iv = layout$iv$iv.getParent$ui_release();
            node$iv$iv = (layout$iv$iv == null || (nodes = layout$iv$iv.getNodes()) == null) ? null : nodes.getTail();
            delegatableNode = t;
            $this$visitAncestors_u2dY_u2dYKmho_u24default$iv3 = $this$visitAncestors_u2dY_u2dYKmho_u24default$iv;
            includeSelf$iv2 = includeSelf$iv;
            i2 = i;
            mask$iv$iv3 = mask$iv$iv;
            type$iv4 = type$iv;
        }
    }

    public static final void traverseChildren(DelegatableNode $this$traverseChildren, Object key, Function1<? super TraversableNode, Boolean> function1) {
        DelegatableNode $this$visitChildren_u2d6rFNWt0$iv;
        int i;
        int type$iv;
        int type$iv2;
        int type$iv3;
        int type$iv4 = NodeKind.m5222constructorimpl(262144);
        DelegatableNode $this$visitChildren_u2d6rFNWt0$iv2 = $this$traverseChildren;
        int i2 = 0;
        if (!$this$visitChildren_u2d6rFNWt0$iv2.getNode().getIsAttached()) {
            throw new IllegalStateException("visitChildren called on an unattached node".toString());
        }
        MutableVector branches$iv$iv = new MutableVector(new Modifier.Node[16], 0);
        Modifier.Node child$iv$iv = $this$visitChildren_u2d6rFNWt0$iv2.getNode().getChild();
        if (child$iv$iv == null) {
            DelegatableNodeKt.addLayoutNodeChildren(branches$iv$iv, $this$visitChildren_u2d6rFNWt0$iv2.getNode());
        } else {
            branches$iv$iv.add(child$iv$iv);
        }
        while (branches$iv$iv.isNotEmpty()) {
            Modifier.Node branch$iv$iv = (Modifier.Node) branches$iv$iv.removeAt(branches$iv$iv.getSize() - 1);
            if ((branch$iv$iv.getAggregateChildKindSet() & type$iv4) == 0) {
                DelegatableNodeKt.addLayoutNodeChildren(branches$iv$iv, branch$iv$iv);
            } else {
                Modifier.Node node$iv$iv = branch$iv$iv;
                while (true) {
                    if (node$iv$iv == null) {
                        break;
                    }
                    if ((node$iv$iv.getKindSet() & type$iv4) != 0) {
                        Modifier.Node it$iv = node$iv$iv;
                        MutableVector mutableVector = null;
                        Modifier.Node node = it$iv;
                        while (node != null) {
                            if (node instanceof TraversableNode) {
                                TraversableNode it = (TraversableNode) node;
                                $this$visitChildren_u2d6rFNWt0$iv = $this$visitChildren_u2d6rFNWt0$iv2;
                                i = i2;
                                boolean continueTraversal = Intrinsics.areEqual(key, it.getTraverseKey()) ? function1.invoke(it).booleanValue() : true;
                                if (!continueTraversal) {
                                    return;
                                }
                                type$iv = type$iv4;
                                type$iv2 = 1;
                            } else {
                                $this$visitChildren_u2d6rFNWt0$iv = $this$visitChildren_u2d6rFNWt0$iv2;
                                i = i2;
                                Modifier.Node this_$iv$iv$iv = node;
                                if (((this_$iv$iv$iv.getKindSet() & type$iv4) != 0) && (node instanceof DelegatingNode)) {
                                    int count$iv$iv = 0;
                                    DelegatingNode this_$iv$iv$iv2 = (DelegatingNode) node;
                                    Modifier.Node node$iv$iv$iv = this_$iv$iv$iv2.getDelegate();
                                    while (node$iv$iv$iv != null) {
                                        Modifier.Node next$iv$iv = node$iv$iv$iv;
                                        if ((next$iv$iv.getKindSet() & type$iv4) != 0) {
                                            count$iv$iv++;
                                            type$iv3 = type$iv4;
                                            if (count$iv$iv == 1) {
                                                node = next$iv$iv;
                                            } else {
                                                MutableVector mutableVector2 = mutableVector == null ? new MutableVector(new Modifier.Node[16], 0) : mutableVector;
                                                Modifier.Node theNode$iv$iv = node;
                                                if (theNode$iv$iv != null) {
                                                    if (mutableVector2 != null) {
                                                        mutableVector2.add(theNode$iv$iv);
                                                    }
                                                    node = null;
                                                }
                                                if (mutableVector2 != null) {
                                                    mutableVector2.add(next$iv$iv);
                                                }
                                                mutableVector = mutableVector2;
                                            }
                                        } else {
                                            type$iv3 = type$iv4;
                                        }
                                        node$iv$iv$iv = node$iv$iv$iv.getChild();
                                        type$iv4 = type$iv3;
                                    }
                                    type$iv = type$iv4;
                                    type$iv2 = 1;
                                    if (count$iv$iv == 1) {
                                        $this$visitChildren_u2d6rFNWt0$iv2 = $this$visitChildren_u2d6rFNWt0$iv;
                                        i2 = i;
                                        type$iv4 = type$iv;
                                    }
                                } else {
                                    type$iv = type$iv4;
                                    type$iv2 = 1;
                                }
                            }
                            node = DelegatableNodeKt.pop(mutableVector);
                            $this$visitChildren_u2d6rFNWt0$iv2 = $this$visitChildren_u2d6rFNWt0$iv;
                            i2 = i;
                            type$iv4 = type$iv;
                        }
                    } else {
                        node$iv$iv = node$iv$iv.getChild();
                        type$iv4 = type$iv4;
                    }
                }
            }
        }
    }

    public static final <T extends TraversableNode> void traverseChildren(T t, Function1<? super T, Boolean> function1) {
        DelegatableNode $this$visitChildren_u2d6rFNWt0$iv;
        int i;
        int type$iv;
        boolean z;
        int type$iv2;
        MutableVector mutableVector;
        DelegatableNode delegatableNode = t;
        DelegatableNode $this$visitChildren_u2d6rFNWt0$iv2 = delegatableNode;
        int type$iv3 = NodeKind.m5222constructorimpl(262144);
        int count$iv$iv = 0;
        if (!$this$visitChildren_u2d6rFNWt0$iv2.getNode().getIsAttached()) {
            throw new IllegalStateException("visitChildren called on an unattached node".toString());
        }
        MutableVector branches$iv$iv = new MutableVector(new Modifier.Node[16], 0);
        Modifier.Node child$iv$iv = $this$visitChildren_u2d6rFNWt0$iv2.getNode().getChild();
        if (child$iv$iv == null) {
            DelegatableNodeKt.addLayoutNodeChildren(branches$iv$iv, $this$visitChildren_u2d6rFNWt0$iv2.getNode());
        } else {
            branches$iv$iv.add(child$iv$iv);
        }
        while (branches$iv$iv.isNotEmpty()) {
            Modifier.Node branch$iv$iv = (Modifier.Node) branches$iv$iv.removeAt(branches$iv$iv.getSize() - 1);
            if ((branch$iv$iv.getAggregateChildKindSet() & type$iv3) != 0) {
                Modifier.Node node$iv$iv = branch$iv$iv;
                while (true) {
                    if (node$iv$iv == null) {
                        delegatableNode = t;
                        break;
                    }
                    if ((node$iv$iv.getKindSet() & type$iv3) != 0) {
                        Modifier.Node it$iv = node$iv$iv;
                        MutableVector mutableVector2 = null;
                        Modifier.Node node = it$iv;
                        while (node != null) {
                            if (node instanceof TraversableNode) {
                                TraversableNode it = (TraversableNode) node;
                                $this$visitChildren_u2d6rFNWt0$iv = $this$visitChildren_u2d6rFNWt0$iv2;
                                i = count$iv$iv;
                                boolean continueTraversal = (Intrinsics.areEqual(t.getTraverseKey(), it.getTraverseKey()) && Actual_jvmKt.areObjectsOfSameType(delegatableNode, it)) ? function1.invoke(it).booleanValue() : true;
                                if (!continueTraversal) {
                                    return;
                                }
                                type$iv = type$iv3;
                                z = true;
                            } else {
                                $this$visitChildren_u2d6rFNWt0$iv = $this$visitChildren_u2d6rFNWt0$iv2;
                                i = count$iv$iv;
                                Modifier.Node this_$iv$iv$iv = node;
                                if (((this_$iv$iv$iv.getKindSet() & type$iv3) != 0) && (node instanceof DelegatingNode)) {
                                    int count$iv$iv2 = 0;
                                    DelegatingNode this_$iv$iv$iv2 = (DelegatingNode) node;
                                    Modifier.Node node$iv$iv$iv = this_$iv$iv$iv2.getDelegate();
                                    while (node$iv$iv$iv != null) {
                                        Modifier.Node next$iv$iv = node$iv$iv$iv;
                                        if ((next$iv$iv.getKindSet() & type$iv3) != 0) {
                                            count$iv$iv2++;
                                            if (count$iv$iv2 == 1) {
                                                node = next$iv$iv;
                                                type$iv2 = type$iv3;
                                            } else {
                                                if (mutableVector2 == null) {
                                                    type$iv2 = type$iv3;
                                                    mutableVector = new MutableVector(new Modifier.Node[16], 0);
                                                } else {
                                                    type$iv2 = type$iv3;
                                                    mutableVector = mutableVector2;
                                                }
                                                Modifier.Node theNode$iv$iv = node;
                                                if (theNode$iv$iv != null) {
                                                    if (mutableVector != null) {
                                                        mutableVector.add(theNode$iv$iv);
                                                    }
                                                    node = null;
                                                }
                                                if (mutableVector != null) {
                                                    mutableVector.add(next$iv$iv);
                                                }
                                                mutableVector2 = mutableVector;
                                            }
                                        } else {
                                            type$iv2 = type$iv3;
                                        }
                                        node$iv$iv$iv = node$iv$iv$iv.getChild();
                                        type$iv3 = type$iv2;
                                    }
                                    type$iv = type$iv3;
                                    z = true;
                                    if (count$iv$iv2 == 1) {
                                        $this$visitChildren_u2d6rFNWt0$iv2 = $this$visitChildren_u2d6rFNWt0$iv;
                                        count$iv$iv = i;
                                        type$iv3 = type$iv;
                                        delegatableNode = t;
                                    }
                                } else {
                                    type$iv = type$iv3;
                                    z = true;
                                }
                            }
                            node = DelegatableNodeKt.pop(mutableVector2);
                            $this$visitChildren_u2d6rFNWt0$iv2 = $this$visitChildren_u2d6rFNWt0$iv;
                            count$iv$iv = i;
                            type$iv3 = type$iv;
                            delegatableNode = t;
                        }
                        delegatableNode = t;
                    } else {
                        node$iv$iv = node$iv$iv.getChild();
                        delegatableNode = t;
                    }
                }
            } else {
                DelegatableNodeKt.addLayoutNodeChildren(branches$iv$iv, branch$iv$iv);
            }
        }
    }

    public static final void traverseDescendants(DelegatableNode $this$traverseDescendants, Object key, Function1<? super TraversableNode, ? extends TraversableNode.Companion.TraverseDescendantsAction> function1) {
        int type$iv;
        DelegatableNode $this$visitSubtreeIf_u2d6rFNWt0$iv;
        int i;
        int mask$iv$iv;
        int type$iv2;
        int i2;
        int type$iv3;
        int type$iv4;
        int type$iv5;
        DelegatingNode this_$iv$iv$iv;
        int count$iv$iv;
        MutableVector mutableVector;
        int type$iv6 = NodeKind.m5222constructorimpl(262144);
        DelegatableNode $this$visitSubtreeIf_u2d6rFNWt0$iv2 = $this$traverseDescendants;
        int i3 = 0;
        int mask$iv$iv2 = type$iv6;
        if (!$this$visitSubtreeIf_u2d6rFNWt0$iv2.getNode().getIsAttached()) {
            throw new IllegalStateException("visitSubtreeIf called on an unattached node".toString());
        }
        MutableVector branches$iv$iv = new MutableVector(new Modifier.Node[16], 0);
        Modifier.Node child$iv$iv = $this$visitSubtreeIf_u2d6rFNWt0$iv2.getNode().getChild();
        if (child$iv$iv == null) {
            DelegatableNodeKt.addLayoutNodeChildren(branches$iv$iv, $this$visitSubtreeIf_u2d6rFNWt0$iv2.getNode());
        } else {
            branches$iv$iv.add(child$iv$iv);
        }
        while (branches$iv$iv.isNotEmpty()) {
            int size = branches$iv$iv.getSize();
            int i4 = 1;
            Modifier.Node branch$iv$iv = (Modifier.Node) branches$iv$iv.removeAt(size - 1);
            if ((branch$iv$iv.getAggregateChildKindSet() & mask$iv$iv2) != 0) {
                Modifier.Node node$iv$iv = branch$iv$iv;
                while (node$iv$iv != null) {
                    if ((node$iv$iv.getKindSet() & mask$iv$iv2) != 0) {
                        Modifier.Node node$iv = node$iv$iv;
                        MutableVector mutableVector2 = null;
                        Modifier.Node this_$iv$iv$iv2 = node$iv;
                        while (true) {
                            if (this_$iv$iv$iv2 == null) {
                                type$iv = type$iv6;
                                $this$visitSubtreeIf_u2d6rFNWt0$iv = $this$visitSubtreeIf_u2d6rFNWt0$iv2;
                                i = i3;
                                mask$iv$iv = mask$iv$iv2;
                                type$iv2 = i4;
                                i2 = type$iv2;
                                break;
                            }
                            if (this_$iv$iv$iv2 instanceof TraversableNode) {
                                Object it$iv = this_$iv$iv$iv2;
                                $this$visitSubtreeIf_u2d6rFNWt0$iv = $this$visitSubtreeIf_u2d6rFNWt0$iv2;
                                TraversableNode it = (TraversableNode) it$iv;
                                i = i3;
                                mask$iv$iv = mask$iv$iv2;
                                TraversableNode.Companion.TraverseDescendantsAction action = Intrinsics.areEqual(key, it.getTraverseKey()) ? function1.invoke(it) : TraversableNode.Companion.TraverseDescendantsAction.ContinueTraversal;
                                if (action == TraversableNode.Companion.TraverseDescendantsAction.CancelTraversal) {
                                    return;
                                }
                                if (!(action != TraversableNode.Companion.TraverseDescendantsAction.SkipSubtreeAndContinueTraversal)) {
                                    type$iv = type$iv6;
                                    type$iv2 = 1;
                                    i2 = 0;
                                    break;
                                }
                                type$iv3 = type$iv6;
                                type$iv4 = 1;
                            } else {
                                $this$visitSubtreeIf_u2d6rFNWt0$iv = $this$visitSubtreeIf_u2d6rFNWt0$iv2;
                                i = i3;
                                mask$iv$iv = mask$iv$iv2;
                                if (((this_$iv$iv$iv2.getKindSet() & type$iv6) != 0) && (this_$iv$iv$iv2 instanceof DelegatingNode)) {
                                    int count$iv$iv2 = 0;
                                    DelegatingNode this_$iv$iv$iv3 = (DelegatingNode) this_$iv$iv$iv2;
                                    Modifier.Node node$iv$iv$iv = this_$iv$iv$iv3.getDelegate();
                                    while (node$iv$iv$iv != null) {
                                        Modifier.Node next$iv$iv = node$iv$iv$iv;
                                        if ((next$iv$iv.getKindSet() & type$iv6) != 0) {
                                            count$iv$iv2++;
                                            type$iv5 = type$iv6;
                                            if (count$iv$iv2 == 1) {
                                                this_$iv$iv$iv2 = next$iv$iv;
                                                this_$iv$iv$iv = this_$iv$iv$iv3;
                                            } else {
                                                if (mutableVector2 == null) {
                                                    count$iv$iv = count$iv$iv2;
                                                    this_$iv$iv$iv = this_$iv$iv$iv3;
                                                    mutableVector = new MutableVector(new Modifier.Node[16], 0);
                                                } else {
                                                    count$iv$iv = count$iv$iv2;
                                                    this_$iv$iv$iv = this_$iv$iv$iv3;
                                                    mutableVector = mutableVector2;
                                                }
                                                Modifier.Node theNode$iv$iv = this_$iv$iv$iv2;
                                                if (theNode$iv$iv != null) {
                                                    if (mutableVector != null) {
                                                        mutableVector.add(theNode$iv$iv);
                                                    }
                                                    this_$iv$iv$iv2 = null;
                                                }
                                                if (mutableVector != null) {
                                                    mutableVector.add(next$iv$iv);
                                                }
                                                mutableVector2 = mutableVector;
                                                count$iv$iv2 = count$iv$iv;
                                            }
                                        } else {
                                            type$iv5 = type$iv6;
                                            this_$iv$iv$iv = this_$iv$iv$iv3;
                                        }
                                        node$iv$iv$iv = node$iv$iv$iv.getChild();
                                        type$iv6 = type$iv5;
                                        this_$iv$iv$iv3 = this_$iv$iv$iv;
                                    }
                                    type$iv3 = type$iv6;
                                    type$iv4 = 1;
                                    if (count$iv$iv2 == 1) {
                                        i4 = 1;
                                        $this$visitSubtreeIf_u2d6rFNWt0$iv2 = $this$visitSubtreeIf_u2d6rFNWt0$iv;
                                        i3 = i;
                                        mask$iv$iv2 = mask$iv$iv;
                                        type$iv6 = type$iv3;
                                    }
                                } else {
                                    type$iv3 = type$iv6;
                                    type$iv4 = 1;
                                }
                            }
                            this_$iv$iv$iv2 = DelegatableNodeKt.pop(mutableVector2);
                            i4 = type$iv4;
                            $this$visitSubtreeIf_u2d6rFNWt0$iv2 = $this$visitSubtreeIf_u2d6rFNWt0$iv;
                            i3 = i;
                            mask$iv$iv2 = mask$iv$iv;
                            type$iv6 = type$iv3;
                        }
                        if (i2 == 0) {
                            $this$visitSubtreeIf_u2d6rFNWt0$iv2 = $this$visitSubtreeIf_u2d6rFNWt0$iv;
                            i3 = i;
                            mask$iv$iv2 = mask$iv$iv;
                            type$iv6 = type$iv;
                            break;
                        }
                    } else {
                        type$iv = type$iv6;
                        $this$visitSubtreeIf_u2d6rFNWt0$iv = $this$visitSubtreeIf_u2d6rFNWt0$iv2;
                        i = i3;
                        mask$iv$iv = mask$iv$iv2;
                        type$iv2 = i4;
                    }
                    node$iv$iv = node$iv$iv.getChild();
                    i4 = type$iv2;
                    $this$visitSubtreeIf_u2d6rFNWt0$iv2 = $this$visitSubtreeIf_u2d6rFNWt0$iv;
                    i3 = i;
                    mask$iv$iv2 = mask$iv$iv;
                    type$iv6 = type$iv;
                }
            }
            DelegatableNodeKt.addLayoutNodeChildren(branches$iv$iv, branch$iv$iv);
            $this$visitSubtreeIf_u2d6rFNWt0$iv2 = $this$visitSubtreeIf_u2d6rFNWt0$iv2;
            i3 = i3;
            mask$iv$iv2 = mask$iv$iv2;
            type$iv6 = type$iv6;
        }
    }

    public static final <T extends TraversableNode> void traverseDescendants(T t, Function1<? super T, ? extends TraversableNode.Companion.TraverseDescendantsAction> function1) {
        DelegatableNode $this$visitSubtreeIf_u2d6rFNWt0$iv;
        int type$iv;
        int i;
        int mask$iv$iv;
        boolean z;
        int i2;
        boolean z2;
        int type$iv2;
        boolean z3;
        DelegatingNode this_$iv$iv$iv;
        int type$iv3;
        int count$iv$iv;
        MutableVector mutableVector;
        DelegatableNode delegatableNode = t;
        DelegatableNode $this$visitSubtreeIf_u2d6rFNWt0$iv2 = delegatableNode;
        int type$iv4 = NodeKind.m5222constructorimpl(262144);
        int i3 = 0;
        int mask$iv$iv2 = type$iv4;
        if (!$this$visitSubtreeIf_u2d6rFNWt0$iv2.getNode().getIsAttached()) {
            throw new IllegalStateException("visitSubtreeIf called on an unattached node".toString());
        }
        int i4 = 0;
        MutableVector branches$iv$iv = new MutableVector(new Modifier.Node[16], 0);
        Modifier.Node child$iv$iv = $this$visitSubtreeIf_u2d6rFNWt0$iv2.getNode().getChild();
        if (child$iv$iv == null) {
            DelegatableNodeKt.addLayoutNodeChildren(branches$iv$iv, $this$visitSubtreeIf_u2d6rFNWt0$iv2.getNode());
        } else {
            branches$iv$iv.add(child$iv$iv);
        }
        while (branches$iv$iv.isNotEmpty()) {
            int size = branches$iv$iv.getSize();
            boolean z4 = true;
            Modifier.Node branch$iv$iv = (Modifier.Node) branches$iv$iv.removeAt(size - 1);
            if ((branch$iv$iv.getAggregateChildKindSet() & mask$iv$iv2) != 0) {
                Modifier.Node node$iv$iv = branch$iv$iv;
                while (node$iv$iv != null) {
                    if ((node$iv$iv.getKindSet() & mask$iv$iv2) != 0) {
                        Modifier.Node node$iv = node$iv$iv;
                        MutableVector mutableVector2 = null;
                        Modifier.Node this_$iv$iv$iv2 = node$iv;
                        while (true) {
                            if (this_$iv$iv$iv2 == null) {
                                $this$visitSubtreeIf_u2d6rFNWt0$iv = $this$visitSubtreeIf_u2d6rFNWt0$iv2;
                                type$iv = type$iv4;
                                i = i3;
                                mask$iv$iv = mask$iv$iv2;
                                z = z4;
                                i2 = 0;
                                z2 = z;
                                break;
                            }
                            if (this_$iv$iv$iv2 instanceof TraversableNode) {
                                Object it$iv = this_$iv$iv$iv2;
                                $this$visitSubtreeIf_u2d6rFNWt0$iv = $this$visitSubtreeIf_u2d6rFNWt0$iv2;
                                TraversableNode it = (TraversableNode) it$iv;
                                i = i3;
                                mask$iv$iv = mask$iv$iv2;
                                TraversableNode.Companion.TraverseDescendantsAction action = (Intrinsics.areEqual(t.getTraverseKey(), it.getTraverseKey()) && Actual_jvmKt.areObjectsOfSameType(delegatableNode, it)) ? function1.invoke(it) : TraversableNode.Companion.TraverseDescendantsAction.ContinueTraversal;
                                if (action == TraversableNode.Companion.TraverseDescendantsAction.CancelTraversal) {
                                    return;
                                }
                                if (!(action != TraversableNode.Companion.TraverseDescendantsAction.SkipSubtreeAndContinueTraversal)) {
                                    type$iv = type$iv4;
                                    z = true;
                                    i2 = 0;
                                    z2 = false;
                                    break;
                                }
                                type$iv2 = type$iv4;
                                z3 = true;
                            } else {
                                $this$visitSubtreeIf_u2d6rFNWt0$iv = $this$visitSubtreeIf_u2d6rFNWt0$iv2;
                                i = i3;
                                mask$iv$iv = mask$iv$iv2;
                                if (((this_$iv$iv$iv2.getKindSet() & type$iv4) != 0) && (this_$iv$iv$iv2 instanceof DelegatingNode)) {
                                    int count$iv$iv2 = 0;
                                    DelegatingNode this_$iv$iv$iv3 = (DelegatingNode) this_$iv$iv$iv2;
                                    Modifier.Node node$iv$iv$iv = this_$iv$iv$iv3.getDelegate();
                                    while (node$iv$iv$iv != null) {
                                        Modifier.Node next$iv$iv = node$iv$iv$iv;
                                        if ((next$iv$iv.getKindSet() & type$iv4) != 0) {
                                            count$iv$iv2++;
                                            this_$iv$iv$iv = this_$iv$iv$iv3;
                                            if (count$iv$iv2 == 1) {
                                                this_$iv$iv$iv2 = next$iv$iv;
                                                type$iv3 = type$iv4;
                                            } else {
                                                if (mutableVector2 == null) {
                                                    count$iv$iv = count$iv$iv2;
                                                    type$iv3 = type$iv4;
                                                    mutableVector = new MutableVector(new Modifier.Node[16], 0);
                                                } else {
                                                    count$iv$iv = count$iv$iv2;
                                                    type$iv3 = type$iv4;
                                                    mutableVector = mutableVector2;
                                                }
                                                MutableVector mutableVector3 = mutableVector;
                                                Modifier.Node theNode$iv$iv = this_$iv$iv$iv2;
                                                if (theNode$iv$iv != null) {
                                                    if (mutableVector3 != null) {
                                                        mutableVector3.add(theNode$iv$iv);
                                                    }
                                                    this_$iv$iv$iv2 = null;
                                                }
                                                if (mutableVector3 != null) {
                                                    mutableVector3.add(next$iv$iv);
                                                }
                                                mutableVector2 = mutableVector3;
                                                count$iv$iv2 = count$iv$iv;
                                            }
                                        } else {
                                            this_$iv$iv$iv = this_$iv$iv$iv3;
                                            type$iv3 = type$iv4;
                                        }
                                        node$iv$iv$iv = node$iv$iv$iv.getChild();
                                        this_$iv$iv$iv3 = this_$iv$iv$iv;
                                        type$iv4 = type$iv3;
                                    }
                                    type$iv2 = type$iv4;
                                    z3 = true;
                                    if (count$iv$iv2 == 1) {
                                        delegatableNode = t;
                                        z4 = true;
                                        $this$visitSubtreeIf_u2d6rFNWt0$iv2 = $this$visitSubtreeIf_u2d6rFNWt0$iv;
                                        i3 = i;
                                        mask$iv$iv2 = mask$iv$iv;
                                        type$iv4 = type$iv2;
                                    }
                                } else {
                                    type$iv2 = type$iv4;
                                    z3 = true;
                                }
                            }
                            this_$iv$iv$iv2 = DelegatableNodeKt.pop(mutableVector2);
                            delegatableNode = t;
                            z4 = z3;
                            $this$visitSubtreeIf_u2d6rFNWt0$iv2 = $this$visitSubtreeIf_u2d6rFNWt0$iv;
                            i3 = i;
                            mask$iv$iv2 = mask$iv$iv;
                            type$iv4 = type$iv2;
                        }
                        boolean diveDeeper$iv$iv = z2;
                        if (!diveDeeper$iv$iv) {
                            delegatableNode = t;
                            i4 = i2;
                            $this$visitSubtreeIf_u2d6rFNWt0$iv2 = $this$visitSubtreeIf_u2d6rFNWt0$iv;
                            i3 = i;
                            mask$iv$iv2 = mask$iv$iv;
                            type$iv4 = type$iv;
                            break;
                        }
                    } else {
                        $this$visitSubtreeIf_u2d6rFNWt0$iv = $this$visitSubtreeIf_u2d6rFNWt0$iv2;
                        type$iv = type$iv4;
                        i = i3;
                        mask$iv$iv = mask$iv$iv2;
                        z = z4;
                        i2 = i4;
                    }
                    node$iv$iv = node$iv$iv.getChild();
                    delegatableNode = t;
                    z4 = z;
                    i4 = i2;
                    $this$visitSubtreeIf_u2d6rFNWt0$iv2 = $this$visitSubtreeIf_u2d6rFNWt0$iv;
                    i3 = i;
                    mask$iv$iv2 = mask$iv$iv;
                    type$iv4 = type$iv;
                }
            }
            DelegatableNodeKt.addLayoutNodeChildren(branches$iv$iv, branch$iv$iv);
            delegatableNode = t;
            i4 = i4;
            $this$visitSubtreeIf_u2d6rFNWt0$iv2 = $this$visitSubtreeIf_u2d6rFNWt0$iv2;
            i3 = i3;
            mask$iv$iv2 = mask$iv$iv2;
            type$iv4 = type$iv4;
        }
    }
}
