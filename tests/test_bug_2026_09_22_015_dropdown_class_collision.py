# -*- coding: utf-8 -*-
"""BUG-2026-09-22-015：下拉框 span 抢占行内字段 class（.spec/.name/.unit），
采购申请/销售单保存抛 TypeError 或静默写入失败。

现场（真人操作复现）：新增采购申请，物料自动补全下拉渲染后点「保存」，
`collectItems()` 在 `row.querySelector('.spec').value.trim()` 抛
`Cannot read properties of undefined (reading 'trim')`——
`querySelector('.spec')` 按文档序先命中下拉注入的
`<span class="spec">`（无 .value），而不是真正的
`<input class="form-control spec">`。同理 `.name`/`.unit` 被抢占时，
`row.querySelector('.name').value = ...` 静默写入失败（span 无 value 语义）。

根因：物料/供应商自动补全下拉把行内字段的语义 class
（code/name/spec/unit）直接用在展示 span 上，污染了行内 class 命名空间。
受影响模板 7 个：purchase_request_add / sales_order_add / sales_order_edit /
in_order_add / out_order_add / after_sale_out_add / ai_location_recommendation。

修复：下拉 span 统一迁入 `dropdown-*` 命名空间（dropdown-code / dropdown-name /
dropdown-spec / dropdown-unit），CSS 选择器同步，行内字段 class 恢复独占。

断言：
  T1 7 个模板下拉生成代码中不再出现裸字段 class 的 span
  T2 CSS 选择器同步收敛（无残留 .material-dropdown-item .spec 等）
  T3 运行时模拟：含下拉残留的行，`.spec` 首个命中必须是 INPUT（复现 TypeError 场景）
  T4 运行时模拟：`.name`/`.unit` 首个命中必须是 INPUT（销售单场景）
"""
import re
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

TEMPLATES = Path(__file__).resolve().parents[1] / "app" / "templates"

AFFECTED = [
    "purchase_request_add.html",
    "sales_order_add.html",
    "sales_order_edit.html",
    "in_order_add.html",
    "out_order_add.html",
    "after_sale_out_add.html",
    "ai_location_recommendation.html",
]

FIELD_CLASSES = ("code", "name", "spec", "unit")


def _read(name):
    return (TEMPLATES / name).read_text(encoding="utf-8")


@pytest.mark.parametrize("tpl", AFFECTED)
def test_t1_no_bare_field_class_span_in_dropdown_markup(tpl):
    """T1：模板中不得再生成 <span class="code|name|spec|unit"> 这类裸字段 class。"""
    src = _read(tpl)
    for cls in FIELD_CLASSES:
        hits = re.findall(rf'<span class="{cls}"', src)
        assert not hits, (
            f"{tpl} 仍存在 <span class=\"{cls}\"> ×{len(hits)}，"
            f"会抢占行内 <input class=\"...{cls}\"> 的 querySelector 命中"
        )


@pytest.mark.parametrize("tpl", AFFECTED)
def test_t2_css_selectors_migrated(tpl):
    """T2：CSS 中不得残留针对下拉 span 旧 class 的选择器。"""
    src = _read(tpl)
    stale = re.findall(
        r"\.(?:material|supplier)-(?:dropdown-item|option)\s+\.(code|name|spec|unit)\b",
        src,
    )
    assert not stale, f"{tpl} 残留旧 CSS 选择器: {stale}"


def _simulate_first_hit(dropdown_span_class, row_input_class):
    """模拟 JS `row.querySelector('.X')`：返回文档序首个命中的 tag 名。

    构造「行内既有下拉残留 span、又有真实 input」的最小场景——
    只放被测的那一个 class，避免硬编码其他 class 干扰命中顺序。
    """
    html = f"""
    <table><tbody><tr>
      <td>
        <div class="material-dropdown">
          <div class="material-dropdown-item">
            <span class="{dropdown_span_class}">下拉残留</span>
          </div>
        </div>
      </td>
      <td><input type="text" class="form-control {row_input_class}" readonly></td>
    </tr></tbody></table>
    """
    soup = BeautifulSoup(html, "html.parser")
    row = soup.find("tr")
    hit = row.select(f".{row_input_class}")[0]
    return hit.name


def test_t3_runtime_spec_first_hit_must_be_input():
    """T3：下拉残留存在时，.spec 首个命中必须是 input（否则 .value 抛 TypeError）。

    用与模板一致的下拉 class 命名构造场景：修复后模板生成的是
    <span class="dropdown-spec">，因此 .spec 选择器只能命中行内 input。
    """
    src = _read("purchase_request_add.html")
    m = re.search(r'<span class="([\w-]+)">[^<]*(?:\$\{escapeHtml\(m\.spec\)\}|m\.spec)', src)
    span_cls = m.group(1) if m else "spec"
    tag = _simulate_first_hit(span_cls, "spec")
    assert tag == "input", (
        f"row.querySelector('.spec') 首个命中是 <{tag}>（下拉 span class={span_cls}），"
        f"保存时 .value 将抛 TypeError"
    )


def test_t4_runtime_name_unit_first_hit_must_be_input():
    """T4：销售单场景 .name/.unit 首个命中必须是 input（否则写入静默失败）。"""
    src = _read("sales_order_add.html")
    for field in ("name", "unit"):
        m = re.search(
            rf"<span class=\"([\w-]+)\">\s*'\s*\+\s*esc\((?:m\.{field}|unitName\(m\))", src)
        span_cls = m.group(1) if m else field
        tag = _simulate_first_hit(span_cls, field)
        assert tag == "input", (
            f"row.querySelector('.{field}') 首个命中是 <{tag}>，"
            f"fillRow 写入将静默失败"
        )


def test_t5_dropdown_namespace_adopted():
    """T5：下拉 span 已迁入 dropdown-* 命名空间（防改一半）。"""
    for tpl in AFFECTED:
        src = _read(tpl)
        if "dropdown-spec" in src or "dropdown-name" in src:
            continue
        # 该模板已无 dropdown span 也行，但至少不允许既无新名又无改动痕迹
        assert not re.search(r'<span class="(code|name|spec|unit)"', src), (
            f"{tpl} 既未迁移到 dropdown-* 命名空间，也未移除裸 class span"
        )
