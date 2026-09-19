# -*- coding: utf-8 -*-
"""P1-2 新建表单必填校验回归锁（第 1 批 / 采购订单）。

背景（源码核实，非照抄计划文档）：
  purchase_order_add.html 的保存按钮是 `type="button"`，表单**从不原生提交**，
  所以模板上的 `required` 属性自己不会生效——必须配套 JS 才会真的拦得住。
  旧实现在 submitForm() 里是「逐条 showToast + 立刻 return」：只报第一条，
  用户改完再点才知道还有下一条，来回多次才填完一张单。

本次改成「一次收集全部 + 面板列出全部 + 一次性高亮全部缺失字段」，契约与
in_order_add.html / sales_order_add.html 的 wms-validation-panel 保持一致：
  error = { message, rowIndex?, selector? }
  rowIndex 存在   → 明细行错误（tr 加 wms-row-error，输入框加 wms-cell-error）
  rowIndex 不存在 → 表头错误（只给 selector 匹配的输入框加 wms-cell-error）

pytest 里没有 JS 引擎，所以锁的是**结构与口径**而不是运行时渲染。
"""

import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TPL_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "templates"
)

TPL = "purchase_order_add.html"

_PANEL_ID = "purchaseOrderValidationPanel"
_LIST_ID = "purchaseOrderValidationList"


def _src(name=TPL):
    with open(os.path.join(TPL_DIR, name), encoding="utf-8") as f:
        return f.read()


def _fn(src, name):
    """截取某个顶层函数的源码片段（到下一个顶层 `function ` 或文件尾为止）。"""
    pos = src.find("function %s(" % name)
    assert pos != -1, "%s 里找不到函数 %s()" % (TPL, name)
    nxt = src.find("\nfunction ", pos + 1)
    return src[pos:nxt] if nxt != -1 else src[pos:]


# ===================== 表头 required / 明细行 min =====================


def test_po_t1_date_has_required():
    m = re.search(r'<input[^>]*name="date"[^>]*>', _src())
    assert m, "找不到 name=date 的采购日期输入框"
    assert re.search(r"\brequired\b", m.group(0)), "采购日期缺少 required"


def test_po_t2_supplier_name_has_required():
    m = re.search(r'<input[^>]*name="supplier_name"[^>]*>', _src())
    assert m, "找不到 name=supplier_name 的供应商输入框"
    assert re.search(r"\brequired\b", m.group(0)), "供应商缺少 required"


def test_po_t3_qty_min_must_be_positive():
    m = re.search(r'<input[^>]*class="[^"]*material-qty[^"]*"[^>]*>', _src())
    assert m, "找不到明细行的数量输入框 material-qty"
    assert 'min="0.01"' in m.group(0), "数量必须 > 0，min 应为 0.01（原来是 min=\"0\"，允许填 0）"


def test_po_t4_price_min_keeps_zero():
    """单价允许为 0（赠品/搭赠），所以保持 min=\"0\"，不能跟着数量一起改成 0.01。"""
    m = re.search(r'<input[^>]*class="[^"]*material-price[^"]*"[^>]*>', _src())
    assert m, "找不到明细行的单价输入框 material-price"
    assert 'min="0"' in m.group(0), "单价允许为 0，min 应保持 0"


# ===================== 面板骨架与样式 =====================


def test_po_t5_panel_markup_exists():
    src = _src()
    assert 'id="%s"' % _PANEL_ID in src, "缺少校验面板容器"
    assert 'id="%s"' % _LIST_ID in src, "缺少校验面板列表"
    panel_pos = src.find('id="%s"' % _PANEL_ID)
    list_pos = src.find('id="%s"' % _LIST_ID)
    assert panel_pos < list_pos, "列表必须在面板容器内部"


def test_po_t6_panel_hidden_by_default_shown_by_class():
    """面板默认隐藏、加 .show 才显示——否则「请先处理以下问题」会常驻可见。"""
    src = _src()
    m = re.search(r"\.wms-validation-panel\s*\{[^}]*\}", src)
    assert m, "缺少 .wms-validation-panel 基础样式"
    assert re.search(r"display\s*:\s*none", m.group(0)), "面板默认必须隐藏"
    m2 = re.search(r"\.wms-validation-panel\.show\s*\{[^}]*\}", src)
    assert m2, "缺少 .wms-validation-panel.show 样式"
    assert re.search(r"display\s*:\s*block", m2.group(0)), "加 .show 后必须显示"


