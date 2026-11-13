package com.factory.wms.data.local

import android.content.ContentValues
import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.util.Log
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase

@Database(
    entities = [MaterialEntity::class, OperationLogEntity::class, PendingOperationEntity::class],
    version = 3,
    exportSchema = false
)
abstract class AppDatabase : RoomDatabase() {

    abstract fun materialDao(): MaterialDao
    abstract fun operationLogDao(): OperationLogDao

    /** AI-MOB-OFFLINE-01：离线待提交作业队列。 */
    abstract fun pendingOperationDao(): PendingOperationDao

    companion object {
        private const val DB_NAME = "wms_database"

        @Volatile
        private var INSTANCE: AppDatabase? = null

        /**
         * 本地库含不可重建的离线单据。打开、升级、降级或损坏时一律保留原库，
         * 禁止自动删库或破坏性迁移；异常由 WmsRepository 捕获后降级为无缓存模式，
         * 既不让启动崩溃，也不把失败暂存谎报为成功（11-08-012 / 09-21-005）。
         */
        fun getDatabase(context: Context): AppDatabase {
            return INSTANCE ?: synchronized(this) {
                INSTANCE?.let { return@synchronized it }
                val appContext = context.applicationContext
                val instance = try {
                    buildDatabase(appContext)
                } catch (e: Exception) {
                    Log.e(
                        "AppDatabase",
                        "本地库打开失败，原库已保留；离线作业需人工核对: ${e.javaClass.simpleName}: ${e.message}"
                    )
                    throw e
                }
                INSTANCE = instance
                instance
            }
        }

        /**
         * 历史保单诊断辅助：以原生 SQLite 读取队列，兼容 v2 无归属记录与 v3 归属字段。
         * 不接入启动恢复，不把空结果或读取失败作为可删库的证据；原文件始终保留。
         * 显式回补使用 restorePendingOperations；合成回归验证 WAL 及全部字段保真。
         */
        internal fun backupPendingOperations(context: Context): List<PendingOperationEntity> {
            val dbFile = context.getDatabasePath(DB_NAME)
            if (!dbFile.isFile) return emptyList()
            // Room 默认以 WAL 模式打开库，而 OPEN_READONLY 打开 WAL 库可能因无法恢复
            // WAL 索引直接失败（SQLiteCantOpenDatabaseException）——先只读、失败回退
            // 读写打开（读写打开会正常完成 WAL 恢复），两档都失败才认定文件不可读。
            fun readRows(db: SQLiteDatabase): List<PendingOperationEntity> {
                val hasTable = db.rawQuery(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='pending_operations' LIMIT 1",
                    null
                ).use { it.moveToFirst() }
                if (!hasTable) {
                    return emptyList()
                }
                return db.rawQuery(
                    "SELECT request_id, operation_type, payload_json, warehouse_code, " +
                        "summary, status, attempt_count, last_error, created_at, updated_at " +
                        ", * FROM pending_operations",
                    null
                ).use { c ->
                    val rows = mutableListOf<PendingOperationEntity>()
                    while (c.moveToNext()) {
                        rows.add(
                            PendingOperationEntity(
                                requestId = c.getString(0),
                                operationType = c.getString(1),
                                payloadJson = c.getString(2),
                                warehouseCode = if (c.isNull(3)) null else c.getString(3),
                                summary = c.getString(4),
                                status = c.getString(5),
                                attemptCount = c.getInt(6),
                                lastError = if (c.isNull(7)) null else c.getString(7),
                                createdAt = c.getLong(8),
                                updatedAt = c.getLong(9),
                                ownerServer = c.getColumnIndex("owner_server").takeIf { it >= 0 }?.let {
                                    if (c.isNull(it)) null else c.getString(it)
                                },
                                ownerUserId = c.getColumnIndex("owner_user_id").takeIf { it >= 0 }?.let {
                                    if (c.isNull(it)) null else c.getInt(it)
                                },
                                needsReview = c.getColumnIndex("needs_review").takeIf { it >= 0 }
                                    ?.let { c.getInt(it) != 0 } ?: true,
                                nextRetryAt = c.getColumnIndex("next_retry_at").takeIf { it >= 0 }
                                    ?.let { c.getLong(it) } ?: 0
                            )
                        )
                    }
                    rows
                }
            }

            // BUG-2026-10-08-014：OPEN_READONLY 打开成功但读到空也可能是 WAL 未恢复
            // （Robolectric 影子实现下，只读打开不执行 WAL recovery，直接读主文件——
            // 刚写入的行还在 -wal 侧车 → 读到空）。原回退只在「打开抛异常」时触发，
            // 「打开成功但读到空」不触发 → 备份静默为空 → 删库重建后单据全丢
            // （CI 三次复发：run #691/#692/#695/302b2c1/74eedaf/df97b0d）。
            // 修复：只读读到空且文件非空时，回退读写打开再读一次。
            val readonly = openRawDatabase(dbFile.absolutePath, SQLiteDatabase.OPEN_READONLY)
            if (readonly != null) {
                val rows = runCatching { readonly.use { readRows(it) } }.getOrElse { err ->
                    Log.e(
                        "AppDatabase",
                        "离线待同步单据备份失败（只读读取异常，原库已保留，待同步记录需人工核对）: " +
                            "${err.javaClass.simpleName}: ${err.message}"
                    )
                    emptyList()
                }
                if (rows.isNotEmpty()) {
                    Log.w("AppDatabase", "诊断读取离线队列 ${rows.size} 条离线待同步单据")
                    return rows
                }
                // 只读读到空：可能真无单，也可能 WAL 未恢复（Robolectric 影子实现下
                // 只读打开不执行 WAL recovery，刚写入的行还在 -wal 侧车 → 读到空）。
                // 文件非空时回退读写再确认——读写打开会正常完成 WAL 恢复。
                if (dbFile.length() > 0L) {
                    val rw = openRawDatabase(dbFile.absolutePath, SQLiteDatabase.OPEN_READWRITE)
                    if (rw != null) {
                        val rwRows = runCatching { rw.use { readRows(it) } }.getOrElse { err ->
                            Log.e(
                                "AppDatabase",
                                "只读备份为空后读写回退读取异常: ${err.javaClass.simpleName}: ${err.message}"
                            )
                            emptyList()
                        }
                        if (rwRows.isNotEmpty()) {
                            Log.w(
                                "AppDatabase",
                                "只读备份为空，读写回退备份 ${rwRows.size} 条离线待同步单据（WAL 未恢复）"
                            )
                            return rwRows
                        }
                        Log.w("AppDatabase", "只读与读写打开均读到空队列表（真无单可保）")
                    } else {
                        Log.e(
                            "AppDatabase",
                            "只读备份为空，且读写打开失败（库文件存在但不可读写），" +
                                "原库已保留，待同步记录需人工核对"
                        )
                    }
                }
                return rows
            }
            // 只读打开失败：回退读写（原有路径，读写打开完成 WAL 恢复）
            val rwFallback = openRawDatabase(dbFile.absolutePath, SQLiteDatabase.OPEN_READWRITE)
            if (rwFallback == null) {
                Log.e(
                    "AppDatabase",
                    "离线待同步单据备份失败（原库文件不可读，原库已保留，待同步记录需人工核对）"
                )
                return emptyList()
            }
            return runCatching {
                rwFallback.use { readRows(it) }
            }.onSuccess { rows ->
                if (rows.isNotEmpty()) {
                    Log.w("AppDatabase", "诊断读取离线队列 ${rows.size} 条离线待同步单据")
                }
            }.getOrElse { err ->
                Log.e(
                    "AppDatabase",
                    "离线待同步单据备份失败（读取异常，原库已保留，待同步记录需人工核对）: " +
                        "${err.javaClass.simpleName}: ${err.message}"
                )
                emptyList()
            }
        }

        /** 以指定标志打开原始库文件，失败返回 null（调用方负责降级与告警）。 */
        private fun openRawDatabase(path: String, flags: Int): SQLiteDatabase? =
            runCatching {
                SQLiteDatabase.openDatabase(path, null, flags) {
                    throw android.database.sqlite.SQLiteDatabaseCorruptException("原库已保留，禁止自动删库")
                }
            }.getOrNull()

        /**
         * BUG-2026-09-21-005：把备份的离线待同步单据回补进重建后的新库。
         *
         * 经 `openHelper.writableDatabase` 直写而非 DAO：本方法在 getDatabase 内同步
         * 执行（主线程，见上方 BUG-2026-09-13-023 说明），Room DAO 默认禁止主线程
         * 查询，而 SupportSQLiteDatabase 层无此限制；且走同一连接可避免"DAO 用到的
         * 实例尚未打开"的时序问题。恢复失败只记 ERROR 不抛出——不能因为回补失败
         * 让 App 再次无法启动（BUG-2026-09-13-023 的底线优先），失败必须让人知道（R5）。
         */
        internal fun restorePendingOperations(db: AppDatabase, rows: List<PendingOperationEntity>) {
            if (rows.isEmpty()) return
            runCatching {
                val writable = db.openHelper.writableDatabase
                writable.beginTransaction()
                try {
                    rows.forEach { row ->
                        val values = ContentValues().apply {
                            put("request_id", row.requestId)
                            put("operation_type", row.operationType)
                            put("payload_json", row.payloadJson)
                            put("warehouse_code", row.warehouseCode)
                            put("summary", row.summary)
                            put("status", row.status)
                            put("attempt_count", row.attemptCount)
                            put("last_error", row.lastError)
                            put("created_at", row.createdAt)
                            put("updated_at", row.updatedAt)
                            put("owner_server", row.ownerServer)
                            put("owner_user_id", row.ownerUserId)
                            put("needs_review", if (row.needsReview) 1 else 0)
                            put("next_retry_at", row.nextRetryAt)
                        }
                        writable.insert(
                            "pending_operations",
                            SQLiteDatabase.CONFLICT_REPLACE,
                            values
                        )
                    }
                    writable.setTransactionSuccessful()
                } finally {
                    writable.endTransaction()
                }
                Log.w("AppDatabase", "已从备份恢复 ${rows.size} 条离线待同步单据")
            }.onFailure { err ->
                Log.e(
                    "AppDatabase",
                    "离线待同步单据回补失败，需人工核查未同步数据: " +
                        "${err.javaClass.simpleName}: ${err.message}"
                )
            }
        }

        private fun buildDatabase(context: Context): AppDatabase =
            Room.databaseBuilder(
                context,
                AppDatabase::class.java,
                DB_NAME
            )
                // 不允许破坏性迁移：schema 变更必须显式升级，避免静默清空本地缓存数据。
                // 新增迁移请登记在 DatabaseMigrations.ALL，并同步提升 @Database(version)。
                .addMigrations(*DatabaseMigrations.ALL)
                .openHelperFactory(PreservingSQLiteOpenHelperFactory)
                .build()
                // BUG-2026-09-21-005：构建后立即真实打开一次库文件。Room 默认惰性打开
                // （首次 DAO 调用才触发 onCreate/onUpgrade/identity-hash 校验），若不强制
                // 打开，"库损坏/迁移缺失"的异常会推迟到 ViewModel 组合期的某次 DAO 调用
                // 随机爆出（正是 BUG-2026-09-13-023 的闪退路径），getDatabase 的
                // 删库恢复分支根本走不到。在此打开，恢复分支才对触发场景真实可达。
                .also {
                    try { it.openHelper.writableDatabase } catch (e: Exception) {
                        it.close()
                        throw e
                    }
                }
    }
}
