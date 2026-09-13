package com.factory.wms.data.local

import android.content.Context
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
         * fallbackToDestructiveMigration）/ 磁盘空间不足。本地库只存放物料缓存与
         * 操作日志，**属于可重建数据**，不值得为它牺牲 App 启动。
         * 策略：先删库再重建一次；仍失败则把异常抛出（此时属环境级故障，
         * 由上层 WmsRepository 的调用点继续兜底）。
         */
        fun getDatabase(context: Context): AppDatabase {
            return INSTANCE ?: synchronized(this) {
                INSTANCE?.let { return@synchronized it }
                val appContext = context.applicationContext
                val instance = try {
                    buildDatabase(appContext)
                } catch (e: Exception) {
                    android.util.Log.w(
                        "AppDatabase",
                        "建库失败，尝试删除本地库重建: ${e.javaClass.simpleName}: ${e.message}"
                    )
                    appContext.deleteDatabase(DB_NAME)
                    buildDatabase(appContext)
                }
                INSTANCE = instance
                instance
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
    }
}