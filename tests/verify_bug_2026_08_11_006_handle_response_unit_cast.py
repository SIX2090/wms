"""
回归测试：BUG-2026-08-11-006 - handleResponse 的 `Unit as T` 兜底导致
"kotlin.Unit cannot be cast to com.factory.wms.data.api.RecognizeMaterialResult"

问题模式：
- App 端 WmsRepository.handleResponse<T> 在 envelope success 但 data==null 时
  无条件执行 `Result.success(Unit as T)`。
- reified 泛型下 `Unit as T` 是真实 checkcast：T=RecognizeMaterialResult 时抛
  ClassCastException("kotlin.Unit cannot be cast to ...RecognizeMaterialResult")，
  被 recognizeMaterial 外层 catch 包装成 "网络错误: kotlin.Unit cannot be cast..."
  （用户截图中的报错文本）。
- 触发条件：服务端 success 响应缺 data 字段（旧版本服务端、代理丢 body 等）。

修复：
- data==null 时仅当 T::class == Unit::class（删除类接口）才回填 Unit；
- 其他类型返回 Result.failure(Exception(envelope.displayMessage()))，
  UI 展示服务端 msg，而不是 ClassCastException 文本。

验收标准：
- T1: handleResponse 中 `Unit as T` 必须由 `T::class == Unit::class` 守卫
- T2: data==null 且非 Unit 分支必须返回 Result.failure（不允许 Result.success）
- T3: 非 Unit 兜底失败必须使用 envelope.displayMessage() 透出服务端消息
- T4: 后端 recognize_material success 响应必须包含 data 字段（防服务端回归）
"""

import re
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
REPO_FILE = WORKSPACE / "app/android-native-wms/app/src/main/java/com/factory/wms/data/repository/WmsRepository.kt"
BACKEND_FILE = WORKSPACE / "app/routes/mobile.py"


def _src() -> str:
    return REPO_FILE.read_text(encoding="utf-8")


def _extract_function_body(src: str, signature: str) -> str:
    m = re.search(signature, src)
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


def _handle_response_body() -> str:
    return _extract_function_body(_src(), r"private\s+inline\s+fun\s+<reified\s+T>\s+handleResponse")


# ---------- T1: Unit as T 必须由 T::class == Unit::class 守卫 ----------
def test_t1_unit_cast_guarded_by_unit_class_check():
    body = _handle_response_body()
    assert body, "handleResponse 函数未找到"
    assert "Unit as T" in body, "handleResponse 缺少 Unit 兜底分支（删除类接口需要）"
    assert "T::class == Unit::class" in body, (
        "handleResponse 的 `Unit as T` 缺少 `T::class == Unit::class` 守卫；"
        "BUG-2026-08-11-006：非 Unit 类型执行 Unit as T 会抛 ClassCastException"
    )
    # 守卫必须在 Unit as T 之前出现（else if 分支）
    guard_pos = body.find("T::class == Unit::class")
    cast_pos = body.find("Unit as T")
    assert guard_pos < cast_pos, "T::class == Unit::class 守卫必须出现在 `Unit as T` 之前"


# ---------- T2: data==null 且非 Unit 分支必须返回 Result.failure ----------
def test_t2_non_unit_null_data_returns_failure():
    body = _handle_response_body()
    assert body, "handleResponse 函数未找到"
    # 找到 T::class == Unit::class 守卫之后的 else 分支（非 Unit 兜底）
    m = re.search(
        r"T::class\s*==\s*Unit::class\s*\)[\s\S]*?\}\s*else\s*\{([\s\S]*?)\}",
        body,
    )
    assert m, "非 Unit 且 data==null 的 else 兜底分支未找到"
    else_body = m.group(1)
    assert "Result.failure" in else_body, (
        "非 Unit 且 data==null 时必须返回 Result.failure，不能 Result.success"
    )
    assert "Result.success" not in else_body, (
        "非 Unit 且 data==null 的兜底分支仍含 Result.success——会把 Unit 当业务数据返回"
    )


# ---------- T3: 非 Unit 兜底失败必须透出服务端 displayMessage ----------
def test_t3_failure_uses_display_message():
    body = _handle_response_body()
    assert body, "handleResponse 函数未找到"
    m = re.search(
        r"T::class\s*==\s*Unit::class\s*\)[\s\S]*?\}\s*else\s*\{([\s\S]*?)\}",
        body,
    )
    assert m, "非 Unit 兜底分支未找到"
    else_body = m.group(1)
    assert "displayMessage()" in else_body, (
        "非 Unit 兜底失败必须使用 envelope.displayMessage() 透出服务端 msg，"
        "让用户看到可读错误而非 ClassCastException 文本"
    )


# ---------- T4: 后端 recognize_material success 响应必须包含 data 字段 ----------
def _extract_python_function_body(src: str, signature: str) -> str:
    """按缩进截取 Python 函数体（Python 无花括号，不能用 _extract_function_body）。"""
    m = re.search(signature, src)
    if not m:
        return ""
    lines = src[m.start():].split("\n")
    # 结束于下一个同缩进级的 def/decorator（不能用"缩进回退"判断：
    # 函数体内的多行字符串字面量内容顶格在 column 0，会误判函数结束）
    def_indent = len(lines[0]) - len(lines[0].lstrip())
    end_re = re.compile(r"^" + " " * def_indent + r"(def\s|@)")
    body_lines = [lines[0]]
    for line in lines[1:]:
        if end_re.match(line):
            break
        body_lines.append(line)
    return "\n".join(body_lines)


def test_t4_backend_success_response_has_data():
    src = BACKEND_FILE.read_text(encoding="utf-8")
    body = _extract_python_function_body(src, r"def\s+mobile_recognize_material\s*\(")
    assert body, "mobile_recognize_material 函数未找到"
    # 找到 success 返回块
    m = re.search(r"'status':\s*'success'[\s\S]*?'success':\s*True[\s\S]*?'data':\s*\{", body)
    assert m, (
        "recognize_material success 响应缺少 data 字段；"
        "App 端 ApiEnvelope<RecognizeMaterialResult> 需要 data 才能反序列化"
    )
    # data 内必须包含 App 端 RecognizeMaterialResult 的四个字段
    data_block_start = body.find("'data': {", m.start())
    data_block = body[data_block_start: data_block_start + 400]
    for field in ("reply", "extracted", "matches", "match_count"):
        assert f"'{field}'" in data_block, f"success 响应 data 缺少字段 {field}"


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
    print(f"\n所有 {len(tests)} 个 BUG-2026-08-11-006 回归测试通过")
