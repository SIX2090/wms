# -*- coding: utf-8 -*-
"""BUG-2026-11-28-002 回归测试：领料单、领料单详情与领料明细报表第二批报表对齐、布局 UX 与业务细节修复。

Part A（纯 AST / Jinja / openpyxl / Node-VM，本地 Windows 与 Linux CI 均执行，支持 R8 文件备份回退验证）：
- P1-1：out_detail 报表与 in_detail 对齐（合同编号/工程名称/领料人/仓库/库位列与筛选/排序、material_id 精确查询、
  停用历史仓下拉、web_print=1 快照打印、副标题说明、report_inout_print 往来方优先级）
- P1-2：out_order_detail.html 布局与交互收口（title 前置 out_document_label、统一 #columnSettingsBtn 与
  setupDynamicDetailColumnControls、去除重复旧列设置与 .resize-handle/手写拖拽、补用途与领料人信息卡、
  停用仓禁用兜底选项、saveHeader._busy 防连点、移除阻塞 alert 兜底）
- P1-3：out_order.html 与 out-order-list.js 修复（平衡两行筛选网格、清除保留 list_base_path 与 warehouse_id、
  只读角色隐藏勾选列、往来方与空业务类型展示修正、操作列不换行、列拖动 off-by-one 修复与 dragMoved 清理、
  singleOutOrderAction 异常 warning→force=true 交互与防连点锁、Node-VM 行为验证）
- P1-4：out_order_add.html 与后端/自动领料/打印模板收口（_initOutOrderRow 复用、编辑草稿不误弹联想下拉、
  业务类型切换联动、前端负单价拦截、清理 console.log 与死 dataset；_out_order_stock_error 物料编码名称、
  _build_out_order_excel 含箱号表头合并偏移、add_out_order 合同/部门存在性校验与行级合同继承、
  行内增删改与批量完成补 log_operation、批量删除全失败返回 400、批量完成异常脱敏、
  execute_auto_push_requisition 继承合同工程、print_out_with_excel 展示单号/仓库并校验 r.ok/has_file、
  /export/template/out_order 补合同编号与工程名称）
- P1-5：_ai_analyze_out_order_anomalies 按单据仓库与物料范围计算近 30 天净日均（扣减 revert_out）、
  已完成单跳过超库存误报、未完成草稿覆盖负库存并调整摘要文案

Part B（完整隔离 Flask + SQLite 端到端集成测试，于 Linux CI 运行）。
"""
from __future__ import annotations

import ast
import io
import json
import os
import shutil
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import jinja2
import pytest
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
APP_PY = ROOT / "app" / "app.py"
OUT_ORDER_PY = ROOT / "app" / "routes" / "out_order.py"
REPORT_PY = ROOT / "app" / "routes" / "report.py"
EXPORT_PY = ROOT / "app" / "routes" / "export.py"
IN_COMPLETE_PY = ROOT / "app" / "services" / "in_order_completion.py"
OUT_LIST_HTML = ROOT / "app" / "templates" / "out_order.html"
OUT_ADD_HTML = ROOT / "app" / "templates" / "out_order_add.html"
OUT_DETAIL_HTML = ROOT / "app" / "templates" / "out_order_detail.html"
REPORT_VIEW_HTML = ROOT / "app" / "templates" / "report_view.html"
PRINT_OUT_EXCEL_HTML = ROOT / "app" / "templates" / "print_out_with_excel.html"
OUT_LIST_JS = ROOT / "app" / "static" / "js" / "pages" / "out-order-list.js"

_IS_LINUX_ISOLATED = sys.platform.startswith("linux") or os.environ.get("WMS_RUN_FULL_INTEGRATION") == "1"


def _get_func(path: Path, name: str) -> tuple[ast.FunctionDef, str]:
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            lines = src.splitlines()
            return node, "\n".join(lines[node.lineno - 1 : node.end_lineno])
    raise AssertionError(f"Function {name} not found in {path}")


# ==================== Part A: 纯 AST / Jinja / openpyxl / Node-VM 回归 ====================


