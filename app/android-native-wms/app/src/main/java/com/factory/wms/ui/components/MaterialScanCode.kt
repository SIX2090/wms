package com.factory.wms.ui.components

import java.net.URI
import java.net.URLDecoder

/** Labels open the live material page in WeChat and yield the code in every scanner. */
internal fun materialScanCode(raw: String): String {
    val value = raw.trim()
    return runCatching {
        val uri = URI(value)
        if (uri.scheme in listOf("http", "https") && !uri.host.isNullOrEmpty() && uri.path == "/mobile/material") {
            val codes = (uri.rawQuery ?: "").split("&").mapNotNull { part ->
                val pair = part.split("=", limit = 2)
                if (URLDecoder.decode(pair[0], "UTF-8") == "code" && pair.size == 2) URLDecoder.decode(pair[1], "UTF-8") else null
            }
            if (codes.size == 1) codes.first() else ""
        } else value
    }.getOrDefault(value)
}
