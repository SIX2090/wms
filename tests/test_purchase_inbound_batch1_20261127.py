# -*- coding: utf-8 -*-
"""BUG-2026-11-27-004 回归测试：采购入库第一批 P0 高危缺陷及全仓同类防护（R6）。

覆盖：
- P0-1：选采购单带入 >300 缓存外物料时批量按仓补拉 /material/api/by_codes、写入缓存并填充真实仓库级库存
- P0-2 & P0-3：complete_in_order / batch_complete_in_order / mobile_scan_draft_confirm 共享
  app/services/in_order_completion.py（自动下推领料、PO 状态同步、超收复核、客供归属、未来日期、库位门禁、总额与日志），
  并同步补齐手机确认出库（out_order）的未来日期/库位/总额/日志同源门禁
- P0-4 + R6：in_order.py 3 处导出及全仓其余 8 个单据/报表路由共 21 处 Excel 导出统一接入 _sanitize_excel_cell，
  并修正 batch_export_in_order 无明细草稿行 15→16 列错位及 N+1 预加载
- P0-5 + R6：in_order / out_order / native_api 全写入口拒绝负单价与非有限数
- P0-6：add_in_order 校验 Supplier 外键存在性及 contract_id 安全解析（含 out_order 行级 contract_id）
- P0-7：update_completed_in_order 补齐已完成采购退货行删除/减量保护（409）与已关闭/取消采购单新增拦截
"""
from __future__ import annotations

import ast
import io
import json
import re
import shutil
import subprocess
from datetime import date, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
IN_ORDER_ROUTE = ROOT / "app" / "routes" / "in_order.py"
OUT_ORDER_ROUTE = ROOT / "app" / "routes" / "out_order.py"
MOBILE_ROUTE = ROOT / "app" / "routes" / "mobile.py"
NATIVE_API_ROUTE = ROOT / "app" / "routes" / "native_api.py"
COMPLETION_SVC = ROOT / "app" / "services" / "in_order_completion.py"
IN_ORDER_ADD_HTML = ROOT / "app" / "templates" / "in_order_add.html"


# =============================================================================
# Part A: Pure static / AST / Node-VM tests (runnable without DB / app import)
# =============================================================================

def _extract_func_source(path: Path, func_name: str) -> str:
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            lines = src.splitlines()
            return "\n".join(lines[node.lineno - 1 : node.end_lineno])
    raise AssertionError(f"Function {func_name} not found in {path}")


def _extract_js_function(source: str, signature_prefix: str) -> str:
    start = source.index(signature_prefix)
    brace_open = source.index(") {", start) + 2
    depth = 0
    for idx in range(brace_open, len(source)):
        ch = source[idx]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return source[start : idx + 1]
    raise AssertionError(f"Unclosed JS function: {signature_prefix}")


