package com.factory.wms.data.api

import com.factory.wms.data.model.*
import com.google.gson.annotations.SerializedName
import okhttp3.MultipartBody
import okhttp3.RequestBody
import retrofit2.Response
import retrofit2.http.*

interface WmsApiService {

    @POST("api/login")
    suspend fun login(@Body request: LoginRequest): Response<ApiEnvelope<LoginData>>

    @GET("api/material/search")
    suspend fun searchMaterial(
        @Query("keyword") keyword: String,
        // BUG-2026-09-03-004：已选仓库时传仓库名/编码，返回该仓仓库级账面库存
        @Query("warehouse") warehouse: String? = null
    ): Response<ApiEnvelope<List<MaterialDto>>>

    @GET("api/material/info")
    suspend fun materialInfo(
        @Query("code") code: String,
        @Query("warehouse") warehouse: String? = null
    ): Response<ApiEnvelope<MaterialDto>>

    @GET("api/material/all")
    suspend fun allMaterials(): Response<ApiEnvelope<List<MaterialDto>>>

    /**
     * AI-MOB-STOCK-F01：库存列表查询（分页）。
     *
     * 复用既有后端端点 `GET /api/mobile/stock/query`（native_api.py），不新增/修改后端。
     * 返回**仓库级账面库存**（服务端经 get_warehouse_stock_quantities 实时聚合，
     * 绝不回退全局 Material.stock）。
     *
     * - warehouse：仓库名或编码，**必填**（AGENTS.md 第二节）。服务端未取到仓库
     *   返回 400「请选择仓库」，Android 侧须先选仓再发起请求。
     * - keyword：按 编码/名称/规格 模糊匹配；为空则返回全部物料分页。
     * - 响应含完整分页元数据（total/page/page_size/total_pages），调用方按
     *   total_pages 翻页合并取全，不得把默认 page_size 当业务上限（R1）。
     */
    @GET("api/mobile/stock/query")
    suspend fun stockQuery(
        @Query("warehouse") warehouse: String,
        @Query("keyword") keyword: String? = null,
        @Query("page") page: Int = 1,
        @Query("page_size") pageSize: Int = 20
    ): Response<ApiEnvelope<StockQueryPageData>>

    @POST("api/inbound")
    suspend fun submitInbound(
        @Header("X-Idempotency-Key") requestId: String,
        @Body request: InboundRequest
    ): Response<ApiEnvelope<SubmitResult>>

    @POST("api/outbound")
    suspend fun submitOutbound(
        @Header("X-Idempotency-Key") requestId: String,
        @Body request: OutboundRequest
    ): Response<ApiEnvelope<SubmitResult>>

    @POST("api/stocktake")
    suspend fun submitStocktake(
        @Header("X-Idempotency-Key") requestId: String,
        @Body request: StocktakeRequest
    ): Response<ApiEnvelope<SubmitResult>>

    /** INV-BATCH-001-E：某仓库进行中盘点单列表（盘点提交前必须先选单） */
    @GET("api/stocktake/check_orders")
    suspend fun listPendingCheckOrders(
        @Query("warehouse") warehouse: String? = null
    ): Response<ApiEnvelope<CheckOrdersListData>>

    /**
     * AI-MOB-CHECK-F01：盘点记录回查（仅本人提交的扫码盘点单，分页）。
     * warehouse 为 null 时回看本人全部经手记录；status 缺省只看正常记录。
     */
    @GET("api/mobile/stocktake/list")
    suspend fun listStocktakeRecords(
        @Query("warehouse") warehouse: String? = null,
        @Query("status") status: String? = null,
        @Query("page") page: Int = 1,
        @Query("page_size") pageSize: Int = 20
    ): Response<ApiEnvelope<StocktakeRecordListData>>

    @Multipart
    @POST("api/ai/document_ocr")
    suspend fun documentOcr(
        @Part image: MultipartBody.Part,
        @Part("document_type") documentType: RequestBody? = null
    ): Response<ApiEnvelope<DocumentOcrResult>>

    @Multipart
    @POST("mobile/api/recognize_material")
    suspend fun recognizeMaterial(
        @Part image: MultipartBody.Part
    ): Response<ApiEnvelope<RecognizeMaterialResult>>

