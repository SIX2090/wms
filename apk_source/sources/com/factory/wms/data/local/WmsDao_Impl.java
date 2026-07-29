package com.factory.wms.data.local;

import android.database.Cursor;
import android.os.CancellationSignal;
import androidx.autofill.HintConstants;
import androidx.room.CoroutinesRoom;
import androidx.room.EntityDeletionOrUpdateAdapter;
import androidx.room.EntityInsertionAdapter;
import androidx.room.RoomDatabase;
import androidx.room.RoomSQLiteQuery;
import androidx.room.SharedSQLiteStatement;
import androidx.room.util.CursorUtil;
import androidx.room.util.DBUtil;
import androidx.sqlite.db.SupportSQLiteStatement;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.Callable;
import kotlin.Unit;
import kotlin.coroutines.Continuation;

/* loaded from: classes8.dex */
public final class WmsDao_Impl implements WmsDao {
    private final RoomDatabase __db;
    private final EntityDeletionOrUpdateAdapter<PendingDocumentEntity> __deletionAdapterOfPendingDocumentEntity;
    private final EntityInsertionAdapter<CachedMaterialEntity> __insertionAdapterOfCachedMaterialEntity;
    private final EntityInsertionAdapter<PendingDocumentEntity> __insertionAdapterOfPendingDocumentEntity;
    private final SharedSQLiteStatement __preparedStmtOfMarkPendingError;

    public WmsDao_Impl(final RoomDatabase __db) {
        this.__db = __db;
        this.__insertionAdapterOfCachedMaterialEntity = new EntityInsertionAdapter<CachedMaterialEntity>(__db) { // from class: com.factory.wms.data.local.WmsDao_Impl.1
            @Override // androidx.room.SharedSQLiteStatement
            protected String createQuery() {
                return "INSERT OR REPLACE INTO `cached_material` (`code`,`name`,`spec`,`unit`,`stock`,`warehouseCode`,`updatedAt`) VALUES (?,?,?,?,?,?,?)";
            }

            /* JADX INFO: Access modifiers changed from: protected */
            @Override // androidx.room.EntityInsertionAdapter
            public void bind(final SupportSQLiteStatement statement, final CachedMaterialEntity entity) {
                statement.bindString(1, entity.getCode());
                statement.bindString(2, entity.getName());
                if (entity.getSpec() == null) {
                    statement.bindNull(3);
                } else {
                    statement.bindString(3, entity.getSpec());
                }
                if (entity.getUnit() == null) {
                    statement.bindNull(4);
                } else {
                    statement.bindString(4, entity.getUnit());
                }
                statement.bindDouble(5, entity.getStock());
                if (entity.getWarehouseCode() == null) {
                    statement.bindNull(6);
                } else {
                    statement.bindString(6, entity.getWarehouseCode());
                }
                statement.bindLong(7, entity.getUpdatedAt());
            }
        };
        this.__insertionAdapterOfPendingDocumentEntity = new EntityInsertionAdapter<PendingDocumentEntity>(__db) { // from class: com.factory.wms.data.local.WmsDao_Impl.2
            @Override // androidx.room.SharedSQLiteStatement
            protected String createQuery() {
                return "INSERT OR ABORT INTO `pending_document` (`id`,`type`,`payloadJson`,`createdAt`,`lastError`) VALUES (nullif(?, 0),?,?,?,?)";
            }

            /* JADX INFO: Access modifiers changed from: protected */
            @Override // androidx.room.EntityInsertionAdapter
            public void bind(final SupportSQLiteStatement statement, final PendingDocumentEntity entity) {
                statement.bindLong(1, entity.getId());
                statement.bindString(2, entity.getType());
                statement.bindString(3, entity.getPayloadJson());
                statement.bindLong(4, entity.getCreatedAt());
                if (entity.getLastError() == null) {
                    statement.bindNull(5);
                } else {
                    statement.bindString(5, entity.getLastError());
                }
            }
        };
        this.__deletionAdapterOfPendingDocumentEntity = new EntityDeletionOrUpdateAdapter<PendingDocumentEntity>(__db) { // from class: com.factory.wms.data.local.WmsDao_Impl.3
            @Override // androidx.room.EntityDeletionOrUpdateAdapter, androidx.room.SharedSQLiteStatement
            protected String createQuery() {
                return "DELETE FROM `pending_document` WHERE `id` = ?";
            }

            /* JADX INFO: Access modifiers changed from: protected */
            @Override // androidx.room.EntityDeletionOrUpdateAdapter
            public void bind(final SupportSQLiteStatement statement, final PendingDocumentEntity entity) {
                statement.bindLong(1, entity.getId());
            }
        };
        this.__preparedStmtOfMarkPendingError = new SharedSQLiteStatement(__db) { // from class: com.factory.wms.data.local.WmsDao_Impl.4
            @Override // androidx.room.SharedSQLiteStatement
            public String createQuery() {
                return "UPDATE pending_document SET lastError = ? WHERE id = ?";
            }
        };
    }

