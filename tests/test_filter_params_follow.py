# -*- coding: utf-8 -*-
"""筛选条件必须跟随「分页」与「导出」（AI-WMS-FILTER-002）。

背景：全系统筛选功能评估时发现两类静默错误——用户在列表页筛完，
① 点下一页，条件丢了；② 点导出，导出的是全量数据。
二者都不报错、不提示，用户以为筛了其实没筛，会污染对账与决策数据。

已修样本：
- out_order.html 分页链接漏 contract_no / project_name / warehouse_id /
  business_type；导出链接漏 business_type / contract_no / project_name，
  且 export_out_order() 后端根本没读这三个参数（只修前端会变成假修复）。
- purchase_order / sales_order 导出链接漏 contract_no / project_name。
- supplier / customer / category / unit / department / warehouse /
  subcontract* 的导出链接是硬编码无参 URL，而后端其实读 search / status /
  日期等参数——后端支持、前端没传。
- sales_order 分页链接漏 contract_no / project_name。

本测试用静态分析守住这条底线：**筛选表单里出现的字段，必须出现在同页
的分页链接与导出链接里**。新增筛选字段却忘了回填，此测试即失败。

判定口径（避免误报）：
- 筛选表单 = 含「搜索/查询/筛选/重置/清除」按钮的 <form> 块。
- embedded / csrf_token 属框架参数，不计入筛选字段。
- 无任何分页链接的模板（如数据量天然不分页）跳过分页断言。
- 无任何「数据导出」链接的模板跳过导出断言；export/import 模板下载
  （URL 含 template）不算数据导出。
- JS 运行时从表单收集参数的页面（如 sales_report.html 用 URLSearchParams
  + FormData）静态无法判定，列入 JS_DYNAMIC_EXPORT 白名单。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TPL_DIR = ROOT / "app" / "templates"

FORM_RE = re.compile(r"<form\b[^>]*>(.*?)</form>", re.I | re.S)
NAME_RE = re.compile(
    r"<(?:input|select|textarea)\b[^>]*?\bname\s*=\s*[\"']([A-Za-z_][\w]*)\s*[\"']",
    re.I | re.S,
)
FILTER_BTN = ("搜索", "查询", "筛选", "重置", "清除")
IGNORE_FIELDS = {"embedded", "csrf_token"}

# 允许一层嵌套括号：url_for('x', a=request.args.get('y', ''))
URLFOR_RE = re.compile(r"url_for\((?:[^()]|\([^()]*\))*\)")
PARAM_RE = re.compile(r"(\w+)\s*=")

# 导出参数在 JS 里运行时从筛选表单收集，静态分析看不到，单独豁免。
# 这类写法反而最健壮（加字段自动跟随），不是缺陷。
JS_DYNAMIC_EXPORT = {
    "sales_report.html",
    "sales_execution_report.html",
    "sales_outflow_report.html",
    "sales_price_analysis.html",
    "sales_trend_report.html",
}


def _read(name: str) -> str:
    return (TPL_DIR / name).read_text(encoding="utf-8", errors="replace")


def _filter_fields(src: str) -> set:
    """筛选表单里的字段名（排除框架参数）。"""
    fields = set()
    for m in FORM_RE.finditer(src):
        block = m.group(0)
        if any(k in block for k in FILTER_BTN):
            fields |= set(NAME_RE.findall(block))
    return {x for x in fields if x not in IGNORE_FIELDS}


def _pager_params(src: str):
    """分页链接的参数集合；无分页链接返回 None。"""
    params, found = set(), False
    for m in URLFOR_RE.finditer(src):
        snip = m.group(0)
        if re.search(r"\bpage\s*=", snip):
            found = True
            params |= set(PARAM_RE.findall(snip))
    for m in re.finditer(r'href="[^"]*[?&]page=[^"]*"', src):
        found = True
        params |= set(PARAM_RE.findall(m.group(0)))
    return params if found else None


def _export_params(src: str):
    """数据导出链接的参数集合；无导出链接返回 None。"""
    params, found = set(), False
    for m in URLFOR_RE.finditer(src):
        snip = m.group(0)
        if re.search(r"export", snip, re.I) and not re.search(r"template", snip, re.I):
            found = True
            params |= set(PARAM_RE.findall(snip))
    for m in re.finditer(r'href="([^"]*(?:export|excel)[^"]*)"', src, re.I):
        url = m.group(1)
        if "template" in url:
            continue  # 导入模板下载，不是导出当前筛选结果
        found = True
        params |= set(PARAM_RE.findall(url))
    return params if found else None


def _templates():
    return sorted(p.name for p in TPL_DIR.glob("*.html"))


def _scan(kind: str):
    """返回 [(模板名, 遗漏字段列表)]。"""
    bad = []
    for name in _templates():
        if kind == "export" and name in JS_DYNAMIC_EXPORT:
            continue
        src = _read(name)
        fields = _filter_fields(src)
        if not fields:
            continue
        params = _pager_params(src) if kind == "pager" else _export_params(src)
        if params is None:
            continue
        miss = sorted(fields - params)
        if miss:
            bad.append((name, miss))
    return bad


def test_pager_links_keep_all_filter_fields():
    """翻页时筛选条件不得丢失。"""
    bad = _scan("pager")
    assert not bad, (
        "以下模板的分页链接漏了筛选字段（翻页会丢条件）：\n"
        + "\n".join("  %s: %s" % (n, ", ".join(m)) for n, m in bad)
    )


def test_export_links_keep_all_filter_fields():
    """导出必须跟随当前筛选，否则用户拿到的是全量数据。"""
    bad = _scan("export")
    assert not bad, (
        "以下模板的导出链接漏了筛选字段（导出与页面不一致）：\n"
        + "\n".join("  %s: %s" % (n, ", ".join(m)) for n, m in bad)
    )


def test_scan_rules_are_effective():
    """防「规则本身失效」：扫描器必须能识别出真实的筛选字段与链接参数。"""
    # in_order.html 是公认的标杆：分页与导出都带全 10 个筛选字段
    src = _read("in_order.html")
    fields = _filter_fields(src)
    assert "contract_no" in fields and "project_name" in fields, (
        "扫描器未能识别 in_order.html 的筛选字段，规则已失效"
    )
    pager = _pager_params(src)
    assert pager is not None and "contract_no" in pager, (
        "扫描器未能识别 in_order.html 的分页参数，规则已失效"
    )
    export = _export_params(src)
    assert export is not None and "contract_no" in export, (
        "扫描器未能识别 in_order.html 的导出参数，规则已失效"
    )


def test_known_good_pages_stay_green():
    """已修页面不得回退（回归锁定）。"""
    for name in ("out_order.html", "sales_order.html", "supplier.html",
                 "subcontract.html"):
        src = _read(name)
        fields = _filter_fields(src)
        if not fields:
            continue
        export = _export_params(src)
        if export is not None:
            miss = sorted(fields - export)
            assert not miss, "%s 导出回退，漏：%s" % (name, ", ".join(miss))


@pytest.mark.parametrize("name", _templates())
def test_export_url_not_hardcoded_without_filters(name):
    """导出链接不得是「硬编码零参数」——那等于永远导出全量。"""
    if name in JS_DYNAMIC_EXPORT:
        pytest.skip("JS 动态收集参数，静态不可判定")
    src = _read(name)
    fields = _filter_fields(src)
    if not fields:
        pytest.skip("无筛选表单")
    for m in re.finditer(r'href="(/[\w/]*/export)"', src):
        raise AssertionError(
            "%s 的导出链接 %s 未携带任何筛选参数；"
            "若后端支持筛选应补参数，若不支持请改为显式说明" % (name, m.group(1))
        )
