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
        val request = chain.request().newBuilder()
        authToken?.let { token ->
            request.addHeader("Authorization", "Bearer $token")
        }
        val response = chain.proceed(request.build())
        if (response.code == 401) {
            authToken = null
            onUnauthorized?.invoke()
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
        .baseUrl(if (baseUrl.isBlank()) "http://127.0.0.1:5000/" else if (baseUrl.endsWith("/")) baseUrl else "$baseUrl/")
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