def test_p1_1_out_detail_report_parity_and_inout_print_partner():
    """P1-1: out_detail matches in_detail columns, filters, sorting, inactive warehouses, web_print, and subtitle."""
    _, cols_body = _get_func(APP_PY, "_out_detail_columns")
    for field in ("'contract_no'", "'project_name'", "'picker'", "'warehouse'", "'location'"):
        assert field in cols_body, f"_out_detail_columns missing {field}"

    _, row_body = _get_func(APP_PY, "_out_detail_row")
    for key in ("'contract_no':", "'project_name':", "'picker':", "'warehouse':", "'location':"):
        assert key in row_body, f"_out_detail_row missing {key}"

    _, query_body = _get_func(APP_PY, "_filtered_out_detail_query")
    assert "if filters.get('material_id'):" in query_body
    assert "_apply_header_or_item_contract_filters(" in query_body
    assert "item_level=True" in query_body

    _, check_query_body = _get_func(APP_PY, "_filtered_check_query")
    assert "OutOrderItem" not in check_query_body, "_filtered_check_query must not touch OutOrderItem"

    _, filters_body = _get_func(APP_PY, "_build_report_filters")
    assert "report_type in ('in_detail', 'ledger') or report_type in _OUT_DETAIL_REPORT_TYPES" in filters_body
    assert "report_type == 'in_detail' or report_type in _OUT_DETAIL_REPORT_TYPES" in filters_body

    app_src = APP_PY.read_text(encoding="utf-8")
    sort_seg = app_src[app_src.index("_OUT_DETAIL_SORT_MAP = {") : app_src.index("def _sql_order_by(")]
    assert "func.coalesce(func.nullif(OutOrder.business_type, ''), '领料单')" in sort_seg
    for key in ("'contract_no':", "'project_name':", "'picker':", "'warehouse':", "'location':"):
        assert key in sort_seg, f"_OUT_DETAIL_SORT_MAP missing {key}"

    _, rview_body = _get_func(REPORT_PY, "report_view")
    assert "report_type == 'in_detail' or report_type in _OUT_DETAIL_REPORTS" in rview_body

    _, inout_body = _get_func(REPORT_PY, "report_inout_print")
    assert "if order.business_type in ('销售出库', '采购退货出库', '其他出库')" in inout_body

    rv_html = REPORT_VIEW_HTML.read_text(encoding="utf-8")
    assert "{% elif report_type == 'out_detail' %}" in rv_html
    assert "默认显示已完成领料单" in rv_html
    assert "{% if report_type in ('in_detail', 'out_detail', 'requisition_detail', 'other_out_detail') %}" in rv_html
    assert "report_type in ('in_detail', 'out_detail', 'requisition_detail', 'other_out_detail') or is_purchase_order_report" in rv_html
    assert "'in_detail', 'out_detail', 'requisition_detail', 'other_out_detail', 'purchase_order_execution'" in rv_html
    assert "['in_detail', 'out_detail', 'requisition_detail', 'other_out_detail'].includes(reportType)" in rv_html


def test_p1_2_out_order_detail_layout_controls_and_header_guards():
    """P1-2: out_order_detail title order, unified column settings, info-grid purpose/picker, inactive warehouse & busy lock."""
    html = OUT_DETAIL_HTML.read_text(encoding="utf-8")
    assert html.index("{% set out_document_label =") < html.index("{% block title %}")
    assert 'id="columnSettingsBtn"' in html
    assert 'id="columnSettingsPanel"' not in html
    assert "resize-handle" not in html
    assert "window.setupDynamicDetailColumnControls({" in html
    assert "function toggleColumnSettings()" in html  # keeps frontend_browser_report_20261103.cjs contract
    assert '<span class="info-label">用途</span>' in html
    assert "{{ order.purpose or '-' }}" in html
    assert "{{ order.picker or '-' }}" in html
    assert "（已停用，请重选）</option>" in html
    assert "alert(msg)" not in html
    assert "if (saveHeader._busy) return;" in html
    assert html.count("WMS.api.postRaw(") == 12


