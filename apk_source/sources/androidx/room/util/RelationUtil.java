package androidx.room.util;

import androidx.collection.ArrayMap;
import androidx.collection.LongSparseArray;
import androidx.room.RoomDatabase;
import java.util.HashMap;
import java.util.Map;
import kotlin.Metadata;
import kotlin.Unit;
import kotlin.jvm.functions.Function1;
import kotlin.jvm.internal.Intrinsics;

/* compiled from: RelationUtil.kt */
@Metadata(d1 = {"\u00002\n\u0000\n\u0002\u0010\u0002\n\u0000\n\u0002\u0010\u0000\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010\u000b\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\u001aR\u0010\u0000\u001a\u00020\u0001\"\b\b\u0000\u0010\u0002*\u00020\u0003\"\u0004\b\u0001\u0010\u00042\u0012\u0010\u0005\u001a\u000e\u0012\u0004\u0012\u0002H\u0002\u0012\u0004\u0012\u0002H\u00040\u00062\u0006\u0010\u0007\u001a\u00020\b2\u001e\u0010\t\u001a\u001a\u0012\u0010\u0012\u000e\u0012\u0004\u0012\u0002H\u0002\u0012\u0004\u0012\u0002H\u00040\u0006\u0012\u0004\u0012\u00020\u00010\n\u001ar\u0010\u000b\u001a\u00020\u0001\"\b\b\u0000\u0010\u0002*\u00020\u0003\"\u0004\b\u0001\u0010\u00042\"\u0010\u0005\u001a\u001e\u0012\u0004\u0012\u0002H\u0002\u0012\u0004\u0012\u0002H\u00040\fj\u000e\u0012\u0004\u0012\u0002H\u0002\u0012\u0004\u0012\u0002H\u0004`\r2\u0006\u0010\u0007\u001a\u00020\b2.\u0010\t\u001a*\u0012 \u0012\u001e\u0012\u0004\u0012\u0002H\u0002\u0012\u0004\u0012\u0002H\u00040\fj\u000e\u0012\u0004\u0012\u0002H\u0002\u0012\u0004\u0012\u0002H\u0004`\r\u0012\u0004\u0012\u00020\u00010\n\u001a<\u0010\u000e\u001a\u00020\u0001\"\u0004\b\u0000\u0010\u00042\f\u0010\u0005\u001a\b\u0012\u0004\u0012\u0002H\u00040\u000f2\u0006\u0010\u0007\u001a\u00020\b2\u0018\u0010\t\u001a\u0014\u0012\n\u0012\b\u0012\u0004\u0012\u0002H\u00040\u000f\u0012\u0004\u0012\u00020\u00010\n¨\u0006\u0010"}, d2 = {"recursiveFetchArrayMap", "", "K", "", "V", "map", "Landroidx/collection/ArrayMap;", "isRelationCollection", "", "fetchBlock", "Lkotlin/Function1;", "recursiveFetchHashMap", "Ljava/util/HashMap;", "Lkotlin/collections/HashMap;", "recursiveFetchLongSparseArray", "Landroidx/collection/LongSparseArray;", "room-runtime_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes11.dex */
public final class RelationUtil {
    public static final <K, V> void recursiveFetchHashMap(HashMap<K, V> map, boolean isRelationCollection, Function1<? super HashMap<K, V>, Unit> fetchBlock) {
        Intrinsics.checkNotNullParameter(map, "map");
        Intrinsics.checkNotNullParameter(fetchBlock, "fetchBlock");
        HashMap tmpMap = new HashMap(RoomDatabase.MAX_BIND_PARAMETER_CNT);
        int count = 0;
        for (K key : map.keySet()) {
            if (isRelationCollection) {
                Intrinsics.checkNotNullExpressionValue(key, "key");
                tmpMap.put(key, map.get(key));
            } else {
                Intrinsics.checkNotNullExpressionValue(key, "key");
                tmpMap.put(key, null);
            }
            count++;
            if (count == 999) {
                fetchBlock.invoke(tmpMap);
                if (!isRelationCollection) {
                    map.putAll(tmpMap);
                }
                tmpMap.clear();
                count = 0;
            }
        }
        if (count > 0) {
            fetchBlock.invoke(tmpMap);
            if (!isRelationCollection) {
                map.putAll(tmpMap);
            }
        }
    }

    public static final <V> void recursiveFetchLongSparseArray(LongSparseArray<V> map, boolean z, Function1<? super LongSparseArray<V>, Unit> fetchBlock) {
        Intrinsics.checkNotNullParameter(map, "map");
        Intrinsics.checkNotNullParameter(fetchBlock, "fetchBlock");
        LongSparseArray<? extends V> longSparseArray = new LongSparseArray<>(RoomDatabase.MAX_BIND_PARAMETER_CNT);
        int i = 0;
        int i2 = 0;
        int size = map.size();
        while (i2 < size) {
            if (z) {
                longSparseArray.put(map.keyAt(i2), map.valueAt(i2));
            } else {
                longSparseArray.put(map.keyAt(i2), null);
            }
            i2++;
            i++;
            if (i == 999) {
                fetchBlock.invoke(longSparseArray);
                if (!z) {
                    map.putAll(longSparseArray);
                }
                longSparseArray.clear();
                i = 0;
            }
        }
        if (i > 0) {
            fetchBlock.invoke(longSparseArray);
            if (!z) {
                map.putAll(longSparseArray);
            }
        }
    }

    public static final <K, V> void recursiveFetchArrayMap(ArrayMap<K, V> map, boolean isRelationCollection, Function1<? super ArrayMap<K, V>, Unit> fetchBlock) {
        Intrinsics.checkNotNullParameter(map, "map");
        Intrinsics.checkNotNullParameter(fetchBlock, "fetchBlock");
        ArrayMap tmpMap = new ArrayMap(RoomDatabase.MAX_BIND_PARAMETER_CNT);
        int count = 0;
        int mapIndex = 0;
        int limit = map.getSize();
        while (mapIndex < limit) {
            if (isRelationCollection) {
                tmpMap.put(map.keyAt(mapIndex), map.valueAt(mapIndex));
            } else {
                tmpMap.put(map.keyAt(mapIndex), null);
            }
            mapIndex++;
            count++;
            if (count == 999) {
                fetchBlock.invoke(tmpMap);
                if (!isRelationCollection) {
                    map.putAll((Map) tmpMap);
                }
                tmpMap.clear();
                count = 0;
            }
        }
        if (count > 0) {
            fetchBlock.invoke(tmpMap);
            if (!isRelationCollection) {
                map.putAll((Map) tmpMap);
            }
        }
    }
}
