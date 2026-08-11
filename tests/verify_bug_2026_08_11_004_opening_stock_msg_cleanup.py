"""
回归测试：BUG-2026-08-11-004 submitOpeningStock 冗余可空解包清理

问题模式：WmsRepository.submitOpeningStock 成功分支写有
    val msg = submitResult?.let { "期初库存已保存" } ?: "期初库存已保存"
两个分支返回相同字符串，?.let 永走非空分支，属无意义冗余代码；
且 handleResponse 在 data=null 时已返回 Unit as T，此处对非空类型做
可空解包具有误导性。

修复：成功分支直接 Result.success("期初库存已保存")，删除冗余 msg 变量。

验收标准：
- T1: submitOpeningStock 内不再有 submitResult?.let 冗余解包
- T2: 成功分支直接 Result.success("期初库存已保存")
- T3: 操作日志写入（operationLogDao.insert）保留
"""

import re
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
REPO_FILE = (
    WORKSPACE
    / "app/android-native-wms/app/src/main/java/com/factory/wms/data/repository/WmsRepository.kt"
)


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
    return src[brace_start:end + 1]


# ---------- T1: 不再有冗余可空解包 ----------
def test_t1_no_redundant_nullable_unwrap():
    """submitOpeningStock 内不再有 submitResult?.let {...} ?: 相同字符串的冗余写法。"""
    body = _extract_function_body(_src(), "submitOpeningStock")
    assert body, "submitOpeningStock 函数未找到"
    assert not re.search(r"submitResult\?\.let", body), (
        "submitOpeningStock 仍有 submitResult?.let 冗余解包；"
        "BUG-2026-08-11-004：两分支返回相同字符串，?.let 无意义"
    )


# ---------- T2: 成功分支直接返回固定提示 ----------
def test_t2_success_returns_fixed_message():
    """成功分支直接 Result.success("期初库存已保存")。"""
    body = _extract_function_body(_src(), "submitOpeningStock")
    assert body, "submitOpeningStock 函数未找到"
    assert 'Result.success("期初库存已保存")' in body, (
        "成功分支未直接返回 Result.success(\"期初库存已保存\")"
    )


# ---------- T3: 操作日志写入保留 ----------
def test_t3_operation_log_kept():
    """成功分支仍写入 opening_stock 操作日志。"""
    body = _extract_function_body(_src(), "submitOpeningStock")
    assert body, "submitOpeningStock 函数未找到"
    assert "operationLogDao.insert" in body and 'operationType = "opening_stock"' in body, (
        "submitOpeningStock 的 opening_stock 操作日志写入被误删"
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
    print(f"\n所有 {len(tests)} 个 BUG-2026-08-11-004 回归测试通过")
