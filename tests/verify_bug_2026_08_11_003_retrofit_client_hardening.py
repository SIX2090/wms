"""
回归测试：BUG-2026-08-11-003 RetrofitClient 安全加固

问题模式：
1) buildRetrofit() 在 baseUrl 为空时静默 fallback 到硬编码域名 https://gd2026.top/，
   baseUrl 未配置时 API 请求（含 Authorization token）会被发往该默认服务器。
2) object 单例的 baseUrl / authToken / retrofit 可变字段无并发保护，
   setBaseUrl 重建 retrofit 期间，其他线程可能读到半更新中间态。

修复：
- buildRetrofit(url) 空 url 改用不可达占位地址 http://127.0.0.1:9/（discard 端口），
  绝不静默 fallback 到真实域名；
- apiService getter 在 baseUrl 为空时 check() 抛错，占位地址永远收不到请求；
- baseUrl / authToken / retrofit 全部 @Volatile；
- setBaseUrl 在 synchronized 锁内先构建新 retrofit 再发布引用。

验收标准：
- T1: buildRetrofit 不再包含 gd2026.top 硬编码 fallback
- T2: baseUrl 为空时使用不可达占位 127.0.0.1:9
- T3: apiService getter 在 baseUrl 为空时 check 抛错
- T4: baseUrl / authToken / retrofit 均带 @Volatile
- T5: setBaseUrl 使用 synchronized 锁
- T6: setBaseUrl 先构建 retrofit 再赋值 baseUrl（先构建后发布）
"""

import re
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
CLIENT_FILE = (
    WORKSPACE
    / "app/android-native-wms/app/src/main/java/com/factory/wms/data/api/RetrofitClient.kt"
)


def _src() -> str:
    return CLIENT_FILE.read_text(encoding="utf-8")


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
    return src[brace_start:end + 1]


# ---------- T1: 不再硬编码 gd2026.top fallback ----------
def test_t1_no_hardcoded_domain_fallback():
    """buildRetrofit 不再把空 baseUrl 静默 fallback 到 gd2026.top。"""
    src = _src()
    assert "gd2026.top" not in src, (
        "RetrofitClient 仍包含硬编码域名 gd2026.top；"
        "BUG-2026-08-11-003：空 baseUrl 绝不静默 fallback 到任何真实域名"
    )


# ---------- T2: 空 baseUrl 使用不可达占位 ----------
def test_t2_blank_baseurl_uses_unreachable_placeholder():
    """buildRetrofit 在 url 为空时必须使用不可达占位地址。"""
    src = _src()
    # buildRetrofit 是表达式函数体（= Retrofit.Builder()...build()），无大括号，
    # 取函数声明到下一个 .build() 之间的片段
    m = re.search(r"fun\s+buildRetrofit[\s\S]*?\.build\(\)", src)
    assert m, "buildRetrofit 函数未找到"
    body = m.group(0)
    assert "127.0.0.1:9" in body, (
        "buildRetrofit 空 url 未使用不可达占位 127.0.0.1:9；"
        "占位地址必须永远收不到请求（discard 端口）"
    )


# ---------- T3: apiService getter 空 baseUrl 抛错 ----------
def test_t3_apiservice_throws_when_baseurl_blank():
    """apiService getter 必须在 baseUrl 为空时 check 抛错，不发任何请求。"""
    src = _src()
    m = re.search(r"val\s+apiService[\s\S]*?get\(\)\s*\{([\s\S]*?)\n    \}", src)
    assert m, "apiService getter 未找到"
    getter_body = m.group(1)
    assert re.search(r"check\s*\(\s*baseUrl\.isNotBlank\s*\(\s*\)\s*\)", getter_body), (
        "apiService getter 缺少 check(baseUrl.isNotBlank())；"
        "必须在 baseUrl 未配置时快速失败，而不是静默发请求"
    )


# ---------- T4: 可变字段全部 @Volatile ----------
def test_t4_mutable_fields_are_volatile():
    """baseUrl / authToken / retrofit 三个可变字段必须全部 @Volatile。"""
    src = _src()
    for field in ("baseUrl", "authToken", "retrofit"):
        assert re.search(
            rf"@Volatile\s+private\s+var\s+{field}", src
        ), f"{field} 缺少 @Volatile；BUG-2026-08-11-003 要求可变状态全部可见性保护"


# ---------- T5: setBaseUrl 使用 synchronized ----------
def test_t5_setbaseurl_synchronized():
    """setBaseUrl 必须在 synchronized(lock) 内更新状态。"""
    src = _src()
    body = _extract_function_body(src, "setBaseUrl")
    assert body, "setBaseUrl 函数未找到"
    assert re.search(r"synchronized\s*\(\s*lock\s*\)", body), (
        "setBaseUrl 未使用 synchronized(lock)；并发下可能发布半更新状态"
    )


# ---------- T6: 先构建 retrofit 再发布 baseUrl ----------
def test_t6_build_before_publish():
    """setBaseUrl 必须先 retrofit = buildRetrofit(url)，再 baseUrl = url。"""
    src = _src()
    body = _extract_function_body(src, "setBaseUrl")
    assert body, "setBaseUrl 函数未找到"
    build_idx = body.find("retrofit = buildRetrofit(url)")
    publish_idx = body.find("baseUrl = url")
    assert build_idx >= 0 and publish_idx >= 0, (
        "setBaseUrl 内缺少 retrofit 重建或 baseUrl 赋值"
    )
    assert build_idx < publish_idx, (
        "setBaseUrl 必须先构建 retrofit 再赋值 baseUrl（先构建后发布），"
        "否则其他线程会读到 新 baseUrl + 旧 retrofit 的中间态"
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
    print(f"\n所有 {len(tests)} 个 BUG-2026-08-11-003 回归测试通过")
