package com.factory.wms.ui.viewmodel.stocktake

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.factory.wms.data.model.StocktakeRecordDto
import com.factory.wms.data.repository.WmsRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/**
 * 盘点记录回查（AI-MOB-CHECK-F01）。
 *
 * 手机盘点提交后记录只挂在 PC 批次详情，作业员本人无从回看自己盘过哪些单、
 * 差异多少、批次是否已被 PC 采纳，出错时无处对账。本页按「本人经手」回查。
 */
data class StocktakeRecordUiState(
    val isLoading: Boolean = false,
    val error: String? = null,
    /** 记录列表（服务端只返回本人记录） */
    val records: List<StocktakeRecordDto> = emptyList(),
    val total: Int = 0,
    val page: Int = 1,
    val pageSize: Int = 20,
    val totalPages: Int = 0,
    /** true 时展示已作废记录（默认只看正常记录） */
    val showVoided: Boolean = false
) {
    val isEmpty: Boolean get() = !isLoading && records.isEmpty()
    val hasMore: Boolean get() = page < totalPages
}

class StocktakeRecordViewModel(application: Application) : AndroidViewModel(application) {
    private val repository = WmsRepository(application)
    private val _uiState = MutableStateFlow(StocktakeRecordUiState())
    val uiState: StateFlow<StocktakeRecordUiState> = _uiState.asStateFlow()

    init {
        // BUG-2026-08-24-006：ViewModel 在 App 启动导航图组合阶段即被创建，
        // 此时可能尚未登录/会话未还原，不能在 init 拉数据（会留下过期错误态）。
        // 加载统一由页面进入时的 LaunchedEffect 触发。
    }

    /** 首次加载 / 下拉刷新：回到第 1 页覆盖。 */
    fun load() {
        fetch(page = 1, append = false)
    }

    /** 上拉加载下一页（追加）。 */
    fun loadMore() {
        if (_uiState.value.isLoading || !_uiState.value.hasMore) return
        fetch(page = _uiState.value.page + 1, append = true)
    }

    /** 切换「已作废」视图：重新从第 1 页拉取。 */
    fun toggleVoided() {
        if (_uiState.value.isLoading) return
        _uiState.value = _uiState.value.copy(showVoided = !_uiState.value.showVoided)
        load()
    }

    private fun fetch(page: Int, append: Boolean) {
        val state = _uiState.value
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            // 服务端 status 缺省为 completed；显式传 void 才看已作废记录
            val status = if (state.showVoided) "void" else "completed"
            repository.loadStocktakeRecords(
                warehouse = null, // 回看本人全部经手记录（跨仓），不做仓库过滤
                status = status,
                page = page,
                pageSize = state.pageSize
            ).fold(
                onSuccess = { data ->
                    val merged = if (append) state.records + data.items else data.items
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        records = merged,
                        total = data.total,
                        page = data.page,
                        pageSize = data.pageSize,
                        totalPages = data.totalPages
                    )
                },
                onFailure = { e ->
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = e.message ?: "加载失败"
                    )
                }
            )
        }
    }

    fun clearError() {
        _uiState.value = _uiState.value.copy(error = null)
    }
}
