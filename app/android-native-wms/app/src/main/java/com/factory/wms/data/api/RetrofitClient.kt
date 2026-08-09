package com.factory.wms.data.api

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

    private val loggingInterceptor = HttpLoggingInterceptor().apply {
        level = HttpLoggingInterceptor.Level.HEADERS
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