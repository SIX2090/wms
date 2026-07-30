package com.factory.wms.data.local

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "operation_logs")
data class OperationLogEntity(
    @PrimaryKey(autoGenerate = true)
    val id: Long = 0,

    @ColumnInfo(name = "operation_type")
    val operationType: String, // "inbound", "outbound", "stocktake"

    @ColumnInfo(name = "order_no")
    val orderNo: String?,

    @ColumnInfo(name = "material_code")
    val materialCode: String?,

    @ColumnInfo(name = "quantity")
    val quantity: Double?,

    @ColumnInfo(name = "timestamp")
    val timestamp: Long = System.currentTimeMillis()
)