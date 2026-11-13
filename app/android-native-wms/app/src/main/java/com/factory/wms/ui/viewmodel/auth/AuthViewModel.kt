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
            // BUG-2026-09-13-023（启动崩溃）：本协程是 App 冷启动的必经路径（AppNavGraph
            // 组合期即创建 AuthViewModel）。此前无 try/catch——任一持久化读取失败（Keystore
            // 失效、DataStore 文件损坏、磁盘满）都会让协程抛未捕获异常并**杀掉整个进程**，
            // 现场表现为"应用屡次停止运行"。
            // 会话还原属于"尽力而为"：失败时保持默认的未登录状态，让用户走正常登录流程，
            // 绝不能因本地缓存问题导致 App 打不开。
            try {
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
                    // 自动登录的关键一步：进程被杀后 RetrofitClient.authToken 是内存态，
                    // 必须把持久化在 EncryptedSharedPreferences 的 token 重新注入内存，
                    // 否则重启后首个请求不带 Authorization → 401 → 拦截器触发登出清凭据，
                    // 用户每次点图标都被迫重新登录。
                    RetrofitClient.setToken(token)
                    _uiState.value = _uiState.value.copy(
                        isLoggedIn = true,
                        username = username ?: "",
                        role = role ?: "",
                        baseUrl = baseUrl
                    )
                }
            } catch (e: Exception) {
                android.util.Log.w(
                    "AuthVM",
                    "会话还原失败，降级为未登录: ${e.javaClass.simpleName}: ${e.message}"
                )
                _uiState.value = _uiState.value.copy(isLoggedIn = false)
            }
        }
        // Observe 401 unauthorized events from the token interceptor
        viewModelScope.launch {
            // 登出清理同样兜底：清理失败不能杀进程（用户已处于下台状态）。
            try {
                AuthEventBus.unauthorizedEvents.collect {
                    repository.logout()
                    _uiState.value = AuthUiState()
                }
            } catch (e: Exception) {
                android.util.Log.w("AuthVM", "401 登出处理异常（已忽略）: ${e.message}")
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
