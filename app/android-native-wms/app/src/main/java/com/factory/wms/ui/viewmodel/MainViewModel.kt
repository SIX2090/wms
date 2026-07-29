package com.factory.wms.ui.viewmodel

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.factory.wms.data.model.*
import com.factory.wms.data.repository.WmsRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class AppUiState(
    val isLoggedIn: Boolean = false,
    val isLoading: Boolean = false,
    val username: String = "",
    val role: String = "",
    val baseUrl: String = "http://10.0.2.2:5000",
    val error: String? = null,
    val success: String? = null,
    // Material scan result
    val scannedMaterial: MaterialDto? = null,
    val scannedCode: String = "",
    // Scan list for batch operations
    val scanLines: List<ScanLine> = emptyList(),
    val totalQuantity: Double = 0.0,
    // Document OCR
    val ocrResult: DocumentOcrResult? = null,
    val ocrReply: String? = null,
    // Object recognition
    val recognizedMaterial: RecognizeMaterialResult? = null,
    val recognizedReply: String? = null
)

class MainViewModel(application: Application) : AndroidViewModel(application) {

    private val repository = WmsRepository(application)

    private val _uiState = MutableStateFlow(AppUiState())
    val uiState: StateFlow<AppUiState> = _uiState.asStateFlow()

    init {
        viewModelScope.launch {
            val token = repository.getSavedToken()
            val baseUrl = repository.getSavedBaseUrl()
            val username = repository.getUsername()
            val role = repository.getRole()
            if (token != null && baseUrl != null) {
                _uiState.value = _uiState.value.copy(
                    isLoggedIn = true,
                    username = username ?: "",
                    role = role ?: "",
                    baseUrl = baseUrl
                )
            }
        }
    }

    fun login(username: String, password: String, baseUrl: String) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            val result = repository.login(username, password, baseUrl)
            result.fold(
                onSuccess = { data ->
                    _uiState.value = _uiState.value.copy(
                        isLoggedIn = true,
                        isLoading = false,
                        username = username,
                        role = data.user.role ?: "",
                        baseUrl = baseUrl,
                        error = null
                    )
                },
                onFailure = { e ->
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = e.message
                    )
                }
            )
        }
    }

    fun logout() {
        viewModelScope.launch {
            repository.logout()
            _uiState.value = AppUiState()
        }
    }

    fun clearError() {
        _uiState.value = _uiState.value.copy(error = null)
    }

    fun clearSuccess() {
        _uiState.value = _uiState.value.copy(success = null)
    }

    fun clearScannedMaterial() {
        _uiState.value = _uiState.value.copy(scannedMaterial = null, scannedCode = "")
    }

    fun clearOcrResult() {
        _uiState.value = _uiState.value.copy(ocrResult = null, ocrReply = null)
    }

    fun clearRecognizedMaterial() {
        _uiState.value = _uiState.value.copy(recognizedMaterial = null, recognizedReply = null)
    }

    fun addScanLine(line: ScanLine) {
        val current = _uiState.value.scanLines.toMutableList()
        // Check if same material already exists, update quantity
        val existingIndex = current.indexOfFirst { it.material_code == line.material_code }
        if (existingIndex >= 0) {
            val existing = current[existingIndex]
            current[existingIndex] = existing.copy(quantity = existing.quantity + line.quantity)
        } else {
            current.add(line)
        }
        _uiState.value = _uiState.value.copy(
            scanLines = current,
            totalQuantity = current.sumOf { it.quantity }
        )
    }

    fun removeScanLine(index: Int) {
        val current = _uiState.value.scanLines.toMutableList()
        if (index in current.indices) {
            current.removeAt(index)
            _uiState.value = _uiState.value.copy(
                scanLines = current,
                totalQuantity = current.sumOf { it.quantity }
            )
        }
    }

    fun clearScanLines() {
        _uiState.value = _uiState.value.copy(scanLines = emptyList(), totalQuantity = 0.0)
    }

    fun searchMaterialByCode(code: String) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            val result = repository.getMaterialInfo(code)
            result.fold(
                onSuccess = { material ->
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        scannedMaterial = material,
                        scannedCode = code
                    )
                },
                onFailure = { e ->
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = e.message,
                        scannedMaterial = null,
                        scannedCode = code
                    )
                }
            )
        }
    }

    fun submitInbound(businessType: String = "采购入库", warehouse: String? = null) {
        viewModelScope.launch {
            val lines = _uiState.value.scanLines
            if (lines.isEmpty()) {
                _uiState.value = _uiState.value.copy(error = "请先扫描物料")
                return@launch
            }
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            val request = InboundRequest(
                lines = lines,
                businessType = businessType,
                warehouse = warehouse,
                warehouseCode = warehouse
            )
            val result = repository.submitInbound(request)
            result.fold(
                onSuccess = { submitResult ->
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        success = "入库成功！单号: ${submitResult.order_no}",
                        scanLines = emptyList(),
                        totalQuantity = 0.0
                    )
                },
                onFailure = { e ->
                    _uiState.value = _uiState.value.copy(isLoading = false, error = e.message)
                }
            )
        }
    }

    fun submitOutbound(receiver: String? = null, department: String? = null, warehouse: String? = null) {
        viewModelScope.launch {
            val lines = _uiState.value.scanLines
            if (lines.isEmpty()) {
                _uiState.value = _uiState.value.copy(error = "请先扫描物料")
                return@launch
            }
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            val request = OutboundRequest(
                lines = lines,
                receiver = receiver,
                department = department,
                warehouse = warehouse,
                warehouseCode = warehouse
            )
            val result = repository.submitOutbound(request)
            result.fold(
                onSuccess = { submitResult ->
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        success = "出库成功！单号: ${submitResult.order_no}",
                        scanLines = emptyList(),
                        totalQuantity = 0.0
                    )
                },
                onFailure = { e ->
                    _uiState.value = _uiState.value.copy(isLoading = false, error = e.message)
                }
            )
        }
    }

    fun submitStocktake() {
        viewModelScope.launch {
            val lines = _uiState.value.scanLines
            if (lines.isEmpty()) {
                _uiState.value = _uiState.value.copy(error = "请先扫描盘点物料")
                return@launch
            }
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            val stocktakeLines = lines.map { line ->
                StocktakeLine(
                    material_code = line.material_code,
                    actual_stock = line.quantity,
                    system_stock = null
                )
            }
            val request = StocktakeRequest(lines = stocktakeLines, mode = "scan")
            val result = repository.submitStocktake(request)
            result.fold(
                onSuccess = { submitResult ->
                    val msg = if (submitResult.check_no != null)
                        "盘点成功！盘点单号: ${submitResult.check_no}"
                    else "盘点提交成功"
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        success = msg,
                        scanLines = emptyList(),
                        totalQuantity = 0.0
                    )
                },
                onFailure = { e ->
                    _uiState.value = _uiState.value.copy(isLoading = false, error = e.message)
                }
            )
        }
    }

    fun documentOcr(imagePart: okhttp3.MultipartBody.Part) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null, ocrResult = null, ocrReply = null)
            val result = repository.documentOcr(imagePart)
            result.fold(
                onSuccess = { envelope ->
                    val data = envelope.data
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

    fun recognizeMaterial(imagePart: okhttp3.MultipartBody.Part) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null, recognizedMaterial = null, recognizedReply = null)
            val result = repository.recognizeMaterial(imagePart)
            result.fold(
                onSuccess = { envelope ->
                    val data = envelope.data
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
}