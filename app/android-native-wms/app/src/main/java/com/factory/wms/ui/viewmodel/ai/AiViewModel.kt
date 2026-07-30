package com.factory.wms.ui.viewmodel.ai

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.factory.wms.data.api.DocumentOcrResult
import com.factory.wms.data.api.RecognizeMaterialResult
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
    val recognizedReply: String? = null
)

class AiViewModel(application: Application) : AndroidViewModel(application) {

    private val repository = WmsRepository(application)

    private val _uiState = MutableStateFlow(AiUiState())
    val uiState: StateFlow<AiUiState> = _uiState.asStateFlow()

    fun clearError() {
        _uiState.value = _uiState.value.copy(error = null)
    }

    fun clearOcrResult() {
        _uiState.value = _uiState.value.copy(ocrResult = null, ocrReply = null)
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
}