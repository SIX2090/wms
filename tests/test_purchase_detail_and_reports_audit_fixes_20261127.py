# -*- coding: utf-8 -*-
"""BUG-2026-11-27-007 回归测试：采购入库详情与采购入库报表全面审计 18 项问题及同类点修复。

Part A（纯 AST / 模板 / Node-VM，本地 Windows 与 Linux CI 均执行，支持 R8 文件备份回退验证）：
- P0-D1 / P0-R1 + R6：详情/打印/模板（in_order + out_order）与报表全部路由 @require_role 门禁，
  以及 in_order_detail.html / out_order_detail.html 前后端读写权限对齐
- P0-D2 + R6 + 深度后端缺陷：行内增删改写锁、add_in_order_item 拦已关/取消采购单、
  batch_add_in_order_items 捕获 .xls 异常并预加载物料、copy_in_order_to_out 校验、
  complete_in_order 超收复核、delete/revert 锁后重验活跃下推、download_*_print_template 404 修正
- P0-R2 / P1-R3 / P1-R4 / P1-R5 / P2-3 / P2-4 / P2-5：采购 4 表 warehouse_id=0 公司口径、
  采购退货净实收与已退货数量列、同日最新价 MAX、跨单位数量与供应商均价防护、
  price_dimension_enabled 控制、Excel 中文表名与公式清洗、批量导出跳过重复聚合与停用历史仓
- P1-D3 / P1-D4 / P1-D5 / P1-R6 / P1-R7 / P2-1：详情/打印价格维度、#editHeaderModal 往来切换与防重、
  工具栏去噪与移除双列宽拖拽柄、purchase_report 分区与 report_view 导航/排序/401 防护、
  ExcelTable 走 WMS.api.postRaw + 文本格 Ctrl+V + 顶部总金额联动
- P1-D6 + R6：_load_in_order_for_print / _load_out_order_for_print 预加载与按物料 ID 范围查仓库库存

Part B（完整 Flask + SQLite 端到端集成测试，于隔离 Linux CI 运行）。
"""
from __future__ import annotations

import ast
import io
import json
import os
import shutil
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_PY = ROOT / "app" / "app.py"
IN_ORDER_PY = ROOT / "app" / "routes" / "in_order.py"
OUT_ORDER_PY = ROOT / "app" / "routes" / "out_order.py"
REPORT_PY = ROOT / "app" / "routes" / "report.py"
IN_DETAIL_HTML = ROOT / "app" / "templates" / "in_order_detail.html"
OUT_DETAIL_HTML = ROOT / "app" / "templates" / "out_order_detail.html"
PRINT_IN_HTML = ROOT / "app" / "templates" / "print_in.html"
PURCHASE_REPORT_HTML = ROOT / "app" / "templates" / "purchase_report.html"
REPORT_VIEW_HTML = ROOT / "app" / "templates" / "report_view.html"
EXCEL_TABLE_JS = ROOT / "app" / "static" / "js" / "excel-table.js"
EXCEL_IE_JS = ROOT / "app" / "static" / "js" / "excel-import-export.js"
APP_JS = ROOT / "app" / "static" / "js" / "app.js"

_IS_LINUX_ISOLATED = sys.platform.startswith("linux") or os.environ.get("WMS_RUN_FULL_INTEGRATION") == "1"


def _get_func(path: Path, name: str) -> tuple[ast.FunctionDef, str]:
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            lines = src.splitlines()
            body = "\n".join(lines[node.lineno - 1 : node.end_lineno])
            return node, body
    raise AssertionError(f"Function {name} not found in {path}")


def _decorator_calls(func: ast.FunctionDef) -> list[str]:
    return [ast.unparse(dec) for dec in func.decorator_list]


# ==================== Part A: 纯静态 / AST / Node-VM 回归 ====================


