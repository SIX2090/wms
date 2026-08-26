# -*- coding: utf-8 -*-
"""BUG-2026-08-26-001 回归测试：打印模板编辑器占位符速插必须显示中文标签。

需求（2026-08-26）：Excel 打印模板编辑器顶部"占位符速插"区原本直接显示
纯英文模板变量（如 {order.order_no}、{item.material.code}），仓库一线人员
看不懂含义、不知道该插入什么。改为：chip 显示中文标签（label），
悬停提示与点击插入仍使用英文模板变量（value）——value 是模板引擎的取值
键，绝对不能中文化，否则渲染时取不到数据。

测试用例：
  T1. PLACEHOLDERS 数组每个条目都是 { label, value } 结构，label 必须含中文
  T2. 所有 value 保持 {order.*}/{item.*}/{total_*}/{print_date} 英文变量格式，
      不得被中文化（模板引擎取值键安全）
  T3. buildPlaceholders 用 label 做 chip 显示、用 value 做插入与悬停提示，
      防止日后被改回全英文显示
  T4. 面板标题文案包含使用说明（点击字段插入到当前单元格）
"""
from __future__ import annotations

import re
from pathlib import Path

TPL = (
    Path(__file__).resolve().parent.parent
    / "app" / "templates" / "print_template_editor.html"
).read_text(encoding="utf-8")

PLACEHOLDER_ENTRY = re.compile(
    r"\{\s*label:\s*'([^']+)',\s*value:\s*'(\{[^']+\})'\s*\}"
)
CHINESE = re.compile(r"[\u4e00-\u9fff]")
VALID_VALUE = re.compile(r"^\{(order\.[a-z_.]+|item\.[a-z_.]+|total_(quantity|amount)|print_date)\}$")


def _entries():
    return PLACEHOLDER_ENTRY.findall(TPL)


def test_entries_have_chinese_labels():
    """T1：每个占位符条目都是 { label, value }，且 label 含中文。"""
    entries = _entries()
    assert len(entries) >= 20, f"占位符条目数过少：{len(entries)}（应覆盖常用字段）"
    for label, value in entries:
        assert CHINESE.search(label), f"label 必须是中文：{label!r}（value={value}）"
        assert label.strip(), f"label 不能为空（value={value}）"


def test_values_stay_english_template_keys():
    """T2：value 保持英文模板变量格式，不得中文化。"""
    for label, value in _entries():
        assert not CHINESE.search(value), (
            f"模板变量不得中文化：{value!r}（label={label}），否则模板引擎取不到数据"
        )
        assert VALID_VALUE.match(value), f"非法模板变量：{value!r}（label={label}）"


def test_chips_display_label_insert_value():
    """T3：chip 显示中文 label、插入英文 value，防改回全英文显示。"""
    assert "chip.textContent = p.label" in TPL, "chip 显示必须取中文 label"
    assert "insertPlaceholder(p.value)" in TPL, "点击插入必须取英文 value"
    assert "chip.textContent = p;" not in TPL, "禁止直接显示英文占位符原文"


def test_panel_title_has_usage_hint():
    """T4：面板标题含中文使用说明。"""
    assert "点击字段插入到当前单元格" in TPL, "占位符面板标题必须说明用法"
