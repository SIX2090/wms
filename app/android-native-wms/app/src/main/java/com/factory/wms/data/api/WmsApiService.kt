package com.factory.wms.data.api

import com.factory.wms.data.model.*
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
    suspend fun submitInbound(@Body request: InboundRequest): Response<ApiEnvelope<SubmitResult>>

    @POST("api/outbound")
    suspend fun submitOutbound(@Body request: OutboundRequest): Response<ApiEnvelope<SubmitResult>>

    @POST("api/stocktake")
    suspend fun submitStocktake(@Body request: StocktakeRequest): Response<ApiEnvelope<SubmitResult>>

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
    suspend fun getWarehouses(): Response<ApiEnvelope<List<WarehouseDto>>>

    @GET("api/opening_stock")
    suspend fun getOpeningStock(
        @Query("warehouse_id") warehouseId: Int? = null,
        @Query("keyword") keyword: String? = null
    ): Response<ApiEnvelope<OpeningStockListData>>

    @POST("api/opening_stock")
    suspend fun submitOpeningStock(@Body request: OpeningStockRequest): Response<ApiEnvelope<SubmitResult>>

    @POST("api/mobile/inbound_draft")
    suspend fun createInboundDraft(@Body request: InboundDraftRequest): Response<ApiEnvelope<InboundDraftResult>>
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
    val extracted: DocumentOcrResult?
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
    val confidence: Double?
)