def test_p0_d1_r1_rbac_and_template_role_gating_ast():
    """P0-D1 / P0-R1 + R6: detail, print, template, and report routes require proper roles; UI matches RBAC."""
    for fn_name in (
        "in_order_detail",
        "preview_in_order_template",
        "print_in_order_with_template",
        "print_in_order_excel",
        "in_order_print_templates_json",
        "download_in_order_print_template",
        "print_in_order_direct",
        "print_in_order_labels",
    ):
        fn, _ = _get_func(IN_ORDER_PY, fn_name)
        decs = _decorator_calls(fn)
        assert any("require_role(" in d for d in decs), f"{fn_name} missing @require_role"

    in_tpl_fn, _ = _get_func(IN_ORDER_PY, "in_order_print_template_list")
    assert any("require_role('admin')" in d for d in _decorator_calls(in_tpl_fn))

    # R6 sibling: out_order detail/print/template routes
    for fn_name in (
        "out_order_detail",
        "preview_out_order_template",
        "print_out_order_with_template",
        "print_out_order_excel",
        "out_order_print_templates_json",
        "download_out_order_print_template",
    ):
        fn, _ = _get_func(OUT_ORDER_PY, fn_name)
        assert any("require_role(" in d for d in _decorator_calls(fn)), f"{fn_name} missing @require_role"

    out_tpl_fn, _ = _get_func(OUT_ORDER_PY, "out_order_print_template_list")
    assert any("require_role('admin')" in d for d in _decorator_calls(out_tpl_fn))

    # Report routes RBAC
    for fn_name in (
        "report",
        "purchase_report",
        "report_dashboard",
        "report_view",
        "report_api_query",
        "report_print_not_implemented",
        "report_print_excel",
        "report_print_preview",
        "report_inout_print",
        "report_inout_export",
        "report_stock_print",
        "report_stock_print_preview",
    ):
        fn, _ = _get_func(REPORT_PY, fn_name)
        assert any("require_role(" in d for d in _decorator_calls(fn)), f"{fn_name} missing @require_role"

    for fn_name in ("report_view", "report_api_query", "report_print_excel", "report_print_preview"):
        _, body = _get_func(REPORT_PY, fn_name)
        assert "_deny_purchase_report_access(" in body, f"{fn_name} must enforce purchase report role check"

    # A9 anchor: verify _deny_purchase_report_access helper behavior directly
    _, helper_src = _get_func(REPORT_PY, "_deny_purchase_report_access")
    fake_user = type("U", (), {"role": "sales"})()
    flashed = []
    ns = {
        "_PURCHASE_ONLY_REPORTS": {
            "purchase_order_execution",
            "supplier_purchase_summary",
            "material_purchase_summary",
            "purchase_price_analysis",
        },
        "_PURCHASE_REPORT_ALLOWED_ROLES": {"admin", "warehouse", "finance", "purchase"},
        "current_user": fake_user,
        "jsonify": lambda payload: payload,
        "flash": lambda msg, cat="info": flashed.append((msg, cat)),
        "redirect": lambda target: ("redirect", target),
        "url_for": lambda ep: f"/{ep}",
    }
    exec(compile(helper_src, str(REPORT_PY), "exec"), ns)
    deny_fn = ns["_deny_purchase_report_access"]
    denied_json = deny_fn("purchase_order_execution", as_json=True)
    assert denied_json[1] == 403 and denied_json[0]["status"] == "error"
    assert deny_fn("purchase_order_execution", as_json=False) == ("redirect", "/index")
    assert flashed and flashed[-1][1] == "danger"
    assert deny_fn("in_detail", as_json=True) is None
    fake_user.role = "finance"
    assert deny_fn("purchase_order_execution", as_json=True) is None

    # Detail template role gating: Print/Back visible to read-only viewers, write controls gated on editable_pending/editable_lines
    in_html = IN_DETAIL_HTML.read_text(encoding="utf-8")
    assert "{% set can_edit_in = (current_user is not defined) or (current_user.role in ['admin', 'warehouse']) %}" in in_html
    assert "{% set editable_pending = order.status == 'pending' and can_edit_in %}" in in_html
    assert "{% if editable_pending %}" in in_html
    assert "{% if editable_pending %} editable-cell{% endif %}" in in_html
    assert "editable: function() { return {{ (order.status == 'pending' and ((current_user is not defined) or (current_user.role in ['admin', 'warehouse'])))|tojson }}; }" in in_html

    out_html = OUT_DETAIL_HTML.read_text(encoding="utf-8")
    assert "{% set can_edit_out = (current_user is not defined) or (current_user.role in ['admin', 'warehouse']) %}" in out_html
    assert "{% set editable_lines = order.status == 'pending' and not push_source and can_edit_out %}" in out_html


def test_p0_d2_locks_copy_to_out_and_backend_guards_ast():
    """P0-D2 + R6 + deep backend audit fixes: write locks, closed PO guard, .xls guard, copy_to_out, 404 tuple fix."""
    for fn_name in ("add_in_order_item", "batch_add_in_order_items", "delete_in_order_item", "update_in_order_item"):
        _, body = _get_func(IN_ORDER_PY, fn_name)
        assert "_acquire_order_write_lock(" in body, f"{fn_name} missing write lock"

    for fn_name in ("add_out_order_item", "delete_out_order_item", "update_out_order_item"):
        _, body = _get_func(OUT_ORDER_PY, fn_name)
        assert "_acquire_order_write_lock(" in body, f"{fn_name} missing write lock"

    _, add_item_body = _get_func(IN_ORDER_PY, "add_in_order_item")
    assert "('closed', 'cancelled')" in add_item_body
    assert "len(box_no) > 100" in add_item_body and "len(remark) > 500" in add_item_body

    _, batch_add_body = _get_func(IN_ORDER_PY, "batch_add_in_order_items")
    assert "InvalidFileException" in batch_add_body and "zipfile.BadZipFile" in batch_add_body
    assert "Material.code.in_(" in batch_add_body

    _, complete_body = _get_func(IN_ORDER_PY, "complete_in_order")
    assert "check_purchase_over_receive_for_order(order)" in complete_body

    for fn_name in ("delete_in_order", "revert_in_order"):
        _, body = _get_func(IN_ORDER_PY, fn_name)
        lock_pos = body.index("_acquire_order_write_lock(")
        assert "_source_has_active_push(order.id)" in body[lock_pos:], f"{fn_name} must re-check active push after write lock"

    _, dl_in_body = _get_func(IN_ORDER_PY, "download_in_order_print_template")
    assert "api_error('打印模板缺少 Excel 文件', 404)" in dl_in_body
    assert "api_error('打印模板文件不存在', 404)" in dl_in_body
    assert "), 404" not in dl_in_body

    _, dl_out_body = _get_func(OUT_ORDER_PY, "download_out_order_print_template")
    assert "), 404" not in dl_out_body

    _, direct_body = _get_func(IN_ORDER_PY, "print_in_order_direct")
    assert "sales_return_sources=_in_order_sales_sources(order)" in direct_body

    _, copy_out_body = _get_func(IN_ORDER_PY, "copy_in_order_to_out")
    assert "is_customer_supplied" in copy_out_body
    assert "inactive" in copy_out_body and "getattr(item.material, 'status'" in copy_out_body
    assert "recalculate_order_total(out_order)" in copy_out_body
    assert "customer=in_order.supplier.name" not in copy_out_body


