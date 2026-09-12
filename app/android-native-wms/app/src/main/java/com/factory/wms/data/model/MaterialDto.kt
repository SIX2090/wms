package com.factory.wms.data.model

import com.google.gson.annotations.SerializedName
import kotlin.jvm.Transient

data class MaterialDto(
    val id: Int?,
    val code: String?,
    val name: String?,
    val brand: String?,
    val spec: String?,
    val unit: String?,
    val category: String?,
    val supplier: String?,
    val stock: Double?,
    val price: Double?,
    @SerializedName("min_stock") val minStock: Double?,
    @SerializedName("reorder_point") val reorderPoint: Double?,
    // BUG-2026-09-10-003：库位分布（开启库位管理时后端下发，未开启为空列表）。
    // 默认 null 保持 MaterialEntity.toDto() 等存量构造调用兼容。
    @SerializedName("locations") val locations: List<MaterialLocationDto>? = null,

    // AI-MOB-OFFLINE-HINT-01：本条是否为**本地缓存回退**数据。
    // 后端不下发这两个字段（@Transient 由 Gson 处理，不参与序列化往返），
    // 由 WmsRepository.getMaterialInfo 在「网络失败 → 读 Room 缓存」分支里置位。
    //
    // 为什么必须有：回退到缓存时若不给任何标记，UI 无法区分"实时库存 5"
    // 与"三天前的库存 5"。用户看到数字就出库 5 —— 这是**业务风险**，不是体验问题。
    @Transient val fromCache: Boolean = false,
    /** 缓存写入时间（epoch millis），仅 [fromCache] 为 true 时有意义。 */
    @Transient val cachedAtMillis: Long? = null
)

/** 单个库位的库存量（查库存结果卡「库位分布」展示）。 */
data class MaterialLocationDto(
    @SerializedName("location") val location: String?,
    @SerializedName("quantity") val quantity: Double?
)
