package com.factory.wms.data.model

/** Frozen body and original key for a user-confirmed write whose response is not yet known. */
data class PendingNativeWrite(
    val operation: String,
    val requestId: String,
    val payloadJson: String,
    val createdAt: Long = System.currentTimeMillis(),
    val responseJson: String? = null
)