def test_p0_r2_p1_r3_r4_r5_p2_reports_backend_ast():
    """P0-R2 / P1-R3 / P1-R4 / P1-R5 / P2-3 / P2-4 / P2-5: purchase report scope, returns, MAX price, units, excel."""
    _, filters_body = _get_func(APP_PY, "_build_report_filters")
    assert "_PURCHASE_ORDER_REPORT_TYPES" in filters_body and "all_warehouses" in filters_body
    assert "web_print" in filters_body

    _, po_query_body = _get_func(APP_PY, "_purchase_order_item_query")
    assert "not filters.get('all_warehouses')" in po_query_body

    _, receipts_body = _get_func(APP_PY, "_purchase_completed_receipts_subquery")
    assert "deduct_returns=False" in receipts_body
    assert "'采购退货出库'" in receipts_body
    assert "source_in_order_item_id" in receipts_body

    _, exec_cols_body = _get_func(APP_PY, "_purchase_order_execution_columns")
    assert "'returned_quantity'" in exec_cols_body
    _, sup_cols_body = _get_func(APP_PY, "_supplier_purchase_summary_columns")
    assert "'returned_quantity'" not in sup_cols_body
    _, mat_cols_body = _get_func(APP_PY, "_material_purchase_summary_columns")
    assert "'returned_quantity'" not in mat_cols_body

    for fn_name in (
        "_sql_paged_purchase_execution_report",
        "_sql_paged_supplier_purchase_report",
        "_sql_paged_material_purchase_report",
        "_sql_paged_purchase_price_analysis_report",
    ):
        _, body = _get_func(APP_PY, fn_name)
        assert "filters.get('all_warehouses')" in body, f"{fn_name} must support all_warehouses=True"

    sup_sql_node, sup_sql_body = _get_func(APP_PY, "_sql_paged_supplier_purchase_report")
    assert "Supplier.query.all()" not in ast.unparse(sup_sql_node)
    assert "Supplier.name.in_(" in sup_sql_body
    assert "unit_count" in sup_sql_body and "None if mixed_units" in sup_sql_body

    _, price_mem_body = _get_func(APP_PY, "_build_purchase_price_analysis_report")
    assert "row_date > bucket['last_purchase_date']" in price_mem_body
    assert "row_date >= bucket['last_purchase_date']" not in price_mem_body

    _, price_sql_body = _get_func(APP_PY, "_sql_paged_purchase_price_analysis_report")
    assert "func.max(sub.c.order_no)" in price_sql_body
    assert "func.max(sub.c.item_id)" in price_sql_body
    assert "func.min(sub.c.order_no)" not in price_sql_body

    # A9 anchor: directly exercise _apply_mixed_unit_summary
    _, mixed_src = _get_func(APP_PY, "_apply_mixed_unit_summary")
    sys.path.insert(0, str(ROOT / "app"))
    try:
        ns: dict = {}
        exec(compile(mixed_src, str(APP_PY), "exec"), ns)
        fn = ns["_apply_mixed_unit_summary"]
        s_single = fn({"count": 2, "quantity": 10.0, "amount": 100.0}, {"个": 10.0})
        assert s_single == {"count": 2, "quantity": 10.0, "amount": 100.0}
        s_mixed = fn({"count": 2, "quantity": 15.0, "amount": 100.0}, {"个": 10.0, "箱": 5.0})
        assert s_mixed["quantity"] is None
        assert "10 个" in s_mixed["quantity_text"] and "5 箱" in s_mixed["quantity_text"]
    finally:
        if str(ROOT / "app") in sys.path:
            sys.path.remove(str(ROOT / "app"))

    _, xl_body = _get_func(APP_PY, "_build_report_excel_download")
    assert "hcell.data_type = 's'" in xl_body and "cell.data_type = 's'" in xl_body
    assert "ws.title = 'Report'" not in xl_body
    assert "not filters.get('include_prices', True)" in xl_body

    _, iter_body = _get_func(APP_PY, "_iter_report_export_batches")
    assert "_skip_summary" in iter_body and "_known_total" in iter_body

    _, report_view_body = _get_func(REPORT_PY, "report_view")
    assert "_PURCHASE_ONLY_REPORTS" in report_view_body

    _, inout_print_body = _get_func(REPORT_PY, "report_inout_print")
    assert "joinedload(InOrder.customer)" in inout_print_body


