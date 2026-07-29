package androidx.compose.ui.modifier;

import androidx.compose.runtime.collection.MutableVector;
import androidx.compose.ui.Modifier;
import androidx.compose.ui.node.DelegatableNode;
import androidx.compose.ui.node.DelegatableNodeKt;
import androidx.compose.ui.node.DelegatingNode;
import androidx.compose.ui.node.LayoutNode;
import androidx.compose.ui.node.NodeChain;
import androidx.compose.ui.node.NodeKind;
import kotlin.Metadata;

/* compiled from: ModifierLocalModifierNode.kt */
@Metadata(d1 = {"\u0000&\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0004\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0010\u0002\n\u0002\b\u0004\bf\u0018\u00002\u00020\u00012\u00020\u0002J)\u0010\f\u001a\u00020\r\"\u0004\b\u0000\u0010\b2\f\u0010\u000e\u001a\b\u0012\u0004\u0012\u0002H\b0\t2\u0006\u0010\u000f\u001a\u0002H\bH\u0016¢\u0006\u0002\u0010\u0010R\u0014\u0010\u0003\u001a\u00020\u00048VX\u0096\u0004¢\u0006\u0006\u001a\u0004\b\u0005\u0010\u0006R$\u0010\u0007\u001a\u0002H\b\"\u0004\b\u0000\u0010\b*\b\u0012\u0004\u0012\u0002H\b0\t8VX\u0096\u0004¢\u0006\u0006\u001a\u0004\b\n\u0010\u000bø\u0001\u0000\u0082\u0002\u0006\n\u0004\b!0\u0001¨\u0006\u0011À\u0006\u0001"}, d2 = {"Landroidx/compose/ui/modifier/ModifierLocalModifierNode;", "Landroidx/compose/ui/modifier/ModifierLocalReadScope;", "Landroidx/compose/ui/node/DelegatableNode;", "providedValues", "Landroidx/compose/ui/modifier/ModifierLocalMap;", "getProvidedValues", "()Landroidx/compose/ui/modifier/ModifierLocalMap;", "current", "T", "Landroidx/compose/ui/modifier/ModifierLocal;", "getCurrent", "(Landroidx/compose/ui/modifier/ModifierLocal;)Ljava/lang/Object;", "provide", "", "key", "value", "(Landroidx/compose/ui/modifier/ModifierLocal;Ljava/lang/Object;)V", "ui_release"}, k = 1, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes11.dex */
public interface ModifierLocalModifierNode extends ModifierLocalReadScope, DelegatableNode {
    default ModifierLocalMap getProvidedValues() {
        return EmptyMap.INSTANCE;
    }

    default <T> void provide(ModifierLocal<T> key, T value) {
        if (!(getProvidedValues() != EmptyMap.INSTANCE)) {
            throw new IllegalArgumentException("In order to provide locals you must override providedValues: ModifierLocalMap".toString());
        }
        if (!getProvidedValues().contains$ui_release(key)) {
            throw new IllegalArgumentException(("Any provided key must be initially provided in the overridden providedValues: ModifierLocalMap property. Key " + key + " was not found.").toString());
        }
        getProvidedValues().mo5103set$ui_release(key, value);
    }

    @Override // androidx.compose.ui.modifier.ModifierLocalReadScope
    default <T> T getCurrent(ModifierLocal<T> modifierLocal) {
        ModifierLocalModifierNode modifierLocalModifierNode;
        int i;
        boolean z;
        int i2;
        NodeChain nodes;
        ModifierLocalModifierNode modifierLocalModifierNode2;
        int i3;
        int i4;
        int i5;
        int i6;
        MutableVector mutableVector;
        Modifier.Node node;
        if (!getNode().getIsAttached()) {
            throw new IllegalArgumentException("ModifierLocal accessed from an unattached node".toString());
        }
        ModifierLocalModifierNode modifierLocalModifierNode3 = this;
        int m5222constructorimpl = NodeKind.m5222constructorimpl(32);
        boolean z2 = false;
        int i7 = 0;
        if (!modifierLocalModifierNode3.getNode().getIsAttached()) {
            throw new IllegalStateException("visitAncestors called on an unattached node".toString());
        }
        Modifier.Node parent = modifierLocalModifierNode3.getNode().getParent();
        LayoutNode requireLayoutNode = DelegatableNodeKt.requireLayoutNode(modifierLocalModifierNode3);
        while (requireLayoutNode != null) {
            if ((requireLayoutNode.getNodes().getHead().getAggregateChildKindSet() & m5222constructorimpl) != 0) {
                while (parent != null) {
                    if ((parent.getKindSet() & m5222constructorimpl) != 0) {
                        MutableVector mutableVector2 = null;
                        modifierLocalModifierNode2 = modifierLocalModifierNode3;
                        Modifier.Node node2 = parent;
                        while (node2 != null) {
                            boolean z3 = z2;
                            if (node2 instanceof ModifierLocalModifierNode) {
                                ModifierLocalModifierNode modifierLocalModifierNode4 = (ModifierLocalModifierNode) node2;
                                i3 = i7;
                                if (modifierLocalModifierNode4.getProvidedValues().contains$ui_release(modifierLocal)) {
                                    return (T) modifierLocalModifierNode4.getProvidedValues().get$ui_release(modifierLocal);
                                }
                                i4 = m5222constructorimpl;
                            } else {
                                i3 = i7;
                                int i8 = 1;
                                if (((node2.getKindSet() & m5222constructorimpl) != 0 ? 1 : 0) == 0 || !(node2 instanceof DelegatingNode)) {
                                    i4 = m5222constructorimpl;
                                } else {
                                    int i9 = 0;
                                    Modifier.Node delegate = ((DelegatingNode) node2).getDelegate();
                                    while (delegate != null) {
                                        Modifier.Node node3 = delegate;
                                        if (((node3.getKindSet() & m5222constructorimpl) != 0 ? i8 : 0) != 0) {
                                            i9++;
                                            if (i9 == i8) {
                                                node2 = node3;
                                                i5 = m5222constructorimpl;
                                            } else {
                                                if (mutableVector2 == null) {
                                                    i5 = m5222constructorimpl;
                                                    i6 = i9;
                                                    mutableVector = new MutableVector(new Modifier.Node[16], 0);
                                                } else {
                                                    i5 = m5222constructorimpl;
                                                    i6 = i9;
                                                    mutableVector = mutableVector2;
                                                }
                                                mutableVector2 = mutableVector;
                                                Modifier.Node node4 = node2;
                                                if (node4 != null) {
                                                    if (mutableVector2 != null) {
                                                        mutableVector2.add(node4);
                                                    }
                                                    node2 = null;
                                                }
                                                if (mutableVector2 != null) {
                                                    node = node3;
                                                    mutableVector2.add(node);
                                                } else {
                                                    node = node3;
                                                }
                                                i9 = i6;
                                            }
                                        } else {
                                            i5 = m5222constructorimpl;
                                        }
                                        delegate = delegate.getChild();
                                        m5222constructorimpl = i5;
                                        i8 = 1;
                                    }
                                    i4 = m5222constructorimpl;
                                    if (i9 == 1) {
                                        z2 = z3;
                                        i7 = i3;
                                        m5222constructorimpl = i4;
                                    }
                                }
                            }
                            node2 = DelegatableNodeKt.pop(mutableVector2);
                            z2 = z3;
                            i7 = i3;
                            m5222constructorimpl = i4;
                        }
                    } else {
                        modifierLocalModifierNode2 = modifierLocalModifierNode3;
                    }
                    parent = parent.getParent();
                    modifierLocalModifierNode3 = modifierLocalModifierNode2;
                    z2 = z2;
                    i7 = i7;
                    m5222constructorimpl = m5222constructorimpl;
                }
                modifierLocalModifierNode = modifierLocalModifierNode3;
                i = m5222constructorimpl;
                z = z2;
                i2 = i7;
            } else {
                modifierLocalModifierNode = modifierLocalModifierNode3;
                i = m5222constructorimpl;
                z = z2;
                i2 = i7;
            }
            requireLayoutNode = requireLayoutNode.getParent$ui_release();
            parent = (requireLayoutNode == null || (nodes = requireLayoutNode.getNodes()) == null) ? null : nodes.getTail();
            modifierLocalModifierNode3 = modifierLocalModifierNode;
            z2 = z;
            i7 = i2;
            m5222constructorimpl = i;
        }
        return modifierLocal.getDefaultFactory$ui_release().invoke();
    }
}