    @Override // com.factory.wms.data.local.WmsDao
    public Object upsertMaterials(final List<CachedMaterialEntity> materials, final Continuation<? super Unit> $completion) {
        return CoroutinesRoom.execute(this.__db, true, new Callable<Unit>() { // from class: com.factory.wms.data.local.WmsDao_Impl.5
            @Override // java.util.concurrent.Callable
            public Unit call() throws Exception {
                WmsDao_Impl.this.__db.beginTransaction();
                try {
                    WmsDao_Impl.this.__insertionAdapterOfCachedMaterialEntity.insert((Iterable) materials);
                    WmsDao_Impl.this.__db.setTransactionSuccessful();
                    return Unit.INSTANCE;
                } finally {
                    WmsDao_Impl.this.__db.endTransaction();
                }
            }
        }, $completion);
    }

    @Override // com.factory.wms.data.local.WmsDao
    public Object insertPending(final PendingDocumentEntity document, final Continuation<? super Long> $completion) {
        return CoroutinesRoom.execute(this.__db, true, new Callable<Long>() { // from class: com.factory.wms.data.local.WmsDao_Impl.6
            /* JADX WARN: Can't rename method to resolve collision */
            @Override // java.util.concurrent.Callable
            public Long call() throws Exception {
                WmsDao_Impl.this.__db.beginTransaction();
                try {
                    Long _result = Long.valueOf(WmsDao_Impl.this.__insertionAdapterOfPendingDocumentEntity.insertAndReturnId(document));
                    WmsDao_Impl.this.__db.setTransactionSuccessful();
                    return _result;
                } finally {
                    WmsDao_Impl.this.__db.endTransaction();
                }
            }
        }, $completion);
    }

    @Override // com.factory.wms.data.local.WmsDao
    public Object deletePending(final PendingDocumentEntity document, final Continuation<? super Unit> $completion) {
        return CoroutinesRoom.execute(this.__db, true, new Callable<Unit>() { // from class: com.factory.wms.data.local.WmsDao_Impl.7
            @Override // java.util.concurrent.Callable
            public Unit call() throws Exception {
                WmsDao_Impl.this.__db.beginTransaction();
                try {
                    WmsDao_Impl.this.__deletionAdapterOfPendingDocumentEntity.handle(document);
                    WmsDao_Impl.this.__db.setTransactionSuccessful();
                    return Unit.INSTANCE;
                } finally {
                    WmsDao_Impl.this.__db.endTransaction();
                }
            }
        }, $completion);
    }

    @Override // com.factory.wms.data.local.WmsDao
    public Object markPendingError(final long id, final String message, final Continuation<? super Unit> $completion) {
        return CoroutinesRoom.execute(this.__db, true, new Callable<Unit>() { // from class: com.factory.wms.data.local.WmsDao_Impl.8
            @Override // java.util.concurrent.Callable
            public Unit call() throws Exception {
                SupportSQLiteStatement _stmt = WmsDao_Impl.this.__preparedStmtOfMarkPendingError.acquire();
                _stmt.bindString(1, message);
                _stmt.bindLong(2, id);
                try {
                    WmsDao_Impl.this.__db.beginTransaction();
                    try {
                        _stmt.executeUpdateDelete();
                        WmsDao_Impl.this.__db.setTransactionSuccessful();
                        return Unit.INSTANCE;
                    } finally {
                        WmsDao_Impl.this.__db.endTransaction();
                    }
                } finally {
                    WmsDao_Impl.this.__preparedStmtOfMarkPendingError.release(_stmt);
                }
            }
        }, $completion);
    }

