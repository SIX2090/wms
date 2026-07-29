package androidx.compose.ui.modifier;

import androidx.compose.runtime.collection.MutableVector;
import androidx.compose.ui.Modifier;
import androidx.compose.ui.node.BackwardsCompatNode;
import androidx.compose.ui.node.DelegatableNode;
import androidx.compose.ui.node.DelegatableNodeKt;
import androidx.compose.ui.node.DelegatingNode;
import androidx.compose.ui.node.LayoutNode;
import androidx.compose.ui.node.NodeKind;
import androidx.compose.ui.node.Owner;
import java.util.HashSet;
import java.util.Set;
import kotlin.Metadata;
import kotlin.Unit;
import kotlin.jvm.functions.Function0;

/* compiled from: ModifierLocalManager.kt */
@Metadata(d1 = {"\u0000H\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010\u000b\n\u0002\b\u0003\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0010\u0002\n\u0002\b\u0004\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010#\n\u0002\b\u0004\b\u0000\u0018\u00002\u00020\u0001B\r\u0012\u0006\u0010\u0002\u001a\u00020\u0003¢\u0006\u0002\u0010\u0004J\u001a\u0010\u0011\u001a\u00020\u00122\u0006\u0010\u0013\u001a\u00020\u00072\n\u0010\u0014\u001a\u0006\u0012\u0002\b\u00030\tJ\u0006\u0010\u0015\u001a\u00020\u0012J*\u0010\u0016\u001a\u00020\u00122\u0006\u0010\u0013\u001a\u00020\u00172\n\u0010\u0014\u001a\u0006\u0012\u0002\b\u00030\t2\f\u0010\u0018\u001a\b\u0012\u0004\u0012\u00020\u00070\u0019H\u0002J\u001a\u0010\u001a\u001a\u00020\u00122\u0006\u0010\u0013\u001a\u00020\u00072\n\u0010\u0014\u001a\u0006\u0012\u0002\b\u00030\tJ\u0006\u0010\u001b\u001a\u00020\u0012J\u001a\u0010\u001c\u001a\u00020\u00122\u0006\u0010\u0013\u001a\u00020\u00072\n\u0010\u0014\u001a\u0006\u0012\u0002\b\u00030\tR\u0014\u0010\u0005\u001a\b\u0012\u0004\u0012\u00020\u00070\u0006X\u0082\u0004¢\u0006\u0002\n\u0000R\u0018\u0010\b\u001a\f\u0012\b\u0012\u0006\u0012\u0002\b\u00030\t0\u0006X\u0082\u0004¢\u0006\u0002\n\u0000R\u000e\u0010\n\u001a\u00020\u000bX\u0082\u000e¢\u0006\u0002\n\u0000R\u0011\u0010\u0002\u001a\u00020\u0003¢\u0006\b\n\u0000\u001a\u0004\b\f\u0010\rR\u0014\u0010\u000e\u001a\b\u0012\u0004\u0012\u00020\u000f0\u0006X\u0082\u0004¢\u0006\u0002\n\u0000R\u0018\u0010\u0010\u001a\f\u0012\b\u0012\u0006\u0012\u0002\b\u00030\t0\u0006X\u0082\u0004¢\u0006\u0002\n\u0000¨\u0006\u001d"}, d2 = {"Landroidx/compose/ui/modifier/ModifierLocalManager;", "", "owner", "Landroidx/compose/ui/node/Owner;", "(Landroidx/compose/ui/node/Owner;)V", "inserted", "Landroidx/compose/runtime/collection/MutableVector;", "Landroidx/compose/ui/node/BackwardsCompatNode;", "insertedLocal", "Landroidx/compose/ui/modifier/ModifierLocal;", "invalidated", "", "getOwner", "()Landroidx/compose/ui/node/Owner;", "removed", "Landroidx/compose/ui/node/LayoutNode;", "removedLocal", "insertedProvider", "", "node", "key", "invalidate", "invalidateConsumersOfNodeForKey", "Landroidx/compose/ui/Modifier$Node;", "set", "", "removedProvider", "triggerUpdates", "updatedProvider", "ui_release"}, k = 1, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes11.dex */
public final class ModifierLocalManager {
    public static final int $stable = 8;
    private boolean invalidated;
    private final Owner owner;
    private final MutableVector<BackwardsCompatNode> inserted = new MutableVector<>(new BackwardsCompatNode[16], 0);
    private final MutableVector<ModifierLocal<?>> insertedLocal = new MutableVector<>(new ModifierLocal[16], 0);
    private final MutableVector<LayoutNode> removed = new MutableVector<>(new LayoutNode[16], 0);
    private final MutableVector<ModifierLocal<?>> removedLocal = new MutableVector<>(new ModifierLocal[16], 0);

    public ModifierLocalManager(Owner owner) {
        this.owner = owner;
    }

    public final Owner getOwner() {
        return this.owner;
    }

    public final void invalidate() {
        if (!this.invalidated) {
            this.invalidated = true;
            this.owner.registerOnEndApplyChangesListener(new Function0<Unit>() { // from class: androidx.compose.ui.modifier.ModifierLocalManager$invalidate$1
                {
                    super(0);
                }

                @Override // kotlin.jvm.functions.Function0
                public /* bridge */ /* synthetic */ Unit invoke() {
                    invoke2();
                    return Unit.INSTANCE;
                }

                /* renamed from: invoke, reason: avoid collision after fix types in other method */
                public final void invoke2() {
                    ModifierLocalManager.this.triggerUpdates();
                }
            });
        }
    }

    public final void triggerUpdates() {
        this.invalidated = false;
        Iterable toUpdate = new HashSet();
        MutableVector this_$iv = this.removed;
        int size$iv = this_$iv.getSize();
        if (size$iv > 0) {
            int i$iv = 0;
            Object[] content$iv = this_$iv.getContent();
            do {
                LayoutNode layout = (LayoutNode) content$iv[i$iv];
                int i = i$iv;
                ModifierLocal<?> key = this.removedLocal.getContent()[i];
                if (layout.getNodes().getHead().getIsAttached()) {
                    invalidateConsumersOfNodeForKey(layout.getNodes().getHead(), key, (Set) toUpdate);
                }
                i$iv++;
            } while (i$iv < size$iv);
        }
        this.removed.clear();
        this.removedLocal.clear();
        MutableVector this_$iv2 = this.inserted;
        int size$iv2 = this_$iv2.getSize();
        if (size$iv2 > 0) {
            int i$iv2 = 0;
            Object[] content$iv2 = this_$iv2.getContent();
            do {
                BackwardsCompatNode node = (BackwardsCompatNode) content$iv2[i$iv2];
                int i2 = i$iv2;
                ModifierLocal<?> key2 = this.insertedLocal.getContent()[i2];
                if (node.getIsAttached()) {
                    invalidateConsumersOfNodeForKey(node, key2, (Set) toUpdate);
                }
                i$iv2++;
            } while (i$iv2 < size$iv2);
        }
        this.inserted.clear();
        this.insertedLocal.clear();
        Iterable $this$forEach$iv = toUpdate;
        for (Object element$iv : $this$forEach$iv) {
            BackwardsCompatNode it = (BackwardsCompatNode) element$iv;
            it.updateModifierLocalConsumer();
        }
    }

    /* JADX WARN: Multi-variable type inference failed */
    private final void invalidateConsumersOfNodeForKey(Modifier.Node node, ModifierLocal<?> key, Set<BackwardsCompatNode> set) {
        Modifier.Node node2;
        int i;
        int i2;
        boolean z;
        DelegatableNode delegatableNode;
        int i3;
        boolean z2;
        int i4;
        int i5;
        MutableVector mutableVector;
        ModifierLocal<?> modifierLocal = key;
        Modifier.Node node3 = node;
        int m5222constructorimpl = NodeKind.m5222constructorimpl(32);
        int i6 = 0;
        if (!node3.getNode().getIsAttached()) {
            throw new IllegalStateException("visitSubtreeIf called on an unattached node".toString());
        }
        MutableVector mutableVector2 = new MutableVector(new Modifier.Node[16], 0);
        Modifier.Node child = node3.getNode().getChild();
        if (child == null) {
            DelegatableNodeKt.addLayoutNodeChildren(mutableVector2, node3.getNode());
        } else {
            mutableVector2.add(child);
        }
        while (mutableVector2.isNotEmpty()) {
            int size = mutableVector2.getSize();
            boolean z3 = true;
            Modifier.Node node4 = (Modifier.Node) mutableVector2.removeAt(size - 1);
            if ((node4.getAggregateChildKindSet() & m5222constructorimpl) != 0) {
                Modifier.Node node5 = node4;
                while (node5 != null) {
                    if ((node5.getKindSet() & m5222constructorimpl) != 0) {
                        MutableVector mutableVector3 = null;
                        Modifier.Node node6 = node5;
                        while (true) {
                            if (node6 == null) {
                                node2 = node3;
                                i = m5222constructorimpl;
                                i2 = i6;
                                z = z3;
                                delegatableNode = z ? 1 : 0;
                                break;
                            }
                            if (node6 instanceof ModifierLocalModifierNode) {
                                node2 = node3;
                                ModifierLocalModifierNode modifierLocalModifierNode = (ModifierLocalModifierNode) node6;
                                i2 = i6;
                                if ((modifierLocalModifierNode instanceof BackwardsCompatNode) && (((BackwardsCompatNode) modifierLocalModifierNode).getElement() instanceof ModifierLocalConsumer)) {
                                    if (((BackwardsCompatNode) modifierLocalModifierNode).getReadValues().contains(modifierLocal)) {
                                        set.add(modifierLocalModifierNode);
                                    }
                                }
                                if (modifierLocalModifierNode.getProvidedValues().contains$ui_release(modifierLocal)) {
                                    i = m5222constructorimpl;
                                    z = true;
                                    delegatableNode = null;
                                    break;
                                }
                                i3 = m5222constructorimpl;
                                z2 = true;
                            } else {
                                node2 = node3;
                                i2 = i6;
                                if (((node6.getKindSet() & m5222constructorimpl) != 0) && (node6 instanceof DelegatingNode)) {
                                    int i7 = 0;
                                    Modifier.Node delegate = ((DelegatingNode) node6).getDelegate();
                                    while (delegate != null) {
                                        Modifier.Node node7 = delegate;
                                        if ((node7.getKindSet() & m5222constructorimpl) != 0) {
                                            i7++;
                                            if (i7 == 1) {
                                                node6 = node7;
                                                i4 = m5222constructorimpl;
                                            } else {
                                                if (mutableVector3 == null) {
                                                    i5 = i7;
                                                    i4 = m5222constructorimpl;
                                                    mutableVector = new MutableVector(new Modifier.Node[16], 0);
                                                } else {
                                                    i5 = i7;
                                                    i4 = m5222constructorimpl;
                                                    mutableVector = mutableVector3;
                                                }
                                                Modifier.Node node8 = node6;
                                                if (node8 != null) {
                                                    if (mutableVector != null) {
                                                        mutableVector.add(node8);
                                                    }
                                                    node6 = null;
                                                }
                                                if (mutableVector != null) {
                                                    mutableVector.add(node7);
                                                }
                                                mutableVector3 = mutableVector;
                                                i7 = i5;
                                            }
                                        } else {
                                            i4 = m5222constructorimpl;
                                        }
                                        delegate = delegate.getChild();
                                        m5222constructorimpl = i4;
                                    }
                                    i3 = m5222constructorimpl;
                                    z2 = true;
                                    if (i7 == 1) {
                                        z3 = true;
                                        node3 = node2;
                                        i6 = i2;
                                        m5222constructorimpl = i3;
                                        modifierLocal = key;
                                    }
                                } else {
                                    i3 = m5222constructorimpl;
                                    z2 = true;
                                }
                            }
                            node6 = DelegatableNodeKt.pop(mutableVector3);
                            z3 = z2;
                            node3 = node2;
                            i6 = i2;
                            m5222constructorimpl = i3;
                            modifierLocal = key;
                        }
                        if (delegatableNode == null) {
                            modifierLocal = key;
                            node3 = node2;
                            i6 = i2;
                            m5222constructorimpl = i;
                            break;
                        }
                    } else {
                        node2 = node3;
                        i = m5222constructorimpl;
                        i2 = i6;
                        z = z3;
                    }
                    node5 = node5.getChild();
                    z3 = z;
                    node3 = node2;
                    i6 = i2;
                    m5222constructorimpl = i;
                    modifierLocal = key;
                }
            }
            DelegatableNodeKt.addLayoutNodeChildren(mutableVector2, node4);
            modifierLocal = key;
            node3 = node3;
            i6 = i6;
            m5222constructorimpl = m5222constructorimpl;
        }
    }

    public final void updatedProvider(BackwardsCompatNode node, ModifierLocal<?> key) {
        MutableVector this_$iv = this.inserted;
        this_$iv.add(node);
        MutableVector this_$iv2 = this.insertedLocal;
        this_$iv2.add(key);
        invalidate();
    }

    public final void insertedProvider(BackwardsCompatNode node, ModifierLocal<?> key) {
        MutableVector this_$iv = this.inserted;
        this_$iv.add(node);
        MutableVector this_$iv2 = this.insertedLocal;
        this_$iv2.add(key);
        invalidate();
    }

    public final void removedProvider(BackwardsCompatNode node, ModifierLocal<?> key) {
        MutableVector this_$iv = this.removed;
        this_$iv.add(DelegatableNodeKt.requireLayoutNode(node));
        MutableVector this_$iv2 = this.removedLocal;
        this_$iv2.add(key);
        invalidate();
    }
}
