# -*- coding: utf-8 -*-
"""AI-WMS-FILTER-006：采购入库明细表的「关键词」框补物料搜索候选。

需求：用户要求红色框（筛选区「关键词」输入框）加上物料搜索功能。

现状核查（先查后改）：
- 后端**早已**支持按物料搜索——`_apply_in_order_search` 的条件里含
  Material.code / name / spec / brand，与 /api/material/search 的口径一致；
- 缺口只在**输入侧**：该框是裸 input，没有候选提示，而同排的「供应商」
  「工程名称」都有 quick-select 下拉。用户输入「EDI 电源」得靠记忆拼对
  全名，打错了就只能拿到空列表，且不知道是"没有"还是"打错了"。

修复：挂 `data-ks="material"` 复用既有 quick-select（零新增 JS），
物料候选自带「编码+名称 / 规格·品牌」两行富展示与拼音匹配。

刻意的设计选择（防后人"顺手补齐"改错）：
- **不挂** data-ks-submit：本框是混合关键词框（单号/来源/供应商/物料都能搜），
  选中即提交会剥夺用户继续手打单号的用法。挂 submit 的是语义单一的选择框。
"""
from __future__ import annotations

import os
import re

import pytest

TEMPLATE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "app", "templates", "in_order.html")


@pytest.fixture(scope="module")
def html() -> str:
    return open(TEMPLATE, encoding="utf-8").read()


def _search_input_tag(html: str) -> str:
    """取出 name="search" 的那个 input 标签（整个标签文本）。"""
    m = re.search(r'<input[^>]*name="search"[^>]*>', html)
    assert m, '未找到 name="search" 的关键词输入框'
    return m.group(0)


def test_keyword_input_has_material_quick_select(html):
    """关键词框必须挂 data-ks="material"，否则用户仍无候选提示。"""
    tag = _search_input_tag(html)
    assert 'data-ks="material"' in tag, (
        '关键词框缺少 data-ks="material"：物料搜索候选未启用，'
        f'用户需盲打全名。当前标签：{tag}'
    )


def test_keyword_input_put_name_so_form_still_filters(html):
    """选中候选必须回填 name="search" 本身，表单才照常提交模糊搜索。

    data-ks-put 若不填（默认 label）或指向不存在的隐藏框，选中后
    输入框内容与提交值会脱节，筛选结果对不上用户看到的东西。
    """
    tag = _search_input_tag(html)
    assert 'data-ks-put="name"' in tag, (
        '未指定 data-ks-put="name"：选中物料后回填值不确定，'
        f'可能提交出用户没看到的筛选词。当前标签：{tag}'
    )
    # 回填目标就是提交目标：name="search"
    assert 'name="search"' in tag


def test_keyword_input_must_not_auto_submit(html):
    """不得挂 data-ks-submit——本框是混合关键词框，选中即提交会限制用法。

    这是一条**防倒退**断言：照抄旁边供应商/工程框的写法（它们都带 submit）
    是最容易犯的错，会把"还能继续打单号"的能力删掉。
    """
    tag = _search_input_tag(html)
    assert 'data-ks-submit' not in tag, (
        '关键词框是混合关键词框（单号/来源/供应商/物料），不应挂 data-ks-submit；'
        '选中物料即自动提交会让用户无法继续手打单号。'
    )


def test_keyword_input_autocomplete_off_to_avoid_browser_shadow(html):
    """必须 autocomplete="off"：浏览器原生历史下拉会与 quick-select 菜单重叠。"""
    tag = _search_input_tag(html)
    assert 'autocomplete="off"' in tag, (
        '缺少 autocomplete="off"：浏览器历史下拉会盖住 quick-select 菜单'
    )


def test_material_entity_supported_by_options_api():
    """后端 /api/options/material 必须存在且带 spec/brand（富展示依赖）。"""
    from app.routes.options_api import ENTITY_CONFIG

    assert "material" in ENTITY_CONFIG, (
        "/api/options/material 未注册，前端 data-ks=\"material\" 会 404 且静默无候选"
    )
    cfg = ENTITY_CONFIG["material"]
    extra = cfg[3] if len(cfg) > 3 else ()
    assert "spec" in extra and "brand" in extra, (
        f'material 实体未覆盖 spec/brand，按规格或品牌搜不到。实际额外字段：{extra}'
    )


def test_backend_search_covers_material_fields():
    """后端搜索条件必须覆盖物料四字段，否则前端了候选也筛不出结果。

    直接读 app.py 源码文本（该函数定义在 app.py 模块级，不在 Flask 实例上）。
    """
    app_py = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "app.py")
    src = open(app_py, encoding="utf-8").read()
    m = re.search(r"def _apply_in_order_search\(.*?(?=\ndef )", src, re.S)
    assert m, "未找到 _apply_in_order_search 定义"
    body = m.group(0)
    for field in ("Material.code", "Material.name", "Material.spec", "Material.brand"):
        assert field in body, (
            f"_apply_in_order_search 缺少 {field}：关键词搜物料会漏结果，"
            "前端候选与后端口径不一致"
        )
