package com.factory.wms.data.api

import com.factory.wms.BuildConfig
import okhttp3.Interceptor
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit

object RetrofitClient {

    // 可变状态并发保护：全部 @Volatile，setBaseUrl 在锁内"先构建后发布"，
    // 多线程下 apiService 不会读到 baseUrl/retrofit 半更新的中间态。
    private val lock = Any()

    @Volatile
    private var baseUrl: String = ""

    @Volatile
    private var authToken: String? = null

    var onUnauthorized: (() -> Unit)? = null

    private val authInterceptor = Interceptor { chain ->
        val newRequest = chain.request().newBuilder().apply {
            authToken?.let { token ->
                addHeader("Authorization", "Bearer $token")
            }
        }.build()
        val response = chain.proceed(newRequest)
        if (response.code == 401) {
            // 登录接口本身返回 401（如密码错误）不应触发"令牌失效"事件：
            // 否则会误清空已保存的 baseUrl/token 并重复跳转登录页，干扰登录流程。
            val isLoginRequest = newRequest.url.encodedPath.endsWith("/api/login")
            if (!isLoginRequest) {
                authToken = null
                onUnauthorized?.invoke()
            }
        }
        response
    }

    // 日志仅在 debug 构建开启，且只记录请求行/响应行，绝不打印 header（避免 Authorization token 泄漏）。
    // release 构建关闭日志，防止 token、业务数据落入日志。
    private val loggingInterceptor = HttpLoggingInterceptor().apply {
        level = if (BuildConfig.DEBUG) HttpLoggingInterceptor.Level.BASIC else HttpLoggingInterceptor.Level.NONE
    }

    // AUDIT-2026-10-07-P1：LLM 长请求独立超时。
    // 默认 readTimeout=30s，但 assistant_chat / voice_intent / voice_out_draft
    // 走 LLM 链路，后端 ai_llm_timeout_seconds 可在系统设置调到 60s+（app.py:12399），
    // 30s 必断——用户只看到「网络错误: timeout」，后端 503 JSON 都收不到。
    // 方案：Interceptor.Chain.withReadTimeout（OkHttp 4.10+）按路径放宽到 120s，
    // 其余请求保持 30s 不变。
    // BUG-2026-10-07-013：识物 recognize_material 与单据 OCR document_ocr 同样走
    // 视觉 LLM（_ai_call_llm_vision，后端超时 max(配置,60)=60s+），视觉识别大图
    // 常超 30s；P1 白名单漏了这两条路径——用户拍照识物 30s 必被 App 掐断，
    // 只见「网络错误: timeout」，误以为识物功能全坏。补进白名单。
    // FEATURE-2026-10-08-EXCEL：Excel 导出接口同样走视觉 LLM，一并放宽。
    private val llmTimeoutInterceptor = Interceptor { chain ->
        val path = chain.request().url.encodedPath
        val isLlmPath = path.endsWith("/api/mobile/assistant_chat") ||
            path.endsWith("/api/mobile/voice_intent") ||
            path.endsWith("/api/mobile/voice_out_draft") ||
            path.endsWith("/api/recognize_material") ||
            path.endsWith("/api/ai/document_ocr") ||
            path.endsWith("/api/ai/document_ocr_excel")
        if (isLlmPath) {
            chain.withReadTimeout(LLM_READ_TIMEOUT_SECONDS, TimeUnit.SECONDS)
                .proceed(chain.request())
        } else {
            chain.proceed(chain.request())
        }
    }

    private val okHttpClient = OkHttpClient.Builder()
        .addInterceptor(authInterceptor)
        .addInterceptor(llmTimeoutInterceptor)
        .addInterceptor(loggingInterceptor)
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .writeTimeout(30, TimeUnit.SECONDS)
        .build()

    @Volatile
    private var retrofit: Retrofit = buildRetrofit("")

    private fun buildRetrofit(url: String): Retrofit = Retrofit.Builder()
        // baseUrl 未配置时用不可达占位地址（127.0.0.1:9 discard 端口）：
        // apiService getter 会在 baseUrl 为空时先抛错，该占位永远不会真正收到请求
        // （更不会携带 Authorization token）。绝不静默 fallback 到任何真实域名，
        // 避免 baseUrl 未配置时 token 被发往非预期服务器。
        .baseUrl(if (url.isBlank()) "http://127.0.0.1:9/" else if (url.endsWith("/")) url else "$url/")
        .client(okHttpClient)
        .addConverterFactory(GsonConverterFactory.create())
        .build()

    val apiService: WmsApiService
        get() {
            check(baseUrl.isNotBlank()) { "服务器地址未配置，请先登录并填写服务器地址" }
            return retrofit.create(WmsApiService::class.java)
        }

    fun setBaseUrl(url: String) {
        synchronized(lock) {
            // 先构建新实例再发布引用，避免读到"新 baseUrl + 旧 retrofit"中间态
            retrofit = buildRetrofit(url)
            baseUrl = url
        }
    }

    fun setToken(token: String?) {
        authToken = token
    }

    fun getToken(): String? = authToken

    fun getBaseUrl(): String = baseUrl

    fun sharedOkHttpClient(): OkHttpClient = okHttpClient

    // AUDIT-2026-10-07-P1：LLM 长请求读超时（秒）。
    // 后端 ai_llm_timeout_seconds 上限 60s（系统设置），再留一倍余量给
    // 意图理解 + 查库 + 兜底重试，120s 足够覆盖最坏链路。
    // BUG-2026-10-07-013：识物/单据 OCR 的后端视觉超时是 max(配置,60)=60s+，
    // 大图识别常超 30s——此白名单已覆盖 recognize_material / document_ocr。
    // 注意：Interceptor.Chain.withReadTimeout 的签名是 (Int, TimeUnit)，
    // 用 Int 而不是 Long（CI 编译错误教训：Long 会 Argument type mismatch）。
    const val LLM_READ_TIMEOUT_SECONDS: Int = 120
}
