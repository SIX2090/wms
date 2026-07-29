package com.factory.wms.data.local;

import androidx.autofill.HintConstants;
import androidx.room.DatabaseConfiguration;
import androidx.room.InvalidationTracker;
import androidx.room.RoomDatabase;
import androidx.room.RoomMasterTable;
import androidx.room.RoomOpenHelper;
import androidx.room.migration.AutoMigrationSpec;
import androidx.room.migration.Migration;
import androidx.room.util.DBUtil;
import androidx.room.util.TableInfo;
import androidx.sqlite.db.SupportSQLiteDatabase;
import androidx.sqlite.db.SupportSQLiteOpenHelper;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/* loaded from: classes8.dex */
public final class WmsDatabase_Impl extends WmsDatabase {
    private volatile WmsDao _wmsDao;

    @Override // androidx.room.RoomDatabase
    protected SupportSQLiteOpenHelper createOpenHelper(final DatabaseConfiguration config) {
        SupportSQLiteOpenHelper.Callback _openCallback = new RoomOpenHelper(config, new RoomOpenHelper.Delegate(1) { // from class: com.factory.wms.data.local.WmsDatabase_Impl.1
            @Override // androidx.room.RoomOpenHelper.Delegate
            public void createAllTables(final SupportSQLiteDatabase db) {
                db.execSQL("CREATE TABLE IF NOT EXISTS `cached_material` (`code` TEXT NOT NULL, `name` TEXT NOT NULL, `spec` TEXT, `unit` TEXT, `stock` REAL NOT NULL, `warehouseCode` TEXT, `updatedAt` INTEGER NOT NULL, PRIMARY KEY(`code`))");
                db.execSQL("CREATE TABLE IF NOT EXISTS `pending_document` (`id` INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, `type` TEXT NOT NULL, `payloadJson` TEXT NOT NULL, `createdAt` INTEGER NOT NULL, `lastError` TEXT)");
                db.execSQL(RoomMasterTable.CREATE_QUERY);
                db.execSQL("INSERT OR REPLACE INTO room_master_table (id,identity_hash) VALUES(42, '3f107a8cd2b0b22c48e3187847e42984')");
            }

            @Override // androidx.room.RoomOpenHelper.Delegate
            public void dropAllTables(final SupportSQLiteDatabase db) {
                db.execSQL("DROP TABLE IF EXISTS `cached_material`");
                db.execSQL("DROP TABLE IF EXISTS `pending_document`");
                List<? extends RoomDatabase.Callback> _callbacks = WmsDatabase_Impl.this.mCallbacks;
                if (_callbacks != null) {
                    for (RoomDatabase.Callback _callback : _callbacks) {
                        _callback.onDestructiveMigration(db);
                    }
                }
            }

            @Override // androidx.room.RoomOpenHelper.Delegate
            public void onCreate(final SupportSQLiteDatabase db) {
                List<? extends RoomDatabase.Callback> _callbacks = WmsDatabase_Impl.this.mCallbacks;
                if (_callbacks != null) {
                    for (RoomDatabase.Callback _callback : _callbacks) {
                        _callback.onCreate(db);
                    }
                }
            }

            @Override // androidx.room.RoomOpenHelper.Delegate
            public void onOpen(final SupportSQLiteDatabase db) {
                WmsDatabase_Impl.this.mDatabase = db;
                WmsDatabase_Impl.this.internalInitInvalidationTracker(db);
                List<? extends RoomDatabase.Callback> _callbacks = WmsDatabase_Impl.this.mCallbacks;
                if (_callbacks != null) {
                    for (RoomDatabase.Callback _callback : _callbacks) {
                        _callback.onOpen(db);
                    }
                }
            }

            @Override // androidx.room.RoomOpenHelper.Delegate
            public void onPreMigrate(final SupportSQLiteDatabase db) {
                DBUtil.dropFtsSyncTriggers(db);
            }

            @Override // androidx.room.RoomOpenHelper.Delegate
            public void onPostMigrate(final SupportSQLiteDatabase db) {
            }

            @Override // androidx.room.RoomOpenHelper.Delegate
            public RoomOpenHelper.ValidationResult onValidateSchema(final SupportSQLiteDatabase db) {
                HashMap<String, TableInfo.Column> _columnsCachedMaterial = new HashMap<>(7);
                _columnsCachedMaterial.put("code", new TableInfo.Column("code", "TEXT", true, 1, null, 1));
                _columnsCachedMaterial.put(HintConstants.AUTOFILL_HINT_NAME, new TableInfo.Column(HintConstants.AUTOFILL_HINT_NAME, "TEXT", true, 0, null, 1));
                _columnsCachedMaterial.put("spec", new TableInfo.Column("spec", "TEXT", false, 0, null, 1));
                _columnsCachedMaterial.put("unit", new TableInfo.Column("unit", "TEXT", false, 0, null, 1));
                _columnsCachedMaterial.put("stock", new TableInfo.Column("stock", "REAL", true, 0, null, 1));
                _columnsCachedMaterial.put("warehouseCode", new TableInfo.Column("warehouseCode", "TEXT", false, 0, null, 1));
                _columnsCachedMaterial.put("updatedAt", new TableInfo.Column("updatedAt", "INTEGER", true, 0, null, 1));
                HashSet<TableInfo.ForeignKey> _foreignKeysCachedMaterial = new HashSet<>(0);
                HashSet<TableInfo.Index> _indicesCachedMaterial = new HashSet<>(0);
                TableInfo _infoCachedMaterial = new TableInfo("cached_material", _columnsCachedMaterial, _foreignKeysCachedMaterial, _indicesCachedMaterial);
                TableInfo _existingCachedMaterial = TableInfo.read(db, "cached_material");
                if (!_infoCachedMaterial.equals(_existingCachedMaterial)) {
                    return new RoomOpenHelper.ValidationResult(false, "cached_material(com.factory.wms.data.local.CachedMaterialEntity).\n Expected:\n" + _infoCachedMaterial + "\n Found:\n" + _existingCachedMaterial);
                }
                HashMap<String, TableInfo.Column> _columnsPendingDocument = new HashMap<>(5);
                _columnsPendingDocument.put("id", new TableInfo.Column("id", "INTEGER", true, 1, null, 1));
                _columnsPendingDocument.put("type", new TableInfo.Column("type", "TEXT", true, 0, null, 1));
                _columnsPendingDocument.put("payloadJson", new TableInfo.Column("payloadJson", "TEXT", true, 0, null, 1));
                _columnsPendingDocument.put("createdAt", new TableInfo.Column("createdAt", "INTEGER", true, 0, null, 1));
                _columnsPendingDocument.put("lastError", new TableInfo.Column("lastError", "TEXT", false, 0, null, 1));
                HashSet<TableInfo.ForeignKey> _foreignKeysPendingDocument = new HashSet<>(0);
                HashSet<TableInfo.Index> _indicesPendingDocument = new HashSet<>(0);
                TableInfo _infoPendingDocument = new TableInfo("pending_document", _columnsPendingDocument, _foreignKeysPendingDocument, _indicesPendingDocument);
                TableInfo _existingPendingDocument = TableInfo.read(db, "pending_document");
                if (!_infoPendingDocument.equals(_existingPendingDocument)) {
                    return new RoomOpenHelper.ValidationResult(false, "pending_document(com.factory.wms.data.local.PendingDocumentEntity).\n Expected:\n" + _infoPendingDocument + "\n Found:\n" + _existingPendingDocument);
                }
                return new RoomOpenHelper.ValidationResult(true, null);
            }
        }, "3f107a8cd2b0b22c48e3187847e42984", "2171b0c170bc4452f72fb232c6e50f92");
        SupportSQLiteOpenHelper.Configuration _sqliteConfig = SupportSQLiteOpenHelper.Configuration.builder(config.context).name(config.name).callback(_openCallback).build();
        SupportSQLiteOpenHelper _helper = config.sqliteOpenHelperFactory.create(_sqliteConfig);
        return _helper;
    }

