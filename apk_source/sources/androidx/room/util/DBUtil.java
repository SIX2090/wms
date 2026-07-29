package androidx.room.util;

import android.database.AbstractWindowedCursor;
import android.database.Cursor;
import android.database.sqlite.SQLiteConstraintException;
import android.os.CancellationSignal;
import androidx.room.RoomDatabase;
import androidx.sqlite.db.SupportSQLiteCompat;
import androidx.sqlite.db.SupportSQLiteDatabase;
import androidx.sqlite.db.SupportSQLiteQuery;
import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import kotlin.Deprecated;
import kotlin.Metadata;
import kotlin.Unit;
import kotlin.collections.CollectionsKt;
import kotlin.io.CloseableKt;
import kotlin.jvm.internal.Intrinsics;
import kotlin.text.StringsKt;

/* compiled from: DBUtil.kt */
@Metadata(d1 = {"\u0000D\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0010\u000e\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010\u000b\n\u0002\b\u0002\n\u0002\u0010\b\n\u0000\n\u0002\u0018\u0002\n\u0000\u001a\b\u0010\u0000\u001a\u0004\u0018\u00010\u0001\u001a\u000e\u0010\u0002\u001a\u00020\u00032\u0006\u0010\u0004\u001a\u00020\u0005\u001a\u0016\u0010\u0006\u001a\u00020\u00032\u0006\u0010\u0004\u001a\u00020\u00052\u0006\u0010\u0007\u001a\u00020\b\u001a\u0010\u0010\t\u001a\u00020\b2\u0006\u0010\n\u001a\u00020\u000bH\u0002\u001a \u0010\f\u001a\u00020\u000b2\u0006\u0010\u0004\u001a\u00020\r2\u0006\u0010\u000e\u001a\u00020\u000f2\u0006\u0010\u0010\u001a\u00020\u0011H\u0007\u001a(\u0010\f\u001a\u00020\u000b2\u0006\u0010\u0004\u001a\u00020\r2\u0006\u0010\u000e\u001a\u00020\u000f2\u0006\u0010\u0010\u001a\u00020\u00112\b\u0010\u0012\u001a\u0004\u0018\u00010\u0001\u001a\u000e\u0010\u0013\u001a\u00020\u00142\u0006\u0010\u0015\u001a\u00020\u0016¨\u0006\u0017"}, d2 = {"createCancellationSignal", "Landroid/os/CancellationSignal;", "dropFtsSyncTriggers", "", "db", "Landroidx/sqlite/db/SupportSQLiteDatabase;", "foreignKeyCheck", "tableName", "", "processForeignKeyCheckFailure", "cursor", "Landroid/database/Cursor;", "query", "Landroidx/room/RoomDatabase;", "sqLiteQuery", "Landroidx/sqlite/db/SupportSQLiteQuery;", "maybeCopy", "", "signal", "readVersion", "", "databaseFile", "Ljava/io/File;", "room-runtime_release"}, k = 2, mv = {1, 8, 0}, xi = 48)
/* loaded from: classes11.dex */
public final class DBUtil {
    @Deprecated(message = "This is only used in the generated code and shouldn't be called directly.")
    public static final Cursor query(RoomDatabase db, SupportSQLiteQuery sqLiteQuery, boolean maybeCopy) {
        Intrinsics.checkNotNullParameter(db, "db");
        Intrinsics.checkNotNullParameter(sqLiteQuery, "sqLiteQuery");
        return query(db, sqLiteQuery, maybeCopy, null);
    }

    public static final Cursor query(RoomDatabase db, SupportSQLiteQuery sqLiteQuery, boolean maybeCopy, CancellationSignal signal) {
        int rowsInWindow;
        Intrinsics.checkNotNullParameter(db, "db");
        Intrinsics.checkNotNullParameter(sqLiteQuery, "sqLiteQuery");
        Cursor cursor = db.query(sqLiteQuery, signal);
        if (maybeCopy && (cursor instanceof AbstractWindowedCursor)) {
            int rowsInCursor = ((AbstractWindowedCursor) cursor).getCount();
            if (((AbstractWindowedCursor) cursor).hasWindow()) {
                rowsInWindow = ((AbstractWindowedCursor) cursor).getWindow().getNumRows();
            } else {
                rowsInWindow = rowsInCursor;
            }
            if (rowsInWindow < rowsInCursor) {
                return CursorUtil.copyAndClose(cursor);
            }
        }
        return cursor;
    }

