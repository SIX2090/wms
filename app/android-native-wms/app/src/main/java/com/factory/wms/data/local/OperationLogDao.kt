package com.factory.wms.data.local

import androidx.room.*

@Dao
interface OperationLogDao {

    @Query("SELECT * FROM operation_logs ORDER BY timestamp DESC")
    suspend fun getAll(): List<OperationLogEntity>

    @Query("SELECT * FROM operation_logs WHERE operation_type = :type ORDER BY timestamp DESC")
    suspend fun getByType(type: String): List<OperationLogEntity>

    @Insert
    suspend fun insert(log: OperationLogEntity)

    @Query("DELETE FROM operation_logs")
    suspend fun deleteAll()
}