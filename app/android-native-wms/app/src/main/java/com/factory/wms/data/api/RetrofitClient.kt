package com.factory.wms.data.api

import com.factory.wms.BuildConfig
import okhttp3.Interceptor
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit

object RetrofitClient {

    private var baseUrl: String = ""
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

    private val okHttpClient = OkHttpClient.Builder()
        .addInterceptor(authInterceptor)
        .addInterceptor(loggingInterceptor)
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .writeTimeout(30, TimeUnit.SECONDS)
        .build()

    private var retrofit: Retrofit = buildRetrofit()

    private fun buildRetrofit(): Retrofit = Retrofit.Builder()
        .baseUrl(if (baseUrl.isBlank()) "https://gd2026.top/" else if (baseUrl.endsWith("/")) baseUrl else "$baseUrl/")
        .client(okHttpClient)
        .addConverterFactory(GsonConverterFactory.create())
        .build()

    val apiService: WmsApiService
        get() = retrofit.create(WmsApiService::class.java)

    fun setBaseUrl(url: String) {
        baseUrl = url
        retrofit = buildRetrofit()
    }

    fun setToken(token: String?) {
        authToken = token
    }

    fun getToken(): String? = authToken

    fun getBaseUrl(): String = baseUrl
}
