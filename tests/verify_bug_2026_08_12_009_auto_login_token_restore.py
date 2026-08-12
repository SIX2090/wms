"""
回归测试：BUG-2026-08-12-009 手机端重启后无法自动登录（会话恢复漏恢复 token）

问题模式：
AuthViewModel.init 在 App 重启后从 EncryptedSharedPreferences 读回持久化 token，
并恢复了 RetrofitClient 的 baseUrl、把 isLoggedIn 置为 true，但**没有**把 token
注入 RetrofitClient 的内存态 authToken（@Volatile，进程死亡即清空）。
结果：重启后首个 API 请求不带 Authorization: Bearer → 服务端 401 →
authInterceptor（非登录路径）置空 authToken 并回调 onUnauthorized →
AuthEventBus → AuthViewModel 收集后 repository.logout() 清空全部已存凭据 →
用户每次点击图标都被迫重新输入用户名密码。

修复：
AuthViewModel.init 恢复会话分支内补 RetrofitClient.setToken(token)，
与 login() 成功路径的 saveLoginInfo()（内部 setToken/setBaseUrl）行为对齐。

验收标准：
- T1: AuthViewModel.init 恢复分支调用 RetrofitClient.setToken(token)
- T2: setToken 在标记 isLoggedIn=true 之前执行（先进内存态，再进 Home 发请求）
- T3: baseUrl 恢复逻辑保留（RetrofitClient.setBaseUrl(baseUrl)）
- T4: 持久化层完好：WmsRepository.getSavedToken 从 EncryptedSharedPreferences 读 auth_token
- T5: 自动跳转契约完好：LoginScreen 监听 uiState.isLoggedIn 并调 onLoginSuccess()
- T6: 过期边界契约：AuthViewModel 收集 AuthEventBus.unauthorizedEvents 后 repository.logout()
      （7 天 token 过期或 401 时回退手动登录，而非静默挂着）
"""

import re
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
ANDROID_ROOT = WORKSPACE / "app/android-native-wms/app/src/main/java/com/factory/wms"
AUTH_VM_FILE = ANDROID_ROOT / "ui/viewmodel/auth/AuthViewModel.kt"
REPO_FILE = ANDROID_ROOT / "data/repository/WmsRepository.kt"
LOGIN_SCREEN_FILE = ANDROID_ROOT / "ui/screens/LoginScreen.kt"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _init_block(src: str) -> str:
    """提取 AuthViewModel 的 init { ... } 块（含嵌套大括号）。"""
    m = re.search(r"^\s*init\s*\{", src, flags=re.MULTILINE)
    assert m, "AuthViewModel 缺少 init 块"
    start = src.find("{", m.start())
    depth = 0
    for i in range(start, len(src)):
        c = src[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return src[start:i + 1]
    raise AssertionError("AuthViewModel init 块大括号不闭合")


# ---------- T1: init 恢复分支必须注入 token 到 RetrofitClient ----------
def test_t1_init_restores_token_into_retrofit_client():
    """App 重启恢复会话时，必须把持久化 token 注入 RetrofitClient 内存态。"""
    src = _init_block(_read(AUTH_VM_FILE))
    assert "RetrofitClient.setToken(token)" in src, (
        "AuthViewModel.init 未调用 RetrofitClient.setToken(token)；"
        "BUG-2026-08-12-009：重启后内存 token 为空，首个请求 401 触发强制登出，"
        "用户每次点击图标都要重新登录"
    )


# ---------- T2: setToken 必须先于 isLoggedIn=true ----------
def test_t2_set_token_before_marking_logged_in():
    """token 必须先注入内存态，再放行 isLoggedIn=true（Home 页随即发请求）。"""
    src = _init_block(_read(AUTH_VM_FILE))
    idx_token = src.find("RetrofitClient.setToken(token)")
    idx_logged_in = src.find("isLoggedIn = true")
    assert idx_token >= 0, "缺少 RetrofitClient.setToken(token)"
    assert idx_logged_in >= 0, "init 恢复分支缺少 isLoggedIn = true"
    assert idx_token < idx_logged_in, (
        "RetrofitClient.setToken(token) 必须先于 isLoggedIn=true 执行，"
        "否则 Home 页首个请求仍可能不带 Authorization"
    )


# ---------- T3: baseUrl 恢复逻辑保留 ----------
def test_t3_base_url_restore_kept():
    """baseUrl 恢复逻辑必须保留（否则请求发到占位地址）。"""
    src = _init_block(_read(AUTH_VM_FILE))
    assert "RetrofitClient.setBaseUrl(baseUrl)" in src, (
        "AuthViewModel.init 缺少 RetrofitClient.setBaseUrl(baseUrl) 恢复逻辑"
    )


# ---------- T4: 持久化层完好 ----------
def test_t4_saved_token_persisted_in_encrypted_prefs():
    """getSavedToken 必须从 EncryptedSharedPreferences 读取 auth_token。"""
    src = _read(REPO_FILE)
    assert "EncryptedSharedPreferences" in src, "WmsRepository 未使用 EncryptedSharedPreferences"
    assert 'KEY_TOKEN = "auth_token"' in src, "WmsRepository 缺少 auth_token 键"
    assert re.search(r"fun\s+getSavedToken[\s\S]*?encryptedPrefs\.getString\(KEY_TOKEN", src), (
        "getSavedToken() 未从 encryptedPrefs 读取 KEY_TOKEN"
    )


# ---------- T5: 自动跳转契约完好 ----------
def test_t5_login_screen_auto_navigates_when_logged_in():
    """LoginScreen 必须在 isLoggedIn=true 时自动调 onLoginSuccess() 进首页。"""
    src = _read(LOGIN_SCREEN_FILE)
    assert "LaunchedEffect(uiState.isLoggedIn)" in src, (
        "LoginScreen 缺少 LaunchedEffect(uiState.isLoggedIn) 自动跳转监听"
    )
    assert re.search(r"LaunchedEffect\(uiState\.isLoggedIn\)\s*\{[\s\S]*?onLoginSuccess\(\)", src), (
        "isLoggedIn 监听块内未调用 onLoginSuccess()"
    )


# ---------- T6: 过期/401 回退手动登录边界 ----------
def test_t6_unauthorized_event_triggers_logout():
    """token 过期（7 天 TTL）或任意 401 时必须清凭据回登录页，不能静默挂着。"""
    src = _init_block(_read(AUTH_VM_FILE))
    assert "AuthEventBus.unauthorizedEvents.collect" in src, (
        "AuthViewModel 未收集 AuthEventBus.unauthorizedEvents"
    )
    assert re.search(r"unauthorizedEvents\.collect\s*\{[\s\S]*?repository\.logout\(\)", src), (
        "401 事件收集块内未调用 repository.logout()；"
        "过期 token 不应伪装成自动登录成功"
    )