def test_p0_1_po_selection_fetches_uncached_materials_node_vm():
    """P0-1: applyPurchaseOrderSelectionToForm fetches uncached >300 materials with warehouse stock."""
    node_bin = shutil.which("node")
    assert node_bin, "Node.js is required for frontend runtime verification"
    html = IN_ORDER_ADD_HTML.read_text(encoding="utf-8")
    assert "async function applyPurchaseOrderSelectionToForm()" in html
    fn_src = _extract_js_function(html, "async function applyPurchaseOrderSelectionToForm()")
    find_fn = _extract_js_function(html, "function findMaterialByCode(")
    unit_fn = _extract_js_function(html, "function getMaterialUnit(")
    stock_fn = _extract_js_function(html, "function formatStock(")
    qty_fn = _extract_js_function(html, "function formatQtyTrim(")
    fill_fn = _extract_js_function(html, "function fillMaterialFields(")
    purpose_fn = _extract_js_function(html, "function fillPurposeFromMaterial(")
    po_qty_fn = _extract_js_function(html, "function formatPurchaseQty(")

    harness = r"""
const vm = require('node:vm');
const assert = require('node:assert/strict');
const payload = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));

function makeField(val = '') {
  return { value: val, dataset: {}, focus() {}, getAttribute(k) { return k === 'max' ? '10' : null; } };
}
function makeRow() {
  const fields = {
    '.material-code': makeField(''),
    '.material-brand': makeField(''),
    '.material-name': makeField(''),
    '.material-spec': makeField(''),
    '.material-unit': makeField(''),
    '.material-stock': makeField(''),
    '.material-qty': makeField(''),
    '.material-price': makeField(''),
  };
  return {
    dataset: {},
    querySelector(sel) { return fields[sel] || null; },
    remove() { const i = bodyRows.indexOf(this); if (i >= 0) bodyRows.splice(i, 1); },
  };
}

let bodyRows = [];
let apiCalls = [];
let toasts = [];
let modalRemoved = false;
let confirmBtn = { disabled: false, isConnected: true };
let modalEl = { isConnected: true, remove() { modalRemoved = true; this.isConnected = false; } };
let mode = 'ok';

const poCheckbox = {
  dataset: { itemId: '501' },
  focus() {},
  closest() { return { querySelector(sel) { return sel === '.po-select-qty' ? makeField('3') : null; } }; },
};

const ctx = {
  URLSearchParams,
  Number, Array, Set, Map, String, parseFloat,
  materials: [{ code: 'M001', name: '缓存内物料', brand: 'B1', spec: 'S1', unit: { name: '个' }, stock: 5, price: 2 }],
  purchaseOrderSelectableMap: new Map([
    ['501', {
      purchase_order_item_id: 501,
      purchase_order_no: 'PO-999',
      supplier_id: 88,
      supplier_name: '供应商甲',
      material_code: 'M999',
      brand: '旧品牌',
      material_name: '300缓存外物料',
      spec: 'X99',
      unit: '套',
      price: 18.5,
    }],
  ]),
  WMS: {
    materialCache: { warehouseFromForm() { return '主仓库'; } },
    api: {
      async get(url) {
        apiCalls.push(url);
        if (mode === 'error') throw new Error('network down');
        if (mode === 'missing') return [];
        return [{ code: 'M999', name: '300缓存外物料', brand: '真实品牌', spec: 'X99', unit: { name: '套' }, stock: 42.5, price: 99 }];
      },
    },
  },
  document: {
    getElementById(id) {
      if (id === 'purchaseOrderSelectModal') return modalEl.isConnected ? modalEl : null;
      if (id === 'materialTableBody') return { querySelectorAll() { return bodyRows.slice(); } };
      return null;
    },
    querySelector(sel) {
      if (sel.includes('applyPurchaseOrderSelectionToForm')) return confirmBtn;
      if (sel === '#materialTableBody tr:last-child') return bodyRows[bodyRows.length - 1] || null;
      if (sel === '[name="remark"]') return { value: '' };
      if (sel === '[name="purpose"]') return { value: '' };
      return null;
    },
    querySelectorAll(sel) {
      if (sel === '#purchaseOrderSelectBody .po-select-row:checked') return [poCheckbox];
      return [];
    },
  },
  showToast(msg, type) { toasts.push({ msg, type }); },
  findEmptyRow() { return null; },
  addNewRow() { const r = makeRow(); bodyRows.push(r); return r; },
  calcAmount() {},
  calcTotal() {},
  renumberRows() {},
  setHeaderSupplier() {},
};
ctx.window = ctx;
vm.createContext(ctx);
for (const chunk of payload.chunks) vm.runInContext(chunk, ctx);

(async () => {
  // Case 1: network error -> danger toast, modal stays open, no fake 0.00 row added
  mode = 'error';
  await ctx.applyPurchaseOrderSelectionToForm();
  assert.equal(bodyRows.length, 0);
  assert.equal(modalRemoved, false);
  assert.equal(confirmBtn.disabled, false);
  assert.ok(toasts.some(t => t.type === 'danger' && t.msg.includes('获取物料及仓库库存失败')));

  // Case 2: unresolved/inactive material -> danger toast, modal stays open
  mode = 'missing';
  toasts = [];
  await ctx.applyPurchaseOrderSelectionToForm();
  assert.equal(bodyRows.length, 0);
  assert.equal(modalRemoved, false);
  assert.ok(toasts.some(t => t.type === 'danger' && t.msg.includes('M999')));

  // Case 3: success -> fetches /material/api/by_codes with warehouse, populates cache & real stock, keeps PO price
  mode = 'ok';
  toasts = [];
  apiCalls = [];
  await ctx.applyPurchaseOrderSelectionToForm();
  assert.equal(apiCalls.length, 1);
  assert.ok(apiCalls[0].includes('/material/api/by_codes?'));
  assert.ok(apiCalls[0].includes('code=M999'));
  assert.ok(apiCalls[0].includes('warehouse='));
  assert.ok(ctx.findMaterialByCode('M999'), 'M999 must be cached so submitForm passes');
  assert.equal(bodyRows.length, 1);
  assert.equal(bodyRows[0].querySelector('.material-stock').value, '42.50');
  assert.equal(bodyRows[0].querySelector('.material-price').value, '18.50');
  assert.equal(bodyRows[0].dataset.sourcePurchaseOrderItemId, 501);
  assert.equal(modalRemoved, true);
})().catch(err => { console.error(err); process.exit(1); });
"""
    chunks = [stock_fn, qty_fn, find_fn, unit_fn, purpose_fn, fill_fn, po_qty_fn, fn_src]
    proc = subprocess.run(
        [node_bin, "-e", harness],
        input=json.dumps({"chunks": chunks}),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=20,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_p0_2_p0_3_completion_paths_share_service_ast():
    """P0-2 & P0-3: single, batch, and mobile confirm all delegate to in_order_completion service."""
    assert COMPLETION_SVC.is_file()
    svc_src = COMPLETION_SVC.read_text(encoding="utf-8")
    for fn in (
        "check_supplied_receipt_order",
        "check_purchase_over_receive_for_order",
        "sync_in_order_purchase_order_statuses",
        "execute_auto_push_requisition",
    ):
        assert f"def {fn}(" in svc_src

    single_src = _extract_func_source(IN_ORDER_ROUTE, "complete_in_order")
    batch_src = _extract_func_source(IN_ORDER_ROUTE, "batch_complete_in_order")
    mobile_src = _extract_func_source(MOBILE_ROUTE, "mobile_scan_draft_confirm")

    for name, body in (("complete_in_order", single_src), ("batch_complete_in_order", batch_src), ("mobile_scan_draft_confirm", mobile_src)):
        assert "execute_auto_push_requisition" in body, f"{name} must run auto_push_requisition"
        assert "sync_in_order_purchase_order_statuses" in body, f"{name} must sync PO statuses"
        assert "log_operation(" in body, f"{name} must write operation log"

    for guard in (
        "is_future_date",
        "location_management_enabled",
        "check_supplied_receipt_order",
        "validate_purchase_in_order_source",
        "check_purchase_over_receive_for_order",
        "order.total_amount = round_to_2_decimals",
    ):
        assert guard in mobile_src, f"mobile_scan_draft_confirm missing {guard}"


def test_p0_4_all_document_and_report_exports_sanitize_excel_ast():
    """P0-4 + R6: all 21 document/report Excel export functions sanitize cells & batch_export aligns 16 cols."""
    targets = [
        (ROOT / "app/routes/in_order.py", "_build_in_order_excel"),
        (ROOT / "app/routes/in_order.py", "batch_export_in_order"),
        (ROOT / "app/routes/in_order.py", "export_single_in_order"),
        (ROOT / "app/routes/out_order.py", "_build_out_order_excel"),
        (ROOT / "app/routes/out_order.py", "export_out_order"),
        (ROOT / "app/routes/out_order.py", "export_single_out_order"),
        (ROOT / "app/routes/requisition.py", "export_single_requisition"),
        (ROOT / "app/routes/transfer.py", "export_single_transfer"),
        (ROOT / "app/routes/check.py", "export_single_check"),
        (ROOT / "app/routes/bom.py", "export_bom"),
        (ROOT / "app/routes/report.py", "report_inout_print"),
        (ROOT / "app/routes/report.py", "report_stock_print"),
        (ROOT / "app/routes/sales.py", "export_sales_outbound"),
        (ROOT / "app/routes/sales.py", "export_sales_orders"),
        (ROOT / "app/routes/sales.py", "export_sales_report"),
        (ROOT / "app/routes/sales.py", "export_sales_reconciliation_report"),
        (ROOT / "app/routes/sales.py", "export_sales_outflow_report"),
        (ROOT / "app/routes/sales.py", "export_sales_trend_report"),
        (ROOT / "app/routes/sales.py", "export_sales_execution_report"),
        (ROOT / "app/routes/sales.py", "export_sales_price_analysis"),
        (ROOT / "app/routes/ai_excel.py", "api_document_ocr_excel"),
    ]
    for file_path, fn_name in targets:
        body = _extract_func_source(file_path, fn_name)
        assert "_sanitize_excel_cell" in body, f"{file_path.name}:{fn_name} missing _sanitize_excel_cell"

    # Verify batch_export_in_order empty-items branch emits 16 items matching its 16-column header
    batch_exp_src = _extract_func_source(IN_ORDER_ROUTE, "batch_export_in_order")
    tree = ast.parse("def _wrap():\n" + "\n".join("    " + ln for ln in batch_exp_src.splitlines()))
    header_len = None
    data_list_lens = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "append":
            if node.args and isinstance(node.args[0], ast.List):
                header_len = len(node.args[0].elts)
            elif node.args and isinstance(node.args[0], ast.ListComp):
                comp_iter = node.args[0].generators[0].iter
                if isinstance(comp_iter, ast.List):
                    data_list_lens.append(len(comp_iter.elts))
    assert header_len == 16
    assert data_list_lens == [16, 16], f"batch_export_in_order column mismatch: {data_list_lens}"


def test_p0_5_p0_6_p0_7_inbound_and_peer_guards_ast():
    """P0-5/6/7 + R6: negative price guards, Supplier FK + contract_id safe parse, return & closed PO guards."""
    for path, fn in (
        (IN_ORDER_ROUTE, "add_in_order"),
        (IN_ORDER_ROUTE, "add_in_order_item"),
        (IN_ORDER_ROUTE, "batch_add_in_order_items"),
        (IN_ORDER_ROUTE, "update_in_order_item"),
        (IN_ORDER_ROUTE, "update_completed_in_order"),
        (OUT_ORDER_ROUTE, "add_out_order"),
        (OUT_ORDER_ROUTE, "add_out_order_item"),
        (OUT_ORDER_ROUTE, "update_out_order_item"),
        (NATIVE_API_ROUTE, "native_api_inbound"),
        (NATIVE_API_ROUTE, "native_api_outbound"),
    ):
        body = _extract_func_source(path, fn)
        assert "< 0" in body and "单价不能小于" in body, f"{path.name}:{fn} missing negative price guard"

    add_in_src = _extract_func_source(IN_ORDER_ROUTE, "add_in_order")
    assert "db.session.get(Supplier, int(supplier_id))" in add_in_src
    assert "合同ID格式不正确" in add_in_src

    upd_comp_src = _extract_func_source(IN_ORDER_ROUTE, "update_completed_in_order")
    assert "_purchase_returned_quantity_by_source_item" in upd_comp_src
    assert "已完成采购退货" in upd_comp_src
    assert "('closed', 'cancelled')" in upd_comp_src


# =============================================================================
# Part B: Full isolated Flask + SQLite integration tests (Linux CI)
# =============================================================================

def _setup_case():
    import app as w
    from werkzeug.security import generate_password_hash

    w.app.config["TESTING"] = True
    w.app.config["WTF_CSRF_ENABLED"] = False
    w.db.session.remove()
    w.db.drop_all()
    w.db.create_all()

    unit = w.Unit(code="PCS", name="个")
    wh = w.Warehouse(code="WH-B1", name="采购主仓", is_default=True, status="active")
    sup = w.Supplier(code="SUP-B1", name="=CMD|' /C calc'!A0")
    cust = w.Customer(code="CUST-B1", name="测试客户")
    user = w.User(
        username="b1_admin",
        password_hash=generate_password_hash("admin"),
        role="admin",
        status="normal",
        must_change_password=False,
    )
    mat = w.Material(code="M-B1-001", name="+SUM(1,2)", spec="S1", unit=unit, stock=0, price=10)
    w.db.session.add_all([unit, wh, sup, cust, user, mat])
    w.db.session.flush()
    w.set_system_setting("location_management_enabled", "0")
    w.set_system_setting("allow_negative_stock", "0")
    w.db.session.commit()

    client = w.app.test_client()
    client.post("/login", data={"username": "b1_admin", "password": "admin"})
    return w, client, {
        "wh": wh.id, "wh_name": wh.name, "sup": sup.id, "cust": cust.id,
        "user": user.id, "mat": mat.id, "mat_code": mat.code,
    }


def test_check_supplied_receipt_order():
    """A9 anchor + unit behavior for check_supplied_receipt_order."""
    from types import SimpleNamespace as NS
    from services.in_order_completion import check_supplied_receipt_order

    bad_type = NS(business_type="采购入库", customer_id=1, items=[NS(is_customer_supplied=True)])
    assert "其他入库" in (check_supplied_receipt_order(bad_type) or "")

    bad_cust = NS(business_type="其他入库", customer_id=None, items=[NS(is_customer_supplied=True)])
    assert "客户" in (check_supplied_receipt_order(bad_cust) or "")

    ok_order = NS(business_type="其他入库", customer_id=2, items=[NS(is_customer_supplied=True)])
    assert check_supplied_receipt_order(ok_order) is None


def test_check_purchase_over_receive_for_order():
    """A9 anchor + integration test for check_purchase_over_receive_for_order via mobile confirm."""
    import app as w

    with w.app.app_context():
        w, client, ids = _setup_case()
        w.set_system_setting("purchase_receipt_strict_order", "1")
        w.set_system_setting("purchase_over_receive_control_mode", "forbid")
        po = w.PurchaseOrder(order_no="PO-OVR-1", supplier_id=ids["sup"], status="pending", total_amount=50)
        w.db.session.add(po)
        w.db.session.flush()
        poi = w.PurchaseOrderItem(purchase_order_id=po.id, material_id=ids["mat"], quantity=5, received_quantity=8, price=10, amount=50)
        order = w.InOrder(order_no="IN-OVR-1", date=date.today(), business_type="采购入库", supplier_id=ids["sup"], warehouse=ids["wh_name"], status="pending")
        w.db.session.add_all([poi, order])
        w.db.session.flush()
        w.db.session.add(w.InOrderItem(in_order_id=order.id, material_id=ids["mat"], source_purchase_order_item_id=poi.id, quantity=8, price=10, amount=80))
        w.db.session.commit()

        resp = client.post(f"/mobile/api/scan_draft_confirm/{order.id}", json={"order_type": "in"})
        assert resp.status_code == 400, resp.get_json()
        assert "未入库数量" in resp.get_json()["msg"]
        assert w.db.session.get(w.InOrder, order.id).status == "pending"


def test_sync_in_order_purchase_order_statuses():
    """A9 anchor + integration test: mobile confirm syncs PO status and recalculates total_amount."""
    import app as w

    with w.app.app_context():
        w, client, ids = _setup_case()
        po = w.PurchaseOrder(order_no="PO-SYNC-1", supplier_id=ids["sup"], status="pending", total_amount=50)
        w.db.session.add(po)
        w.db.session.flush()
        poi = w.PurchaseOrderItem(purchase_order_id=po.id, material_id=ids["mat"], quantity=5, received_quantity=5, price=10, amount=50)
        order = w.InOrder(
            order_no="IN-SYNC-1", date=date.today(), business_type="采购入库",
            supplier_id=ids["sup"], warehouse=ids["wh_name"], status="pending", total_amount=0,
        )
        w.db.session.add_all([poi, order])
        w.db.session.flush()
        w.db.session.add(w.InOrderItem(in_order_id=order.id, material_id=ids["mat"], source_purchase_order_item_id=poi.id, quantity=5, price=10, amount=50))
        w.db.session.commit()

        resp = client.post(f"/mobile/api/scan_draft_confirm/{order.id}", json={"order_type": "in"})
        assert resp.status_code == 200, resp.get_json()
        assert w.db.session.get(w.InOrder, order.id).total_amount == pytest.approx(50.0)
        assert w.db.session.get(w.PurchaseOrder, po.id).status == "completed"


def test_execute_auto_push_requisition():
    """A9 anchor + P0-2/P0-3 integration test: batch_complete & mobile confirm both execute auto_push_requisition."""
    import app as w

    with w.app.app_context():
        w, client, ids = _setup_case()
        o1 = w.InOrder(
            order_no="IN-AUTO-BATCH", date=date.today(), business_type="采购入库",
            supplier_id=ids["sup"], warehouse=ids["wh_name"], status="pending", auto_push_requisition=True,
        )
        o2 = w.InOrder(
            order_no="IN-AUTO-MOB", date=date.today(), business_type="采购入库",
            supplier_id=ids["sup"], warehouse=ids["wh_name"], status="pending", auto_push_requisition=True,
        )
        w.db.session.add_all([o1, o2])
        w.db.session.flush()
        w.db.session.add_all([
            w.InOrderItem(in_order_id=o1.id, material_id=ids["mat"], quantity=4, price=10, amount=40),
            w.InOrderItem(in_order_id=o2.id, material_id=ids["mat"], quantity=3, price=10, amount=30),
        ])
        w.db.session.commit()

        r_batch = client.post("/in_order/batch_complete", json={"ids": [o1.id]})
        assert r_batch.status_code == 200 and r_batch.get_json()["completed"] == 1, r_batch.get_json()
        assert w.db.session.get(w.Material, ids["mat"]).stock == pytest.approx(0.0)
        assert w.OutOrder.query.filter_by(business_type="领料单", status="completed").count() == 1
        assert w.OperationLog.query.filter_by(target_type="in_order", target_id=o1.id).count() >= 1

        r_mob = client.post(f"/mobile/api/scan_draft_confirm/{o2.id}", json={"order_type": "in"})
        assert r_mob.status_code == 200 and r_mob.get_json()["data"].get("auto_requisition_id"), r_mob.get_json()
        assert w.db.session.get(w.Material, ids["mat"]).stock == pytest.approx(0.0)
        assert w.OutOrder.query.filter_by(business_type="领料单", status="completed").count() == 2

        # Mobile confirm also rejects future date & empty location when location management is on
        o_future = w.InOrder(
            order_no="IN-FUT-1", date=date.today() + timedelta(days=2), business_type="采购入库",
            supplier_id=ids["sup"], warehouse=ids["wh_name"], status="pending",
        )
        w.db.session.add(o_future)
        w.db.session.flush()
        w.db.session.add(w.InOrderItem(in_order_id=o_future.id, material_id=ids["mat"], quantity=1, price=10, amount=10))
        w.db.session.commit()
        r_fut = client.post(f"/mobile/api/scan_draft_confirm/{o_future.id}", json={"order_type": "in"})
        assert r_fut.status_code == 400 and "晚于今天" in r_fut.get_json()["msg"]


def test_p0_4_batch_and_single_export_formula_sanitization_and_alignment():
    """P0-4: batch_export empty row has 16 aligned columns and neutralizes formula payloads."""
    import app as w
    from openpyxl import load_workbook

    with w.app.app_context():
        w, client, ids = _setup_case()
        o_with = w.InOrder(
            order_no="IN-EXP-1", date=date.today(), business_type="采购入库",
            supplier_id=ids["sup"], warehouse=ids["wh_name"], status="pending", remark="@HYPERLINK(\"x\")",
        )
        o_empty = w.InOrder(
            order_no="IN-EXP-EMPTY", date=date.today(), business_type="采购入库",
            supplier_id=ids["sup"], warehouse=ids["wh_name"], status="pending", remark="=1+1",
        )
        w.db.session.add_all([o_with, o_empty])
        w.db.session.flush()
        w.db.session.add(w.InOrderItem(in_order_id=o_with.id, material_id=ids["mat"], quantity=2, price=10, amount=20))
        w.db.session.commit()

        resp = client.post("/in_order/batch_export", json={"ids": [o_with.id, o_empty.id]})
        assert resp.status_code == 200
        wb = load_workbook(io.BytesIO(resp.data))
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        assert len(rows[0]) == 16
        assert len(rows[1]) == 16 and len(rows[2]) == 16
        # Verify formula prefixes neutralized & empty row status/remark in columns 15/16 (idx 14/15)
        by_no = {r[0]: r for r in rows[1:]}
        assert str(by_no["IN-EXP-1"][3]).startswith("'")
        assert str(by_no["IN-EXP-1"][6]).startswith("'")
        assert str(by_no["IN-EXP-1"][15]).startswith("'")
        assert by_no["IN-EXP-EMPTY"][14] == "待完成"
        assert by_no["IN-EXP-EMPTY"][15] == "'=1+1"

        single = client.get(f"/in_order/{o_with.id}/export")
        assert single.status_code == 200
        swb = load_workbook(io.BytesIO(single.data))
        srows = list(swb.active.iter_rows(values_only=True))
        assert str(srows[1][3]).startswith("'")
        assert str(srows[1][6]).startswith("'")
        assert str(srows[1][14]).startswith("'")


def test_p0_5_p0_6_negative_price_and_invalid_supplier_contract_rejected():
    """P0-5 & P0-6: negative prices, nonexistent supplier_id, and non-int contract_id return 400."""
    import app as w

    with w.app.app_context():
        w, client, ids = _setup_case()
        base = {
            "business_type": "采购入库", "warehouse_id": ids["wh"], "supplier_id": ids["sup"],
            "date": date.today().isoformat(),
            "items": [{"code": ids["mat_code"], "quantity": 2, "price": -5}],
        }
        r_neg = client.post("/in_order/add", json=base)
        assert r_neg.status_code == 400 and "单价不能小于0" in r_neg.get_json()["msg"]

        r_bad_sup = client.post("/in_order/add", json={**base, "supplier_id": 999999, "items": [{"code": ids["mat_code"], "quantity": 2, "price": 5}]})
        assert r_bad_sup.status_code == 400 and "供应商" in r_bad_sup.get_json()["msg"]

        r_bad_cid = client.post("/in_order/add", json={**base, "contract_id": "abc", "items": [{"code": ids["mat_code"], "quantity": 2, "price": 5}]})
        assert r_bad_cid.status_code == 400 and "合同ID" in r_bad_cid.get_json()["msg"]

        r_out_neg = client.post("/out_order/add", json={
            "business_type": "领料单", "warehouse_id": ids["wh"], "date": date.today().isoformat(),
            "items": [{"code": ids["mat_code"], "quantity": 1, "price": -1}],
        })
        assert r_out_neg.status_code == 400 and "单价不能小于0" in r_out_neg.get_json()["msg"]


def test_p0_7_update_completed_blocks_returned_delete_reduce_and_closed_po():
    """P0-7: update_completed_in_order blocks deleting/reducing returned lines and adding from closed PO."""
    import app as w
    from tests.document_revision_client import document_post

    with w.app.app_context():
        w, client, ids = _setup_case()
        po_closed = w.PurchaseOrder(order_no="PO-CLOSED", supplier_id=ids["sup"], status="closed", total_amount=100)
        in_order = w.InOrder(
            order_no="IN-RET-1", date=date.today(), business_type="采购入库",
            supplier_id=ids["sup"], warehouse=ids["wh_name"], status="pending",
        )
        w.db.session.add_all([po_closed, in_order])
        w.db.session.flush()
        closed_poi = w.PurchaseOrderItem(purchase_order_id=po_closed.id, material_id=ids["mat"], quantity=10, received_quantity=0, price=10, amount=100)
        in_item = w.InOrderItem(in_order_id=in_order.id, material_id=ids["mat"], quantity=10, price=10, amount=100)
        w.db.session.add_all([closed_poi, in_item])
        w.db.session.commit()

        assert document_post(client, f"/in_order/{in_order.id}/complete?force=1").status_code == 200

        # Create completed purchase return of 4 against in_item
        ret_out = w.OutOrder(
            order_no="OUT-PRET-1", date=date.today(), business_type="采购退货出库",
            warehouse=ids["wh_name"], status="completed", source_in_order_id=in_order.id,
        )
        w.db.session.add(ret_out)
        w.db.session.flush()
        w.db.session.add(w.OutOrderItem(
            out_order_id=ret_out.id, material_id=ids["mat"],
            source_in_order_item_id=in_item.id, quantity=4, price=10, amount=40,
        ))
        w.db.session.commit()

        # 1. Deleting returned item blocked with 409
        r_del = document_post(client, f"/in_order/{in_order.id}/update_completed", json={
            "reason": "删行测试", "deleted_items": [in_item.id], "items": [],
        })
        assert r_del.status_code == 409 and "已完成采购退货" in r_del.get_json()["msg"]

        # 2. Reducing below returned qty (3 < 4) blocked with 409
        r_red = document_post(client, f"/in_order/{in_order.id}/update_completed", json={
            "reason": "减量测试", "deleted_items": [], "items": [{"id": in_item.id, "quantity": 3, "price": 10}],
        })
        assert r_red.status_code == 409 and "已完成采购退货" in r_red.get_json()["msg"]

        # 3. Adding negative price blocked with 400
        r_neg = document_post(client, f"/in_order/{in_order.id}/update_completed", json={
            "reason": "负价测试", "deleted_items": [], "items": [{"id": in_item.id, "quantity": 10, "price": -2}],
        })
        assert r_neg.status_code == 400 and "单价不能小于0" in r_neg.get_json()["msg"]

        # 4. Adding line from closed PO blocked with 400
        r_closed = document_post(client, f"/in_order/{in_order.id}/update_completed", json={
            "reason": "关单测试", "deleted_items": [],
            "items": [{"is_new": True, "code": ids["mat_code"], "quantity": 2, "price": 10, "source_purchase_order_item_id": closed_poi.id}],
        })
        assert r_closed.status_code == 400 and "已关闭或取消" in r_closed.get_json()["msg"]

        # 5. Reducing to >= returned qty (6 >= 4) succeeds
        r_ok = document_post(client, f"/in_order/{in_order.id}/update_completed", json={
            "reason": "合法核减", "deleted_items": [], "items": [{"id": in_item.id, "quantity": 6, "price": 10}],
        })
        assert r_ok.status_code == 200, r_ok.get_json()
        assert w.db.session.get(w.InOrderItem, in_item.id).quantity == pytest.approx(6.0)
