package com.factory.wms.update

import com.google.gson.JsonParser
import okhttp3.Call
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import java.io.File
import java.io.IOException
import java.util.concurrent.TimeUnit

/** Deliberately independent of RetrofitClient, its tokens, cookie jar and interceptors. */
internal class UpdateDownloadClient(private val calls: Call.Factory = client()) {
    private fun response(address: String): Response {
        var url = checkedUpdateUrl(address)
        repeat(6) {
            val response = calls.newCall(Request.Builder().url(url)
                .header("Accept", "application/vnd.github+json")
                .header("User-Agent", "WMS-Android-Updater").build()).execute()
            if (response.code in listOf(301, 302, 303, 307, 308)) {
                val next = response.header("Location")
                response.close()
                url = checkedUpdateUrl(requireNotNull(next?.let { url.resolve(it)?.toString() }) {
                    "更新下载跳转无效"
                })
            } else {
                if (!response.isSuccessful) {
                    val code = response.code
                    response.close()
                    throw IOException("更新服务暂不可用（HTTP $code），可稍后重试")
                }
                return response
            }
        }
        throw IOException("更新下载跳转次数过多")
    }

    private fun json(address: String): String = response(address).use { response ->
        val stream = requireNotNull(response.body).byteStream()
        val bytes = stream.readBytesLimited(1024 * 1024)
        bytes.toString(Charsets.UTF_8)
    }

    fun latest(): UpdateRelease? {
        // matching-refs is a prefix lookup, not the first page of all repository releases.
        val refs = JsonParser.parseString(json("$UPDATE_API/git/matching-refs/tags/$STABLE_PREFIX"))
            .asJsonArray
        val tags = refs.mapNotNull { entry ->
            val ref = entry.asJsonObject["ref"].asString.removePrefix("refs/tags/")
            Regex("android-stable-v([1-9][0-9]*)-([0-9a-f]{40})").matchEntire(ref)
                ?.let { Triple(it.groupValues[1].toLong(), ref, it.groupValues[2]) }
        }.sortedByDescending { it.first }
        for ((code, tag, sha) in tags) {
            val release = JsonParser.parseString(json("$UPDATE_API/releases/tags/$tag")).asJsonObject
            if (release["draft"].asBoolean || release["prerelease"].asBoolean) continue
            val metadata = UpdateRelease.parse(release["body"].asString)
            require(metadata.tag == tag && metadata.versionCode == code && metadata.commitSha == sha &&
                release["target_commitish"].asString == sha) { "稳定版本来源不匹配" }
            return metadata
        }
        return null
    }

    fun download(release: UpdateRelease, destination: File, progress: (Int) -> Unit) {
        require(release.size in 1..MAX_APK_BYTES)
        val temporary = File(destination.parentFile, destination.name + ".part")
        try {
            response(release.url).use { response ->
                val body = requireNotNull(response.body)
                require(body.contentLength() == -1L || body.contentLength() == release.size) {
                    "更新包长度不匹配"
                }
                body.byteStream().use { source -> temporary.outputStream().use { output ->
                    val buffer = ByteArray(64 * 1024)
                    var total = 0L
                    var last = -1
                    while (true) {
                        val count = source.read(buffer)
                        if (count < 0) break
                        total += count
                        require(total <= release.size) { "更新包超过预期大小" }
                        output.write(buffer, 0, count)
                        val percent = (total * 100 / release.size).toInt()
                        if (last != percent) { progress(percent); last = percent }
                    }
                    require(total == release.size) { "更新包未下载完整" }
                } }
            }
            require(temporary.sha256() == release.sha256) { "更新包校验失败，请重新下载" }
            java.nio.file.Files.move(temporary.toPath(), destination.toPath(),
                java.nio.file.StandardCopyOption.REPLACE_EXISTING,
                java.nio.file.StandardCopyOption.ATOMIC_MOVE)
        } finally { temporary.delete() }
    }

    companion object {
        fun client(): OkHttpClient = OkHttpClient.Builder()
            .followRedirects(false).followSslRedirects(false)
            .connectTimeout(15, TimeUnit.SECONDS).readTimeout(30, TimeUnit.SECONDS)
            .callTimeout(5, TimeUnit.MINUTES).build()
    }
}

private fun java.io.InputStream.readBytesLimited(limit: Int): ByteArray {
    val output = java.io.ByteArrayOutputStream()
    val buffer = ByteArray(8192)
    while (true) {
        val count = read(buffer)
        if (count < 0) break
        require(output.size() + count <= limit) { "更新清单过大" }
        output.write(buffer, 0, count)
    }
    return output.toByteArray()
}