def test_p1_d3_d4_d5_r6_r7_templates_and_excel_table_runtime():
    """Templates (detail/print/purchase_report/report_view) + ExcelTable Node-VM runtime behavior."""
    in_html = IN_DETAIL_HTML.read_text(encoding="utf-8")
    assert 'id="detailHeaderTotalAmount"' in in_html
    assert 'id="editSupplierField"' in in_html and 'id="editCustomerField"' in in_html
    assert "function syncEditHeaderParty()" in in_html
    assert "saveHeader._busy" in in_html
    assert "resize-handle" not in in_html and "let isResizing" not in in_html
    assert "show_batch_col" in in_html
    assert "console.error('保存失败:'" not in in_html

    out_html = OUT_DETAIL_HTML.read_text(encoding="utf-8")
    assert 'id="detailHeaderTotalAmount"' in out_html
    assert "console.error('保存失败:'" not in out_html

    print_html = PRINT_IN_HTML.read_text(encoding="utf-8")
    assert "price-col-hidden" in print_html and "数量合计：" in print_html
    assert "item.material.code if item.material else '-'" in print_html

    pr_html = PURCHASE_REPORT_HTML.read_text(encoding="utf-8")
    assert "把采购报表放回采购管理模块" not in pr_html
    assert "purchase-gap-table" not in pr_html and "priority-badge" not in pr_html
    assert "{% block extra_css %}" in pr_html
    assert "核心采购报表" in pr_html and "关联单据与档案" in pr_html

    rv_html = REPORT_VIEW_HTML.read_text(encoding="utf-8")
    assert '<option value="0" selected>全部仓库（含未入库在途订单）</option>' in rv_html
    assert "返回采购报表" in rv_html
    assert "th.dataset.sortActive = '1';" in rv_html
    assert "currentPage = 1;" in rv_html
    assert "登录状态已失效，请刷新页面重新登录" in rv_html
    assert "'purchase_order_execution', 'supplier_purchase_summary', 'material_purchase_summary', 'purchase_price_analysis'" in rv_html

    ie_js = EXCEL_IE_JS.read_text(encoding="utf-8")
    assert '#cbGlobalActionBar [data-wms-action="export"]' in ie_js
    app_js = APP_JS.read_text(encoding="utf-8")
    assert "pageHasOwnButton(['导出Excel', '导出 Excel', '导出'], bar)" in app_js

    # Node-VM runtime verification for excel-table.js (P1-R7)
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js required for excel-table runtime checks")
    script = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const src = fs.readFileSync(process.argv[1], 'utf8');

let postRawCalls = [];
let headerAmountEl = { textContent: '¥0.00' };
let startedEdits = [];
let errors = [];
let keydownHandler = null;
const qtyCell = { dataset: { field: 'quantity', value: '3' } };
const priceCell = { dataset: { field: 'price', value: '12.5' } };
const tfootQty = { textContent: '' };
const tfootAmt = { textContent: '' };
const fakeRow = {
    querySelector(sel) {
        if (sel === '[data-field="quantity"]') return qtyCell;
        if (sel === '[data-field="price"]') return priceCell;
        return null;
    }
};
const fakeTable = {
    addEventListener(evt, fn) { if (evt === 'keydown') keydownHandler = fn; },
    removeEventListener() {},
    contains() { return true; },
    querySelector(sel) {
        if (sel === 'tbody') return { querySelectorAll() { return [fakeRow]; } };
        if (sel === 'tfoot') return {
            querySelectorAll(s) { return s === '[data-total]' ? [tfootQty, tfootAmt] : []; },
            querySelector(s) {
                if (s === '[data-total="quantity"]') return tfootQty;
                if (s === '[data-total="amount"]') return tfootAmt;
                return null;
            }
        };
        return null;
    },
    querySelectorAll() { return []; },
};
let clipboardText = '';
const ctx = vm.createContext({
    console,
    parseFloat,
    isNaN,
    Number,
    String,
    Array,
    Map,
    Set,
    Promise,
    Error,
    window: {
        WMS: {
            api: {
                postRaw(url, body) {
                    postRawCalls.push({ url, body });
                    return Promise.resolve({ status: 'success' });
                }
            }
        },
        WMSMoney: { product(a, b) { return Math.round(a * b * 100) / 100; } },
        prompt() {},
    },
    document: {
        getElementById(id) {
            if (id === 'itemTable') return fakeTable;
            if (id === 'detailHeaderTotalAmount') return headerAmountEl;
            return null;
        },
        addEventListener() {},
        removeEventListener() {},
    },
    navigator: {
        clipboard: {
            readText() { return Promise.resolve(clipboardText); },
            writeText() { return Promise.resolve(); },
        }
    },
    showToast(msg, type) { if (type === 'danger') errors.push(msg); },
});
vm.runInContext(src + '\nthis.ExcelTable = ExcelTable;', ctx);
const table = new ctx.ExcelTable('itemTable', { enableKeyboard: false, enableCopyPaste: true });
table.startEdit = (cell, val) => startedEdits.push({ field: cell.dataset.field, val });

