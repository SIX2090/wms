"""
回归测试：P2-D 修复 - displayMessage 加固（长度截断 + HTML 标签过滤）

审计报告位置：docs/Android_Mobile_App_Code_Audit_Report_2026-08-09.md §2.3 / §6 P2-D
问题模式：ApiEnvelope.displayMessage() 直接拼接后端 message/msg 字段，
恶意后端或中间人可注入超长文本 / <script>/<img onerror=> 标签。

修复：
- ApiEnvelope.displayMessage() 调用 sanitizeMessage() 清洗
- sanitizeMessage: 去除空白 + 过滤 <...> 标签 + 解码常见 HTML 实体后再次过滤
- 长度截断至 200 字符（超出加 "..."）
- 提供 companion object 常量 MAX_DISPLAY_MESSAGE_LENGTH

验收标准：
- T1: displayMessage() 必须经过清洗函数（不能再是单行三元表达式）
- T2: 必须有 sanitizeMessage(...) 函数定义
- T3: 清洗函数必须过滤 <...> 标签
- T4: 清洗函数必须有长度截断
- T5: 长度上限 MAX_DISPLAY_MESSAGE_LENGTH 必须在 100~500 之间（合理阈值）
- T6: 清洗函数必须 decode 至少一个常见 HTML 实体（&lt; &gt; &amp; &quot; 等）
- T7: 函数必须 import 不到 android.text.Html 等额外依赖（用纯 Kotlin Regex）
- T8: sanitizeMessage 必须处理空字符串/纯空白情况
"""

import re
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
API_ENV_FILE = WORKSPACE / "app/android-native-wms/app/src/main/java/com/factory/wms/data/model/ApiEnvelope.kt"


def _src() -> str:
    return API_ENV_FILE.read_text(encoding="utf-8")


# ---------- T1: displayMessage 必须经过清洗 ----------
def test_t1_displaymessage_uses_sanitize():
    """displayMessage() 不再是单行三元，必须经过清洗函数。"""
    src = _src()
    # 找到 displayMessage 函数体
    m = re.search(r"fun\s+displayMessage\s*\(\s*\)", src)
    assert m, "displayMessage() 未找到"
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
    # 旧实现：`fun displayMessage(): String = message ?: msg ?: if (isOk()) ...`
    # 旧实现的特征：return 类型后直接是 = 表达式（无大括号体），或函数体只有一行表达式
    # 我们的判断逻辑：旧实现的 `= message ?: msg ?: ...` 出现在函数体第一行/第二行
    # （即 '= message' 紧跟 fun 声明后），新实现必须调用 sanitizeMessage(...)。
    # 简化判断：旧实现的 `message ?: msg ?: if (isOk()` 出现在 body 前 80 字符内
    # 且没有 sanitizeMessage 调用 → 旧实现
    first_line = body.split("\n", 1)[0]
    if re.search(r"message\s*\?\s*:\s*msg\s*\?\s*:\s*if\s*\(\s*isOk", first_line):
        # 第一行就出现旧的三元式 + 返回类型简写
        assert "sanitizeMessage" in body, (
            "displayMessage() 仍是单行三元表达式（旧实现），"
            "审计报告 P2-D：必须经过 sanitizeMessage() 清洗"
        )
    # 同时 body 内必须有 sanitizeMessage 调用
    assert "sanitizeMessage" in body, (
        "displayMessage() 函数体未调用 sanitizeMessage()；"
        "P2-D 修复要求 message/msg 必须经过清洗"
    )


# ---------- T2: sanitizeMessage 函数必须存在 ----------
def test_t2_sanitize_message_function_exists():
    """必须存在 sanitizeMessage 函数定义。"""
    src = _src()
    assert re.search(
        r"(internal\s+|private\s+|public\s+)?fun\s+sanitizeMessage\s*\(",
        src,
    ), (
        "未找到 sanitizeMessage 函数定义；"
        "P2-D 修复要求：displayMessage() 必须经过清洗函数"
    )