    @Override // com.factory.wms.data.local.WmsDao
    public Object searchMaterials(final String keyword, final Continuation<? super List<CachedMaterialEntity>> $completion) {
        final RoomSQLiteQuery _statement = RoomSQLiteQuery.acquire("\n        SELECT * FROM cached_material\n        WHERE code LIKE '%' || ? || '%'\n           OR name LIKE '%' || ? || '%'\n           OR IFNULL(spec, '') LIKE '%' || ? || '%'\n        ORDER BY code\n        LIMIT 50\n        ", 3);
        _statement.bindString(1, keyword);
        _statement.bindString(2, keyword);
        _statement.bindString(3, keyword);
        CancellationSignal _cancellationSignal = DBUtil.createCancellationSignal();
        return CoroutinesRoom.execute(this.__db, false, _cancellationSignal, new Callable<List<CachedMaterialEntity>>() { // from class: com.factory.wms.data.local.WmsDao_Impl.9
            @Override // java.util.concurrent.Callable
            public List<CachedMaterialEntity> call() throws Exception {
                String _tmpSpec;
                String _tmpUnit;
                String _tmpWarehouseCode;
                Cursor _cursor = DBUtil.query(WmsDao_Impl.this.__db, _statement, false, null);
                try {
                    int _cursorIndexOfCode = CursorUtil.getColumnIndexOrThrow(_cursor, "code");
                    int _cursorIndexOfName = CursorUtil.getColumnIndexOrThrow(_cursor, HintConstants.AUTOFILL_HINT_NAME);
                    int _cursorIndexOfSpec = CursorUtil.getColumnIndexOrThrow(_cursor, "spec");
                    int _cursorIndexOfUnit = CursorUtil.getColumnIndexOrThrow(_cursor, "unit");
                    int _cursorIndexOfStock = CursorUtil.getColumnIndexOrThrow(_cursor, "stock");
                    int _cursorIndexOfWarehouseCode = CursorUtil.getColumnIndexOrThrow(_cursor, "warehouseCode");
                    int _cursorIndexOfUpdatedAt = CursorUtil.getColumnIndexOrThrow(_cursor, "updatedAt");
                    List<CachedMaterialEntity> _result = new ArrayList<>(_cursor.getCount());
                    while (_cursor.moveToNext()) {
                        String _tmpCode = _cursor.getString(_cursorIndexOfCode);
                        String _tmpName = _cursor.getString(_cursorIndexOfName);
                        if (_cursor.isNull(_cursorIndexOfSpec)) {
                            _tmpSpec = null;
                        } else {
                            _tmpSpec = _cursor.getString(_cursorIndexOfSpec);
                        }
                        if (_cursor.isNull(_cursorIndexOfUnit)) {
                            _tmpUnit = null;
                        } else {
                            String _tmpUnit2 = _cursor.getString(_cursorIndexOfUnit);
                            _tmpUnit = _tmpUnit2;
                        }
                        double _tmpStock = _cursor.getDouble(_cursorIndexOfStock);
                        if (_cursor.isNull(_cursorIndexOfWarehouseCode)) {
                            _tmpWarehouseCode = null;
                        } else {
                            String _tmpWarehouseCode2 = _cursor.getString(_cursorIndexOfWarehouseCode);
                            _tmpWarehouseCode = _tmpWarehouseCode2;
                        }
                        long _tmpUpdatedAt = _cursor.getLong(_cursorIndexOfUpdatedAt);
                        CachedMaterialEntity _item = new CachedMaterialEntity(_tmpCode, _tmpName, _tmpSpec, _tmpUnit, _tmpStock, _tmpWarehouseCode, _tmpUpdatedAt);
                        _result.add(_item);
                    }
                    return _result;
                } finally {
                    _cursor.close();
                    _statement.release();
                }
            }
        }, $completion);
    }

