"""
回归测试：P2-A 修复 - 启动时清理 cacheDir/camera/ 旧文件

审计报告位置：docs/Android_Mobile_App_Code_Audit_Report_2026-08-09.md §4.3.2 / §6 P2-A
问题模式：拍照临时文件路径 cacheDir/camera/{prefix}_{ts}.jpg 多次拍照不会自动清理，
长期使用会累积占用空间。

修复：
- WmsApplication.onCreate() 调用 cleanupStaleCameraCache()
- 删除 cacheDir/camera/ 下超过 24 小时的临时文件
- 失败时仅 Log.w 记录，不阻塞 App 启动

验收标准：
- T1: WmsApplication.onCreate 内必须调用 cleanupStaleCameraCache()
- T2: cleanupStaleCameraCache 内部使用 cacheDir/camera 路径
- T3: 内部必须有 lastModified() < cutoff 的判断（即基于时间过滤旧文件）
- T4: cutoff 必须为 24h（24 * 60 * 60 * 1000 ms）
- T5: 删除文件调用 f.delete()
- T6: 整个清理函数必须用 try/catch 包裹，失败不阻塞启动
- T7: 失败时仅 Log.w 记录，不抛异常
"""

import re
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
APP_FILE = WORKSPACE / "app/android-native-wms/app/src/main/java/com/factory/wms/WmsApplication.kt"


def _src() -> str:
    return APP_FILE.read_text(encoding="utf-8")


def _strip_comments(src: str) -> str:
    no_block = re.sub(r"/\*.*?\*/", "", src, flags=re.DOTALL)
    no_line = re.sub(r"//[^\n]*", "", no_block)
    return no_line


# ---------- T1: onCreate 必须调用 cleanupStaleCameraCache ----------
def test_t1_oncreate_invokes_camera_cleanup():
    """WmsApplication.onCreate() 函数体内必须出现 cleanupStaleCameraCache() 调用。"""
    src = _src()
    m = re.search(r"override\s+fun\s+onCreate\s*\(\s*\)", src)
    assert m, "WmsApplication.onCreate 未找到"
    # 找到 onCreate 后的第一个 { 起点
    brace_start = src.find("{", m.end())
    assert brace_start >= 0
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
    body = src[brace_start: end + 1]
    assert "cleanupStaleCameraCache" in body, (
        "WmsApplication.onCreate() 内未调用 cleanupStaleCameraCache()；"
        "审计报告 P2-A：必须在 App 启动时清理 cacheDir/camera 旧文件"
    )


# ---------- T2: cleanupStaleCameraCache 内部使用 cacheDir/camera 路径 ----------
def test_t2_cleanup_uses_cache_dir_camera_path():
    """cleanupStaleCameraCache 内部必须使用 cacheDir + camera 路径组合。"""
    src = _src()
    no_comments = _strip_comments(src)
    # 形如 `File(cacheDir, "camera")` 或 `File(cacheDir, "camera/")`
    assert re.search(
        r'File\s*\(\s*cacheDir\s*,\s*"camera"\s*\)',
        no_comments,
    ), (
        "cleanupStaleCameraCache 内部必须使用 File(cacheDir, \"camera\") 路径；"
        "FileProvider 配置 res/xml/file_paths.xml 限定 path=\"camera/\"，"
        "清理逻辑必须与之对齐"
    )


# ---------- T3: 基于时间过滤旧文件 ----------
def test_t3_cleanup_filters_by_lastmodified():
    """cleanupStaleCameraCache 内部必须基于文件 lastModified() 与 cutoff 比较。"""
    src = _src()
    no_comments = _strip_comments(src)
    assert "lastModified" in no_comments, (
        "cleanupStaleCameraCache 内部必须使用 lastModified() 过滤旧文件"
    )
    # 必须有 lastModified() < cutoff 的比较
    assert re.search(r"lastModified\s*\(\s*\)\s*<\s*\w+", no_comments), (
        "cleanupStaleCameraCache 内部必须出现 lastModified() < cutoff 比较"
    )


# ---------- T4: cutoff 必须为 24 小时 ----------
def test_t4_cleanup_cutoff_is_24_hours():
    """cutoff 必须是 24 小时（24 * 60 * 60 * 1000 ms）。"""
    src = _src()
    no_comments = _strip_comments(src)
    # 允许不同的写法：24L * 60L * 60L * 1000L 或 24 * 60 * 60 * 1000 等
    # 核心是出现 24 * 60 * 60 * 1000 序列
    pattern = r"24\s*[Ll]?\s*\*\s*60\s*[Ll]?\s*\*\s*60\s*[Ll]?\s*\*\s*1000\s*[Ll]?"
    assert re.search(pattern, no_comments), (
        "cutoff 计算必须基于 24 小时（24 * 60 * 60 * 1000 ms）"
    )


# ---------- T5: 真正删除文件 ----------
def test_t5_cleanup_deletes_files():
    """cleanupStaleCameraCache 内部必须真正调用 f.delete()。"""
    src = _src()
    no_comments = _strip_comments(src)
    assert re.search(r"\.delete\s*\(\s*\)", no_comments), (
        "cleanupStaleCameraCache 必须调用 f.delete() 真正删除文件"
    )


# ---------- T6: 整个清理函数必须用 try/catch 包裹 ----------
def test_t6_cleanup_wrapped_in_try_catch():
    """cleanupStaleCameraCache 函数体必须用 try { ... } catch 包裹，失败不阻塞启动。"""
    src = _src()
    # 找到 fun cleanupStaleCameraCache() { 后的函数体
    m = re.search(r"private\s+fun\s+cleanupStaleCameraCache\s*\(", src)
    assert m, "cleanupStaleCameraCache 函数未找到"
    brace_start = src.find("{", m.end())
    assert brace_start >= 0
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
    body = src[brace_start: end + 1]
    # 简单校验：函数体内同时出现 try 和 catch
    assert "try" in body, "cleanupStaleCameraCache 必须用 try 包裹"
    assert "catch" in body, "cleanupStaleCameraCache 必须有 catch 子句"


# ---------- T7: 失败时仅 Log.w，不抛异常 ----------
def test_t7_cleanup_failure_only_logs_warning():
    """catch 子句内必须只 Log.w 记录，不抛出新异常。"""
    src = _src()
    # 找到 catch 子句
    m = re.search(
        r"catch\s*\([^)]+\)\s*\{([^}]*)\}",
        src,
        flags=re.DOTALL,
    )
    assert m, "catch 子句未找到"
    catch_body = m.group(1)
    # 校验：必须出现 Log.w（警告日志）
    assert re.search(r"Log\.[wev]\s*\(", catch_body) or "Log.w" in catch_body, (
        "catch 子句内必须使用 Log.w/e 记录异常"
    )
    # 校验：catch 内不得 throw 新异常（不阻塞 App 启动）
    assert "throw" not in catch_body, (
        "catch 子句内不得 throw 新异常，否则会阻塞 App 启动"
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
    print(f"\n所有 {len(tests)} 个 P2-A 回归测试通过")
