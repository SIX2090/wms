package com.factory.wms.ui.viewmodel.home

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.factory.wms.data.model.DashboardDto
import com.factory.wms.data.repository.WmsRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class HomeUiState(
    val isLoading: Boolean = false,
    val dashboard: DashboardDto? = null,
    val error: String? = null
)

class HomeViewModel(application: Application) : AndroidViewModel(application) {

    private val repository = WmsRepository(application)

    private val _uiState = MutableStateFlow(HomeUiState())
    val uiState: StateFlow<HomeUiState> = _uiState.asStateFlow()

    init {
        loadDashboard()
    }

    fun loadDashboard() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            val result = repository.getDashboard()
            result.fold(
                onSuccess = { dashboard ->
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        dashboard = dashboard,
                        error = null
                    )
                },
                onFailure = { e ->
                    // 概览加载失败降级隐藏，不阻塞首页其余功能
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        dashboard = null,
                        error = e.message
                    )
                }
            )
        }
    }
}