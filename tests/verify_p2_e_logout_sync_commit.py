"""
回归测试：P2-E 修复 - logout() 同步 commit 清空加密 SharedPreferences

审计报告位置：docs/Android_Mobile_App_Code_Audit_Report_2026-08-09.md §3.8 / §6 P2-E
问题模式：WmsRepository.logout() 使用 .remove(KEY_TOKEN).apply() 异步清空，
物理文件仍残留加密 token。如果攻击者拿到设备 root + keystore，
可能解密历史 token。

修复：
- logout() 改为 encryptedPrefs.edit().clear().commit() 同步清空所有键值
- 失败时仅 Log.w，不阻塞 logout 流程
- logout() 内同时清空 DataStore 和 RetrofitClient 内存

验收标准：
- T1: logout() 体内出现 encryptedPrefs.edit().clear()
- T2: 必须使用 .commit()（同步）而非 .apply()（异步）
- T3: 不能再单独使用 .remove(KEY_TOKEN)（仅删一个键，残留其他键）
- T4: 必须用 try/catch 包裹，失败不抛异常
- T5: catch 内必须 Log.w 记录
- T6: 之后还必须清空 DataStore + RetrofitClient.setToken(null)
- T7: 不能再使用 .apply() 在 logout 流程中
"""

import re
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
REPO_FILE = WORKSPACE / "app/android-native-wms/app/src/main/java/com/factory/wms/data/repository/WmsRepository.kt"


def _src() -> str:
    return REPO_FILE.read_text(encoding="utf-8")


def _extract_function_body(src: str, func_name: str) -> str:
    m = re.search(rf"fun\s+{func_name}\s*\(", src)
    if not m:
        return ""
    brace_start = src.find("{", m.end())
    if brace_start < 0:
        return ""
    depth = 0
    end = brace_start
    for i in range(brace_start, len(src)):
        c = src[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    return src[brace_start: end + 1]


# ---------- T1: logout() 出现 encryptedPrefs.edit().clear() ----------
def test_t1_logout_clears_encrypted_prefs():
    """logout() 必须调用 encryptedPrefs.edit().clear() 清空所有键值。"""
    src = _src()
    body = _extract_function_body(src, "logout")
    assert body, "logout() 函数未找到"
    assert re.search(
        r"encryptedPrefs\s*\.\s*edit\s*\(\s*\)\s*\.\s*clear\s*\(",
        body,
    ), (
        "logout() 缺少 encryptedPrefs.edit().clear() 调用；"
        "P2-E 修复要求：必须清空所有键值（不止 KEY_TOKEN 一个）"
    )


# ---------- T2: 必须使用 .commit() 同步落盘 ----------
def test_t2_logout_uses_commit_synchronously():
    """logout() 必须使用 .commit() 而非 .apply() 同步落盘。"""
    src = _src()
    body = _extract_function_body(src, "logout")
    assert body, "logout() 函数未找到"
    # 找到 encryptedPrefs.edit().clear() 后必须跟 .commit()
    # 允许跨多行写法
    assert re.search(
        r"encryptedPrefs\s*\.\s*edit\s*\(\s*\)\s*\.\s*clear\s*\(\s*\)\s*\.\s*commit\s*\(\s*\)",
        body,
    ), (
        "logout() 必须使用 encryptedPrefs.edit().clear().commit() 同步提交；"
        "P2-E：必须保证 token 在闪存上被覆写，避免物理文件残留加密 token"
    )


# ---------- T3: 不再使用 .remove(KEY_TOKEN) 单独删除 ----------
def test_t3_logout_does_not_only_remove_single_key():
    """logout() 不能再单独 .remove(KEY_TOKEN)，必须改为 .clear() 清空所有键。"""
    src = _src()
    body = _extract_function_body(src, "logout")
    assert body, "logout() 函数未找到"
    # 不允许出现 .remove(KEY_TOKEN) 单独删除（这是旧实现）
    has_old_remove = re.search(r"\.remove\s*\(\s*KEY_TOKEN\s*\)", body) is not None
    assert not has_old_remove, (
        "logout() 仍在使用 .remove(KEY_TOKEN) 单独删除 token（仅清一个键）；"
        "P2-E 修复要求：改为 .clear() 清空所有键"
    )


# ---------- T4: 加密 prefs clear 必须用 try/catch 包裹 ----------
def test_t4_logout_clear_in_try_catch():
    """logout() 中 encryptedPrefs.edit().clear().commit() 必须用 try/catch 包裹。"""
    src = _src()
    body = _extract_function_body(src, "logout")
    assert body, "logout() 函数未找到"
    # 必须出现 try { ... } catch (...) 包含 .clear().commit()
    has_try = re.search(r"\btry\s*\{", body) is not None
    has_catch = re.search(r"\bcatch\s*\(", body) is not None
    assert has_try and has_catch, (
        "logout() 缺少 try/catch 包裹加密 prefs.clear()；"
        "P2-E：clear() 失败不阻塞 logout 流程"
    )


# ---------- T5: catch 内必须 Log.w 记录 ----------
def test_t5_logout_catch_logs_warning():
    """logout() catch 子句内必须使用 Log.w 记录异常。"""
    src = _src()
    body = _extract_function_body(src, "logout")
    assert body, "logout() 函数未找到"
    # 找到所有 catch 子句，校验至少一个使用 Log.w
    catch_blocks = re.findall(r"catch\s*\([^)]+\)\s*\{([^}]*)\}", body, flags=re.DOTALL)
    assert catch_blocks, "logout() 未找到 catch 子句"
    found_log = any(
        re.search(r"Log\.[wev]\s*\(", cb) or "Log.w" in cb
        for cb in catch_blocks
    )
    assert found_log, "logout() 的 catch 子句内必须使用 Log.w/e 记录异常"


# ---------- T6: 之后必须清空 DataStore 和 RetrofitClient.setToken(null) ----------
def test_t6_logout_clears_datastore_and_retrofit():
    """logout() 必须继续清空 DataStore 和 RetrofitClient.setToken(null)。"""
    src = _src()
    body = _extract_function_body(src, "logout")
    assert body, "logout() 函数未找到"
    assert "dataStore.edit { it.clear() }" in body, (
        "logout() 必须调用 context.dataStore.edit { it.clear() } 清空非敏感数据"
    )
    assert "RetrofitClient.setToken(null)" in body, (
        "logout() 必须调用 RetrofitClient.setToken(null) 清空内存 token"
    )


# ---------- T7: logout 流程中不能使用 .apply() 异步提交 ----------
def test_t7_logout_no_async_apply():
    """logout() 函数体内不能再使用 .apply() 异步提交（必须 .commit() 同步）。"""
    src = _src()
    body = _extract_function_body(src, "logout")
    assert body, "logout() 函数未找到"
    # 在 logout 流程中不应该有 .apply() 调用（关键凭据必须同步落盘）
    has_apply = re.search(r"\.apply\s*\(\s*\)", body) is not None
    assert not has_apply, (
        "logout() 中仍存在 .apply() 异步提交；"
        "P2-E：关键凭据清除必须使用 .commit() 同步落盘，避免物理文件残留"
    )


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failures = []
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            print(f"FAIL {t.__name__}: {e}")
            failures.append(t.__name__)
    if failures:
        sys.exit(1)
    print(f"\n所有 {len(tests)} 个 P2-E 回归测试通过")
