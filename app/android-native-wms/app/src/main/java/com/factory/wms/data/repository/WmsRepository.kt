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
import com.factory.wms.data.local.PendingOperationEntity
import com.factory.wms.util.NetworkMonitor
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
    // BUG-2026-09-13-023：本地数据层（Room）失败不应导致 App 无法启动。
    // 本类由 AppNavGraph 组合期的 11 个 ViewModel 同时构造，构造期抛异常 = 闪退。
    // 本地库只存物料缓存、操作日志与离线待传队列（均可重建、非权威数据），
    // 故降级为"无本地缓存"继续运行；离线队列在 db 为空时不可用（降级为直连模式）。
    private val db: AppDatabase? = try {
        AppDatabase.getDatabase(context)
    } catch (e: Exception) {
        android.util.Log.w(
            "WmsRepo",
            "本地数据库不可用，已降级为无本地缓存: ${e.javaClass.simpleName}: ${e.message}"
        )
        null
    }
    private val materialDao = db?.materialDao()
    private val operationLogDao = db?.operationLogDao()
    private val pendingOperationDao = db?.pendingOperationDao()

    /**
     * AI-MOB-OFFLINE-01：离线待提交作业队列。
     *
     * 网络不可用时把**人工已确认的提交**暂存本地，联网后自动补传（幂等，不产生重复单据）。
     * lazy 避免构造期就注册网络回调。
     * BUG-2026-09-13-023：db 为空（本地库不可用）时返回 null，
     * 由调用方降级为直连提交，不得因离线能力缺失阻塞启动。
     */
    // BUG-2026-09-14-029（真实冷启动崩溃根因，堆栈见 last_crash.txt）：
    // 此前这里直接传 `api`，而 api 的 getter（RetrofitClient.apiService）在 baseUrl
    // 未配置（未登录 / 全新安装 / 清除数据）时抛 IllegalStateException。ScanViewModel
    // .init 会**同步**访问 offlineQueue（不在 safeCall 内），异常沿组合期传播 → 闪退。
    // 改为传惰性提供者 `{ api }`：构造 OfflineQueueManager 时不解析 api，仅在真正同步
    // （replay）时才取——那时用户已登录、baseUrl 已配置；即便仍为空也由 doSync 兜底。
    val offlineQueue: OfflineQueueManager? by lazy {
        val dao = pendingOperationDao ?: return@lazy null
        OfflineQueueManager.getInstance(
            context,
            dao,
            { api },
            NetworkMonitor.getInstance(context)
        )
    }

    // EncryptedSharedPreferences for sensitive token storage
    //
    // BUG-2026-09-13-023（启动崩溃）：EncryptedSharedPreferences 依赖 Android Keystore。
    // 在下列场景 MasterKey 会失效并抛 GeneralSecurityException / IOException 等**运行时异常**：
    //   - 用户清除应用数据 / 恢复出厂后残留旧密钥别名；
    //   - 换机由系统备份还原（备份不包含 Keystore 密钥）；
    //   - 部分厂商 ROM 的 Keystore 实现缺陷（个别机型冷启动时密钥暂不可用）；
    //   - 系统时间被大幅调整导致密钥失效。
    // 该异常发生在 AuthViewModel.init 的协程中，未捕获会直接杀进程 → "应用屡次停止运行"。
    // 处理策略：捕获后返回 null（等价于"无已保存凭据"），交由登录页走正常登录流程；
    // 同时删除损坏的 prefs 文件，让下一次写入重建一份干净密钥，避免永久不可用。
    private val encryptedPrefs: android.content.SharedPreferences? by lazy {
        try {
            createEncryptedPrefs()
        } catch (e: Exception) {
            android.util.Log.w(
                "WmsRepo",
                "加密存储不可用，已降级为待登录状态: ${e.javaClass.simpleName}: ${e.message}"
            )
            resetSecurePrefsFile()
            null
        }
    }

    private fun createEncryptedPrefs(): android.content.SharedPreferences {
        val masterKey = MasterKey.Builder(context)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build()
        return EncryptedSharedPreferences.create(
            context,
            SECURE_PREFS_NAME,
            masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
        )
    }

    /** 删除损坏的加密 prefs 文件（含日记文件），下次写入会以新密钥重建，避免永久卡死。 */
    private fun resetSecurePrefsFile() {
        try {
            val prefsFile = java.io.File(context.filesDir.parentFile, "shared_prefs/$SECURE_PREFS_NAME.xml")
            if (prefsFile.exists() && !prefsFile.delete()) {
                android.util.Log.w("WmsRepo", "损坏的加密 prefs 文件删除失败: ${prefsFile.name}")
            }
        } catch (e: Exception) {
            android.util.Log.w("WmsRepo", "重置加密 prefs 失败: ${e.message}")
        }
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
        class BusinessException(message: String) : Exception(message) {
            var safeToEdit: Boolean = false

            constructor(message: String, safeToEdit: Boolean) : this(message) {
                this.safeToEdit = safeToEdit
            }
        }

        /**
         * AI-MOB-OFFLINE-01：网络不可用但**已成功暂存到离线队列**。
         *
         * 用独立类型而非普通 Exception，是为了让 UI 能区分两种情况并给出正确措辞：
         * - 普通失败 → "提交失败，请重试"（用户需重扫/重试）
         * - 本异常  → "已暂存，联网后自动提交"（数据没丢，用户可放心离开）
         *
         * 若混用同一类型，UI 会把"已安全暂存"显示成"失败"，用户重复操作反而制造重复数据。
         */
        class OfflineQueuedException(
            val operationLabel: String
        ) : Exception("网络不可用，$operationLabel 已暂存，联网后自动提交")

        private const val KEY_TOKEN = "auth_token"
        private const val SECURE_PREFS_NAME = "wms_secure_prefs"
        private val KEY_BASE_URL = stringPreferencesKey("base_url")
        private val KEY_USERNAME = stringPreferencesKey("username")
        private val KEY_ROLE = stringPreferencesKey("role")
        // BUG-2026-09-03-003 断点续盘：盘点草稿 JSON（DataStore）
        private val KEY_STOCKTAKE_DRAFT = stringPreferencesKey("stocktake_draft")
    }

    // 幂等键：每次写操作生成唯一 request_id，配合后端 mobile_api_idempotent
    // 在请求重试/网络抖动时避免重复入库、重复扣库存。
    private fun newRequestId(): String = UUID.randomUUID().toString()

    /**
     * 读取已保存 token。加密存储不可用时返回 null（等价"未登录"），
     * 绝不向上抛异常——本方法在 App 冷启动链路中被调用，抛异常即闪退。
     */
    suspend fun getSavedToken(): String? {
        return try {
            encryptedPrefs?.getString(KEY_TOKEN, null)
        } catch (e: Exception) {
            // getString 本身也可能因密钥中途失效（如 Keystore 被系统回收）抛异常
            android.util.Log.w("WmsRepo", "读取 token 失败，按未登录处理: ${e.message}")
            null
        }
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

    suspend fun editDraftKey(operation: String): String {
        require(operation == "inbound" || operation == "outbound")
        val preferences = context.dataStore.data.first()
        val server = preferences[KEY_BASE_URL].orEmpty().trimEnd('/')
        val username = preferences[KEY_USERNAME].orEmpty()
        check(server.isNotBlank() && username.isNotBlank()) { "请先登录再恢复清单" }
        val scope = Gson().toJson(listOf(server, username, operation))
        val digest = java.security.MessageDigest.getInstance("SHA-256")
            .digest(scope.toByteArray(Charsets.UTF_8))
            .joinToString("") { "%02x".format(it) }
        return "scan_edit_$digest"
    }

    suspend fun saveEditDraft(key: String, draft: ScanEditDraft?) {
        context.dataStore.edit {
            if (draft == null || draft.lines.isEmpty()) it.remove(stringPreferencesKey(key))
            else it[stringPreferencesKey(key)] = Gson().toJson(draft)
        }
    }

    /**
     * 读取扫码改单草稿（BUG-2026-09-14-026）。
     *
     * 与 [loadStocktakeDraft] 对齐：**反序列化必须 try/catch**。Gson 走的是
     * `Unsafe.allocateInstance`，完全绕过 Kotlin 构造器与 init，因此**不会**执行
     * 默认值、也不会做非空校验——`contractNo: String` 这类非空字段一旦在磁盘 JSON 里
     * 缺失，会被静默置为 null 并装进"非空"属性（平台类型，编译器不插 checkNotNull）。
     * 脏值随后在 UI 层被裸调（`.trim()` / 拼接 / 直接渲染）→ 主线程 NPE → 整 App 崩溃。
     * 这与 BUG-2026-08-24-007 是同一类故障模式（Gson 破坏非空契约），只是入口换成了草稿。
     *
     * 两道防线：
     * ① 最外层 try/catch —— JSON 本身损坏 / 结构不兼容时返回 null（等同"无草稿"），
     *    而不是把异常抛到冷启动链路上去杀进程。
     * ② [sanitizeEditDraft] —— 结构能解出来但含脏字段时，要么剔除坏行，
     *    要么（脏到无法安全修补时）整体退化为 null，确保返回值里绝不带 null 字段进 UI。
     */
    suspend fun loadEditDraft(key: String): ScanEditDraft? {
        val json = context.dataStore.data.first()[stringPreferencesKey(key)] ?: return null
        return try {
            Gson().fromJson(json, ScanEditDraft::class.java)?.let { sanitizeEditDraft(it) }
        } catch (e: Exception) {
            android.util.Log.w("WmsRepo", "读取改单草稿失败，按无草稿处理: ${e.message}")
            null
        }
    }

    /**
     * 净化反序列化后的草稿：剔除无法定位物料的坏行，并保证失败时退化为"无草稿"。
     *
     * draft 及其嵌套对象全部由 Gson 经 Unsafe 构造，Kotlin 的非空标注只是编译期契约，
     * 运行期完全可能为 null。因此整段净化用 runCatching 包裹：任一处因脏数据（null 字段）
     * 抛出，都退化为 null，绝不把异常或脏值抛给调用方。
     *
     * 只做"保证不崩"的最小修复，不改业务语义。
     */
    private fun sanitizeEditDraft(draft: ScanEditDraft): ScanEditDraft? = runCatching {
        // 逐行净化：material_code 为空的脏行无法定位物料，直接丢弃
        val safeLines = draft.lines.mapNotNull { entry ->
            val code = entry.line.material_code
            if (code.isBlank()) null else entry
        }
        draft.copy(lines = safeLines)
    }.getOrNull()

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
        // 写失败不阻断登录：内存态 token 已足够本次会话使用，仅"下次冷启动需重新登录"。
        try {
            encryptedPrefs?.edit()?.putString(KEY_TOKEN, token)?.apply()
        } catch (e: Exception) {
            android.util.Log.w("WmsRepo", "保存 token 失败（本次会话仍可用）: ${e.message}")
        }
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
        //
        // BUG-2026-09-13-023：encryptedPrefs 已改为可空（Keystore 失效时降级为 null）。
        // 此处**不能**写成 `encryptedPrefs?.edit()?.clear()?.commit()`——安全调用链在
        // prefs 为 null 时整体短路，虽然不会崩，但 commit() 是否真的执行变得不可知；
        // 且 commit() 的布尔返回值会被 `?.` 吞掉，无法判断落盘是否成功。
        // 改为显式判空 + 校验 commit 返回值：非 null 时必须真正同步落盘，失败记日志。
        val prefs = encryptedPrefs
        if (prefs != null) {
            try {
                if (!prefs.edit().clear().commit()) {
                    android.util.Log.w("WmsRepo", "清空加密 prefs 未成功落盘（commit 返回 false）")
                }
            } catch (e: Exception) {
                // 加密 prefs 清空失败不阻塞 logout 流程（已下台仍应可继续）
                android.util.Log.w("WmsRepo", "清空加密 prefs 失败: ${e.message}")
            }
        }
        // DataStore 清空失败同样不应阻断登出：内存态 token 一定会被清掉，
        // 最坏情况是下次冷启动仍读到旧 baseUrl（用户改一次即恢复）。
        try {
            context.dataStore.edit { it.clear() }
        } catch (e: Exception) {
            android.util.Log.w("WmsRepo", "清空 DataStore 失败: ${e.message}")
        }
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
    /** AI-MOB-STOCK-F02：sort / stock_filter 透传，null 时服务端维持原行为。 */
    suspend fun queryStockPage(
        warehouse: String,
        keyword: String? = null,
        page: Int = 1,
        pageSize: Int = 20,
        sort: String? = null,
        stockFilter: String? = null
    ): Result<StockQueryPageData> {
        return safeCall {
            api.stockQuery(
                warehouse = warehouse,
                keyword = keyword?.takeIf { it.isNotBlank() },
                page = page,
                pageSize = pageSize,
                sort = sort?.takeIf { it.isNotBlank() },
                stockFilter = stockFilter?.takeIf { it.isNotBlank() }
            )
        }
    }

    // ── 首页概览下钻（AI-MOB-DRILLDOWN-01）──
    // 三个接口后端早已提供（native_api.py），手机端此前未接入。

    /**
     * 库存告警清单：仓库级库存 <= 安全库存的物料（含低于最低库存的），按缺口从小到大排序
     * （缺口最小的排前面——最接近达标的先补，性价比最高）。
     * [warehouseId] 必填（AGENTS.md 多仓隔离）；库存预警未启用时后端返回
     * 空列表 + 提示，不是错误。
     */
    suspend fun getAlertList(
        warehouseId: String,
        page: Int = 1,
        pageSize: Int = 20
    ): Result<AlertListData> {
        return safeCall {
            api.getAlertList(warehouseId = warehouseId, page = page, pageSize = pageSize)
        }
    }

    /**
     * 入库单列表。[status] 传 "pending"/"completed"，留空为全部。
     * [warehouseId] 必填，服务端按仓库隔离（跨仓不可见）。
     */
    suspend fun getInOrderList(
        warehouseId: String,
        status: String? = null,
        keyword: String? = null,
        page: Int = 1,
        pageSize: Int = 20
    ): Result<MobileOrderListData> {
        return safeCall {
            api.getInOrderList(
                warehouseId = warehouseId,
                status = status?.takeIf { it.isNotBlank() },
                keyword = keyword?.takeIf { it.isNotBlank() },
                page = page,
                pageSize = pageSize
            )
        }
    }

    /** 出库单列表。参数语义同 [getInOrderList]。 */
    suspend fun getOutOrderList(
        warehouseId: String,
        status: String? = null,
        keyword: String? = null,
        page: Int = 1,
        pageSize: Int = 20
    ): Result<MobileOrderListData> {
        return safeCall {
            api.getOutOrderList(
                warehouseId = warehouseId,
                status = status?.takeIf { it.isNotBlank() },
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
                    // 成功后更新缓存（本地库不可用时跳过，不影响主流程）
                    safeCache { materialDao?.insert(dto.toEntity()) }
                },
                onFailure = { }
            )
            result
        } catch (e: Exception) {
            // 网络不可用时，回退到 Room 本地缓存
            val cached = runCatching { materialDao?.getByCode(code) }.getOrNull()
            if (cached != null) {
                // AI-MOB-OFFLINE-HINT-01：标记为缓存数据并带上写入时间。
                // 不给标记的话，UI 无法区分"实时库存 5"与"三天前的 5"，
                // 用户看到数字就出库 —— 这是业务风险，不是体验问题。
                Result.success(
                    cached.toDto().copy(
                        fromCache = true,
                        cachedAtMillis = cached.lastSyncTime
                    )
                )
            } else {
                Result.failure(BusinessException(e.message ?: "网络错误"))
            }
        }
    }

    /** 本地缓存写入统一入口：失败只记日志，绝不影响网络主流程。 */
    private suspend fun safeCache(block: suspend () -> Unit) {
        try {
            block()
        } catch (e: Exception) {
            android.util.Log.w("WmsRepo", "本地缓存写入失败（已忽略）: ${e.message}")
        }
    }

    private suspend fun logOperation(
        operationType: String,
        orderNo: String?,
        materialCode: String,
        quantity: Double
    ) {
        safeCache {
            operationLogDao?.insert(
                OperationLogEntity(
                    operationType = operationType,
                    orderNo = orderNo,
                    materialCode = materialCode,
                    quantity = quantity
                )
            )
        }
    }

    suspend fun submitInbound(request: InboundRequest, requestId: String = newRequestId()): Result<SubmitResult> {
        return submitWithOfflineFallback(
            operationType = PendingOperationEntity.TYPE_INBOUND,
            payload = request,
            warehouseCode = request.warehouseCode ?: request.warehouse,
            lineCount = request.lines.size,
            label = "入库",
            requestId = requestId
        ) { requestId -> api.submitInbound(requestId, request) }
    }

    suspend fun submitOutbound(request: OutboundRequest, requestId: String = newRequestId(), replay: Boolean = false): Result<SubmitResult> {
        return submitWithOfflineFallback(
            operationType = PendingOperationEntity.TYPE_OUTBOUND,
            payload = request,
            warehouseCode = request.warehouseCode ?: request.warehouse,
            lineCount = request.lines.size,
            label = "出库",
            requestId = requestId
        ) { requestId ->
            if (!replay) handleResponse<OutboundPreflightResult>(api.preflightOutbound(request)).getOrThrow()
            api.submitOutbound(requestId, request)
        }
    }

    suspend fun submitStocktake(request: StocktakeRequest): Result<SubmitResult> {
        return submitWithOfflineFallback(
            operationType = PendingOperationEntity.TYPE_STOCKTAKE,
            payload = request,
            warehouseCode = request.warehouseCode ?: request.warehouse,
            lineCount = request.lines.size,
            label = "盘点"
        ) { requestId -> api.submitStocktake(requestId, request) }
    }

    /**
     * AI-MOB-OFFLINE-01：提交统一入口——**网络类失败自动落离线队列**。
     *
     * ## 为什么这样分流（关键业务判断）
     *
     * - **业务类失败**（[BusinessException]，服务端 4xx 且带明确中文原因，如
     *   "请选择仓库""库存不足"）：立即把失败返回给用户。这类错误重试无意义，
     *   若入队会把**确定失败**伪装成"已暂存"，用户以为提交成功、实际永远不会成功——
     *   比丢数据更危险。
     * - **网络类失败**（连接失败/超时/IO）：入队暂存，联网后自动补传。
     *   这是本任务要解决的场景（仓库弱网/地下室）。
     *
     * ## 幂等
     *
     * 无论走在线还是离线，**同一次用户提交复用同一个 requestId**：在线成功即完成；
     * 在线失败转离线后补传时携带同一 requestId，后端 `mobile_api_idempotent` 保证
     * 服务端最多生效一次。用户在弱网下反复点提交也不会产生重复单据。
     *
     * ## 仓库必填（AGENTS.md 第二节）
     *
     * [warehouseCode] 为空时**拒绝入队**并返回明确错误——断网不得回退默认仓，
     * 否则补传会把货记到错误仓库。
     */
    private suspend fun submitWithOfflineFallback(
        operationType: String,
        payload: Any,
        warehouseCode: String?,
        lineCount: Int,
        label: String,
        requestId: String = newRequestId(),
        call: suspend (String) -> Response<ApiEnvelope<SubmitResult>>
    ): Result<SubmitResult> {
        return try {
            val response = call(requestId)
            val result = handleResponse<SubmitResult>(response)
            result.fold(
                onSuccess = { submitResult ->
                    recordOperationLog(operationType, submitResult, payload)
                },
                onFailure = { }
            )
            result
        } catch (e: BusinessException) {
            // 业务拒绝：不回退队列，原样交给 UI 展示服务端原因
            Result.failure(e)
        } catch (e: Exception) {
            // 网络类失败：尝试入队暂存
            // BUG-2026-09-13-023：本地库不可用时 offlineQueue 为 null（降级为无离线能力），
            // 此时按"暂存失败"处理，明确告知用户数据未保住，绝不能谎报已暂存。
            val queue = offlineQueue
            val queued = queue != null && queue.enqueue(
                requestId = requestId,
                operationType = operationType,
                payload = payload,
                warehouseCode = warehouseCode,
                summary = "$label $lineCount 项"
            )
            if (queued) {
                Result.failure(OfflineQueuedException(label))
            } else {
                // BUG-2026-09-12-009：暂存**确实失败**（写库异常或参数不合法）。
                // 此时必须说清"数据没保住"，让用户决定重扫或换网络重试；
                // 绝不能沿用 OfflineQueuedException 的"已暂存"措辞，那是谎报。
                // 也不再统一叫"网络错误"——原因可能是本地存储异常，写网络会误导排查方向。
                Result.failure(
                    Exception("提交失败且本地暂存未成功，请保持本页重试（原因：${e.message}）")
                )
            }
        }
    }

    /** 按作业类型写入本地操作日志（在线成功路径；离线补传成功由队列侧不再重复记）。 */
    private suspend fun recordOperationLog(
        operationType: String,
        submitResult: SubmitResult,
        payload: Any
    ) {
        runCatching {
            when (payload) {
                is InboundRequest -> payload.lines.forEach { line ->
                    operationLogDao?.insert(
                        OperationLogEntity(
                            operationType = operationType,
                            orderNo = submitResult.order_no,
                            materialCode = line.material_code,
                            quantity = line.quantity
                        )
                    )
                }

                is OutboundRequest -> payload.lines.forEach { line ->
                    operationLogDao?.insert(
                        OperationLogEntity(
                            operationType = operationType,
                            orderNo = submitResult.order_no,
                            materialCode = line.material_code,
                            quantity = line.quantity
                        )
                    )
                }

                is StocktakeRequest -> payload.lines.forEach { line ->
                    operationLogDao?.insert(
                        OperationLogEntity(
                            operationType = operationType,
                            orderNo = submitResult.check_no,
                            materialCode = line.material_code,
                            quantity = line.actual_stock
                        )
                    )
                }
            }
        }.onFailure {
            // 操作日志写失败不得影响已成功的业务提交
            android.util.Log.w("WmsRepository", "写操作日志失败: ${it.message}")
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

    suspend fun getLocationOptions(warehouseCode: String): Result<LocationOptions> {
        return runCatching {
            val items = mutableListOf<String>()
            var page = 1
            var last: LocationOptions
            do {
                last = safeCall { api.getLocationOptions(warehouseCode, page) }.getOrThrow()
                check(last.enabled != null && last.totalPages != null) { "库位配置响应不完整" }
                items.addAll(last.items.orEmpty())
                page++
            } while (page <= (last.totalPages ?: 0))
            last.copy(items = items.distinct())
        }
    }

    suspend fun getWarehouses(): Result<List<WarehouseDto>> {
        // BUG-2026-09-14-026：补齐会话兜底，与 getDepartments / getEmployees 对齐。
        // 本方法在冷启动首页（HomeViewModel.init → loadDashboard）即可能被调用，
        // 早于 AuthViewModel 的异步会话还原。缺此调用时首个请求可能不带 baseUrl/token：
        // baseUrl 为空会抛「服务器地址未配置」，token 缺失会让 401 拦截器误触发强制登出。
        // ensureSession 幂等，且 safeCall 全程兜底，重复调用零开销。
        ensureSession()
        return safeCall { api.getWarehouses() }
            .fold(
                onSuccess = { data -> Result.success(data.items) },
                onFailure = { Result.failure(it) }
            )
    }

    /** 2026-09-12 领料部门下拉：启用部门列表 */
    suspend fun getDepartments(): Result<List<DepartmentDto>> {
        ensureSession()
        return safeCall { api.getDepartments() }
            .fold(
                onSuccess = { data -> Result.success(data.items) },
                onFailure = { Result.failure(it) }
            )
    }

    /** 2026-09-12 领料人下拉：员工列表，可选按部门过滤（选部门后联动） */
    suspend fun getEmployees(departmentId: Long? = null): Result<List<EmployeeDto>> {
        ensureSession()
        return safeCall { api.getEmployees(departmentId) }
            .fold(
                onSuccess = { data -> Result.success(data.items) },
                onFailure = { Result.failure(it) }
            )
    }

    /** BUG-2026-09-18-008 入库供应商下拉（写入 InOrder.supplier_id，供日报供应商列归集） */
    suspend fun getSuppliers(): Result<List<SupplierDto>> {
        ensureSession()
        return safeCall { api.getSuppliers() }
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

    /**
     * AI-MOB-CHECK-F01：盘点记录回查（本人提交的扫码盘点单，第 1 页）。
     *
     * 回查场景是"翻看最近几次盘点"，首屏 20 条即可满足；不逐页全量拉取，
     * 避免历史记录多时一次性拉爆（与每日报表"汇总需全集"的诉求不同，
     * BUG-2026-08-28-002 的逐页合并策略不适用于此）。
     */
    suspend fun loadStocktakeRecords(
        warehouse: String? = null,
        status: String? = null,
        page: Int = 1,
        pageSize: Int = 20
    ): Result<StocktakeRecordListData> {
        ensureSession()
        return safeCall { api.listStocktakeRecords(warehouse, status, page, pageSize) }
            .fold(
                onSuccess = { data -> Result.success(data) },
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

    /**
     * 库存日报（AI-MOB-RPT-F02）：按仓库分页拉取当天各物料结存明细（只读）。
     *
     * warehouseId 必传（仓库必填，AGENTS.md §二）。与 getDailyReport 的
     * 「逐页合并全集」不同：库存日报明细可能上千行，页面边滚边出（loadMore
     * 驱动翻页），故此处只拉单页、由 ViewModel 持有分页状态。summary 由服务端
     * 按过滤后全集计算、每页都带（R1 汇总与分页解耦），首页取值即可。
     * 走 safeCall：服务端业务提示（如"请选择仓库"）原样透传，不被"网络错误"覆盖。
     *
     * AI-MOB-RPT-F03：date 传历史日期（yyyy-MM-dd）时服务端回推当天收市结存；
     * null 按今天。明细服务端已过滤为结存 > 0（用户口径：只显示有库存物料）。
     */
    suspend fun getStockDailyReport(
        warehouseId: String,
        keyword: String? = null,
        sort: String = "code_asc",
        page: Int = 1,
        pageSize: Int = 20,
        date: String? = null
    ): Result<StockDailyReportData> {
        ensureSession()
        return safeCall {
            api.stockDailyReport(
                warehouseId = warehouseId,
                keyword = keyword?.takeIf { it.isNotBlank() },
                sort = sort,
                page = page,
                pageSize = pageSize,
                date = date?.takeIf { it.isNotBlank() }
            )
        }
    }

    /**
     * 出入库明细（AI-MOB-RPT-F01 收尾：Android 消费页）：按仓库分页拉取
     * 指定日期范围内的出入库流水明细（只读，零写操作）。
     *
     * warehouseId 必传（仓库必填，AGENTS.md §二）；startDate/endDate 为
     * yyyy-MM-dd，null 时服务端按今天；direction 方向过滤 in/out/all；
     * summary 由服务端按过滤后全集计算、每页都带（R1 汇总与分页解耦）。
     * 与 getStockDailyReport 同模式：只拉单页，分页状态由 ViewModel 持有；
     * 走 safeCall，服务端业务提示（如"end_date 不能晚于今天"）原样透传。
     */
    suspend fun getInOutDetailReport(
        warehouseId: String,
        startDate: String? = null,
        endDate: String? = null,
        direction: String = "all",
        keyword: String? = null,
        sort: String = "time_desc",
        page: Int = 1,
        pageSize: Int = 20
    ): Result<InOutDetailReportData> {
        ensureSession()
        return safeCall {
            api.inOutDetailReport(
                warehouseId = warehouseId,
                startDate = startDate?.takeIf { it.isNotBlank() },
                endDate = endDate?.takeIf { it.isNotBlank() },
                direction = direction,
                keyword = keyword?.takeIf { it.isNotBlank() },
                sort = sort,
                page = page,
                pageSize = pageSize
            )
        }
    }

    /**
     * 库存台账（AI-MOB-LDG-F01）：按单一物料查看库存流水账（只读，零写操作）。
     *
     * - [warehouseId] 必传（仓库必填，AGENTS.md §二）；[materialCode] 必传且为
     *   精确编码（单一物料口径，AI-OS-LD-001；调用方先经 searchMaterial 选定）。
     * - [startDate]/[endDate]（yyyy-MM-dd）null 时服务端按 全部流水/今天
     *   （用户决策默认口径）；空串一律转 null，不发给服务端。
     * - summary（期初/入/出/期末）由服务端按过滤后全集计算、每页都带
     *   （R1 汇总与分页解耦）；只拉单页，分页状态由 ViewModel 持有。
     * - 走 safeCall，服务端业务提示（如"物料不存在"）原样透传。
     */
    suspend fun getStockLedgerReport(
        warehouseId: String,
        materialCode: String,
        startDate: String? = null,
        endDate: String? = null,
        page: Int = 1,
        pageSize: Int = 20
    ): Result<StockLedgerReportData> {
        ensureSession()
        return safeCall {
            api.stockLedgerReport(
                warehouseId = warehouseId,
                materialCode = materialCode,
                startDate = startDate?.takeIf { it.isNotBlank() },
                endDate = endDate?.takeIf { it.isNotBlank() },
                page = page,
                pageSize = pageSize
            )
        }
    }

    /**
     * 已建账明细列表（P1-C），带标准分页。
     *
     * 返回 [OpeningStockListData] 而非裸 List——列表页需要 total/total_pages
     * 才能翻页，需要 built_total/built_quantity 才能显示本仓建账概览。
     * （R1：这两个汇总由后端按仓库全集算，不随分页缩小。）
     */
    suspend fun getOpeningStockPage(
        warehouseId: Int? = null,
        keyword: String? = null,
        page: Int = 1,
        pageSize: Int = 20
    ): Result<OpeningStockListData> {
        return safeCall {
            api.getOpeningStock(
                warehouseId = warehouseId,
                keyword = keyword?.takeIf { it.isNotBlank() },
                page = page,
                pageSize = pageSize
            )
        }
    }

    /**
     * 兼容旧调用方：只要 items 的场景（如建账后回显）继续用这个。
     * 新列表页请用 [getOpeningStockPage]。
     */
    suspend fun getOpeningStock(warehouseId: Int? = null, keyword: String? = null): Result<List<OpeningStockDto>> {
        return getOpeningStockPage(warehouseId = warehouseId, keyword = keyword)
            .fold(
                onSuccess = { data -> Result.success(data.items) },
                onFailure = { Result.failure(it) }
            )
    }

    /**
     * 编辑已建账明细（P1-C）：按差额调整数量/单价。
     *
     * 走 safeCall 统一错误映射 + 幂等键，避免网络重试重复调整。
     */
    suspend fun updateOpeningStock(
        lineId: Int,
        request: OpeningStockUpdateRequest
    ): Result<OpeningStockUpdateResult> {
        return safeCall {
            api.updateOpeningStock(newRequestId(), lineId, request)
        }
    }

    suspend fun submitOpeningStock(request: OpeningStockRequest): Result<String> {
        return try {
            val response = api.submitOpeningStock(newRequestId(), request)
            val result = handleResponse<SubmitResult>(response)
            result.fold(
                onSuccess = {
                    request.lines.forEachIndexed { index, line ->
                        logOperation(
                            operationType = "opening_stock",
                            orderNo = "期初-${index + 1}",
                            materialCode = line.materialCode,
                            quantity = line.quantity
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
     * 语音建单（领料单草稿）。
     *
     * dry_run=true 只解析匹配（消歧）；dry_run=false 用确认的物料+数量建草稿。
     * 走 safeCall 统一错误映射 + 幂等键，避免网络重试重复建单。
     */
    suspend fun createVoiceOutDraft(request: VoiceOutDraftRequest): Result<VoiceOutDraftResult> {
        return safeCall {
            api.voiceOutDraft(newRequestId(), request)
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
            Result.failure(BusinessException(errorMsg ?: "请求失败 (${response.code()})",
                safeToEdit = response.code() in listOf(400, 404, 422)))
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