def test_po_t7_highlight_classes_defined():
    src = _src()
    assert "wms-row-error" in src and "wms-cell-error" in src, "缺少缺失字段高亮样式类"


# ===================== 提交校验改成一次报全部 =====================


def test_po_t8_old_early_return_toast_gone():
    """旧的逐条 showToast + return 必须被替换掉。"""
    src = _src()
    assert "showToast('请选择采购日期'" not in src, "旧的「请选择采购日期」早退分支仍在"
    assert "showToast('请至少添加一条采购明细'" not in src, "旧的「请至少添加一条采购明细」早退分支仍在"


def test_po_t9_submit_collects_all_before_post():
    """submitForm 必须先收集全部错误并展示，再 return；不能先发请求。"""
    body = _fn(_src(), "submitForm")
    c = body.find("collectPurchaseValidationErrors(")
    s = body.find("showPurchaseValidation(")
    p = body.find("WMS.api.post(")
    assert c != -1, "submitForm 未调用 collectPurchaseValidationErrors()"
    assert s != -1, "submitForm 未调用 showPurchaseValidation()"
    assert p != -1, "submitForm 未发起保存请求"
    assert c < s < p, "顺序必须是 收集 → 展示 → 再发请求"
    assert re.search(r"if\s*\(errors\.length\)\s*return\s*;", body), "收集到错误后必须 return"


def test_po_t10_collect_reads_required_attributes():
    """required 属性不能只是摆设：校验必须直接读 [required]，避免「属性写了但 JS 不认」。"""
    body = _fn(_src(), "collectPurchaseValidationErrors")
    assert "[required]" in body, "collectPurchaseValidationErrors 未按 [required] 扫描表头必填项"
    assert "items.length" in body, "缺少「至少一条明细」的兜底校验"


def test_po_t11_row_errors_carry_rowindex_and_selector():
    """明细行错误必须带 rowIndex（用于高亮整行）和 selector（用于高亮具体输入框）。"""
    body = _fn(_src(), "collectPurchaseValidationErrors")
    pushes = re.findall(r"errors\.push\(\{[^}]*\}\)", body)
    assert pushes, "collectPurchaseValidationErrors 没有产出任何错误项"
    row_pushes = [p for p in pushes if "rowIndex" in p]
    assert row_pushes, "明细行错误必须带 rowIndex"
    for p in row_pushes:
        assert "selector" in p, "带 rowIndex 的错误必须同时带 selector：%s" % p
        assert "第 " in p, "明细行错误文案必须指出行号：%s" % p


def test_po_t12_show_clears_then_highlights():
    body = _fn(_src(), "showPurchaseValidation")
    assert "clearPurchaseValidation()" in body, "展示前必须先清空上一次的高亮，否则会残留"
    assert "classList.add('show')" in body, "有错误时面板必须显示"
    assert "wms-cell-error" in body and "wms-row-error" in body, "必须一次性高亮全部缺失字段"


def test_po_t13_clear_removes_highlight():
    body = _fn(_src(), "clearPurchaseValidation")
    assert "wms-row-error" in body, "清理未移除 wms-row-error"
    assert "wms-cell-error" in body, "清理未移除 wms-cell-error"
    assert "classList.remove('show')" in body, "清理未隐藏面板"


def test_po_t14_blank_rows_not_validated():
    """页面预置 30 行空白行，未填物料编码的行不能被判为错误。"""
    body = _fn(_src(), "collectPurchaseValidationErrors")
    assert re.search(r"if\s*\(!code\)\s*return\s*;", body), "未填物料编码的空白行必须跳过校验"


def test_po_t15_template_still_compiles():
    """改动不能破坏 Jinja 语法。"""
    jinja2 = pytest.importorskip("jinja2")
    src = _src()
    try:
        jinja2.Environment().parse(src)
    except Exception as exc:  # pragma: no cover - 只在真的写坏时才走这里
        pytest.fail("purchase_order_add.html Jinja 语法错误：%s" % exc)
