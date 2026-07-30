package com.factory.wms.data.repository

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import com.factory.wms.data.api.RetrofitClient
import com.factory.wms.data.api.WmsApiService
import com.factory.wms.data.model.*
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map

private val Context.dataStore: DataStore<Preferences> by preferencesDataStore(name = "wms_settings")

class WmsRepository(private val context: Context) {

    private val api: WmsApiService = RetrofitClient.apiService

    // EncryptedSharedPreferences for sensitive token storage
    private val encryptedPrefs by lazy {
        val masterKey = MasterKey.Builder(context)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build()
        EncryptedSharedPreferences.create(
            context,
            "wms_secure_prefs",
            masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
        )
    }

    companion object {
        private const val KEY_TOKEN = "auth_token"
        private val KEY_BASE_URL = stringPreferencesKey("base_url")
        private val KEY_USERNAME = stringPreferencesKey("username")
        private val KEY_ROLE = stringPreferencesKey("role")
    }

    suspend fun getSavedToken(): String? {
        return encryptedPrefs.getString(KEY_TOKEN, null)
    }

    suspend fun getSavedBaseUrl(): String? {
        return context.dataStore.data.map { it[KEY_BASE_URL] }.first()
    }

    suspend fun saveLoginInfo(token: String, baseUrl: String, username: String, role: String) {
        // Token stored in EncryptedSharedPreferences
        encryptedPrefs.edit().putString(KEY_TOKEN, token).apply()
        // Non-sensitive data stored in DataStore
        context.dataStore.edit {
            it[KEY_BASE_URL] = baseUrl
            it[KEY_USERNAME] = username
            it[KEY_ROLE] = role
        }
        RetrofitClient.setToken(token)
        RetrofitClient.setBaseUrl(baseUrl)
    }

    suspend fun logout() {
        // Clear encrypted token
        encryptedPrefs.edit().remove(KEY_TOKEN).apply()
        // Clear non-sensitive data
        context.dataStore.edit { it.clear() }
        RetrofitClient.setToken(null)
    }

    suspend fun getUsername(): String? {
        return context.dataStore.data.map { it[KEY_USERNAME] }.first()
    }

    suspend fun getRole(): String? {
        return context.dataStore.data.map { it[KEY_ROLE] }.first()
    }

    suspend fun login(username: String, password: String, baseUrl: String): Result<LoginData> {
        return try {
            RetrofitClient.setBaseUrl(baseUrl)
            val response = api.login(LoginRequest(username, password))
            if (response.isSuccessful) {
                val envelope = response.body()
                if (envelope != null && envelope.isOk() && envelope.data != null) {
                    saveLoginInfo(envelope.data.token, baseUrl, username, envelope.data.user.role ?: "")
                    Result.success(envelope.data)
                } else {
                    Result.failure(Exception(envelope?.displayMessage() ?: "登录失败"))
                }
            } else {
                val errorMsg = try {
                    val errorBody = response.errorBody()?.string()
                    com.google.gson.Gson().fromJson(errorBody, ApiEnvelope::class.java)?.displayMessage()
                } catch (_: Exception) { null }
                Result.failure(Exception(errorMsg ?: "登录失败 (${response.code()})"))
            }
        } catch (e: Exception) {
            Result.failure(Exception("网络连接失败: ${e.message}"))
        }
    }

    suspend fun searchMaterial(keyword: String): Result<List<MaterialDto>> {
        return try {
            val response = api.searchMaterial(keyword)
            handleResponse(response) { it }
        } catch (e: Exception) {
            Result.failure(Exception("网络错误: ${e.message}"))
        }
    }

    suspend fun getMaterialInfo(code: String): Result<MaterialDto> {
        return try {
            val response = api.materialInfo(code)
            handleResponse(response) { it }
        } catch (e: Exception) {
            Result.failure(Exception("网络错误: ${e.message}"))
        }
    }

    suspend fun submitInbound(request: InboundRequest): Result<SubmitResult> {
        return try {
            val response = api.submitInbound(request)
            handleResponse(response) { it }
        } catch (e: Exception) {
            Result.failure(Exception("网络错误: ${e.message}"))
        }
    }

    suspend fun submitOutbound(request: OutboundRequest): Result<SubmitResult> {
        return try {
            val response = api.submitOutbound(request)
            handleResponse(response) { it }
        } catch (e: Exception) {
            Result.failure(Exception("网络错误: ${e.message}"))
        }
    }

    suspend fun submitStocktake(request: StocktakeRequest): Result<SubmitResult> {
        return try {
            val response = api.submitStocktake(request)
            handleResponse(response) { it }
        } catch (e: Exception) {
            Result.failure(Exception("网络错误: ${e.message}"))
        }
    }

    suspend fun documentOcr(imagePart: okhttp3.MultipartBody.Part): Result<ApiEnvelope<DocumentOcrResult>> {
        return try {
            val response = api.documentOcr(imagePart)
            handleResponse(response) { response.body()!! }
        } catch (e: Exception) {
            Result.failure(Exception("网络错误: ${e.message}"))
        }
    }

    suspend fun recognizeMaterial(imagePart: okhttp3.MultipartBody.Part): Result<ApiEnvelope<RecognizeMaterialResult>> {
        return try {
            val response = api.recognizeMaterial(imagePart)
            handleResponse(response) { response.body()!! }
        } catch (e: Exception) {
            Result.failure(Exception("网络错误: ${e.message}"))
        }
    }

    private fun <T> handleResponse(response: retrofit2.Response<ApiEnvelope<T>>, mapper: (T) -> Any): Result<Any> {
        return if (response.isSuccessful) {
            val envelope = response.body()
            if (envelope != null && envelope.isOk()) {
                val data = envelope.data
                if (data != null) {
                    Result.success(mapper(data))
                } else {
                    Result.success(Unit)
                }
            } else {
                Result.failure(Exception(envelope?.displayMessage() ?: "请求失败"))
            }
        } else {
            val errorMsg = try {
                val errorBody = response.errorBody()?.string()
                com.google.gson.Gson().fromJson(errorBody, ApiEnvelope::class.java)?.displayMessage()
            } catch (_: Exception) { null }
            Result.failure(Exception(errorMsg ?: "请求失败 (${response.code()})"))
        }
    }
}