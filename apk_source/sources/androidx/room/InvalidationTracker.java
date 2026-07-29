package androidx.room;

import android.content.Context;
import android.content.Intent;
import android.database.Cursor;
import android.database.sqlite.SQLiteException;
import android.util.Log;
import androidx.arch.core.internal.SafeIterableMap;
import androidx.autofill.HintConstants;
import androidx.lifecycle.LiveData;
import androidx.sqlite.db.SimpleSQLiteQuery;
import androidx.sqlite.db.SupportSQLiteDatabase;
import androidx.sqlite.db.SupportSQLiteStatement;
import java.lang.ref.WeakReference;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collection;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.Callable;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.locks.Lock;
import kotlin.Deprecated;
import kotlin.Metadata;
import kotlin.Unit;
import kotlin.collections.CollectionsKt;
import kotlin.collections.MapsKt;
import kotlin.collections.SetsKt;
import kotlin.io.CloseableKt;
import kotlin.jvm.internal.DefaultConstructorMarker;
import kotlin.jvm.internal.Intrinsics;
import kotlin.text.StringsKt;

/* compiled from: InvalidationTracker.kt */
@Metadata(d1 = {"\u0000¬\u0001\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010\u0011\n\u0002\u0010\u000e\n\u0002\b\u0002\n\u0002\u0010$\n\u0000\n\u0002\u0010\"\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0007\n\u0002\u0010\u000b\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0018\u0002\n\u0002\b\u0004\n\u0002\u0010\b\n\u0002\b\b\n\u0002\u0010\u0002\n\u0002\b\u0003\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\b\u0006\n\u0002\u0018\u0002\n\u0002\b\u000f\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\b\u0010\b\u0016\u0018\u0000 e2\u00020\u0001:\u0005efghiB#\b\u0017\u0012\u0006\u0010\u0002\u001a\u00020\u0003\u0012\u0012\u0010\u0004\u001a\n\u0012\u0006\b\u0001\u0012\u00020\u00060\u0005\"\u00020\u0006¢\u0006\u0002\u0010\u0007BV\b\u0007\u0012\u0006\u0010\u0002\u001a\u00020\u0003\u0012\u0012\u0010\b\u001a\u000e\u0012\u0004\u0012\u00020\u0006\u0012\u0004\u0012\u00020\u00060\t\u0012\u001d\u0010\n\u001a\u0019\u0012\u0004\u0012\u00020\u0006\u0012\u000f\u0012\r\u0012\u0004\u0012\u00020\u00060\u000b¢\u0006\u0002\b\f0\t\u0012\u0012\u0010\u0004\u001a\n\u0012\u0006\b\u0001\u0012\u00020\u00060\u0005\"\u00020\u0006¢\u0006\u0002\u0010\rJ\u0010\u00108\u001a\u0002092\u0006\u0010:\u001a\u00020\"H\u0017J\u0010\u0010;\u001a\u0002092\u0006\u0010:\u001a\u00020\"H\u0017J9\u0010<\u001a\b\u0012\u0004\u0012\u0002H>0=\"\u0004\b\u0000\u0010>2\u000e\u0010\u0004\u001a\n\u0012\u0006\b\u0001\u0012\u00020\u00060\u00052\u000e\u0010?\u001a\n\u0012\u0006\u0012\u0004\u0018\u0001H>0@H\u0017¢\u0006\u0002\u0010AJA\u0010<\u001a\b\u0012\u0004\u0012\u0002H>0=\"\u0004\b\u0000\u0010>2\u000e\u0010\u0004\u001a\n\u0012\u0006\b\u0001\u0012\u00020\u00060\u00052\u0006\u0010B\u001a\u00020\u00192\u000e\u0010?\u001a\n\u0012\u0006\u0012\u0004\u0018\u0001H>0@H\u0017¢\u0006\u0002\u0010CJ\r\u0010D\u001a\u00020\u0019H\u0000¢\u0006\u0002\bEJ\u0015\u0010F\u001a\u0002092\u0006\u0010\u0002\u001a\u00020GH\u0000¢\u0006\u0002\bHJ!\u0010I\u001a\u0002092\u0012\u0010J\u001a\n\u0012\u0006\b\u0001\u0012\u00020\u00060\u0005\"\u00020\u0006H\u0007¢\u0006\u0002\u0010KJ\b\u0010L\u001a\u000209H\u0002J\b\u0010M\u001a\u000209H\u0016J\b\u0010N\u001a\u000209H\u0017J\u0010\u0010O\u001a\u0002092\u0006\u0010:\u001a\u00020\"H\u0017J%\u0010P\u001a\n\u0012\u0006\b\u0001\u0012\u00020\u00060\u00052\u000e\u0010Q\u001a\n\u0012\u0006\b\u0001\u0012\u00020\u00060\u0005H\u0002¢\u0006\u0002\u0010RJ\u0015\u0010S\u001a\u0002092\u0006\u0010\u000e\u001a\u00020\u000fH\u0000¢\u0006\u0002\bTJ%\u0010U\u001a\u0002092\u0006\u0010V\u001a\u00020W2\u0006\u0010X\u001a\u00020\u00062\u0006\u0010Y\u001a\u00020ZH\u0000¢\u0006\u0002\b[J\u0018\u0010\\\u001a\u0002092\u0006\u0010]\u001a\u00020G2\u0006\u0010^\u001a\u000200H\u0002J\r\u0010_\u001a\u000209H\u0000¢\u0006\u0002\b`J\u0018\u0010a\u001a\u0002092\u0006\u0010]\u001a\u00020G2\u0006\u0010^\u001a\u000200H\u0002J\r\u0010b\u001a\u000209H\u0000¢\u0006\u0002\bcJ\u0015\u0010b\u001a\u0002092\u0006\u0010\u0002\u001a\u00020GH\u0000¢\u0006\u0002\bcJ%\u0010d\u001a\n\u0012\u0006\b\u0001\u0012\u00020\u00060\u00052\u000e\u0010\u0004\u001a\n\u0012\u0006\b\u0001\u0012\u00020\u00060\u0005H\u0002¢\u0006\u0002\u0010RR\u0010\u0010\u000e\u001a\u0004\u0018\u00010\u000fX\u0082\u000e¢\u0006\u0002\n\u0000R\u001c\u0010\u0010\u001a\u0004\u0018\u00010\u0011X\u0080\u000e¢\u0006\u000e\n\u0000\u001a\u0004\b\u0012\u0010\u0013\"\u0004\b\u0014\u0010\u0015R\u0014\u0010\u0002\u001a\u00020\u0003X\u0080\u0004¢\u0006\b\n\u0000\u001a\u0004\b\u0016\u0010\u0017R\u000e\u0010\u0018\u001a\u00020\u0019X\u0082\u000e¢\u0006\u0002\n\u0000R\u000e\u0010\u001a\u001a\u00020\u001bX\u0082\u0004¢\u0006\u0002\n\u0000R\u0010\u0010\u001c\u001a\u0004\u0018\u00010\u001dX\u0082\u000e¢\u0006\u0002\n\u0000R\u000e\u0010\u001e\u001a\u00020\u001fX\u0082\u0004¢\u0006\u0002\n\u0000R\"\u0010 \u001a\u000e\u0012\u0004\u0012\u00020\"\u0012\u0004\u0012\u00020#0!8\u0000X\u0081\u0004¢\u0006\b\n\u0000\u001a\u0004\b$\u0010%R\u0016\u0010&\u001a\u00020'8GX\u0087\u0004¢\u0006\b\n\u0000\u001a\u0004\b(\u0010)R\u0016\u0010*\u001a\u00020+8\u0006X\u0087\u0004¢\u0006\b\n\u0000\u0012\u0004\b,\u0010-R\u001a\u0010\b\u001a\u000e\u0012\u0004\u0012\u00020\u0006\u0012\u0004\u0012\u00020\u00060\tX\u0082\u0004¢\u0006\u0002\n\u0000R\u000e\u0010.\u001a\u00020\u0001X\u0082\u0004¢\u0006\u0002\n\u0000R \u0010/\u001a\u000e\u0012\u0004\u0012\u00020\u0006\u0012\u0004\u0012\u0002000\tX\u0080\u0004¢\u0006\b\n\u0000\u001a\u0004\b1\u00102R\u001e\u00103\u001a\n\u0012\u0006\b\u0001\u0012\u00020\u00060\u0005X\u0080\u0004¢\u0006\n\n\u0002\u00106\u001a\u0004\b4\u00105R\u000e\u00107\u001a\u00020\u0001X\u0082\u0004¢\u0006\u0002\n\u0000R%\u0010\n\u001a\u0019\u0012\u0004\u0012\u00020\u0006\u0012\u000f\u0012\r\u0012\u0004\u0012\u00020\u00060\u000b¢\u0006\u0002\b\f0\tX\u0082\u0004¢\u0006\u0002\n\u0000¨\u0006j"}, d2 = {"Landroidx/room/InvalidationTracker;", "", "database", "Landroidx/room/RoomDatabase;", "tableNames", "", "", "(Landroidx/room/RoomDatabase;[Ljava/lang/String;)V", "shadowTablesMap", "", "viewTables", "", "Lkotlin/jvm/JvmSuppressWildcards;", "(Landroidx/room/RoomDatabase;Ljava/util/Map;Ljava/util/Map;[Ljava/lang/String;)V", "autoCloser", "Landroidx/room/AutoCloser;", "cleanupStatement", "Landroidx/sqlite/db/SupportSQLiteStatement;", "getCleanupStatement$room_runtime_release", "()Landroidx/sqlite/db/SupportSQLiteStatement;", "setCleanupStatement$room_runtime_release", "(Landroidx/sqlite/db/SupportSQLiteStatement;)V", "getDatabase$room_runtime_release", "()Landroidx/room/RoomDatabase;", "initialized", "", "invalidationLiveDataContainer", "Landroidx/room/InvalidationLiveDataContainer;", "multiInstanceInvalidationClient", "Landroidx/room/MultiInstanceInvalidationClient;", "observedTableTracker", "Landroidx/room/InvalidationTracker$ObservedTableTracker;", "observerMap", "Landroidx/arch/core/internal/SafeIterableMap;", "Landroidx/room/InvalidationTracker$Observer;", "Landroidx/room/InvalidationTracker$ObserverWrapper;", "getObserverMap$room_runtime_release", "()Landroidx/arch/core/internal/SafeIterableMap;", "pendingRefresh", "Ljava/util/concurrent/atomic/AtomicBoolean;", "getPendingRefresh", "()Ljava/util/concurrent/atomic/AtomicBoolean;", "refreshRunnable", "Ljava/lang/Runnable;", "getRefreshRunnable$annotations", "()V", "syncTriggersLock", "tableIdLookup", "", "getTableIdLookup$room_runtime_release", "()Ljava/util/Map;", "tablesNames", "getTablesNames$room_runtime_release", "()[Ljava/lang/String;", "[Ljava/lang/String;", "trackerLock", "addObserver", "", "observer", "addWeakObserver", "createLiveData", "Landroidx/lifecycle/LiveData;", "T", "computeFunction", "Ljava/util/concurrent/Callable;", "([Ljava/lang/String;Ljava/util/concurrent/Callable;)Landroidx/lifecycle/LiveData;", "inTransaction", "([Ljava/lang/String;ZLjava/util/concurrent/Callable;)Landroidx/lifecycle/LiveData;", "ensureInitialization", "ensureInitialization$room_runtime_release", "internalInit", "Landroidx/sqlite/db/SupportSQLiteDatabase;", "internalInit$room_runtime_release", "notifyObserversByTableNames", "tables", "([Ljava/lang/String;)V", "onAutoCloseCallback", "refreshVersionsAsync", "refreshVersionsSync", "removeObserver", "resolveViews", "names", "([Ljava/lang/String;)[Ljava/lang/String;", "setAutoCloser", "setAutoCloser$room_runtime_release", "startMultiInstanceInvalidation", "context", "Landroid/content/Context;", HintConstants.AUTOFILL_HINT_NAME, "serviceIntent", "Landroid/content/Intent;", "startMultiInstanceInvalidation$room_runtime_release", "startTrackingTable", "db", "tableId", "stopMultiInstanceInvalidation", "stopMultiInstanceInvalidation$room_runtime_release", "stopTrackingTable", "syncTriggers", "syncTriggers$room_runtime_release", "validateAndResolveTableNames", "Companion", "ObservedTableTracker", "Observer", "ObserverWrapper", "WeakObserver", "room-runtime_release"}, k = 1, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes11.dex */
public class InvalidationTracker {
    private static final String CREATE_TRACKING_TABLE_SQL = "CREATE TEMP TABLE room_table_modification_log (table_id INTEGER PRIMARY KEY, invalidated INTEGER NOT NULL DEFAULT 0)";
    private static final String INVALIDATED_COLUMN_NAME = "invalidated";
    public static final String RESET_UPDATED_TABLES_SQL = "UPDATE room_table_modification_log SET invalidated = 0 WHERE invalidated = 1";
    public static final String SELECT_UPDATED_TABLES_SQL = "SELECT * FROM room_table_modification_log WHERE invalidated = 1;";
    private static final String TABLE_ID_COLUMN_NAME = "table_id";
    private static final String UPDATE_TABLE_NAME = "room_table_modification_log";
    private AutoCloser autoCloser;
    private volatile SupportSQLiteStatement cleanupStatement;
    private final RoomDatabase database;
    private volatile boolean initialized;
    private final InvalidationLiveDataContainer invalidationLiveDataContainer;
    private MultiInstanceInvalidationClient multiInstanceInvalidationClient;
    private final ObservedTableTracker observedTableTracker;
    private final SafeIterableMap<Observer, ObserverWrapper> observerMap;
    private final AtomicBoolean pendingRefresh;
    public final Runnable refreshRunnable;
    private final Map<String, String> shadowTablesMap;
    private final Object syncTriggersLock;
    private final Map<String, Integer> tableIdLookup;
    private final String[] tablesNames;
    private final Object trackerLock;
    private final Map<String, Set<String>> viewTables;

    /* renamed from: Companion, reason: from kotlin metadata */
    public static final Companion INSTANCE = new Companion(null);
    private static final String[] TRIGGERS = {"UPDATE", "DELETE", "INSERT"};

    public static /* synthetic */ void getRefreshRunnable$annotations() {
    }

    /* JADX WARN: Multi-variable type inference failed */
    public InvalidationTracker(RoomDatabase database, Map<String, String> shadowTablesMap, Map<String, Set<String>> viewTables, String... tableNames) {
        String str;
        Intrinsics.checkNotNullParameter(database, "database");
        Intrinsics.checkNotNullParameter(shadowTablesMap, "shadowTablesMap");
        Intrinsics.checkNotNullParameter(viewTables, "viewTables");
        Intrinsics.checkNotNullParameter(tableNames, "tableNames");
        this.database = database;
        this.shadowTablesMap = shadowTablesMap;
        this.viewTables = viewTables;
        this.pendingRefresh = new AtomicBoolean(false);
        this.observedTableTracker = new ObservedTableTracker(tableNames.length);
        this.invalidationLiveDataContainer = new InvalidationLiveDataContainer(this.database);
        this.observerMap = new SafeIterableMap<>();
        this.syncTriggersLock = new Object();
        this.trackerLock = new Object();
        this.tableIdLookup = new LinkedHashMap();
        int length = tableNames.length;
        String[] strArr = new String[length];
        for (int i = 0; i < length; i++) {
            String str2 = tableNames[i];
            Locale US = Locale.US;
            Intrinsics.checkNotNullExpressionValue(US, "US");
            String tableName = str2.toLowerCase(US);
            Intrinsics.checkNotNullExpressionValue(tableName, "this as java.lang.String).toLowerCase(locale)");
            this.tableIdLookup.put(tableName, Integer.valueOf(i));
            String str3 = this.shadowTablesMap.get(tableNames[i]);
            if (str3 != null) {
                Locale US2 = Locale.US;
                Intrinsics.checkNotNullExpressionValue(US2, "US");
                str = str3.toLowerCase(US2);
                Intrinsics.checkNotNullExpressionValue(str, "this as java.lang.String).toLowerCase(locale)");
            } else {
                str = null;
            }
            String shadowTableName = str;
            if (shadowTableName != null) {
                tableName = shadowTableName;
            }
            strArr[i] = tableName;
        }
        this.tablesNames = strArr;
        Map $this$forEach$iv = this.shadowTablesMap;
        for (Map.Entry element$iv : $this$forEach$iv.entrySet()) {
            String value = element$iv.getValue();
            Locale US3 = Locale.US;
            Intrinsics.checkNotNullExpressionValue(US3, "US");
            String shadowTableName2 = value.toLowerCase(US3);
            Intrinsics.checkNotNullExpressionValue(shadowTableName2, "this as java.lang.String).toLowerCase(locale)");
            if (this.tableIdLookup.containsKey(shadowTableName2)) {
                String key = element$iv.getKey();
                Locale US4 = Locale.US;
                Intrinsics.checkNotNullExpressionValue(US4, "US");
                String tableName2 = key.toLowerCase(US4);
                Intrinsics.checkNotNullExpressionValue(tableName2, "this as java.lang.String).toLowerCase(locale)");
                this.tableIdLookup.put(tableName2, MapsKt.getValue(this.tableIdLookup, shadowTableName2));
            }
        }
        this.refreshRunnable = new Runnable() { // from class: androidx.room.InvalidationTracker$refreshRunnable$1
            /* JADX WARN: Code restructure failed: missing block: B:31:0x0089, code lost:
            
                if (r1 != null) goto L42;
             */
            /* JADX WARN: Code restructure failed: missing block: B:32:0x00cc, code lost:
            
                r1 = r2;
             */
            /* JADX WARN: Code restructure failed: missing block: B:33:0x00d6, code lost:
            
                if (r1.isEmpty() != false) goto L58;
             */
            /* JADX WARN: Code restructure failed: missing block: B:34:0x00d8, code lost:
            
                r2 = r11.this$0.getObserverMap$room_runtime_release();
                r3 = r11.this$0;
             */
            /* JADX WARN: Code restructure failed: missing block: B:35:0x00e0, code lost:
            
                monitor-enter(r2);
             */
            /* JADX WARN: Code restructure failed: missing block: B:38:0x00e2, code lost:
            
                r3 = r3.getObserverMap$room_runtime_release();
                r6 = r3.iterator();
             */
            /* JADX WARN: Code restructure failed: missing block: B:40:0x00f1, code lost:
            
                if (r6.hasNext() == false) goto L68;
             */
            /* JADX WARN: Code restructure failed: missing block: B:41:0x00f3, code lost:
            
                r7 = r6.next();
                r8 = (java.util.Map.Entry) r7;
                ((androidx.room.InvalidationTracker.ObserverWrapper) r8.getValue()).notifyByTableInvalidStatus$room_runtime_release(r1);
             */
            /* JADX WARN: Code restructure failed: missing block: B:43:0x0107, code lost:
            
                r3 = kotlin.Unit.INSTANCE;
             */
            /* JADX WARN: Code restructure failed: missing block: B:44:0x010b, code lost:
            
                monitor-exit(r2);
             */
            /* JADX WARN: Code restructure failed: missing block: B:45:?, code lost:
            
                return;
             */
            /* JADX WARN: Code restructure failed: missing block: B:49:0x0110, code lost:
            
                return;
             */
            /* JADX WARN: Code restructure failed: missing block: B:50:0x00c9, code lost:
            
                r1.decrementCountAndScheduleClose();
             */
            /* JADX WARN: Code restructure failed: missing block: B:63:0x00ac, code lost:
            
                if (r1 == null) goto L43;
             */
            /* JADX WARN: Code restructure failed: missing block: B:67:0x00c7, code lost:
            
                if (r1 == null) goto L43;
             */
            @Override // java.lang.Runnable
            /*
                Code decompiled incorrectly, please refer to instructions dump.
                To view partially-correct add '--show-bad-code' argument
            */
            public void run() {
                /*
                    Method dump skipped, instructions count: 288
                    To view this dump add '--comments-level debug' option
                */
                throw new UnsupportedOperationException("Method not decompiled: androidx.room.InvalidationTracker$refreshRunnable$1.run():void");
            }

            private final Set<Integer> checkUpdatedTable() {
                InvalidationTracker invalidationTracker = InvalidationTracker.this;
                Set $this$checkUpdatedTable_u24lambda_u243 = SetsKt.createSetBuilder();
                Cursor $this$useCursor$iv = RoomDatabase.query$default(invalidationTracker.getDatabase(), new SimpleSQLiteQuery(InvalidationTracker.SELECT_UPDATED_TABLES_SQL), null, 2, null);
                Cursor cursor = $this$useCursor$iv;
                try {
                    Cursor cursor2 = cursor;
                    while (cursor2.moveToNext()) {
                        $this$checkUpdatedTable_u24lambda_u243.add(Integer.valueOf(cursor2.getInt(0)));
                    }
                    Unit unit = Unit.INSTANCE;
                    CloseableKt.closeFinally(cursor, null);
                    Set invalidatedTableIds = SetsKt.build($this$checkUpdatedTable_u24lambda_u243);
                    if (!invalidatedTableIds.isEmpty()) {
                        if (InvalidationTracker.this.getCleanupStatement() == null) {
                            throw new IllegalStateException("Required value was null.".toString());
                        }
                        SupportSQLiteStatement statement = InvalidationTracker.this.getCleanupStatement();
                        if (statement == null) {
                            throw new IllegalArgumentException("Required value was null.".toString());
                        }
                        statement.executeUpdateDelete();
                    }
                    return invalidatedTableIds;
                } finally {
                }
            }
        };
    }

    /* renamed from: getDatabase$room_runtime_release, reason: from getter */
    public final RoomDatabase getDatabase() {
        return this.database;
    }

    public final Map<String, Integer> getTableIdLookup$room_runtime_release() {
        return this.tableIdLookup;
    }

    /* renamed from: getTablesNames$room_runtime_release, reason: from getter */
    public final String[] getTablesNames() {
        return this.tablesNames;
    }

    public final AtomicBoolean getPendingRefresh() {
        return this.pendingRefresh;
    }

    /* renamed from: getCleanupStatement$room_runtime_release, reason: from getter */
    public final SupportSQLiteStatement getCleanupStatement() {
        return this.cleanupStatement;
    }

    public final void setCleanupStatement$room_runtime_release(SupportSQLiteStatement supportSQLiteStatement) {
        this.cleanupStatement = supportSQLiteStatement;
    }

    public final SafeIterableMap<Observer, ObserverWrapper> getObserverMap$room_runtime_release() {
        return this.observerMap;
    }

    /* JADX WARN: 'this' call moved to the top of the method (can break code semantics) */
    public InvalidationTracker(RoomDatabase database, String... tableNames) {
        this(database, MapsKt.emptyMap(), MapsKt.emptyMap(), (String[]) Arrays.copyOf(tableNames, tableNames.length));
        Intrinsics.checkNotNullParameter(database, "database");
        Intrinsics.checkNotNullParameter(tableNames, "tableNames");
    }

    public final void setAutoCloser$room_runtime_release(AutoCloser autoCloser) {
        Intrinsics.checkNotNullParameter(autoCloser, "autoCloser");
        this.autoCloser = autoCloser;
        autoCloser.setAutoCloseCallback(new Runnable() { // from class: androidx.room.InvalidationTracker$$ExternalSyntheticLambda0
            @Override // java.lang.Runnable
            public final void run() {
                InvalidationTracker.this.onAutoCloseCallback();
            }
        });
    }

    public final void internalInit$room_runtime_release(SupportSQLiteDatabase database) {
        Intrinsics.checkNotNullParameter(database, "database");
        synchronized (this.trackerLock) {
            if (this.initialized) {
                Log.e(Room.LOG_TAG, "Invalidation tracker is initialized twice :/.");
                return;
            }
            database.execSQL("PRAGMA temp_store = MEMORY;");
            database.execSQL("PRAGMA recursive_triggers='ON';");
            database.execSQL(CREATE_TRACKING_TABLE_SQL);
            syncTriggers$room_runtime_release(database);
            this.cleanupStatement = database.compileStatement(RESET_UPDATED_TABLES_SQL);
            this.initialized = true;
            Unit unit = Unit.INSTANCE;
        }
    }

    /* JADX INFO: Access modifiers changed from: private */
    public final void onAutoCloseCallback() {
        synchronized (this.trackerLock) {
            this.initialized = false;
            this.observedTableTracker.resetTriggerState();
            SupportSQLiteStatement supportSQLiteStatement = this.cleanupStatement;
            if (supportSQLiteStatement != null) {
                supportSQLiteStatement.close();
                Unit unit = Unit.INSTANCE;
            }
        }
    }

    public final void startMultiInstanceInvalidation$room_runtime_release(Context context, String name, Intent serviceIntent) {
        Intrinsics.checkNotNullParameter(context, "context");
        Intrinsics.checkNotNullParameter(name, "name");
        Intrinsics.checkNotNullParameter(serviceIntent, "serviceIntent");
        this.multiInstanceInvalidationClient = new MultiInstanceInvalidationClient(context, name, serviceIntent, this, this.database.getQueryExecutor());
    }

    public final void stopMultiInstanceInvalidation$room_runtime_release() {
        MultiInstanceInvalidationClient multiInstanceInvalidationClient = this.multiInstanceInvalidationClient;
        if (multiInstanceInvalidationClient != null) {
            multiInstanceInvalidationClient.stop();
        }
        this.multiInstanceInvalidationClient = null;
    }

    private final void stopTrackingTable(SupportSQLiteDatabase db, int tableId) {
        String tableName = this.tablesNames[tableId];
        for (String trigger : TRIGGERS) {
            StringBuilder $this$stopTrackingTable_u24lambda_u243 = new StringBuilder();
            $this$stopTrackingTable_u24lambda_u243.append("DROP TRIGGER IF EXISTS ");
            $this$stopTrackingTable_u24lambda_u243.append(INSTANCE.getTriggerName$room_runtime_release(tableName, trigger));
            String sql = $this$stopTrackingTable_u24lambda_u243.toString();
            Intrinsics.checkNotNullExpressionValue(sql, "StringBuilder().apply(builderAction).toString()");
            db.execSQL(sql);
        }
    }

    private final void startTrackingTable(SupportSQLiteDatabase db, int tableId) {
        db.execSQL("INSERT OR IGNORE INTO room_table_modification_log VALUES(" + tableId + ", 0)");
        String tableName = this.tablesNames[tableId];
        for (String trigger : TRIGGERS) {
            StringBuilder $this$startTrackingTable_u24lambda_u244 = new StringBuilder();
            $this$startTrackingTable_u24lambda_u244.append("CREATE TEMP TRIGGER IF NOT EXISTS ");
            $this$startTrackingTable_u24lambda_u244.append(INSTANCE.getTriggerName$room_runtime_release(tableName, trigger));
            $this$startTrackingTable_u24lambda_u244.append(" AFTER ");
            $this$startTrackingTable_u24lambda_u244.append(trigger);
            $this$startTrackingTable_u24lambda_u244.append(" ON `");
            $this$startTrackingTable_u24lambda_u244.append(tableName);
            $this$startTrackingTable_u24lambda_u244.append("` BEGIN UPDATE ");
            $this$startTrackingTable_u24lambda_u244.append(UPDATE_TABLE_NAME);
            $this$startTrackingTable_u24lambda_u244.append(" SET ").append(INVALIDATED_COLUMN_NAME);
            $this$startTrackingTable_u24lambda_u244.append(" = 1");
            $this$startTrackingTable_u24lambda_u244.append(" WHERE ").append(TABLE_ID_COLUMN_NAME);
            $this$startTrackingTable_u24lambda_u244.append(" = ").append(tableId);
            $this$startTrackingTable_u24lambda_u244.append(" AND ").append(INVALIDATED_COLUMN_NAME);
            $this$startTrackingTable_u24lambda_u244.append(" = 0");
            $this$startTrackingTable_u24lambda_u244.append("; END");
            String sql = $this$startTrackingTable_u24lambda_u244.toString();
            Intrinsics.checkNotNullExpressionValue(sql, "StringBuilder().apply(builderAction).toString()");
            db.execSQL(sql);
        }
    }

    public void addObserver(Observer observer) {
        ObserverWrapper currentObserver;
        Intrinsics.checkNotNullParameter(observer, "observer");
        String[] tableNames = resolveViews(observer.getTables());
        Collection destination$iv$iv = new ArrayList(tableNames.length);
        for (String str : tableNames) {
            Map<String, Integer> map = this.tableIdLookup;
            Locale US = Locale.US;
            Intrinsics.checkNotNullExpressionValue(US, "US");
            String lowerCase = str.toLowerCase(US);
            Intrinsics.checkNotNullExpressionValue(lowerCase, "this as java.lang.String).toLowerCase(locale)");
            Integer num = map.get(lowerCase);
            if (num == null) {
                throw new IllegalArgumentException("There is no table with name " + str);
            }
            destination$iv$iv.add(Integer.valueOf(num.intValue()));
        }
        int[] tableIds = CollectionsKt.toIntArray((List) destination$iv$iv);
        ObserverWrapper wrapper = new ObserverWrapper(observer, tableIds, tableNames);
        synchronized (this.observerMap) {
            currentObserver = this.observerMap.putIfAbsent(observer, wrapper);
        }
        if (currentObserver == null && this.observedTableTracker.onAdded(Arrays.copyOf(tableIds, tableIds.length))) {
            syncTriggers$room_runtime_release();
        }
    }

    private final String[] validateAndResolveTableNames(String[] tableNames) {
        String[] resolved = resolveViews(tableNames);
        for (String str : resolved) {
            Map<String, Integer> map = this.tableIdLookup;
            Locale US = Locale.US;
            Intrinsics.checkNotNullExpressionValue(US, "US");
            String lowerCase = str.toLowerCase(US);
            Intrinsics.checkNotNullExpressionValue(lowerCase, "this as java.lang.String).toLowerCase(locale)");
            if (!map.containsKey(lowerCase)) {
                throw new IllegalArgumentException(("There is no table with name " + str).toString());
            }
        }
        return resolved;
    }

    private final String[] resolveViews(String[] names) {
        Set $this$resolveViews_u24lambda_u2410 = SetsKt.createSetBuilder();
        for (String str : names) {
            Map<String, Set<String>> map = this.viewTables;
            Locale US = Locale.US;
            Intrinsics.checkNotNullExpressionValue(US, "US");
            String lowerCase = str.toLowerCase(US);
            Intrinsics.checkNotNullExpressionValue(lowerCase, "this as java.lang.String).toLowerCase(locale)");
            if (map.containsKey(lowerCase)) {
                Map<String, Set<String>> map2 = this.viewTables;
                Locale US2 = Locale.US;
                Intrinsics.checkNotNullExpressionValue(US2, "US");
                String lowerCase2 = str.toLowerCase(US2);
                Intrinsics.checkNotNullExpressionValue(lowerCase2, "this as java.lang.String).toLowerCase(locale)");
                Set<String> set = map2.get(lowerCase2);
                Intrinsics.checkNotNull(set);
                $this$resolveViews_u24lambda_u2410.addAll(set);
            } else {
                $this$resolveViews_u24lambda_u2410.add(str);
            }
        }
        Collection $this$toTypedArray$iv = SetsKt.build($this$resolveViews_u24lambda_u2410);
        return (String[]) $this$toTypedArray$iv.toArray(new String[0]);
    }

    public void addWeakObserver(Observer observer) {
        Intrinsics.checkNotNullParameter(observer, "observer");
        addObserver(new WeakObserver(this, observer));
    }

    public void removeObserver(Observer observer) {
        ObserverWrapper wrapper;
        Intrinsics.checkNotNullParameter(observer, "observer");
        synchronized (this.observerMap) {
            wrapper = this.observerMap.remove(observer);
        }
        if (wrapper != null) {
            ObservedTableTracker observedTableTracker = this.observedTableTracker;
            int[] tableIds = wrapper.getTableIds();
            if (observedTableTracker.onRemoved(Arrays.copyOf(tableIds, tableIds.length))) {
                syncTriggers$room_runtime_release();
            }
        }
    }

    public final boolean ensureInitialization$room_runtime_release() {
        if (!this.database.isOpenInternal()) {
            return false;
        }
        if (!this.initialized) {
            this.database.getOpenHelper().getWritableDatabase();
        }
        if (!this.initialized) {
            Log.e(Room.LOG_TAG, "database is not initialized even though it is open");
            return false;
        }
        return true;
    }

    public void refreshVersionsAsync() {
        if (this.pendingRefresh.compareAndSet(false, true)) {
            AutoCloser autoCloser = this.autoCloser;
            if (autoCloser != null) {
                autoCloser.incrementCountAndEnsureDbIsOpen();
            }
            this.database.getQueryExecutor().execute(this.refreshRunnable);
        }
    }

    public void refreshVersionsSync() {
        AutoCloser autoCloser = this.autoCloser;
        if (autoCloser != null) {
            autoCloser.incrementCountAndEnsureDbIsOpen();
        }
        syncTriggers$room_runtime_release();
        this.refreshRunnable.run();
    }

    public final void notifyObserversByTableNames(String... tables) {
        Intrinsics.checkNotNullParameter(tables, "tables");
        synchronized (this.observerMap) {
            Iterable $this$forEach$iv = this.observerMap;
            for (Object element$iv : $this$forEach$iv) {
                Map.Entry entry = (Map.Entry) element$iv;
                Intrinsics.checkNotNullExpressionValue(entry, "(observer, wrapper)");
                Observer observer = (Observer) entry.getKey();
                ObserverWrapper wrapper = (ObserverWrapper) entry.getValue();
                if (!observer.isRemote$room_runtime_release()) {
                    wrapper.notifyByTableNames$room_runtime_release(tables);
                }
            }
            Unit unit = Unit.INSTANCE;
        }
    }

    public final void syncTriggers$room_runtime_release(SupportSQLiteDatabase database) {
        Intrinsics.checkNotNullParameter(database, "database");
        if (database.inTransaction()) {
            return;
        }
        try {
            Lock closeLock = this.database.getCloseLock$room_runtime_release();
            closeLock.lock();
            try {
                synchronized (this.syncTriggersLock) {
                    int[] tablesToSync = this.observedTableTracker.getTablesToSync();
                    if (tablesToSync == null) {
                        return;
                    }
                    INSTANCE.beginTransactionInternal$room_runtime_release(database);
                    int index$iv = 0;
                    try {
                        int length = tablesToSync.length;
                        int i = 0;
                        while (i < length) {
                            int item$iv = tablesToSync[i];
                            int index$iv2 = index$iv + 1;
                            switch (item$iv) {
                                case 1:
                                    startTrackingTable(database, index$iv);
                                    break;
                                case 2:
                                    stopTrackingTable(database, index$iv);
                                    break;
                            }
                            i++;
                            index$iv = index$iv2;
                        }
                        database.setTransactionSuccessful();
                        database.endTransaction();
                        Unit unit = Unit.INSTANCE;
                    } catch (Throwable th) {
                        database.endTransaction();
                        throw th;
                    }
                }
            } finally {
                closeLock.unlock();
            }
        } catch (SQLiteException ex) {
            Log.e(Room.LOG_TAG, "Cannot run invalidation tracker. Is the db closed?", ex);
        } catch (IllegalStateException ex2) {
            Log.e(Room.LOG_TAG, "Cannot run invalidation tracker. Is the db closed?", ex2);
        }
    }

    public final void syncTriggers$room_runtime_release() {
        if (!this.database.isOpenInternal()) {
            return;
        }
        syncTriggers$room_runtime_release(this.database.getOpenHelper().getWritableDatabase());
    }

    @Deprecated(message = "Use [createLiveData(String[], boolean, Callable)]")
    public <T> LiveData<T> createLiveData(String[] tableNames, Callable<T> computeFunction) {
        Intrinsics.checkNotNullParameter(tableNames, "tableNames");
        Intrinsics.checkNotNullParameter(computeFunction, "computeFunction");
        return createLiveData(tableNames, false, computeFunction);
    }

    public <T> LiveData<T> createLiveData(String[] tableNames, boolean inTransaction, Callable<T> computeFunction) {
        Intrinsics.checkNotNullParameter(tableNames, "tableNames");
        Intrinsics.checkNotNullParameter(computeFunction, "computeFunction");
        return this.invalidationLiveDataContainer.create(validateAndResolveTableNames(tableNames), inTransaction, computeFunction);
    }

    /* compiled from: InvalidationTracker.kt */
    @Metadata(d1 = {"\u00008\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010\u0015\n\u0000\n\u0002\u0010\u0011\n\u0002\u0010\u000e\n\u0002\b\u0004\n\u0002\u0010\"\n\u0002\b\u0004\n\u0002\u0010\u0002\n\u0000\n\u0002\u0010\b\n\u0002\b\u0006\b\u0000\u0018\u00002\u00020\u0001B%\u0012\u0006\u0010\u0002\u001a\u00020\u0003\u0012\u0006\u0010\u0004\u001a\u00020\u0005\u0012\u000e\u0010\u0006\u001a\n\u0012\u0006\b\u0001\u0012\u00020\b0\u0007¢\u0006\u0002\u0010\tJ\u001d\u0010\u0011\u001a\u00020\u00122\u000e\u0010\u0013\u001a\n\u0012\u0006\u0012\u0004\u0018\u00010\u00140\rH\u0000¢\u0006\u0002\b\u0015J\u001f\u0010\u0016\u001a\u00020\u00122\u000e\u0010\u0017\u001a\n\u0012\u0006\b\u0001\u0012\u00020\b0\u0007H\u0000¢\u0006\u0004\b\u0018\u0010\u0019R\u0014\u0010\u0002\u001a\u00020\u0003X\u0080\u0004¢\u0006\b\n\u0000\u001a\u0004\b\n\u0010\u000bR\u0014\u0010\f\u001a\b\u0012\u0004\u0012\u00020\b0\rX\u0082\u0004¢\u0006\u0002\n\u0000R\u0014\u0010\u0004\u001a\u00020\u0005X\u0080\u0004¢\u0006\b\n\u0000\u001a\u0004\b\u000e\u0010\u000fR\u0018\u0010\u0006\u001a\n\u0012\u0006\b\u0001\u0012\u00020\b0\u0007X\u0082\u0004¢\u0006\u0004\n\u0002\u0010\u0010¨\u0006\u001a"}, d2 = {"Landroidx/room/InvalidationTracker$ObserverWrapper;", "", "observer", "Landroidx/room/InvalidationTracker$Observer;", "tableIds", "", "tableNames", "", "", "(Landroidx/room/InvalidationTracker$Observer;[I[Ljava/lang/String;)V", "getObserver$room_runtime_release", "()Landroidx/room/InvalidationTracker$Observer;", "singleTableSet", "", "getTableIds$room_runtime_release", "()[I", "[Ljava/lang/String;", "notifyByTableInvalidStatus", "", "invalidatedTablesIds", "", "notifyByTableInvalidStatus$room_runtime_release", "notifyByTableNames", "tables", "notifyByTableNames$room_runtime_release", "([Ljava/lang/String;)V", "room-runtime_release"}, k = 1, mv = {1, 8, 0}, xi = 48)
    public static final class ObserverWrapper {
        private final Observer observer;
        private final Set<String> singleTableSet;
        private final int[] tableIds;
        private final String[] tableNames;

        public ObserverWrapper(Observer observer, int[] tableIds, String[] tableNames) {
            Set<String> emptySet;
            Intrinsics.checkNotNullParameter(observer, "observer");
            Intrinsics.checkNotNullParameter(tableIds, "tableIds");
            Intrinsics.checkNotNullParameter(tableNames, "tableNames");
            this.observer = observer;
            this.tableIds = tableIds;
            this.tableNames = tableNames;
            if (!(this.tableNames.length == 0)) {
                emptySet = SetsKt.setOf(this.tableNames[0]);
            } else {
                emptySet = SetsKt.emptySet();
            }
            this.singleTableSet = emptySet;
            if (this.tableIds.length == this.tableNames.length) {
            } else {
                throw new IllegalStateException("Check failed.".toString());
            }
        }

        /* renamed from: getObserver$room_runtime_release, reason: from getter */
        public final Observer getObserver() {
            return this.observer;
        }

        /* renamed from: getTableIds$room_runtime_release, reason: from getter */
        public final int[] getTableIds() {
            return this.tableIds;
        }

        public final void notifyByTableInvalidStatus$room_runtime_release(Set<Integer> invalidatedTablesIds) {
            Set invalidatedTables;
            Intrinsics.checkNotNullParameter(invalidatedTablesIds, "invalidatedTablesIds");
            int i = 0;
            switch (this.tableIds.length) {
                case 0:
                    invalidatedTables = SetsKt.emptySet();
                    break;
                case 1:
                    if (invalidatedTablesIds.contains(Integer.valueOf(this.tableIds[0]))) {
                        invalidatedTables = this.singleTableSet;
                        break;
                    } else {
                        invalidatedTables = SetsKt.emptySet();
                        break;
                    }
                default:
                    Set $this$notifyByTableInvalidStatus_u24lambda_u241 = SetsKt.createSetBuilder();
                    int[] $this$forEachIndexed$iv = this.tableIds;
                    int index$iv = 0;
                    int length = $this$forEachIndexed$iv.length;
                    while (i < length) {
                        int item$iv = $this$forEachIndexed$iv[i];
                        int index$iv2 = index$iv + 1;
                        if (invalidatedTablesIds.contains(Integer.valueOf(item$iv))) {
                            $this$notifyByTableInvalidStatus_u24lambda_u241.add(this.tableNames[index$iv]);
                        }
                        i++;
                        index$iv = index$iv2;
                    }
                    invalidatedTables = SetsKt.build($this$notifyByTableInvalidStatus_u24lambda_u241);
                    break;
            }
            if (!invalidatedTables.isEmpty()) {
                this.observer.onInvalidated(invalidatedTables);
            }
        }

        public final void notifyByTableNames$room_runtime_release(String[] tables) {
            Set invalidatedTables;
            Intrinsics.checkNotNullParameter(tables, "tables");
            boolean z = false;
            switch (this.tableNames.length) {
                case 0:
                    invalidatedTables = SetsKt.emptySet();
                    break;
                case 1:
                    int length = tables.length;
                    int i = 0;
                    while (true) {
                        if (i < length) {
                            if (StringsKt.equals(tables[i], this.tableNames[0], true)) {
                                z = true;
                            } else {
                                i++;
                            }
                        }
                    }
                    if (z) {
                        invalidatedTables = this.singleTableSet;
                        break;
                    } else {
                        invalidatedTables = SetsKt.emptySet();
                        break;
                    }
                default:
                    Set $this$notifyByTableNames_u24lambda_u245 = SetsKt.createSetBuilder();
                    for (String str : tables) {
                        String[] strArr = this.tableNames;
                        int length2 = strArr.length;
                        int i2 = 0;
                        while (i2 < length2) {
                            String str2 = strArr[i2];
                            int i3 = length2;
                            if (StringsKt.equals(str2, str, true)) {
                                $this$notifyByTableNames_u24lambda_u245.add(str2);
                            }
                            i2++;
                            length2 = i3;
                        }
                    }
                    invalidatedTables = SetsKt.build($this$notifyByTableNames_u24lambda_u245);
                    break;
            }
            if (!invalidatedTables.isEmpty()) {
                this.observer.onInvalidated(invalidatedTables);
            }
        }
    }

    /* compiled from: InvalidationTracker.kt */
    @Metadata(d1 = {"\u0000*\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0000\n\u0002\u0010\u000e\n\u0000\n\u0002\u0010\u0011\n\u0002\b\u0004\n\u0002\u0010\u000b\n\u0002\b\u0006\n\u0002\u0010\u0002\n\u0002\u0010\"\n\u0000\b&\u0018\u00002\u00020\u0001B#\b\u0014\u0012\u0006\u0010\u0002\u001a\u00020\u0003\u0012\u0012\u0010\u0004\u001a\n\u0012\u0006\b\u0001\u0012\u00020\u00030\u0005\"\u00020\u0003¢\u0006\u0002\u0010\u0006B\u0015\u0012\u000e\u0010\u0007\u001a\n\u0012\u0006\b\u0001\u0012\u00020\u00030\u0005¢\u0006\u0002\u0010\bJ\u0016\u0010\u0010\u001a\u00020\u00112\f\u0010\u0007\u001a\b\u0012\u0004\u0012\u00020\u00030\u0012H&R\u0014\u0010\t\u001a\u00020\n8PX\u0090\u0004¢\u0006\u0006\u001a\u0004\b\u000b\u0010\fR\u001e\u0010\u0007\u001a\n\u0012\u0006\b\u0001\u0012\u00020\u00030\u0005X\u0080\u0004¢\u0006\n\n\u0002\u0010\u000f\u001a\u0004\b\r\u0010\u000e¨\u0006\u0013"}, d2 = {"Landroidx/room/InvalidationTracker$Observer;", "", "firstTable", "", "rest", "", "(Ljava/lang/String;[Ljava/lang/String;)V", "tables", "([Ljava/lang/String;)V", "isRemote", "", "isRemote$room_runtime_release", "()Z", "getTables$room_runtime_release", "()[Ljava/lang/String;", "[Ljava/lang/String;", "onInvalidated", "", "", "room-runtime_release"}, k = 1, mv = {1, 8, 0}, xi = 48)
    public static abstract class Observer {
        private final String[] tables;

        public abstract void onInvalidated(Set<String> tables);

        public Observer(String[] tables) {
            Intrinsics.checkNotNullParameter(tables, "tables");
            this.tables = tables;
        }

        /* renamed from: getTables$room_runtime_release, reason: from getter */
        public final String[] getTables() {
            return this.tables;
        }

        /* JADX WARN: Illegal instructions before constructor call */
        /*
            Code decompiled incorrectly, please refer to instructions dump.
            To view partially-correct add '--show-bad-code' argument
        */
        protected Observer(java.lang.String r5, java.lang.String... r6) {
            /*
                r4 = this;
                java.lang.String r0 = "firstTable"
                kotlin.jvm.internal.Intrinsics.checkNotNullParameter(r5, r0)
                java.lang.String r0 = "rest"
                kotlin.jvm.internal.Intrinsics.checkNotNullParameter(r6, r0)
                java.util.List r0 = kotlin.collections.CollectionsKt.createListBuilder()
                r1 = r0
                r2 = 0
                r3 = r1
                java.util.Collection r3 = (java.util.Collection) r3
                kotlin.collections.CollectionsKt.addAll(r3, r6)
                r1.add(r5)
                java.util.List r0 = kotlin.collections.CollectionsKt.build(r0)
                java.util.Collection r0 = (java.util.Collection) r0
                r1 = 0
                r2 = r0
                r3 = 0
                java.lang.String[] r3 = new java.lang.String[r3]
                java.lang.Object[] r0 = r2.toArray(r3)
                java.lang.String[] r0 = (java.lang.String[]) r0
                r4.<init>(r0)
                return
            */
            throw new UnsupportedOperationException("Method not decompiled: androidx.room.InvalidationTracker.Observer.<init>(java.lang.String, java.lang.String[]):void");
        }

        public boolean isRemote$room_runtime_release() {
            return false;
        }
    }

    /* compiled from: InvalidationTracker.kt */
    @Metadata(d1 = {"\u00008\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0000\n\u0002\u0010\b\n\u0002\b\u0002\n\u0002\u0010\u000b\n\u0002\b\u0005\n\u0002\u0010\u0016\n\u0002\b\u0003\n\u0002\u0010\u0015\n\u0000\n\u0002\u0010\u0018\n\u0002\b\u0005\n\u0002\u0010\u0002\n\u0002\b\u0002\b\u0000\u0018\u0000 \u00192\u00020\u0001:\u0001\u0019B\r\u0012\u0006\u0010\u0002\u001a\u00020\u0003¢\u0006\u0002\u0010\u0004J\n\u0010\u0013\u001a\u0004\u0018\u00010\u0010H\u0007J\u0012\u0010\u0014\u001a\u00020\u00062\n\u0010\u0015\u001a\u00020\u0010\"\u00020\u0003J\u0012\u0010\u0016\u001a\u00020\u00062\n\u0010\u0015\u001a\u00020\u0010\"\u00020\u0003J\u0006\u0010\u0017\u001a\u00020\u0018R\u001a\u0010\u0005\u001a\u00020\u0006X\u0086\u000e¢\u0006\u000e\n\u0000\u001a\u0004\b\u0007\u0010\b\"\u0004\b\t\u0010\nR\u0011\u0010\u000b\u001a\u00020\f¢\u0006\b\n\u0000\u001a\u0004\b\r\u0010\u000eR\u000e\u0010\u000f\u001a\u00020\u0010X\u0082\u0004¢\u0006\u0002\n\u0000R\u000e\u0010\u0011\u001a\u00020\u0012X\u0082\u0004¢\u0006\u0002\n\u0000¨\u0006\u001a"}, d2 = {"Landroidx/room/InvalidationTracker$ObservedTableTracker;", "", "tableCount", "", "(I)V", "needsSync", "", "getNeedsSync", "()Z", "setNeedsSync", "(Z)V", "tableObservers", "", "getTableObservers", "()[J", "triggerStateChanges", "", "triggerStates", "", "getTablesToSync", "onAdded", "tableIds", "onRemoved", "resetTriggerState", "", "Companion", "room-runtime_release"}, k = 1, mv = {1, 8, 0}, xi = 48)
    public static final class ObservedTableTracker {
        public static final int ADD = 1;
        public static final int NO_OP = 0;
        public static final int REMOVE = 2;
        private boolean needsSync;
        private final long[] tableObservers;
        private final int[] triggerStateChanges;
        private final boolean[] triggerStates;

        public ObservedTableTracker(int tableCount) {
            this.tableObservers = new long[tableCount];
            this.triggerStates = new boolean[tableCount];
            this.triggerStateChanges = new int[tableCount];
        }

        public final long[] getTableObservers() {
            return this.tableObservers;
        }

        public final boolean getNeedsSync() {
            return this.needsSync;
        }

        public final void setNeedsSync(boolean z) {
            this.needsSync = z;
        }

        public final boolean onAdded(int... tableIds) {
            Intrinsics.checkNotNullParameter(tableIds, "tableIds");
            boolean needTriggerSync = false;
            synchronized (this) {
                for (int element$iv : tableIds) {
                    long prevObserverCount = this.tableObservers[element$iv];
                    this.tableObservers[element$iv] = 1 + prevObserverCount;
                    if (prevObserverCount == 0) {
                        this.needsSync = true;
                        needTriggerSync = true;
                    }
                }
                Unit unit = Unit.INSTANCE;
            }
            return needTriggerSync;
        }

        public final boolean onRemoved(int... tableIds) {
            Intrinsics.checkNotNullParameter(tableIds, "tableIds");
            boolean needTriggerSync = false;
            synchronized (this) {
                for (int element$iv : tableIds) {
                    long prevObserverCount = this.tableObservers[element$iv];
                    this.tableObservers[element$iv] = prevObserverCount - 1;
                    if (prevObserverCount == 1) {
                        this.needsSync = true;
                        needTriggerSync = true;
                    }
                }
                Unit unit = Unit.INSTANCE;
            }
            return needTriggerSync;
        }

        public final void resetTriggerState() {
            synchronized (this) {
                Arrays.fill(this.triggerStates, false);
                this.needsSync = true;
                Unit unit = Unit.INSTANCE;
            }
        }

        public final int[] getTablesToSync() {
            synchronized (this) {
                if (!this.needsSync) {
                    return null;
                }
                long[] $this$forEachIndexed$iv = this.tableObservers;
                int index$iv = 0;
                int length = $this$forEachIndexed$iv.length;
                int i = 0;
                while (i < length) {
                    long item$iv = $this$forEachIndexed$iv[i];
                    int index$iv2 = index$iv + 1;
                    boolean newState = item$iv > 0;
                    if (newState != this.triggerStates[index$iv]) {
                        this.triggerStateChanges[index$iv] = newState ? 1 : 2;
                    } else {
                        this.triggerStateChanges[index$iv] = 0;
                    }
                    this.triggerStates[index$iv] = newState;
                    i++;
                    index$iv = index$iv2;
                }
                this.needsSync = false;
                return (int[]) this.triggerStateChanges.clone();
            }
        }
    }

    /* compiled from: InvalidationTracker.kt */
    @Metadata(d1 = {"\u0000*\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0018\u0002\n\u0002\b\u0005\n\u0002\u0010\u0002\n\u0000\n\u0002\u0010\"\n\u0002\u0010\u000e\n\u0000\b\u0000\u0018\u00002\u00020\u0001B\u0015\u0012\u0006\u0010\u0002\u001a\u00020\u0003\u0012\u0006\u0010\u0004\u001a\u00020\u0001¢\u0006\u0002\u0010\u0005J\u0016\u0010\f\u001a\u00020\r2\f\u0010\u000e\u001a\b\u0012\u0004\u0012\u00020\u00100\u000fH\u0016R\u0017\u0010\u0006\u001a\b\u0012\u0004\u0012\u00020\u00010\u0007¢\u0006\b\n\u0000\u001a\u0004\b\b\u0010\tR\u0011\u0010\u0002\u001a\u00020\u0003¢\u0006\b\n\u0000\u001a\u0004\b\n\u0010\u000b¨\u0006\u0011"}, d2 = {"Landroidx/room/InvalidationTracker$WeakObserver;", "Landroidx/room/InvalidationTracker$Observer;", "tracker", "Landroidx/room/InvalidationTracker;", "delegate", "(Landroidx/room/InvalidationTracker;Landroidx/room/InvalidationTracker$Observer;)V", "delegateRef", "Ljava/lang/ref/WeakReference;", "getDelegateRef", "()Ljava/lang/ref/WeakReference;", "getTracker", "()Landroidx/room/InvalidationTracker;", "onInvalidated", "", "tables", "", "", "room-runtime_release"}, k = 1, mv = {1, 8, 0}, xi = 48)
    public static final class WeakObserver extends Observer {
        private final WeakReference<Observer> delegateRef;
        private final InvalidationTracker tracker;

        public final InvalidationTracker getTracker() {
            return this.tracker;
        }

        /* JADX WARN: 'super' call moved to the top of the method (can break code semantics) */
        public WeakObserver(InvalidationTracker tracker, Observer delegate) {
            super(delegate.getTables());
            Intrinsics.checkNotNullParameter(tracker, "tracker");
            Intrinsics.checkNotNullParameter(delegate, "delegate");
            this.tracker = tracker;
            this.delegateRef = new WeakReference<>(delegate);
        }

        public final WeakReference<Observer> getDelegateRef() {
            return this.delegateRef;
        }

        @Override // androidx.room.InvalidationTracker.Observer
        public void onInvalidated(Set<String> tables) {
            Intrinsics.checkNotNullParameter(tables, "tables");
            Observer observer = this.delegateRef.get();
            if (observer == null) {
                this.tracker.removeObserver(this);
            } else {
                observer.onInvalidated(tables);
            }
        }
    }

    /* compiled from: InvalidationTracker.kt */
    @Metadata(d1 = {"\u0000*\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0002\b\u0002\n\u0002\u0010\u000e\n\u0002\b\u0007\n\u0002\u0010\u0011\n\u0002\b\u0003\n\u0002\u0010\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0006\b\u0086\u0003\u0018\u00002\u00020\u0001B\u0007\b\u0002¢\u0006\u0002\u0010\u0002J\u0015\u0010\u000f\u001a\u00020\u00102\u0006\u0010\u0011\u001a\u00020\u0012H\u0000¢\u0006\u0002\b\u0013J\u001d\u0010\u0014\u001a\u00020\u00042\u0006\u0010\u0015\u001a\u00020\u00042\u0006\u0010\u0016\u001a\u00020\u0004H\u0000¢\u0006\u0002\b\u0017R\u000e\u0010\u0003\u001a\u00020\u0004X\u0082T¢\u0006\u0002\n\u0000R\u000e\u0010\u0005\u001a\u00020\u0004X\u0082T¢\u0006\u0002\n\u0000R\u0016\u0010\u0006\u001a\u00020\u00048\u0000X\u0081T¢\u0006\b\n\u0000\u0012\u0004\b\u0007\u0010\u0002R\u0016\u0010\b\u001a\u00020\u00048\u0000X\u0081T¢\u0006\b\n\u0000\u0012\u0004\b\t\u0010\u0002R\u000e\u0010\n\u001a\u00020\u0004X\u0082T¢\u0006\u0002\n\u0000R\u0016\u0010\u000b\u001a\b\u0012\u0004\u0012\u00020\u00040\fX\u0082\u0004¢\u0006\u0004\n\u0002\u0010\rR\u000e\u0010\u000e\u001a\u00020\u0004X\u0082T¢\u0006\u0002\n\u0000¨\u0006\u0018"}, d2 = {"Landroidx/room/InvalidationTracker$Companion;", "", "()V", "CREATE_TRACKING_TABLE_SQL", "", "INVALIDATED_COLUMN_NAME", "RESET_UPDATED_TABLES_SQL", "getRESET_UPDATED_TABLES_SQL$room_runtime_release$annotations", "SELECT_UPDATED_TABLES_SQL", "getSELECT_UPDATED_TABLES_SQL$room_runtime_release$annotations", "TABLE_ID_COLUMN_NAME", "TRIGGERS", "", "[Ljava/lang/String;", "UPDATE_TABLE_NAME", "beginTransactionInternal", "", "database", "Landroidx/sqlite/db/SupportSQLiteDatabase;", "beginTransactionInternal$room_runtime_release", "getTriggerName", "tableName", "triggerType", "getTriggerName$room_runtime_release", "room-runtime_release"}, k = 1, mv = {1, 8, 0}, xi = 48)
    public static final class Companion {
        public /* synthetic */ Companion(DefaultConstructorMarker defaultConstructorMarker) {
            this();
        }

        public static /* synthetic */ void getRESET_UPDATED_TABLES_SQL$room_runtime_release$annotations() {
        }

        public static /* synthetic */ void getSELECT_UPDATED_TABLES_SQL$room_runtime_release$annotations() {
        }

        private Companion() {
        }

        public final String getTriggerName$room_runtime_release(String tableName, String triggerType) {
            Intrinsics.checkNotNullParameter(tableName, "tableName");
            Intrinsics.checkNotNullParameter(triggerType, "triggerType");
            return "`room_table_modification_trigger_" + tableName + '_' + triggerType + '`';
        }

        public final void beginTransactionInternal$room_runtime_release(SupportSQLiteDatabase database) {
            Intrinsics.checkNotNullParameter(database, "database");
            if (database.isWriteAheadLoggingEnabled()) {
                database.beginTransactionNonExclusive();
            } else {
                database.beginTransaction();
            }
        }
    }
}
