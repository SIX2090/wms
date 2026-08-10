package com.factory.wms.data.model

import com.google.gson.annotations.SerializedName

/**
 * 物料档案搜索结果项（后端 /mobile/api/material_archive/search 返回）。
 */
data class MaterialArchiveDto(
    val id: Int?,
    val code: String?,
    val name: String?,
    val spec: String?,
    val unit: String?,
    val category: String?,
    @SerializedName("image_count") val imageCount: Int?
)

/**
 * 物料档案图片（后端 /mobile/api/material_archive 图片列表/上传返回的单条记录）。
 */
data class MaterialArchiveImageDto(
    val id: Int?,
    val image: String?,
    @SerializedName("sort_order") val sortOrder: Int?,
    @SerializedName("created_at") val createdAt: String?,
    val url: String?
)

/**
 * 某物料的档案图片列表数据：material 为物料基础信息，images 为全部图片。
 */
data class MaterialArchiveImagesData(
    val material: MaterialArchiveDto?,
    val images: List<MaterialArchiveImageDto>?
)