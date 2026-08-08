package com.factory.wms.ui.viewmodel.ai

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.factory.wms.data.api.DocumentOcrResult
import com.factory.wms.data.api.RecognizeMaterialResult
import com.factory.wms.data.model.InboundDraftRequest
import com.factory.wms.data.model.InboundDraftResult
import com.factory.wms.data.model.WarehouseDto
import com.factory.wms.data.repository.WmsRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import okhttp3.MultipartBody

data class AiUiState(
    val isLoading: Boolean = false,
    val error: String? = null,
    // Document OCR
    val ocrResult: DocumentOcrResult? = null,
    val ocrReply: String? = null,
    // Object recognition
    val recognizedMaterial: RecognizeMaterialResult? = null,
    val recognizedReply: String? = null,
    // Inbound draft from OCR confirmation
    val warehouses: List<WarehouseDto> = emptyList(),
    val selectedWarehouse: WarehouseDto? = null,
    val draftSubmitting: Boolean = false,
    val draftResult: InboundDraftResult? = null
)

class AiViewModel(application: Application) : AndroidViewModel(application) {

    private val repository = WmsRepository(application)

    private val _uiState = MutableStateFlow(AiUiState())
    val uiState: StateFlow<AiUiState> = _uiState.asStateFlow()

    fun clearError() {
        _uiState.value = _uiState.value.copy(error = null)
    }

    fun clearOcrResult() {
        _uiState.value = _uiState.value.copy(ocrResult = null, ocrReply = null, draftResult = null)
    }

    fun clearRecognizedMaterial() {
        _uiState.value = _uiState.value.copy(recognizedMaterial = null, recognizedReply = null)
    }

    fun documentOcr(imagePart: MultipartBody.Part) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null, ocrResult = null, ocrReply = null)
            val result = repository.documentOcr(imagePart)
            result.fold(
                onSuccess = { data ->
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        ocrResult = data,
                        ocrReply = data?.reply
                    )
                },
                onFailure = { e ->
                    _uiState.value = _uiState.value.copy(isLoading = false, error = e.message)
                }
            )
        }
    }

    fun recognizeMaterial(imagePart: MultipartBody.Part) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null, recognizedMaterial = null, recognizedReply = null)
            val result = repository.recognizeMaterial(imagePart)
            result.fold(
                onSuccess = { data ->
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        recognizedMaterial = data,
                        recognizedReply = data?.reply
                    )
                },
                onFailure = { e ->
                    _uiState.value = _uiState.value.copy(isLoading = false, error = e.message)
                }
            )
        }
    }

    fun loadWarehouses() {
        if (_uiState.value.warehouses.isNotEmpty() || _uiState.value.isLoading) return
        viewModelScope.launch {
            val result = repository.getWarehouses()
            result.fold(
                onSuccess = { warehouses ->
                    _uiState.value = _uiState.value.copy(
                        warehouses = warehouses,
                        selectedWarehouse = _uiState.value.selectedWarehouse
                            ?: warehouses.firstOrNull()
                    )
                },
                onFailure = { e ->
                    _uiState.value = _uiState.value.copy(error = e.message)
                }
            )
        }
    }

    fun selectWarehouse(warehouse: WarehouseDto) {
        _uiState.value = _uiState.value.copy(selectedWarehouse = warehouse)
    }

    fun submitInboundDraft(businessType: String, remark: String? = null) {
        val ocr = _uiState.value.ocrResult ?: run {
            _uiState.value = _uiState.value.copy(error = "请先识别单据")
            return
        }
        val matchedLines = (ocr.items ?: emptyList())
            .filter { it.matched == true && !it.code.isNullOrBlank() }
        if (matchedLines.isEmpty()) {
            _uiState.value = _uiState.value.copy(error = "没有已匹配到建档物料的识别行，无法生成入库草稿")
            return
        }
        val warehouse = _uiState.value.selectedWarehouse
        if (warehouse == null) {
            _uiState.value = _uiState.value.copy(error = "请选择仓库")
            return
        }
        val request = InboundDraftRequest(
            lines = matchedLines.map {
                com.factory.wms.data.model.InboundDraftLine(
                    materialCode = it.code.orEmpty(),
                    quantity = it.quantity ?: 1.0,
                    price = it.price
                )
            },
            businessType = businessType,
            warehouseCode = warehouse.code,
            remark = remark
        )
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(draftSubmitting = true, error = null)
            val result = repository.createInboundDraft(request)
            _uiState.value = _uiState.value.copy(draftSubmitting = false)
            result.fold(
                onSuccess = { data ->
                    _uiState.value = _uiState.value.copy(draftResult = data)
                },
                onFailure = { e ->
                    _uiState.value = _uiState.value.copy(error = e.message)
                }
            )
        }
    }
}