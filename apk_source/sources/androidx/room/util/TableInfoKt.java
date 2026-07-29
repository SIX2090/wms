package androidx.room.util;

import android.database.Cursor;
import androidx.autofill.HintConstants;
import androidx.room.util.TableInfo;
import androidx.sqlite.db.SupportSQLiteDatabase;
import java.util.ArrayList;
import java.util.Collection;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import kotlin.Metadata;
import kotlin.collections.CollectionsKt;
import kotlin.collections.MapsKt;
import kotlin.collections.SetsKt;
import kotlin.io.CloseableKt;
import kotlin.jvm.internal.Intrinsics;

/* compiled from: TableInfo.kt */
@Metadata(d1 = {"\u0000H\n\u0000\n\u0002\u0010$\n\u0002\u0010\u000e\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0010 \n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010\"\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0010\u000b\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0000\u001a$\u0010\u0000\u001a\u000e\u0012\u0004\u0012\u00020\u0002\u0012\u0004\u0012\u00020\u00030\u00012\u0006\u0010\u0004\u001a\u00020\u00052\u0006\u0010\u0006\u001a\u00020\u0002H\u0002\u001a\u0016\u0010\u0007\u001a\b\u0012\u0004\u0012\u00020\t0\b2\u0006\u0010\n\u001a\u00020\u000bH\u0002\u001a\u001e\u0010\f\u001a\b\u0012\u0004\u0012\u00020\u000e0\r2\u0006\u0010\u0004\u001a\u00020\u00052\u0006\u0010\u0006\u001a\u00020\u0002H\u0002\u001a\"\u0010\u000f\u001a\u0004\u0018\u00010\u00102\u0006\u0010\u0004\u001a\u00020\u00052\u0006\u0010\u0011\u001a\u00020\u00022\u0006\u0010\u0012\u001a\u00020\u0013H\u0002\u001a \u0010\u0014\u001a\n\u0012\u0004\u0012\u00020\u0010\u0018\u00010\r2\u0006\u0010\u0004\u001a\u00020\u00052\u0006\u0010\u0006\u001a\u00020\u0002H\u0002\u001a\u0018\u0010\u0015\u001a\u00020\u00162\u0006\u0010\u0004\u001a\u00020\u00052\u0006\u0010\u0006\u001a\u00020\u0002H\u0000¨\u0006\u0017"}, d2 = {"readColumns", "", "", "Landroidx/room/util/TableInfo$Column;", "database", "Landroidx/sqlite/db/SupportSQLiteDatabase;", "tableName", "readForeignKeyFieldMappings", "", "Landroidx/room/util/TableInfo$ForeignKeyWithSequence;", "cursor", "Landroid/database/Cursor;", "readForeignKeys", "", "Landroidx/room/util/TableInfo$ForeignKey;", "readIndex", "Landroidx/room/util/TableInfo$Index;", HintConstants.AUTOFILL_HINT_NAME, "unique", "", "readIndices", "readTableInfo", "Landroidx/room/util/TableInfo;", "room-runtime_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes11.dex */
public final class TableInfoKt {
    public static final TableInfo readTableInfo(SupportSQLiteDatabase database, String tableName) {
        Intrinsics.checkNotNullParameter(database, "database");
        Intrinsics.checkNotNullParameter(tableName, "tableName");
        Map columns = readColumns(database, tableName);
        Set foreignKeys = readForeignKeys(database, tableName);
        Set indices = readIndices(database, tableName);
        return new TableInfo(tableName, columns, foreignKeys, indices);
    }

    private static final Set<TableInfo.ForeignKey> readForeignKeys(SupportSQLiteDatabase database, String tableName) {
        Throwable th;
        List myColumns;
        List refColumns;
        int $i$f$useCursor;
        Cursor $this$useCursor$iv = database.query("PRAGMA foreign_key_list(`" + tableName + "`)");
        int $i$f$useCursor2 = 0;
        Cursor cursor = $this$useCursor$iv;
        try {
            Cursor cursor2 = cursor;
            int i = 0;
            int idColumnIndex = cursor2.getColumnIndex("id");
            int seqColumnIndex = cursor2.getColumnIndex("seq");
            int tableColumnIndex = cursor2.getColumnIndex("table");
            int onDeleteColumnIndex = cursor2.getColumnIndex("on_delete");
            int onUpdateColumnIndex = cursor2.getColumnIndex("on_update");
            Iterable ordered = readForeignKeyFieldMappings(cursor2);
            cursor2.moveToPosition(-1);
            Set $this$readForeignKeys_u24lambda_u243_u24lambda_u242 = SetsKt.createSetBuilder();
            while (cursor2.moveToNext()) {
                int seq = cursor2.getInt(seqColumnIndex);
                if (seq == 0) {
                    int id = cursor2.getInt(idColumnIndex);
                    List myColumns2 = new ArrayList();
                    List refColumns2 = new ArrayList();
                    Iterable $this$filter$iv = ordered;
                    Collection destination$iv$iv = new ArrayList();
                    for (Object element$iv$iv : $this$filter$iv) {
                        try {
                            TableInfo.ForeignKeyWithSequence it = (TableInfo.ForeignKeyWithSequence) element$iv$iv;
                            Cursor $this$useCursor$iv2 = $this$useCursor$iv;
                            int id2 = id;
                            if (it.getId() == id2) {
                                Collection destination$iv$iv2 = destination$iv$iv;
                                try {
                                    destination$iv$iv2.add(element$iv$iv);
                                    destination$iv$iv = destination$iv$iv2;
                                } catch (Throwable th2) {
                                    th = th2;
                                    try {
                                        throw th;
                                    } catch (Throwable th3) {
                                        CloseableKt.closeFinally(cursor, th);
                                        throw th3;
                                    }
                                }
                            }
                            id = id2;
                            $this$useCursor$iv = $this$useCursor$iv2;
                        } catch (Throwable th4) {
                            th = th4;
                        }
                    }
                    Cursor $this$useCursor$iv3 = $this$useCursor$iv;
                    int id3 = id;
                    try {
                        Iterable $this$forEach$iv = (List) destination$iv$iv;
                        int $i$f$forEach = 0;
                        for (Object element$iv : $this$forEach$iv) {
                            TableInfo.ForeignKeyWithSequence key = (TableInfo.ForeignKeyWithSequence) element$iv;
                            Iterable $this$forEach$iv2 = $this$forEach$iv;
                            int $i$f$forEach2 = $i$f$forEach;
                            List myColumns3 = myColumns2;
                            myColumns3.add(key.getFrom());
                            int id4 = id3;
                            List refColumns3 = refColumns2;
                            refColumns3.add(key.getTo());
                            refColumns2 = refColumns3;
                            $this$forEach$iv = $this$forEach$iv2;
                            id3 = id4;
                            myColumns2 = myColumns3;
                            $i$f$forEach = $i$f$forEach2;
                        }
                        myColumns = myColumns2;
                        refColumns = refColumns2;
                        $i$f$useCursor = $i$f$useCursor2;
                    } catch (Throwable th5) {
                        th = th5;
                        throw th;
                    }
                    try {
                        String string = cursor2.getString(tableColumnIndex);
                        int i2 = i;
                        Intrinsics.checkNotNullExpressionValue(string, "cursor.getString(tableColumnIndex)");
                        String string2 = cursor2.getString(onDeleteColumnIndex);
                        int idColumnIndex2 = idColumnIndex;
                        Intrinsics.checkNotNullExpressionValue(string2, "cursor.getString(onDeleteColumnIndex)");
                        String string3 = cursor2.getString(onUpdateColumnIndex);
                        Intrinsics.checkNotNullExpressionValue(string3, "cursor.getString(onUpdateColumnIndex)");
                        $this$readForeignKeys_u24lambda_u243_u24lambda_u242.add(new TableInfo.ForeignKey(string, string2, string3, myColumns, refColumns));
                        $i$f$useCursor2 = $i$f$useCursor;
                        i = i2;
                        idColumnIndex = idColumnIndex2;
                        cursor2 = cursor2;
                        $this$useCursor$iv = $this$useCursor$iv3;
                    } catch (Throwable th6) {
                        th = th6;
                        throw th;
                    }
                }
            }
            Set<TableInfo.ForeignKey> build = SetsKt.build($this$readForeignKeys_u24lambda_u243_u24lambda_u242);
            CloseableKt.closeFinally(cursor, null);
            return build;
        } catch (Throwable th7) {
            th = th7;
        }
    }

    private static final List<TableInfo.ForeignKeyWithSequence> readForeignKeyFieldMappings(Cursor cursor) {
        int idColumnIndex = cursor.getColumnIndex("id");
        int seqColumnIndex = cursor.getColumnIndex("seq");
        int fromColumnIndex = cursor.getColumnIndex("from");
        int toColumnIndex = cursor.getColumnIndex("to");
        List $this$readForeignKeyFieldMappings_u24lambda_u244 = CollectionsKt.createListBuilder();
        while (cursor.moveToNext()) {
            int i = cursor.getInt(idColumnIndex);
            int i2 = cursor.getInt(seqColumnIndex);
            String string = cursor.getString(fromColumnIndex);
            Intrinsics.checkNotNullExpressionValue(string, "cursor.getString(fromColumnIndex)");
            String string2 = cursor.getString(toColumnIndex);
            Intrinsics.checkNotNullExpressionValue(string2, "cursor.getString(toColumnIndex)");
            $this$readForeignKeyFieldMappings_u24lambda_u244.add(new TableInfo.ForeignKeyWithSequence(i, i2, string, string2));
        }
        return CollectionsKt.sorted(CollectionsKt.build($this$readForeignKeyFieldMappings_u24lambda_u244));
    }

    private static final Map<String, TableInfo.Column> readColumns(SupportSQLiteDatabase database, String tableName) {
        Throwable th;
        String str = "type";
        String str2 = HintConstants.AUTOFILL_HINT_NAME;
        Cursor $this$useCursor$iv = database.query("PRAGMA table_info(`" + tableName + "`)");
        Cursor cursor = $this$useCursor$iv;
        try {
            Cursor cursor2 = cursor;
            if (cursor2.getColumnCount() <= 0) {
                try {
                    Map<String, TableInfo.Column> emptyMap = MapsKt.emptyMap();
                    CloseableKt.closeFinally(cursor, null);
                    return emptyMap;
                } catch (Throwable th2) {
                    th = th2;
                }
            } else {
                int nameIndex = cursor2.getColumnIndex(HintConstants.AUTOFILL_HINT_NAME);
                int typeIndex = cursor2.getColumnIndex("type");
                int notNullIndex = cursor2.getColumnIndex("notnull");
                int pkIndex = cursor2.getColumnIndex("pk");
                int defaultValueIndex = cursor2.getColumnIndex("dflt_value");
                Map createMapBuilder = MapsKt.createMapBuilder();
                Map $this$readColumns_u24lambda_u246_u24lambda_u245 = createMapBuilder;
                while (cursor2.moveToNext()) {
                    String name = cursor2.getString(nameIndex);
                    String type = cursor2.getString(typeIndex);
                    boolean notNull = cursor2.getInt(notNullIndex) != 0;
                    int primaryKeyPosition = cursor2.getInt(pkIndex);
                    String defaultValue = cursor2.getString(defaultValueIndex);
                    Intrinsics.checkNotNullExpressionValue(name, str2);
                    String str3 = str2;
                    Cursor $this$useCursor$iv2 = $this$useCursor$iv;
                    try {
                        Intrinsics.checkNotNullExpressionValue(type, str);
                        String str4 = str;
                        Map $this$readColumns_u24lambda_u246_u24lambda_u2452 = $this$readColumns_u24lambda_u246_u24lambda_u245;
                        $this$readColumns_u24lambda_u246_u24lambda_u2452.put(name, new TableInfo.Column(name, type, notNull, primaryKeyPosition, defaultValue, 2));
                        $this$readColumns_u24lambda_u246_u24lambda_u245 = $this$readColumns_u24lambda_u246_u24lambda_u2452;
                        str = str4;
                        str2 = str3;
                        $this$useCursor$iv = $this$useCursor$iv2;
                    } catch (Throwable th3) {
                        th = th3;
                    }
                }
                Map<String, TableInfo.Column> build = MapsKt.build(createMapBuilder);
                CloseableKt.closeFinally(cursor, null);
                return build;
            }
        } catch (Throwable th4) {
            th = th4;
        }
        try {
            throw th;
        } catch (Throwable th5) {
            CloseableKt.closeFinally(cursor, th);
            throw th5;
        }
    }

    private static final Set<TableInfo.Index> readIndices(SupportSQLiteDatabase database, String tableName) {
        Throwable th;
        Cursor $this$useCursor$iv = database.query("PRAGMA index_list(`" + tableName + "`)");
        Cursor cursor = $this$useCursor$iv;
        try {
            Cursor cursor2 = cursor;
            int nameColumnIndex = cursor2.getColumnIndex(HintConstants.AUTOFILL_HINT_NAME);
            int originColumnIndex = cursor2.getColumnIndex("origin");
            int uniqueIndex = cursor2.getColumnIndex("unique");
            if (nameColumnIndex != -1 && originColumnIndex != -1) {
                if (uniqueIndex != -1) {
                    Set $this$readIndices_u24lambda_u248_u24lambda_u247 = SetsKt.createSetBuilder();
                    while (cursor2.moveToNext()) {
                        String origin = cursor2.getString(originColumnIndex);
                        if (Intrinsics.areEqual("c", origin)) {
                            String name = cursor2.getString(nameColumnIndex);
                            Cursor $this$useCursor$iv2 = $this$useCursor$iv;
                            try {
                                boolean z = true;
                                if (cursor2.getInt(uniqueIndex) != 1) {
                                    z = false;
                                }
                                boolean unique = z;
                                Intrinsics.checkNotNullExpressionValue(name, "name");
                                TableInfo.Index index = readIndex(database, name, unique);
                                if (index == null) {
                                    CloseableKt.closeFinally(cursor, null);
                                    return null;
                                }
                                $this$readIndices_u24lambda_u248_u24lambda_u247.add(index);
                                $this$useCursor$iv = $this$useCursor$iv2;
                            } catch (Throwable th2) {
                                th = th2;
                                try {
                                    throw th;
                                } catch (Throwable th3) {
                                    CloseableKt.closeFinally(cursor, th);
                                    throw th3;
                                }
                            }
                        }
                    }
                    Set<TableInfo.Index> build = SetsKt.build($this$readIndices_u24lambda_u248_u24lambda_u247);
                    CloseableKt.closeFinally(cursor, null);
                    return build;
                }
            }
            CloseableKt.closeFinally(cursor, null);
            return null;
        } catch (Throwable th4) {
            th = th4;
        }
    }

    /* JADX WARN: Unreachable blocks removed: 2, instructions: 4 */
    private static final TableInfo.Index readIndex(SupportSQLiteDatabase database, String name, boolean unique) {
        Throwable th;
        Cursor $this$useCursor$iv = database.query("PRAGMA index_xinfo(`" + name + "`)");
        Cursor cursor = $this$useCursor$iv;
        try {
            Cursor cursor2 = cursor;
            int seqnoColumnIndex = cursor2.getColumnIndex("seqno");
            int cidColumnIndex = cursor2.getColumnIndex("cid");
            int nameColumnIndex = cursor2.getColumnIndex(HintConstants.AUTOFILL_HINT_NAME);
            int descColumnIndex = cursor2.getColumnIndex("desc");
            if (seqnoColumnIndex != -1 && cidColumnIndex != -1 && nameColumnIndex != -1 && descColumnIndex != -1) {
                TreeMap columnsMap = new TreeMap();
                TreeMap ordersMap = new TreeMap();
                while (cursor2.moveToNext()) {
                    try {
                        int cid = cursor2.getInt(cidColumnIndex);
                        if (cid >= 0) {
                            int seq = cursor2.getInt(seqnoColumnIndex);
                            String columnName = cursor2.getString(nameColumnIndex);
                            String order = cursor2.getInt(descColumnIndex) > 0 ? "DESC" : "ASC";
                            Integer valueOf = Integer.valueOf(seq);
                            Cursor cursor3 = cursor2;
                            TreeMap treeMap = columnsMap;
                            Cursor $this$useCursor$iv2 = $this$useCursor$iv;
                            try {
                                Intrinsics.checkNotNullExpressionValue(columnName, "columnName");
                                treeMap.put(valueOf, columnName);
                                ordersMap.put(Integer.valueOf(seq), order);
                                cursor2 = cursor3;
                                $this$useCursor$iv = $this$useCursor$iv2;
                            } catch (Throwable th2) {
                                th = th2;
                                th = th;
                                try {
                                    throw th;
                                } catch (Throwable th3) {
                                    CloseableKt.closeFinally(cursor, th);
                                    throw th3;
                                }
                            }
                        }
                    } catch (Throwable th4) {
                        th = th4;
                        th = th;
                        throw th;
                    }
                }
                Collection values = columnsMap.values();
                Intrinsics.checkNotNullExpressionValue(values, "columnsMap.values");
                List columns = CollectionsKt.toList(values);
                Collection values2 = ordersMap.values();
                Intrinsics.checkNotNullExpressionValue(values2, "ordersMap.values");
                List orders = CollectionsKt.toList(values2);
                try {
                    TableInfo.Index index = new TableInfo.Index(name, unique, columns, orders);
                    CloseableKt.closeFinally(cursor, null);
                    return index;
                } catch (Throwable th5) {
                    th = th5;
                    th = th;
                    throw th;
                }
            }
            CloseableKt.closeFinally(cursor, null);
            return null;
        } catch (Throwable th6) {
            th = th6;
        }
    }
}
