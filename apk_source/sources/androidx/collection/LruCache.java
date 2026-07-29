package androidx.collection;

import androidx.collection.internal.Lock;
import androidx.collection.internal.LruHashMap;
import java.util.LinkedHashMap;
import java.util.Map;
import kotlin.Metadata;
import kotlin.Unit;
import kotlin.jvm.internal.Intrinsics;

/* compiled from: LruCache.kt */
@Metadata(d1 = {"\u0000@\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010\u0000\n\u0002\b\u0002\n\u0002\u0010\b\n\u0002\b\u0005\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0007\n\u0002\u0010\u0002\n\u0000\n\u0002\u0010\u000b\n\u0002\b\u000e\n\u0002\u0010%\n\u0000\n\u0002\u0010\u000e\n\u0002\b\u0002\b\u0016\u0018\u0000*\b\b\u0000\u0010\u0001*\u00020\u0002*\b\b\u0001\u0010\u0003*\u00020\u00022\u00020\u0002B\u000f\u0012\b\b\u0001\u0010\u0004\u001a\u00020\u0005¢\u0006\u0002\u0010\u0006J\u0017\u0010\u0011\u001a\u0004\u0018\u00018\u00012\u0006\u0010\u0012\u001a\u00028\u0000H\u0014¢\u0006\u0002\u0010\u0013J\u0006\u0010\u0007\u001a\u00020\u0005J/\u0010\u0014\u001a\u00020\u00152\u0006\u0010\u0016\u001a\u00020\u00172\u0006\u0010\u0012\u001a\u00028\u00002\u0006\u0010\u0018\u001a\u00028\u00012\b\u0010\u0019\u001a\u0004\u0018\u00018\u0001H\u0014¢\u0006\u0002\u0010\u001aJ\u0006\u0010\u001b\u001a\u00020\u0015J\u0006\u0010\b\u001a\u00020\u0005J\u0018\u0010\u001c\u001a\u0004\u0018\u00018\u00012\u0006\u0010\u0012\u001a\u00028\u0000H\u0086\u0002¢\u0006\u0002\u0010\u0013J\u0006\u0010\t\u001a\u00020\u0005J\u0006\u0010\u0004\u001a\u00020\u0005J\u0006\u0010\u000e\u001a\u00020\u0005J\u001d\u0010\u001d\u001a\u0004\u0018\u00018\u00012\u0006\u0010\u0012\u001a\u00028\u00002\u0006\u0010\u001e\u001a\u00028\u0001¢\u0006\u0002\u0010\u001fJ\u0006\u0010\u000f\u001a\u00020\u0005J\u0015\u0010 \u001a\u0004\u0018\u00018\u00012\u0006\u0010\u0012\u001a\u00028\u0000¢\u0006\u0002\u0010\u0013J\u0012\u0010!\u001a\u00020\u00152\b\b\u0001\u0010\u0004\u001a\u00020\u0005H\u0016J\u001d\u0010\"\u001a\u00020\u00052\u0006\u0010\u0012\u001a\u00028\u00002\u0006\u0010\u001e\u001a\u00028\u0001H\u0002¢\u0006\u0002\u0010#J\u0006\u0010\u0010\u001a\u00020\u0005J\u001d\u0010$\u001a\u00020\u00052\u0006\u0010\u0012\u001a\u00028\u00002\u0006\u0010\u001e\u001a\u00028\u0001H\u0014¢\u0006\u0002\u0010#J\u0012\u0010%\u001a\u000e\u0012\u0004\u0012\u00028\u0000\u0012\u0004\u0012\u00028\u00010&J\b\u0010'\u001a\u00020(H\u0016J\u0010\u0010)\u001a\u00020\u00152\u0006\u0010\u0004\u001a\u00020\u0005H\u0016R\u000e\u0010\u0007\u001a\u00020\u0005X\u0082\u000e¢\u0006\u0002\n\u0000R\u000e\u0010\b\u001a\u00020\u0005X\u0082\u000e¢\u0006\u0002\n\u0000R\u000e\u0010\t\u001a\u00020\u0005X\u0082\u000e¢\u0006\u0002\n\u0000R\u000e\u0010\n\u001a\u00020\u000bX\u0082\u0004¢\u0006\u0002\n\u0000R\u001a\u0010\f\u001a\u000e\u0012\u0004\u0012\u00028\u0000\u0012\u0004\u0012\u00028\u00010\rX\u0082\u0004¢\u0006\u0002\n\u0000R\u000e\u0010\u0004\u001a\u00020\u0005X\u0082\u000e¢\u0006\u0002\n\u0000R\u000e\u0010\u000e\u001a\u00020\u0005X\u0082\u000e¢\u0006\u0002\n\u0000R\u000e\u0010\u000f\u001a\u00020\u0005X\u0082\u000e¢\u0006\u0002\n\u0000R\u000e\u0010\u0010\u001a\u00020\u0005X\u0082\u000e¢\u0006\u0002\n\u0000¨\u0006*"}, d2 = {"Landroidx/collection/LruCache;", "K", "", "V", "maxSize", "", "(I)V", "createCount", "evictionCount", "hitCount", "lock", "Landroidx/collection/internal/Lock;", "map", "Landroidx/collection/internal/LruHashMap;", "missCount", "putCount", "size", "create", "key", "(Ljava/lang/Object;)Ljava/lang/Object;", "entryRemoved", "", "evicted", "", "oldValue", "newValue", "(ZLjava/lang/Object;Ljava/lang/Object;Ljava/lang/Object;)V", "evictAll", "get", "put", "value", "(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;", "remove", "resize", "safeSizeOf", "(Ljava/lang/Object;Ljava/lang/Object;)I", "sizeOf", "snapshot", "", "toString", "", "trimToSize", "collection"}, k = 1, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes.dex */
public class LruCache<K, V> {
    private int createCount;
    private int evictionCount;
    private int hitCount;
    private final Lock lock;
    private final LruHashMap<K, V> map;
    private int maxSize;
    private int missCount;
    private int putCount;
    private int size;

    public LruCache(int maxSize) {
        this.maxSize = maxSize;
        if (!(this.maxSize > 0)) {
            throw new IllegalArgumentException("maxSize <= 0".toString());
        }
        this.map = new LruHashMap<>(0, 0.75f);
        this.lock = new Lock();
    }

    public void resize(int maxSize) {
        if (!(maxSize > 0)) {
            throw new IllegalArgumentException("maxSize <= 0".toString());
        }
        Lock $this$synchronized$iv = this.lock;
        synchronized ($this$synchronized$iv) {
            this.maxSize = maxSize;
            Unit unit = Unit.INSTANCE;
        }
        trimToSize(maxSize);
    }

    public final V get(K key) {
        V v;
        Intrinsics.checkNotNullParameter(key, "key");
        synchronized (this.lock) {
            V v2 = this.map.get(key);
            if (v2 != null) {
                this.hitCount++;
                return v2;
            }
            this.missCount++;
            V create = create(key);
            if (create == null) {
                return null;
            }
            synchronized (this.lock) {
                this.createCount++;
                v = (V) this.map.put(key, create);
                if (v != null) {
                    this.map.put(key, v);
                } else {
                    this.size += safeSizeOf(key, create);
                    Unit unit = Unit.INSTANCE;
                }
            }
            if (v != null) {
                entryRemoved(false, key, create, v);
                return v;
            }
            trimToSize(this.maxSize);
            return create;
        }
    }

    public final V put(K key, V value) {
        V put;
        Intrinsics.checkNotNullParameter(key, "key");
        Intrinsics.checkNotNullParameter(value, "value");
        Lock $this$synchronized$iv = this.lock;
        synchronized ($this$synchronized$iv) {
            this.putCount++;
            this.size += safeSizeOf(key, value);
            put = this.map.put(key, value);
            if (put != null) {
                this.size -= safeSizeOf(key, put);
            }
            Unit unit = Unit.INSTANCE;
        }
        if (put != null) {
            entryRemoved(false, key, put, value);
        }
        trimToSize(this.maxSize);
        return put;
    }

    /* JADX WARN: Code restructure failed: missing block: B:29:0x0067, code lost:
    
        return;
     */
    /* JADX WARN: Multi-variable type inference failed */
    /*
        Code decompiled incorrectly, please refer to instructions dump.
        To view partially-correct add '--show-bad-code' argument
    */
    public void trimToSize(int r12) {
        /*
            r11 = this;
        L1:
            r0 = 0
            r1 = 0
            androidx.collection.internal.Lock r2 = r11.lock
            r3 = 0
            r4 = r2
            r5 = 0
            monitor-enter(r4)
            r6 = 0
            int r7 = r11.size     // Catch: java.lang.Throwable -> L76
            r8 = 1
            if (r7 < 0) goto L1f
            androidx.collection.internal.LruHashMap<K, V> r7 = r11.map     // Catch: java.lang.Throwable -> L76
            boolean r7 = r7.isEmpty()     // Catch: java.lang.Throwable -> L76
            if (r7 == 0) goto L1d
            int r7 = r11.size     // Catch: java.lang.Throwable -> L76
            if (r7 != 0) goto L1f
        L1d:
            r7 = r8
            goto L20
        L1f:
            r7 = 0
        L20:
            if (r7 == 0) goto L68
            int r7 = r11.size     // Catch: java.lang.Throwable -> L76
            if (r7 <= r12) goto L65
            androidx.collection.internal.LruHashMap<K, V> r7 = r11.map     // Catch: java.lang.Throwable -> L76
            boolean r7 = r7.isEmpty()     // Catch: java.lang.Throwable -> L76
            if (r7 == 0) goto L2f
            goto L65
        L2f:
            androidx.collection.internal.LruHashMap<K, V> r7 = r11.map     // Catch: java.lang.Throwable -> L76
            java.util.Set r7 = r7.getEntries()     // Catch: java.lang.Throwable -> L76
            java.lang.Iterable r7 = (java.lang.Iterable) r7     // Catch: java.lang.Throwable -> L76
            java.lang.Object r7 = kotlin.collections.CollectionsKt.firstOrNull(r7)     // Catch: java.lang.Throwable -> L76
            java.util.Map$Entry r7 = (java.util.Map.Entry) r7     // Catch: java.lang.Throwable -> L76
            if (r7 != 0) goto L41
            monitor-exit(r4)
            return
        L41:
            java.lang.Object r9 = r7.getKey()     // Catch: java.lang.Throwable -> L76
            r0 = r9
            java.lang.Object r9 = r7.getValue()     // Catch: java.lang.Throwable -> L76
            r1 = r9
            androidx.collection.internal.LruHashMap<K, V> r9 = r11.map     // Catch: java.lang.Throwable -> L76
            r9.remove(r0)     // Catch: java.lang.Throwable -> L76
            int r9 = r11.size     // Catch: java.lang.Throwable -> L76
            int r10 = r11.safeSizeOf(r0, r1)     // Catch: java.lang.Throwable -> L76
            int r9 = r9 - r10
            r11.size = r9     // Catch: java.lang.Throwable -> L76
            int r9 = r11.evictionCount     // Catch: java.lang.Throwable -> L76
            int r9 = r9 + r8
            r11.evictionCount = r9     // Catch: java.lang.Throwable -> L76
            monitor-exit(r4)
            r2 = 0
            r11.entryRemoved(r8, r0, r1, r2)
            goto L1
        L65:
            monitor-exit(r4)
            return
        L68:
            r7 = 0
            java.lang.String r8 = "LruCache.sizeOf() is reporting inconsistent results!"
            java.lang.IllegalStateException r7 = new java.lang.IllegalStateException     // Catch: java.lang.Throwable -> L76
            java.lang.String r8 = r8.toString()     // Catch: java.lang.Throwable -> L76
            r7.<init>(r8)     // Catch: java.lang.Throwable -> L76
            throw r7     // Catch: java.lang.Throwable -> L76
        L76:
            r6 = move-exception
            monitor-exit(r4)
            throw r6
        */
        throw new UnsupportedOperationException("Method not decompiled: androidx.collection.LruCache.trimToSize(int):void");
    }

    public final V remove(K key) {
        V remove;
        Intrinsics.checkNotNullParameter(key, "key");
        Lock $this$synchronized$iv = this.lock;
        synchronized ($this$synchronized$iv) {
            remove = this.map.remove(key);
            if (remove != null) {
                this.size -= safeSizeOf(key, remove);
            }
            Unit unit = Unit.INSTANCE;
        }
        if (remove != null) {
            entryRemoved(false, key, remove, null);
        }
        return remove;
    }

    protected void entryRemoved(boolean evicted, K key, V oldValue, V newValue) {
        Intrinsics.checkNotNullParameter(key, "key");
        Intrinsics.checkNotNullParameter(oldValue, "oldValue");
    }

    protected V create(K key) {
        Intrinsics.checkNotNullParameter(key, "key");
        return null;
    }

    private final int safeSizeOf(K key, V value) {
        int result = sizeOf(key, value);
        if (!(result >= 0)) {
            throw new IllegalStateException(("Negative size: " + key + '=' + value).toString());
        }
        return result;
    }

    protected int sizeOf(K key, V value) {
        Intrinsics.checkNotNullParameter(key, "key");
        Intrinsics.checkNotNullParameter(value, "value");
        return 1;
    }

    public final void evictAll() {
        trimToSize(-1);
    }

    public final int size() {
        int i;
        Lock $this$synchronized$iv = this.lock;
        synchronized ($this$synchronized$iv) {
            i = this.size;
        }
        return i;
    }

    public final int maxSize() {
        int i;
        Lock $this$synchronized$iv = this.lock;
        synchronized ($this$synchronized$iv) {
            i = this.maxSize;
        }
        return i;
    }

    public final int hitCount() {
        int i;
        Lock $this$synchronized$iv = this.lock;
        synchronized ($this$synchronized$iv) {
            i = this.hitCount;
        }
        return i;
    }

    public final int missCount() {
        int i;
        Lock $this$synchronized$iv = this.lock;
        synchronized ($this$synchronized$iv) {
            i = this.missCount;
        }
        return i;
    }

    public final int createCount() {
        int i;
        Lock $this$synchronized$iv = this.lock;
        synchronized ($this$synchronized$iv) {
            i = this.createCount;
        }
        return i;
    }

    public final int putCount() {
        int i;
        Lock $this$synchronized$iv = this.lock;
        synchronized ($this$synchronized$iv) {
            i = this.putCount;
        }
        return i;
    }

    public final int evictionCount() {
        int i;
        Lock $this$synchronized$iv = this.lock;
        synchronized ($this$synchronized$iv) {
            i = this.evictionCount;
        }
        return i;
    }

    /* JADX WARN: Multi-variable type inference failed */
    public final Map<K, V> snapshot() {
        LinkedHashMap copy = new LinkedHashMap();
        Lock $this$synchronized$iv = this.lock;
        synchronized ($this$synchronized$iv) {
            Iterable $this$forEach$iv = this.map.getEntries();
            for (Object element$iv : $this$forEach$iv) {
                Map.Entry entry = (Map.Entry) element$iv;
                Object key = entry.getKey();
                Object value = entry.getValue();
                copy.put(key, value);
            }
            Unit unit = Unit.INSTANCE;
        }
        return copy;
    }

    public String toString() {
        int hitPercent;
        String str;
        Lock $this$synchronized$iv = this.lock;
        synchronized ($this$synchronized$iv) {
            int accesses = this.hitCount + this.missCount;
            if (accesses != 0) {
                hitPercent = (this.hitCount * 100) / accesses;
            } else {
                hitPercent = 0;
            }
            str = "LruCache[maxSize=" + this.maxSize + ",hits=" + this.hitCount + ",misses=" + this.missCount + ",hitRate=" + hitPercent + "%]";
        }
        return str;
    }
}