    public static final void dropFtsSyncTriggers(SupportSQLiteDatabase db) {
        Intrinsics.checkNotNullParameter(db, "db");
        List $this$dropFtsSyncTriggers_u24lambda_u241 = CollectionsKt.createListBuilder();
        Cursor $this$useCursor$iv = db.query("SELECT name FROM sqlite_master WHERE type = 'trigger'");
        Cursor cursor = $this$useCursor$iv;
        try {
            Cursor cursor2 = cursor;
            while (cursor2.moveToNext()) {
                $this$dropFtsSyncTriggers_u24lambda_u241.add(cursor2.getString(0));
            }
            Unit unit = Unit.INSTANCE;
            CloseableKt.closeFinally(cursor, null);
            Iterable existingTriggers = CollectionsKt.build($this$dropFtsSyncTriggers_u24lambda_u241);
            Iterable $this$forEach$iv = existingTriggers;
            for (Object element$iv : $this$forEach$iv) {
                String triggerName = (String) element$iv;
                Intrinsics.checkNotNullExpressionValue(triggerName, "triggerName");
                if (StringsKt.startsWith$default(triggerName, "room_fts_content_sync_", false, 2, (Object) null)) {
                    db.execSQL("DROP TRIGGER IF EXISTS " + triggerName);
                }
            }
        } finally {
        }
    }

    public static final void foreignKeyCheck(SupportSQLiteDatabase db, String tableName) {
        Intrinsics.checkNotNullParameter(db, "db");
        Intrinsics.checkNotNullParameter(tableName, "tableName");
        Cursor $this$useCursor$iv = db.query("PRAGMA foreign_key_check(`" + tableName + "`)");
        Cursor cursor = $this$useCursor$iv;
        try {
            Cursor cursor2 = cursor;
            if (cursor2.getCount() > 0) {
                String errorMsg = processForeignKeyCheckFailure(cursor2);
                throw new SQLiteConstraintException(errorMsg);
            }
            Unit unit = Unit.INSTANCE;
            CloseableKt.closeFinally(cursor, null);
        } catch (Throwable th) {
            try {
                throw th;
            } catch (Throwable th2) {
                CloseableKt.closeFinally(cursor, th);
                throw th2;
            }
        }
    }

    public static final int readVersion(File databaseFile) throws IOException {
        Intrinsics.checkNotNullParameter(databaseFile, "databaseFile");
        FileChannel channel = new FileInputStream(databaseFile).getChannel();
        try {
            FileChannel input = channel;
            ByteBuffer buffer = ByteBuffer.allocate(4);
            input.tryLock(60L, 4L, true);
            input.position(60L);
            int read = input.read(buffer);
            if (read != 4) {
                throw new IOException("Bad database header, unable to read 4 bytes at offset 60");
            }
            buffer.rewind();
            int i = buffer.getInt();
            CloseableKt.closeFinally(channel, null);
            return i;
        } catch (Throwable th) {
            try {
                throw th;
            } catch (Throwable th2) {
                CloseableKt.closeFinally(channel, th);
                throw th2;
            }
        }
    }

    public static final CancellationSignal createCancellationSignal() {
        return SupportSQLiteCompat.Api16Impl.createCancellationSignal();
    }

    private static final String processForeignKeyCheckFailure(Cursor cursor) {
        StringBuilder $this$processForeignKeyCheckFailure_u24lambda_u245 = new StringBuilder();
        int rowCount = cursor.getCount();
        Map fkParentTables = new LinkedHashMap();
        while (cursor.moveToNext()) {
            if (cursor.isFirst()) {
                $this$processForeignKeyCheckFailure_u24lambda_u245.append("Foreign key violation(s) detected in '");
                $this$processForeignKeyCheckFailure_u24lambda_u245.append(cursor.getString(0)).append("'.\n");
            }
            String constraintIndex = cursor.getString(3);
            if (!fkParentTables.containsKey(constraintIndex)) {
                Intrinsics.checkNotNullExpressionValue(constraintIndex, "constraintIndex");
                String string = cursor.getString(2);
                Intrinsics.checkNotNullExpressionValue(string, "cursor.getString(2)");
                fkParentTables.put(constraintIndex, string);
            }
        }
        $this$processForeignKeyCheckFailure_u24lambda_u245.append("Number of different violations discovered: ");
        $this$processForeignKeyCheckFailure_u24lambda_u245.append(fkParentTables.keySet().size()).append("\n");
        $this$processForeignKeyCheckFailure_u24lambda_u245.append("Number of rows in violation: ");
        $this$processForeignKeyCheckFailure_u24lambda_u245.append(rowCount).append("\n");
        $this$processForeignKeyCheckFailure_u24lambda_u245.append("Violation(s) detected in the following constraint(s):\n");
        for (Map.Entry entry : fkParentTables.entrySet()) {
            String key = (String) entry.getKey();
            String value = (String) entry.getValue();
            $this$processForeignKeyCheckFailure_u24lambda_u245.append("\tParent Table = ");
            $this$processForeignKeyCheckFailure_u24lambda_u245.append(value);
            $this$processForeignKeyCheckFailure_u24lambda_u245.append(", Foreign Key Constraint Index = ");
            $this$processForeignKeyCheckFailure_u24lambda_u245.append(key).append("\n");
        }
        String sb = $this$processForeignKeyCheckFailure_u24lambda_u245.toString();
        Intrinsics.checkNotNullExpressionValue(sb, "StringBuilder().apply(builderAction).toString()");
        return sb;
    }
}
