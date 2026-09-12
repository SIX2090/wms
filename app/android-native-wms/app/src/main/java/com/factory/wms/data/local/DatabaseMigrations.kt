package com.factory.wms.data.local

import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase

/**
 * 集中管理 Room schema 的显式迁移。
 *
 * 已禁用破坏性迁移（fallbackToDestructiveMigration），因此任何 schema 版本变更
 * 都必须在此新增一个 [Migration]，并把新版本号加入 [ALL]；否则已安装应用升级时
 * 会抛 IllegalStateException 而非静默清空本地缓存 / 操作日志。
 *
 * 约定：schema 版本号 +1 时，必须同步满足两处——
 *   1. [AppDatabase] 的 @Database(version = N) 提升到 N；
 *   2. 在 [ALL] 中追加一条从 (N-1 -> N) 的迁移。
 */
object DatabaseMigrations {

    /**
     * v1 -> v2：新增离线待提交作业队列表（AI-MOB-OFFLINE-01）。
     *
     * 关键点：**纯新增表迁移，不触碰 materials / operation_logs 任何数据**。
     * 升级路径只执行 CREATE TABLE + CREATE INDEX，既有本地物料缓存与操作日志
     * 原样保留——丢缓存会直接导致断网时扫不了码，是必须避免的回归。
     *
     * DDL 必须与 [PendingOperationEntity] 的 Room 生成结果严格一致，否则 Room 的
     * schema 校验（identity hash 比对）会在打开数据库时报
     * "Migration didn't properly handle ..."。要点：
     *   - 列顺序与实体声明顺序一致
     *   - warehouse_code / last_error 可为 NULL（实体声明为 `String?`）
     *   - 其余列 NOT NULL，且**不写数据库级 DEFAULT**（Room 未标注 defaultValue 时
     *     即不生成 DEFAULT，多写反而导致 schema 不匹配）
     *   - 索引名遵循 Room 约定：index_pending_operations_<列名>_<列名>
     */
    private val MIGRATION_1_2 = object : Migration(1, 2) {
        override fun migrate(db: SupportSQLiteDatabase) {
            db.execSQL(
                "CREATE TABLE IF NOT EXISTS `pending_operations` (" +
                    "`request_id` TEXT NOT NULL, " +
                    "`operation_type` TEXT NOT NULL, " +
                    "`payload_json` TEXT NOT NULL, " +
                    "`warehouse_code` TEXT, " +
                    "`summary` TEXT NOT NULL, " +
                    "`status` TEXT NOT NULL, " +
                    "`attempt_count` INTEGER NOT NULL, " +
                    "`last_error` TEXT, " +
                    "`created_at` INTEGER NOT NULL, " +
                    "`updated_at` INTEGER NOT NULL, " +
                    "PRIMARY KEY(`request_id`))"
            )
            db.execSQL(
                "CREATE INDEX IF NOT EXISTS `index_pending_operations_status_created_at` " +
                    "ON `pending_operations` (`status`, `created_at`)"
            )
            db.execSQL(
                "CREATE INDEX IF NOT EXISTS `index_pending_operations_operation_type` " +
                    "ON `pending_operations` (`operation_type`)"
            )
        }
    }

    /**
     * 全部已登记的迁移，按 (fromVersion -> toVersion) 顺序排列。
     *
     * **声明位置必须在各 [Migration] 常量之后**：Kotlin `object` 的属性初始化
     * 严格按源码顺序执行，若 [ALL] 写在 [MIGRATION_1_2] 之前，初始化 [ALL] 时
     * [MIGRATION_1_2] 仍为 null，编译期即报
     * "variable 'MIGRATION_1_2' must be initialized"（BUG-2026-09-12-006）。
     * 新增迁移时请追加到本行之前，切勿把本条上移。
     */
    val ALL: Array<Migration> = arrayOf(
        MIGRATION_1_2
    )
}