def test_p1_3_out_order_list_template_and_js_runtime():
    """P1-3: out_order.html balanced grid/clear/role-checkbox/party/type; out-order-list.js drag-drop & warning->force VM."""
    html = OUT_LIST_HTML.read_text(encoding="utf-8")
    assert "{% set can_batch_out = current_user.role in ['admin', 'warehouse'] %}" in html
    assert 'colspan="{{ 18 if can_batch_out else 17 }}"' in html
    assert "{{ list_base_path }}" in html
    assert "('warehouse_id', filters.warehouse_id)" in html
    assert 'width="150" class="text-nowrap"' in html
    assert "{{ item.out_order.business_type or '领料单' }}" in html
    assert "item.out_order.business_type in ['销售出库', '其他出库', '采购退货出库']" in html

    js_src = OUT_LIST_JS.read_text(encoding="utf-8")
    assert "toIndex + 1" not in js_src
    assert "setTimeout(function() { if (th) th.dataset.dragMoved = ''; }, 0);" in js_src
    assert "if (batchOutOrderAction._busy) return;" in js_src
    assert "if (singleOutOrderAction._busy) return Promise.resolve();" in js_src
    assert "data.status === 'warning'" in js_src
    assert "force=true" in js_src

    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js required")
    script = r"""
const assert = require('node:assert/strict'), vm = require('node:vm');
const src = JSON.parse(require('node:fs').readFileSync(0, 'utf8')).src;

// 1) Test drag-drop right-half of index 1 from index 0: [A, B, C] -> [B, A, C] (NOT [B, C, A])
function makeRow(tags) {
  const row = {
    children: [],
    listeners: {},
    addEventListener(n, fn) { (this.listeners[n] ||= []).push(fn); },
    insertBefore(node, ref) {
      const oldIdx = this.children.indexOf(node);
      if (oldIdx >= 0) this.children.splice(oldIdx, 1);
      if (ref == null) { this.children.push(node); return node; }
      const refIdx = this.children.indexOf(ref);
      this.children.splice(refIdx, 0, node);
      return node;
    },
  };
  tags.forEach(t => {
    row.children.push({
      tag: t, style: {}, dataset: {},
      closest(s) { return s === 'th' ? this : null; },
      getBoundingClientRect() { return { left: 100, width: 100 }; },
    });
  });
  return row;
}
const theadRow = makeRow(['A', 'B', 'C']);
const bodyRow = makeRow(['a1', 'b1', 'c1']);
const table = {
  getAttribute() { return '领料单'; },
  querySelector(s) { return s === 'thead tr' ? theadRow : null; },
  querySelectorAll(s) { return s === 'tbody tr' ? [bodyRow] : []; },
};
let domReady = null;
const posts = [], confirms = [], toasts = [], timers = [];
const ctx = {
  document: {
    addEventListener(n, fn) { if (n === 'DOMContentLoaded') domReady = fn; },
    getElementById(id) { return id === 'outOrderTable' ? table : null; },
    querySelectorAll() { return []; },
  },
  initCheckAll() {},
  setupResizableTable() {},
  location: { reload() {} },
  setTimeout(fn, ms) { timers.push({ fn, ms }); },
  showConfirm(msg, opts) { confirms.push({ msg, opts }); return Promise.resolve(true); },
  showToast(msg, type) { toasts.push({ msg, type }); },
  WMS: {
    api: {
      postRaw(url) {
        posts.push(url);
        if (url === '/out_order/9/complete') {
          return Promise.resolve({ status: 'warning', msg: '发现重复', anomalies: [{ msg: '同日已存在 OUT-1' }] });
        }
        return Promise.resolve({ status: 'success', msg: '提交成功' });
      },
    },
  },
};
ctx.window = ctx;
vm.createContext(ctx);
vm.runInContext(src, ctx);
domReady();

// Simulate drag A (index 0) onto RIGHT half of B (index 1 -> clientX=180 > mid=150)
const thA = theadRow.children[0], thB = theadRow.children[1];
theadRow.listeners.dragstart[0]({ target: thA, dataTransfer: { setData() {}, effectAllowed: '' } });
theadRow.listeners.drop[0]({ target: thB, clientX: 180, preventDefault() {} });
theadRow.listeners.dragend[0]({ target: thA });
assert.deepEqual(theadRow.children.map(x => x.tag), ['B', 'A', 'C']);
assert.deepEqual(bodyRow.children.map(x => x.tag), ['b1', 'a1', 'c1']);
assert.equal(thA.dataset.dragMoved, '1');
timers.filter(t => t.ms === 0).forEach(t => t.fn());
assert.equal(thA.dataset.dragMoved, '');

// 2) Test singleOutOrderAction warning -> confirm -> force=true
(async () => {
  await ctx.singleOutOrderAction('/out_order/9/complete', '确认完成？');
  assert.deepEqual(posts, ['/out_order/9/complete', '/out_order/9/complete?force=true']);
  assert.equal(confirms.length, 2);
  assert(confirms[1].msg.includes('同日已存在 OUT-1'));
  assert(toasts.some(t => t.type === 'success'));
})().catch(e => { process.stderr.write(e.stack); process.exitCode = 1; });
"""
    res = subprocess.run([node, "-e", script], input=json.dumps({"src": js_src}), capture_output=True, text=True, encoding="utf-8", timeout=20)
    assert res.returncode == 0, res.stdout + res.stderr


