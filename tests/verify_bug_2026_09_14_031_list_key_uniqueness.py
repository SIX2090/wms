#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BUG-2026-09-14-031 回归：Compose LazyList 的 items(key=...) 必须保证唯一性。

## 缺陷

`items(list, key = { it.id ?: 0 })` —— 模型 id 为可空 Int?，后端一旦下发 2 条以上
id 为 null 的数据（异常响应 / 分页拼接 / 未落库的临时行），key 全部塌缩为同一个 0，
Compose 的 LazyColumn 要求 key 唯一，直接抛
`IllegalArgumentException: Key "0" was already used` → 进程崩溃。

同类：`key = { it.id }` 且 id 为**有默认值 0 的非空 Long**（StocktakeRecordDto）——
看似安全，但 Gson 反序列化遇缺字段会落 0，多条即冲突。

## 修复约定（本测试锁死）

所有 items 的 key 必须满足「id 有效 → 业务唯一码 → hashCode」三级兜底，
**禁止**任何会塌缩为同一个常量（0 / ""）的兜底写法。

## 为什么是静态断言

沙箱/CI 无 Android SDK 与 Kotlin 工具链，无法编译 Compose 运行时行为；
本测试锁源码契约，防修复被后续提交回退（与项目既有 verify_* 测试同范式）。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

APP_SRC = Path(__file__).resolve().parents[1] / "app" / "android-native-wms" / "app" / "src" / "main" / "java" / "com" / "factory" / "wms"

# BUG-2026-09-14-031 修复覆盖的 4 个消费点（文件 -> key 必须含的兜底标记）
FIXED_SITES = {
    "ui/screens/ScanScreens.kt": "uiState.stockListItems",
    "ui/screens/OverviewListScreen.kt": "state.alerts",
    "ui/screens/StocktakeRecordScreens.kt": "uiState.records",
}

# 允许的 key 表达式必须包含 hashCode 兜底（三级兜底的最后一环）
HASH_FALLBACK = "hashCode()"


def _read(rel: str) -> str:
    p = APP_SRC / rel
    assert p.exists(), f"源码文件不存在：{p}"
    return p.read_text(encoding="utf-8")


def _iter_items_key_exprs(text: str, start_marker: str):
    """产出 (行号, key 表达式) —— 从 start_marker 起，抽取 items(...) 的完整调用。"""
    idx = text.find(start_marker)
    assert idx != -1, f"未找到标记 {start_marker}"
    # 从标记处向后找 items( 起始，再括号配平取出完整调用
    items_idx = text.find("items(", idx)
    assert items_idx != -1, f"未在 {start_marker} 附近找到 items("
    depth = 0
    i = text.find("(", items_idx)
    start = i
    while i < len(text):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                break
        i += 1
    call = text[start : i + 1]
    m = re.search(r"key\s*=\s*\{(.*?)\}\s*\)", call, re.S)
    assert m, f"{start_marker} 的 items() 未找到 key = {{ }}：\n{call[:300]}"
    line_no = text[:start].count("\n") + 1
    return line_no, m.group(1).strip()


@pytest.mark.parametrize("rel,marker", FIXED_SITES.items())
def test_031_key_has_hashcode_fallback(rel: str, marker: str) -> None:
    """修复点 1-3：key 表达式必须含 hashCode 兜底（三级兜底落地证据）。"""
    text = _read(rel)
    if marker == "uiState.records":
        return  # records 走 test_031_stocktake_record_key_handle_zero_id 单独断言
    line_no, expr = _iter_items_key_exprs(text, marker)
    assert HASH_FALLBACK in expr, (
        f"{rel}:{line_no} 的 items key 缺少 hashCode 兜底：key = {{ {expr} }}"
    )


def test_031_stocktake_record_key_handle_zero_id() -> None:
    """修复点 4：盘点记录 id 有效判断（!= 0L），并带 checkNo/hashCode 兜底。"""
    text = _read("ui/screens/StocktakeRecordScreens.kt")
    line_no, expr = _iter_items_key_exprs(text, "uiState.records")
    assert "0L" in expr or "!= 0" in expr, (
        f"StocktakeRecordScreens.kt:{line_no} 未对 id==0 无效值做判断：key = {{ {expr} }}"
    )
    assert "checkNo" in expr, (
        f"StocktakeRecordScreens.kt:{line_no} 未用 checkNo 作业务唯一码兜底：key = {{ {expr} }}"
    )
    assert HASH_FALLBACK in expr, (
        f"StocktakeRecordScreens.kt:{line_no} 缺少 hashCode 兜底：key = {{ {expr} }}"
    )


def test_031_no_constant_key_collapse_anywhere() -> None:
    """全项目反向断言：禁止任何 key 兜底塌缩为同一常量（0 / ""）。

    这是本 BUG 的根因形式——`?: 0`、`?: ""` 让所有 null-id 项共享同一个 key。
    """
    offenders: list[str] = []
    for kt in APP_SRC.rglob("*.kt"):
        text = kt.read_text(encoding="utf-8")
        for m in re.finditer(r"key\s*=\s*\{([^}]*)\}", text):
            expr = m.group(1)
            if re.search(r"\?\:\s*0\s*$", expr) or re.search(r'\?\:\s*"\s*"\s*$', expr):
                line_no = text[: m.start()].count("\n") + 1
                offenders.append(f"{kt.relative_to(APP_SRC)}:{line_no}  key = {{{expr.strip()}}}")
    assert not offenders, (
        "以下 items key 会塌缩为同一常量，多条 null-id 数据将导致 Compose 崩溃：\n  "
        + "\n  ".join(offenders)
    )


def test_031_material_archive_kept_consistent_pattern() -> None:
    """既有正确范式（MaterialArchiveScreens）不得被改坏——防修复过程中误伤。"""
    text = _read("ui/screens/MaterialArchiveScreens.kt")
    assert "it.id ?: it.code ?: it.hashCode()" in text, (
        "MaterialArchiveScreens 的三级兜底范式被破坏（该项目原有的正确写法，是本次修复的参照标准）"
    )


def test_031_baseline_registered() -> None:
    """BUG-2026-09-14-031 必须已登记进基线（AGENTS.md BUG 流程要求）。"""
    baseline = Path(__file__).resolve().parents[1] / "WMS_BUG_BASELINE.md"
    assert baseline.exists(), "WMS_BUG_BASELINE.md 不存在"
    content = baseline.read_text(encoding="utf-8")
    assert "BUG-2026-09-14-031" in content, "BUG-2026-09-14-031 未登记进 WMS_BUG_BASELINE.md"
