package com.factory.wms.data.local

import androidx.room.*

@Dao
interface MaterialDao {

    @Query("SELECT * FROM materials WHERE code = :code")
    suspend fun getByCode(code: String): MaterialEntity?

    @Query("SELECT * FROM materials")
    suspend fun getAll(): List<MaterialEntity>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(material: MaterialEntity)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertAll(materials: List<MaterialEntity>)

    @Delete
    suspend fun delete(material: MaterialEntity)

    @Query("DELETE FROM materials")
    suspend fun deleteAll()
}