def test_p1_4_out_order_add_backend_auto_push_and_print_excel():
    """P1-4: out_order_add row builder/edit/price/switcher, backend logs/guards/excel merge, auto-push contract, print/template."""
    add_html = OUT_ADD_HTML.read_text(encoding="utf-8")
    assert "function _initOutOrderRow(row, rowIndex)" in add_html
    assert "_initOutOrderRow(newRow, currentRow.rowIndex)" in add_html
    assert "console.log(message)" not in add_html
    assert "sourcePurchaseOrderItemId" not in add_html
    assert "const matchedMaterial = findMaterialByCode(item.material_code);" in add_html
    assert "row.querySelector('.material-price').style.borderColor = '#ff4d4f'" in add_html
    assert "btSelect.addEventListener('change'" in add_html

    _, stock_err_body = _get_func(OUT_ORDER_PY, "_out_order_stock_error")
    assert "material_labels[item.material_id]" in stock_err_body

    _, add_page_body = _get_func(OUT_ORDER_PY, "out_order_add_page")
    assert "party_required=" not in add_page_body

    _, add_body = _get_func(OUT_ORDER_PY, "add_out_order")
    assert "所选部门不存在或已停用" in add_body
    assert "所选合同档案不存在" in add_body
    assert "resolve_item_contract(" in add_body

    for fn_name in ("add_out_order_item", "delete_out_order_item", "update_out_order_item", "batch_complete_out_order"):
        _, body = _get_func(OUT_ORDER_PY, fn_name)
        assert "log_operation(" in body, f"{fn_name} missing log_operation"

    _, bdel_body = _get_func(OUT_ORDER_PY, "batch_delete_out_order")
    assert "if deleted_count == 0:" in bdel_body
    assert "'deleted': 0" in bdel_body

    _, bcomp_body = _get_func(OUT_ORDER_PY, "batch_complete_out_order")
    assert "except ValueError as e:" in bcomp_body
    assert "处理失败，请稍后重试" in bcomp_body
    assert "错误: {e}" not in bcomp_body

    # _build_out_order_excel row 2 merge with box_numbers (offset=1)
    app_dir = str(ROOT / "app")
    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)
    from routes.out_order import _build_out_order_excel

    unit = SimpleNamespace(name="个")
    mat = SimpleNamespace(code="M1", brand="", name="轴承", spec="S", unit=unit)
    item = SimpleNamespace(id=7, material=mat, quantity=2, price=5, amount=10, contract_no="C1")
    order = SimpleNamespace(
        order_no="SO-1", date=date(2026, 11, 28), business_type="销售出库",
        department=None, customer="甲客户", contract_no="C1", warehouse="A仓",
        remark="", total_amount=10.0, items=[item],
    )
    wb = load_workbook(_build_out_order_excel(order, box_numbers={7: "BOX-01"}, show_price=True))
    ws = wb.active
    assert ws.cell(row=2, column=7).value == "日期：2026-11-28"
    wb.close()

    _, auto_body = _get_func(IN_COMPLETE_PY, "execute_auto_push_requisition")
    assert "contract_id=order.contract_id" in auto_body
    assert "contract_no=order.contract_no" in auto_body
    assert "project_name=order.project_name" in auto_body

    _, tpl_body = _get_func(EXPORT_PY, "export_out_order_template")
    assert "'合同编号'" in tpl_body and "'工程名称'" in tpl_body

    pe_html = PRINT_OUT_EXCEL_HTML.read_text(encoding="utf-8")
    assert "单据编号：{{ order.order_no or '' }}" in pe_html
    assert "仓库：{{ order.warehouse or '' }}" in pe_html
    assert "if (!r.ok)" in pe_html
    assert "t.has_file === false" in pe_html