# ---------- T3: 清洗函数必须过滤 <...> 标签 ----------
def test_t3_sanitize_filters_html_tags():
    """sanitizeMessage 必须使用 Regex 过滤 <...> 形式的 HTML 标签。"""
    src = _src()
    # 找到 sanitizeMessage 函数体
    m = re.search(r"fun\s+sanitizeMessage\s*\(", src)
    assert m, "sanitizeMessage 函数未找到"
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
    # 校验：必须出现 `<[^>]+>` 形式的正则
    assert re.search(r'<\[\^>\]+>', body) or 'Regex("<[^>]+>")' in body, (
        "sanitizeMessage 必须使用 Regex(\"<[^>]+>\") 过滤 HTML 标签"
    )


# ---------- T4: 长度截断 ----------
def test_t4_sanitize_truncates_long_message():
    """sanitizeMessage 必须按 MAX_DISPLAY_MESSAGE_LENGTH 截断超长消息。"""
    src = _src()
    m = re.search(r"fun\s+sanitizeMessage\s*\(", src)
    assert m, "sanitizeMessage 函数未找到"
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
    # 校验：必须出现 .substring(0, MAX_...) 或类似截断
    assert re.search(r"\.substring\s*\(\s*0\s*,\s*MAX_", body) or "length > MAX_" in body, (
        "sanitizeMessage 必须使用 substring(0, MAX_...) 截断超长消息"
    )


# ---------- T5: 长度上限必须是 100~500 ----------
def test_t5_max_length_in_reasonable_range():
    """MAX_DISPLAY_MESSAGE_LENGTH 必须在 100~500 之间（合理阈值）。"""
    src = _src()
    m = re.search(
        r"const\s+val\s+MAX_DISPLAY_MESSAGE_LENGTH\s*:\s*Int\s*=\s*(\d+)",
        src,
    )
    assert m, "MAX_DISPLAY_MESSAGE_LENGTH 常量未找到"
    val = int(m.group(1))
    assert 100 <= val <= 500, (
        f"MAX_DISPLAY_MESSAGE_LENGTH={val} 不在合理范围 [100, 500]；"
        "100 以下截得太短用户体验差，500 以上仍可能撑爆 Snackbar"
    )


# ---------- T6: 清洗函数必须 decode 至少一个 HTML 实体 ----------
def test_t6_sanitize_decodes_html_entities():
    """sanitizeMessage 必须解码至少一个常见 HTML 实体（防 &lt;script&gt; 绕过）。"""
    src = _src()
    m = re.search(r"fun\s+sanitizeMessage\s*\(", src)
    assert m, "sanitizeMessage 函数未找到"
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
    # 至少要出现 &lt; &gt; &amp; &quot; 之一
    has_entity_decode = (
        "&lt;" in body
        or "&gt;" in body
        or "&amp;" in body
        or "&quot;" in body
    )
    assert has_entity_decode, (
        "sanitizeMessage 必须 decode 至少一个 HTML 实体（&lt; &gt; &amp; &quot; 等），"
        "防止后端用 &lt;script&gt; 形式绕过标签过滤"
    )


# ---------- T7: 不能依赖 android.text.Html（保持纯 Kotlin） ----------
def test_t7_no_android_html_dependency():
    """清洗函数不应依赖 android.text.Html.fromHtml（避免编码细节差异）。"""
    src = _src()
    no_comments = re.sub(r"//[^\n]*", "", src)
    assert "android.text.Html" not in no_comments, (
        "sanitizeMessage 不应使用 android.text.Html（行为不稳定），应使用纯 Kotlin Regex"
    )


# ---------- T8: 空字符串/纯空白处理 ----------
def test_t8_sanitize_handles_empty_input():
    """sanitizeMessage 必须正确处理空字符串/纯空白输入。"""
    src = _src()
    m = re.search(r"fun\s+sanitizeMessage\s*\(", src)
    assert m, "sanitizeMessage 函数未找到"
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
    # 校验：必须 trim() 并判断 isEmpty()
    assert ".trim()" in body, "sanitizeMessage 必须调用 .trim()"
    assert re.search(r"isEmpty\s*\(\s*\)", body) or "isBlank()" in body, (
        "sanitizeMessage 必须对 trim 后的字符串做空判断，"
        "避免空输入走到正则匹配浪费 CPU"
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
    print(f"\n所有 {len(tests)} 个 P2-D 回归测试通过")
