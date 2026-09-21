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
    version = 2,
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
         * BUG-2026-09-13-023（启动崩溃）：本方法在 WmsRepository 构造期同步执行，
         * 而 WmsRepository 又在 11 个 ViewModel 的构造期被创建（AppNavGraph 组合阶段），
         * 因此任何建库异常都会直接冒泡到主线程导致闪退。
         *
         * 已知触发场景：本地库文件损坏 / 迁移缺失（本项目未启用
         * fallbackToDestructiveMigration）/ 磁盘空间不足。
         * 策略：先删库再重建一次；仍失败则把异常抛出（此时属环境级故障，
         * 由上层 WmsRepository 的调用点继续兜底）。
         *
         * BUG-2026-09-21-005（删库丢单）：本库除物料缓存/操作日志（可重建）外还有
         * **pending_operations——工人已提交、尚未同步的离线单据，是不可重建的业务数据**。
         * 因此删库前必须尽最大努力备份队列表（见 [backupPendingOperations]），
         * 重建后原样回补（见 [restorePendingOperations]）；备份失败说明原文件本就
         * 不可读（物理损坏），数据在删库前已经丢失，但必须 ERROR 级大声记录让人知道，
         * 不得静默（R5）。物料缓存/操作日志可联网重建，无需备份。
         */
        fun getDatabase(context: Context): AppDatabase {
            return INSTANCE ?: synchronized(this) {
                INSTANCE?.let { return@synchronized it }
                val appContext = context.applicationContext
                val instance = try {
                    buildDatabase(appContext)
                } catch (e: Exception) {
                    Log.w(
                        "AppDatabase",
                        "建库失败，尝试删除本地库重建: ${e.javaClass.simpleName}: ${e.message}"
                    )
                    rebuildPreservingQueue(appContext)
                }
                INSTANCE = instance
                instance
            }
        }

        /**
         * BUG-2026-09-21-005：删库重建恢复路径（从 getDatabase 的 catch 抽出以便直接测试）。
         *
         * 顺序铁律：**先备份离线待同步队列 → 再删库 → 重建 → 原样回补**。
         * 端到端测试直接调用本函数验证保单链路，不依赖"Room 对特定坏文件何时抛异常"
         * 的内部行为（不同 Android/Room 版本触发点不同，属环境依赖，不可测）。
         */
        internal fun rebuildPreservingQueue(appContext: Context): AppDatabase {
            val backup = backupPendingOperations(appContext)
            appContext.deleteDatabase(DB_NAME)
            val rebuilt = buildDatabase(appContext)
            restorePendingOperations(rebuilt, backup)
            return rebuilt
        }

        /**
         * BUG-2026-09-21-005：删库前用**原生 SQLite 只读**打开旧库备份 pending_operations。
         *
         * 为什么绕开 Room：到达本分支说明 Room 打开失败（identity hash 校验 / 迁移缺失
         * 是最常见触发点），再经 Room 读同一份文件只会再次失败；而原生 SQLite 不做
         * schema 校验，只要文件本身可读就能取出数据。
         *
         * 返回空列表的两种正常情形：库文件不存在（全新安装）；表不存在
         * （v1 老库尚无队列表，本就无单可丢）。备份本身抛异常（文件物理损坏）
         * 说明数据在删库前已不可读——记 ERROR 后返回空，不阻断恢复流程。
         */
        internal fun backupPendingOperations(context: Context): List<PendingOperationEntity> {
            val dbFile = context.getDatabasePath(DB_NAME)
            if (!dbFile.isFile) return emptyList()
            // Room 默认以 WAL 模式打开库，而 OPEN_READONLY 打开 WAL 库可能因无法恢复
            // WAL 索引直接失败（SQLiteCantOpenDatabaseException）——先只读、失败回退
            // 读写打开（读写打开会正常完成 WAL 恢复），两档都失败才认定文件不可读。
            val raw = openRawDatabase(dbFile.absolutePath, SQLiteDatabase.OPEN_READONLY)
                ?: openRawDatabase(dbFile.absolutePath, SQLiteDatabase.OPEN_READWRITE)
            if (raw == null) {
                Log.e(
                    "AppDatabase",
                    "离线待同步单据备份失败（原库文件不可读，未同步记录在删库前已无法取出）"
                )
                return emptyList()
            }
            return runCatching {
                raw.use { db ->
                    val hasTable = db.rawQuery(
                        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='pending_operations' LIMIT 1",
                        null
                    ).use { it.moveToFirst() }
                    if (!hasTable) return@use emptyList()
                    db.rawQuery(
                        "SELECT request_id, operation_type, payload_json, warehouse_code, " +
                            "summary, status, attempt_count, last_error, created_at, updated_at " +
                            "FROM pending_operations",
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
                                    updatedAt = c.getLong(9)
                                )
                            )
                        }
                        rows
                    }
                }
            }.onSuccess { rows ->
                if (rows.isNotEmpty()) {
                    Log.w("AppDatabase", "删库重建前已备份 ${rows.size} 条离线待同步单据")
                }
            }.getOrElse { err ->
                Log.e(
                    "AppDatabase",
                    "离线待同步单据备份失败（读取异常，未同步记录在删库前已无法取出）: " +
                        "${err.javaClass.simpleName}: ${err.message}"
                )
                emptyList()
            }
        }

        /** 以指定标志打开原始库文件，失败返回 null（调用方负责降级与告警）。 */
        private fun openRawDatabase(path: String, flags: Int): SQLiteDatabase? =
            runCatching {
                SQLiteDatabase.openDatabase(path, null, flags)
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
                .build()
                // BUG-2026-09-21-005：构建后立即真实打开一次库文件。Room 默认惰性打开
                // （首次 DAO 调用才触发 onCreate/onUpgrade/identity-hash 校验），若不强制
                // 打开，"库损坏/迁移缺失"的异常会推迟到 ViewModel 组合期的某次 DAO 调用
                // 随机爆出（正是 BUG-2026-09-13-023 的闪退路径），getDatabase 的
                // 删库恢复分支根本走不到。在此打开，恢复分支才对触发场景真实可达。
                .also { it.openHelper.writableDatabase }
    }
}