package com.factory.wms.data.model

import com.google.gson.annotations.SerializedName

data class ApiEnvelope<T>(
    @SerializedName("status") val status: String?,
    @SerializedName("success") val success: Boolean?,
    @SerializedName("msg") val msg: String?,
    @SerializedName("message") val message: String?,
    @SerializedName("data") val data: T?
) {
    fun isOk(): Boolean = success == true || status == "success"

    fun displayMessage(): String = message ?: msg ?: if (isOk()) "操作成功" else "操作失败"
}