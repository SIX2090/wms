package com.factory.wms.data.local

import androidx.room.migration.Migration

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

    /** 全部已登记的迁移，按 (fromVersion -> toVersion) 顺序排列。 */
    val ALL: Array<Migration> = arrayOf(
        // 示例：v1 -> v2 新增字段时启用下面这条
        // MIGRATION_1_2
    )

    // 示例写法（未来 schema 变更时解除注释并实现）：
    //
    // private val MIGRATION_1_2 = object : Migration(1, 2) {
    //     override fun migrate(db: SupportSQLiteDatabase) {
    //         db.execSQL("ALTER TABLE materials ADD COLUMN new_field TEXT DEFAULT NULL")
    //         // 需要新增/重建索引、表时同样在此执行对应 SQL
    //     }
    // }
}