def test_p1_5_ai_anomaly_warehouse_net_avg_and_completed_status():
    """P1-5: _ai_analyze_out_order_anomalies scopes 30-day avg by warehouse+materials net of revert_out and handles completed orders."""
    _, ai_body = _get_func(APP_PY, "_ai_analyze_out_order_anomalies")
    assert "StockTransaction.transaction_type.in_(('out', 'revert_out'))" in ai_body
    assert "StockTransaction.material_id.in_(item_material_ids)" in ai_body
    assert "StockTransaction.warehouse_id == wh_obj.id" in ai_body
    assert "if not is_completed and item_qty > current_stock:" in ai_body
    assert "and current_stock >= 0" not in ai_body
    assert "建议复核该已完成单据。" in ai_body


# ==================== Part B: 完整隔离 Flask + SQLite 端到端集成测试 ====================


def _setup_env():
    app_dir = str(ROOT / "app")
    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)
    import app as w

    w.app.config["TESTING"] = True
    w.app.config["WTF_CSRF_ENABLED"] = False
    with w.app.app_context():
        assert str(w.db.engine.url) == "sqlite:///:memory:"
        w.db.drop_all()
        w.db.create_all()
        from werkzeug.security import generate_password_hash

        u_wh = w.User(username="b2_wh", password_hash=generate_password_hash("Pass1234!"), role="warehouse", must_change_password=False)
        u_fin = w.User(username="b2_fin", password_hash=generate_password_hash("Pass1234!"), role="finance", must_change_password=False)
        wh_a = w.Warehouse(code="WHA", name="A仓", status="active", is_default=True)
        wh_b = w.Warehouse(code="WHB", name="B仓", status="active")
        wh_off = w.Warehouse(code="WHOFF", name="历史旧仓", status="inactive")
        unit = w.Unit(code="PCS", name="个")
        dept = w.Department(code="D01", name="机加车间", status="active")
        dept_off = w.Department(code="D02", name="已撤车间", status="inactive")
        sup = w.Supplier(code="S01", name="测试供应商")
        contract = w.Contract(contract_no="HT-B2-01", project_name="二期工程")
        w.db.session.add_all([u_wh, u_fin, wh_a, wh_b, wh_off, unit, dept, dept_off, sup, contract])
        w.db.session.flush()
        m1 = w.Material(code="B2-M1", name="深沟球轴承", spec="6204", unit_id=unit.id, price=10.0, min_stock=5.0, stock=0.0, status="active")
        m2 = w.Material(code="B2-M2", name="六角螺栓", spec="M8", unit_id=unit.id, price=2.0, min_stock=0.0, stock=0.0, status="active")
        w.db.session.add_all([m1, m2])
        w.db.session.commit()
        return w, {
            "wh_user": u_wh.id, "fin_user": u_fin.id,
            "wh_a": wh_a.id, "wh_b": wh_b.id, "wh_off": wh_off.id,
            "dept": dept.id, "dept_off": dept_off.id, "sup": sup.id,
            "contract": contract.id, "m1": m1.id, "m2": m2.id,
        }


def _client_as(w, uid: int):
    c = w.app.test_client()
    with c.session_transaction() as s:
        s["_user_id"] = str(uid)
        s["_fresh"] = True
    return c