    @Override // com.factory.wms.data.local.WmsDao
    public Object materialByCode(final String code, final Continuation<? super CachedMaterialEntity> $completion) {
        final RoomSQLiteQuery _statement = RoomSQLiteQuery.acquire("SELECT * FROM cached_material WHERE code = ? LIMIT 1", 1);
        _statement.bindString(1, code);
        CancellationSignal _cancellationSignal = DBUtil.createCancellationSignal();
        return CoroutinesRoom.execute(this.__db, false, _cancellationSignal, new Callable<CachedMaterialEntity>() { // from class: com.factory.wms.data.local.WmsDao_Impl.10
            /* JADX WARN: Can't rename method to resolve collision */
            @Override // java.util.concurrent.Callable
            public CachedMaterialEntity call() throws Exception {
                CachedMaterialEntity _result;
                String _tmpSpec;
                String _tmpUnit;
                String _tmpWarehouseCode;
                Cursor _cursor = DBUtil.query(WmsDao_Impl.this.__db, _statement, false, null);
                try {
                    int _cursorIndexOfCode = CursorUtil.getColumnIndexOrThrow(_cursor, "code");
                    int _cursorIndexOfName = CursorUtil.getColumnIndexOrThrow(_cursor, HintConstants.AUTOFILL_HINT_NAME);
                    int _cursorIndexOfSpec = CursorUtil.getColumnIndexOrThrow(_cursor, "spec");
                    int _cursorIndexOfUnit = CursorUtil.getColumnIndexOrThrow(_cursor, "unit");
                    int _cursorIndexOfStock = CursorUtil.getColumnIndexOrThrow(_cursor, "stock");
                    int _cursorIndexOfWarehouseCode = CursorUtil.getColumnIndexOrThrow(_cursor, "warehouseCode");
                    int _cursorIndexOfUpdatedAt = CursorUtil.getColumnIndexOrThrow(_cursor, "updatedAt");
                    if (_cursor.moveToFirst()) {
                        String _tmpCode = _cursor.getString(_cursorIndexOfCode);
                        String _tmpName = _cursor.getString(_cursorIndexOfName);
                        if (_cursor.isNull(_cursorIndexOfSpec)) {
                            _tmpSpec = null;
                        } else {
                            _tmpSpec = _cursor.getString(_cursorIndexOfSpec);
                        }
                        if (_cursor.isNull(_cursorIndexOfUnit)) {
                            _tmpUnit = null;
                        } else {
                            String _tmpUnit2 = _cursor.getString(_cursorIndexOfUnit);
                            _tmpUnit = _tmpUnit2;
                        }
                        double _tmpStock = _cursor.getDouble(_cursorIndexOfStock);
                        if (_cursor.isNull(_cursorIndexOfWarehouseCode)) {
                            _tmpWarehouseCode = null;
                        } else {
                            String _tmpWarehouseCode2 = _cursor.getString(_cursorIndexOfWarehouseCode);
                            _tmpWarehouseCode = _tmpWarehouseCode2;
                        }
                        long _tmpUpdatedAt = _cursor.getLong(_cursorIndexOfUpdatedAt);
                        _result = new CachedMaterialEntity(_tmpCode, _tmpName, _tmpSpec, _tmpUnit, _tmpStock, _tmpWarehouseCode, _tmpUpdatedAt);
                    } else {
                        _result = null;
                    }
                    return _result;
                } finally {
                    _cursor.close();
                    _statement.release();
                }
            }
        }, $completion);
    }

