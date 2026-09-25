# -*- coding: utf-8 -*-
"""P1-2 新建表单必填校验回归锁（第 2 批 / 售后出库单）。

背景（源码核实，非照抄计划文档）：
  after_sale_out_add.html 的保存按钮是 `type="button"`，表单**从不原生提交**，
  所以模板上的 `required` 自己不会生效——仓库、库位早就是 required，旧 JS 却只
  校验了仓库，库位的红色星号形同虚设，用户能一路点到后端才被拒。

  更严重的是旧实现把 `return` 写在明细行 for 循环**内部**：第 1 行数量为空就
  直接退出，后面 29 行根本不检查，用户要来回点很多次才填完一张单。

本次改成「一次收集全部 + 面板列出全部 + 一次性高亮全部缺失字段」，契约与
in_order_add.html / sales_order_add.html 的 wms-validation-panel 保持一致：
  error = { message, rowIndex?, selector? }

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

TPL = "after_sale_out_add.html"

_PANEL_ID = "afterSaleOutValidationPanel"
_LIST_ID = "afterSaleOutValidationList"


def _src(name=TPL):
    with open(os.path.join(TPL_DIR, name), encoding="utf-8") as f:
        return f.read()


def _fn(src, name):
    """截取某个顶层函数的源码片段（到下一个顶层 `function ` 或文件尾为止）。"""
    pos = src.find("function %s(" % name)
    assert pos != -1, "%s 里找不到函数 %s()" % (TPL, name)
    nxt = src.find("\nfunction ", pos + 1)
    return src[pos:nxt] if nxt != -1 else src[pos:]


def _input_by_name(src, name):
    m = re.search(r'<input[^>]*name="%s"[^>]*>' % re.escape(name), src)
    assert m, "找不到 name=%s 的输入框" % name
    return m.group(0)


# ===================== 表头 required / 明细行 min =====================


def test_aso_t1_date_has_required():
    assert re.search(r"\brequired\b", _input_by_name(_src(), "date")), "日期缺少 required"


def test_aso_t2_customer_has_required():
    assert re.search(r"\brequired\b", _input_by_name(_src(), "customer")), "客户名称缺少 required"


def test_aso_t3_warehouse_keeps_required():
    # P1-6（2026-09-25）：仓库参数统一为 warehouse_id（ID），required 语义不变
    m = re.search(r'<select[^>]*name="warehouse_id"[^>]*>', _src())
    assert m, "找不到 name=warehouse_id 的下拉框"
    assert re.search(r"\brequired\b", m.group(0)), "仓库必须保持 required"


def test_aso_t4_location_required_and_conditional():
    """库位只在开启库位管理时渲染；渲染出来就必须带 required（否则星号形同虚设）。"""
    src = _src()
    assert re.search(r"\brequired\b", _input_by_name(src, "location")), "库位缺少 required"
    # 必须仍受 location_management_enabled 开关控制，未开启时不得出现
    loc_pos = src.find('name="location"')
    if_pos = src.find("{% if location_management_enabled %}")
    assert if_pos != -1, "location_management_enabled 开关被移除了"
    assert if_pos < loc_pos, "库位字段必须仍在 location_management_enabled 分支内"


def test_aso_t5_qty_min_positive_price_min_zero():
    src = _src()
    m = re.search(r'<input[^>]*class="[^"]*material-qty[^"]*"[^>]*>', src)
    assert m, "找不到明细行数量输入框 material-qty"
    assert 'min="0.01"' in m.group(0), "数量必须 > 0，min 应为 0.01"
    m2 = re.search(r'<input[^>]*class="[^"]*material-price[^"]*"[^>]*>', src)
    assert m2, "找不到明细行单价输入框 material-price"
    assert 'min="0"' in m2.group(0), "单价允许为 0（赠品），min 应保持 0"


# ===================== 面板骨架与样式 =====================


def test_aso_t6_panel_markup_exists():
    src = _src()
    assert 'id="%s"' % _PANEL_ID in src, "缺少校验面板容器"
    assert 'id="%s"' % _LIST_ID in src, "缺少校验面板列表"


def test_aso_t7_panel_hidden_by_default_shown_by_class():
    src = _src()
    m = re.search(r"\.wms-validation-panel\s*\{[^}]*\}", src)
    assert m, "缺少 .wms-validation-panel 基础样式"
    assert re.search(r"display\s*:\s*none", m.group(0)), "面板默认必须隐藏"
    m2 = re.search(r"\.wms-validation-panel\.show\s*\{[^}]*\}", src)
    assert m2, "缺少 .wms-validation-panel.show 样式"
    assert re.search(r"display\s*:\s*block", m2.group(0)), "加 .show 后必须显示"


def test_aso_t8_highlight_classes_defined():
    src = _src()
    assert "wms-row-error" in src and "wms-cell-error" in src, "缺少缺失字段高亮样式类"


# ===================== 提交校验改成一次报全部 =====================


def test_aso_t9_old_early_returns_gone():
    """旧的逐条 showToast + return（含循环内的那个）必须全部被替换掉。"""
    src = _src()
    for old in [
        "showToast('请填写完整的物料信息'",
        "showToast('请至少添加一条物料'",
        "showToast('仓库不能为空，请选择仓库'",
    ]:
        assert old not in src, "旧的早退分支仍在：%s" % old


def test_aso_t10_row_scan_has_no_early_return():
    """关键修复：遍历明细行时不得再遇到第一个错误就 return。"""
    body = _fn(_src(), "collectAfterSaleOutRows")
    assert "showToast" not in body, "明细行遍历里不能再出现 showToast 早退"
    # 唯一允许的 return 是「跳过空白行」，以及末尾统一返回
    returns = re.findall(r"return[^;{]*;", body)
    for r in returns:
        assert r.strip() == "return;", "遍历里出现非跳过的 return：%s" % r
    assert "return { items: items, errors: errors }" in body, "末尾必须一次性返回全部明细与错误"


def test_aso_t11_submit_collects_all_before_fetch():
    body = _fn(_src(), "submitForm")
    c1 = body.find("collectAfterSaleOutRows(")
    c2 = body.find("collectAfterSaleOutErrors(")
    s = body.find("showAfterSaleOutValidation(")
    f = body.find("fetch('/after_sale_out/add'")
    assert c1 != -1 and c2 != -1, "submitForm 未收集校验错误"
    assert s != -1, "submitForm 未展示校验错误"
    assert f != -1, "submitForm 未发起保存请求"
    assert max(c1, c2) < s < f, "顺序必须是 收集 → 展示 → 再发请求"
    assert re.search(r"if\s*\(errors\.length\)\s*return\s*;", body), "收集到错误后必须 return"


def test_aso_t12_collect_reads_required_attributes():
    """required 不能只是摆设：校验必须直接读 [required]。"""
    body = _fn(_src(), "collectAfterSaleOutErrors")
    assert "[required]" in body, "collectAfterSaleOutErrors 未按 [required] 扫描表头必填项"
    assert "#addForm" in body, "扫描范围必须限定在当前表单内"
    assert "items.length" in body, "缺少「至少一条物料」的兜底校验"


def test_aso_t13_row_errors_carry_rowindex_and_selector():
    body = _fn(_src(), "collectAfterSaleOutRows")
    pushes = re.findall(r"errors\.push\(\{[^}]*\}\)", body)
    assert pushes, "collectAfterSaleOutRows 没有产出任何错误项"
    for p in pushes:
        assert "rowIndex" in p, "明细行错误必须带 rowIndex：%s" % p
        assert "selector" in p, "明细行错误必须带 selector：%s" % p
        assert "第 " in p, "明细行错误文案必须指出行号：%s" % p


def test_aso_t14_show_clears_then_highlights():
    body = _fn(_src(), "showAfterSaleOutValidation")
    assert "clearAfterSaleOutValidation()" in body, "展示前必须先清空上一次的高亮"
    assert "classList.add('show')" in body, "有错误时面板必须显示"
    assert "wms-cell-error" in body and "wms-row-error" in body, "必须一次性高亮全部缺失字段"


def test_aso_t15_clear_removes_highlight():
    body = _fn(_src(), "clearAfterSaleOutValidation")
    assert "wms-row-error" in body and "wms-cell-error" in body, "清理未移除高亮类"
    assert "classList.remove('show')" in body, "清理未隐藏面板"


def test_aso_t16_blank_rows_not_validated():
    body = _fn(_src(), "collectAfterSaleOutRows")
    assert re.search(r"if\s*\(!code\)\s*return\s*;", body), "未填物料编码的空白行必须跳过校验"


def test_aso_t17_template_still_compiles():
    jinja2 = pytest.importorskip("jinja2")
    try:
        jinja2.Environment().parse(_src())
    except Exception as exc:  # pragma: no cover - 只在真的写坏时才走这里
        pytest.fail("after_sale_out_add.html Jinja 语法错误：%s" % exc)