@pytest.mark.skipif(not _IS_LINUX_ISOLATED, reason="Full Flask integration runs on isolated Linux CI")
def test_b2_integration_out_detail_parity_filters_columns_and_inactive_wh():
    w, env = _setup_env()
    today = date.today()
    with w.app.app_context():
        o1 = w.OutOrder(
            order_no="OUT-PAR-1", date=today, department_id=env["dept"], picker="王师傅",
            business_type="领料单", warehouse="A仓", location="A-01",
            contract_id=env["contract"], contract_no="HT-B2-01", project_name="二期工程",
            status="completed", operator_id=env["wh_user"], total_amount=30.0,
        )
        o2 = w.OutOrder(
            order_no="OUT-PAR-2", date=today, department_id=env["dept"], picker="李师傅",
            business_type="领料单", warehouse="A仓", location="",
            contract_no="HT-OTHER", project_name="其他项目",
            status="completed", operator_id=env["wh_user"], total_amount=4.0,
        )
        w.db.session.add_all([o1, o2])
        w.db.session.flush()
        w.db.session.add(w.OutOrderItem(out_order_id=o1.id, material_id=env["m1"], quantity=3, price=10, amount=30, contract_no="HT-B2-01", project_name="二期工程"))
        w.db.session.add(w.OutOrderItem(out_order_id=o2.id, material_id=env["m2"], quantity=2, price=2, amount=4, contract_no="HT-OTHER", project_name="其他项目"))
        w.db.session.commit()

    fin_c = _client_as(w, env["fin_user"])
    view_html = fin_c.get("/report/view/out_detail").get_data(as_text=True)
    assert "历史旧仓（已停用）" in view_html
    assert 'id="contract_no"' in view_html and 'id="project_name"' in view_html
    assert 'id="detail_material_id"' in view_html

    r_api = fin_c.get("/report/api/out_detail", query_string={
        "warehouse_id": env["wh_a"], "start_date": today.isoformat(), "end_date": today.isoformat(),
        "contract_no": "HT-B2-01", "project_name": "二期", "material_id": env["m1"],
    })
    assert r_api.status_code == 200
    body = r_api.get_json()
    assert len(body["data"]) == 1
    row = body["data"][0]
    assert row["order_no"] == "OUT-PAR-1"
    assert row["contract_no"] == "HT-B2-01"
    assert row["project_name"] == "二期工程"
    assert row["picker"] == "王师傅"
    assert row["warehouse"] == "A仓"
    assert row["location"] == "A-01"


@pytest.mark.skipif(not _IS_LINUX_ISOLATED, reason="Full Flask integration runs on isolated Linux CI")
def test_b2_integration_out_order_guards_logs_and_auto_push_contract():
    from tests.document_revision_client import document_post

    w, env = _setup_env()
    wh_c = _client_as(w, env["wh_user"])
    today = date.today().isoformat()

    # 1. Invalid contract_id and inactive non-requisition dept rejected (400, not 500)
    r_bad_c = wh_c.post("/out_order/add", json={
        "date": today, "business_type": "领料单", "warehouse_id": env["wh_a"],
        "contract_id": "not-an-int", "items": [{"code": "B2-M1", "quantity": 1, "price": 10}],
    })
    assert r_bad_c.status_code == 400
    r_bad_d = wh_c.post("/out_order/add", json={
        "date": today, "business_type": "其他出库", "warehouse_id": env["wh_a"],
        "department_id": env["dept_off"], "items": [{"code": "B2-M1", "quantity": 1, "price": 10}],
    })
    assert r_bad_d.status_code == 400

    # 2. Valid add_out_order inherits header contract onto line item; item add/update/delete write OperationLog
    r_ok = wh_c.post("/out_order/add", json={
        "date": today, "business_type": "领料单", "warehouse_id": env["wh_a"],
        "department_id": env["dept"], "contract_id": env["contract"],
        "items": [{"code": "B2-M1", "quantity": 2, "price": 10}],
    })
    assert r_ok.status_code == 200
    oid = r_ok.get_json()["id"]
    with w.app.app_context():
        order = w.db.session.get(w.OutOrder, oid)
        assert order.contract_no == "HT-B2-01"
        assert order.items[0].contract_no == "HT-B2-01"
        assert order.items[0].project_name == "二期工程"

    r_add_item = document_post(wh_c, f"/out_order/{oid}/item/add", data={"code": "B2-M2", "quantity": "3", "price": "2"})
    assert r_add_item.status_code == 200
    new_iid = r_add_item.get_json()["item_id"]
    assert document_post(wh_c, "/out_order/item/update", data={"id": str(new_iid), "quantity": "4"}).status_code == 200
    assert document_post(wh_c, f"/out_order/{oid}/delete_item/{new_iid}").status_code == 200
    with w.app.app_context():
        log_types = {l.operation_type for l in w.OperationLog.query.filter_by(target_type="out_order", target_id=oid).all()}
        assert {"添加出库明细", "编辑出库明细", "删除出库明细"}.issubset(log_types)

    # 3. batch_delete with nonexistent IDs returns 400 error (not 200 success)
    r_bdel = wh_c.post("/out_order/batch_delete", json={"ids": [999999]})
    assert r_bdel.status_code == 400 and r_bdel.get_json()["status"] == "error"

    # 4. Auto-push requisition copies header contract_id/contract_no/project_name from purchase InOrder
    with w.app.app_context():
        in_ord = w.InOrder(
            order_no="IN-AUTO-C1", date=date.today(), supplier_id=env["sup"],
            warehouse="A仓", business_type="采购入库", status="pending",
            auto_push_requisition=True, contract_id=env["contract"],
            contract_no="HT-B2-01", project_name="二期工程",
            operator_id=env["wh_user"], total_amount=20.0,
        )
        w.db.session.add(in_ord)
        w.db.session.flush()
        w.db.session.add(w.InOrderItem(in_order_id=in_ord.id, material_id=env["m1"], quantity=2, price=10, amount=20, contract_id=env["contract"], contract_no="HT-B2-01", project_name="二期工程"))
        w.db.session.commit()
        in_id = in_ord.id
    r_comp_in = document_post(wh_c, f"/in_order/{in_id}/complete")
    assert r_comp_in.status_code == 200
    with w.app.app_context():
        auto_out = w.OutOrder.query.filter_by(purpose="自动下推领料单").one()
        assert auto_out.contract_id == env["contract"]
        assert auto_out.contract_no == "HT-B2-01"
        assert auto_out.project_name == "二期工程"


