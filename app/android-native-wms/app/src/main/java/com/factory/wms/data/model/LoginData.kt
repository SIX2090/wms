package com.factory.wms.data.model

import com.google.gson.annotations.SerializedName

data class LoginData(
    val token: String,
    @SerializedName("expires_in") val expiresIn: Int,
    val user: UserInfo
)

data class UserInfo(
    val id: Int,
    val username: String,
    val name: String?,
    val role: String?
)