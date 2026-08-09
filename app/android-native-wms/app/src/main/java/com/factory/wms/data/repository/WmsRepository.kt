package com.factory.wms.data.repository

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import com.factory.wms.data.api.DocumentOcrResult
import com.factory.wms.data.api.RecognizeMaterialResult
import com.factory.wms.data.api.RetrofitClient
import com.factory.wms.data.api.WmsApiService
import com.factory.wms.data.local.AppDatabase
import com.factory.wms.data.local.MaterialEntity
import com.factory.wms.data.local.OperationLogEntity
import com.factory.wms.data.model.*
import com.google.gson.Gson
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import retrofit2.Response
import java.util.UUID

private val Context.dataStore: DataStore<Preferences> by preferencesDataStore(name = "wms_settings")

class WmsRepository(private val context: Context) {

    private val api: WmsApiService
        get() = RetrofitClient.apiService
    private val db: AppDatabase = AppDatabase.getDatabase(context)
    private val materialDao = db.materialDao()
    private val operationLogDao = db.operationLogDao()

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

    // 幂等键：每次写操作生成唯一 request_id，配合后端 mobile_api_idempotent
    // 在请求重试/网络抖动时避免重复入库、重复扣库存。
    private fun newRequestId(): String = UUID.randomUUID().toString()

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
            handleResponse<List<MaterialDto>>(response)
        } catch (e: Exception) {
            Result.failure(Exception("网络错误: ${e.message}"))
        }
    }

    suspend fun getMaterialInfo(code: String): Result<MaterialDto> {
        return try {
            // 网络优先：查库存要求实时准确，先请求后端，成功后再回写本地缓存
            val response = api.materialInfo(code)
            val result = handleResponse<MaterialDto>(response)
            result.fold(
                onSuccess = { dto ->
                    // 成功后更新缓存
                    materialDao.insert(dto.toEntity())
                },
                onFailure = { }
            )
            result
        } catch (e: Exception) {
            // 网络不可用时，回退到 Room 本地缓存
            val cached = materialDao.getByCode(code)
            if (cached != null) {
                Result.success(cached.toDto())
            } else {
                Result.failure(Exception("网络错误: ${e.message}"))
            }
        }
    }

    suspend fun submitInbound(request: InboundRequest): Result<SubmitResult> {
        return try {
            val response = api.submitInbound(newRequestId(), request)
            val result = handleResponse<SubmitResult>(response)
            result.fold(
                onSuccess = { submitResult ->
                    // Log operation
                    request.lines.forEach { line ->
                        operationLogDao.insert(
                            OperationLogEntity(
                                operationType = "inbound",
                                orderNo = submitResult.order_no,
                                materialCode = line.material_code,
                                quantity = line.quantity
                            )
                        )
                    }
                },
                onFailure = { }
            )
            result
        } catch (e: Exception) {
            Result.failure(Exception("网络错误: ${e.message}"))
        }
    }

    suspend fun submitOutbound(request: OutboundRequest): Result<SubmitResult> {
        return try {
            val response = api.submitOutbound(newRequestId(), request)
            val result = handleResponse<SubmitResult>(response)
            result.fold(
                onSuccess = { submitResult ->
                    request.lines.forEach { line ->
                        operationLogDao.insert(
                            OperationLogEntity(
                                operationType = "outbound",
                                orderNo = submitResult.order_no,
                                materialCode = line.material_code,
                                quantity = line.quantity
                            )
                        )
                    }
                },
                onFailure = { }
            )
            result
        } catch (e: Exception) {
            Result.failure(Exception("网络错误: ${e.message}"))
        }
    }

    suspend fun submitStocktake(request: StocktakeRequest): Result<SubmitResult> {
        return try {
            val response = api.submitStocktake(newRequestId(), request)
            val result = handleResponse<SubmitResult>(response)
            result.fold(
                onSuccess = { submitResult ->
                    request.lines.forEach { line ->
                        operationLogDao.insert(
                            OperationLogEntity(
                                operationType = "stocktake",
                                orderNo = submitResult.check_no,
                                materialCode = line.material_code,
                                quantity = line.actual_stock
                            )
                        )
                    }
                },
                onFailure = { }
            )
            result
        } catch (e: Exception) {
            Result.failure(Exception("网络错误: ${e.message}"))
        }
    }

    suspend fun documentOcr(imagePart: okhttp3.MultipartBody.Part): Result<DocumentOcrResult> {
        return try {
            val response = api.documentOcr(imagePart)
            handleResponse<DocumentOcrResult>(response)
        } catch (e: Exception) {
            Result.failure(Exception("网络错误: ${e.message}"))
        }
    }

    suspend fun recognizeMaterial(imagePart: okhttp3.MultipartBody.Part): Result<RecognizeMaterialResult> {
        return try {
            val response = api.recognizeMaterial(imagePart)
            handleResponse<RecognizeMaterialResult>(response)
        } catch (e: Exception) {
            Result.failure(Exception("网络错误: ${e.message}"))
        }
    }

    suspend fun getWarehouses(): Result<List<WarehouseDto>> {
        return try {
            val response = api.getWarehouses()
            handleResponse<List<WarehouseDto>>(response)
        } catch (e: Exception) {
            Result.failure(Exception("网络错误: ${e.message}"))
        }
    }

    suspend fun getOpeningStock(warehouseId: Int? = null, keyword: String? = null): Result<List<OpeningStockDto>> {
        return try {
            val response = api.getOpeningStock(warehouseId, keyword)
            val data = handleResponse<OpeningStockListData>(response).getOrNull()
            Result.success(data?.items ?: emptyList())
        } catch (e: Exception) {
            Result.failure(Exception("网络错误: ${e.message}"))
        }
    }

    suspend fun submitOpeningStock(request: OpeningStockRequest): Result<String> {
        return try {
            val response = api.submitOpeningStock(newRequestId(), request)
            val result = handleResponse<SubmitResult>(response)
            result.fold(
                onSuccess = { submitResult ->
                    val msg = submitResult?.let { "期初库存已保存" } ?: "期初库存已保存"
                    request.lines.forEachIndexed { index, line ->
                        operationLogDao.insert(
                            OperationLogEntity(
                                operationType = "opening_stock",
                                orderNo = "期初-${index + 1}",
                                materialCode = line.materialCode,
                                quantity = line.quantity
                            )
                        )
                    }
                    Result.success(msg)
                },
                onFailure = { e ->
                    Result.failure(e)
                }
            )
        } catch (e: Exception) {
            Result.failure(Exception("网络错误: ${e.message}"))
        }
    }

    suspend fun createInboundDraft(request: InboundDraftRequest): Result<InboundDraftResult> {
        return try {
            val response = api.createInboundDraft(newRequestId(), request)
            handleResponse<InboundDraftResult>(response)
        } catch (e: Exception) {
            Result.failure(Exception("网络错误: ${e.message}"))
        }
    }

    suspend fun getDashboard(): Result<DashboardDto> {
        return try {
            val response = api.getDashboard()
            handleResponse<DashboardDto>(response)
        } catch (e: Exception) {
            Result.failure(Exception("网络错误: ${e.message}"))
        }
    }

    private inline fun <reified T> handleResponse(response: Response<ApiEnvelope<T>>): Result<T> {
        return if (response.isSuccessful) {
            val envelope = response.body()
            if (envelope != null && envelope.isOk()) {
                val data = envelope.data
                if (data != null) {
                    Result.success(data)
                } else {
                    @Suppress("UNCHECKED_CAST")
                    Result.success(Unit as T)
                }
            } else {
                Result.failure(Exception(envelope?.displayMessage() ?: "请求失败"))
            }
        } else {
            val errorMsg = try {
                val errorBody = response.errorBody()?.string()
                Gson().fromJson(errorBody, ApiEnvelope::class.java)?.displayMessage()
            } catch (_: Exception) { null }
            Result.failure(Exception(errorMsg ?: "请求失败 (${response.code()})"))
        }
    }
}

// Extension functions for model-entity conversion
private fun MaterialDto.toEntity(): MaterialEntity = MaterialEntity(
    code = code ?: "",
    name = name,
    spec = spec,
    unit = unit,
    stock = stock,
    price = price,
    category = category,
    supplier = supplier,
    minStock = minStock,
    reorderPoint = reorderPoint
)

private fun MaterialEntity.toDto(): MaterialDto = MaterialDto(
    id = null,
    code = code,
    name = name,
    spec = spec,
    unit = unit,
    category = category,
    supplier = supplier,
    stock = stock,
    price = price,
    minStock = minStock,
    reorderPoint = reorderPoint
)