package com.factory.wms.ui.viewmodel.archive

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.factory.wms.data.model.MaterialArchiveDto
import com.factory.wms.data.model.MaterialArchiveImageDto
import com.factory.wms.data.model.MaterialArchiveImagesData
import com.factory.wms.data.repository.WmsRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import okhttp3.MultipartBody

data class MaterialArchiveUiState(
    val isLoading: Boolean = false,
    val error: String? = null,
    // 搜索列表
    val keyword: String = "",
    val materials: List<MaterialArchiveDto> = emptyList(),
    // 图片管理
    val imagesData: MaterialArchiveImagesData? = null,
    val images: List<MaterialArchiveImageDto> = emptyList(),
    val uploading: Boolean = false,
    val deletingId: Int? = null
)

class MaterialArchiveViewModel(application: Application) : AndroidViewModel(application) {

    private val repository = WmsRepository(application)

    private val _uiState = MutableStateFlow(MaterialArchiveUiState())
    val uiState: StateFlow<MaterialArchiveUiState> = _uiState.asStateFlow()

    fun clearError() {
        _uiState.value = _uiState.value.copy(error = null)
    }

    fun onKeywordChange(keyword: String) {
        _uiState.value = _uiState.value.copy(keyword = keyword)
    }

    fun search(keyword: String = _uiState.value.keyword) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            val result = repository.searchMaterialArchive(keyword)
            _uiState.value = _uiState.value.copy(isLoading = false)
            result.fold(
                onSuccess = { materials ->
                    _uiState.value = _uiState.value.copy(materials = materials)
                },
                onFailure = { e ->
                    _uiState.value = _uiState.value.copy(error = e.message)
                }
            )
        }
    }

    fun loadImages(materialId: Int) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            val result = repository.getMaterialArchiveImages(materialId)
            _uiState.value = _uiState.value.copy(isLoading = false)
            result.fold(
                onSuccess = { data ->
                    _uiState.value = _uiState.value.copy(
                        imagesData = data,
                        images = data.images ?: emptyList()
                    )
                },
                onFailure = { e ->
                    _uiState.value = _uiState.value.copy(error = e.message)
                }
            )
        }
    }

    fun uploadImage(materialId: Int, imagePart: MultipartBody.Part) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(uploading = true, error = null)
            val result = repository.uploadMaterialArchiveImage(materialId, imagePart)
            _uiState.value = _uiState.value.copy(uploading = false)
            result.fold(
                onSuccess = { _ ->
                    // 上传成功后重新拉取列表，保证数量与排序与服务端一致
                    loadImages(materialId)
                },
                onFailure = { e ->
                    _uiState.value = _uiState.value.copy(error = e.message)
                }
            )
        }
    }

    fun deleteImage(materialId: Int, imageId: Int) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(deletingId = imageId, error = null)
            val result = repository.deleteMaterialArchiveImage(imageId)
            _uiState.value = _uiState.value.copy(deletingId = null)
            result.fold(
                onSuccess = { _ ->
                    loadImages(materialId)
                },
                onFailure = { e ->
                    _uiState.value = _uiState.value.copy(error = e.message)
                }
            )
        }
    }
}