    @Override // com.factory.wms.data.local.WmsDao
    public Object allMaterials(final Continuation<? super List<CachedMaterialEntity>> $completion) {
        final RoomSQLiteQuery _statement = RoomSQLiteQuery.acquire("SELECT * FROM cached_material ORDER BY code", 0);
        CancellationSignal _cancellationSignal = DBUtil.createCancellationSignal();
        return CoroutinesRoom.execute(this.__db, false, _cancellationSignal, new Callable<List<CachedMaterialEntity>>() { // from class: com.factory.wms.data.local.WmsDao_Impl.11
            @Override // java.util.concurrent.Callable
            public List<CachedMaterialEntity> call() throws Exception {
                String _tmpSpec;
                String _tmpUnit;
                String _tmpWarehouseCode;
                Cursor _cursor = DBUtil.query(WmsDao_Impl.this.__db, _statement, false, null);
                try {
                    int _cursorIndexOfCode = CursorUtil.getColumnIndexOrThrow(_cursor, "code");
                    int _cursorIndexOfName = CursorUtil.getColumnIndexOrThrow(_cursor, HintConstants.AUTOFILL_HINT_NAME);
                    int _cursorIndexOfSpec = CursorUtil.getColumnIndexOrThrow(_cursor, "spec");
                    int _cursorIndexOfUnit = CursorUtil.getColumnIndexOrThrow(_cursor, "unit");
                    int _cursorIndexOfStock = CursorUtil.getColumnIndexOrThrow(_cursor, "stock");
                    int _cursorIndexOfWarehouseCode = CursorUtil.getColumnIndexOrThrow(_cursor, "warehouseCode");
                    int _cursorIndexOfUpdatedAt = CursorUtil.getColumnIndexOrThrow(_cursor, "updatedAt");
                    List<CachedMaterialEntity> _result = new ArrayList<>(_cursor.getCount());
                    while (_cursor.moveToNext()) {
                        String _tmpCode = _cursor.getString(_cursorIndexOfCode);
                        String _tmpName = _cursor.getString(_cursorIndexOfName);
                        if (_cursor.isNull(_cursorIndexOfSpec)) {
                            _tmpSpec = null;
                        } else {
                            _tmpSpec = _cursor.getString(_cursorIndexOfSpec);
                        }
                        if (_cursor.isNull(_cursorIndexOfUnit)) {
                            _tmpUnit = null;
                        } else {
                            String _tmpUnit2 = _cursor.getString(_cursorIndexOfUnit);
                            _tmpUnit = _tmpUnit2;
                        }
                        double _tmpStock = _cursor.getDouble(_cursorIndexOfStock);
                        if (_cursor.isNull(_cursorIndexOfWarehouseCode)) {
                            _tmpWarehouseCode = null;
                        } else {
                            String _tmpWarehouseCode2 = _cursor.getString(_cursorIndexOfWarehouseCode);
                            _tmpWarehouseCode = _tmpWarehouseCode2;
                        }
                        long _tmpUpdatedAt = _cursor.getLong(_cursorIndexOfUpdatedAt);
                        CachedMaterialEntity _item = new CachedMaterialEntity(_tmpCode, _tmpName, _tmpSpec, _tmpUnit, _tmpStock, _tmpWarehouseCode, _tmpUpdatedAt);
                        _result.add(_item);
                    }
                    return _result;
                } finally {
                    _cursor.close();
                    _statement.release();
                }
            }
        }, $completion);
    }

    @Override // com.factory.wms.data.local.WmsDao
    public Object pendingDocuments(final Continuation<? super List<PendingDocumentEntity>> $completion) {
        final RoomSQLiteQuery _statement = RoomSQLiteQuery.acquire("SELECT * FROM pending_document ORDER BY createdAt ASC", 0);
        CancellationSignal _cancellationSignal = DBUtil.createCancellationSignal();
        return CoroutinesRoom.execute(this.__db, false, _cancellationSignal, new Callable<List<PendingDocumentEntity>>() { // from class: com.factory.wms.data.local.WmsDao_Impl.12
            @Override // java.util.concurrent.Callable
            public List<PendingDocumentEntity> call() throws Exception {
                String _tmpLastError;
                Cursor _cursor = DBUtil.query(WmsDao_Impl.this.__db, _statement, false, null);
                try {
                    int _cursorIndexOfId = CursorUtil.getColumnIndexOrThrow(_cursor, "id");
                    int _cursorIndexOfType = CursorUtil.getColumnIndexOrThrow(_cursor, "type");
                    int _cursorIndexOfPayloadJson = CursorUtil.getColumnIndexOrThrow(_cursor, "payloadJson");
                    int _cursorIndexOfCreatedAt = CursorUtil.getColumnIndexOrThrow(_cursor, "createdAt");
                    int _cursorIndexOfLastError = CursorUtil.getColumnIndexOrThrow(_cursor, "lastError");
                    List<PendingDocumentEntity> _result = new ArrayList<>(_cursor.getCount());
                    while (_cursor.moveToNext()) {
                        long _tmpId = _cursor.getLong(_cursorIndexOfId);
                        String _tmpType = _cursor.getString(_cursorIndexOfType);
                        String _tmpPayloadJson = _cursor.getString(_cursorIndexOfPayloadJson);
                        long _tmpCreatedAt = _cursor.getLong(_cursorIndexOfCreatedAt);
                        if (_cursor.isNull(_cursorIndexOfLastError)) {
                            _tmpLastError = null;
                        } else {
                            _tmpLastError = _cursor.getString(_cursorIndexOfLastError);
                        }
                        PendingDocumentEntity _item = new PendingDocumentEntity(_tmpId, _tmpType, _tmpPayloadJson, _tmpCreatedAt, _tmpLastError);
                        _result.add(_item);
                    }
                    return _result;
                } finally {
                    _cursor.close();
                    _statement.release();
                }
            }
        }, $completion);
    }

    public static List<Class<?>> getRequiredConverters() {
        return Collections.emptyList();
    }
}
