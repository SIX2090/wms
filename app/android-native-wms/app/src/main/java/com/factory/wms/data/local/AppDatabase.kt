package com.factory.wms.data.local

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase

@Database(
    entities = [MaterialEntity::class, OperationLogEntity::class],
    version = 1,
    exportSchema = false
)
abstract class AppDatabase : RoomDatabase() {

    abstract fun materialDao(): MaterialDao
    abstract fun operationLogDao(): OperationLogDao

    companion object {
        @Volatile
        private var INSTANCE: AppDatabase? = null

        fun getDatabase(context: Context): AppDatabase {
            return INSTANCE ?: synchronized(this) {
                val instance = Room.databaseBuilder(
                    context.applicationContext,
                    AppDatabase::class.java,
                    "wms_database"
                )
                    // 不允许破坏性迁移：schema 变更必须显式升级，避免静默清空本地缓存数据
                    .build()
                INSTANCE = instance
                instance
            }
        }
    }
}