    @Override // androidx.room.RoomDatabase
    protected InvalidationTracker createInvalidationTracker() {
        HashMap<String, String> _shadowTablesMap = new HashMap<>(0);
        HashMap<String, Set<String>> _viewTables = new HashMap<>(0);
        return new InvalidationTracker(this, _shadowTablesMap, _viewTables, "cached_material", "pending_document");
    }

    @Override // androidx.room.RoomDatabase
    public void clearAllTables() {
        super.assertNotMainThread();
        SupportSQLiteDatabase _db = super.getOpenHelper().getWritableDatabase();
        try {
            super.beginTransaction();
            _db.execSQL("DELETE FROM `cached_material`");
            _db.execSQL("DELETE FROM `pending_document`");
            super.setTransactionSuccessful();
        } finally {
            super.endTransaction();
            _db.query("PRAGMA wal_checkpoint(FULL)").close();
            if (!_db.inTransaction()) {
                _db.execSQL("VACUUM");
            }
        }
    }

    @Override // androidx.room.RoomDatabase
    protected Map<Class<?>, List<Class<?>>> getRequiredTypeConverters() {
        HashMap<Class<?>, List<Class<?>>> _typeConvertersMap = new HashMap<>();
        _typeConvertersMap.put(WmsDao.class, WmsDao_Impl.getRequiredConverters());
        return _typeConvertersMap;
    }

    @Override // androidx.room.RoomDatabase
    public Set<Class<? extends AutoMigrationSpec>> getRequiredAutoMigrationSpecs() {
        HashSet<Class<? extends AutoMigrationSpec>> _autoMigrationSpecsSet = new HashSet<>();
        return _autoMigrationSpecsSet;
    }

    @Override // androidx.room.RoomDatabase
    public List<Migration> getAutoMigrations(final Map<Class<? extends AutoMigrationSpec>, AutoMigrationSpec> autoMigrationSpecs) {
        List<Migration> _autoMigrations = new ArrayList<>();
        return _autoMigrations;
    }

    @Override // com.factory.wms.data.local.WmsDatabase
    public WmsDao dao() {
        WmsDao wmsDao;
        if (this._wmsDao != null) {
            return this._wmsDao;
        }
        synchronized (this) {
            if (this._wmsDao == null) {
                this._wmsDao = new WmsDao_Impl(this);
            }
            wmsDao = this._wmsDao;
        }
        return wmsDao;
    }
}
