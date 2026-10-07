"""BUG-2026-10-07-004 回归测试：视觉模型只返回结构化 JSON（无文字说明）时不得丢弃提取结果。

静态契约：
1. _ai_call_llm_vision 在 reply 为空但能从 content 解析出 JSON 时，必须返回 extracted
   （bare-JSON fallback：先试 _ai_vision_parse_extracted，再试 _ai_extract_json_object）。
2. 主链路（_ai_handle_warehouse_assistant_request 的图片分支）在 vision_reply 为空
   但 extracted 非空时，必须通过 _ai_vision_extracted_fallback_reply 生成兜底回复，
   不得直接落到「没有返回具体错误」的误导报错。
3. _ai_vision_extracted_fallback_reply 必须存在于 app.py，且对 items 逐条渲染
   编码/名称/规格/数量/单位。
4. 兜底函数对空 extracted（无 items 且无单号）返回空串，主链路继续走错误分支。
5. 修改不破坏既有路径：extracted 为空且 reply 非空时行为不变。
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_PY = ROOT / "app" / "app.py"


def _read() -> str:
    return APP_PY.read_bytes().decode("utf-8", errors="replace")


def test_files_exist():
    assert APP_PY.exists(), f"missing {APP_PY}"


def test_bare_json_fallback_in_vision_call():
    src = _read()
    i = src.find("def _ai_call_llm_vision")
    assert i > 0, "_ai_call_llm_vision not found"
    body = src[i : src.find("def _ai_vision_parse_extracted")]
    assert "if not extracted:" in body, "vision call must check empty extracted"
    assert "_ai_extract_json_object(content)" in body, (
        "vision call must fall back to _ai_extract_json_object for bare JSON replies"
    )


def test_main_chain_uses_fallback_reply():
    src = _read()
    j = src.find(
        "vision_reply, extracted, vision_error = _ai_call_llm_vision(message, images, context)"
    )
    assert j > 0, "main vision chain not found"
    window = src[j : j + 400]
    assert "if not vision_reply and extracted:" in window, (
        "main chain must handle extracted-only replies before the vision_reply branch"
    )
    assert "_ai_vision_extracted_fallback_reply(extracted)" in window, (
        "main chain must build fallback reply via _ai_vision_extracted_fallback_reply"
    )


def test_fallback_helper_defined():
    src = _read()
    i = src.find("def _ai_vision_extracted_fallback_reply")
    assert i > 0, "_ai_vision_extracted_fallback_reply not defined"
    body = src[i : src.find("\ndef ", i + 10)]
    for token in ("items", "code", "name", "spec", "quantity", "unit"):
        assert token in body, f"fallback helper missing token {token}"
    # 空提取保护：无单号且无 items 时返回空串
    assert "if not extracted.get('order_no') and not items:" in body, (
        "fallback helper must return empty string for empty extraction"
    )


def test_helper_handles_labels_and_limits():
    src = _read()
    i = src.find("def _ai_vision_extracted_fallback_reply")
    body = src[i : src.find("\ndef ", i + 10)]
    assert "AI_DOC_TYPE_LABELS.get(doc_type)" in body, "helper should map doc type label"
    assert "items[:20]" in body, "helper should cap rendered items at 20"


def test_fallback_reply_empty_for_empty_extraction():
    """直接 import 不可行（Flask app 模块重），用 exec 提取函数体做行为验证。"""
    src = _read()
    i = src.find("def _ai_vision_extracted_fallback_reply")
    body = src[i : src.find("\ndef ", i + 10)]
    # 剥离 docstring 依赖：函数引用 AI_DOC_TYPE_LABELS（模块级），用桩替换后 exec
    tree = ast.parse(body)
    fn = tree.body[0]
    assert isinstance(fn, ast.FunctionDef)
    # 移除 docstring
    if (fn.body and isinstance(fn.body[0], ast.Expr)
            and isinstance(fn.body[0].value, ast.Constant)):
        fn.body.pop(0)
    code = ast.unparse(fn)
    ns = {"AI_DOC_TYPE_LABELS": {"in_order": "采购入库草稿", "other": "其他"}}
    exec(compile(code + "\n", "<fallback>", "exec"), ns)  # noqa: S102
    fn_obj = ns["_ai_vision_extracted_fallback_reply"]
    assert fn_obj({}) == "", "empty extraction must yield empty reply"
    assert fn_obj({"document_type": "in_order", "items": []}) == "", (
        "no order_no and no items must yield empty reply"
    )
    reply = fn_obj({
        "document_type": "in_order",
        "order_no": "PO-123",
        "items": [{"code": "A001", "name": "轴承", "quantity": 10, "unit": "套"}],
    })
    assert "A001" in reply and "轴承" in reply and "10" in reply, reply
    assert "采购入库草稿" in reply, "doc type label must be rendered"


def test_misleading_error_branch_still_guarded():
    src = _read()
    i = src.find("def _ai_vision_extracted_fallback_reply")
    j = src.find("没有返回具体错误", i)
    assert j > 0, "misleading error text should still exist for genuine failures"
    # 错误分支应保持 vision_error 的传递（存在 '供应商返回：' 前缀拼接）
    assert "供应商返回：" in src[j - 600 : j + 600]


if __name__ == "__main__":
    import sys

    fails = 0
    for name, fn in sorted({k: v for k, v in globals().items() if k.startswith("test_")}.items()):
        try:
            fn()
            print(f"PASS {name}")
        except AssertionError as exc:
            fails += 1
            print(f"FAIL {name}: {exc}")
    sys.exit(1 if fails else 0)
