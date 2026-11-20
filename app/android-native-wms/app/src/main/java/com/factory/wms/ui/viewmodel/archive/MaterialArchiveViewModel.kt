package com.factory.wms.ui.viewmodel.archive

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.factory.wms.data.model.MaterialArchiveDto
import com.factory.wms.data.model.MaterialArchiveImageDto
import com.factory.wms.data.model.MaterialArchiveImagesData
import com.factory.wms.data.model.PrintJobRequest
import com.factory.wms.data.repository.WmsRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.Job
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import com.factory.wms.data.api.RetrofitClient
import okhttp3.MultipartBody

data class MaterialArchiveUiState(
    val isLoading: Boolean = false,
    val error: String? = null,
    /** AI-APP-FIX-201：搜索列表为空时加载失败的持久错误（全屏错误态 + 重试） */
    val loadError: String? = null,
    // 搜索列表
    val keyword: String = "",
    val materials: List<MaterialArchiveDto> = emptyList(),
    val truncatedTotal: Int? = null,
    // 图片管理
    val imagesData: MaterialArchiveImagesData? = null,
    val images: List<MaterialArchiveImageDto> = emptyList(),
    /** AI-APP-FIX-201：档案图片为空时加载失败的持久错误（全屏错误态 + 重试） */
    val imagesError: String? = null,
    val uploading: Boolean = false,
    val deletingId: Int? = null,
    // 物料档案"打印"（远程打印队列）
    val printing: Boolean = false,
    val success: String? = null
)

class MaterialArchiveViewModel(application: Application) : AndroidViewModel(application) {

    private val repository = WmsRepository(application)

    private val _uiState = MutableStateFlow(MaterialArchiveUiState())
    val uiState: StateFlow<MaterialArchiveUiState> = _uiState.asStateFlow()

    private var listVersion = 0L
    private var detailVersion = 0L
    private var listJob: Job? = null
    private var detailJob: Job? = null

    fun clearError() {
        _uiState.value = _uiState.value.copy(error = null)
    }

    fun clearSuccess() {
        _uiState.value = _uiState.value.copy(success = null)
    }

    fun onKeywordChange(keyword: String) {
        _uiState.value = _uiState.value.copy(keyword = keyword)
    }

    fun search(keyword: String = _uiState.value.keyword) {
        listJob?.cancel()
        val version = ++listVersion
        val owner = RetrofitClient.sessionSnapshot()
        listJob = viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null, loadError = null)
            val result = repository.searchMaterialArchive(keyword)
            currentCoroutineContext().ensureActive()
            if (version != listVersion || owner.generation != RetrofitClient.sessionSnapshot().generation) return@launch
            _uiState.value = _uiState.value.copy(isLoading = false)
            result.fold(
                onSuccess = { matches ->
                    _uiState.value = _uiState.value.copy(
                        materials = matches.items,
                        truncatedTotal = matches.total.takeIf { matches.truncated }
                    )
                },
                onFailure = { e ->
                    // AI-APP-FIX-201：首屏失败（列表还空着）→ 全屏错误态；
                    // 带结果搜索失败 → Snackbar，保留旧列表。
                    if (_uiState.value.materials.isEmpty()) {
                        _uiState.value = _uiState.value.copy(loadError = e.message ?: "加载失败")
                    } else {
                        _uiState.value = _uiState.value.copy(error = e.message)
                    }
                }
            )
        }
    }

    fun loadImages(materialId: Int) {
        detailJob?.cancel()
        val version = ++detailVersion
        val owner = RetrofitClient.sessionSnapshot()
        detailJob = viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null, imagesError = null)
            val result = repository.getMaterialArchiveImages(materialId).mapCatching { data ->
                check(data.material?.id == materialId) { "未能获取当前物料的档案" }
                data
            }
            currentCoroutineContext().ensureActive()
            if (version != detailVersion || owner.generation != RetrofitClient.sessionSnapshot().generation) return@launch
            _uiState.value = _uiState.value.copy(isLoading = false)
            result.fold(
                onSuccess = { data ->
                    _uiState.value = _uiState.value.copy(
                        imagesData = data,
                        images = data.images ?: emptyList()
                    )
                },
                onFailure = { e ->
                    // AI-APP-FIX-201：图片首载失败 → 全屏错误态，不再伪装成"暂无档案图片"
                    if (_uiState.value.images.isEmpty()) {
                        _uiState.value = _uiState.value.copy(imagesError = e.message ?: "加载失败")
                    } else {
                        _uiState.value = _uiState.value.copy(error = e.message)
                    }
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

    /** 把物料档案加入远程打印队列（桌面打印工作站渲染出纸）。 */
    fun printMaterial(materialId: Int) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(printing = true, error = null)
            val result = repository.createPrintJob(
                PrintJobRequest(jobType = "material_archive", targetId = materialId)
            )
            result.fold(
                onSuccess = { _ ->
                    _uiState.value = _uiState.value.copy(
                        printing = false,
                        success = "已加入打印队列，请到桌面端打印工作站查看"
                    )
                },
                onFailure = { e ->
                    _uiState.value = _uiState.value.copy(printing = false, error = e.message)
                }
            )
        }
    }
}
