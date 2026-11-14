package com.factory.wms.update

import com.google.gson.JsonParser
import com.google.gson.JsonObject
import okhttp3.HttpUrl
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull
import java.io.File
import java.security.MessageDigest

internal const val UPDATE_REPO = "SIX2090/wms"
internal const val UPDATE_API = "https://api.github.com/repos/$UPDATE_REPO"
internal const val STABLE_PREFIX = "android-stable-v"
internal const val MAX_APK_BYTES = 150L * 1024 * 1024

internal data class UpdateRelease(
    val packageName: String, val versionCode: Long, val versionName: String,
    val minSdk: Int, val url: String, val size: Long, val sha256: String,
    val certificateSha256: String, val commitSha: String, val notes: String
) {
    val tag: String get() = "$STABLE_PREFIX$versionCode-$commitSha"

    // Explicit keys survive R8 field obfuscation; this is also our persisted protocol.
    fun toJson(): String = JsonObject().apply {
        addProperty("packageName", packageName); addProperty("versionCode", versionCode)
        addProperty("versionName", versionName); addProperty("minSdk", minSdk)
        addProperty("url", url); addProperty("size", size); addProperty("sha256", sha256)
        addProperty("certificateSha256", certificateSha256); addProperty("commitSha", commitSha)
        addProperty("notes", notes)
    }.toString()

    fun validate(currentPackage: String, currentVersion: Long, sdk: Int) {
        require(packageName == currentPackage) { "更新包名不匹配" }
        require(versionCode > currentVersion) { "当前已是最新版本" }
        require(minSdk in 26..sdk) { "手机系统版本不支持此更新" }
        require(versionName.isNotBlank() && versionName.length <= 80) { "更新版本信息无效" }
        require(size in 1..MAX_APK_BYTES) { "更新包大小异常" }
        require(Regex("[0-9a-f]{64}").matches(sha256) &&
            Regex("[0-9a-f]{64}").matches(certificateSha256) &&
            Regex("[0-9a-f]{40}").matches(commitSha)) { "更新校验信息无效" }
        val download = checkedUpdateUrl(url)
        require(download.host == "github.com" && download.encodedPath.startsWith(
            "/$UPDATE_REPO/releases/download/android-apk-") &&
            download.encodedPath.endsWith("/wms-mobile-scan.apk")) { "更新地址未绑定发行产物" }
    }

    companion object {
        fun parse(body: String): UpdateRelease {
            val obj = JsonParser.parseString(body).asJsonObject
            return UpdateRelease(obj["packageName"].asString, obj["versionCode"].asLong,
                obj["versionName"].asString, obj["minSdk"].asInt, obj["url"].asString,
                obj["size"].asLong, obj["sha256"].asString, obj["certificateSha256"].asString,
                obj["commitSha"].asString, obj["notes"].asString.take(2000))
        }
    }
}

/** Exact hosts, TLS only, no credentials, arbitrary ports or URL fragments. */
internal fun checkedUpdateUrl(value: String): HttpUrl {
    val url = requireNotNull(value.toHttpUrlOrNull()) { "更新地址无效" }
    require(url.isHttps && url.port == 443 && url.username.isEmpty() &&
        url.password.isEmpty() && url.fragment == null && url.host in setOf(
            "api.github.com", "github.com", "release-assets.githubusercontent.com",
            "objects.githubusercontent.com")) { "更新地址不在可信 HTTPS 范围" }
    return url
}

internal fun File.sha256(): String = inputStream().use { stream ->
    val digest = MessageDigest.getInstance("SHA-256")
    val buffer = ByteArray(64 * 1024)
    while (true) {
        val count = stream.read(buffer)
        if (count < 0) break
        digest.update(buffer, 0, count)
    }
    digest.digest().joinToString("") { "%02x".format(it) }
}