(async () => {
    // 1. defaultSave routes via WMS.api.postRaw
    const res = await table.defaultSave({ item_id: 1 });
    assert.equal(res.status, 'success');
    assert.equal(postRawCalls.length, 1);
    assert.equal(postRawCalls[0].url, '/in_order/item/update');

    // 2. updateTotal syncs header total amount
    table.updateTotal();
    assert.equal(tfootQty.textContent, '3.00');
    assert.equal(tfootAmt.textContent, '¥37.50');
    assert.equal(headerAmountEl.textContent, '¥37.50');

    // 3. Ctrl+V on remark allows Chinese text; box_no allows alphanumeric code; quantity rejects text
    clipboardText = '急用备件，请先检';
    table.currentCell = { dataset: { field: 'remark' } };
    await keydownHandler({ ctrlKey: true, key: 'v', preventDefault() {} });
    assert.equal(startedEdits.length, 1);
    assert.equal(startedEdits[0].field, 'remark');
    assert.equal(startedEdits[0].val, '急用备件，请先检');

    clipboardText = 'BOX-001-A';
    table.currentCell = { dataset: { field: 'box_no' } };
    await keydownHandler({ ctrlKey: true, key: 'v', preventDefault() {} });
    assert.equal(startedEdits.length, 2);
    assert.equal(startedEdits[1].val, 'BOX-001-A');

    clipboardText = '非数字';
    table.currentCell = { dataset: { field: 'quantity' } };
    await keydownHandler({ ctrlKey: true, key: 'v', preventDefault() {} });
    assert.equal(startedEdits.length, 2);
    assert.ok(errors.includes('粘贴内容无效'));
})().catch(err => { console.error(err); process.exit(1); });
"""
    res = subprocess.run([node, "-e", script, str(EXCEL_TABLE_JS)], capture_output=True, text=True, encoding="utf-8", timeout=15)
    assert res.returncode == 0, res.stderr


def test_p1_d6_eager_loading_and_scoped_warehouse_stock_ast():
    """P1-D6 + R6: detail/print eager loading helpers and material_ids scoped warehouse stock lookup."""
    # A9 anchors for _load_in_order_for_print & _load_out_order_for_print
    _, load_in_body = _get_func(IN_ORDER_PY, "_load_in_order_for_print")
    assert "joinedload(InOrder.operator)" in load_in_body and "selectinload(InOrder.items)" in load_in_body

    _, load_out_body = _get_func(OUT_ORDER_PY, "_load_out_order_for_print")
    assert "joinedload(OutOrder.operator)" in load_out_body and "selectinload(OutOrder.items)" in load_out_body

    for fn_name in ("preview_in_order_template", "_render_in_order_print", "print_in_order_excel", "print_in_order_direct"):
        _, body = _get_func(IN_ORDER_PY, fn_name)
        assert "_load_in_order_for_print(" in body, f"{fn_name} must use _load_in_order_for_print"

    for fn_name in ("preview_out_order_template", "_render_out_order_print", "print_out_order_excel"):
        _, body = _get_func(OUT_ORDER_PY, fn_name)
        assert "_load_out_order_for_print(" in body, f"{fn_name} must use _load_out_order_for_print"

    _, in_detail_body = _get_func(IN_ORDER_PY, "in_order_detail")
    assert "joinedload(InOrder.operator)" in in_detail_body
    assert "material_ids=item_material_ids" in in_detail_body
    assert "if can_edit_header else []" in in_detail_body

    _, out_detail_body = _get_func(OUT_ORDER_PY, "out_order_detail")
    assert "joinedload(OutOrder.operator)" in out_detail_body
    assert "material_ids=item_material_ids" in out_detail_body

    _, stock_fn_body = _get_func(APP_PY, "get_warehouse_stock_quantities_for_materials")
    assert "material_ids=None" in stock_fn_body
    # A9 anchor: exercise get_warehouse_stock_quantities_for_materials empty/None early returns
    ns_stock = {}
    exec(compile(stock_fn_body, str(APP_PY), "exec"), ns_stock)
    get_warehouse_stock_quantities_for_materials = ns_stock["get_warehouse_stock_quantities_for_materials"]
    assert get_warehouse_stock_quantities_for_materials(None) == {}
    assert get_warehouse_stock_quantities_for_materials(object(), material_ids=[]) == {}


def test_get_warehouse_stock_quantities_for_materials():
    """A9 dedicated test for get_warehouse_stock_quantities_for_materials boundary behavior."""
    _, stock_fn_body = _get_func(APP_PY, "get_warehouse_stock_quantities_for_materials")
    assert "material_ids=None" in stock_fn_body
    ns_stock = {}
    exec(compile(stock_fn_body, str(APP_PY), "exec"), ns_stock)
    fn = ns_stock["get_warehouse_stock_quantities_for_materials"]
    assert fn(None) == {}
    assert fn(object(), material_ids=[]) == {}
    assert fn(object(), material_ids=[None]) == {}


# ==================== Part B: 完整隔离 Flask + SQLite 端到端回归 ====================


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

        users = {}
        for role in ("admin", "warehouse", "finance", "purchase", "sales", "viewer", "user"):
            u = w.User(
                username=f"u_{role}",
                password_hash=generate_password_hash("Pass1234!"),
                role=role,
                must_change_password=False,
            )
            w.db.session.add(u)
            users[role] = u
        wh_a = w.Warehouse(code="WHA", name="A仓", status="active", is_default=True)
        wh_b = w.Warehouse(code="WHB", name="B仓", status="active")
        unit_pcs = w.Unit(code="PCS", name="个")
        unit_box = w.Unit(code="BOX", name="箱")
        sup = w.Supplier(code="SUP1", name="鑫达五金")
        w.db.session.add_all([wh_a, wh_b, unit_pcs, unit_box, sup])
        w.db.session.flush()
        m1 = w.Material(code="M001", name="轴承", unit_id=unit_pcs.id, price=10.0, stock=0.0, status="active")
        m2 = w.Material(code="M002", name="箱装螺母", unit_id=unit_box.id, price=50.0, stock=0.0, status="active")
        m_inactive = w.Material(code="M_OFF", name="停用物料", unit_id=unit_pcs.id, price=5.0, stock=0.0, status="inactive")
        w.db.session.add_all([m1, m2, m_inactive])
        w.db.session.commit()
        return w, {
            "user_ids": {role: u.id for role, u in users.items()},
            "wh_a_id": wh_a.id,
            "wh_b_id": wh_b.id,
            "sup_id": sup.id,
            "m1_id": m1.id,
            "m2_id": m2.id,
            "m_inactive_id": m_inactive.id,
        }


def _client_as(w, user_id: int):
    c = w.app.test_client()
    with c.session_transaction() as sess:
        sess["_user_id"] = str(user_id)
        sess["_fresh"] = True
    return c


@pytest.mark.skipif(not _IS_LINUX_ISOLATED, reason="Full Flask integration runs on isolated Linux CI")
def test_integration_rbac_blocks_viewer_and_user_allows_authorized_roles():
    w, env = _setup_env()
    with w.app.app_context():
        io_doc = w.InOrder(
            order_no="IN261127001",
            date=date.today(),
            supplier_id=env["sup_id"],
            warehouse="A仓",
            business_type="采购入库",
            status="pending",
            operator_id=env["user_ids"]["warehouse"],
            total_amount=100.0,
        )
        w.db.session.add(io_doc)
        w.db.session.flush()
        w.db.session.add(w.InOrderItem(in_order_id=io_doc.id, material_id=env["m1_id"], quantity=10.0, price=10.0, amount=100.0))
        oo_doc = w.OutOrder(
            order_no="OUT261127001",
            date=date.today(),
            warehouse="A仓",
            business_type="领料单",
            status="pending",
            operator_id=env["user_ids"]["warehouse"],
            total_amount=20.0,
        )
        w.db.session.add(oo_doc)
        w.db.session.flush()
        w.db.session.add(w.OutOrderItem(out_order_id=oo_doc.id, material_id=env["m1_id"], quantity=2.0, price=10.0, amount=20.0))
        w.db.session.commit()
        in_id, out_id = io_doc.id, oo_doc.id

    json_hdr = {"Accept": "application/json"}
    for role in ("viewer", "user"):
        c = _client_as(w, env["user_ids"][role])
        assert c.get(f"/in_order/{in_id}").status_code == 302
        assert c.get(f"/in_order/{in_id}/print_excel", headers=json_hdr).status_code == 403
        assert c.get("/in_order_print_template").status_code == 302
        assert c.get(f"/out_order/{out_id}").status_code == 302
        assert c.get("/purchase_report").status_code == 302
        assert c.get(f"/report/api/in_detail?warehouse_id={env['wh_a_id']}", headers=json_hdr).status_code == 403
        assert c.get("/report/api/purchase_order_execution?warehouse_id=0", headers=json_hdr).status_code == 403
        assert c.get(f"/report/inout/export?warehouse_id={env['wh_a_id']}", headers=json_hdr).status_code == 403

    # sales cannot access purchase-only reports
    c_sales = _client_as(w, env["user_ids"]["sales"])
    assert c_sales.get("/purchase_report").status_code == 302
    assert c_sales.get("/report/api/purchase_order_execution?warehouse_id=0").status_code == 403

    # finance can view detail (sees Print & Back, NO write actions / editable-cell) and purchase reports, but not admin templates
    c_fin = _client_as(w, env["user_ids"]["finance"])
    r_detail = c_fin.get(f"/in_order/{in_id}")
    assert r_detail.status_code == 200
    html = r_detail.get_data(as_text=True)
    assert "返回" in html and "栏目设置" in html
    assert 'data-document-action="completeOrder"' not in html and 'id="batchDeleteBtn"' not in html
    assert 'id="editHeaderModal"' not in html and 'class="editable-cell"' not in html
    assert c_fin.get("/in_order_print_template").status_code == 302
    assert c_fin.get("/purchase_report").status_code == 200
    assert c_fin.get("/report/api/purchase_order_execution?warehouse_id=0").status_code == 200


@pytest.mark.skipif(not _IS_LINUX_ISOLATED, reason="Full Flask integration runs on isolated Linux CI")
def test_integration_purchase_reports_all_warehouses_returns_and_price_dim():
    from openpyxl import load_workbook

    w, env = _setup_env()
    with w.app.app_context():
        today = date.today()
        # 1. Unreceived overdue PO (no InOrder at all!)
        po_unrec = w.PurchaseOrder(
            order_no="PO-UNREC-01",
            date=today - timedelta(days=10),
            expected_date=today - timedelta(days=5),
            supplier_id=env["sup_id"],
            status="pending",
            operator_id=env["user_ids"]["warehouse"],
            total_amount=500.0,
        )
        w.db.session.add(po_unrec)
        w.db.session.flush()
        w.db.session.add(
            w.PurchaseOrderItem(
                purchase_order_id=po_unrec.id,
                material_id=env["m2_id"],
                quantity=10.0,
                received_quantity=0.0,
                price=50.0,
                amount=500.0,
                remark="=SUM(A1:A2)",
            )
        )

        # 2. Split-warehouse PO: ordered 10 (m1, unit 个), received 4 in A仓 + 6 in B仓, returned 2 in A仓
        po_split = w.PurchaseOrder(
            order_no="PO-SPLIT-01",
            date=today,
            expected_date=today + timedelta(days=5),
            supplier_id=env["sup_id"],
            status="partial",
            operator_id=env["user_ids"]["warehouse"],
            total_amount=100.0,
        )
        w.db.session.add(po_split)
        w.db.session.flush()
        po_split_item = w.PurchaseOrderItem(
            purchase_order_id=po_split.id,
            material_id=env["m1_id"],
            quantity=10.0,
            received_quantity=10.0,
            price=10.0,
            amount=100.0,
        )
        w.db.session.add(po_split_item)
        w.db.session.flush()

        in_a = w.InOrder(
            order_no="IN-A-1",
            date=today,
            supplier_id=env["sup_id"],
            warehouse="A仓",
            business_type="采购入库",
            status="completed",
            source_purchase_order_id=po_split.id,
            operator_id=env["user_ids"]["warehouse"],
            total_amount=40.0,
        )
        in_b = w.InOrder(
            order_no="IN-B-1",
            date=today,
            supplier_id=env["sup_id"],
            warehouse="B仓",
            business_type="采购入库",
            status="completed",
            source_purchase_order_id=po_split.id,
            operator_id=env["user_ids"]["warehouse"],
            total_amount=60.0,
        )
        w.db.session.add_all([in_a, in_b])
        w.db.session.flush()
        in_a_item = w.InOrderItem(
            in_order_id=in_a.id,
            material_id=env["m1_id"],
            source_purchase_order_item_id=po_split_item.id,
            quantity=4.0,
            price=10.0,
            amount=40.0,
        )
        in_b_item = w.InOrderItem(
            in_order_id=in_b.id,
            material_id=env["m1_id"],
            source_purchase_order_item_id=po_split_item.id,
            quantity=6.0,
            price=10.0,
            amount=60.0,
        )
        w.db.session.add_all([in_a_item, in_b_item])
        w.db.session.flush()

        # Completed purchase return of 2 from in_a_item
        ret_out = w.OutOrder(
            order_no="PR-A-1",
            date=today,
            warehouse="A仓",
            business_type="采购退货出库",
            status="completed",
            source_in_order_id=in_a.id,
            operator_id=env["user_ids"]["warehouse"],
            total_amount=20.0,
        )
        w.db.session.add(ret_out)
        w.db.session.flush()
        w.db.session.add(
            w.OutOrderItem(
                out_order_id=ret_out.id,
                material_id=env["m1_id"],
                source_in_order_item_id=in_a_item.id,
                quantity=2.0,
                price=10.0,
                amount=20.0,
            )
        )
        w.db.session.commit()
        in_a_id = in_a.id

    c = _client_as(w, env["user_ids"]["admin"])
    # Default price_dimension_enabled=0
    r_exec = c.get("/report/api/purchase_order_execution?warehouse_id=0")
    assert r_exec.status_code == 200
    payload = r_exec.get_json()
    assert payload["total"] == 2
    by_no = {row["order_no"]: row for row in payload["data"]}
    assert "PO-UNREC-01" in by_no and by_no["PO-UNREC-01"]["overdue_days"] >= 5
    assert by_no["PO-SPLIT-01"]["order_quantity"] == 10.0
    assert by_no["PO-SPLIT-01"]["received_quantity"] == 8.0
    assert by_no["PO-SPLIT-01"]["returned_quantity"] == 2.0
    assert by_no["PO-SPLIT-01"]["remaining_quantity"] == 2.0
    # Mixed units (个 + 箱): summary.quantity is None with quantity_text
    assert payload["summary"]["quantity"] is None
    assert "10 个" in payload["summary"]["quantity_text"] and "10 箱" in payload["summary"]["quantity_text"]
    # Price dimension disabled hides money columns
    assert all(col.get("type") != "money" for col in payload["columns"])

    # Supplier summary: mixed units -> avg_price is None, net received=8
    r_sup = c.get("/report/api/supplier_purchase_summary?warehouse_id=0")
    assert r_sup.status_code == 200
    sup_data = r_sup.get_json()
    assert sup_data["total"] == 1
    assert sup_data["data"][0]["received_quantity"] == 8.0
    assert "avg_price" not in sup_data["data"][0]  # stripped when price_dimension_enabled=0

    # Excel export: Chinese sheet title & formula written as literal text cell (data_type='s')
    r_xl = c.get("/report/api/purchase_order_execution?warehouse_id=0&export=excel")
    assert r_xl.status_code == 200
    wb = load_workbook(io.BytesIO(r_xl.data))
    ws = wb.active
    assert ws.title != "Report" and "采购" in ws.title
    formula_cells = [cell for row in ws.iter_rows() for cell in row if cell.value == "=SUM(A1:A2)"]
    assert formula_cells and all(cell.data_type == "s" for cell in formula_cells)

    # print_in.html hides price/amount when price_dimension_enabled=0
    r_print = c.get(f"/in_order/{in_a_id}/print_direct")
    assert r_print.status_code == 200
    p_html = r_print.get_data(as_text=True)
    assert 'class="price-col-hidden">单价</th>' in p_html and 'class="price-col-hidden">金额</th>' in p_html
    assert "数量合计：" in p_html and "40.00" not in p_html


@pytest.mark.skipif(not _IS_LINUX_ISOLATED, reason="Full Flask integration runs on isolated Linux CI")
def test_integration_copy_to_out_print_template_404_and_scoped_stock():
    w, env = _setup_env()
    with w.app.app_context():
        # Order with inactive material -> copy_to_out rejected
        io_off = w.InOrder(
            order_no="IN-OFF-1",
            date=date.today(),
            supplier_id=env["sup_id"],
            warehouse="A仓",
            business_type="采购入库",
            status="completed",
            operator_id=env["user_ids"]["warehouse"],
        )
        w.db.session.add(io_off)
        w.db.session.flush()
        w.db.session.add(w.InOrderItem(in_order_id=io_off.id, material_id=env["m_inactive_id"], quantity=3.0, price=5.0, amount=15.0))

        # Order with customer-supplied item -> copy_to_out rejected (CS-RULE-001)
        io_cs = w.InOrder(
            order_no="IN-CS-1",
            date=date.today(),
            warehouse="A仓",
            business_type="其他入库",
            status="completed",
            operator_id=env["user_ids"]["warehouse"],
        )
        w.db.session.add(io_cs)
        w.db.session.flush()
        w.db.session.add(
            w.InOrderItem(
                in_order_id=io_cs.id,
                material_id=env["m1_id"],
                quantity=2.0,
                price=0.0,
                amount=0.0,
                is_customer_supplied=True,
            )
        )

        # Valid normal order -> copy_to_out succeeds with total_amount, cleared customer, copied contract/project
        io_ok = w.InOrder(
            order_no="IN-OK-1",
            date=date.today(),
            supplier_id=env["sup_id"],
            warehouse="A仓",
            business_type="采购入库",
            contract_no="HT-2026-01",
            project_name="测试工程",
            status="completed",
            operator_id=env["user_ids"]["warehouse"],
        )
        w.db.session.add(io_ok)
        w.db.session.flush()
        w.db.session.add(w.InOrderItem(in_order_id=io_ok.id, material_id=env["m1_id"], quantity=5.0, price=10.0, amount=50.0))

        # Missing-file print templates (in_order & out_order) must return JSON 404, not 500
        in_tpl = w.InOrderPrintTemplate(name="空模板", template_type="excel", excel_template_path="")
        out_tpl = w.OutOrderPrintTemplate(name="空出库模板", template_type="excel", excel_template_path="")
        w.db.session.add_all([in_tpl, out_tpl])
        w.db.session.commit()
        off_id, cs_id, ok_id, in_tpl_id, out_tpl_id = io_off.id, io_cs.id, io_ok.id, in_tpl.id, out_tpl.id

    c = _client_as(w, env["user_ids"]["warehouse"])
    assert c.post(f"/in_order/{off_id}/copy_to_out").status_code == 400
    assert c.post(f"/in_order/{cs_id}/copy_to_out").status_code == 400

    r_ok = c.post(f"/in_order/{ok_id}/copy_to_out")
    assert r_ok.status_code == 200
    out_id = r_ok.get_json()["out_order_id"]
    with w.app.app_context():
        out_doc = w.db.session.get(w.OutOrder, out_id)
        assert out_doc.total_amount == 50.0
        assert (out_doc.customer or "") == ""
        assert out_doc.contract_no == "HT-2026-01" and out_doc.project_name == "测试工程"

        # Verify scoped get_warehouse_stock_quantities and _load_*_for_print helpers
        from routes.in_order import _load_in_order_for_print
        from routes.out_order import _load_out_order_for_print

        loaded_in = _load_in_order_for_print(ok_id)
        loaded_out = _load_out_order_for_print(out_id)
        assert loaded_in.id == ok_id and loaded_out.id == out_id
        wh_a = w.db.session.get(w.Warehouse, env["wh_a_id"])
        assert w.get_warehouse_stock_quantities_for_materials(None) == {}
        assert isinstance(w.get_warehouse_stock_quantities_for_materials(wh_a, material_ids=[env["m1_id"]]), dict)

    r_404_in = c.get(f"/in_order_print_template/{in_tpl_id}/download")
    assert r_404_in.status_code == 404 and r_404_in.get_json()["status"] == "error"
    r_404_out = c.get(f"/out_order_print_template/{out_tpl_id}/download")
    assert r_404_out.status_code == 404 and r_404_out.get_json()["status"] == "error"
