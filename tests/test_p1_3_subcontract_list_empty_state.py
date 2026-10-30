# -*- coding: utf-8 -*-
"""P1-3 空态回归锁：委外三页主列表在无数据时必须显示中文空态，不能只剩表头。

背景（WMS完善现有功能开发计划.md §3 P1-3）
------------------------------------------
列表页在「无数据」时只剩一个 `thead`，用户**分不清是加载失败还是真没数据**，
计划把这条列为「影响日常实用第 1 位」。委外（加工单/发料/收货）是计划点名的
第一个业务域，本次先收口这三页主列表。

实现要点
--------
用 Jinja2 原生的 `{% for %}...{% else %}...{% endfor %}`：循环为空时渲染 else
分支。**不引入 JS 判断、不改后端、不动业务逻辑**，纯粹是模板层空态。

为什么锁 colspan
----------------
空态单元格的 `colspan` 必须等于该表 `thead` 的列数，否则表格会出现错位/断列
（这正是"加空态"最容易写错的地方，且肉眼在浏览器里不易发现）。故本测试用
**自动数 thead 列数**来校验，而不是写死数字——表头将来加列时测试自动跟随。

注意：本文件只做**模板静态 + 渲染**校验，不起 Flask 服务。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parent.parent
TPL_DIR = ROOT / "app" / "templates"

# (模板, 主列表循环变量, 空态关键文案)
CASES = [
    ("subcontract.html", "orders", "暂无委外加工单"),
    ("subcontract_issue.html", "issues", "暂无委外发料单"),
    ("subcontract_receive.html", "receives", "暂无委外收货单"),
]


@pytest.fixture(scope="module")
def env():
    """裸 Jinja 环境 + Flask 常用全局 stub。

    列表行里会调 `url_for(...)` 等 Flask 全局；本测试不启 app context
    （太重），故注入最小 stub，让"有数据"分支也能渲染出来做反向断言。
    """
    e = Environment(loader=FileSystemLoader(str(TPL_DIR)))
    e.globals.setdefault("url_for", lambda *a, **k: "#")
    e.globals.setdefault("csrf_token", lambda: "test-csrf")
    e.globals.setdefault("get_flashed_messages", lambda *a, **k: [])
    return e


def _main_tbody_block(text: str) -> str:
    """取主列表的 tbody 块（跳过 itemTableBody 这类明细行容器）。"""
    for m in re.finditer(r"<tbody([^>]*)>(.*?)</tbody>", text, re.S):
        attrs, blk = m.group(1), m.group(2)
        if "itemTableBody" in attrs:      # 明细行表格，由 JS 动态加行，不属本契约
            continue
        if "{% for" in blk:
            return blk
    raise AssertionError("未找到主列表 tbody 循环块")


def _thead_col_count(text: str, tbody_start: int) -> int:
    """统计该 tbody 之前最近一个 thead 的列数。"""
    head = text[:tbody_start]
    m = None
    for m in re.finditer(r"<thead[^>]*>(.*?)</thead>", head, re.S):
        pass
    assert m is not None, "未找到 thead"
    return len(re.findall(r"<th[\s>]", m.group(1)))


@pytest.mark.parametrize("name,var,text", CASES)
def test_t1_has_empty_state_branch(name, var, text):
    """主列表循环必须带 {% else %} 空态分支。"""
    src = (TPL_DIR / name).read_text(encoding="utf-8")
    blk = _main_tbody_block(src)
    assert "{% else %}" in blk, f"{name} 主列表缺空态分支"
    assert text in blk, f"{name} 空态文案缺失/不匹配（期望含「{text}」）"


@pytest.mark.parametrize("name,var,text", CASES)
def test_t2_colspan_matches_thead(name, var, text):
    """空态单元格 colspan 必须等于表头列数（防表格错位）。"""
    src = (TPL_DIR / name).read_text(encoding="utf-8")
    m = re.search(r"<tbody([^>]*)>", src)
    tbody_m = None
    for m in re.finditer(r"<tbody([^>]*)>(.*?)</tbody>", src, re.S):
        if "itemTableBody" in m.group(1):
            continue
        if "{% for" in m.group(2):
            tbody_m = m
            break
    assert tbody_m is not None
    cols = _thead_col_count(src, tbody_m.start())
    blk = tbody_m.group(2)
    cs = re.search(r'colspan="(\d+)"', blk)
    assert cs, f"{name} 空态未设置 colspan"
    assert int(cs.group(1)) == cols, (
        f"{name} 空态 colspan={cs.group(1)} 与表头列数 {cols} 不一致，表格会错位"
    )


@pytest.mark.parametrize("name,var,text", CASES)
def test_t3_renders_empty_state_when_list_empty(env, name, var, text):
    """渲染验证：列表为空时输出空态文案；有数据时不输出（不误伤正常路径）。"""
    src = (TPL_DIR / name).read_text(encoding="utf-8")
    tpl = env.from_string(src)
    # 逐个变量置空过于脆弱（模板引用大量上下文），改为只针对本契约做最小渲染：
    # 抽出主列表 tbody 片段单独渲染，避免整个页面依赖 app context。
    m = None
    for m in re.finditer(r"<tbody([^>]*)>(.*?)</tbody>", src, re.S):
        if "itemTableBody" in m.group(1):
            continue
        if "{% for" in m.group(2):
            break
    frag = m.group(0)
    frag_tpl = env.from_string(frag)

    empty_html = frag_tpl.render(**{var: []})
    assert text in empty_html, f"{name} 空列表未渲染空态"

    # 有数据时不应出现空态（构造一行假数据对象，模板只用到少量属性）
    class _Row:
        id = 1

        def __getattr__(self, _):
            return ""

    filled = frag_tpl.render(**{var: [_Row()]})
    assert text not in filled, f"{name} 有数据时不应显示空态"


def test_t4_no_js_only_empty_state_regression():
    """防回归：空态必须是模板层（Jinja），不能只靠 JS 兜底。

    若有人把空态改成"页面加载后 JS 判断长度再插入"，弱网/JS 报错时又会退回
    "只剩表头"的原状，故在此锁死。
    """
    for name, var, text in CASES:
        src = (TPL_DIR / name).read_text(encoding="utf-8")
        # 文案必须出现在模板源码里（Jinja 静态可见），而不是 JS 字符串拼接
        assert text in src, f"{name} 空态文案不在模板源码中（疑似改成了 JS 动态插入）"
