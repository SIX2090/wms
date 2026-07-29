package androidx.compose.foundation.lazy;

import androidx.compose.foundation.lazy.layout.LazyLayoutAnimation;
import androidx.compose.foundation.lazy.layout.LazyLayoutAnimationSpecsNode;
import androidx.compose.foundation.lazy.layout.LazyLayoutKeyIndexMap;
import androidx.compose.ui.unit.IntOffset;
import androidx.compose.ui.unit.IntOffsetKt;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import kotlin.Metadata;
import kotlin.collections.MapsKt;
import kotlin.jvm.internal.Intrinsics;
import kotlinx.coroutines.CoroutineScope;

/* compiled from: LazyListItemAnimator.kt */
@Metadata(d1 = {"\u0000`\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0002\b\u0002\n\u0002\u0010\b\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010%\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010!\n\u0002\u0018\u0002\n\u0002\b\u0004\n\u0002\u0010\u000b\n\u0002\b\u0003\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0010\u0002\n\u0002\b\t\n\u0002\u0018\u0002\n\u0002\b\u0004\n\u0002\u0018\u0002\n\u0002\b\u0004\b\u0000\u0018\u00002\u00020\u0001:\u0001.B\u0005¢\u0006\u0002\u0010\u0002J\u0018\u0010\u0017\u001a\u0004\u0018\u00010\u00182\u0006\u0010\u0019\u001a\u00020\u00012\u0006\u0010\u001a\u001a\u00020\u0004J\"\u0010\u001b\u001a\u00020\u001c2\u0006\u0010\u001d\u001a\u00020\u000f2\u0006\u0010\u001e\u001a\u00020\u00042\b\b\u0002\u0010\u001f\u001a\u00020\tH\u0002JT\u0010 \u001a\u00020\u001c2\u0006\u0010!\u001a\u00020\u00042\u0006\u0010\"\u001a\u00020\u00042\u0006\u0010#\u001a\u00020\u00042\f\u0010$\u001a\b\u0012\u0004\u0012\u00020\u000f0\u000e2\u0006\u0010%\u001a\u00020&2\u0006\u0010'\u001a\u00020\u00142\u0006\u0010(\u001a\u00020\u00142\u0006\u0010)\u001a\u00020\u00142\u0006\u0010*\u001a\u00020+J\u0006\u0010,\u001a\u00020\u001cJ\u0010\u0010-\u001a\u00020\u001c2\u0006\u0010\u001d\u001a\u00020\u000fH\u0002R\u000e\u0010\u0003\u001a\u00020\u0004X\u0082\u000e¢\u0006\u0002\n\u0000R\u0010\u0010\u0005\u001a\u0004\u0018\u00010\u0006X\u0082\u000e¢\u0006\u0002\n\u0000R\u001a\u0010\u0007\u001a\u000e\u0012\u0004\u0012\u00020\u0001\u0012\u0004\u0012\u00020\t0\bX\u0082\u0004¢\u0006\u0002\n\u0000R\u001e\u0010\n\u001a\u0012\u0012\u0004\u0012\u00020\u00010\u000bj\b\u0012\u0004\u0012\u00020\u0001`\fX\u0082\u0004¢\u0006\u0002\n\u0000R\u0014\u0010\r\u001a\b\u0012\u0004\u0012\u00020\u000f0\u000eX\u0082\u0004¢\u0006\u0002\n\u0000R\u0014\u0010\u0010\u001a\b\u0012\u0004\u0012\u00020\u000f0\u000eX\u0082\u0004¢\u0006\u0002\n\u0000R\u0014\u0010\u0011\u001a\b\u0012\u0004\u0012\u00020\u000f0\u000eX\u0082\u0004¢\u0006\u0002\n\u0000R\u0014\u0010\u0012\u001a\b\u0012\u0004\u0012\u00020\u000f0\u000eX\u0082\u0004¢\u0006\u0002\n\u0000R\u0018\u0010\u0013\u001a\u00020\u0014*\u00020\u000f8BX\u0082\u0004¢\u0006\u0006\u001a\u0004\b\u0015\u0010\u0016¨\u0006/"}, d2 = {"Landroidx/compose/foundation/lazy/LazyListItemAnimator;", "", "()V", "firstVisibleIndex", "", "keyIndexMap", "Landroidx/compose/foundation/lazy/layout/LazyLayoutKeyIndexMap;", "keyToItemInfoMap", "", "Landroidx/compose/foundation/lazy/LazyListItemAnimator$ItemInfo;", "movingAwayKeys", "Ljava/util/LinkedHashSet;", "Lkotlin/collections/LinkedHashSet;", "movingAwayToEndBound", "", "Landroidx/compose/foundation/lazy/LazyListMeasuredItem;", "movingAwayToStartBound", "movingInFromEndBound", "movingInFromStartBound", "hasAnimations", "", "getHasAnimations", "(Landroidx/compose/foundation/lazy/LazyListMeasuredItem;)Z", "getAnimation", "Landroidx/compose/foundation/lazy/layout/LazyLayoutAnimation;", "key", "placeableIndex", "initializeAnimation", "", "item", "mainAxisOffset", "itemInfo", "onMeasured", "consumedScroll", "layoutWidth", "layoutHeight", "positionedItems", "itemProvider", "Landroidx/compose/foundation/lazy/LazyListMeasuredItemProvider;", "isVertical", "isLookingAhead", "hasLookaheadOccurred", "coroutineScope", "Lkotlinx/coroutines/CoroutineScope;", "reset", "startPlacementAnimationsIfNeeded", "ItemInfo", "foundation_release"}, k = 1, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public final class LazyListItemAnimator {
    public static final int $stable = 8;
    private int firstVisibleIndex;
    private LazyLayoutKeyIndexMap keyIndexMap;
    private final Map<Object, ItemInfo> keyToItemInfoMap = new LinkedHashMap();
    private final LinkedHashSet<Object> movingAwayKeys = new LinkedHashSet<>();
    private final List<LazyListMeasuredItem> movingInFromStartBound = new ArrayList();
    private final List<LazyListMeasuredItem> movingInFromEndBound = new ArrayList();
    private final List<LazyListMeasuredItem> movingAwayToStartBound = new ArrayList();
    private final List<LazyListMeasuredItem> movingAwayToEndBound = new ArrayList();

    /* JADX WARN: Removed duplicated region for block: B:123:0x030f A[LOOP:7: B:116:0x02ef->B:123:0x030f, LOOP_END] */
    /* JADX WARN: Removed duplicated region for block: B:124:0x030d A[SYNTHETIC] */
    /*
        Code decompiled incorrectly, please refer to instructions dump.
        To view partially-correct add '--show-bad-code' argument
    */
    public final void onMeasured(int r39, int r40, int r41, java.util.List<androidx.compose.foundation.lazy.LazyListMeasuredItem> r42, androidx.compose.foundation.lazy.LazyListMeasuredItemProvider r43, boolean r44, boolean r45, boolean r46, kotlinx.coroutines.CoroutineScope r47) {
        /*
            Method dump skipped, instructions count: 1080
            To view this dump add '--comments-level debug' option
        */
        throw new UnsupportedOperationException("Method not decompiled: androidx.compose.foundation.lazy.LazyListItemAnimator.onMeasured(int, int, int, java.util.List, androidx.compose.foundation.lazy.LazyListMeasuredItemProvider, boolean, boolean, boolean, kotlinx.coroutines.CoroutineScope):void");
    }

    public final void reset() {
        this.keyToItemInfoMap.clear();
        this.keyIndexMap = LazyLayoutKeyIndexMap.INSTANCE;
        this.firstVisibleIndex = -1;
    }

    static /* synthetic */ void initializeAnimation$default(LazyListItemAnimator lazyListItemAnimator, LazyListMeasuredItem lazyListMeasuredItem, int i, ItemInfo itemInfo, int i2, Object obj) {
        if ((i2 & 4) != 0) {
            itemInfo = (ItemInfo) MapsKt.getValue(lazyListItemAnimator.keyToItemInfoMap, lazyListMeasuredItem.getKey());
        }
        lazyListItemAnimator.initializeAnimation(lazyListMeasuredItem, i, itemInfo);
    }

    private final void initializeAnimation(LazyListMeasuredItem item, int mainAxisOffset, ItemInfo itemInfo) {
        long targetFirstPlaceableOffset;
        long targetFirstPlaceableOffset2;
        LazyLayoutAnimation[] lazyLayoutAnimationArr;
        LazyListMeasuredItem lazyListMeasuredItem = item;
        int i = 0;
        long firstPlaceableOffset = lazyListMeasuredItem.m674getOffsetBjo55l4(0);
        if (item.getIsVertical()) {
            targetFirstPlaceableOffset = IntOffset.m6218copyiSbpLlY$default(firstPlaceableOffset, 0, mainAxisOffset, 1, null);
        } else {
            targetFirstPlaceableOffset = IntOffset.m6218copyiSbpLlY$default(firstPlaceableOffset, mainAxisOffset, 0, 2, null);
        }
        LazyLayoutAnimation[] animations = itemInfo.getAnimations();
        int index$iv = 0;
        int length = animations.length;
        while (i < length) {
            LazyLayoutAnimation lazyLayoutAnimation = animations[i];
            int index$iv2 = index$iv + 1;
            if (lazyLayoutAnimation == null) {
                targetFirstPlaceableOffset2 = targetFirstPlaceableOffset;
                lazyLayoutAnimationArr = animations;
            } else {
                long arg0$iv = lazyListMeasuredItem.m674getOffsetBjo55l4(index$iv);
                lazyLayoutAnimationArr = animations;
                long arg0$iv2 = IntOffsetKt.IntOffset(IntOffset.m6222getXimpl(arg0$iv) - IntOffset.m6222getXimpl(firstPlaceableOffset), IntOffset.m6223getYimpl(arg0$iv) - IntOffset.m6223getYimpl(firstPlaceableOffset));
                targetFirstPlaceableOffset2 = targetFirstPlaceableOffset;
                long targetFirstPlaceableOffset3 = IntOffsetKt.IntOffset(IntOffset.m6222getXimpl(targetFirstPlaceableOffset) + IntOffset.m6222getXimpl(arg0$iv2), IntOffset.m6223getYimpl(targetFirstPlaceableOffset) + IntOffset.m6223getYimpl(arg0$iv2));
                lazyLayoutAnimation.m715setRawOffsetgyyYBs(targetFirstPlaceableOffset3);
            }
            i++;
            lazyListMeasuredItem = item;
            index$iv = index$iv2;
            targetFirstPlaceableOffset = targetFirstPlaceableOffset2;
            animations = lazyLayoutAnimationArr;
        }
    }

    private final void startPlacementAnimationsIfNeeded(LazyListMeasuredItem item) {
        ItemInfo itemInfo;
        ItemInfo itemInfo2 = (ItemInfo) MapsKt.getValue(this.keyToItemInfoMap, item.getKey());
        LazyLayoutAnimation[] animations = itemInfo2.getAnimations();
        int index$iv = 0;
        int length = animations.length;
        int i = 0;
        while (i < length) {
            LazyLayoutAnimation lazyLayoutAnimation = animations[i];
            int index$iv2 = index$iv + 1;
            if (lazyLayoutAnimation != null) {
                long newTarget = item.m674getOffsetBjo55l4(index$iv);
                long currentTarget = lazyLayoutAnimation.getRawOffset();
                itemInfo = itemInfo2;
                if (!IntOffset.m6221equalsimpl0(currentTarget, LazyLayoutAnimation.INSTANCE.m716getNotInitializednOccac()) && !IntOffset.m6221equalsimpl0(currentTarget, newTarget)) {
                    lazyLayoutAnimation.m710animatePlacementDeltagyyYBs(IntOffsetKt.IntOffset(IntOffset.m6222getXimpl(newTarget) - IntOffset.m6222getXimpl(currentTarget), IntOffset.m6223getYimpl(newTarget) - IntOffset.m6223getYimpl(currentTarget)));
                }
                lazyLayoutAnimation.m715setRawOffsetgyyYBs(newTarget);
            } else {
                itemInfo = itemInfo2;
            }
            i++;
            index$iv = index$iv2;
            itemInfo2 = itemInfo;
        }
    }

    public final LazyLayoutAnimation getAnimation(Object key, int placeableIndex) {
        LazyLayoutAnimation[] animations;
        ItemInfo itemInfo = this.keyToItemInfoMap.get(key);
        if (itemInfo == null || (animations = itemInfo.getAnimations()) == null) {
            return null;
        }
        return animations[placeableIndex];
    }

    private final boolean getHasAnimations(LazyListMeasuredItem $this$hasAnimations) {
        LazyLayoutAnimationSpecsNode specs;
        int placeablesCount = $this$hasAnimations.getPlaceablesCount();
        for (int i = 0; i < placeablesCount; i++) {
            int index = i;
            specs = LazyListItemAnimatorKt.getSpecs($this$hasAnimations.getParentData(index));
            if (specs != null) {
                return true;
            }
        }
        return false;
    }

    /* compiled from: LazyListItemAnimator.kt */
    @Metadata(d1 = {"\u0000*\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0002\b\u0002\n\u0002\u0010\u0011\n\u0002\u0018\u0002\n\u0002\b\u0005\n\u0002\u0010\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\b\u0002\u0018\u00002\u00020\u0001B\u0005¢\u0006\u0002\u0010\u0002J\u0016\u0010\n\u001a\u00020\u000b2\u0006\u0010\f\u001a\u00020\r2\u0006\u0010\u000e\u001a\u00020\u000fR0\u0010\u0006\u001a\n\u0012\u0006\u0012\u0004\u0018\u00010\u00050\u00042\u000e\u0010\u0003\u001a\n\u0012\u0006\u0012\u0004\u0018\u00010\u00050\u0004@BX\u0086\u000e¢\u0006\n\n\u0002\u0010\t\u001a\u0004\b\u0007\u0010\b¨\u0006\u0010"}, d2 = {"Landroidx/compose/foundation/lazy/LazyListItemAnimator$ItemInfo;", "", "()V", "<set-?>", "", "Landroidx/compose/foundation/lazy/layout/LazyLayoutAnimation;", "animations", "getAnimations", "()[Landroidx/compose/foundation/lazy/layout/LazyLayoutAnimation;", "[Landroidx/compose/foundation/lazy/layout/LazyLayoutAnimation;", "updateAnimation", "", "positionedItem", "Landroidx/compose/foundation/lazy/LazyListMeasuredItem;", "coroutineScope", "Lkotlinx/coroutines/CoroutineScope;", "foundation_release"}, k = 1, mv = {1, 8, 0}, xi = 48)
    private static final class ItemInfo {
        private LazyLayoutAnimation[] animations;

        public ItemInfo() {
            LazyLayoutAnimation[] lazyLayoutAnimationArr;
            lazyLayoutAnimationArr = LazyListItemAnimatorKt.EmptyArray;
            this.animations = lazyLayoutAnimationArr;
        }

        public final LazyLayoutAnimation[] getAnimations() {
            return this.animations;
        }

        public final void updateAnimation(LazyListMeasuredItem positionedItem, CoroutineScope coroutineScope) {
            LazyLayoutAnimationSpecsNode specs;
            int length = this.animations.length;
            for (int i = positionedItem.getPlaceablesCount(); i < length; i++) {
                LazyLayoutAnimation lazyLayoutAnimation = this.animations[i];
                if (lazyLayoutAnimation != null) {
                    lazyLayoutAnimation.stopAnimations();
                }
            }
            if (this.animations.length != positionedItem.getPlaceablesCount()) {
                Object[] copyOf = Arrays.copyOf(this.animations, positionedItem.getPlaceablesCount());
                Intrinsics.checkNotNullExpressionValue(copyOf, "copyOf(this, newSize)");
                this.animations = (LazyLayoutAnimation[]) copyOf;
            }
            int placeablesCount = positionedItem.getPlaceablesCount();
            for (int i2 = 0; i2 < placeablesCount; i2++) {
                int index = i2;
                specs = LazyListItemAnimatorKt.getSpecs(positionedItem.getParentData(index));
                if (specs == null) {
                    LazyLayoutAnimation lazyLayoutAnimation2 = this.animations[index];
                    if (lazyLayoutAnimation2 != null) {
                        lazyLayoutAnimation2.stopAnimations();
                    }
                    this.animations[index] = null;
                } else {
                    LazyLayoutAnimation it = this.animations[index];
                    if (it == null) {
                        it = new LazyLayoutAnimation(coroutineScope);
                        this.animations[index] = it;
                    }
                    it.setAppearanceSpec(specs.getAppearanceSpec());
                    it.setPlacementSpec(specs.getPlacementSpec());
                }
            }
        }
    }
}
