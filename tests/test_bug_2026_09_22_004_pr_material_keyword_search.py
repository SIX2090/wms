# -*- coding: utf-8 -*-
"""BUG-2026-09-22-004 回归：采购申请单物料编码框无法像采购入库单那样关键词联想。

事故：``purchase_request_add.html`` 的物料联想与 ``in_order_add.html`` 口径不一致。

根因（两个叠加）：

  1. ``bindMaterialInput`` 的 ``input`` 事件里先调 ``findMaterialQuickMatch(keyword)``，
     该函数最后一条分支是 ``materials.find(m => materialSearchText(m).includes(normalized))``
     ——**模糊命中即自动选中并回填编码**。用户敲下第一个字符（如 ``0``）时，只要该字符
     出现在任意一条物料的 code/name/spec/unit 拼接串中，输入框就会被强行改写成那条物料
     的编码，用户再也无法继续输入完整关键词，联想下拉自然弹不出来。
     而采购入库单的 ``findMaterialByCode`` **只做编码完全相等**（``===``）判断，不误吞。
     ``materialSearchText`` 未纳入 ``brand``，品牌词也搜不到。

  2. 整个联想只靠页面初始化一次性灌入的 ``materials`` 做前端 ``filter``，未接
     ``/api/material/search`` 服务端模糊搜索——上万条物料时首屏卡顿，新建物料后本页刷不出来。

修复：
  * ``findMaterialQuickMatch`` 去掉 ``includes`` 模糊分支，只保留编码/名称完全相等；
  * ``materialSearchText`` / ``getMaterialMatches`` 纳入 ``brand``；
  * ``showDropdown`` 改为「服务端搜索（220ms 防抖 + 请求序号防竞态）+ 本地缓存兜底」，
    与采购入库单同构；
  * 新增 ``getMaterialUnitName`` / ``getMaterialUnitId`` 归一化 unit——
    本地缓存里 ``unit`` 是对象 ``{id,name}``，而服务端返回的是字符串，
    原 ``material.unit.name`` 写法在服务端命中时会把单位填成空。

测试用例（纯源码门禁，无需 app context，符合 A12/R7）：
  T1. findMaterialQuickMatch 不再包含 includes 模糊自动选中分支；
  T2. findMaterialQuickMatch 仍保留编码、名称的完全相等匹配；
  T3. materialSearchText 纳入 brand；
  T4. getMaterialMatches 的精确/前缀判断覆盖 brand；
  T5. showDropdown 接入 /api/material/search 且有防抖与请求序号防竞态；
  T6. showDropdown 在服务端失败/网络异常时降级到本地过滤；
  T7. unit 归一化函数存在且 selectMaterial 用它们取值（不再直取 material.unit.name）；
  T8. selectMaterialByDropdownItem 在本地缓存缺该物料时有回源兜底。
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TPL = ROOT / "app" / "templates" / "purchase_request_add.html"
IN_ORDER_TPL = ROOT / "app" / "templates" / "in_order_add.html"


def _src() -> str:
    return TPL.read_text(encoding="utf-8")


def _fn_body(src: str, name: str) -> str:
    """抓取 ``function name(...) { ... }`` 函数体（以同缩进的 ``\\nfunction `` 为界）。"""
    m = re.search(
        r"function " + re.escape(name) + r"\(.*?\{(.*?)\nfunction ",
        src,
        re.S,
    )
    assert m, f"未找到函数 {name}"
    return m.group(1)


def test_T1_no_fuzzy_auto_select():
    body = _fn_body(_src(), "findMaterialQuickMatch")
    assert "materialSearchText(m).includes" not in body, (
        "findMaterialQuickMatch 仍含 includes 模糊分支——输入首字符即被自动回填，"
        "用户无法继续输入关键词（BUG-2026-09-22-004 根因）"
    )
    assert ".includes(" not in body, (
        "findMaterialQuickMatch 仍含包含式匹配，应只做完全相等"
    )


def test_T2_keeps_exact_match():
    body = _fn_body(_src(), "findMaterialQuickMatch")
    assert "String(m.code || '').toLowerCase() === normalized" in body, "编码完全相等匹配缺失"
    assert "String(m.name || '').toLowerCase() === normalized" in body, "名称完全相等匹配缺失"


def test_T3_search_text_includes_brand():
    body = _fn_body(_src(), "materialSearchText")
    assert "material.brand" in body, "materialSearchText 未纳入 brand，品牌词搜不到"


def test_T4_matches_cover_brand():
    body = _fn_body(_src(), "getMaterialMatches")
    assert "brand === normalized" in body, "getMaterialMatches 精确判断未覆盖 brand"
    assert "brand.startsWith(normalized)" in body, "getMaterialMatches 前缀判断未覆盖 brand"


def test_T5_server_search_with_debounce_and_race_guard():
    body = _fn_body(_src(), "showDropdown")
    assert "/api/material/search" in body, "showDropdown 未接入服务端搜索接口"
    assert "clearTimeout" in body and "setTimeout" in body, "缺少防抖（clearTimeout/setTimeout）"
    assert "materialSearchState.seq" in body, "缺少请求序号防竞态覆盖"
    assert "++materialSearchState.seq" in body, "未自增请求序号"


def test_T6_local_fallback_on_failure():
    body = _fn_body(_src(), "showDropdown")
    assert ".catch(" in body, "缺少网络异常降级分支"
    assert "getMaterialMatches(keyword" in body, "网络异常时未降级为本地缓存过滤"


def test_T7_unit_normalized():
    src = _src()
    assert re.search(r"function getMaterialUnitName\(", src), "缺少 unit 名称归一化函数"
    assert re.search(r"function getMaterialUnitId\(", src), "缺少 unit id 归一化函数"
    body = _fn_body(src, "selectMaterial")
    assert "getMaterialUnitName(material)" in body, "selectMaterial 未用归一化函数取单位名"
    assert "material.unit ? material.unit.name" not in body, (
        "selectMaterial 仍直取 material.unit.name——服务端返回 unit 是字符串，会填成空"
    )


def test_T8_dropdown_item_has_refetch_fallback():
    body = _fn_body(_src(), "selectMaterialByDropdownItem")
    assert "/api/material/search" in body, "下拉项点选缺少回源兜底"


def test_T9_parity_with_in_order_page():
    """与采购入库单对齐：入库单的 findMaterialByCode 只做编码完全相等，
    申请单也不得出现「模糊即自动选中」。"""
    in_order = IN_ORDER_TPL.read_text(encoding="utf-8")
    assert "function findMaterialByCode(" in in_order, "采购入库单基准函数缺失（模板被改？）"
    pr_body = _fn_body(_src(), "findMaterialQuickMatch")
    assert "===" in pr_body, "申请单缺少完全相等匹配"
    assert ".includes(" not in pr_body, "申请单仍存在模糊自动选中，与入库单口径不一致"
