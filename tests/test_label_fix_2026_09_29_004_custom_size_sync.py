# -*- coding: utf-8 -*-
"""LABEL-FIX-2026-09-29-004：自定义尺寸保存前必须同步 applyCustomSize()。

生效确认：saveTemplate / saveAsTemplate 在序列化前，若尺寸选择器为 custom
则先调用 applyCustomSize()，杜绝「改了数字没点应用」导致界面与存库尺寸不一致。
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "app" / "templates" / "material.html"


def _fn_body(text, name, span=700):
    m = re.search(rf"function {name}\(\) \{{", text)
    assert m, f"未找到函数 {name}"
    return text[m.start():m.start() + span]


def test_save_template_syncs_custom_size():
    text = PAGE.read_text(encoding="utf-8")
    for fn in ("saveTemplate", "saveAsTemplate"):
        body = _fn_body(text, fn)
        assert "__syncCustomSizeBeforeSave" in body, \
            f"{fn}() 未在保存前同步自定义尺寸（界面与存库尺寸可能不一致）"


def test_sync_guarded_by_custom_check():
    """同步必须带 custom 条件守卫——否则会把预设尺寸（如 90x50）误用
    customWidth/customHeight 输入框里的残留值覆盖。"""
    text = PAGE.read_text(encoding="utf-8")
    body = _fn_body(text, "__syncCustomSizeBeforeSave")
    assert "applyCustomSize" in body, "同步函数未调用 applyCustomSize()"
    i = body.find("applyCustomSize")
    ctx = body[max(0, i - 200):i]
    assert "custom" in ctx, "applyCustomSize 调用缺少 custom 条件守卫"


def test_helper_defined_before_use():
    """helper 必须先定义后使用（脚本同文件顺序执行，函数声明提升但保持显式顺序）。"""
    text = PAGE.read_text(encoding="utf-8")
    i_def = text.find("function __syncCustomSizeBeforeSave()")
    i_use = text.find("function saveTemplate()")
    assert 0 < i_def < i_use, "helper 定义必须位于 saveTemplate 之前"
