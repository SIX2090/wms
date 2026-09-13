package com.factory.wms.data.model

import com.google.gson.annotations.SerializedName

data class LocationOptions(
    val enabled: Boolean? = null,
    val items: List<String>? = null,
    @SerializedName("default_location") val defaultLocation: String? = null,
    @SerializedName("total_pages") val totalPages: Int? = null
)
