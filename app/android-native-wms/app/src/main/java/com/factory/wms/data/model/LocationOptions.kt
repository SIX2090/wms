package com.factory.wms.data.model

import com.google.gson.annotations.SerializedName

data class LocationOptions(
    val enabled: Boolean? = null,
    val items: List<String>? = null,
    @SerializedName("default_location") val defaultLocation: String? = null,
    val total: Int? = null,
    val page: Int? = null,
    @SerializedName("page_size") val pageSize: Int? = null,
    @SerializedName("total_pages") val totalPages: Int? = null
)
