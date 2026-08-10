package com.factory.wms.ui.viewmodel.auth

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.factory.wms.data.api.AuthEventBus
import com.factory.wms.data.api.RetrofitClient
import com.factory.wms.data.repository.WmsRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class AuthUiState(
    val isLoggedIn: Boolean = false,
    val isLoading: Boolean = false,
    val username: String = "",
    val role: String = "",
    val baseUrl: String = "",
    val error: String? = null
)

class AuthViewModel(application: Application) : AndroidViewModel(application) {

    private val repository = WmsRepository(application)

    private val _uiState = MutableStateFlow(AuthUiState())
    val uiState: StateFlow<AuthUiState> = _uiState.asStateFlow()

    init {
        viewModelScope.launch {
            val token = repository.getSavedToken()
            val baseUrl = repository.getSavedBaseUrl()
            val username = repository.getUsername()
            val role = repository.getRole()
            // App 重启后必须恢复 RetrofitClient 的 baseUrl，否则所有 API 请求
            // 会 fallback 到默认值 http://127.0.0.1:5000/（本地回环，手机连不上）。
            if (!baseUrl.isNullOrBlank()) {
                RetrofitClient.setBaseUrl(baseUrl)
            }
            if (token != null && baseUrl != null) {
                _uiState.value = _uiState.value.copy(
                    isLoggedIn = true,
                    username = username ?: "",
                    role = role ?: "",
                    baseUrl = baseUrl
                )
            }
        }
        // Observe 401 unauthorized events from the token interceptor
        viewModelScope.launch {
            AuthEventBus.unauthorizedEvents.collect {
                repository.logout()
                _uiState.value = AuthUiState()
            }
        }
    }

    fun login(username: String, password: String, baseUrl: String) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            val result = repository.login(username, password, baseUrl)
            result.fold(
                onSuccess = { data ->
                    // 登录成功，复位 401 事件门闩，允许下次令牌失效再次触发
                    AuthEventBus.reset()
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
            _uiState.value = AuthUiState()
        }
    }

    fun clearError() {
        _uiState.value = _uiState.value.copy(error = null)
    }
}