@pytest.mark.skipif(not _IS_LINUX_ISOLATED, reason="Full Flask integration runs on isolated Linux CI")
def test_b2_integration_ai_anomaly_warehouse_net_avg_and_completed_no_false_overstock():
    w, env = _setup_env()
    with w.app.app_context():
        # Seed B仓 huge outbound (should NOT pollute A仓 30-day average) and A仓 out+revert_out net=30 (avg=1/day)
        now = datetime.now()
        w.db.session.add_all([
            w.StockTransaction(material_id=env["m1"], warehouse_id=env["wh_b"], transaction_type="out", quantity=-3000, created_at=now - timedelta(days=2)),
            w.StockTransaction(material_id=env["m1"], warehouse_id=env["wh_a"], transaction_type="out", quantity=-60, created_at=now - timedelta(days=2)),
            w.StockTransaction(material_id=env["m1"], warehouse_id=env["wh_a"], transaction_type="revert_out", quantity=30, created_at=now - timedelta(days=1)),
        ])
        completed_out = w.OutOrder(
            order_no="OUT-AI-DONE", date=date.today(), department_id=env["dept"],
            warehouse="A仓", business_type="领料单", status="completed",
            operator_id=env["wh_user"], total_amount=50.0,
        )
        pending_out = w.OutOrder(
            order_no="OUT-AI-PEND", date=date.today(), department_id=env["dept"],
            warehouse="A仓", business_type="领料单", status="pending",
            operator_id=env["wh_user"], total_amount=50.0,
        )
        w.db.session.add_all([completed_out, pending_out])
        w.db.session.flush()
        # qty=5 > A仓 net avg(1.0)*3=3.0 (caught!), while B仓 avg would have been 100/day (would have missed!)
        w.db.session.add(w.OutOrderItem(out_order_id=completed_out.id, material_id=env["m1"], quantity=5, price=10, amount=50))
        w.db.session.add(w.OutOrderItem(out_order_id=pending_out.id, material_id=env["m1"], quantity=5, price=10, amount=50))
        w.db.session.commit()
        done_id, pend_id = completed_out.id, pending_out.id

    wh_c = _client_as(w, env["wh_user"])
    res_done = wh_c.get(f"/api/ai/out_order/{done_id}/anomaly_analysis").get_json()["data"]
    done_types = [a["anomaly_type"] for a in res_done["anomalies"]]
    assert "超库存出库" not in done_types, "completed order must not false-alarm overstock"
    assert "数量异常偏大" in done_types, "warehouse-scoped net avg must trigger anomaly"
    assert "建议复核该已完成单据。" in res_done["summary"]

    res_pend = wh_c.get(f"/api/ai/out_order/{pend_id}/anomaly_analysis").get_json()["data"]
    pend_types = [a["anomaly_type"] for a in res_pend["anomalies"]]
    assert "超库存出库" in pend_types, "pending order with negative current_stock (-30) must catch overstock"
