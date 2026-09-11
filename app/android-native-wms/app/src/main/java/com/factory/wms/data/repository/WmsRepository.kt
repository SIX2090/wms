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
        /**
         * 服务端已给出明确业务原因的错误（如「请选择进行中的盘点单」）。
         *
         * BUG-2026-09-10-011：此前多处调用点在外层 `catch (e: Exception)` 里
         * 统一包成 `"网络错误: ..."`，把 handleResponse 正确透传的服务端 msg 覆盖掉，
         * 现场看到"网络错误"却反复重试（其实网络正常，是业务前置条件未满足）。
         * 用独立类型标记，外层 catch 原样放行、不再加"网络错误"前缀。
         */
        class BusinessException(message: String) : Exception(message)

        private const val KEY_TOKEN = "auth_token"
        private val KEY_BASE_URL = stringPreferencesKey("base_url")
        private val KEY_USERNAME = stringPreferencesKey("username")
        private val KEY_ROLE = stringPreferencesKey("role")
        // BUG-2026-09-03-003 断点续盘：盘点草稿 JSON（DataStore）
        private val KEY_STOCKTAKE_DRAFT = stringPreferencesKey("stocktake_draft")
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

    // BUG-2026-09-03-003 断点续盘：盘点草稿持久化（DataStore JSON，进程被杀可恢复）
    suspend fun saveStocktakeDraft(draft: StocktakeDraft) {
        context.dataStore.edit { it[KEY_STOCKTAKE_DRAFT] = Gson().toJson(draft) }
    }

    suspend fun loadStocktakeDraft(): StocktakeDraft? {
        val json = context.dataStore.data.map { it[KEY_STOCKTAKE_DRAFT] }.first() ?: return null
        return try {
            Gson().fromJson(json, StocktakeDraft::class.java)
        } catch (e: Exception) {
            null
        }
    }

    suspend fun clearStocktakeDraft() {
        context.dataStore.edit { it.remove(KEY_STOCKTAKE_DRAFT) }
    }

    /**
     * 会话兜底恢复（BUG-2026-08-24-006）：App 冷启动时 AuthViewModel 异步还原
     * baseUrl/token 依赖 DataStore + EncryptedSharedPreferences 首轮读取（数百毫秒），
     * 而 AppNavGraph 组合阶段即创建各 ViewModel 并发起请求，存在竞态——请求若先于
     * 会话还原完成，RetrofitClient.apiService 会抛「服务器地址未配置」。
     * 在发起网络请求前调用：若内存 baseUrl 为空，则从持久化存储同步还原 baseUrl
     * 与 token（token 必须先于请求注入，否则首个请求 401 会误触发强制登出）。
     * 已登录/已还原时调用为零开销 no-op，可安全重复调用。
     */
    suspend fun ensureSession() {
        if (RetrofitClient.getBaseUrl().isNotBlank()) return
        val savedBaseUrl = getSavedBaseUrl()
        if (savedBaseUrl.isNullOrBlank()) return
        val savedToken = getSavedToken()
        if (!savedToken.isNullOrBlank()) {
            RetrofitClient.setToken(savedToken)
        }
        RetrofitClient.setBaseUrl(savedBaseUrl)
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
        // P2-E: 同步 commit 清空加密 SharedPreferences，确保 token 在闪存上被覆写，
        // 避免物理文件残留加密 token（虽然无法解出明文，但减少攻击面）。
        // logout() 流程必须先清空本地凭据，再清空 DataStore + RetrofitClient 内存。
        // 加密 prefs 的 clear() 是同步操作（commit 而非 apply），保证 logout 返回时数据已落盘。
        try {
            encryptedPrefs.edit().clear().commit()
        } catch (e: Exception) {
            // 加密 prefs 清空失败不阻塞 logout 流程（已下台仍应可继续）
            android.util.Log.w("WmsRepo", "清空加密 prefs 失败: ${e.message}")
        }
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

    suspend fun searchMaterial(keyword: String, warehouseCode: String? = null): Result<List<MaterialDto>> {
        return safeCall { api.searchMaterial(keyword, warehouseCode) }
    }

    /**
     * AI-MOB-STOCK-F01：库存列表查询（分页，复用既有 `/api/mobile/stock/query`）。
     *
     * - [warehouse] 必填（仓库名或编码）。缺失时服务端 400「请选择仓库」，
     *   调用方（ViewModel）须在选仓后再调用，不得传空串探测全量。
     * - 返回仓库级账面库存分页数据；调用方按 total_pages 翻页（R1）。
     * - 走 safeCall：服务端业务提示（如"请选择仓库"）原样透传，不被
     *   覆盖为"网络错误"（BUG-2026-09-10-011）。
     */
    suspend fun queryStockPage(
        warehouse: String,
        keyword: String? = null,
        page: Int = 1,
        pageSize: Int = 20
    ): Result<StockQueryPageData> {
        return safeCall {
            api.stockQuery(
                warehouse = warehouse,
                keyword = keyword?.takeIf { it.isNotBlank() },
                page = page,
                pageSize = pageSize
            )
        }
    }

    suspend fun getMaterialInfo(code: String, warehouseCode: String? = null): Result<MaterialDto> {
        return try {
            // 网络优先：查库存要求实时准确，先请求后端（已选仓库时按仓库级口径），成功后再回写本地缓存
            val response = api.materialInfo(code, warehouseCode)
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
                Result.failure(BusinessException(e.message ?: "网络错误"))
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
        } catch (e: BusinessException) {
            Result.failure(e)
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
        } catch (e: BusinessException) {
            Result.failure(e)
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
        } catch (e: BusinessException) {
            Result.failure(e)
        } catch (e: Exception) {
            Result.failure(Exception("网络错误: ${e.message}"))
        }
    }

    suspend fun documentOcr(imagePart: okhttp3.MultipartBody.Part): Result<DocumentOcrResult> {
        return safeCall {
            api.documentOcr(imagePart)
        }
    }

    suspend fun recognizeMaterial(imagePart: okhttp3.MultipartBody.Part): Result<RecognizeMaterialResult> {
        return safeCall {
            api.recognizeMaterial(imagePart)
        }
    }

    suspend fun getWarehouses(): Result<List<WarehouseDto>> {
        return safeCall { api.getWarehouses() }
            .fold(
                onSuccess = { data -> Result.success(data.items) },
                onFailure = { Result.failure(it) }
            )
    }

    /** INV-BATCH-001-E：拉取某仓库进行中盘点单（盘点提交前必须先选单）。 */
    suspend fun loadPendingCheckOrders(warehouseCode: String): Result<List<CheckOrderDto>> {
        ensureSession()
        return safeCall { api.listPendingCheckOrders(warehouseCode) }
            .fold(
                onSuccess = { data -> Result.success(data.orders) },
                onFailure = { Result.failure(it) }
            )
    }

    /** 合同编号模糊搜索（出库选填合同字段快速匹配）。 */
    suspend fun searchContracts(keyword: String): Result<List<ContractDto>> {
        ensureSession()
        return safeCall { api.searchContracts(keyword) }
            .fold(
                onSuccess = { data -> Result.success(data.items) },
                onFailure = { Result.failure(it) }
            )
    }

    /**
     * 每日明细报表：type=purchase_in / requisition，date 为 yyyy-MM-dd，null 表示今天。
     * warehouseId 为 null 时跟随系统默认仓；传 "all" 为全部仓库汇总（BUG-2026-09-10-009）。
     */
    suspend fun getDailyReport(
        type: String,
        date: String? = null,
        warehouseId: String? = null
    ): Result<DailyReportData> {
        ensureSession()
        // BUG-2026-08-28-002：明细行按 page_size 条/页分页返回，仅取第 1 页时，
        // 当日明细超过一页则后续明细永远不可见（汇总统计基于全集，表现为
        // "58 明细只能看到 20 条"）。逐页拉取并合并全部明细。
        //
        // BUG-2026-09-10-011：改用 safeCall，服务端业务提示（如日期/仓库参数非法）
        // 原样透传给页面，不再被"网络错误"覆盖。
        val first = safeCall { api.dailyReportDetail(type, date, warehouseId, page = 1, pageSize = 20) }
            .getOrElse { return Result.failure(it) }
        if (first.totalPages <= 1) {
            return Result.success(first)
        }
        val allItems = first.items.toMutableList()
        for (page in 2..first.totalPages) {
            val data = safeCall {
                api.dailyReportDetail(type, date, warehouseId, page = page, pageSize = 20)
            }.getOrElse { return Result.failure(it) }
            allItems.addAll(data.items)
        }
        return Result.success(first.copy(items = allItems, page = 1))
    }

    suspend fun getOpeningStock(warehouseId: Int? = null, keyword: String? = null): Result<List<OpeningStockDto>> {
        return safeCall { api.getOpeningStock(warehouseId, keyword) }
            .fold(
                onSuccess = { data -> Result.success(data.items) },
                onFailure = { Result.failure(it) }
            )
    }

    suspend fun submitOpeningStock(request: OpeningStockRequest): Result<String> {
        return try {
            val response = api.submitOpeningStock(newRequestId(), request)
            val result = handleResponse<SubmitResult>(response)
            result.fold(
                onSuccess = {
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
                    Result.success("期初库存已保存")
                },
                onFailure = { e ->
                    Result.failure(e)
                }
            )
        } catch (e: BusinessException) {
            Result.failure(e)
        } catch (e: Exception) {
            Result.failure(Exception("网络错误: ${e.message}"))
        }
    }

    suspend fun createInboundDraft(request: InboundDraftRequest): Result<InboundDraftResult> {
        return safeCall {
            api.createInboundDraft(newRequestId(), request)
        }
    }

    /**
     * 首页概览。
     *
     * BUG-2026-09-10-010：新增 [warehouseId] —— null 跟随系统默认仓（旧行为），
     * "all" 为全部仓库汇总，其余为仓库 id。此前首页不带仓库参数，多仓用户
     * 只能看到默认仓的数字。
     */
    suspend fun getDashboard(warehouseId: String? = null): Result<DashboardDto> {
        ensureSession()
        return safeCall { api.getDashboard(warehouseId) }
    }

    // ── 物料档案（多图） ──

    suspend fun searchMaterialArchive(keyword: String): Result<List<MaterialArchiveDto>> {
        return safeCall { api.searchMaterialArchive(keyword) }
    }

    suspend fun getMaterialArchiveImages(id: Int): Result<MaterialArchiveImagesData> {
        return safeCall {
            api.getMaterialArchiveImages(id)
        }
    }

    suspend fun uploadMaterialArchiveImage(id: Int, imagePart: okhttp3.MultipartBody.Part): Result<MaterialArchiveImageDto> {
        return safeCall {
            api.uploadMaterialArchiveImage(id, imagePart)
        }
    }

    suspend fun deleteMaterialArchiveImage(imageId: Int): Result<Unit> {
        return safeCall {
            api.deleteMaterialArchiveImage(imageId)
        }
    }

    // ── 远程打印队列 ──

    /** 创建打印任务（入库/出库单据、物料档案、物料标签）。 */
    suspend fun createPrintJob(request: PrintJobRequest): Result<PrintJobResult> {
        return safeCall {
            api.createPrintJob(request)
        }
    }

    /**
     * 统一网络调用包装：HTTP/业务错误（已由 [handleResponse] 解出可读 msg）原样返回，
     * 只有真正的网络层异常（IOException / 超时 / 解析失败等）才标注"网络错误"。
     *
     * BUG-2026-09-10-011：收口 20 处重复的 try/catch，避免服务端 msg 被吞。
     */
    // T 必须 reified：内部要调用同为 `inline fun <reified T>` 的 handleResponse，
    // 非 reified 的 T 会报 "Cannot use 'T' as reified type parameter"（Release 编译失败）。
    private suspend inline fun <reified T> safeCall(
        block: () -> Response<ApiEnvelope<T>>
    ): Result<T> {
        return try {
            handleResponse(block())
        } catch (e: BusinessException) {
            Result.failure(e)
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
                } else if (T::class == Unit::class) {
                    // 仅删除类接口（ApiEnvelope<Unit>）允许 success 无 data 时回填 Unit。
                    // BUG-2026-08-11-006：其他类型绝不能 `Unit as T`——reified 泛型会真实 checkcast，
                    // 抛 "kotlin.Unit cannot be cast to X"，把服务端漏发 data 的问题变成晦涩崩溃。
                    @Suppress("UNCHECKED_CAST")
                    Result.success(Unit as T)
                } else {
                    // success 但 data 缺失（旧版本服务端/代理丢 body 等异常路径）：
                    // 返回干净失败，UI 展示服务端 msg，而不是 ClassCastException 文本
                    Result.failure(BusinessException(envelope.displayMessage()))
                }
            } else {
                Result.failure(BusinessException(envelope?.displayMessage() ?: "请求失败"))
            }
        } else {
            val errorMsg = try {
                val errorBody = response.errorBody()?.string()
                Gson().fromJson(errorBody, ApiEnvelope::class.java)?.displayMessage()
            } catch (_: Exception) { null }
            Result.failure(BusinessException(errorMsg ?: "请求失败 (${response.code()})"))
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
    brand = null,
    spec = spec,
    unit = unit,
    category = category,
    supplier = supplier,
    stock = stock,
    price = price,
    minStock = minStock,
    reorderPoint = reorderPoint
)