    @GET("api/warehouses")
    suspend fun getWarehouses(): Response<ApiEnvelope<WarehousesListData>>

    /** 2026-09-12 领料部门下拉：启用部门列表 */
    @GET("api/departments")
    suspend fun getDepartments(): Response<ApiEnvelope<DepartmentsListData>>

    /** 2026-09-12 领料人下拉：员工列表，department_id 过滤（选了部门后联动） */
    @GET("api/employees")
    suspend fun getEmployees(
        @Query("department_id") departmentId: Long? = null
    ): Response<ApiEnvelope<EmployeesListData>>

    /** 合同编号模糊搜索（选填合同字段快速匹配：如 0709 匹配 HD260709） */
    @GET("api/mobile/contracts")
    suspend fun searchContracts(
        @Query("keyword") keyword: String? = null
    ): Response<ApiEnvelope<ContractsListData>>

    /**
     * 每日明细报表：type=purchase_in（采购入库）/ requisition（领料单），date 缺省为今天。
     * warehouseId：仓 id 字符串或 "all"（全部仓库汇总）；null 表示跟随系统默认仓
     * （BUG-2026-09-10-009：多仓用户此前只能看默认仓，录在其他仓的单据查不到）。
     */
    @GET("api/mobile/report/daily_detail")
    suspend fun dailyReportDetail(
        @Query("type") type: String,
        @Query("date") date: String? = null,
        @Query("warehouse_id") warehouseId: String? = null,
        @Query("page") page: Int = 1,
        @Query("page_size") pageSize: Int = 20
    ): Response<ApiEnvelope<DailyReportData>>

    @GET("api/opening_stock")
    suspend fun getOpeningStock(
        @Query("warehouse_id") warehouseId: Int? = null,
        @Query("keyword") keyword: String? = null
    ): Response<ApiEnvelope<OpeningStockListData>>

    @POST("api/opening_stock")
    suspend fun submitOpeningStock(
        @Header("X-Idempotency-Key") requestId: String,
        @Body request: OpeningStockRequest
    ): Response<ApiEnvelope<SubmitResult>>

    @POST("api/mobile/inbound_draft")
    suspend fun createInboundDraft(
        @Header("X-Idempotency-Key") requestId: String,
        @Body request: InboundDraftRequest
    ): Response<ApiEnvelope<InboundDraftResult>>

    /**
     * 语音建单：说「领8*25螺丝 1000个」→ 生成领料单草稿（pending，不扣库存）。
     *
     * 两阶段：dry_run=true 只解析匹配（消歧）；dry_run=false 建草稿。
     * 多命中时后端返回 match_status=multiple + matches，由客户端点选后再建单。
     */
    @POST("api/mobile/voice_out_draft")
    suspend fun voiceOutDraft(
        @Header("X-Idempotency-Key") requestId: String,
        @Body request: VoiceOutDraftRequest
    ): Response<ApiEnvelope<VoiceOutDraftResult>>

    @GET("api/mobile/dashboard")
    suspend fun getDashboard(
        // BUG-2026-09-10-010：首页概览支持指定仓库 / all（全部仓库汇总）；
        // 不传则由服务端回退默认仓（兼容旧行为）
        @Query("warehouse_id") warehouseId: String? = null
    ): Response<ApiEnvelope<DashboardDto>>

    // ── 首页概览下钻（AI-MOB-DRILLDOWN-01）──
    // 后端三个列表接口早已存在，手机端此前未接入：首页「库存告警」只跳到
    // 查库存的空搜索框、「待处理单据」点了完全没反应。以下为对应声明。

    // 仓库统一传 warehouse_id（服务端 resolve_request_warehouse 支持 id/code/name）：
    // 首页存的本来就是仓库 id，用 id 可规避同名仓库的歧义。

    /** 库存告警清单：仓库级库存 <= 最低库存的物料，按缺口排序。 */
    @GET("api/mobile/alert/list")
    suspend fun getAlertList(
        @Query("warehouse_id") warehouseId: String,
        @Query("page") page: Int = 1,
        @Query("page_size") pageSize: Int = 20
    ): Response<ApiEnvelope<AlertListData>>

