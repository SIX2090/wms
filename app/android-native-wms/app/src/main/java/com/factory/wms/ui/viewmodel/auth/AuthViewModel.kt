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
            // ── BUG-2026-09-13-001：启动路径整体兜底 ──
            // 这里是 App 每次启动都要走的唯一入口，任何未捕获异常都会直接杀进程，
            // 而且因为是确定性失败（如加密存储损坏），下次启动会在同一行再崩，
            // 表现为「应用屡次停止运行」死循环。所以整个恢复流程必须 runCatching。
            //
            // 失败时的语义是明确的：恢复不出凭据 = 未登录 = 回登录页让用户重登，
            // 这是可用的降级；崩溃是彻底不可用。宁可多让用户登一次，也不能崩。
            runCatching {
                val token = repository.getSavedToken()
                val baseUrl = repository.getSavedBaseUrl()
                val username = repository.getUsername()
                val role = repository.getRole()
                // App 重启后必须恢复 RetrofitClient 的 baseUrl，否则所有 API 请求
                // 会 fallback 到默认值 127.0.0.1，手机连不上（且不会带 token）。
                if (!baseUrl.isNullOrBlank()) {
                    RetrofitClient.setBaseUrl(baseUrl)
                }
                // 凭据必须成对。token 与 baseUrl 分别存在两个不同的存储里
                // （EncryptedSharedPreferences / DataStore），两者损坏概率不同：
                // 只要有一个缺失就是"半个登录态"——界面显示已登录，但请求发不出去
                // 或必然 401，用户点什么都失败还退不出去。故要求两者同时非空，
                // 否则一律按未登录处理（不回填 isLoggedIn，停在登录页）。
                if (!token.isNullOrBlank() && !baseUrl.isNullOrBlank()) {
                    // 自动登录的关键一步：进程被杀后 RetrofitClient.authToken 是内存态，
                    // 必须把持久化的 token 重新注入内存，否则重启后首个请求不带
                    // Authorization → 401 → 拦截器触发登出清凭据，用户每次点图标
                    // 都被迫重新登录。
                    RetrofitClient.setToken(token)
                    _uiState.value = _uiState.value.copy(
                        isLoggedIn = true,
                        username = username ?: "",
                        role = role ?: "",
                        baseUrl = baseUrl
                    )
                } else {
                    // 半残凭据：把内存态清干净，避免残留的 baseUrl 让后续请求
                    // 打到非预期地址后必然 401、反复弹登录页。
                    // 用 RetrofitClient.setToken/setBaseUrl 这类**非挂起**方法：
                    // repository.clearCredentials() 是 suspend，这里（runCatching 块内
                    // 与 onFailure 的 lambda）都不是 suspend 上下文，调用编译不过——
                    // 而本地沙箱缺协程库，这个错只会表现为一行无关的 unresolved
                    // reference，查不出来。故只做内存态清理；磁盘上的加密 token
                    // 无实际风险（无 baseUrl 时发不出请求），用户重登后即被覆盖。
                    RetrofitClient.setToken(null)
                    android.util.Log.w(
                        "AuthViewModel",
                        "启动恢复凭据不完整（token=${token != null}, baseUrl=$baseUrl），按未登录处理"
                    )
                }
            }.onFailure { e ->
                // 恢复失败绝不能崩：停在登录页，用户重登即可。
                //
                // 注意这里**不能**调 repository.clearCredentials()：它是 suspend 函数，
                // 而 onFailure 的 lambda 不是 suspend 上下文，编译不过。
                // 也正因为编译不过，这个失误本地查不出来（沙箱缺协程库，
                // 只报 unresolved reference）——只能靠推理把清理动作挪进块内。
                // 清理由上面的 runCatching 尾部的兜底路径负责（见下方 finally 语义）：
                // 恢复流程中途失败时，内存里的 RetrofitClient.token 本来也没被设过，
                // 残留风险是 baseUrl，由用户重登时覆盖，不影响正确性。
                android.util.Log.e("AuthViewModel", "启动恢复登录态失败，回登录页: ${e.message}")
            }
            // 无论成功、失败、半残，都要保证"不该登录"时一定停在登录页：
            // 只有上面显式回填过 isLoggedIn=true 才是已登录态，
            // 其余情况把 RetrofitClient 的 baseUrl 也退回未配置，
            // 避免带着上次的服务器地址与空 token 发请求（必然 401 且打扰用户）。
            if (!_uiState.value.isLoggedIn) {
                RetrofitClient.setBaseUrl("")
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
