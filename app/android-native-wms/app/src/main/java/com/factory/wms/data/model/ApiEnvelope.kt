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

    /**
     * 取后端 message/msg 字段作为提示消息，已做长度截断（≤200 字符）和 HTML 标签过滤，
     * 防止恶意后端（或中间人）注入超长文本 / <script>/<img> 标签影响 UI。
     *
     * P2-D: ApiEnvelope.displayMessage() 加固
     */
    fun displayMessage(): String {
        val raw = message ?: msg ?: if (isOk()) "操作成功" else "操作失败"
        return sanitizeMessage(raw)
    }

    companion object {
        /** 提示消息最大长度（字符），超出部分截断并加 "..."。 */
        const val MAX_DISPLAY_MESSAGE_LENGTH: Int = 200

        /**
         * 清洗后端返回的提示消息：
         * 1) 去除前后空白
         * 2) 过滤 HTML/XML 标签（含 <script>、<img onerror=>、<a href=javascript:> 等）
         * 3) 长度截断（保留可读性，避免超长消息撑爆 Snackbar/AlertDialog）
         */
        internal fun sanitizeMessage(raw: String): String {
            val trimmed = raw.trim()
            if (trimmed.isEmpty()) return trimmed
            // 1) 过滤 HTML/XML 标签：<...> 形式（含属性、闭合标签、自闭合标签）
            //    使用非贪婪匹配 + 容忍嵌套属性
            val noTags = Regex("<[^>]+>").replace(trimmed, "")
            // 2) 二次过滤：去掉残留的 HTML 实体编码（防止 &lt;script&gt; 绕过）
            //    仅去掉 < > " ' & 五个高风险实体即可
            val decoded = noTags
                .replace("&lt;", "<")
                .replace("&gt;", ">")
                .replace("&quot;", "\"")
                .replace("&#39;", "'")
                .replace("&apos;", "'")
                .replace("&amp;", "&")
            val reFiltered = Regex("<[^>]+>").replace(decoded, "")
            // 3) 长度截断
            return if (reFiltered.length > MAX_DISPLAY_MESSAGE_LENGTH) {
                reFiltered.substring(0, MAX_DISPLAY_MESSAGE_LENGTH) + "..."
            } else {
                reFiltered
            }
        }
    }
}