    /** 入库单列表：status 传 pending/completed 筛选，留空为全部。 */
    @GET("api/mobile/in_order/list")
    suspend fun getInOrderList(
        @Query("warehouse_id") warehouseId: String,
        @Query("status") status: String? = null,
        @Query("keyword") keyword: String? = null,
        @Query("page") page: Int = 1,
        @Query("page_size") pageSize: Int = 20
    ): Response<ApiEnvelope<MobileOrderListData>>

    /** 出库单列表：status 传 pending/completed 筛选，留空为全部。 */
    @GET("api/mobile/out_order/list")
    suspend fun getOutOrderList(
        @Query("warehouse_id") warehouseId: String,
        @Query("status") status: String? = null,
        @Query("keyword") keyword: String? = null,
        @Query("page") page: Int = 1,
        @Query("page_size") pageSize: Int = 20
    ): Response<ApiEnvelope<MobileOrderListData>>

    @Multipart
    @POST("mobile/api/asr")
    suspend fun asrAudio(
        @Part audio: MultipartBody.Part
    ): Response<AsrResult>

    // ── 物料档案（多图） ──

    @GET("mobile/api/material_archive/search")
    suspend fun searchMaterialArchive(
        @Query("keyword") keyword: String
    ): Response<ApiEnvelope<List<MaterialArchiveDto>>>

    @GET("mobile/api/material_archive/{id}/images")
    suspend fun getMaterialArchiveImages(
        @Path("id") id: Int
    ): Response<ApiEnvelope<MaterialArchiveImagesData>>

    @Multipart
    @POST("mobile/api/material_archive/{id}/images")
    suspend fun uploadMaterialArchiveImage(
        @Path("id") id: Int,
        @Part image: MultipartBody.Part
    ): Response<ApiEnvelope<MaterialArchiveImageDto>>

    @DELETE("mobile/api/material_archive/images/{imageId}")
    suspend fun deleteMaterialArchiveImage(
        @Path("imageId") imageId: Int
    ): Response<ApiEnvelope<Unit>>

    // ── 远程打印队列（提交入库/出库后"打印单据"、物料档案"打印"） ──

    @POST("print_queue/jobs")
    suspend fun createPrintJob(
        @Body request: PrintJobRequest
    ): Response<ApiEnvelope<PrintJobResult>>
}

/**
 * 语音指令云识别结果。
 *
 * 后端 /mobile/api/asr 走后端中转（腾讯云一句话识别），返回结构不是
 * [ApiEnvelope] 包裹，而是扁平的 `{status, text, msg}`：
 * - 成功：`{"status": "success", "text": "入库"}`
 * - 失败：`{"status": "error", "msg": "..."}`（HTTP 400/500/502）
 */
data class AsrResult(
    @SerializedName("status") val status: String?,
    @SerializedName("text") val text: String?,
    @SerializedName("msg") val msg: String?
) {
    fun isOk(): Boolean = status == "success"
}

data class OcrItem(
    val code: String?,
    val name: String?,
    val spec: String?,
    val quantity: Double?,
    val price: Double?,
    val matched: Boolean?,
    val unit: String?
)

data class DocumentOcrResult(
    val document_type: String?,
    val supplier: String?,
    val order_no: String?,
    val date: String?,
    val items: List<OcrItem>?,
    val remarks: String?,
    val reply: String?,
    val matches: List<MaterialDto>?,
    val match_count: Int?,
    val extracted: ExtractedDocument?
)

data class ExtractedDocument(
    @SerializedName("document_type") val documentType: String?,
    val supplier: String?,
    @SerializedName("order_no") val orderNo: String?,
    @SerializedName("purchase_order_no") val purchaseOrderNo: String?,
    val date: String?,
    val items: List<OcrItem>?,
    val remarks: String?
)

data class RecognizeMaterialResult(
    val reply: String?,
    val extracted: ExtractedMaterial?,
    val matches: List<MaterialDto>?,
    val match_count: Int?
)

data class ExtractedMaterial(
    val code: String?,
    val name: String?,
    val spec: String?,
    val quantity: Double?,
    val confidence: Double?,
    val description: String?
)