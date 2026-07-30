package com.factory.wms.data.local

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "materials")
data class MaterialEntity(
    @PrimaryKey
    @ColumnInfo(name = "code")
    val code: String,

    @ColumnInfo(name = "name")
    val name: String?,

    @ColumnInfo(name = "spec")
    val spec: String?,

    @ColumnInfo(name = "unit")
    val unit: String?,

    @ColumnInfo(name = "stock")
    val stock: Double?,

    @ColumnInfo(name = "price")
    val price: Double?,

    @ColumnInfo(name = "category")
    val category: String?,

    @ColumnInfo(name = "supplier")
    val supplier: String?,

    @ColumnInfo(name = "min_stock")
    val minStock: Double?,

    @ColumnInfo(name = "reorder_point")
    val reorderPoint: Double?,

    @ColumnInfo(name = "last_sync_time")
    val lastSyncTime: Long = System.currentTimeMillis()
)