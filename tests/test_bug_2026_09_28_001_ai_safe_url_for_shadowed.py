# -*- coding: utf-8 -*-
"""P1-1 回归锁：_ai_safe_url_for 必须只有一个定义，且支持 **values。

BUG-2026-09-28-001：app/app.py 中曾同时存在两个 _ai_safe_url_for 定义——
  - 19549 行 `def _ai_safe_url_for(endpoint, **values)`（返回 None/URL）
  - 31900 行 `def _ai_safe_url_for(endpoint: str) -> str`（返回 空串/URL）
Python 后定义覆盖前者，后者不接受 **values，导致
_ai_page_navigation_catalog() 第 19599 行 `_ai_safe_url_for(endpoint, **values)`
抛 TypeError，**整个自然语言页面导航 skill 崩溃**（不是少几个条目，是整体不可用）。

本测试锁定三件事，任一被破坏即视为回归：
  T1. app/app.py 中 _ai_safe_url_for 只能有一个顶层定义；
  T2. 该定义必须接受 **values（签名含 VAR_KEYWORD）；
  T3. 真实调用 _ai_page_navigation_catalog() 不抛异常，且带 values 的
      3 个条目（采购入库列表 / 销售出库 / 风险操作审计）都在目录中、
      URL 带上了对应查询串。
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_PY = ROOT / "app" / "app.py"

# 带 routing values 的条目：title -> 期望 URL 中的查询串
VALUE_ENTRIES = {
    "采购入库列表": "business_type=",
    "销售出库": "type=sale",
    "风险操作审计": "risk=1",
}


def _top_level_defs(source: str):
    tree = ast.parse(source, filename=str(APP_PY))
    return [n for n in tree.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            and n.name == "_ai_safe_url_for"]


def test_T1_only_one_top_level_definition():
    """T1：_ai_safe_url_for 在 app.py 顶层只能定义一次（后定义会覆盖前者）。"""
    source = APP_PY.read_text(encoding="utf-8-sig")
    defs = _top_level_defs(source)
    assert len(defs) == 1, (
        f"_ai_safe_url_for 出现 {len(defs)} 个顶层定义，行号 "
        f"{[d.lineno for d in defs]}；重复定义会让后者静默覆盖前者（BUG-2026-09-28-001）"
    )


def test_T2_signature_accepts_kwargs():
    """T2：定义必须接受 **values，否则 _ai_page_navigation_catalog 传参会 TypeError。"""
    source = APP_PY.read_text(encoding="utf-8-sig")
    defs = _top_level_defs(source)
    assert defs, "_ai_safe_url_for 未找到"
    node = defs[0]
    assert node.args.kwarg is not None, (
        f"_ai_safe_url_for 定义于第 {node.lineno} 行，签名不含 **values；"
        "_ai_page_navigation_catalog 以 `_ai_safe_url_for(endpoint, **values)` 调用，"
        "会抛 TypeError（BUG-2026-09-28-001）"
    )


def test_T3_catalog_with_values_entries_present():
    """T3：真实调用 catalog，带 values 的条目必须存在且 URL 正确。"""
    import os
    import sys

    os.environ.setdefault("FLASK_ENV", "production")
    os.environ.setdefault("WMS_ALLOW_INSECURE_COOKIE", "1")
    os.environ.setdefault("WMS_ALLOW_AUTO_SECRET_KEY", "1")
    os.environ.setdefault("WMS_NO_DB_TOUCH", "1")
    os.environ.setdefault("PYTHONUTF8", "1")
    app_dir = str(ROOT / "app")
    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)

    import app as wms_app  # noqa: E402

    with wms_app.app.test_request_context("/"):
        catalog = wms_app._ai_page_navigation_catalog()

    by_title = {c["title"]: c for c in catalog}
    missing = []
    wrong = []
    for title, expect in VALUE_ENTRIES.items():
        if title not in by_title:
            missing.append(title)
        elif expect not in (by_title[title].get("url") or ""):
            wrong.append(f"{title}: url={by_title[title].get('url')!r} 不含 {expect!r}")

    assert not missing, (
        f"带 routing values 的导航条目缺失: {missing}；"
        "说明 _ai_safe_url_for 又不接受 **values 了（BUG-2026-09-28-001）"
    )
    assert not wrong, f"导航条目 URL 未带上预期查询串: {wrong}"
