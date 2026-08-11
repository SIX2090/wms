"""
回归测试：BUG-2026-08-11-005 CloudAsrVoiceSttEngine 上传协程并发上限

问题模式：CloudAsrVoiceSttEngine.uploadScope 是独立 SupervisorJob 作用域，
destroy() 刻意不取消（避免丢弃异步识别结果）；但 stop() 每触发一次就
launch 一个上传协程，极端频繁触发时在途协程无界累积，
每个在途上传最坏 30s readTimeout 才结束，可能拖垮弱网设备。

修复：stop() 上传前用 AtomicInteger 计数，超过 MAX_CONCURRENT_UPLOADS(3)
个在途上传直接回调 SttError.TooManyRequests 拒绝；协程 finally 中递减计数。

验收标准：
- T1: 声明 MAX_CONCURRENT_UPLOADS 常量
- T2: 声明 AtomicInteger 在途计数器
- T3: 上传前 incrementAndGet 超限则 decrementAndGet + TooManyRequests 拒绝
- T4: 上传协程 finally 块递减计数（不泄漏计数）
- T5: uploadScope/destroy 语义不变（destroy 仍不取消 uploadScope）
"""

import re
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
ENGINE_FILE = (
    WORKSPACE
    / "app/android-native-wms/app/src/main/java/com/factory/wms"
    / "ui/viewmodel/voice/CloudAsrVoiceSttEngine.kt"
)


def _src() -> str:
    return ENGINE_FILE.read_text(encoding="utf-8")


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


# ---------- T1: MAX_CONCURRENT_UPLOADS 常量 ----------
def test_t1_max_concurrent_uploads_constant():
    """必须声明 MAX_CONCURRENT_UPLOADS 上限常量。"""
    src = _src()
    assert re.search(r"MAX_CONCURRENT_UPLOADS\s*=\s*\d+", src), (
        "缺少 MAX_CONCURRENT_UPLOADS 常量；"
        "BUG-2026-08-11-005：上传协程必须有并发上限"
    )


# ---------- T2: AtomicInteger 在途计数器 ----------
def test_t2_active_uploads_counter():
    """必须用 AtomicInteger 跟踪在途上传数。"""
    src = _src()
    assert re.search(r"AtomicInteger\s*\(\s*0\s*\)", src), (
        "缺少 AtomicInteger 在途计数器"
    )


# ---------- T3: 超限拒绝并回调 TooManyRequests ----------
def test_t3_over_limit_rejected():
    """stop() 内超过上限时必须 decrementAndGet 回退并回调 TooManyRequests。"""
    src = _src()
    body = _extract_function_body(src, "stop")
    assert body, "stop() 函数未找到"
    assert re.search(
        r"incrementAndGet\s*\(\s*\)\s*>\s*MAX_CONCURRENT_UPLOADS", body
    ), "stop() 缺少超限判断（incrementAndGet() > MAX_CONCURRENT_UPLOADS）"
    assert "SttError.TooManyRequests" in body, (
        "超限分支未回调 SttError.TooManyRequests"
    )


# ---------- T4: 协程 finally 递减计数 ----------
def test_t4_finally_decrements():
    """上传协程必须在 finally 中 decrementAndGet，保证计数不泄漏。"""
    src = _src()
    body = _extract_function_body(src, "stop")
    assert body, "stop() 函数未找到"
    assert re.search(r"finally\s*\{[^}]*decrementAndGet", body, flags=re.DOTALL), (
        "上传协程缺少 finally { decrementAndGet() }；计数会泄漏导致后续上传被误拒"
    )


# ---------- T5: destroy 不取消 uploadScope 语义不变 ----------
def test_t5_destroy_still_keeps_upload_scope():
    """destroy() 仍不得取消 uploadScope（异步结果需能回调）。"""
    src = _src()
    body = _extract_function_body(src, "destroy")
    assert body, "destroy() 函数未找到"
    assert "uploadScope.cancel" not in body and "cancel()" not in body, (
        "destroy() 不应取消 uploadScope；BUG-2026-08-09-010 的设计约束仍需保持"
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
    print(f"\n所有 {len(tests)} 个 BUG-2026-08-11-005 回归测试通过")
