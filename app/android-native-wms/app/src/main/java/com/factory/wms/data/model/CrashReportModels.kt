package com.factory.wms.data.model

import com.google.gson.annotations.SerializedName

/**
 * AI-MOB-CRASH-01：移动端崩溃上报请求体。
 *
 * 与后端 `POST /api/mobile/crash_report`（app/routes/native_api.py 的
 * CrashReportRequest，pydantic）字段一一对应、长度上限一致——超任一上限
 * 后端直接 400，故 Android 侧在 CrashReporter 里已按同口径截断，不会触发。
 *
 * 该模型同时用作本地待上报文件的落盘格式（Gson 序列化到 filesDir/crash/），
 * 存储格式 == 上报格式，下次启动读回原样上报，无需二次映射。
 */
data class CrashReportRequest(
    @SerializedName("app_version") val appVersion: String,
    @SerializedName("version_code") val versionCode: Int,
    @SerializedName("android_sdk") val androidSdk: Int,
    @SerializedName("device") val device: String,
    @SerializedName("thread") val thread: String,
    @SerializedName("exception") val exception: String,
    @SerializedName("stacktrace") val stacktrace: String,
    @SerializedName("occurred_at") val occurredAt: Long
)
