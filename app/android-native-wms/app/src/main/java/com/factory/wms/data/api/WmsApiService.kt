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
    suspend fun searchMaterial(@Query("keyword") keyword: String): Response<ApiEnvelope<List<MaterialDto>>>

    @GET("api/material/info")
    suspend fun materialInfo(@Query("code") code: String): Response<ApiEnvelope<MaterialDto>>

    @GET("api/material/all")
    suspend fun allMaterials(): Response<ApiEnvelope<List<MaterialDto>>>

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

    @GET("api/mobile/dashboard")
    suspend fun getDashboard(): Response<ApiEnvelope<DashboardDto>>

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